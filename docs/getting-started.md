# 安装与配置

技能内部名称：`article-to-vertical-video`；当前共创发布版：`5.0.1`。

## 本地路径

下载 Release 的 `article-to-vertical-video.zip`，解压后进入 `article-to-vertical-video` 文件夹。先运行 `python3 scripts/doctor.py` 查看缺项。

| 宿主 | 用户级目录 |
|---|---|
| Claude Code | `~/.claude/skills/article-to-vertical-video` |
| Cursor | `~/.cursor/skills/article-to-vertical-video` |
| Codex | `~/.agents/skills/article-to-vertical-video` |

选择实际使用的宿主运行 `python3 scripts/install.py --hosts codex`。项目级复制使用 `python3 scripts/install.py --hosts codex --project /你的项目路径 --copy`。现有目录不会被覆盖；先处理同名旧版，再在新任务明确启用版本。

## 能力配置

Agent 的模型在你使用的宿主里选择。媒体能力优先采用宿主已有工具；本地适配器支持 Fish TTS、可选 Seed TTS 及已登录的 Grok CLI。凭据仅保存在本地环境或系统钥匙串中，不写入提交和视频附件。

启动后先让 Agent 按 [宿主适配](../references/hosts.md) 探测真实能力。看到工具名称不代表已经生成成功；只启用你已有权限的服务。无需为了试 Skill 同时配置所有提供者。

## 开始一条作品

```text
使用 $article-to-vertical-video 5.0.1。
把这些文章、链接和视频素材做成一条面向 AI 爱好者的短视频。
重点讲清最值得看的三个发现，主版 3:4，同时输出 9:16 和 16:9。
请先核对信息与素材，再给我脚本和开头样片。
```

确认完整脚本和带声开头样片后，再继续全片。素材不足时，Agent 应先尝试查找或获取，并说明实际缺口。遇到权限、网络或生成额度问题，保留当前工程和错误信息，不伪造结果。

## 秒悟

访问 https://meoo.com/，从首页点击技能并搜索“爆款短视频”。平台条目与 GitHub 包版本独立；如需精确运行本版，下载 Release ZIP 后导入，并在新任务写明内部技能名和版本。详细步骤见 https://docs.meoo.com/file 。

原工程与先前作品保留，使用独立工作目录进行新制作。
