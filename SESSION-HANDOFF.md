# SESSION-HANDOFF — F210-c Generator 启动

> 生成时间：2026-04-25
> 上一个 session：F210-b ✅ done（SetupMonitor "AI 排序" 集成，commit 5bacb52）
> 下一个 session：F210-c Generator 模式（前端开发）
> 当前 branch：cockpit

---

## 1. 立即执行指令（粘贴到新 session）

> 继续开发 F210-c，参考 F210-b 已完成的模式。
> 读取本文件 + `docs/开发/sprint-contracts/`（F210-c contract 待起草）。
> 先草拟 F210-c Sprint Contract，与用户确认后进入 Generator 模式。

---

## 2. F210 整体状态

| 子 sprint | phase | 说明 |
|----------|-------|------|
| F210-a | ✅ done | 后端 schemas + trade_plan guardrail；含 2853e3b regime 5 值 hotfix |
| F210-b | ✅ **done** | SetupMonitor "AI 排序" 集成（commit 5bacb52） |
| **F210-c** | ⬜ design_ready（下一个 sprint）| DecisionPanel "Generate AI Plan" 集成 |

---

## 3. F210-b 完成内容（本 session）

### 3.1 新建文件

**`frontend/src/cockpit/components/AiCandidateRankerSection.tsx`**（325 行）：
- 类型：`CandidateInput` / `CandidateRankerInput` / `RankedCandidate` / `CandidateRankerOutput`
- `buildCandidateRankerInput`：9 字段精确映射，`slice(0,20)`，null 容错
- `ActionBadge`：enter→breakout色 / watch→warn色 / wait→muted色（三色枚举）
- 主组件：5 状态渲染（closed / spinning skeleton / error / success / empty→disabled）
- `flexBasis: 100%` 使 result panel 在 flex-wrap tabs 容器内另起一行
- cache badge：`meta.cacheHit ? 'Cached' : 'Generated · {modelUsed}'`
- ✕ 关闭：仅 `setOpen(false)`，不 invalidate（缓存保留）

### 3.2 修改文件

**`frontend/src/cockpit/widgets/SetupMonitorWidget.tsx`**（+13 行）：
- 新增 `getCockpitRegime` + `AiCandidateRankerSection` import
- 新增 regime `useQuery`（key `['cockpit-regime']`，staleTime 5min）
- Filter Tabs div 末尾挂 `<AiCandidateRankerSection items={items} regime={regimeData?.regime ?? null} regimeScore={regimeData?.marketScore ?? null} />`

**`frontend/src/cockpit/widgets/__tests__/SetupMonitorWidget.test.tsx`**（+414 行）：
- §R 11 用例全部通过（R1–R11）
- 复用 F209-c `makeRoutedFetch` 路由 mock 模板
- R11 验证缓存命中（fetch spy 计数 = 1）

### 3.3 文档回写（规则 8）

- `docs/设计/design-spec.md` Widget 5 新增 v2.0 AI 排序段
- `docs/设计/data-mapping.md` 新增 §5.c AI Candidate Ranker（输入/输出映射表）

### 3.4 测试结果

- 全量 106/106 通过（前端）
- tsc --noEmit：零错
- lint：我们的文件零新增 error

---

## 4. F210-c 骨架预览（下一个 sprint，来自 F210-b 合约 §8）

**核心**：DecisionPanelWidget 接入 `POST /api/ai/trade_plan`：
- 新建 `AiTradePlanSection.tsx`（按钮 + 4 状态 + memo 段 + management 列表 + Guardrail 红 banner / 通过 ✓）
- `DecisionPanelWidget.tsx` 在 Decision Card 下方追加该 section，从 `decision` query 取字段构造 input
- 测试 ~12 用例（含 409 AI_GUARDRAIL_VIOLATION 红 banner、memo / management 渲染、cache 命中）

预计 3 文件，与 F210-b 风格对称。

---

## 5. 技术约束（F210-c Generator 需要知道的）

- **F210-a 落地的 trade_plan schema**：`backend/app/ai/schemas/trade_plan.py`
  - 输入 `TradePlanInput`：11 字段（ticker / regime / regimeScore / setupType / setupQuality / trendScore / rsPercentile / entryPrice / stopPrice / rewardRisk / earningsRisk）
  - 输出 `TradePlanOutput`：memo（string）+ management（list[TradeManagementStep]）
  - Guardrail：`TradePlanGuardrail` 策略，409 = `AI_GUARDRAIL_VIOLATION`
- **Decision 数据来源**：`DecisionPanelWidget` 的 `decision` useQuery 已有所有 11 字段
- **regime 来源**：同 F210-b，`useQuery(['cockpit-regime'], getCockpitRegime, {staleTime: 5min})`
- **缓存**：`staleTime/gcTime: 24h`，`retry: false`（与 F210-b / F209-c 一致）
- **AI_GUARDRAIL_VIOLATION** 需单独处理：红色 banner，文案来自 `error.detail` 或固定文案

---

## 6. 关键文件路径

| 文件 | 用途 |
|------|------|
| `frontend/src/cockpit/widgets/DecisionPanelWidget.tsx` | 注入点 |
| `frontend/src/cockpit/widgets/__tests__/DecisionPanelWidget.test.tsx` | 扩展测试 |
| `frontend/src/cockpit/components/AiCandidateRankerSection.tsx` | F210-b 模板 |
| `frontend/src/cockpit/components/AiSetupExplainerPopover.tsx` | F209-c 模板 |
| `backend/app/ai/schemas/trade_plan.py` | schema 权威 |
| `docs/系统设计/API-CONTRACT.md` | §POST /api/ai/{task_type} |

---

## 7. 未决事项（F210-b acceptance 阶段）

- 视觉验证：result panel 在 widget 默认高度内的占位（3 行 card ≈ 90px）
- 真实 cache hit smoke：第一次调返回 `meta.cacheHit=false`；24h 内复调 `meta.cacheHit=true`
- AI 输出 ticker 不在当前 items 集合的容错行为（渲染孤立 ticker，无 setSelectedTicker 联动）

---

## 8. git 状态

- branch：`cockpit`
- 最新 commit：`5bacb52 feat(F210-b): SetupMonitor AI rank top 3`
- features.json：`F210-b.phase = "done"`，`active_sprint_phase = "done"`
