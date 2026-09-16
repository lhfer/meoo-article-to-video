#!/usr/bin/env python3
"""Cover copy checks: the AI writes the candidates, this tool rejects the ones that will not survive the platform or the facts.

  cover_copy.py <project> check --platform xiaohongshu|douyin|bilibili --cover "…" [--cover "…"] [--title "…"] [--json]
  cover_copy.py <project> formulas
Cover text = the big characters inside the cover image (per-platform length); title = the publish headline. Rules: length, banned 播音腔 words,
every number must appear in claims.json quotes or the script narration, no off-screen promises, and the candidate set must span ≥ 3 formulas."""
import argparse, json, re
from pathlib import Path
from common import read, write, run_main, CJK_RE
from validate import banned_words

COVER_CHARS = {'xiaohongshu': (8, 14), 'douyin': (4, 8), 'bilibili': (6, 12)}
TITLE_MAX = {'xiaohongshu': 20, 'douyin': 30, 'bilibili': 40}
PLATFORM_RATIO = {'xiaohongshu': '3x4', 'douyin': '9x16', 'bilibili': '16x9'}
FORMULAS = [
    ('question', '问句', lambda t: t.rstrip().endswith(('？', '?')) or any(w in t for w in ('为什么', '怎么', '凭什么', '还是', '吗', '呢'))),
    ('number', '数字', lambda t: bool(re.search(r'\d', t)) or any(w in t for w in ('一半', '十倍', '三分之一', '零'))),
    ('contrast', '反差', lambda t: any(w in t for w in ('但', '却', '居然', '竟然', '其实', '反而', '没想到', '结果'))),
    ('identity', '身份代入', lambda t: any(w in t for w in ('你', '我', '我们', '程序员', '打工人', '独立开发', '设计师', '学生', '妈妈', '爸爸', '老板'))),
    ('gap', '悬念缺口', lambda t: any(w in t for w in ('真相', '秘密', '才知道', '原来', '最后', '藏', '不敢', '没人说', '一件事', '一个细节'))),
]
OFFSCREEN = ['震惊', '必看', '99%', '颠覆', '史上', '全网', '疯了', '炸了', '封神', '天花板', '绝绝子', '无敌', '秒杀', '一夜', '暴富', '躺赚', '不看后悔']


def formula_of(text):
    return [key for key, _, fn in FORMULAS if fn(text)]


def numbers_in(text):
    return set(re.findall(r'\d+(?:\.\d+)?', text))


def check_cover_text(text, platform, banned, allowed_numbers):
    """Problems list for one cover line (empty = pass). Length counts CJK chars + ASCII words."""
    lo, hi = COVER_CHARS[platform]; n = len(CJK_RE.findall(text)) + len(re.findall(r'[A-Za-z0-9]+', text)); problems = []
    if n < lo: problems.append(f'太短：{n} 字，{platform} 封面大字要 {lo}–{hi} 字')
    if n > hi: problems.append(f'太长：{n} 字，{platform} 封面大字要 {lo}–{hi} 字（缩略图上读不完）')
    hits = [w for w in banned if w in text]
    if hits: problems.append('播音腔 / 禁词：' + '、'.join(hits))
    off = [w for w in OFFSCREEN if w in text]
    if off: problems.append('画面外承诺：' + '、'.join(off))
    unknown = numbers_in(text) - allowed_numbers
    if unknown: problems.append('数字没有出处（不在 claims / 脚本里）：' + '、'.join(sorted(unknown)))
    if '\n' in text and platform == 'douyin': problems.append('抖音封面大字一行')
    return problems


def check_title(text, platform, banned, allowed_numbers):
    problems = []; n = len(text.strip())
    if n > TITLE_MAX[platform]: problems.append(f'发布标题 {n} 字，{platform} 建议 ≤ {TITLE_MAX[platform]}')
    hits = [w for w in banned if w in text]
    if hits: problems.append('播音腔 / 禁词：' + '、'.join(hits))
    off = [w for w in OFFSCREEN if w in text]
    if off: problems.append('画面外承诺：' + '、'.join(off))
    unknown = numbers_in(text) - allowed_numbers
    if unknown: problems.append('数字没有出处：' + '、'.join(sorted(unknown)))
    return problems


def allowed_numbers_from(project):
    nums = set()
    for c in read(project / 'content/claims.json', []): nums |= numbers_in(c.get('quote', '') + ' ' + c.get('text', ''))
    for b in read(project / 'content/script.json', {}).get('beats', []): nums |= numbers_in(b.get('narration', ''))
    return nums


def check_set(covers, platform, banned, allowed):
    rows = [{'text': t, 'formulas': formula_of(t), 'problems': check_cover_text(t, platform, banned, allowed)} for t in covers]
    used = {f for r in rows if not r['problems'] for f in r['formulas']}
    set_problems = [] if len(used) >= 3 or len(covers) < 3 else [f'通过的候选只覆盖 {len(used)} 种公式（{"、".join(sorted(used)) or "无"}）；至少 3 种：问句 / 数字 / 反差 / 身份代入 / 悬念']
    return rows, set_problems


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter); p.add_argument('project', type=Path); sub = p.add_subparsers(dest='cmd', required=True)
    q = sub.add_parser('check'); q.add_argument('--platform', choices=sorted(COVER_CHARS), required=True); q.add_argument('--cover', action='append', default=[]); q.add_argument('--title', action='append', default=[]); q.add_argument('--json', action='store_true')
    sub.add_parser('formulas')
    a = p.parse_args(); project = a.project.resolve()
    if a.cmd == 'formulas':
        for key, zh, _ in FORMULAS: print(f'{key:9s} {zh}')
        print('每个平台至少 5 条封面大字候选、覆盖 ≥ 3 种公式；发布标题另出 3 条（问句 / 数字 / 反差）。数字必须能在 claims 或脚本里找到。'); return
    brief = read(project / 'content/brief.json', {}); banned = banned_words() + [w for w in (brief.get('bannedWordsExtra') or []) if w]; allowed = allowed_numbers_from(project)
    rows, set_problems = check_set(a.cover, a.platform, banned, allowed)
    titles = [{'text': t, 'problems': check_title(t, a.platform, banned, allowed)} for t in a.title]
    result = {'platform': a.platform, 'ratio': PLATFORM_RATIO[a.platform], 'covers': rows, 'setProblems': set_problems, 'titles': titles, 'pass': not set_problems and all(not r['problems'] for r in rows) and all(not t['problems'] for t in titles)}
    cover = read(project / 'content/cover.json', {'version': 1, 'candidates': [], 'selected': {}}); cover.setdefault('copy', {})[a.platform] = result; write(project / 'content/cover.json', cover)
    if a.json: print(json.dumps(result, ensure_ascii=False, indent=2)); return
    for r in rows: print(('✓ ' if not r['problems'] else '✗ ') + r['text'] + f"  [{'、'.join(r['formulas']) or '无公式'}]" + (('  ← ' + '；'.join(r['problems'])) if r['problems'] else ''))
    for t in titles: print(('✓ 标题 ' if not t['problems'] else '✗ 标题 ') + t['text'] + (('  ← ' + '；'.join(t['problems'])) if t['problems'] else ''))
    for s in set_problems: print('✗ ' + s)
    print('通过' if result['pass'] else '有候选被打回：改写后再查')


if __name__ == '__main__': run_main(main)
