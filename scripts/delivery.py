#!/usr/bin/env python3
"""Final delivery gate; a render is not automatically a publish-ready film.
  delivery.py PROJECT status
  delivery.py PROJECT check [--file 3x4=out/final-3x4.mp4 ...]
  delivery.py PROJECT adopt-master --source out/final-3x4.mp4 --target out/mastered-final-3x4.mp4
Run QA and visual_review on the exact final/mastered file. No synthetic approval and no stale QA.
"""
import argparse,json
from pathlib import Path
from common import read,write,inside,filehash,digest,probe,run_main

def project_fingerprint(project):
    project=Path(project).resolve();paths=[project/f for f in ['content/brief.json','content/script.json','content/film.json','content/alignment.json','content/materials.json','content/sources.json','content/claims.json','content/font-check.json','package-lock.json']]
    paths+=sorted(p for folder in ['src','core'] for p in (project/folder).rglob('*') if p.is_file())
    film=read(project/'content/film.json',{})
    paths += [inside(project/'public',a['src']) for a in film.get('assets',{}).values() if a.get('src')]
    paths += [inside(project/'public',a['src']) for a in film.get('audio',[]) if a.get('src')]
    paths += [inside(project/'public',a['src']) for a in read(project/'content/alignment.json',{}).get('segments',{}).values() if a.get('src')]
    paths += [inside(project,a['textFile']) for a in read(project/'content/sources.json',[]) if a.get('textFile')]
    return digest({str(p.relative_to(project)):filehash(p) for p in paths if p.is_file()})

def delivery_errors(project,files=None):
    from validate import validate
    from review import ensure_script,ensure_opening
    project=Path(project);errors=[];artifacts=[]
    try:validate(project,False,stage='final');ensure_script(project);ensure_opening(project)
    except (ValueError,KeyError,FileNotFoundError) as e:errors.append(str(e))
    brief=read(project/'content/brief.json');t=read(project/'content/timeline.json',{})
    formats=brief.get('formats',['3x4','9x16','16x9']);mapping=files or {}
    if set(mapping)-set(formats):errors.append('Unexpected format in supplied file mapping')
    for fmt in formats:
        path_str=mapping.get(fmt,f'out/final-{fmt}.mp4')
        try:
            path=inside(project,path_str);sha=filehash(path);meta=read(path.with_suffix('.render.json'))
            if meta.get('stage')!='final' or meta.get('sha256')!=sha:raise ValueError('Missing or stale final render receipt')
            guard=meta.get('layoutGuard',{})
            if not guard.get('strict') or guard.get('inputSha256')!=sha or guard.get('checkedFrames')!=t.get('durationFrames'):raise ValueError('Final has missing/stale/incomplete per-frame layout checks')
            if meta.get('projectFingerprint')!=project_fingerprint(project):raise ValueError('Project changed since the final render')
            dims=t.get('formats',{}).get(fmt,{});v=next(s for s in probe(path)['streams'] if s['codec_type']=='video')
            if [v['width'],v['height']] != [dims.get('width'),dims.get('height')]:raise ValueError('Final is not full composition resolution')
            report=read(project/f'out/qa/report-{fmt}.json')
            if report.get('inputSha256')!=sha or report.get('ok') is not True:raise ValueError('Machine QA is missing, stale or failed')
            review=read(project/f'out/qa/visual-review-{fmt}.json')
            if review.get('inputSha256')!=sha:raise ValueError('Actual visual/audio review is missing or stale')
            if not review.get('frames') or not review.get('fullPlayback',{}).get('reviewed'):raise ValueError('Incomplete final viewing receipt')
            artifacts.append({'format':fmt,'path':path_str,'sha256':sha})
        except (ValueError,KeyError,FileNotFoundError,StopIteration) as e:errors.append(fmt+': '+str(e))
    return errors,artifacts

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('project',type=Path);sub=p.add_subparsers(dest='cmd',required=True)
    for cmd in ['status','check']:
        q=sub.add_parser(cmd);q.add_argument('--file',action='append',default=[])
    q=sub.add_parser('adopt-master');q.add_argument('--source',required=True);q.add_argument('--target',required=True)
    a=p.parse_args();project=a.project.resolve()
    if a.cmd=='adopt-master':
        from review import decoded_signature
        source=inside(project,a.source);target=inside(project,a.target);meta=read(source.with_suffix('.render.json'))
        if meta.get('sha256')!=filehash(source) or meta.get('projectFingerprint')!=project_fingerprint(project):raise ValueError('Source render is stale')
        before,after=decoded_signature(source),decoded_signature(target)
        if any(before[k]!=after[k] for k in ['size','frames','count']):raise ValueError('Mastering changed picture frames; re-render instead of inheriting layout checks')
        target_sha=filehash(target)
        guard=meta.get('layoutGuard',{})
        if not guard.get('strict') or guard.get('inputSha256')!=filehash(source):raise ValueError('Source layout checks are missing/stale')
        guard.update(inputSha256=target_sha,carriedFromSourceSha256=filehash(source),carryBasis='decoded picture signature equality; new audio still unreviewed')
        meta.update(sha256=target_sha,masteredFrom=a.source,requiresFreshAudioAndVisualReview=True)
        write(target.with_suffix('.render.json'),meta);print('Picture unchanged. Run fresh qa.py, visual_review.py and delivery.py on the mastered target.');return
    mapping={}
    for item in a.file:
        if '=' not in item:raise ValueError('--file must be FORMAT=project-relative-path')
        fmt,path=item.split('=',1);mapping[fmt]=path
    errors,artifacts=delivery_errors(project,mapping)
    result={'ready':not errors,'errors':errors,'artifacts':artifacts,'scope':'Video readiness only; also check covers, publishing copy and reuse rights separately'}
    write(project/'out/delivery.json',result);print(json.dumps(result,ensure_ascii=False,indent=2))
    if errors and a.cmd=='check':raise SystemExit(1)
if __name__=='__main__':run_main(main)
