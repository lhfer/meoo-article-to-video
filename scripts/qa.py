#!/usr/bin/env python3
"""Machine checks on a rendered file (ffmpeg/ffprobe only): luminance comfort limits, visual-change cadence, frozen frames,
cut-vs-event alignment, contact sheet, optional whisper cross-check. Writes out/qa/report-<fmt>.json and appends out/qa.md.
These are house-style comfort limits, not a photosensitive-epilepsy safety certification.

  qa.py <project> --input out/preview-3x4.mp4 [--format 3x4] [--sheet] [--asr --model <ggml.bin>] [--json]
"""
import argparse, json, re, subprocess, time
from pathlib import Path
from common import read, write, probe, norm, run_main, spoken_text, filehash

LIMITS = {'flashMaxFrames': 4, 'flashLuma': 200, 'flashWindowSeconds': 8, 'flashPerWindow': 1, 'jumpDelta': 60, 'jumpsPerSecond': 2,
          'darkLuma': 8, 'darkMaxSeconds': 0.2, 'brightLuma': 235, 'brightMaxFrames': 3, 'changeDelta': 6.0, 'stillDelta': 1.5, 'stillFps': 10, 'cutToleranceFrames': 2,
          # content placement (measured above the caption band): a 16:9 frame whose content sits in the left third is a 3:4 layout pushed left
          'coverageDelta': 24, 'wideMinWidth': 0.55, 'wideRightMassMin': 0.08, 'wideLeftMassMax': 0.5, 'tallMinHeight': 0.45, 'clusteredFrameRatio': 0.3}
CAPTION_TOP = {'3x4': 1103/1440, '9x16': 1442/1920, '16x9': 859/1080}  # kit/layout.ts captionTop ÷ height


def configure_layout(project):
    """Share the exact caption band with the renderer, including film.style.layout overrides."""
    project=Path(project)
    engine=project/'src/kit/layout-engine.mjs'
    if not engine.is_file():raise ValueError('Missing measured-layout engine; migrate the project instead of guessing subtitle geometry')
    film=read(project/'content/film.json',{});options=film.get('style',{}).get('layout',{})
    code="import {layoutFor} from './src/kit/layout-engine.mjs';const o=JSON.parse(process.argv[1]);console.log(JSON.stringify(Object.fromEntries(['3x4','9x16','16x9'].map(f=>{const l=layoutFor(f,o[f]);return [f,l.caption.y/l.h]}))))"
    r=subprocess.run(['node','--input-type=module','-e',code,json.dumps(options)],cwd=project,capture_output=True,text=True,check=True)
    CAPTION_TOP.update(json.loads(r.stdout))


def yavg_series(path, vf_prefix=''):
    """Per-frame luma average through signalstats (optionally after a filter such as tblend difference)."""
    vf = f"{vf_prefix}scale=160:-2,signalstats,metadata=print:key=lavfi.signalstats.YAVG:file=-"
    r = subprocess.run(['ffmpeg', '-v', 'error', '-nostats', '-i', str(path), '-vf', vf, '-f', 'null', '-'], capture_output=True, text=True, check=True)
    return [float(m) for m in re.findall(r'YAVG=([0-9.]+)', r.stdout)]


def gray_frames(path, w=96, h=54, fps=1):
    """Downscaled 8-bit gray frames (one per second by default); pure-Python analysis follows."""
    r = subprocess.run(['ffmpeg', '-v', 'error', '-nostats', '-i', str(path), '-vf', f'fps={fps},scale={w}:{h}', '-pix_fmt', 'gray', '-f', 'rawvideo', '-'], capture_output=True, check=True)
    n = w * h; data = r.stdout
    return [data[i * n:(i + 1) * n] for i in range(len(data) // n)], w, h


def frame_placement(frame, w, h, fmt, delta=LIMITS['coverageDelta']):
    """Where the content is: bbox (fractions) and horizontal mass thirds, measured above the caption band against the border-mode background."""
    top_limit = max(2, int(h * CAPTION_TOP.get(fmt, 0.85)))
    border = list(frame[:w]) + list(frame[(top_limit - 1) * w:top_limit * w]) + [frame[y * w] for y in range(top_limit)] + [frame[y * w + w - 1] for y in range(top_limit)]
    bg = max(set(border), key=border.count)
    xs, ys, thirds = [], [], [0, 0, 0]
    for y in range(top_limit):
        row = frame[y * w:(y + 1) * w]
        for x in range(w):
            if abs(row[x] - bg) > delta: xs.append(x); ys.append(y); thirds[min(2, x * 3 // w)] += 1
    if not xs: return None
    total = sum(thirds)
    return {'x0': round(min(xs) / w, 3), 'x1': round((max(xs) + 1) / w, 3), 'y0': round(min(ys) / top_limit, 3), 'y1': round((max(ys) + 1) / top_limit, 3), 'thirds': [round(t / total, 3) for t in thirds]}


def analyze_coverage(placements, fmt, limits=LIMITS):
    """Findings when too many sampled frames use the canvas badly: 16:9 content narrower than wideMinWidth or piled in the left third; vertical content shorter than tallMinHeight."""
    frames = [p for p in placements if p]
    if not frames: return [], {'sampled': 0}
    narrow = clustered = short = 0
    for p in frames:
        width = p['x1'] - p['x0']; height = p['y1'] - p['y0']
        if fmt == '16x9':
            if width < limits['wideMinWidth']: narrow += 1
            if p['thirds'][2] < limits['wideRightMassMin'] and p['thirds'][0] > limits['wideLeftMassMax']: clustered += 1
        elif height < limits['tallMinHeight']: short += 1
    n = len(frames); ratio = limits['clusteredFrameRatio']; findings = []
    if narrow / n > ratio: findings.append({'kind': 'narrow-content', 'frames': narrow, 'of': n, 'hint': '16:9 content spans under 55% of the width: use kit columns() (subject ≥ 55%, two columns), not a 3:4 layout pushed left'})
    if clustered / n > ratio: findings.append({'kind': 'clustered-left', 'frames': clustered, 'of': n, 'hint': 'content mass sits in the left third with an empty right third: give the right column a subject (screen, card, metric)'})
    if short / n > ratio: findings.append({'kind': 'short-content', 'frames': short, 'of': n, 'hint': 'vertical content uses under 45% of the height: scale the subject up or stack a second element'})
    return findings, {'sampled': n, 'narrowFrames': narrow, 'clusteredFrames': clustered, 'shortFrames': short}


def runs(mask):
    out, start = [], None
    for i, v in enumerate(mask):
        if v and start is None: start = i
        if not v and start is not None: out.append((start, i)); start = None
    if start is not None: out.append((start, len(mask)))
    return out


def analyze_luma(y, fps, limits=LIMITS):
    findings = []
    flash_runs = runs([v > limits['flashLuma'] for v in y])
    for a, b in flash_runs:
        if b - a > limits['flashMaxFrames']: findings.append({'kind': 'flash-too-long', 'atSeconds': round(a / fps, 2), 'frames': b - a})
    window = int(limits['flashWindowSeconds'] * fps)
    for i, (a, _) in enumerate(flash_runs):
        near = [r for r in flash_runs if a <= r[0] < a + window]
        if len(near) > limits['flashPerWindow']: findings.append({'kind': 'flash-frequency', 'atSeconds': round(a / fps, 2), 'count': len(near), 'windowSeconds': limits['flashWindowSeconds']}); break
    jumps = [i for i in range(1, len(y)) if abs(y[i] - y[i - 1]) > limits['jumpDelta']]
    for j in jumps:
        if sum(1 for k in jumps if j <= k < j + int(fps)) > limits['jumpsPerSecond']: findings.append({'kind': 'luminance-jumps', 'atSeconds': round(j / fps, 2)}); break
    for a, b in runs([v < limits['darkLuma'] for v in y]):
        if (b - a) / fps > limits['darkMaxSeconds']: findings.append({'kind': 'black-frames', 'atSeconds': round(a / fps, 2), 'seconds': round((b - a) / fps, 2)})
    bright = sum(1 for v in y if v > limits['brightLuma'])
    if bright > limits['brightMaxFrames']: findings.append({'kind': 'overexposed-frames', 'frames': bright})
    return findings, {'flashes': len(flash_runs), 'jumps': len(jumps), 'minLuma': round(min(y), 1) if y else None, 'maxLuma': round(max(y), 1) if y else None}


def analyze_changes(diff, fps, max_gap_seconds, delta=LIMITS['changeDelta']):
    """diff = per-frame luma of |frame - previous|; a visible change is a frame whose difference exceeds delta."""
    changes = [i for i, v in enumerate(diff) if v > delta]
    gaps, last = [], 0
    for c in changes + [len(diff)]:
        if (c - last) / fps > max_gap_seconds: gaps.append({'fromSeconds': round(last / fps, 2), 'toSeconds': round(c / fps, 2), 'seconds': round((c - last) / fps, 2)})
        last = c
    return gaps, {'changes': len(changes), 'longestStillSeconds': round(max([(g['seconds']) for g in gaps], default=0), 2)}


def still_runs(frames, fps, window_s, delta=LIMITS['stillDelta']):
    """Stretches with no visible change, on downscaled gray frames (gray_frames). A change is either an adjacent-frame step above
    `delta` (something appears, moves or cuts) or drift accumulated since the last change above `delta` (slow motion counts too).
    A stretch longer than `window_s` without either is a still stretch — the moment viewers leave."""
    if not frames: return [], {'changes': 0, 'longestStillSeconds': 0}
    def mean(a, b): return sum(map(abs, map(int.__sub__, a, b))) / len(a)
    stills, anchor, changes = [], 0, 0
    def close(t):
        if (t - anchor) / fps > window_s: stills.append({'fromSeconds': round(anchor / fps, 2), 'toSeconds': round(t / fps, 2), 'seconds': round((t - anchor) / fps, 2)})
    for t in range(1, len(frames)):
        if mean(frames[t], frames[t - 1]) > delta or mean(frames[t], frames[anchor]) > delta:
            close(t); anchor = t; changes += 1
    close(len(frames))
    return stills, {'changes': changes, 'longestStillSeconds': round(max([g['seconds'] for g in stills], default=0), 2)}


def still_stretches(path, window_s, fmt=None, delta=LIMITS['stillDelta'], fps=LIMITS['stillFps']):
    """Still stretches of a rendered file, measured on the picture above the caption band (captions changing do not make a dead picture alive)."""
    frames, w, h = gray_frames(path, 96, 54, fps)
    if fmt in CAPTION_TOP: rows = max(2, int(h * CAPTION_TOP[fmt])); frames = [f[:rows * w] for f in frames]
    return still_runs(frames, fps, window_s, delta)


def split_holds(stills, timeline):
    """Still stretches lying inside a shot that declares `hold` (film.shots[].hold: reason — e.g. a screen recording the eye follows) are declared, not violations."""
    if not timeline: return stills, []
    fps = timeline.get('fps') or 30
    holds = [(s['from'] / fps, s['end'] / fps, s['hold'], s['id']) for s in timeline.get('shots') or [] if s.get('hold')]
    keep, declared = [], []
    for g in stills:
        h = next((h for h in holds if h[0] - 0.05 <= g['fromSeconds'] and g['toSeconds'] <= h[1] + 0.05), None)
        (declared if h else keep).append({**g, 'shot': h[3], 'hold': h[2]} if h else g)
    return keep, declared


def freezes(path):
    r = subprocess.run(['ffmpeg', '-v', 'info', '-nostats', '-i', str(path), '-vf', 'freezedetect=n=-60dB:d=0.5', '-f', 'null', '-'], capture_output=True, text=True)
    starts = re.findall(r'freeze_start: ([0-9.]+)', r.stderr); durs = re.findall(r'freeze_duration: ([0-9.]+)', r.stderr)
    return [{'atSeconds': round(float(s), 2), 'seconds': round(float(d), 2)} for s, d in zip(starts, durs)]


def cut_checks(timeline, tolerance=LIMITS['cutToleranceFrames']):
    findings = []; events = timeline['events']
    for s in timeline['shots']:
        anchor = s.get('anchor')
        if anchor:
            if anchor not in events: findings.append({'kind': 'unknown-anchor', 'shot': s['id'], 'anchor': anchor}); continue
            if abs(s['from'] - events[anchor]) > tolerance: findings.append({'kind': 'cut-off-event', 'shot': s['id'], 'anchor': anchor, 'deltaFrames': s['from'] - events[anchor]})
        for v in timeline['voices']:
            for w in v.get('words') or []:
                a = v['from'] + w['startMs'] / 1000 * timeline['fps']; b = v['from'] + w['endMs'] / 1000 * timeline['fps']
                if a + 1 < s['from'] < b - 1 and s['from'] > 0: findings.append({'kind': 'cut-inside-word', 'shot': s['id'], 'word': w['text'], 'atSeconds': round(s['from'] / timeline['fps'], 2)}); break
    return findings


def contact_sheet(path, out, seconds, every=2.0, cols=6):
    n = max(1, int(seconds / every) + 1); rows = (n + cols - 1) // cols
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(path), '-vf', f'fps=1/{every},scale=360:-2,tile={cols}x{rows}', '-frames:v', '1', str(out)], check=True)
    return str(out)


def asr_check(project, path, model, timeline):
    folder = project / 'work/qa'; folder.mkdir(parents=True, exist_ok=True); wav = folder / 'asr.wav'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(path), '-vn', '-ar', '16000', '-ac', '1', str(wav)], check=True)
    subprocess.run(['whisper-cli', '-m', str(model), '-f', str(wav), '-l', 'zh', '-ml', '1', '-sow', '-ojf', '-of', str(folder / 'asr')], check=True, capture_output=True)
    raw = read(folder / 'asr.json'); beats = {b['id']: b for b in read(project / 'content/script.json')['beats']}
    import difflib
    rows = []
    for v in timeline['voices']:
        a = v['from'] / timeline['fps'] * 1000; b = (v['from'] + v['durationFrames']) / timeline['fps'] * 1000
        heard = ''.join(x['text'] for x in raw.get('transcription', []) if a <= x.get('offsets', {}).get('from', -1) < b)
        expected = spoken_text(beats[v['id']]) if v['id'] in beats else ''
        rows.append({'id': v['id'], 'matchRatio': round(difflib.SequenceMatcher(None, norm(heard), norm(expected)).ratio(), 2), 'heard': heard[:60]})
    return sorted(rows, key=lambda r: r['matchRatio'])


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter); p.add_argument('project', type=Path); p.add_argument('--input', required=True); p.add_argument('--format'); p.add_argument('--sheet', action='store_true'); p.add_argument('--asr', action='store_true'); p.add_argument('--model', type=Path); p.add_argument('--json', action='store_true'); p.add_argument('--advisory',action='store_true',help='Report-only diagnostic; never turns a failed QA into a passing delivery'); a = p.parse_args()
    project = a.project.resolve(); path = (project / a.input) if not Path(a.input).is_absolute() else Path(a.input)
    if not path.is_file(): raise ValueError('Rendered file not found: ' + str(path))
    configure_layout(project)
    brief = read(project / 'content/brief.json', {}); timeline = read(project / 'content/timeline.json', None)
    fmt = a.format or (re.search(r'(3x4|9x16|16x9)', path.name).group(1) if re.search(r'(3x4|9x16|16x9)', path.name) else '?')
    info = probe(path); video = next(s for s in info['streams'] if s['codec_type'] == 'video'); seconds = float(info['format']['duration'])
    num, den = video.get('avg_frame_rate', '30/1').split('/'); fps = float(num) / float(den or 1)
    y = yavg_series(path)
    luma_findings, luma_stats = analyze_luma(y, fps)
    max_gap = (brief.get('pacing') or {}).get('visualChangeMaxSeconds', 1.5 if brief.get('profile', 'viral') == 'viral' else 2.5)
    gaps, change_stats = still_stretches(path, max_gap, fmt); gaps, declared_holds = split_holds(gaps, timeline)
    frames, gw, gh = gray_frames(path); placements = [frame_placement(f, gw, gh, fmt) for f in frames]; coverage_findings, coverage_stats = analyze_coverage(placements, fmt)
    report = {'file': str(path), 'format': fmt, 'width': video['width'], 'height': video['height'], 'seconds': round(seconds, 3), 'fps': fps, 'hasAudio': any(s['codec_type'] == 'audio' for s in info['streams']),
              'limits': LIMITS, 'luma': luma_stats, 'lumaFindings': luma_findings, 'visualChange': {**change_stats, 'maxGapSeconds': max_gap, 'stillGaps': gaps, 'declaredHolds': declared_holds}, 'coverage': {**coverage_stats, 'findings': coverage_findings}, 'freezes': freezes(path),
              'cuts': cut_checks(timeline) if timeline else [], 'checkedAt': time.strftime('%Y-%m-%dT%H:%M:%S'),
              'scope': 'Machine checks only: luminance comfort limits (house style, not a photosensitivity certification), change cadence, freezes, cut alignment. Pacing, meaning and sound need a real viewing.'}
    out_dir = project / 'out/qa'; out_dir.mkdir(parents=True, exist_ok=True)
    if a.sheet: report['contactSheet'] = contact_sheet(path, out_dir / f'sheet-{fmt}.jpg', seconds)
    if a.asr:
        if not a.model or not a.model.is_file(): raise ValueError('--asr needs --model <ggml.bin>')
        report['asr'] = asr_check(project, path, a.model.resolve(), timeline)
    # A white product background is not a flash/overexposure diagnosis. Absolute-brightness heuristics, coverage,
    # exact freezes and word-interior cuts are review hints; real temporal flashes, unplanned stills and bad anchors block.
    hard_luma=[x for x in luma_findings if x['kind'] in ('flash-frequency','luminance-jumps','black-frames')]
    hard_cuts=[x for x in report['cuts'] if x['kind'] in ('unknown-anchor','cut-off-event')]
    hard=hard_luma+gaps+hard_cuts
    report.update(inputSha256=filehash(path),ok=not hard,hardFindings=hard,
                  advisoryFindings=[x for x in luma_findings if x not in hard_luma]+coverage_findings+report['freezes']+[x for x in report['cuts'] if x not in hard_cuts])
    write(out_dir / f'report-{fmt}.json', report)
    problems = len(luma_findings) + len(gaps) + len(report['freezes']) + len(report['cuts']) + len(coverage_findings)
    lines = [f"## qa.py · {path.name} · {report['checkedAt']}", '', f"- {video['width']}×{video['height']} · {seconds:.2f}s · {fps:g} fps · audio {'yes' if report['hasAudio'] else 'NO'}",
             f"- luma: min {luma_stats['minLuma']} max {luma_stats['maxLuma']} · flashes {luma_stats['flashes']} · findings {luma_findings or 'none'}",
             f"- visual change: {change_stats['changes']} changes · longest still {change_stats['longestStillSeconds']}s (limit {max_gap}s) · gaps {gaps or 'none'}" + (f" · declared holds {declared_holds}" if declared_holds else ''),
             f"- freezes: {report['freezes'] or 'none'} · cut checks: {report['cuts'] or 'none'}",
             f"- placement: {coverage_stats.get('sampled', 0)} frames sampled · " + (', '.join(f"{f['kind']} {f['frames']}/{f['of']} — {f['hint']}" for f in coverage_findings) or 'content fills the format')]
    if a.asr: lines.append('- ASR worst: ' + ', '.join(f"{r['id']} {r['matchRatio']}" for r in report['asr'][:3]) + ' (whisper on a stylised voice is a hint, not a verdict)')
    lines.append(f"- machine problems: {problems}. Human viewing still required for meaning, pacing and sound.\n")
    with (project / 'out/qa.md').open('a', encoding='utf-8') as fh: fh.write('\n'.join(lines) + '\n')
    print(json.dumps(report, ensure_ascii=False, indent=2) if a.json else '\n'.join(lines))
    if hard and not a.advisory: raise SystemExit(1)


if __name__ == '__main__': run_main(main)
