import React from 'react';
import {AbsoluteFill,Sequence,staticFile,useCurrentFrame,interpolate} from 'remotion';
import {Audio} from '@remotion/media';
import {loadFont} from '@remotion/fonts';
import raw from '../content/timeline.json';
import {registry} from './registry.generated';
import {Captions} from './Captions';
import {LayoutGuard} from './LayoutGuard';
import {FrameLayoutProvider} from './kit/safe';
import type {LayoutOptions} from './kit/layout-engine.mjs';
import {ThemeProvider} from './kit/core';
import type {CaptionStyle} from './Captions';
import type {Format,Shot,Timeline} from './types';
const data=raw as unknown as Timeline;
for(const font of (data.style.fonts??[]) as Array<{family:string;asset:string;weight?:string}>){
  if(!data.globalAssets.includes(font.asset)||!data.assets[font.asset])throw new Error('Register font asset in globalAssets: '+font.asset);
  loadFont({family:font.family,url:staticFile(data.assets[font.asset].src),weight:font.weight??'400'});
}

const ShotLayer:React.FC<{shot:Shot;format:Format}>=({shot,format})=>{
  const frame=useCurrentFrame();const Component=registry[shot.component];
  if(!Component)throw new Error(`Missing component ${shot.component}`);
  const opacity=shot.transitionIn.type==='fade'&&shot.transitionIn.frames>0?interpolate(frame,[0,shot.transitionIn.frames],[0,1],{extrapolateRight:'clamp'}):1;
  return <AbsoluteFill data-qa-shot={shot.id} style={{opacity}}><Component shot={shot} format={format} layout={shot.layouts[format]} events={data.events} style={data.style} asset={(id)=>{
    if(!(shot.assets??[]).includes(id)&&!data.globalAssets.includes(id))throw new Error('Declare the asset on this shot: '+id);
    if(!data.assets[id])throw new Error('Unknown asset '+id);return data.assets[id].src;
  }} cue={(name)=>{
    const e=(data.events as Record<string,number>)[name];if(e===undefined)throw new Error(`Unknown cue ${name}`);return e-shot.from;
  }}/></AbsoluteFill>;
};

// noMusic renders the 干声版 (voice + shots, no film.audio beds) for creators who add a platform BGM in-app; passed via `remotion render --props`.
export const Film:React.FC<{format:Format;noMusic?:boolean;strictLayout?:boolean;layoutReceiptToken?:string}>=({format,noMusic,strictLayout=true,layoutReceiptToken})=><ThemeProvider style={data.style}><FrameLayoutProvider options={data.style.layout as Partial<Record<Format,LayoutOptions>>}><AbsoluteFill data-qa-root="true" style={{background:(data.style as Record<string,string>).background??'#101217',fontFamily:(data.style as Record<string,string>).fontFamily??'"PingFang SC", "Microsoft YaHei", sans-serif'}}>
  {(data.shots as Shot[]).map(s=><Sequence key={s.id} name={s.id} from={s.from} durationInFrames={s.durationFrames}><ShotLayer shot={s} format={format}/></Sequence>)}
  {data.voices.filter(v=>v.real).map(v=><Sequence key={v.id} from={v.from} durationInFrames={v.durationFrames}><Audio src={staticFile(v.src)} volume={v.gain}/></Sequence>)}
  {(noMusic?[]:data.audio).map((a,i)=><Sequence key={i} from={a.from} durationInFrames={a.durationFrames}><Audio src={staticFile(a.src)} trimBefore={a.trimStart} volume={(f)=>{
    const gain=a.gain;
    const intro=a.fadeIn?Math.min(1,f/a.fadeIn):1;
    const outro=a.fadeOut?Math.min(1,(a.durationFrames-f)/a.fadeOut):1;
    const spec=a as typeof a & {duck?:number};
    const global=f+a.from;
    // A short linear envelope around speech protects words without abrupt gain jumps.
    let speech=0;
    for(const v of data.voices){const attack=9,release=15;const x=Math.min(1,Math.max(0,(global-(v.from-attack))/attack),Math.max(0,(v.from+v.durationFrames+release-global)/release));speech=Math.max(speech,x);}
    return gain*intro*outro*(1-speech*(1-(spec.duck??1)));
  }}/></Sequence>)}
  <Captions format={format} captions={data.captions} style={data.captionStyle as CaptionStyle}/>
  <LayoutGuard format={format} strict={strictLayout} receiptToken={layoutReceiptToken}/>
  {data.draft?<div data-qa-ignore="technical-draft-watermark" style={{position:'absolute',left:30,top:28,padding:'10px 16px',background:'#d63e34',color:'#fff',fontSize:28}}>技术草稿 · 非正式样片</div>:null}
</AbsoluteFill></FrameLayoutProvider></ThemeProvider>;
