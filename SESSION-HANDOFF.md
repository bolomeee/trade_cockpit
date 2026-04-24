# SESSION-HANDOFF — 2026-04-24（F204-b 完成，进入 F201）

> 覆盖上一版 handoff（F204-a done → F204-b）。本次完成 F204-b Earnings Calendar 接入层，用户验收通过。

## 立即执行指令（给下一个 session）

**开启新 session 后，说**：

> 继续 Cockpit Epic v1.8 开发。F200-a、F200-b、F204-a、F204-b 均已验收通过（done）。
> 读以下文件后决定下一步：
> 1. `CLAUDE.md`
> 2. `SESSION-HANDOFF.md`（本文件）
> 3. `claude-progress.txt` 末尾条目
> 4. `docs/需求/features.json`（_pipeline_status + active_sprint）
>
> 下一个 sprint 是 **F201**（Market Regime Widget：后端计分引擎 + `/api/cockpit/regime` endpoint）。
> 进入 feature-dev skill，走 Sprint Contract 协商流程。

---

## 本次 session 做了什么

实现 F204-b：Earnings Calendar 接入层。

### 产出清单

| 文件 | 动作 | 说明 |
|---|---|---|
| `backend/app/config.py` | 修改 | +`earnings_cron_hour=5`, `earnings_cron_minute=30` |
| `backend/app/services/refresh_job.py` | 修改 | `EARNINGS_JOB_ID` + `_earnings_tick`（weekdays 05:30 UTC） |
| `backend/app/schemas/cockpit/__init__.py` | 新建 | package marker |
| `backend/app/schemas/cockpit/earnings.py` | 新建 | `EarningsData` + `EarningsResponse`（CamelModel） |
| `backend/app/routers/cockpit/earnings.py` | 新建 | `GET /earnings` endpoint，注入 EarningsService |
| `backend/app/routers/cockpit/__init__.py` | 修改 | 从 F200-b 空占位升级为真实 cockpit APIRouter |
| `backend/app/main.py` | 修改 | `app.include_router(cockpit_router, prefix="/api/cockpit")` |
| `backend/tests/test_earnings_f204b.py` | 新建 | 7/7 测试（S1–S7） |
| `docs/开发/sprint-contracts/F204-b-contract.md` | 新建 | Sprint Contract |
| `docs/需求/features.json` | 修改 | F204-b → done；active_sprint → F201 |
| `claude-progress.txt` | 追加 | F204-b Sprint 条目 |

### Evaluator 自检结果

- 7/7 F204-b 测试通过 ✅
- 全量回归：368 passed；1 pre-existing failure（test_news_api）✅
- GET /api/cockpit/earnings?ticker=AAPL → 200 camelCase 响应 ✅
- 用户手动验收：启动后端访问端点，确认 API 通畅 ✅
- commit: `af972f8 feat(F204-b): Earnings Calendar 接入层（Cron + Router）`

---

## v1.8 P0 执行路线图（当前位置）

```
[F200-a 前端骨架]                    ✅ done
        ↓
[F200-b TopNav + backend 骨架]       ✅ done
        ↓
[F204-a Earnings Calendar 数据层]    ✅ done
        ↓
[F204-b Earnings Calendar 接入层]    ✅ done
        ↓
[F201 Market Regime Widget]          ← 下一个 sprint（新 session）
        ↓
[F202 Setup Monitor Widget]（依赖 F201+F204）
        ↓
[F203-a/b/c Decision Panel]
        ↓
v1.8.0 发版
```

---

## F201 概要（给下一个 session 的 Sprint Contract 协商素材）

**目标**：实现 `GET /api/cockpit/regime` endpoint，返回 market regime 打分 + SPY/QQQ/IWM 指数卡片 + 11 sector heatmap。

**涉及数据**：
- `market_regime_snapshots` 表（需确认是否已存在，或需 Alembic 迁移新建）
- `market_indices` 表（已存在，含 SPY/QQQ/IWM/XL* 数据）
- `cockpit_params.py` §0（regime 权重）+ §1（regime 枚举阈值）

**注意**：
- F201 可能需要拆分为 F201-a（数据层：model + repo + 计分 service）和 F201-b（接入层：cron + router），对照 F204 的拆分模式
- 需要先查 `docs/系统设计/DATA-MODEL.md` 确认 `market_regime_snapshots` 表是否已定义
- cockpit_params.py 是 F201 首次落地的关键新文件（§0 regime weight + §1 threshold）

**API-CONTRACT 引用**：`GET /api/cockpit/regime`（已定义，见 API-CONTRACT.md §Cockpit Market Regime）

---

## 给下一个 session 的提醒

1. **F200-a/b + F204-a/b 均为 done** — 不用再回顾
2. **下一个 sprint 是 F201**（Market Regime Widget，后端为主）
3. **pre-existing test failure**：`tests/test_news_api.py::test_fmp_failure_with_cached_data_returns_degraded` 已作为独立 task 标记，不阻塞 F201
4. **cockpit router 已就绪**：`app.include_router(cockpit_router, prefix="/api/cockpit")` 已在 main.py 注册，F201 只需在 `routers/cockpit/__init__.py` include 新 sub-router

## 未决事项

- `test_news_api.py::test_fmp_failure_with_cached_data_returns_degraded`：预先存在，已标记独立修复（非 F201 阻塞）
