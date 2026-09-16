# 效果目录雷达（维护者流程，不进制作流程）

效果目录（`src/kit/`）冻结在最初七条成片做过的东西，会同质化；但每条片去查 Remotion 更新既慢又无关（补丁版两天一个，内容是渲染 / Studio / Lambda）。所以：**按 Remotion 小版本或每月**跑一次雷达，把值得要的效果按"语义 → 强度 → 硬限"收进目录；制作流程只读 `references/effects.md`。

## 怎么跑

1. `python3 scripts/effects_radar.py`：列出下表没评估过的 `@remotion/*` 包和 pinned / npm 最新版本（离线也能跑，只是不联网部分空着）。
2. 每个新包读官方文档：任意 remotion.dev 文档 URL 后加 `.md` 即得 Markdown 源（本机有 Remotion 文档插件时也可搜索）。
3. 判定四件事：它表达哪种语义（对上 effects.md 的行）、两个 profile 各用不用、强度与硬限（部件内限幅 + `qa.py` 复核）、渲染要求（WebGL2 需要 `--gl=angle`，`render.py` 自动加）。
4. 采纳：写成 `src/kit/` 部件（六条硬规则见 `kit/README.md`）、加进 effects.md 表、种子镜头用一次并三画幅看帧、`qa.py` 复核；不采纳也要记一行原因。
5. 升级 Remotion 版本本身另算：所有 `@remotion/*` 必须同版本，改 `assets/director/package.json` 后 `npm install` 更新 lock，跑 `npm run check` 与全部测试。

## 确定性实测（2026-09-11，写部件前必读）

| 配置 | 相同输入多次渲染 | 结论 |
|---|---|---|
| 默认后端，无 WebGL 部件 | 4 次 × 300 帧逐字节一致 | 基线 |
| `--gl=angle`，无 WebGL 部件（4.0.4 种子） | 2 / 300 帧相差 ±1–2 级（渐变抖色） | GPU 后端本身有抖动 |
| `--gl=angle`，WebGL 画布 + `mix-blend-mode: screen` | 12–18 / 150 帧不同，最大像素差 14–47 | 禁用 |
| `--gl=angle`，WebGL 画布包在 blend / isolation 分组里 | 同上量级 | 禁用 |
| `--gl=angle`，正常混合 + CSS 遮罩（现行写法） | 5 次 × 31 帧 0 差异；全片 4 次 × 300 帧仅 ±1 级抖色 | 采用 |
| `--gl=swangle`，现行写法 | 同样 ±1 级抖动，且慢 6 倍 | 只给无 GPU 机器 |

| `--gl=angle` + JPEG 中间帧（Remotion 默认）→ H.264 | 解码差 26–38（文字边缘把 ±1 放大） | 禁用：GPU 后端一律 PNG 中间帧 |
| `--gl=angle` + PNG 中间帧 → H.264 | 解码差 0–3，渲染慢 20% | 采用 |

结论写进了 `render.py`（GPU 后端自动 `--image-format=png`）与 `review.py carry-opening`（GPU 后端下允许 ±4 级抖动，音频、尺寸、帧数必须一致），其余仍逐字节。

## 2026-09-11 评估（Remotion pinned 4.0.520，npm 最新 4.0.523）

### 采纳

| 包 | 部件 | 语义 | profile | 限幅 / 备注 |
|---|---|---|---|---|
| `@remotion/effects` | `LightLeak`、`Starburst`（`kit/fx.tsx`，透明 `<Solid>` 上跑 `lightLeak()` / `starburst()`，正常混合 + CSS 遮罩） | 转折与卡片交换处的漏光；数字 / 印章后的放射 | impact | 漏光 ≤ 0.45 / ≤ 24 帧 / 单侧遮罩 / 一片 ≤ 3；放射 ≤ 0.35 / 径向遮罩 / 一片 ≤ 4；WebGL2（`--gl=angle`）；`vignette()` 也能在链内做衰减（实测同样确定），暂用 CSS 遮罩。其余 70 个效果（hue / glow / halftone / pixelate / scanlines / zoom-blur…）只作用于 canvas 组件，等 `HtmlInCanvas` 可用再评估 |
| `@remotion/rough-notation` | `Note`（`kit/notation.tsx`） | 划重点：圈、下划线、记号笔、框、括号、划掉 | 两个 | 只包裹已定型文字；impact 粗糙双笔，product 细单笔；同屏一次一个 |
| `@remotion/mac-cursors` | `MacCursorTrail`（`kit/cursor.tsx`） | 录屏证据、prompt → 结果里的真光标 | 两个（product 默认） | 与 `CursorTrail` 同 path API，点击变手型 |
| `@remotion/motion-blur` | `Trail`（`kit/fx.tsx`） | 砸字 / 卡片甩入的拖影 | impact | ≤ 6 层；层内自动换算 ShotClock 滞后；product 直通 |

### 评估未采纳

| 包 | 原因 |
|---|---|
| `@remotion/transitions` | 硬切是房规；`TransitionSeries` 要改镜头模型与 `Film.tsx`（所有开头指纹失效）；漏光已覆盖"盖住切点"的需求 |
| `@remotion/light-leaks` | 官方已标记废弃，改用 `@remotion/effects` 的 `lightLeak()` |
| `@remotion/starburst` | 同上，改用 `starburst()` |
| `@remotion/animated-emoji` | 渲染时从 Google 拉素材，联网依赖；表情反应也不是两套视觉语言 |
| `@remotion/lottie` | 外部动画资产流程，选题需要时按素材流程引入 |
| `@remotion/rive` | 同上 |
| `@remotion/three` | 3D 不在两套视觉语言里 |
| `@remotion/skia` | 同上；且需额外原生依赖 |
| `@remotion/gsap` | 时间轴适配器，无画面收益；kit 已是帧驱动 |
| `@remotion/canvas` | 编辑器 / 交互界面原语，不是效果 |
| `@remotion/gif` | 素材类；需要时用 `Clip` / 素材流程 |
| `@remotion/shapes` | kit 自绘 SVG 已覆盖（`Sparks`、`Connector`、`CutLine`） |
| `@remotion/paths` | 同上 |
| `@remotion/noise` | `Backdrop` 已有纹理；等有具体语义再评估 |
| `@remotion/maptiler` | 选题需要地图时再评估 |
| `<HtmlInCanvas>`（remotion 核心） | 需 Chrome 149 + `chrome://flags/#canvas-draw-element`，渲染器不稳定；开放后可让 glow / chromatic-aberration / zoom-blur 作用于任意 HTML（砸字、卡片），值得下次再看 |
| `shine()`（`@remotion/effects`） | 透明画布上无内容可扫，实测结论卡上无任何变化；需 `HtmlInCanvas` |

### 下一轮候选（雷达会继续列出，直到评估并挪到上面两张表）

| 包 | 为什么值得看 |
|---|---|
| `@remotion/sfx` | 官方音效库（峰值归一化到 −3 dB，无需署名）：砸字 / 印章 / 计数落定的命中音；需要设计怎么进 `film.audio` 与 duck |
| `@remotion/rounded-text-box` | TikTok 式多行字幕底框路径：卡拉OK字幕底框候选（`Captions.tsx`） |
| `@remotion/layout-utils` | `measureText()` / 文字适配：字幕宽度与 16:9 两栏字号的自动计算（现在按加权字数） |
| `@remotion/svg-3d-engine` | 3D SVG 挤出效果：爆款标题的候选，需先看文档与渲染成本 |
| `@remotion/animation-utils` | CSS 属性动画助手：kit 已有 ramp / spring，看是否有可替换的部分 |

### 基础设施（不评估）

| 包 | 说明 |
|---|---|
| `@remotion/cli` | 已在用 |
| `@remotion/bundler` | 渲染基础 |
| `@remotion/renderer` | 渲染基础 |
| `@remotion/studio` | 预览 |
| `@remotion/studio-server` | 预览 |
| `@remotion/studio-codemods` | 预览 |
| `@remotion/studio-protocol` | 预览 |
| `@remotion/timeline-utils` | 内部 |
| `@remotion/player` | 网页播放器，与成片无关 |
| `@remotion/lambda` | 云渲染 |
| `@remotion/cloudrun` | 云渲染 |
| `@remotion/vercel` | 云渲染 |
| `@remotion/compositor-darwin-arm64` | 平台二进制 |
| `@remotion/compositor-darwin-x64` | 平台二进制 |
| `@remotion/compositor-linux-x64-gnu` | 平台二进制 |
| `@remotion/compositor-linux-x64-musl` | 平台二进制 |
| `@remotion/compositor-linux-arm64-gnu` | 平台二进制 |
| `@remotion/compositor-linux-arm64-musl` | 平台二进制 |
| `@remotion/eslint-config` | 工具链 |
| `@remotion/eslint-config-flat` | 工具链 |
| `@remotion/eslint-plugin` | 工具链 |
| `@remotion/tailwind` | 工具链 |
| `@remotion/tailwind-v4` | 工具链 |
| `@remotion/babel-loader` | 工具链 |
| `@remotion/enable-scss` | 工具链 |
| `@remotion/zod-types` | 类型 |
| `@remotion/zod-types-v3` | 类型 |
| `@remotion/licensing` | 授权 |
| `@remotion/media-parser` | 解析库 |
| `@remotion/drag-and-drop` | Studio 交互 |
| `@remotion/google-fonts` | 字体（本包用 `@remotion/fonts` 装本地字体） |
| `@remotion/fonts` | 已在用 |
| `@remotion/media` | 已在用 |
| `@remotion/media-utils` | 已在用 |
| `@remotion/captions` | 已在用 |
| `@remotion/preload` | 预加载，与渲染无关 |
| `@remotion/canvas-capture` | HtmlInCanvas 录制，随 HtmlInCanvas 一起等 |
| `@remotion/compositor-win32-x64-msvc` | 平台二进制 |
| `@remotion/core` | 1.0.0 预发布占位包 |
| `@remotion/design` | Studio 设计系统 |
| `@remotion/elevenlabs` | 第三方 TTS 输出适配；本包 TTS 在 python 侧（Fish / 宿主工具） |
| `@remotion/install-whisper-cpp` | 转写安装助手；本包用 python 侧 whisper.cpp 路径 |
| `@remotion/openai-whisper` | 转写输出适配；同上 |
| `@remotion/whisper-web` | 浏览器内转写；同上 |
| `@remotion/whisper-webgpu` | 浏览器内转写；同上 |
| `@remotion/lambda-client` | 云渲染 |
| `@remotion/serverless` | 云渲染 |
| `@remotion/serverless-client` | 云渲染 |
| `@remotion/streaming` | 内部 |
| `@remotion/studio-shared` | 内部 |
| `@remotion/mcp` | Remotion 的 MCP 服务器（查文档用，维护者可装；不进制作流程） |
| `@remotion/p5` | 3.0 时代实验包 |
| `@remotion/player-a11y` | 网页播放器 |
| `@remotion/promo-pages` | 内部 |
| `@remotion/video` | 4.0.350 的实验标签；本包已用 `@remotion/media` |
| `@remotion/web-renderer` | 浏览器内渲染 |
| `@remotion/webcodecs` | 浏览器内转码 |
