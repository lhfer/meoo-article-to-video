# 宿主工具接入

先读 [Meoo 执行协议](meoo.md)。当前任务可用工具以实际发现/调用为准，不以技能的工具名称为准。

## 已有声音/生成工具接口（保留兼容）

# 一个创作核心，分别适配宿主与媒体提供者

每个宿主可以独立完成整条制作流程。把宿主自带的读取文件、运行命令、预览媒体、询问用户、生成媒体等动作映射到它当前实际提供的工具；脚本接口保持一致。

| 宿主 | 推荐个人目录 | 项目目录 | 使用方式 |
|---|---|---|---|
| Claude Code | `~/.claude/skills/<name>` | `.claude/skills/<name>` | `/<name>` 或匹配的自然语言请求；询问用 AskUserQuestion |
| Cursor | `~/.cursor/skills/<name>` | `.cursor/skills/<name>` | 在技能列表选择，或明确指定技能与素材 |
| Grok Build CLI | `~/.grok/skills/<name>` | `.grok/skills/<name>` | `grok inspect` 查看发现项，再在会话中明确调用；自带 image_gen / image_edit / image_to_video |
| Codex（兼容入口） | `~/.agents/skills/<name>` | `.agents/skills/<name>` | `$<name>`；可使用附带 UI 元数据 |
| Agent 内置工具型平台（百炼 / Qwen 系等） | 平台的技能目录 | 项目内复制 | 见下节：TTS / 音乐 / 生图由平台工具产出，脚本负责接入 |

`<name>` 为包名（`article-to-vertical-video` 或 `vibecoding-launch-video`）。`python3 <skill>/scripts/install.py --hosts claude,cursor,grok` 为本机建立指向同一目录的链接（目录名取自 SKILL.md 的 `name`）；已有安装会保留并提示。`--project <repo> --copy` 复制到项目，适用于云端或跨机器。

## 当前宿主能力适配

- 路径：从本 SKILL.md 的实际位置解析 `<skill>`；所有命令使用绝对路径。
- 用户确认：使用宿主可用的询问工具；没有专用工具时在对话中交付方案卡／完整文案／样片并等待实际回复。继承当前对话已有确认。
- 文件交付：使用宿主原生附件／视频预览或实际绝对路径；远程机器路径仅在远程环境有效。
- 长渲染：优先使用宿主支持的长任务／会话句柄，回收退出码与日志。
- 图片／视频查看：优先实际图像或视频预览；截图／抽帧（`qa.py --sheet`）与音轨试听补充。只有静帧时，把完整运动与听感列为未验证。
- 搜索与抓取：产品调研用宿主的搜索 / 抓取工具；**没有这类工具时不跳过调研也不凭记忆编**，在步骤 0 直接向用户要官网 / 新闻稿 / 评测链接与图片视频文件，来源记 `--kind user`（[research.md](research.md) §5）。
- 生成媒体：所有宿主可运行 `media.py` 调用已登录的 Grok CLI；宿主自带媒体工具时直接生成，再用 `media.py --kind ingest` / `cover.py ingest` / `music.py ingest` 登记。

## Agent 内置工具型平台（qwen-audio-3.0 / fun-music-v1 / 平台生图）

平台把 TTS、音乐、生图作为 Agent 工具提供，没有本机 API key。接入路径固定为 **plan → 宿主工具生成 → import/ingest**，之后与本机 provider 走完全相同的剪辑、指纹、对齐与校验：

| 能力 | 计划 | 宿主工具 | 接入 |
|---|---|---|---|
| 配音 | `tts.py plan <project>` 每段给 text（含文档确认过的 `[excited]` 类标签）、`instruction`（表演 + "每秒约 N 个汉字"硬性要求）、`expectedSeconds` | 平台 TTS 工具生成，保存到 `audioOut`（有时码则存 `timestampsOut`） | `tts.py import --id … --audio …` 自动剪气口并打印 `pace ✓/⚠`；⚠ 必须重生成（更快的 instruction / 语速参数），`--tempo ≤ 1.3` 只是最后手段；无时码 → `align.py transcribe` |
| 音乐 | `music.py plan <project> --id bgm --candidates 3` 按产品卡 / 脚本推导调性，写 N 条提示词（`is_instrumental: true`、`format: wav`；模型不能指定时长，一次一首） | 平台音乐工具按每条提示词各生成一首，保存到各自 `output` | `music.py rank --inputs …` 打分 → 听 → `music.py ingest --id bgm` → `music.py fit` → `music.py grid` |
| 封面 / 素材 | `cover.py plan` 打印各比例提示词；镜头素材提示词按 [media.md](media.md) | 平台生图工具生成 | `cover.py ingest --ratio 3x4 --input <img>`；素材 `media.py --kind ingest --id <id> --input <file>` |
| 询问 / 交付 | — | 平台的提问与附件工具 | 方案卡与两个确认点照常 |

宿主工具的可用性只能由一次真实调用证明；`doctor.py` 对 `host-*` 只报告"由宿主提供"。适配器不假设平台参数名，`brief.tts.provider: "host"` 时 `tts.py` 直接合成会拒绝并指向 plan/import。

## 能力探测与验证范围

`doctor.py` 检查可执行文件、版本与各 provider 凭据是否存在（不打印值），并列出 whisper 模型；凭据存在不等于已授权，宿主工具存在不等于已调用成功。真实生成成功、完整作品质量分别记录。Fish 免费模型只用 `s2.1-pro-free`；用户的订阅授权与 API 计费通道分别使用。

Grok 低层调用沿用 `grok -p --tools ... --output-format streaming-json` 包装器（`grok_media.py`）；接口有版本差异时看本机 `--help`，失败保留任务日志。Cursor 云端应使用项目内文件并在执行机器配置依赖与凭据。

## 真实宿主验收用例

各宿主分别在独立工作目录使用 `evals/evals.json` 的请求：第一轮应先做步骤 0 对齐并返回方案卡（或在"直接做"后直接进入脚本），交付完整脚本并停在真实确认点；批准后制作带声前十秒并停在第二确认点；之后完成三画幅、封面与检查。使用 CLI 读取／发现检查不等于跑过上述完整任务。

## 官方依据（升级时重新核对）

[Claude Code Skills](https://code.claude.com/docs/en/skills) · [Cursor Skills](https://prod.cursor.com/docs/skills) · [Grok Build](https://docs.x.ai/build/overview) · [Fish Audio TTS](https://docs.fish.audio) · [阿里云百炼 Qwen-Audio-TTS](https://help.aliyun.com/zh/model-studio/realtime-tts-user-guide) · [Fun-Music](https://help.aliyun.com/zh/model-studio/fun-music-api)

## 无 GPU 的宿主（4.0.5）

`LightLeak` / `Starburst` 是 WebGL2 效果：本机 `render.py` 自动加 `--gl=angle`；云端或无 GPU 的宿主在 `brief.render.gl` 写 `"swangle"`（软件渲染，慢但能出）；不用这两个部件的工程命令不变。
