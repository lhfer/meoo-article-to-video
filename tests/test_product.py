"""Product card: identity round 0, evidence levels, ≤3 questions, media todo, confirmation; and the BGM tone that reads it (pure functions)."""
import sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / 'scripts'))
import product, music_tone

def card(**kw):
    c = product.blank(kw.pop('name', 'X'), kw.pop('ownership', 'third-party'), kw.pop('query', None), kw.pop('confidence', 'likely'), kw.pop('candidates', None))
    for k, v in kw.items(): product.put(c, k, v)
    return c

def src(c, url, kind='press'): c['sources'].append({'id': f"P{len(c['sources']) + 1}", 'url': url, 'kind': kind})

class Identity(unittest.TestCase):
    def test_ambiguous_name_is_the_only_question(self):
        c = card(query='苹果 duo', confidence='ambiguous', candidates=['iPhone Duo', 'Apple Duo Pack']); src(c, 'https://apple.com/iphone-duo/', 'official'); src(c, 'https://example.com/a', 'press')
        g = product.gaps(c, 'viral'); self.assertEqual(g['round'], 0); self.assertEqual(len(g['questions']), 1); self.assertIn('苹果 duo', g['questions'][0]); self.assertIn('iPhone Duo', g['questions'][0]); self.assertIn('先确认', g['advice'])
        g = product.gaps(card(query='xx', confidence='unknown'), 'viral'); self.assertEqual(len(g['questions']), 1); self.assertIn('正式名称', g['questions'][0])

class Evidence(unittest.TestCase):
    def test_levels(self):
        c = card(); self.assertEqual(product.evidence_level(c), 'none')
        src(c, 'https://rumors.example/a', 'rumor'); self.assertEqual(product.evidence_level(c), 'rumor')
        src(c, 'https://news.example/b', 'press'); self.assertEqual(product.evidence_level(c), 'thin')
        src(c, 'https://www.news.example/c', 'official'); self.assertEqual(product.evidence_level(c), 'thin')  # same domain as b: not independent
        src(c, 'https://vendor.example/', 'official'); self.assertEqual(product.evidence_level(c), 'solid')
    def test_own_product_with_user_one_liner_is_solid(self):
        c = card(ownership='own'); product.put(c, 'oneLiner', '归档邮件'); c['provenance']['oneLiner'] = 'user'; self.assertEqual(product.evidence_level(c), 'solid')
        g = product.gaps(c, 'launch'); self.assertFalse(any('来源' in q for q in g['questions']))
    def test_solid_launched_product_asks_nothing_but_lists_media_todo(self):
        c = card(stage='launched'); src(c, 'https://apple.com/newsroom/x', 'official'); src(c, 'https://en.wikipedia.org/wiki/X', 'press')
        product.put(c, 'oneLiner', 'a'); product.put(c, 'audience.who', 'b'); product.put(c, 'tone.adjectives', ['高级'])
        g = product.gaps(c, 'viral'); self.assertEqual(g['evidence'], 'solid'); self.assertEqual(g['questions'], []); self.assertEqual(len(g['todo']), 1); self.assertIn('官方图片', g['todo'][0])
        c['media'].append({'id': 'M1', 'url': 'https://apple.com/x.jpg', 'kind': 'image'}); self.assertEqual(product.gaps(c, 'viral')['todo'], [])
    def test_thin_quotes_what_was_found_and_caps_questions(self):
        c = card(stage='launched'); src(c, 'https://iphoneplay.cn/a', 'press'); product.put(c, 'oneLiner', '首款折叠屏 iPhone')
        g = product.gaps(c, 'launch'); self.assertEqual(g['evidence'], 'thin'); self.assertIn('iphoneplay.cn', g['questions'][0]); self.assertIn('首款折叠屏 iPhone', g['questions'][0]); self.assertIn('没有官方来源', g['questions'][0])
        self.assertLessEqual(len(g['questions']), 3); self.assertIn('气质', g['questions'][1]); self.assertIn('信息稀薄', g['advice'])
        c['confirmation'] = {'evidence': '对，就是它'}; g = product.gaps(c, 'launch'); self.assertFalse(any('来源' in q for q in g['questions']))
    def test_rumor_only_asks_for_rumor_mode(self):
        c = card(); src(c, 'https://leaks.example/a', 'rumor'); g = product.gaps(c, 'viral'); self.assertEqual(g['evidence'], 'rumor'); self.assertIn('传闻向', g['questions'][0])
    def test_none_is_new_and_must_ask(self):
        g = product.gaps(card(), 'viral'); self.assertTrue(g['new']); self.assertIn('必须问用户', g['advice']); self.assertIn('链接', ''.join(g['questions']))

class Misc(unittest.TestCase):
    def test_parse_value(self):
        self.assertEqual(product.parse_value('tone.adjectives', '克制, 可靠 ,极客'), ['克制', '可靠', '极客']); self.assertEqual(product.parse_value('tone.energy', '4'), 4)
        with self.assertRaises(ValueError): product.parse_value('tone.energy', '9')
        with self.assertRaises(ValueError): product.parse_value('stage', 'soon')
    def test_card_text_shows_evidence_media_and_bgm(self):
        c = card(name='收件箱管家', ownership='own', query='我那个邮件工具'); product.put(c, 'tone.adjectives', ['克制', '可靠']); c['provenance']['oneLiner'] = 'inferred'; product.put(c, 'oneLiner', '归档邮件')
        text = product.card_text(c, {'profile': 'launch'}); self.assertIn('BGM 调性：沉稳', text); self.assertIn('（推断）', text); self.assertIn('信息等级：none', text); self.assertIn('我那个邮件工具', text)

if __name__ == '__main__': unittest.main()
