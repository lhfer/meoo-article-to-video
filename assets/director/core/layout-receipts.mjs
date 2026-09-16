/** Pure contract for browser-emitted geometry receipts. Never treats missing checks as success. */
export const MARKER='VIDEO_SKILL_LAYOUT_OK:';
export function collectLayoutReceipt(log,token,format,seen){
  const text=typeof log==='string'?log:log?.text;
  if(typeof text!=='string'||!text.startsWith(MARKER))return false;
  let row;try{row=JSON.parse(text.slice(MARKER.length));}catch{return false;}
  if(row.token!==token||row.format!==format||row.ok!==true||!Number.isInteger(row.frame)||row.frame<0)return false;
  seen.add(row.frame);return true;
}
export function verifyCoverage(seen,start,end){
  if(!Number.isInteger(start)||!Number.isInteger(end)||start<0||end<start)throw new Error('Invalid render range');
  const missing=[];for(let f=start;f<=end;f++)if(!seen.has(f))missing.push(f);
  if(missing.length)throw new Error(`Missing strict layout checks on ${missing.length} rendered frames (first: ${missing.slice(0,12).join(', ')}). Do not remove the guard or manufacture receipts.`);
  return {strict:true,checkedFrames:end-start+1,frameRange:[start,end],scope:'Actual browser DOM geometry; not raster-image understanding or human visual review'};
}
