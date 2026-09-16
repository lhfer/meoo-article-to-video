#!/usr/bin/env python3
"""Material ledger. acquired != visually reviewed != used in the film.
  materials.py PROJECT init [--from-script]
  materials.py PROJECT add --id demo --need "..." --why "..." --required --evidence-kind real-demo --required-for opening
  materials.py PROJECT set --id demo --asset demo --source source-id --rights "user's own product" --provenance user
  materials.py PROJECT attempt --id demo --route browser --result blocked --evidence work/capture/error.json --note "login required"
  materials.py PROJECT verify --id demo --tool-ref "actual image/video-view call id" --inspection-note "Viewed the input and result; no personal data"
  materials.py PROJECT check [--stage opening|final]
  materials.py PROJECT list [--missing] [--json]
Code illustrations: set --strategy code --shot SHOT, then verify AFTER viewing a real render. Never count code as real-demo.
"""
import argparse, json, time
from pathlib import Path
from common import read, write, ident, inside, filehash, run_main
from material_contract import check_asset, material_errors
PATH='content/materials.json'
STATUS=['pending','acquired','ready','blocked','asked','skipped']
STRATEGY=['user','search','capture','generate','code','existing','skip']
def load(project): return read(project/PATH,{'version':2,'items':[]})
def main():
    p=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('project',type=Path);sub=p.add_subparsers(dest='cmd',required=True)
    q=sub.add_parser('init');q.add_argument('--from-script',action='store_true')
    for cmd in ('add','set'):
        q=sub.add_parser(cmd);q.add_argument('--id',required=True)
        q.add_argument('--need',required=cmd=='add');q.add_argument('--why',required=cmd=='add')
        q.add_argument('--strategy',choices=STRATEGY,default='search' if cmd=='add' else None)
        q.add_argument('--beat');q.add_argument('--ask');q.add_argument('--asset');q.add_argument('--source');q.add_argument('--rights');q.add_argument('--note');q.add_argument('--shot')
        q.add_argument('--provenance',choices=['user','official','licensed','browser-capture','generated','code'])
        q.add_argument('--evidence-kind',choices=['real-demo','screenshot','illustration','reference'],default='reference' if cmd=='add' else None)
        q.add_argument('--required-for',choices=['opening','final'],default='final' if cmd=='add' else None)
        if cmd=='add':q.add_argument('--required',action='store_true')
        else:q.add_argument('--status',choices=STATUS)
    q=sub.add_parser('verify');q.add_argument('--id',required=True);q.add_argument('--tool-ref',required=True);q.add_argument('--inspection-note',required=True)
    q=sub.add_parser('attempt');q.add_argument('--id',required=True);q.add_argument('--route',required=True);q.add_argument('--result',choices=['acquired','blocked','unavailable','not-found'],required=True);q.add_argument('--evidence',required=True);q.add_argument('--note',required=True)
    q=sub.add_parser('check');q.add_argument('--stage',choices=['opening','final'],default='final')
    q=sub.add_parser('list');q.add_argument('--missing',action='store_true');q.add_argument('--json',action='store_true')
    a=p.parse_args();project=a.project.resolve()
    if not (project/'content/film.json').is_file():raise ValueError('Initialize the project FIRST: project.py init <work>')
    data=load(project);now=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
    if a.cmd=='init':
        if a.from_script:
            ids={x['id'] for x in data['items']}
            for b in read(project/'content/script.json').get('beats',[]):
                id=b['id']+'-visual'
                if id not in ids and b.get('narration','').strip():
                    data['items'].append({'id':id,'beat':b['id'],'need':'Fill in the exact visual evidence','why':b.get('viewerGain',''),'strategy':'search','status':'pending','required':b.get('kind') in ('hook','evidence'),'requiredFor':'opening' if b.get('kind')=='hook' else 'final','evidenceKind':'reference','attempts':[]})
        write(project/PATH,data);print(f"{len(data['items'])} items");return
    if a.cmd=='list':
        items=[x for x in data['items'] if not a.missing or x.get('status')!='ready']
        print(json.dumps(items,ensure_ascii=False,indent=2) if a.json else '\n'.join(f"{x['id']:24s} {x.get('status','pending'):9s} {'REQUIRED' if x.get('required') else 'optional'} {x['need']}" for x in items));return
    if a.cmd=='check':
        errors=material_errors(project,a.stage)
        print(json.dumps({'ok':not errors,'errors':errors},ensure_ascii=False,indent=2))
        if errors:raise SystemExit(1)
        return
    item=next((x for x in data['items'] if x['id']==a.id),None)
    if a.cmd=='add':
        if item:raise ValueError('Material id exists; use set')
        item={'id':ident(a.id),'status':'pending','required':a.required,'attempts':[]};data['items'].append(item)
    elif not item:raise ValueError('Unknown material: '+a.id)
    if a.cmd in ('add','set'):
        if getattr(a,'status',None)=='ready':raise ValueError('Use verify after actually viewing the file; set cannot assert ready')
        for k,arg in [('need','need'),('why','why'),('strategy','strategy'),('beat','beat'),('ask','ask'),('assetId','asset'),('sourceId','source'),('rights','rights'),('note','note'),('shotId','shot'),('provenance','provenance'),('evidenceKind','evidence_kind'),('requiredFor','required_for')]:
            value=getattr(a,arg,None)
            if value is not None:item[k]=value
        if getattr(a,'status',None):item['status']=a.status
        if a.asset:item['status']='acquired';item.pop('inspection',None)
        if item.get('strategy')=='skip' or item.get('status')=='skipped':
            if item.get('required'):raise ValueError('Required evidence cannot be silently skipped. Revise the unsupported claim/requirement explicitly.')
            item['status']='skipped'
    elif a.cmd=='attempt':
        receipt=inside(project,a.evidence)
        if not receipt.is_file():raise ValueError('Attempt receipt must exist under the project')
        item.setdefault('attempts',[]).append({'route':a.route,'result':a.result,'evidence':a.evidence,'sha256':filehash(receipt),'note':a.note,'at':now})
        if a.result=='blocked':item['status']='blocked'
    else:
        if not a.inspection_note.strip() or not a.tool_ref.strip():raise ValueError('Empty review receipt')
        if item.get('strategy')=='code':
            if item.get('evidenceKind')=='real-demo':raise ValueError('Code is not real demo evidence')
            film=read(project/'content/film.json');shot=next((s for s in film.get('shots',[]) if s['id']==item.get('shotId')),None)
            if not shot:raise ValueError('Name an existing --shot for the code illustration')
            code=inside(project/'src',film['components'][shot['component']]);meta={'sha256':filehash(code),'kind':'code'}
        else:meta=check_asset(project,item)
        item['inspection']={**meta,'toolRef':a.tool_ref,'note':a.inspection_note,'at':now,'kindOfCheck':'reviewer-attestation; not automated visual understanding'}
        item['status']='ready'
    item['updatedAt']=now;data['version']=2;write(project/PATH,data);print(f"{item['id']}: {item['status']}")
if __name__=='__main__':run_main(main)
