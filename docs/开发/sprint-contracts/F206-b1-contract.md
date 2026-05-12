# Sprint Contract：F206-b1 — PendingOrder 数据层 + 后端 CRUD

> 状态：草案，待用户确认 | 起草：2026-04-26
> 父 Feature：F206 Position Manager（v1.9 Cockpit P1）
> 拆分：F206-a ✅（Position 后端）/ **F206-b1（本 sprint，PendingOrder 后端）** / F206-b2（Risk Summary 聚合 + APScheduler EXPIRED）/ F206-c（前端 Widget）
> 依赖：
>   - F206-a ✅（已落地：`PositionService` 模式 / `position_sizer` / `position_action_rules` / D041 last_close fallback 模板可直接复用）
>   - F203-d / F203-b1 ✅（`user_settings.account_size` — riskPct 分母）
>   - 既有：`daily_bars` + `FmpClient.get_daily_bars`
>
> 引用文档：
>   - DATA-MODEL.md §PendingOrder（line 560-589：13 字段权威定义 + 状态机 + 索引）
>   - API-CONTRACT.md §Cockpit Pending Orders（line 1533-1581：4 endpoints schema）
>   - DECISIONS.md D041（on-demand FMP fallback）/ D066（仓位公式 — riskPct 分母 = account_size）/ D067（ticker 不 FK）/ D074（camelCase）
>   - features.json#F206（acceptance_criteria 第 4 条 Pending Orders 表）
>   - 模板参考（强复用 F206-a）：
>     - `backend/app/services/cockpit/position_service.py`（D041 _load_last_closes 直接复制结构）
>     - `backend/app/repositories/position_repository.py`（CRUD 风格）
>     - `backend/app/schemas/cockpit/position.py`（D074 camelCase + alias_generator）
>     - `backend/app/routers/cockpit/positions.py`（router + APIError 风格）
>     - `backend/alembic/versions/013_f206a_positions.py`（迁移模板）

---

## 0. 背景与定位

F206-b1 落地 **PendingOrder 半边**，对称 F206-a 的 Position 半边。本 sprint **不做 summary 聚合、不做 scheduler EXPIRED、不做前端**（→ F206-b2 / F206-c）。

**为什么先做纯 CRUD**：
1. PendingOrder 字段集是 Position 的子集 + 几个独有字段（`expirationDate` / `distanceToTriggerPct`）。F206-a 的 D041 fallback / camelCase / 错误处理模式已稳定，本 sprint 直接镜像即可，风险低。
2. Summary 顶条同时依赖 positions 和 pending_orders 的运行时数据，必须等 b1 落地后再聚合（→ b2）。
3. APScheduler EXPIRED tick 需要 PendingOrderRepository 已就位（→ b2）。

**关键约束（继承 F206-a，不重新发明）**：

1. **last_close 取数完全复用 F206-a 模式**：
   - 优先 `daily_bars` 最新一行（仅 watchlist ticker，即 `stocks` 表内）
   - 否则 on-demand 调 `FmpClient.get_daily_bars(ticker, today-30d, today)`，**不**回写 daily_bars
   - 批量优化：GET 列表时收集所有 ticker，watchlist 内一次 SQL，watchlist 外串行 FMP；FMP 失败 → 单行 `lastClose=null`，相关计算字段（`distanceToTriggerPct`）一并 null，不抛 502
   - **实现选择**：将 `_load_last_closes` 抽到独立模块 `backend/app/services/cockpit/last_close_loader.py`（新建，~50 行），让 `PositionService` 和 `PendingOrderService` 共享，避免双实现。**Q1（开放）**：是否允许在本 sprint 重构 `position_service.py` 把 `_load_last_closes` 迁出？默认**允许**（影响 1 个文件 + 1 个新建，已计入 12 文件清单）；如果用户希望保持 F206-a 不动，则 PendingOrderService 内复制实现一份（违反 DRY，但隔离更彻底）。

2. **服务端实时计算字段（PendingOrder 独有，3 个）**：
   - `lastClose: float | None` — 同上
   - `distanceToTriggerPct: float | None` = `(entry_price - last_close) / last_close × 100`，保留 2 位小数。`last_close` 为 None 时为 None。负值表示已穿越 entry（需要前端注意，但本 sprint 不做颜色规则）。**对照 DATA-MODEL.md line 439（distance_to_entry_pct 同公式）和 API-CONTRACT line 1560 示例（180/176.5 → 1.98）**。
   - `riskPct: float | None` = `(entry_price - stop_price) × shares / account_size × 100`，保留 2 位小数。`account_size` 取自 `UserSettingsRepository.get_or_default()`。即使 `last_close=None` 也能算出 riskPct（不依赖市价），所以 riskPct 始终有值。

3. **status 字段的状态机**：
   - 默认 `ACTIVE`；4 终态：`ACTIVE` / `TRIGGERED` / `CANCELLED` / `EXPIRED`
   - 流转：`ACTIVE → {TRIGGERED, CANCELLED, EXPIRED}`；`TRIGGERED` 后不允许改回 ACTIVE（422，API-CONTRACT line 1580）
   - **本 sprint 决定**：`CANCELLED` / `EXPIRED` → ACTIVE 也禁止（422，对称防止"复活"）；`ACTIVE → ACTIVE` 允许（修订字段不变状态）；终态之间互转禁止（如 `CANCELLED → EXPIRED`，422）。
   - **EXPIRED 由 scheduler 写入**（→ F206-b2）；本 sprint 允许用户 PATCH 手动写入 EXPIRED（一致性：4 状态都对用户开放，scheduler 仅作为兜底）。

4. **status 查询参数大小写不敏感**：
   - `?status=active|all|ACTIVE|TRIGGERED|CANCELLED|EXPIRED`（API-CONTRACT line 1542）
   - 实现：router 接收 raw string → service 内 `.upper()` 标准化；非合法值 → 422
   - **默认 `active`**（不是 ALL，与 GET /positions 默认 `open` 对称）

5. **响应结构差异（与 Position 不一致，必须遵守 API-CONTRACT）**：
   - GET /positions：`{ data: { items: [...] }, message }`（嵌一层 `items`，为后续 summary 留位）
   - GET /pending-orders：`{ data: [...], message }`（**直接数组，无 items 包裹**，对照 API-CONTRACT line 1547）
   - **Q2（开放）**：是否要把 GET /pending-orders 也改成 `{ data: { items: [...] } }` 与 positions 对齐？默认**遵守 API-CONTRACT 现状**（`data: [...]`），如果用户希望对齐则同步更新 API-CONTRACT.md（增量 1 行修改 + 1 个新决策）。

6. **字段命名 D074 camelCase**：复用 F206-a 的 `_CamelModel` 基类（`alias_generator=to_camel + populate_by_name=True + from_attributes=True`）。schema 文件结构对称 `position.py`。

7. **setupType 是必填**（DATA-MODEL line 572）：
   - F206-a 的 Position.setup_type 是可选；PendingOrder.setup_type 必填。
   - 枚举沿用 F206-a 的 `_VALID_SETUP_TYPES`（`BREAKOUT/PULLBACK/RECLAIM/EARNINGS_DRIFT/EXTENDED/BROKEN/NONE`）；考虑把 Literal 提到 `app/schemas/cockpit/_setup_types.py` 共享，**Q3（开放）**：默认**就地复制 Literal**（避免新建第 13 个文件破坏 12 文件清单）；如果用户接受 +1 文件可以共享。

8. **expirationDate 校验**：
   - 可选字段。**Q4（开放）**：POST 时是否禁止过去日期（`expiration_date < today` → 422）？默认**禁止**（业务上"已过期的计划"无意义；scheduler 也会立即将其转 EXPIRED，倒不如前端阻止）。

---

## 1. 实现范围

### 1.1 包含

#### 1.1.1 `backend/alembic/versions/014_f206b1_pending_orders.py`（新建，~70 行）

新表 `pending_orders`，字段对照 DATA-MODEL.md line 568-582。

```python
op.create_table(
    "pending_orders",
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("ticker", sa.String(10), nullable=False),
    sa.Column("setup_type", sa.String(24), nullable=False),
    sa.Column("entry_price", sa.Float, nullable=False),
    sa.Column("stop_price", sa.Float, nullable=False),
    sa.Column("shares", sa.Integer, nullable=False),
    sa.Column("target_2r", sa.Float, nullable=True),
    sa.Column("target_3r", sa.Float, nullable=True),
    sa.Column("expiration_date", sa.Date, nullable=True),
    sa.Column("status", sa.String(16), nullable=False, server_default="ACTIVE"),
    sa.Column("notes", sa.Text, nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    sa.CheckConstraint(
        "status IN ('ACTIVE', 'TRIGGERED', 'CANCELLED', 'EXPIRED')",
        name="ck_pending_orders_status",
    ),
    sa.CheckConstraint("shares > 0", name="ck_pending_orders_shares_positive"),
)
op.create_index("ix_pending_orders_ticker", "pending_orders", ["ticker"])
op.create_index("ix_pending_orders_status", "pending_orders", ["status"])
```

`down_revision = "013_f206a_positions"`，`revision = "014_f206b1_pending_orders"`。

#### 1.1.2 `backend/app/models/pending_order.py`（新建，~40 行）

SQLAlchemy 2.0 ORM model，结构对称 `position.py`：String(16) status，无 close_price/closed_at，新增 expiration_date。

#### 1.1.3 `backend/app/models/__init__.py`（修改 +1 行）

追加 `from app.models.pending_order import PendingOrder` 注册。

#### 1.1.4 `backend/app/repositories/pending_order_repository.py`（新建，~70 行）

CRUD 方法，对称 `position_repository.py`：
- `list_by_status(status: str) -> list[PendingOrder]`（接收已大写或 `"active"`/`"all"` 的标准化值；`active` → `status == "ACTIVE"`，`all` → 不过滤）
- `get_by_id(id: int) -> PendingOrder | None`
- `create(payload: dict) -> PendingOrder`（`status="ACTIVE"` 默认；时间戳由 repo 写入）
- `update(id: int, patch: dict) -> PendingOrder | None`（自动更新 `updated_at`）
- `delete(id: int) -> bool`

#### 1.1.5 `backend/app/schemas/cockpit/pending_order.py`（新建，~140 行）

Pydantic schemas（D074 camelCase）：
- `PendingOrderCreate`：POST body — `ticker / setupType / entryPrice / stopPrice / shares / target2r? / target3r? / expirationDate? / notes?`，含：
  - `entry_price > stop_price` validator（VALIDATION_ERROR 422）
  - `shares > 0`（Field(gt=0)）
  - `expiration_date >= today` validator（Q4 默认禁止过去）
  - `setupType` 必填，枚举沿用
- `PendingOrderUpdate`：PATCH body — 全 optional，含：
  - 终态防复活 validator：当 `status` 字段出现且值为 `ACTIVE` 时，service 层根据当前 row.status 决定是否 422（schema 层不知道当前状态，只校验枚举合法）
  - `entryPrice/stopPrice` 配对校验：若两者**同时**出现且 `entryPrice <= stopPrice` → 422；若仅一个出现，service 层与 DB 现值合并后再校验
- `PendingOrderItem`：GET 列表 / 创建 / 更新响应单项 — 含计算字段 `lastClose`/`distanceToTriggerPct`/`riskPct`
- **响应包装**（区别于 positions）：
  - `PendingOrderListResponse`：`{ data: [PendingOrderItem, ...], message }`（**`data` 直接是数组，不嵌 items**）
  - `PendingOrderSingleResponse`：`{ data: PendingOrderItem, message }`（POST/PATCH）
  - `PendingOrderDeleteResponse`：`{ data: { id, deleted: true }, message }`

#### 1.1.6 `backend/app/services/cockpit/last_close_loader.py`（新建，~60 行；Q1 默认方案）

把 F206-a `position_service._load_last_closes` + `_fmp_latest_close` 提取为共享纯模块：

```python
class LastCloseLoader:
    def __init__(self, db: Session, fmp: FmpClient) -> None: ...
    def load(self, tickers: list[str]) -> dict[str, float | None]: ...
```

`position_service.py` 同步改为调用 `LastCloseLoader`（删除内部两个私有方法）；`pending_order_service.py` 同样调用。

**回归保险**：F206-a 的 35 测试用例 + 全量回归 657 必须仍全绿。重构步骤独立 commit（`refactor(F206-b1): extract last_close_loader`），便于回滚。

#### 1.1.7 `backend/app/services/cockpit/pending_order_service.py`（新建，~140 行）

核心业务（对称 `position_service.py`，但更轻量，因为没有 sizer/action_rules）：
- `list_pending_orders(status: str) -> list[PendingOrderItem]` — 标准化 status → repo → 批量 last_close → 逐行 enrich
- `get_pending_order(id) -> PendingOrderItem | None`
- `create_pending_order(payload: PendingOrderCreate) -> PendingOrderItem`
- `update_pending_order(id, patch: PendingOrderUpdate) -> PendingOrderItem | None`
  - 状态机校验（终态不可改回 ACTIVE / 终态之间互转禁止）→ 422 `APIError`
  - `entry_price/stop_price` 合并后校验（如果 patch 只改 entry，需要与 DB 中 stop 比较）
- `delete_pending_order(id) -> bool`
- `_enrich(row, last_close, account_size) -> PendingOrderItem` — 实时计算 distanceToTriggerPct + riskPct

依赖注入：`db: Session, fmp: FmpClient`（构造内部 `PendingOrderRepository / UserSettingsRepository / LastCloseLoader`，对称 PositionService）。

#### 1.1.8 `backend/app/routers/cockpit/pending_orders.py`（新建，~100 行）

4 endpoint：
- `GET /api/cockpit/pending-orders?status=active` → `PendingOrderListResponse`
- `POST /api/cockpit/pending-orders` → `201 + PendingOrderSingleResponse`
- `PATCH /api/cockpit/pending-orders/{id}` → `PendingOrderSingleResponse`
- `DELETE /api/cockpit/pending-orders/{id}` → `PendingOrderDeleteResponse`

错误码：
- 422 VALIDATION_ERROR（Pydantic 自动 + status 非法 + entry≤stop + 状态机违规）
- 404 NOT_FOUND（PATCH/DELETE id 不存在）

`status` query 参数**不**用 `pattern=` 严格限制（因为大小写不敏感），改为接收任意 string，service 层 `.upper()` 标准化后校验合法性。

注册到 `backend/app/routers/cockpit/__init__.py`。

#### 1.1.9 `backend/app/routers/cockpit/__init__.py`（修改 +2 行）

追加 import + `include_router`。

#### 1.1.10–1.1.12 测试（4 文件）

`backend/tests/`（命名沿用 `f206b1_` 前缀避免冲突）：

- **§A `test_pending_order_f206b1_schema.py`**（~8 用例）：
  - PendingOrderCreate 必填字段（缺 ticker/setupType/entryPrice/stopPrice/shares 各 1 例）
  - entry≤stop → 422
  - shares≤0 → 422
  - expirationDate < today → 422
  - setupType 非枚举 → 422
  - PendingOrderUpdate status=ACTIVE 仅枚举校验通过（service 层另测）
  - D074 camelCase 序列化（dump alias）

- **§B `test_pending_order_f206b1_repo.py`**（~5 用例）：
  - CRUD 闭环
  - list_by_status("active") 仅返 ACTIVE
  - list_by_status("all") 返全部
  - 按 status 过滤（TRIGGERED / EXPIRED）
  - update 自动更新 updated_at（纳秒级断言：旧 vs 新）

- **§C `test_pending_order_f206b1_service.py`**（~12 用例）：
  - status 大小写不敏感（`"active"` / `"ACTIVE"` / `"All"` 等价）
  - 非法 status → 422
  - 状态机：ACTIVE → TRIGGERED ✅
  - 状态机：TRIGGERED → ACTIVE → 422
  - 状态机：CANCELLED → ACTIVE → 422
  - 状态机：CANCELLED → EXPIRED → 422（终态互转）
  - distanceToTriggerPct 计算（180/176.5 → 1.98）
  - distanceToTriggerPct last_close=None → null
  - riskPct 计算（180-173 × 40 / 100000 × 100 → 0.28，对照 API-CONTRACT 示例 0.70 用 50 share 是用户设定的 share）
  - riskPct last_close=None 仍计算（不依赖市价）
  - patch 只改 entry，与 DB stop 合并校验 entry≤stop → 422
  - last_close_loader 重构后 Position 路径回归（运行 1 个 PositionService 用例确保不破坏）

- **§D `test_pending_order_f206b1_integration.py`**（~10 用例）：
  - GET 默认 active
  - GET ?status=all 含 TRIGGERED 行
  - GET ?status=EXPIRED 大写
  - POST 201 含 lastClose/distanceToTriggerPct/riskPct
  - POST 422 entry≤stop
  - POST 422 expirationDate < today
  - POST 422 setupType 非法
  - PATCH 200 移动 stop
  - PATCH 422 状态机违规（TRIGGERED→ACTIVE）
  - PATCH 404 id 不存在
  - DELETE 200
  - DELETE 404

### 1.2 不包含

- ❌ Risk Summary 顶条聚合 → F206-b2
- ❌ APScheduler EXPIRED 自动转换 → F206-b2
- ❌ `GET /api/cockpit/positions` 响应内 `summary` 字段 → F206-b2
- ❌ 前端 widget / form dialog → F206-c
- ❌ `TRIGGERED → 自动创建 Position`（v1.9 后续决定，非本 sprint）
- ❌ FMP `/quote/{multi}` 多 ticker 接口扩展（沿用 F206-a 串行模式）
- ❌ 与 `setup_snapshots` 联动（"setup 已 BROKEN → cancel_order 提示"在 F207 action_service）

---

## 2. 验收契约（Evaluator 入口）

### 2.1 测试门禁
- 所有 §A/§B/§C/§D 测试必须 100% pass
- backend 全量回归（`uv run pytest`）必须 pass：657（F206-a 末）+ 新增 ≥35 = ≥692
- mypy / ruff 无新增 warning
- last_close_loader 重构必须不破坏 F206-a 的 35 测试用例（独立 wip commit）

### 2.2 功能验收（用户验收阶段，b2 完工后合并验收脚本）
- 通过 curl 创建 1 watchlist pending_order（如 NVDA）+ 1 非 watchlist
- GET 列表：watchlist 行 lastClose 来自 daily_bars，非 watchlist 来自 FMP（或 null 容错）
- POST 响应含 distanceToTriggerPct + riskPct
- PATCH 移动 stopPrice → riskPct 随之变化
- PATCH status=TRIGGERED → 再 PATCH status=ACTIVE → 422
- PATCH status=ACTIVE → ACTIVE → 200（同状态修订不阻断）
- DELETE → 再 GET 该 id → 404
- POST expirationDate=过去日期 → 422

---

## 3. 时间预算
- 估计 1 session（~F206-a 的 70%，因 sizer/action_rules 不需要、enrich 字段更少）
- 风险：last_close_loader 重构可能涉及现有 PositionService 测试调整（已纳入 §C 末例兜底）

---

## 4. 开放问题（请用户确认契约时一并答复）

| # | 问题 | 默认建议 |
|---|------|---------|
| Q1 | 是否抽 `last_close_loader.py` 共享模块（影响 1 改 + 1 新建文件） | **抽**（DRY；F206-a 35 用例兜底回归） |
| Q2 | GET /pending-orders 响应是否对齐 positions 的 `data: { items: [...] }` 结构（需要同步改 API-CONTRACT.md） | **不对齐**（遵守现行 API-CONTRACT；保持响应不变 = 不增加文件改动） |
| Q3 | `_VALID_SETUP_TYPES` Literal 是否抽到 `_setup_types.py` 共享模块（+1 文件） | **就地复制**（守 12 文件清单；下次有第三处用到再抽） |
| Q4 | POST `expirationDate < today` 是否拒绝（422） | **拒绝**（业务上无意义；scheduler 也会立即转 EXPIRED） |

---

## 5. 实施步骤（顺序，不得颠倒）

1. **Migration 014** + ORM model + 注册 `models/__init__.py` → wip commit
2. **last_close_loader 重构**（如 Q1=抽）：
   - 新建 `last_close_loader.py`
   - 改 `position_service.py` 用 loader
   - 跑 F206-a 全部测试确保不破 → wip commit `refactor(F206-b1): extract last_close_loader`
3. **PendingOrderRepository** + §B test → wip commit
4. **PendingOrder Schemas** + §A test → wip commit
5. **PendingOrderService**（含状态机 + enrich）+ §C test → wip commit
6. **Router** + §D integration test → wip commit
7. 全量回归（`uv run pytest`）
8. Evaluator 自检 → 一通过即最终 commit `feat(F206-b1): PendingOrder 数据层 + CRUD`

---

## 6. 文件清单（共 12 个，对照 6 文件原则已在 plan 阶段拆分）

| # | 文件 | 类型 |
|---|------|------|
| 1 | `backend/alembic/versions/014_f206b1_pending_orders.py` | 新建 |
| 2 | `backend/app/models/pending_order.py` | 新建 |
| 3 | `backend/app/models/__init__.py` | 修改 |
| 4 | `backend/app/repositories/pending_order_repository.py` | 新建 |
| 5 | `backend/app/schemas/cockpit/pending_order.py` | 新建 |
| 6 | `backend/app/services/cockpit/last_close_loader.py` | 新建（Q1 默认方案） |
| 7 | `backend/app/services/cockpit/pending_order_service.py` | 新建 |
| 8 | `backend/app/services/cockpit/position_service.py` | 修改（改用 last_close_loader） |
| 9 | `backend/app/routers/cockpit/pending_orders.py` | 新建 |
| 10 | `backend/app/routers/cockpit/__init__.py` | 修改 |
| 11 | `backend/tests/test_pending_order_f206b1_schema.py` | 新建（§A 8 用例） |
| 12 | `backend/tests/test_pending_order_f206b1_repo.py` | 新建（§B 5 用例） |
| 13 | `backend/tests/test_pending_order_f206b1_service.py` | 新建（§C 12 用例） |
| 14 | `backend/tests/test_pending_order_f206b1_integration.py` | 新建（§D 10 用例） |

> ⚠️ 实际 14 文件（含 4 个测试 + 1 个重构 + 1 个共享 loader）。与 F206-a（14 文件）等量级。如 Q1 选"不抽"则降到 12 文件。**仍超 6 文件原则**，但 sprint 内是逻辑紧密的"CRUD 平行切片"（与 F206-a 同形态），单 session 可控。

---

**完成本契约后**：
- features.json 新增 `F206-b1` 子条目，phase 设为 `contract_agreed`（或在 F206 父条目下追加 `_subtasks`）
- 新 session 进入 Generator 模式，从步骤 1 开始
- 完成后走标准 needs_review，**等 F206-b2 完工后合并验收**（用户验收 PendingOrder 完整能力需要 b2 的 summary 才直观）
