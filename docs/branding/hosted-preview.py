"""Optional hosted GitHub README smoke test. Saves evidence, never changes repository files."""
import json,os
from pathlib import Path
from playwright.sync_api import sync_playwright
out=Path('readme-preview');out.mkdir(exist_ok=True)
repo=os.environ['GITHUB_REPOSITORY'];sha=os.environ['GITHUB_SHA']
results=[]
with sync_playwright() as p:
 browser=p.chromium.launch()
 for width,theme in ((1440,'light'),(1440,'dark'),(390,'light'),(320,'dark')):
  page=browser.new_page(viewport={'width':width,'height':1000},device_scale_factor=1,color_scheme=theme)
  item={'width':width,'theme':theme,'url':f'https://github.com/{repo}/blob/{sha}/README.md'}
  try:
   page.goto(item['url'],wait_until='domcontentloaded',timeout=60000)
   article=page.locator('article.markdown-body').first
   article.wait_for(timeout=30000)
   page.evaluate('''theme=>{document.documentElement.setAttribute('data-color-mode',theme);document.documentElement.setAttribute('data-light-theme','light');document.documentElement.setAttribute('data-dark-theme','dark')}''',theme)
   article.locator('img').last.scroll_into_view_if_needed()
   page.wait_for_function("Array.from(document.querySelectorAll('article.markdown-body img')).every(i=>i.complete&&i.naturalWidth>0)",timeout=30000)
   item['images']=article.locator('img').evaluate_all('(a)=>a.map(i=>({src:i.currentSrc,width:i.naturalWidth}))')
   item['articleOverflow']=article.evaluate('(e)=>e.scrollWidth>e.clientWidth+1')
   item['pageOverflow']=page.evaluate('document.documentElement.scrollWidth>innerWidth+1')
   page.emulate_media(reduced_motion='reduce');page.wait_for_timeout(500)
   item['reducedMotionPoster']=article.locator('img').last.evaluate('(i)=>i.currentSrc.includes("meoo-mascot-poster.png")')
   article.screenshot(path=str(out/f'readme-{theme}-{width}.png'))
   item['status']='passed' if not item['articleOverflow'] and not item['pageOverflow'] and item['reducedMotionPoster'] else 'needs-review'
  except Exception as e:item['status']='unverified';item['error']=str(e)
  finally:results.append(item);page.close()
 browser.close()
(out/'hosted-report.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
print(json.dumps(results,ensure_ascii=False,indent=2))
if any(r['status']!='passed' for r in results):raise SystemExit(1)
