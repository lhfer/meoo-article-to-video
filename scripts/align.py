#!/usr/bin/env python3
"""Import measured timestamps or transcribe actual audio; review before production use.

  align.py import     <project> --id ID (--words F | --from-timing | --from-native) [--method provider|manual|whisper] [--provider P] [--no-map]
  align.py transcribe <project> --id ID --model <ggml.bin> [--language zh]
  align.py review     <project> --id ID --note '...'
Words in alignment.json are always on the DISPLAY narration; provider timing measured on the spoken text
(readings such as GPT-6 → GPT 六) is mapped back through beats[].overrides.
"""
import argparse, json, re, subprocess
from pathlib import Path
from common import read, write, inside, duration, filehash, texthash, norm, ident, run_main, spoken_text, cps

PUNCT = set('，。：；、？！“”‘’（）「」《》—…·-,.:;?!()"\' ')


def check_words(words, seconds):
    last = 0
    for w in words:
        if not isinstance(w.get('text'), str) or not isinstance(w.get('startMs'), (int, float)) or not isinstance(w.get('endMs'), (int, float)): raise ValueError('Expected Caption-shaped entries: text/startMs/endMs')
        if w['startMs'] < last - 1 or w['endMs'] <= w['startMs'] or w['endMs'] > seconds * 1000 + 80: raise ValueError('Timestamps overlap or exceed actual audio')
        last = w['endMs']; w.setdefault('timestampMs', None); w.setdefault('confidence', None)
    if not words: raise ValueError('No measured timestamps')


def _isp(ch): return ch in PUNCT or ch.isspace()


def _ascii(ch): return ch.isascii() and (ch.isalnum() or ch in '.%-_/')


JOINERS = '.-_/%'  # punctuation that glues an ASCII run together (claude-fable-5-1, v0.3, 92%)


def _break_before(text, k):
    """Is a caption break allowed before text[k]? After punctuation/space, or at a CJK↔ASCII boundary; never inside an ASCII run (joiners included)."""
    if k <= 0 or k >= len(text): return False
    a, b = text[k - 1], text[k]
    if a in JOINERS and k >= 2 and _ascii(text[k - 2]) and _ascii(b): return False
    if _isp(a): return not _isp(b)
    if _isp(b): return False
    return _ascii(a) != _ascii(b)


LOOKBACK = 6


def group_captions(narration, words, max_chars):
    """Group display words into readable captions: sentence punctuation always breaks, commas break once the line is long enough,
    an ASCII word or number is never split, and when the cap is hit the break backs up (≤ LOOKBACK chars) to the last punctuation or CJK↔ASCII boundary."""
    caps = []; cur = ''; idx = []; ci = 0

    def emit(text, wi):
        if text.strip() and wi: caps.append({'text': text, 'startMs': words[wi[0]]['startMs'], 'endMs': words[wi[-1]]['endMs'], 'timestampMs': None, 'confidence': None})

    def flush_all():
        nonlocal cur, idx
        emit(cur, [i for i in idx if i is not None]); cur, idx = '', []

    def split_at(k):
        nonlocal cur, idx
        emit(cur[:k], [i for i in idx[:k] if i is not None]); cur, idx = cur[k:], idx[k:]

    for ch in narration:
        if _isp(ch):
            if not cur: continue
            cur += ch; idx.append(None)
            if ch in '。！？；：?!': flush_all()
            elif ch in '，、,' and len(norm(cur)) >= 8: flush_all()
            continue
        if ci >= len(words): break
        if len(norm(cur)) >= max_chars and not (cur and _ascii(cur[-1]) and _ascii(ch)):
            k = next((j for j in range(len(cur), max(0, len(cur) - LOOKBACK) - 1, -1) if _break_before(cur, j) and len(norm(cur[:j])) >= 2), len(cur))
            split_at(k)
        cur += ch; idx.append(ci); ci += 1
    flush_all()
    return caps


def map_spoken_to_display(narration, overrides, spoken_words, max_chars=16):
    """Timed tokens on the SPOKEN text → per-character display words + caption groups on the NARRATION.
    A narration substring inherits the time span of its spoken replacement; multi-character provider tokens are split
    proportionally. Returns {'words': [...], 'captions': [...]} in Remotion Caption shape (ms)."""
    pairs = sorted([(a, b) for a, b in (overrides or []) if a], key=lambda x: -len(x[0]))
    units, i = [], 0
    while i < len(narration):
        hit = next(((a, b) for a, b in pairs if narration.startswith(a, i)), None)
        if hit: units.append(hit); i += len(hit[0])
        else: units.append((narration[i], narration[i])); i += 1
    spoken = ''.join(b for _, b in units)
    sp_chars = [c for c in spoken if not _isp(c)]
    timed, k = [], 0
    for w in spoken_words:
        txt = ''.join(c for c in w['text'] if not _isp(c))
        if not txt: continue
        n = len(txt)
        if norm(txt) != norm(''.join(sp_chars[k:k + n])):
            raise ValueError(f"token {txt!r} does not match the spoken text {''.join(sp_chars[k:k + n])!r} at character {k}; correct the timestamps or the overrides")
        a, b = float(w['startMs']), float(w['endMs'])
        for j in range(n): timed.append((a + (b - a) * j / n, a + (b - a) * (j + 1) / n))
        k += n
    if k != len(sp_chars): raise ValueError(f'timestamps cover {k} of {len(sp_chars)} spoken characters')
    words, k = [], 0
    for a, b in units:
        nb = [c for c in b if not _isp(c)]; na = [c for c in a if not _isp(c)]
        if not nb: continue
        span = timed[k:k + len(nb)]; k += len(nb)
        t0, t1 = span[0][0], span[-1][1]
        for j, c in enumerate(na):
            s0 = t0 + (t1 - t0) * j / len(na); s1 = t0 + (t1 - t0) * (j + 1) / len(na)
            words.append({'text': c, 'startMs': int(round(s0)), 'endMs': int(round(s1)), 'timestampMs': None, 'confidence': None})
    for w0, w1 in zip(words, words[1:]):
        if w1['startMs'] < w0['endMs']: w1['startMs'] = w0['endMs']
        if w1['endMs'] <= w1['startMs']: w1['endMs'] = w1['startMs'] + 1
    return {'words': words, 'captions': group_captions(narration, words, max_chars)}


def _segment(project, id, beat, src, words, captions, method, provider=None, spoken_words=None, mapping_error=None):
    audio = inside(project / 'public', src); seconds = duration(audio)
    check_words(words, seconds)
    if captions is not None: check_words(captions, seconds)
    spoken = spoken_text(beat)
    seg = {'src': src, 'durationSeconds': seconds, 'audioSha256': filehash(audio), 'textSha256': texthash(beat['narration']),
           'spokenSha256': texthash(spoken), 'method': method, 'provider': provider, 'reviewed': False, 'words': words,
           'transcriptMatches': norm(''.join(w['text'] for w in words)) == norm(beat['narration']), 'measuredCps': cps(spoken, seconds)}
    if captions is not None: seg['captions'] = captions
    if spoken_words is not None: seg['spokenWords'] = spoken_words
    if mapping_error: seg['mappingError'] = mapping_error
    edit = read(project / 'work/voice' / f'{id}-edit.json', None)
    if edit: seg['edit'] = {'editFingerprint': read(project / 'public/narration/index.json', {}).get(id, {}).get('editFingerprint'), 'removedSeconds': edit['removedSeconds'], 'cuts': edit['cuts']}
    return seg


def import_timing(project, id, provider=None, timing_path=None, no_map=False, method='provider'):
    """Normal path after tts.py: work/voice/<id>-timing.json (spoken text, remapped) → alignment.json display segment."""
    project = Path(project); script = read(project / 'content/script.json'); beat = next(b for b in script['beats'] if b['id'] == id)
    timing = read(Path(timing_path) if timing_path else project / 'work/voice' / f'{id}-timing.json')
    spoken_words = timing['words']; max_chars = (read(project / 'content/brief.json', {}).get('captions') or {}).get('maxChars', 16)
    src = f'narration/{id}.wav'
    if no_map:
        words, captions, err = spoken_words, timing.get('captions'), None
    else:
        try:
            mapped = map_spoken_to_display(beat['narration'], beat.get('overrides', []), spoken_words, max_chars); words, captions, err = mapped['words'], mapped['captions'], None
        except ValueError as e:
            words, captions, err = spoken_words, None, str(e)
    seg = _segment(project, id, beat, src, words, captions, method, provider, spoken_words, err)
    path = project / 'content/alignment.json'; data = read(path, {'version': 3, 'segments': {}}); data.setdefault('segments', {})[id] = seg; write(path, data)
    return seg


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter); sub = p.add_subparsers(dest='cmd', required=True)
    for cmd in ['import', 'transcribe', 'review']:
        q = sub.add_parser(cmd); q.add_argument('project', type=Path); q.add_argument('--id', required=True)
        if cmd != 'review': q.add_argument('--audio', help='Relative to public; defaults to narration/<id>.wav (or .mp3)')
        if cmd == 'import':
            q.add_argument('--words', type=Path, help='Measured words on the DISPLAY text (Caption shape, ms)'); q.add_argument('--from-timing', action='store_true', help='Use work/voice/<id>-timing.json (spoken text) and map to display')
            q.add_argument('--from-native', action='store_true', help='Use work/voice/raw/<id>.native.json tokens (seconds, unedited audio)'); q.add_argument('--no-map', action='store_true'); q.add_argument('--provider')
            q.add_argument('--method', choices=['provider', 'manual', 'whisper'], default='provider')
        if cmd == 'transcribe': q.add_argument('--model', required=True, type=Path); q.add_argument('--language', default='zh')
        if cmd == 'review': q.add_argument('--note', required=True, help='Record actual listen/check and corrections')
    a = p.parse_args(); project = a.project.resolve(); id = ident(a.id)
    beat = next((b for b in read(project / 'content/script.json')['beats'] if b['id'] == id), None)
    if not beat: raise ValueError('Unknown script beat ' + id)
    path = project / 'content/alignment.json'; data = read(path, {'version': 3, 'segments': {}})
    if a.cmd == 'review':
        seg = data['segments'][id]; audio = inside(project / 'public', seg['src']); check_words(seg['words'], duration(audio))
        if seg['audioSha256'] != filehash(audio) or seg['textSha256'] != texthash(beat['narration']): raise ValueError('Audio/script changed; re-align first')
        if norm(''.join(w['text'] for w in seg['words'])) != norm(beat['narration']): raise ValueError('Transcript differs from approved text; correct measured words and re-import')
        if not a.note.strip(): raise ValueError('Provide the actual timing review note')
        seg.update(reviewed=True, reviewNote=a.note); write(path, data); print(id + ' alignment reviewed'); return
    if a.cmd == 'import' and (a.from_timing or a.from_native):
        timing_path = None
        if a.from_native:
            native = read(project / 'work/voice/raw' / f'{id}.native.json')
            if not native.get('tokens'): raise ValueError('No native tokens recorded for ' + id)
            timing_path = project / 'work/voice' / f'{id}-native-timing.json'
            write(timing_path, {'text': native['text'], 'words': [{'text': t['text'], 'startMs': round(t['start'] * 1000, 3), 'endMs': round(t['end'] * 1000, 3), 'timestampMs': None, 'confidence': None} for t in native['tokens']], 'captions': None})
        seg = import_timing(project, id, a.provider, timing_path, a.no_map, a.method)
        print(json.dumps({'id': id, 'method': seg['method'], 'words': len(seg['words']), 'captions': len(seg.get('captions') or []), 'transcriptMatches': seg['transcriptMatches'], 'mappingError': seg.get('mappingError'), 'reviewed': False, 'next': 'Listen, correct actual timestamps/text when needed, then align.py review --note ...'}, ensure_ascii=False)); return
    default_src = f'narration/{id}.wav' if (project / 'public/narration' / f'{id}.wav').exists() else f'narration/{id}.mp3'
    src = a.audio or default_src; audio = inside(project / 'public', src); seconds = duration(audio)
    spoken_words = None; err = None; captions = None; provider = getattr(a, 'provider', None)
    if a.cmd == 'import':
        if not a.words: raise ValueError('Provide --words, --from-timing or --from-native')
        raw = read(a.words); words = raw if isinstance(raw, list) else raw['words']; method = a.method
        captions = None if isinstance(raw, list) else raw.get('captions')
    else:
        if not a.model.is_file(): raise ValueError('Whisper model file missing')
        folder = project / 'work/alignment' / id; folder.mkdir(parents=True, exist_ok=True); wav = folder / 'audio.wav'; out = folder / 'whisper'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(audio), '-ar', '16000', '-ac', '1', str(wav)], check=True)
        subprocess.run(['whisper-cli', '-m', str(a.model.resolve()), '-f', str(wav), '-l', a.language, '-ml', '1', '-sow', '-ojf', '-of', str(out)], check=True)
        raw = read(out.with_suffix('.json')); words = []
        for item in raw.get('transcription', []):
            text = item.get('text', ''); offsets = item.get('offsets', {})
            if text.strip() and offsets.get('to', 0) > offsets.get('from', 0): words.append({'text': text, 'startMs': offsets['from'], 'endMs': offsets['to'], 'timestampMs': None, 'confidence': None})
        method = 'whisper'; provider = 'whisper'
        # Whisper hears the spoken readings; map back to the display text when the beat declares overrides.
        if beat.get('overrides'):
            spoken_words = words; write(folder / 'whisper-words.json', words)
            try:
                mapped = map_spoken_to_display(beat['narration'], beat['overrides'], words, (read(project / 'content/brief.json', {}).get('captions') or {}).get('maxChars', 16)); words, captions = mapped['words'], mapped['captions']
            except ValueError as e: err = str(e)
    seg = _segment(project, id, beat, src, words, captions, method, provider, spoken_words, err)
    data.setdefault('segments', {})[id] = seg; write(path, data)
    print(json.dumps({'id': id, 'method': method, 'words': len(words), 'transcriptMatches': seg['transcriptMatches'], 'mappingError': err, 'reviewed': False, 'next': 'Listen, correct actual timestamps/text when needed, then align.py review --note ...'}, ensure_ascii=False))


if __name__ == '__main__': run_main(main)
