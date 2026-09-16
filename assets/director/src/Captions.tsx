import React from 'react';
import {useCurrentFrame} from 'remotion';
import type {Caption,Format} from './types';
import {SafeText,useFrameLayout} from './kit/safe';
type LayoutCfg={bottom?:number;fontSize?:number;maxWidth?:number|string;color?:string;background?:string;highlightColor?:string;dimColor?:string;fontWeight?:number;lineHeight?:number};
export type CaptionStyle={enabled?:boolean;style?:'block'|'karaoke';layouts?:Partial<Record<Format,LayoutCfg>>};
export const Captions:React.FC<{format:Format;captions:Caption[];style:CaptionStyle}>=({format,captions,style})=>{
 const frame=useCurrentFrame(),l=useFrameLayout(format);if(style.enabled===false)return null;
 const active=captions.filter(c=>frame>=c.from&&frame<c.end);
 if(active.length>1)throw new Error('Overlapping caption intervals at frame '+frame);
 const cfg=style.layouts?.[format]??{};
 // caption bottom/width are deliberately not independent knobs: all layers use film.style.layout[format].
 return <>{active.map(c=><SafeText key={`${c.from}-${c.end}-${c.text}`} id="captions" format={format} r={{x:l.caption.x+22,y:l.caption.y+10,w:l.caption.w-44,h:l.caption.h-20}} text={c.text} role="caption" maxFont={Math.max(l.min.caption,cfg.fontSize??l.captionFont)} maxLines={2} lineHeight={1.28} style={{textAlign:'center',color:cfg.color??'#fff',display:'flex',alignItems:'center',fontWeight:cfg.fontWeight??600}}>
 <span style={{background:cfg.background??'rgba(0,0,0,.78)',padding:'4px 12px',borderRadius:10,boxDecorationBreak:'clone',WebkitBoxDecorationBreak:'clone'}}>{style.style==='karaoke'&&c.words?.length?renderKaraoke(c,frame,cfg):c.text}</span>
 </SafeText>)}</>;
};
function renderKaraoke(c:Caption,frame:number,cfg:LayoutCfg){
 const starts:number[]=[];for(const w of c.words??[])for(let i=0;i<w.text.replace(/[^\p{L}\p{N}]/gu,'').length;i++)starts.push(w.from);
 let index=0,last=c.from;
 return Array.from(c.text).map((ch,i)=>{if(/[\p{L}\p{N}]/u.test(ch)){last=starts[index]??last;index++;}const lit=frame>=last;return <span key={i} style={{color:lit?(cfg.highlightColor??'#FFD54A'):(cfg.dimColor??cfg.color??'#fff'),opacity:lit?1:.6}}>{ch}</span>;});
}
