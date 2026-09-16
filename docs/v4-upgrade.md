> 历史版本记录，不是当前执行协议。新版以 SKILL.md 和 references/layout-and-qa.md 为准。

# V4：一套源码、两个 skill 包——爆款自媒体版与 vibecoding 宣发版

本次升级根据一周内 7 条真实成片暴露的重复劳动（每条都手写 Fish 配音、静音压缩、读法映射、效果库、音乐对位、QA 脚本）把这些能力收进引擎，并按用户确认的方向拆成两个自包含包：

| 包 | name | 版本 | 面向 | 关键差异 |
|---|---|---|---|---|
| 爆款自媒体版 | `article-to-vertical-video` | 4.0.0 | 科技、AI 资讯类自媒体 | preset impact、Fish 曼波、8.0 字/秒、气口 ≤ 0.8 s、卡拉OK字幕、必须 BGM、砸字/印章/计数器/社交卡 |
| 作品宣发版 | `vibecoding-launch-video` | 1.0.0 | 个人 vibecoding 作品 / App | preset product、真人男播客声线、7.4 字/秒、录屏先行、设备框/UI 放大/前后对比/prompt→结果、无白闪无震屏、诚实边界 |

两个包由 `python3 scripts/package.py --profile viral|launch <zip>` 从同一源码构建；`scripts/` 与 `assets/director` 引擎字节相同，`profiles/launch/files/` 覆盖 SKILL.md、README、`references/profile.md`、brief/visual/film.json、evals 与 agents。ZIP 校验值在 `dist/SHA256SUMS.txt`。

## 这次真正改了什么

| 诉求 | 实现 |
|---|---|
| 1 语速 | 语速是实测的字/秒目标（`brief.pacing.targetCps`），`tts.py calibrate` 按声线扫描参数并写回 brief；`tts.py measure` 与 `validate.py` 报告每段实测值。曼波声线实测：speed 1.35 → 6.8–7.0、1.5 → 7.9、1.65 → 8.2 字/秒；默认 1.5 / 目标 8.0±0.8。 |
| 2 语义动效 | `src/kit/`（core/clock/layout/surface/text/marks/media/cards/product）主题化效果库 + `references/effects.md` "语义 → 效果 → 强度 → 硬限"目录；不闪眼硬限写进组件（白闪 ≤ 4 帧 ≤ 0.6、震幅 ≤ 12 px、RGB 分离 ≤ 14 px）并由 `qa.py` 在成片上复核；`KitShowcase.tsx` / `ProductShowcase.tsx` 两个可运行参考镜头。 |
| 3 气口 | `voice_edit.py`：裁首尾、句内 > 0.30 s 的停顿压到 0.18 s、时间戳重映射、两遍响度；剪辑指纹与合成指纹同时匹配才复用缓存。`project.py plan-voices` 按标点/段类型排段间间隔；`compile.mjs` 量测 `voiceGaps`，`validate.py` 对未登记的超限气口报警；`gapIntent.reason` 登记有意留白。 |
| 4 平台适配 | 目标平台以 Agent 内置工具提供 TTS/音乐/生图：`tts.py plan → 宿主生成 → tts.py import`、`music.py plan → ingest → fit`、`cover.py plan → ingest`；无时间戳时 whisper 或宿主 ASR 导入。`hosts.md` 新增该类平台的映射表；`doctor.py` 报告各 provider 凭据（不打印值）。 |
| 5 其他优化 | 显示文案与朗读文本分离（`overrides`），原生时间戳映射回显示文案；`formats` 可子集；卡拉OK字幕；`music.py` 重击分析与对位；`qa.py` 接触表/亮度/冻帧/切点/ASR；`materials.py` 素材台账；恢复 V2 的播音腔禁词与可度量叙事规则。 |
| 6 前期对齐 | 步骤 0：`references/intake.md` 的 ≤5 问一轮访谈 + 固定格式方案卡（素材盘点 + 四选一：你补 / 我找 / 我生成 / 直接做）；"直接做"跳过。主动素材规划：每个 beat 写"最该被看到的东西"并自行搜索/生成/代码绘制。 |
| 封面 | `cover.py`：按平台比例生成含中文标题的提示词（去 AI 味词表），Grok 或宿主生图模型出候选，`sheet` 出 200px 缩略图行，逐张检查后 `select`。实测 Grok 两张候选中文标题逐字正确、缩略图可辨。 |

## 实际完成的验证（机器可读：verification/results-v4.json（历史附件未随本版分发；当前结果见 [VERIFICATION](../VERIFICATION.md)））

- **42 项自动化测试通过**：12 项时间轴测试（含 formats 子集、voiceGaps、卡拉OK）、30 项 Python 测试（Fish SSE 真实夹具解析、气口裁剪与重映射、读法映射、间隔策略、请求构造、音乐对位、qa 亮度/变化分析、打包 overlay）。
- **真实 Fish 配音链路跑通**：3 段口播合成 → 剪气口 → 自动导入逐字时间戳并映射回显示文案（含 GPT-6 读法）→ 排间隔 → 编译 → 渲染 10 秒带声开头（卡拉OK字幕、砸字、计数器、印章、社交卡）→ `qa.py` 出报告。缓存语义验证：改剪辑参数只重剪不重合成。
- **语速标定**：5 档扫描并出实测表；**宣发声线试听**：4 个 Fish 公开声线各合成一段并测语速（真人男播客 1.3 → 8.2 字/秒，默认取 1.2）。
- **音乐**：本地曲目经 uv+numpy 分析出重击，`fit` 把 `bgm.hit_1` 对位到钩子词事件（Δ0 帧）。
- **封面**：Grok 出 2 张 3:4 候选，中文标题逐字正确。
- **product 预设**：宣发工程 draft 渲染 3:4 与 16:9，设备框/前后对比/prompt 气泡/终端/指标/步骤无重叠。
- **离线三画幅音轨测试** `tests/render_smoke.py` 通过（含开头确认继承）。
- **两个包**：各自解压后 `doctor.py`、`install.py --dry-run`、Python/Node 测试、`tsc` 通过；`scripts/` 字节相同。

## 验证范围（如实标注）

- Seed-TTS 未执行（无 `SEED_AUDIO_KEY`）；qwen-audio-3.0 / fun-music-v1 / 平台生图只验证了 plan → import/ingest 路径（用本机产物模拟），未在真实平台上调用。
- Agent 没有主观听感能力：语速与清晰度的最终判断在开头确认点由用户完成；whisper base 对曼波类声线识别率低，`qa.py --asr` 只作提示。
- 不闪眼限制是舒适度房规，不是光敏安全认证；留存类规则来自已确认成片，尚无新片的真实平台数据。
- 三个 Agent 从真实选题出发、经两个确认点做完整片的行为评测（`evals/`）尚未执行。

## 迁移

- V3 工程不改字段即可在 V4 引擎下编译渲染（版本 3/4 都接受，默认三画幅、block 字幕）。
- `Film.tsx` 抽出字幕组件会改变已有工程的开头文件指纹：按原比例重渲 opening 后 `review.py carry-opening`，解码画面与音频一致才继承确认。
- 打开 `voiceEdit` 会改变音频：需要 `tts.py` 重跑、`align.py review`、重新确认开头，这是正确行为。
- 旧安装用 `install.py` 时目录名改取 SKILL.md 的 `name`；本机四个宿主的软链仍指向 `article-to-vertical-video`。

## 4.0.1 / 1.0.1：产品调研与按调性配乐（2026-09-11 追加）

用户追加的两点：提到产品要先全网调研、新产品要问清楚；配乐要按产品调性（燃 / 动感 / 节奏…）针对性生成，短视频配乐很重要。

- **产品调研**：`references/research.md` + `scripts/product.py`（`content/product.json`，每字段带 `user|web|inferred` 来源；`gaps` 机械判定"新产品 / 未公开"并生成 ≤5 个问题；`card` 输出方案卡里的【产品卡】块，末行是 BGM 调性与依据）。两包 SKILL 步骤 0 与 `intake.md` 都改为"先搜、后问"。
- **调性配乐**：`scripts/music_tone.py`（纯函数）：8 种原型表、推导顺序（brief 显式 → 产品卡 → 脚本 → profile 默认）、BPM 随语速与切换频率微调、按秒的结构（drop / lift / settle / end）、含反向约束的中文提示词、候选打分、小节网格。`music.py plan` 重写（修掉了 `visual.sound` 默认文案被当成提示词的 bug）；新增 `rank`、`grid`；分析器新增 1–4 kHz 占比、首个强重击、速度置信度。
- **平台层**：`render.py --dry-voice` 出干声版（`--props {"noMusic":true}`，文件名 `-dry`，不写 openingDigest），供平台内叠站内热门 BGM；`music.md` 写明站内曲库加成与版权边界。宣发版默认改为轻节奏床 BGM（`music.required true, gain 0.35`），作者明确不要才关。
- **核实**：fun-music-v1 文档（prompt 1–2000 字符、不能指定时长、一次一首）；`--props` 确实到达 Film（干声版无旁白窗口 −91 dB vs 带 BGM −30 dB）；`plan` 在两个 e2e 工程的输出；`rank` 对 4 个 ffmpeg 变体（原曲 / 前置 4 s 静音 / 低通 / 中频增益）的排序符合预期；`grid` 写 7 个小节事件后编译、校验通过。未核实：真实 fun-music-v1 产物的音乐质量、站内 BGM 的分发加成幅度。
- 测试：+10（`tests/test_music.py` Tone ×6、`tests/test_product.py` ×4），共 40 项 python + 12 项 node。`tests/test_workflow.py` 改为与 profile 无关（从 film.json 取开头镜头与画幅），宣发包种子镜头延长到 0–12 s 以覆盖 10 s 开头窗口。
- `validate.py` 新增警告：profile 要求 BGM 而 `film.audio` 为空（只在非 draft 编译时报，`fit` 之后消失）。

## 4.0.2 / 1.0.2：名字确认、素材同步收集、信息稀薄确认、无搜索兜底（2026-09-11 追加）

用户用「帮我制作一套苹果duo发布的产品介绍视频」核对流程后补的四点：

- **第 0 轮身份确认**：`product.py init --query --confidence`；ambiguous / unknown 时 `gaps` 只给一个"你指的是哪一个"问题，答复前不问别的、不推断。
- **信息等级**：来源带 `--kind official|press|review|rumor|community|user`；`evidence_level` = none / rumor / thin / solid（≥2 独立域名 + 1 条官方；自己的产品定位来自作者即 solid；传闻不计独立域名）。thin / rumor 必须复述已找到的事实让用户确认，`product.py confirm` 记录原话；`validate.py` 在正式编译对未确认的非 solid 卡警告。问题最多 3 个，给开场对齐留位置；none 时先要链接。
- **调研同步收集素材**：research.md §1.5 把官方新闻稿 / 产品页的图与直链视频经 `sources.py → download_media.sh → materials.py` 收进工程；平台视频记 url + 时间码 + 权利（`product.py media`），不另装下载器；第三方已发布产品 0 条素材时 `gaps` 给待办。
- **无搜索工具兜底**：hosts.md 与 research.md §5：向用户要链接与文件，来源记 user，不凭记忆编。
- 顺手：调性关键词补"高级 / 精密 / 旗舰 / 质感 / 工艺 / 设计感 → 科技冷感"、"重磅 / 发布 / 新品 → 动感"；**燃只由明确词触发**，能量分再高也只到动感（iPhone Duo 实跑原先推成燃，现在是动感）。
- 核实：真实搜索 iPhone Duo（Apple 官网 / 新闻稿 / 维基 / 中外报道）→ 5 条来源 → solid、0 个问题、1 条素材待办；删到 1 条中文报道 → thin，问题里复述"首款折叠屏 iPhone"并要官方链接；`--confidence ambiguous` → 仅 1 个身份问题。测试净 +5（test_product 重写为 10 项），共 45 项 python。

## 4.0.3 / 1.0.3：节奏、语气、排版、封面（2026-09-11，基于两条实测宿主成片）

用户用平台自带 qwen TTS 出了两条 16:9 成片（59.8 s 与 64.5 s），实测：语速 **4.0 / 4.2 字/秒**（目标 7.4 / 8.0）；段间静音 0.5–1.3 s 共 8 s；画面无可见变化的静止段最长 **4.5 s / 6.0 s**（各 6 段超过 2.5 s）；一条 16:9 的内容挤在左上（placement clustered-left **50/64** 帧）；标注盖住界面文字；空的终端框；字幕在「vibec|oding」「——不是|现金」处断开。整体加速救不回语速：atempo 1.25× whisper 匹配 0.95 只到 5.0 字/秒，1.5× 掉到 0.905 才 6.0。

- **语速回路**：`tts.py plan` 每段给 instruction（表演 + "每秒约 N 个汉字"硬性要求）、只用文档确认的内联标签、`expectedSeconds`；`tts.py import` 打印 `pace ✓/⚠`；新增 `--tempo ≤ 1.3` 最后手段（时间戳自动缩放）。两包 `pacing.enforce: true`，且 `validate.py` 只把语速 / 气口 / 尾部静音升级为错误。
- **语气**：按段落类型的情绪表（`KIND_EMOTION`，`brief.tts.emotion.byKind` 可覆盖），所有 provider 共用；qwen 的 `instruction` 模板见 voice.md。
- **静止段**：`render.py` 渲后在真实像素上量（96×54 灰度、10 fps；相邻帧均差 > 1.5 或自上次变化起累计漂移 > 1.5 记一次可见变化，慢推 / 计数器 / 光标都算，字幕带不计），草稿 / 开头警告，preview / final 在 enforce 下拒绝；`film.shots[].hold: "原因"` 登记观众跟着看的录屏。用户两条成片在这把尺下最长静止 4.5 s / 6.0 s（各 6 段）。两个种子示例镜头本身也按这把尺改到合格：爆款种子换成 impact 参考 `KitShowcase`（0–10 s，提示点 ≤ 1.5 s 一个，计数器 / 印章 / 分步结论卡 / 收尾提问自带后续动作；原 `ContinuousExample` 是浅色低对比的接口演示，改前最长静止 4.6 s，仍保留可用），宣发 `ProductShowcase` 加慢扫对比、分步与证据放大（改前 6.7 s，改后 0）。
- **排版**：`kit/layout.ts` 新增 `columns()`（16:9 两栏，主体 ≥ 55% 宽）与 `MIN_TEXT`；`Terminal` 在 `at` 前隐藏、之后立刻显示提示符；motion.md 新增"横版不是把竖版放到左边"、标注不压界面文字；`qa.py` 新增 placement 检查（实测：用户成片 50/64 帧命中，ProductShowcase 16:9 0 命中）。
- **字幕**：`align.py group_captions` 不在英文单词 / 数字中间断开，撞上限时回退到标点或中英边界（两条成片的 whisper 转写共 58 条字幕 0 处误断）。
- **封面**：`cover.py plan --reference auto`（产品卡 media → 台账 ready → 正片素材，pad/crop 到比例，`image_edit` 锁主体）、平台点击要素、视觉钩子、无字版；新增 `cover_copy.py check`（封面大字 / 发布标题：字数、禁词、画面外承诺、数字出处、公式覆盖）。
- 测试：+17（captions 4、host voice 4、coverage 3、cover 5、product 1、still detector 1），共 62 项 python + 12 项 node；`tests/render_smoke.py` 的合成音夹具显式关闭 `pacing.enforce` 并固定 12 s 片长。

## 4.0.4 / 1.0.4：脚本留存（2026-09-11 追加）

脚本之前只有结构与口吻规则，"吸引人、衔接、用户视角、易懂"停留在一句原则。这轮把它写成方法并量化：

- **文档**：storytelling.md 新增留存曲线（0–3 / 3–8 / 8–15 / 15–30 s / 结尾各要做到什么）、衔接四种桥（反问、先果后因、对照、回接关键词，例句来自已确认成片）、交给用户前的"观众座位自审"八条；两个 profile.md 各加一张"有趣手法"表（✗/✓ 对照）与本 profile 常见划走点；禁止问候 / 自我介绍 / 交代背景式开头与播音式报幕。
- **`script_check.py`**（两包共享，`project.py script` 自动附到 `out/script-review.md`）：估算留存时间轴（3 / 8 / 15 / 30 / 60 s 各在讲什么，按 `targetCps` 与 gapPolicy 估）、划走点、ERROR 只针对开头（第一段是 hook、前 3 秒有数字 / 名字 / 疑问 / 反差词、不以问候开场），WARN 有一口气无标点超过 22 字、单段超过 15 s、缺 viewerGain、没有 turn、结尾既不提问也不回调也不邀请、套话结尾、数字不在 claims.json；提示有术语首次出现无白话、衔接断裂、播音式转场、数字重复、全片没有"你"、25 s 无新事实、viewerGain 像作者视角、缺 hook 候选。
- **校准**：6 条已确认成片脚本（千禧年 ×2、英雄联盟、codex-80、iPhone Duo、elfware）全部 0 ERROR，WARN 各 0–1（一处 23 字人名串、一处 9.6 s 开场段）；用户两条慢节奏成片的转写：衔接提示 10/19 与 20/32 段，其一开头是"这条宣发视频是……"式自述。校准中发现文档里"同一数字只出现一次""结尾必须是争议提问"被已确认成片有意打破（数字回调、承诺式结尾），因此降为提示。
- `script.json` 顶层可选 `hookVariants[]`（2–3 个开场候选）与 `glossary`，都不进确认指纹；评测各加一条脚本留存 case；python 测试 +7。

## 4.0.5 / 1.0.5：效果目录进化与专属镜头（2026-09-11 追加）

用户问：会不会每次任务去查 Remotion 有什么新动效来刺激视觉？答案是不会，也不该：Remotion 补丁版两天一个（4.0.520 → 4.0.523），内容是渲染 / Studio / Lambda；观众看到的是效果目录和每条片的定制镜头。这轮做的是目录进化一次 + 一条规则 + 一个雷达：

- **评估**：npm 上 49 个 `@remotion/*` 包逐个看（记录在 `docs/effects-radar.md`）。采纳 `@remotion/effects`（`lightLeak()` / `starburst()`；官方已把 `@remotion/light-leaks`、`@remotion/starburst` 标记废弃）、`@remotion/rough-notation`（手绘批注）、`@remotion/mac-cursors`（真 macOS 光标）、`@remotion/motion-blur`（`Trail` 拖影）。未采纳：`transitions`（硬切是房规，TransitionSeries 要改镜头模型）、`HtmlInCanvas` 系（需 Chrome 149 + flag，任意 HTML 上跑着色器这轮不做）、`animated-emoji`（渲染时联网）、three / skia / lottie / rive（不在两套视觉语言里）、gsap / canvas（无画面收益）、`shine()`（透明画布上无内容可扫，实测结论卡无变化）。
- **部件**（`src/kit/fx.tsx` / `notation.tsx` / `cursor.tsx`）：`LightLeak`（不透明 ≤ 0.4、≤ 24 帧、单侧遮罩；实测 3:4 峰值底部亮度 14→33、顶部不变，第一版无遮罩时整屏洗白、结论卡标题不可读）、`Starburst`（≤ 0.35、径向遮罩、原点在数字 / 印章）、`Trail`（≤ 6 层，层内自动换算 ShotClock 滞后）、`Note`（underline / circle / highlight / box / bracket / strike；impact 粗糙双笔，product 细单笔）、`MacCursorTrail`（与 `CursorTrail` 同 path API，点击变手型）。product 预设下漏光 / 放射 / 拖影不渲染。两个种子镜头都用上了新部件，三画幅实际看过。
- **渲染**：WebGL2 效果在 Remotion 4 需要 `--gl=angle`（默认后端实测报 "Failed to acquire WebGL2 context"）。`render.py` 只在 `film.shots[].component` 排到的镜头文件（顺着本地 import，kit 不算）用到 `LightLeak` / `Starburst` 时加该标志——宣发种子随包带着 `KitShowcase.tsx` 但没排它，仍走默认命令（或 `brief.render.gl`：`swangle` 给无 GPU 机器，`default` 强制不加）；不用的工程命令逐字节不变。
- **确定性（实测，决定了部件怎么写）**：画布上加 `mix-blend-mode: screen`（或包一层 blend / isolation 分组）后，相同输入的两次渲染有 12–18 / 150 帧不同（最大像素差 14–47）；改为正常混合 + CSS 遮罩后，5 次渲染 310 次帧比较 0 差异。但 GPU 后端本身也有抖动：angle / swangle 下不含任何效果的 4.0.4 种子也有 2 / 300 帧相差 ±1–2 级（渐变抖色），默认后端 4 次 × 300 帧逐字节一致。这 ±1–2 级经 JPEG 中间帧 + H.264 后在文字边缘被放大到 26–38（实测三次），换 PNG 中间帧后解码差 0–3、渲染只慢 20%，因此 `render.py` 走 GPU 后端时同时加 `--image-format=png`，`review.py carry-opening` 在 GPU 后端下允许解码画面 ±4 级差异（音频、帧数、尺寸必须一致），其余情况仍要求逐字节一致；`tests/render_smoke.py` 的 carry 步骤就是靠这两条通过的。swangle 比 angle 慢 6 倍（22 s vs 3.5 s / 300 帧 0.25 倍），只给无 GPU 机器。
- **专属镜头规则**：`film.shots[].bespoke: "隐喻说明"`，`validate.py` 对 scope=full 的非草稿缺它就警告（普通警告，`enforce` 不会因此拒绝）；两包 SKILL 步骤 4、评测、`project.py script` 的视觉方向都带这一条。
- **雷达**：`docs/effects-radar.md` 记录本轮评估表；`scripts/effects_radar.py` 列出文档没评估过的 `@remotion/*` 包与 pinned / npm 最新版本（离线也能跑）；按 Remotion 小版本或每月跑一次，不进 SKILL 流程。
- **验证**：两个种子镜头三画幅重渲，`qa.py` 无 luma 发现、0 静止段，冻帧只剩 0.93 / 7.63 s（4.0.4 基线是 0.93 / 6.23 / 7.63 s；结论卡加了第四条后 6.23 s 那段消失，也顺手关掉了 16:9 里 5.6–7.3 s 一段临界的静止段），最高亮度 142 来自原有白闪；`tests/test_effects.py` +5（GL 判定、bespoke、雷达纯函数、carry 裁决、帧差量测）、node +1（hold / bespoke 透传），共 74 项 python + 13 项 node；`tests/render_smoke.py` 在种子用了 WebGL 部件的情况下走通 carry-opening。
- **迁移**：kit 桶文件变化 → 所有导入 `../kit` 的镜头指纹变化；已确认的开头按原比例重渲后 `review.py carry-opening`，画面与音频一致即继承（不用新部件的工程逐字节一致；用了的允许 ±4 级抖动）。`npm ci` 装四个新包（均 4.0.520，lock 已更新）。
- **未验证**：无 GPU 机器上 `swangle` 的速度；rough-notation 对换行长文本的框选；宣发种子的 `qa.py` 白闪规则本就把浅色纸底整段算作"闪"（与 4.0.4 相同，规则是按深底爆款片定的）；这些效果对留存的影响（无平台数据）；±4 容差分支还没有真实走通过一次：单测覆盖、PNG 中间帧实测差 0–3，但 smoke 工程的开头连渲 4 次（0.25 倍、`--gl=angle`）全部逐字节一致，抖动测量也都在 0.25 倍下做（开头样片默认 0.5 倍）。

## 建议与你可能不了解的点

1. 三个 hook 各渲 10 秒做 A/B，`render.py --stage opening` 已支持。
2. 逐字卡拉OK字幕零成本（`captions.style: "karaoke"`），静音刷片时留存最直接的抓手。
3. 首帧＝封面视觉，0.15 s 溶入正片；前 3 秒不靠声音也成立（60% 观众静音）。
4. `kit/layout.ts` 的 `safeArea(format, platform)` 给出抖音右栏、底部遮挡；出一版带安全区蒙版的预览一眼看出字幕会不会被盖。
5. 每平台封面字数不同（抖音 4–8、B站 6–12、小红书 8–14），同一主体分别生成三比例。
6. 响度 −14 LUFS / TP −1.5（手机可到 −11）；已有成片 −15/−3.6 偏轻。
7. 结尾可循环：末帧呼应首帧，自动重播时像有意为之。
8. 交付 3 标题 + 首评（把争议或试用链接丢出来）+ 话题包，作为交付物一部分。
9. 短版 auto-cut（hook + 3 证据 + turn + CTA，15–30 s）值得作为下一步。
10. 交付报告的结构化字段（profile、hook 类型、turn 位置、语速、封面类型）可回流 content-retro 按角度统计。
11. BGM 重击与硬切同帧是"贵感"的来源，现在进了 `qa.py` 的切点检查。
12. 母版素材一图三用（hook 底 / 封面底 / 结尾回收）省生成次数还带视觉连续。
13. Fish `s3-preview` 一次 200 即扣费，默认只用免费模型；宿主 TTS 无时间戳时 whisper 需听校。
14. 宣发版声线试听文件已交付（真人男播客 / 沉稳男声 / 清晰男声 / 小米宣传片-温柔女声），首条片确认时定。
