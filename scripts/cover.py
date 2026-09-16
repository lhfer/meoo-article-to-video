#!/usr/bin/env python3
"""Covers made by an image model (title text included), one per platform ratio, chosen from real candidates.

  cover.py <project> plan   [--title "…"] [--subject "…"] [--ratios 3x4,9x16,16x9] [--style-file F] [--reference auto|<materialId|assetId|path>|none] [--fit pad|crop] [--hook "…"]
  cover.py <project> generate --ratio 3x4 [--n 4] [--provider grok] [--reference <image>] [--variant-file F]
  cover.py <project> ingest   --ratio 3x4 --input <image from a host image tool> [--prompt-file F]
  cover.py <project> sheet    [--ratio 3x4]
  cover.py <project> select   --ratio 3x4 --id <candidateId> [--upscale]
Prompts encode the de-AI vocabulary and the platform composition from references/covers.md; every candidate must be
looked at (title characters correct, hands, symmetry, thumbnail legibility) before select.
"""
import argparse, json, shutil, subprocess, sys, time
from pathlib import Path
from common import inside, ROOT, read, write, ident, run_main

RATIOS = {'3x4': ('3:4', 1080, 1440, '小红书'), '9x16': ('9:16', 1080, 1920, '抖音／视频号'), '16x9': ('16:9', 1920, 1080, 'Bilibili')}
COMPOSITION = {
    '3x4': '竖版 3:4 构图：主体占画面上方约 2/3 并偏大，底部 1/4 留出干净区域放标题；单一视觉焦点，高对比。',
    '9x16': '竖版 9:16 构图：主体在上方 2/3 居中偏上，脸或物件要大；画面底部 25% 保持简洁（会被平台界面遮挡），标题放在中上部。',
    '16x9': '横版 16:9 构图：主体占左侧或右侧约 2/3，另一侧大面积留白放标题；缩略图很小也要一眼看清主体。',
}
TITLE_CHARS = {'3x4': '8–14', '9x16': '4–8', '16x9': '6–12'}
# What makes a thumb stop: platform-specific, written into every prompt (the old "吸睛、点开欲高" said nothing the model could draw).
CLICK = {
    '3x4': '小红书信息流：生活场景里正在发生的一个动作，明亮自然光，画面下方留一块干净高对比色块给标题；主体带一点张力（半折的手机、正在被删掉的账单、屏幕上刚跳出的结果）。',
    '9x16': '抖音全屏：主体占画面 60% 以上，脸或物件要大，元素少、对比强；一个动作正在发生、一个情绪线索（手、表情、光），标题放在中上部的干净区域。',
    '16x9': 'B 站封面：主体一眼可辨、有表情或物件的张力，另一侧大面积色块或留白放标题；缩略图 320px 宽也要看清主体。',
}
SUBJECT_LOCK = '主体以参考图为准：产品 / 界面的外观、颜色、文字、比例与参考图完全一致，不得重新设计或换成别的设备；只改场景、光线、构图与标题。'
REFERENCE_BG = '#f4f4f6'


def hook_line(script, explicit=None):
    """The visual hook: what the first sentence promises, drawn as one action or tension."""
    if explicit: return f'视觉钩子：{explicit}'
    hook = next((b for b in script.get('beats', []) if b.get('kind') == 'hook' and b.get('narration', '').strip()), None)
    text = (hook or {}).get('narration') or script.get('thesis') or ''
    return f'视觉钩子：把「{text[:30]}」画成一个正在发生的动作或张力，而不是摆拍。' if text else ''


def pick_reference(product, materials, film):
    """Reference image to lock the subject: product.media with a local asset → ready image materials → film image assets. Returns (assetId|path, why) or (None, why)."""
    for m in (product or {}).get('media', []):
        if m.get('kind') in ('image', 'screenshot') and m.get('asset'): return m['asset'], f"产品卡素材 {m['id']}（{m.get('rights') or '权利未填'}）"
    for it in (materials or {}).get('items', []):
        if it.get('status') == 'ready' and it.get('assetId'): return it['assetId'], f"素材台账 {it['id']}"
    for aid, a in ((film or {}).get('assets') or {}).items():
        if a.get('kind') == 'image': return aid, f'正片素材 {aid}'
    return None, '没有可用的真实图片（产品卡 media / 素材台账 ready / 正片图片素材都为空）：退回纯文生图，cover-qa 里标明'


def resolve_reference(project, spec):
    """--reference auto|<materialId|assetId|path>|none → (absolute path or None, why)."""
    if spec in (None, '', 'none'): return None, '未使用参考图'
    film = read(project / 'content/film.json', {}); materials = read(project / 'content/materials.json', {}); product = read(project / 'content/product.json', {})
    key, why = (pick_reference(product, materials, film) if spec == 'auto' else (spec, f'指定 {spec}'))
    if key is None: return None, why
    asset = (film.get('assets') or {}).get(key)
    if asset: return inside(project / 'public', asset['src']), why
    item = next((x for x in materials.get('items', []) if x['id'] == key), None)
    if item and item.get('assetId') and (film.get('assets') or {}).get(item['assetId']): return inside(project / 'public', film['assets'][item['assetId']]['src']), why
    path = Path(key).expanduser()
    if path.is_file(): return path.resolve(), why
    raise ValueError(f'Reference {key} is not a film asset, a ready material, or a file')


def prepare_reference(src, ratio, out, fit='pad'):
    """Grok image_edit inherits the input aspect, so the reference is padded (default) or center-cropped to the target ratio first."""
    _, w, h, _ = RATIOS[ratio]
    vf = (f'scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color={REFERENCE_BG}' if fit == 'pad'
          else f'scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}')
    out.parent.mkdir(parents=True, exist_ok=True); subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(src), '-vf', vf, str(out)], check=True); return out
REAL = '真实相机拍摄质感，35mm 或 50mm 镜头，自然光或单一主光源，浅景深，轻微胶片颗粒与暗角，手持的轻微不对称，材质和皮肤保留真实瑕疵与反光；像一张真的照片，不像渲染图。'
NEGATIVE = '不要：塑料感高光、过度锐化、彩虹渐变、完美对称、多余的手指或肢体、乱码或多余文字、水印、logo、磨皮、过曝白边、3D 渲染感。'


def title_line(ratio, title, brief):
    if not (brief.get('cover') or {}).get('titleInImage', True): return '画面中不要出现任何文字。'
    return f'在画面{"底部" if ratio == "3x4" else "中上部" if ratio == "9x16" else "留白一侧"}用粗黑体中文写标题「{title}」（{TITLE_CHARS[ratio]} 字，字要大、对比强、逐字正确、不能出现任何其他文字）。'


def cmd_plan(a):
    project = a.project.resolve(); script = read(project / 'content/script.json'); visual = read(project / 'content/visual.json', {}); brief = read(project / 'content/brief.json', {})
    title = a.title or script.get('coverTitle') or script.get('title', '')
    if not title: raise ValueError('Provide --title or script.title')
    subject = a.subject or visual.get('coverSubject') or visual.get('concept', '')
    style = Path(a.style_file).read_text(encoding='utf-8').strip() if a.style_file else (visual.get('stylePrompt') or '')
    ratios = [r for r in (a.ratios.split(',') if a.ratios else (brief.get('cover') or {}).get('ratios', list(RATIOS)))]
    folder = project / 'work/cover/prompts'; folder.mkdir(parents=True, exist_ok=True)
    cover = read(project / 'content/cover.json', {'version': 1, 'candidates': [], 'selected': {}})
    ref_src, ref_why = resolve_reference(project, a.reference if a.reference is not None else 'auto')
    cover.update(title=title, subject=subject, prompts={}, reference={'source': str(ref_src) if ref_src else None, 'why': ref_why, 'fit': a.fit})
    print(f'参考图：{ref_src or "无"} — {ref_why}')
    hook = hook_line(script, a.hook)
    for r in ratios:
        if r not in RATIOS: raise ValueError('Unknown ratio ' + r)
        ref = prepare_reference(ref_src, r, project / 'work/cover/ref' / f'{r}.png', a.fit) if ref_src else None
        lines = [f'为{RATIOS[r][3]}封面生成一张真实感强的图。', CLICK[r], f'主体：{subject}', SUBJECT_LOCK if ref else '', hook, COMPOSITION[r], REAL, style]
        prompt = '\n'.join(x for x in lines + [title_line(r, title, brief), NEGATIVE] if x).strip()
        notitle = '\n'.join(x for x in lines + ['画面中不要出现任何文字（无字版：标题在平台内添加或做 A/B）。', NEGATIVE] if x).strip()
        (folder / f'{r}.txt').write_text(prompt, encoding='utf-8'); (folder / f'{r}-notitle.txt').write_text(notitle, encoding='utf-8')
        cover['prompts'][r] = {'file': str((folder / f'{r}.txt').relative_to(project)), 'noTitleFile': str((folder / f'{r}-notitle.txt').relative_to(project)), 'aspect': RATIOS[r][0], 'reference': str(ref.relative_to(project)) if ref else None}
        print(f'--- {r} ({RATIOS[r][3]}) ---\n{prompt}\n')
    write(project / 'content/cover.json', cover); print('Prompts written (with a no-title variant each); edit the subject/hook lines if needed, then cover.py generate / ingest. Reference (if any) is pre-fitted under work/cover/ref/.')


def register(project, ratio, path, provider, prompt, reference=None):
    cover = read(project / 'content/cover.json', {'version': 1, 'candidates': [], 'selected': {}})
    n = 1 + sum(1 for c in cover['candidates'] if c['ratio'] == ratio); cid = f'{ratio}-{n}'
    info = subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'stream=width,height', '-of', 'csv=p=0', str(path)]).decode().strip().split(',')
    cover['candidates'].append({'id': cid, 'ratio': ratio, 'file': str(path.relative_to(project)), 'width': int(info[0]), 'height': int(info[1]), 'provider': provider, 'prompt': prompt, 'reference': reference, 'createdAt': time.strftime('%Y-%m-%dT%H:%M:%S'), 'checked': None})
    write(project / 'content/cover.json', cover); return cid


def cmd_generate(a):
    project = a.project.resolve(); ratio = a.ratio
    if ratio not in RATIOS: raise ValueError('Unknown ratio ' + ratio)
    cover = read(project / 'content/cover.json', None)
    if not cover or ratio not in cover.get('prompts', {}): raise ValueError('Run cover.py plan first')
    base = (project / cover['prompts'][ratio]['noTitleFile' if a.no_title else 'file']).read_text(encoding='utf-8')
    variant = Path(a.variant_file).read_text(encoding='utf-8').strip() if a.variant_file else ''
    if a.reference is None and cover['prompts'][ratio].get('reference'): a.reference = str(project / cover['prompts'][ratio]['reference'])
    if a.reference == 'none': a.reference = None
    out_dir = project / 'public/cover/candidates'; out_dir.mkdir(parents=True, exist_ok=True)
    for k in range(a.n):
        prompt = base + (('\n变体：' + variant) if variant and k >= a.n // 2 else '')
        stamp = str(time.time_ns()); job = project / 'work/cover/jobs' / f'{ratio}-{stamp}'; job.mkdir(parents=True, exist_ok=True)
        (job / 'prompt.txt').write_text(prompt, encoding='utf-8'); out = out_dir / f'{ratio}-{stamp}.png'
        if a.provider != 'grok': raise ValueError('Only the local grok provider generates here; host image tools go through cover.py ingest')
        cmd = [sys.executable, str(ROOT / 'scripts/grok_media.py'), 'edit' if a.reference else 'image', '-o', str(out), '--prompt-file', str(job / 'prompt.txt'), '--work-dir', str(job)]
        cmd += ['--image', str(Path(a.reference).expanduser().resolve()), '--aspect', RATIOS[ratio][0]] if a.reference else ['--aspect', RATIOS[ratio][0]]
        if a.dry_run: print(json.dumps({'executed': False, 'cmd': cmd, 'prompt': prompt}, ensure_ascii=False, indent=2)); continue
        with (job / 'result.log').open('w') as log: r = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT)
        if r.returncode != 0 or not out.is_file(): print(f'candidate {k + 1}: generation failed; see {job / "result.log"}'); continue
        cid = register(project, ratio, out, 'grok-cli', prompt, a.reference); print(f'{cid}: {out}')
    print('Look at every candidate (title characters, hands, symmetry, 200px legibility), then cover.py sheet / select.')


def cmd_ingest(a):
    project = a.project.resolve(); ratio = a.ratio; src = Path(a.input).expanduser().resolve()
    if ratio not in RATIOS: raise ValueError('Unknown ratio ' + ratio)
    if not src.is_file(): raise ValueError('Input image does not exist')
    out_dir = project / 'public/cover/candidates'; out_dir.mkdir(parents=True, exist_ok=True); out = out_dir / f'{ratio}-{time.time_ns()}.png'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(src), str(out)], check=True)
    prompt = Path(a.prompt_file).read_text(encoding='utf-8') if a.prompt_file else ''
    cid = register(project, ratio, out, a.provider or 'host-image', prompt, None); print(f'{cid}: {out}')


def cmd_sheet(a):
    project = a.project.resolve(); cover = read(project / 'content/cover.json', {'candidates': []})
    for ratio in ([a.ratio] if a.ratio else sorted({c['ratio'] for c in cover['candidates']})):
        files = [project / c['file'] for c in cover['candidates'] if c['ratio'] == ratio]
        if not files: continue
        out = project / 'out' / f'cover-sheet-{ratio}.jpg'; out.parent.mkdir(exist_ok=True)
        inputs = []; filters = []
        for i, f in enumerate(files): inputs += ['-i', str(f)]; filters.append(f'[{i}:v]scale=360:-2[b{i}];[{i}:v]scale=200:-2,pad=360:ih:80:0:black[t{i}];[b{i}][t{i}]vstack[c{i}]')
        graph = ';'.join(filters) + ';' + ''.join(f'[c{i}]' for i in range(len(files))) + f'hstack=inputs={len(files)}[out]'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', *inputs, '-filter_complex', graph, '-map', '[out]', '-frames:v', '1', str(out)], check=True)
        print(f'{ratio}: {out} (top row full, bottom row 200px thumbnails — judge legibility from the small ones)')


def cmd_select(a):
    project = a.project.resolve(); cover = read(project / 'content/cover.json'); c = next((x for x in cover['candidates'] if x['id'] == a.id), None)
    if not c or c['ratio'] != a.ratio: raise ValueError('Unknown candidate for that ratio')
    w, h = RATIOS[a.ratio][1], RATIOS[a.ratio][2]; out = project / 'out' / f'cover-{a.ratio}.png'; out.parent.mkdir(exist_ok=True)
    if a.upscale and (c['width'] < w or c['height'] < h):
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(project / c['file']), '-vf', f'scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos,crop={w}:{h}', str(out)], check=True)
    else: shutil.copy2(project / c['file'], out)
    cover['selected'][a.ratio] = {'id': a.id, 'file': str(out.relative_to(project)), 'originalSize': [c['width'], c['height']], 'deliverySize': [w, h], 'note': a.note or ''}
    c['checked'] = a.note or 'selected'; write(project / 'content/cover.json', cover)
    qa = project / 'out/cover-qa.md'
    if not qa.exists(): qa.write_text('# 封面检查\n\n每张选定候选逐项打勾：标题逐字正确 / 手指与肢体 / 无诡异对称与塑料高光 / 景深合理 / 与正片主体色彩连续 / 200px 缩略图可辨主体 / 标题对比度 / 封面承诺与内容一致\n\n', encoding='utf-8')
    with qa.open('a', encoding='utf-8') as fh: fh.write(f"- {a.ratio}: {a.id} → {out.name} ({c['width']}×{c['height']} → {w}×{h}). {a.note or ''}\n")
    print(out)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter); p.add_argument('project', type=Path); sub = p.add_subparsers(dest='cmd', required=True)
    q = sub.add_parser('plan'); q.add_argument('--title'); q.add_argument('--subject'); q.add_argument('--ratios'); q.add_argument('--style-file'); q.add_argument('--reference', help='auto (default) | materialId | assetId | path | none'); q.add_argument('--fit', choices=['pad', 'crop'], default='pad'); q.add_argument('--hook', help='visual hook line; default derived from the hook beat'); q.set_defaults(fn=cmd_plan)
    q = sub.add_parser('generate'); q.add_argument('--ratio', required=True); q.add_argument('--n', type=int, default=4); q.add_argument('--provider', default='grok'); q.add_argument('--reference', help='override the plan reference; none = pure text-to-image'); q.add_argument('--no-title', action='store_true', help='use the no-title prompt variant'); q.add_argument('--variant-file'); q.add_argument('--dry-run', action='store_true'); q.set_defaults(fn=cmd_generate)
    q = sub.add_parser('ingest'); q.add_argument('--ratio', required=True); q.add_argument('--input', required=True); q.add_argument('--prompt-file'); q.add_argument('--provider'); q.set_defaults(fn=cmd_ingest)
    q = sub.add_parser('sheet'); q.add_argument('--ratio'); q.set_defaults(fn=cmd_sheet)
    q = sub.add_parser('select'); q.add_argument('--ratio', required=True); q.add_argument('--id', required=True); q.add_argument('--upscale', action='store_true'); q.add_argument('--note'); q.set_defaults(fn=cmd_select)
    a = p.parse_args(); a.fn(a)


if __name__ == '__main__': run_main(main)
