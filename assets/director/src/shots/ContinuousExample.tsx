// A worked interface example: one continuous subject, three independently composed formats.
// Replace with the current video's own design and content.
import {AbsoluteFill,Easing,interpolate,useCurrentFrame,useVideoConfig} from 'remotion';
import type {ShotProps} from '../types';

export default function ContinuousExample({format,layout,cue}:ShotProps){
  const frame=useCurrentFrame();const {width,height}=useVideoConfig();
  const wide=format==='16x9';const accent='#007d78';
  const connect=interpolate(frame,[cue('connect'),cue('connect')+70],[0,1],{easing:Easing.bezier(.22,1,.36,1),extrapolateLeft:'clamp',extrapolateRight:'clamp'});
  const focus=interpolate(frame,[cue('focus'),cue('focus')+55],[0,1],{easing:Easing.bezier(.22,1,.36,1),extrapolateLeft:'clamp',extrapolateRight:'clamp'});
  const centerX=width*Number(layout.centerX);const centerY=height*Number(layout.centerY);const radius=width*(wide?.15:.26);
  const nodes=[{label:'一段笔记',a:-2.1,x:-.29,y:-.1},{label:'一个案例',a:-.1,x:.25,y:.1},{label:'一张截图',a:1.8,x:-.1,y:.28}];
  const positions=nodes.map(n=>({x:centerX+(1-connect)*n.x*width+connect*Math.cos(n.a)*radius,y:centerY+(1-connect)*n.y*height+connect*Math.sin(n.a)*radius}));
  const title=focus>.65?'让线索，重新连起来。':'收藏之后，\n怎样重新找到？';
  return <AbsoluteFill style={{background:'#f4f3ef',color:'#182220',overflow:'hidden'}}>
    <div style={{position:'absolute',left:width*.075,top:height*Number(layout.titleY),width:wide?width*.38:width*.85}}>
      <div style={{fontSize:25,letterSpacing:5,color:accent,marginBottom:24}}>MOTION STUDY / 01</div>
      <div style={{fontSize:wide?76:78,fontWeight:600,letterSpacing:-3,lineHeight:1.16,whiteSpace:'pre-line'}}>{title}</div>
      <div style={{fontSize:30,color:'#69736c',marginTop:28}}>同一主体 · 连续变化 · 三种构图</div>
    </div>
    <svg width={width} height={height} style={{position:'absolute',inset:0}}>
      {positions.map((p,i)=><path key={i} d={`M${centerX},${centerY} Q${centerX},${p.y} ${p.x},${p.y}`} fill="none" stroke={accent} strokeWidth={4} opacity={connect*.45} pathLength={1} strokeDasharray={1} strokeDashoffset={1-connect}/>)}
    </svg>
    {positions.map((p,i)=><div key={i} style={{position:'absolute',left:p.x-110,top:p.y-72,width:220,height:144,borderRadius:24,background:'#fff',boxShadow:'0 18px 65px rgba(25,56,39,.09)',display:'flex',alignItems:'center',justifyContent:'center',fontSize:32,fontWeight:500,transform:`rotate(${(1-connect)*[-9,7,-4][i]}deg) scale(${1+focus*(i===1?.12:-.08)})`,opacity:1-focus*(i===1?0:.4)}}>{nodes[i].label}</div>)}
    <div style={{position:'absolute',left:centerX-70,top:centerY-70,width:140,height:140,borderRadius:70,background:accent,color:'#fff',display:'flex',alignItems:'center',justifyContent:'center',fontSize:36,opacity:connect,transform:`scale(${.72+.28*connect})`}}>问题</div>
    <div style={{position:'absolute',bottom:height*.045,left:width*.075,color:'#69736c',fontSize:23}}>接口演示 · 具体作品按素材另行创作</div>
  </AbsoluteFill>;
}
