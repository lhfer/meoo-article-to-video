# Grok 媒体与整片一致性

围绕当前表达决定生成什么：核心主体、概念机制、视觉隐喻、空间变化、承接真实素材的镜头。封面单独走 [covers.md](covers.md)（`cover.py`）。本机有 Grok 订阅时优先用它；宿主自带生图／生视频工具时直接生成，再用 `media.py --kind ingest` 登记，保持素材生成与宿主选择独立。生成素材只做概念解释与隐喻，不冒充真实演示。

先在 `visual.json.stylePrompt` 写本片的材质、色彩、光线和运动方向；生成每镜时补充主体、动作、构图、用途和承接关系。风格与镜头目的共同决定提示词。

```bash
python3 <skill>/scripts/media.py <project> --id subject --kind image --prompt-file <prompt.txt> --aspect 3:4
python3 <skill>/scripts/media.py <project> --id subject-motion --kind i2v --image <approved-reference.png> --prompt-file <motion.txt> --duration 6 --resolution 720p
python3 <skill>/scripts/media.py <project> --id scene --kind r2v --image <reference-a.png> --image <reference-b.png> --prompt-file <scene.txt> --duration 6 --resolution 480p
python3 <skill>/scripts/media.py <project> --id imported --kind ingest --input <existing-media-file>
```

`--dry-run` 只打印调用计划。具体工具时长与尺寸参数采用本机已核验能力；生成片段的时长不决定整片长度。原始生成文件与日志保留在当前工程，输出用唯一文件名登记到 `film.assets` 和 `public/gen/manifest.json`。

视频登记时会保留原件，生成含单一主视频流的 H.264／AAC 文件，避免封面附图流干扰后续处理；同时记录实际尺寸、时长和音轨。提供者返回的画幅可能只是近似目标比例，在镜头内按真实尺寸选择构图和取景，三版成片尺寸由 Remotion 合成保证。

## 一致性的工作方式

先选好主体／关键帧，再以参考图编辑、图生视频或参考生视频延续视觉身份。查看真实输出的轮廓、颜色、材质、光线、空间方向与动作；必要时生成替代方案、调整构图或修正接点。与真实录屏衔接时，通过共同形状、位置、动作或颜色建立关系。

镜头中使用的素材 id 写入 `shot.assets`，字体等全局素材写入 `globalAssets`。代码使用 `staticFile(asset.src)` 加载本地资源。真实产品能力用实际演示支撑，概念动画负责解释；出处与用途清楚区分。

保留生成音轨原件，按镜头目的决定是否使用。实际混音可选择环境声、动作声、旁白和音乐，音量与音画时刻在共同时间轴中安排。

没有必要为每条复制同一套生成背景；将迭代投入到能显著增强理解、吸引力或风格连续性的镜头上。

## 失败处理

先读当前 job 的日志与退出状态，确认是凭据、工具能力、参数、限流还是输出解析问题。保留已有有效资产，按具体原因修正。低层 `grok_media.py` 的接口校准注释属于历史版本证据，真实可用性以当前调用为准。媒体权限／参数不兼容时，可在具备该能力的 Grok 交互会话生成，再通过 ingest 接入。
