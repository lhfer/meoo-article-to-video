import test from 'node:test';import assert from 'node:assert/strict';
import {layoutFor,contains,intersect,MIN_TEXT} from '../assets/director/src/kit/layout-engine.mjs';
import {collectLayoutReceipt,verifyCoverage,MARKER} from '../assets/director/core/layout-receipts.mjs';
for(const format of ['3x4','9x16','16x9']){
 test(`${format}: default zones are disjoint, inside safe frame and readable`,()=>{
  const l=layoutFor(format);for(const r of [l.title,l.subject,l.side,l.caption])assert(contains(l.safe,r));
  const rows=[l.title,l.subject,l.side,l.caption];for(let i=0;i<rows.length;i++)for(let j=i+1;j<rows.length;j++)assert.equal(intersect(rows[i],rows[j]),0);
  assert(l.captionFont>=MIN_TEXT[format].caption);
 });
 test(`${format}: 20 reasonable custom margin/gap combinations remain separated`,()=>{
  for(let n=0;n<20;n++){const l=layoutFor(format,{insets:{top:80+n,bottom:180+n},gap:24+n,subjectShare:.55+n*.006});assert.equal(intersect(l.content,l.caption),0);assert.equal(intersect(l.title,l.content),0);assert(contains(l.safe,l.content));}
 });
}
test('unsafe insets / invalid formats / tiny content / invalid ratio reject',()=>{
 for(const x of [()=>layoutFor('x'),()=>layoutFor('16x9',{insets:{bottom:-1}}),()=>layoutFor('3x4',{insets:{left:1000}}),()=>layoutFor('16x9',{titleHeight:9999}),()=>layoutFor('9x16',{subjectShare:.1}),()=>layoutFor('16x9',{gap:NaN})])assert.throws(x);
});
test('landscape is actually two columns; portrait stacks',()=>{const a=layoutFor('16x9'),b=layoutFor('3x4');assert(a.subject.x+a.subject.w<a.side.x);assert(b.subject.y+b.subject.h<b.side.y);});
test('wrong token, missing frames and bad logs cannot pass checked-render contract',()=>{
 const seen=new Set();for(const log of ['x',MARKER+'bad',MARKER+JSON.stringify({token:'wrong',format:'3x4',ok:true,frame:0})])assert.equal(collectLayoutReceipt(log,'token','3x4',seen),false);
 assert.throws(()=>verifyCoverage(seen,0,2),/Missing/);
 for(let f=0;f<3;f++)assert(collectLayoutReceipt({text:MARKER+JSON.stringify({token:'token',format:'3x4',ok:true,frame:f})},'token','3x4',seen));
 assert.equal(verifyCoverage(seen,0,2).checkedFrames,3);assert.throws(()=>verifyCoverage(seen,0,3));
});
