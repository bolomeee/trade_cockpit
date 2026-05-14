# Sprint Contract：F109-a Widget 内部间距 + Title 底色规范落实

> 日期：2026-04-21 | 状态：**反向补契约**
> 依赖：v1.1.0 Workbench 发布（F100/F101/F102）；design-spec v1.1.0 规范已备案
> 引用文档：
>   design-spec.md#Workbench-Widget-Shell（"Widget 内部垂直间距规范（v1.1.0 起强制）" + title 底色 #ebf2fa）
>   DECISIONS.md#D046（本 sprint 新增，记录硬编码策略）

---

## 背景

v1.1.0 的 design-spec 原本规定 widget title 底色用 `--color-surface-muted`，实际视觉落地过程中统一替换为 `#ebf2fa`；同时补充"顶部贴边偏移 `marginTop: -5 / marginLeft: -5`"与"子组件间距 `gap-1`"两条规范。design-spec.md 已于本次修订补备案，但代码落地是绕过 feature-dev 手改的。本 sprint 把代码改动纳入契约轨道，作为 Evaluator 验收基线。

---

## 本次实现范围

### 1. `frontend/src/workbench/WidgetShell.tsx`（修改）
- widget handle bar：
  - 移除 `bg-muted` class
  - 追加 `style={{ backgroundColor: '#ebf2fa' }}`
  - 其他（高 18px、下分隔线、cursor-grab、text-xs）保持不变

### 2. `frontend/src/workbench/widgets/WatchlistWidget.tsx`（修改）
- 根 `<div>` 改：
  - `gap-3` → `gap-1`
  - 追加 `style={{ marginTop: '-5px', marginLeft: '-5px' }}`

### 3. `frontend/src/workbench/widgets/PullbackWidget.tsx`（修改）
- `PullbackHistoryCard` 外层包 `<div style={{ marginTop: '-5px', marginLeft: '-5px' }}>`

### 4. `frontend/src/workbench/widgets/FundamentalsWidget.tsx`（修改）
- `FundamentalsCard` 外层包同上 div

### 5. `frontend/src/workbench/widgets/QuickAddWidget.tsx`（修改）
- 内容容器追加同规范（根据当前 diff 已落地，确认即可）

> 注：`MarketBreakoutWidget` 的相同间距已经在 F106-c 里落地，不归本 sprint。

---

## 明确排除

- tokens.css 改动（design-spec 明确规范硬编码，D046 记录）
- WidgetRegistry / layout json 改动
- TopNav / App.tsx 布局变更（→ F109-b）
- 其它非 widget 组件（AddStockCard search 样式 → F109-b）

---

## 预计修改文件（共 5 个）

| # | 文件 | 类型 | 改动 |
|---|---|---|---|
| 1 | `frontend/src/workbench/WidgetShell.tsx` | 修改 | title 底色硬编码 `#ebf2fa` |
| 2 | `frontend/src/workbench/widgets/WatchlistWidget.tsx` | 修改 | `gap-1` + `marginTop: -5 / marginLeft: -5` |
| 3 | `frontend/src/workbench/widgets/PullbackWidget.tsx` | 修改 | 根 wrapper 加 `marginTop: -5 / marginLeft: -5` |
| 4 | `frontend/src/workbench/widgets/FundamentalsWidget.tsx` | 修改 | 同上 |
| 5 | `frontend/src/workbench/widgets/QuickAddWidget.tsx` | 修改 | 同上 |

---

## 可测试的完成标准

| # | 标准 | 层级 |
|---|---|---|
| 1 | 所有 widget title bar 底色一致 `#ebf2fa`（浏览器 devtools computed style）| 手工 |
| 2 | 5 个改动 widget 的内容区到 Shell 上/左边缘偏移 -5px，视觉紧贴 | 手工 |
| 3 | Workbench 首屏视觉对比截图：widget 边距与 v1.2.0 一致，无回归 | 手工 |
| 4 | design-spec.md 的"Widget 内部垂直间距规范（v1.1.0 起强制）"小节存在 | 文档 |
| 5 | DECISIONS.md D046 含：UI 规范硬编码 `#ebf2fa / -5px / gap-1`，理由 + 范围 | 文档 |
| 6 | `pnpm --filter frontend typecheck` + `build` 通过 | 静态 |
| 7 | grep 确认只有 widget 外壳层硬编码这些值，其他组件不扩散 | 手工 |

---

## Evaluator 自检清单

- [ ] `pnpm --filter frontend typecheck` 通过
- [ ] `pnpm --filter frontend build` 通过
- [ ] 浏览器打开 Workbench，肉眼确认 5 个 widget 视觉一致
- [ ] 切换到浅色 / 深色主题（若有）确认 `#ebf2fa` 在两模式下的可读性可接受
- [ ] design-spec.md 对应小节已备案
- [ ] DECISIONS.md D046 追加

### 代码质量检查
- [ ] 硬编码值仅出现在 widget 外壳层，未扩散到业务组件内部
- [ ] 无重复的 style 对象字面量（可抽 `WIDGET_SHELL_TOP_OFFSET` 常量，若 5 处重复可考虑；本 sprint 不强制）

### 回归测试
- F100/F101/F102 既有 widget 切换 / 拖拽 / 尺寸调节回归
- 起 docker 环境对比 v1.2.0 截图（如有）

---

⚠️ **反向补契约**：代码已落地 + design-spec 已备案（本次改动内）。Evaluator 阶段主要核对"代码 / design-spec / DECISIONS 三者一致性"。
