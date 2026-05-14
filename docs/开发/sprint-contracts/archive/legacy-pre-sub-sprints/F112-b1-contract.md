# Sprint Contract：F112-b1 — News 页骨架（导航 + /news 路由 + NewsTable widget）

> 状态：contract_agreed | 起草：2026-04-22
> 父 Feature：F112 | 依赖：F112-a（后端）、F112-b（老合约，本合约取代其"路径 B"决策）
> 兄弟：F112-b2（ArticleModal + Chart widget 复用 + ticker 联动）

---

## 0. 背景（为何取代老 F112-b）

老 F112-b 选了"路径 B — 只在 Workbench 加 widget，不新增路由/导航"。验收时发现与用户原始意图不符：用户要的是 **TopNav 增 News 入口 → 独立 /news 页 → grid-layout 内放 NewsTable + Chart，点击行开 modal，点击 ticker 切 chart**。老 F112-b 的 commit（aa86e7a）需要在本合约执行过程中部分回滚（把 NewsWidget 从 Workbench 默认布局移除）。NewsWidget 组件本身保留并重写为 table 形式。

老 F112-b 合约标记为 **superseded**，不再执行。

---

## 1. 实现范围

**包含：**

- TopNav 新增 `News` 入口（与 `Journal`、`Logs` 同级），高亮规则沿用现有 NavLink 模式
- 新增路由 `/news`，懒加载 `NewsPage` 组件（与 `Workbench / Journal / Logs` 一致懒加载）
- NewsPage：`react-grid-layout` 容器，首版仅包含一个 widget（`news.table`）
- **widget 注册重构**：`WIDGET_REGISTRY` 保留单一真相源，按 `category` 分派：
  - `getDefaultLayout()` 改名为 `getWorkbenchDefaultLayout()`，过滤掉 `category === 'news'`（效果：Workbench 首页不再显示 NewsWidget）
  - 新增 `getNewsDefaultLayout()`，只返回 `category === 'news'` 的 manifest
  - Workbench.tsx 改用新函数名；`news.articles` manifest id 重命名为 `news.table`
- **布局持久化独立**：新建 `useNewsLayoutStore`（zustand persist，key = `ma150.news.layouts.v1`），与 `useLayoutStore` 并列互不干扰
- NewsWidget 重构为 **table**（取代原卡片列表）：
  - 列：`Date` | `Site` | `Title` | `Tickers`
  - Date 列：相对时间（沿用 `formatRelativeTime`）
  - Title 列：`line-clamp-1`
  - Tickers 列：最多 3 个小徽章 + `+N`（沿用现有逻辑）
  - 整行 `cursor:default`（点击不跳外链，本合约**不做** modal；F112-b2 接）
  - 保留 loading / error / empty 三态
  - 沿用 `@/components/ui/table` 与 tokens.css
- `features.json`：F112 subtasks 中 `F112-b` 改为 `F112-b1` + `F112-b2`；F112-b1 phase 迁移按本 Sprint

**排除：**

- ArticleModal（F112-b2）
- Chart widget 放置到 News 页（F112-b2）
- 点击 ticker 切 chart（F112-b2）
- 点击行跳外链（旧行为废弃，本 Sprint 不保留）
- ticker 点击事件（F112-b2）

---

## 2. 预计修改文件（共 7 个，超上限 1 个；理由：新路由 + 新页面 + 注册表重构三者同属"骨架"，强行拆分会产生半成品页面不可演示）

| # | 文件 | 类型 | 说明 |
|---|------|------|------|
| 1 | `frontend/src/App.tsx` | 修改 | 新增 `<Route path="/news" element={<News />} />`，懒加载 |
| 2 | `frontend/src/components/features/topnav/TopNav.tsx` | 修改 | 新增 `News` NavLink（置于 Journal 与 Logs 之间或同组末尾） |
| 3 | `frontend/src/pages/News.tsx` | 新建 | grid-layout 容器，参照 Workbench.tsx，使用 `getNewsDefaultLayout()` + `useNewsLayoutStore` |
| 4 | `frontend/src/pages/useNewsLayoutStore.ts` | 新建 | zustand persist，key `ma150.news.layouts.v1` |
| 5 | `frontend/src/workbench/widgets/NewsWidget.tsx` | 修改 | 卡片列表 → table（列：Date/Site/Title/Tickers）；删除外链跳转；保留三态；id 引用变化 |
| 6 | `frontend/src/workbench/WidgetRegistry.ts` | 修改 | manifest id `news.articles` → `news.table`；title `Market News` → `News`；`getDefaultLayout` → `getWorkbenchDefaultLayout`（过滤 news）+ 新增 `getNewsDefaultLayout` |
| 7 | `frontend/src/workbench/Workbench.tsx` | 修改 | 调用处改名 |

**额外**（不计入 7 文件）：
- `docs/需求/features.json`：F112 subtasks 结构更新
- 老 `docs/开发/sprint-contracts/F112-b-contract.md` 文件头状态改为 `superseded`

---

## 3. 布局默认值

`news.table` 默认 layout：`{ x: 0, y: 0, w: 12, h: 14, minW: 6, minH: 6 }`（整行铺满，后续 F112-b2 加 Chart 时再调整）

---

## 4. 完成标准

| # | 标准 | 层级 | 工具 |
|---|------|------|------|
| 1 | `pnpm build`（含 tsc -b）通过 | 静态 | pnpm |
| 2 | `pnpm lint` 无新增错误 | 静态 | eslint |
| 3 | 访问 `/`（首页 Workbench）**不再**显示 News widget | 手动 | preview |
| 4 | TopNav 显示 `News` 入口，点击跳转 `/news` | 手动 | preview |
| 5 | `/news` 页面渲染 NewsTable，列 Date/Site/Title/Tickers 均可见 | 手动 | preview |
| 6 | Table 展示 20 条真实 FMP 数据 | 手动 | preview |
| 7 | loading 态 Skeleton / 错误态 ErrorState / 空态 EmptyState 全部实现 | 代码审 | diff |
| 8 | 老 `ma150.workbench.layouts.v5` localStorage 条目存在用户访问首页**不崩**（Registry 按 id 查找，找不到就跳过） | 手动 | preview |
| 9 | `/news` 页 layout 可拖动且持久化（刷新后位置保持） | 手动 | preview |

---

## 5. Evaluator 自检清单

- [ ] `pnpm build` / `pnpm lint` 通过
- [ ] 无 `console.error`
- [ ] 颜色/字号仅使用 tokens / tailwind 默认；无硬编码色值
- [ ] 无死代码；未使用的 import 清理
- [ ] 单函数 ≤ 50 行
- [ ] Workbench 的 localStorage 布局迁移兼容：旧 layout 中若有 `news.articles` 条目，Workbench 渲染时 `WIDGET_REGISTRY['news.articles']` 查不到 → 降级为 `<div key={item.i} />`（Workbench.tsx 现有逻辑已支持）
- [ ] News 页 layout store 与 Workbench store 独立持久化（localStorage 两个 key）
- [ ] NewsTable 空态文案为 `No news yet`（或等价）

---

## 6. 开发顺序

1. `WidgetRegistry.ts`：重命名 + 分派函数 → Workbench.tsx 更新调用
2. `useNewsLayoutStore.ts` 新建
3. `pages/News.tsx` 新建（复制 Workbench.tsx 模板，换 store + registry 函数）
4. `App.tsx` 加路由 / `TopNav.tsx` 加链接
5. `NewsWidget.tsx` 重构为 table
6. build + lint + preview 手动验证（B1–B9）
7. features.json 更新
8. commit

---

## 7. 非目标（留给 F112-b2）

- ArticleModal（50% 透明遮罩 + 圆形关闭按钮）
- News 页新增 `news.chart` widget 实例（复用 `ChartWidget` 组件 + `ChartWidget` 的 F111-a 当日缓存路径）
- 点击表格行 → 打开 ArticleModal
- 点击 modal 中 ticker → 关闭 modal + `useAppStore.setSelectedSymbol(ticker)` → news 页 chart widget 切换
