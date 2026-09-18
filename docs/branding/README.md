# {一起 Vibe} × Meoo · 视觉资产

[← 返回项目首页](../../README.md)

本系列使用维护者提供的官方 Meoo 字标、M 图标与猫咪吉祥物。文章版使用纸白与淡紫，作品版使用深色与淡紫；两版共用品牌位置、字号体系和猫咪形象，分别重排桌面与手机画面。

## 素材

`source/meoo-logo.png` 是所提供字标的 128 色网页副本，尺寸与轮廓不变；`source/meoo-icon.png` 和 `source/meoo-mascot.gif` 保留所提供文件，GIF 共 41 帧。`source/meoo-mascot-poster.png` 是第一帧，供减少动态效果模式使用。

首屏用静态 PNG，页尾保留原版动态猫咪，不把整个首屏做成重型 GIF。图形是品牌与流程示意，不是 Skill 的实际视频输出。

素材权利见 [视觉与案例素材说明](../../BRAND_ASSETS.md)。这里没有分发字体文件。

## 重渲染

安装 Pillow 11.3.0，并在机器上安装 Noto Sans CJK 字体，然后在仓库根目录运行：

```bash
python3 docs/branding/render.py --profile article --assets docs/branding/source --output docs/media/brand-v2
python3 scripts/check-readme.py
```

其他字体路径使用 `--font-dir`；该目录需含 NotoSansCJK-Regular.ttc 和 NotoSansCJK-Bold.ttc。更换字体版本后应重新检查字宽、排版与导出图片。

八张 PNG 的字节数与 SHA-256 保存在 [素材清单](../media/brand-v2/manifest.json)。桌面主图为 1600×840，手机主图为 800×1120。修改后同时检查两种构图。

[README 设计与检查范围](../readme-design.md)
