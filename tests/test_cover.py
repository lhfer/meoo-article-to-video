"""Cover copy checks and reference selection (pure functions)."""
import sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / 'scripts'))
import cover, cover_copy

class Copy(unittest.TestCase):
    banned = ['震撼', '王炸']
    def test_length_and_offscreen_and_numbers(self):
        self.assertEqual(cover_copy.check_cover_text('折叠屏 iPhone 到底值不值', 'xiaohongshu', self.banned, set()), [])
        self.assertTrue(any('太长' in p for p in cover_copy.check_cover_text('这是一条超过十四个字的封面大字候选文案哦', 'xiaohongshu', self.banned, set())))
        self.assertTrue(any('太短' in p for p in cover_copy.check_cover_text('来了', 'douyin', self.banned, set())))
        self.assertTrue(any('画面外承诺' in p for p in cover_copy.check_cover_text('震惊全网的手机', 'bilibili', self.banned, set())))
        self.assertTrue(any('禁词' in p for p in cover_copy.check_cover_text('王炸级折叠屏', 'douyin', self.banned, set())))
        self.assertTrue(any('没有出处' in p for p in cover_copy.check_cover_text('15999 元值不值', 'douyin', self.banned, set())))
        self.assertEqual(cover_copy.check_cover_text('15999 元值不值', 'douyin', self.banned, {'15999'}), [])
    def test_formulas_and_set_rule(self):
        self.assertIn('question', cover_copy.formula_of('折叠屏值不值？')); self.assertIn('number', cover_copy.formula_of('贵 6000 元')); self.assertIn('contrast', cover_copy.formula_of('贵，但我买了'))
        rows, problems = cover_copy.check_set(['折叠屏 iPhone 到底值不值？', '苹果第一台折叠机贵 6000 元', '一万六，但我还是买了'], 'xiaohongshu', self.banned, {'6000'})
        self.assertEqual(problems, [])
        rows, problems = cover_copy.check_set(['苹果第一台折叠机来了', '苹果最贵的一台手机', '苹果新款折叠手机发布'], 'xiaohongshu', self.banned, set())
        self.assertEqual(len(problems), 1)
        self.assertEqual(cover_copy.check_set(['一条'], 'douyin', self.banned, set())[1], [])
    def test_title_rules(self):
        self.assertEqual(cover_copy.check_title('苹果折叠屏 iPhone Duo 上手：贵，但真香', 'bilibili', self.banned, set()), [])
        self.assertTrue(cover_copy.check_title('这' * 25, 'xiaohongshu', self.banned, set()))

class Reference(unittest.TestCase):
    def test_pick_order(self):
        film = {'assets': {'hero': {'kind': 'image', 'src': 'images/01.jpg'}, 'bgm': {'kind': 'audio', 'src': 'bgm/x.wav'}}}
        self.assertEqual(cover.pick_reference({}, {}, film)[0], 'hero')
        mats = {'items': [{'id': 'ui', 'status': 'ready', 'assetId': 'shot1'}, {'id': 'x', 'status': 'pending', 'assetId': 'nope'}]}
        self.assertEqual(cover.pick_reference({}, mats, film)[0], 'shot1')
        prod = {'media': [{'id': 'M1', 'kind': 'video', 'asset': 'v'}, {'id': 'M2', 'kind': 'image', 'asset': 'press', 'rights': '官方新闻稿素材'}]}
        key, why = cover.pick_reference(prod, mats, film); self.assertEqual(key, 'press'); self.assertIn('官方新闻稿', why)
        key, why = cover.pick_reference({}, {}, {}); self.assertIsNone(key); self.assertIn('纯文生图', why)
    def test_hook_line(self):
        self.assertIn('搜完之后', cover.hook_line({'beats': [{'kind': 'hook', 'narration': '搜完之后，答案到底从哪来的？'}]}))
        self.assertEqual(cover.hook_line({'beats': []}), ''); self.assertIn('半折', cover.hook_line({}, '半折的手机在桌上'))

if __name__ == '__main__': unittest.main()
