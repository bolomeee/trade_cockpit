# Sprint Contract：F216-d3 — SetupMonitor 前端 WS 列

> 日期：2026-05-15 | 状态：✅ 已确认（用户 2026-05-15 NP1-NP6 全部按推荐拍板）
> Feature：F216 Cockpit Phase B — Weekly Stage Layer
> Sub-sprint：F216-d3（d 段第 3 个，前端层；d1=DB schema done，d2=service gate done）
> 父 feature 拆分理由：F216-d 原估 ~13 文件远超 6 文件上限，按 sub_sprint_notes 拆 d1/d2/d3
> 依赖：
>   - F216-d2 done（GET /api/cockpit/setup-monitor 响应已含 `weeklyStage: number | null`）
>   - F216-c2 done（WeeklyStageChartWidget 已落地 STAGE_LABELS / STAGE_BG_TOKENS 常量，可抽出复用）
> 引用文档：
>   - design-spec.md §Widget 5：SetupMonitorWidget
>   - API-CONTRACT.md §GET /api/cockpit/setup-monitor（已含 weeklyStage 字段说明 + readySignal 8 条 AND 文案）
>   - 完整改善计划：/Users/wonderer/.claude/plans/featrue-dev-replicated-goblet.md §Phase B / B4 前端段
>   - features.json F216 acceptance_criteria："SetupMonitor 加 WS 列展示 Stage 1-4"

---

## 0. 背景与定位

Phase B 的"显示层"收尾 — 把 d2 已暴露的 `weeklyStage` 字段渲染到 SetupMonitorWidget 表格，让用户在做日线买入决策前能看到该标的当前的周线 Stan Weinstein Stage（1-4），与 readySignal 8 条 AND 门的 stage==2 设计意图视觉对齐："为什么这只标的 ready=false / 为什么 ready=true 集合变小了"。

不动后端、不动 DB schema、不引入新依赖；纯前端 +1 列 + 1 共享常量模块。

---

## 1. 实现范围

### 1.1 frontend/src/cockpit/lib/weeklyStageTokens.ts（新建）

抽出 `WeeklyStageChartWidget.tsx` 现有的 3 个常量到独立模块：

```ts
export const STAGE_LABELS: Record<number, string> = {
  0: 'Unknown',
  1: 'Base',
  2: 'Advancing',
  3: 'Distribution',
  4: 'Declining',
}

export const STAGE_BG_TOKENS: Record<number, string> = {
  0: '--color-text-muted',
  1: '--color-log-warn',
  2: '--color-change-positive',
  3: '--color-log-warn',
  4: '--color-change-negative',
}

export const STAGE_BG_FALLBACKS: Record<number, string> = {
  0: '#6b7280',
  1: '#f59e0b',
  2: '#10b981',
  3: '#f59e0b',
  4: '#ef4444',
}

export function readStageColor(stage: number | null | undefined): string {
  // stage null/undefined 视作 0（Unknown） — 颜色取 muted
  const key = stage == null ? 0 : stage
  if (typeof window === 'undefined') return STAGE_BG_FALLBACKS[key] ?? STAGE_BG_FALLBACKS[0]
  const v = getComputedStyle(document.documentElement).getPropertyValue(STAGE_BG_TOKENS[key] ?? STAGE_BG_TOKENS[0]).trim()
  return v || STAGE_BG_FALLBACKS[key] ?? STAGE_BG_FALLBACKS[0]
}
```

### 1.2 frontend/src/cockpit/widgets/WeeklyStageChartWidget.tsx（重构 import）

删本地 3 个常量声明 + 本地 `readToken` 调用改成从新模块 import：

```ts
import { STAGE_LABELS, STAGE_BG_TOKENS, STAGE_BG_FALLBACKS } from '../lib/weeklyStageTokens'
```

`readToken(STAGE_BG_TOKENS[stageNum], STAGE_BG_FALLBACKS[stageNum])` 调用保留（行为零变更，本地 `readToken` 函数仍用于 MA tokens；只是 STAGE 三常量改成 import）。

⚠️ MA_TOKENS / MA_FALLBACKS 保留在 WeeklyStageChartWidget 本地（仅该 widget 使用，不抽取）。

### 1.3 frontend/src/cockpit/lib/api/setupMonitorApi.ts（修改）

`SetupItem` 类型追加：

```ts
weeklyStage: number | null
```

放在 `upDownVolumeRatio` 之后，与后端 `_row_to_dict` 字段时序保持一致。

### 1.4 frontend/src/cockpit/widgets/SetupMonitorWidget.tsx（修改）

**A. thead 新增 `<Th>`**

在 `<Th width="6%">Vol Z</Th>` 之后、`<Th width="7%" align="center">Earn</Th>` 之前插入：

```tsx
<Th width="6%" align="center">WS</Th>
```

**B. 列宽重新分配（NP3 推荐方案 a）**

| 列 | 原 width | 新 width |
|----|---------|---------|
| Ticker | 14% | 13% |
| Setup | 16% | 14% |
| Q | 5% | 5% |
| Entry | 11% | 10% |
| Stop | 11% | 10% |
| R:R | 8% | 7% |
| Dist | 9% | 9% |
| RS | 5% | 5% |
| Vol Z | 6% | 6% |
| **WS** | — | **6%**（新增） |
| Earn | 7% | 7% |
| (delete) | 8% | 8% |
| **合计** | **100%** | **100%** |

**C. tbody 新增 `<td>` 渲染**

在 Vol Z 单元格之后、Earn 单元格之前插入：

```tsx
<td style={{ ...tdStyle, textAlign: 'center' }}>
  <WeeklyStageCell stage={item.weeklyStage} />
</td>
```

`WeeklyStageCell` 内联在 SetupMonitorWidget.tsx 内（不新建组件文件 — 仅 SetupMonitor 使用，无复用价值）：

```tsx
function WeeklyStageCell({ stage }: { stage: number | null }) {
  // null / 0 → "—" 灰色（与表格其他空值列一致）
  if (stage == null || stage === 0) {
    return (
      <span
        title={stage === 0 ? STAGE_LABELS[0] : '无 Weekly Stage 数据'}
        style={{ color: 'var(--color-text-muted)' }}
      >
        —
      </span>
    )
  }
  const color = readStageColor(stage)
  const label = STAGE_LABELS[stage] ?? 'Unknown'
  return (
    <span
      data-stage={stage}
      title={label}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '4px',
        fontFamily: 'var(--font-family-numeric)',
        color: 'var(--color-text-primary)',
      }}
    >
      <span
        aria-hidden="true"
        style={{
          width: '8px',
          height: '8px',
          borderRadius: '50%',
          background: color,
          display: 'inline-block',
        }}
      />
      {stage}
    </span>
  )
}
```

**D. import**

文件顶部追加：

```ts
import { STAGE_LABELS, readStageColor } from '../lib/weeklyStageTokens'
```

### 1.5 frontend/src/cockpit/widgets/__tests__/SetupMonitorWidget.test.tsx（修改）

**A. fixture `makeItem` 默认加 `weeklyStage: 2`**

```ts
function makeItem(overrides: Partial<SetupItem>): SetupItem {
  return {
    // ... 现有字段
    upDownVolumeRatio: 1.45,
    weeklyStage: 2,  // ← 新增
    ...overrides,
  }
}
```

**B. 新增 §W 描述块（W1-W7）**

```ts
describe('§W – WS column', () => {
  afterEach(() => vi.unstubAllGlobals())

  // W1: 表头渲染 "WS" 列
  it('W1: table header renders "WS" column', async () => {
    vi.stubGlobal('fetch', makeRoutedFetch({ '/cockpit/setup-monitor': SETUP_MONITOR_OK_FETCH }))
    renderWidget()
    await screen.findByText('AAPL')
    expect(screen.getByText('WS')).toBeInTheDocument()
  })

  // W2-W5: stage 1/2/3/4 渲染数字 + title 全名
  it.each([
    [1, 'Base'],
    [2, 'Advancing'],
    [3, 'Distribution'],
    [4, 'Declining'],
  ])('W2-5: stage=%i → 数字 "%i" + title="%s"', async (stage, label) => {
    const item = makeItem({ ticker: 'AAPL', weeklyStage: stage })
    vi.stubGlobal(
      'fetch',
      makeRoutedFetch({
        '/cockpit/setup-monitor': () => Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({
            data: {
              summary: { total: 1, ready: 1, near: 0, extended: 0, broken: 0, none: 0 },
              items: [item],
            },
          }),
        } as FetchResponse),
      }),
    )
    renderWidget()
    await screen.findByText('AAPL')
    const cell = await screen.findByTitle(label)
    expect(cell).toHaveAttribute('data-stage', String(stage))
    expect(cell).toHaveTextContent(String(stage))
  })

  // W6: stage=0 → "—" + title="Unknown"
  it('W6: stage=0 → "—" + title="Unknown"', async () => {
    const item = makeItem({ ticker: 'AAPL', weeklyStage: 0 })
    vi.stubGlobal(
      'fetch',
      makeRoutedFetch({
        '/cockpit/setup-monitor': () => Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({
            data: {
              summary: { total: 1, ready: 1, near: 0, extended: 0, broken: 0, none: 0 },
              items: [item],
            },
          }),
        } as FetchResponse),
      }),
    )
    renderWidget()
    await screen.findByText('AAPL')
    const cell = await screen.findByTitle('Unknown')
    expect(cell).toHaveTextContent('—')
  })

  // W7: stage=null → "—" + title="无 Weekly Stage 数据"
  it('W7: stage=null → "—"', async () => {
    const item = makeItem({ ticker: 'AAPL', weeklyStage: null })
    vi.stubGlobal(
      'fetch',
      makeRoutedFetch({
        '/cockpit/setup-monitor': () => Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({
            data: {
              summary: { total: 1, ready: 1, near: 0, extended: 0, broken: 0, none: 0 },
              items: [item],
            },
          }),
        } as FetchResponse),
      }),
    )
    renderWidget()
    await screen.findByText('AAPL')
    const cell = await screen.findByTitle('无 Weekly Stage 数据')
    expect(cell).toHaveTextContent('—')
  })
})
```

### 1.6 docs/设计/design-spec.md §Widget 5（修改）

更新 ASCII mock 表头与示例行加 WS 列；在交互 bullets 后追加 WS 渲染规则段：

```markdown
- **WS 列（F216-d3）**：展示 weekly_stage 数值（1-4）+ 同色小圆点，title 显示全名（Base / Advancing / Distribution / Declining）。stage=0（UNKNOWN）或 null（cron 未跑）→ "—" 灰色。颜色映射：Stage 2 绿 / Stage 1 & 3 黄 / Stage 4 红 / 0 & null 灰，与 WeeklyStageChartWidget 共用 STAGE_BG_TOKENS。设计意图：让用户在表格中看到"为何 ready=false"，与 d2 的 readySignal 第 8 条 AND 门视觉对齐。
```

ASCII mock 表头改成：
```
│ Ticker Setup     Q  Entry  Stop  R:R  Dist   RS  VolZ  WS  Earn ││
│ NVDA   BREAKOUT  A  850.0  820.0 2.0  +1.25% 88  1.83  ●2  SAFE ●││
```

---

## 2. 预计修改文件（6 个，恰好上限）

| # | 文件 | 改动类型 | 改动规模 |
|---|------|---------|---------|
| 1 | `frontend/src/cockpit/lib/weeklyStageTokens.ts` | 新建 | 4 常量 + readStageColor helper（~30 行） |
| 2 | `frontend/src/cockpit/widgets/WeeklyStageChartWidget.tsx` | 修改 | 删 3 const + 加 import（~5 行 net delete） |
| 3 | `frontend/src/cockpit/lib/api/setupMonitorApi.ts` | 修改 | SetupItem 加 `weeklyStage: number \| null` 1 行 |
| 4 | `frontend/src/cockpit/widgets/SetupMonitorWidget.tsx` | 修改 | thead 加列 + 列宽调整 + tbody 加 td + WeeklyStageCell 函数 + import |
| 5 | `frontend/src/cockpit/widgets/__tests__/SetupMonitorWidget.test.tsx` | 修改 | makeItem 加 weeklyStage:2 + §W 7 个测试 case |
| 6 | `docs/设计/design-spec.md` | 修改 | §Widget 5 ASCII mock 列扩展 + WS 规则 bullet |

**明确排除（留给后续 sprint）**：

| 项 | 归属 |
|---|---|
| AI candidate_ranker 加 weeklyStage 入参 | **不做**（NP6，scope 不外溢） |
| DecisionPanel / 其他 widget 显示 stage | F210 / F216-e 之后再议 |
| refresh_job cron 顺序编排 regime→weekly_stage→setup | F216-e |
| stage 历史轨迹 sparkline | 未规划 |

---

## 3. 协商点结论（NP1-NP6，全部按推荐）

| NP | 主题 | 选择 | 理由 |
|----|------|------|------|
| **NP1** | 渲染样式 | a：彩色圆点 + 数字 + title 全名 | 表格密度合适，与 Earn 列点风格一致；无新组件；颜色与 WeeklyStageChartWidget 统一 |
| **NP2** | null/0 显示 | a：都显示 "—" + 不同 title | "无数据"和"unknown"在用户视野等价；区分仅靠 hover title 调试用 |
| **NP3** | 列宽分配 | a：均匀微调 Ticker/Setup/Entry/Stop/R:R | 最稳，Setup 14% 仍能放下 EARNINGS_DRIFT；删除列 8% 保留 |
| **NP4** | 常量复用 | b：抽 weeklyStageTokens.ts 共享模块 | 未来 stage→color 是产品级约定，不该藏在 widget 内；代码量小（30 行） |
| **NP5** | 插入位置 | a：Vol Z 与 Earn 之间 | 信号列簇（RS / Vol Z / WS / Earn），视野从左→右 = 价格 → 信号 → 风险 |
| **NP6** | AI candidate 字段 | a：不加 weeklyStage | R6 测试 9 字段断言不变；ranker 已凭 readySignal 隐含 stage=2；scope 不外溢 |

---

## 4. 可测试的完成标准

| # | 标准描述 | 测试层级 | 工具 / 验证方法 |
|---|---------|---------|----------------|
| W1 | 表头渲染 "WS" 列（Vol Z 与 Earn 之间） | 单元 | `screen.getByText('WS')` |
| W2 | weeklyStage=1 → 数字 "1" + 黄圆点 + title="Base" | 单元 | `getByTitle('Base')` + data-stage="1" |
| W3 | weeklyStage=2 → 数字 "2" + 绿圆点 + title="Advancing" | 单元 | 同上 |
| W4 | weeklyStage=3 → 数字 "3" + 黄圆点 + title="Distribution" | 单元 | 同上 |
| W5 | weeklyStage=4 → 数字 "4" + 红圆点 + title="Declining" | 单元 | 同上 |
| W6 | weeklyStage=0 → "—" 灰 + title="Unknown" | 单元 | `getByTitle('Unknown')` |
| W7 | weeklyStage=null → "—" 灰 + title="无 Weekly Stage 数据" | 单元 | `getByTitle('无 Weekly Stage 数据')` |
| W8 | makeItem fixture 加 `weeklyStage:2` 不破坏现有 §R/§S/§V 共 30+ 测试 | 回归 | 全跑 SetupMonitorWidget.test.tsx |
| W9 | R6（AI ranker candidate 9 字段断言）仍恰好 9 字段 | 回归 | R6 |
| W10 | WeeklyStageChartWidget 现有测试（若有）全绿（import 重构兜底） | 回归 | 全跑 cockpit 测试 |
| W11 | `pnpm typecheck`（tsc --noEmit）零错误 | 静态 | tsc |
| W12 | `pnpm lint` 无新增 warning | 静态 | eslint |
| W13 | design-spec.md §Widget 5 ASCII mock 含 WS 列 + WS 规则 bullet | 文档 | 人工 diff |
| W14 | 全量 `pnpm test`（vitest）无新增失败 | 回归 | vitest |

---

## 5. Evaluator 自检清单

- [ ] W1-W7 新增测试 7 条全绿
- [ ] W8-W10 回归零新增失败
- [ ] W11 typecheck 零错
- [ ] W12 lint 零新 warning
- [ ] W13 design-spec.md 同步（ASCII mock + WS 规则 bullet）
- [ ] STAGE_BG_TOKENS 颜色严格用 `var(--color-...)` 不写硬编码（与现有 widget 一致）
- [ ] WS 列 title 属性提供 a11y 兜底（颜色不是唯一区分手段）
- [ ] null/0 在表格中走 `—` 路径，不渲染数字
- [ ] WeeklyStageChartWidget import 重构后行为零变更（不改任何 chart 渲染逻辑）
- [ ] commit 显式列文件名（按 §2 清单），禁用 `git add -A`
- [ ] 无新增 npm 依赖
- [ ] 代码质量：无死代码 / 无硬编码 stage 数字（全走 STAGE_LABELS map）/ 无未使用 import
- [ ] consistency-check C1/C4/C5 全清后再标 needs_review

---

## 6. WIP commit 节点

| # | 触发条件 | 命令 |
|---|---------|------|
| WIP 1 | weeklyStageTokens.ts 新建 + WeeklyStageChartWidget import 重构 + SetupItem.weeklyStage 类型加完 + 现有 WeeklyStageChartWidget 测试（若有）全绿 + typecheck 绿 | `git add frontend/src/cockpit/lib/weeklyStageTokens.ts frontend/src/cockpit/widgets/WeeklyStageChartWidget.tsx frontend/src/cockpit/lib/api/setupMonitorApi.ts` → `git commit -m "wip(F216-d3): extract weeklyStageTokens + SetupItem.weeklyStage"` |
| WIP 2 | SetupMonitorWidget WS 列实现 + 测试 makeItem fixture + §W 7 条 case + 全量 SetupMonitorWidget.test.tsx 全绿 | `git add frontend/src/cockpit/widgets/SetupMonitorWidget.tsx frontend/src/cockpit/widgets/__tests__/SetupMonitorWidget.test.tsx` → `git commit -m "wip(F216-d3): WS column + tests"` |
| Final | design-spec.md 同步 + Evaluator 全清 + 全量 vitest 零回归 | `git add docs/设计/design-spec.md` → `git commit -m "feat(F216-d3): WS column in SetupMonitorWidget"` |

⚠️ 禁用 `git add -A`。

---

## 7. 开发顺序（Generator 模式逐步执行）

1. 读本 contract + 当前 `SetupMonitorWidget.tsx` / `WeeklyStageChartWidget.tsx` / `setupMonitorApi.ts` 保 context
2. 新建 `frontend/src/cockpit/lib/weeklyStageTokens.ts`（4 常量 + readStageColor helper）
3. 改 `WeeklyStageChartWidget.tsx`：删本地 STAGE_LABELS / STAGE_BG_TOKENS / STAGE_BG_FALLBACKS 三个 const；加 import；保留本地 MA 常量与 readToken 函数
4. 跑 `pnpm test WeeklyStageChartWidget`（若有测试）+ `pnpm typecheck` 验证 step 3 零回归
5. 改 `setupMonitorApi.ts` `SetupItem` 加 `weeklyStage: number | null`
6. 跑 `pnpm typecheck` 验证类型补全；此时 SetupMonitorWidget 应该会因 fixture 缺字段编译失败 — 进 step 7
7. 改 `__tests__/SetupMonitorWidget.test.tsx` `makeItem` 默认加 `weeklyStage: 2`
8. 跑 `pnpm test SetupMonitorWidget` 确认现有 §R/§S/§V 测试零回归（无新功能，仅 fixture 默认值变更）
9. **WIP commit 1**
10. 改 `SetupMonitorWidget.tsx`：
    - 顶部加 `import { STAGE_LABELS, readStageColor } from '../lib/weeklyStageTokens'`
    - thead 在 `<Th width="6%">Vol Z</Th>` 后插入 `<Th width="6%" align="center">WS</Th>`，前 5 列与 R:R 列 width 按 §1.4 表调整
    - tbody 在 Vol Z `<td>` 后插入 `<WeeklyStageCell stage={item.weeklyStage} />`
    - 文件底部加 `WeeklyStageCell` 函数（见 §1.4 C）
11. 追加 `__tests__/SetupMonitorWidget.test.tsx` §W 描述块（W1-W7 共 7 个 case，含 W2-W5 参数化）
12. 跑 `pnpm test SetupMonitorWidget` 全绿（含 W1-W7 + 现有 §R/§S/§V 30+ case）
13. **WIP commit 2**
14. 跑 `pnpm typecheck` 零错；`pnpm lint` 零新 warning
15. 跑全量 `pnpm test`（vitest）确认零新增失败（W10）
16. 改 `docs/设计/design-spec.md` §Widget 5：
    - ASCII mock 表头加 WS 列
    - 示例行加 stage 数值
    - 交互 bullets 后追加 "WS 渲染规则（F216-d3）" 段
17. Evaluator 自检 → **Final commit** → 调用 consistency-check (mode=interactive) C1/C4/C5 → 标 sub_sprints["F216-d3"]=needs_review → 等待 acceptance

---

## 8. 风险与回滚

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| 列宽 a 方案在窄屏 cockpit 布局下挤压 Setup badge 截断 | 中 | EARNINGS_DRIFT badge 末字符省略 | 现有 `tableLayout:fixed` + `overflow:hidden + textOverflow:ellipsis` 兜底；用户可拖宽 widget；最坏 badge 视觉截断但布局不破坏 |
| WeeklyStageChartWidget import 重构破坏其测试 | 低 | F216-c2 测试失败 | step 4 单独验证；行为零变更（const 值不变） |
| `makeItem` fixture 默认 `weeklyStage:2` 破坏某条断言（如字段总数判断） | 低 | §R/§S/§V 个别 case 失败 | step 8 全跑兜底；现有断言全是 by-name 查找无字段总数依赖 |
| R6 candidate 9 字段断言被破坏（NP6 防御失败） | 低 | R6 红 | NP6 已决"不加"，candidatePayload 构造时只 pick 9 字段（看 AiCandidateRankerSection 源代码确认）；step 15 兜底 |
| design-spec ASCII mock 列对齐重画错位 | 低 | 文档可读性 | 用 monospace mock，按现有风格扩 1 列宽度（每列 5-6 字符） |
| readStageColor SSR fallback 路径未触发（vitest 在 jsdom 下有 window） | 低 | 测试用例验证不到 SSR 分支 | 单元测试只验证客户端渲染；SSR fallback 是兜底防御代码，不强测 |

**回滚方案**：
- 视觉层：`git revert <final-commit>` 一次回退 6 文件改动；不影响后端 / d2 已落地的 weeklyStage API 字段
- 部分回滚：若仅 design-spec 描述有误 → 改文档不需 revert commit
- WeeklyStageChartWidget 重构若引发问题：单独 revert WIP 1 commit 即可（恢复本地 const）

---

## 9. 后续衔接

F216-d3 done 后：
- F216 sub_sprints 状态：a/b/c1/c2/d1/d2/d3 全 done，仅剩 F216-e（refresh_job cron 编排）
- consistency-check C1 自动验证 F216 父 feature **不能**升 done（e 仍 design_needed），保持 in_progress
- F216-e Contract 协商：~2 文件（refresh_job.py + 测试），不会触发 6 文件原则二次拆
- F216-e done 后 F216 父 feature 升 done，触发 acceptance 入口

---

## 10. 验收切入点（acceptance skill 用）

F216-d3 needs_review 后由 acceptance skill 验证：
- 启动 `pnpm dev`（前端）+ 后端 cockpit setup-monitor endpoint
- 对照 design-spec.md §Widget 5 验证 WS 列视觉：颜色 / 数字 / hover title
- 选 1-2 个真实 Stage=2 ticker 验证圆点为绿
- 选 1 个 weeklyStage=null 的 ticker 验证 "—"
- 验收记录：`docs/验收/v2.0-F216-d3-acceptance.md`

---

👤 用户已确认本 Contract（2026-05-15 NP1-NP6 全部按推荐 a/a/a/b/a/a 拍板）。下个 session（建议 Sonnet）从 §7 开发顺序步骤 1 开始。
