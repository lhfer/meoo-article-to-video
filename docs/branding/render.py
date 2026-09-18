#!/usr/bin/env python3
"""Render the Meoo README family with Pillow. Fonts remain on the rendering host."""
from __future__ import annotations
import argparse, hashlib, json
from functools import lru_cache
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
PAPER='#f9f9fb'
INK='#232033'
CONFIG={
'article':dict(bg=PAPER,fg=INK,muted='#737080',line='#dfdce8',accent='#7960c9',panel='#eeebf7',tag='自媒体短视频 SKILL',number='01',en='ARTICLE TO VIDEO',title=('好内容，','不止于文字。'),sub=('把文章、资讯与观点，','讲成有声有画的故事。'),stages=('读懂内容','核对素材','组织镜头','带声样片','完成交付'),meta=('提炼发现与观点','记录证据与来源','写脚本，排镜头','确认声音与节奏','视频、封面、工程')),
'vibecoding':dict(bg='#111218',fg='#f5f3fa',muted='#aba7b8',line='#34313f',accent='#b8a5f4',panel='#242031',tag='VibeCoding 作品宣传 SKILL',number='02',en='BUILD IT. SHOW IT.',title=('好作品，','值得被看见。'),sub=('把网站、App、工具与小游戏，','带到真正需要它的人面前。'),stages=('体验作品','找到价值','组织镜头','带声样片','完成交付'),meta=('真实操作与结果','讲清谁需要它','写脚本，排镜头','确认声音与节奏','视频、封面、工程'))}
FONT=Path('/usr/share/fonts/opentype/noto')
@lru_cache(maxsize=96)
def font(n,bold=False):
 p=FONT/('NotoSansCJK-Bold.ttc' if bold else 'NotoSansCJK-Regular.ttc')
 if not p.exists():raise RuntimeError(f'Install Noto Sans CJK or pass --font-dir: {p}')
 return ImageFont.truetype(str(p),n,index=2)
def text(im,x,y,s,n=26,fill=INK,bold=False,max_width=None):
 d=ImageDraw.Draw(im);f=font(n,bold)
 if max_width and d.textlength(s,font=f)>max_width:raise ValueError(f'Text overflows: {s}')
 d.text((x,y),s,font=f,fill=fill,anchor='lt')
def rr(im,box,fill,r=24,outline=None,width=1):
 ImageDraw.Draw(im).rounded_rectangle(box,r,fill=fill,outline=outline,width=width)
def paste(im,asset,box):
 x,y,w,h=box;src=asset.convert('RGBA');src.thumbnail((w,h),Image.Resampling.LANCZOS)
 im.alpha_composite(src,(round(x+(w-src.width)/2),round(y+(h-src.height)/2)))
def glow(im,center,radius,color,alpha=85):
 layer=Image.new('RGBA',im.size);d=ImageDraw.Draw(layer);x,y=center
 for r in range(radius,0,-4):
  a=round(alpha*(1-r/radius)**2);d.ellipse((x-r,y-r,x+r,y+r),fill=(*color,a))
 im.alpha_composite(layer.filter(ImageFilter.GaussianBlur(8)))
def finish(im,path,radius=28):
 mask=Image.new('L',im.size)
 ImageDraw.Draw(mask).rounded_rectangle((0,0,im.width-1,im.height-1),radius,fill=255)
 im.putalpha(mask);im.save(path,optimize=True)
def brand(im,assets,dark=False,mobile=False):
 x,y=(42,29) if mobile else (60,36);w,h=(409,82) if mobile else (462,96)
 if dark:rr(im,(x,y,x+w,y+h),PAPER,20)
 text(im,x+19,y+27,'{一起 Vibe}',29 if mobile else 33,INK,True)
 text(im,x+(185 if mobile else 218),y+29,'×',25,'#928b9c')
 paste(im,assets['logo'],(x+(223 if mobile else 258),y+2,175 if mobile else 190,h-4))
def stage_art(im,assets,c,box,mobile=False):
 x,y,w,h=map(int,box);p=Image.new('RGBA',(w,h),c['panel']);dark=c['number']=='02'
 glow(p,(int(w*.72),int(h*.40)),int(w*.70),(152,114,247),110 if dark else 52)
 glow(p,(int(w*.91),int(h*.96)),int(w*.42),(243,169,197),72);d=ImageDraw.Draw(p)
 if dark:
  d.rounded_rectangle((int(w*.09),int(h*.13),int(w*.86),int(h*.82)),radius=26,outline='#82709e',width=2)
  for i in range(3):d.ellipse((int(w*.15)+i*18,int(h*.20),int(w*.15)+i*18+6,int(h*.20)+6),fill='#8f81a2')
  text(p,int(w*.13),int(h*.29),'</>',43,'#bca9e8',True)
  text(p,int(w*.13),int(h*.40),'YOUR NEXT',16,'#b1a7c1');text(p,int(w*.13),int(h*.47),'BIG IDEA.',16,'#b1a7c1')
 else:
  rr(p,(int(w*.08),int(h*.10),int(w*.43),int(h*.73)),PAPER,18,outline='#d9d1e9')
  text(p,int(w*.12),int(h*.16),'SOURCE / 01',14,'#8c7aaa')
  text(p,int(w*.12),int(h*.27),'一个发现',24,INK,True);text(p,int(w*.12),int(h*.35),'一段故事',24,INK,True)
  for i in range(4):d.line((int(w*.12),int(h*.48)+i*17,int(w*.33)-(i%2)*20,int(h*.48)+i*17),fill='#d5cddd',width=4)
 size=min(round(w*.83),round(h*1.08));cat=assets['cat'].resize((size,size),Image.Resampling.LANCZOS)
 p.alpha_composite(cat,(w-size+25,h-size+25))
 # Conceptual track: not a real screenshot or generated video.
 by=h-64;rr(p,(int(w*.09),by,w-int(w*.08),h-19),'#272235',18);d=ImageDraw.Draw(p);px=int(w*.14)
 d.polygon([(px,by+14),(px,by+33),(px+15,by+23)],fill='#d6c5ff')
 phrase='把内容，讲给人听。' if not dark else '把作品，带到观众眼前。'
 text(p,px+32,by+12,phrase,21,'#f1ecfa',True,max_width=w-px-62)
 mask=Image.new('L',(w,h));ImageDraw.Draw(mask).rounded_rectangle((0,0,w,h),36,fill=255);im.paste(p,(x,y),mask)
def hero(out,assets,c,mobile=False):
 W,H=(800,1120) if mobile else (1600,840);im=Image.new('RGBA',(W,H),c['bg']);d=ImageDraw.Draw(im)
 brand(im,assets,c['number']=='02',mobile)
 if mobile:
  text(im,648,55,c['number']+' /',30,c['accent'],True);d.line((45,133,755,133),fill=c['line'],width=1)
  text(im,49,167,c['tag'],25,c['accent'],True,max_width=700)
  text(im,42,233,c['title'][0],80,c['fg'],True,max_width=720);text(im,42,335,c['title'][1],80,c['fg'],True,max_width=720)
  text(im,49,453,c['sub'][0],29,c['muted'],max_width=708);text(im,49,501,c['sub'][1],29,c['muted'],max_width=708)
  stage_art(im,assets,c,(45,570,710,444),True)
  text(im,48,1056,'真实素材  /  镜头叙事  /  多画幅交付',25,c['muted'],max_width=704)
 else:
  text(im,1130,75,c['number']+' / '+c['en'],19,c['muted'],max_width=420);d.line((65,155,1535,155),fill=c['line'],width=1)
  text(im,70,218,c['tag'],26,c['accent'],True,max_width=760)
  text(im,61,291,c['title'][0],94,c['fg'],True,max_width=790);text(im,61,411,c['title'][1],94,c['fg'],True,max_width=790)
  text(im,72,558,c['sub'][0]+c['sub'][1],25,c['muted'],max_width=770)
  for i,s in enumerate(('真实素材','镜头叙事','多画幅交付')):
   x=70+i*188;rr(im,(x,630,x+164,681),c['panel'],25,outline=c['line']);text(im,x+22,644,s,23,c['accent'],True,max_width=145)
  stage_art(im,assets,c,(875,206,658,506));d.line((65,750,1535,750),fill=c['line'])
  text(im,70,780,'OPEN WORKFLOW. HUMAN DIRECTION.',18,c['muted'])
  right='文章 · 资讯 · 观点 · 案例' if c['number']=='01' else '网站 · APP · 工具 · 小游戏'
  text(im,1125,777,right,22,c['muted'],max_width=420)
 finish(im,out/('hero-mobile.png' if mobile else 'hero.png'))
def workflow(out,assets,c,mobile=False):
 W,H=(800,745) if mobile else (1600,320);im=Image.new('RGBA',(W,H),c['bg']);d=ImageDraw.Draw(im)
 text(im,44 if mobile else 55,35,c['number']+' / THE CREATIVE WORKFLOW',22,c['accent'],True)
 if mobile:
  d.line((77,139,77,632),fill=c['line'],width=2)
  for i,(s,t) in enumerate(zip(c['stages'],c['meta'])):
   y=115+i*116;rr(im,(45,y,109,y+64),c['panel'],32,outline=c['line']);text(im,60,y+17,f'{i+1:02}',24,c['accent'],True)
   text(im,140,y,s,33,c['fg'],True);text(im,140,y+48,t,27,c['muted'])
  text(im,45,695,'脚本与实际样片，先确认，再推进。',25,c['muted'])
 else:
  for i,(s,t) in enumerate(zip(c['stages'],c['meta'])):
   x=55+i*306;rr(im,(x,102,x+50,152),c['panel'],25,outline=c['line']);text(im,x+10,115,f'{i+1:02}',21,c['accent'],True)
   if i<4:d.line((x+66,127,x+286,127),fill=c['line'],width=2)
   text(im,x,185,s,35,c['fg'],True);text(im,x,240,t,24,c['muted'])
 finish(im,out/('workflow-mobile.png' if mobile else 'workflow.png'))
def case(out,assets,c,mobile=False):
 W,H=(800,520) if mobile else (1600,330);im=Image.new('RGBA',(W,H),'#eae5f5');d=ImageDraw.Draw(im)
 text(im,44,34,'THE MAKING OF / 历史作品复盘',23,'#78648f')
 if mobile:
  text(im,35,99,'38',140,'#42314d',True);text(im,233,201,'个案例',31,'#766284')
  text(im,44,290,'把一堆素材，',42,'#352b41',True);text(im,44,350,'讲成一段值得看的故事。',42,'#352b41',True,max_width=710)
  text(im,44,443,'素材分组  /  叙事顺序  /  音画对应',25,'#7f6a8d')
 else:
  text(im,35,88,'38',166,'#42314d',True);text(im,266,222,'个案例',30,'#766284');d.line((432,101,432,282),fill='#cfc1de',width=2)
  text(im,492,116,'把一堆素材，讲成一段值得看的故事。',47,'#352b41',True,max_width=1070)
  text(im,497,206,'素材分组  /  叙事顺序  /  音画对应',27,'#7f6a8d');text(im,497,270,'方法来源：{一起 Vibe} 的历史制作流程',21,'#7f6a8d')
 finish(im,out/('case-mobile.png' if mobile else 'case.png'))
def family(out,assets,c,mobile=False):
 W,H=(800,288) if mobile else (1600,245);im=Image.new('RGBA',(W,H),PAPER);paste(im,assets['icon'],(37,43,103,90))
 if mobile:
  text(im,162,54,'两套 Skill，一起创作。',34,INK,True,max_width=590);text(im,48,167,'内容转短视频  /  作品做宣传',29,'#796589')
  text(im,48,225,'{一起 Vibe} × 秒悟 Meoo',24,'#8d8398')
 else:
  text(im,175,62,'两套 Skill，一起把创意讲出来。',46,INK,True,max_width=1370);text(im,179,146,'内容转短视频  /  作品做宣传',29,'#796589')
  text(im,1190,161,'{一起 Vibe} × Meoo',23,'#8d8398',max_width=370)
 finish(im,out/('family-mobile.png' if mobile else 'family.png'))
def main():
 global FONT
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--profile',choices=CONFIG,required=True)
 p.add_argument('--assets',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--font-dir',type=Path,default=FONT)
 a=p.parse_args();FONT=a.font_dir;a.output.mkdir(parents=True,exist_ok=True)
 logo=Image.open(a.assets/'meoo-logo.png').convert('RGBA');icon=Image.open(a.assets/'meoo-icon.png').convert('RGBA')
 src=a.assets/'meoo-mascot.gif'
 if not src.exists():src=a.assets/'meoo-mascot-poster.png'
 gif=Image.open(src);gif.seek(0);cat=gif.convert('RGBA');cat.save(a.assets/'meoo-mascot-poster.png',optimize=True)
 assets=dict(logo=logo,icon=icon,cat=cat)
 for builder in (hero,workflow,case,family):
  for mobile in (False,True):builder(a.output,assets,CONFIG[a.profile],mobile)
 entries=[]
 for f in sorted(a.output.glob('*.png')):
  with Image.open(f) as im:im.verify()
  entries.append(dict(path=f.name,bytes=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest()))
 (a.output/'manifest.json').write_text(json.dumps(dict(profile=a.profile,files=entries),indent=2)+'\n');print(json.dumps(entries,indent=2))
if __name__=='__main__':main()
