import type {FrameLayout,Rect} from './layout-engine.mjs';
export function effectiveOpacity(el:Element,root:Element):number;
export function measureRect(el:Element,root:Element,width:number):Rect;
export function fitElement(el:HTMLElement,options:{minFont:number;maxFont:number;maxLines?:number;lineHeight?:number}):number;
export function inspectLayout(root:HTMLElement,layout:FrameLayout):{ok:boolean;blocks:unknown[];findings:Array<Record<string,unknown>>};
