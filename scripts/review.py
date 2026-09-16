#!/usr/bin/env python3
"""Record actual script/opening approvals, and detect changes to reviewed material."""
import argparse, json, re, subprocess, hashlib
from datetime import datetime, timezone
from pathlib import Path
from common import read, write, filehash, digest, script_hash, ensure_script, inside, run_main, probe

def opening_seconds(project):
    """Seconds covered by the opening approval; brief.review.openingSeconds, default 10."""
    return int((read(Path(project)/'content/brief.json',{}).get('review') or {}).get('openingSeconds',10) or 10)

def primary_format(project,t=None):
    t=t or read(Path(project)/'content/timeline.json');return t.get('primaryFormat','3x4')

def opening_artifact(project):
    return f'out/opening-{primary_format(project)}.mp4'

def opening_material(project):
    project=Path(project);t=read(project/'content/timeline.json');film=read(project/'content/film.json');limit=min(opening_seconds(project)*t['fps'],t['durationFrames']);primary=primary_format(project,t)
    shots=[{**s,'layouts':{primary:s['layouts'][primary]}} for s in t['shots'] if s['from']<limit]
    files={};cue_names=set();assets=set(t.get('globalAssets',[]))
    def add_code(path):
        path=path.resolve();key=str(path.relative_to(project.resolve()))
        if key in ['src/registry.generated.ts','content/timeline.json']:return
        if key in files:return
        files[key]=filehash(path)
        if path.suffix not in ['.tsx','.ts','.js','.jsx','.css','.mjs']:return
        text=path.read_text(encoding='utf-8')
        cue_names.update(re.findall(r"cue\(['\"]([^'\"]+)['\"]\)",text))
        for ref in re.findall(r"(?:from\s*|import\s*\(?)[\"'](\.[^\"']+)[\"']",text):
            candidate=(path.parent/ref).resolve()
            if not candidate.is_relative_to(project.resolve()):raise ValueError('Local import escapes project: '+ref)
            choices=[candidate]+[Path(str(candidate)+x) for x in ['.tsx','.ts','.js','.jsx','.json','.css']]+[candidate/'index.tsx',candidate/'index.ts']
            found=next((x for x in choices if x.is_file()),None)
            if found:add_code(found)
    # Shared composition/render logic affects the opening, while adding independent later shots does not.
    for path in (project/'src').iterdir():
        if path.is_file() and path.name!='registry.generated.ts':
            add_code(path)
    for shot in shots:
        add_code(inside(project/'src',film['components'][shot['component']]))
        assets.update(shot.get('assets',[]))
    voices=[v for v in t['voices'] if v['from']<limit]
    audio=[v for v in t['audio'] if v['from']<limit]
    for v in voices+audio:files['public/'+v['src']]=filehash(inside(project/'public',v['src']))
    for id in assets:
        src=t['assets'][id]['src'];files['public/'+src]=filehash(inside(project/'public',src))
    capstyle=dict(t['captionStyle'])
    if 'layouts' in capstyle:capstyle['layouts']={primary:capstyle['layouts'].get(primary,{})}
    return {'fps':t['fps'],'frames':limit,'style':t['style'],'shots':shots,'voices':voices,'audio':audio,'captions':[c for c in t['captions'] if c['from']<limit],'captionStyle':capstyle,'events':{k:v for k,v in t['events'].items() if v<limit or k in cue_names},'files':files}

def opening_hash(project):return digest(opening_material(project))

def ensure_opening(project):
    ensure_script(project);r=read(Path(project)/'content/reviews.json',{}).get('opening',{})
    if r.get('digest')!=opening_hash(project):raise ValueError('The current first 10 seconds need user approval (or changed since approval).')
    artifact=inside(project,r['artifact'])
    if r.get('artifactSha256')!=filehash(artifact):raise ValueError('The approved opening artifact changed. Preserve it and re-record the actual review.')

# GPU render backends (--gl=angle / swangle, needed for WebGL2 effects) dither gradients non-deterministically: identical renders differ by ±1–2
# levels on a few frames (measured 2026-09-11: max 2 over 4 × 300 raw frames, both backends; the default backend is byte-exact). render.py pairs
# a GPU backend with lossless PNG intermediates, so the decoded H.264 difference stays ≤ 3 (JPEG intermediates amplified it to 26–38 at text
# edges). A re-rendered opening within this band, with identical audio, size and frame count, is still the sample the user saw.
GL_DITHER_TOLERANCE=4

def decoded_signature(path):
    info=probe(path);v=next(s for s in info['streams'] if s['codec_type']=='video')
    frames=subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-map','0:v:0','-an','-f','framemd5','-'])
    result={'size':[v['width'],v['height']],'frames':hashlib.sha256(frames).hexdigest(),'count':sum(1 for l in frames.splitlines() if l and not l.startswith(b'#')),'audio':None}
    if any(s['codec_type']=='audio' for s in info['streams']):
        audio=subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-map','0:a:0','-vn','-ac','2','-ar','48000','-f','s16le','-'])
        result['audio']=hashlib.sha256(audio).hexdigest()
    return result

def max_frame_difference(a,b):
    """Largest per-pixel difference (any plane, 8-bit levels) between two decoded videos of equal size and length; ffmpeg does the work."""
    out=subprocess.run(['ffmpeg','-v','error','-i',str(a),'-i',str(b),'-filter_complex','[0:v][1:v]blend=all_mode=difference,signalstats,metadata=mode=print:file=-','-f','null','-'],capture_output=True,text=True,check=True).stdout
    values=[int(m) for m in re.findall(r'lavfi\.signalstats\.[YUV]MAX=(\d+)',out)]
    if not values:raise ValueError('Could not compare decoded frames')
    return max(values)

def carry_verdict(same_signature,size_and_count_match,audio_match,max_diff,gl):
    """Pure decision: identical decodes always carry; under a GPU backend, frames within GL_DITHER_TOLERANCE with identical audio carry too."""
    if same_signature:return True,'Identical decoded frames and audio; original user evidence preserved'
    if gl and size_and_count_match and audio_match and max_diff is not None and max_diff<=GL_DITHER_TOLERANCE:
        return True,f'Decoded frames within ±{max_diff} levels (GPU render dithering under --gl={gl}, tolerance ±{GL_DITHER_TOLERANCE}) and identical audio; original user evidence preserved'
    return False,'Opening picture or audio changed: show the new sample to the user for approval'

def carry_opening(project):
    ensure_script(project);project=Path(project);reviews=read(project/'content/reviews.json');prior=reviews.get('opening')
    if not prior:raise ValueError('An actual prior opening approval is required')
    current=project/opening_artifact(project);meta=read(current.with_suffix('.render.json'))
    if meta.get('openingDigest')!=opening_hash(project) or meta.get('sha256')!=filehash(current):raise ValueError('Render the current opening first')
    candidates=[current]+list((project/'out/versions').glob(f'{current.stem}-*.mp4'))
    original=next((p for p in candidates if filehash(p)==prior.get('artifactSha256')),None)
    if original is None:raise ValueError('The original approved sample is missing')
    so,sc=decoded_signature(original),decoded_signature(current);same=so==sc
    from render import gl_backend  # local import: render.py imports this module
    gl=None if same else gl_backend(project,read(project/'content/brief.json'))
    shape=so['size']==sc['size'] and so['count']==sc['count'];audio=so['audio']==sc['audio']
    diff=max_frame_difference(original,current) if (gl and shape and audio) else None
    ok,note=carry_verdict(same,shape,audio,diff,gl)
    if not ok:raise ValueError(note)
    reviews.setdefault('history',[]).append({'stage':'opening',**prior})
    reviews['opening']={**prior,'digest':opening_hash(project),'artifact':opening_artifact(project),'artifactSha256':filehash(current),'carriedBy':note}
    write(project/'content/reviews.json',reviews);return note

def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='cmd',required=True)
    q=sub.add_parser('approve');q.add_argument('project',type=Path);q.add_argument('stage',choices=['script','opening']);q.add_argument('--evidence',required=True)
    q=sub.add_parser('status');q.add_argument('project',type=Path)
    q=sub.add_parser('carry-opening',help='Retain a prior approval only when the newly rendered opening is audiovisually identical');q.add_argument('project',type=Path)
    a=p.parse_args();project=a.project.resolve();reviews=read(project/'content/reviews.json',{})
    if a.cmd=='carry-opening':print('Prior user approval retained: '+carry_opening(project));return
    if a.cmd=='status':
        result={}
        for stage,fn in [('script',ensure_script),('opening',ensure_opening)]:
            try:fn(project);result[stage]='current'
            except (ValueError,KeyError,FileNotFoundError) as e:result[stage]=str(e)
        print(json.dumps(result,ensure_ascii=False,indent=2));return
    if not a.evidence.strip():raise ValueError('Record the actual user reply or its conversation location')
    record={'evidence':a.evidence,'approvedAt':datetime.now(timezone.utc).isoformat()}
    if a.stage=='script':record['digest']=script_hash(project)
    else:
        ensure_script(project)
        t=read(project/'content/timeline.json')
        if t['draft']:raise ValueError('A technical draft is not an approval sample')
        artifact=project/opening_artifact(project);meta=read(artifact.with_suffix('.render.json'))
        if meta.get('openingDigest')!=opening_hash(project) or meta.get('sha256')!=filehash(artifact):raise ValueError('Opening sample is stale or not rendered by render.py')
        record.update(digest=opening_hash(project),artifact=opening_artifact(project),artifactSha256=filehash(artifact))
    previous=reviews.get(a.stage)
    if previous:reviews.setdefault('history',[]).append({'stage':a.stage,**previous})
    reviews[a.stage]=record;write(project/'content/reviews.json',reviews);print(a.stage+' approval recorded. This records the supplied user evidence, not an AI quality score.')

if __name__=='__main__':run_main(main)
