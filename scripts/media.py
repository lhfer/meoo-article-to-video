#!/usr/bin/env python3
"""Generate using the Grok subscription CLI, or ingest existing media with provenance."""
import argparse, json, shutil, subprocess, sys, time
from pathlib import Path
from common import ROOT,read,write,ident,filehash,inside,run_main,probe

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('project',type=Path);p.add_argument('--id',required=True);p.add_argument('--kind',choices=['image','edit','i2v','r2v','ingest'],required=True);p.add_argument('--prompt-file',type=Path);p.add_argument('--image',action='append',default=[]);p.add_argument('--input',type=Path);p.add_argument('--aspect',default='3:4');p.add_argument('--duration',type=int,default=6);p.add_argument('--resolution',default='720p');p.add_argument('--dry-run',action='store_true');a=p.parse_args()
    project=a.project.resolve();id=ident(a.id);stamp=str(time.time_ns());job=project/'work/generation'/f'{id}-{stamp}'
    prompt=a.prompt_file.read_text(encoding='utf-8') if a.prompt_file else ''
    visual=read(project/'content/visual.json',{});style=visual.get('stylePrompt','')
    if a.kind!='ingest' and not prompt.strip():raise ValueError('Provide the shot-specific prompt file')
    if a.kind=='ingest' and (not a.input or not a.input.is_file()):raise ValueError('Provide an existing --input file')
    ext=a.input.suffix.lower() if a.kind=='ingest' else ('.mp4'if a.kind in ['i2v','r2v']else '.png')
    relative=f'gen/{id}-{stamp}{ext}';out=inside(project/'public',relative)
    final_prompt=f'{style}\n\n本镜具体表达：\n{prompt}'.strip()
    cmd=[sys.executable,str(ROOT/'scripts/grok_media.py'),a.kind,'-o',str(out),'--prompt-file',str(job/'prompt.txt'),'--work-dir',str(job)]
    for image in a.image:cmd.extend(['--image',str(Path(image).expanduser().resolve())])
    if a.kind in ['image','edit','r2v']:cmd.extend(['--aspect',a.aspect])
    if a.kind in ['i2v','r2v']:cmd.extend(['--duration',str(a.duration),'--resolution',a.resolution])
    if a.dry_run:print(json.dumps({'provider':'grok-cli' if a.kind!='ingest'else 'ingest','command':cmd if a.kind!='ingest'else None,'prompt':final_prompt,'output':relative,'executed':False},ensure_ascii=False,indent=2));return
    job.mkdir(parents=True);out.parent.mkdir(parents=True,exist_ok=True);(job/'prompt.txt').write_text(final_prompt,encoding='utf-8')
    if a.kind=='ingest':shutil.copy2(a.input,out)
    else:
        with (job/'result.log').open('w') as log:subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,check=True)
    if not out.is_file():raise ValueError('Provider returned without a local output; inspect the current job log')
    metadata={}
    if ext in ['.mp4','.mov','.webm']:
        raw=job/('source'+ext);out.replace(raw)
        # A generated MP4 may also contain a poster stream. Keep one moving video and optional audio.
        relative=f'gen/{id}-{stamp}.mp4';out=inside(project/'public',relative)
        subprocess.run(['ffmpeg','-v','error','-y','-i',str(raw),'-map','0:v:0','-map','0:a:0?','-vf','scale=trunc(iw/2)*2:trunc(ih/2)*2,setsar=1','-c:v','libx264','-crf','18','-preset','fast','-pix_fmt','yuv420p','-c:a','aac','-movflags','+faststart','-map_metadata','-1',str(out)],check=True)
        info=probe(out);video=next(s for s in info['streams'] if s['codec_type']=='video')
        metadata={'width':video['width'],'height':video['height'],'durationSeconds':float(info['format']['duration']),'hasAudio':any(s['codec_type']=='audio' for s in info['streams']),'requestedAspect':a.aspect,'originalRetained':str(raw.relative_to(project))}
    film_path=project/'content/film.json';film=read(film_path)
    entry={'src':relative,'sha256':filehash(out),'provider':'grok-cli' if a.kind!='ingest'else 'ingest','prompt':final_prompt,'references':a.image,'createdAtNs':stamp,'kind':'video'if ext in ['.mp4','.mov','.webm']else 'image',**metadata}
    film.setdefault('assets',{})[id]=entry;write(film_path,film)
    log_path=project/'public/gen/manifest.json';manifest=read(log_path,[]);manifest.append({'id':id,**entry});write(log_path,manifest)
    print(json.dumps({'id':id,'file':str(out),'next':'Inspect the actual output, then reference the asset id in the shot.assets list.'},ensure_ascii=False))

if __name__=='__main__':run_main(main)
