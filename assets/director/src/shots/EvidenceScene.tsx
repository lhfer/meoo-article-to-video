/** Executable evidence-first layout, not a finished video or a fabricated product demo.
 * props: title, media (registered asset id), mediaKind ('video'|'image'), steps (3 short strings), notes (3 short strings).
 * Author a bespoke scene for the subject. Keep the geometry/measurement primitives, not this exact composition.
 */
import {AbsoluteFill,Img,staticFile,useCurrentFrame,interpolate} from 'remotion';
import {Video} from '@remotion/media';
import type {ShotProps} from '../types';
import {SafeBox,SafeText,useFrameLayout} from '../kit/safe';
import {useTheme} from '../kit/core';
export default function EvidenceScene(props:ShotProps & {mode?:'product'|'news'}){
 const {format,shot,asset,mode='news'}=props,frame=useCurrentFrame(),l=useFrameLayout(format),{palette}=useTheme();
 const cfg=shot.props??{};const phase=Math.min(2,Math.floor(frame/(shot.durationFrames/3)));
 const titles=Array.isArray(cfg.steps)?cfg.steps as string[]:['先看真实画面','再解释关键一步','最后说清楚边界'];
 const notes=Array.isArray(cfg.notes)?cfg.notes as string[]:['不要让文字卡片替代证据。','画面和这句旁白说同一件事。','演示、概念图和推断分开标明。'];
 const title=typeof cfg.title==='string'?cfg.title:(mode==='product'?'先看结果，再讲过程':'让观众看见你的证据');
 const id=typeof cfg.media==='string'?cfg.media:null;
 const r={x:l.subject.x+12,y:l.subject.y+12,w:l.subject.w-24,h:l.subject.h-24};
 const side={x:l.side.x+12,y:l.side.y+12,w:l.side.w-24,h:l.side.h-24};
 const lift=interpolate(frame,[0,16],[8,0],{extrapolateRight:'clamp'});
 const ink=mode==='product'?'#15171c':'#f5f5f3',muted=mode==='product'?'#4a4f59':'#c2c5cb';
 return <AbsoluteFill style={{background:mode==='product'?'#f5f5f2':'#101216'}}>
   <SafeText id="headline" format={format} r={{x:l.title.x+8,y:l.title.y+8,w:l.title.w-16,h:l.title.h-16}} text={title} role="title" maxFont={l.min.title+20} maxLines={2} style={{color:ink}}/>
   <SafeBox id="evidence" r={r} role="media" style={{borderRadius:24,overflow:'hidden',background:mode==='product'?'#e7e8e6':'#20232a',border:`1px solid ${mode==='product'?'#d4d5d4':'#40444d'}`,transform:`translateY(${lift}px)`}}>
     {id?(cfg.mediaKind==='video'?<Video src={staticFile(asset(id))} muted style={{width:'100%',height:'100%',objectFit:'contain'}}/>:<Img src={staticFile(asset(id))} style={{width:'100%',height:'100%',objectFit:'contain'}}/>):<>
       <div aria-hidden="true" style={{position:'absolute',left:'12%',right:'12%',top:'22%',height:'46%',display:'flex',alignItems:'end',gap:20}}>{[.45,.72,.92].map((v,i)=><div key={i} style={{flex:1,height:`${v*100}%`,background:palette.accent,opacity:i===phase ? .95 : .25,borderRadius:12}}/>)}</div>
       <SafeText id="placeholder-label" format={format} r={{x:24,y:r.h-72,w:r.w-48,h:48}} role="note" maxFont={l.min.note} maxLines={1} text="布局示例 · 不是产品实测" style={{color:muted,textAlign:'center'}}/>
     </>}
   </SafeBox>
   <SafeBox id="explanation-panel" r={side} style={{background:mode==='product'?'#fff':'#1c1f25',borderRadius:24}}>
     <SafeText key={`step-${phase}`} id="step" format={format} r={{x:24,y:24,w:side.w-48,h:Math.ceil(l.min.body*1.2*2+8)}} text={titles[phase]??titles[0]} maxFont={l.min.body+6} maxLines={2} style={{color:ink}}/>
     <SafeText key={`note-${phase}`} id="explanation" format={format} r={{x:24,y:Math.ceil(l.min.body*1.2*2+48),w:side.w-48,h:side.h-Math.ceil(l.min.body*1.2*2+72)}} text={notes[phase]??notes[0]} maxFont={l.min.body} maxLines={format==='16x9'?5:3} lineHeight={1.22} style={{color:muted,fontWeight:500}}/>
     <div aria-hidden="true" style={{position:'absolute',left:24,right:24,bottom:10,height:3,background:mode==='product'?'#e4e5e6':'#383d46'}}><div style={{height:'100%',width:`${Math.min(100,frame/Math.max(1,shot.durationFrames-1)*100)}%`,background:palette.accent}}/></div>
   </SafeBox>
 </AbsoluteFill>;
}
