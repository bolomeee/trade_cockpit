# SESSION-HANDOFF — 2026-04-24（F204-a 完成，needs_review → done；进入 F204-b）

> 覆盖上一版 handoff（F200-a + F200-b needs_review）。本次完成 F204-a Earnings Calendar 数据层，用户验收通过。

## 立即执行指令（给下一个 session）

**开启新 session 后，说**：

> 继续 Cockpit Epic v1.8 开发。F200-a、F200-b、F204-a 均已验收通过（done）。
> 读以下文件后决定下一步：
> 1. `CLAUDE.md`
> 2. `SESSION-HANDOFF.md`（本文件）
> 3. `claude-progress.txt` 末尾条目
> 4. `docs/需求/features.json`（_pipeline_status + active_sprint）
>
> 下一个 sprint 是 **F204-b**（Earnings Calendar 接入层：Config cron + APScheduler + Schema + Router + main.py 注册）。
> 进入 feature-dev skill，走 Sprint Contract 协商流程。

---

## 本次 session 做了什么

实现 F204-a：Earnings Calendar 数据层。

### 产出清单

| 文件 | 动作 | 说明 |
|---|---|---|
| `backend/alembic/versions/008_f204_earnings_events.py` | 新建 | Alembic 迁移；upgrade/downgrade 双向验证 |
| `backend/app/models/earnings_event.py` | 新建 | SQLAlchemy model，严格对照 DATA-MODEL.md |
| `backend/app/models/__init__.py` | 修改 | +1 import EarningsEvent |
| `backend/app/repositories/earnings_event_repository.py` | 新建 | upsert_batch（actual None 保护）+ get_next + delete_before |
| `backend/app/external/fmp_client.py` | 修改 | FMP_EP_EARNINGS_CALENDAR 常量 + get_earnings_calendar() |
| `backend/app/services/cockpit/earnings_service.py` | 新建 | fetch_and_store（today-7 ~ today+30）+ get_next_earnings（camelCase） |
| `backend/tests/conftest.py` | 修改 | FakeFMP 新增 earnings_calendar_* 属性和方法 |
| `backend/tests/test_earnings_f204a.py` | 新建 | 12 个单元/集成测试，覆盖 Sprint Contract 标准 3–11 |
| `backend/tests/test_schema.py` | 修改 | EXPECTED_TABLES 加入 "earnings_events" |
| `docs/开发/sprint-contracts/F204-a-contract.md` | 新建 | F204-a Sprint Contract |
| `docs/需求/features.json` | 修改 | F204 拆为 F204-a(done)/F204-b(design_ready)；active_sprint=F204-b |
| `claude-progress.txt` | 追加 | F204-a Sprint 条目 |

### Evaluator 自检结果

- 12/12 单元/集成测试通过 ✅
- 全量回归：361 passed（1 pre-existing failure：test_news_api，与 F204-a 无关）✅
- upsert actual=None 保留旧值（关键业务规则）✅
- time_of_day normalization：BMO/AMC 保留，其他映射 None ✅
- D065 合规：earnings_service.py 无 workbench 引用 ✅
- commit: `da10c33 feat(F204-a): Earnings Calendar 数据层`

---

## v1.8 P0 执行路线图（当前位置）

```
[F200-a 前端骨架]          ✅ done（用户验收）
        ↓
[F200-b TopNav + backend 骨架 + ESLint]  ✅ done（用户验收）
        ↓
[F204-a Earnings Calendar 数据层]  ✅ done（用户验收）
        ↓
[F204-b Earnings Calendar 接入层]  ← 下一个 sprint（新 session）
        ↓
[F201 Market Regime Widget]（首个业务 widget；首创 cockpit_params.py §0+§1）
        ↓
[F202 Setup Monitor Widget]（依赖 F201+F204）
        ↓
[F203-a/b/c Decision Panel]
        ↓
v1.8.0 发版
```

---

## F204-b 概要（给下一个 session 的 Sprint Contract 协商素材）

**6 文件**：

| # | 文件 | 动作 |
|---|------|------|
| 1 | `backend/app/config.py` | 修改（add `earnings_cron_hour/minute`，默认 5/30） |
| 2 | `backend/app/services/refresh_job.py` | 修改（add earnings cron job，weekdays 05:30 UTC，调用 EarningsService.fetch_and_store） |
| 3 | `backend/app/schemas/cockpit/earnings.py` | 新建（Pydantic EarningsResponse schema） |
| 4 | `backend/app/routers/cockpit/earnings.py` | 新建（GET /api/cockpit/earnings，注入 EarningsService） |
| 5 | `backend/app/routers/cockpit/__init__.py` | 修改（组装 cockpit APIRouter，include earnings sub-router） |
| 6 | `backend/app/main.py` | 修改（app.include_router(cockpit_router, prefix="/api/cockpit")） |

**API**：`GET /api/cockpit/earnings?ticker=AAPL` → API-CONTRACT.md §Cockpit Earnings

**注意**：
- `backend/app/schemas/cockpit/` 目录需新建（目前只有 `schemas/__init__.py`，没有 cockpit 子目录）
- `backend/app/routers/cockpit/__init__.py` 已存在（F200-b 建的空占位），需修改为真实 router
- `main.py` 当前 import 路径：`from app.routers import data, journal, logs, market, news, signals, stocks, watchlist`；需新增 cockpit router

---

## 给下一个 session 的提醒

1. **F200-a + F200-b + F204-a 均为 done** — 验收已通过，不用再回顾
2. **下一个 sprint 是 F204-b**（接入层，纯后端，无前端改动）
3. **pre-existing test failure**：`tests/test_news_api.py::test_fmp_failure_with_cached_data_returns_degraded` 在 F204-a 前已存在，不属于 F204-b 的修复范围，不阻塞
4. **cockpit_params.py §4 EARNINGS 阈值**：不在 F204-b 范围（由 F202 落地）
5. **前端 Earnings Widget**：不在 v1.8 P0 范围（v1.9 P1）

## 未决事项

- `test_news_api.py::test_fmp_failure_with_cached_data_returns_degraded`：预先存在的 failure，需独立 session 排查修复（非 F204 相关）
