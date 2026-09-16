#!/usr/bin/env python3
"""Initialize a project (optionally with a profile overlay), prepare a full-script review, plan narration gaps, compile or validate.

  project.py init <work> [--profile viral|launch]
  project.py script <project>
  project.py plan-voices <project> [--lead 0.3] [--tail 1.5]
  project.py compile <project> [--draft]
  project.py validate <project> [--draft]
"""
import argparse, json, shutil, subprocess
from pathlib import Path
from common import ROOT, read, write, run_main

def plan_voices(project, lead=None, tail=None):
    """Schedule narration back to back with policy gaps: voices[].at = {after, offset}; existing per-voice keys are kept."""
    from voice_edit import gap_seconds
    project=Path(project);brief=read(project/'content/brief.json');script=read(project/'content/script.json');film=read(project/'content/film.json')
    policy=(brief.get('pacing') or {}).get('gapPolicy') or {}
    lead=float(lead if lead is not None else (brief.get('pacing') or {}).get('leadSeconds',0.3))
    beats=[b for b in script['beats'] if b.get('narration','').strip()]
    existing={v['id']:v for v in film.get('voices',[])}
    voices=[];rows=[];prev=None
    for b in beats:
        v={k:x for k,x in existing.get(b['id'],{}).items() if k not in ('at',)}
        v['id']=b['id']
        if prev is None: v['at']=lead;gap=lead
        else:
            gap=gap_seconds(prev,b,policy);v['at']={'after':prev['id'],'offset':gap}
        voices.append(v);rows.append((b['id'],b.get('kind',''),gap));prev=b
    film['voices']=voices;write(project/'content/film.json',film)
    for id,kind,gap in rows:print(f'{id:14s} {kind:8s} gap-before {gap:.2f}s')
    print(f'{len(voices)} voices scheduled; compile to resolve measured starts')
    return voices

def main():
    p=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter);sub=p.add_subparsers(dest='cmd',required=True)
    for name in ['init','script','compile','validate','plan-voices']:
        q=sub.add_parser(name);q.add_argument('path',type=Path)
        if name=='init':q.add_argument('--profile',choices=['viral','launch']);q.add_argument('--resume',action='store_true',help='Reuse a recognizable initialized project without overwriting anything')
        if name in ('compile','validate'):q.add_argument('--draft',action='store_true')
        if name=='plan-voices':q.add_argument('--lead',type=float);q.add_argument('--tail',type=float)
    a=p.parse_args();project=a.path.resolve()
    if a.cmd=='init':
        project=project/'project'
        if project.exists():
            if a.resume and all((project/f).is_file() for f in ['content/film.json','src/Film.tsx','package.json','core/build.mjs']):
                print(project);print('Resumed without overwriting. Existing source may need explicit migration; --resume does not upgrade it.');return
            raise ValueError(f'Project already exists; preserved: {project}. Use a fresh work directory; --resume only accepts an initialized project.')
        shutil.copytree(ROOT/'assets/director',project,ignore=shutil.ignore_patterns('node_modules','out','__pycache__','.DS_Store'))
        overlay=ROOT/'profiles'/(a.profile or '')/'files/assets/director'
        if a.profile and overlay.is_dir():
            for src in overlay.rglob('*'):
                if src.is_file():
                    dst=project/src.relative_to(overlay);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
        if a.profile:
            brief=read(project/'content/brief.json');brief['profile']=a.profile;write(project/'content/brief.json',brief)
        print(project);return
    if a.cmd=='compile':
        subprocess.run(['node','core/build.mjs']+(['--draft'] if a.draft else []),cwd=project,check=True);return
    if a.cmd=='validate':
        subprocess.run(['python3',str(ROOT/'scripts/validate.py'),str(project)]+(['--draft']if a.draft else []),check=True);return
    if a.cmd=='plan-voices':
        plan_voices(project,a.lead,a.tail);return
    s=read(project/'content/script.json');lines=['# '+s.get('title','脚本文案'),'', '**观看收益**：'+s.get('viewerPromise',''),'', '**核心观点**：'+s.get('thesis',''),'','## 完整口播','']
    for b in s.get('beats',[]):
        lines.extend([f"### {b['id']}"+(f"（{b['kind']}）" if b.get('kind') else ''),'',b.get('narration',''),''])
        if b.get('overrides'):lines.extend(['读法：'+'；'.join(f'{x}→{y}' for x,y in b['overrides']),''])
        if b.get('viewerGain'):lines.extend(['本段作用：'+b['viewerGain'],''])
        if b.get('claims'):lines.extend(['事实引用：'+', '.join(b['claims']),''])
    hv=s.get('hookVariants') or []
    if hv:lines.extend(['## 开场候选（采用的是 beats[0]，其余供替换）','']+[f"- {v.get('type','')}：{v.get('narration','')}" for v in hv if isinstance(v,dict)]+[''])
    vis=read(project/'content/visual.json',{})
    lines.extend(['## 视觉方向','',vis.get('concept','待按本条素材设计'),'','专属镜头（这条片独有的视觉隐喻，不来自效果目录；写进 film.shots[].bespoke）：'+(vis.get('bespoke') or '待定'),''])
    import script_check;_report,check_md=script_check.run(project);lines.extend(['',check_md])  # retention timeline, exit points, hints (out/script-check.md too)
    out=project/'out/script-review.md';out.parent.mkdir(exist_ok=True);out.write_text('\n'.join(lines),encoding='utf-8');print(out)

if __name__=='__main__':run_main(main)
