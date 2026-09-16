/** Browser-only measurement, not visual understanding. Imported by the real Film and browser regression tests. */
import {contains,intersect} from './layout-engine.mjs';
export function effectiveOpacity(el,root){
  let o=1;
  for(let n=el;n&&n!==root.parentElement;n=n.parentElement){const s=getComputedStyle(n);if(s.display==='none'||s.visibility==='hidden')return 0;o*=Number(s.opacity);}
  return o;
}
export function measureRect(el,root,width){
  const a=el.getBoundingClientRect(),b=root.getBoundingClientRect(),scale=b.width/width;
  return {x:(a.x-b.x)/scale,y:(a.y-b.y)/scale,w:a.width/scale,h:a.height/scale};
}
export function fitElement(el,{minFont,maxFont,maxLines=2,lineHeight=1.16}){
  if(!Number.isFinite(minFont)||!Number.isFinite(maxFont)||maxFont<minFont||maxLines<1)throw new Error('Invalid text bounds');
  const fits=(size)=>{el.style.fontSize=size+'px';el.style.lineHeight=String(lineHeight);return el.scrollWidth<=el.clientWidth+1 && el.scrollHeight<=el.clientHeight+1 && el.scrollHeight<=size*lineHeight*maxLines+2;};
  // In a fixed-height element scrollHeight is at least clientHeight. Use a natural-height inner text span to measure line count.
  const inner=el.querySelector('[data-qa-text-inner]');
  const check=(size)=>{
    el.style.fontSize=size+'px';el.style.lineHeight=String(lineHeight);
    if(!inner)return fits(size);
    const r=inner.getBoundingClientRect();
    const scale=el.getBoundingClientRect().width/Math.max(1,el.clientWidth);
    return el.scrollHeight<=el.clientHeight+1 && el.scrollWidth<=el.clientWidth+1 && inner.scrollWidth<=el.clientWidth+1 && r.height/scale<=el.clientHeight+1 && r.height/scale<=size*lineHeight*maxLines+2;
  };
  if(!check(minFont))throw new Error(`Text cannot fit at minimum ${minFont}px: ${el.textContent?.slice(0,100)}. Shorten, split the shot, or recompose.`);
  let lo=Math.ceil(minFont),hi=Math.floor(maxFont),best=lo;
  while(lo<=hi){const mid=(lo+hi)>>1;if(check(mid)){best=mid;lo=mid+1}else hi=mid-1;}
  check(best);el.dataset.qaFitted='true';return best;
}
export function inspectLayout(root,layout){
  const findings=[];const blocks=[...root.querySelectorAll('[data-qa-block]')].filter(el=>effectiveOpacity(el,root)>.08&&el.getBoundingClientRect().width>0);
  const visibleShots=[...root.querySelectorAll('[data-qa-shot]')].filter(el=>effectiveOpacity(el,root)>.08);
  for(const shot of visibleShots)if(!blocks.some(el=>shot.contains(el)))findings.push({kind:'uninstrumented-shot',id:shot.dataset.qaShot});
  const rows=blocks.map(el=>({el,id:el.dataset.qaBlock,role:el.dataset.qaRole??'body',r:measureRect(el,root,layout.w),shot:el.closest('[data-qa-shot]')?.getAttribute('data-qa-shot')}));
  for(const row of rows){
    if(row.role==='background'&&!(row.el.dataset.qaAllowOverlap?.trim().length>=12))findings.push({kind:'undeclared-background-overlap',id:row.id});
    const region=row.role==='background'?{x:0,y:0,w:layout.w,h:layout.h}:row.role==='caption'?layout.caption:row.role==='title'?layout.title:row.role==='note'?layout.safe:layout.content;
    if(!contains(region,row.r,2))findings.push({kind:'outside-region',id:row.id,role:row.role,rect:row.r,allowed:region});
    if(row.el.dataset.qaText!==undefined){
      const size=parseFloat(getComputedStyle(row.el).fontSize),min=layout.min[row.role]??layout.min.body;
      if(size<min-.1)findings.push({kind:'small-type',id:row.id,size,min});
      if(row.el.scrollWidth>row.el.clientWidth+1||row.el.scrollHeight>row.el.clientHeight+1)findings.push({kind:'text-overflow',id:row.id});
    }
  }
  for(let i=0;i<rows.length;i++)for(let j=i+1;j<rows.length;j++){
    const a=rows[i],b=rows[j];
    if(a.el.contains(b.el)||b.el.contains(a.el))continue;
    // A crossfade can overlay two complete shots. It does not permit either shot to invade subtitles.
    if(a.shot&&b.shot&&a.shot!==b.shot)continue;
    const why=a.el.dataset.qaAllowOverlap??b.el.dataset.qaAllowOverlap;
    if(why&&why.trim().length>=12)continue;
    if(intersect(a.r,b.r)>6)findings.push({kind:'overlap',a:a.id,b:b.id,area:intersect(a.r,b.r)});
  }
  // Catch legacy/unmarked text leaking into the caption band or outside the frame.
  const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);let node;
  while((node=walker.nextNode())){
    if(!node.textContent.trim())continue;const el=node.parentElement;
    if(!el||el.closest('[data-qa-ignore]')||el.closest('[data-qa-role="caption"]')||effectiveOpacity(el,root)<=.08)continue;
    const range=document.createRange();range.selectNodeContents(node);
    const rootRect=root.getBoundingClientRect(),scale=rootRect.width/layout.w;
    for(const rr of range.getClientRects()){
      const r={x:(rr.x-rootRect.x)/scale,y:(rr.y-rootRect.y)/scale,w:rr.width/scale,h:rr.height/scale};
      if(!contains({x:0,y:0,w:layout.w,h:layout.h},r,2))findings.push({kind:'text-outside-frame',text:node.textContent.slice(0,60)});
      if(intersect(r,layout.caption)>6)findings.push({kind:'text-in-caption-band',text:node.textContent.slice(0,60)});
    }
  }
  return {ok:findings.length===0,blocks:rows.map(({el,...r})=>r),findings};
}
