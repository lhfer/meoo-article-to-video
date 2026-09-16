# 音乐：按调性选曲、生成、打分、对位、卡点、混音

短视频平台上配乐不是背景，是留存的一半：前 2 秒没有重击观众就划走，中频太满旁白就糊，节奏和切换不同步就"廉价"。两包都默认有 BGM：爆款版必须有且重击对位大动作；宣发版默认一条轻的节奏床（`gain 0.35`），只有作者明确要"无配乐"才关。

## 1. 调性从哪来（`music.py plan`）

配乐先定**调性**再谈风格。推导顺序，取到即止：

1. `brief.music.archetype` 显式指定；
2. **产品卡** `content/product.json`（`product.py`）：`tone.adjectives`、`tone.energy`、`category`、`audience.who` 命中关键词；
3. 脚本文本：连续出现"反转 / 翻车 / 内幕"→ 悬念，"燃 / 对决 / 碾压"→ 燃，证据与拆解占比高 → 节奏；
4. profile 默认：爆款 = 动感，宣发 = 沉稳。

| 原型 | 中文 | BPM | 适合 |
|---|---|---|---|
| hype | 燃 | 130–150 | 重大发布、正面对决、榜单、赛事 |
| upbeat | 动感 | 118–132 | 科技资讯、新功能、消费类 App、社交内容 |
| groove | 节奏 | 92–112 | 教程、清单、拆解、口播密集 |
| calm | 沉稳 | 84–104 | 开发者工具、效率工具、B 端、作者宣发 |
| tech | 科技冷感 | 100–120 | AI / 基础设施 / CLI / API |
| warm | 温暖 | 90–110 | 生活方式、亲子、健康、陪伴 |
| suspense | 悬念 | 88–108 | 争议、翻车、反转、调查 |
| uplift | 励志 | 100–120 | 作者历程、从 0 到 1 |

BPM 随语速与切换频率微调：8 字/秒以上 +6，切换 ≤1.5 s 再 +4（合计封顶 ±8）。`music.py plan --list-archetypes` 打印全表；`--archetype` 覆盖；推导依据写进方案卡"声音"行：`BGM 调性：动感（依据：产品卡命中「年轻、社交」）`，让用户在步骤 0 就能否决。

## 2. 生成提示词（fun-music-v1 等宿主工具）

`music.py plan <project> --id bgm [--candidates 3]` 从 brief、产品卡、脚本（有 timeline 时用实测节拍时间）生成 N 条中文提示词到 `work/music/host/bgm-*.prompt.txt` 与 `bgm-plan.json`。每条提示词固定包含：

- 调性、风格、乐器、BPM 区间；用途（平台 + 竖屏 + 旁白全程压在上面）、大致时长、内容一句话；
- **结构按秒**：第一小节进鼓、开头 2 秒内一个清晰重击（对位 hook）；转折处能量抬升一次；总结前收束成轻的节奏床；结尾干净、可循环；
- **混音**：低频与打击为主，1–4 kHz 让给人声，动态清晰不砖墙；
- **不要**：人声/哼唱/歌词、长前奏、淡入、预告片 riser 与 braam、突兀静音、廉价 trap 音色、水印。

三个变体：主线版 / 打击版（去旋律给旁白让路）/ 高能版。已核对（2026-09-11 阿里云文档）：prompt 1–2000 字符；**不能指定时长**（模型自定，所以提示词只描述、由 `fit` 截取）；每次调用只出一首，N 个候选 = N 次调用；`is_instrumental: true`；`format: wav`。

## 3. 候选打分（`music.py rank`）

`music.py rank <project> --inputs a.wav b.wav c.wav` 用同一个分析器给每条打分：首个强重击时间（≤2 s 满分）、BPM 是否落在区间（接受 ½× / 2× 读数）、1–4 kHz 能量占比（越低越不打架）、时长是否够、动态（crest）。分数只看结构指标；**人声、淡入、突兀静音必须实际听一遍**再定。本地曲库同样可以 rank。

## 4. 对位与卡点

```bash
python3 <skill>/scripts/music.py <project> ingest --id bgm --input <best.wav>          # 48k wav + 分析 hits/BPM → content/music.json
python3 <skill>/scripts/music.py <project> fit --id bgm --hit bgm.hit_1 --to hook.王炸  # 求 trimStart，写 film.audio 与 bgm.hit_N 事件
python3 <skill>/scripts/music.py <project> grid --id bgm                                 # fit 之后：按 BPM 与该重击相位写 bgm.bar_N 事件
```

`fit` 让选定重击正好落在词事件（≤2 帧），并把所有重击注入 `film.events.bgm.hit_N`；镜头里 `cue('bgm.hit_5')` 把最有力的动作（砸字、硬切、白闪）放在上面。`grid` 在 fit 之后跑（trim 改变相位），把小节线写成 `bgm.bar_N`，镜头 `anchor: 'bgm.bar_3'` 即可让硬切吸在拍子上；`--beats` 给每拍事件。BPM 可能是 ½× / 2× 读数，先听 bar_2 / bar_3 是否落在真实强拍。`qa.py` 用 `shot.anchor` 核对切点与事件同帧。

## 5. 平台层：站内曲库与干声版

- 抖音 / 小红书 / 视频号对使用**站内热门 BGM** 的作品通常有分发加成（创作者普遍观察，未量化，以平台当前规则为准），AI 生成或外部音乐拿不到；但站内曲库不能进成片文件。做法：正片带 BGM 版照常交付，**同时交付干声版** `render.py --stage final --dry-voice`（同画面同旁白，无音乐床，文件名 `final-<fmt>-dry.mp4`），上传后在 App 内叠热门原声，避免双重 BGM。
- 版权：AI 生成音乐没有第三方版权风险；本地曲库只用有授权的曲子并记录来源；商用平台音乐只能在站内使用。
- 平台一般会做响度归一（具体目标值不公开），成片按 −14 LUFS / TP −1.5 交付，避免被压得更小。

## 6. 混音

- `film.audio[]`：爆款 `gain 0.55`、`duck 0.45`（旁白附近降到 45%，9 帧起、15 帧收）；宣发 `gain 0.35`、`duck 0.5`；演示原声段压到 0.18。`fadeIn 0.2`、`fadeOut 1.5`。
- 8 字/秒的口播几乎不间断，BGM 大部分时间处于 duck 状态，所以候选要选中频空的；rank 的"中频"列就是这个。
- 旁白是主角；每段配音在 `voice_edit` 里已做两遍 loudnorm（−15 LUFS / TP −1.5）。成片 `master_audio.sh <in> <out> -14`；手机场景可到 −11。归一化不能掩盖糟糕的表演。
