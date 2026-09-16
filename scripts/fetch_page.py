#!/usr/bin/env python3
"""fetch_page.py — fetch an article past Cloudflare-style bot walls and extract text + media.

Usage:
  uv run --with curl_cffi --with trafilatura python3 scripts/fetch_page.py <url> <out_dir> [--json]
  uv run --with curl_cffi --with trafilatura python3 scripts/fetch_page.py --from-html page.html <out_dir> [--base-url URL] [--json]
  python3 scripts/fetch_page.py --from-text notes.txt <out_dir> [--json]

Writes into <out_dir>:
  page.html    the fetched (or given) HTML — not written for --from-text
  article.md   "# <title>" first, then trafilatura markdown (tables kept); regex fallback when trafilatura
               is unavailable or returns < 800 chars
  media.json   [{kind: "mp4"|"embed"|"image", url, title, alt, size, w, h, order}] in page order
               (0 = unknown for size/w/h)

Media sources: Contentful assets inside Next.js `__next_f` payloads (openai.com), <video>/<source>, og:video,
bare .mp4/.webm/.mov/.m3u8 URLs, Vimeo/YouTube/bilibili/腾讯视频 iframes → kind "embed", <img src|data-src|
data-original>, srcset (largest candidate), <picture><source srcset>, og:image; 微信公众号 (mmbiz.qpic.cn data-src
images, mpvideo iframes → embed). Skipped: data: URIs, .svg, tracking pixels (< 200 px), duplicates, images inside
<nav>/<footer>/<header> (outside <main>/<article>).

Exit codes: 0 ok · 2 usage / missing module · 3 HTTP status != 200 or network error.
Fallback when a site blocks the fetch: save the page as HTML in a browser → --from-html, or paste the text → --from-text.
"""
import bisect
import datetime
import html as htmllib
import json
import pathlib
import re
import sys
import urllib.parse
from html.parser import HTMLParser

UV_HINT = "uv run --with curl_cffi --with trafilatura python3 scripts/fetch_page.py …"
ACCEPT_LANGUAGE = "en-US,en;q=0.9,zh-CN;q=0.8"
MIN_TRAFILATURA_CHARS = 800
MIN_IMAGE_PX = 200
IMG_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".avif", ".bmp", ".tif", ".tiff", ".heic", ".jfif")
VID_EXT = (".mp4", ".webm", ".mov", ".m3u8")
VIDEO_EXT_RE = re.compile(r"\.(?:mp4|webm|mov|m3u8)(?:$|[?#])", re.I)
EMBED_RE = re.compile(r"https?://(?:player\.vimeo\.com/video/\d+|www\.youtube\.com/embed/[\w-]+|youtu\.be/[\w-]+)")
EMBED_HOSTS = ("player.vimeo.com", "vimeo.com", "youtube.com", "youtube-nocookie.com", "youtu.be",
               "player.bilibili.com", "bilibili.com", "v.qq.com", "player.youku.com", "open.iqiyi.com", "mp.weixin.qq.com")
SKIP_TAGS = ("nav", "footer", "header")
MAIN_TAGS = ("main", "article")

JSON_MODE = False


def log(*a):
    """Human-readable progress; stderr in --json mode so stdout stays machine-readable."""
    print(*a, file=sys.stderr if JSON_MODE else sys.stdout, flush=True)


def die(msg, code=1):
    print(f"fetch_page.py: {msg}", file=sys.stderr)
    sys.exit(code)


# ----------------------------------------------------------------------------- url helpers
def norm_url(u, base):
    if not u:
        return None
    u = htmllib.unescape(u).strip().strip("'\"")
    if not u or u.startswith(("data:", "blob:", "javascript:", "about:", "#")):
        return None
    if u.startswith("//"):
        u = "https:" + u
    if base and not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", u):
        u = urllib.parse.urljoin(base, u)
    if not u.startswith(("http://", "https://")):
        return None
    return u


def path_of(u):
    return urllib.parse.urlsplit(u).path.lower()


def is_svg(u):
    return path_of(u).endswith(".svg") or "image/svg" in u.lower()


def is_embed_url(u):
    host = urllib.parse.urlsplit(u).netloc.lower()
    return any(host == h or host.endswith("." + h) for h in EMBED_HOSTS)


def video_kind(u):
    return "embed" if is_embed_url(u) else "mp4"


QUERY_ID_HOSTS = ("mp.weixin.qq.com", "v.qq.com", "bilibili.com", "player.bilibili.com")


def dedupe_key(u, kind="image"):
    """Same asset with a different query (CDN sizing / player flags) counts once when the path has a media
    extension or the URL is a Vimeo/YouTube-style embed (id in the path)."""
    p = urllib.parse.urlsplit(u)
    path = p.path
    host = p.netloc.lower()
    if kind == "embed":
        keep_query = any(host == h or host.endswith("." + h) for h in QUERY_ID_HOSTS)
    else:
        keep_query = not path.lower().endswith(IMG_EXT + VID_EXT)
    return (host, path, p.query if keep_query else "")


def parse_srcset(srcset):
    """→ [(url, width_or_0, density_or_0)] ; tolerant of commas inside URLs."""
    if not srcset:
        return []
    out = []
    for m in re.finditer(r"(\S+?)\s+(\d+(?:\.\d+)?)([wx])\s*(?:,|$)", srcset):
        url, num, unit = m.group(1), float(m.group(2)), m.group(3)
        out.append((url, int(num) if unit == "w" else 0, num if unit == "x" else 0))
    if not out:
        for part in re.split(r",\s+", srcset.strip()):
            url = part.strip().split()[0] if part.strip() else ""
            if url:
                out.append((url, 0, 0))
    return out


def best_candidate(cands):
    """Largest srcset candidate: max width descriptor, else max density, else the last one."""
    if not cands:
        return None, 0
    with_w = [c for c in cands if c[1]]
    if with_w:
        c = max(with_w, key=lambda c: c[1])
        return c[0], c[1]
    with_x = [c for c in cands if c[2]]
    if with_x:
        return max(with_x, key=lambda c: c[2])[0], 0
    return cands[-1][0], 0


def to_int(v):
    if v is None:
        return 0
    m = re.match(r"\s*(\d+(?:\.\d+)?)\s*(?:px)?\s*$", str(v))
    return int(float(m.group(1))) if m else 0


# ----------------------------------------------------------------------------- media collector
class Media:
    def __init__(self):
        self.items = []
        self.index = {}

    def add(self, kind, url, base=None, title="", alt="", size=0, w=0, h=0, pos=0):
        url = norm_url(url, base)
        if not url:
            return
        if kind == "image" and is_svg(url):
            return
        if kind == "image" and ((w and w < MIN_IMAGE_PX) or (h and h < MIN_IMAGE_PX)):
            return
        key = (kind if kind != "embed" else "video", *dedupe_key(url, kind))
        if key in self.index:
            cur = self.items[self.index[key]]
            for k, v in (("title", title), ("alt", alt), ("size", size), ("w", w), ("h", h)):
                if v and not cur[k]:
                    cur[k] = v
            return
        self.index[key] = len(self.items)
        self.items.append({"kind": kind, "url": url, "title": (title or "").strip(), "alt": (alt or "").strip(),
                           "size": int(size or 0), "w": int(w or 0), "h": int(h or 0), "_pos": pos})

    def finish(self):
        self.items.sort(key=lambda m: m["_pos"])
        for i, m in enumerate(self.items):
            m.pop("_pos", None)
            m["order"] = i
        return self.items


class PageParser(HTMLParser):
    """Walks the HTML once, in order; feeds <img>/<picture>/<video>/<source>/<iframe>/<meta> into Media."""

    def __init__(self, text, base, media):
        super().__init__(convert_charrefs=True)
        self.line_starts = [0] + [m.end() for m in re.finditer("\n", text)]
        self.base = base
        self.media = media
        self.title = ""
        self.og_title = ""
        self.og_url = ""
        self.base_href = ""
        self.h1 = ""
        self.skip = 0          # inside nav/footer/header …
        self.main = 0          # … unless inside main/article
        self.in_video = 0
        self.in_picture = 0
        self.picture_cands = []
        self.picture_done = False
        self._text_target = None
        self._last_og_image = None

    def pos(self):
        line, off = self.getpos()
        return self.line_starts[line - 1] + off

    def add(self, kind, url, **kw):
        self.media.add(kind, url, base=self.base, pos=self.pos(), **kw)

    # -- tags
    def handle_starttag(self, tag, attrs):
        a = {}
        for k, v in attrs:
            if k not in a:
                a[k] = v if v is not None else ""
        if tag in MAIN_TAGS:
            self.main += 1
        elif tag in SKIP_TAGS:
            self.skip += 1
        elif tag == "base" and a.get("href") and not self.base_href:
            self.base_href = a["href"]
            self.base = norm_url(a["href"], self.base) or self.base
        elif tag == "title":
            self._text_target = "title"
        elif tag == "h1" and not self.h1:
            self._text_target = "h1"
        elif tag == "meta":
            self.handle_meta(a)
        elif tag == "picture":
            self.in_picture += 1
            self.picture_cands = []
            self.picture_done = False
        elif tag == "video":
            self.in_video += 1
            for k in ("src", "data-src"):
                if a.get(k):
                    self.add(video_kind(norm_url(a[k], self.base) or a[k]), a[k], title=a.get("title", ""), alt=a.get("aria-label", ""))
        elif tag == "source":
            self.handle_source(a)
        elif tag == "img":
            self.handle_img(a)
        elif tag == "iframe":
            self.handle_iframe(a)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag in ("picture", "video", "title", "h1") or tag in MAIN_TAGS or tag in SKIP_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag in MAIN_TAGS:
            self.main = max(0, self.main - 1)
        elif tag in SKIP_TAGS:
            self.skip = max(0, self.skip - 1)
        elif tag in ("title", "h1"):
            self._text_target = None
        elif tag == "picture":
            if not self.picture_done and self.picture_cands and not self.excluded():
                url, w = best_candidate(self.picture_cands)
                self.add("image", url, w=w)
            self.in_picture = max(0, self.in_picture - 1)
            self.picture_cands = []
        elif tag == "video":
            self.in_video = max(0, self.in_video - 1)

    def handle_data(self, data):
        if self._text_target == "title" and data.strip():
            self.title += data
        elif self._text_target == "h1" and data.strip():
            self.h1 += data

    # -- helpers
    def excluded(self):
        return self.skip > 0 and self.main == 0

    def handle_meta(self, a):
        prop = (a.get("property") or a.get("name") or "").lower()
        content = a.get("content") or ""
        if not content:
            return
        if prop == "og:title" and not self.og_title:
            self.og_title = content
        elif prop == "og:url" and not self.og_url:
            self.og_url = content
        elif prop in ("og:image", "og:image:url", "og:image:secure_url", "twitter:image", "twitter:image:src"):
            before = len(self.media.items)
            self.add("image", content, title=self.og_title, alt="og:image")
            self._last_og_image = self.media.items[-1] if len(self.media.items) > before else None
        elif prop in ("og:image:width", "og:image:height") and self._last_og_image is not None:
            key = "w" if prop.endswith("width") else "h"
            v = to_int(content)
            if v and not self._last_og_image[key]:
                self._last_og_image[key] = v
        elif prop in ("og:video", "og:video:url", "og:video:secure_url"):
            u = norm_url(content, self.base)
            if u:
                self.add(video_kind(u), u, title=self.og_title)

    def handle_source(self, a):
        if self.in_video:
            src = a.get("src") or a.get("data-src") or ""
            typ = (a.get("type") or "").lower()
            u = norm_url(src, self.base)
            if u and (VIDEO_EXT_RE.search(u) or typ.startswith("video/") or typ == "application/x-mpegurl"):
                self.add(video_kind(u), u, title=a.get("title", ""))
        elif self.in_picture:
            self.picture_cands += parse_srcset(a.get("srcset") or a.get("data-srcset") or "")

    def handle_img(self, a):
        if self.excluded():
            return
        w = to_int(a.get("width")) or to_int(a.get("data-w"))
        h = to_int(a.get("height"))
        if w and not h and a.get("data-ratio"):
            try:
                h = int(round(w * float(a["data-ratio"])))
            except ValueError:
                pass
        if (w and w < MIN_IMAGE_PX) or (h and h < MIN_IMAGE_PX):
            return  # tracking pixel / icon
        cands = list(self.picture_cands) if self.in_picture else []
        cands += parse_srcset(a.get("srcset") or a.get("data-srcset") or "")
        url, sw = best_candidate(cands)
        if not url:
            for k in ("data-src", "data-original", "data-lazy-src", "data-actualsrc", "src"):
                v = a.get(k)
                if v and not v.startswith("data:"):
                    url = v
                    break
            if not url:
                url = a.get("src")
        if not url:
            return
        if sw and sw > w:
            if w and h:
                h = int(round(h * sw / w))
            w = sw
        alt = a.get("alt") or ""
        title = a.get("title") or a.get("data-title") or ""
        self.add("image", url, title=title, alt=alt, w=w, h=h)
        if self.in_picture:
            self.picture_done = True

    def handle_iframe(self, a):
        src = a.get("data-src") or a.get("src") or ""
        cls = (a.get("class") or "").lower()
        mpvid = a.get("data-mpvid") or ""
        u = norm_url(src, self.base) if src else None
        w = to_int(a.get("data-w"))
        h = 0
        if w and a.get("data-ratio"):
            try:
                h = int(round(w * float(a["data-ratio"])))
            except ValueError:
                pass
        title = a.get("data-title") or a.get("title") or ""
        is_mp = mpvid or (u and ("mpvideo" in u or "video_player_tmpl" in u))
        if is_mp:  # 微信公众号 video: cannot be downloaded, report as embed
            if not u or ("mpvideo" not in u and "video_player_tmpl" not in u):
                u = f"https://mp.weixin.qq.com/mp/readtemplate?t=pages/video_player_tmpl&action=mpvideo&auto=0&vid={mpvid}"
            self.add("embed", u, title=title, alt=f"mpvideo {mpvid}".strip(), w=w, h=h)
        elif u and (is_embed_url(u) or "video_iframe" in cls):
            self.add("embed", u, title=title, w=w, h=h)


# ----------------------------------------------------------------------------- Next.js payload / regex passes
def unescape_js(t):
    """Undo JSON-in-JS escaping (\\" \\/ \\uXXXX) and return (u, u_offset → t_offset)."""
    out, shifts, last, shift, ulen = [], [], 0, 0, 0
    for m in re.finditer(r'\\"|\\/|\\u[0-9a-fA-F]{4}', t):
        tok = m.group(0)
        if tok == '\\"':
            rep = '"'
        elif tok == "\\/":
            rep = "/"
        else:
            cp = int(tok[2:], 16)
            rep = tok if 0xD800 <= cp <= 0xDFFF else chr(cp)  # keep surrogate halves untouched
        seg = t[last:m.start()]
        out.append(seg)
        ulen += len(seg)
        out.append(rep)
        ulen += len(rep)
        shift += len(tok) - len(rep)
        shifts.append((ulen, shift))
        last = m.end()
    out.append(t[last:])
    us = [s[0] for s in shifts]

    def to_t(x):
        i = bisect.bisect_right(us, x) - 1
        return x + (shifts[i][1] if i >= 0 else 0)

    return "".join(out), to_t


CONTENTFUL_VIDEO_RE = re.compile(
    r'"title":"([^"]*)"(?:,"description":"[^"]*")?,"file":\{"url":"(//videos\.ctfassets\.net[^"]+)","details":\{"size":(\d+)\},'
    r'"fileName":"[^"]+","contentType":"video/[^"]+"\}\}(?:,"altText":"([^"]*)")?')
CONTENTFUL_IMAGE_RE = re.compile(
    r'"title":"([^"]*)"(?:,"description":"[^"]*")?,"file":\{"url":"(//images\.ctfassets\.net[^"]+)","details":\{"size":(\d+),'
    r'"image":\{"width":(\d+),"height":(\d+)\}\},"fileName":"[^"]+","contentType":"image/(?!svg)[^"]+"\}\}(?:,"altText":"([^"]*)")?')
TAG_VIDEO_RE = re.compile(r'<(?:video|source)[^>]+(?:src|data-src)="([^"]+\.(?:mp4|webm|mov|m3u8)[^"]*)"', re.I)
BARE_VIDEO_RE = re.compile(r'https?://[^"\'\s<>\\)]+?\.(?:mp4|webm|mov|m3u8)(?:\?[^"\'\s<>\\)]*)?')


def extract_media(t, base):
    media = Media()
    parser = PageParser(t, base, media)
    try:
        parser.feed(t)
        parser.close()
    except Exception as e:  # never let a broken page kill the run
        log(f"warn: html parser stopped early: {e}")
    u, to_t = unescape_js(t)
    for m in CONTENTFUL_VIDEO_RE.finditer(u):
        media.add("mp4", m.group(2), base, title=m.group(1), alt=m.group(4) or "", size=int(m.group(3)), pos=to_t(m.start()))
    for m in CONTENTFUL_IMAGE_RE.finditer(u):
        media.add("image", m.group(2), base, title=m.group(1), alt=m.group(6) or "", size=int(m.group(3)),
                  w=int(m.group(4)), h=int(m.group(5)), pos=to_t(m.start()))
    for m in TAG_VIDEO_RE.finditer(t):
        media.add(video_kind(norm_url(m.group(1), base) or m.group(1)), m.group(1), base, pos=m.start())
    for m in BARE_VIDEO_RE.finditer(u):
        media.add(video_kind(m.group(0)), m.group(0), base, pos=to_t(m.start()))
    for m in EMBED_RE.finditer(u):
        media.add("embed", m.group(0), base, pos=to_t(m.start()))
    return media.finish(), parser


def page_title(t, parser):
    for cand in (parser.og_title, parser.title, parser.h1):
        cand = htmllib.unescape(re.sub(r"\s+", " ", cand or "")).strip()
        if cand:
            return cand
    m = re.search(r"<title[^>]*>(.*?)</title>", t, re.S | re.I)
    return htmllib.unescape(re.sub(r"\s+", " ", m.group(1))).strip() if m else ""


# ----------------------------------------------------------------------------- text
def regex_strip(t):
    """v1 fallback: tags → markdown-ish text; table cells ' | ' separated. Only strips script/style/svg
    (stripping <nav>/<footer> with regex eats table cells when navs are nested inside tables)."""
    body = re.search(r"<body.*?</body>", t, re.S | re.I)
    body = body.group(0) if body else t
    body = re.sub(r"<script.*?</script>|<style.*?</style>|<svg.*?</svg>|<noscript.*?</noscript>", "", body, flags=re.S | re.I)
    body = re.sub(r"<(h[1-6])[^>]*>", lambda m: "\n\n" + "#" * int(m.group(1)[1]) + " ", body, flags=re.I)
    body = re.sub(r"</(h[1-6]|p|li|div|tr)>", "\n", body, flags=re.I)
    body = re.sub(r"<li[^>]*>", "- ", body, flags=re.I)
    body = re.sub(r"<td[^>]*>|<th[^>]*>", " | ", body, flags=re.I)
    body = re.sub(r"<br\s*/?>", "\n", body, flags=re.I)
    body = re.sub(r"<[^>]+>", "", body)
    body = htmllib.unescape(body)
    body = re.sub(r"[ \t]+", " ", body)
    body = re.sub(r"\n\s*\n+", "\n\n", body).strip()
    return body


def extract_text(t, url):
    md, how = None, "trafilatura"
    try:
        import trafilatura  # lazy: heavy, and optional under plain python3
        md = trafilatura.extract(t, url=url or None, include_tables=True, include_images=True, include_links=False,
                                 output_format="markdown", favor_recall=True)
    except ImportError:
        log(f"warn: trafilatura not importable → regex fallback (run via: {UV_HINT})")
    except Exception as e:
        log(f"warn: trafilatura failed ({e}) → regex fallback")
    if not md or len(md) < MIN_TRAFILATURA_CHARS:
        fb = regex_strip(t)
        if not md or len(fb) > len(md):
            log(f"warn: trafilatura returned {len(md or '')} chars (< {MIN_TRAFILATURA_CHARS}) → regex fallback ({len(fb)} chars)")
            md, how = fb, "regex"
    return (md or "").strip(), how


def write_article(out, title, body):
    lines = body.split("\n")
    if title and lines and lines[0].strip().lstrip("#").strip() == title:
        body = "\n".join(lines[1:]).lstrip("\n")
    text = (f"# {title}\n\n" if title else "") + body + "\n"
    (out / "article.md").write_text(text, encoding="utf-8")
    return len(body)


# ----------------------------------------------------------------------------- modes
def fetch(url):
    try:
        from curl_cffi import requests  # lazy: only the URL mode needs it
    except ImportError:
        die(f"curl_cffi is not importable. Run via: {UV_HINT}   (or: pip install curl_cffi trafilatura)", 2)
    try:
        r = requests.get(url, impersonate="chrome", timeout=90, headers={"Accept-Language": ACCEPT_LANGUAGE})
    except Exception as e:
        die(f"network error: {e}\nFallback: open the page in a browser, save as HTML → --from-html page.html <out_dir>;"
            f" or paste the text into a file → --from-text notes.txt <out_dir>", 3)
    log(f"status {r.status_code} bytes {len(r.content)}")
    if r.status_code != 200:
        die(f"fetch failed: HTTP {r.status_code}.\nFallback: open the page in a browser, save as HTML → --from-html page.html <out_dir>;"
            f" or paste the text into a file → --from-text notes.txt <out_dir>", 3)
    text = r.text
    if not text.strip():
        die("fetch returned an empty body (JS-only page?). Fallback: --from-html / --from-text", 3)
    return text, r.status_code, str(getattr(r, "url", url) or url)


def read_html_file(path):
    raw = pathlib.Path(path).read_bytes()
    for enc in ("utf-8",):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            pass
    m = re.search(rb'charset=["\']?\s*([A-Za-z0-9_-]+)', raw[:4096])
    if m:
        try:
            return raw.decode(m.group(1).decode("ascii"), errors="replace")
        except LookupError:
            pass
    return raw.decode("utf-8", errors="replace")


def run_html(t, out, base_url, source_kind, status=None):
    out.mkdir(parents=True, exist_ok=True)
    (out / "page.html").write_text(t, encoding="utf-8")
    # base URL: --base-url / fetched URL > <base href> > og:url
    pre = PageParser(t, base_url, Media())
    try:
        pre.feed(t)
    except Exception:
        pass
    base = base_url or (norm_url(pre.base_href, None) if pre.base_href else None) or (norm_url(pre.og_url, None) if pre.og_url else None) or ""
    if not base_url and base:
        log(f"base url: {base}")
    media, parser = extract_media(t, base)
    title = page_title(t, parser)
    body, how = extract_text(t, base or None)
    chars = write_article(out, title, body)
    json.dump(media, open(out / "media.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    counts = {k: sum(1 for m in media if m["kind"] == k) for k in ("image", "mp4", "embed")}
    for m in media:
        dims = f"{m['w']}x{m['h']}" if m["w"] or m["h"] else ""
        log(f"  {m['order']:3d} {m['kind']:5s} {m['url'][:96]:96s} {dims:>9s} | {(m['title'] or m['alt'])[:60]}")
    log(f"summary: chars={chars} images={counts['image']} mp4s={counts['mp4']} embeds={counts['embed']} text={how} title={title[:60]!r}")
    return {"ok": True, "source": {"kind": source_kind, "url": base or None, "title": title,
                                    "fetchedAt": datetime.datetime.now().astimezone().isoformat(timespec="seconds")},
            "status": status, "chars": chars, "images": counts["image"], "mp4s": counts["mp4"], "embeds": counts["embed"],
            "text": how, "files": {"page": str(out / "page.html"), "article": str(out / "article.md"), "media": str(out / "media.json")}}


def run_text(path, out):
    out.mkdir(parents=True, exist_ok=True)
    text = pathlib.Path(path).read_text(encoding="utf-8", errors="replace")
    lines = text.split("\n")
    first = next((i for i, l in enumerate(lines) if l.strip()), None)
    title = ""
    if first is not None:
        if lines[first].lstrip().startswith("#"):
            title = lines[first].lstrip("#").strip()
        else:
            title = lines[first].strip()
            lines[first] = "# " + lines[first].strip()
            text = "\n".join(lines)
    (out / "article.md").write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")
    json.dump([], open(out / "media.json", "w", encoding="utf-8"))
    chars = len(text)
    log(f"summary: chars={chars} images=0 mp4s=0 embeds=0 text=verbatim title={title[:60]!r}")
    return {"ok": True, "source": {"kind": "text", "url": None, "title": title,
                                    "fetchedAt": datetime.datetime.now().astimezone().isoformat(timespec="seconds")},
            "status": None, "chars": chars, "images": 0, "mp4s": 0, "embeds": 0, "text": "verbatim",
            "files": {"article": str(out / "article.md"), "media": str(out / "media.json")}}


def main(argv):
    global JSON_MODE
    args = list(argv)
    if not args or "-h" in args or "--help" in args:
        print(__doc__.strip())
        return 0 if args else 2
    from_html = from_text = base_url = None
    pos = []
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--json":
            JSON_MODE = True
        elif a in ("--from-html", "--from-text", "--base-url"):
            if i + 1 >= len(args):
                die(f"{a} needs a value", 2)
            if a == "--from-html":
                from_html = args[i + 1]
            elif a == "--from-text":
                from_text = args[i + 1]
            else:
                base_url = args[i + 1]
            i += 1
        elif a.startswith("-") and not a.startswith("-/"):
            die(f"unknown option {a}", 2)
        else:
            pos.append(a)
        i += 1
    if from_html and from_text:
        die("use either --from-html or --from-text", 2)
    if from_html or from_text:
        if len(pos) != 1:
            die("usage: fetch_page.py --from-html FILE <out_dir>  |  --from-text FILE <out_dir>", 2)
        out = pathlib.Path(pos[0])
        if from_text:
            summary = run_text(from_text, out)
        else:
            if not pathlib.Path(from_html).is_file():
                die(f"no such file: {from_html}", 2)
            summary = run_html(read_html_file(from_html), out, base_url, "html")
    else:
        if len(pos) != 2:
            die("usage: fetch_page.py <url> <out_dir> [--json]", 2)
        url, out = pos[0], pathlib.Path(pos[1])
        if not url.startswith(("http://", "https://")):
            die(f"not a URL: {url} (use --from-html FILE or --from-text FILE for local files)", 2)
        text, status, final_url = fetch(url)
        summary = run_html(text, out, base_url or final_url, "url", status)
        summary["source"]["requestedUrl"] = url
    if JSON_MODE:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
