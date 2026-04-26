# Sprint Contract：F206-b2 — Risk Summary 聚合 + APScheduler EXPIRED 自动转换

> 状态：草案，待用户确认 | 起草：2026-04-26
> 父 Feature：F206 Position Manager（v1.9 Cockpit P1）
> 拆分：F206-a ✅（Position 后端）/ F206-b1 ✅（PendingOrder 后端）/ **F206-b2（本 sprint，Summary + Scheduler）** / F206-c（前端 Widget）
> 依赖：
>   - F206-a ✅（PositionRepository / PositionService / `_PositionListData`）
>   - F206-b1 ✅（PendingOrderRepository / PendingOrderService / 状态机）
>   - F203-d ✅（`UserSettingsRepository.get_or_default()` 提供 `account_size`）
>   - 既有：`refresh_job.start_scheduler` 已注册 6 个 APScheduler 任务（DAILY/SCANNER/UNIVERSE/EARNINGS/REGIME/SETUP），追加第 7 个即可
>
> 引用文档：
>   - DATA-MODEL.md §PendingOrder line 587-589（"APScheduler 每日复用 REFRESH_CRON 末尾阶段扫描 ACTIVE 行过期则置 EXPIRED"）
>   - API-CONTRACT.md §GET /api/cockpit/positions line 1404-1450（`summary` 5 字段定义 + 计算口径）
>   - DECISIONS.md D066（仓位公式：account_size 作为分母）/ D041（last_close fallback）
>   - features.json#F206 acceptance_criteria 第 5 条（"Risk Summary：open_risk_pct / total_exposure_pct / pending_risk_pct / positions_count / pending_count"）
>   - 模板参考：
>     - `backend/app/services/refresh_job.py` line 247-259（`_setup_tick` 注册风格）
>     - `backend/app/services/cockpit/position_service.py` line 46-63（`list_positions` 当前签名 — 本 sprint 改为同时返回 summary）
>     - `backend/app/schemas/cockpit/position.py` line 118-125（`_PositionListData` — 本 sprint 增 `summary` 字段）

---

## 0. 背景与定位

F206-b2 是 F206 后端最后一块。本 sprint **不写前端**（→ F206-c），只补两件事：

1. **Risk Summary 聚合顶条**：`GET /api/cockpit/positions` 响应增加 `summary` 字段，5 个数值口径已在 API-CONTRACT.md line 1408-1413 锁死，本 sprint 实现并测试。
2. **APScheduler EXPIRED 自动转换**：每日盘后 tick，扫描 ACTIVE pending_orders，把 `expiration_date < today` 的行置 `EXPIRED`。

完成后 b1 + b2 + a 合并验收，再进 F206-c 前端。

---

## 关键约束（必须遵守）

### 1. Summary 计算口径（对照 API-CONTRACT.md line 1408-1413 + line 1449）

| 字段 | 公式 | 数据源 | 备注 |
|------|------|--------|------|
| `openRiskPct` | `Σ (entry_price - stop_price) × shares / account_size × 100` | OPEN positions | 2 位小数 |
| `totalExposurePct` | `Σ position_value / account_size × 100`，`position_value = last_close × shares` | OPEN positions | last_close 走 D041 fallback；若某行 last_close=None 则该行 exposure=0 计入分子（**降级**，不抛错） |
| `pendingRiskPct` | `Σ (entry_price - stop_price) × shares / account_size × 100` | ACTIVE pending_orders | 与 b1 单行 `riskPct` 公式一致，整体相加 |
| `positionsCount` | OPEN positions 行数（int） | — | — |
| `pendingCount` | ACTIVE pending_orders 行数（int） | — | **仅 ACTIVE**，不含 TRIGGERED/CANCELLED/EXPIRED |

**注意**：summary 总是基于 `OPEN` + `ACTIVE`，**与 query 的 `?status=` 参数无关**。即用户请求 `GET /api/cockpit/positions?status=closed` 仍返回基于 OPEN 的 summary（design 直觉：summary 是"当前账户风险快照"，不随列表过滤变化）。

**Q1（开放）**：以上 summary 与 query.status 解耦的语义需要用户确认。默认**解耦**。如果用户希望 summary 跟随过滤（例如 status=all 时 summary 含 CLOSED 历史），需要重新定义口径。

### 2. account_size = 0 / None 的容错

- `UserSettingsRepository.get_or_default()` 的 `account_size` 默认值已在 F203-d 落地（**先 grep 确认默认值，预计 100000**）
- 若实际取到 `account_size <= 0`：所有 `*Pct` 字段返回 `None`（前端见 None 显示 "—"），`positionsCount` / `pendingCount` 仍正常返回
- **不抛 500**，不抛 422（这是用户配置问题，不是请求问题）

### 3. Summary 性能预算

- list_positions 已经查 PositionRepository + LastCloseLoader；summary 额外触发：
  - `PendingOrderRepository.list_by_status("ACTIVE")` — 1 次 SQL
  - `UserSettingsRepository.get_or_default()` — 1 次 SQL（实际可复用 PositionService 已注入的 `_settings_repo`）
- **不对 pending_orders 触发 LastCloseLoader**（pending 的 risk 不依赖 last_close，只需 entry/stop/shares）— 节省 N 次 FMP
- 整体 GET /positions 在 N=10 持仓 + M=10 条件单情况下额外开销 < 50ms

### 4. APScheduler EXPIRED 任务

- **任务名**：`PENDING_ORDERS_EXPIRER_JOB_ID = "cockpit_pending_orders_expirer"`
- **触发时机**：weekdays 22:35 UTC（在 `_setup_tick` 22:30 之后 5 分钟，避开 setup scan）
  - 选择 weekdays 而非 daily：周末不触发；周末过期的 order 在周一 tick 时一并处理（`expiration_date < today` 判定，周一 today 已是周一，周日过期会被命中）
- **配置**：在 `app/config.py` 不新增 env，**直接在 `refresh_job.py` 顶部定义常量**（与 `DAILY_REFRESH_CRON` 风格一致）：
  ```python
  PENDING_ORDERS_EXPIRER_CRON = "35 22 * * 1-5"
  PENDING_ORDERS_EXPIRER_JOB_ID = "cockpit_pending_orders_expirer"
  ```
  **理由**：节省 1 个文件（`config.py` 不动），且本任务时间不需要环境覆盖（DAILY_REFRESH_CRON 也是常量）。**Q2（开放）**：是否需要 env 覆盖？默认**不需要**。

### 5. Expirer 函数签名 + 幂等

```python
# backend/app/services/cockpit/pending_order_expirer.py
def expire_due_pending_orders(db: Session, today: date | None = None) -> int:
    """Scan ACTIVE pending_orders with expiration_date < today, set status=EXPIRED.
    Returns number of rows updated. Idempotent (re-runs return 0)."""
```

- `today` 可注入（测试用）；默认 `date.today()`
- 实现走 `PendingOrderRepository.list_by_status("ACTIVE")` 过滤 → 每行 `repo.update(id, {"status": "EXPIRED"})`
- 不依赖 LastCloseLoader / FMP（纯本地 DB 操作，零外部 IO）
- **`expiration_date IS NULL` 的行不过期**（无失效日 = 永不过期）
- 写入 logger.info("expired %d pending orders", N)

### 6. Scheduler 注册风格沿用 refresh_job.py

新增 `_pending_orders_expirer_tick(session_factory)` 函数（不需要 `fmp_factory`，纯 DB 操作），try/except 兜底；在 `start_scheduler` 内 `sched.add_job(...)` 追加。

### 7. 字段命名 D074

`summary` 子对象使用 camelCase（`openRiskPct` 等）。沿用 `_CamelModel` 基类。

---

## 1. 实现范围

### 1.1 包含

#### 1.1.1 `backend/app/schemas/cockpit/position.py`（修改，+~25 行）

新增 `PositionSummary` 子模型，并把 `_PositionListData` 改为含 `summary` 字段：

```python
class PositionSummary(_CamelModel):
    open_risk_pct: float | None
    total_exposure_pct: float | None
    pending_risk_pct: float | None
    positions_count: int
    pending_count: int


class _PositionListData(_CamelModel):
    summary: PositionSummary
    items: list[PositionItem]
```

**兼容性影响**：API 字段 *新增* 不破坏既有调用方（前端 F206-c 尚未写）；F206-a/b1 既有 35+41 测试中读 `data.items` 的部分仍然能跑（增字段不删字段）。但读 `_PositionListData(...)` 的测试构造点需要补 `summary=...`，需要扫描调整（预计 2-3 处）。

#### 1.1.2 `backend/app/services/cockpit/position_service.py`（修改，+~70 行）

- 构造函数新增依赖 `PendingOrderRepository`：
  ```python
  from app.repositories.pending_order_repository import PendingOrderRepository
  ...
  self._pending_repo = PendingOrderRepository(db)
  ```
- `list_positions(status)` 签名 **保持不变**，但内部增计算 summary，返回类型改为 `tuple[PositionSummary, list[PositionItem]]`。**Q3（开放）**：返回 tuple 还是新建一个 `PositionListResult` dataclass？默认**返回 tuple**（最少改动，调用方仅 router 一处）。
- 新增 `_compute_summary() -> PositionSummary`：
  - `account_size = self._settings_repo.get_or_default()["account_size"]`
  - 拉 OPEN positions（**复用 status="open" 的 rows 重算，不重新 query**；如果当前 status != open 则单独 query OPEN）
  - 计算 4 个聚合数 + 2 个 count
  - account_size <= 0 → 三个 Pct 字段全 None，counts 仍返回
  - 对 OPEN positions 中 last_close=None 的行，exposure 当 0 处理（不抛错）
  - **last_close 复用计算**：当 `status="open"` 时，`list_positions` 已经 load 过 last_closes，summary 复用同一字典（避免重复 FMP 调用）；当 `status="closed"` 或 `"all"` 时，summary 单独 query OPEN 行 + 单独 load last_closes

#### 1.1.3 `backend/app/routers/cockpit/positions.py`（修改，+~3 行）

`list_positions` endpoint 改为接收 tuple：
```python
summary, items = svc.list_positions(status)
return PositionListResponse(data=_PositionListData(summary=summary, items=items))
```

#### 1.1.4 `backend/app/services/cockpit/pending_order_expirer.py`（新建，~40 行）

```python
"""F206-b2: APScheduler tick — auto-expire ACTIVE pending_orders past expiration_date."""
from __future__ import annotations

import logging
from datetime import date

from sqlalchemy.orm import Session

from app.repositories.pending_order_repository import PendingOrderRepository

logger = logging.getLogger(__name__)


def expire_due_pending_orders(db: Session, today: date | None = None) -> int:
    today = today or date.today()
    repo = PendingOrderRepository(db)
    rows = repo.list_by_status("ACTIVE")
    expired = 0
    for row in rows:
        if row.expiration_date is not None and row.expiration_date < today:
            repo.update(row.id, {"status": "EXPIRED"})
            expired += 1
    if expired > 0:
        logger.info("F206-b2 expirer: marked %d pending_orders as EXPIRED", expired)
    return expired
```

#### 1.1.5 `backend/app/services/refresh_job.py`（修改，+~30 行）

- 顶部增常量：
  ```python
  PENDING_ORDERS_EXPIRER_CRON = "35 22 * * 1-5"
  PENDING_ORDERS_EXPIRER_JOB_ID = "cockpit_pending_orders_expirer"
  ```
- `start_scheduler` 内追加：
  ```python
  sched.add_job(
      _pending_orders_expirer_tick,
      trigger=CronTrigger.from_crontab(PENDING_ORDERS_EXPIRER_CRON, timezone="UTC"),
      id=PENDING_ORDERS_EXPIRER_JOB_ID,
      args=[session_factory],
      replace_existing=True,
  )
  ```
- 新增 tick 函数：
  ```python
  def _pending_orders_expirer_tick(session_factory: SessionFactory) -> None:
      """APScheduler tick for pending_orders auto-EXPIRED (F206-b2): weekdays 22:35 UTC."""
      try:
          with _session_scope(session_factory) as db:
              expire_due_pending_orders(db)
      except Exception:  # noqa: BLE001
          logger.error("pending_orders expirer tick failed\n%s", traceback.format_exc())
  ```

#### 1.1.6 测试（合并 2 个文件，控总数）

**§A `backend/tests/test_position_summary_f206b2.py`**（新建，~14 用例）：

Summary 聚合 + GET 集成（合并到一个文件）：
- account_size=100000，1 OPEN position（NVDA entry=850 stop=820 shares=33）→ openRiskPct ≈ 0.99
- account_size=100000，2 OPEN positions → 求和正确
- 含 1 CLOSED position：summary 不计入 CLOSED
- positionsCount = OPEN 行数（不含 CLOSED）
- 1 ACTIVE pending_order：pendingRiskPct 正确，pendingCount=1
- 1 EXPIRED + 1 CANCELLED + 1 ACTIVE pending_order：pendingCount=1（仅 ACTIVE）
- account_size=0 → 三个 Pct=None，counts 正常
- account_size=None（settings 表无行用默认值）→ 走 default 100000，正常计算
- 某 OPEN position 的 last_close=None → totalExposurePct 不含该行（不抛 500）
- query ?status=closed 时 summary 仍基于 OPEN（**Q1 默认解耦语义**）
- query ?status=all 时 summary 仍基于 OPEN
- 2 位小数四舍五入（边界值如 0.995 → 1.00 / 1.005 → 1.00 或 1.01，按 Python round 半偶数）
- positions 全空 + pending 全空 → summary 全 0 / 0.00
- GET /api/cockpit/positions 集成：响应 JSON 含 `data.summary.openRiskPct` 等 5 字段（camelCase）

**§B `backend/tests/test_pending_order_expirer_f206b2.py`**（新建，~10 用例）：

Expirer 函数 + scheduler 注册：
- expire_due_pending_orders today=2026-04-26，1 ACTIVE 行 expiration_date=2026-04-25 → 该行变 EXPIRED，返回 1
- 同上但 expiration_date=2026-04-26（== today）→ 不过期（严格 <），返回 0
- 同上但 expiration_date=2026-04-27 → 不过期，返回 0
- expiration_date=None → 永不过期
- TRIGGERED / CANCELLED / EXPIRED 已是终态 → 不变
- 多行 ACTIVE 混合过期/未过期 → 仅过期行变 EXPIRED
- 幂等：连续调用两次，第二次返回 0
- updated_at 在过期时刷新（断言新旧时间戳）
- scheduler 注册：调用 `start_scheduler(autostart=False)`，断言 jobs 含 `cockpit_pending_orders_expirer` id 且 trigger 为 CronTrigger("35 22 * * 1-5")
- _pending_orders_expirer_tick 异常被捕获（mock repo 抛错，tick 不抛出）

### 1.2 不包含

- ❌ 前端 widget / form dialog → F206-c
- ❌ summary 字段加入 `GET /api/cockpit/pending-orders`（API-CONTRACT 未要求；前端从 positions 一次取齐）
- ❌ TRIGGERED → 自动创建 Position 联动（v1.9 后续决定）
- ❌ 历史 EXPIRED 自动 purge（保留历史用于回溯）
- ❌ summary 中加入 `closedPositionsCount` 等扩展字段（API-CONTRACT 仅 5 个）
- ❌ 修改 `config.py` 增加 `pending_orders_expirer_cron_*` env（直接常量；Q2 默认）

---

## 2. 验收契约（Evaluator 入口）

### 2.1 测试门禁
- §A 14 + §B 10 = 24 新用例，100% pass
- backend 全量回归（`uv run pytest`）必须 pass：698（F206-b1 末）+ 24 = ≥722
- mypy / ruff 无新增 warning
- F206-a 35 + F206-b1 41 = 76 既有用例必须仍全绿（不允许回归）
  - 重点关注：`_PositionListData` schema 变化是否破坏 b1 的 router 测试（不直接相关，但 F206-a 的 §D 集成测试访问 `data.items` 路径需要确认）

### 2.2 功能验收（F206 整体合并验收，b2 完工后写 acceptance 文档）
- 通过 curl 创建 1 OPEN position + 1 ACTIVE pending_order + 1 EXPIRED 历史 pending_order
- GET /api/cockpit/positions：响应含 `data.summary` 5 字段，数值与手算一致
- GET /api/cockpit/positions?status=all：summary 仍只基于 OPEN（Q1 默认）
- 创建 1 ACTIVE pending_order，expiration_date=昨天 → 手动调用 `expire_due_pending_orders(db)` → 该行 status=EXPIRED
- 启动应用 → APScheduler 列表含 `cockpit_pending_orders_expirer` 任务，next_run_time 为下一个工作日 22:35 UTC

---

## 3. 时间预算
- 估计 0.5-1 session（小切片，无新模型/迁移/外部 IO）
- 风险：summary 计算与 list_positions 的 last_closes 字典复用逻辑略 tricky（status != "open" 时需要单独 query OPEN 行 + load last_closes），写测试覆盖 4 种 status 组合即可

---

## 4. 开放问题（请用户确认契约时一并答复）

| # | 问题 | 默认建议 |
|---|------|---------|
| Q1 | summary 是否随 `?status=` 过滤？（即 status=closed 时 summary 含 CLOSED） | **解耦**（summary 始终基于 OPEN/ACTIVE，是"当前账户风险快照"） |
| Q2 | EXPIRED cron 是否需要 env 覆盖？ | **不需要**（直接常量；与 DAILY_REFRESH_CRON 同风格） |
| Q3 | `list_positions` 返回 `tuple[summary, items]` 还是新建 `PositionListResult` dataclass？ | **tuple**（最少改动；调用方仅 router 一处） |
| Q4 | EXPIRED tick 时间是否 22:35 UTC weekdays？（其他选择：00:05 UTC daily / 与 setup tick 合并） | **22:35 UTC weekdays**（接 setup tick 之后 5 分钟，集中盘后窗口） |
| Q5 | account_size 默认值确认（grep 显示 100000？）— 测试基线 | 实现时 grep 确认；如不同则同步调整测试预期 |

---

## 5. 实施步骤（顺序，不得颠倒）

1. **grep `account_size` 默认值** → 确认 UserSettings 默认行为，记录到 step 6 测试基线
2. **修改 schema**（新增 `PositionSummary` + 改 `_PositionListData`）→ 修复 F206-a/b1 既有测试中显式构造 `_PositionListData(items=...)` 的位置（grep `_PositionListData(`）→ wip commit
3. **新建 `pending_order_expirer.py`** + §B 前 8 用例（纯函数测试）→ wip commit
4. **修改 `refresh_job.py`** 注册 expirer tick + §B 后 2 用例（scheduler 注册 + tick 异常捕获）→ wip commit
5. **修改 `position_service.py`** 增 summary 计算 + 改 `list_positions` 签名 → 跑 F206-a §D 集成测试确保不破 → wip commit
6. **修改 `routers/cockpit/positions.py`** 适配新 tuple 签名 + §A 14 用例 → wip commit
7. **全量回归** `uv run pytest` → 确认 ≥722 pass + F206-a/b1 全绿
8. Evaluator 自检 → 通过即最终 commit `feat(F206-b2): risk summary + pending order expirer`

---

## 6. 文件清单（共 6 个，符合 6 文件原则）

| # | 文件 | 类型 | 估行 |
|---|------|------|------|
| 1 | `backend/app/schemas/cockpit/position.py` | 修改 | +25 |
| 2 | `backend/app/services/cockpit/position_service.py` | 修改 | +70 |
| 3 | `backend/app/routers/cockpit/positions.py` | 修改 | +3 |
| 4 | `backend/app/services/cockpit/pending_order_expirer.py` | 新建 | ~40 |
| 5 | `backend/app/services/refresh_job.py` | 修改 | +30 |
| 6 | `backend/tests/test_position_summary_f206b2.py` | 新建（§A 14 用例） | ~280 |
| 7 | `backend/tests/test_pending_order_expirer_f206b2.py` | 新建（§B 10 用例） | ~180 |

> ⚠️ 实际 7 文件（5 业务 + 2 测试）。**测试文件按惯例不计入 6 文件原则**（与 F206-a 14 文件、F206-b1 14 文件一致：业务文件计 5，符合 6 文件原则；测试是衍生产物）。如严格按 7 计算，仍小于 b1 的 14 一半，单 session 可控。

---

**完成本契约后**：
- features.json 在 F206 `iteration_history` 追加 `F206-b2` 子条目，phase 设为 `contract_agreed`
- F206-a / b1 / b2 三者同步进入合并验收准备（acceptance 文档由 b2 完工后统一起草）
- 进入 in_progress 后走 Generator → Evaluator → needs_review
- F206-b2 完成后下一步是 F206-c 前端 widget（新 sprint，不在本契约范围）
