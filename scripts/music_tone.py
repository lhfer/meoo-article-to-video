"""Music tone: map product/profile/script evidence to a BGM archetype, BPM range, structure, prompt, and candidate scoring.
Pure functions only (no ffmpeg, no filesystem) so music.py plan/rank stay testable; the tables are the house taste, not platform facts."""
from common import norm

# 调性原型：短视频配乐的八种"感觉"，每种给出风格、乐器、BPM 与适用题材。
ARCHETYPES = {
    'hype':     {'zh': '燃',     'bpm': (130, 150), 'genre': '高能电子 / trap-rock 混合', 'instruments': '硬底鼓、808 低音、铜管重音、失真合成器主音；riser 不超过 1 小节', 'feel': '热血、对抗、冲刺', 'fits': '重大发布、正面对决、榜单、赛事、颠覆式新闻'},
    'upbeat':   {'zh': '动感',   'bpm': (118, 132), 'genre': 'future bass / 电子流行', 'instruments': '明亮 pluck、侧链 pad、干净鼓组、拍手', 'feel': '轻快、年轻、有推进感', 'fits': '科技资讯、新功能、消费类 App、社交与内容产品'},
    'groove':   {'zh': '节奏',   'bpm': (92, 112),  'genre': 'boom-bap / lo-fi hip-hop / 轻 trap', 'instruments': '干鼓、sub 低音、稀疏 pluck、黑胶质感；几乎没有旋律', 'feel': '松弛、有律动、不抢戏', 'fits': '教程、清单、案例拆解、口播密集的内容'},
    'calm':     {'zh': '沉稳',   'bpm': (84, 104),  'genre': '极简电子 / 柔和钢琴', 'instruments': '柔和 pad、轻钢琴、软鼓、细碎打击', 'feel': '克制、可靠、专业', 'fits': '开发者工具、效率工具、B 端产品、作者宣发'},
    'tech':     {'zh': '科技冷感', 'bpm': (100, 120), 'genre': '模拟合成器琶音 + glitch 打击', 'instruments': '琶音器、细线打击、低频脉冲、少量 glitch', 'feel': '精密、极客、未来', 'fits': 'AI / 基础设施 / CLI / API 类产品与深度解读'},
    'warm':     {'zh': '温暖',   'bpm': (90, 110),  'genre': '原声流行 / indie folk', 'instruments': '木吉他、轻鼓刷、钢片琴、人声式 pad（无歌词）', 'feel': '亲切、治愈、生活化', 'fits': '生活方式、亲子、健康、陪伴类产品'},
    'suspense': {'zh': '悬念',   'bpm': (88, 108),  'genre': '脉冲式电影电子', 'instruments': '低频 drone、滴答打击、脉冲 bass、偶发重音', 'feel': '紧张、反转、追问', 'fits': '争议、翻车、反转、调查类资讯'},
    'uplift':   {'zh': '励志',   'bpm': (100, 120), 'genre': '钢琴 + 弦乐 + 电子铺底', 'instruments': '钢琴动机、弦乐层叠、电子鼓渐进', 'feel': '成长、故事、希望', 'fits': '作者历程、案例故事、从 0 到 1'},
}
PROFILE_DEFAULT = {'viral': 'upbeat', 'launch': 'calm'}
# 关键词 → 原型（产品卡 tone.adjectives / category / audience 与脚本文本共用）
KEYWORDS = [
    ('hype', ['燃', '热血', '竞技', '对决', '炸裂', '极限', '赛事', '冲刺', '硬刚', '碾压']),
    ('suspense', ['争议', '反转', '翻车', '塌房', '被骂', '内幕', '疑点', '调查', '悬念', '真相']),
    ('tech', ['极客', '硬核', '开发者', '基础设施', '命令行', 'cli', 'api', 'sdk', '模型', '推理', '编译', '终端', 'agent', '自动化', '高级', '精密', '旗舰', '质感', '工艺', '设计感']),
    ('warm', ['温暖', '治愈', '家庭', '亲子', '生活', '陪伴', '健康', '宠物', '手账', '日记']),
    ('uplift', ['励志', '成长', '故事', '历程', '从零', '从 0', '坚持', '逆袭']),
    ('groove', ['教程', '清单', '拆解', '步骤', '手把手', '技巧', '合集']),
    ('calm', ['沉稳', '专业', '克制', '可靠', '极简', '效率', '笔记', '待办', '安全', '金融', '企业', 'b端', '严谨']),
    ('upbeat', ['动感', '活力', '年轻', '潮', '好玩', '社交', '短视频', '游戏', '创作者', '有趣', '新功能', '重磅', '发布', '新品']),
]
# 生成模型常见的、正好踩在短视频雷区上的毛病，一律写成"不要"。
NEGATIVES = ['不要人声、哼唱或歌词', '不要长前奏：第一小节就进鼓，开头 2 秒内出现一个明确重击', '不要淡入', '不要电影预告片式的长 riser 与 braam',
             '不要突然的静音段或整段抽掉鼓', '不要廉价的 trap 音色和塑料感的预置音色', '避免 1–4 kHz 的持续主旋律，把中频让给人声', '不要任何水印或采样人声']
PLATFORM_ZH = {'xiaohongshu': '小红书', 'bilibili': 'B站', 'douyin': '抖音', 'shipinhao': '视频号', 'wechat-channels': '视频号', 'kuaishou': '快手', 'x': 'X', 'youtube': 'YouTube', 'weibo': '微博'}


def _hits(text, words):
    t = norm(text or '')
    return [w for w in words if norm(w) and norm(w) in t]


def derive_archetype(brief=None, product=None, script=None):
    """Return (archetype, reasons). Order: brief.music.archetype → product card (tone/category/audience) → script text → profile default."""
    brief = brief or {}; product = product or {}; script = script or {}
    profile = brief.get('profile', 'viral'); reasons = []
    explicit = (brief.get('music') or {}).get('archetype')
    if explicit:
        if explicit not in ARCHETYPES: raise ValueError(f'Unknown music archetype {explicit}; one of {sorted(ARCHETYPES)}')
        return explicit, [f'brief.music.archetype = {explicit}（显式指定）']
    tone = product.get('tone') or {}
    tone_text = ' '.join([*(tone.get('adjectives') or []), product.get('category') or '', (product.get('audience') or {}).get('who') or '', product.get('oneLiner') or ''])
    scores = {}
    for key, words in KEYWORDS:
        hit = _hits(tone_text, words)
        if hit: scores[key] = scores.get(key, 0) + len(hit); reasons.append(f'产品卡命中「{"、".join(hit)}」→ {ARCHETYPES[key]["zh"]}')
    energy = tone.get('energy')
    if isinstance(energy, (int, float)):
        # 燃 only comes from explicit words (燃 / 对决 / 碾压…); high energy alone means 动感, so a premium launch does not get a trap-rock bed.
        pick = 'upbeat' if energy >= 3 else ('calm' if profile == 'launch' else 'groove')
        scores[pick] = scores.get(pick, 0) + 1.5; reasons.append(f'产品卡 tone.energy = {energy} → {ARCHETYPES[pick]["zh"]}')
    if scores:
        best = max(scores, key=lambda k: (scores[k], k)); reasons.append(f'综合得分最高：{ARCHETYPES[best]["zh"]} ({best})')
        return best, reasons
    text = ' '.join(b.get('narration', '') for b in script.get('beats', []))
    for key in ('suspense', 'hype'):
        hit = _hits(text, dict(KEYWORDS)[key])
        if len(hit) >= 2: reasons.append(f'脚本出现「{"、".join(hit[:3])}」→ {ARCHETYPES[key]["zh"]}'); return key, reasons
    beats = script.get('beats', [])
    if profile == 'viral' and beats and sum(1 for b in beats if b.get('kind') in ('evidence', 'chapter')) / len(beats) >= 0.6:
        reasons.append('脚本以拆解 / 证据为主（口播密集）→ 节奏'); return 'groove', reasons
    default = PROFILE_DEFAULT.get(profile, 'upbeat'); reasons.append(f'无产品卡与脚本线索，按 profile {profile} 默认 → {ARCHETYPES[default]["zh"]}')
    return default, reasons


def bpm_range(archetype, target_cps=None, visual_change_max=None):
    """Nudge the archetype's BPM window toward the narration pace: faster speech and faster cuts want a faster pulse."""
    lo, hi = ARCHETYPES[archetype]['bpm']; shift = 0
    if target_cps is not None: shift += 6 if target_cps >= 7.8 else (-6 if target_cps <= 7.0 else 0)
    if visual_change_max is not None: shift += 4 if visual_change_max <= 1.5 else (-4 if visual_change_max >= 2.5 else 0)
    shift = max(-8, min(8, shift))
    return lo + shift, hi + shift


def estimate_beats(script, brief):
    """Approximate beat start/end seconds from narration length when no timeline exists (chars / targetCps + default gap)."""
    from common import weighted_len, spoken_text
    cps = float((brief.get('pacing') or {}).get('targetCps') or 8.0); gap = float(((brief.get('pacing') or {}).get('gapPolicy') or {}).get('default', 0.3))
    t = 0.0; out = []
    for b in script.get('beats', []):
        text = b.get('narration', '')
        if not text.strip(): continue
        try: spoken = spoken_text(b)
        except Exception: spoken = text
        seconds = max(0.6, weighted_len(spoken) / cps)
        out.append({'id': b['id'], 'kind': b.get('kind'), 'start': round(t, 2), 'end': round(t + seconds, 2)}); t += seconds + gap
    return out


def structure(beats, total_seconds):
    """Where the music should drop, lift and resolve, in film seconds. `beats` = [{id, kind, start, end}]."""
    turn = next((b for b in beats if b.get('kind') == 'turn'), None)
    lift = round(turn['start'], 2) if turn else round(total_seconds * 0.45, 2)
    summary = next((b for b in beats if b.get('kind') in ('summary', 'cta', 'ending')), None)
    settle = round(summary['start'], 2) if summary else round(total_seconds * 0.8, 2)
    points = [{'at': 0.0, 'want': 'drop', 'zh': '第一小节进鼓，0–2 秒内一个明确重击（对位 hook 词）'}]
    if total_seconds >= 10 and 3.0 <= lift < total_seconds - 3: points.append({'at': lift, 'want': 'lift', 'zh': '能量抬升一次（对位转折 / 最强论点）'})
    if settle >= lift + 3 and settle < total_seconds - 1: points.append({'at': settle, 'want': 'settle', 'zh': '收束到轻的节奏床，给总结 / CTA 留空间'})
    points.append({'at': round(total_seconds, 2), 'want': 'end', 'zh': '干净结束，可无缝循环'})
    return points  # sections are in time order; short films (< ~8 s) collapse to drop + end


def build_prompt(archetype, bpm, structure_points, total_seconds, platforms=(), product=None, extra=''):
    """Chinese prompt for fun-music-v1 style generators (verified limit: 1–2000 chars; duration cannot be requested, only described)."""
    a = ARCHETYPES[archetype]; product = product or {}
    plat = '、'.join(PLATFORM_ZH.get(p, p) for p in platforms) or '短视频平台'
    subject = product.get('oneLiner') or product.get('name') or ''
    lift = next((p for p in structure_points if p['want'] == 'lift'), None); settle = next((p for p in structure_points if p['want'] == 'settle'), None)
    parts = [f'纯音乐背景，整体气质：{a["zh"]}（{a["feel"]}）。风格：{a["genre"]}；速度约 {bpm[0]}–{bpm[1]} BPM；乐器：{a["instruments"]}。',
             f'用途：{plat}竖屏短视频的背景音乐，人声旁白全程压在上面，整曲约 {int(round(total_seconds + 4))} 秒' + (f'，内容是「{subject[:40]}」' if subject else '') + '。',
             '结构：第一小节直接进鼓，开头 2 秒内有一个清晰的重击' + (f'；约第 {int(round(lift["at"]))} 秒能量抬升一次' if lift and lift['at'] > 2 else '') + (f'；约第 {int(round(settle["at"]))} 秒后收束成轻的节奏床' if settle and settle['at'] > 4 else '') + '；结尾干净，可无缝循环。',
             '混音：以低频与打击为主，中频留给人声；动态清晰、不要砖墙压缩。', '要求：' + '；'.join(NEGATIVES) + '。']
    if extra: parts.append(extra.strip())
    text = ''.join(parts)
    return text[:2000]


VARIATIONS = [('main', '主线版：按上面的描述'), ('percussive', '打击版：去掉大部分旋律，只留鼓组、低音与织体，给旁白更多空间'), ('bright', '高能版：更亮的合成器音色，重击更硬，抬升更明显')]


def plan_spec(brief, product=None, script=None, beats=None, total_seconds=None, platforms=None, archetype=None, candidates=3, extra=''):
    """Full generation plan: archetype + reasons, bpm, structure, N prompt variations, and what to check on the results."""
    product = product or {}; script = script or {}; music_cfg = brief.get('music') or {}
    key, reasons = (archetype, [f'--archetype {archetype}（命令行指定）']) if archetype else derive_archetype(brief, product, script)
    if key not in ARCHETYPES: raise ValueError(f'Unknown music archetype {key}; one of {sorted(ARCHETYPES)}')
    pacing = brief.get('pacing') or {}
    bpm = bpm_range(key, pacing.get('targetCps'), pacing.get('visualChangeMaxSeconds'))
    beats = beats if beats is not None else estimate_beats(script, brief)
    total = float(total_seconds if total_seconds is not None else (beats[-1]['end'] if beats else 60.0))
    points = structure(beats, total)
    plats = list(platforms if platforms is not None else (brief.get('platforms') or []))
    n = max(1, int(candidates or music_cfg.get('candidates') or 1))
    prompts = []
    for i, (vid, vtext) in enumerate(VARIATIONS[:n]):
        prompts.append({'id': vid, 'prompt': build_prompt(key, bpm, points, total, plats, product, (vtext if i else '') + ('\n' + extra if extra else ''))})
    return {'archetype': key, 'archetypeZh': ARCHETYPES[key]['zh'], 'reasons': reasons, 'bpm': list(bpm), 'feel': ARCHETYPES[key]['feel'], 'genre': ARCHETYPES[key]['genre'],
            'structure': points, 'totalSeconds': round(total, 2), 'platforms': plats, 'prompts': prompts, 'negatives': NEGATIVES,
            'checks': ['首个强重击 ≤ 2 s（rank 会量）', 'BPM 落在区间内（允许 ½× / 2× 歧义）', '人声频段（1–4 kHz）能量占比低', '实际听：无人声、无淡入、无突兀静音', '时长 ≥ 成片长度 + 2 s，否则 fit 时截取或循环']}


def tempo_match(estimates, bpm):
    """Best match of analyzer tempo estimates to the wanted window, accepting half/double-time readings. Returns (matched_bpm|None, factor)."""
    lo, hi = bpm
    for est in estimates or []:
        for factor in (1.0, 2.0, 0.5):
            v = est * factor
            if lo - 8 <= v <= hi + 8: return round(v, 1), factor  # archetype windows are taste, not physics: ±8 BPM tolerance
    return None, None


def score_candidate(metrics, bpm, needed_seconds):
    """0–1 score with a breakdown. Metrics come from _music_analyze.py (firstStrongHitSeconds, tempoEstimatesBpm, tempoConfidence, speechBandRatio, durationSeconds, crestFactorDb)."""
    first = metrics.get('firstStrongHitSeconds'); first = 99.0 if first is None else float(first)
    s_first = 1.0 if first <= 2.0 else (0.7 if first <= 3.0 else (0.3 if first <= 5.0 else 0.0))
    matched, _ = tempo_match(metrics.get('tempoEstimatesBpm') or [], bpm)
    conf = float(metrics.get('tempoConfidence') or 0.5)
    s_tempo = (1.0 if matched else 0.0) * min(1.0, 0.5 + conf / 2)
    band = metrics.get('speechBandRatio'); band = 0.45 if band is None else float(band)
    s_band = 1.0 if band <= 0.25 else max(0.0, 1.0 - (band - 0.25) / 0.30)
    dur = float(metrics.get('durationSeconds') or 0); s_dur = 1.0 if dur >= needed_seconds else max(0.0, dur / max(1.0, needed_seconds))
    crest = float(metrics.get('crestFactorDb') or 0); s_crest = 1.0 if crest >= 8 else max(0.0, crest / 8)
    total = 0.30 * s_first + 0.25 * s_tempo + 0.25 * s_band + 0.15 * s_dur + 0.05 * s_crest
    return round(total, 4), {'firstHit': (round(first, 2), s_first), 'tempo': (matched, round(s_tempo, 2)), 'speechBand': (round(band, 3), round(s_band, 2)), 'duration': (round(dur, 1), round(s_dur, 2)), 'crest': (round(crest, 1), round(s_crest, 2))}


def bar_grid(bpm, downbeat_music_seconds, trim_start, start, end, beats_per_bar=4, beats=False):
    """Bar (and optionally beat) events in film seconds for 卡点: phase from a downbeat hit in music time, shifted by the fitted trim/start."""
    if not bpm or bpm <= 0: raise ValueError('bpm required')
    step = 60.0 / bpm * (1 if beats else beats_per_bar)
    offset = downbeat_music_seconds - trim_start + start
    first_k = int(((start - offset) // step) - 1)
    out = []; k = first_k; i = 0
    while True:
        t = offset + k * step; k += 1
        if t < start - 1e-6: continue
        if t > end + 1e-6: break
        i += 1; out.append({'id': f"bgm.{'beat' if beats else 'bar'}_{i}", 'seconds': round(t, 3)})
    return out
