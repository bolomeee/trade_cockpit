# Sprint Contract：F109-b TopNav 布局 + 搜索框样式

> 日期：2026-04-21 | 状态：**反向补契约**
> 依赖：F100 TopNav（v1.1.0）
> 引用文档：
>   design-spec.md#TopNav / #AddStockCard（本 Contract 同步更新这两段）

---

## 本次实现范围

### 1. `frontend/src/App.tsx`（修改）
- 移除 `useLocation` 导入及 `showResetLayout` 条件渲染逻辑
- 移除 ResetLayoutButton 在 MarketOverviewBar 右上角绝对定位的容器
- MarketOverviewBar 变回单纯的 row 元素（无 relative 包裹）
- 保持路由结构、lazy import、Suspense fallback 不变

### 2. `frontend/src/components/features/topnav/TopNav.tsx`（修改）
- 顶部品牌 `MA150 Tracker` 从 `<span>` 改为 `<NavLink to="/" end>`（点击回 Workbench 首页）
  - 样式补 `textDecoration: 'none'`，其它字号/字重/颜色复用既有 token
- 右侧 `RefreshButton` 后追加 `ResetLayoutButton`，仅在 `pathname === '/'` 时渲染
- 引入 `useLocation`、`ResetLayoutButton`

### 3. `frontend/src/components/features/dashboard/AddStockCard.tsx`（修改）
- `<Input>` 加 className：`rounded-full text-[10px] md:text-[10px] font-bold placeholder:font-bold`
- 其它 props（value / placeholder / onChange）保持不变

### 4. `docs/设计/design-spec.md`（修改）
- TopNav 小节：
  - 标注品牌字为"可点击回首页"（v1.3 起）
  - ResetLayoutButton 从 MarketOverviewBar 右上角挪到 TopNav 右侧（紧邻 RefreshButton），仅在首页可见
- AddStockCard 小节：
  - search input 外观：pill 形（`rounded-full`）、字号 `10px`、粗体 + placeholder 粗体
  - 小节标注 `(v1.3 起)`

---

## 明确排除

- ResetLayoutButton 自身实现（既有组件复用，不改）
- MarketOverviewBar 内部渲染（不动）
- 其它表单输入框样式（本 sprint 只改 search input）
- i18n / a11y 增强

---

## 预计修改文件（共 4 个）

| # | 文件 | 类型 | 改动 |
|---|---|---|---|
| 1 | `frontend/src/App.tsx` | 修改 | 去掉 ResetLayoutButton 的覆盖层 |
| 2 | `frontend/src/components/features/topnav/TopNav.tsx` | 修改 | 品牌字变链接 + ResetLayoutButton 右侧挂载 |
| 3 | `frontend/src/components/features/dashboard/AddStockCard.tsx` | 修改 | search input pill 样式 |
| 4 | `docs/设计/design-spec.md` | 修改 | TopNav + AddStockCard 两小节备案 |

---

## 可测试的完成标准

| # | 标准 | 层级 |
|---|---|---|
| 1 | 首页 TopNav 右侧按顺序：刷新时间 + RefreshButton + ResetLayoutButton | 手工 |
| 2 | 非首页（/journal /logs）TopNav 右侧不显示 ResetLayoutButton | 手工 |
| 3 | 点击品牌字 `MA150 Tracker` → 跳到 `/` | 手工 |
| 4 | 品牌字视觉（字号 / 字重 / 颜色）与 v1.2.0 一致，仅指针变 pointer | 手工 |
| 5 | AddStockCard 的 search input 为 pill 形、`10px` 字号、粗体 + placeholder 粗体 | 手工 |
| 6 | MarketOverviewBar 区域不再有右上角浮层按钮 | 手工 |
| 7 | design-spec.md 新增 TopNav / AddStockCard 两段备案 | 文档 |
| 8 | `pnpm --filter frontend typecheck` + `build` 通过 | 静态 |

---

## Evaluator 自检清单

- [ ] `pnpm --filter frontend typecheck` 通过
- [ ] `pnpm --filter frontend build` 通过
- [ ] 浏览器确认 6 项视觉标准
- [ ] 切换路由 3 次以上（/, /journal, /logs）确认 ResetLayoutButton 条件渲染无残留
- [ ] AddStockCard 功能回归：搜索结果 popover 正常展开 / 点击添加正常
- [ ] design-spec.md 对应小节已备案

### 代码质量检查
- [ ] App.tsx 移除未使用的 import（`useLocation` 不再需要）
- [ ] 无死代码 / 无 inline 条件渲染冗余
- [ ] AddStockCard 样式类重复值如 `text-[10px] md:text-[10px]` 可简化为单一 `text-[10px]`（保留 md 前缀仅当业务确有断点需求）→ 由 Evaluator 判断是否简化

### 回归测试
- 前端既有路由 / 搜索 smoke 测试
- 起 docker 环境肉眼确认 TopNav 和 Search 视觉

---

⚠️ **反向补契约**：AddStockCard 的 `text-[10px] md:text-[10px]` 是手工 commit 来的样式，Evaluator 需评估是否冗余，若是则简化；但简化属"代码质量"不算功能改动。
