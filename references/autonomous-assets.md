# 自主取材：从“要找什么”到“真的用上了”

## 以脚本的证据需求规划，不以搜到什么拼视频

每个 beat 写清楚观众必须看见的内容、用途、首选来源与备用方案。把决定核心主张的素材标为 required。资讯可用原文局部、图表、真实演示；产品宣发的功能主张需要真实操作视频，至少一项 required real-demo 在前十秒出现。

默认先自主获取。只有实际路线均受阻或涉及额外授权，才向用户索取最小缺口；不要一开场要求用户自己准备全部图片和录屏。

```sh
python3 "<skill>/scripts/materials.py" "<project>" init --from-script
python3 "<skill>/scripts/materials.py" "<project>" add --id product-demo --need "从输入到结果的一次真实操作" --why "证明核心能力" --strategy capture --evidence-kind real-demo --required --required-for opening
```

`--from-script` 创建的是待填写需求，不是取材完成。根据实际内容改成准确需求，不能保留占位说明。

## A. 搜索与直链下载

先搜索官方产品页/新闻稿/文档/README/作者发布/媒体资源，核对主体、版本、时间。官方原图、真实产品画面优先于无关库存视频。使用 `sources.py` 保存来源；`fetch_page.py` 的 HTML 和 media.json 帮助发现资源，**它不是浏览器截图**。

支持的直链可用现有 `download_media.sh` 下载，再用 `media.py --kind ingest` 注册。查到视频页面、iframe 或播放清单不等于已经拿到媒体文件；优先官方可用下载/授权素材库/获授权浏览器录制。不得绕过登录、DRM、付费墙或使用他人会话凭据。需要用户补素材时，说明已经试过哪条路线，而不是直接甩回一个录制清单。

## B. 真截图/真录屏

有宿主浏览器优先用宿主。否则，本地浏览器捕获：

```sh
python3 "<skill>/scripts/capture.py" "<project>" --id official-shot --url "https://官方实际域名/产品页" --selector main --rights "实际使用依据，含来源与用途"
```

`capture.py` 等待页面、字体和可见图片，保存全分辨率图、来源文本、调用收据并注册 film.assets。它只能标为 acquired，不能替你判断内容正确。

自己的测试产品/本地预览，可使用显式授权的操作脚本：

```json
[
  {"type":"fill","selector":"[data-testid=query]","value":"公开演示样例"},
  {"type":"click","selector":"[data-testid=run]"},
  {"type":"wait","seconds":2}
]
```

```sh
python3 "<skill>/scripts/capture.py" "<project>" --id demo --url "http://127.0.0.1:3000" --allow-local --record --actions "<project>/work/actions.json" --allow-interaction --seconds 3 --rights "作者自己的测试产品与演示数据" --material product-demo
```

操作 selector 必须来自实际 DOM，不猜按钮。脚本最多 30 步，不执行任意 JavaScript。录屏发生在真实网页，不能重绘一个假 App 作为结果。录屏中的真实光标可后期增强，但点击位置/先后顺序必须对应实际操作。

`--mask` 仅用于截图；它不能给视频脱敏。用干净演示账号/假数据，别录真实邮箱、通知、token、客户信息。调用失败的 `work/captures/*/receipt.json` 用于记录阻塞，不清空旧素材。

## C. 导入、实际查看、绑定镜头

```sh
python3 "<skill>/scripts/sources.py" "<project>" --id original-demo --input "/actual/demo.mp4" --title "作者提供的产品操作视频"
python3 "<skill>/scripts/media.py" "<project>" --id demo --kind ingest --input "/actual/demo.mp4"
python3 "<skill>/scripts/materials.py" "<project>" set --id product-demo --asset demo --source original-demo --provenance user --rights "作者拥有产品与该录屏，授权用于本次宣发"
# 先用真实工具打开文件，看输入→操作→结果及隐私信息，再记录（不能自动填以下占位内容）：
python3 "<skill>/scripts/materials.py" "<project>" verify --id product-demo --tool-ref "实际查看工具调用编号" --inspection-note "具体看到了哪些状态、可用区间和限制"
```

将 `demo` 放入实际镜头的 `assets`，代码中用 `asset('demo')`。关联了 beat 的证据必须与该段旁白同时出现。`materials.py check` 会检查映射、真实文件、可解码性、内容哈希、来源、查看记录与使用情况；不把仅有链接当成 ready。

生成素材仅做概念解释，标记 provenance=generated；code 为代码示意，须命名 shot 并看过实际渲染才 verify。两者都不能满足 real-demo。截图动效也不是产品操作录像。

## 阻塞记录与降级

`materials.py attempt --id … --route … --result blocked --evidence work/实际错误文件.json --note "具体失败原因"`。

required 不能静默 skip。若核心证据不可得：优先缩小/移除对应主张并明确调整方案，或交付待素材草稿；不能保留强结论，同时偷偷把 required 改为 false。未经实际查看，不填写“已确认一致/无隐私/已实测”。


## 离线技术样例与草图（不能用于产品实测）

已有获授权的自包含 HTML，可运行：

```sh
python3 "<skill>/scripts/capture.py" "<project>" --id html-preview --html work/demo.html --rights "本项目作者自有的示意页面"
```

`--html` 与 `--url` 互斥；路径必须在工程内，页面外部网络请求被阻止。它会标注 `sourceMode=local-html`；绑定素材时为 illustration，不能用它通过 real-demo 门禁。联网访问受阻时不能用这一分支冒充访问了官网。操作录制的权限/动作限制与网页模式相同。
