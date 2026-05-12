# Sprint Contract：F206-a — Position 数据层 + 后端 CRUD

> 状态：草案，待用户确认 | 起草：2026-04-26
> 父 Feature：F206 Position Manager（手动录入持仓，v1.9 Cockpit P1）
> 拆分：**F206-a（本 sprint，Position 后端）** / F206-b（PendingOrder 后端 + Summary 聚合）/ F206-c（前端 Widget）
> 依赖：
>   - F203 ✅（`GET /api/cockpit/decision/{ticker}` deterministic quote + `_compute_hash`）
>   - F203-d / F203-b1 ✅（`user_settings` 表 + repository + position_sizer 公式入口）
>   - F204 ✅（`earnings_events` 表 — `nextAction` 规则引擎需检测 earnings 临近）
>   - 既有：`daily_bars` + `FmpClient.get_daily_bars`（D041 on-demand fallback 模板已在 chart_service 使用）
>
> 引用文档：
>   - DATA-MODEL.md §Position（line 525-558：14 字段权威定义 + 业务规则）
>   - DATA-MODEL.md §UserSettings（line 499-521：account_size / risk_pct）
>   - API-CONTRACT.md §Cockpit Positions（line 1391-1531：4 endpoints 完整 schema）
>   - DECISIONS.md D041（on-demand FMP fallback）/ D066（仓位公式 + position_sizer）/ D067（ticker 不 FK）/ D074（camelCase）
>   - design-spec.md §Widget 7 PositionListWidget（line 1029-1058：UI 字段需求）
>   - data-mapping.md §Cockpit-7（line 681-740：字段映射 + PositionFormDialog 请求体）
>   - features.json#F206（acceptance_criteria 6 条）
>   - 模板参考：
>     - backend/app/services/cockpit/chart_service.py line 178-235（D041 fallback 模板）
>     - backend/app/repositories/user_settings_repository.py（repo 风格）
>     - backend/app/routers/cockpit/setup.py（router 风格 + 错误码）
>     - backend/alembic/versions/011_f203b1_user_settings.py（迁移模板）

---

## 0. 背景与定位

F206 是 v1.9 Cockpit P1 的核心：嘉信无 API → 全手动录入持仓与条件单。本 sprint 落地 **Position 半边**（持仓 CRUD + 服务端实时计算 + last_close 回退），**不做 PendingOrder、不做 summary 聚合、不做前端**。

**为什么先做 Position**：
1. PendingOrder 的字段集是 Position 的子集且共用 last_close 取数逻辑 → Position 先稳定，b 可直接对称复用。
2. Summary 顶条同时依赖 positions 和 pending_orders，必须等两表都有；放 b。
3. 前端两 widget 共享 react-query 模式，等 a + b 后端契约稳定再起前端，避免改 schema 时连环改。

**关键约束**：

1. **last_close 取数走 D041 fallback**：
   - 优先 `daily_bars` 最新一行（仅 watchlist ticker，即 `stocks` 表内）
   - 否则 on-demand 调 `FmpClient.get_daily_bars(ticker, from=today-30d, to=today)` 取最后一根 close（**不**写回 daily_bars，与 chart_service line 187-235 一致）
   - **批量优化**：GET 列表时收集所有 ticker，watchlist 内一次 SQL，watchlist 外**串行**调 FMP（与 chart 一致；FMP `/quote/{multi}` 暂不引入，避免本 sprint 扩展 FmpClient）。N 个非 watchlist position 触发 N 次 FMP 调用，由 default_rate_limiter 节流。
   - FMP 失败：单个 ticker 的 `lastClose` 字段返回 `null`，**不阻断整行**，不抛 502；前端见 null 时降级显示 entry。**Q1（开放）**：是否要在 response.meta 增 `fmpErrors: [ticker, ...]` 让前端显示警告？默认**不加**（个别失败容错；如需，b 阶段加到 summary）。

2. **`nextAction` 规则引擎（deterministic，本 sprint 一次落地完整版）**：
   - 4 值 `hold` / `raise_stop` / `reduce` / `exit`，由 `position_action_rules.py` 纯函数计算，输入 `(position_row, last_close, earnings_event)`，输出 `nextAction: str`。
   - 规则优先级（自上向下，命中即返回）：
     1. `last_close <= stop_price` → `exit`（止损位已破）
     2. earnings_event 存在且 `days_until_earnings <= 2` → `reduce`（earnings 临近 2 天）
     3. `r_multiple >= 2.0` 且 `stop_price < entry_price` → `raise_stop`（已达 2R 但 stop 还在初始位下方）
     4. 其余 → `hold`
   - F207 复用：本规则引擎放 `backend/app/services/cockpit/position_action_rules.py`，F207 `action_service` import 同一函数（避免双实现）。

3. **POST 不强制 shares = sizer 输出，但响应附 `recommendedShares` 字段**：
   - 用户确认（前面对话）。
   - `recommendedShares` 由 `position_sizer.compute_shares(account_size, risk_pct, entry, stop)` 计算（D066 公式）。
   - 若 `entry_price <= stop_price` → 422 VALIDATION_ERROR（API-CONTRACT line 1480 约束）；recommendedShares 仅在 valid 输入下计算。
   - **复用 / 新建**：检查 `backend/app/services/cockpit/` 是否已有 `position_sizer.py`（D066 描述但未确认实现）。**Q2（开放）**：若不存在，本 sprint 新建（~30 行纯函数 + unit test）；若已存在，仅 import。先在实现阶段读源码确认。

4. **status 字段的状态机**：
   - 默认 `OPEN`；PATCH status=CLOSED 必须同时提供 `closedAt + closePrice`，否则 422（API-CONTRACT line 1508）。
   - CLOSED → OPEN 不允许（422）。CLOSED → CLOSED 仍允许（修订 closedAt / closePrice / notes）。
   - **F211 副作用 (`journal_assistant` 异步触发)** 不在本 sprint 范围（DATA-MODEL line 553 注释 "v2.0 新字段，非本 Epic 加"）。

5. **字段命名 D074 camelCase**：API 层 Pydantic schema 使用 `entryPrice`/`stopPrice`/`closePrice`/`closedAt` 等 camelCase；DB 层 SQLAlchemy 模型保持 snake_case。映射通过 Pydantic `Field(alias=...)` + `model_config = {"populate_by_name": True}` 或 service 层显式转换（与 `user_settings` schema 风格保持一致）。

---

## 1. 实现范围

### 1.1 包含

#### 1.1.1 `backend/alembic/versions/013_f206a_positions.py`（新建，~70 行）

新表 `positions`，字段对照 DATA-MODEL.md line 533-549。

```python
op.create_table(
    "positions",
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("ticker", sa.String(10), nullable=False),
    sa.Column("entry_price", sa.Float, nullable=False),
    sa.Column("entry_date", sa.Date, nullable=False),
    sa.Column("shares", sa.Integer, nullable=False),
    sa.Column("stop_price", sa.Float, nullable=False),
    sa.Column("target_2r", sa.Float, nullable=True),
    sa.Column("target_3r", sa.Float, nullable=True),
    sa.Column("setup_type", sa.String(24), nullable=True),
    sa.Column("notes", sa.Text, nullable=True),
    sa.Column("status", sa.String(8), nullable=False, server_default="OPEN"),
    sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("close_price", sa.Float, nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    sa.CheckConstraint("status IN ('OPEN', 'CLOSED')", name="ck_positions_status"),
    sa.CheckConstraint("shares > 0", name="ck_positions_shares_positive"),
    sa.Index("ix_positions_ticker", "ticker"),
    sa.Index("ix_positions_status", "status"),
)
```

`down_revision = "012_f208a_ai_memos"`，`revision = "013_f206a_positions"`。

#### 1.1.2 `backend/app/models/position.py`（新建，~40 行）

SQLAlchemy 2.0 ORM model，字段同迁移；`status` 用 `Mapped[str]`（不引入 Enum，schema 层校验枚举）。注册到 `app/models/__init__.py`。

#### 1.1.3 `backend/app/repositories/position_repository.py`（新建，~120 行）

CRUD 方法：
- `list_by_status(status: Literal["open", "closed", "all"]) -> list[Position]`
- `get_by_id(position_id: int) -> Position | None`
- `create(payload: dict) -> Position`（payload 已为 snake_case）
- `update(position_id: int, patch: dict) -> Position | None`（自动更新 `updated_at`）
- `delete(position_id: int) -> bool`

#### 1.1.4 `backend/app/schemas/cockpit/position.py`（新建，~120 行）

Pydantic schemas（D074 camelCase）：
- `PositionCreate`：POST body — `ticker / entryPrice / entryDate / shares / stopPrice / target2r? / target3r? / setupType? / notes?`，含 `entry_price > stop_price`、`shares > 0` validator。
- `PositionUpdate`：PATCH body — 全 optional，含 `status=CLOSED ↔ closedAt+closePrice` 联合 validator。
- `PositionItem`：GET 列表 / 创建 / 更新响应单项 — 含计算字段 `lastClose`/`rMultiple`/`unrealizedPl`/`positionValue`/`earningsDate`/`daysUntilEarnings`/`nextAction`/`recommendedShares`（POST 才填，GET 列表 null）。
- `PositionListResponse`：`{ data: { items: [PositionItem, ...] }, message }`（**不含 summary**，summary 留 b）。
- `PositionDeleteResponse`：`{ data: { id, deleted: true }, message }`。

#### 1.1.5 `backend/app/services/cockpit/position_service.py`（新建，~180 行）

核心业务：
- `list_positions(status: str) -> list[PositionItem]` — 拉 ORM 行 + 批量 last_close + 逐行 enrich。
- `get_position(id) -> PositionItem | None` — enrich 单行。
- `create_position(payload: PositionCreate) -> PositionItem` — 入库 + enrich + 附 `recommendedShares`。
- `update_position(id, patch: PositionUpdate) -> PositionItem | None` — 业务规则校验 + enrich。
- `delete_position(id) -> bool`。
- `_enrich(row: Position, last_close: float | None, earnings_event: EarningsEvent | None) -> PositionItem` — 实时计算字段汇总点。
- `_load_last_closes(tickers: list[str]) -> dict[str, float | None]` — D041 批量 fallback。

依赖注入（构造函数）：`PositionRepository`, `StockRepository`, `EarningsEventRepository`, `FmpClient`, `UserSettingsRepository`。

#### 1.1.6 `backend/app/services/cockpit/position_action_rules.py`（新建，~40 行）

```python
def compute_next_action(
    *, last_close: float | None, entry_price: float, stop_price: float,
    days_until_earnings: int | None,
) -> Literal["hold", "raise_stop", "reduce", "exit"]:
    if last_close is None:
        return "hold"
    if last_close <= stop_price:
        return "exit"
    if days_until_earnings is not None and days_until_earnings <= 2:
        return "reduce"
    r = (last_close - entry_price) / (entry_price - stop_price)
    if r >= 2.0 and stop_price < entry_price:
        return "raise_stop"
    return "hold"
```

#### 1.1.7 `backend/app/services/cockpit/position_sizer.py`（新建或复用，~30 行）

D066 公式：
```python
def compute_shares(*, account_size: float, risk_pct: float, entry: float, stop: float) -> int:
    if entry <= stop or risk_pct <= 0:
        return 0
    return floor(account_size * risk_pct / 100 / (entry - stop))
```

实现时先 `grep -r position_sizer backend/app/` 确认是否已存在，存在则复用，不存在则新建。

#### 1.1.8 `backend/app/routers/cockpit/positions.py`（新建，~140 行）

4 endpoint，依赖注入 + `PositionService`：
- `GET /api/cockpit/positions?status=open|closed|all` → `PositionListResponse`
- `POST /api/cockpit/positions` → `201 + PositionItem`
- `PATCH /api/cockpit/positions/{id}` → `PositionItem`
- `DELETE /api/cockpit/positions/{id}` → `PositionDeleteResponse`

错误码：
- 422 VALIDATION_ERROR（Pydantic 自动 + 业务校验）
- 404 NOT_FOUND（PATCH/DELETE id 不存在）

注册到 `backend/app/routers/cockpit/__init__.py`。

#### 1.1.9 测试

`backend/tests/`：
- `§A schema_test.py`（~6 用例）：`PositionCreate` 必填 / entry≤stop / shares≤0 / `PositionUpdate` CLOSED 缺 closedAt/closePrice / D074 camelCase 序列化
- `§B repo_test.py`（~5 用例）：CRUD 闭环 + status 过滤 + ticker index 命中
- `§C service_test.py`（~10 用例）：`compute_next_action` 4 分支 / `compute_shares` 边界（entry=stop / risk=0 / 正常）/ enrich last_close=None 时 rMultiple/unrealizedPl 为 null / FMP 失败容错
- `§D integration_test.py`（~8 用例）：4 endpoint 200/201/404/422 + GET 含 mixed watchlist 与非 watchlist + recommendedShares 出现在 POST 响应

### 1.2 不包含

- ❌ PendingOrder 表 / endpoints / 计算（→ F206-b）
- ❌ Summary 顶条（openRiskPct / totalExposurePct / pendingRiskPct / counts）→ F206-b
- ❌ APScheduler EXPIRED 转换（→ F206-b）
- ❌ 前端 widget / form dialog → F206-c
- ❌ F211 `journal_assistant` 副作用（CLOSED → AI 复盘）
- ❌ 自动从 PendingOrder 创建 Position（v1.9 后续决定）
- ❌ FMP `/quote/{multi}` 多 ticker 接口扩展

---

## 2. 验收契约（Evaluator 入口）

### 2.1 测试门禁
- 所有 §A/§B/§C/§D 测试必须 100% pass
- backend 全量回归（`uv run pytest`）必须 pass，含已有 587 用例
- 新增不少于 29 用例（A6 + B5 + C10 + D8）
- mypy / ruff 无新增 warning

### 2.2 功能验收（用户验收阶段）
- 验收脚本 `docs/验收/v1.9-F206-a-acceptance.md`，含：
  - 通过 curl/httpie 创建 1 watchlist position（如 NVDA）+ 1 非 watchlist position（如 OTC ticker）
  - GET 列表：watchlist 行 lastClose 来自 daily_bars，非 watchlist 行 lastClose 来自 FMP（或 null 容错）
  - POST 响应含 `recommendedShares`，且与手输 shares 可不同
  - PATCH 移动 stop_price → 重新 GET，rMultiple 随之变化
  - PATCH status=CLOSED 缺 closedAt → 422
  - DELETE → 再 GET 该 id → 404

---

## 3. 时间预算
- 估计 1.5 sessions
- 风险：D041 fallback 串行 FMP 在多个非 watchlist ticker 下的延迟（~ N × 200ms）。MVP 接受；如 latency > 3s 触发用户感知，b/c 阶段加 background prefetch 或 `/quote` 多 ticker 接口

---

## 4. 开放问题（请用户在确认契约时一并答复）

| # | 问题 | 默认建议 |
|---|------|---------|
| Q1 | response.meta 是否暴露 `fmpErrors: [ticker]` 数组？ | **不加**（容错降级；b 阶段如需再加） |
| Q2 | `position_sizer.py` 已存在 → 复用，不存在 → 新建 | **新建并附 unit test**（实现时先 grep 确认） |
| Q3 | `setupType` 是否限定 SetupSnapshot 7 枚举？ | **限定**（与 setup.py 同 Literal 枚举；POST 校验严格） |
| Q4 | `entry_date` 是否允许未来日期？ | **不允许**（≤ today；防误录入） |

---

## 5. 实施步骤（顺序）

1. Migration 013 + ORM model + 注册 `models/__init__.py`
2. `position_sizer.py`（grep 确认 → 复用 / 新建）+ unit test §C 部分
3. `position_action_rules.py` + unit test §C 部分
4. Repository + §B test
5. Schema (Pydantic) + §A test
6. Service（含 _load_last_closes / _enrich）+ §C 余下 test
7. Router + §D integration test
8. 全量回归（`uv run pytest`）
9. 手动 curl 验证 + 起草验收文档（验收交用户）

---

**完成本契约后**：
- features.json `F206-a` phase → `contract_agreed`
- 进入 in_progress（`feature-dev` skill）
- 完成后走标准 needs_review → 用户验收 → done 流程
