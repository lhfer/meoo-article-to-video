#!/usr/bin/env python3
"""Real Chromium regression for the SHIPPED pure DOM/layout engine, plus screenshot/interaction capture.
Not a React/Remotion render or Meoo end-to-end test. Requires Python Playwright, Chromium, ffmpeg/ffprobe.
python tests/browser_regression.py --out /absolute/test-output [--browser /path/to/chromium]
"""
import argparse,base64,contextlib,http.server,json,os,shutil,subprocess,sys,tempfile,threading
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
FIXTURE_JS=r'''
import {layoutFor} from './layout-engine.mjs';import {fitElement,inspectLayout} from './dom-qa.mjs';
window.inspectLayout=inspectLayout;window.layoutFor=layoutFor;window.fitElement=fitElement;
const rect=(r)=>({position:'absolute',left:r.x+'px',top:r.y+'px',width:r.w+'px',height:r.h+'px',boxSizing:'border-box'});
window.make=(fmt,caption='自动归档后直接查看每日待办',title='先看结果，再讲过程',options={})=>{
 document.body.innerHTML='';const l=layoutFor(fmt,options);window.L=l;
 const root=document.createElement('div');root.dataset.qaRoot='true';root.style.cssText=`position:relative;width:${l.w}px;height:${l.h}px;background:#f5f5f2;font-family:"Noto Sans CJK SC",sans-serif;`;document.body.append(root);window.R=root;
 const shot=document.createElement('div');shot.dataset.qaShot='fixture';shot.style.cssText='position:absolute;inset:0';root.append(shot);
 function box(id,r,role,parent=shot){const el=document.createElement('div');el.dataset.qaBlock=id;el.dataset.qaRole=role;Object.assign(el.style,rect(r));parent.append(el);return el;}
 function text(id,r,value,role,min,max,lines=2,parent=shot){const el=box(id,r,role,parent);el.dataset.qaText='true';Object.assign(el.style,{fontSize:max+'px',fontWeight:role==='title'?'700':'600',whiteSpace:'pre-wrap',overflowWrap:'anywhere',wordBreak:'normal',lineHeight:role==='caption'?'1.28':'1.16',color:'#15171c'});const inner=document.createElement('span');inner.dataset.qaTextInner='true';inner.style.cssText='display:block;width:100%';inner.textContent=value;el.append(inner);fitElement(el,{minFont:min,maxFont:max,maxLines:lines,lineHeight:role==='caption'?1.28:1.16});return el;}
 text('title',{x:l.title.x+8,y:l.title.y+8,w:l.title.w-16,h:l.title.h-16},title,'title',l.min.title,l.min.title+20);
 const mr={x:l.subject.x+12,y:l.subject.y+12,w:l.subject.w-24,h:l.subject.h-24};const media=box('evidence',mr,'media');media.style.background='#e7e8e6';media.style.borderRadius='24px';media.style.overflow='hidden';
 const art=document.createElement('div');art.style.cssText='position:absolute;left:12%;right:12%;top:20%;height:40%;display:flex;gap:20px;align-items:end';media.append(art);for(const h of [45,72,92]){const bar=document.createElement('div');bar.style.cssText=`flex:1;height:${h}%;background:#83949b;border-radius:12px`;art.append(bar);}
 text('placeholder',{x:24,y:mr.h-72,w:mr.w-48,h:48},'布局回归测试 · 不是产品实测','note',l.min.note,l.min.note,1,media);
 const sr={x:l.side.x+12,y:l.side.y+12,w:l.side.w-24,h:l.side.h-24};const side=box('side',sr,'body');side.style.background='white';side.style.borderRadius='24px';
 text('step',{x:24,y:24,w:sr.w-48,h:Math.ceil(l.min.body*1.2*2+8)},'先看真实画面','body',l.min.body,l.min.body+6,2,side);
 text('detail',{x:24,y:Math.ceil(l.min.body*1.2*2+48),w:sr.w-48,h:sr.h-Math.ceil(l.min.body*1.2*2+72)},'不要让文字卡片替代证据。','body',l.min.body,l.min.body,fmt==='16x9'?5:3,side);
 const sub=text('caption',{x:l.caption.x+22,y:l.caption.y+10,w:l.caption.w-44,h:l.caption.h-20},caption,'caption',l.min.caption,l.captionFont,2,root);Object.assign(sub.style,{textAlign:'center',display:'flex',alignItems:'center',color:'white'});
 const inside=sub.querySelector('[data-qa-text-inner]');const pill=document.createElement('span');pill.textContent=inside.textContent;inside.textContent='';pill.style.cssText='background:rgba(0,0,0,.78);padding:4px 12px;border-radius:10px;box-decoration-break:clone;-webkit-box-decoration-break:clone';inside.append(pill);fitElement(sub,{minFont:l.min.caption,maxFont:l.captionFont,maxLines:2,lineHeight:1.28});
 return inspectLayout(root,l);
};window.ready=true;
'''
class Handler(http.server.SimpleHTTPRequestHandler):
 def log_message(self,*a):pass

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--browser');args=ap.parse_args();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
 browser_path=args.browser or os.getenv('CHROMIUM_PATH') or shutil.which('chromium') or shutil.which('chromium-browser')
 from playwright.sync_api import sync_playwright
 rows=[]
 with tempfile.TemporaryDirectory() as td:
  td=Path(td);web=td/'site';web.mkdir()
  for filename in ['layout-engine.mjs','dom-qa.mjs']:shutil.copy2(ROOT/'assets/director/src/kit'/filename,web/filename)
  (web/'fixture.mjs').write_text(FIXTURE_JS);(web/'index.html').write_text('<!doctype html><meta charset="utf-8"><style>body{margin:0}*{box-sizing:border-box}</style><script type="module" src="fixture.mjs"></script>')
  (web/'app.html').write_text('''<!doctype html><meta charset="utf-8"><title>Local capture regression fixture</title><style>body{font:26px "Noto Sans CJK SC",sans-serif;margin:70px;background:#f5f5f2}button{font:inherit;padding:18px 32px}#result{margin-top:45px;font-size:38px}</style><h1>真实浏览器操作测试</h1><p>本地合成测试页，不是真实产品或商业证据。</p><button id="run" onclick="document.querySelector('#result').textContent='结果已更新：任务完成'">运行测试</button><div id="result">等待操作</div>''')
  server=http.server.ThreadingHTTPServer(('127.0.0.1',0),lambda *a,**k:Handler(*a,directory=str(web),**k));thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();url=f'http://127.0.0.1:{server.server_port}'
  try:
   with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,**({'executable_path':browser_path} if browser_path else {}));page=browser.new_page(viewport={'width':1920,'height':1920},device_scale_factor=1)
    # This host blocks loopback navigation. Load unchanged module logic with data-URL imports, without changing browser policy.
    def uri(text):return 'data:text/javascript;base64,'+base64.b64encode(text.encode()).decode()
    engine=uri((web/'layout-engine.mjs').read_text())
    dom=uri((web/'dom-qa.mjs').read_text().replace("'./layout-engine.mjs'",json.dumps(engine)))
    fixture=uri(FIXTURE_JS.replace("'./layout-engine.mjs'",json.dumps(engine)).replace("'./dom-qa.mjs'",json.dumps(dom)))
    page.set_content('<!doctype html><meta charset="utf-8"><style>body{margin:0}*{box-sizing:border-box}</style>')
    page.evaluate('(url)=>import(url)',fixture);page.wait_for_function('window.ready');page.evaluate('document.fonts.ready')
    for fmt in ['3x4','9x16','16x9']:
     r=page.evaluate('(f)=>make(f)',fmt);rows.append({'case':fmt+' thirteen-character caption + real DOM measurement','ok':r['ok'],'report':r})
     page.locator('[data-qa-root]').screenshot(path=str(out/f'layout-{fmt}.png'))
     # Two-line caption, two-line title, scaling, and an entry animation extreme.
     r=page.evaluate("f=>make(f,'自动归档后直接查看每日待办，先看结果再了解完整的实现过程。','一套布局同时约束标题、主体与字幕的位置')",fmt);rows.append({'case':fmt+' long Chinese wrap','ok':r['ok'],'report':r})
     r=page.evaluate("f=>{make(f);R.style.transform='scale(.5)';R.style.transformOrigin='top left';return inspectLayout(R,L)}",fmt);rows.append({'case':fmt+' half-resolution geometry normalization','ok':r['ok'],'report':r})
     r=page.evaluate("f=>{make(f);document.querySelector('[data-qa-block=evidence]').style.transform='translateY(8px)';return inspectLayout(R,L)}",fmt);rows.append({'case':fmt+' entrance extreme','ok':r['ok'],'report':r})
     caught=page.evaluate("f=>{try{make(f,'这是不能靠裁切隐藏的超长字幕。'.repeat(40));return false}catch(e){return /cannot fit/.test(e.message)}}",fmt);rows.append({'case':fmt+' impossible long caption rejected','ok':caught})
    for name,js,kind in [
      ('caption covers subject',"const e=document.querySelector('[data-qa-block=evidence]');e.style.top=L.caption.y+'px'",'overlap'),
      ('font below minimum',"document.querySelector('[data-qa-block=title]').style.fontSize='20px'",'small-type'),
      ('subject outside content',"document.querySelector('[data-qa-block=evidence]').style.left='-20px'",'outside-region'),
      ('unmarked legacy text under caption',"const e=document.createElement('div');e.textContent='legacy text';e.style.cssText=`position:absolute;left:100px;top:${L.caption.y+20}px;font-size:44px`;R.append(e)",'text-in-caption-band'),
      ('uninstrumented shot',"document.querySelectorAll('[data-qa-shot] [data-qa-block]').forEach(e=>e.removeAttribute('data-qa-block'))",'uninstrumented-shot')]:
     r=page.evaluate(f"()=>{{make('16x9');{js};return inspectLayout(R,L)}}");rows.append({'case':name+' detected','ok':any(f['kind']==kind for f in r['findings']),'report':r})
    for declared in [False,True]:
     report=page.evaluate("declared=>{make('16x9');const b=document.createElement('div');b.dataset.qaBlock='cinematic-background';b.dataset.qaRole='background';if(declared)b.dataset.qaAllowOverlap='Intentional full-frame footage behind readable protected text';b.style.cssText=`position:absolute;inset:0;width:${L.w}px;height:${L.h}px`;R.prepend(b);return inspectLayout(R,L)}",declared)
     rows.append({'case':'declared cinematic full-bleed allowed' if declared else 'undeclared full-bleed rejected','ok':report['ok'] if declared else not report['ok'],'report':report})
    caught=page.evaluate("()=>{try{make('16x9','W'.repeat(350));return false}catch(e){return /cannot fit/.test(e.message)}}");rows.append({'case':'unbroken English overflow rejected','ok':caught})
    browser.close()
   # Use installed system FFmpeg through a private TEST-only Playwright browser cache if no bundled recorder exists.
   project=out/'capture-project';shutil.copytree(ROOT/'assets/director',project,ignore=shutil.ignore_patterns('node_modules','out','work','__pycache__'))
   env=os.environ.copy();env['CHROMIUM_PATH']=browser_path or ''
   import playwright
   registry=Path(playwright.__file__).parent/'driver/package/browsers.json';revision=next(b['revision'] for b in json.loads(registry.read_text())['browsers'] if b['name']=='ffmpeg')
   cache=td/'playwright-cache';folder=cache/f'ffmpeg-{revision}';folder.mkdir(parents=True);exe=shutil.which('ffmpeg')
   if not sys.platform.startswith('linux') or not exe:raise RuntimeError('Capture regression cache adapter currently requires Linux system FFmpeg; production capture supports regular Playwright installs')
   (folder/'ffmpeg-linux').symlink_to(exe);env['PLAYWRIGHT_BROWSERS_PATH']=str(cache)
   shutil.copy2(web/'app.html',project/'test-app.html')
   actions=out/'test-actions.json';actions.write_text(json.dumps([{'type':'click','selector':'#run'},{'type':'wait','seconds':.5}]))
   for label,extra in [('screenshot',[]),('recording',['--record','--actions',str(actions),'--allow-interaction'])]:
    cmd=[sys.executable,str(ROOT/'scripts/capture.py'),str(project),'--id',label,'--html','test-app.html','--seconds','0.5','--rights','Locally authored regression fixture; not product evidence',*extra]
    r=subprocess.run(cmd,capture_output=True,text=True,env=env,timeout=90);(out/f'capture-{label}.log').write_text(r.stdout+'\n'+r.stderr)
    row={'case':'offline self-contained HTML browser '+label,'ok':r.returncode==0,'returncode':r.returncode}
    if r.returncode==0:
     data=json.loads(r.stdout);row['receipt']=data;src=project/'public'/data['file'];shutil.copy2(src,out/('capture-result'+src.suffix));row['artifact']='capture-result'+src.suffix
    else:row['error']=r.stderr[-2500:]
    rows.append(row)
   r=subprocess.run([sys.executable,str(ROOT/'scripts/fonts.py'),str(project),'auto'],capture_output=True,text=True,env=env,timeout=45);(out/'font-check.log').write_text(r.stdout+'\n'+r.stderr);rows.append({'case':'installed CJK font verified in real Chromium','ok':r.returncode==0,'returncode':r.returncode})
  finally:server.shutdown();server.server_close()
 result={'ok':all(r['ok'] for r in rows),'checks':len(rows),'passed':sum(r['ok'] for r in rows),'scope':'Actual Chromium with browser-local data-URL imports of shipped DOM/layout logic, plus self-contained HTML capture; network navigation blocked by host policy, NOT React/Remotion rendering or Meoo end-to-end','recordingTestSetup':'Linux system Chromium and system FFmpeg via a temporary private Playwright recorder cache, no global mutation','results':rows}
 (out/'browser-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='results'},ensure_ascii=False,indent=2))
 if not result['ok']:raise SystemExit(1)
if __name__=='__main__':main()
