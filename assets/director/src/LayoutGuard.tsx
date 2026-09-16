/** Per-rendered-frame DOM guard. Detects instrumented geometry errors; never claims to understand a screenshot or media pixels. */
import React,{useLayoutEffect} from 'react';
import {useCurrentFrame,delayRender,continueRender,cancelRender} from 'remotion';
import type {Format} from './types';
import {useFrameLayout} from './kit/safe';
import {inspectLayout} from './kit/dom-qa.mjs';
export const LayoutGuard:React.FC<{format:Format;strict?:boolean;receiptToken?:string}>=({format,strict=true,receiptToken})=>{
 const frame=useCurrentFrame();const layout=useFrameLayout(format);
 useLayoutEffect(()=>{
   const handle=delayRender('layout-guard '+frame);let cancelled=false;
   const finish=()=>{if(cancelled)return;try{
     const root=document.querySelector<HTMLElement>('[data-qa-root]');
     if(!root)throw new Error('Missing QA root');
     const report=inspectLayout(root,layout);
     if(!report.ok){const message=`Layout QA ${format} frame ${frame}: ${JSON.stringify(report.findings)}`;if(strict)throw new Error(message);console.warn(message);}
     if(report.ok&&strict&&receiptToken)console.log('VIDEO_SKILL_LAYOUT_OK:'+JSON.stringify({ok:true,frame,format,token:receiptToken}));
     continueRender(handle);
   }catch(e){if(strict)cancelRender(e instanceof Error?e:new Error(String(e)));else continueRender(handle);}};
   document.fonts.ready.then(()=>requestAnimationFrame(()=>requestAnimationFrame(finish)));
   return()=>{cancelled=true;continueRender(handle);};
 },[frame,format,strict,receiptToken,JSON.stringify(layout)]);
 return null;
};
