#!/usr/bin/env python3
"""Capture a real webpage, optionally with a bounded interaction recording.
  capture.py PROJECT --id homepage --url https://example.com --rights "Use basis" [--selector main]
  capture.py PROJECT --id demo --url http://127.0.0.1:3000 --allow-local --record --actions actions.json --allow-interaction --rights "Own test app"
Requires Python Playwright and Chromium. Host-native browser tools remain the preferred route when available.
No login/cookie import, arbitrary JS, downloader bypass, or generated UI. Never use production/private data.
"""
import argparse, ipaddress, json, os, shutil, socket, subprocess, time
from pathlib import Path
from urllib.parse import urlsplit
from common import read, write, inside, ident, filehash, probe, run_main

ACTIONS={'click','fill','press','scroll','wait','hover'}
def validate_url(url, allow_local=False):
    parsed=urlsplit(url)
    if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Only http(s) URLs without embedded credentials are supported')
    if allow_local:return
    host=parsed.hostname.lower()
    try: addresses=[str(ipaddress.ip_address(host))]
    except ValueError:
        addresses=list({x[4][0] for x in socket.getaddrinfo(host,parsed.port or (443 if parsed.scheme=='https' else 80))})
    if any(not ipaddress.ip_address(x).is_global for x in addresses):
        raise ValueError('Private/local target requires explicit --allow-local for your own authorized app')

def validate_actions(actions):
    if not isinstance(actions,list) or len(actions)>30:raise ValueError('Actions must be a list with at most 30 steps')
    total=0
    for action in actions:
        if not isinstance(action,dict) or action.get('type') not in ACTIONS:raise ValueError('Unsupported capture action (no script evaluation)')
        if action['type'] in ('click','fill','press','hover') and not action.get('selector'):raise ValueError('Action requires a selector')
        if action['type']=='wait':
            seconds=float(action.get('seconds',1))
            if not 0<=seconds<=10:raise ValueError('A wait must be 0..10 seconds')
            total+=seconds
        if action['type']=='scroll' and (not isinstance(action.get('y',500),(float,int)) or abs(action.get('y',500))>4000):raise ValueError('Scroll must be bounded')
    if total>45:raise ValueError('Total waits exceed 45 seconds')
    return actions

def main():
    p=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('project',type=Path);p.add_argument('--id',required=True);target=p.add_mutually_exclusive_group(required=True);target.add_argument('--url');target.add_argument('--html',help='Project-relative self-contained HTML; offline illustration only, NOT verified product evidence');p.add_argument('--rights',required=True)
    p.add_argument('--selector');p.add_argument('--wait-selector');p.add_argument('--record',action='store_true');p.add_argument('--actions',type=Path)
    p.add_argument('--allow-interaction',action='store_true');p.add_argument('--allow-local',action='store_true');p.add_argument('--browser')
    p.add_argument('--width',type=int,default=1440);p.add_argument('--height',type=int,default=900);p.add_argument('--seconds',type=float,default=3)
    p.add_argument('--mask',action='append',default=[]);p.add_argument('--material');a=p.parse_args()
    project=a.project.resolve();id=ident(a.id)
    if not (project/'content/film.json').exists():raise ValueError('Initialize the project before capture')
    if not 320<=a.width<=3840 or not 240<=a.height<=2160 or not 0<=a.seconds<=30:raise ValueError('Capture dimensions/duration out of bounds')
    if a.mask and a.record:raise ValueError('Screenshot masks do not mask recordings. Use a clean test dataset; do not record private data.')
    if id in read(project/'content/film.json').get('assets',{}):raise ValueError('Asset id already exists; use a new id to preserve it')
    if not a.rights.strip():raise ValueError('Record an actual use basis')
    if a.material and not any(x.get('id')==a.material for x in read(project/'content/materials.json',{'items':[]})['items']):raise ValueError('Unknown material '+a.material)
    html_path=inside(project,a.html) if a.html else None
    if html_path and not html_path.is_file():raise ValueError('Local HTML file does not exist')
    target_label=a.url or 'local-html:'+a.html
    if a.url:validate_url(a.url,a.allow_local)
    actions=validate_actions(read(a.actions)) if a.actions else []
    if actions and not a.allow_interaction:raise ValueError('Actions require --allow-interaction and authorization to operate this test app')
    stamp=str(time.time_ns());job=project/'work/captures'/f'{id}-{stamp}';job.mkdir(parents=True)
    receipt={'id':id,'url':target_label,'sourceMode':'local-html' if html_path else 'webpage','viewport':{'width':a.width,'height':a.height},'status':'started','steps':[],'rights':a.rights,'capturedAt':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            binary=a.browser or os.getenv('CHROMIUM_PATH') or shutil.which('chromium') or shutil.which('chromium-browser')
            browser=pw.chromium.launch(headless=True,**({'executable_path':binary} if binary else {}))
            opts={'viewport':receipt['viewport'],'device_scale_factor':1,'service_workers':'block'}
            if a.record:opts.update(record_video_dir=str(job/'raw'),record_video_size=receipt['viewport'])
            context=browser.new_context(**opts)
            checked=set()
            def route_handler(route):
                u=route.request.url
                if html_path and not u.startswith(('data:','blob:')):route.abort();return
                if u.startswith(('data:','blob:')):route.continue_();return
                try:
                    host=urlsplit(u).netloc
                    if host not in checked:validate_url(u,a.allow_local);checked.add(host)
                    route.continue_()
                except Exception:route.abort()
            context.route('**/*',route_handler)
            page=context.new_page();page.set_default_timeout(15000)
            if html_path:
                page.set_content(html_path.read_text(encoding='utf-8'),wait_until='domcontentloaded',timeout=45000);response=None
                receipt['inputHtmlSha256']=filehash(html_path)
            else:response=page.goto(a.url,wait_until='domcontentloaded',timeout=45000)
            if response and response.status>=400:raise ValueError(f'HTTP {response.status}; do not treat an error page as product evidence')
            if a.wait_selector:page.locator(a.wait_selector).wait_for(state='visible')
            page.evaluate('() => document.fonts.ready')
            page.wait_for_timeout(600)
            page.evaluate("() => Promise.all(Array.from(document.images).filter(i=>i.getBoundingClientRect().top<innerHeight).map(i=>i.complete?Promise.resolve():new Promise(r=>{i.onload=r;i.onerror=r;setTimeout(r,3000)})))")
            for action in actions:
                kind=action['type'];loc=page.locator(action['selector']) if action.get('selector') else None
                if kind=='click':loc.click()
                elif kind=='fill':loc.fill(str(action.get('value','')))
                elif kind=='press':loc.press(action.get('key','Enter'))
                elif kind=='hover':loc.hover()
                elif kind=='scroll':page.mouse.wheel(0,action.get('y',500))
                else:page.wait_for_timeout(float(action.get('seconds',1))*1000)
                receipt['steps'].append({'type':kind,'selector':action.get('selector'),'completed':True})
            page.wait_for_timeout(a.seconds*1000)
            receipt['title']=page.title();receipt['finalUrl']=page.url
            image=job/'screenshot.png';masks=[page.locator(s) for s in a.mask]
            (page.locator(a.selector) if a.selector else page).screenshot(path=str(image),animations='disabled',mask=masks)
            video=page.video
            context.close()
            raw=Path(video.path()) if video else None
            browser.close()
        ext='.mp4' if raw else '.png';src=f'captures/{id}-{stamp}{ext}';dest=inside(project/'public',src);dest.parent.mkdir(parents=True,exist_ok=True)
        if raw:
            subprocess.run(['ffmpeg','-v','error','-y','-i',str(raw),'-an','-vf','scale=trunc(iw/2)*2:trunc(ih/2)*2,setsar=1','-c:v','libx264','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(dest)],check=True,timeout=120)
        else:shutil.copy2(image,dest)
        info=probe(dest);v=next(s for s in info['streams'] if s['codec_type']=='video')
        if min(v['width'],v['height'])<32:raise ValueError('Capture too small')
        source_id=id+'-capture-'+stamp;source_file=f'assets/sources/{source_id}/source.md';source_path=inside(project,source_file);source_path.parent.mkdir(parents=True)
        source_path.write_text(f"# Real browser capture\n\nInput: {target_label}\nFinal URL: {receipt['finalUrl']}\nTitle: {receipt['title']}\nCaptured: {receipt['capturedAt']}\nUse basis: {a.rights}\n\nReadiness: acquired only. Inspect the actual pixels and redact any private information before use.\n",encoding='utf-8')
        sources=read(project/'content/sources.json',[]);sources.append({'id':source_id,'input':target_label,'title':receipt['title'],'textFile':source_file,'kind':'browser-capture'});write(project/'content/sources.json',sources)
        film=read(project/'content/film.json')
        if id in film.get('assets',{}):raise ValueError('Asset id already exists; use a new id to preserve the earlier asset')
        entry={'src':src,'sha256':filehash(dest),'kind':'video' if raw else 'image','provider':'browser-capture','sourceMode':receipt['sourceMode'],'sourceId':source_id,'width':v['width'],'height':v['height'],'rights':a.rights,'capturedAt':receipt['capturedAt']}
        film.setdefault('assets',{})[id]=entry;write(project/'content/film.json',film)
        receipt.update(status='acquired',assetId=id,sourceId=source_id,file=src,sha256=entry['sha256'],screenshot=str(image.relative_to(project)),notChecked=['visual correctness','private information','licence interpretation','claim validity'])
        if a.material:
            data=read(project/'content/materials.json');item=next((x for x in data['items'] if x['id']==a.material),None)
            if not item:raise ValueError('Unknown material '+a.material)
            item.update(assetId=id,sourceId=source_id,rights=a.rights,provenance='browser-capture',status='acquired');item.pop('inspection',None)
            if html_path:item['evidenceKind']='illustration'
            write(project/'content/materials.json',data)
    except Exception as e:
        receipt.update(status='blocked',error=str(e));write(job/'receipt.json',receipt)
        raise ValueError(f"Capture failed; receipt: {job/'receipt.json'}\n{e}") from e
    write(job/'receipt.json',receipt);print(json.dumps(receipt,ensure_ascii=False,indent=2))
if __name__=='__main__':run_main(main)
