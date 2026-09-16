"""Small shared file/validation helpers; no account secrets are read here."""
from pathlib import Path
import hashlib, json, os, re, subprocess, tempfile, unicodedata

ROOT = Path(__file__).resolve().parent.parent

def read(path, default=None):
    p = Path(path)
    if not p.exists() and default is not None: return default
    return json.loads(p.read_text(encoding='utf-8'))

def write(path, value):
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, ensure_ascii=False, indent=2) + '\n'
    fd, tmp = tempfile.mkstemp(prefix='.' + p.name, dir=p.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f: f.write(data)
        os.replace(tmp, p)
    finally:
        if Path(tmp).exists(): Path(tmp).unlink()

def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

def filehash(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()
def texthash(text): return hashlib.sha256(text.encode()).hexdigest()
def norm(text): return ''.join(c.lower() for c in unicodedata.normalize('NFKC',text) if c.isalnum())

def inside(root, relative):
    root = Path(root).resolve(); p = (root / relative).resolve()
    if Path(relative).is_absolute() or not p.is_relative_to(root): raise ValueError(f'Path must stay under {root.name}: {relative}')
    return p

def ident(value):
    if not re.fullmatch(r'[a-zA-Z][a-zA-Z0-9_-]*', value): raise ValueError(f'Invalid id: {value}')
    return value

def probe(path):
    r = subprocess.run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(path)], check=True, capture_output=True, text=True)
    return json.loads(r.stdout)

def duration(path): return float(probe(path)['format']['duration'])

def script_material(project):
    s = read(Path(project)/'content/script.json')
    return {k:s.get(k,'') for k in ['title','viewerPromise','thesis']} | {'beats':[{'id':b['id'],'narration':b.get('narration','')} for b in s.get('beats',[])]}

def script_hash(project): return digest(script_material(project))

def ensure_script(project):
    r = read(Path(project)/'content/reviews.json', {})
    if r.get('script', {}).get('digest') != script_hash(project):
        raise ValueError('Full script needs a current user approval. Present out/script-review.md, then record the actual reply with review.py.')

def run_main(fn):
    try: fn()
    except (ValueError, KeyError, FileNotFoundError, json.JSONDecodeError, subprocess.CalledProcessError) as e:
        raise SystemExit(str(e))

# ---- V4 additions: pure text helpers (no I/O, no secrets) ----
TAG_RE = re.compile(r'\[[^\[\]\n]{1,60}\]')
CJK_RE = re.compile(r'[　-〿㐀-䶿一-鿿豈-﫿＀-￯]')

def skill_name():
    """Skill name from SKILL.md frontmatter; falls back to the directory name."""
    try:
        text = (ROOT / 'SKILL.md').read_text(encoding='utf-8')
        m = re.search(r'\A---\s*\n(.*?)\n---', text, re.S)
        n = re.search(r'^name:\s*([A-Za-z0-9._-]+)\s*$', m.group(1), re.M) if m else None
        if n: return n.group(1)
    except OSError:
        pass
    return ROOT.name

def strip_tags(text):
    return TAG_RE.sub('', text).strip()

def apply_overrides(text, overrides):
    """Replace narration substrings with their spoken readings, longest match first, scanning left to right."""
    pairs = sorted([(a, b) for a, b in (overrides or []) if a], key=lambda x: -len(x[0]))
    out, i = [], 0
    while i < len(text):
        hit = next(((a, b) for a, b in pairs if text.startswith(a, i)), None)
        if hit: out.append(hit[1]); i += len(hit[0])
        else: out.append(text[i]); i += 1
    return ''.join(out)

def spoken_text(beat):
    """The pronounceable text: narration with overrides applied. beat.spoken may cache it but must agree."""
    derived = apply_overrides(beat.get('narration', ''), beat.get('overrides', []))
    cached = beat.get('spoken')
    if cached and norm(cached) != norm(derived):
        raise ValueError(f"beat.spoken is stale for {beat.get('id')}: express readings as overrides [[narration_sub, spoken_sub]] so timestamps can be mapped back to the display text")
    return derived

def tts_text(beat, brief, emotion=lambda tag: tag):
    """Provider text: optional emotion tag (formatted by the adapter) + spoken text."""
    cfg = brief.get('tts', {}).get('emotion', {}) or {}
    tag = (beat.get('voice', {}) or {}).get('emotion') or cfg.get('default', '')
    enabled = cfg.get('enabled', True)
    tag = emotion(tag) if (tag and enabled) else ''
    return f'{tag}{spoken_text(beat)}'

def chunk_text(text, limit):
    """Split long narration after sentence-final punctuation so each request stays under the provider limit."""
    if len(text) <= limit: return [text]
    pieces = [p for p in re.split(r'(?<=[。！？!?])', text) if p]
    chunks, buf = [], ''
    for p in pieces:
        if buf and len(buf) + len(p) > limit: chunks.append(buf); buf = p
        else: buf += p
    if buf: chunks.append(buf)
    out = []
    for c in chunks:
        while len(c) > limit: out.append(c[:limit]); c = c[limit:]
        out.append(c)
    return out

def weighted_len(text):
    """Caption width estimate: CJK/full-width = 1, ASCII letters/digits/punctuation = 0.6, spaces = 0."""
    total = 0.0
    for ch in text:
        if ch.isspace(): continue
        total += 1 if CJK_RE.match(ch) else 0.6
    return round(total, 2)

def cps(text, seconds):
    """Measured pace: pronounceable characters per second (norm() strips punctuation and spaces)."""
    return round(len(norm(text)) / seconds, 2) if seconds > 0 else 0.0
