# 镜头组件工具箱

新镜头优先使用 `safe.tsx` 的 `SafeText`、`SafeBox`、`useFrameLayout`。布局实现在 `layout-engine.mjs`，浏览器实测与检查在 `dom-qa.mjs`。`LayoutGuard` 在 Film 中逐帧检查；不要移除。

旧 `layout.ts` 保留 stage/columns/subjectArea/safeArea 兼容接口，但它们采用默认区域；需要自定义边距时一律通过 `useFrameLayout` 读取同一份配置。`safeArea(format, platform)` 的平台参数仅为旧代码兼容，不代表某平台官方 UI 保证。具体发布界面需实际预览。

其他现有动作、颜色、卡片、特效组件可以继续组合。它们不是无条件适配任意长文案的模板；承担文字与信息的外层必须接入测量/区域约束。默认 EvidenceScene 只是可执行技术示例，正式作品不能保持 template=true。

全屏电影感素材可用 SafeBox role="background" 并填写 overlapReason；重要界面文字仍须清晰展示。时间驱动采用 useCurrentFrame，不使用在离线渲染中不稳定的 CSS 实时时间动画。
