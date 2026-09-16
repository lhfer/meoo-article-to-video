/** Single source of geometry; pure and independently testable. These are house margins, NOT platform guarantees. */
export const FORMATS = {'3x4':{w:1080,h:1440},'9x16':{w:1080,h:1920},'16x9':{w:1920,h:1080}};
export const MIN_TEXT = {'3x4':{title:64,body:40,caption:48,note:24},'9x16':{title:72,body:44,caption:52,note:26},'16x9':{title:60,body:34,caption:44,note:24}};
const DEFAULT_INSETS = {'3x4':{top:80,right:64,bottom:170,left:64},'9x16':{top:140,right:150,bottom:300,left:66},'16x9':{top:64,right:84,bottom:64,left:84}};
export const intersect = (a,b) => Math.max(0,Math.min(a.x+a.w,b.x+b.w)-Math.max(a.x,b.x))*Math.max(0,Math.min(a.y+a.h,b.y+b.h)-Math.max(a.y,b.y));
export const contains = (a,b,tolerance=1) => b.x>=a.x-tolerance && b.y>=a.y-tolerance && b.x+b.w<=a.x+a.w+tolerance && b.y+b.h<=a.y+a.h+tolerance;
export function layoutFor(format, options={}) {
  const dim=FORMATS[format]; if(!dim) throw new Error('Unknown format '+format);
  const inset={...DEFAULT_INSETS[format],...(options.insets??{})};
  if(Object.values(inset).some(v=>!Number.isFinite(v)||v<0)) throw new Error('Insets must be finite nonnegative pixels');
  const safe={x:inset.left,y:inset.top,w:dim.w-inset.left-inset.right,h:dim.h-inset.top-inset.bottom};
  if(safe.w<400||safe.h<500) throw new Error('Safe area too small; recompose rather than scale everything down');
  const min=MIN_TEXT[format]; const gap=options.gap??32;
  const titleH=options.titleHeight??Math.ceil(min.title*1.16*2+32);
  const captionFont=Math.max(min.caption,options.captionFont??min.caption);
  const captionH=Math.ceil(captionFont*1.28*2+44);
  if(!Number.isFinite(gap)||gap<16||!Number.isFinite(titleH)||titleH<min.title*1.16||!Number.isFinite(captionFont))throw new Error('Invalid title/caption/gap geometry');
  const title={x:safe.x,y:safe.y,w:safe.w,h:titleH};
  const caption={x:safe.x,y:safe.y+safe.h-captionH,w:safe.w,h:captionH};
  const content={x:safe.x,y:title.y+title.h+gap,w:safe.w,h:caption.y-gap-(title.y+title.h+gap)};
  if(content.h<240) throw new Error('Title and captions leave insufficient subject space');
  const share=options.subjectShare??0.62;
  if(!Number.isFinite(share)||share<0.50||share>0.8)throw new Error('subjectShare must be 0.50..0.80');
  let subject,side;
  if(format==='16x9'){
    const sw=Math.floor((content.w-gap)*share);
    subject={x:content.x,y:content.y,w:sw,h:content.h};
    side={x:content.x+sw+gap,y:content.y,w:content.w-sw-gap,h:content.h};
  }else{
    const sh=Math.floor((content.h-gap)*share);
    subject={x:content.x,y:content.y,w:content.w,h:sh};
    side={x:content.x,y:content.y+sh+gap,w:content.w,h:content.h-sh-gap};
  }
  return {format,...dim,safe,title,content,caption,subject,side,min,gap,captionFont};
}
