# Sprint Contract：F211-c — News 页 AI 摘要 bar 前端

> 状态：已确认 | 起草：2026-04-28 | 用户确认：2026-04-28（Q1-Q8 全采默认方案）
> 父 Feature：F211 AI Contradiction Detector + News Summarizer + Journal Assistant
> 拆分位置：F211-a1 ✅ done / F211-a2 ✅ done / F211-b ✅ done / **F211-c（本 sprint）** / F211-d
> 依赖：
>   - F208-c ✅（POST /api/ai/{task_type} 统一 endpoint，复用 callAiTask）
>   - F211-a1 ✅（news_summarizer schema + BANNED_PHRASES guardrail 已注册）
>   - F211-a2 ✅（per-task model override 基建，不动后端）
>   - F211-b ✅（AiContradictionsSection 是本 sprint 的结构 / state machine / cache badge 模板）
> 引用文档：
>   - features.json F211 acceptance_criteria："News 页顶部 'AI 摘要'（可选开关）展示 catalyst_summary / sentiment / risks"
>   - design-spec.md line 634（关联 Feature F200–F211 v2.0 AI Layer）
>   - API-CONTRACT.md line 1655-1735（POST /api/ai/{task_type} + meta 字段 + AI 命名空间错误码）
>   - data-mapping.md line 987（taskType 枚举包含 news_summarizer）
>   - backend/app/ai/schemas/news_summarizer.py（input/output Pydantic schema 权威，前端类型与之 1:1 映射）
>   - frontend/src/cockpit/components/AiContradictionsSection.tsx（结构 / 6 态状态机 / cache badge / 关闭按钮模板）
>   - frontend/src/cockpit/lib/api/aiApi.ts（callAiTask 通用 helper，已暴露 AiTaskResponse / AiMeta）
>   - frontend/src/hooks/useNewsArticles.ts（articles 数据源，queryKey=['news', 'articles']，5 天窗口 + localStorage 持久化）
>   - frontend/src/types/news.ts（NewsArticle：title / publishedAt / contentHtml / symbols[] / url / …）
>   - frontend/src/pages/News.tsx（集成宿主，bar 插入 grid 上方）
>   - frontend/eslint.config.js（cross-import 限制：仅 cockpit/* ⇄ workbench/* 互斥；pages → cockpit/lib import 合法）

---

## 0. 背景与定位

F211-a1 已落地 `news_summarizer` Pydantic schema：input `{ articles: NewsArticleItem[1..30], windowDays: int[1..30]=5 }`，output `{ catalystSummary, sentiment: positive|neutral|negative, relevantTickers[≤10], risks[≤5] }`，guardrail 扫描 BANNED_PHRASES。F208-c 已暴露 `POST /api/ai/news_summarizer`。F211-c 在 News 页顶部补齐前端展示。

视觉与交互形态完全对齐 F211-b 落地的 `AiContradictionsSection`：默认 collapsed → 点 trigger → useQuery enabled → POST → 渲染 catalystSummary + sentiment badge + relevantTickers chips + risks list。lazy 触发避免每次进 News 页烧 token（D069 月预算考虑）。

**关键约束**：
1. **不动后端**：schema / endpoint / guardrail 已就绪，本 sprint 0 行后端代码改动。
2. **lazy 触发**：默认 collapsed，关闭后回到 trigger 按钮（不"完全消失"），不持久化 open/closed 状态。
3. **input 数据源**：从 `useNewsArticles` 已有 react-query cache 读 articles，按 publishedAt desc 取前 30；不新增 endpoint，不按 ticker 过滤。
4. **HTML → text 预处理**：用 `DOMParser` strip `contentHtml` → trim → slice(0, 2000)，对应 schema `contentText` 字段约束（min_length=0, max_length=2000）。
5. **import 边界**：`callAiTask` / `AiTaskResponse` / `AiMeta` 从 `@/cockpit/lib/api/aiApi` 直接 import；ESLint 仅约束 cockpit/* ⇄ workbench/* 互斥，pages → cockpit/lib 合法。本 sprint **不做** aiApi.ts 上提到 `frontend/src/lib/api/` 的重构（避免触发 4 处 cockpit 内部 import 改动，超 6 文件预算）。
6. **不引入新依赖**：复用 `@tanstack/react-query` / `@/components/ui/skeleton` / 现有 token / 浏览器原生 `DOMParser` / `crypto.subtle`（用于 deterministicHash）。

---

## 1. 实现范围

### 1.1 包含

#### A. 新建 `AiNewsSummaryBar.tsx`（第 1 文件）

位置：`frontend/src/components/news/AiNewsSummaryBar.tsx`（新目录 `components/news/`）
模板参考：`frontend/src/cockpit/components/AiContradictionsSection.tsx`

**Props**：无（self-contained：内部 useNewsArticles 读 cache）。

```typescript
export function AiNewsSummaryBar(): JSX.Element
```

**内部类型**（与 backend `news_summarizer.py` 1:1 镜像）：

```typescript
type Sentiment = 'positive' | 'neutral' | 'negative'

type NewsArticleItem = {
  title: string         // 1-300
  contentText: string   // 0-2000
  tickers: string[]     // 0-20
  publishedAt: string   // 10-40 chars (ISO)
}

type NewsSummarizerInput = {
  articles: NewsArticleItem[]  // 1-30
  windowDays: number           // 1-30, 默认 5
}

type NewsSummarizerOutput = {
  catalystSummary: string      // 1-500
  sentiment: Sentiment
  relevantTickers: string[]    // 0-10
  risks: string[]              // 0-5
}
```

**6 态状态机**（沿用 AiContradictionsSection 命名）：

| 态 | 触发 | 渲染 |
|---|---|---|
| closed | 初始 / `setOpen(false)` | trigger 按钮 "Generate AI News Summary"（disabled 当 articles 数为 0） |
| loading | `open && (isLoading || isFetching && !data)` | header + 2 行 skeleton（catalystSummary 块 64px / risks 块 40px） |
| error-502 | `open && error && !is409` | "AI 暂不可用" + 关闭按钮 |
| error-409 | `open && error instanceof ApiError && error.status === 409` | "AI 输出被拦截"（红底）+ 关闭按钮 |
| success-with | `open && data && data.output.risks.length > 0` | catalystSummary + sentiment badge + relevantTickers chips（length>0 渲染）+ risks bullet list |
| success-with（risks 0 子分支）| `open && data && data.output.risks.length === 0` | 同上但隐藏 risks 区 |

> success-empty 分支**不存在**：schema 约束 `catalystSummary: min_length=1`，后端永远返回非空摘要。Contract 不留模板。

**输入构造器**（pure function，便于单测）：

```typescript
async function buildSummarizerInput(articles: NewsArticle[]): Promise<NewsSummarizerInput>
```
逻辑：
1. articles 排序：`[...articles].sort((a, b) => b.publishedAt.localeCompare(a.publishedAt))`
2. slice(0, 30)
3. map → `{ title: a.title || 'Untitled', contentText: stripHtml(a.contentHtml ?? ''), tickers: a.symbols.slice(0, 20), publishedAt: a.publishedAt }`
4. windowDays: 5

`stripHtml` helper：
```typescript
function stripHtml(html: string): string {
  if (!html) return ''
  const doc = new DOMParser().parseFromString(html, 'text/html')
  return (doc.body.textContent ?? '').trim().slice(0, 2000)
}
```

**deterministicHash**（queryKey 稳定化，避免不同 articles 命中同一 cache）：
```typescript
async function articlesHash(articles: NewsArticleItem[]): Promise<string>
```
逻辑：JSON.stringify articles 的 `{t: title, p: publishedAt}` 排序后数组 → encodeUTF8 → `crypto.subtle.digest('SHA-256', ...)` → hex 前 16 位。

**queryKey**：`['ai', 'news_summarizer', hash]`，hash 由 `articles.map(...).sort()` 同步派生（用 useMemo + useState 缓存 async hash）。

**staleTime / gcTime**：均 24h（与 trade_plan / contradictions 一致）。

**retry: false**（不自动重试 LLM 失败）。

**enabled**：`open && !isDisabled && hashReady`（hash 异步算完才发起）。

**sentiment badge token**：
- `positive` → bg `color-mix(in srgb, var(--color-success) 20%, transparent)` / fg `var(--color-success)` / 文字 "Positive"
- `neutral` → bg `color-mix(in srgb, var(--color-text-muted) 12%, transparent)` / fg `var(--color-text-secondary)` / 文字 "Neutral"
- `negative` → bg `color-mix(in srgb, var(--color-error) 20%, transparent)` / fg `var(--color-error)` / 文字 "Negative"

> 步骤 1 实测：`--color-success` (#10b981) 与 `--color-error` (#d4183d) 已存在 tokens.css line 28-30。

**relevantTickers chip**：
- 复用 NewsWidget TickerChip 同款样式：`var(--color-surface-muted)` 背景 / `var(--color-border)` 描边 / `--color-text-primary` 文字
- 点击调 `useAppStore((s) => s.setSelectedSymbol)(ticker)`（与 NewsRow 行为一致）
- 0 个 → 整行隐藏（含 label）

**risks 渲染**：
- bullet list（每行 `· {risk}`，`color: var(--color-text-secondary)`，`font-size: var(--font-size-caption)`）
- length === 0 → 整段隐藏

**cache badge**：success header 右侧
- `data.meta.cacheHit === true` → "Cached"
- 否则 → `Generated · ${data.meta.modelUsed}`

**禁用条件**：`articles.length === 0`（来自 useNewsArticles().data）→ trigger button `disabled`，`title="暂无 news"`。

**关闭按钮**：复用 inline `CloseButton` 组件（不抽公共，与 Contradictions 同结构镜像）。

#### B. 新建 `AiNewsSummaryBar.test.tsx`（第 2 文件）

位置：`frontend/src/components/news/__tests__/AiNewsSummaryBar.test.tsx`
框架：`vitest` + `@testing-library/react`

**测试 case（C1-C8，总计 8 用例）**：

| # | 名称 | 断言 |
|---|---|---|
| C1 | renders trigger when closed | `getByTestId('ai-news-summary-trigger')` 存在；点击进 loading |
| C2 | renders skeleton during loading | `getByTestId('ai-news-summary-skeleton-summary')` + `…-risks` |
| C3 | success-with: catalystSummary + sentiment + tickers + risks 全渲染 | byTestId 命中 4 区块；sentiment badge 文字 = "Positive" |
| C4 | success: risks length 0 时不渲染 risks 区 | `queryByTestId('ai-news-summary-risks')` 为 null |
| C5 | success: relevantTickers length 0 时不渲染 tickers 行 | `queryByTestId('ai-news-summary-tickers')` 为 null |
| C6 | error 502 → "AI 暂不可用" + 关闭按钮回到 closed | byText 命中；点击 ✕ 后 trigger 重现 |
| C7 | error 409 → "AI 输出被拦截" | byTestId `ai-news-summary-guardrail-error` |
| C8 | articles 为空 → trigger disabled + tooltip="暂无 news" | `disabled` attribute + title 属性 |

> articles 排序、stripHtml、articlesHash 三个 pure function 在 C1-C8 之外**额外**写 3 个 unit test（共 11 case），用于：
> - sortByPublishedDesc + slice(0,30) 边界
> - stripHtml 处理 null / 空 / 含 HTML / 长度截断
> - articlesHash 同输入同输出 / 不同输入不同 hash

mock 策略：
- `vi.mock('@/cockpit/lib/api/aiApi')` 替换 `callAiTask`
- `vi.mock('@/hooks/useNewsArticles')` 控制 articles 数据
- `vi.mock('@/store/useAppStore')` 替换 `setSelectedSymbol`（用于 ticker chip 点击断言，可选）
- 每个 case 用 `QueryClientProvider` 包裹（fresh QueryClient）

#### C. 修改 `News.tsx`（第 3 文件）

位置：`frontend/src/pages/News.tsx`
变更：~10 行 diff

```diff
+ import { AiNewsSummaryBar } from '@/components/news/AiNewsSummaryBar'

  return (
    <div className="p-4">
+     <div className="mb-3">
+       <AiNewsSummaryBar />
+     </div>
      <div ref={containerRef}>
        ...
```

无其他逻辑改动（layout state / refresh handler / article modal 全部保留）。

#### D. 更新 `features.json`（第 4 文件）

位置：`docs/需求/features.json`

变更：
1. `sub_sprints["F211-c"]: "design_needed"` → `"contract_agreed"`
2. `iteration_history` 追加一条 F211-c contract_agreed 记录（参考 F211-b 同格式）
3. `_meta.active_sprint` → `"F211-c"`

### 1.2 排除

- ❌ 后端 schema / endpoint / guardrail 改动（已在 F211-a1 完成）
- ❌ aiApi.ts 上提到 `frontend/src/lib/api/`（重构需 5+ 文件改动，超预算；本 sprint 直接 cross-import 合法）
- ❌ design-spec.md / data-mapping.md / component-plan.md 更新（本 sprint 视觉规则与 F211-b 一致，无新视觉决策）
- ❌ DECISIONS.md 追加（无非显而易见技术决策；DOMParser / crypto.subtle 均为浏览器原生）
- ❌ tokens / cost 详细数字展示（cache badge 已暗示；详细数据看 ai_memos 表）
- ❌ windowDays 可调控件（写死 5，对齐 useNewsArticles 的 fiveDaysAgoIso）
- ❌ ticker 过滤（按 publishedAt desc 取前 30，不按 selectedSymbol 过滤）
- ❌ open/closed 状态 localStorage 持久化（每次刷新重置为 closed）
- ❌ 平仓 hook / journal_entries.ai_review 迁移 / 月度 cron（属 F211-d）

---

## 2. 预计修改文件清单（共 4 个，远低于 6 上限）

| # | 文件 | 操作 | 估行数 |
|---|------|------|------|
| 1 | `frontend/src/components/news/AiNewsSummaryBar.tsx` | 新建 | ~280 |
| 2 | `frontend/src/components/news/__tests__/AiNewsSummaryBar.test.tsx` | 新建 | ~11 case，~250 |
| 3 | `frontend/src/pages/News.tsx` | 修改 | +6 / -0 |
| 4 | `docs/需求/features.json` | 更新 | sub_sprints + iteration_history + active_sprint |

---

## 3. 完成标准（可测试）

| # | 标准 | 测试层级 | 工具 |
|---|------|---------|------|
| C1 | closed → 点 trigger → loading skeleton | 单元 | vitest + RTL |
| C2 | success-with：catalystSummary + sentiment badge + relevantTickers chips + risks list 全渲染 | 单元 | vitest |
| C3 | risks 长度 0 时不渲染 risks 区，其余正常 | 单元 | vitest |
| C4 | relevantTickers 长度 0 时不渲染 tickers 行 | 单元 | vitest |
| C5 | error 502 → "AI 暂不可用" + 关闭按钮回到 closed | 单元 | vitest |
| C6 | error 409 → "AI 输出被拦截" + 关闭按钮 | 单元 | vitest |
| C7 | articles 为空 → trigger disabled + title="暂无 news" | 单元 | vitest |
| C8 | 关闭按钮回到 closed，再次打开命中 cache（cacheBadge="Cached"） | 单元 | vitest |
| C9 | News.tsx 渲染 bar 在 grid 之上（DOM 顺序） | 集成 | vitest |
| C10 | sortByPublishedDesc / stripHtml / articlesHash pure functions 单测 | 单元 | vitest |
| C11 | tsc --noEmit 0 error；ESLint 我变更文件 0 新增 warning | 静态 | tsc / eslint |
| C12 | 全量回归测试 ≥ 当前基线（259/262），无新增失败 | 回归 | vitest |

---

## 4. Evaluator 自检清单

代码：
- [ ] C1-C12 全过
- [ ] 颜色 / 字体 / 间距 0 硬编码：grep 我新建文件，无 `#[0-9a-fA-F]{3,8}` / `rgb(` / `rgba(`
- [ ] queryKey 含 deterministicHash，不同 articles 集触发独立 cache
- [ ] DOMParser 处理 contentHtml 为 null / undefined / 空字符串边界
- [ ] articles slice ≤ 30（schema cap）；title fallback 'Untitled' 时长度 ≥ 1（schema cap）
- [ ] News.tsx diff ≤ 12 行；只新增 import + bar 容器，不动 layout / handler / modal
- [ ] 无 `console.error` / `console.warn` 遗留
- [ ] enabled gating 正确：open && !isDisabled && hashReady（hash 异步未完成时不发起 query）

文档：
- [ ] features.json 字段更新完整（sub_sprints + iteration_history + active_sprint 三处）
- [ ] claude-progress.txt 追加 F211-c contract_agreed 记录
- [ ] SESSION-HANDOFF.md 更新

回归（不可跳过）：
- [ ] 全量前端 vitest 跑一遍，对比 F211-b 验收基线（~262 total，~3 TopNav 预先存在失败）
- [ ] 失败计数 ≤ 基线，否则打回 Generator
- [ ] consistency-check (mode=interactive) C5 通过：sub_sprints["F211-c"] entry 存在 ↔ 合约文件存在

---

## 5. 开发顺序（Generator 模式）

> ⚠️ 不得跳步、不得颠倒。每完成一步，wip commit + claude-progress.txt 追加。

**步骤 1：预检（不写实现）**
- grep `frontend/src/styles/tokens.css`，确认 `--color-success` / `--color-error` / `--color-text-secondary` / `--color-text-muted` / `--color-input-background` / `--color-border` / `--color-surface-muted` 全存在；不存在则记录降级方案
- 读 `frontend/src/hooks/useNewsArticles.ts`，确认 queryKey 实际为 `['news', 'articles']`
- 读 `backend/app/ai/schemas/news_summarizer.py`，复核 input/output 字段名拼写（NewsArticleItem / NewsSummarizerInput / NewsSummarizerOutput）
- 读 `frontend/src/cockpit/components/AiContradictionsSection.tsx` 完整实现，作为复制起点
- 验证 vitest 环境支持 `DOMParser`（写一个 throwaway test 跑 `new DOMParser().parseFromString('<p>x</p>', 'text/html').body.textContent` → 应返回 "x"；如不支持需在测试 setup 加 jsdom polyfill 或改 mock）

**步骤 2：核心组件（无错误处理）**
- 新建 `frontend/src/components/news/AiNewsSummaryBar.tsx`
- 拷贝 AiContradictionsSection 骨架，改类型 / 改 SectionHeader 标题 / 改 buildInput / 改成功态 JSX
- 实现 stripHtml / sortByPublishedDesc / articlesHash 三个 helper（放同文件顶部，不抽公共）
- 6 态状态机全部分支落地

→ wip commit：`wip(F211-c): AiNewsSummaryBar component skeleton`

**步骤 3：News.tsx 集成**
- 改 News.tsx，import + bar 容器插入 grid 上方
- 手动浏览器验证：进 News 页，bar 显示，trigger 按钮可点（mock 数据下进 loading）

→ wip commit：`wip(F211-c): integrate AiNewsSummaryBar into News page`

**步骤 4：测试**
- 新建 `frontend/src/components/news/__tests__/AiNewsSummaryBar.test.tsx`
- 写 11 case（C1-C8 + 3 helper test），全部通过
- 跑 `pnpm vitest run` 当前文件 → 期望 11/11

→ wip commit：`wip(F211-c): AiNewsSummaryBar tests 11 cases`

**步骤 5：Evaluator 模式（自我切换）**
- 跑全量 `pnpm vitest run`，对比基线
- 跑 `pnpm tsc --noEmit`
- 跑 `pnpm lint`（仅看新增 warning）
- 完成自检清单 §4 全部条目
- 调用 consistency-check skill (mode=interactive)
- phase → needs_review

→ 最终 commit：`feat(F211-c): AiNewsSummaryBar — News 页 AI 摘要 bar 前端`

---

## 6. 开放问题处理记录

Q1-Q8 全采默认方案（用户 2026-04-28 确认）：

| Q | 决策 |
|---|------|
| Q1 关闭后行为 | 变回 trigger 按钮（同 Contradictions） |
| Q2 sentiment 展示 | 纯色 text badge（"Positive"/"Neutral"/"Negative"） |
| Q3 tokens/cost 详细 | 不显式展示，cache badge 暗示 |
| Q4 risks 渲染 | bullet list（`·` 前缀） |
| Q5 relevantTickers 0 个 | 隐藏整行 |
| Q6 windowDays 可调 | 写死 5 |
| Q7 折叠态高度 | trigger ~32px，展开内容驱动 |
| Q8 articles 排序 | publishedAt desc 取前 30，不按 ticker 过滤 |

---

## 7. 待 Generator 阶段验证（步骤 1 预检 fallback）

| 项 | 验证方法 | 不通过时方案 |
|---|---|---|
| `--color-success` / `--color-error` 存在 tokens.css | grep | 已实测存在（line 28-30）；理论无需 fallback |
| useNewsArticles queryKey 实际写法 | 读源码 | 已实测 `['news', 'articles']` |
| jsdom DOMParser 支持 | throwaway test | 不支持则在 vitest setup 加 `jsdom: { url: 'http://localhost' }` 或改用 happy-dom；最坏情况：mock stripHtml |
| crypto.subtle 在测试环境可用 | throwaway test | 不可用则用 fallback：JSON.stringify + simple checksum；测试环境用 `vi.stubGlobal('crypto', ...)` |

---

## 8. 不变约束（铁律）

1. **0 行后端代码改动**：违反 → 立即停止并报告
2. **不动 cockpit 内部任何文件**：违反 → 立即停止
3. **不引入新 npm 依赖**：违反 → 触发新依赖流程（停止 + 报告）
4. **不抽 callAiTask / 不重构 aiApi.ts**：违反 → 超 6 文件预算，立即停止
5. **不修改 useNewsArticles.ts / NewsWidget.tsx / 现有 ArticleModal**：仅消费 cache，不改源
