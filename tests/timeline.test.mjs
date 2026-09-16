import test from 'node:test';
import assert from 'node:assert/strict';
import {compile} from '../assets/director/core/compile.mjs';
const layouts={'3x4':{},'9x16':{},'16x9':{}};
function fixture(){return {
  script:{version:3,beats:[{id:'open',narration:'先看结果'}]},
  alignment:{segments:{open:{src:'voice.mp3',durationSeconds:3,reviewed:true,method:'manual',words:[{text:'先看',startMs:120,endMs:800},{text:'结果',startMs:1720,endMs:2450}]}}},
  film:{version:3,fps:30,components:{Scene:'shots/Scene.tsx'},voices:[{id:'open',at:.2}],events:{result:{voice:'open',word:'结果'}},shots:[{id:'a',component:'Scene',start:0,end:2.5,layouts},{id:'b',component:'Scene',start:2,end:4,layouts,transitionIn:{type:'fade',seconds:.5}}],audio:[]}
};}
test('A transition overlap is counted exactly once; voice and actual word cues are independent',()=>{
  const {film,script,alignment}=fixture();const t=compile(film,script,alignment);
  assert.equal(t.durationFrames,120);assert.equal(t.shots[1].from,60);assert.equal(t.voices[0].from,6);assert.equal(t.voices[0].durationFrames,90);assert.equal(t.events.result,58);
  assert.equal(t.captions[0].from,10);assert.equal(t.captions[0].end,30);assert.equal(t.captions[1].from,58);
});
test('Measured authored captions stay unchanged even with real VO',()=>{
  const {film,script,alignment}=fixture();alignment.segments.open.captions=[{text:'先看结果',startMs:140,endMs:2600}];
  const t=compile(film,script,alignment);assert.equal(t.captions.length,1);assert.equal(t.captions[0].startMs,140);assert.equal(t.captions[0].end,84);
});
test('Phrase anchors cross multiple measured words and select the requested occurrence',()=>{
  const {film,script,alignment}=fixture();script.beats[0].narration='看看结果';alignment.segments.open.words=[{text:'看',startMs:0,endMs:500},{text:'看',startMs:600,endMs:900},{text:'结',startMs:1300,endMs:1600},{text:'果',startMs:1700,endMs:2200}];
  film.events={again:{voice:'open',word:'看',occurrence:2},end:{voice:'open',word:'结果',edge:'end'}};
  const t=compile(film,script,alignment);assert.equal(t.events.again,24);assert.equal(t.events.end,72);
});
test('Visual gaps, incomplete transitions and cut-off narration are rejected',()=>{
  const f=fixture();f.film.shots[1].start=3;assert.throws(()=>compile(f.film,f.script,f.alignment),/gap/);
  const g=fixture();g.film.shots[0].end=2.2;assert.throws(()=>compile(g.film,g.script,g.alignment),/coverage/);
  const h=fixture();h.film.shots=h.film.shots.slice(0,1);assert.throws(()=>compile(h.film,h.script,h.alignment),/cut off/);
});
test('Cyclic/unknown cues and unreviewed or changed transcripts are rejected',()=>{
  const f=fixture();f.film.events={x:{event:'y'},y:{event:'x'}};assert.throws(()=>compile(f.film,f.script,f.alignment),/Cyclic/);
  const g=fixture();g.alignment.segments.open.reviewed=false;assert.throws(()=>compile(g.film,g.script,g.alignment),/alignment required/);
  const h=fixture();h.script.beats[0].narration='另一个稿件';assert.throws(()=>compile(h.film,h.script,h.alignment),/differs/);
});
test('Opening scope schedules only its actual audio; full scope requires every approved paragraph',()=>{
  const f=fixture();f.script.beats.push({id:'later',narration:'稍后解释'});f.film.scope='opening';assert.equal(compile(f.film,f.script,f.alignment).scope,'opening');
  f.film.scope='full';assert.throws(()=>compile(f.film,f.script,f.alignment),/unscheduled/);
});
test('Three layouts are required; draft is explicitly separate from production',()=>{
  const f=fixture();f.film.shots[1].layouts={'3x4':{},'9x16':{}};assert.throws(()=>compile(f.film,f.script,f.alignment),/16x9/);
  const g=fixture();g.film.voices[0].draftSeconds=3;g.film.events={result:1.9};const t=compile(g.film,g.script,{}, {draft:true});assert.equal(t.draft,true);assert.equal(t.voices[0].real,false);
});
test('Voice after uses measured end, then all tracks share explicit frames',()=>{
  const f=fixture();f.script.beats.push({id:'next',narration:'明白'});f.alignment.segments.next={src:'next.mp3',durationSeconds:1,reviewed:true,method:'manual',words:[{text:'明白',startMs:100,endMs:900}]};f.film.voices.push({id:'next',at:{after:'open',offset:.3}});f.film.shots[1].end=5;
  const t=compile(f.film,f.script,f.alignment);assert.equal(t.voices[1].from,105);assert.equal(t.durationFrames,150);
});
test('Accidental simultaneous narration and changed approved order are caught',()=>{
  const f=fixture();f.script.beats.push({id:'next',narration:'明白'});f.alignment.segments.next={src:'next.mp3',durationSeconds:1,reviewed:true,method:'manual',words:[{text:'明白',startMs:100,endMs:900}]};
  f.film.voices.push({id:'next',at:1});assert.throws(()=>compile(f.film,f.script,f.alignment),/Overlapping/);
  f.film.voices=[{id:'next',at:0},{id:'open',at:1.2}];f.film.shots[1].end=5;assert.throws(()=>compile(f.film,f.script,f.alignment),/playback order/);
});
test('V4: a formats subset compiles without the missing layout, primaryFormat resolves, version 4 accepted',()=>{
  const f=fixture();f.film.version=4;f.script.version=4;f.film.formats=['3x4','9x16'];f.film.shots[1].layouts={'3x4':{},'9x16':{}};
  const t=compile(f.film,f.script,f.alignment);assert.deepEqual(Object.keys(t.formats),['3x4','9x16']);assert.equal(t.primaryFormat,'3x4');
  const g=fixture();g.film.formats=['16x9'];g.film.shots[0].layouts={'16x9':{}};g.film.shots[1].layouts={'16x9':{}};assert.equal(compile(g.film,g.script,g.alignment).primaryFormat,'16x9');
  const h=fixture();h.film.formats=['3x4'];h.film.primaryFormat='9x16';assert.throws(()=>compile(h.film,h.script,h.alignment),/primaryFormat/);
  const k=fixture();k.film.formats=['4x3'];assert.throws(()=>compile(k.film,k.script,k.alignment),/formats/);
});
test('V4: voice gaps, lead and trailing silence are measured; gapIntent surfaces as intentional',()=>{
  const f=fixture();f.script.beats.push({id:'next',narration:'明白'});f.alignment.segments.next={src:'next.mp3',durationSeconds:1,reviewed:true,method:'manual',words:[{text:'明白',startMs:100,endMs:900}]};
  f.film.voices.push({id:'next',at:{after:'open',offset:1.0},gapIntent:{reason:'反转前的停顿'}});f.film.shots[1].end=6;
  const t=compile(f.film,f.script,f.alignment);assert.equal(t.voiceGaps.length,1);assert.equal(t.voiceGaps[0].frames,30);assert.equal(t.voiceGaps[0].intentional,'反转前的停顿');
  assert.equal(t.leadSilenceSeconds,0.2);assert.equal(t.trailingSilenceSeconds,(180-(t.voices[1].from+30))/30);
  const g=fixture();const u=compile(g.film,g.script,g.alignment);assert.equal(u.voiceGaps.length,0);assert.equal(u.trailingSilenceSeconds,(120-96)/30);
});
test('V4: karaoke captions carry word frames; block captions keep the V3 shape',()=>{
  const f=fixture();const block=compile(f.film,f.script,f.alignment);assert.equal(block.captions[0].words,undefined);
  f.film.captions={style:'karaoke',maxChars:18};const t=compile(f.film,f.script,f.alignment);
  assert.equal(t.captions[0].words.length,1);assert.equal(t.captions[0].words[0].from,6+Math.round(.12*30));assert.equal(t.captions[0].words[0].text,'先看');
});
test('V4: shot hold and bespoke declarations pass through to the timeline',()=>{
  const {film,script,alignment}=fixture();film.shots[0].hold='观众跟着看录屏';film.shots[1].bespoke='水流：方程讲的是水怎么流';
  const t=compile(film,script,alignment);assert.equal(t.shots[0].hold,'观众跟着看录屏');assert.equal(t.shots[1].bespoke,'水流：方程讲的是水怎么流');assert.equal(t.shots[0].bespoke,undefined);
});
