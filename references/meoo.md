# Meoo 执行协议（先读，不把宿主能力当成既定事实）

## 独立工作区与首次探测

这是视频制作技能，不是只做播放器页面的技能。Meoo 可能正在维护一个已有 Web 工程：**不要覆盖它的 package.json、src 或锁文件**。在独立 `<work>/project` 中制作视频，宿主页面只负责展示/下载结果。

1. 用宿主文件读取工具定位实际 `SKILL.md`，打印技能名、版本、脚本目录；不猜 `/mnt/data`、`/workspace` 或 `~/.skills`。
2. `python3 "<skill>/scripts/project.py" init "<work>" --profile viral`（宣发版用 `launch`）。先初始化，之后才写任何产品卡/素材台账。
3. `python3 "<skill>/scripts/capabilities.py" "<project>" probe`。本地程序存在只证明能找到它，不证明联网/录屏/生成成功。
4. 在**实际工具列表**中查找搜索、浏览器导航/截图/录制、打开图片、听音频、TTS、图片/视频/音乐生成。只记录真实工具名，不编造 `browser.screenshot`、`meoo.search` 等接口。
5. 对当前任务确实需要的工具做一次最小真实调用，把经过脱敏的结果/错误保存到项目内，用 `capabilities.py record` 登记：

```sh
python3 "<skill>/scripts/capabilities.py" "<project>" record --name search --tool "实际工具名" --status passed --receipt work/search-result.json --note "实际检索到了产品官方页"
```

`passed` 必须对应已调用的工具。没有工具写 unavailable；有工具但未调用仍是 not_tested；权限/网络错误写 failed。**不得用应用的服务端 AI API 能力，推断制作 Agent 也有搜索、浏览器或视觉能力。**

## 工具分支，不是单一路径

| 需求 | 首选 | 备选 | 都受阻后 |
|---|---|---|---|
| 找资料/素材 | 宿主搜索 + 一手来源 | 已知官网的可访问导航、README、官方媒体页 | 给出缺口、实际尝试、最少需要用户补什么 |
| 网页截图 | 宿主真实浏览器 | `capture.py` + Python Playwright + Chromium | 使用现有真实截图；不能冒充已截图 |
| 产品操作录屏 | 已获授权的宿主浏览器录制 | `capture.py --record` + actions JSON | 缩小主张/请用户提供对应录屏，不用生成画面代替实测 |
| 媒体文件 | 官方公开下载/用户有权使用的文件 | 获授权的浏览器录制、其他合适的一手素材 | 记录页面链接不等于可剪辑素材 |
| 生图/视频/TTS/配乐 | 宿主已有且实际可调用的工具 | 本包已有 Grok/Fish 等适配器（仅有权限时） | 明确阻塞，不用空白图/静音假装成功 |
| 看图/听音频 | 宿主实际视觉/试听工具 | 用户实际预览（明确标为用户检查） | 只能交付待检草稿，不能填“已检查” |

下载/采集每项最多先尝试两条有根据的路线，失败记日志；不要在没有网络/权限时反复重试。普通失败优先自主修正；涉及登录、付款、公开发布、私有数据或产品关键定义时，不扩大授权。

## 本地依赖

在 `<project>` 运行 `npm ci`，**不在 Meoo 宿主根目录运行**，也不擅自升级锁定依赖。必要条件是 Node/npm、Python3、FFmpeg/ffprobe 与可用 Chromium。

只有需要本地捕获且宿主允许安装时：

```sh
python3 -m pip install playwright
python3 -m playwright install chromium ffmpeg
```

有系统 Chromium 时，`capture.py --browser /actual/chromium`；无权限安装就走宿主浏览器。录屏需 Playwright 的 FFmpeg 运行组件，不能只安装 Python 包就宣称录制可用。

字体先 `fonts.py <project> auto`；没有本地浏览器时，可使用用户/宿主提供且有权使用的字体资产，按现有 `film.style.fonts` 注册，真实渲染后检查。不要偷偷回落到导致中文换行不同的字体。

## 失败时交付什么

保存当前工程、素材台账、实际错误、能看的草稿和下一条可执行修复；标注“待验证/缺实测素材/缺试听”，不要把问题隐藏成通用 PPT。技能不可能凭文字赋予宿主未开放的工具或权限。

同名旧技能可能影响路由：导入新版后，在新任务中明确指定此技能及版本，只启用对应的一个版本。Meoo 的具体加载路径、模式和工具以当前任务实际发现为准。

公开参考（核对：2026-09-12）：https://docs.meoo.com/file · https://docs.meoo.com/agent 。官方文档支持本地技能包与脚本，但不等于本文所有工具在每个任务都已授权。
