#!/usr/bin/env python3
"""Music: analyze hits/tempo, fit a hit to a word event, ingest tracks, list a local library, or plan a host-tool generation.

  music.py analyze <project> --input <file|assetId> [--id bgm]
  music.py ingest  <project> --id bgm --input <file> [--no-analyze]
  music.py fit     <project> --id bgm --hit bgm.hit_1 --to <eventName|seconds> [--start 0] [--end <event|seconds>] [--gain .55] [--duck .45] [--fade-in .2] [--fade-out 1.5] [--allow-lead]
  music.py library <project> [--dir DIR] [--json]
  music.py plan    <project> --id bgm [--archetype KEY] [--candidates 3] [--extra "…"] [--provider host] [--list-archetypes]
  music.py rank    <project> --inputs a.wav b.wav … [--archetype KEY] [--json]      # score generated / library candidates for short-video use
  music.py grid    <project> --id bgm [--downbeat bgm.hit_N] [--beats]              # after fit: bar (or beat) events for 卡点 cuts
Hits become numeric film.events (bgm.hit_N) so shots can cue() them and qa.py can check cut alignment.
plan derives the BGM 调性 from brief.music.archetype → content/product.json (tone / category / audience) → script → profile default.
"""
import argparse, json, shutil, subprocess, sys, time
from pathlib import Path
from common import ROOT, read, write, ident, inside, filehash, duration, run_main
import music_tone

AUDIO_EXT = {'.mp3', '.wav', '.m4a', '.aac', '.flac', '.ogg', '.aif', '.aiff'}


def solve_trim(hit_seconds, target_film_seconds):
    """(trimStart, musicAt): trim the track so the hit lands at the film time; negative trims become a delayed start."""
    trim = hit_seconds - target_film_seconds
    return (round(trim, 3), 0.0) if trim >= 0 else (0.0, round(-trim, 3))


def analyze_file(path, max_hits=40):
    cmd = ['uv', 'run', '--with', 'numpy', '--with', 'scipy', 'python3', str(ROOT / 'scripts/_music_analyze.py'), str(path), '--max-hits', str(max_hits)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0: raise ValueError('music analysis failed (needs uv + ffmpeg): ' + r.stderr[-400:])
    return json.loads(r.stdout.strip().splitlines()[-1])


def resolve_input(project, value):
    film = read(project / 'content/film.json'); asset = film.get('assets', {}).get(value)
    if asset: return inside(project / 'public', asset['src']), value
    p = Path(value).expanduser().resolve()
    if not p.is_file(): raise ValueError('Input file or asset id not found: ' + value)
    return p, None


def locate(timeline, seconds):
    fps = timeline['fps']; f = seconds * fps
    for v in timeline['voices']:
        if v['from'] <= f <= v['from'] + v['durationFrames']:
            rel = (f - v['from']) / fps * 1000; words = v.get('words') or []
            if not words: return f"{v['id']} @{rel / 1000:.2f}s"
            j = min(range(len(words)), key=lambda i: abs(words[i]['startMs'] - rel))
            return f"{v['id']} @{rel / 1000:.2f}s 「{''.join(w['text'] for w in words[max(0, j - 3):j + 4])}」"
    return 'gap/tail'


def cmd_analyze(a):
    project = a.project.resolve(); path, asset_id = resolve_input(project, a.input); id = ident(a.id or asset_id or 'bgm')
    result = analyze_file(path, a.max_hits)
    music = read(project / 'content/music.json', {'version': 1, 'tracks': {}}); music['tracks'][id] = {**result, 'assetId': asset_id, 'analyzedAt': time.strftime('%Y-%m-%dT%H:%M:%S')}
    write(project / 'content/music.json', music)
    print(json.dumps({'id': id, 'durationSeconds': result['durationSeconds'], 'tempoEstimatesBpm': result['tempoEstimatesBpm'], 'barSeconds': result['barSeconds'], 'hits': [(h['id'], h['seconds']) for h in result['hits'][:12]], 'note': result['note']}, ensure_ascii=False, indent=2))


def cmd_ingest(a):
    project = a.project.resolve(); id = ident(a.id); src = Path(a.input).expanduser().resolve()
    if not src.is_file() or src.suffix.lower() not in AUDIO_EXT: raise ValueError('Provide an existing audio file')
    stamp = str(time.time_ns()); rel = f'bgm/{id}-{stamp}.wav'; out = inside(project / 'public', rel); out.parent.mkdir(parents=True, exist_ok=True)
    # One editing format for every track: 48 kHz stereo PCM; the original is kept beside it for provenance.
    shutil.copy2(src, out.parent / f'{id}-{stamp}-original{src.suffix.lower()}')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(src), '-vn', '-ar', '48000', '-ac', '2', '-c:a', 'pcm_s16le', str(out)], check=True)
    film = read(project / 'content/film.json'); film.setdefault('assets', {})[id] = {'src': rel, 'sha256': filehash(out), 'kind': 'audio', 'provider': a.provider or 'ingest', 'origin': str(src), 'createdAtNs': stamp, 'durationSeconds': round(duration(out), 3)}
    write(project / 'content/film.json', film); print(f'{id}: {rel} ({film["assets"][id]["durationSeconds"]}s)')
    if not a.no_analyze:
        a.input = id; a.max_hits = 40; cmd_analyze(a)


def time_value(project, value, timeline=None):
    try: return float(value)
    except ValueError: pass
    t = timeline or read(project / 'content/timeline.json')
    if value not in t['events']: raise ValueError(f'Unknown event {value}; compile first or pass seconds')
    return t['events'][value] / t['fps']


def cmd_fit(a):
    project = a.project.resolve(); id = ident(a.id); film = read(project / 'content/film.json'); music = read(project / 'content/music.json', {'tracks': {}})
    track = music['tracks'].get(id)
    if not track: raise ValueError(f'Analyze {id} first (music.py analyze)')
    asset = film.get('assets', {}).get(id)
    if not asset: raise ValueError(f'{id} is not a registered film asset; use music.py ingest')
    timeline = read(project / 'content/timeline.json', None)
    hit = next((h for h in track['hits'] if h['id'] == a.hit), None)
    if not hit: raise ValueError(f"Unknown hit {a.hit}; available: {[h['id'] for h in track['hits'][:10]]}…")
    target = time_value(project, a.to, timeline)
    trim, music_at = solve_trim(hit['seconds'], target)
    if music_at > a.max_lead and not a.allow_lead: raise ValueError(f'Fitting needs {music_at:.2f}s of silence before the music; pick an earlier hit or pass --allow-lead')
    start = max(music_at, float(a.start)); trim += max(0.0, start - music_at)
    end = a.end if a.end is not None else (timeline['durationFrames'] / timeline['fps'] if timeline else None)
    end_value = time_value(project, str(end), timeline) if end is not None and not isinstance(end, float) else end
    if end_value is None: raise ValueError('Provide --end or compile the film first')
    available = track['durationSeconds'] - trim
    if end_value - start > available + 0.05: raise ValueError(f'Track too short after trim: {available:.1f}s available, {end_value - start:.1f}s needed')
    entry = {'src': asset['src'], 'start': round(start, 3), 'end': round(end_value, 3), 'gain': a.gain, 'trimStart': round(trim, 3), 'fadeIn': a.fade_in, 'fadeOut': a.fade_out, 'duck': a.duck, 'fitHit': a.hit, 'fitTo': a.to}
    audio = [x for x in film.get('audio', []) if x.get('src') != asset['src']] + [entry]; film['audio'] = audio
    events = film.setdefault('events', {}); anchors = []
    for h in track['hits']:
        film_seconds = h['seconds'] - trim + start
        if film_seconds < start - 0.01 or film_seconds > end_value: continue
        events[h['id']] = round(film_seconds, 3); anchors.append({'id': h['id'], 'music': h['seconds'], 'film': round(film_seconds, 3), 'where': locate(timeline, film_seconds) if timeline else '?'})
    write(project / 'content/film.json', film)
    lines = ['# BGM 锚点（music.py fit 自动生成）', '', f"轨道 {id}：trimStart {trim:.3f}s，起点 {start:.3f}s，终点 {end_value:.3f}s，{a.hit} 对位到 {a.to}（片内 {target:.3f}s）", '', '| 事件 | 音乐秒 | 片内秒 | 落在 |', '|---|---:|---:|---|'] + [f"| {x['id']} | {x['music']} | {x['film']} | {x['where']} |" for x in anchors]
    (project / 'out').mkdir(exist_ok=True); (project / 'out/music-anchors.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('\n'.join(lines)); print('\nRecompile to resolve events; shots may cue() any bgm.hit_N listed above.')


def cmd_library(a):
    folder = Path(a.dir).expanduser() if a.dir else Path.home() / 'Music/bgm'
    rows = []
    for p in sorted(folder.glob('*')) if folder.is_dir() else []:
        if p.suffix.lower() in AUDIO_EXT:
            try: rows.append({'file': str(p), 'seconds': round(duration(p), 1)})
            except Exception: rows.append({'file': str(p), 'seconds': None})
    if a.json: print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        if not rows: print(f'No audio files under {folder}')
        for r in rows: print(f"{r['seconds'] or '?':>7}s  {r['file']}")


def beats_from_timeline(timeline):
    fps = timeline['fps']
    return [{'id': v['id'], 'kind': v.get('kind'), 'start': round(v['from'] / fps, 2), 'end': round((v['from'] + v['durationFrames']) / fps, 2)} for v in timeline['voices']]


def plan_context(project, archetype=None, candidates=None, extra=''):
    brief = read(project / 'content/brief.json'); product = read(project / 'content/product.json', {}); script = read(project / 'content/script.json', {})
    timeline = read(project / 'content/timeline.json', None)
    if timeline:
        beats = beats_from_timeline(timeline); kinds = {b['id']: b.get('kind') for b in script.get('beats', [])}
        for b in beats: b['kind'] = b['kind'] or kinds.get(b['id'])
        total = timeline['durationFrames'] / timeline['fps']
    else: beats, total = None, None
    n = candidates if candidates is not None else (brief.get('music') or {}).get('candidates', 3)
    return music_tone.plan_spec(brief, product, script, beats, total, None, archetype, n, extra), brief


def cmd_plan(a):
    if a.list_archetypes:
        for k, v in music_tone.ARCHETYPES.items(): print(f"{k:9s} {v['zh']:5s} {v['bpm'][0]}–{v['bpm'][1]} BPM  {v['feel']}  ← {v['fits']}")
        return
    project = a.project.resolve(); id = ident(a.id)
    spec, brief = plan_context(project, a.archetype, a.candidates, a.extra or '')
    out = project / 'work/music/host'; out.mkdir(parents=True, exist_ok=True)
    requests = [{'id': f"{id}-{p['id']}", 'model': 'fun-music-v1', 'request': {'prompt': p['prompt'], 'is_instrumental': True, 'format': 'wav'}, 'output': str(out / f"{id}-{p['id']}.wav")} for p in spec['prompts']]
    plan = {'provider': a.provider, 'id': id, **{k: spec[k] for k in ('archetype', 'archetypeZh', 'reasons', 'bpm', 'feel', 'genre', 'structure', 'totalSeconds', 'platforms', 'negatives', 'checks')},
            'requests': requests,
            'verified': {'fun-music-v1': 'prompt 1–2000 字符；不能指定时长（模型自定）；每次调用只出一首，所以 N 个候选 = N 次调用；format mp3|wav；is_instrumental=true 去人声（核对于 2026-09-11 阿里云文档）'},
            'next': f"用宿主音乐工具逐条生成并保存到 output → music.py rank <project> --inputs <files> → music.py ingest --id {id} --input <best> → music.py fit --hit bgm.hit_N --to <event> → music.py grid --id {id}"}
    for p in spec['prompts']: (out / f"{id}-{p['id']}.prompt.txt").write_text(p['prompt'] + '\n', encoding='utf-8')
    write(out / f'{id}-plan.json', plan)
    print(f"BGM 调性：{spec['archetypeZh']}（{spec['archetype']}） {spec['bpm'][0]}–{spec['bpm'][1]} BPM · {spec['feel']}")
    for r in spec['reasons']: print('  依据：' + r)
    print('结构：' + '；'.join(f"{p['at']}s {p['zh']}" for p in spec['structure']))
    for r in requests: print(f"\n[{r['id']}] → {r['output']}\n{r['request']['prompt']}")
    print(f"\n{plan['next']}")


def cmd_rank(a):
    project = a.project.resolve(); spec, brief = plan_context(project, a.archetype, 1)
    bpm = tuple(spec['bpm']); needed = spec['totalSeconds'] + 2
    rows = []
    for f in a.inputs:
        path = Path(f).expanduser().resolve()
        if not path.is_file(): raise ValueError('Not a file: ' + f)
        m = analyze_file(path, 40); score, parts = music_tone.score_candidate(m, bpm, needed)
        rows.append({'file': str(path), 'score': score, 'parts': parts, 'bpm': m['tempoEstimatesBpm'], 'seconds': m['durationSeconds']})
    rows.sort(key=lambda r: -r['score'])
    if a.json: print(json.dumps({'archetype': spec['archetype'], 'bpm': list(bpm), 'neededSeconds': needed, 'rows': rows}, ensure_ascii=False, indent=2)); return
    print(f"目标：{spec['archetypeZh']} {bpm[0]}–{bpm[1]} BPM，需要 ≥ {needed:.0f}s；分项 = 首击 / 速度 / 人声频段 / 时长 / 动态")
    for i, r in enumerate(rows, 1):
        p = r['parts']; print(f"{i}. {r['score']:.3f}  首击 {p['firstHit'][0]}s  BPM {p['tempo'][0] or '-'}({r['bpm'][:2]})  中频 {p['speechBand'][0]}  {p['duration'][0]}s  crest {p['crest'][0]}dB  {Path(r['file']).name}")
    print('分数只看结构指标；人声、淡入、突兀静音必须实际听一遍再选。')


def cmd_grid(a):
    project = a.project.resolve(); id = ident(a.id); film = read(project / 'content/film.json'); music = read(project / 'content/music.json', {'tracks': {}})
    track = music['tracks'].get(id); asset = film.get('assets', {}).get(id)
    if not track or not asset: raise ValueError(f'{id}: analyze/ingest first')
    entry = next((x for x in film.get('audio', []) if x.get('src') == asset['src']), None)
    if not entry: raise ValueError('Run music.py fit first: the grid phase depends on trimStart/start')
    bpm = a.bpm or (track['tempoEstimatesBpm'][0] if track['tempoEstimatesBpm'] else None)
    if not bpm: raise ValueError('No tempo estimate; pass --bpm')
    downbeat = next((h for h in track['hits'] if h['id'] == (a.downbeat or entry.get('fitHit'))), None)
    if not downbeat: raise ValueError('Unknown downbeat hit; pass --downbeat bgm.hit_N')
    events = music_tone.bar_grid(bpm, downbeat['seconds'], entry['trimStart'], entry['start'], entry['end'], beats=a.beats)
    ev = film.setdefault('events', {})
    for k in [k for k in ev if k.startswith('bgm.bar_') or k.startswith('bgm.beat_')]: del ev[k]
    for e in events: ev[e['id']] = e['seconds']
    write(project / 'content/film.json', film)
    print(f"{len(events)} {'beat' if a.beats else 'bar'} events at {bpm} BPM from {downbeat['id']} (phase {downbeat['seconds']}s, trim {entry['trimStart']}s); recompile, then snap cuts with shot.anchor = 'bgm.bar_N'.")
    print('Tempo may be a ½× / 2× reading: check that bar_2 / bar_3 land on audible downbeats before cutting to them.')


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter); sub = p.add_subparsers(dest='cmd', required=True)
    q = sub.add_parser('analyze'); q.add_argument('project', type=Path); q.add_argument('--input', required=True); q.add_argument('--id'); q.add_argument('--max-hits', type=int, default=40); q.set_defaults(fn=cmd_analyze)
    q = sub.add_parser('ingest'); q.add_argument('project', type=Path); q.add_argument('--id', required=True); q.add_argument('--input', required=True); q.add_argument('--provider'); q.add_argument('--no-analyze', action='store_true'); q.set_defaults(fn=cmd_ingest)
    q = sub.add_parser('fit'); q.add_argument('project', type=Path); q.add_argument('--id', required=True); q.add_argument('--hit', required=True); q.add_argument('--to', required=True); q.add_argument('--start', default='0'); q.add_argument('--end'); q.add_argument('--gain', type=float, default=0.55); q.add_argument('--duck', type=float, default=0.45); q.add_argument('--fade-in', type=float, default=0.2); q.add_argument('--fade-out', type=float, default=1.5); q.add_argument('--allow-lead', action='store_true'); q.add_argument('--max-lead', type=float, default=0.5); q.set_defaults(fn=cmd_fit)
    q = sub.add_parser('library'); q.add_argument('project', type=Path, nargs='?'); q.add_argument('--dir'); q.add_argument('--json', action='store_true'); q.set_defaults(fn=cmd_library)
    q = sub.add_parser('plan'); q.add_argument('project', type=Path); q.add_argument('--id', default='bgm'); q.add_argument('--archetype', choices=sorted(music_tone.ARCHETYPES)); q.add_argument('--candidates', type=int); q.add_argument('--extra', help='one extra line appended to every prompt'); q.add_argument('--provider', default='host'); q.add_argument('--list-archetypes', action='store_true'); q.set_defaults(fn=cmd_plan)
    q = sub.add_parser('rank'); q.add_argument('project', type=Path); q.add_argument('--inputs', nargs='+', required=True); q.add_argument('--archetype', choices=sorted(music_tone.ARCHETYPES)); q.add_argument('--json', action='store_true'); q.set_defaults(fn=cmd_rank)
    q = sub.add_parser('grid'); q.add_argument('project', type=Path); q.add_argument('--id', default='bgm'); q.add_argument('--downbeat'); q.add_argument('--bpm', type=float); q.add_argument('--beats', action='store_true'); q.set_defaults(fn=cmd_grid)
    a = p.parse_args(); a.fn(a)


if __name__ == '__main__': run_main(main)
