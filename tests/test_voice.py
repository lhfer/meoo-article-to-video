"""Unit tests for the voice pipeline: Fish SSE parsing (real recorded fixture), breath-cut planning and timestamp
remapping, spoken→display mapping, tags/fingerprints, gap policy, request builders. No network, no ffmpeg."""
import json, sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / 'scripts'))
import tts_fish, tts_seed2, voice_edit, align, tts
from common import spoken_text, tts_text, strip_tags, chunk_text, weighted_len, apply_overrides, norm

FIXTURE = ROOT / 'tests/fixtures/fish-sse.txt'


class FishStream(unittest.TestCase):
    def test_recorded_stream_parses_to_monotonic_tokens(self):
        raw = FIXTURE.read_bytes()
        audio, tokens, mode = tts_fish.collect_stream(tts_fish.sse_events(raw.splitlines()))
        self.assertEqual(mode, 'snapshot'); self.assertGreater(len(audio), 100000); self.assertEqual(len(tokens), 32)
        self.assertTrue(all(b['start'] >= a['start'] for a, b in zip(tokens, tokens[1:])))
        self.assertEqual(norm(''.join(t['text'] for t in tokens)), norm('家人们，实在太离谱了。海外博主两句话就复刻了英雄联盟，连英雄都是原版的！'))
        self.assertLessEqual(tokens[-1]['end'], 4.876 + 0.18)
    def test_sse_parser_handles_comments_crlf_multiline_and_unterminated(self):
        lines = [x.encode('utf-8') for x in [': keepalive', 'data: {"audio_base64":"AA==",', 'data: "alignment":null}\r', '', 'data: [DONE]', '', 'data: {"audio_base64":"","alignment":{"segments":[{"text":"你","start":0,"end":0.1}]},"chunk_seq":0,"chunk_audio_offset_sec":0}']]
        events = list(tts_fish.sse_events(lines)); self.assertEqual(len(events), 2)
        audio, tokens, mode = tts_fish.collect_stream(events); self.assertEqual(mode, 'snapshot'); self.assertEqual(tokens[0]['text'], '你')
    def test_snapshot_offsets_and_cumulative_fallback(self):
        ev = [{'audio_base64': 'AA==', 'alignment': {'segments': [{'text': 'a', 'start': 0, 'end': .5}]}, 'chunk_seq': 0, 'chunk_audio_offset_sec': 0},
              {'audio_base64': 'AA==', 'alignment': {'segments': [{'text': 'b', 'start': 0, 'end': .4}]}, 'chunk_seq': 1, 'chunk_audio_offset_sec': 2.0}]
        _, tokens, _ = tts_fish.collect_stream(ev); self.assertEqual([t['start'] for t in tokens], [0, 2.0])
        ev = [{'audio_base64': 'AA==', 'alignment': {'segments': [{'text': 'a', 'start': 0, 'end': .5}]}}, {'audio_base64': '', 'alignment': {'segments': [{'text': 'a', 'start': 0, 'end': .5}, {'text': 'b', 'start': .6, 'end': .9}]}}]
        _, tokens, mode = tts_fish.collect_stream(ev); self.assertEqual(mode, 'cumulative'); self.assertEqual(len(tokens), 2)
        with self.assertRaises(tts_fish.ProviderError): tts_fish.collect_stream([{'audio_base64': 'AA==', 'alignment': {'segments': [{'text': 'b', 'start': 1, 'end': 2}, {'text': 'a', 'start': 0, 'end': .5}]}}])
        with self.assertRaises(tts_fish.ProviderError): tts_fish.collect_stream([{'foo': 1}])


class BreathEdit(unittest.TestCase):
    cfg = voice_edit.settings({})
    def test_remap_is_monotone_and_totals_add_up(self):
        cuts = [(0.0, 0.25), (2.09, 2.41), (5.9, 6.0)]
        self.assertAlmostEqual(voice_edit.remap(6.0, cuts), 6.0 - sum(e - s for s, e in cuts))
        ts = [0, 0.1, 0.25, 0.3, 2.0, 2.09, 2.2, 2.41, 2.5, 5.9, 6.0]; out = [voice_edit.remap(t, cuts) for t in ts]
        self.assertEqual(out, sorted(out)); self.assertEqual(voice_edit.remap(0.25, cuts), 0.0); self.assertAlmostEqual(voice_edit.remap(2.41, cuts), 2.09 - 0.25)
    def test_plan_cuts_respects_native_boundaries(self):
        cuts = voice_edit.plan_cuts([(0.0, 0.6), (5.7, 6.0)], 6.0, self.cfg, [{'text': 'a', 'start': 0.3, 'end': 0.5}, {'text': 'b', 'start': 5.5, 'end': 5.8}])
        self.assertEqual(cuts[0], (0.0, 0.275)); self.assertEqual(cuts[1][0], 5.85)
        cuts = voice_edit.plan_cuts([(1.0, 1.5)], 6.0, self.cfg); self.assertEqual(cuts, [(1.09, 1.41)])
        self.assertEqual(voice_edit.plan_cuts([(1.0, 1.25)], 6.0, self.cfg), [])
    def test_keeps_and_token_remap_merge_zero_length(self):
        cuts = [(0.0, 0.25), (2.0, 2.5)]; self.assertEqual(voice_edit.keeps_from_cuts(cuts, 3.0), [(0.25, 2.0), (2.5, 3.0)])
        words = voice_edit.remap_tokens([{'text': '一', 'start': 0.3, 'end': 0.6}, {'text': '，', 'start': 2.1, 'end': 2.4}, {'text': '二', 'start': 2.6, 'end': 2.9}], cuts)
        self.assertEqual([w['text'] for w in words], ['一', '，二']); self.assertEqual(words[1]['startMs'], 1850.0)
    def test_gap_policy(self):
        policy = {'default': 0.3, 'min': 0.12, 'max': 0.8, 'byPunctuation': {'。': 0.3, '？': 0.4}, 'byBeatKind': {'turn': 0.5}}
        self.assertEqual(voice_edit.gap_seconds({'narration': '好。'}, {'kind': 'chapter'}, policy), 0.3)
        self.assertEqual(voice_edit.gap_seconds({'narration': '好？'}, {'kind': 'turn'}, policy), 0.5)
        self.assertEqual(voice_edit.gap_seconds({'narration': '好', 'voice': {'pauseAfter': 2}}, {}, policy), 0.8)
        self.assertEqual(voice_edit.gap_seconds({'narration': '好'}, {}, policy), 0.3)
    def test_edit_fingerprint_changes_with_parameters(self):
        a = voice_edit.edit_fingerprint('abc', voice_edit.settings({})); b = voice_edit.edit_fingerprint('abc', voice_edit.settings({'voiceEdit': {'keepInternalPauseSeconds': 0.12}}))
        self.assertNotEqual(a, b); self.assertEqual(a, voice_edit.edit_fingerprint('abc', voice_edit.settings({'voiceEdit': {'enabled': False}})))
    def test_silencedetect_parse_closes_dangling_run(self):
        self.assertEqual(voice_edit.parse_silencedetect('x silence_start: 0.5\n silence_end: 0.9 | d\nsilence_start: 3.1\n', 4.0), [(0.5, 0.9), (3.1, 4.0)])


class SpokenDisplay(unittest.TestCase):
    def test_overrides_and_stale_spoken(self):
        b = {'id': 'x', 'narration': 'OpenAI深夜王炸，宣布放弃100万美元。', 'overrides': [['100万美元', '一百万美元']]}
        self.assertEqual(spoken_text(b), 'OpenAI深夜王炸，宣布放弃一百万美元。')
        with self.assertRaises(ValueError): spoken_text({**b, 'spoken': '另一句'})
        self.assertEqual(apply_overrides('aab', [['a', 'x'], ['aa', 'y']]), 'yb')
    def test_mapping_inherits_replacement_span_and_splits_multichar_tokens(self):
        narr = 'OpenAI深夜王炸，宣布放弃100万美元。'; ov = [['100万美元', '一百万美元'], ['OpenAI', 'open A I']]
        sp_chars = [c for c in 'open A I深夜王炸，宣布放弃一百万美元。' if not align._isp(c)]
        words = [{'text': 'open', 'startMs': 0, 'endMs': 390}] + [{'text': c, 'startMs': i * 100, 'endMs': i * 100 + 90} for i, c in enumerate(sp_chars) if i >= 4]
        m = align.map_spoken_to_display(narr, ov, words, 16)
        self.assertEqual(''.join(w['text'] for w in m['words']), ''.join(c for c in narr if not align._isp(c)))
        self.assertEqual(m['words'][0]['startMs'], 0); self.assertEqual([w['text'] for w in m['words'][-6:]], list('100万美元'))
        self.assertEqual([c['text'] for c in m['captions']], ['OpenAI深夜王炸，', '宣布放弃100万美元。'])
        with self.assertRaises(ValueError): align.map_spoken_to_display(narr, ov, words[:-1], 16)
    def test_tags_and_fingerprints(self):
        b = {'id': 'x', 'narration': '你好'}; brief = {'tts': {'emotion': {'default': '[excited]'}}}
        self.assertEqual(tts_text(b, brief, tts_fish.emotion), '[excited]你好'); self.assertEqual(strip_tags('[excited]你好'), '你好')
        self.assertEqual(tts_text(b, {'tts': {'emotion': {'enabled': False, 'default': '[excited]'}}}, tts_fish.emotion), '你好')
        self.assertNotEqual(tts.synth_fingerprint('[excited]你好', 'fish', 'm', 's', {'speed': 1.3}, '1'), tts.synth_fingerprint('[calm]你好', 'fish', 'm', 's', {'speed': 1.3}, '1'))
        self.assertEqual(chunk_text('一二三。四五六！七八九', 7), ['一二三。', '四五六！七八九']); self.assertEqual(weighted_len('读 W-2，自动填'), 6.8)


class Requests(unittest.TestCase):
    def test_fish_request_builder(self):
        r = tts_fish.build_request('[calm]你好', {'reference_id': 'ref', 'model': 's2.1-pro-free'}, {'speed': 1.4, 'temperature': 0.5})
        self.assertEqual(r['headers']['model'], 's2.1-pro-free'); self.assertEqual(r['body']['prosody']['speed'], 1.4); self.assertEqual(r['body']['format'], 'wav'); self.assertNotIn('Authorization', r['headers'])
        with self.assertRaises(ValueError): tts_fish.build_request('x', {'reference_id': 'ref'}, {'speed': 3})
    def test_seed_request_builder_keeps_v1_shape(self):
        r = tts_seed2.build_request('你好', {'speaker': 'v'}, {'rate': 40})
        self.assertEqual(r['body']['req_params']['audio_params'], {'format': 'mp3', 'sample_rate': 48000, 'speech_rate': 40}); self.assertEqual(tts_seed2.emotion('[x]'), '')
    def test_beat_params_precedence(self):
        brief = {'tts': {'params': {'speed': 1.3, 'temperature': 0.7}}}
        self.assertEqual(tts.beat_params(brief, {'voice': {'speed': 1.1}}, tts_fish.PARAM_KEYS, {'temperature': 0.5}), {'speed': 1.1, 'temperature': 0.5})
        self.assertEqual(tts.parse_params(['speed=1.2', 'style=快']), {'speed': 1.2, 'style': '快'})


if __name__ == '__main__': unittest.main()


class CaptionGrouping(unittest.TestCase):
    """Captions from the two user videos: never split an ASCII word, back up to punctuation instead of cutting a phrase."""
    def words(self, text):
        import align
        return [{'text': ch, 'startMs': i * 200, 'endMs': i * 200 + 180} for i, ch in enumerate(ch for ch in text if not align._isp(ch))]
    def test_never_splits_ascii_word(self):
        import align
        text = '整个应用是我在秒悟上 vibecoding 出来的页面、逻辑和演示数据'
        caps = align.group_captions(text, self.words(text), 16)
        joined = ''.join(c['text'] for c in caps); self.assertEqual(joined.replace(' ', ''), text.replace(' ', ''))
        for c in caps: self.assertFalse(c['text'].rstrip().endswith('vibec'), caps); self.assertNotIn('coding 出来', ''.join(x['text'] for x in caps if 'vibecoding' not in x['text']))
        self.assertTrue(any('vibecoding' in c['text'] for c in caps))
    def test_backs_up_to_dash_break(self):
        import align
        text = '广场里每个需求都标着赏金——不是现金，是真实资源'
        caps = align.group_captions(text, self.words(text), 16)
        self.assertFalse(any(c['text'].rstrip('，,').endswith('不是') for c in caps), caps); self.assertTrue(any('不是现金' in c['text'] for c in caps))
        caps = align.group_captions('广场里每个需求都标着赏金——不是现金也不是积分', self.words('广场里每个需求都标着赏金——不是现金也不是积分'), 16)
        self.assertEqual(caps[0]['text'], '广场里每个需求都标着赏金——'); self.assertTrue(caps[1]['text'].startswith('不是现金')); self.assertEqual(caps[0]['endMs'], self.words(text)[11]['endMs'])
    def test_sentence_and_comma_breaks_unchanged(self):
        import align
        text = '有人带着一个想法来现场。七十二分钟后，它变成一个能用的应用！'
        caps = align.group_captions(text, self.words(text), 16)
        self.assertEqual([c['text'] for c in caps], ['有人带着一个想法来现场。', '七十二分钟后，它变成一个能用的应用！'])
    def test_long_ascii_run_overflows_rather_than_splits(self):
        import align
        text = '我用的模型是 claude-fable-5-1 这一版'
        caps = align.group_captions(text, self.words(text), 8)
        self.assertTrue(any('claude-fable-5-1' in c['text'] for c in caps), caps)


class HostVoice(unittest.TestCase):
    def test_kind_emotion_defaults_then_brief_default(self):
        import tts
        brief = {'profile': 'launch', 'tts': {'emotion': {'default': '[calm]'}}}
        self.assertEqual(tts.beat_emotion({'kind': 'turn'}, brief), 'amazed'); self.assertEqual(tts.beat_emotion({'kind': 'cta'}, brief), 'warm')
        self.assertEqual(tts.beat_emotion({'kind': 'hook', 'voice': {'emotion': '[serious]'}}, brief), 'serious'); self.assertEqual(tts.beat_emotion({}, brief), 'calm')
        self.assertEqual(tts.beat_emotion({'kind': 'hook'}, {'profile': 'viral', 'tts': {'emotion': {'byKind': {'hook': 'laughing'}}}}), 'laughing')
        b = tts.with_kind_emotion({'id': 'x', 'kind': 'hook', 'narration': '你好'}, {'profile': 'viral'}); self.assertEqual(b['voice']['emotion'], 'excited')
    def test_host_instruction_states_pace_as_hard_requirement(self):
        import tts
        text = tts.host_instruction('launch', 'evidence', 'calm', 7.4, '数字读慢一点')
        for must in ['同行', '证据', '平稳清晰', '每秒约 7 个汉字', '硬性要求', '数字读慢一点']: self.assertIn(must, text)
        self.assertNotIn('每秒', tts.host_instruction('viral', 'hook', 'excited', None))
    def test_host_text_uses_only_confirmed_tags(self):
        import tts
        self.assertTrue(tts.host_text({'kind': 'hook', 'narration': '来了'}, {'profile': 'viral'}).startswith('[excited]'))
        self.assertEqual(tts.host_text({'kind': 'evidence', 'narration': '来了'}, {'profile': 'launch'}), '来了')  # calm is not a confirmed inline tag
        self.assertTrue(tts.host_text({'kind': 'turn', 'narration': '来了'}, {'profile': 'launch'}).startswith('[amazed]'))
    def test_expected_seconds_and_tempo_scaling(self):
        import tts
        e = tts.expected_seconds({'narration': '一二三四五六七八九十' * 2}, 8.0, 0.8); self.assertEqual(e['chars'], 20); self.assertEqual(e['target'], 2.5); self.assertLess(e['min'], e['target']); self.assertGreater(e['max'], e['target'])
        self.assertEqual(tts.scale_tokens([{'text': 'a', 'start': 1.0, 'end': 2.5}], 1.25), [{'text': 'a', 'start': 0.8, 'end': 2.0}]); self.assertIsNone(tts.expected_seconds({'narration': 'x'}, None, 0.5))
        self.assertEqual(tts.TEMPO_MAX, 1.3)
