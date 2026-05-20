---
status: confirmed
drafted_at: 2026-05-20
confirmed_at: 2026-05-20
sprint: F218-d7a
parent_feature: F218
---

# F218-d7a Sprint Contract — Repricing Trigger cron 注册 + router + 2 endpoint

> 生成：2026-05-20 | 状态：已确认 → 进入 Generator
> Feature：[F218](docs/需求/features.json) Cockpit Phase D — Repricing Trigger 完整框架（5 类）
> Sub-sprint：F218-d7a（Phase D 10 sub-sprint 第 9 个；cron 接线 + 后端 router）
> 前置：F218-d1~d6b 全部 done（5 detector 实装完毕；service 主入口 `compute_and_store_all_triggers` 可调用；`RepricingTriggerRepository.get_active_for_ticker` / `get_all_active` 读接口就绪）
> 下游：F218-d7b（前端 widget + DecisionPanel chip）

> 引用文档：
> - [ARCHITECTURE.md](docs/系统设计/ARCHITECTURE.md) §Cockpit Repricing Trigger Service 533-593（cron 22:40 UTC weekdays / router 位置 / 模块边界）
> - [API-CONTRACT.md](docs/系统设计/API-CONTRACT.md) §Cockpit Repricing Triggers 1988-2106（2 endpoint 完整契约 / 错误响应 / 字段说明）
> - [DATA-MODEL.md](docs/系统设计/DATA-MODEL.md) §RepricingTrigger 1080-1129（5 类 evidence_json schema / confidence 规则）
> - [F218-d6b-contract.md](docs/开发/sprint-contracts/F218-d6b-contract.md) — 上游 sprint 下游清单声明
> - [refresh_job.py](backend/app/services/refresh_job.py) — 现有 9 cron 模式样板
> - [test_weekly_stage_cron_f216e.py](backend/tests/test_weekly_stage_cron_f216e.py) — 同模式 cron 测试样板（S1/S2a/S2b）

---

## 0. 背景与定位

d6b 收工后，RepricingTriggerService 5 detector + 主入口 `compute_and_store_all_triggers` 已可独立调用。但目前没有任何自动化触发路径，前端也没有 endpoint 可消费。d7a 把"调度 + HTTP 出口"两件事接线，闭合 Phase D 后端环：

- **cron**：每个交易日 22:40 UTC 触发 `RepricingTriggerService.compute_and_store_all_triggers()`，写 `repricing_triggers` 表
- **router**：暴露 2 endpoint 让前端按需读 `active=true` 行（单标的 + 全市场）

d7a 不动 detector 逻辑，不动 repo 读接口（d1 已实现 `get_active_for_ticker` / `get_all_active`），不动文档（4 份 status=confirmed）。

---

## 1. 实现范围

### 1.1 cron 注册（`backend/app/services/refresh_job.py`）

**顶部追加常量段**（与既有 `POOL_CACHE_CRON` / `PENDING_ORDERS_EXPIRER_CRON` 模式并列）：

```python
# F218-d7a: repricing triggers compute, weekdays 22:40 UTC
# After: setup_cron (22:30) → pending_orders_expirer (22:35) → repricing (22:40).
# Detectors are pure-DB reads; no FMP calls in this tick.
REPRICING_TRIGGER_CRON = "40 22 * * 1-5"
REPRICING_TRIGGER_JOB_ID = "cockpit_repricing_triggers"
```

**顶部 import 追加**：

```python
from app.services.cockpit.repricing_trigger_service import RepricingTriggerService
```

**`start_scheduler` 内追加 add_job 块**（位置：紧跟既有 `_pool_cache_tick` 注册块之后；保持声明顺序与既有调度链对齐）：

```python
# F218-d7a: repricing triggers compute, weekdays 22:40 UTC
sched.add_job(
    _repricing_trigger_tick,
    trigger=CronTrigger.from_crontab(REPRICING_TRIGGER_CRON, timezone="UTC"),
    id=REPRICING_TRIGGER_JOB_ID,
    args=[session_factory, fmp_factory],
    replace_existing=True,
)
```

**模块级新增 tick 函数**（紧跟 `_pool_cache_tick` 之后）：

```python
def _repricing_trigger_tick(
    session_factory: SessionFactory,
    fmp_factory: FmpFactory,  # noqa: ARG001 — signature parity; detectors are pure-DB
) -> None:
    """APScheduler tick for RepricingTriggerService (F218-d7a): weekdays 22:40 UTC."""
    try:
        with _session_scope(session_factory) as db:
            RepricingTriggerService(db).compute_and_store_all_triggers()
    except Exception:  # noqa: BLE001
        logger.error("repricing trigger tick failed\n%s", traceback.format_exc())
```

`fmp_factory` 保留是为与同模块所有"周期跑数据"类 tick（regime / setup / weekly_stage / pool_cache）签名对齐，便于 `args=[session_factory, fmp_factory]` 统一传参；当前 detector 全部纯 DB 读不调用 FMP。

### 1.2 Pydantic schema（`backend/app/schemas/cockpit/repricing_trigger.py`，新建）

```python
"""F218-d7a: Pydantic response models for /api/cockpit/repricing-triggers."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

TriggerType = Literal[
    "EARNINGS_ACCEL",
    "MARGIN_EXPANSION",
    "NEW_PRODUCT",
    "SECTOR_CYCLE",
    "BALANCE_INFLECTION",
]


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class RepricingTriggerItem(CamelModel):
    """单条 trigger 项（用于单标的 endpoint，不带 ticker）。"""
    trigger_type: TriggerType
    detected_date: str            # ISO date YYYY-MM-DD
    confidence: float
    evidence: dict[str, Any]      # camelCase keys；schema 5 类按 trigger_type 区分（DATA-MODEL §1080-1129）
    computed_at: str              # ISO8601 UTC


class RepricingTriggerItemWithTicker(RepricingTriggerItem):
    """全市场 endpoint 用：单条带 ticker 字段。"""
    ticker: str


class TickerRepricingTriggersData(CamelModel):
    ticker: str
    triggers: list[RepricingTriggerItem]


class TickerRepricingTriggersResponse(BaseModel):
    data: TickerRepricingTriggersData
    message: str = "success"


class MarketRepricingTriggersData(CamelModel):
    triggers: list[RepricingTriggerItemWithTicker]
    total_count: int
    computed_at: str              # ISO8601 UTC


class MarketRepricingTriggersResponse(BaseModel):
    data: MarketRepricingTriggersData
    message: str = "success"
```

### 1.3 Router（`backend/app/routers/cockpit/repricing_triggers.py`，新建）

```python
"""F218-d7a: /api/cockpit/repricing-triggers — 2 endpoint (single ticker + market-wide)."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.repricing_trigger import RepricingTrigger
from app.repositories.repricing_trigger_repository import RepricingTriggerRepository
from app.schemas.cockpit.repricing_trigger import (
    MarketRepricingTriggersData,
    MarketRepricingTriggersResponse,
    RepricingTriggerItem,
    RepricingTriggerItemWithTicker,
    TickerRepricingTriggersData,
    TickerRepricingTriggersResponse,
    TriggerType,
)
from app.services.watchlist_service import APIError

router = APIRouter(prefix="/repricing-triggers", tags=["cockpit-repricing"])

_TICKER_RE = re.compile(r"^[A-Z0-9.\-]+$")


def _snake_to_camel(s: str) -> str:
    head, *tail = s.split("_")
    return head + "".join(w.title() for w in tail)


def _evidence_to_camel(evidence: dict) -> dict:
    """Recursively snake_case → camelCase keys on evidence dict (values untouched)."""
    return {_snake_to_camel(k): v for k, v in evidence.items()}


def _row_to_item(row: RepricingTrigger) -> dict:
    """Map ORM row → dict suitable for RepricingTriggerItem(WithTicker) validation."""
    evidence = _evidence_to_camel(json.loads(row.evidence_json))
    return {
        "ticker": row.ticker,
        "trigger_type": row.trigger_type,
        "detected_date": row.detected_date.isoformat(),
        "confidence": row.confidence,
        "evidence": evidence,
        "computed_at": row.computed_at.isoformat(),
    }


@router.get("/{ticker}", response_model=TickerRepricingTriggersResponse)
def get_repricing_triggers_for_ticker(
    ticker: str,
    db: Session = Depends(get_db),
) -> TickerRepricingTriggersResponse:
    """Return all active triggers for the given ticker (empty list if none)."""
    upper = ticker.upper()
    if not _TICKER_RE.match(upper):
        raise APIError("VALIDATION_ERROR", f"invalid ticker: {ticker}", 422)

    rows = RepricingTriggerRepository(db).get_active_for_ticker(upper)
    items = [RepricingTriggerItem.model_validate(_row_to_item(r)) for r in rows]
    return TickerRepricingTriggersResponse(
        data=TickerRepricingTriggersData(ticker=upper, triggers=items),
    )


@router.get("", response_model=MarketRepricingTriggersResponse)
def get_repricing_triggers_market(
    trigger_type: TriggerType | None = Query(default=None, alias="triggerType"),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> MarketRepricingTriggersResponse:
    """Return market-wide active triggers, optional filter by triggerType."""
    rows, total = RepricingTriggerRepository(db).get_all_active(
        trigger_type=trigger_type, limit=limit,
    )
    items = [RepricingTriggerItemWithTicker.model_validate(_row_to_item(r)) for r in rows]
    computed_at = (
        max(r.computed_at for r in rows).isoformat()
        if rows else datetime.now(timezone.utc).isoformat()
    )
    return MarketRepricingTriggersResponse(
        data=MarketRepricingTriggersData(
            triggers=items, total_count=total, computed_at=computed_at,
        ),
    )
```

### 1.4 Router include（`backend/app/routers/cockpit/__init__.py`）

```python
from app.routers.cockpit.repricing_triggers import router as repricing_triggers_router
# ...
router.include_router(repricing_triggers_router)
```

### 1.5 Tests

#### Cron 测试（`backend/tests/test_f218_d7a_repricing_cron.py`，新建，3 tests）

样板 = `test_weekly_stage_cron_f216e.py`：

| # | 测试 |
|---|------|
| S1 | `start_scheduler(autostart=False)` 注册 `REPRICING_TRIGGER_JOB_ID`；trigger fields `hour=22 / minute=40 / day_of_week=mon-fri`；timezone=UTC |
| S2a | `_repricing_trigger_tick(lambda: mock_db, lambda: None)` → `RepricingTriggerService(mock_db)` 实例化一次 + `compute_and_store_all_triggers()` 调用一次（mock 模式）|
| S2b | `RepricingTriggerService` 构造抛 `RuntimeError("DB down")` → `_repricing_trigger_tick` 不向上抛 |

#### Router 测试（`backend/tests/test_f218_d7a_repricing_router.py`，新建，8 tests）

使用 FastAPI TestClient + sqlite in-memory db_session fixture（复用既有 conftest）。

| # | 测试 | 场景 |
|---|------|------|
| R1 | seed `NVDA` 2 行 active triggers（MARGIN_EXPANSION + EARNINGS_ACCEL，不同 detected_date）→ `GET /api/cockpit/repricing-triggers/NVDA` → 200；`data.ticker=NVDA`；`triggers` 长度 2，按 `detectedDate` DESC；item 含 camelCase 字段 `triggerType` / `detectedDate` / `computedAt`；evidence keys 已 camelCase（如 `triggerMetric` / `expansionBp`）|
| R2 | 无 active triggers 的 ticker → 200 + `data.triggers=[]`（**不报 404**）|
| R3 | 输入 `aaa@@` / 含空格 / 空串 → 422 + error_code `VALIDATION_ERROR` |
| R4 | 小写 `nvda` → 自动 upper；返回 `data.ticker="NVDA"` |
| R5 | seed 3 ticker × 5 trigger 类型（共 15 active 行）→ `GET /api/cockpit/repricing-triggers` → 200；`triggers` 长度 15；`totalCount=15`；按 `detectedDate` DESC 同日按 `confidence` DESC；`computedAt` = max(rows.computed_at).isoformat() |
| R6 | `?triggerType=BALANCE_INFLECTION` 过滤 → 仅返 BALANCE_INFLECTION 行；`totalCount` = filter 后数 |
| R7 | `?triggerType=INVALID` → 422；`?limit=501` → 422；`?limit=0` → 422 |
| R8 | 表完全为空 → 200 + `triggers=[]` + `totalCount=0` + `computedAt` 是合法 ISO8601 UTC 串（约等于 now）|

**测试 helper**：
- `_seed_trigger(db, *, ticker, trigger_type, detected_date, confidence=0.5, evidence=None, active=True, computed_at=None)` 直接 INSERT `RepricingTrigger` 行
- evidence 默认按 trigger_type 给一个最小合法 dict（snake_case，如 T2 → `{"trigger_metric": "gross_margin", "expansion_bp": 900}`）→ 让 R1 断言能验 snake→camel 转换

**预期新增测试：11 个**（3 cron + 8 router）。

---

## 2. 预计修改文件

| # | 文件路径 | 改动类型 | 说明 |
|---|---------|---------|------|
| 1 | `backend/app/services/refresh_job.py` | 修改 | +2 顶部常量 / +1 import / +1 `add_job` 块 / +1 模块级 `_repricing_trigger_tick` 函数（~10 行） |
| 2 | `backend/app/routers/cockpit/repricing_triggers.py` | 新建 | 2 endpoint + ticker 校验 + evidence camelCase 转换 helper（~90 行） |
| 3 | `backend/app/routers/cockpit/__init__.py` | 修改 | +1 import / +1 `include_router` |
| 4 | `backend/app/schemas/cockpit/repricing_trigger.py` | 新建 | 6 Pydantic 类 + TriggerType Literal（~55 行） |
| 5 | `backend/tests/test_f218_d7a_repricing_cron.py` | 新建 | 3 tests / 2 class（TestScheduler + TestTick） |
| 6 | `backend/tests/test_f218_d7a_repricing_router.py` | 新建 | 8 tests / 2 class（TestTickerEndpoint + TestMarketEndpoint） |

**实际 6 文件 = 上限**，不超。

---

## 3. 可测试的完成标准

| # | 标准描述 | 测试层级 | 工具 |
|---|---------|---------|------|
| 1 | `start_scheduler(autostart=False)` 注册 `REPRICING_TRIGGER_JOB_ID`；trigger 字段 hour=22 / minute=40 / day_of_week=mon-fri；timezone=UTC | 单元 | pytest |
| 2 | `_repricing_trigger_tick(session_factory, fmp_factory)` 用 mock `RepricingTriggerService`：实例化用 db session，调用 `compute_and_store_all_triggers()` 一次 | 单元 | pytest + mock |
| 3 | `_repricing_trigger_tick` 内构造抛 `RuntimeError` → tick 不向上抛 | 单元 | pytest |
| 4 | seed 2 行 active triggers → `GET /api/cockpit/repricing-triggers/NVDA` → 200 + 长度 2 + DESC 排序 + evidence camelCase（`triggerMetric` / `expansionBp` 实际可断言）+ envelope 含 `data` `message="success"` | 集成 | pytest + TestClient |
| 5 | 无 active triggers → 200 + `triggers=[]`（不报 404）| 集成 | pytest |
| 6 | 非法 ticker（`aaa@@` / 含空格 / 空字符）→ 422 + error_code `VALIDATION_ERROR` | 集成 | pytest |
| 7 | 小写 `nvda` → 自动 upper，`data.ticker="NVDA"` | 集成 | pytest |
| 8 | seed 3 ticker × 5 trigger（15 active 行）→ `GET /api/cockpit/repricing-triggers` → 200 + `triggers` 长度 15 + `totalCount=15` + `computedAt = max(rows.computed_at).isoformat()` + 行项含 `ticker` 字段 + 排序 detectedDate DESC, confidence DESC | 集成 | pytest |
| 9 | `?triggerType=BALANCE_INFLECTION` → 仅返 BALANCE_INFLECTION 行；`totalCount` = filter 后数 | 集成 | pytest |
| 10 | `?triggerType=INVALID` / `?limit=501` / `?limit=0` → 全部 422 | 集成 | pytest |
| 11 | 表为空 → 200 + `triggers=[]` + `totalCount=0` + `computedAt` 是合法 ISO8601 UTC 串 | 集成 | pytest |

**预期测试数：11 个**。

---

## 4. Evaluator 自检清单

- [ ] 11 个新测试全部通过（`cd backend && uv run pytest tests/test_f218_d7a_repricing_cron.py tests/test_f218_d7a_repricing_router.py -v`）
- [ ] d1–d6b 既有测试全绿（`uv run pytest tests/test_repricing_trigger_skeleton.py tests/test_repricing_trigger_earnings_accel.py tests/test_repricing_trigger_margin_expansion.py tests/test_repricing_trigger_new_product.py tests/test_repricing_trigger_sector_cycle.py tests/test_repricing_trigger_balance_inflection.py tests/test_f218_d3a_key_metrics.py tests/test_f218_d6a_fundamentals.py -v`）
- [ ] 既有 cron 测试全绿（`uv run pytest tests/test_weekly_stage_cron_f216e.py tests/test_regime_f201b.py tests/test_setup_f202b.py tests/test_earnings_f204b.py tests/test_pending_order_expirer_f206b2.py tests/test_pool_service.py tests/test_journal_review_service_f211d2.py -v`）— 不得回归
- [ ] 全量后端回归 `uv run pytest` 通过 — 允许 9 个 pre-existing failures，不得新增
- [ ] `start_scheduler` 注册 job_id 数量 = 旧值 + 1（新增 `REPRICING_TRIGGER_JOB_ID`）
- [ ] 22:40 UTC 不与既有 cron 撞时段（既有：22:15 regime / 22:20 weekly_stage / 22:30 setup / 22:35 pending_orders_expirer → 22:40 repricing 不冲突）
- [ ] `app.main` 启动 + `app.openapi()` 含 `/api/cockpit/repricing-triggers/{ticker}` 和 `/api/cockpit/repricing-triggers` 两条路径
- [ ] evidence dict 内部 snake→camel 转换覆盖全部 5 类：T1 `eps_yoy_growth` / `revenue_yoy_growth` / T2 `gross_margin_trend` / `fcf_margin_trend` / `trigger_metric` / `expansion_bp` / T3 `match_count` / `keywords` / T4 `rs_percentile` / `sector_etf` / T5 `net_debt_trend` / `fcf_trend` / `trigger_metric` / `quarters`
- [ ] `computedAt` ISO8601 含 `Z` 或 `+00:00`，不裸 naive datetime
- [ ] APIError 抛出时 JSON 响应符合既有 cockpit router 错误 envelope 格式
- [ ] `RepricingTriggerService.__init__(db)` 签名未变；构造代价低（仅 4 repository 注入，无 IO）
- [ ] `RepricingTriggerRepository.get_active_for_ticker` / `get_all_active` 接口签名未变

### 代码质量检查
- [ ] router 单文件 < 150 行；2 endpoint 函数体各 < 30 行
- [ ] 无硬编码魔法值：`100`/`500` 抽 Query default/max；regex `^[A-Z0-9.\-]+$` 抽模块级常量 `_TICKER_RE`
- [ ] `_snake_to_camel` / `_evidence_to_camel` / `_row_to_item` 纯函数无副作用
- [ ] 无注释掉的代码 / 死 import / 未使用变量（`fmp_factory` 在 tick 签名用 `# noqa: ARG001` 显式标记）

### 回归测试
- [ ] 后端全量 `uv run pytest` 通过（允许 9 pre-existing failures，不得新增）
- [ ] cockpit 既有 router 测试（pool / chart / decision / positions / pending_orders / regime / setup / earnings / user_settings / actions）未受 router include 改动影响

---

## 5. 关键设计决策（已与用户确认，2026-05-20）

| # | 议题 | 已定方案 | 理由 |
|---|------|---------|------|
| **NP-d7a-1** | cron 时段配置位置 | refresh_job.py 顶部常量 `REPRICING_TRIGGER_CRON = "40 22 * * 1-5"`，不动 config.py | 与 `POOL_CACHE_CRON` / `PENDING_ORDERS_EXPIRER_CRON` 模式一致；22:40 UTC 是生产固定值，不需要 env 可配 |
| **NP-d7a-2** | tick 签名 | `_repricing_trigger_tick(session_factory, fmp_factory)` 保留 fmp_factory（`# noqa: ARG001`），未使用 | 与"周期跑数据"类 tick（regime/setup/weekly_stage/pool_cache）签名对齐；未来若 detector 需要 FMP 不用改签名 |
| **NP-d7a-3** | tick 错误吞咽 | `except Exception: logger.error(...)`，不向上抛 | 与同模块所有 tick 一致；apscheduler best practice，避免线程崩溃 |
| **NP-d7a-4** | service 实例化 | `with _session_scope(session_factory) as db: RepricingTriggerService(db).compute_and_store_all_triggers()` | 与 `_setup_tick` / `_weekly_stage_tick` 完全对称 |
| **NP-d7a-5** | router prefix / tag | `APIRouter(prefix="/repricing-triggers", tags=["cockpit-repricing"])` | 与 `cockpit-regime` / `cockpit-setup` tag 命名一致 |
| **NP-d7a-6** | ticker 校验 | upper → regex `^[A-Z0-9.\-]+$` → 不匹配 `APIError("VALIDATION_ERROR", ..., 422)` | API-CONTRACT §2047 要求；复用既有 APIError 模式 |
| **NP-d7a-7** | evidence schema 类型 | Pydantic `dict[str, Any]` + 手动 snake→camel 转 key；不为 5 类 evidence 写 discriminated union | 5 类 evidence shape 差异大，union 复杂度收益低；evidence 一致性由 detector 端 contract（d2-d6b）保证 |
| **NP-d7a-8** | 全市场 `computedAt` 语义 | `max(rows.computed_at).isoformat()`；表空 → `datetime.now(timezone.utc).isoformat()` | API-CONTRACT §2097 明文规定 |
| **NP-d7a-9** | `triggerType` query 校验 | FastAPI Query 用 `TriggerType` Literal，自动 422 | 不需手写校验；alias=`triggerType`（camelCase 入口） |
| **NP-d7a-10** | `limit` 校验 | `Query(default=100, ge=1, le=500)`，自动 422 | API-CONTRACT §2105 |

---

## 6. 不在范围（本 sprint 排除）

- ❌ 前端 `frontend/src/cockpit/lib/api/cockpitRepricingApi.ts` 客户端封装（→ d7b）
- ❌ `RepricingTriggerWidget.tsx` / `DecisionPanelWidget` chip 区（→ d7b）
- ❌ DATA-MODEL.md / API-CONTRACT.md / ARCHITECTURE.md 任何修改（4 文档 status=confirmed，严格无新增 drift）
- ❌ T1-T5 detector 逻辑变更（d2-d6b 收工）
- ❌ `RepricingTriggerRepository` 读接口扩展（`get_active_for_ticker` / `get_all_active` 已就绪）
- ❌ retention 调度（`delete_expired_inactive` 已实装但 cron 接线由独立 issue 决定）
- ❌ DECISIONS.md 追加（D096/D097/D098 已覆盖；NP-d7a-1~10 是实施级决策，由本 contract 承载）
- ❌ 真实 cron 触发的 e2e（mock SessionLocal + scheduler 反射足够；e2e 留 acceptance）
- ❌ T5 历史回测验证（acceptance 收官统一做）
- ❌ 并发 / 限流压测（5 detector × ~50 ticker 串行预估 < 10s，d7b 上线后再评估）

---

## 7. 开发顺序（Generator 模式执行）

1. **`refresh_job.py` 改动**（+常量 / +import / +add_job 块 / +tick 函数）→ 启动 import 跑通 → wip commit
2. **cron 单测**（`test_f218_d7a_repricing_cron.py` 3 tests）→ 全绿 → wip commit
3. **`schemas/cockpit/repricing_trigger.py` 新建** → import 通 → wip commit
4. **`routers/cockpit/repricing_triggers.py` 新建** + **`routers/cockpit/__init__.py` include** → `app.openapi()` 验证 2 路径出现 → wip commit
5. **router 集成测试**（`test_f218_d7a_repricing_router.py` 8 tests）→ 全绿 → wip commit
6. **全量回归 → Evaluator 自检 → consistency-check (C1/C4/C5) → phase=needs_review**

每步 wip commit **按文件名显式 add，禁用 `git add -A`**。

---

## 8. 用户已确认（2026-05-20）

- ✅ NP-d7a-1 ~ NP-d7a-10 全部按推荐
- ✅ 6 文件清单合理（正好等于上限）
- ✅ 11 测试规划合适
- ✅ 进入 Generator 模式开发（开新 session）
