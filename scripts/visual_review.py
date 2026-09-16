#!/usr/bin/env python3
"""Extract full-resolution critical frames; record an ACTUAL visual/audio review separately.
  visual_review.py PROJECT extract --input out/final-3x4.mp4 --format 3x4
  visual_review.py PROJECT record --input out/final-3x4.mp4 --format 3x4 --review work/review-3x4.json
The generated review template starts NOT reviewed. Open the returned images with the host vision tool and listen before filling it.
"""
import argparse,json,subprocess
from pathlib import Path
from common import read,write,filehash,inside,probe,run_main

def critical_frames(timeline,total,fps):
    frames={0,max(0,total-1)}
    for shot in timeline.get('shots',[]):
        a=int(shot['from']);b=min(int(shot['end']),total)
        if a>=total:continue
        for n in [a,a+1,a+int(.25*fps),a+int(.55*fps),(a+b)//2,b-1]:frames.add(max(a,min(b-1,n)))
        for n in shot.get('props',{}).get('qaFrames',[]):frames.add(a+int(n))
    for at in timeline.get('events',{}).values():
        for delta in [0,1,8,16]:frames.add(int(at)+delta)
    for c in timeline.get('captions',[]):
        frames.update([int(c['from']),max(int(c['from']),int(c['end'])-1)])
    return sorted(n for n in frames if 0<=n<total)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('project',type=Path);sub=p.add_subparsers(dest='cmd',required=True)
    for cmd in ['extract','record']:
        q=sub.add_parser(cmd);q.add_argument('--input',required=True);q.add_argument('--format',choices=['3x4','9x16','16x9'],required=True)
        if cmd=='record':q.add_argument('--review',required=True)
    a=p.parse_args();project=a.project.resolve();video=inside(project,a.input);sha=filehash(video)
    folder=project/'out/qa'/f'frames-{a.format}-{sha[:12]}';manifest=folder/'manifest.json'
    if a.cmd=='extract':
        info=probe(video);v=next(x for x in info['streams'] if x['codec_type']=='video')
        n,d=map(float,v['avg_frame_rate'].split('/'));fps=n/d
        total=int(v.get('nb_frames') or round(float(info['format']['duration'])*fps))
        frames=critical_frames(read(project/'content/timeline.json'),total,fps);folder.mkdir(parents=True,exist_ok=True)
        expression='+'.join(f'eq(n,{n})' for n in frames)
        subprocess.run(['ffmpeg','-v','error','-y','-i',str(video),'-vf',f"select='{expression}'",'-vsync','0',str(folder/'frame-%06d.png')],check=True)
        images=sorted(folder.glob('frame-*.png'))
        if len(images)!=len(frames):raise ValueError('Critical-frame extraction count mismatch; do not claim complete inspection')
        rows=[{'frame':n,'seconds':round(n/fps,3),'path':str(path.relative_to(project)),'sha256':filehash(path)} for n,path in zip(frames,images)]
        write(manifest,{'input':a.input,'inputSha256':sha,'format':a.format,'resolution':[v['width'],v['height']],'frames':rows,'scope':'critical samples, not every frame; DOM guard runs on each rendered frame'})
        template={'inputSha256':sha,'frames':[{'frame':r['frame'],'path':r['path'],'reviewed':False,'toolRef':'','observations':'','unresolved':[]} for r in rows],
                  'audio':{'reviewed':False,'toolRef':'','observations':''},'fullPlayback':{'reviewed':False,'toolRef':'','observations':''}}
        path=project/'work'/f'review-{a.format}.json'
        if path.exists():path=project/'work'/f'review-{a.format}-{sha[:12]}.json'
        if not path.exists():write(path,template)
        print(json.dumps({'manifest':str(manifest),'reviewTemplate':str(path),'count':len(rows),'next':'Actually inspect the images and full playback; do not auto-fill reviewed=true'},ensure_ascii=False));return
    data=read(inside(project,a.review));mf=read(manifest)
    if data.get('inputSha256')!=sha or mf['inputSha256']!=sha:raise ValueError('Review is for a different video')
    seen={r['frame']:r for r in data.get('frames',[])}
    for r in mf['frames']:
        row=seen.get(r['frame'],{})
        if filehash(inside(project,r['path']))!=r['sha256']:raise ValueError('Review screenshot changed')
        if row.get('path')!=r['path'] or row.get('reviewed') is not True or not row.get('toolRef','').strip() or not row.get('observations','').strip() or row.get('unresolved',[]):
            raise ValueError('Missing/incomplete review or unresolved issue at frame '+str(r['frame']))
    info=probe(video);needs_audio=any(s['codec_type']=='audio' for s in info['streams'])
    for key in ['fullPlayback']+(['audio'] if needs_audio else []):
        row=data.get(key,{})
        if row.get('reviewed') is not True or not row.get('toolRef','').strip() or not row.get('observations','').strip():raise ValueError('Actual '+key+' review is missing')
    data['scope']='Reviewer attestations tied to the file hash; this CLI does not see or hear the work'
    data['input']=a.input;data['format']=a.format
    out=project/'out/qa'/f'visual-review-{a.format}.json';write(out,data);print(out)
if __name__=='__main__':run_main(main)
