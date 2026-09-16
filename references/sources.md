# 混合素材与证据

每个来源保存独立身份、原始文件、提取文本与时间。用户想法、作者亲历、产品官网、第三方报道、图片与演示分别归属，再围绕同一个观众收益组织内容。

```bash
python3 <skill>/scripts/sources.py <project> --id announcement --input 'https://example.com/article' --title '原始发布'
python3 <skill>/scripts/sources.py <project> --id notes --input <local-file.md>
python3 <skill>/scripts/sources.py <project> --id demo --input <local-demo.mp4>
```

文本、Markdown、HTML、PDF、DOCX、JSON/CSV 可由导入器处理；音视频和图片会保留原件供宿主查看。扫描 PDF、复杂版式、图表与幻灯片通过宿主现有的文档／视觉能力读取，必要时渲染逐页检查。提取失败时报告具体来源与缺失内容，保留原文件。

网页提取器使用 V2 的 fetch_page.py；按网站实际响应选择正常浏览器或已保存页面等回退。`media.json` 中的真实演示需要单独下载并实际查看，按当前来源的目录保存。保留工具 `download_media.sh` 与 `contact_sheet.sh` 供需要时调用，其帮助中说明所需的 workdir/assets 与 project 结构；多来源时分别在独立 source workdir 中使用，然后登记目标素材。

`content/sources.json` 数组条目含 `id,title,origin,fetchedAt,textFile,mediaFiles`。`textFile` 相对工程根目录。重要事实在 `claims.json` 中记录：

```json
[{"id":"claim-a","sourceId":"announcement","claim":"当前文案使用的事实表达","quote":"确实出现在该来源里的原文","kind":"source-claim"}]
```

验证器检查引用确实出现在所标注来源。作者继续核对数字的单位、对象、范围和条件，以及原文是否支持当前句子；需要时将推断单独写明。对于视频中的观察，保存可回看的时间码与具体观察记录，再引用该记录并标明它来自哪个视频。

同一内容可以包含多个相互补充甚至冲突的来源。保留归属、时间与证据强弱，解释冲突，而后形成有依据的判断。
