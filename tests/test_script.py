"""script_check.py: the audience-seat pass, measured. Errors only for the opening; the rest are hints calibrated on confirmed videos."""
import json, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import script_check

GOOD = {'title': 'OpenAI 深夜王炸', 'thesis': '解了题，不要奖金', 'viewerPromise': '三分钟看懂这题为什么值一百万',
        'hookVariants': [{'id': 'q', 'type': '疑问', 'narration': '一道 26 年没人拿走的悬赏，AI 88 小时交卷，为什么不要钱？'}, {'id': 'r', 'type': '反差', 'narration': 'OpenAI 攻克七大难题之一，然后放弃 100 万美元。'}],
        'beats': [
            {'id': 'hook', 'kind': 'hook', 'narration': 'OpenAI深夜王炸，宣布新模型攻克了世界七大数学难题之一，并宣布放弃100万美元。', 'viewerGain': '你知道今晚最大的事是什么', 'claims': ['c1']},
            {'id': 'prize', 'kind': 'setup', 'narration': '这100万，是克雷研究所2000年挂出来的悬赏，26年没人拿走。', 'viewerGain': '你知道这笔钱的分量'},
            {'id': 'what', 'kind': 'chapter', 'narration': '这题叫纳维-斯托克斯方程，专门算水怎么流。但有个问题90年没人答上来：一团流得好好的水，会不会某个点的速度冲到无穷大？', 'viewerGain': '你能用一句话讲清这道题'},
            {'id': 'turn', 'kind': 'turn', 'narration': '那为什么不要这100万？官方题面有四个版本，它证的是有外力推着的那两个；数学家心里的真题，是没外力的那两个。', 'viewerGain': '你看到被埋掉的条件'},
            {'id': 'sum', 'kind': 'summary', 'narration': '截图收藏：题解了一半，奖金没人领，克雷研究所说先发表、再等两年。', 'viewerGain': '你收藏三条结论'},
            {'id': 'cta', 'kind': 'cta', 'narration': '90年的题，88小时。你觉得，这题算解出来了吗？', 'viewerGain': '你有话想说'},
        ]}
BAD = {'title': 'x', 'beats': [
    {'id': 'intro', 'kind': 'setup', 'narration': '大家好，今天给大家介绍一款很好用的软件，它的功能非常丰富，接下来我们一起来看看它到底能做什么以及怎么使用它才是最合适的方式吧。'},
    {'id': 'body', 'kind': 'chapter', 'narration': '首先它支持 MCP 协议。'},
    {'id': 'end', 'kind': 'ending', 'narration': '感谢观看，我们下期见。'},
]}
BRIEF = {'profile': 'viral', 'pacing': {'targetCps': 8.0, 'gapPolicy': {'default': 0.3, 'byBeatKind': {'hook': 0.25, 'turn': 0.5}}}}


def project(script, brief=BRIEF, claims=None):
    d = Path(tempfile.mkdtemp()); (d / 'content').mkdir()
    (d / 'content/script.json').write_text(json.dumps(script, ensure_ascii=False)); (d / 'content/brief.json').write_text(json.dumps(brief))
    if claims is not None: (d / 'content/claims.json').write_text(json.dumps(claims, ensure_ascii=False))
    return d


class ScriptCheck(unittest.TestCase):
    def test_confirmed_style_script_passes_with_a_retention_timeline(self):
        r = script_check.check(project(GOOD))
        self.assertEqual(r['errors'], []); self.assertEqual([w['code'] for w in r['warnings']], [])
        self.assertEqual(r['timeline'][0]['beat'], 'hook'); self.assertEqual(r['timeline'][-1]['beat'], 'cta')
        self.assertIn('名字', r['stats']['hookAnchors']); self.assertEqual(r['stats']['hookVariants'], 2)
        self.assertTrue(0.35 <= r['beats'][3]['start'] / r['stats']['estimatedSeconds'] <= 0.75)
        self.assertNotIn('L-HOOK-VARIANTS', [i['code'] for i in r['info']])
    def test_opening_errors_and_hints_on_a_broadcast_script(self):
        r = script_check.check(project(BAD)); codes = {e['code'] for e in r['errors']}; warns = {w['code'] for w in r['warnings']}; hints = {i['code'] for i in r['info']}
        self.assertEqual(codes, {'L-FIRST-HOOK', 'L-HOOK-OPENER', 'L-HOOK-3S'})  # a greeting has no anchor inside the first 3 seconds either
        self.assertIn('L-BREATH', warns); self.assertIn('L-FILLER', warns); self.assertIn('L-TURN', warns); self.assertIn('L-GAIN', warns); self.assertIn('L-HOOK-LEN', warns)
        self.assertIn('L-TERM', hints); self.assertIn('L-MID-OPENER', hints); self.assertIn('L-HOOK-VARIANTS', hints); self.assertIn('L-YOU', hints)
    def test_hook_anchor_is_read_across_short_beats_and_missing_anchor_is_an_error(self):
        ok = {'beats': [{'id': 'h', 'kind': 'hook', 'narration': '有人带着一个想法来现场，'}, {'id': 's', 'kind': 'setup', 'narration': '72分钟后它变成一个能用的应用。'}]}
        self.assertEqual([e['code'] for e in script_check.check(project(ok))['errors']], [])
        flat = {'beats': [{'id': 'h', 'kind': 'hook', 'narration': '我们的产品是一个帮助用户管理信息的工具，功能很多。'}]}
        self.assertIn('L-HOOK-3S', [e['code'] for e in script_check.check(project(flat))['errors']])
    def test_ending_accepts_question_callback_or_invitation(self):
        base = [{'id': 'h', 'kind': 'hook', 'narration': 'iPhone Duo 真机到底长什么样？'}, {'id': 'b', 'kind': 'chapter', 'narration': '合上以后是短短宽宽的比例。', 'viewerGain': '你看到真机比例'}]
        for end, ok in [('二十条看完，最让你心动的是哪一个？', True), ('Duo 的开合动画，就是这条视频最想给你看的。', True), ('等它把整个乐园跑完，我一定要给你们看看效果。', True), ('这就是全部内容。', False)]:
            codes = [w['code'] for w in script_check.check(project({'beats': base + [{'id': 'e', 'kind': 'ending', 'narration': end, 'viewerGain': '你知道该看什么'}]}))['warnings']]
            self.assertEqual('L-ENDING' not in codes, ok, end)
    def test_numbers_are_checked_against_claims_and_repeats_are_hints(self):
        r = script_check.check(project(GOOD, claims=[{'id': 'c1', 'quote': '100万美元 26年 2000年 88小时 90年'}]))
        self.assertEqual([w['code'] for w in r['warnings']], [])
        self.assertTrue(any(i['code'] == 'L-NUM-REPEAT' and '100' in i['message'] for i in r['info']))
        r = script_check.check(project(GOOD, claims=[{'id': 'c1', 'quote': '100万美元'}]))
        self.assertIn('L-NUM-SOURCE', [w['code'] for w in r['warnings']])
    def test_empty_seed_and_markdown_do_not_crash(self):
        r = script_check.check(project({'beats': []})); self.assertEqual(r['info'][0]['code'], 'S-EMPTY'); self.assertIn('还没有 beats', script_check.markdown(r))
        md = script_check.markdown(script_check.check(project(GOOD))); self.assertIn('留存时间轴', md); self.assertIn('| hook | hook |', md)
    def test_launch_profile_thresholds_and_cta_rule(self):
        brief = {'profile': 'launch', 'pacing': {'targetCps': 7.4, 'gapPolicy': {'default': 0.45}}}
        s = {'beats': [{'id': 'h', 'kind': 'hook', 'narration': '收件箱 200 封未读，我做了个工具让它每天变成一页待办。', 'viewerGain': '你看到它解决哪件事'},
                       {'id': 'demo', 'kind': 'evidence', 'narration': '你看，这 3 封邮件 2 秒进了对应文件夹。', 'viewerGain': '你看到证据'}]}
        r = script_check.check(project(s, brief)); self.assertEqual(r['errors'], []); self.assertIn('L-CTA', [w['code'] for w in r['warnings']]); self.assertNotIn('L-TURN', [w['code'] for w in r['warnings']])


if __name__ == '__main__': unittest.main()
