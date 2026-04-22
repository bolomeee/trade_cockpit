# Sprint Contract：F112-b — NewsWidget（Workbench 内新闻卡片列表）

> 状态：SUPERSEDED by F112-b1 + F112-b2（2026-04-22）| 起草：2026-04-22
>
> ## Contract 修订 — 2026-04-22
> **原始决策**：路径 B — 只在 Workbench 加 NewsWidget，不加新路由/导航。
> **变更原因**：验收发现需求理解偏差。用户原始意图为 TopNav 新 News 入口 + 独立 /news 页（grid-layout）+ NewsTable + Chart widget 复用 + ArticleModal + ticker 联动（即我当初给的"路径 A"）。
> **处理**：本合约作废，拆分为：
> - `F112-b1-contract.md` — 导航 + /news 页 + NewsTable（table 形式，删除外链跳转；Workbench 首页移除 NewsWidget）
> - `F112-b2-contract.md` — ArticleModal + news 页 Chart widget + ticker 联动 + DOMPurify
> **commit aa86e7a 的处理**：NewsWidget 组件保留（F112-b1 改造为 table），Workbench 注册与默认布局在 F112-b1 中移除。
> 父 Feature：F112 News Widget
> 依赖：F112-a（后端 `GET /api/news/articles` 已固化）
> 兄弟：F112-c（ArticleModal + Ticker 联动）

---

## 0. Scope 修订（路径 B）

**原 F112-b 范围**：前端导航 +/news 页骨架 + NewsWidget
**修订后（本 Contract）**：仅在 Workbench 注册 NewsWidget。**不加新路由、不改 TopNav**，不做 NewsPage。设计文档缺口（无 Figma、design-spec/component-plan 无 News 章节）由"复用现有 widget 视觉约定"填补，不阻塞开发。

F112-c 继承，同时承担"卡片点击交互"从临时 URL 外跳 → ArticleModal 的切换。

---

## 1. 实现范围

**包含：**

- TS 类型：`NewsArticle`（对齐后端 `NewsArticle` schema，camelCase）
- API 客户端：`getNewsArticles(limit?: number): Promise<NewsArticle[]>`
- React Query hook：`useNewsArticles(limit?: number)`，staleTime 60s（与其它只读 widget 一致）
- 组件 `NewsWidget`：
  - 顶部无 tab / 无 toolbar（本版本极简）
  - 列表渲染 `NewsArticle`：**缩略图（imageUrl 存在时 48×48 圆角）+ 标题单行截断 + 副标题行（`site · 相对时间` / 如 "FMP · 2h ago"）+ 最多 3 个 ticker 小徽章**
  - 单列 vertical stack，内部可滚动
  - 点击卡片 → `window.open(article.url, '_blank', 'noopener,noreferrer')`（临时行为；F112-c 替换为 ArticleModal）
  - 无 url 的卡片不可点击（cursor:default）
  - 状态：`Skeleton`（加载）/ `ErrorState`（错误）/ `EmptyState`（空）— 直接复用 `@/components/common/*` 与 `@/components/ui/skeleton`
  - `limit` 固定 20（与后端默认一致，暂不暴露 UI 控件）
- Widget 注册：`WidgetRegistry.ts` 追加 `'news.articles'` manifest
  - 新增 category `'news'`（扩展 `WidgetCategory` 联合类型）
  - defaultLayout：`{ x: 0, y: 24, w: 4, h: 10, minW: 3, minH: 6 }`（与 scanner/watchlist 靠下，不撞既有布局）
- 视觉：严格使用 `tokens.css` 变量（颜色 / 字号 / 间距），不写硬编码色值
- features.json：F112-b scope 改写为本 Scope；F112-c scope 增"ArticleModal 替换 URL 外跳"一条

**排除：**

- 无 NewsPage / 新路由 / 导航项
- 无 filter / search / pagination UI
- 无 ArticleModal（F112-c）
- 无 ticker 点击跳股票详情（F112-c）
- 无 HTML `contentHtml` 渲染（F112-b 不需要，详情在 modal 里）

---

## 2. 预计修改文件（共 6 个）

| # | 文件 | 类型 | 说明 |
|---|------|------|------|
| 1 | `frontend/src/types/news.ts` | 新建 | `NewsArticle` TS 类型 |
| 2 | `frontend/src/lib/api/news.ts` | 新建 | `getNewsArticles(limit?)` 走 `apiFetch` |
| 3 | `frontend/src/hooks/useNewsArticles.ts` | 新建 | React Query hook，60s staleTime |
| 4 | `frontend/src/workbench/widgets/NewsWidget.tsx` | 新建 | 组件本体，含 4 种状态 |
| 5 | `frontend/src/workbench/WidgetRegistry.ts` | 修改 | 注册 `news.articles` + 新 category |
| 6 | `docs/需求/features.json` | 修改 | F112-b 完成态、F112-c 补说明 |

`claude-progress.txt` 与验收记录不计入。

---

## 3. 视觉规格（本地决策，因 design-spec 缺 News 章节）

颜色 / 字号沿用现有 widget 体感（对照 `WatchlistWidget`、`MarketBreakoutWidget`）：

- 容器：`WidgetShell` 默认 padding
- 卡片：`flex gap-3 p-2 rounded-md hover:bg-muted/50 cursor-pointer`
- 缩略图：`48x48 object-cover rounded`；无图时整块省略（不占位）
- 标题：`text-sm font-medium line-clamp-1 text-foreground`
- 副标题行：`text-xs text-muted-foreground`（`site · 相对时间`）
- ticker 徽章：`Badge variant="secondary" text-[10px]`，最多 3 个，超出显示 `+N`
- 相对时间：`formatDistanceToNow` 若项目有用 `date-fns` 则沿用，否则轻量自写（"Xm / Xh / Xd ago"）

> ⚠️ 本章作为"视觉本地决策"记录，F112 整体 done 后若有 Figma 覆盖以 Figma 为准。

---

## 4. 完成标准

> 方案 1：无自动化前端测试（与项目现有约定一致）。全部通过 `pnpm build`（TS 编译）+ preview 浏览器人工确认。

| # | 标准 | 层级 | 工具 |
|---|------|------|------|
| 1 | `pnpm build` 通过（含 tsc -b） | 静态 | pnpm |
| 2 | `pnpm lint` 无新增错误 | 静态 | eslint |
| 3 | 本机 Workbench 加载 NewsWidget，真实 FMP 数据渲染 3+ 条 | 手动 | preview |
| 4 | 有 imageUrl 的卡片渲染图；无 imageUrl 仅文本 | 手动 | preview 截图 |
| 5 | symbols > 3 时显示前 3 + `+N` | 手动 | preview 截图 |
| 6 | 点击有 url 的卡片在新 tab 打开原文 | 手动 | preview |
| 7 | loading → Skeleton；mock 502 → ErrorState；mock 空 → EmptyState | 手动 | DevTools 断网 / preview |
| 8 | `WIDGET_REGISTRY['news.articles']` category 为 `'news'`，布局不撞既有 widget | 代码审 + 手动 | diff + preview |

---

## 5. Evaluator 自检清单

- [ ] `pnpm build` 通过
- [ ] `pnpm lint` 无新增错误
- [ ] 颜色/字号只用 tokens（无硬编码色）
- [ ] 无 `console.error` 遗留
- [ ] API 字段命名对齐 API-CONTRACT.md News 章节（camelCase）
- [ ] 无死代码 / 无硬编码魔法值（`DEFAULT_LIMIT=20`、`MAX_TICKER_BADGES=3` 为常量）
- [ ] 单函数 ≤ 50 行
- [ ] 无 `any`（TS 严格）
- [ ] `defaultLayout` 不与其它 widget y-轴重叠冲突（实测加载后布局正常）

### 回归测试

| 测试范围 | 通过 | 失败 |
|---------|------|------|
| F112-b | N/N | 0 |
| 全量前端 `pnpm test` | ?/? | ? |

---

## 6. 非目标 / 延后

- **相对时间库**：若 `date-fns` 未安装，本 Sprint 写一个 60 行以内的轻量 formatter；后续若多处需要再引入依赖（单独 DECISIONS）
- **ArticleModal / ticker 点击跳转**：F112-c
- **按 ticker 过滤新闻**：F112+1
- **分页 / 无限滚动**：v1.3 后看需求

---

## 7. 开发顺序

1. `types/news.ts` → `lib/api/news.ts` → `hooks/useNewsArticles.ts`
2. `NewsWidget.tsx`（含 4 种状态）
3. 组件测试
4. `WidgetRegistry.ts` 注册
5. 本机 `pnpm dev` 实测打真实后端
6. features.json 更新
