#!/usr/bin/env python3
"""Validate sources, transcript/audio identity, assets, compiled timeline freshness, plus editorial/pacing checks.
Hard errors raise. Pacing and editorial findings are warnings unless brief.pacing.enforce is true."""
import argparse, hashlib, json
from pathlib import Path
from common import ROOT, read, inside, filehash, texthash, duration, norm, ident, run_main, spoken_text, cps, weighted_len

def banned_words():
    path = ROOT / 'references/banned-words.txt'
    if not path.exists(): return []
    out = []
    for line in path.read_text(encoding='utf-8').splitlines():
        word = line.split('#', 1)[0].strip()
        if word: out.append(word)
    return out

def bespoke_missing(t,draft=False):
    """A finished film needs one shot built for its topic (film.shots[].bespoke names the metaphor); drafts and partial scopes are exempt."""
    return (not draft) and t.get('scope')=='full' and not any(s.get('bespoke') for s in t.get('shots',[]))

def validate(project,draft=False,stage="final"):
    project=Path(project);s=read(project/'content/script.json');film=read(project/'content/film.json');a=read(project/'content/alignment.json',{});t=read(project/'content/timeline.json');brief=read(project/'content/brief.json')
    canonical='\x1f'.join((project/f).read_text(encoding='utf-8') if (project/f).exists() else '{}' for f in ['content/film.json','content/script.json','content/alignment.json'])
    if t.get('inputHash')!=hashlib.sha256(canonical.encode()).hexdigest():raise ValueError('Timeline is stale: run project.py compile')
    if t.get('draft') and not draft:raise ValueError('Technical draft cannot be used as a real preview/final')
    if not draft and brief.get('narrationRequired',True) and not t['voices']:raise ValueError('This brief requires actual narration')
    sources={x['id']:x for x in read(project/'content/sources.json',[])}
    claims={x['id']:x for x in read(project/'content/claims.json',[])}
    for c in claims.values():
        src=sources.get(c.get('sourceId'))
        if not src:raise ValueError('Unknown source for claim '+c['id'])
        sourcefile=inside(project,src['textFile'])
        quote=c.get('quote','')
        if not quote.strip() or ''.join(quote.split()) not in ''.join(sourcefile.read_text(encoding='utf-8').split()):raise ValueError('Quote absent from stated source: '+c['id'])
    ids=set();beats={}
    for b in s.get('beats',[]):
        ident(b['id'])
        if b['id'] in ids:raise ValueError('Duplicate script id')
        ids.add(b['id']);beats[b['id']]=b
        for c in b.get('claims',[]):
            if c not in claims:raise ValueError(f"Unknown claim {c} in {b['id']}")
        spoken_text(b)   # raises when beat.spoken disagrees with overrides
    scheduled={v['id'] for v in t['voices']}
    index=read(project/'public/narration/index.json',{})
    edit_on=bool((brief.get('voiceEdit') or {}).get('enabled'))
    for b in s.get('beats',[]):
        if b['id'] not in scheduled or not b.get('narration'):continue
        seg=a.get('segments',{}).get(b['id'])
        if not seg:
            if draft:continue
            raise ValueError('Missing alignment '+b['id'])
        audio=inside(project/'public',seg['src'])
        if seg.get('audioSha256')!=filehash(audio) or seg.get('textSha256')!=texthash(b['narration']):raise ValueError('Audio/script changed after alignment: '+b['id'])
        if abs(duration(audio)-seg['durationSeconds'])>.08:raise ValueError('Audio duration differs from alignment: '+b['id'])
        entry=index.get(b['id']) if isinstance(index.get(b['id']),dict) else {}
        if edit_on and seg.get('edit') and entry.get('editFingerprint') and seg['edit'].get('editFingerprint')!=entry['editFingerprint']:
            raise ValueError(f"Alignment does not match the edited audio: {b['id']}. Re-run voice_edit.py then align.py import --from-timing")
    assets=film.get('assets',{})
    for shot in t['shots']:
        for id in shot.get('assets',[]):
            if id not in assets:raise ValueError('Unknown shot asset '+id)
    for id in film.get('globalAssets',[]):
        if id not in assets:raise ValueError('Unknown global asset '+id)
    for id,asset in assets.items():
        path=inside(project/'public',asset['src'])
        if not path.is_file():raise ValueError('Missing asset '+id)
        if asset.get('sha256') and filehash(path)!=asset['sha256']:raise ValueError('Changed asset '+id)
    for clip in t['audio']:
        path=inside(project/'public',clip['src'])
        if duration(path)*t['fps']+2<clip['trimStart']+clip['durationFrames']:raise ValueError('Audio track is too short: '+clip['src'])
        if not 0<=clip.get('duck',1)<=1:raise ValueError('duck must be 0..1')
    # ---- editorial and pacing findings (warnings; errors when brief.pacing.enforce) ----
    warnings=[];pace=[];_pace=lambda m:(warnings.append(m),pace.append(m));pacing=brief.get('pacing') or {};report={'targetCps':pacing.get('targetCps'),'beats':{},'gaps':t.get('voiceGaps',[]),'leadSilenceSeconds':t.get('leadSilenceSeconds'),'trailingSilenceSeconds':t.get('trailingSilenceSeconds')}
    max_gap=pacing.get('maxVoiceGapSeconds')
    for g in t.get('voiceGaps',[]):
        if max_gap is not None and g['seconds']>max_gap and not g.get('intentional'):_pace(f"Voice gap {g['seconds']:.2f}s between {g['after']} and {g['before']} exceeds {max_gap}s; shorten it or declare film.voices[].gapIntent.reason for a deliberate pause")
    max_tail=pacing.get('maxTrailingSilenceSeconds')
    if max_tail is not None and t['voices'] and t.get('scope','full')=='full' and (t.get('trailingSilenceSeconds') or 0)>max_tail:_pace(f"Trailing silence {t['trailingSilenceSeconds']:.2f}s exceeds {max_tail}s")
    target=pacing.get('targetCps');tol=float(pacing.get('toleranceCps',0.7))
    for v in t['voices']:
        b=beats.get(v['id']);seg=a.get('segments',{}).get(v['id'])
        if not b or not seg:continue
        c=seg.get('measuredCps') or cps(spoken_text(b),seg['durationSeconds']);report['beats'][v['id']]=c
        if target is not None and abs(c-float(target))>tol:_pace(f"{v['id']} speaks at {c} chars/s; target {target}±{tol} (tts.py calibrate, or beats[].voice.speed)")
    banned=banned_words()+[w for w in (brief.get('bannedWordsExtra') or []) if w]
    for b in s.get('beats',[]):
        hits=[w for w in banned if w in (b.get('narration') or '')]
        if hits:warnings.append(f"{b['id']} uses 播音腔 words {hits}; say it like a person")
    max_w=(brief.get('captions') or {}).get('maxWeightedChars')
    if max_w:
        wide=[c['text'] for c in t.get('captions',[]) if weighted_len(c['text'])>max_w]
        if wide:warnings.append(f"{len(wide)} caption(s) wider than {max_w} weighted chars, e.g. {wide[0]!r}")
    if not draft and t.get('scope','full')=='full' and t['durationFrames']:
        for v in t['voices']:
            if beats.get(v['id'],{}).get('kind')=='turn':
                pos=v['from']/t['durationFrames']
                if not .35<=pos<=.75:warnings.append(f"turn beat {v['id']} starts at {pos:.0%} of the film; the turn lands best at 35–75%")
    from material_contract import material_errors
    material_findings=material_errors(project,stage)
    if material_findings and not draft:raise ValueError('Material gate failed:\n- '+'\n- '.join(material_findings))
    warnings.extend(material_findings)
    if not draft:
        if any(x.get('props',{}).get('template') for x in t.get('shots',[])):raise ValueError('Template placeholder remains: replace with actual content; do not label a template as a finished film')
        if brief.get('profile')=='launch':
            candidates=[x for x in read(project/'content/materials.json',{'items':[]}).get('items',[]) if x.get('required') and x.get('status')=='ready' and x.get('evidenceKind')=='real-demo']
            early={a for shot in t.get('shots',[]) if shot.get('from',0)<t.get('fps',30)*10 for a in shot.get('assets',[])}
            if not any(x.get('assetId') in early for x in candidates):raise ValueError('Launch gate: at least one inspected required real-demo asset must appear in the first 10 seconds. For concept-only work use an explicitly revised brief, not a fake launch demo.')

    prod=read(project/'content/product.json',{})
    if not draft and prod:
        import product as _product;ev=_product.evidence_level(prod)
        if ev!='solid' and not prod.get('confirmation'):warnings.append(f"product evidence is {ev} and unconfirmed: ask the user (product.py gaps) and record the answer with product.py confirm --evidence; inferred facts must not be narrated as facts")
    if not draft and (brief.get('music') or {}).get('required') and t.get('scope')=='full' and not t.get('audio'):warnings.append('brief.music.required is true but film.audio is empty: music.py plan → rank → ingest → fit (or set music.required false with the user)')
    if bespoke_missing(t,draft):warnings.append('no shot declares film.shots[].bespoke: build at least one shot for this topic (its own visual metaphor) instead of catalogue parts only, and name it there')
    if brief.get('formats') and set(brief['formats'])!=set(t['formats']):warnings.append(f"film.formats {sorted(t['formats'])} differ from brief.formats {sorted(brief['formats'])}")
    # Technical drafts carry synthetic or partial audio; enforcement bites at opening / preview / final where real narration is required.
    if pacing.get('enforce') and pace and not draft:raise ValueError('Pacing checks failed (brief.pacing.enforce; gaps / trailing silence / chars-per-second):\n- '+'\n- '.join(pace)+'\nOther findings stay warnings.')
    return {'ok':True,'draft':bool(t.get('draft')),'shots':len(t['shots']),'frames':t['durationFrames'],'warnings':warnings,'pacing':report,'facts':'Quote provenance checked; meaning and numerical context require editorial review.'}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('project',type=Path);p.add_argument('--draft',action='store_true');a=p.parse_args();print(json.dumps(validate(a.project,a.draft),ensure_ascii=False,indent=2))
if __name__=='__main__':run_main(main)
