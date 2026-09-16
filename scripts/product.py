#!/usr/bin/env python3
"""Product card: what the video is about, with provenance per field (user | web | inferred), an evidence level, harvested media, and the questions still owed to the user.

  product.py <project> init --name "…" [--ownership own|third-party] [--query "用户原话里的名字"] [--confidence confirmed|likely|ambiguous|unknown] [--candidates "A,B"]
  product.py <project> identity --resolved "iPhone Duo" --confidence likely [--candidates "…"]    # what the user's words resolve to
  product.py <project> source --url URL --kind official|press|review|rumor|community|user [--note "…"]
  product.py <project> media --url URL --kind image|video|screenshot|clip [--note] [--timecodes "0:12-0:20"] [--rights "…"] [--asset <materialId|path>]
  product.py <project> set --field oneLiner --value "…" --from web [--source P1]       # dotted paths: audience.who, tone.energy, tone.adjectives (comma list)
  product.py <project> confirm --evidence "用户原话"                                     # user confirmed thin / rumor facts
  product.py <project> gaps [--json]                                                      # round 0 identity question, or ≤3 questions + todos
  product.py <project> card                                                               # the 产品卡 block for the 方案卡
  product.py <project> show
Evidence: none (no sources) · rumor (only rumor sources) · thin (< 2 independent domains or no official source) · solid.
Own products with user-provided fields are solid (the author is the primary source). Round 0: an ambiguous / unknown identity is the only question until resolved."""
import argparse, json, time
from pathlib import Path
from urllib.parse import urlparse
from common import read, write, run_main

PATH = 'content/product.json'; FROM = ['user', 'web', 'inferred']
KINDS = ['official', 'press', 'review', 'rumor', 'community', 'user']; CONFIDENCE = ['confirmed', 'likely', 'ambiguous', 'unknown']; MEDIA_KINDS = ['image', 'video', 'screenshot', 'clip']
LIST_FIELDS = {'features', 'platforms', 'links', 'competitors', 'proof', 'tone.adjectives', 'brand.colors'}
STAGES = ['idea', 'beta', 'launched', 'unknown']; MAX_QUESTIONS = 3
# field → (question, profiles that require it); order = priority inside the ≤5-question round
REQUIRED = [
    ('tone.adjectives', '想让人感觉它是什么气质？给三个词（例：克制、可靠、极客 / 燃、年轻、好玩）——这决定配乐与画面。', ('viral', 'launch')),
    ('oneLiner', '它替谁解决哪一件事？一句话。', ('viral', 'launch')),
    ('audience.who', '给谁用？（职业 / 场景 / 水平）', ('viral', 'launch')),
    ('proof', '有哪些能放进视频的证据？（录屏、数据、用户反馈、对比）', ('launch',)),
    ('stage', '现在到哪一步？（想法 / 内测 / 已上线；有没有定价）', ('launch',)),
    ('replaces', '用户现在用什么替代方案？为什么会换？', ('launch',)),
    ('links', '官网 / 仓库 / 商店链接？（我没搜到公开页面）', ('viral', 'launch')),
]


def now(): return time.strftime('%Y-%m-%dT%H:%M:%S')


def blank(name, ownership, query=None, confidence='likely', candidates=None):
    return {'version': 2, 'name': name, 'ownership': ownership, 'identity': {'query': query or name, 'resolvedName': name, 'confidence': confidence, 'candidates': candidates or []},
            'oneLiner': '', 'category': '', 'stage': 'unknown', 'features': [], 'audience': {'who': '', 'scenario': '', 'level': ''}, 'tone': {'adjectives': [], 'energy': None, 'register': ''},
            'replaces': '', 'proof': [], 'pricing': '', 'platforms': [], 'links': [], 'competitors': [], 'brand': {'colors': [], 'fonts': ''},
            'sources': [], 'media': [], 'provenance': {}, 'confirmation': None, 'unknowns': [], 'updatedAt': now()}


def get(card, path):
    cur = card
    for k in path.split('.'):
        if not isinstance(cur, dict) or k not in cur: return None
        cur = cur[k]
    return cur


def put(card, path, value):
    keys = path.split('.'); cur = card
    for k in keys[:-1]: cur = cur.setdefault(k, {})
    cur[keys[-1]] = value


def parse_value(path, value):
    if path in LIST_FIELDS: return [x.strip() for x in value.split(',') if x.strip()]
    if path == 'tone.energy':
        n = int(value)
        if not 1 <= n <= 5: raise ValueError('tone.energy is 1–5')
        return n
    if path == 'stage' and value not in STAGES: raise ValueError(f'stage is one of {STAGES}')
    return value.strip()


def filled(card, path):
    v = get(card, path)
    return bool(v) if not isinstance(v, (int, float)) else True


def domain(url):
    host = (urlparse(url).hostname or '').lower()
    return host[4:] if host.startswith('www.') else host


def evidence_level(card):
    """none | rumor | thin | solid. Own products whose one-liner came from the user are solid: the author is the primary source."""
    if card.get('ownership') == 'own' and card.get('provenance', {}).get('oneLiner') == 'user': return 'solid'
    srcs = [s for s in card.get('sources', []) if s.get('url') or s.get('kind') == 'user']
    if not srcs: return 'none'
    if all(s.get('kind') == 'rumor' for s in srcs): return 'rumor'
    domains = {domain(s['url']) for s in srcs if s.get('url') and s.get('kind') != 'rumor'}  # rumors never count toward independence
    official = any(s.get('kind') in ('official', 'user') for s in srcs)
    return 'solid' if len(domains) >= 2 and official else 'thin'


def is_new(card): return evidence_level(card) == 'none' or card.get('stage') in ('idea', 'beta')


def identity_question(card):
    idn = card.get('identity') or {}
    if idn.get('confidence', 'likely') not in ('ambiguous', 'unknown'): return None
    q = idn.get('query') or card.get('name'); cands = idn.get('candidates') or []
    if cands: return f"你说的「{q}」是指 {' / '.join(cands)} 中的哪一个？（我搜到了这几个可能）"
    return f"你说的「{q}」我没搜到明确对应的产品：它的正式名称、官网或任何一条链接是什么？是已发布的产品还是传闻？"


def evidence_question(card):
    ev = evidence_level(card)
    if ev == 'solid' or card.get('confirmation'): return None
    srcs = [s for s in card.get('sources', []) if s.get('url')]; doms = '、'.join(sorted({domain(s['url']) for s in srcs})) or '无'
    if ev == 'rumor': return f"我只找到传闻类来源（{len(srcs)} 条：{doms}），没有官方信息：按「传闻向」做（旁白说「据称 / 传闻」）还是等官方信息？你有官方链接吗？"
    if ev == 'thin':
        facts = f"它是「{card.get('oneLiner')}」" if card.get('oneLiner') else '我还没能确定它是什么'
        why = '没有官方来源' if not any(s.get('kind') in ('official', 'user') for s in srcs) else '来源太少'
        return f"我只找到 {len(srcs)} 条来源（{doms}），{why}：{facts}，阶段 {card.get('stage')}，对吗？有官方链接或素材可以给我吗？"
    return None


def gaps(card, profile):
    """Round 0 identity question alone; otherwise ≤3 questions (evidence → tone → fields) plus todos that need no user input."""
    ev = evidence_level(card); idq = identity_question(card)
    base = {'name': card.get('name'), 'evidence': ev, 'new': is_new(card), 'confirmed': bool(card.get('confirmation')), 'inferred': [f for f, src in card.get('provenance', {}).items() if src == 'inferred']}
    if idq: return {**base, 'round': 0, 'missing': [], 'questions': [idq], 'todo': [], 'advice': '先确认它是什么；其他问题与推断都等这一步。'}
    questions = []; missing = []
    eq = evidence_question(card)
    if eq: questions.append(eq)
    for field, question, profiles in REQUIRED:
        if profile not in profiles: continue
        if field == 'links' and any(s.get('url') for s in card.get('sources', [])): continue
        if field == 'tone.adjectives' and filled(card, 'tone.energy'): continue
        if not filled(card, field): missing.append({'field': field, 'question': question})
    if ev == 'none': missing.sort(key=lambda m: m['field'] != 'links')  # nothing found: a link from the user unlocks everything else
    for m in missing:
        if len(questions) >= MAX_QUESTIONS: break
        questions.append(m['question'])
    todo = []
    if card.get('ownership') == 'third-party' and card.get('stage') == 'launched' and not card.get('media'):
        todo.append('未收集任何官方图片 / 视频：按 research.md §1.5 抓官方新闻稿 / 产品页素材并 product.py media 登记，方案卡"已有素材"才是真的')
    if ev == 'none': advice = '新产品或未公开：缺的项必须问用户，不能靠推断。'
    elif ev in ('thin', 'rumor') and not card.get('confirmation'): advice = '信息稀薄：先让用户确认关键事实（product.py confirm），推断项不能当事实写进脚本。'
    elif missing: advice = '先补齐必填项再出方案卡。'
    else: advice = '可开工；推断项在方案卡里标注"推断"。'
    return {**base, 'round': 1, 'missing': missing, 'questions': questions, 'todo': todo, 'advice': advice}


def card_text(card, brief):
    import music_tone
    key, reasons = music_tone.derive_archetype(brief, card, {})
    prov = card.get('provenance', {}); ev = evidence_level(card); idn = card.get('identity') or {}
    def mark(field): return {'user': '', 'web': '（来源：网络）', 'inferred': '（推断）'}.get(prov.get(field), '')
    kinds = {}
    for s in card.get('sources', []): kinds[s.get('kind', 'press')] = kinds.get(s.get('kind', 'press'), 0) + 1
    media = card.get('media', []); mk = {}
    for m in media: mk[m.get('kind')] = mk.get(m.get('kind'), 0) + 1
    lines = [f"【产品卡】{card.get('name')}" + ('（第三方）' if card.get('ownership') == 'third-party' else '') + ('  · 新产品 / 未公开' if is_new(card) else '')]
    if idn.get('query') and idn.get('query') != card.get('name'): lines.append(f"你说的「{idn['query']}」→ {idn.get('resolvedName') or card.get('name')}（{idn.get('confidence')}）")
    lines += [f"一句话：{card.get('oneLiner') or '—'}{mark('oneLiner')}", f"给谁：{get(card, 'audience.who') or '—'}{mark('audience.who')}   阶段：{card.get('stage')}{mark('stage')}",
              f"气质：{'、'.join(get(card, 'tone.adjectives') or []) or '—'}{mark('tone.adjectives')}   能量：{get(card, 'tone.energy') or '—'}",
              f"替代：{card.get('replaces') or '—'}{mark('replaces')}", f"证据：{'；'.join(card.get('proof') or []) or '—'}{mark('proof')}",
              f"信息等级：{ev}（" + ('、'.join(f'{k} {v}' for k, v in kinds.items()) or '无来源') + ('；已由用户确认' if card.get('confirmation') else '') + '）',
              f"已收集素材：{len(media)} 条" + ('（' + '、'.join(f'{k} {v}' for k, v in mk.items()) + '）' if media else '（无：第三方新品应先抓官方图 / 视频）' if card.get('ownership') == 'third-party' else ''),
              f"BGM 调性：{music_tone.ARCHETYPES[key]['zh']}（{key}；{music_tone.ARCHETYPES[key]['feel']}）  依据：{reasons[-1] if reasons else '—'}"]
    return '\n'.join(lines)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter); p.add_argument('project', type=Path); sub = p.add_subparsers(dest='cmd', required=True)
    q = sub.add_parser('init'); q.add_argument('--name', required=True); q.add_argument('--ownership', choices=['own', 'third-party'], default='own'); q.add_argument('--from', dest='src', choices=FROM, default='user'); q.add_argument('--query'); q.add_argument('--confidence', choices=CONFIDENCE, default='likely'); q.add_argument('--candidates')
    q = sub.add_parser('identity'); q.add_argument('--resolved'); q.add_argument('--confidence', choices=CONFIDENCE, required=True); q.add_argument('--candidates'); q.add_argument('--query')
    q = sub.add_parser('set'); q.add_argument('--field', required=True); q.add_argument('--value', required=True); q.add_argument('--from', dest='src', choices=FROM, required=True); q.add_argument('--source')
    q = sub.add_parser('source'); q.add_argument('--url', required=True); q.add_argument('--kind', choices=KINDS, default='press'); q.add_argument('--note', default='')
    q = sub.add_parser('media'); q.add_argument('--url', required=True); q.add_argument('--kind', choices=MEDIA_KINDS, required=True); q.add_argument('--note', default=''); q.add_argument('--timecodes'); q.add_argument('--rights', default=''); q.add_argument('--asset')
    q = sub.add_parser('confirm'); q.add_argument('--evidence', required=True)
    q = sub.add_parser('gaps'); q.add_argument('--json', action='store_true')
    sub.add_parser('card'); sub.add_parser('show')
    a = p.parse_args(); project = a.project.resolve(); path = project / PATH
    if a.cmd == 'init':
        if path.exists(): raise ValueError('product.json exists; use set / identity')
        card = blank(a.name, a.ownership, a.query, a.confidence, [x.strip() for x in (a.candidates or '').split(',') if x.strip()]); card['provenance']['name'] = a.src; write(path, card); print(f"product card: {a.name} ({a.confidence})"); return
    card = read(path, None)
    if card is None: raise ValueError('No product card yet: product.py init --name …')
    card.setdefault('identity', {'query': card.get('name'), 'resolvedName': card.get('name'), 'confidence': 'likely', 'candidates': []}); card.setdefault('media', []); card.setdefault('confirmation', None)
    brief = read(project / 'content/brief.json', {})
    if a.cmd == 'identity':
        idn = card['identity']; idn['confidence'] = a.confidence
        if a.resolved: idn['resolvedName'] = a.resolved; card['name'] = a.resolved
        if a.query: idn['query'] = a.query
        if a.candidates is not None: idn['candidates'] = [x.strip() for x in a.candidates.split(',') if x.strip()]
        card['updatedAt'] = now(); write(path, card); print(f"identity: {idn['query']} → {idn['resolvedName']} ({a.confidence})")
    elif a.cmd == 'set':
        put(card, a.field, parse_value(a.field, a.value)); card['provenance'][a.field] = a.src
        if a.source: card['provenance'][a.field + '@source'] = a.source
        card['updatedAt'] = now(); write(path, card); print(f'{a.field} ← {a.src}')
    elif a.cmd == 'source':
        sid = f"P{len(card['sources']) + 1}"; card['sources'].append({'id': sid, 'url': a.url, 'kind': a.kind, 'note': a.note, 'fetchedAt': now()}); card['updatedAt'] = now(); write(path, card); print(f'{sid} ({a.kind}, {evidence_level(card)})')
    elif a.cmd == 'media':
        mid = f"M{len(card['media']) + 1}"; card['media'].append({'id': mid, 'url': a.url, 'kind': a.kind, 'note': a.note, 'timecodes': a.timecodes, 'rights': a.rights, 'asset': a.asset, 'addedAt': now()}); card['updatedAt'] = now(); write(path, card); print(mid)
    elif a.cmd == 'confirm':
        card['confirmation'] = {'evidence': a.evidence, 'evidenceLevel': evidence_level(card), 'at': now()}; write(path, card); print(f"confirmed ({card['confirmation']['evidenceLevel']})")
    elif a.cmd == 'gaps':
        g = gaps(card, brief.get('profile', 'viral'))
        if a.json: print(json.dumps(g, ensure_ascii=False, indent=2)); return
        print(f"信息等级 {g['evidence']}" + ('，新产品 / 未公开' if g['new'] else '') + (f"，{len(g['inferred'])} 项为推断" if g['inferred'] else '') + (f"，第 {g['round']} 轮" if g['round'] == 0 else ''))
        for i, qn in enumerate(g['questions'], 1): print(f'  问 {i}. {qn}')
        for t in g['todo']: print(f'  待办. {t}')
        print(g['advice'])
    elif a.cmd == 'card': print(card_text(card, brief))
    else: print(json.dumps(card, ensure_ascii=False, indent=2))


if __name__ == '__main__': run_main(main)
