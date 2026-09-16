#!/usr/bin/env python3
"""Seed-TTS 2.0 adapter (ByteDance). The request body is kept verbatim from v1; synthesis now flows through tts.py
(breath edit, fingerprints, alignment). Running this file directly delegates to tts.py with the same arguments.
No native timestamps: align with align.py transcribe (whisper) or measured words after synthesis.
"""
import base64, json, os, pathlib, subprocess, sys, urllib.error, urllib.request, uuid

NAME = 'seed2'
ADAPTER_VERSION = '2'
MAX_CHARS = 300
PACE_PARAM = ('rate', -50, 100)
PARAM_KEYS = ('rate', 'style')
DEFAULT_SPEAKER = "zh_male_qingshuangnanda_uranus_bigtts"
DEFAULT_RATE = 28
DEFAULT_STYLE = "阳光、青春、有活力、有亲和力，像与朋友分享有趣发现，重音与停顿跟随语义，表达自然清楚"
DEFAULT_PARAMS = {'rate': DEFAULT_RATE, 'style': DEFAULT_STYLE}
DEFAULT_MODELS = ['seed-tts-2.0']
ENDPOINT = "https://openspeech.bytedance.com/api/v3/tts/unidirectional"
RESOURCE_ID = "seed-tts-2.0"
KEY_HINT = "SEED_AUDIO_KEY not set. export SEED_AUDIO_KEY=…  or:  set -a; source config.env; set +a"


def emotion(tag):
    return ''   # Seed has no inline tag syntax; direction travels in the style text


def build_request(text, voice, params, model=None):
    p = {**DEFAULT_PARAMS, **{k: v for k, v in (params or {}).items() if k in PARAM_KEYS}}
    rate = int(p['rate'])
    if not -50 <= rate <= 100: raise ValueError('Seed speech rate must be -50..100')
    speaker = voice.get('speaker') or DEFAULT_SPEAKER
    body = {"user": {"uid": "vertical-video"}, "req_params": {"text": text, "speaker": speaker,
            "audio_params": {"format": "mp3", "sample_rate": 48000, "speech_rate": rate},
            "additions": json.dumps({"context_texts": [p['style']]}, ensure_ascii=False)}}
    return {'url': ENDPOINT, 'headers': {"Content-Type": "application/json", "X-Api-Resource-Id": RESOURCE_ID}, 'body': body, 'model': RESOURCE_ID}


# ------------------------------------------------------------------ Seed-TTS 2.0 (kept verbatim from v1)
def tts(text, dst, key, speaker, rate, style):
    body = {"user": {"uid": "vertical-video"}, "req_params": {"text": text, "speaker": speaker,
            "audio_params": {"format": "mp3", "sample_rate": 48000, "speech_rate": rate},
            "additions": json.dumps({"context_texts": [style]}, ensure_ascii=False)}}
    req = urllib.request.Request(ENDPOINT, data=json.dumps(body, ensure_ascii=False).encode(),
        headers={"Content-Type": "application/json", "X-Api-Key": key, "X-Api-Resource-Id": RESOURCE_ID, "X-Api-Request-Id": str(uuid.uuid4())})
    raw = None
    for attempt in (1, 2):
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                raw = r.read()
            break
        except urllib.error.HTTPError as e:
            sys.exit(f"HTTP {e.code}: {e.read()[:300]}")
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            if attempt == 2:
                sys.exit(f"network error for {dst.stem}: {e}")
            print(f"  retry {dst.stem}: {e}", flush=True)
    audio = b""
    for line in raw.split(b"\n"):
        if line.strip():
            j = json.loads(line)
            if j.get("code") not in (0, 20000000): sys.exit(f"TTS error for {dst.stem}: {j}")
            if j.get("data"): audio += base64.b64decode(j["data"])
    if not audio: sys.exit(f"no audio for {dst.stem}: {raw[:300]}")
    dst.write_bytes(audio)


def synthesize(text, voice, params, dest, key, log=lambda *a: None, record_sse=None):
    """One request → decoded 48k mono wav at dest. Returns {'seconds','tokens':None,'model','mode','source'}."""
    req = build_request(text, voice, params)
    dest = pathlib.Path(dest); dest.parent.mkdir(parents=True, exist_ok=True)
    source = dest.with_suffix('.source.mp3')
    p = {**DEFAULT_PARAMS, **{k: v for k, v in (params or {}).items() if k in PARAM_KEYS}}
    tts(text, source, key, voice.get('speaker') or DEFAULT_SPEAKER, int(p['rate']), p['style'])
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(source), '-ar', '48000', '-ac', '1', '-c:a', 'pcm_s16le', str(dest)], check=True)
    out = subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(dest)]).decode().strip()
    return {'seconds': round(float(out), 3), 'tokens': None, 'model': RESOURCE_ID, 'mode': None, 'source': str(source)}


def main():
    """Back-compat CLI: tts_seed2.py <project> [--only] [--speaker] [--rate] [--style] [--force] [--dry-run] → tts.py."""
    import argparse
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('project', type=pathlib.Path); p.add_argument('--only'); p.add_argument('--speaker'); p.add_argument('--rate', type=int); p.add_argument('--style'); p.add_argument('--force', action='store_true'); p.add_argument('--dry-run', action='store_true'); a = p.parse_args()
    argv = [sys.executable, str(pathlib.Path(__file__).with_name('tts.py')), str(a.project)]
    if a.only: argv += ['--only', a.only]
    if a.force: argv.append('--force')
    if a.dry_run: argv.append('--dry-run')
    if a.rate is not None: argv += ['--param', f'rate={a.rate}']
    if a.style: argv += ['--param', f'style={json.dumps(a.style, ensure_ascii=False)}']
    if a.speaker: print('note: --speaker is read from brief.tts.speaker; edit the brief to change the Seed voice', file=sys.stderr)
    raise SystemExit(subprocess.call(argv))


if __name__ == '__main__':
    main()
