#!/usr/bin/env python3
"""Breath/pause editing (气口) for narration: trim lead/tail silence, shorten internal pauses, remap native timestamps,
then two-pass loudness. ffmpeg only (no numpy). The edit is fingerprinted so cached audio is never served unedited.

  voice_edit.py <project> [--only id,id] [--force] [--dry-run] [--report]
"""
import argparse, hashlib, json, re, subprocess
from pathlib import Path
from common import read, write, filehash, norm, ident, duration, cps, run_main

VOICE_EDIT_VERSION = '1'
DEFAULTS = {
    'enabled': True, 'silenceThresholdDb': -38, 'minSilenceSeconds': 0.16,
    'leadKeepSeconds': 0.05, 'tailKeepSeconds': 0.10,
    'maxInternalPauseSeconds': 0.30, 'keepInternalPauseSeconds': 0.18,
    'jointFadeMs': 2, 'edgeFadeMs': 4,
    'loudness': {'I': -15, 'TP': -1.5, 'LRA': 7},
    'prefilter': 'highpass=f=70,acompressor=threshold=0.11:ratio=2:attack=5:release=60',
}


def settings(brief):
    cfg = {**DEFAULTS, **(brief.get('voiceEdit') or {})}
    cfg['loudness'] = {**DEFAULTS['loudness'], **((brief.get('voiceEdit') or {}).get('loudness') or {})}
    return cfg


def edit_fingerprint(synth_fingerprint, cfg):
    material = {k: v for k, v in cfg.items() if k != 'enabled'}
    return hashlib.sha256(f"{synth_fingerprint}\x1f{json.dumps(material, sort_keys=True)}\x1f{VOICE_EDIT_VERSION}".encode()).hexdigest()[:24]


# ---------------------------------------------------------------- pure functions
def parse_silencedetect(stderr, total):
    """ffmpeg silencedetect stderr → [(start, end)]; a dangling silence_start closes at the audio end."""
    runs, current = [], None
    for line in stderr.splitlines():
        m = re.search(r'silence_start: ([0-9.]+)', line)
        if m: current = float(m.group(1))
        m = re.search(r'silence_end: ([0-9.]+)', line)
        if m and current is not None: runs.append((current, float(m.group(1)))); current = None
    if current is not None: runs.append((current, total))
    return runs


def plan_cuts(silences, total, cfg, tokens=None):
    """Which intervals to remove. Native token boundaries are respected: lead/tail cuts never enter the first/last token."""
    lead_keep, tail_keep = float(cfg['leadKeepSeconds']), float(cfg['tailKeepSeconds'])
    max_int, keep_int = float(cfg['maxInternalPauseSeconds']), float(cfg['keepInternalPauseSeconds'])
    first = tokens[0]['start'] if tokens else None
    last = tokens[-1]['end'] if tokens else None
    cuts = []
    for s, e in silences:
        if s <= 0.02:
            cut_end = e - lead_keep
            if first is not None: cut_end = min(cut_end, first - 0.025)
            if cut_end > 0.01: cuts.append((0.0, round(cut_end, 4)))
        elif e >= total - 0.03:
            cut_start = s + tail_keep
            if last is not None: cut_start = max(cut_start, last + 0.05)
            if cut_start < total - 0.01: cuts.append((round(cut_start, 4), round(total, 4)))
        elif e - s > max_int:
            half = keep_int / 2
            cuts.append((round(s + half, 4), round(e - half, 4)))
    return cuts


def remap(t, cuts):
    """Time in the raw file → time in the edited file (monotone; remap(total) == total − Σcuts)."""
    return max(0.0, t - sum(max(0.0, min(t, e) - s) for s, e in cuts if t > s))


def keeps_from_cuts(cuts, total):
    keeps, cursor = [], 0.0
    for s, e in cuts:
        if s > cursor: keeps.append((cursor, s))
        cursor = max(cursor, e)
    if cursor < total: keeps.append((cursor, total))
    return keeps


def gap_seconds(prev_beat, next_beat, policy):
    """Silence to leave between two narration beats: explicit pauseAfter, else the larger of the punctuation and
    beat-kind tables, else the default; always clamped to [min, max]."""
    policy = policy or {}
    lo, hi = float(policy.get('min', 0.12)), float(policy.get('max', 0.8))
    explicit = ((prev_beat.get('voice') or {}).get('pauseAfter'))
    if explicit is not None:
        g = float(explicit)
    else:
        tail = (prev_beat.get('narration') or '').rstrip().rstrip('”’"\')）】」』》')
        last = tail[-1] if tail else ''
        candidates = []
        by_p = policy.get('byPunctuation') or {}
        by_k = policy.get('byBeatKind') or {}
        if last in by_p: candidates.append(float(by_p[last]))
        if next_beat.get('kind') in by_k: candidates.append(float(by_k[next_beat['kind']]))
        g = max(candidates) if candidates else float(policy.get('default', 0.3))
    return round(min(hi, max(lo, g)), 3)


def remap_tokens(tokens, cuts):
    """Native tokens (seconds, spoken text) → Caption-shaped words in the edited file. Tokens that collapse to zero
    length inside a cut are merged forward into the next token; no boundaries are invented."""
    words, carry = [], ''
    for t in tokens:
        a, b = remap(float(t['start']), cuts), remap(float(t['end']), cuts)
        if b - a <= 0.001:
            carry += t['text']; continue
        words.append({'text': carry + t['text'], 'startMs': round(a * 1000, 3), 'endMs': round(b * 1000, 3), 'timestampMs': None, 'confidence': None}); carry = ''
    if carry and words: words[-1]['text'] += carry
    for prev, cur in zip(words, words[1:]):
        if cur['startMs'] < prev['endMs']: cur['startMs'] = prev['endMs']
        if cur['endMs'] <= cur['startMs']: cur['endMs'] = cur['startMs'] + 1
    return words


# ---------------------------------------------------------------- ffmpeg steps
def detect_silence(path, cfg):
    total = duration(path)
    r = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', str(path), '-af',
                        f"silencedetect=noise={cfg['silenceThresholdDb']}dB:d={cfg['minSilenceSeconds']}", '-f', 'null', '-'],
                       capture_output=True, text=True, check=True)
    return parse_silencedetect(r.stderr, total), total


def cut_audio(src, dst, keeps, cfg):
    joint, edge = float(cfg['jointFadeMs']) / 1000, float(cfg['edgeFadeMs']) / 1000
    parts, labels = [], []
    for i, (a, b) in enumerate(keeps):
        length = b - a
        fin = min(edge if i == 0 else joint, length / 2)
        fout = min(edge if i == len(keeps) - 1 else joint, length / 2)
        parts.append(f"[0:a]atrim=start={a:.4f}:end={b:.4f},asetpts=PTS-STARTPTS,afade=t=in:st=0:d={fin:.4f},afade=t=out:st={max(0.0, length - fout):.4f}:d={fout:.4f}[k{i}]")
        labels.append(f'[k{i}]')
    graph = ';'.join(parts) + f";{''.join(labels)}concat=n={len(keeps)}:v=0:a=1[out]"
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(src), '-filter_complex', graph, '-map', '[out]', '-ar', '48000', '-ac', '1', '-c:a', 'pcm_s16le', str(dst)], check=True)


def loudness_two_pass(src, dst, cfg):
    L = cfg['loudness']; base = f"loudnorm=I={L['I']}:TP={L['TP']}:LRA={L['LRA']}"
    pre = (cfg.get('prefilter') + ',') if cfg.get('prefilter') else ''
    r = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', str(src), '-af', f'{pre}{base}:print_format=json', '-f', 'null', '-'], capture_output=True, text=True, check=True)
    blocks = re.findall(r'\{[^{}]*"input_i"[^{}]*\}', r.stderr)
    if not blocks: raise ValueError('loudnorm measurement missing from ffmpeg output')
    m = json.loads(blocks[-1])
    applied = f"{pre}{base}:measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true"
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(src), '-af', applied, '-ar', '48000', '-ac', '1', '-c:a', 'pcm_s16le', str(dst)], check=True)
    return {'measuredI': float(m['input_i']), 'measuredTP': float(m['input_tp'])}


def edit_beat(project, id, raw_wav, tokens, cfg, spoken, dest=None):
    """raw wav + native tokens → public/narration/<id>.wav, work/voice/<id>-edit.json, work/voice/<id>-timing.json."""
    project = Path(project); work = project / 'work/voice'; work.mkdir(parents=True, exist_ok=True)
    dest = Path(dest) if dest else project / 'public/narration' / f'{id}.wav'; dest.parent.mkdir(parents=True, exist_ok=True)
    silences, total = detect_silence(raw_wav, cfg)
    cuts = plan_cuts(silences, total, cfg, tokens)
    keeps = keeps_from_cuts(cuts, total)
    cut = work / f'{id}.cut.wav'
    if cuts: cut_audio(raw_wav, cut, keeps, cfg)
    else: subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(raw_wav), '-ar', '48000', '-ac', '1', '-c:a', 'pcm_s16le', str(cut)], check=True)
    loud = loudness_two_pass(cut, dest, cfg)
    edited = duration(dest)
    words = remap_tokens(tokens, cuts) if tokens else None
    if words and words[-1]['endMs'] > edited * 1000 + 80: raise ValueError(f'Remapped timing exceeds edited audio for {id}')
    report = {'id': id, 'rawSeconds': round(total, 3), 'editedSeconds': round(edited, 3), 'removedSeconds': round(total - edited, 3),
              'cuts': cuts, 'keeps': keeps, 'internalCuts': sum(1 for s, e in cuts if s > 0.02 and e < total - 0.03),
              'silenceThresholdDb': cfg['silenceThresholdDb'], 'minimumRemainingPauseMs': round(float(cfg['keepInternalPauseSeconds']) * 1000),
              'loudness': loud, 'measuredCps': cps(spoken, edited), 'timestamps': 'native-remapped' if words else 'none',
              'notes': 'Lead/tail silence trimmed, internal pauses shortened symmetrically; native timestamps remapped through the cuts; no boundaries invented.'}
    write(work / f'{id}-edit.json', report)
    if words: write(work / f'{id}-timing.json', {'text': spoken, 'words': words, 'captions': None})
    elif (work / f'{id}-timing.json').exists(): (work / f'{id}-timing.json').unlink()
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('project', type=Path); p.add_argument('--only'); p.add_argument('--force', action='store_true'); p.add_argument('--dry-run', action='store_true'); p.add_argument('--report', action='store_true'); a = p.parse_args()
    project = a.project.resolve(); brief = read(project / 'content/brief.json'); cfg = settings(brief)
    index_path = project / 'public/narration/index.json'; index = read(index_path, {})
    script = read(project / 'content/script.json'); beats = {b['id']: b for b in script['beats']}
    ids = [ident(x) for x in a.only.split(',')] if a.only else list(index)
    if a.report:
        for id in ids:
            r = read(project / 'work/voice' / f'{id}-edit.json', None)
            print(f"{id:14s} " + (f"{r['rawSeconds']:6.2f}s → {r['editedSeconds']:6.2f}s  -{r['removedSeconds']:.2f}s  cuts {r['internalCuts']}  {r['measuredCps']} cps" if r else 'not edited'))
        return
    from common import spoken_text
    durations = read(project / 'content/narration-durations.json', {})
    for id in ids:
        entry = index.get(id)
        if not entry or not entry.get('raw'): raise ValueError(f'No raw synthesis recorded for {id}; run tts.py first')
        fp = edit_fingerprint(entry['synthFingerprint'], cfg)
        dest = project / 'public/narration' / f'{id}.wav'
        if not a.force and entry.get('editFingerprint') == fp and dest.exists() and filehash(dest) == entry.get('sha256'):
            print(f'{id}: edit current'); continue
        if a.dry_run: print(f'{id}: would edit (fingerprint {fp})'); continue
        native = read(project / entry['native'], {}) if entry.get('native') else {}
        report = edit_beat(project, id, project / entry['raw'], native.get('tokens'), cfg, spoken_text(beats[id]))
        entry.update(editFingerprint=fp, fingerprint=fp, src=f'narration/{id}.wav', sha256=filehash(dest), seconds=report['editedSeconds'], removedSeconds=report['removedSeconds'], measuredCps=report['measuredCps'])
        durations[id] = report['editedSeconds']; index[id] = entry
        write(index_path, index); write(project / 'content/narration-durations.json', durations)
        print(f"{id}: {report['rawSeconds']:.2f}s → {report['editedSeconds']:.2f}s (-{report['removedSeconds']:.2f}s, {report['internalCuts']} internal cuts, {report['measuredCps']} cps); re-run align.py import --from-timing")


if __name__ == '__main__': run_main(main)
