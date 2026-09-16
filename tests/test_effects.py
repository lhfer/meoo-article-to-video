"""4.0.5 / 1.0.5: GL flag only for projects that use WebGL2 parts, the bespoke-shot warning, and the effects radar's pure functions."""
import json, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import subprocess, effects_radar, render, review, validate

RADAR_MD = """# radar
| 包 | 结论 |
|---|---|
| `@remotion/effects` | 采纳 |
| @remotion/transitions | 评估未采纳 |
| `@remotion/cli` | 基础设施 |
plain text mentioning @remotion/three is not a row

### 下一轮候选
| 包 | 为什么 |
|---|---|
| `@remotion/sfx` | 音效库 |
"""


def project(shot_source, scheduled=True, extra=None):
    """A project whose film schedules shot A (or not); `extra` adds an unscheduled shot file, as a shipped reference shot would be."""
    d = Path(tempfile.mkdtemp()); (d / 'src/shots').mkdir(parents=True); (d / 'content').mkdir(); (d / 'src/shots/A.tsx').write_text(shot_source, encoding='utf-8')
    comps = {'A': 'shots/A.tsx'}
    if extra is not None: (d / 'src/shots/B.tsx').write_text(extra, encoding='utf-8'); comps['B'] = 'shots/B.tsx'
    (d / 'content/film.json').write_text(json.dumps({'components': comps, 'shots': [{'id': 'a', 'component': 'A'}] if scheduled else []}), encoding='utf-8'); return d


class Effects(unittest.TestCase):
    def test_gl_backend_only_when_a_shot_uses_webgl_parts(self):
        plain = project("import {Slam} from '../kit'; export default () => <Slam text='x' at={0} size={10} />;")
        self.assertIsNone(render.gl_backend(plain, {}))
        fx = project("import {LightLeak} from '../kit'; export default () => <LightLeak at={10} />;")
        self.assertEqual(render.gl_backend(fx, {}), 'angle')
        self.assertEqual(render.gl_backend(plain, {'render': {'gl': 'swangle'}}), 'swangle')
        self.assertIsNone(render.gl_backend(fx, {'render': {'gl': 'default'}}))  # explicit opt-out keeps the plain command
        self.assertIsNone(render.gl_backend(project("// <LightLeakish> is not a part"), {}))
        shipped = project("import {Slam} from '../kit'; export default () => <Slam text='x' at={0} size={10} />;", extra="import {Starburst} from '../kit'; export default () => <Starburst at={0} x={1} y={1} />;")
        self.assertIsNone(render.gl_backend(shipped, {}))  # an unscheduled reference shot (KitShowcase in a launch project) must not trigger the GPU path
        self.assertIsNone(render.gl_backend(project("import {LightLeak} from '../kit'; export default () => <LightLeak at={10} />;", scheduled=False), {}))
        self.assertEqual(render.gl_flags('angle'), ['--gl=angle', '--image-format=png']); self.assertEqual(render.gl_flags(None), [])  # plain projects keep the exact command
    def test_bespoke_missing_only_for_finished_full_films(self):
        full = {'scope': 'full', 'shots': [{'id': 'a'}, {'id': 'b'}]}
        self.assertTrue(validate.bespoke_missing(full)); self.assertFalse(validate.bespoke_missing(full, draft=True))
        self.assertFalse(validate.bespoke_missing({'scope': 'opening', 'shots': [{'id': 'a'}]}))
        self.assertFalse(validate.bespoke_missing({'scope': 'full', 'shots': [{'id': 'a'}, {'id': 'b', 'bespoke': '水流：方程讲的是水怎么流'}]}))
    def test_carry_verdict_tolerates_only_gpu_dither_with_identical_audio(self):
        self.assertTrue(review.carry_verdict(True, True, True, None, None)[0])
        self.assertFalse(review.carry_verdict(False, True, True, 2, None)[0])       # plain renders must stay byte-identical
        self.assertTrue(review.carry_verdict(False, True, True, 2, 'angle')[0])     # ±2 dithering under a GPU backend carries
        self.assertFalse(review.carry_verdict(False, True, True, review.GL_DITHER_TOLERANCE + 1, 'angle')[0])
        self.assertFalse(review.carry_verdict(False, True, False, 1, 'angle')[0])   # audio must match
        self.assertFalse(review.carry_verdict(False, False, True, 1, 'angle')[0])   # same size and frame count
    def test_max_frame_difference_measures_decoded_levels(self):
        d = Path(tempfile.mkdtemp())
        for name, color in [('a', '0x404040'), ('b', '0x404040'), ('c', '0x484848')]:
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', f'color=c={color}:s=64x64:d=0.2:r=10', '-pix_fmt', 'yuv420p', str(d / f'{name}.mp4')], check=True)
        self.assertEqual(review.max_frame_difference(d / 'a.mp4', d / 'b.mp4'), 0)
        self.assertTrue(4 <= review.max_frame_difference(d / 'a.mp4', d / 'c.mp4') <= 12)
        self.assertEqual(review.decoded_signature(d / 'a.mp4')['count'], 2)
    def test_radar_reads_table_rows_and_lists_only_new_packages(self):
        names = effects_radar.evaluated_names(RADAR_MD)
        self.assertEqual(names, {'@remotion/effects', '@remotion/transitions', '@remotion/cli'})  # 下一轮候选 rows stay unevaluated
        rows = [{'name': '@remotion/effects', 'version': '4.0.523'}, {'name': '@remotion/new-thing', 'version': '4.0.523', 'description': 'x'}, {'name': 'not-remotion', 'version': '1'}, {'name': '@remotion/cli', 'version': '4.0.523'}]
        self.assertEqual([r['name'] for r in effects_radar.unevaluated(rows, names)], ['@remotion/new-thing'])
        self.assertEqual(effects_radar.pinned_version(Path(__file__).resolve().parents[1] / 'assets/director/package.json'), '4.0.520')


if __name__ == '__main__': unittest.main()
