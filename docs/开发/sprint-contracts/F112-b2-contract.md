# Sprint Contract：F112-b2 — ArticleModal + Chart widget 复用 + ticker 联动

> 状态：draft | 起草：2026-04-22
> 父 Feature：F112 | 依赖：F112-b1（/news 页 + NewsTable 已就绪）

---

## 1. 实现范围

**包含：**

- 新组件 `ArticleModal`：
  - Portal 渲染到 `document.body`
  - 背景遮罩 `rgba(0,0,0,0.5)`，点击遮罩关闭
  - 卡片居中，圆形关闭按钮（`w-8 h-8 rounded-full` + lucide `X` icon），右上角
  - 内容：`title` / `site · author · publishedAt` / `contentHtml` 渲染（**必须 sanitize**）/ tickers 行（可点击）
  - `Escape` 键关闭；`aria-modal="true"`；焦点陷阱（本 Sprint 接受简化实现：打开时聚焦关闭按钮，关闭后还原）
- `DOMPurify` 引入：sanitize `contentHtml`
  - **新依赖决策**：按规则 9，正式记录到 `DECISIONS.md`；API 来源 Context7
- `NewsWidget`（table）行为升级：
  - 行 `cursor: pointer`；点击触发 `onOpenArticle(article)`
  - 支持受控 props：`onOpenArticle?: (a: NewsArticle) => void`
- News 页新增 `news.chart` widget：
  - 复用现有 `ChartWidget` 组件（`src/workbench/widgets/ChartWidget.tsx`）— 不拷贝
  - 注册表新增 manifest：`id: 'news.chart'`, category: `'news'`
  - 默认布局调整：NewsTable `{x:0 y:0 w:8 h:14}` + Chart `{x:8 y:0 w:4 h:14}`
- ticker 点击联动：
  - modal 内 ticker chip 变为按钮；点击调用 `useAppStore.setSelectedSymbol(ticker)` → 关闭 modal
  - `ChartWidget` 已有从 `useAppStore.selectedSymbol` 读取逻辑（首页也是这么用），自动切换
  - **当日数据复用**：F111-a `daily_payload_cache` 已在后端生效，前端走 `getStockChart(ticker)` 即可（React Query 同 key 命中缓存；后端也命中 DB 缓存）
- NewsPage：
  - 维护 `selectedArticle` 本地 state；传给 NewsWidget 的 `onOpenArticle`
  - 渲染 ArticleModal（受控 open / onOpenChange）

**排除：**

- ArticleModal 的 AA 级完整键盘陷阱（Radix FocusScope 可选未来升级）
- 按 ticker 过滤新闻（F112+1）
- Modal 内的"相关新闻"推荐

---

## 2. 预计修改文件（共 6 个）

| # | 文件 | 类型 | 说明 |
|---|------|------|------|
| 1 | `frontend/package.json` + `pnpm-lock.yaml` | 修改 | 新依赖 `dompurify` + `@types/dompurify`（记 1 个文件对） |
| 2 | `frontend/src/components/common/ArticleModal.tsx` | 新建 | 遮罩 + 圆形关闭 + sanitize 渲染 + ticker 按钮 |
| 3 | `frontend/src/workbench/widgets/NewsWidget.tsx` | 修改 | 行 onClick → props 回调；导出 `NewsTableProps` |
| 4 | `frontend/src/workbench/WidgetRegistry.ts` | 修改 | 新增 `news.chart` manifest；调整 defaultLayout |
| 5 | `frontend/src/pages/News.tsx` | 修改 | 状态管理 + ArticleModal 渲染 |
| 6 | `docs/系统设计/DECISIONS.md` | 修改 | 新增决策：引入 DOMPurify 理由 + 版本 |

---

## 3. 完成标准

| # | 标准 | 层级 | 工具 |
|---|------|------|------|
| 1 | `pnpm build` / `pnpm lint` 通过 | 静态 | pnpm |
| 2 | 点击 NewsTable 行 → modal 弹出，背景 50% 透明 | 手动 | preview |
| 3 | 关闭按钮圆形且可点击关闭；Escape 键可关闭 | 手动 | preview |
| 4 | Modal 内 `contentHtml` 正常渲染（至少图片/段落/列表），无 XSS payload 通过 | 手动 | preview + 手工插入 `<script>` 测试 |
| 5 | Modal 内 ticker 可点击 → modal 关闭 + News 页 Chart widget 切换到该 ticker | 手动 | preview |
| 6 | 同一 ticker 二次点击（同日内）走缓存：DevTools Network 无重复 `/api/stocks/{ticker}/chart` 请求，或 Response header 显示缓存命中（F111-a 日志） | 手动 | preview + DevTools |
| 7 | News 页布局可拖动（Table + Chart 两个 widget） | 手动 | preview |
| 8 | DECISIONS.md 已追加 DOMPurify 决策条目 | 手动 | diff |

---

## 4. 非目标

- Chart widget 在 news 页的二级状态（例如专属时间范围）— 沿用 ChartWidget 默认行为
- Modal 内 tickers 多选跳转（只支持单击单个）
