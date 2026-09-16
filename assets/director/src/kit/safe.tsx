/** Measured text + shared frame zones. Animation must stay inside its allocation. */
import React,{createContext,useContext,useLayoutEffect,useRef} from 'react';
import {delayRender,continueRender,cancelRender} from 'remotion';
import type {Format} from '../types';
import type {Rect} from './core';
import {useTheme} from './core';
import {layoutFor} from './layout-engine.mjs';
import type {LayoutOptions} from './layout-engine.mjs';
import {fitElement} from './dom-qa.mjs';
const LayoutContext=createContext<Partial<Record<Format,LayoutOptions>>>({});
export const FrameLayoutProvider:React.FC<{options?:Partial<Record<Format,LayoutOptions>>;children:React.ReactNode}>=({options,children})=><LayoutContext.Provider value={options??{}}>{children}</LayoutContext.Provider>;
export const useFrameLayout=(format:Format)=>layoutFor(format,useContext(LayoutContext)[format]);
export const rectStyle=(r:Rect):React.CSSProperties=>({position:'absolute',left:r.x,top:r.y,width:r.w,height:r.h,boxSizing:'border-box'});
export const SafeBox:React.FC<{id:string;r:Rect;role?:'body'|'media'|'note'|'background';overlapReason?:string;style?:React.CSSProperties;children?:React.ReactNode}>=({id,r,role='body',overlapReason,style,children})=><div data-qa-block={id} data-qa-role={role} data-qa-allow-overlap={overlapReason} style={{...rectStyle(r),...style}}>{children}</div>;
export const SafeText:React.FC<{id:string;format:Format;r:Rect;text:string;role?:'title'|'body'|'caption'|'note';maxFont?:number;maxLines?:number;lineHeight?:number;style?:React.CSSProperties;children?:React.ReactNode}>=({id,format,r,text,role='body',maxFont,maxLines=2,lineHeight=1.16,style,children})=>{
 const l=useFrameLayout(format),{fonts}=useTheme(),ref=useRef<HTMLDivElement>(null);
 const min=l.min[role];const max=Math.max(min,maxFont??(role==='title'?min+28:min+8));
 // Every content/geometry change gets its own blocking handle; no stale continued handles.
 useLayoutEffect(()=>{const handle=delayRender('fit '+id);let alive=true;document.fonts.ready.then(()=>{if(!alive)return;try{if(ref.current)fitElement(ref.current,{minFont:min,maxFont:max,maxLines,lineHeight});continueRender(handle);}catch(e){cancelRender(e instanceof Error?e:new Error(String(e)));}});return()=>{alive=false;continueRender(handle);};},[id,text,r.w,r.h,min,max,maxLines,lineHeight,fonts.body,fonts.display]);
 return <div ref={ref} data-qa-block={id} data-qa-role={role} data-qa-text="true" style={{...rectStyle(r),fontFamily:role==='title'?fonts.display:fonts.body,fontWeight:role==='title'?700:600,fontSize:max,lineHeight,whiteSpace:'pre-wrap',overflowWrap:'anywhere',wordBreak:'normal',...style}}><span data-qa-text-inner="true" style={{display:'block',width:'100%'}}>{children??text}</span></div>;
};
