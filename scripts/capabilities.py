#!/usr/bin/env python3
"""Probe local executables separately from host-native tools. Never invent tool names.
  capabilities.py PROJECT probe
  capabilities.py PROJECT record --name search --tool ACTUAL_NAME --status passed --receipt work/search-result.json --note "Official page found"
  capabilities.py PROJECT show
A receipt is evidence of a reported call, not proof of an unperformed call. Do not record API keys, cookies or private contents.
"""
import argparse, importlib.util, json, shutil, subprocess, time
from pathlib import Path
from common import read,write,filehash,inside,run_main
HOST=['search','browse','image_view','audio_listen','tts','image_generation','video_generation','music_generation']
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('project',type=Path);sub=p.add_subparsers(dest='cmd',required=True)
    sub.add_parser('probe');sub.add_parser('show');q=sub.add_parser('record')
    q.add_argument('--name',choices=HOST,required=True);q.add_argument('--tool',required=True);q.add_argument('--status',choices=['passed','failed','unavailable'],required=True);q.add_argument('--receipt',required=True);q.add_argument('--note',required=True)
    a=p.parse_args();project=a.project.resolve()
    if not (project/'content/film.json').exists():raise ValueError('Run project.py init before recording capabilities')
    out=project/'content/capabilities.json';data=read(out,{'version':1,'host':{k:{'status':'not_tested'} for k in HOST}})
    if a.cmd=='probe':
        data['local']={}
        for name in ['python3','node','npm','ffmpeg','ffprobe','chromium','grok','uv']:
            path=shutil.which(name);entry={'status':'available' if path else 'unavailable','path':path,'liveTaskVerified':False}
            if path and name in ['python3','node','npm','ffmpeg','ffprobe']:
                r=subprocess.run([path,'-version' if name in ['ffmpeg','ffprobe'] else '--version'],capture_output=True,text=True,timeout=15)
                entry.update(status='passed' if r.returncode==0 else 'failed',version=(r.stdout or r.stderr).splitlines()[:1],scope='version command only')
            data['local'][name]=entry
        data['local']['python_playwright']={'status':'available' if importlib.util.find_spec('playwright') else 'unavailable','liveTaskVerified':False}
    elif a.cmd=='record':
        receipt=inside(project,a.receipt)
        if not receipt.is_file() or not receipt.stat().st_size:raise ValueError('Receipt must be a real nonempty local result/error file')
        data['host'][a.name]={'status':a.status,'tool':a.tool,'receipt':a.receipt,'sha256':filehash(receipt),'note':a.note,'scope':'recorded actual host invocation; a receipt is not an entitlement guarantee'}
    if a.cmd!='show':data['updatedAt']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime());write(out,data)
    print(json.dumps(data,ensure_ascii=False,indent=2))
if __name__=='__main__':run_main(main)
