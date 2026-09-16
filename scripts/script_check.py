#!/usr/bin/env python3
"""Retention review of content/script.json before any voice is made — the audience-seat pass from storytelling.md, measured.

  script_check.py <project> [--json]        # print the markdown (or JSON) report; exit 1 only on ERROR
  project.py script <project>               # runs this and appends the report to out/script-review.md

Hard errors are limited to the opening, because the first 3 seconds decide whether anyone stays: the first beat is the hook,
a hook anchor (number / name / question / contrast word) sits inside the first 3 seconds of text, and the opening is not a
greeting or a self-introduction. Everything else is a WARN or a 提示: calibrated on confirmed videos, where good scripts do break
the softer rules on purpose (a number called back, an ending that is a callback rather than a question).
Durations are estimates: chars ÷ brief.pacing.targetCps plus the gapPolicy gap per beat kind, the same numbers plan-voices uses."""
import argparse, json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import read, write, norm, weighted_len, CJK_RE, run_main

PUNCT = set('，。！？；：…、—（）()“”"\'!?,.;:')
SENT_END = '。！？…!?'
LIMITS = {'hookSeconds': 3.0, 'hookBeatSeconds': 6.0, 'breathWeighted': {'viral': 22, 'launch': 26}, 'beatSeconds': {'viral': 15, 'launch': 20},
          'turnWindow': (0.35, 0.75), 'factGapSeconds': 25, 'totalTolerance': 0.2, 'checkpoints': [3, 8, 15, 30, 60]}
# Words that make a first clause a hook: contrast, curiosity, stakes. A digit, an ASCII name, ？ or ！ count as anchors too.
HOOK_WORDS = ['到底', '竟然', '居然', '离谱', '免费', '唯一', '没人', '没想到', '真的', '为什么', '凭什么', '怎么', '谁', '不是', '别', '最', '第一', '一次', '一句话', '两句话',
              '全网', '所有', '翻车', '刚', '直接', '原来', '其实', '结果', '居然', '炸', '疯', '再也', '终于', '只要', '只用', '一天', '一夜', '一个人', '亲测', '实测', '真机', '上手']
OPENERS = ['大家好', '哈喽', '你好', 'hello', 'hi', '嗨', '今天给', '今天我们', '今天来', '今天要', '今天想', '这期', '本期', '欢迎', '我是', '首先', '在开始之前', '众所周知', '随着',
           '近年来', '近日', '据报道', '这条视频', '这个视频', '这条宣发', '这期视频', '这支视频', '本视频', '介绍一下', '给大家介绍', '分享一下']
MID_OPENERS = ['接下来', '下面我们', '下面来', '首先', '其次', '再来看看', '然后我们', '说完了', '让我们']
FILLER_END = ['感谢观看', '谢谢观看', '下期见', '拜拜', '记得点赞', '一键三连', '点赞关注', '关注我', '我们下期', '下次再见']
BRIDGES = ['但', '可', '然而', '不过', '结果', '所以', '因为', '于是', '那', '然后', '后来', '问题是', '关键是', '更', '比如', '换句话说', '也就是', '巧的是', '当然', '最后', '先', '再',
           '还有', '另外', '其实', '没想到', '原来', '答案', '原话', '不是', '别', '连', '等', '现在', '这', '它', '他们', '你', '我', '为什么', '怎么', '意味着', '说白了', '一句话', '就', '第', '看', '于是', '同时', '而且', '甚至', '反而', '唯一', '真正']
CONTINUERS = ['也', '还', '又', '都', '同样', '照样', '它', '他们', '她', '这', '那', '不是', '而是', '你']
STOP_GRAMS = {'我们', '这个', '一个', '就是', '可以', '没有', '什么', '这样', '因为', '所以', '但是', '然后', '的话', '他们', '你们', '这些', '那些', '一下', '出来', '起来', '不是', '还是', '已经', '现在', '自己'}
KNOWN_TERMS = {'AI', 'App', 'APP', 'iPhone', 'iPad', 'iOS', 'Android', 'Mac', 'Windows', 'OpenAI', 'Anthropic', 'Claude', 'Codex', 'GPT', 'Google', 'Gemini', 'Apple', 'Meta', 'Microsoft',
               'Chrome', 'TikTok', 'Twitter', 'YouTube', 'Web', 'USB', 'CPU', 'GPU', 'PPT', 'Excel', 'Word', 'PDF', 'QQ', 'OK', 'ok', 'KPI', 'CEO', 'vs', 'VS', 'UI', 'ID', 'Pro', 'Max', 'Plus', 'Duo',
               'MB', 'GB', 'KB', 'TB', 'FPS', 'HD', 'QWER', 'ABCD', 'ESC', 'ABC', 'High', 'Low', 'Mini', 'Air', 'Ultra', 'Studio', 'Wi-Fi', 'WiFi', 'PC', 'TV', 'VR', 'AR', 'LLM', 'Agent', 'Prompt', 'Bug', 'Demo', 'Vibe', 'Coding'}
GLOSS = ['就是', '也就是', '相当于', '专门', '用来', '叫', '是一个', '是个', '是一', '的意思', '意思是', '说白了', '简单说', '简单来说', '一种', '所谓', '这东西', '这玩意', '工具', '平台', '模型', '公司', '软件', '功能', '平台', '网站', '应用', '游戏', '博主', '开发者', '教授', '研究所']
VIEWER_VERBS = ['看到', '看见', '知道', '学会', '判断', '避免', '省', '得到', '明白', '搞清', '理解', '决定', '选', '试', '拿到', '少走', '不用', '能用', '上手', '记住', '收藏', '发现', '感受', '意识到']
V4_KINDS = {'hook', 'setup', 'chapter', 'evidence', 'turn', 'summary', 'cta', 'ending'}
ENDING_CUES = ['试试', '评论区', '留言', '告诉我', '链接', '去试', '去玩', '去用', '下载', '体验', '下次', '下一条', '等它', '等我', '一定', '以后', '继续', '接着', '到时候', '再给你', '再来']
TERM_RE = re.compile(r'[A-Za-z][A-Za-z0-9+\-.]*[A-Za-z0-9]|[A-Za-z]{2,}')
NUM_RE = re.compile(r'\d+(?:\.\d+)?|[一二两三四五六七八九十百千万亿零〇]{2,}')


def sentences(text):
    out, cur = [], ''
    for ch in text:
        cur += ch
        if ch in SENT_END: out.append(cur.strip()); cur = ''
    if cur.strip(): out.append(cur.strip())
    return out


def breath_runs(text):
    """Weighted length of every run between punctuation marks: the unit a voice has to say in one breath."""
    runs, cur = [], ''
    for ch in text:
        if ch in PUNCT or ch.isspace():
            if cur: runs.append((weighted_len(cur), cur)); cur = ''
        else: cur += ch
    if cur: runs.append((weighted_len(cur), cur))
    return runs


def grams(text):
    cjk = ''.join(ch for ch in text if CJK_RE.match(ch))
    return {cjk[i:i + 2] for i in range(len(cjk) - 1)} - STOP_GRAMS


def anchors(text):
    found = []
    if re.search(r'\d', text): found.append('数字')
    if TERM_RE.search(text): found.append('名字')
    if '？' in text or '?' in text: found.append('疑问')
    if '！' in text or '!' in text: found.append('感叹')
    found += [w for w in HOOK_WORDS if w in text][:3]
    return found


def known_terms(project, script, brief):
    known = set(KNOWN_TERMS) | set(script.get('glossary') or {}) | set((brief.get('audience') or {}).get('knownTerms', []) if isinstance(brief.get('audience'), dict) else [])
    card = read(project / 'content/product.json', {}) or {}
    for v in [card.get('name'), (card.get('identity') or {}).get('resolvedName'), (card.get('identity') or {}).get('query')] + list((card.get('identity') or {}).get('candidates') or []):
        if isinstance(v, str): known |= set(TERM_RE.findall(v)) | {v}
    return known


def claim_numbers(project):
    nums = set()
    for c in read(project / 'content/claims.json', []) or []:
        if isinstance(c, dict): nums |= set(NUM_RE.findall(' '.join(str(v) for v in c.values() if isinstance(v, (str, int, float)))))
    return nums


def estimate(beats, brief):
    pacing = brief.get('pacing') or {}; profile = brief.get('profile', 'viral')
    cps_t = float(pacing.get('targetCps') or (8.0 if profile == 'viral' else 7.4)); gaps = (pacing.get('gapPolicy') or {}); by_kind = gaps.get('byBeatKind') or {}
    t = float(pacing.get('leadSeconds') or 0.3); rows = []
    for b in beats:
        n = len(norm(b.get('narration') or '')); sec = n / cps_t if cps_t else 0
        rows.append({'id': b.get('id'), 'kind': b.get('kind') or '', 'chars': n, 'seconds': round(sec, 1), 'start': round(t, 1)})
        t += sec + float(by_kind.get(b.get('kind') or '', gaps.get('default', 0.3)) or 0)
    return rows, round(t, 1), cps_t


def tier(seconds): return 'xs' if seconds <= 30 else 's' if seconds <= 90 else 'm' if seconds <= 240 else 'l'


def at_time(beats, rows, t, cps_t):
    cur = None
    for b, r in zip(beats, rows):
        if r['start'] <= t: cur = (b, r)
    if not cur: return None, ''
    b, r = cur; i = max(0, min(int((t - r['start']) * cps_t), max(0, r['chars'] - 8))); return r['id'], (b.get('narration') or '')[i:i + 22]


def check(project):
    project = Path(project); script = read(project / 'content/script.json', {}) or {}; brief = read(project / 'content/brief.json', {}) or {}
    profile = brief.get('profile', 'viral'); beats = [b for b in script.get('beats', []) if isinstance(b, dict)]
    errors, warnings, info = [], [], []
    E = lambda code, beat, msg: errors.append({'code': code, 'beat': beat, 'message': msg})
    W = lambda code, beat, msg: warnings.append({'code': code, 'beat': beat, 'message': msg})
    I = lambda code, beat, msg: info.append({'code': code, 'beat': beat, 'message': msg})
    rows, total, cps_t = estimate(beats, brief)
    stats = {'profile': profile, 'beats': len(beats), 'chars': sum(r['chars'] for r in rows), 'estimatedSeconds': total, 'tier': tier(total), 'targetCps': cps_t,
             'you': sum((b.get('narration') or '').count('你') for b in beats), 'kindsPresent': any((b.get('kind') or '') in V4_KINDS for b in beats), 'hookVariants': len(script.get('hookVariants') or [])}
    if not beats:
        I('S-EMPTY', None, 'script.json 还没有 beats；写完口播再跑一次'); return {'errors': errors, 'warnings': warnings, 'info': info, 'stats': stats, 'beats': rows, 'timeline': [], 'exits': []}
    spoken = [b for b in beats if (b.get('narration') or '').strip()]
    if not stats['kindsPresent']: I('S-KIND', None, 'beats 没有 v4 的 kind（hook / setup / chapter / evidence / turn / summary / cta / ending）；按位置把第一段当 hook、最后一段当结尾')
    # --- the opening: the only hard errors
    hook = beats[0]; htext = (hook.get('narration') or '').strip(); budget = int(round(LIMITS['hookSeconds'] * cps_t))
    if stats['kindsPresent'] and hook.get('kind') != 'hook': E('L-FIRST-HOOK', hook.get('id'), f"第一段 kind 是 {hook.get('kind')!r}，不是 hook：前 3 秒决定完播，开头必须是钩子")
    if not htext: E('L-HOOK-EMPTY', hook.get('id'), '第一段没有口播')
    else:
        low = htext.lower()
        opener = next((o for o in OPENERS if low.startswith(o.lower())), None)
        if opener: E('L-HOOK-OPENER', hook.get('id'), f"开头是「{opener}」：问候 / 自我介绍 / 交代背景都不是钩子，第一句就要给结果、疑问或反差")
        head_raw = ''; k = 0
        while len(norm(head_raw)) < budget + 2 and k < len(beats): head_raw += (beats[k].get('narration') or '').strip(); k += 1
        head_raw = head_raw[:max(budget + 6, 8)]; found = anchors(head_raw)
        if not found: E('L-HOOK-3S', hook.get('id'), f"前 3 秒（约 {budget} 字）「{head_raw}」里没有钩子：数字、名字、疑问、反差词至少一个")
        else: stats['hookAnchors'] = found
        if rows[0]['seconds'] > LIMITS['hookBeatSeconds']: W('L-HOOK-LEN', hook.get('id'), f"hook 段约 {rows[0]['seconds']} s：开头拖长了，把背景挪到下一段")
    if stats['hookVariants'] < 2: I('L-HOOK-VARIANTS', None, f"只有 {stats['hookVariants']} 个开场候选（script.json.hookVariants）：给 2–3 个不同类型的 hook 让用户选")
    # --- per beat
    known = known_terms(project, script, brief); seen_terms = set(); num_beats = {}; last_fact_t = 0.0; exits = []; claims = claim_numbers(project); seat_misses = []
    all_text = ' '.join(b.get('narration') or '' for b in beats)
    for i, (b, r) in enumerate(zip(beats, rows)):
        text = (b.get('narration') or '').strip(); bid = b.get('id'); kind = b.get('kind') or ''
        if not text: I('S-NO-NARRATION', bid, '无旁白段：画面必须自己成立'); continue
        if r['seconds'] > LIMITS['beatSeconds'][profile if profile in LIMITS['beatSeconds'] else 'viral']: W('L-BEAT-LEN', bid, f"约 {r['seconds']} s 一段：拆成两段，或在中间安排一个画面事件")
        limit = LIMITS['breathWeighted'].get(profile, 22); runs = breath_runs(text); longest = max(runs, default=(0, ''))
        if longest[0] > limit: W('L-BREATH', bid, f"一口气 {longest[0]:.0f} 字没有标点：「{longest[1]}」；念出来喘不过气，加逗号或拆句")
        for w in FILLER_END:
            if w in text: W('L-FILLER', bid, f"套话「{w}」：结尾要么提问要么回调开头，不说谢谢观看")
        if i > 0 and any(text.startswith(o) for o in MID_OPENERS): I('L-MID-OPENER', bid, f"播音式转场「{text[:4]}」：用上一段留下的问题或关键词接，不用报幕")
        for term in TERM_RE.findall(text):
            if term in seen_terms or len(term) < 2 or any(term.lower().startswith(k.lower()) for k in known): continue
            seen_terms.add(term)
            sents = sentences(text); idx = next((k for k, s in enumerate(sents) if term in s), 0); near = ' '.join(sents[idx:idx + 2])
            if not any(g in near for g in GLOSS): I('L-TERM', bid, f"「{term}」第一次出现没有一句白话说它是什么（观众是{(brief.get('audience') if isinstance(brief.get('audience'), str) else '') or '普通人'}）")
        for n in set(NUM_RE.findall(text)): num_beats.setdefault(n, []).append(bid)
        if claims:
            missing = [n for n in set(re.findall(r'\d+(?:\.\d+)?', text)) if n not in claims and len(n) > 1]
            if missing: W('L-NUM-SOURCE', bid, f"数字 {', '.join(sorted(missing))} 不在 claims.json 里：口播里的数字都要有出处")
        if re.search(r'\d', text) or TERM_RE.search(text) or b.get('claims'): last_fact_t = r['start'] + r['seconds']
        elif r['start'] + r['seconds'] - last_fact_t > LIMITS['factGapSeconds']: I('L-FACT-GAP', bid, f"到这里已经 {r['start'] + r['seconds'] - last_fact_t:.0f} s 没有新的数字 / 名字 / 引用：每 25 s 给一个新事实"); last_fact_t = r['start'] + r['seconds']
        if not b.get('viewerGain'): W('L-GAIN', bid, '没有 viewerGain：这段观众得到什么？写不出来就删掉这段')
        elif '你' not in b['viewerGain'] and not any(v in b['viewerGain'] for v in VIEWER_VERBS): seat_misses.append(f"{bid}「{b['viewerGain'][:12]}」")
        # bridge from the previous beat
        if i > 0:
            prev = (beats[i - 1].get('narration') or '').strip(); first = sentences(text)[0] if sentences(text) else text; clause = re.split(r'[，。！？；：…,]', first)[0]
            bridged = ('？' in first or '?' in first or any(clause.startswith(x) for x in BRIDGES) or any(c in clause for c in CONTINUERS)
                       or bool(grams(sentences(prev)[-1] if sentences(prev) else prev) & grams(first)) or bool(set(TERM_RE.findall(prev)) & set(TERM_RE.findall(first)))
                       or bool(set(NUM_RE.findall(prev)) & set(NUM_RE.findall(first))))
            if not bridged: I('L-BRIDGE', bid, f"「{clause[:18]}」和上一段结尾没有接上：回接上一段的关键词、先果后因、或用一个反问带过去")
        exit_reasons = [x['message'].split('：')[0] for x in warnings if x['beat'] == bid and x['code'] in ('L-BEAT-LEN', 'L-BREATH')]
        if r['seconds'] > 6 and not anchors(text) and '你' not in text: exit_reasons.append(f"{r['seconds']} s 没有数字 / 名字 / 疑问 / 对观众说话")
        if exit_reasons: exits.append({'beat': bid, 'at': r['start'], 'why': '；'.join(exit_reasons)})
    if seat_misses: I('L-GAIN-SEAT', None, f"{len(seat_misses)}/{len(spoken)} 段的 viewerGain 像作者视角（没有「你」，也没有 看到 / 知道 / 学会 类动词）：{'、'.join(seat_misses[:4])}{'…' if len(seat_misses) > 4 else ''}；改成观众坐在座位上得到的东西")
    for n, where in num_beats.items():
        if len(where) > 1: I('L-NUM-REPEAT', None, f"数字 {n} 出现在 {len(where)} 段（{', '.join(where)}）：回调可以，别重复解释")
    # --- structure
    kinds = [b.get('kind') for b in beats]
    if stats['kindsPresent']:
        turns = [k for k, b in enumerate(beats) if b.get('kind') == 'turn']
        if not turns and profile == 'viral': W('L-TURN', None, '没有 turn 段：被埋掉的条件、输掉的地方、官方没说的——反转是完播和评论的来源')
        for k in turns:
            pos = rows[k]['start'] / total if total else 0; lo, hi = LIMITS['turnWindow']
            if not lo <= pos <= hi: W('L-TURN-POS', beats[k].get('id'), f"turn 落在 {pos * 100:.1f}%：最好在 35–75%，太早观众还没投入，太晚已经划走")
        if 'summary' not in kinds and stats['tier'] in ('m', 'l'): I('L-SUMMARY', None, '没有 summary 段：90 s 以上给一个截图收藏点')
        if profile == 'launch' and 'cta' not in kinds and 'ending' not in kinds: W('L-CTA', None, '没有 cta / ending 段：说清想让观众做什么（试用 / 反馈 / 关注）')
    last = spoken[-1]; ltext = (last.get('narration') or '')
    callback = bool(grams(htext) & grams(ltext)) or bool(set(NUM_RE.findall(htext)) & set(NUM_RE.findall(ltext))) or bool(set(TERM_RE.findall(htext)) & set(TERM_RE.findall(ltext)))
    if '？' not in ltext and '?' not in ltext and not callback and not any(c in ltext for c in ENDING_CUES): W('L-ENDING', last.get('id'), '结尾既不是留给观众的问题，也没有回调开头：最后一句要么让人想评论，要么让人想再看一遍')
    if stats['you'] == 0: I('L-YOU', None, '全片没有一个「你」：观众是被讲给听的人，不是旁观者')
    target = brief.get('targetSeconds') or (brief.get('intake') or {}).get('targetSeconds') if isinstance(brief.get('intake'), dict) else brief.get('targetSeconds')
    if target and abs(total - float(target)) > LIMITS['totalTolerance'] * float(target): W('L-TOTAL', None, f"预计 {total} s，目标 {target} s：偏差超过 20%")
    timeline = []
    for t in LIMITS['checkpoints']:
        if t < total:
            bid, snippet = at_time(beats, rows, t, cps_t); timeline.append({'t': t, 'beat': bid, 'text': snippet})
    timeline.append({'t': total, 'beat': last.get('id'), 'text': ltext[-22:]})
    return {'errors': errors, 'warnings': warnings, 'info': info, 'stats': stats, 'beats': rows, 'timeline': timeline, 'exits': exits}


def markdown(report):
    s = report['stats']; lines = ['## 脚本检查（script_check.py · 提示不是裁决）', '']
    if s['beats'] == 0: return '\n'.join(lines + ['- ' + report['info'][0]['message'], ''])
    lines.append(f"- 预计 ~{s['estimatedSeconds']} s（{s['tier']} 档）· {s['beats']} 段 · {s['chars']} 字 · 按 {s['targetCps']} 字/秒 · 「你」{s['you']} 次" + (f" · 钩子：{' / '.join(s['hookAnchors'])}" if s.get('hookAnchors') else ''))
    lines.append('- 留存时间轴：' + ' · '.join(f"{'结尾' if i == len(report['timeline']) - 1 else str(x['t']) + ' s'} → {x['beat']}「{x['text']}」" for i, x in enumerate(report['timeline'])))
    if report['exits']: lines.append('- 可能划走点：' + '；'.join(f"{x['beat']}（{x['at']} s：{x['why']}）" for x in report['exits']))
    for label, items in [('ERROR', report['errors']), ('WARN', report['warnings']), ('提示', report['info'])]:
        lines.append(f"- {label} ×{len(items)}" + ('' if not items else '：'))
        by_code = {}
        for x in items: by_code.setdefault(x['code'], []).append(x)
        for code, xs in by_code.items():
            if len(xs) <= 3 or not any(x['beat'] for x in xs): lines += [f"  - [{code}] {x['beat'] + '：' if x['beat'] else ''}{x['message']}" for x in xs]
            else:
                ex = [x for x in xs if '「' in x['message']][:2]
                lines.append(f"  - [{code}] ×{len(xs)}（{', '.join(str(x['beat']) for x in xs)}）：{xs[0]['message'].split('：')[-1]}" + ('' if not ex else '；例如 ' + '、'.join(f"{x['beat']}「{x['message'].split('「')[1].split('」')[0]}」" for x in ex)))
    lines += ['', '| 段 | kind | 字 | ≈秒 | 起点 |', '|---|---|---|---|---|'] + [f"| {r['id']} | {r['kind']} | {r['chars']} | {r['seconds']} | {r['start']} |" for r in report['beats']] + ['']
    return '\n'.join(lines)


def run(project):
    project = Path(project); report = check(project); md = markdown(report)
    out = project / 'out'; out.mkdir(exist_ok=True); write(out / 'script-check.json', report); (out / 'script-check.md').write_text(md, encoding='utf-8')
    return report, md


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter); ap.add_argument('project', type=Path); ap.add_argument('--json', action='store_true'); a = ap.parse_args()
    report, md = run(a.project)
    print(json.dumps(report, ensure_ascii=False, indent=2) if a.json else md)
    if report['errors']: raise SystemExit(1)


if __name__ == '__main__': run_main(main)
