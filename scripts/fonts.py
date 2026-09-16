#!/usr/bin/env python3
"""Verify an installed browser font and lock all roles to it; no font files are distributed by this skill.
  fonts.py PROJECT auto [--browser /path/to/chromium]
  fonts.py PROJECT verify --family "Noto Sans CJK SC"
This probes actual canvas metrics against missing-font fallbacks. It is not a complete glyph coverage proof; inspect rendered Chinese text.
For custom licensed fonts use existing film.style.fonts + registered assets and @remotion/fonts, then visually verify the real render.
"""
import argparse,json,os,platform,shutil
from pathlib import Path
from common import read,write,run_main,digest
CANDIDATES=['Noto Sans CJK SC','Noto Sans SC','PingFang SC','Microsoft YaHei','WenQuanYi Zen Hei','Source Han Sans SC']
def host_id():return digest({'platform':platform.platform(),'node':platform.node()})
def ensure_font(project):
    film=read(Path(project)/'content/film.json');fonts=film.get('style',{}).get('fonts',[])
    if fonts:return  # @remotion/fonts awaits actual font file loading; assets are checked by validate.
    receipt=read(Path(project)/'content/font-check.json',{})
    if not receipt.get('verified') or receipt.get('hostId')!=host_id():raise ValueError('Verify/lock an installed font on THIS host: fonts.py PROJECT auto (or register licensed font assets)')
    expected=receipt.get('fontRoles');actual=film.get('style',{}).get('fontRoles')
    if not expected or actual!=expected:raise ValueError('Font roles changed; repeat font verification')
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('project',type=Path);sub=p.add_subparsers(dest='cmd',required=True)
    for cmd in ['auto','verify']:
        q=sub.add_parser(cmd);q.add_argument('--browser')
        if cmd=='verify':q.add_argument('--family',required=True)
    a=p.parse_args();project=a.project.resolve()
    from playwright.sync_api import sync_playwright
    names=[a.family] if a.cmd=='verify' else CANDIDATES
    with sync_playwright() as pw:
        binary=a.browser or os.getenv('CHROMIUM_PATH') or shutil.which('chromium') or shutil.which('chromium-browser')
        browser=pw.chromium.launch(headless=True,**({'executable_path':binary} if binary else {}));page=browser.new_page()
        result=page.evaluate(r"""(names)=>{const c=document.createElement('canvas').getContext('2d');const samples=['字幕与标题宽度测试 2026 AI','mmmmmmWWWWiiIl1','待办事项，界面已更新。'];
          return names.map(name=>{let differs=false;const rows=[];for(const fallback of ['monospace','serif','sans-serif'])for(const text of samples){c.font=`48px "__missing_font__",${fallback}`;const base=c.measureText(text).width;c.font=`48px "${name}",${fallback}`;const width=c.measureText(text).width;if(Math.abs(base-width)>.1)differs=true;rows.push({fallback,text,base,width});}return {family:name,available:differs,measurements:rows};});}""",names)
        browser.close()
    selected=next((r for r in result if r['available']),None)
    if not selected:raise ValueError('No requested CJK font verified in this browser. Use host-provided licensed font files; do not silently fall back.')
    family=selected['family'];roles={k:f'"{family}",sans-serif' for k in ['display','sans','body']}
    film=read(project/'content/film.json');film.setdefault('style',{})['fontRoles']=roles;film['style']['fontFamily']=roles['body'];write(project/'content/film.json',film)
    receipt={'verified':True,'method':'browser canvas missing-font comparison','family':family,'fontRoles':roles,'hostId':host_id(),'measurements':selected['measurements'],'limitations':'Metric-based availability test, not all-glyph coverage or visual review'}
    write(project/'content/font-check.json',receipt);print(json.dumps(receipt,ensure_ascii=False,indent=2))
if __name__=='__main__':run_main(main)
