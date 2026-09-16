#!/usr/bin/env python3
"""Maintainer radar for the effect catalogue — never part of a production run.
Lists @remotion packages that docs/effects-radar.md has not evaluated yet and how far the pinned Remotion lags npm.
Usage: effects_radar.py [--doc docs/effects-radar.md] [--package assets/director/package.json] [--json]
Network calls are best-effort: offline it prints the pinned version and the evaluated count and exits 0."""
import argparse, json, re, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
NAME_RE=re.compile(r'`?(@remotion/[a-z0-9-]+)`?')

def evaluated_names(md):
    """Package names in the first column of the radar doc's table rows (adopted, rejected, infrastructure). Rows under a heading containing 下一轮 / TODO are candidates, not evaluations, so they stay listed."""
    names=set();candidates=False
    for line in md.splitlines():
        if line.startswith('#'):candidates=('下一轮' in line) or ('TODO' in line.upper());continue
        if candidates or not line.startswith('|'):continue
        cells=[c.strip() for c in line.strip().strip('|').split('|')]
        m=NAME_RE.fullmatch(cells[0]) if cells and cells[0] else None
        if m:names.add(m.group(1))
    return names

def unevaluated(rows,names):
    """npm rows (name/version/description) for @remotion packages the doc has not evaluated, sorted by name."""
    return sorted((r for r in rows if r.get('name','').startswith('@remotion/') and r['name'] not in names),key=lambda r:r['name'])

def npm_rows(limit=250):
    r=subprocess.run(['npm','search','@remotion','--searchlimit',str(limit),'--json'],capture_output=True,text=True,timeout=180)
    if r.returncode!=0:raise RuntimeError(r.stderr.strip()[:200] or 'npm search failed')
    return [{'name':x.get('name',''),'version':x.get('version',''),'description':(x.get('description') or '')[:100]} for x in json.loads(r.stdout or '[]')]

def npm_latest(pkg='remotion'):
    r=subprocess.run(['npm','view',pkg,'version'],capture_output=True,text=True,timeout=60)
    return r.stdout.strip() if r.returncode==0 and r.stdout.strip() else None

def pinned_version(package_json):
    return json.loads(Path(package_json).read_text(encoding='utf-8')).get('dependencies',{}).get('remotion')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--doc',type=Path,default=ROOT/'docs/effects-radar.md');p.add_argument('--package',type=Path,default=ROOT/'assets/director/package.json');p.add_argument('--json',action='store_true');a=p.parse_args()
    names=evaluated_names(a.doc.read_text(encoding='utf-8')) if a.doc.is_file() else set()
    report={'pinned':pinned_version(a.package),'evaluated':len(names),'latest':None,'new':[],'offline':False}
    try:
        report['latest']=npm_latest();report['new']=unevaluated(npm_rows(),names)
    except Exception as e:  # offline or npm missing: still useful, never fatal
        report['offline']=True;report['error']=str(e)[:160]
    if a.json:print(json.dumps(report,ensure_ascii=False,indent=1));return
    print(f"remotion pinned {report['pinned']} · npm latest {report['latest'] or '(offline)'} · {report['evaluated']} packages already evaluated in {a.doc.name}")
    if report['offline']:print('npm unreachable: '+report.get('error',''));return
    if not report['new']:print('no unevaluated @remotion packages');return
    print(f"{len(report['new'])} unevaluated package(s) — read their docs (append .md to the remotion.dev URL) and add a row to the radar doc:")
    for r in report['new']:print(f"- {r['name']} {r['version']}: {r['description']}")

if __name__=='__main__':main()
