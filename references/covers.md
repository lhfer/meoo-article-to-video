# 封面：真实素材锁主体，生图模型出图，文案先过检查

封面由生图模型整张生成（含中文标题），不用程序叠字；可以是本机 Grok（`cover.py generate`）或平台自带生图模型（`cover.py ingest`）。每个比例 3–4 张候选 + 1 张无字版，**逐张实际查看**再选。

## 1. 先锁主体：参考图不是可选项

之前的封面"想象"了一台设备，不引用素材，原因是 plan 从不去看素材。现在 `cover.py plan --reference auto` 按顺序找真实图片：产品卡 `media`（官方图、截图）→ 素材台账里 `ready` 的图 → 正片图片素材；找到就按目标比例 pad（默认）或 crop 成 `work/cover/ref/<ratio>.png`，`generate` 走 `image_edit`，提示词里写死"主体与参考图完全一致，只改场景、光线、构图与标题"。宿主生图工具则在计划里注明"附上这张参考图"。一张都没有才退回纯文生图，并在 `out/cover-qa.md` 标明。自己的 App 用真实界面截图或录屏帧；第三方产品用官方新闻稿图（权利记进产品卡）。

## 2. 提示词里写"能画出来的点击要素"

`cover.py plan` 每比例生成提示词（可手改）：

1. 平台点击要素（`CLICK`）：小红书 = 生活场景里正在发生的动作、明亮自然光、下方留高对比色块；抖音 = 主体 ≥ 60%、脸或物件大、元素少对比强、标题在中上；B 站 = 主体一眼可辨、有张力、另一侧色块放标题。
2. 主体一句话 + **主体锁定**（有参考图时）。
3. **视觉钩子**：默认取 hook 那句话，"画成一个正在发生的动作或张力，不是摆拍"（`--hook` 可指定，如"半折的手机在桌上"）。
4. 构图（下表）、真实感词表、本片风格、标题行（位置 + 字数 + 逐字正确 + 不能有别的字）、负面词。

| 平台 | 比例 | 构图 | 封面大字 | 注意 |
|---|---|---|---|---|
| 小红书 | 3:4 | 主体偏上占 2/3，底部 1/4 留标题 | 8–14 字，可两行 | 双列信息流，缩略图 ~360px |
| B站 | 16:9 | 主体占一侧 2/3，另一侧留白放标题 | 6–12 字，一行 | 缩略图 ~320px，主体要一眼可辨 |
| 抖音 / 视频号 | 9:16 | 主体上 2/3 居中偏上，脸 / 物件大 | 4–8 字 | 底部 300–380px 被界面盖住 |

无字版（`<ratio>-notitle.txt`，`generate --no-title`）用于平台内加字或 A/B。

## 3. 文案：AI 写，工具查（`cover_copy.py`）

封面大字（图里的字）和发布标题是两套。每平台写 ≥ 5 条封面大字候选，覆盖 ≥ 3 种公式：问句 / 数字 / 反差 / 身份代入 / 悬念缺口；再写 3 条发布标题（问句 / 数字 / 反差）。然后：

```bash
python3 <skill>/scripts/cover_copy.py <project> check --platform xiaohongshu --cover "折叠屏 iPhone 到底值不值" --cover "…" --title "…"
```

打回规则：字数超出平台区间；命中 `banned-words.txt` 与 `brief.bannedWordsExtra`；画面外承诺（震惊 / 必看 / 全网 / 天花板…）；**数字在 claims 与脚本里找不到**；候选集公式不足 3 种。通过的记进 `content/cover.json.copy`。

## 4. 流程

```bash
python3 <skill>/scripts/cover_copy.py <project> check --platform xiaohongshu --cover … --title …
python3 <skill>/scripts/cover.py <project> plan --title "<通过的封面大字>" --subject "…" [--reference auto] [--hook "…"]
python3 <skill>/scripts/cover.py <project> generate --ratio 3x4 --n 4          # 本机 Grok，自动带上 plan 的参考图
python3 <skill>/scripts/cover.py <project> generate --ratio 3x4 --n 1 --no-title
python3 <skill>/scripts/cover.py <project> ingest --ratio 9x16 --input <宿主生图产物>
python3 <skill>/scripts/cover.py <project> sheet && python3 <skill>/scripts/cover.py <project> select --ratio 3x4 --id 3x4-2 --upscale --note "标题正确，主体与参考图一致"
```

## 5. 逐张检查（写进 `out/cover-qa.md`）

1. 标题逐字正确（错一个字就重出）；2. **主体与参考图一致**（型号、界面、颜色没被重新设计）；3. 手指与肢体；4. 诡异对称、塑料高光；5. 景深合理；6. 与正片主体、色彩、光线连续；7. 缩到 200px 宽还能一眼看出主体（`cover.py sheet` 底行）；8. 标题对比度；9. 封面承诺与内容一致。

Grok `image_gen` 3:4 实测 864×1152，`image_edit` 输出继承输入画幅（所以参考图先 pad/crop）；`--upscale` 用 lanczos 放大到交付尺寸并记录原始分辨率。首帧＝封面：hook 镜头 frame 0 可以直接用封面图做底，0.15 s 内溶入正片。
