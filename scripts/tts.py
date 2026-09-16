#!/usr/bin/env python3
"""Voice router: one pipeline for every provider (synthesis → breath edit → index → native alignment import).

  tts.py <project> [--only id,id] [--provider fish|seed2] [--force] [--no-edit] [--no-align] [--dry-run] [--param k=v]
  tts.py plan <project> [--only ids]                     # request specs for a host-provided TTS tool
  tts.py import <project> --id ID --audio F [--timestamps F] [--provider host] [--model M] [--tempo 1.2] [--no-edit]
  tts.py calibrate <project> [--provider P] [--text T|--beat ID] [--sweep 1.0,1.2,1.4] [--target-cps X] [--apply]
  tts.py measure <project> [--only ids]
  tts.py providers
Pace is a measured target (brief.pacing.targetCps); provider knobs are calibrated to it, not guessed.
"""
import argparse, hashlib, importlib, json, shutil, subprocess, sys, time
from pathlib import Path
from common import read, write, filehash, ident, ensure_script, spoken_text, tts_text, chunk_text, cps, norm, duration, run_main, strip_tags, TAG_RE, weighted_len
import voice_edit

PROVIDERS = {'fish': 'tts_fish', 'seed2': 'tts_seed2'}
SUBS = {'plan', 'import', 'calibrate', 'measure', 'providers'}
ROUTER_VERSION = '1'

# ---- performance defaults: one emotion per beat kind (the single default tag is what makes a whole film monotone)
KIND_EMOTION = {
    'viral': {'hook': 'excited', 'setup': 'excited', 'chapter': 'confident', 'evidence': 'confident', 'turn': 'amazed', 'summary': 'confident', 'cta': 'excited', 'ending': 'soft'},
    'launch': {'hook': 'confident', 'setup': 'calm', 'chapter': 'confident', 'evidence': 'calm', 'turn': 'amazed', 'summary': 'sincere', 'cta': 'warm', 'ending': 'calm'},
}
EMOTION_ZH = {'excited': '兴奋', 'confident': '自信笃定', 'amazed': '惊讶、语调抬高', 'calm': '平稳清晰', 'sincere': '真诚、略放慢', 'warm': '温和', 'soft': '轻声收尾', 'serious': '严肃', 'curious': '好奇', 'sad': '低落', 'angry': '不满', 'whispers': '耳语', 'laughing': '带笑'}
KIND_ZH = {'hook': '开头钩子', 'setup': '铺垫', 'chapter': '章节主张', 'evidence': '证据', 'turn': '转折', 'summary': '总结', 'cta': '行动号召', 'ending': '结尾'}
REGISTER = {'viral': '像跟朋友爆料的科技博主：兴奋、带梗，重音砸在数字和转折词上，句尾不拖', 'launch': '像跟同行讲自己做的东西：克制、准确、自信，不喊口号'}
# Inline tags confirmed for qwen-audio-3.0-tts (Aliyun guide): [excited] [amazed] [sad] [angry] [whispers] [laughing] [sighing] [gasp] [crying]. Others go into the instruction text.
HOST_TAGS = {'excited': 'excited', 'amazed': 'amazed', 'surprised': 'amazed', 'curious': 'amazed', 'sad': 'sad', 'angry': 'angry', 'whispers': 'whispers', 'whisper': 'whispers', 'soft': 'whispers', 'laughing': 'laughing', 'sighing': 'sighing', 'gasp': 'gasp', 'crying': 'crying'}
TEMPO_MAX = 1.3  # measured on a real qwen narration: whisper match 0.95 at 1.25, 0.92 at 1.4, 0.905 at 1.5 — and even 1.5× only reaches 6 cps from 4


def beat_emotion(beat, brief):
    """beats[].voice.emotion → brief.tts.emotion.byKind → house table by profile/kind → brief.tts.emotion.default (brackets stripped)."""
    explicit = (beat.get('voice') or {}).get('emotion')
    if explicit: return explicit.strip('[]')
    cfg = (brief.get('tts') or {}).get('emotion') or {}
    by_kind = cfg.get('byKind') or KIND_EMOTION.get(brief.get('profile', 'viral'), KIND_EMOTION['viral'])
    kind = beat.get('kind')
    if kind and by_kind.get(kind): return by_kind[kind]
    return (cfg.get('default') or '').strip('[]')


def with_kind_emotion(beat, brief):
    """Copy of the beat with voice.emotion filled from the kind table so every provider gets the per-kind performance."""
    emo = beat_emotion(beat, brief)
    if not emo: return beat
    b = dict(beat); v = dict(b.get('voice') or {}); v['emotion'] = emo; b['voice'] = v; return b


def host_instruction(profile, kind, emotion, target_cps, extra=''):
    """Natural-language direction for host TTS tools that accept an `instruction` field (qwen-audio-3.0-tts). Pace is stated as a hard requirement: default host output measured 4 chars/s."""
    parts = [REGISTER.get(profile, REGISTER['viral']), f"这一段是{KIND_ZH.get(kind, '正文')}，语气{EMOTION_ZH.get(emotion, emotion or '自然')}"]
    if target_cps: parts.append(f'语速快：按每秒约 {target_cps:.0f} 个汉字朗读，这是硬性要求（默认语速太慢，只有一半），短句之间几乎不停顿，不拖长音，重音落在数字和转折词上')
    if extra: parts.append(extra.strip('。；'))
    return '；'.join(parts) + '。'


def host_text(beat, brief):
    """Spoken text with the confirmed host inline tag in front (unconfirmed emotions stay in the instruction only)."""
    tag = HOST_TAGS.get(beat_emotion(beat, brief))
    return (f'[{tag}]' if tag else '') + spoken_text(beat)


def expected_seconds(beat, target_cps, tolerance):
    n = len(norm(spoken_text(beat)))  # same measure as cps() / tts.py measure / validate, so the band and the verdict agree
    if not target_cps: return None
    return {'chars': round(n, 1), 'target': round(n / target_cps, 2), 'min': round(n / (target_cps + tolerance), 2), 'max': round(n / max(0.5, target_cps - tolerance), 2)}


def scale_tokens(tokens, tempo):
    """Timestamps of audio sped up by atempo=tempo: every time divides by tempo."""
    if not tokens or not tempo or tempo == 1.0: return tokens
    return [{**t, 'start': round(t['start'] / tempo, 4), 'end': round(t['end'] / tempo, 4)} for t in tokens]


def adapter(name):
    if name not in PROVIDERS: raise ValueError(f"Unknown TTS provider '{name}'. Use one of {sorted(PROVIDERS)} or `tts.py import` for a host tool")
    return importlib.import_module(PROVIDERS[name])


def synth_fingerprint(text, provider, model, speaker, params, version):
    return hashlib.sha1(f"{text}\x1f{provider}\x1f{model}\x1f{speaker}\x1f{json.dumps(params, sort_keys=True, ensure_ascii=False)}\x1f{version}".encode()).hexdigest()[:16]


def beat_params(brief, beat, keys, overrides=None):
    params = dict((brief.get('tts') or {}).get('params') or {})
    voice = beat.get('voice') or {}
    for k in keys:
        if k in voice: params[k] = voice[k]
    for k, v in (overrides or {}).items(): params[k] = v
    return {k: v for k, v in params.items() if k in keys}


def parse_params(items):
    out = {}
    for item in items or []:
        k, _, v = item.partition('=')
        if not k or not _: raise ValueError('--param expects key=value')
        try: out[k] = json.loads(v)
        except json.JSONDecodeError: out[k] = v
    return out


def concat_wavs(parts, dest):
    lst = dest.with_suffix('.concat.txt'); lst.write_text(''.join(f"file '{p}'\n" for p in parts), encoding='utf-8')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', str(lst), '-ar', '48000', '-ac', '1', '-c:a', 'pcm_s16le', str(dest)], check=True); lst.unlink()


def synthesize_text(mod, text, voice, params, dest, key, log):
    """Chunk long text, synthesize each part, offset native tokens by measured part durations, concat to dest."""
    tag = ''
    m = TAG_RE.match(text)
    if m: tag, text = m.group(0), text[m.end():]
    chunks = [tag + c for c in chunk_text(text, mod.MAX_CHARS)]
    dest = Path(dest); dest.parent.mkdir(parents=True, exist_ok=True)
    parts, tokens, offset, model, mode = [], [], 0.0, None, None
    for i, chunk in enumerate(chunks):
        part = dest.with_name(f'{dest.stem}.part{i}.wav') if len(chunks) > 1 else dest
        r = mod.synthesize(chunk, voice, params, part, key, log=log)
        model, mode = r['model'], r.get('mode')
        if r.get('tokens') is not None:
            tokens.extend({'text': t['text'], 'start': round(t['start'] + offset, 4), 'end': round(t['end'] + offset, 4)} for t in r['tokens'])
        elif tokens or i == 0: tokens = None if r.get('tokens') is None else tokens
        offset += r['seconds']; parts.append(part)
    if len(parts) > 1:
        concat_wavs(parts, dest)
        for p in parts: p.unlink()
    return {'seconds': round(duration(dest), 3), 'tokens': tokens, 'model': model, 'mode': mode, 'chunks': len(chunks)}


def finalize(project, brief, beat, entry, index, durations, no_edit, no_align, log):
    """Shared tail for synth and import: breath edit (or copy), index/durations update, native alignment import."""
    id = beat['id']; cfg = voice_edit.settings(brief); spoken = spoken_text(beat)
    dest = project / 'public/narration' / f'{id}.wav'; dest.parent.mkdir(parents=True, exist_ok=True)
    native = read(project / entry['native'], {}) if entry.get('native') else {}
    tokens = native.get('tokens')
    edit_on = cfg.get('enabled', True) and not no_edit
    efp = voice_edit.edit_fingerprint(entry['synthFingerprint'], cfg) if edit_on else 'none'
    if entry.get('editFingerprint') == efp and dest.exists() and filehash(dest) == entry.get('sha256'):
        log(f'{id}: edited audio current'); return entry
    if dest.exists():
        archive = project / 'work/voice-versions'; archive.mkdir(parents=True, exist_ok=True); dest.replace(archive / f'{id}-{time.time_ns()}.wav')
    raw = project / entry['raw']
    if edit_on:
        report = voice_edit.edit_beat(project, id, raw, tokens, cfg, spoken)
        seconds, removed, measured = report['editedSeconds'], report['removedSeconds'], report['measuredCps']
    else:
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(raw), '-ar', '48000', '-ac', '1', '-c:a', 'pcm_s16le', str(dest)], check=True)
        seconds = round(duration(dest), 3); removed = 0.0; measured = cps(spoken, seconds)
        timing = project / 'work/voice' / f'{id}-timing.json'
        if tokens: write(timing, {'text': spoken, 'words': voice_edit.remap_tokens(tokens, []), 'captions': None})
        elif timing.exists(): timing.unlink()
    entry.update(editFingerprint=efp, fingerprint=efp if edit_on else entry['synthFingerprint'], src=f'narration/{id}.wav', sha256=filehash(dest),
                 seconds=seconds, removedSeconds=removed, measuredCps=measured, timestamps='native' if tokens else 'none', editedAt=time.strftime('%Y-%m-%dT%H:%M:%S'))
    index[id] = entry; durations[id] = seconds
    write(project / 'public/narration/index.json', index); write(project / 'content/narration-durations.json', durations)
    log(f"{id}: {seconds:.3f}s  {measured} cps  (-{removed:.2f}s breath)  {entry['provider']}/{entry.get('model')}")
    if tokens and not no_align:
        import align
        seg = align.import_timing(project, id, provider=entry['provider'])
        log(f"  alignment imported ({len(seg['words'])} words, transcriptMatches={seg['transcriptMatches']}); listen, then align.py review --note ...")
    elif not tokens:
        log('  no native timestamps: run align.py transcribe (whisper) or import measured words, then review')
    return entry


def run_synth(a):
    project = a.project.resolve(); brief = read(project / 'content/brief.json'); script = read(project / 'content/script.json')
    tts = brief.get('tts') or {}; provider = a.provider or tts.get('provider', 'fish')
    if provider == 'host': raise ValueError('brief.tts.provider is a host tool: run `tts.py plan`, generate with the host tool, then `tts.py import`')
    mod = adapter(provider); overrides = parse_params(a.param)
    beats = [b for b in script['beats'] if b.get('narration', '').strip()]
    if a.only:
        selected = set(a.only.split(',')); unknown = selected - {b['id'] for b in beats}
        if unknown: raise ValueError('Unknown voice ids: ' + ','.join(sorted(unknown)))
        beats = [b for b in beats if b['id'] in selected]
    for b in beats: ident(b['id'])
    plan = []
    for b in beats:
        text = tts_text(with_kind_emotion(b, brief), brief, mod.emotion); params = beat_params(brief, b, mod.PARAM_KEYS, overrides)
        model = tts.get('model') or getattr(mod, 'DEFAULT_MODELS', [''])[0]; speaker = tts.get('reference_id') or tts.get('speaker', '')
        plan.append({'id': b['id'], 'text': text, 'params': params, 'fingerprint': synth_fingerprint(text, provider, model, speaker, params, mod.ADAPTER_VERSION + ROUTER_VERSION)})
    if a.dry_run:
        print(json.dumps({'executed': False, 'provider': provider, 'model': tts.get('model'), 'speaker': tts.get('speaker'), 'ids': [p['id'] for p in plan], 'text': [p['text'] for p in plan], 'params': [p['params'] for p in plan]}, ensure_ascii=False, indent=2)); return
    ensure_script(project)
    import keys
    key, source = keys.provider_key(provider); print(f'credential: {source}')
    index = read(project / 'public/narration/index.json', {}); durations = read(project / 'content/narration-durations.json', {})
    voice = {**tts, 'model': tts.get('model') or getattr(mod, 'DEFAULT_MODELS', [''])[0]}
    for b, p in zip(beats, plan):
        id = b['id']; entry = index.get(id) if isinstance(index.get(id), dict) else {}
        raw = project / 'work/voice/raw' / f'{id}.wav'
        fresh = (not a.force and entry.get('synthFingerprint') == p['fingerprint'] and raw.exists() and filehash(raw) == entry.get('rawSha256'))
        if not fresh:
            if raw.exists():
                archive = project / 'work/voice-versions'; archive.mkdir(parents=True, exist_ok=True); raw.replace(archive / f'{id}-raw-{time.time_ns()}.wav')
            r = synthesize_text(mod, p['text'], voice, p['params'], raw, key, log=print)
            native = project / 'work/voice/raw' / f'{id}.native.json'
            write(native, {'text': spoken_text(b), 'ttsText': p['text'], 'provider': provider, 'model': r['model'], 'mode': r.get('mode'), 'tokens': r['tokens']})
            entry = {'provider': provider, 'model': r['model'], 'speaker': voice.get('reference_id') or voice.get('speaker'), 'params': p['params'], 'ttsText': p['text'],
                     'spokenSha256': hashlib.sha256(spoken_text(b).encode()).hexdigest(), 'synthFingerprint': p['fingerprint'],
                     'raw': str(raw.relative_to(project)), 'rawSha256': filehash(raw), 'rawSeconds': r['seconds'], 'native': str(native.relative_to(project)), 'chunks': r['chunks']}
            print(f"{id}: synthesized {r['seconds']:.3f}s raw ({r['chunks']} request{'s' if r['chunks'] > 1 else ''})")
        else:
            print(f'{id}: synthesis reused')
        finalize(project, brief, b, entry, index, durations, a.no_edit, a.no_align, print)


def run_plan(a):
    project = a.project.resolve(); brief = read(project / 'content/brief.json'); script = read(project / 'content/script.json'); tts = brief.get('tts') or {}
    pacing = brief.get('pacing') or {}; target = pacing.get('targetCps'); tol = float(pacing.get('toleranceCps', 0.7)); profile = brief.get('profile', 'viral')
    beats = [b for b in script['beats'] if b.get('narration', '').strip()]
    if a.only: beats = [b for b in beats if b['id'] in set(a.only.split(','))]
    out = project / 'work/voice/host'; out.mkdir(parents=True, exist_ok=True)
    items = []
    for b in beats:
        emo = beat_emotion(b, brief); extra = (b.get('voice') or {}).get('style') or tts.get('style', '')
        items.append({'id': b['id'], 'kind': b.get('kind'), 'text': host_text(b, brief), 'spoken': spoken_text(b), 'emotion': emo,
                      'instruction': host_instruction(profile, b.get('kind'), emo, target, extra), 'expectedSeconds': expected_seconds(b, target, tol),
                      'voice': tts.get('speaker') or tts.get('voice'), 'format': 'wav, 48000 Hz, mono (mp3 accepted)',
                      'audioOut': str(out / f"{b['id']}.wav"), 'timestampsOut': str(out / f"{b['id']}.json"),
                      'timestampsShape': 'optional: [{"text","start","end"}] seconds on the spoken text, or Caption-shaped [{"text","startMs","endMs"}]'})
    plan = {'provider': tts.get('provider', 'host'), 'model': tts.get('model') or 'qwen-audio-3.0-tts-plus (or the host default)', 'profile': profile,
            'pace': {'targetCps': target, 'toleranceCps': tol, 'why': '两条实测宿主成片默认语速只有 4.0 字/秒，是目标的一半；整体加速到 1.5× 也只到 6 字/秒，所以必须在生成时就说快',
                     'rateHint': '若工具暴露数字语速参数（常见名 rate / speech_rate / speed，本机未核实），先设 1.3–1.5；instruction 里的"每秒约 N 个汉字"是硬性要求'},
            'items': items,
            'next': ('每条用宿主 TTS 工具生成：text 原样（含 [excited] 类标签）、instruction 原样、voice 按 brief；保存到 audioOut（有时码则存 timestampsOut）→ '
                     'tts.py import <project> --id <id> --audio <audioOut> [--timestamps <timestampsOut>]（自动剪气口、量语速）→ 看 import 打印的 cps 判定：'
                     '偏慢就改 instruction（更快）或调高 rate 重新生成，不要接受；最后手段 --tempo ≤ 1.3（音质降级，且只能补 30%）。全部 ✓ 后 project.py plan-voices → align.py transcribe（无时码时）→ review')}
    write(out / 'plan.json', plan); print(json.dumps(plan, ensure_ascii=False, indent=2))


def parse_timestamps(path, spoken):
    raw = read(path)
    items = raw.get('tokens') or raw.get('words') or raw.get('segments') if isinstance(raw, dict) else raw
    if not isinstance(items, list) or not items: raise ValueError('Timestamps file must contain a non-empty list of tokens')
    tokens = []
    for t in items:
        if 'startMs' in t: tokens.append({'text': str(t['text']), 'start': float(t['startMs']) / 1000, 'end': float(t['endMs']) / 1000})
        else: tokens.append({'text': str(t['text']), 'start': float(t['start']), 'end': float(t['end'])})
    if norm(''.join(t['text'] for t in tokens)) != norm(spoken): raise ValueError('Timestamp text differs from the spoken text of this beat')
    return tokens


def run_import(a):
    project = a.project.resolve(); brief = read(project / 'content/brief.json'); script = read(project / 'content/script.json')
    id = ident(a.id); beat = next((b for b in script['beats'] if b['id'] == id), None)
    if not beat: raise ValueError('Unknown script beat ' + id)
    ensure_script(project)
    audio = Path(a.audio).expanduser().resolve()
    if not audio.is_file(): raise ValueError('Audio file does not exist')
    spoken = spoken_text(beat); tokens = parse_timestamps(Path(a.timestamps).expanduser().resolve(), spoken) if a.timestamps else None
    raw = project / 'work/voice/raw' / f'{id}.wav'; raw.parent.mkdir(parents=True, exist_ok=True)
    if raw.exists():
        archive = project / 'work/voice-versions'; archive.mkdir(parents=True, exist_ok=True); raw.replace(archive / f'{id}-raw-{time.time_ns()}.wav')
    tempo = float(getattr(a, 'tempo', 1.0) or 1.0)
    if not 1.0 <= tempo <= TEMPO_MAX: raise ValueError(f'--tempo must be 1.0–{TEMPO_MAX} (whisper match drops below 0.92 beyond 1.3×; regenerate faster instead)')
    af = ['-af', f'atempo={tempo}'] if tempo > 1.0 else []
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(audio), *af, '-ar', '48000', '-ac', '1', '-c:a', 'pcm_s16le', str(raw)], check=True)
    if tempo > 1.0: tokens = scale_tokens(tokens, tempo); print(f'  tempo {tempo}× applied before the breath edit (last resort: quality degrades; timestamps scaled)')
    seconds = round(duration(raw), 3)
    if tokens and tokens[-1]['end'] > seconds + 0.18: raise ValueError('Timestamps extend past the audio')
    provider = a.provider or 'host'; text = tts_text(with_kind_emotion(beat, brief), brief)
    fp = synth_fingerprint(text, provider, a.model or '', filehash(audio), {}, ROUTER_VERSION)
    native = project / 'work/voice/raw' / f'{id}.native.json'
    write(native, {'text': spoken, 'ttsText': text, 'provider': provider, 'model': a.model, 'mode': 'imported', 'tokens': tokens, 'importedFrom': str(audio)})
    index = read(project / 'public/narration/index.json', {}); durations = read(project / 'content/narration-durations.json', {})
    entry = {'provider': provider, 'model': a.model, 'speaker': a.speaker, 'params': {'tempo': tempo} if tempo > 1.0 else {}, 'ttsText': text, 'spokenSha256': hashlib.sha256(spoken.encode()).hexdigest(),
             'synthFingerprint': fp, 'raw': str(raw.relative_to(project)), 'rawSha256': filehash(raw), 'rawSeconds': seconds, 'native': str(native.relative_to(project)), 'chunks': 1, 'importedFrom': str(audio)}
    print(f'{id}: imported {seconds:.3f}s from {audio.name}' + (f' with {len(tokens)} timestamps' if tokens else ' (no timestamps)'))
    done = finalize(project, brief, beat, entry, index, durations, a.no_edit, a.no_align, print)
    target = (brief.get('pacing') or {}).get('targetCps'); tol = float((brief.get('pacing') or {}).get('toleranceCps', 0.7))
    if target is not None and done.get('measuredCps') is not None:
        c = float(done['measuredCps'])
        if abs(c - float(target)) <= tol: print(f'  pace ✓ {c} cps (target {target}±{tol})')
        elif c < float(target): print(f"  pace ⚠ {c} cps is below {target}±{tol}: regenerate with a faster instruction / higher rate (see work/voice/host/plan.json); --tempo ≤ {TEMPO_MAX} only as a last resort")
        else: print(f'  pace ⚠ {c} cps is above {target}±{tol}: regenerate slower')


def run_calibrate(a):
    project = a.project.resolve(); brief = read(project / 'content/brief.json'); tts = brief.get('tts') or {}
    provider = a.provider or tts.get('provider', 'fish')
    if provider == 'host': raise ValueError('Host tools cannot be swept from here: generate probes with the host tool at several rates, then use `tts.py measure --audio F --text T` for each')
    mod = adapter(provider); name, lo, hi = mod.PACE_PARAM
    target = a.target_cps if a.target_cps is not None else (brief.get('pacing') or {}).get('targetCps')
    if target is None: raise ValueError('Provide --target-cps or brief.pacing.targetCps')
    if a.beat:
        beat = next((b for b in read(project / 'content/script.json')['beats'] if b['id'] == a.beat), None)
        if not beat: raise ValueError('Unknown beat ' + a.beat)
        text = tts_text(with_kind_emotion(beat, brief), brief, mod.emotion); spoken = spoken_text(beat)
    else:
        spoken = a.text or '把几份资料放在一起之后，它能不能在回答时找回关键证据？这一步决定了你到底敢不敢把活交给它。'
        emo = (tts.get('emotion') or {}).get('default', ''); text = (mod.emotion(emo) if emo else '') + spoken
    sweep = [float(x) for x in (a.sweep.split(',') if a.sweep else [])] or [round(lo + (hi - lo) * k / 5, 2) for k in range(6)]
    import keys
    key, source = keys.provider_key(provider); print(f'credential: {source}; provider {provider}; param {name}; target {target} cps')
    cfg = voice_edit.settings(brief); folder = project / 'work/calibration'; folder.mkdir(parents=True, exist_ok=True)
    voice = {**tts, 'model': tts.get('model') or getattr(mod, 'DEFAULT_MODELS', [''])[0]}
    rows = []
    for value in sweep:
        if not lo <= value <= hi: raise ValueError(f'{name} must be within {lo}..{hi}')
        params = beat_params(brief, {}, mod.PARAM_KEYS, {name: value})
        dest = folder / f'{provider}-{name}-{value}.wav'
        r = synthesize_text(mod, text, voice, params, dest, key, log=print)
        raw_cps = cps(spoken, r['seconds']); edited_cps = None
        if cfg.get('enabled', True):
            rep = voice_edit.edit_beat(project, f'calib-{value}', dest, r['tokens'], cfg, spoken, dest=folder / f'{provider}-{name}-{value}.edited.wav')
            edited_cps = rep['measuredCps']
        rows.append({name: value, 'rawSeconds': r['seconds'], 'rawCps': raw_cps, 'editedCps': edited_cps})
        print(f'  {name}={value}: raw {r["seconds"]:.2f}s {raw_cps} cps' + (f', edited {edited_cps} cps' if edited_cps is not None else ''))
    key_cps = lambda row: row['editedCps'] if row['editedCps'] is not None else row['rawCps']
    best = min(rows, key=lambda row: abs(key_cps(row) - target))
    result = {'provider': provider, 'param': name, 'target': target, 'rows': rows, 'best': best, 'note': 'Choose by edited cps (what the film hears). Confirm by listening: clarity beats the number.'}
    write(folder / f'{provider}-calibration.json', result); print(json.dumps({'best': best, 'file': str(folder / f'{provider}-calibration.json')}, ensure_ascii=False))
    if a.apply:
        brief.setdefault('tts', {}).setdefault('params', {})[name] = best[name]; write(project / 'content/brief.json', brief); print(f'brief.tts.params.{name} = {best[name]}')


def run_measure(a):
    project = a.project.resolve()
    if a.audio:
        if not a.text: raise ValueError('--text is required with --audio')
        print(json.dumps({'seconds': round(duration(a.audio), 3), 'cps': cps(a.text, duration(a.audio))})); return
    script = read(project / 'content/script.json'); index = read(project / 'public/narration/index.json', {}); durations = read(project / 'content/narration-durations.json', {})
    target = (read(project / 'content/brief.json').get('pacing') or {}).get('targetCps')
    for b in script['beats']:
        if a.only and b['id'] not in set(a.only.split(',')): continue
        if b['id'] not in durations: continue
        c = cps(spoken_text(b), durations[b['id']]); flag = '' if target is None else ('  ✓' if abs(c - target) <= (read(project / 'content/brief.json').get('pacing') or {}).get('toleranceCps', 0.7) else '  ⚠ off target')
        print(f"{b['id']:14s} {durations[b['id']]:6.2f}s  {c:5.2f} cps  {index.get(b['id'], {}).get('provider', '?')}{flag}")


def run_providers(a):
    import keys
    for name in list(PROVIDERS) + ['host']:
        status = keys.key_status(name if name != 'host' else 'host-tts')
        mod = adapter(name) if name in PROVIDERS else None
        print(json.dumps({'provider': name, 'paceParam': getattr(mod, 'PACE_PARAM', None), 'maxChars': getattr(mod, 'MAX_CHARS', None), 'timestamps': 'native' if name == 'fish' else 'import or whisper', **status}, ensure_ascii=False))


def main():
    argv = sys.argv[1:]
    sub = argv[0] if argv and argv[0] in SUBS else 'synth'
    if sub != 'synth': argv = argv[1:]
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    if sub != 'providers': p.add_argument('project', type=Path)
    if sub == 'synth':
        p.add_argument('--only'); p.add_argument('--provider'); p.add_argument('--force', action='store_true'); p.add_argument('--no-edit', action='store_true'); p.add_argument('--no-align', action='store_true'); p.add_argument('--dry-run', action='store_true'); p.add_argument('--param', action='append')
    elif sub == 'plan': p.add_argument('--only')
    elif sub == 'import':
        p.add_argument('--id', required=True); p.add_argument('--audio', required=True); p.add_argument('--timestamps'); p.add_argument('--tempo', type=float, default=1.0); p.add_argument('--provider', default='host'); p.add_argument('--model'); p.add_argument('--speaker'); p.add_argument('--no-edit', action='store_true'); p.add_argument('--no-align', action='store_true')
    elif sub == 'calibrate':
        p.add_argument('--provider'); p.add_argument('--text'); p.add_argument('--beat'); p.add_argument('--sweep'); p.add_argument('--target-cps', type=float); p.add_argument('--apply', action='store_true')
    elif sub == 'measure':
        p.add_argument('--only'); p.add_argument('--audio'); p.add_argument('--text')
    a = p.parse_args(argv)
    {'synth': run_synth, 'plan': run_plan, 'import': run_import, 'calibrate': run_calibrate, 'measure': run_measure, 'providers': run_providers}[sub](a)


if __name__ == '__main__': run_main(main)
