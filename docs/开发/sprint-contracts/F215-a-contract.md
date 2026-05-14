# Sprint Contract：F215-a — Risk cap (RISK_ON 1.5%→1.25%) + EMA 10/21

> 日期：2026-05-12 | 状态：✅ 已确认（用户 2026-05-12 按推荐方案确认所有协商点）
> 引用文档：
>   API-CONTRACT.md §GET /api/cockpit/chart/{ticker}（emas 字段扩展）
>   API-CONTRACT.md §GET /api/cockpit/regime（single_trade_risk_pct）
>   DATA-MODEL.md §Entity: MarketRegimeSnapshot（已有 single_trade_risk_pct 列，零变更）
>   完整改善计划：/Users/wonderer/.claude/plans/featrue-dev-replicated-goblet.md Phase A1 + A2

---

## 本次实现范围

**包含**：
1. **A1 — 单笔风险上限调整**：`REGIME.SINGLE_TRADE_RISK_PCT["RISK_ON"]` 从 `1.5` 改为 `1.25`，对齐 SRS 推荐上限。其他 4 个 regime 档位保持不变。
2. **A2 — EMA 10 / EMA 21 加入 chart_service**：
   - `chart_service` 新增纯函数 `_compute_ema_series(bars, period)`（Wilder/标准 EMA，α=2/(period+1)，seed=SMA(period)）
   - `CHART` 参数新增 `DEFAULT_EMAS = [10, 21]`
   - `get_chart()` 返回结构在 `mas` 同级新增 `emas` 字段（dict[str, list[ChartSeriesPoint]]）
   - Pydantic schema `CockpitChartData` 增加 `emas` 字段
   - 前端 API client 类型同步增加 `emas`
   - `CockpitChartWidget` 在 chart 上叠加 EMA10 / EMA21 两条线（虚线 LineStyle.Dashed，与 SMA 视觉区分）

**明确排除（本次不做）**：
- Volume Accumulation 三件套（z-score / OBV / up-down volume）→ 由 F215-b 单独承担
- Weekly Stage Chart（Phase B）
- 任何 setup_service / setup_snapshots 变更
- 任何 DB schema 变更 / alembic migration
- ATR 周期增加（继续仅 ATR14）
- AVWAP from major low 锚点
- DECISIONS.md 仅追加 1 条决策（D076 风险上限对齐 SRS）

---

## 预计修改文件（共 6 个）

| 文件路径 | 改动类型 | 说明 |
|---------|---------|------|
| `backend/app/services/cockpit/cockpit_params.py` | 修改 | 行 83：`"RISK_ON": 1.5` → `1.25`；§3 CHART 类新增 `DEFAULT_EMAS: list[int] = [10, 21]` 字段（验证范围复用现有 MA_MIN/MA_MAX 概念，不另设新字段） |
| `backend/app/services/cockpit/chart_service.py` | 修改 | 新增 `_compute_ema_series()` 纯函数（α=2/(period+1)，seed=SMA(period)）；`get_chart()` 增加 emas 计算与返回 key（EMA 周期硬编码取自 `CHART.DEFAULT_EMAS`，**不接受 `?emas=` 查询参数**） |
| `backend/app/schemas/cockpit/chart.py` | 修改 | `CockpitChartData` 增加 `emas: dict[str, list[ChartSeriesPoint]]` 字段 |
| `frontend/src/cockpit/lib/api/cockpitChartApi.ts` | 修改 | `CockpitChartData` type 增加 `emas: Record<string, ChartSeriesPoint[]>` |
| `frontend/src/cockpit/widgets/CockpitChartWidget.tsx` | 修改 | 仿照 MA 渲染循环为 EMA10/EMA21 增加 LineSeries，**复用 MA 颜色 token (`MA_TOKENS['10']` / `MA_TOKENS['21']`)，用 `lineStyle: LineStyle.Dashed` 区分** |
| `frontend/src/cockpit/widgets/MarketRegimeWidget.tsx` | 修改 | 第 129 行 `singleTradeRiskPct.toFixed(1)` → `toFixed(2)`，让 1.25 精确显示为 1.25%（影响所有 regime 档位：0.75%/1.00%/1.25% 等） |

⚠️ **恰好 6 文件**：满足 6-file 原则上限。

👤 用户确认文件列表合理后，方可进入开发。

---

## 文档同步（开发前/后必做）

| 阶段 | 文档 | 改动 |
|------|------|------|
| **开发前** | API-CONTRACT.md §GET /api/cockpit/chart/{ticker} | 在返回结构示例中追加 `emas: {"10": [...], "21": [...]}`；查询参数表追加 `emas` 可选参数说明（与 `mas` 等价） |
| **开发前** | DATA-MODEL.md | 零改动（不动 schema） |
| **开发后** | DECISIONS.md | 追加 D076：RISK_ON 单笔风险上限从 1.5% 调整为 1.25%（对齐 SRS 第十节"单笔风险 ≤ 1.25%"） |
| **开发后** | DECISIONS.md | 追加 D077：cockpit chart 新增 EMA 序列，与 SMA 共存（EMA 用于退出规则 trailing，SMA 用于趋势分类） |

---

## 可测试的完成标准

| # | 标准描述 | 测试层级 | 工具 |
|---|---------|---------|------|
| 1 | `_compute_ema_series(bars, 10)` 对已知输入返回数学正确的 EMA 序列（seed=SMA(10)；递推 α=2/11）；period >= len(bars) 时返回 []；与一个手动验算的 fixture 比对到 1e-6 精度 | 单元 | pytest |
| 2 | `_compute_ema_series` 对 period=21 与 lightweight-charts 同算法（α=2/22）输出一致 | 单元 | pytest |
| 3 | `CockpitChartService.get_chart(ticker)` 返回的 dict 包含 `emas` key，且 `emas['10']` 与 `emas['21']` 都是非空 list（在 bars >= 22 时） | 单元 | pytest（用 mock bars） |
| 4 | `CockpitChartData` Pydantic schema 接受 `emas` 字段，validation 通过；序列化为 camelCase `emas` | 单元 | pytest |
| 5 | `MarketRegimeService.compute_and_store()` 在 `regime=RISK_ON` 时写入的 `single_trade_risk_pct = 1.25`（不再是 1.5）；其他 4 档位不变 | 集成 | pytest（mock SPY/QQQ/IWM/sector 让 market_score ≥ 80） |
| 6 | `GET /api/cockpit/chart/AAPL?mas=50,150&days=250` 响应包含 `emas` 字段，默认 `emas['10']` / `emas['21']` 非空 | 集成 | pytest httpx + TestClient |
| 7 | `GET /api/cockpit/regime` 在 mock RISK_ON 状态下返回 `singleTradeRiskPct=1.25` | 集成 | pytest |
| 8 | `CockpitChartWidget` 在 chart_data 含 emas 时渲染 EMA10 / EMA21 两条 LineSeries（`lineStyle=LineStyle.Dashed`），无 console.error | 单元（前端） | vitest + @testing-library |
| 9 | `MarketRegimeWidget` 在 regime=RISK_ON 时显示 "Risk/Trade: **1.25%**"（toFixed(2) 精确显示）；其他档位也按 2 位精度（0.75% / 1.00% / 0.50% / 0.00%） | 单元（前端） | vitest |
| 10 | 全量后端 pytest 套件无新增失败 | 回归 | pytest |
| 11 | 全量前端 vitest 套件无新增失败 | 回归 | vitest |

---

## 已确认的协商点（2026-05-12）

| # | 协商点 | 决定 |
|---|--------|------|
| 1 | 单笔风险显示精度 | **改 `toFixed(2)`**，让 1.25 精确显示为 1.25%；MarketRegimeWidget.tsx 加入文件清单（共 6 文件，仍合规） |
| 2 | EMA 颜色 token | **复用 SMA 颜色 + `LineStyle.Dashed` 区分**，不引入新 token，零 tokens.css 变更 |
| 3 | `?emas=...` 查询参数 | **不开放**，EMA 周期固定为 `CHART.DEFAULT_EMAS = [10, 21]`；router 与 service 都不接受 `emas` 查询参数 |

---

## Evaluator 自检清单

开发完成后，Evaluator 模式逐条检查：

- [ ] 单元测试全部通过（`cd backend && pytest tests/cockpit/test_chart_service.py tests/cockpit/test_market_regime_service.py -v`）
- [ ] 集成测试全部通过（`cd backend && pytest tests/cockpit/test_chart_router.py tests/cockpit/test_regime_router.py -v`）
- [ ] 前端单元测试通过（`cd frontend && pnpm test`）
- [ ] 全量后端 pytest 通过（`cd backend && pytest`）
- [ ] 全量前端 vitest 通过（`cd frontend && pnpm test`）
- [ ] API 响应格式符合 API-CONTRACT.md（emas 字段已记录）
- [ ] 数据库零变更（无 alembic migration 文件被创建）
- [ ] UI 对照 design-spec.md：chart widget 在 4 种状态下（正常 / 加载 / 空数据 / 错误）EMA 渲染逻辑都不报错
- [ ] 无 console.error 遗留
- [ ] DECISIONS.md 追加 D076 + D077
- [ ] Lint 通过（`pnpm lint` / 后端 ruff or 等价）
- [ ] 无死代码（删除了任何调试 print/console.log）
- [ ] 无硬编码魔法值（EMA 周期、颜色都通过 CHART 参数 / tokens）

---

👤 **本 Contract 已于 2026-05-12 用户确认（按推荐方案）。下一 session 进入 Generator 模式开始开发。**
