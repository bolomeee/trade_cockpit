# SESSION-HANDOFF — 2026-04-25（F203-c contract_agreed）

> 覆盖上一版（F203-b2 done）。
> 本次完成 F203-c Sprint Contract 协商并经用户确认。
> **请用 Sonnet 新开 session 进入 Generator 模式。**

---

## 当前状态

| Feature | 状态 |
|---------|------|
| F200-a / F200-b | ✅ done |
| F201-a / F201-b | ✅ done |
| F204-a / F204-b | ✅ done |
| F202-a / F202-b / F202-c | ✅ done |
| F203-a | 🔍 needs_review |
| F203-b1 | 🔍 needs_review |
| F203-b2 | ✅ done |
| **F203-c** | **📜 contract_agreed（本次）** |
| F203-d | ⬜ ready_to_dev（依赖 F203-b2，已满足） |

---

## F203-c Sprint Contract 摘要

### 实现范围

CockpitChartWidget（独立组件，不复用 workbench ChartWidget — D063）：
- 主图：Candlestick + MA10/21/50/150/200 + AVWAP（anchor 不为 null 时）
- 副图：Volume histogram
- entry / stop / target2r / target3r 4 条 priceLine（联合 decision 端点）
- Header：`Chart · {ticker} · {setupType} · {quality}`
- 联合 `GET /api/cockpit/chart/{ticker}` + `GET /api/cockpit/decision/{ticker}`
- Registry 注册 `cockpit.cockpit-chart`，category=`chart`，layout x=4 y=0 w=5 h=10

### 排除项

- DecisionPanelWidget / Override Form / UserSettings 表单（→ F203-d）
- D|W 切换、MA toggle UI（→ v1.9）
- ATR 绘制、Earnings marker、Setup 文本气泡（→ v1.9 / F204）

### 文件清单（4 个）

| # | 文件 | 类型 |
|---|------|------|
| 1 | `frontend/src/cockpit/lib/api/cockpitChartApi.ts` | 新建 |
| 2 | `frontend/src/cockpit/lib/api/cockpitDecisionApi.ts` | 新建 |
| 3 | `frontend/src/cockpit/widgets/CockpitChartWidget.tsx` | 新建 |
| 4 | `frontend/src/cockpit/CockpitRegistry.ts` | 修改 |

> 另：若 `tokens.css` 缺 `--color-chart-entry/stop/target/avwap`，作为开发顺序步骤 1 补齐（不计入 4 文件）。

---

## 开发顺序（Generator 模式逐步执行）

1. 检查并补齐 `frontend/src/styles/tokens.css` 中的 chart 颜色变量
2. 写 `cockpitChartApi.ts`（含 ChartBarItem / ChartSeriesPoint / ChartAvwap / CockpitChartData 类型）
3. 写 `cockpitDecisionApi.ts`（含 CockpitDecisionData 类型 + overrides 参数）
4. 写 `CockpitChartWidget.tsx`：
   1. ResizeObserver + 容器
   2. createChart + Candlestick + Volume
   3. 5 条 MA LineSeries
   4. AVWAP LineSeries（anchor 存在才加）
   5. decision query → 4 条 priceLine
5. 修改 `CockpitRegistry.ts` 注册一行
6. 单元 + 集成测试（S1–S10）
7. 全量回归 `pnpm -C frontend test && lint && build`（S11）
8. Evaluator 自检清单
9. 通过后 commit：`feat(F203-c): CockpitChart 前端 Widget（chart + decision 联合 + 4 priceLines）`

完成标准 S1–S11、Evaluator 自检清单详见 `docs/开发/sprint-contracts/F203-c-contract.md`。

---

## 关键技术约束（不要忘）

- **D063**：CockpitChartWidget 不 import workbench `PriceChart.tsx`；lightweight-charts 直接 import 自建实例
- **字段命名**：与 API-CONTRACT camelCase 对齐；decision 注意 `target2r/target3r`（pydantic alias）
- **颜色**：所有颜色取 `tokens.css` CSS 变量，不写硬编码 hex
- **decision 失败容忍**：404 时 chart 主图仍渲染，仅丢 4 条横线
- **切 ticker**：销毁旧 chart 实例 + 重建（不用 updateData）
- **测试**：jsdom 下用 spy 断言 createChart / createPriceLine 调用，不做视觉断言

---

## 当前 Git 状态

Branch: `cockpit`
Last commit: `feat(F203-b1): UserSettings 数据/接入栈（model + alembic + repo + router）`

未 committed（F203-b2 全部 + 历史遗留 + 本次 contract 文档）：
- F203-b2 6 文件（按 feature-dev 规则 7，Evaluator 通过后已具备 commit 条件，但未执行）
- F202-c / F203-a / F203-b1 历史遗留
- 本次新增：`docs/开发/sprint-contracts/F203-c-contract.md`、`SESSION-HANDOFF.md`、`claude-progress.txt`、`docs/需求/features.json`

> ⚠ 建议：进入 F203-c Generator 前，先单独 commit F203-b2（按 SESSION-HANDOFF 上一版的方案）+ 本次 Contract 文档，保持 git 历史清晰。

---

## 下一 Session 恢复指令

```
继续开发 F203-c，Sprint Contract 已确认。
读取 SESSION-HANDOFF.md + docs/开发/sprint-contracts/F203-c-contract.md，
进入 Generator 模式，从开发步骤 1（tokens.css 补齐）开始。
```
