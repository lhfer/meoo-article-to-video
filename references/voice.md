# 声音：声线、情绪标签、读法

## 声线预设（`brief.tts`）

| 用途 | provider | 声线 | 起始参数 | 说明 |
|---|---|---|---|---|
| 爆款默认 | `fish` `s2.1-pro-free` | 曼波 `0f08cacd3e354471a4b94dd00b4cc4a3`；备选 赛马娘·曼波欧耶版 `561fcedfdf0e4e1399d1bc4930d50c0e` | speed 1.5（≈ 7.9 字/秒） | 兴奋、带梗；已确认成片用 1.30–1.45 |
| 宣发默认 | `fish` `s2.1-pro-free` | 真人男播客 `8fe87e31932f49a896ae27eb334d5274`（沉稳自信、清晰讲解技术）；备选：沉稳男声 `d6a375a1dbe1477790a4e750a7bd4d21`、清晰男声 `e0b6ab41a54840e993f97fd08d382093`、小米宣传片-温柔女声 `a97f5ab216614899ac3bc72e3dcc0257`；换声线用 `GET https://api.fish.audio/model?title=…&language=zh&sort_by=task_count` 搜 | speed 1.2（实测 1.3 → 8.2 字/秒，1.2 ≈ 7.5） | 像跟同行讲自己做的东西；首条片在开头确认点由用户定 |
| 可选 | `seed2` | `zh_male_qingshuangnanda_uranus_bigtts` | rate 45 | 需要 `SEED_AUDIO_KEY`；无原生时间戳，走 whisper |
| 宿主内置 | `host`（qwen-audio-3.0-tts-plus / flash 等） | 平台声线 | `instruction` 自然语言 + 文本内联 `[excited]` 类标签 + 语速参数（名称各工具不同） | `tts.py plan` → 宿主工具 → `tts.py import` → 看 cps 判定，慢了必须重生成 |

Fish 免费模型只用 `s2.1-pro-free`；`s3-preview` 一次 200 即扣费，不要放进 fallbackModels。

## 情绪标签

- Fish S2 系列：**方括号** `[excited]`，圆括号会被念出来。每段开头一个主情绪，句内 ≤ 3 个标签；`[break]` 短停、`[long-break]` 长停；`[sighing]` 一片 ≤ 2 次。
- 标签写在 `beats[].voice.emotion`，默认值在 `brief.tts.emotion.default`；`tts.py` 只把标签给 provider，字幕与对齐用去标签文本。
- Seed：没有行内标签，表演指令进 `params.style`。
- qwen-audio-3.0-tts（宿主，已核对阿里云文档）：`instruction` 字段写自然语言表演指令；文本内联标签只用文档确认过的 `[excited] [amazed] [sad] [angry] [whispers] [laughing] [sighing] [gasp] [crying]`（`tts.py plan` 自动映射，`calm / confident / sincere` 这类不在表里的情绪只进 instruction）；语速有参数但名称按工具的 schema（常见 rate / speech_rate / speed），**默认语速实测只有 4.0 字/秒**，所以 plan 把"每秒约 N 个汉字"写成硬性要求；产物无字级时间戳时用 `align.py transcribe`（whisper）或宿主 ASR 带时码导入。

表演按段落类型走，不是整片一个标签（整片 `[calm]` 就是两条实测成片听起来平的原因）。`tts.py` 对所有 provider 都按下表填 `beats[].voice.emotion` 的缺省值（`brief.tts.emotion.byKind` 可覆盖，显式写的优先）：

| kind | 爆款 | 宣发 |
|---|---|---|
| hook | excited | confident |
| setup | excited | calm |
| chapter | confident | confident |
| evidence | confident | calm |
| turn | amazed | amazed |
| summary | confident | sincere |
| cta | excited | warm |
| ending | soft | calm |

instruction 模板（`tts.py plan` 生成，`beats[].voice.style` 追加）：
- 爆款：`像跟朋友爆料的科技博主：兴奋、带梗，重音砸在数字和转折词上，句尾不拖；这一段是<段落类型>，语气<情绪>；语速快：按每秒约 8 个汉字朗读，这是硬性要求…`
- 宣发：`像跟同行讲自己做的东西：克制、准确、自信，不喊口号；这一段是<段落类型>，语气<情绪>；语速快：按每秒约 7 个汉字朗读…`

## 读法与显示分开

- 显示文案 `narration` 是用户确认的；朗读文本由 `overrides:[["GPT-6","GPT 六"],["100万美元","一百万美元"]]` 派生，`spoken` 只能是它的缓存。
- 数字、日期、英文缩写、专名都写读法；字幕仍显示原文，时间戳由 `align.py import --from-timing` 映射回显示文案。
- 第一段配音出来先 `tts.py measure`：偏离目标 > 10% 就 `tts.py calibrate`（本机 provider）或改 instruction / 语速参数重生成（宿主工具），不要凭先验改参数。`tts.py import` 会直接打印 ✓ / ⚠；⚠ 不能接受。`--tempo ≤ 1.3` 是最后手段：实测 1.25× 时 whisper 匹配 0.95，1.4× 掉到 0.92，而且 4 字/秒的底子加速 1.5× 也只有 6 字/秒。

## 检查

- `alignment.json` 里 `transcriptMatches` 必须为 true；`mappingError` 出现时修 overrides 或时间戳。
- 听：重音是否砸在数字和转折词、句尾是否拖、气口是否已压。曼波类声线 whisper 误识率高，ASR 只当提示。
- 换声线或改参数会改变音频指纹 → 重对齐、重新确认开头，这是正确行为。
