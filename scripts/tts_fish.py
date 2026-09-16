#!/usr/bin/env python3
"""Fish Audio adapter: SSE `with-timestamp` synthesis returning audio plus native per-token timestamps.

Parsing follows the documented stream (audio_base64 chunks; alignment snapshots). Two snapshot semantics exist in
the wild: per-chunk snapshots keyed by chunk_seq with chunk_audio_offset_sec, and cumulative lists. collect_stream()
handles both; tests/fixtures/fish-sse.txt is a real recording that pins the behaviour.
Default model list is the free tier only; paid models are never tried implicitly (a single paid 200 debits the account).
"""
import base64, json, math, subprocess, time, urllib.error, urllib.request
from pathlib import Path

NAME = 'fish'
ADAPTER_VERSION = '1'
MAX_CHARS = 280
PACE_PARAM = ('speed', 0.5, 2.0)
PARAM_KEYS = ('speed', 'volume', 'temperature', 'top_p', 'chunk_length')
DEFAULT_MODELS = ['s2.1-pro-free']
DEFAULT_PARAMS = {'speed': 1.0, 'volume': 0, 'temperature': 0.7, 'top_p': 0.7, 'chunk_length': 200}
ENDPOINT_TS = 'https://api.fish.audio/v1/tts/stream/with-timestamp'
ENDPOINT = 'https://api.fish.audio/v1/tts'
PASS_THROUGH = {400, 402, 403, 404, 422}   # this model is not available to this key: try the next configured one
BACKOFF = [2, 5, 10]


class ProviderError(RuntimeError):
    def __init__(self, message, status=None):
        super().__init__(message); self.status = status


def emotion(tag):
    tag = (tag or '').strip()
    if not tag: return ''
    return tag if tag.startswith('[') else f'[{tag}]'


def build_request(text, voice, params, timestamps=True, model=None):
    """Pure request builder (no key). voice = brief.tts; params = merged pacing/prosody params."""
    model = model or voice.get('model') or DEFAULT_MODELS[0]
    reference_id = voice.get('reference_id', '')
    if not reference_id: raise ValueError('brief.tts.reference_id (Fish voice id) is required')
    p = {**DEFAULT_PARAMS, **{k: v for k, v in (params or {}).items() if k in PARAM_KEYS}}
    speed = float(p['speed'])
    if not PACE_PARAM[1] <= speed <= PACE_PARAM[2]: raise ValueError(f'Fish speed must be within {PACE_PARAM[1]}..{PACE_PARAM[2]}')
    body = {'text': text, 'reference_id': reference_id, 'format': 'wav', 'sample_rate': 44100, 'normalize': True,
            'latency': 'normal', 'chunk_length': int(p['chunk_length']), 'temperature': float(p['temperature']),
            'top_p': float(p['top_p']), 'prosody': {'speed': speed, 'volume': float(p['volume'])}}
    headers = {'Content-Type': 'application/json', 'model': model, 'Accept': 'text/event-stream' if timestamps else 'audio/wav, */*'}
    return {'url': ENDPOINT_TS if timestamps else ENDPOINT, 'headers': headers, 'body': body, 'model': model}


def sse_events(lines):
    """Yield JSON events from SSE lines: handles comments, CRLF, multi-line data and a final unterminated event."""
    data = []
    for raw in lines:
        line = raw.decode('utf-8', 'replace') if isinstance(raw, bytes) else raw
        line = line.rstrip('\r\n')
        if not line:
            if data:
                payload = '\n'.join(data); data = []
                if payload != '[DONE]': yield json.loads(payload)
            continue
        if line.startswith(':'): continue
        if line.startswith('data:'): data.append(line[5:].lstrip(' '))
    if data:
        payload = '\n'.join(data)
        if payload != '[DONE]': yield json.loads(payload)


def _segments(alignment):
    out = []
    for seg in (alignment or {}).get('segments', []) or []:
        text = str(seg.get('text', ''))
        start, end = float(seg.get('start', 0)), float(seg.get('end', 0))
        if not (math.isfinite(start) and math.isfinite(end)) or start < 0 or end < start: raise ProviderError('Invalid native timestamp')
        if text: out.append({'text': text, 'start': start, 'end': end})
    return out


def collect_stream(events):
    """Return (audio_bytes, tokens[{text,start,end}], mode). Snapshot mode when events carry chunk_seq/offset;
    otherwise cumulative mode keeps the longest alignment list seen."""
    audio, snapshots, longest, mode = [], {}, [], None
    for ev in events:
        if 'error' in ev: raise ProviderError(f"Provider reported a streaming error: {str(ev.get('error'))[:200]}")
        if 'audio_base64' not in ev: raise ProviderError('Unexpected SSE schema (no audio_base64); update the adapter from the official docs')
        if ev['audio_base64']: audio.append(base64.b64decode(ev['audio_base64']))
        al = ev.get('alignment')
        if al is None: continue
        if 'chunk_seq' in ev and 'chunk_audio_offset_sec' in ev:
            mode = mode or 'snapshot'
            seq = int(ev['chunk_seq']); offset = float(ev['chunk_audio_offset_sec'])
            if not math.isfinite(offset) or offset < 0: raise ProviderError('Invalid chunk offset')
            snapshots[seq] = (offset, _segments(al))
        else:
            mode = mode or 'cumulative'
            segs = _segments(al)
            if len(segs) >= len(longest): longest = segs
    if mode == 'snapshot':
        tokens = []
        for seq in sorted(snapshots, key=lambda s: (snapshots[s][0], s)):
            offset, segs = snapshots[seq]
            tokens.extend({'text': t['text'], 'start': round(t['start'] + offset, 4), 'end': round(t['end'] + offset, 4)} for t in segs)
    else:
        tokens = [{'text': t['text'], 'start': round(t['start'], 4), 'end': round(t['end'], 4)} for t in longest]
    result = b''.join(audio)
    if not result: raise ProviderError('No audio returned')
    for a, b in zip(tokens, tokens[1:]):
        if b['start'] < a['start'] - 0.04: raise ProviderError('Non-monotonic native timestamps')
    return result, tokens, mode


def _post(req, key, timeout):
    data = json.dumps(req['body'], ensure_ascii=False).encode('utf-8')
    r = urllib.request.Request(req['url'], data=data, method='POST', headers={**req['headers'], 'Authorization': f'Bearer {key}'})
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return resp.read(), (resp.headers.get('content-type') or '').lower()
    except urllib.error.HTTPError as e:
        raise ProviderError(f'Fish HTTP {e.code}: {e.read()[:200].decode("utf-8", "replace")}', e.code) from None


def decode_wav(source, dest, sample_rate=48000):
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(source), '-ar', str(sample_rate), '-ac', '1', '-c:a', 'pcm_s16le', str(dest)], check=True)
    out = subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(dest)]).decode().strip()
    return float(out)


def synthesize(text, voice, params, dest, key, log=lambda *a: None, record_sse=None):
    """One request: write decoded 48k mono wav to dest; return {'seconds','tokens'|None,'model','mode','source'}.
    Tries voice.fallbackModels (default: free tier only) in order; PASS_THROUGH codes move to the next model."""
    models = list(voice.get('fallbackModels') or [voice.get('model') or DEFAULT_MODELS[0]])
    timestamps = voice.get('timestamps', True)
    dest = Path(dest); dest.parent.mkdir(parents=True, exist_ok=True)
    last = None
    for model in models:
        req = build_request(text, voice, params, timestamps=timestamps, model=model)
        raw = None
        for attempt in range(3):
            try:
                raw, ctype = _post(req, key, timeout=240)
                break
            except ProviderError as e:
                last = e
                if e.status in PASS_THROUGH:
                    log(f'  model {model} unavailable ({e.status}); trying the next configured model'); break
                wait = BACKOFF[min(attempt, 2)]; log(f'  {e} → retry in {wait}s'); time.sleep(wait)
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                last = e; wait = BACKOFF[min(attempt, 2)]; log(f'  network: {e} → retry in {wait}s'); time.sleep(wait)
        if raw is None: continue
        source = dest.with_suffix('.source.wav')
        if timestamps:
            if 'event-stream' not in ctype: raise ProviderError(f'Expected an SSE response, got {ctype or "unknown"}')
            if record_sse: Path(record_sse).write_bytes(raw)
            audio, tokens, mode = collect_stream(sse_events(raw.splitlines()))
        else:
            if 'json' in ctype: raise ProviderError(raw[:200].decode('utf-8', 'replace'))
            audio, tokens, mode = raw, None, None
        if len(audio) < 400: raise ProviderError('Tiny audio payload')
        source.write_bytes(audio)
        seconds = decode_wav(source, dest)
        if seconds < 0.15: raise ProviderError('Audio too short to be narration')
        if tokens and tokens[-1]['end'] > seconds + 0.18: raise ProviderError('Native timestamps extend past the decoded audio')
        return {'seconds': round(seconds, 3), 'tokens': tokens, 'model': model, 'mode': mode, 'source': str(source)}
    raise ProviderError(f'All configured Fish models failed: {last}')
