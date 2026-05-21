---
status: confirmed
drafted_at: 2026-05-21
confirmed_at: 2026-05-21
sprint: F219-b
parent_feature: F219
file_count: 6 (6-file budget, no exception needed)
np_decisions: NP-1/2/3/4 全部 A（用户 2026-05-21 一次性按推荐确认）
---

# F219-b Sprint Contract — MACD Divergence 前端切片（PositionList ⚠️ + SetupMonitor 'MACD+' chip）

> 生成：2026-05-21 | 状态：✅ 已确认 → 进入 Generator（下一 session）
> Feature：[F219](docs/需求/features.json) Cockpit Phase E — MACD Divergence 早衰报警（最小化方案）
> Sub-sprint：F219-b（Phase E 2 sub-sprint 第 2 个；前端闭环）
> 前置：F219-a done（后端 indicator + persist + endpoint schema 已上线）
> 下游：F219 整体 needs_review → acceptance

> 引用文档：
> - [F219-a-contract.md](docs/开发/sprint-contracts/F219-a-contract.md) §0 §7 — bearish/bullish 语义与本切片范围定义
> - [API-CONTRACT.md §GET /api/cockpit/setup-monitor 1176/1195](docs/系统设计/API-CONTRACT.md) — `macdDivergence` items[] 字段
> - [API-CONTRACT.md §GET /api/cockpit/positions 1656/1669](docs/系统设计/API-CONTRACT.md) — `macdDivergence` items[] 字段
> - [SetupTypeBadge.tsx](frontend/src/cockpit/components/SetupTypeBadge.tsx) — chip 风格（inline span + `font-size-badge`）样板
> - [_positionListRow.tsx](frontend/src/cockpit/widgets/_positionListRow.tsx) — `PositionRow` 渲染入口（ticker cell 注入 ⚠️）
> - [SetupMonitorWidget.tsx](frontend/src/cockpit/widgets/SetupMonitorWidget.tsx) — `SetupRow` Setup 列（SetupTypeBadge 右侧追加 chip）
> - [tokens.css](frontend/src/styles/tokens.css) — `--color-change-positive`（'MACD+' 绿）与 `--color-text-muted`

---

## 0. 背景与定位

F219-a 已在 EOD setup 计算管线中持久化 `setup_snapshots.macd_divergence ∈ {'bearish', 'bullish', null}`，并通过 `GET /api/cockpit/setup-monitor` 与 `GET /api/cockpit/positions` 的 items[] 以 `macdDivergence` 暴露。

F219-b 仅做"两个 widget 内联渲染"：
- **PositionListWidget**：OPEN 持仓 + `macdDivergence === 'bearish'` → ticker 后内联 ⚠️ + native `title` tooltip
- **SetupMonitorWidget**：`setupType === 'CAPITULATION'` + `macdDivergence === 'bullish'` → Setup 列 SetupTypeBadge 右侧 'MACD+' 绿色 chip

**永不做**（保持最小化）：不动 ready 8-AND gate；不影响 setup filter tabs 统计；不接入 CockpitChart overlay；不接入 DecisionPanel / AI 区块；不抽 MacdDivergenceBadge 组件。

---

## 1. 实现范围

### 1.1 API 类型同步（2 文件）

`frontend/src/cockpit/lib/api/setupMonitorApi.ts`：

```ts
export type MacdDivergence = 'bearish' | 'bullish' | null

export type SetupItem = {
  // ... 现有字段
  weeklyStage: number | null
  macdDivergence: MacdDivergence  // ← 新增
}
```

`frontend/src/cockpit/lib/api/cockpitPositionsApi.ts`：

```ts
import type { MacdDivergence } from './setupMonitorApi'  // 复用 type

export type Position = {
  // ... 现有字段
  updatedAt: string
  macdDivergence: MacdDivergence  // ← 新增
}
```

⚠️ `MacdDivergence` type 定义在 `setupMonitorApi.ts`（前端 widget 中先出场），`cockpitPositionsApi.ts` 仅 import；不新建文件。

### 1.2 PositionList ⚠️ bearish 标识（_positionListRow.tsx）

`PositionRow` 中 ticker cell（第 1 列）渲染：

```tsx
<td style={{ ...tdBase, fontWeight: 'var(--font-weight-medium)' }}>
  {position.ticker}
  {position.status === 'OPEN' && position.macdDivergence === 'bearish' && (
    <span
      data-testid={`macd-bearish-${position.id}`}
      title="bearish divergence detected, consider partial exit at 2R"
      aria-label="bearish divergence warning"
      style={{
        marginLeft: '4px',
        fontSize: 'var(--font-size-caption)',
        cursor: 'help',
      }}
    >
      ⚠️
    </span>
  )}
  <div style={{ fontSize: 'var(--font-size-caption)', color: 'var(--color-text-muted)' }}>
    ({position.shares} sh)
  </div>
</td>
```

- 仅 `status === 'OPEN'` 且 `macdDivergence === 'bearish'` 时显示（NP-3 收紧触发，closed 持仓 / bullish / null 一律不渲染）。
- 用 native `title` 属性提供 tooltip，零新增依赖；`aria-label` 给屏幕阅读器，`cursor: 'help'` 提示可悬浮。
- 不新增列；不动 8 列布局；不动 RiskSummaryBar。

### 1.3 SetupMonitor 'MACD+' chip（SetupMonitorWidget.tsx）

`SetupRow` 中 Setup 列（现：`<SetupTypeBadge value={item.setupType} />`）改为：

```tsx
<td style={tdStyle}>
  <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
    <SetupTypeBadge value={item.setupType} />
    {item.setupType === 'CAPITULATION' && item.macdDivergence === 'bullish' && (
      <span
        data-testid={`macd-plus-${item.ticker}`}
        title="bullish divergence — auxiliary evidence for CAPITULATION (not part of ready gate)"
        aria-label="bullish divergence chip"
        style={{
          color: 'var(--color-change-positive)',
          fontSize: 'var(--font-size-badge)',
          fontWeight: 'var(--font-weight-medium)',
          letterSpacing: '0.04em',
        }}
      >
        MACD+
      </span>
    )}
  </span>
</td>
```

- 仅 `setupType === 'CAPITULATION' && macdDivergence === 'bullish'` 时显示（NP-3 收紧触发）。
- 风格与 SetupTypeBadge 对齐：`font-size-badge`、`font-weight-medium`、`letter-spacing: 0.04em`，颜色用 `--color-change-positive`（绿）。
- 不动 Setup 列宽（`width="14%"`）；inline-flex `gap: 4px` 紧凑摆放。
- **不影响 readySignal 计算与 ready filter tabs**（chip 仅是视觉点缀）。

### 1.4 测试（2 文件）

`PositionListWidget.test.tsx` 新增 3 用例：

1. `macdDivergence === 'bearish' && status === 'OPEN'` → `screen.getByTestId('macd-bearish-1')` 存在，title 含 `'bearish divergence detected, consider partial exit at 2R'`
2. `macdDivergence === 'bearish' && status === 'CLOSED'` → testid 不存在（NP-3 收紧）
3. `macdDivergence === 'bullish' / null` → testid 不存在

`SetupMonitorWidget.test.tsx` 新增 3 用例：

1. `setupType === 'CAPITULATION' && macdDivergence === 'bullish'` → `screen.getByTestId('macd-plus-AAPL')` 存在，文本 `'MACD+'`
2. `setupType === 'BREAKOUT' && macdDivergence === 'bullish'` → testid 不存在（NP-3 收紧）
3. `setupType === 'CAPITULATION' && macdDivergence === 'bearish' / null` → testid 不存在；同 fixture 中 readySignal 行为零变化（ready filter 数量与无 macdDivergence 字段时一致）

### 1.5 明确排除（本 sprint 不做）

- 任何后端文件（已在 F219-a 完成）
- CockpitChartWidget 的 MACD overlay / 任何 chart 标注
- DecisionPanelWidget / AI Contradictions / AiSetupExplainerPopover 接入 'MACD+' 信号
- 单独 `MacdDivergenceBadge` 组件抽取（NP-4 已决：不抽）
- PositionList 显示 bullish chip / SetupMonitor 显示 bearish 标识（NP-3 已决：收紧）
- 改 SetupSummary / RiskSummaryBar / setup filter tabs 的统计口径

---

## 2. 预计修改文件（共 6 个 — 6-file 内）

| 文件路径 | 改动类型 | 说明 |
|---------|---------|------|
| `frontend/src/cockpit/lib/api/setupMonitorApi.ts` | 修改 | 导出 `MacdDivergence` type；`SetupItem` 加 `macdDivergence` 字段 |
| `frontend/src/cockpit/lib/api/cockpitPositionsApi.ts` | 修改 | import `MacdDivergence`；`Position` 加 `macdDivergence` 字段 |
| `frontend/src/cockpit/widgets/_positionListRow.tsx` | 修改 | `PositionRow` ticker cell 注入 ⚠️ span（OPEN + bearish） |
| `frontend/src/cockpit/widgets/SetupMonitorWidget.tsx` | 修改 | `SetupRow` Setup 列改为 inline-flex；CAPITULATION + bullish 渲染 'MACD+' chip |
| `frontend/src/cockpit/widgets/__tests__/PositionListWidget.test.tsx` | 修改 | `makePosition` 默认加 `macdDivergence: null`；新增 3 用例（bearish OPEN 显示 / bearish CLOSED 不显示 / bullish/null 不显示） |
| `frontend/src/cockpit/widgets/__tests__/SetupMonitorWidget.test.tsx` | 修改 | fixture items 加 `macdDivergence`；新增 3 用例（CAP+bullish 显示 / BREAKOUT+bullish 不显示 / CAP+bearish 不显示 + ready 数量零变化） |

⚠️ **6 文件**：恰好 6-file 默认上限，**无需例外授权**。

⚠️ **禁用 `git add -A`**：每个 wip commit 显式列文件名。

---

## 3. 文档同步（开发后必做）

| 阶段 | 文档 | 改动 |
|------|------|------|
| **开发后** | `docs/设计/design-spec.md` | 新增 §F219-b MACD Divergence 视觉规格段落，包含：<br>① PositionList — ticker 后 ⚠️ emoji（仅 OPEN + bearish），`margin-left: 4px`，`font-size: var(--font-size-caption)`，`cursor: help`，title 文案锁定 `'bearish divergence detected, consider partial exit at 2R'`<br>② SetupMonitor — Setup 列 SetupTypeBadge 右侧 'MACD+' chip（仅 CAPITULATION + bullish），`color: var(--color-change-positive)`，`font-size: var(--font-size-badge)`，`font-weight: medium`，`letter-spacing: 0.04em`，title 文案锁定 `'bullish divergence — auxiliary evidence for CAPITULATION (not part of ready gate)'`<br>③ 明确：closed 持仓 / 非 CAPITULATION 行 / bullish 持仓 / bearish setup 一律不渲染 |
| **开发后** | `docs/设计/data-mapping.md` | PositionList / SetupMonitor 字段映射表新增 `macdDivergence` 行：`API 字段 macdDivergence: 'bearish' \| 'bullish' \| null → 视觉：bearish ⚠️ (PositionList only, OPEN) / bullish 'MACD+' chip (SetupMonitor only, CAPITULATION) / 其他不渲染` |
| **开发后** | `DECISIONS.md` | 追加 **D100**：F219-b 不抽 MacdDivergenceBadge 组件——本切片仅 2 处使用（PositionList emoji / SetupMonitor 行内 chip），且 CockpitChart overlay / DecisionPanel 经 F219 contract 排除，无下游复用点；抽组件会成为虚假复用抽象 |
| **开发后** | `DECISIONS.md` | 追加 **D101**：F219-b 触发规则收紧（NP-3）——PositionList 仅 OPEN + bearish 显示 ⚠️；SetupMonitor 仅 CAPITULATION + bullish 显示 'MACD+'。closed 持仓显示 ⚠️ 会被误读为历史问题报警；非 CAPITULATION 行显示 'MACD+' 会被误读为进了 ready gate；两者都是反指 |

---

## 4. 可测试的完成标准

| # | 标准描述 | 测试层级 | 工具 |
|---|---------|---------|------|
| 1 | `SetupItem.macdDivergence` 类型为 `'bearish' \| 'bullish' \| null`；TS 编译无错 | 编译 | tsc |
| 2 | `Position.macdDivergence` 同款；从 `setupMonitorApi` import `MacdDivergence` 复用 | 编译 | tsc |
| 3 | PositionListWidget：fixture `status='OPEN', macdDivergence='bearish'` → DOM 中 `[data-testid="macd-bearish-{id}"]` 存在，`title` 属性等于 `'bearish divergence detected, consider partial exit at 2R'` | 单元 | vitest + RTL |
| 4 | PositionListWidget：fixture `status='CLOSED', macdDivergence='bearish'` → testid 不存在（query 返回 null） | 单元 | vitest + RTL |
| 5 | PositionListWidget：fixture `status='OPEN', macdDivergence='bullish'` 与 `null` → testid 均不存在 | 单元 | vitest + RTL |
| 6 | SetupMonitorWidget：fixture `setupType='CAPITULATION', macdDivergence='bullish'` → `[data-testid="macd-plus-{ticker}"]` 存在，文本 `'MACD+'`，颜色 token `var(--color-change-positive)` | 单元 | vitest + RTL |
| 7 | SetupMonitorWidget：fixture `setupType='BREAKOUT', macdDivergence='bullish'` → testid 不存在 | 单元 | vitest + RTL |
| 8 | SetupMonitorWidget：fixture `setupType='CAPITULATION', macdDivergence='bearish' / null` → testid 不存在 | 单元 | vitest + RTL |
| 9 | SetupMonitorWidget：同 fixture 加/去 `macdDivergence` 字段，ready filter tab `Ready N` 数字、'Near' tab 数字均不变（回归 readySignal 行为零变化） | 单元 | vitest + RTL |
| 10 | `pnpm tsc --noEmit` 全量通过；现有 `frontend/src/cockpit/widgets/__tests__` 所有用例 100% 通过（无新增失败） | 集成回归 | pnpm |
| 11 | `pnpm test` 全量前端测试无新增失败 | 回归 | pnpm |

---

## 5. 已确认的协商点（2026-05-21）

| # | 协商点 | 决定 |
|---|--------|------|
| **NP-1** | bearish 标识视觉 | **A**：Emoji ⚠️ + native `title` tooltip，零新增组件；`cursor: help` + `aria-label` |
| **NP-2** | 'MACD+' chip 视觉 | **A**：'MACD+' 文案，行内 span，`color-change-positive` 绿，`font-size-badge` |
| **NP-3** | 触发收紧 | **A**：PositionList 仅 OPEN+bearish；SetupMonitor 仅 CAPITULATION+bullish；其他一律不渲染 |
| **NP-4** | 文档同步 + 组件抽取 | **A**：design-spec.md + data-mapping.md 双同步；**不**抽 MacdDivergenceBadge 组件（CLAUDE.md "no premature abstraction" + F219 下游已排除） |

---

## 6. Evaluator 自检清单

开发完成后，Evaluator 模式逐条检查：

- [ ] `cd frontend && pnpm tsc --noEmit` 通过
- [ ] `cd frontend && pnpm test src/cockpit/widgets/__tests__/PositionListWidget.test.tsx` 全通过（含新增 3 用例）
- [ ] `cd frontend && pnpm test src/cockpit/widgets/__tests__/SetupMonitorWidget.test.tsx` 全通过（含新增 3 用例）
- [ ] `cd frontend && pnpm test` 全量前端无新增失败
- [ ] `cd frontend && pnpm lint` 无新增 warning（如项目配置）
- [ ] readySignal / setup filter tabs 行为零变化（验收标准 #9 通过）
- [ ] design-spec.md / data-mapping.md 已按 §3 完成同步
- [ ] DECISIONS.md 追加 D100 + D101
- [ ] 无硬编码颜色（全部从 tokens.css CSS 变量读取）
- [ ] 无 `console.log` / 调试残留
- [ ] features.json `F219.sub_sprints['F219-b']` 从 `planned` → `done`
- [ ] 触发 consistency-check skill (mode=interactive)：C1（F219 父 feature 所有 sibling done → 父 feature 升 done 候选）+ C4（iteration_history 补 F219-b 完成记录）+ C5（sub_sprints ↔ 合约目录双向一致）

---

## 7. 完成后的衔接

- F219-b `done` → consistency-check C1：F219.sub_sprints 全 done → F219 整体 phase 升 `needs_review`
- F219 整体 `needs_review` → acceptance skill（用户验收 EOD 后真机观察 setup_snapshots 落字段 + 前端两个 widget 实际渲染）
- acceptance 通过后 → F219 整体 `done`，Phase E 闭环

---

👤 **本 Contract 草案待用户确认**。NP-1~4 已按推荐方案确认。文件清单 6 个文件，6-file 内无需例外。确认后：

1. `F219.phase` → `contract_agreed`
2. `claude-progress.txt` 追加 contract 协商完成
3. 生成 `SESSION-HANDOFF.md`
4. **强制停止**，新 session 用 Sonnet 进入 Generator
