# 有边界的自由构图 + 实际验收

## 不把创作变成同一种模板

`EvidenceScene.tsx` 只是可以跑的安全参考，不是每条片都用的版式。可以做全屏实拍、电影式视觉隐喻、产品操作、左右对照、局部放大、跟随光标；保留 SafeText/SafeBox 与统一版心。不要为了“每秒动一次”添加无意义抖动，也不为填满画面堆卡片。真实演示需要阅读时可声明有理由的 `shot.hold`。

默认模板带 `props.template=true`，正式渲染拒绝模板占位。替换为真实文案、素材和专属镜头后，再明确移除此标记；不能只改标记不改内容。

## 同一个几何来源

`layout-engine.mjs` 计算 safe/title/content/subject/side/caption。`useFrameLayout(format)` 读取 `film.style.layout[format]`，字幕与镜头用同一参数。默认是保守的工作室安全边距，不是小红书/抖音 UI 永久标准；在目标平台的真实预览上复核。修改边距必须重新验收各画幅。

```tsx
const l = useFrameLayout(format);
<SafeText id="title" format={format} r={l.title} role="title" text="只讲一个重点" maxLines={2}/>
<SafeBox id="demo" r={l.subject} role="media">{/* 真实媒体；默认 contain，别裁掉关键 UI */}</SafeBox>
```

16:9 的默认 subject 占两栏可分配宽度的 62%，不是把竖版推到左边。9:16 与3:4按自身高度重新分配；不能把横版整张等比缩小。字幕预留两行并与主体间隔，标题默认两行；不再独立设置 captions.bottom。

| 画幅 | 标题最小字号 | 正文 | 字幕 | 非关键出处小字 |
|---|---:|---:|---:|---:|
| 3:4 | 64 | 40 | 48 | 24 |
| 9:16 | 72 | 44 | 52 | 26 |
| 16:9 | 60 | 34 | 44 | 24 |

这些是工作室规则，不是普适可读性保证。关键结论不能伪装成小字 `note` 绕过要求。SafeText 在字体加载后测量实际 DOM，在最小/最大字号范围内适配；最小字号仍放不下时直接失败，要求删改句子、分镜或换构图。禁止用 overflow:hidden、scale 整体缩小或省略号丢失用户原文来“修复”。

锁定字体：`fonts.py <project> auto` 在当前 Chromium 中测试实际字体并设置三个字体角色；或者登记有权使用的字体资产。未确认字体时不做正式样片。代码字形需要实际看图确认，度量不是完整字体覆盖检查。

## 动画也受约束

文字/标注在起始、运动最大值、停留和退场都要检查。SafeText 的测量保留完整文字尺寸；入场缩放需在设计阶段留出余量，不能依赖最后一帧看起来刚好合适。别把逻辑留在 CSS animation/transition，动画以 Remotion 帧号驱动。

`LayoutGuard` 实际挂在 Film 中：每个渲染帧字体就绪后，检查已标记块的边界、碰撞、字号和溢出，并检查旧组件文字是否进入字幕带/越出画面。默认 strict，发现问题使渲染失败。新镜头至少有一个 SafeBox/SafeText 或等价的 data-qa-block；未标记镜头被拒绝。

有意义的重叠（如画面内部注释）可通过 `overlapReason` 写具体原因；父容器与自身子元素不会互相误判，镜头交叉淡化允许跨镜头重叠。**不要给所有元素统一加 ignore/overlapReason 来关闭验收。**位图/视频里的按钮、文字、相机镜头、WebGL像素，以及语义错误不在 DOM 检查覆盖范围，必须真实视觉复核。

## 三层验收，不互相替代

1. `validate.py`：来源、音频、时间轴、必需素材、真实演示与模板占位。
2. 渲染中的 `LayoutGuard` + `qa.py`：几何检查、静止/闪烁/切点等机器检查。`qa.py` 有硬错误默认非零退出；`--advisory` 仅用于诊断，报告仍是 failed，交付门禁不接受。纯白产品背景不直接当“闪白”；亮度均值、摆放、字内切点等保留为视觉审查提示。
3. `visual_review.py extract`：每镜开头/入场/中间/结尾、事件附近、字幕切换处导出原分辨率关键帧；用真实看图工具逐张查看，并完整播放/听音频。填写生成的 reviewed=false 模板，然后 record；记录绑定成片哈希。关键帧是采样，不代替完整播放；脚本只记录实际审阅声明，不会自己看图听音。

```sh
python3 "<skill>/scripts/qa.py" "<project>" --input out/final-3x4.mp4 --format 3x4 --sheet
python3 "<skill>/scripts/visual_review.py" "<project>" extract --input out/final-3x4.mp4 --format 3x4
# 用宿主工具查看文件、完整播放，填 work/review-3x4.json，不能自动填勾
python3 "<skill>/scripts/visual_review.py" "<project>" record --input out/final-3x4.mp4 --format 3x4 --review work/review-3x4.json
```

所有请求画幅分别执行。修复最多连续做3轮有根据的调整，每轮重渲受影响范围并复检；仍失败保留错误帧与原因，交待检草稿，不伪造通过。代码修复不应把用户已确认的台词、事实或审美方向悄悄改掉。

## 只交付检查过的那个文件

`delivery.py <project> check` 核对正式渲染记录、工程指纹、像素尺寸、当前文件的机器 QA、实际视听记录、素材与原有用户确认。检查结果在 out/delivery.json。

后期响度处理会改变文件哈希。若用 master_audio.sh，输出新文件后先 `delivery.py <project> adopt-master --source out/final-3x4.mp4 --target out/mastered-final-3x4.mp4`：仅画面解码完全相同才能继承几何检查；然后对新的目标重跑 qa/视听，再 `delivery.py check --file 3x4=out/mastered-final-3x4.mp4`（其他画幅同样映射）。干声版也必须单独核对音轨，不能沿用另一个视频的哈希记录。


## 不是固定成 PPT：全屏电影感背景

全屏实景、人物或氛围视频可用 `SafeBox` 的 `role="background"`，矩形设为整个画幅，并写清 `overlapReason`（至少12字符），说明为何有意让文字覆盖背景。未声明的全屏背景会被拒绝。标题、字幕以及承担信息/证据的 UI 文本仍要在各自区域内；画面里不能读的小字应做局部真实放大，而不是解释成“背景”。这允许全屏叙事，不要求每个镜头都是两张卡片。

`SafeText` 会同时测量自然行高与真实滚动溢出，避免中文两行字形伸出行框；本版给标题和字幕留了额外字形余量。字幕底条跟随文字，不填满整个保护带。

## 真正执行了守卫，才有通过回执

`core/render-checked.mjs` 使用官方 `bundle()`、`selectComposition()` 与 `renderMedia()`，两次传入相同 inputProps。每次渲染有独立 token；LayoutGuard 实际检查某帧成功后才发回该帧的回执；缺少任何要求帧就报错。`render.py` 把检查覆盖写入 `.layout.json` / `.render.json`，绑定视频 hash。它不是防恶意篡改的签名系统，但能防常见的漏挂守卫/遗漏帧后误报成功。

最终指纹覆盖引用的媒体、旁白/音乐、来源文件以及代码，而不只覆盖 JSON。大文件采用流式 hash。机器检查、实际视听记录都必须对应最后交付的那个文件。

官方 API 参考：https://www.remotion.dev/docs/renderer/render-media · https://www.remotion.dev/docs/renderer/select-composition · https://www.remotion.dev/docs/bundler 。本次完整 Remotion 依赖/集成验证状态见 VERIFICATION.md。
