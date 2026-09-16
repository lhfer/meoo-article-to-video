#!/usr/bin/env python3
"""Render explicit stages; normal previews/finals respect the two user review gates."""
import argparse, json, re, subprocess, time, os, shutil
from pathlib import Path
from common import read, write, filehash, ensure_script, probe, run_main
from review import ensure_opening, opening_hash, opening_seconds
from validate import validate

WEBGL_PARTS=re.compile(r"<(LightLeak|Starburst)\b|@remotion/effects")
IMPORT_RE=re.compile(r"(?:from\s*|import\s*\(?)[\"'](\.[^\"']+)[\"']")
def webgl_shot_files(project):
    """Shot files the film actually schedules (film.shots[].component via film.components) plus their local non-kit imports, that mount a WebGL2 part.
    The kit barrel always contains fx.tsx, so only the shots' own source counts; a shipped but unscheduled reference shot never triggers the GPU path."""
    film=read(project/'content/film.json',{});comps=film.get('components') or {};src=(project/'src').resolve()
    starts=[src/comps[s['component']] for s in film.get('shots',[]) if s.get('component') in comps]
    seen=set();hits=[]
    def walk(path):
        path=path.resolve()
        if path in seen or not path.is_file() or not path.is_relative_to(src) or 'kit' in path.relative_to(src).parts:return
        seen.add(path);text=path.read_text(encoding='utf-8')
        if WEBGL_PARTS.search(text):hits.append(str(path.relative_to(src)))
        for ref in IMPORT_RE.findall(text):
            cand=(path.parent/ref)
            for x in [cand]+[Path(str(cand)+ext) for ext in ('.tsx','.ts','.js','.jsx')]+[cand/'index.tsx',cand/'index.ts']:
                if x.is_file():walk(x);break
    for s in starts:walk(s)
    return sorted(set(hits))

def gl_backend(project,brief):
    """WebGL2 effects (kit LightLeak / Starburst) need a GL backend in Remotion 4 ('angle' on a desktop, 'swangle' without a GPU).
    Projects whose scheduled shots use none keep the exact default command, so their approved openings still carry over byte-identical."""
    cfg=(brief.get('render') or {}).get('gl')
    if cfg in ('default','none',False):return None
    if cfg:return cfg
    return 'angle' if webgl_shot_files(project) else None

def gl_flags(gl):
    """GPU backends dither by ±1–2 levels between identical renders; lossless PNG intermediates keep that within ±3 after H.264 (JPEG intermediates amplify it to 20–40), which is what review.py carry-opening tolerates."""
    return [f'--gl={gl}','--image-format=png'] if gl else []

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('project',type=Path);p.add_argument('--stage',choices=['draft','opening','preview','final'],required=True);p.add_argument('--format',help='3x4 | 9x16 | 16x9 | all (default: the primary format for opening, all otherwise)');p.add_argument('--scale',type=float);p.add_argument('--dry-voice',action='store_true',help='干声版: same picture and narration, no film.audio beds (for adding a platform BGM in-app); writes <stage>-<fmt>-dry.mp4');a=p.parse_args()
    project=a.project.resolve();draft=a.stage=='draft'
    subprocess.run(['node','core/build.mjs']+(['--draft']if draft else []),cwd=project,check=True)
    result=validate(project,draft,stage=a.stage);t=read(project/'content/timeline.json')
    for w in result.get('warnings',[]):print('warning: '+w)
    if not draft:
        ensure_script(project)
        from fonts import ensure_font
        ensure_font(project)
    if a.stage in ['preview','final']:
        if t['scope']!='full':raise ValueError('Complete the full film and use scope=full before full preview/final')
        ensure_opening(project)
    scale=a.scale if a.scale is not None else (1 if a.stage=='final' else .5)
    if scale<=0 or scale>2:raise ValueError('scale must be >0 and <=2')
    primary=t.get('primaryFormat','3x4')
    gl=gl_backend(project,read(project/'content/brief.json'))
    if gl:print(f'gl: {gl} + png intermediates (WebGL2 effects in the scheduled shots; brief.render.gl = "swangle" on a machine without a GPU, "default" to force the plain renderer)')
    requested=a.format or (primary if a.stage=='opening' else 'all')
    formats=list(t['formats']) if requested=='all' else [requested]
    for fmt in formats:
        if fmt not in t['formats']:raise ValueError(f"Format {fmt} is not in film.formats {sorted(t['formats'])}")
    frames_total=t['durationFrames'];opening_frames=min(frames_total,t['fps']*opening_seconds(project))
    for fmt in formats:
        dims=t['formats'][fmt]
        if any(abs(dims[k]*scale-round(dims[k]*scale))>1e-8 or round(dims[k]*scale)%2 for k in ['width','height']):raise ValueError('H.264 scale must produce even integer dimensions')
        output=project/f"out/{a.stage}-{fmt}{'-dry' if a.dry_voice else ''}.mp4";output.parent.mkdir(exist_ok=True)
        # Preserve earlier renders, including approved samples, for comparisons.
        if output.exists():
            archive=output.parent/'versions';archive.mkdir(exist_ok=True)
            output.replace(archive/f'{output.stem}-{time.time_ns()}.mp4')
        frames=opening_frames if a.stage=='opening' else frames_total
        config=project/f'work/render-{fmt}.json'
        config.parent.mkdir(parents=True,exist_ok=True)
        render_options=read(project/'content/brief.json').get('render') or {}
        write(config,{'format':fmt,'output':str(output),'frames':frames,'scale':scale,'noMusic':a.dry_voice,'gl':gl,
                      'browserExecutable':render_options.get('browserExecutable') or os.getenv('CHROMIUM_PATH') or shutil.which('chromium') or shutil.which('chromium-browser'),
                      'concurrency':render_options.get('concurrency')})
        subprocess.run(['node','core/render-checked.mjs',str(config)],cwd=project,check=True)
        layout_receipt=read(output.with_suffix('.layout.json'))
        if layout_receipt.get('inputSha256')!=filehash(output) or not layout_receipt.get('strict') or layout_receipt.get('checkedFrames')!=frames:
            raise ValueError('Missing or incomplete per-rendered-frame layout receipt')
        info=probe(output);video=next(x for x in info['streams'] if x['codec_type']=='video')
        expected=[round(dims['width']*scale),round(dims['height']*scale)]
        if [video['width'],video['height']]!=expected:raise ValueError('Rendered dimensions differ from composition')
        if abs(float(info['format']['duration'])-frames/t['fps'])>.12:raise ValueError('Rendered duration differs from timeline')
        audible=any(v['from']<frames and v['real'] for v in t['voices']) or (not a.dry_voice and any(v['from']<frames for v in t['audio']))
        if audible and not any(x['codec_type']=='audio' for x in info['streams']):raise ValueError('Expected audio stream is missing')
        meta={'stage':a.stage,'format':fmt,'width':video['width'],'height':video['height'],'frames':frames,'fps':t['fps'],'sha256':filehash(output),'dryVoice':a.dry_voice,'layoutGuard':layout_receipt,'projectFingerprint':__import__('delivery').project_fingerprint(project)}
        if a.stage=='opening' and fmt==primary and not a.dry_voice:meta['openingDigest']=opening_hash(project)
        write(output.with_suffix('.render.json'),meta);print(output)
        # Retention check on the actual pixels: a stretch with no visible change is where viewers leave. Warn at draft/opening, block preview/final under pacing.enforce.
        import qa
        qa.configure_layout(project)
        pacing=read(project/'content/brief.json').get('pacing') or {};max_gap=pacing.get('visualChangeMaxSeconds',1.5)
        still,stats=qa.still_stretches(output,max_gap,fmt);still,declared=qa.split_holds(still,t)
        if declared:print(f"{fmt}: {len(declared)} declared hold(s) not counted (film.shots[].hold): "+', '.join(f"{d['shot']} {d['fromSeconds']}–{d['toSeconds']}s" for d in declared))
        if still:
            msg=f"{fmt}: {len(still)} still stretch(es) over {max_gap}s (longest {stats['longestStillSeconds']}s: "+', '.join(f"{g['fromSeconds']}–{g['toSeconds']}s" for g in still[:4])+") — add motion there (kit KenBurns / ListReveal / cursor / counter), cut sooner, or declare film.shots[].hold for evidence the eye follows"
            if a.stage in('preview','final') and pacing.get('enforce'):raise ValueError(msg)
            print('warning: '+msg)

if __name__=='__main__':run_main(main)
