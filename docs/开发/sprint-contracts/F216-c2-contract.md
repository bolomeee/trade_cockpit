# Sprint Contract：F216-c2 — Weekly Stage Chart Widget（B3 前端）

> 日期：2026-05-14 | 状态：✅ 已确认（用户 NP1-NP10 全部按推荐拍板）
> Feature：F216 Cockpit Phase B — Weekly Stage Layer
> Sub-sprint：F216-c2（Phase B 第 3 子里的前端半段；F216-c 因 6 文件原则拆为 c1=后端 / c2=前端）
> 依赖：F216-c1 needs_review（commit e87a08c — GET /api/cockpit/chart/{ticker}/weekly endpoint 已上线）
> 引用文档：
>   - API-CONTRACT.md §"GET /api/cockpit/chart/{ticker}/weekly"（c1 已落地）
>   - DATA-MODEL.md §"WeeklyStageSnapshot"（字段权威）
>   - DECISIONS.md §D091（Stage 分类细则）
>   - 完整改善计划：/Users/wonderer/.claude/plans/featrue-dev-replicated-goblet.md §Phase B / B3
>   - 参考实现：frontend/src/cockpit/widgets/CockpitChartWidget.tsx（pattern 模板）

---

## 0. 背景与定位

F216-c2 交付前端层：让 c1 后端 endpoint 在 Cockpit 页面可视化。完成后 F216-c 整段完成，Phase B 还差 d/e。

**关键约束（用户已确认 2026-05-14 NP1-NP10 全部按推荐）**：

- **NP1 Stage 标签 UI**：A — widget header 整条背景跟随 stage 色，文字 "AAPL · Stage 2 · Advancing"
- **NP2 Stage 色映射**：A — 复用现有 token（绿/黄/红/灰）
- **NP3 ticker 来源**：A — 复用 `useCockpitStore.selectedTicker`
- **NP4 默认 weeks**：A — 50（与后端 default 一致）
- **NP5 文案**：A — 完全复用 CockpitChartWidget 文案
- **NP6 registry / layout**：B — id=`cockpit.weekly-stage` / category 复用 `chart`（不扩 union）/ 默认位置 x=0, y=43, w=6, h=10
- **NP7 数据不足渲染**：B — weekly_bars 空 → 整 widget 显示 "数据不足"；非空但 stage=0 → 渲染 chart + 灰底
- **NP8 公共 helper 抽取**：C — 本 sprint 复制 pattern 不抽取，作为 follow-up 任务记录
- **NP9 decision price lines**：A — 不渲染（周线粒度不适合）
- **NP10 stage 文本说明**：A — "Stage N · {Label}" 双通道

---

## 1. 实现范围

**包含**：

### 1.1 API client 新建：`frontend/src/cockpit/lib/api/cockpitWeeklyChartApi.ts`

```typescript
import { apiFetch } from '@/lib/api/client'
import type { ChartBarItem, ChartSeriesPoint } from './cockpitChartApi'

export type WeeklyStagePayload = {
  stage: number              // 0=UNKNOWN, 1-4
  weeklyClose: number | null
  weeklyMa10: number | null
  weeklyMa30: number | null
  weeklyMa40: number | null
  slope30W: number | null    // %/week（注意 W 大写，对齐 c1 alias_generator camelCase 输出）
  scanDate: string | null    // ISO date
}

export type WeeklyChartData = {
  ticker: string
  weeklyBars: ChartBarItem[]
  weeklyMas: Record<string, ChartSeriesPoint[]>  // keys: "10" / "30" / "40"
  stage: WeeklyStagePayload
}

const DEFAULT_WEEKS = 50

export type GetCockpitWeeklyChartOptions = {
  weeks?: number
}

export function getCockpitWeeklyChart(
  ticker: string,
  options?: GetCockpitWeeklyChartOptions,
): Promise<WeeklyChartData> {
  const weeks = options?.weeks ?? DEFAULT_WEEKS
  return apiFetch<WeeklyChartData>(`/cockpit/chart/${ticker}/weekly?weeks=${weeks}`)
}
```

**关键点**：
- 复用 `ChartBarItem` / `ChartSeriesPoint` import（已 export from `cockpitChartApi.ts`）
- 注意字段命名：c1 后端用 `alias_generator=to_camel`，`slope_30w` → `slope30W`、`scan_date` → `scanDate`、`weekly_ma_10` → `weeklyMa10`（验证 c1 集成测试样例）
- `apiFetch` 自动抛 ApiError（NOT_FOUND 404 / VALIDATION_ERROR 422）

### 1.2 Widget 新建：`frontend/src/cockpit/widgets/WeeklyStageChartWidget.tsx`

骨架（按 CockpitChartWidget pattern 改造 — 移除 decision price lines / EMA / AVWAP，移除 volume 是可选，但为最小化保留 volume 与日线视觉一致；MA 改为 10/30/40 周线）：

```typescript
import { useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  createChart,
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
  type IChartApi,
  type ISeriesApi,
  type UTCTimestamp,
} from 'lightweight-charts'
import { useCockpitStore } from '@/store/cockpitStore'
import { getCockpitWeeklyChart } from '../lib/api/cockpitWeeklyChartApi'

const WEEKLY_MAS = [10, 30, 40] as const
const DEFAULT_WEEKS = 50

const STAGE_LABELS: Record<number, string> = {
  0: 'Unknown',
  1: 'Base',
  2: 'Advancing',
  3: 'Distribution',
  4: 'Declining',
}

const STAGE_BG_TOKENS: Record<number, string> = {
  0: '--color-text-muted',
  1: '--color-log-warn',
  2: '--color-change-positive',
  3: '--color-log-warn',
  4: '--color-change-negative',
}

const STAGE_BG_FALLBACKS: Record<number, string> = {
  0: '#6b7280',
  1: '#f59e0b',
  2: '#10b981',
  3: '#f59e0b',
  4: '#ef4444',
}

const MA_TOKENS: Record<string, string> = {
  '10': '--color-log-warn',
  '30': '--color-signal-breakout',
  '40': '--color-text-secondary',
}

const MA_FALLBACKS: Record<string, string> = {
  '10': '#f59e0b',
  '30': '#2962ff',
  '40': '#717182',
}

function readToken(name: string, fallback: string): string {
  if (typeof window === 'undefined') return fallback
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback
}

function toTs(date: string): UTCTimestamp {
  return (Date.parse(`${date}T00:00:00Z`) / 1000) as UTCTimestamp
}

export function WeeklyStageChartWidget() {
  const ticker = useCockpitStore((s) => s.selectedTicker)
  const containerRef = useRef<HTMLDivElement | null>(null)

  const chartQuery = useQuery({
    queryKey: ['cockpit-weekly-chart', ticker, DEFAULT_WEEKS],
    queryFn: () => getCockpitWeeklyChart(ticker!, { weeks: DEFAULT_WEEKS }),
    enabled: ticker != null,
    staleTime: 5 * 60 * 1000,
  })

  useEffect(() => {
    const container = containerRef.current
    if (!container || !chartQuery.data) return
    const cd = chartQuery.data
    if (cd.weeklyBars.length === 0) return  // NP7: "数据不足" 分支由 JSX 处理

    // ... createChart + candlestick + volume + 3 MA lines (复用 CockpitChartWidget pattern)
    // 注意：不渲染 decision price lines（NP9）/ 不渲染 EMA / 不渲染 AVWAP
    // 默认可视区：最后 52 周（≈1年）

    return () => { /* observer.disconnect + chart.remove */ }
  }, [chartQuery.data])

  if (!ticker) {
    return <div style={{ /* 复用 CockpitChartWidget 空状态样式 */ }}>请从 Setup Monitor 选择一只股票</div>
  }

  const stagePayload = chartQuery.data?.stage
  const stageColor = stagePayload
    ? readToken(STAGE_BG_TOKENS[stagePayload.stage], STAGE_BG_FALLBACKS[stagePayload.stage])
    : readToken('--color-text-muted', '#6b7280')
  const stageLabel = stagePayload ? STAGE_LABELS[stagePayload.stage] : 'Unknown'
  const headerText = stagePayload
    ? `${ticker} · Stage ${stagePayload.stage} · ${stageLabel}`
    : ticker

  // header 整条 background 用 stageColor（NP1）
  // header 文字白色（确保在彩色背景上可读）
  // chart body 占满剩余空间
  // weeklyBars 为空时 chart body 渲染 "数据不足"（NP7）

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      <div
        data-testid="weekly-stage-header"
        style={{
          padding: '8px 12px',
          background: stageColor,
          color: '#ffffff',
          fontWeight: 'var(--font-weight-medium)',
          fontSize: 'var(--font-size-body)',
          flexShrink: 0,
        }}
      >
        {headerText}
      </div>
      {chartQuery.isPending && <div /* loading */>Loading chart…</div>}
      {chartQuery.isError && <div /* error */>Failed to load chart data</div>}
      {chartQuery.isSuccess && chartQuery.data.weeklyBars.length === 0 && (
        <div /* empty */>数据不足</div>
      )}
      {chartQuery.isSuccess && chartQuery.data.weeklyBars.length > 0 && (
        <div ref={containerRef} data-testid="weekly-chart-container" style={{ flex: 1 }} />
      )}
    </div>
  )
}
```

**关键点**：
- 复用 `useCockpitStore.selectedTicker`（NP3 — Setup Monitor 联动）
- 复用 `CockpitChartWidget` 的 chart 创建 pattern（NP8 — 不抽公共 helper）
- 不渲染 EMA / AVWAP / decision price lines（NP9）
- 默认可视区：最后 52 周（≈1 年），与 CockpitChartWidget 6 月可视区性质一致

### 1.3 Widget 测试新建：`frontend/src/cockpit/widgets/__tests__/WeeklyStageChartWidget.test.tsx`

完全沿用 `CockpitChartWidget.test.tsx` 的 mock pattern（mock `lightweight-charts` / mock `ResizeObserver` / setState `useCockpitStore`）。覆盖 §3 标准 6-12。

### 1.4 API client 测试追加：`frontend/src/cockpit/lib/api/__tests__/cockpitApis.test.ts`

追加 `describe('S4 – cockpitWeeklyChartApi', ...)` 块（参考 S1 cockpitChartApi 写法）：
- default `weeks=50` → 正确 URL
- custom `weeks=30` → 正确 URL
- 404 → throws ApiError NOT_FOUND
- 422 → throws ApiError VALIDATION_ERROR

### 1.5 Registry 修改：`frontend/src/cockpit/CockpitRegistry.ts`

```typescript
import { WeeklyStageChartWidget } from './widgets/WeeklyStageChartWidget'

// COCKPIT_WIDGET_REGISTRY 内追加：
'cockpit.weekly-stage': {
  id: 'cockpit.weekly-stage',
  title: 'Weekly Stage',
  component: WeeklyStageChartWidget,
  defaultLayout: { x: 0, y: 43, w: 6, h: 10, minW: 3, minH: 8 },
  category: 'chart',  // NP6 - 复用现有 category，不扩 union
},
```

### 1.6 Layout 修改：`backend/layouts/cockpit.json`

追加一项（数组末尾）：

```json
{
  "i": "cockpit.weekly-stage",
  "x": 0,
  "y": 43,
  "w": 6,
  "h": 10,
  "minW": 3,
  "minH": 8,
  "moved": false,
  "static": false
}
```

**明确排除（本 sub-sprint 不做）**：

- 任何后端 / DB / API-CONTRACT.md 修改 → 全部 c1 已完成
- 抽取公共 chart helper（NP8 C）→ 作为 follow-up 任务，结尾用 spawn_task 记录
- F216-d setup_service gate UI（前端 SetupMonitorWidget "WS" 列）→ F216-d 范围
- 任何 `cockpit.weekly-stage` 的 e2e / Playwright 测试 → 不在 P0 范围
- 修改 CockpitWidgetCategory union（保持 8 项不变）

---

## 2. 预计修改文件（共 6 个）

| # | 文件 | 改动类型 | 说明 |
|---|------|---------|------|
| 1 | `frontend/src/cockpit/lib/api/cockpitWeeklyChartApi.ts` | 新建 | API client + types |
| 2 | `frontend/src/cockpit/widgets/WeeklyStageChartWidget.tsx` | 新建 | Widget 组件 |
| 3 | `frontend/src/cockpit/widgets/__tests__/WeeklyStageChartWidget.test.tsx` | 新建 | vitest 单元/组件测试 |
| 4 | `frontend/src/cockpit/lib/api/__tests__/cockpitApis.test.ts` | 修改 | 追加 S4 describe 块 |
| 5 | `frontend/src/cockpit/CockpitRegistry.ts` | 修改 | 追加 `cockpit.weekly-stage` manifest（import + entry） |
| 6 | `backend/layouts/cockpit.json` | 修改 | 数组末尾追加 layout 项 |

✅ 6 文件，等于上限。无需二次拆分。

---

## 3. 完成标准（可测试）

| # | 标准描述 | 测试层级 | 工具 |
|---|---------|---------|------|
| 1 | `getCockpitWeeklyChart('AAPL')` 默认请求 `/api/cockpit/chart/AAPL/weekly?weeks=50` | 单元 | vitest mock fetch |
| 2 | `getCockpitWeeklyChart('AAPL', { weeks: 30 })` 请求 URL 含 `weeks=30` | 单元 | vitest |
| 3 | API 404 → `getCockpitWeeklyChart` rejects ApiError code=NOT_FOUND | 单元 | vitest |
| 4 | API 422 → rejects ApiError code=VALIDATION_ERROR | 单元 | vitest |
| 5 | 类型 `WeeklyChartData / WeeklyStagePayload` 字段命名对齐 API-CONTRACT.md camelCase（含 `slope30W` 大写 W / `scanDate` / `weeklyMa10`） | 编译 | tsc |
| 6 | `selectedTicker=null` 时 widget 显示 "请从 Setup Monitor 选择一只股票"，无 fetch | 组件 | vitest |
| 7 | `selectedTicker='NVDA'` + 正常 data → createChart 调用 1 次；addSeries 调用 5 次（candle 1 + volume 1 + MA 3） | 组件 | vitest mock lightweight-charts |
| 8 | `weeklyBars=[]` + `stage.stage=0` → 渲染 "数据不足" 占位，**不**调 createChart；header 显示 "NVDA · Stage 0 · Unknown" + 灰底 | 组件 | vitest |
| 9 | `stage.stage=2` → header background CSS 解析为 `--color-change-positive`（fallback `#10b981`）；文字含 "Stage 2 · Advancing" | 组件 | vitest computed style 或 element.style.background 断言 |
| 10 | `stage.stage=4` → header background `--color-change-negative`（fallback `#ef4444`）；文字含 "Stage 4 · Declining" | 组件 | vitest |
| 11 | `stage.stage=1` 与 `stage.stage=3` → header background 均为 `--color-log-warn`（fallback `#f59e0b`） | 组件 | vitest |
| 12 | ticker 切换 NVDA → CRWD → 旧 chart `.remove()` 被调用，createChart 总共调用 2 次 | 组件 | vitest |
| 13 | `CockpitRegistry.COCKPIT_WIDGET_REGISTRY['cockpit.weekly-stage']` 存在且 component === WeeklyStageChartWidget | 单元 | vitest（可不写专用 test，编译通过即可视为通过；可选补 1 条 registry smoke） |
| 14 | `backend/layouts/cockpit.json` 含 `i: "cockpit.weekly-stage"` 且 x=0, y=43, w=6, h=10 | 人工 | grep |
| 15 | 全量 vitest 回归无新增失败 | 集成 | pnpm test |
| 16 | 全量 pytest 回归无新增失败（应为 0 改动，但仍跑一次保险） | 集成 | uv run pytest backend/tests/ |
| 17 | 浏览器手动 smoke：`pnpm dev` 启动 → 访问 /cockpit → Setup Monitor 点一只 ticker → Weekly Stage widget 出现，header 颜色与 stage 一致，chart 渲染 K 线 + 3 MA；切换 ticker 同步刷新；无 console.error | 手动 | preview_* tools |

---

## 4. Evaluator 自检清单

- [ ] 标准 1-13 vitest 全部通过（`pnpm --filter frontend test`）
- [ ] 标准 14 grep 通过
- [ ] 标准 15 全量 vitest 回归对照基线无新增失败
- [ ] 标准 16 全量 pytest 回归对照基线（c1 = 1001 passed）无新增失败
- [ ] 标准 17 浏览器 smoke 通过（preview_screenshot 留证 stage=2/4 各 1 张）
- [ ] WeeklyStageChartWidget 中**无**对 `cockpitDecisionApi` / `cockpitChartApi`（日线）/ EMA / AVWAP / decision price lines 的调用（grep 验证）
- [ ] 所有颜色 / 字体 / 间距走 CSS var + fallback，无硬编码十六进制（除 fallback 表）
- [ ] 字段命名严格对齐 API-CONTRACT.md camelCase（`slope30W` / `scanDate` / `weeklyMa10/30/40`）
- [ ] `STAGE_LABELS` / `STAGE_BG_TOKENS` / `STAGE_BG_FALLBACKS` 三表 key 完整覆盖 0-4（5 个 entry）
- [ ] 无 console.log / debugger / TODO 残留
- [ ] CockpitWidgetCategory union **未**修改（仍 8 项，复用 'chart'）
- [ ] DECISIONS.md / DATA-MODEL.md / API-CONTRACT.md **未**修改（纯前端 sprint）
- [ ] WeeklyStageChartWidget.tsx 主函数 ≤ 200 行（lightweight-charts setup 较重，放宽到 200；超过须抽 helper 或报告）

---

## 5. 协商点（NP）拍板记录

| # | 议题 | 选项 | 用户拍板 | 落地 |
|---|------|------|---------|------|
| NP1 | Stage 标签 UI | A: header 整条背景 / B: pill badge / C: 边框 | **A** | header `style={{ background: stageColor, color: '#fff' }}` |
| NP2 | 色映射 token | A: 复用现有 / B: 新建专用 | **A** | `--color-change-positive` / `--color-log-warn` / `--color-change-negative` / `--color-text-muted` |
| NP3 | ticker 来源 | A: cockpitStore / B: 独立 input | **A** | `useCockpitStore((s) => s.selectedTicker)` |
| NP4 | 默认 weeks | A: 50 / B: 30 / C: 加 select | **A** | `DEFAULT_WEEKS = 50` |
| NP5 | 文案 | A: 完全复用 / B: 新文案 | **A** | 三态文案逐字复制自 CockpitChartWidget |
| NP6 | registry / layout | A: 新行右侧 / B: 新行左侧 / C: 不入默认 | **B** | id=`cockpit.weekly-stage` / category=`chart` / layout x=0,y=43,w=6,h=10 |
| NP7 | 数据不足渲染 | A: 总渲染 / B: bars 空显示数据不足 / C: stage=0 隐藏 | **B** | `weeklyBars.length===0` → "数据不足"，其他正常渲染 |
| NP8 | 公共 helper 抽取 | A: 复制 / B: 抽取（超 6 文件）/ C: 复制 + follow-up | **C** | 本 sprint 复制 CockpitChartWidget helper（`toTs` / `readToken`），收尾 spawn_task 记录重构任务 |
| NP9 | decision price lines | A: 不渲染 / B: 渲染 | **A** | 不 import `cockpitDecisionApi` |
| NP10 | stage 文本说明 | A: "Stage N · Label" / B: 只 "Stage N" / C: 无文字 | **A** | `STAGE_LABELS` 表（0=Unknown / 1=Base / 2=Advancing / 3=Distribution / 4=Declining） |

---

## 6. 开发顺序（22 步，不得跳步）

> 每完成一步且通过最小验证 → 立即 WIP commit（git add 显式列文件，禁 `-A`）。预计 4 个 WIP commit 节点 + 1 个 Final commit。

### 阶段一：API client（基础数据层）

1. 读 c1 集成测试 `backend/tests/test_cockpit_chart_weekly_router.py`，确认 JSON 响应字段命名 camelCase（特别是 `slope30W` 大写 W）
2. 新建 `frontend/src/cockpit/lib/api/cockpitWeeklyChartApi.ts`：types + `getCockpitWeeklyChart` 函数
3. `pnpm --filter frontend exec tsc --noEmit` 冒烟（无 type error）
4. **WIP commit**：`wip(F216-c2): cockpitWeeklyChartApi + types`
   - 文件：`frontend/src/cockpit/lib/api/cockpitWeeklyChartApi.ts`

### 阶段二：API client 测试

5. 编辑 `frontend/src/cockpit/lib/api/__tests__/cockpitApis.test.ts`，追加 `describe('S4 – cockpitWeeklyChartApi', ...)` 块（4 条 test：default URL / custom weeks / 404 / 422）
6. `pnpm --filter frontend test cockpitApis` 全绿
7. **WIP commit**：`wip(F216-c2): API client tests S4`
   - 文件：`frontend/src/cockpit/lib/api/__tests__/cockpitApis.test.ts`

### 阶段三：Widget 实现

8. 新建 `frontend/src/cockpit/widgets/WeeklyStageChartWidget.tsx`，按 §1.2 骨架完整实现：
   - 顶部常量表（`WEEKLY_MAS` / `STAGE_LABELS` / `STAGE_BG_TOKENS` / `STAGE_BG_FALLBACKS` / `MA_TOKENS` / `MA_FALLBACKS`）
   - helper（`readToken` / `toTs`，复制 CockpitChartWidget）
   - useQuery + useEffect chart 创建（candle + volume + 3 MA）
   - JSX header（背景 stage 色 + 文字白色） + body 4 态（empty / loading / error / 数据不足 / chart）
9. `pnpm --filter frontend exec tsc --noEmit` 冒烟
10. **WIP commit**：`wip(F216-c2): WeeklyStageChartWidget skeleton`
    - 文件：`frontend/src/cockpit/widgets/WeeklyStageChartWidget.tsx`

### 阶段四：Widget 测试

11. 新建 `frontend/src/cockpit/widgets/__tests__/WeeklyStageChartWidget.test.tsx`，按 `CockpitChartWidget.test.tsx` pattern：
    - mock `lightweight-charts`（createChart / Series / LineStyle）
    - mock `ResizeObserver`
    - setState `useCockpitStore`
    - 7-9 条 test 覆盖标准 6-12（empty / chart create / 数据不足 / Stage 2 绿 / Stage 4 红 / Stage 1/3 黄 / ticker 切换）
12. `pnpm --filter frontend test WeeklyStageChartWidget` 全绿
13. **WIP commit**：`wip(F216-c2): WeeklyStageChartWidget tests`
    - 文件：`frontend/src/cockpit/widgets/__tests__/WeeklyStageChartWidget.test.tsx`

### 阶段五：Registry + Layout

14. 编辑 `frontend/src/cockpit/CockpitRegistry.ts`：顶部 import + `COCKPIT_WIDGET_REGISTRY` 追加 `cockpit.weekly-stage` entry
15. 编辑 `backend/layouts/cockpit.json`：数组末尾追加 layout 项
16. `pnpm --filter frontend exec tsc --noEmit` 冒烟（registry import 类型正确）

### 阶段六：浏览器 smoke + 回归

17. `pnpm dev` 启动（用 preview_start，端口 5173）
18. preview_click Setup Monitor 选一只 ticker → preview_screenshot 验证 Weekly Stage widget 出现 + header 颜色正确
19. preview_console_logs 验证无 error
20. 全量 vitest：`pnpm --filter frontend test` — 对照基线无新增失败
21. 全量 pytest：`uv run pytest backend/tests/ -q` — 对照基线 1001 passed 无新增失败

### 阶段七：文档 + 收尾

22. Evaluator 自检清单逐条打勾 → 更新 `features.json`：
    - F216 sub_sprints.F216-c2 → `needs_review`
    - F216 iteration_history 追加 c2 completion 记录
    - active_sprint / active_sprint_phase 更新到 F216-d / design_needed（c2 done + c1 acceptance 走过后再）
    - 调用 consistency-check skill (mode=interactive)：C1（c1+c2 都 done 之前 F216 status 保持 in_progress）/ C4（c2 history 已补）/ C5（sub_sprints F216-c2 ↔ contract 文件存在）
    - 更新 `claude-progress.txt`
    - 生成 `SESSION-HANDOFF.md`（F216-c2 完成 → 下一步 F216-d Contract 协商）
    - **Final commit**：`feat(F216-c2): Weekly Stage Chart Widget`
      - 文件：上述 6 文件 + features.json + claude-progress.txt + SESSION-HANDOFF.md
    - 收尾 `spawn_task` 记录 NP8 follow-up：抽取 `_chartHelpers.ts` 公共文件（toTs / readToken / MA_TOKENS / MA_FALLBACKS）共用于 CockpitChartWidget + WeeklyStageChartWidget

---

## 7. 风险与对策

| 风险 | 概率 | 对策 |
|------|------|------|
| `slope30W` 大写 W 字段名错写成 `slope30w` | 中 | 步骤 1 强制读 c1 测试样例对照；标准 5 tsc 类型检查兜底 |
| lightweight-charts mock 在 vitest 中 timing 不稳定 | 低 | 直接复制 CockpitChartWidget.test.tsx mock pattern，已知稳定 |
| stage 色 header 白字在 `--color-log-warn` 黄底上对比度不足 | 中 | NP1 已锁定白字；如 a11y 工具实测 < 4.5:1 → 后续单独 a11y sprint 优化，本 sprint 不阻塞 |
| `useCockpitStore.selectedTicker=null` 时 header 也要渲染 → 出现"空 stage 灰底带 ticker=null" | 低 | JSX 中 `if (!ticker) return <空状态/>`，提前返回 |
| `weeklyBars.length===0` 时 useEffect 早返但 ResizeObserver 没注册 → 数据后到时 chart 不创建 | 中 | useEffect dep 含 `chartQuery.data`，数据从空变非空时 effect 重跑 |
| cockpit.json 末尾追加破坏 JSON 数组语法（缺逗号 / 多逗号） | 低 | Edit 工具精确替换 `]` 前一项；步骤 16 tsc 不会检测 JSON，靠步骤 17-19 浏览器 smoke 兜底（layout 错位会肉眼可见） |
| 默认 layout 与现有 widget y=43 冲突（action-list y=37 h=6 实际 end=43）| 低 | y=43 紧贴 action-list 下方，无重叠；用户可自由拖动 |

---

## 8. 暂停与恢复指令

如本 sprint 中途中断：
1. WIP commit 当前进度（按 §6 节点）
2. 更新 features.json：`active_sprint_phase` 改为 `in_progress`，iteration_history 追加中断点
3. 生成 SESSION-HANDOFF.md
4. 下个 session 恢复指令：
   > 继续开发 F216-c2，Sprint Contract 已确认。读取 SESSION-HANDOFF.md + docs/开发/sprint-contracts/F216-c2-contract.md，进入 Generator 模式，从开发顺序步骤 [N] 开始。

---

## 9. 完成后联动

- F216-c2 done → F216-c1 / c2 全部 needs_review 或 done → 触发 acceptance skill 走 c1+c2 联合验收（preview_screenshot + 浏览器手动 smoke）
- 验收通过后 → 触发 F216-d Sprint Contract 协商（setup_service gate + setup_snapshots 加列 + 前端 WS 列）
- 父 F216 status 保持 `in_progress`（C1 invariant：d/e 仍 design_needed）
- NP8 follow-up：抽取 `_chartHelpers.ts` 公共文件由 `spawn_task` 记录，后续单独 sprint 处理
