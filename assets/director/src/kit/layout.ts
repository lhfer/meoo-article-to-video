/** Backward-compatible geometry helpers. New shots should use useFrameLayout() so custom insets reach every layer. */
import type {Format} from '../types';
import type {Rect} from './core';
import {layoutFor,MIN_TEXT} from './layout-engine.mjs';
export {MIN_TEXT,layoutFor};
export type StageBox={w:number;h:number;cx:number;cy:number;top:number;bottom:number;captionTop:number;gutter:number};
export const stage=(format:Format):StageBox=>{const l=layoutFor(format);return {w:l.w,h:l.h,cx:l.w/2,cy:l.h/2,top:l.safe.y,bottom:l.content.y+l.content.h,captionTop:l.caption.y,gutter:l.safe.x};};
export const STAGE:Record<Format,StageBox>={'3x4':stage('3x4'),'9x16':stage('9x16'),'16x9':stage('16x9')};
export type Platform='douyin'|'xiaohongshu'|'bilibili'|'wechat-channels'|'generic';
export const safeArea=(format:Format,_platform:Platform='generic'):Rect=>layoutFor(format).safe;
export const subjectArea=(format:Format):Rect=>layoutFor(format).content;
export const columns=(format:Format,subjectShare=.62,gap=32,subjectLeft=true):{subject:Rect;side:Rect}=>{
 const l=layoutFor(format,{subjectShare,gap});
 if(format==='16x9'&&!subjectLeft)return {subject:{...l.subject,x:l.content.x+l.side.w+gap},side:{...l.side,x:l.content.x}};
 return {subject:l.subject,side:l.side};
};
