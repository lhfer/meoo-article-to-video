#!/usr/bin/env python3
"""Check README links, local brand assets, dimensions and source integrity."""
from __future__ import annotations
import hashlib, json, re, sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
class Refs(HTMLParser):
 def __init__(self):
  super().__init__();self.links=[];self.anchors=set();self.errors=[]
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  for k in ('name','id'):
   if a.get(k):self.anchors.add(a[k])
  if tag=='a' and a.get('href'):self.links.append((a['href'],False))
  if tag=='img':
   if not a.get('alt','').strip():self.errors.append('Image missing descriptive alt')
   if a.get('src'):self.links.append((a['src'],True))
  if tag=='source' and a.get('srcset'):
   for item in a['srcset'].split(','):self.links.append((item.strip().split()[0],True))
def main():
 errors=[];count=0
 for name in ('README.md','docs/case-study.md','docs/readme-design.md','docs/branding/README.md'):
  file=ROOT/name
  if not file.is_file():errors.append(f'Missing: {name}');continue
  text=re.sub(r'```.*?```','',file.read_text(encoding='utf-8'),flags=re.S)
  p=Refs();p.feed(text);errors.extend(p.errors)
  for m in re.finditer(r'(!?)\[([^\]\n]*)\]\(([^\s)]+)\)',text):
   image,label,target=m.groups();p.links.append((target,bool(image)))
   if image and not label.strip():errors.append('Markdown image missing alt')
  for url,image in p.links:
   count+=1;u=urlsplit(url)
   if u.scheme or u.netloc:
    if image:errors.append(f'External image dependency: {url}')
    continue
   if not u.path:
    if u.fragment and unquote(u.fragment) not in p.anchors:errors.append(f'Anchor missing in {name}: {url}')
    continue
   dest=(ROOT/unquote(u.path).lstrip('/') if u.path.startswith('/') else file.parent/unquote(u.path)).resolve()
   if not dest.is_relative_to(ROOT):errors.append(f'Path escapes repository: {url}')
   elif not dest.exists():errors.append(f'Missing link in {name}: {url}')
 media=ROOT/'docs/media/brand-v2'
 sizes={'hero.png':(1600,840),'hero-mobile.png':(800,1120),'workflow.png':(1600,320),'workflow-mobile.png':(800,745),'case.png':(1600,330),'case-mobile.png':(800,520),'family.png':(1600,245),'family-mobile.png':(800,288)}
 manifest=json.loads((media/'manifest.json').read_text())
 expected={x['path']:x for x in manifest['files']}
 if set(expected)!=set(sizes):errors.append('Asset manifest inventory mismatch')
 for name,size in sizes.items():
  f=media/name
  with Image.open(f) as im:
   if im.size!=size:errors.append(f'Dimensions mismatch: {name}')
   im.verify()
  b=f.read_bytes()
  if len(b)>600_000:errors.append(f'Image exceeds 600 KB budget: {name}')
  if hashlib.sha256(b).hexdigest()!=expected.get(name,{}).get('sha256'):errors.append(f'Asset checksum mismatch: {name}')
 source=ROOT/'docs/branding/source'
 for name,expected_hash in {'meoo-logo.png':'f6f565b955b4b2fb294717e4b326c40c1c87123826cf174cdece5d28f79b2fa5','meoo-icon.png':'209b2c6bafe805c44c9b205778d960c5dcab083b07595b1424f8b53198ffadef','meoo-mascot.gif':'403f30881aa93a809f04c302d93b81f3f8cd85a55b89c2c6277da5da070f8bdc'}.items():
  if hashlib.sha256((source/name).read_bytes()).hexdigest()!=expected_hash:errors.append(f'Brand source checksum mismatch: {name}')
 with Image.open(source/'meoo-mascot.gif') as im:
  if im.n_frames!=41:errors.append('Mascot frame count changed')
  for i in range(im.n_frames):im.seek(i);im.load()
  im.seek(0);first=im.convert('RGBA')
 with Image.open(source/'meoo-mascot-poster.png') as im:
  if im.convert('RGBA').tobytes()!=first.tobytes():errors.append('Reduced-motion poster differs from first frame')
 if errors:
  print('\n'.join('ERROR: '+e for e in errors),file=sys.stderr);return 1
 print(f'PASS: {count} references; 8 PNGs; source checksums; 41 GIF frames; reduced-motion poster.')
 print('This check does not verify remote page rendering or Skill video generation.')
 return 0
if __name__=='__main__':raise SystemExit(main())
