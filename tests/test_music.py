"""Music fit math and qa luma/change analyzers (pure functions)."""
import sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / 'scripts'))
import music, music_tone, qa

class Fit(unittest.TestCase):
    def test_solve_trim(self):
        self.assertEqual(music.solve_trim(2.075, 1.4), (0.675, 0.0)); self.assertEqual(music.solve_trim(2.075, 3.0), (0.0, 0.925)); self.assertEqual(music.solve_trim(1.0, 1.0), (0.0, 0.0))

class Tone(unittest.TestCase):
    def test_archetype_order_explicit_then_product_then_script_then_profile(self):
        self.assertEqual(music_tone.derive_archetype({'profile': 'launch', 'music': {'archetype': 'hype'}}, {'tone': {'adjectives': ['沉稳']}}, {})[0], 'hype')
        key, reasons = music_tone.derive_archetype({'profile': 'viral'}, {'tone': {'adjectives': ['克制', '可靠'], 'energy': 2}, 'category': '效率工具'}, {}); self.assertEqual(key, 'calm'); self.assertTrue(any('克制' in r for r in reasons))
        self.assertEqual(music_tone.derive_archetype({'profile': 'launch'}, {'tone': {'energy': 5}}, {})[0], 'upbeat'); self.assertEqual(music_tone.derive_archetype({'profile': 'viral'}, {'tone': {'energy': 5}}, {})[0], 'upbeat')  # energy alone never means 燃
        self.assertEqual(music_tone.derive_archetype({'profile': 'viral'}, {'tone': {'adjectives': ['燃', '对决'], 'energy': 5}}, {})[0], 'hype')
        key, _ = music_tone.derive_archetype({'profile': 'viral'}, {'tone': {'adjectives': ['重磅', '高级', '精密'], 'energy': 4}, 'category': '消费电子'}, {}); self.assertIn(key, ('upbeat', 'tech')); self.assertNotEqual(key, 'hype')
        self.assertEqual(music_tone.derive_archetype({'profile': 'viral'}, {}, {'beats': [{'narration': '翻车了，内幕是'}, {'narration': '反转'}]})[0], 'suspense')
        self.assertEqual(music_tone.derive_archetype({'profile': 'viral'}, {}, {})[0], 'upbeat'); self.assertEqual(music_tone.derive_archetype({'profile': 'launch'}, {}, {})[0], 'calm')
        with self.assertRaises(ValueError): music_tone.derive_archetype({'music': {'archetype': 'disco'}}, {}, {})
    def test_bpm_follows_pace(self):
        self.assertEqual(music_tone.bpm_range('upbeat'), (118, 132)); self.assertEqual(music_tone.bpm_range('upbeat', 8.0, 1.5), (126, 140))  # +6 pace +4 cuts, clamped to +8; self.assertEqual(music_tone.bpm_range('calm', 7.4, 2.5), (80, 100))
    def test_prompt_has_no_vocals_no_intro_and_speech_band_rule(self):
        spec = music_tone.plan_spec({'profile': 'viral', 'platforms': ['douyin'], 'pacing': {'targetCps': 8.0}}, {'name': 'X'}, {'beats': [{'id': 'h', 'kind': 'hook', 'narration': '一二三四五六七八' * 3}, {'id': 't', 'kind': 'turn', 'narration': '一二三四五六七八' * 4}, {'id': 's', 'kind': 'summary', 'narration': '一二三四五六七八' * 2}]}, candidates=3)
        text = spec['prompts'][0]['prompt']; self.assertLessEqual(len(text), 2000)
        for must in ['不要人声', '第一小节', '不要淡入', '1–4 kHz', '抖音', '可无缝循环']: self.assertIn(must, text)
        self.assertEqual([p['id'] for p in spec['prompts']], ['main', 'percussive', 'bright']); self.assertIn('打击版', spec['prompts'][1]['prompt'])
        ats = [p['at'] for p in spec['structure']]; self.assertEqual(ats, sorted(ats)); self.assertEqual(spec['structure'][0]['want'], 'drop'); self.assertEqual(spec['structure'][-1]['want'], 'end')
        self.assertEqual([p['want'] for p in music_tone.structure([], 6.0)], ['drop', 'end'])
    def test_tempo_match_accepts_half_and_double(self):
        self.assertEqual(music_tone.tempo_match([62.0, 93.0], (118, 132)), (124.0, 2.0)); self.assertEqual(music_tone.tempo_match([250.0], (118, 132)), (125.0, 0.5)); self.assertEqual(music_tone.tempo_match([90.0], (118, 132)), (None, None))
    def test_score_prefers_early_hit_and_free_midrange(self):
        base = {'firstStrongHitSeconds': 0.5, 'tempoEstimatesBpm': [125.0], 'tempoConfidence': 1.0, 'speechBandRatio': 0.1, 'durationSeconds': 60, 'crestFactorDb': 12}
        good = music_tone.score_candidate(base, (118, 132), 40)[0]
        late = music_tone.score_candidate({**base, 'firstStrongHitSeconds': 4.5}, (118, 132), 40)[0]
        busy = music_tone.score_candidate({**base, 'speechBandRatio': 0.5}, (118, 132), 40)[0]
        short = music_tone.score_candidate({**base, 'durationSeconds': 20}, (118, 132), 40)[0]
        self.assertGreater(good, late); self.assertGreater(good, busy); self.assertGreater(good, short); self.assertGreater(late, music_tone.score_candidate({**base, 'firstStrongHitSeconds': None}, (118, 132), 40)[0])
    def test_bar_grid_phase_and_bounds(self):
        bars = music_tone.bar_grid(120, 2.075, 0.675, 0.0, 10.0)
        self.assertEqual([b['seconds'] for b in bars][:3], [1.4, 3.4, 5.4]); self.assertEqual(bars[-1]['seconds'], 9.4); self.assertEqual(bars[0]['id'], 'bgm.bar_1')
        beats = music_tone.bar_grid(120, 2.075, 0.675, 1.0, 3.0, beats=True); self.assertEqual([b['seconds'] for b in beats], [1.4, 1.9, 2.4, 2.9])
        self.assertEqual(music_tone.bar_grid(120, 0.0, 0.0, 0.0, 4.0)[0]['seconds'], 0.0)
        with self.assertRaises(ValueError): music_tone.bar_grid(0, 0, 0, 0, 1)

class Luma(unittest.TestCase):
    def test_flash_and_black_limits(self):
        y = [60] * 30 + [230] * 3 + [60] * 300 + [230] * 6 + [60] * 30
        findings, stats = qa.analyze_luma(y, 30)
        self.assertEqual(stats['flashes'], 2); self.assertTrue(any(f['kind'] == 'flash-too-long' for f in findings)); self.assertFalse(any(f['kind'] == 'flash-frequency' for f in findings))
        findings, _ = qa.analyze_luma([60] * 30 + [230] * 2 + [60] * 30 + [230] * 2 + [60] * 30, 30); self.assertTrue(any(f['kind'] == 'flash-frequency' for f in findings))
        findings, _ = qa.analyze_luma([60] * 30 + [2] * 12 + [60] * 30, 30); self.assertTrue(any(f['kind'] == 'black-frames' for f in findings))
        findings, _ = qa.analyze_luma([60] * 30 + [2] * 5 + [60] * 30, 30); self.assertFalse(any(f['kind'] == 'black-frames' for f in findings))
    def test_visual_change_gaps(self):
        diff = [0] * 90 + [20] + [0] * 30
        gaps, stats = qa.analyze_changes(diff, 30, 1.5); self.assertEqual(len(gaps), 1); self.assertEqual(gaps[0]['seconds'], 3.0); self.assertEqual(stats['changes'], 1)
        self.assertEqual(qa.analyze_changes([0] * 30 + [20] + [0] * 30, 30, 1.5)[0], [])
    def test_still_runs_events_drift_and_holds(self):
        static = [bytes([60]) * 100] * 40  # 4 s at 10 fps, nothing moves
        stills, stats = qa.still_runs(static, 10, 1.5); self.assertEqual(stats['changes'], 0); self.assertEqual([(g['fromSeconds'], g['seconds']) for g in stills], [(0.0, 4.0)])
        event = static[:20] + [bytes([120]) * 100] * 20  # one big change at 2.0 s: two 2 s stills, both over 1.5 s
        stills, stats = qa.still_runs(event, 10, 1.5); self.assertEqual(stats['changes'], 1); self.assertEqual([g['fromSeconds'] for g in stills], [0.0, 2.0])
        drift = [bytes([60 + i]) * 100 for i in range(40)]  # +1 luma per frame: no adjacent step, but the drift accumulates past the delta well inside the window
        stills, stats = qa.still_runs(drift, 10, 1.5); self.assertEqual(stills, []); self.assertGreater(stats['changes'], 5)
        timeline = {'fps': 30, 'shots': [{'id': 'rec', 'from': 0, 'end': 90, 'hold': '录屏证据：观众跟着光标看'}, {'id': 'b', 'from': 90, 'end': 180}]}
        keep, declared = qa.split_holds([{'fromSeconds': 0.5, 'toSeconds': 2.5, 'seconds': 2.0}, {'fromSeconds': 3.0, 'toSeconds': 6.0, 'seconds': 3.0}], timeline)
        self.assertEqual([g['fromSeconds'] for g in keep], [3.0]); self.assertEqual(declared[0]['shot'], 'rec')
    def test_cut_checks(self):
        t = {'fps': 30, 'events': {'hit': 100}, 'shots': [{'id': 'a', 'from': 0, 'anchor': None}, {'id': 'b', 'from': 104, 'anchor': 'hit'}], 'voices': [{'id': 'v', 'from': 90, 'words': [{'text': '一', 'startMs': 300, 'endMs': 700}]}]}
        f = qa.cut_checks(t); kinds = {x['kind'] for x in f}; self.assertIn('cut-off-event', kinds); self.assertIn('cut-inside-word', kinds)

if __name__ == '__main__': unittest.main()


class Coverage(unittest.TestCase):
    def test_clustered_left_and_narrow_16x9(self):
        left = {'x0': 0.05, 'x1': 0.5, 'y0': 0.1, 'y1': 0.8, 'thirds': [0.7, 0.3, 0.0]}
        full = {'x0': 0.05, 'x1': 0.95, 'y0': 0.1, 'y1': 0.8, 'thirds': [0.35, 0.3, 0.35]}
        findings, stats = qa.analyze_coverage([left] * 7 + [full] * 3, '16x9'); kinds = {f['kind'] for f in findings}
        self.assertEqual(kinds, {'narrow-content', 'clustered-left'}); self.assertEqual(stats['clusteredFrames'], 7)
        self.assertEqual(qa.analyze_coverage([full] * 8 + [left] * 2, '16x9')[0], [])
        self.assertEqual(qa.analyze_coverage([None, None], '16x9'), ([], {'sampled': 0}))
    def test_short_vertical(self):
        short = {'x0': 0.1, 'x1': 0.9, 'y0': 0.1, 'y1': 0.4, 'thirds': [0.3, 0.4, 0.3]}
        self.assertEqual([f['kind'] for f in qa.analyze_coverage([short] * 5, '3x4')[0]], ['short-content']); self.assertEqual(qa.analyze_coverage([short] * 5, '16x9')[0], [])
    def test_frame_placement_ignores_caption_band(self):
        w, h = 12, 8; bg = 240; frame = bytearray([bg] * (w * h))
        for y in range(1, 4):
            for x in range(1, 4): frame[y * w + x] = 20     # content top-left
        for x in range(2, 10): frame[7 * w + x] = 20        # caption band (bottom row) must not count
        p = qa.frame_placement(bytes(frame), w, h, '16x9'); self.assertAlmostEqual(p['x1'], 4 / 12, places=3); self.assertEqual(p['thirds'], [1.0, 0.0, 0.0])
        self.assertIsNone(qa.frame_placement(bytes([bg] * (w * h)), w, h, '16x9'))
