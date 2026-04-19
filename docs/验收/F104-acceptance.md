# F104 最终验收清单

**项目**：MA150 Tracker → Workbench
**Feature**：F104 数据源迁移到 FMP（工程 feature）
**日期**：2026-04-19
**本地预览**：http://localhost:5173
**Sprint Contracts**：F104-s1 / s2 / s2c / s3
**决策记录**：D034（迁移）→ D035（错误推翻）→ D036（两端点合并，正解）

---

## 技术门禁（已自动完成）

| 项 | 结果 |
|---|------|
| 全量单元/集成回归 | ✅ 177/177 passed, 7 deselected |
| Live smoke（真实 FMP key） | ✅ 7/7 passed |
| 无 TS 错误（前端编译） | 待 `pnpm build` 验证 |
| polygon_client.py 仅作 deprecated re-export | ✅ 仅 `app/external/__init__.py` 引用 |

---

## 业务逻辑确认（按 acceptance_criteria）

| # | 检查项 | 期望 | 实际结果 | 状态 |
|---|---|---|---|---|
| B1 | `/api/stocks/search?q=App` | symbol 前缀优先，fallback 公司名 | 已通过 live smoke `test_live_search_*` 两案例 | ✅ |
| B2 | `/api/stocks/AAPL/chart` 响应 schema 零变化 | bars/ma150/pullbackMarkers 前端无需改 | 已通过 `test_stock_detail` 12 个案例 | ✅ |
| B3 | `/api/stocks/AAPL/fundamentals` 真实数据 | `source=fmp`，PE/PS/PEG/ROCE/FCF/marketCap 真值 | curl 实测 AAPL：PE 33.84 / FCF 123.3B / MC 3.97T | ✅ |
| B4 | `/api/stocks/MELI/fundamentals` 外部源交叉验证 | FCF 与 StockAnalysis.com 同量级 | 10.1B vs 10.77B（误差 <7%） | ✅（用户确认） |
| B5 | `/api/market/overview` SPX/NDX/TNX 正常 | DB 层 symbol 保留 SPX/NDX/TNX | 已通过 `test_market_refresh` + `test_market_api` | ✅ |
| B6 | fundamentals 失败字段返回 null | 缺字段 → null，不报 422 | `test_fundamentals_nullifies_*` 3 案例通过 | ✅ |
| B7 | pytest 全量 + live smoke 全通 | 0 regression | 177/177 + 7/7 | ✅ |

---

## 视觉/交互确认（你在浏览器亲眼验证）

| # | 场景 | 期望 | 你的观察 | 状态 |
|---|---|---|---|---|
| V1 | 访问 http://localhost:5173 选 AAPL | Fundamentals widget 显示真实 PE/PS/PEG/ROCE/FCF/MC | ✅ 已确认 | ✅ |
| V2 | 切到 MELI | FCF ≈ 10.1B（不是 mock 哈希值） | ✅ 已确认并交叉验证 | ✅ |
| V3 | Network tab 看 `/fundamentals` 响应 `source` 字段 | 值为 `"fmp"` | 待你 F12 看一眼确认 | ⬜ |
| V4 | 切到其他 ticker（META / ORCL / PLTR / F / SMCI） | 数据都能渲染，某些字段可能为 `—` | 待你各切一次 | ⬜ |
| V5 | FundamentalsCard 无"Mock Data" banner 残留 | 前端代码本就无 banner，视觉应干净 | 待你确认 | ⬜ |

---

## 边缘情况抽查

| # | 场景 | 期望 | 实际结果 | 状态 |
|---|---|---|---|---|
| E1 | 访问 watchlist 外的 ticker（如 `/api/stocks/ZZZZ/fundamentals`） | 404 NOT_FOUND | `test_detail_endpoints_404_when_ticker_missing` 通过 | ✅ |
| E2 | FMP 网络异常时 | 502 EXTERNAL_API_ERROR | `test_fundamentals_502_when_fmp_http_error` 通过 | ✅ |
| E3 | ticker 大小写不敏感 | `/api/stocks/aapl/fundamentals` 也能取数 | `test_detail_endpoints_are_case_insensitive` 通过 | ✅ |

---

## 已知遗留（非阻塞，记录在案）

1. **前端 `Fundamentals` TS 类型**仍为 `number` 非空；后端已 nullable。TS 运行时容错足够（`FundamentalsCard.formatRatio` 接受 `null | undefined`），但类型严格性欠。——D034 约束不改前端类型；建议 v1.2 Sprint 跟进。
2. **前端 FCF 为 null 时显示 `$0.00`**（非 `—`）：`FundamentalsCard` FCF 分支未 null-check。Sprint Contract 已说明"前端不改"。建议同上。
3. **D035 决策保留但已被 D036 修订**：保留是为留下"观察 → 误判 → 修正"的审计痕迹，不删。

---

## 验收决定

等你完成上面 V3 / V4 / V5 三项浏览器检查，给我回复任意：
- **"通过"** → 我更新 features.json phase → done，生成 v1.2 acceptance 聚合记录
- **"V3 有问题"** / **"MELI 没显示"** 等具体 → 我转入 feature-dev 类型 C/D 修复

⚠️ 用户要求：**不合并到 main 分支**。验收通过后：
- 仅在当前分支 `feat-newfeature` 打 patch 级 tag（可选）
- **不** push、**不** merge、**不** PR 到 main
- 下一次 session 由用户决定何时合并
