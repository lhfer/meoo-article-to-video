#!/usr/bin/env bash
# download_media.sh — turn assets/media.json into Remotion-ready clips and images.
#
# Usage: download_media.sh <workdir> [--max-clips N] [--max-images N] [--help]
#   reads   <workdir>/assets/media.json            (from fetch_page.py; optional when files are hand-dropped)
#   videos  kind "mp4" (not .m3u8) → assets/raw/NN.mp4 → project/public/clips/NN.mp4
#             ≤ 1600 px wide, 30 fps, H.264 yuv420p faststart, AAC audio kept when present
#           + project/public/clips/NN.bg.mp4  pre-blurred silent 270 px twin for the scene background
#   images  kind "image" → assets/raw/img/NN.<ext> → project/public/images/NN.jpg (JPEG, ≤ 1600 px wide)
#             skipped when the long side is < 400 px or ffmpeg cannot decode the format
#   hand-dropped files: any assets/raw/*.mp4|mov|webm|m4v and assets/raw/img/* not produced from media.json
#             get the next free index (indices are remembered in clips.json / images.json)
#   writes  assets/clips.json  [{index, src:"clips/NN.mp4", bg:"clips/NN.bg.mp4", w, h, duration, fps, hasAudio, title, alt, sourceUrl|sourceFile}]
#           assets/images.json [{index, src:"images/NN.jpg", w, h, alt, title, sourceUrl|sourceFile}]
#   idempotent: existing raw downloads / outputs are reused; NN is 01, 02, … in media.json order.
#   --max-clips N / --max-images N   only take the first N media entries of that kind (hand-dropped files are always processed)
# Exit 1 when nothing usable was produced; failed single downloads are reported and skipped.
set -euo pipefail

usage() { sed -n '2,/^set -euo/p' "$0" | grep '^#' | sed 's/^# \{0,1\}//'; }

W=""; MAXC=""; MAXI=""
while [ $# -gt 0 ]; do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    --max-clips) MAXC="${2:?--max-clips needs a number}"; shift ;;
    --max-images) MAXI="${2:?--max-images needs a number}"; shift ;;
    -*) echo "unknown argument: $1" >&2; usage >&2; exit 2 ;;
    *) if [ -z "$W" ]; then W="$1"; else echo "unexpected argument: $1" >&2; exit 2; fi ;;
  esac
  shift
done
[ -n "$W" ] || { usage >&2; exit 2; }
[ -d "$W" ] || { echo "FAIL: workdir not found: $W" >&2; exit 2; }
for t in curl ffmpeg ffprobe python3; do command -v "$t" >/dev/null 2>&1 || { echo "FAIL: $t not found" >&2; exit 1; }; done

A="$W/assets"; RAW="$A/raw"; RAWIMG="$RAW/img"; CLIPS="$W/project/public/clips"; IMAGES="$W/project/public/images"
mkdir -p "$RAW" "$RAWIMG" "$CLIPS" "$IMAGES"

MAXC="$MAXC" MAXI="$MAXI" python3 -u - "$A" "$RAW" "$RAWIMG" "$CLIPS" "$IMAGES" <<'PY'
import json, os, pathlib, re, subprocess, sys, urllib.parse

A, RAW, RAWIMG, CLIPS, IMAGES = map(pathlib.Path, sys.argv[1:6])
MAXC = int(os.environ["MAXC"]) if os.environ.get("MAXC") else None
MAXI = int(os.environ["MAXI"]) if os.environ.get("MAXI") else None
VIDEO_EXT = (".mp4", ".mov", ".webm", ".m4v", ".mkv")
IMG_EXT = (".jpg", ".jpeg", ".png", ".webp", ".avif", ".gif", ".bmp", ".tif", ".tiff", ".heic", ".jfif")
MIN_IMG_LONG_SIDE = 400
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

def load(p, default):
    try:
        return json.load(open(p, encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default

def probe(path):
    try:
        out = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height,r_frame_rate,avg_frame_rate",
                                       "-show_entries", "stream_side_data=rotation", "-show_entries", "format=duration", "-of", "json", str(path)],
                                      stderr=subprocess.DEVNULL).decode()
    except subprocess.CalledProcessError:
        return None
    j = json.loads(out)
    v = next((s for s in j.get("streams", []) if s.get("codec_type") == "video"), None)
    if not v:
        return None
    w, h = int(v.get("width", 0)), int(v.get("height", 0))
    rot = 0
    for sd in v.get("side_data_list", []) or []:
        if "rotation" in sd:
            try: rot = int(float(sd["rotation"]))
            except ValueError: pass
    if rot % 180 != 0:
        w, h = h, w
    fps = 0.0
    fr = v.get("avg_frame_rate") or v.get("r_frame_rate") or "0/1"
    if "/" in fr:
        n, d = fr.split("/")
        fps = float(n) / float(d) if float(d) else 0.0
    dur = float(j.get("format", {}).get("duration") or 0)
    return {"w": w, "h": h, "fps": round(fps, 3), "duration": dur, "hasAudio": any(s.get("codec_type") == "audio" for s in j["streams"])}

def download(url, dst):
    tmp = dst.with_name(dst.name + ".part")
    r = subprocess.run(["curl", "-sSL", "-f", "--retry", "2", "--connect-timeout", "30", "-A", UA, "-o", str(tmp), url])
    if r.returncode or not tmp.exists() or tmp.stat().st_size < 1000:
        tmp.unlink(missing_ok=True)
        return False
    tmp.rename(dst)
    return True

def ext_of(url, default):
    path = urllib.parse.urlsplit(url).path.lower()
    m = re.search(r"(\.[a-z0-9]{2,5})$", path)
    if m and m.group(1) in IMG_EXT + VIDEO_EXT:
        return m.group(1)
    q = urllib.parse.urlsplit(url).query.lower()
    m = re.search(r"(?:wx_fmt|fm|format|f)=(jpe?g|png|webp|gif|avif)", q)
    return "." + m.group(1) if m else default

media = load(A / "media.json", [])
if not media and not any(RAW.glob("*")):
    sys.exit(f"FAIL: {A/'media.json'} not found and assets/raw/ is empty — run fetch_page.py first or drop files into assets/raw/")
videos = [m for m in media if m.get("kind") == "mp4" and not urllib.parse.urlsplit(m["url"]).path.lower().endswith(".m3u8")]
images = [m for m in media if m.get("kind") == "image"]
if MAXC is not None: videos = videos[:MAXC]
if MAXI is not None: images = images[:MAXI]

# ------------------------------------------------------------------ videos
prev_clips = {c.get("sourceFile"): c["index"] for c in load(A / "clips.json", []) if c.get("sourceFile")}
clips, failed = [], 0
def clip_entry(i, raw, meta):
    dst, bg = CLIPS / f"{i:02d}.mp4", CLIPS / f"{i:02d}.bg.mp4"
    p = probe(raw)
    if not p:
        print(f"  {i:02d} no video stream in {raw.name}, skipped"); return None
    if not dst.exists() or dst.stat().st_size == 0:
        subprocess.check_call(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-vf", "scale='2*trunc(min(1600,iw)/2)':-2:flags=lanczos,fps=30",
                               "-c:v", "libx264", "-preset", "fast", "-crf", "19", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                               *(["-c:a", "aac", "-b:a", "160k"] if p["hasAudio"] else ["-an"]), str(dst)])
    if not bg.exists() or bg.stat().st_size == 0:
        subprocess.check_call(["ffmpeg", "-v", "error", "-y", "-i", str(dst), "-vf", "scale=270:-2,gblur=sigma=14,eq=brightness=-0.3:saturation=1.4,fps=30",
                               "-an", "-c:v", "libx264", "-crf", "28", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(bg)])
    q = probe(dst) or p
    e = {"index": i, "src": f"clips/{i:02d}.mp4", "bg": f"clips/{i:02d}.bg.mp4", "w": q["w"], "h": q["h"], "duration": round(q["duration"], 2),
         "fps": 30, "hasAudio": q["hasAudio"], "title": meta.get("title", ""), "alt": meta.get("alt", "")}
    if meta.get("url"): e["sourceUrl"] = meta["url"]
    else: e["sourceFile"] = raw.name
    print(f"  {i:02d} {q['w']}x{q['h']} {q['duration']:.1f}s audio={q['hasAudio']} | {(meta.get('alt') or meta.get('title') or raw.name)[:70]}")
    return e

media_raws = set()
for i, m in enumerate(videos, 1):
    raw = RAW / f"{i:02d}.mp4"
    media_raws.add(raw.name)
    if not raw.exists() or raw.stat().st_size == 0:
        print(f"  {i:02d} downloading {m['url'][:90]}")
        if not download(m["url"], raw):
            print(f"  {i:02d} FAILED download {m['url']}"); failed += 1; continue
    e = clip_entry(i, raw, m)
    if e: clips.append(e)
hand = sorted(f for f in RAW.iterdir() if f.is_file() and f.suffix.lower() in VIDEO_EXT and f.name not in media_raws and not f.name.endswith(".part") and not f.name.startswith("."))
next_i = max([len(videos)] + [c["index"] for c in clips] + list(prev_clips.values())) + 1
for f in hand:
    i = prev_clips.get(f.name)
    if i is None or any(c["index"] == i for c in clips):
        i = next_i; next_i += 1
    print(f"  {i:02d} hand-dropped {f.name}")
    e = clip_entry(i, f, {"title": f.stem, "alt": ""})
    if e: clips.append(e)
clips.sort(key=lambda c: c["index"])
json.dump(clips, open(A / "clips.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
print(f"{len(clips)} clips -> {A/'clips.json'}" + (f" ({failed} download(s) failed)" if failed else ""))

# ------------------------------------------------------------------ images
prev_imgs = {c.get("sourceFile"): c["index"] for c in load(A / "images.json", []) if c.get("sourceFile")}
imgs, ifailed = [], 0
def image_entry(i, raw, meta):
    dst = IMAGES / f"{i:02d}.jpg"
    p = probe(raw)
    if not p or not p["w"]:
        print(f"  img {i:02d} cannot decode {raw.name} (format unsupported by this ffmpeg), skipped"); return None
    if max(p["w"], p["h"]) < MIN_IMG_LONG_SIDE:
        print(f"  img {i:02d} {p['w']}x{p['h']} too small (< {MIN_IMG_LONG_SIDE} px), skipped"); return None
    if not dst.exists() or dst.stat().st_size == 0:
        r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-frames:v", "1", "-vf", "scale='2*trunc(min(1600,iw)/2)':-2:flags=lanczos,format=yuvj420p",
                            "-q:v", "2", str(dst)])
        if r.returncode or not dst.exists():
            dst.unlink(missing_ok=True)
            print(f"  img {i:02d} ffmpeg could not convert {raw.name}, skipped"); return None
    q = probe(dst) or p
    e = {"index": i, "src": f"images/{i:02d}.jpg", "w": q["w"], "h": q["h"], "alt": meta.get("alt", ""), "title": meta.get("title", "")}
    if meta.get("url"): e["sourceUrl"] = meta["url"]
    else: e["sourceFile"] = raw.name
    print(f"  img {i:02d} {q['w']}x{q['h']} | {(meta.get('alt') or meta.get('title') or raw.name)[:70]}")
    return e

media_img_raws = set()
for i, m in enumerate(images, 1):
    existing = sorted(RAWIMG.glob(f"{i:02d}.*"))
    existing = [f for f in existing if not f.name.endswith(".part")]
    if existing:
        raw = existing[0]
    else:
        raw = RAWIMG / f"{i:02d}{ext_of(m['url'], '.img')}"
        print(f"  img {i:02d} downloading {m['url'][:90]}")
        if not download(m["url"], raw):
            print(f"  img {i:02d} FAILED download {m['url']}"); ifailed += 1; continue
    media_img_raws.add(raw.name)
    e = image_entry(i, raw, m)
    if e: imgs.append(e)
hand = sorted(f for f in RAWIMG.iterdir() if f.is_file() and f.name not in media_img_raws and not f.name.endswith(".part") and not f.name.startswith("."))
next_i = max([len(images)] + [c["index"] for c in imgs] + list(prev_imgs.values())) + 1
for f in hand:
    i = prev_imgs.get(f.name)
    if i is None or any(c["index"] == i for c in imgs):
        i = next_i; next_i += 1
    print(f"  img {i:02d} hand-dropped {f.name}")
    e = image_entry(i, f, {"title": f.stem, "alt": ""})
    if e: imgs.append(e)
imgs.sort(key=lambda c: c["index"])
json.dump(imgs, open(A / "images.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
print(f"{len(imgs)} images -> {A/'images.json'}" + (f" ({ifailed} download(s) failed)" if ifailed else ""))
if not clips and not imgs:
    sys.exit("FAIL: no clip or image could be produced")
PY
