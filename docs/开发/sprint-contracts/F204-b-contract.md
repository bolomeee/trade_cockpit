# Sprint Contract：F204-b — Earnings Calendar 接入层

> 状态：草案 | 起草：2026-04-24
> 父 Feature：F204 Earnings Calendar
> 前置：F204-a（done）— earnings_events 表 + EarningsService 已就绪
> 引用文档：
>   - API-CONTRACT.md §Cockpit Earnings（GET /api/cockpit/earnings）
>   - ARCHITECTURE.md §后端分层约定 + §依赖边界 D065
>   - DATA-MODEL.md §earnings_events

---

## 0. 背景与定位

F204-a 完成了数据层：`earnings_events` 表、`EarningsEventRepository`、`EarningsService`（含 `fetch_and_store` + `get_next_earnings`）。

F204-b（本 Sprint）完成接入层：
- **Cron**：每个工作日 05:30 UTC 自动刷新 earnings 窗口（今日 -7 ~ +30 天）
- **Router**：`GET /api/cockpit/earnings?ticker=AAPL` 对外暴露 API
- **Schema**：Pydantic `EarningsResponse` 封装响应格式

---

## 1. 范围

### 包含
- `backend/app/config.py`：添加 `earnings_cron_hour=5`, `earnings_cron_minute=30`
- `backend/app/services/refresh_job.py`：添加 `EARNINGS_JOB_ID` + `_earnings_tick` + 在 `start_scheduler` 注册 earnings cron（weekdays 05:30 UTC）
- `backend/app/schemas/cockpit/__init__.py`：新建（空 package marker）
- `backend/app/schemas/cockpit/earnings.py`：新建 `EarningsData` + `EarningsResponse`
- `backend/app/routers/cockpit/earnings.py`：新建 `GET /earnings` endpoint
- `backend/app/routers/cockpit/__init__.py`：从空占位升级为真实 cockpit router（sub-include earnings）
- `backend/app/main.py`：include cockpit router，prefix="/api/cockpit"
- `backend/tests/test_earnings_f204b.py`：API 层测试（TestClient）

### 排除
- `cockpit_params.py` §4 EARNINGS 阈值（F202 落地）
- 前端 Earnings Widget（v1.9 P1）
- earnings 数据补拉逻辑（已在 F204-a 实现）

---

## 2. 预计修改文件（共 7 个产品文件 + 1 个测试文件）

| # | 文件 | 动作 |
|---|------|------|
| 1 | `backend/app/config.py` | 修改 |
| 2 | `backend/app/services/refresh_job.py` | 修改 |
| 3 | `backend/app/schemas/cockpit/__init__.py` | 新建（空） |
| 4 | `backend/app/schemas/cockpit/earnings.py` | 新建 |
| 5 | `backend/app/routers/cockpit/earnings.py` | 新建 |
| 6 | `backend/app/routers/cockpit/__init__.py` | 修改 |
| 7 | `backend/app/main.py` | 修改 |
| 8 | `backend/tests/test_earnings_f204b.py` | 新建 |

> ⚠️ 共 8 个文件（7 产品 + 1 测试）。相比单 Sprint 6 文件上限多 2 个；
> 但 F204-a 验收时已约定 F204-b 范围为以上文件，且 `schemas/cockpit/__init__.py` 是 1 行 package marker。
> 该范围由上一 session 用户确认，本 Sprint 直接执行。

---

## 3. API 合约引用（API-CONTRACT.md §Cockpit Earnings）

```
GET /api/cockpit/earnings?ticker=AAPL

成功（有 earnings）→ 200:
{
  "data": {
    "ticker": "NVDA",
    "nextEarningsDate": "2026-05-22",
    "daysUntil": 28,
    "timeOfDay": "AMC",
    "epsEstimate": 5.20,
    "revenueEstimate": 48000000000
  },
  "message": "success"
}

成功（无 earnings）→ 200:
{
  "data": {
    "ticker": "NVDA",
    "nextEarningsDate": null,
    "daysUntil": null,
    "timeOfDay": null,
    "epsEstimate": null,
    "revenueEstimate": null,
    "note": "No upcoming earnings in next 30 days"
  },
  "message": "success"
}

ticker 缺失 → 422 VALIDATION_ERROR
```

---

## 4. 完成标准

| # | 标准 | 测试层 | 工具 |
|---|------|--------|------|
| S1 | GET /api/cockpit/earnings?ticker=AAPL 返回 200 + 完整 earnings 数据（DB 有记录） | 集成 | TestClient |
| S2 | GET /api/cockpit/earnings?ticker=AAPL 返回 200 + null 字段 + note（DB 无记录） | 集成 | TestClient |
| S3 | GET /api/cockpit/earnings 缺少 ticker → 422 VALIDATION_ERROR | 集成 | TestClient |
| S4 | EarningsService.get_next_earnings 被调用，ticker 转大写 | 集成 | TestClient |
| S5 | start_scheduler 注册 earnings job（05:30 UTC, mon-fri）| 单元 | 检查 sched.get_jobs() |
| S6 | _earnings_tick 调用 EarningsService.fetch_and_store，无异常时正常完成 | 单元 | Mock EarningsService |
| S7 | _earnings_tick 异常时不抛出（logger.error 兜底，与现有 tick 函数行为一致）| 单元 | Mock raises |
| S8 | pnpm build 通过（无前端改动，但验证 backend 无 syntax error）| 构建 | pytest --tb=short |

---

## 5. Evaluator 自检清单

- [ ] 8 个测试用例全部通过（S1–S8）
- [ ] 全量回归通过（或新失败为预先存在）
- [ ] `GET /api/cockpit/earnings?ticker=AAPL` 响应字段全部 camelCase（via CamelModel alias_generator）
- [ ] cockpit router prefix 为 `/api/cockpit`，earnings endpoint 路径为 `/earnings`（不重复 prefix）
- [ ] `schemas/cockpit/earnings.py` 继承 `CamelModel`（与现有 schemas 一致）
- [ ] `refresh_job.py`：earnings tick 异常捕获与 `_scanner_tick` / `_universe_tick` 保持一致（BLE001）
- [ ] `main.py` import 顺序：existing routers 不重排，cockpit router 追加在末尾
- [ ] D065 合规：`routers/cockpit/earnings.py` 无 workbench import
- [ ] 技术决策（如有）追加 DECISIONS.md

---

## 6. 开发顺序

```
1. config.py — 添加 earnings_cron 字段
2. refresh_job.py — 添加 tick + 注册 cron
3. schemas/cockpit/__init__.py（空）+ schemas/cockpit/earnings.py
4. routers/cockpit/earnings.py（endpoint）
5. routers/cockpit/__init__.py（从占位升级为真实 router）
6. main.py（include cockpit router）
7. test_earnings_f204b.py（S1–S8）
```
