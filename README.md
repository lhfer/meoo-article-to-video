<p align="center"><img src="https://raw.githubusercontent.com/lhfer/meoo-article-to-video/main/docs/media/hero.gif" alt="{一起 Vibe} 与秒悟 Meoo 共创 · 自媒体短视频 Skill" width="100%"></p>

# 自媒体短视频 Skill

**由 {一起 Vibe} 与秒悟 Meoo 共创。** 把做视频的经验，变成你能理解、修改和复用的工作流。

面向 **文章、资讯、观点与案例**，从真实素材出发，完成脚本、镜头、配音、剪辑与多画幅交付。你负责方向和关键判断，Skill 把步骤连接起来。

[![下载技能](https://img.shields.io/badge/下载_Skill_ZIP-562AFF?style=for-the-badge&logo=github&logoColor=white)](https://github.com/lhfer/meoo-article-to-video/releases/latest/download/article-to-vertical-video.zip)
[![在秒悟使用](https://img.shields.io/badge/在秒悟使用-C187DD?style=for-the-badge)](https://meoo.com/skills)
[![查看案例](https://img.shields.io/badge/查看真实案例-241344?style=for-the-badge)](#真实案例与方法)

![版本](https://img.shields.io/badge/version-5.0.1-562AFF) [![MIT](https://img.shields.io/badge/code-MIT-8B6DCF)](LICENSE) ![画幅](https://img.shields.io/badge/formats-3%3A4_%7C_9%3A16_%7C_16%3A9-B67BC5)

[静态横幅](https://raw.githubusercontent.com/lhfer/meoo-article-to-video/main/docs/media/hero.png) · [安装与配置](docs/getting-started.md) · [验证范围](docs/release-verification.md) · [另一套技能](https://github.com/lhfer/meoo-vibecoding-video)

## 你给它什么，会得到什么

| 你提供 | 一起完成 | 交付 |
|---|---|---|
| 文章、资讯、观点与案例；现有链接、文件或录屏 | 核对信息、补充素材、找到值得讲的内容 | 素材与来源记录 |
| 受众、重点、发布平台 | 脚本、镜头安排、前三秒的观看理由 | 完整脚本与带声开头样片 |
| 对脚本和样片的反馈 | 配音、音乐、字幕、动效与剪辑 | 按需求输出视频、封面与可修改工程 |

两套技能各自独立：**[内容转短视频](https://github.com/lhfer/meoo-article-to-video)** 适合文章与资讯；**[作品做宣传](https://github.com/lhfer/meoo-vibecoding-video)** 适合 App、网站和游戏。按本次任务选一套即可。

## 两种开始方式

### 在秒悟使用

打开 [meoo.com](https://meoo.com/) → 首页左侧 **技能** → 搜索 **爆款短视频**。

选择 **自媒体爆款视频一键生成**，添加并使用；把素材与目标告诉它。

平台版本号与本仓库版本号分别维护。需要使用本仓库这一版时，可从上方下载独立 ZIP，再按 [秒悟技能说明](https://docs.meoo.com/file) 导入。工具、联网和生成额度以当前任务实际可用能力为准。

### 在自己的 AI 编程工具使用

1. [下载 ZIP](https://github.com/lhfer/meoo-article-to-video/releases/latest/download/article-to-vertical-video.zip) 并解压，保留 `article-to-vertical-video/` 这一层目录。
2. 在技能目录运行环境检查，再选择你使用的宿主安装：

```bash
python3 scripts/doctor.py
python3 scripts/install.py --hosts claude,cursor,codex --dry-run
python3 scripts/install.py --hosts claude,cursor,codex
```

已有安装会保留并提示；`--hosts` 只填写你需要的宿主。项目级安装、模型和媒体配置见 [快速开始](docs/getting-started.md)。

把下面这段交给 Agent：

```text
使用 $article-to-vertical-video 5.0.1。
把这些文章、链接和视频素材做成一条面向 AI 爱好者的短视频。
重点讲清最值得看的三个发现，主版 3:4，同时输出 9:16 和 16:9。
请先核对信息与素材，再给我脚本和开头样片。
```

## 真实案例与方法

<p><img src="https://raw.githubusercontent.com/lhfer/meoo-article-to-video/main/docs/media/case-preview.gif" width="440" alt="GPT-6 38个案例合集的实际成片节选，保留原作者来源标识"></p>

**GPT-6「38 个案例」合集：一堆素材，怎样变成一条讲得清楚的视频。**

| 制作判断 | 案例中的做法 | 你可以带走的方法 |
|---|---|---|
| 素材怎么分组 | 按游戏、三维世界、电脑操作等主题组织 | 先组织观看顺序，再安排镜头 |
| 解说怎么对应画面 | 具体动作对应具体讲解，画面标注演示作者 | 每句话都给观众一个能看到的依据 |
| 开头为什么值得看 | 先展示代表性结果，再交代“38 个案例一次看完” | 让观众尽早知道会得到什么 |

这是 {一起 Vibe} 的历史制作流程复盘，也是共创 Skill 的经验来源。预览展示真实历史成片；本技能将这些内容组织方法整理成可复用流程。 横幅里的流程卡片为说明图，轻专注界面为效果示意。

[案例与素材来源](docs/case-study.md)

## 运行条件与使用边界

- 本地执行需要支持文件和命令工具的 Agent、Node.js 22+、Python 3.10+、FFmpeg/ffprobe，以及可用 Chromium。具体检测以 `doctor.py` 输出为准。
- 模型负责理解与编排；生图、配音、音乐分别需要宿主已有能力或你配置的服务。Skill 的 MIT 开源许可不包含这些服务的调用额度。
- 配音、音乐与画面先形成实际样片，再进入全片；信息是否准确、是否好看和好听需要实际复查。
- 使用自己的字体和素材，并保留来源。Remotion 等依赖沿用各自许可证，参见 [第三方说明](THIRD_PARTY_NOTICES.md)。

## 开发与反馈

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
node --test tests/*.test.mjs
cd assets/director
npm ci
npm run check
```

[变更记录](CHANGELOG.md) · [当前发布验证](docs/release-verification.md) · [问题反馈](https://github.com/lhfer/meoo-article-to-video/issues)

反馈时附技能版本、宿主、预期结果与脱敏后的错误信息。欢迎把具体卡住的步骤告诉我们。

---

**{一起 Vibe} × 秒悟 Meoo** · [秒悟](https://meoo.com/) · [配套技能](https://github.com/lhfer/meoo-vibecoding-video)

原创代码与文档采用 [MIT](LICENSE)。头像、Meoo Logo、吉祥物和案例媒体另见 [视觉素材说明](BRAND_ASSETS.md)。
