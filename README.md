<a name="top"></a>

<p align="center">
  <picture>
    <source media="(max-width: 600px)" srcset="docs/media/brand-v2/hero-mobile.png">
    <img src="docs/media/brand-v2/hero.png" alt="把文章、资讯与观点，讲成有声有画的故事。{一起 Vibe} × Meoo 官方字标与猫咪吉祥物。" width="100%">
  </picture>
</p>

<h1 align="center">自媒体短视频 Skill</h1>
<p align="center">把文章、资讯与观点，讲成有声有画的故事。</p>
<p align="center">
  <a href="https://github.com/lhfer/meoo-article-to-video/releases/latest/download/article-to-vertical-video.zip"><strong>下载 Skill ZIP ↗</strong></a>
  &nbsp; · &nbsp; <a href="https://meoo.com/skills"><strong>在秒悟使用 ↗</strong></a>
  &nbsp; · &nbsp; <a href="docs/getting-started.md"><strong>安装指南</strong></a>
</p>
<p align="center">
  <a href="https://github.com/lhfer/meoo-article-to-video/releases/latest">v5.0.1</a>
  &nbsp; / &nbsp; <a href="LICENSE">MIT · 代码与文档</a>
  &nbsp; / &nbsp; Meoo · Claude Code · Cursor · Codex
</p>
<p align="center">
  <a href="#workflow">制作流程</a> &nbsp; · &nbsp; <a href="#case-study">案例与方法</a>
  &nbsp; · &nbsp; <a href="#start">开始使用</a> &nbsp; · &nbsp; <a href="#family">系列技能</a>
</p>

---

好内容，不止于文字。与其把文章逐段搬上屏幕，不如找到一个值得留下的发现，再用证据、镜头和声音把它讲清楚。

这是 **{一起 Vibe} × 秒悟 Meoo** 共创的开源工作流：素材核对、脚本、镜头、配音、剪辑和多画幅交付，一步步连接起来。**你决定方向、确认样片，也能修改每一步。**

<a name="workflow"></a>

## 01 / 从一段内容，到一条完整视频

<p align="center">
  <picture>
    <source media="(max-width: 600px)" srcset="docs/media/brand-v2/workflow-mobile.png">
    <img src="docs/media/brand-v2/workflow.png" alt="五步制作流程：读懂内容、核对素材、组织镜头、带声样片、完成交付。" width="100%">
  </picture>
</p>

| 从你这里开始 | 一起完成并交付 |
| :--- | :--- |
| 文章、资讯、观点与案例；已有链接、文件或录屏 | 提炼值得讲的发现，核对事实、版本和来源，整理素材与来源 |
| 受众、重点、发布平台 | 完整脚本、镜头安排、带声开头样片 |
| 对脚本和样片的反馈 | 按需求输出视频、封面与可修改工程 |

**真实素材优先。** 先找素材、核对来源，再编入镜头。每一句讲解，都尽量给观众一个看得见的依据。

支持按需求制作 **3:4、9:16、16:9**；不同画幅分别构图，不只是裁一刀。只制作你要求的画幅，先确认脚本与实际样片，再推进全片。

<a name="case-study"></a>

## 02 / 好看的背后，是具体的方法

<p align="center">
  <picture>
    <source media="(max-width: 600px)" srcset="docs/media/brand-v2/case-mobile.png">
    <img src="docs/media/brand-v2/case.png" alt="38 个案例的历史作品复盘：素材分组、叙事顺序与音画对应。" width="100%">
  </picture>
</p>

**先组织，再剪辑。** GPT-6「38 个案例」历史合集，把素材按主题分组，让讲解对应真实画面，再用代表性结果给观众一个继续看的理由。

[阅读完整复盘与真实预览 →](docs/case-study.md) · [直接打开成片节选](docs/media/case-preview.gif)

<sub>这是 {一起 Vibe} 的历史制作经验，也是共创 Skill 的方法来源；不是本 Skill 或秒悟端到端生成的证明。预览保留原作者标识。首屏的文稿、浏览器框与播放条是视觉示意，猫咪为 Meoo 品牌吉祥物。</sub>

<a name="start"></a>

## 03 / 选一个入口，开始第一条

### 在秒悟里，直接开始

打开 [秒悟](https://meoo.com/) → 首页左侧 **技能** → 搜索 **爆款短视频** → 选择 **自媒体爆款视频一键生成**。

添加后，把素材和目标交给它。平台条目与仓库版本分别维护；需要精确使用本仓库版本时，下载独立 ZIP 并按 [秒悟技能说明](https://docs.meoo.com/file) 导入。

### 在自己的 AI 编程工具里使用

[下载独立 ZIP](https://github.com/lhfer/meoo-article-to-video/releases/latest/download/article-to-vertical-video.zip)，解压并进入 `article-to-vertical-video/` 文件夹：

```bash
python3 scripts/doctor.py
python3 scripts/install.py --hosts claude,cursor,codex --dry-run
python3 scripts/install.py --hosts claude,cursor,codex
```

`--hosts` 只填写你需要的宿主。已有安装不会被覆盖；项目级安装、模型与媒体能力配置见 [安装与配置](docs/getting-started.md)。

### 复制这段，交给 Agent

```text
使用 $article-to-vertical-video 5.0.1。

把这些文章、链接和素材做成一条面向目标受众的短视频。
内容链接 / 素材：〔填这里〕
希望讲清的重点：〔填这里〕
目标受众、发布平台与画幅：〔填这里〕

先核对信息、查找并查看真实素材，再组织故事。
先给我完整脚本和带声音的开头样片，确认后再继续全片。
不要把全文做成 PPT；素材与工具有缺口时，请如实说明。
```

## 04 / 好看之外，也要可靠

**Skill 提供制作方法和工程，不附带模型服务额度，也不承诺一键生成爆款。** 工具、联网和生成能力以当前宿主与实际配置为准。

<details>
<summary><strong>运行环境与模型配置</strong></summary>

本地执行需要支持文件与命令工具的 Agent、Node.js 22+、Python 3.10+、FFmpeg / ffprobe，以及可用 Chromium。具体缺项以 `doctor.py` 输出为准。

Agent 模型在宿主里选择。生图、配音、音乐使用宿主已有能力或你配置的服务；无需为了试用同时配置所有提供者。凭据只保存在本地，不写进仓库和附件。

[查看完整安装与配置](docs/getting-started.md)

</details>

<details>
<summary><strong>验证范围与人工确认</strong></summary>

先确认完整脚本与实际带声样片，再进入全片。信息是否准确、画面是否好看、声音是否合适，仍需实际审阅。

历史案例不是本版本运行证明；Meoo 新版在线端到端生成尚未验证。发布检查与限制以 [当前验证记录](docs/release-verification.md) 为准。遇到权限、网络或生成额度问题时，保留工程和错误信息，不伪造成功。

</details>

<details>
<summary><strong>代码、品牌与素材许可</strong></summary>

原创代码与文档采用 [MIT](LICENSE)。Meoo Logo、M 标识、吉祥物、头像、横幅和案例媒体不按 MIT 再授权，详见 [视觉与案例素材说明](BRAND_ASSETS.md)。

Remotion 等依赖沿用各自许可证，参见 [第三方说明](THIRD_PARTY_NOTICES.md)。使用有权使用的字体与素材，并保留来源；共创标识不是强制加在你视频上的水印。

</details>

<a name="family"></a>

## 05 / 两套 Skill，按创作任务选

<p align="center">
  <picture>
    <source media="(max-width: 600px)" srcset="docs/media/brand-v2/family-mobile.png">
    <img src="docs/media/brand-v2/family.png" alt="Meoo 官方 M 标识：两套 Skill，一起把创意讲出来。" width="100%">
  </picture>
</p>

| 内容转短视频 | 作品做宣传 |
| :--- | :--- |
| 文章、资讯、观点与案例 | 网站、App、工具与小游戏 |
| 把信息组织成有证据的故事 | 用真实操作讲清产品价值 |
| [自媒体短视频 Skill](https://github.com/lhfer/meoo-article-to-video) | [VibeCoding 作品宣传 Skill](https://github.com/lhfer/meoo-vibecoding-video) |

两套技能各自独立，按本次任务选一套即可。

[安装与配置](docs/getting-started.md) · [秒悟使用指南](MEOO-QUICKSTART.md) · [Skill 入口](SKILL.md) · [变更记录](CHANGELOG.md) · [反馈问题](https://github.com/lhfer/meoo-article-to-video/issues)

<details>
<summary><strong>开发与视觉维护</strong></summary>

```bash
python3 scripts/check-readme.py
python3 -m unittest discover -s tests -p 'test_*.py'
node --test tests/*.test.mjs
cd assets/director
npm ci
npm run check
```

[README 视觉维护](docs/readme-design.md) · [品牌源素材与重渲染](docs/branding/README.md)

反馈时附技能版本、宿主、预期结果与脱敏后的错误信息，不要上传 API Key、Cookie 或其他凭据。

</details>

---

<p align="center">
  <picture>
    <source media="(prefers-reduced-motion: reduce)" srcset="docs/branding/source/meoo-mascot-poster.png">
    <img src="docs/branding/source/meoo-mascot.gif" width="112" alt="Meoo 官方猫咪吉祥物。减少动态效果模式使用静态帧。">
  </picture>
</p>
<p align="center"><strong>{一起 Vibe} × 秒悟 Meoo</strong></p>
<p align="center">有好内容，也有好作品。一起把它讲出来。</p>
<p align="center"><a href="https://meoo.com/">秒悟</a> &nbsp; · &nbsp; <a href="#top">回到顶部 ↑</a></p>
