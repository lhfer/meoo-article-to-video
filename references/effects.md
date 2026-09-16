# 效果目录：语义 → 效果 → 强度 → 硬限

动效只为"让这句话被看见"。先说清楚观众此刻新增什么理解、哪个主体发生什么可见变化，再选下表的效果。组件都在 `src/kit/`（见 `kit/README.md`），颜色字体只从 `useTheme()` 取。两套预设：**impact**（爆款）与 **product**（宣发，`film.style.preset: "product"`，Flash/Shake/Sparks/LightLeak/Starburst/Trail 自动失效，Slam 退化为柔和上浮）。4.0.5 起目录多了五个部件（`kit/fx.tsx`、`kit/notation.tsx`、`kit/cursor.tsx`）：`Trail` 拖影、`Starburst` 放射、`LightLeak` 漏光、`Note` 手绘批注、`MacCursorTrail` 真 macOS 光标。目录是词汇不是句子：每条片至少一个不来自目录的专属镜头（见用法要点）。

## 不闪眼硬限（房规，写在组件里并由 qa.py 复核）

- 白闪 `Flash` ≤ 4 帧、峰值不透明 ≤ 0.6；比大字**晚 1 帧**；任意 1 s 内 ≤ 2 次、任意 8 s 内 ≤ 1 次。
- 整屏震 `useShake` 幅度 ≤ 12 px、≤ 7 帧、二次方衰减。RGB 分离 ≤ 14 px、7 帧内衰减，不常驻。
- hit-stop 顿 3–6 帧，一片 ≤ 4 处，只给钩子词；用 `hitClock()`，白闪与震屏传真实帧。
- 无黑场（任意帧 YAVG ≥ 8，设计中的骤黑 ≤ 0.2 s）、过曝帧（YAVG > 235）≤ 3。
- 一个 beat ≤ 1 次 slam；同屏同时运动 ≤ 3 组；亮度跳变 > 60 的 1 s 内 ≤ 2 次。
- 每片预算（brief.effects.budget）：slam 6、白闪 6、hit-stop 4、印章 5。
- 4.0.5 部件（限幅写在部件里）：漏光 `LightLeak` 不透明 ≤ 0.45、≤ 24 帧、只从一侧漏（遮罩），一片 ≤ 3 次、前 3 秒不用；放射 `Starburst` 不透明 ≤ 0.35、径向遮罩内、一个 beat ≤ 1 次、一片 ≤ 4 次；拖影 `Trail` ≤ 6 层；手绘批注 `Note` 同屏同时 ≤ 1 个。实测 3:4 漏光峰值只抬亮遮罩内一侧（底部亮度 14→36，顶部不变），`qa.py` 的白闪 / 亮度跳变规则照常复核渲染结果。两个光效部件都用正常混合：画布上的 `mix-blend-mode` 会让相同输入渲出不同帧（实测），破坏开头确认的继承。

## 语义 → 效果

| 语义类型 | impact（爆款） | product（宣发） | 强度 | 限制 |
|---|---|---|---|---|
| hook / 反常识断言 | `Slam` 砸字（scale 1.2→1、blur 10→0、RGB 分离）+ `Trail` 拖影（5 层 0.7 帧）+ `Flash` + `useShake` + `hitClock` 顿 3–4 帧 | `Slam`（退化为上浮 24 px）+ 背景缓推 1.0→1.04 | 3 / 1 | 3 秒内主体+标题+证据同屏 |
| 主张 / 判断 | `TitleBar` 划入 + `HighlightText` 点亮关键词，或 `Note circle / underline` 手绘圈出关键词 | `TitleBar` 淡入 + 细线从左生长，或 `Note underline` 细单笔 | 2 / 1 | 一屏一条主张；`Note` 只包裹已定型的文字 |
| 数字 | `Counter` 滚 0.6–1.0 s + 落定金色脉冲；结论型数字加 `Stamp`，数字后面 `Starburst` 放射（原点在数字） | `MetricTile` 计数 + 单位小字 + 细条增长；落定后 `Note box` 手绘框住 | 2 / 1 | tabular；数字落定早于该词读完；同一数字只出现一次 |
| 原文 / 引用 | `SocialCard` 从下滑入 + `HighlightText` 逐句点亮；卡外引用句可用 `Note highlight` 记号笔划过 | `QuoteCard` 淡入 + 引号细线 | 2 / 1 | 英文原句逐字来自 `claims.json`；推文/声明**代码绘制**不贴截图 |
| 对比 / 前后 | 两张 `Panel` 横向对撞 + `CutLine` 中缝 | `BeforeAfter` 分屏滑杆 24 帧 easeInOut | 2 / 1 | 两侧同构图同尺寸，只变一个变量 |
| 列举 / 清单 | `ListReveal` 纵向快闪 → 命中行高亮其余压暗 | `StepRail` 逐条打勾，完成项 55% | 2 / 1 | ≤ 7 行；未实名项用占位条 |
| 时间线 / 先后 | `TimelineBar` 刻度依次亮 + 进度条冲刺（落在 `bgm.hit_N`） | `TimelineBar` 匀速 | 2 / 1 | 刻度日期必须有来源 |
| 转折（但是 / 其实） | 画面压暗 + `CutLine` 横切 + `Stamp` 落章 + 轻震 2 帧；或 `LightLeak` 从一侧漏光盖住转折切点 | 背景色温位移 + 文字块交叉淡入 0.5 s | 3 / 1 | 一片 1 个大 turn，落在 35–75% |
| 演示证据（录屏） | `Screen` + `Marker` 框住动作 + `Callout` 从动作点弹出 + `MacCursorTrail` | 同左 + `MacCursorTrail`（真 macOS 光标，点击变手型；旧 `CursorTrail` 仍可用）/ `TapRipple` / `UIZoom` | 1 / 2 | 关键操作放慢或 `Clip hold` 定帧；答案出现前不许切走 |
| prompt → 结果 | `PromptBubble` 甩入 + 被驳回时 `Stamp` 红章 | `PromptBubble` 柔和滑入 + `Terminal` 打字 + `UIZoom` 看结果 | 2 / 2 | 打字 ≥ 25 字/秒 |
| 概念解释 / 隐喻 | 生成素材 `Framed` 圆形遮罩推近（1→1.25，2.5 s） | 同左，幅度减半（`KenBurns`） | 1 / 1 | 生成素材嵌在面板/遮罩里，不裸贴，不冒充演示 |
| 结论卡 / summary | `SummaryCard` 3–5 条逐条弹出 + 整卡轻缩定格；卡片交换处可 `LightLeak` 盖住切点 | 同左，无弹性 | 2 / 1 | 停留 ≥ 2.5 s |
| 划重点 / 手写感 | `Note`（underline / circle / highlight / box / bracket / strike，粗糙双笔、accentBright） | `Note`（细单笔、bowing 0.4、accent） | 2 / 1 | 只包裹已定型的文字（Display、说明行、指标），不包裹变形中的 Slam；同屏一次一个 |
| CTA | 骤黑 ≤ 0.2 s → 超大问句 + 底部 `Tag` | 产品名 + "适合谁" + 链接提示 | 2 / 1 | CTA 前留 0.5 s 登记停顿 |
| 转场 | 硬切为主；同形/同位置接点；片内切点可 `LightLeak`（同一 seed、前后两半分在两镜头里）；`CircleWipe` 全片 ≤ 1 次 | `CircleWipe` / 交叉淡入 0.4 s，顺着光标或元素运动方向 | — | 连续主体跨镜头：接点位置/尺寸/速度实测对齐 |

## 用法要点

- 事件先绑词：`film.events.x = {voice, word, edge}`，镜头里 `cue('x')`；BGM 重击由 `music.py fit` 注入 `bgm.hit_N`。
- 标签从被念到的对象位置弹出（`Chip origin` / `Callout`），前一个缩小让位（`shrink`），视线连续。
- 每个 beat 至少一个"属于它自己"的视觉证据；连续 3 个 beat 同一底图就是偷懒。
- `KitShowcase.tsx` 是可运行的参考镜头；`qa.py --sheet` 出接触表逐帧看。
- **每条片至少一个不来自目录的专属镜头**：为这个选题专门做一个视觉隐喻（千禧年那条用流动的水讲方程），写进 `film.shots[].bespoke: "隐喻说明"`；`validate.py` 对完整片缺它就警告。目录部件是词汇，不是句子；只用词汇的片会越来越像。
- WebGL2 部件（`LightLeak` / `Starburst`）：`render.py` 检测到 `film.shots[]` 排到的镜头用了它们就自动加 `--gl=angle --image-format=png`（Remotion 4 默认后端拿不到 WebGL2；PNG 中间帧让 GPU 抖色不被放大，开头确认才能继承）；无 GPU 的机器在 `brief.render.gl` 写 `"swangle"`；Studio 预览无需设置。`Trail` 里的 kit 部件照常传 `at`，各层的滞后由部件自己换算。
- 效果目录的进化走维护者雷达（`docs/effects-radar.md`、`scripts/effects_radar.py`：按 Remotion 小版本或每月评估一次新包），不在每条片的制作流程里查 Remotion 更新。
