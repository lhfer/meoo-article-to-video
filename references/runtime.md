> V5/V2 运行入口更新：渲染由 `scripts/render.py` → `core/render-checked.mjs` 调用官方 Remotion bundler/renderer API，收集实际逐帧布局回执。不得用直接 CLI 渲染绕过后仍声称通过最终交付。字幕几何/字号改动见 layout-and-qa.md。下面的数据 schema 与历史演进说明保留；历史“block 与 V3 完全一致”仅指时间分组，不再代表旧坐标或旧视觉样式。

# 可运行的导演工程

需要 Node 20+、npm、Python 3.9+、ffmpeg/ffprobe；网页提取与音乐分析按需使用 uv；Grok 图像转换需要 Pillow；whisper.cpp 可选。`assets/director` 提供运行骨架与两个参考镜头（`ContinuousExample`、`KitShowcase`）。

```bash
python3 <skill>/scripts/doctor.py
python3 <skill>/scripts/project.py init <work> [--profile viral|launch]
cd <work>/project && npm ci
python3 <skill>/scripts/project.py compile <work>/project --draft
npm run check
python3 <skill>/scripts/render.py <work>/project --stage draft --format all
```

## 内容与实现

`brief.json` 存账号偏好与 profile（声线、语速目标、气口策略、字幕样式、封面、效果预算）；`script.json` 存完整文案；`visual.json` 存本片创意；`film.json` 安排镜头与音轨；`alignment.json` 存实测时码；`materials.json` 是素材台账；`product.json` 是产品卡（`product.py`：identity、来源类型与信息等级 none|rumor|thin|solid、已收集 media、用户 confirm；每字段带 user|web|inferred 来源）；`music.json` 是音乐分析；`cover.json` 是封面候选；`timeline.json` 是编译产物。修改编译输入后重新编译。

口播段：

```json
{"id":"hook","kind":"hook","narration":"OpenAI深夜王炸，宣布放弃100万美元。","overrides":[["100万美元","一百万美元"]],"voice":{"emotion":"[excited]","pauseAfter":0.45},"viewerGain":"建立问题","claims":[]}
```

`narration` 是用户确认的显示文案；`overrides` 给读法（数字、英文、专名），`spoken` 只能是它的缓存；`voice` 可按段覆盖情绪标签、`speed`/`rate`、`pauseAfter`；`viewerGain` 用"你"写这段观众得到什么。顶层可选 `hookVariants[]`（2–3 个开场候选：`{type, narration}`，采用的放在 `beats[0]`）与 `glossary`（观众已认识的术语，`script_check.py` 不再提示）。这些字段都不影响脚本确认指纹。`project.py script` 会附上 `script_check.py` 的留存时间轴、划走点与提示（`out/script-check.md` / `.json`；ERROR 只针对开头：第一段是 hook、前 3 秒有钩子、不以问候开场）。

## 配音 → 气口 → 对齐

```bash
python3 <skill>/scripts/project.py script <project>            # out/script-review.md 交用户确认
python3 <skill>/scripts/review.py approve <project> script --evidence '用户实际确认原话'
python3 <skill>/scripts/tts.py calibrate <project> --sweep 1.3,1.45,1.6      # 可选：按目标字/秒定参数
python3 <skill>/scripts/tts.py <project> [--only hook,what]                   # 合成 → voice_edit 剪气口 → index → 自动导入原生时间戳
python3 <skill>/scripts/tts.py measure <project>
python3 <skill>/scripts/align.py review <project> --id hook --note '实际听音与修正记录'
python3 <skill>/scripts/project.py plan-voices <project>                     # voices[].at = {after, offset}（按标点/段类型的间隔）
```

`tts.py` 按 `brief.tts.provider` 路由：`fish`（原生逐字时间戳）、`seed2`（无时间戳，走 whisper）、宿主工具走 `tts.py plan` → 生成 → `tts.py import --id --audio [--timestamps]`。缓存要求合成指纹与剪辑指纹同时匹配。`voice_edit.py --report` 看每段剪掉多少；`align.py import --from-timing` 把口播文本上的时码映射回显示文案（`--words` 导入人工校订的显示文案时码，`transcribe` 用 whisper.cpp）。

导入数组形状遵循 Remotion Caption（`text/startMs/endMs`）；`alignment.json` 记录音频与文案 SHA256、剪辑指纹与实测字/秒。审核记录只对应实际完成的检查。

## 单一时间轴

```json
{"version":4,"scope":"opening","fps":30,"formats":["3x4","9x16"],"primaryFormat":"3x4",
 "components":{"Hook":"shots/Hook.tsx"},
 "voices":[{"id":"hook","at":0.3},{"id":"what","at":{"after":"hook","offset":0.3},"gapIntent":{"reason":"反转前停顿"}}],
 "events":{"slam":{"voice":"hook","word":"王炸","edge":"start"},"bgm.hit_1":1.05},
 "shots":[{"id":"s1","component":"Hook","start":0,"end":{"event":"what.start"},"anchor":"bgm.hit_1","layouts":{"3x4":{},"9x16":{}},"assets":[]}],
 "audio":[{"src":"bgm/bgm.wav","start":0,"end":{"event":"end"},"gain":0.55,"trimStart":1.02,"fadeIn":0.2,"fadeOut":1.5,"duck":0.45}],
 "captions":{"enabled":true,"style":"karaoke","maxChars":16},
 "style":{"preset":"impact","background":"#070b14","palette":{"accent":"#3b7bff"},"fonts":[],"fontRoles":{}}}
```

- 版本 3 或 4 都接受；`formats` 可为子集，layouts 只需覆盖这些画幅；`primaryFormat` 决定开头样片与确认。
- 时间引用可为秒数或 `{"event":"x","offset":0.15}`；事件支持 `voice-start / voice-end`、`word`（`occurrence`、`edge: end`）、`wordIndex`。
- 编译输出 `voiceGaps` / `leadSilenceSeconds` / `trailingSilenceSeconds`（量测），`validate.py` 按 `brief.pacing` 裁决；`gapIntent.reason` 登记有意留白；`shots[].hold: "原因"` 登记观众跟着看的静止镜头（如录屏证据），`render.py` 渲后的静止段检查对其不计。
- 4.0.5：`render.py` 走 GPU 后端时同时加 `--image-format=png`（PNG 中间帧；JPEG 会把 ±1 的 GPU 抖色放大到 26–38），`review.py carry-opening` 在 GPU 后端下允许解码画面 ±4 级抖动（实测 PNG 中间帧后 ≤ 3；默认后端逐字节一致），音频、尺寸、帧数必须一致；`shots[].bespoke: "这条片专属的视觉隐喻"`（完整片缺它 `validate.py` 警告；和 `hold` 一样，写在开头镜头上会进开头指纹，确认前写好或写在后面的镜头上）；`brief.render.gl`（`render.py` 在 `film.shots[]` 排到的镜头文件（含其本地 import，不含 kit）用到 `LightLeak` / `Starburst` 时自动加 `--gl=angle`；随包带着但没排进片子的参考镜头不算，无 GPU 机器写 `"swangle"`，`"default"` 强制不加）；新依赖 `@remotion/effects`、`@remotion/rough-notation`、`@remotion/mac-cursors`、`@remotion/motion-blur`（均 4.0.520，`npm ci` 装，lock 已更新）。
- 镜头 `anchor` 指向事件时，`qa.py` 核对切点 ≤ 2 帧。`transitionIn` 支持 `cut / fade / custom`。
- `captions.style: "karaoke"` 时字幕附带逐字帧号，由 `src/Captions.tsx` 逐字点亮；`block` 保留原时间分组，布局按新版统一计算。
- 宿主 TTS：`tts.py plan`（按段落类型的情绪 + instruction + expectedSeconds）→ `tts.py import [--tempo ≤1.3]`（剪气口、打印 pace ✓/⚠）。
- 封面：`cover_copy.py check`（文案规则）→ `cover.py plan --reference auto`（真实素材锁主体，pad/crop 到比例，含无字版）→ `generate`/`ingest` → `sheet` → `select`。
- 检查：`render.py` 渲后量静止段（preview/final 在 enforce 下拒绝）；`qa.py` 增 placement（16:9 挤左 / 竖版太矮）。
- 音乐：`music.py plan`（调性 → N 条提示词，纯函数在 `music_tone.py`）→ `rank`（候选打分）→ `ingest/analyze` → `fit` 写 `film.audio` 与 `bgm.hit_N` 事件 → `grid` 写 `bgm.bar_N` 小节事件；Duck 包络在 `Film.tsx`。`render.py --dry-voice` 出无音乐床的干声版（`--props {"noMusic":true}`）。

## 镜头组件与效果库

4.0.5 新部件：`kit/fx.tsx`（`LightLeak`、`Starburst`、`Trail`，impact 专用）、`kit/notation.tsx`（`Note` 手绘批注）、`kit/cursor.tsx`（`MacCursorTrail`）；语义与限幅见 [effects.md](effects.md)，目录进化见 `docs/effects-radar.md`。

在 `film.components` 把组件名映射到 `src/shots/` 内文件。镜头收到 `layout`、`format`、`events`、`style`、`cue()`、`asset()`。`src/kit/` 提供主题化的效果库（见 `src/kit/README.md` 与 [effects.md](effects.md)）；`film.style.palette / fontRoles / preset` 驱动 `useTheme()`。字体文件登记为 `globalAssets` 并在 `film.style.fonts` 声明。

```tsx
import {useCurrentFrame} from 'remotion';
import type {ShotProps} from '../types';
import {ShotClock, hitClock, Backdrop, Slam, Flash, useShake, stage} from '../kit';
export default function Hook({format, cue}: ShotProps) {
  const real = useCurrentFrame(); const {f, c, back} = hitClock(real, cue, [['slam', 4]], 3); const s = stage(format);
  return <ShotClock frame={f}><div style={{transform: useShake([back(c('slam'))], 10, 6, real)}}>
    <Backdrop /><div style={{position: 'absolute', left: s.gutter, top: s.top}}><Slam text="深夜王炸" at={c('slam')} size={150} /></div>
    <Flash at={[back(c('slam'))]} frame={real} /></div></ShotClock>;
}
```

## 阶段渲染与检查

```bash
python3 <skill>/scripts/project.py compile <project> && python3 <skill>/scripts/validate.py <project> && (cd <project> && npm run check)
python3 <skill>/scripts/render.py <project> --stage opening                       # 主画幅前 N 秒
python3 <skill>/scripts/qa.py <project> --input out/opening-3x4.mp4 --sheet
python3 <skill>/scripts/review.py approve <project> opening --evidence '实际确认原话'
python3 <skill>/scripts/render.py <project> --stage preview --format all        # scope=full
python3 <skill>/scripts/render.py <project> --stage final --format all
bash <skill>/scripts/master_audio.sh out/final-3x4.mp4 out/final-3x4-master.mp4 -14
python3 <skill>/scripts/cover.py <project> plan --title '…' && python3 <skill>/scripts/cover.py <project> generate --ratio 3x4
```

默认预览 0.5 倍、最终 1 倍；旧渲染归档到 `out/versions`。技术草稿带标记且可无配音；正式阶段要求真实音频与相应确认。共享实现调整使开头指纹变化时，重渲 opening 后 `review.py carry-opening`。

## 参考依据

[Remotion Sequence](https://www.remotion.dev/docs/sequence) · [Remotion Caption](https://www.remotion.dev/docs/captions/caption) · [whisper.cpp](https://github.com/ggml-org/whisper.cpp)。Remotion 固定 4.0.520；升级时运行类型检查、时间轴测试与实际三画幅渲染。
