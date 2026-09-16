// Pure, explicit timeline compiler. All consumers use these integer frame coordinates. No dependencies.
export const FORMATS = {'3x4': {width:1080,height:1440}, '9x16': {width:1080,height:1920}, '16x9': {width:1920,height:1080}};
const check = (v,m) => {if (!v) throw new Error(m);};
const num = (v) => typeof v === 'number' && Number.isFinite(v);
const clean = (t) => t.normalize('NFKC').replace(/[^\p{L}\p{N}]/gu,'').toLowerCase();

export function compile(film, script, alignment = {}, {draft = false} = {}) {
  check([3,4].includes(film.version) && [3,4].includes(script.version),'Use V3/V4 film/script data; migrate V2 content deliberately');
  const fps = film.fps ?? 30;
  check(Number.isInteger(fps) && fps >= 1 && fps <= 120, 'fps must be an integer in 1..120');
  const frame = (s) => {check(num(s), 'Time must be finite');return Math.round(s*fps);};
  const formatKeys = film.formats ?? Object.keys(FORMATS);
  check(Array.isArray(formatKeys) && formatKeys.length>0 && formatKeys.every(k=>FORMATS[k]) && new Set(formatKeys).size===formatKeys.length, 'film.formats must list distinct formats from 3x4/9x16/16x9');
  const primaryFormat = film.primaryFormat ?? (formatKeys.includes('3x4') ? '3x4' : formatKeys[0]);
  check(formatKeys.includes(primaryFormat), 'primaryFormat must be one of film.formats');
  const beats = new Map();
  for (const b of script.beats ?? []) {check(b.id && !beats.has(b.id),'Duplicate/missing beat id');beats.set(b.id,b);}
  const voices = new Map();
  const segments = alignment.segments ?? {};
  for (const v of film.voices ?? []) {
    check(!voices.has(v.id), `Duplicate voice ${v.id}`);
    const b = beats.get(v.id); check(b, `Unknown script beat ${v.id}`);
    const a = segments[v.id];
    if (!draft) {
      check(a && a.reviewed && ['provider','manual','whisper'].includes(a.method), `Reviewed real alignment required: ${v.id}`);
      check(clean((a.words ?? []).map(w=>w.text).join('')) === clean(b.narration), `Alignment transcript differs from script: ${v.id}`);
    }
    const seconds = a?.durationSeconds ?? v.draftSeconds;
    check(num(seconds) && seconds > 0, `Positive voice duration required: ${v.id}`);
    let start = v.at ?? 0;
    if (typeof start === 'object') {
      const prev = voices.get(start.after);check(prev, `Voice 'after' must reference an earlier voice: ${v.id}`);
      start = (prev.from + prev.durationFrames)/fps + (start.offset ?? 0);
    }
    check(num(start) && start >= 0, `Invalid voice start: ${v.id}`);
    const voice = {id:v.id,src:a?.src ?? `narration/${v.id}.mp3`,from:frame(start),durationFrames:Math.ceil(seconds*fps),gain:v.gain ?? 1, real:Boolean(a?.reviewed), words:a?.words ?? [], captions:a?.captions};
    if (v.gapIntent) voice.gapIntent = v.gapIntent;
    check(num(voice.gain) && voice.gain>=0, `Invalid voice gain: ${v.id}`);
    let previousEnd = 0;
    for (const w of voice.words) {
      check(typeof w.text==='string' && num(w.startMs) && num(w.endMs) && w.startMs>=previousEnd-1 && w.endMs>w.startMs && w.endMs<=seconds*1000+80, `Invalid word timing: ${v.id}`);
      previousEnd=w.endMs;
    }
    if (voice.captions) {
      let end=0;
      for (const c of voice.captions) {check(typeof c.text==='string' && num(c.startMs)&&num(c.endMs)&&c.startMs>=end&&c.endMs>c.startMs&&c.endMs<=seconds*1000+80,`Invalid captions: ${v.id}`);end=c.endMs;}
      check(clean(voice.captions.map(c=>c.text).join(''))===clean(b.narration),`Caption text differs from narration: ${v.id}`);
    }
    voices.set(v.id,voice);
    if(!v.allowOverlap)for(const prev of voices.values())if(prev.id!==v.id)check(voice.from>=prev.from+prev.durationFrames||voice.from+voice.durationFrames<=prev.from,`Overlapping narration: ${v.id}. Use allowOverlap only for a deliberate simultaneous-voice design.`);
  }
  check(['opening','full'].includes(film.scope??'full'),'scope must be opening or full');
  if (!draft && film.scope!=='opening') for (const b of beats.values()) if (b.narration?.trim()) check(voices.has(b.id), `Script narration is unscheduled: ${b.id}`);
  if(!draft){
    const planned=[...beats.values()].filter(b=>b.narration?.trim()).map(b=>b.id);
    const audible=[...voices.values()].sort((a,b)=>a.from-b.from).map(v=>v.id);
    check(audible.every((id,i)=>id===planned[i]),'Narration playback order differs from the approved script. Reorder the script for review before changing its spoken sequence.');
  }
  const events={}, resolving=new Set();
  function event(id) {
    if (Object.hasOwn(events,id)) return events[id];
    check(!resolving.has(id),`Cyclic event: ${id}`);resolving.add(id);
    const e=film.events?.[id];check(e!==undefined,`Unknown event: ${id}`);
    let t;
    if (num(e) || e.event) t=time(e);
    else {
      const v=voices.get(e.voice);check(v,`Unknown voice in event ${id}`);
      if (e.edge==='voice-end') t=v.from+v.durationFrames;
      else if (e.edge==='voice-start') t=v.from;
      else {
        let selected=[];
        if (Number.isInteger(e.wordIndex)) selected=[v.words[e.wordIndex]].filter(Boolean);
        else if (e.word) {
          const needle=clean(e.word);check(needle.length>0,`Empty event word: ${id}`);
          const parts=v.words.map(w=>clean(w.text));const all=parts.join('');let pos=-1;
          check(Number.isInteger(e.occurrence??1)&&(e.occurrence??1)>0,`Invalid occurrence: ${id}`);
          for(let n=0;n<(e.occurrence??1);n++){pos=all.indexOf(needle,pos+1);if(pos<0)break;}
          if(pos>=0){let c=0;selected=v.words.filter((w,i)=>{const left=c;c+=parts[i].length;return c>pos && left<pos+needle.length;});}
        }
        if(draft && !selected.length && num(e.draftSeconds)) t=frame(e.draftSeconds);
        else {check(selected.length,`Word/phrase not found in actual alignment: ${id}`);t=v.from+frame((e.edge==='end'?selected.at(-1).endMs:selected[0].startMs)/1000);}
      }
      t+=frame(e.offset??0);
    }
    check(t>=0,`Negative event ${id}`);events[id]=t;resolving.delete(id);return t;
  }
  function time(spec) {
    if(num(spec))return frame(spec);
    check(spec && typeof spec==='object' && typeof spec.event==='string','Time must be seconds or {event, offset}');
    return event(spec.event)+frame(spec.offset??0);
  }
  for(const id of Object.keys(film.events??{}))event(id);
  const ids=new Set();
  const shots=(film.shots??[]).map(s=>{
    check(s.id && !ids.has(s.id), 'Duplicate/missing shot id');ids.add(s.id);
    check(film.components?.[s.component],`Unregistered component ${s.component}`);
    const from=time(s.start),end=time(s.end);check(from>=0&&end>from,`Invalid shot interval ${s.id}`);
    for (const f of formatKeys)check(s.layouts?.[f] && typeof s.layouts[f]==='object',`Missing ${f} layout: ${s.id}`);
    const incoming=frame(s.transitionIn?.seconds??0);
    check(incoming>=0&&incoming<end-from,`Invalid transition duration: ${s.id}`);
    check(['cut','fade','custom'].includes(s.transitionIn?.type??'cut'),`Unknown transition type: ${s.id}`);
    return {...s,from,end,durationFrames:end-from,transitionIn:{type:s.transitionIn?.type??'cut',frames:incoming}};
  }).sort((a,b)=>a.from-b.from);
  check(shots.length>0,'At least one shot is required');
  let coverage=0;
  for(const s of shots){check(s.from<=coverage,`Uncovered visual gap before ${s.id}`);coverage=Math.max(coverage,s.end);}
  const durationFrames = coverage;
  for (const s of shots) if(s.transitionIn.frames>0) check(shots.some(p=>p!==s&&p.from<s.from&&p.end>=s.from+s.transitionIn.frames),`Transition lacks previous visual coverage: ${s.id}`);
  for (const v of voices.values()) check(v.from+v.durationFrames<=durationFrames,`Voice would be cut off: ${v.id}`);
  const audio=(film.audio??[]).map((a,i)=>{
    const from=time(a.start??0),end=time(a.end??durationFrames/fps);
    check(from>=0&&end>from&&end<=durationFrames,`Invalid audio interval ${i}`);
    const gain=a.gain??1,trimStart=frame(a.trimStart??0),fadeIn=frame(a.fadeIn??0),fadeOut=frame(a.fadeOut??0);
    check(num(gain)&&gain>=0&&trimStart>=0&&fadeIn>=0&&fadeOut>=0&&fadeIn+fadeOut<=end-from,`Invalid audio parameters ${i}`);
    return {...a,from,end,gain,trimStart,fadeIn,fadeOut,durationFrames:end-from};
  });
  // Karaoke captions carry their words in global frames; block captions keep the V3 shape exactly.
  const karaoke = film.captions?.style === 'karaoke';
  const captions=[];
  for (const v of voices.values()) {
    let grouped=v.captions;
    if (!grouped) {
      grouped=[];let g=null;
      for(const w of v.words){
        if(g && (w.startMs-g.endMs>320 || g.text.length+w.text.length>(film.captions?.maxChars??18))){grouped.push(g);g=null;}
        g=g?{...g,text:g.text+w.text,endMs:w.endMs}:{...w};
        if(/[。！？!?]$/.test(w.text)&&g){grouped.push(g);g=null;}
      }
      if(g)grouped.push(g);
    }
    for(const c of grouped){
      const from=v.from+frame(c.startMs/1000);const entry={...c,voice:v.id,from,end:Math.max(from+1,v.from+frame(c.endMs/1000))};
      if(karaoke) entry.words=v.words.filter(w=>w.startMs<c.endMs && w.endMs>c.startMs).map(w=>({text:w.text,from:v.from+frame(w.startMs/1000),end:Math.max(v.from+frame(w.startMs/1000)+1,v.from+frame(w.endMs/1000))}));
      captions.push(entry);
    }
  }
  // Pacing measurements (policy lives in validate.py): gaps between consecutive narration beats, lead and trailing silence.
  const ordered=[...voices.values()].sort((a,b)=>a.from-b.from);
  const voiceGaps=ordered.slice(1).map((v,i)=>{const p=ordered[i];const gap=v.from-(p.from+p.durationFrames);return {after:p.id,before:v.id,frames:gap,seconds:gap/fps,intentional:v.gapIntent?.reason??null};});
  const leadSilenceSeconds=ordered.length?ordered[0].from/fps:0;
  const trailingSilenceSeconds=ordered.length?(durationFrames-(ordered.at(-1).from+ordered.at(-1).durationFrames))/fps:durationFrames/fps;
  return {version:3,scope:film.scope??'full',draft,fps,durationFrames,formats:Object.fromEntries(formatKeys.map(k=>[k,FORMATS[k]])),primaryFormat,events,shots,voices:[...voices.values()],audio,captions,captionStyle:film.captions??{},assets:film.assets??{},globalAssets:film.globalAssets??[],style:film.style??{},voiceGaps,leadSilenceSeconds,trailingSilenceSeconds};
}
