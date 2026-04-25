# Sprint Contract：F204-a — Earnings Calendar 数据层

> 状态：草案 | 起草：2026-04-24
> 父 Feature：F204 Earnings Calendar 接入（仅 Cockpit 消费）
> 兄弟：F204-b（Config cron + APScheduler job + Schema + Router，独立 Sprint）
> 引用文档：
>   - DATA-MODEL.md §Entity: EarningsEvent（字段权威）
>   - API-CONTRACT.md §Cockpit Earnings（接口权威，F204-b 实现）
>   - DECISIONS.md D065（Earnings 仅 cockpit 消费 + 每日增量 upsert）
>   - DECISIONS.md D070（cockpit_params.py 约定；F204 本身不建该文件，§4 EARNINGS 由 F202 落地）

---

## 0. 背景与定位

F204 Earnings Calendar 接入预计总文件数 12（超 6 文件上限），拆分为：

- **F204-a（本 Sprint，6 文件）**：数据层 — Alembic 建表 + SQLAlchemy Model + Repository + FMP client 方法 + EarningsService（fetch/store/query）
- **F204-b（后续 Sprint，6 文件）**：接入层 — Config cron 参数 + APScheduler job + Pydantic Schema + FastAPI Router + 注册到 main.py

F204-a 完成后，`earnings_events` 表存在于数据库，可以通过单元/集成测试验证写入与查询逻辑。但 HTTP endpoint 尚不可用（F204-b 交付）。

---

## 1. 实现范围

### 1.1 Alembic 迁移

新文件 `backend/alembic/versions/008_f204_earnings_events.py`：

```sql
CREATE TABLE earnings_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker VARCHAR(10) NOT NULL,
    earnings_date DATE NOT NULL,
    eps_estimate FLOAT,
    eps_actual FLOAT,
    revenue_estimate BIGINT,
    revenue_actual BIGINT,
    time_of_day VARCHAR(8),
    fetched_at DATETIME NOT NULL,
    UNIQUE (ticker, earnings_date)   -- uq_earnings_event_ticker_date
);
CREATE INDEX ix_earnings_events_ticker ON earnings_events(ticker);
CREATE INDEX ix_earnings_events_earnings_date ON earnings_events(earnings_date);
```

upgrade / downgrade 均实现。

### 1.2 SQLAlchemy Model

新文件 `backend/app/models/earnings_event.py`：

- 严格照搬 DATA-MODEL.md 中 `class EarningsEvent(Base)` 定义
- `UniqueConstraint("ticker", "earnings_date", name="uq_earnings_event_ticker_date")`
- `fetched_at` 默认 `lambda: datetime.now(timezone.utc)`

修改 `backend/app/models/__init__.py`：

- 新增 `from app.models.earnings_event import EarningsEvent  # noqa: E402`
- `__all__` 追加 `"EarningsEvent"`

### 1.3 FMP Client 方法

修改 `backend/app/external/fmp_client.py`，追加：

```python
def get_earnings_calendar(self, from_date: str, to_date: str) -> list[Any]:
    """
    调用 FMP /stable/earnings-calendar
    from_date / to_date: YYYY-MM-DD 格式字符串
    返回原始列表，字段约定：symbol / date / epsEstimated / eps /
    revenueEstimated / revenue / time（BMO/AMC/--）
    """
```

- 走现有 `_request` + 限流器（不引入新 HTTP 逻辑）
- 参数：`{ "from": from_date, "to": to_date }`
- 路径常量：`/earnings-calendar`（注意 `FMP_BASE` 已含 `/stable` 前缀，最终命中 `https://financialmodelingprep.com/stable/earnings-calendar`）

### 1.4 EarningsEventRepository

新文件 `backend/app/repositories/earnings_event_repository.py`：

```python
class EarningsEventRepository:
    def __init__(self, db: Session): ...

    def upsert_batch(self, records: list[dict]) -> int:
        """
        增量 upsert。对于每条 (ticker, earnings_date)：
        - estimate 字段（eps_estimate, revenue_estimate, time_of_day, fetched_at）完整覆盖
        - actual 字段（eps_actual, revenue_actual）仅在新值非 None 时覆盖
          （避免 FMP 回填前擦掉已有实际值）
        返回 upsert 行数。
        """

    def get_next_earnings(self, ticker: str, from_date: date) -> EarningsEvent | None:
        """
        查询 ticker 在 from_date（含）之后最近一次 earnings_event。
        无记录返回 None。
        """

    def delete_before(self, cutoff: date) -> int:
        """
        删除 earnings_date < cutoff 的记录（60 天清理窗口）。
        返回删除行数。
        """
```

**upsert_batch 实现说明**：

由于项目使用 SQLite（`database_url` 以 `sqlite` 开头），使用 SQLite 的 `INSERT OR REPLACE` 语义会导致 actual 字段被 NULL 覆盖。需要改用 `INSERT ... ON CONFLICT DO UPDATE SET`（SQLAlchemy 的 `insert(...).on_conflict_do_update()`）。

实现时检测数据库类型：如果是 SQLite，直接用 SQLAlchemy Core 的 `sqlite` dialect `insert` + `on_conflict_do_update`；如果将来迁移 Postgres，同款 API 兼容。

### 1.5 EarningsService

新文件 `backend/app/services/cockpit/earnings_service.py`：

```python
class EarningsService:
    def __init__(self, db: Session, fmp: FmpClient): ...

    def fetch_and_store(self, today: date | None = None) -> dict:
        """
        拉取并 upsert earnings_events。

        窗口策略（来自 DATA-MODEL.md D065）：
          - 未来窗口：from=today, to=today+30（含）
          - 补拉窗口：from=today-7, to=today-1（已发生未入库的）
          合并为单次 FMP 请求：from=today-7, to=today+30

        FMP 响应中 time 字段映射：
          "BMO" → "BMO" | "AMC" → "AMC" | 其他/空 → None

        返回 {"fetched": N, "upserted": M, "date_range": [from, to]}
        """

    def get_next_earnings(self, ticker: str) -> dict:
        """
        查询 ticker 下一次 earnings（earnings_date >= today）。
        返回供 F204-b Router 使用的 dict（字段与 API-CONTRACT.md 对齐）：
          {
            "ticker": ticker,
            "nextEarningsDate": "YYYY-MM-DD" | None,
            "daysUntil": int | None,
            "timeOfDay": str | None,
            "epsEstimate": float | None,
            "revenueEstimate": int | None,
          }
        无记录时 nextEarningsDate=None, daysUntil=None，其余字段同 None。
        """
```

---

## 2. 预计修改文件（共 6 个）

| # | 文件 | 类型 | 说明 |
|---|------|------|------|
| 1 | `backend/alembic/versions/008_f204_earnings_events.py` | 新建 | Alembic 建表迁移 |
| 2 | `backend/app/models/earnings_event.py` | 新建 | SQLAlchemy ORM model |
| 3 | `backend/app/models/__init__.py` | 修改 | +1 import EarningsEvent |
| 4 | `backend/app/repositories/earnings_event_repository.py` | 新建 | upsert_batch + get_next + delete_before |
| 5 | `backend/app/external/fmp_client.py` | 修改 | add get_earnings_calendar() |
| 6 | `backend/app/services/cockpit/earnings_service.py` | 新建 | fetch_and_store + get_next_earnings |

**不计入 6 文件的额外改动**：
- `docs/需求/features.json` — F204 拆为 F204-a/F204-b；F204-a phase 推进至 `contract_agreed` → `in_progress` → `needs_review`
- `claude-progress.txt` — Sprint 条目

---

## 3. 完成标准（可测试）

| # | 标准 | 层级 | 工具 |
|---|------|------|------|
| 1 | `alembic upgrade head` 成功，`earnings_events` 表创建，唯一约束和索引均存在 | 集成 | `alembic` CLI |
| 2 | `alembic downgrade -1` 成功，`earnings_events` 表删除，回到 007 状态 | 集成 | `alembic` CLI |
| 3 | `EarningsEventRepository.upsert_batch` 写入新记录：10 条 (ticker, date) 不同的记录，DB 有 10 行 | 单元 | pytest + in-memory SQLite |
| 4 | `upsert_batch` 再次写入同一 (ticker, date) 但 eps_estimate 变更 → DB 行更新，eps_estimate 为新值 | 单元 | pytest |
| 5 | `upsert_batch` 再次写入同一 (ticker, date) 但 eps_actual 为 None → DB 中已有的 eps_actual **不被覆盖**（保留旧值） | 单元 | pytest（关键业务规则） |
| 6 | `upsert_batch` 写入 eps_actual 非 None 值 → DB 中 eps_actual 被更新 | 单元 | pytest |
| 7 | `get_next_earnings("AAPL", today)` 在有多条未来记录时返回日期最近的一条 | 单元 | pytest |
| 8 | `get_next_earnings("AAPL", today)` 无未来记录时返回 None | 单元 | pytest |
| 9 | `FmpClient.get_earnings_calendar` 调用正确路径 `/stable/earnings-calendar`，传入 `from` / `to` 参数 | 单元 | FakeFMP 或 monkeypatch |
| 10 | `EarningsService.fetch_and_store` 以 FakeFMP 注入，FMP 返回 3 条记录，DB 写入 3 行 | 集成 | pytest + FakeFMP + in-memory SQLite |
| 11 | `EarningsService.get_next_earnings("NVDA")` 返回 dict，字段名与 API-CONTRACT.md 对齐（nextEarningsDate / daysUntil / timeOfDay / epsEstimate / revenueEstimate） | 集成 | pytest |
| 12 | `pytest backend/tests/` 全量回归通过（含新增测试），无新增 failure | 回归 | pytest |

---

## 4. Evaluator 自检清单

### 文件存在性
- [ ] 6 个文件全部存在，路径与表 2 一致
- [ ] `alembic/versions/008_f204_earnings_events.py` 内同时包含 `upgrade` 和 `downgrade` 函数

### 数据模型合规性
- [ ] `EarningsEvent.__tablename__` = `"earnings_events"`
- [ ] `UniqueConstraint("ticker", "earnings_date", name="uq_earnings_event_ticker_date")` 存在
- [ ] `models/__init__.py` 的 `__all__` 包含 `"EarningsEvent"`

### 业务规则合规性
- [ ] `upsert_batch` 对 `eps_actual` / `revenue_actual` 仅在非 None 时更新（grep 确认 None 检查逻辑存在）
- [ ] `fetch_and_store` 窗口为 `today-7` 至 `today+30`（grep 确认 timedelta 值）
- [ ] FMP `time` 字段映射：只保留 `BMO` / `AMC`，其他映射为 `None`（不写入原始字符串）

### D065 合规性
- [ ] `EarningsService` 仅在 `backend/app/services/cockpit/` 目录下，无 `workbench` 引用
- [ ] `EarningsEventRepository` 无任何 `workbench` / `useAppStore` 引用

### 测试
- [ ] 标准 3–11 全部通过（pytest 逐一核对）
- [ ] 标准 12 全量回归通过

### 代码质量
- [ ] `get_earnings_calendar` 走现有 `_request` + 限流器，无自行构造 httpx 请求
- [ ] 无 `Any` 在内部函数签名中出现（外部 FMP 返回值除外）
- [ ] `EarningsService.get_next_earnings` 返回 dict 键名使用 camelCase（对齐 API-CONTRACT）
- [ ] 无 `console.log` / `print` 遗留（Python 用 `logger`）
- [ ] 单个函数不超过 50 行

### 迁移验证
- [ ] `alembic upgrade head` 实际运行无报错（在 dev.db 上执行）
- [ ] `alembic downgrade -1` 实际运行无报错

---

## 5. 非目标（明确不做，留给 F204-b 或后续）

- APScheduler cron job（F204-b）
- `config.py` 中 `earnings_cron_hour/minute` settings（F204-b）
- FastAPI router `GET /api/cockpit/earnings`（F204-b）
- Pydantic response schema（F204-b）
- `main.py` router 注册（F204-b）
- `cockpit_params.py` §4 EARNINGS 阈值（D070 约定，由 **F202** 首次写入）
- earnings_risk 计算逻辑（DANGER/CAUTION/SAFE）（属于 F202 Setup Monitor）
- 前端 Earnings Widget UI（v1.9 P1 scope，不在 v1.8）
- 60 天历史清理 cron（F204-b 挂在 earnings cron job 内）

---

## 6. 开发顺序

1. 迁移文件 `008_f204_earnings_events.py`，运行 `alembic upgrade head` 验证
2. `models/earnings_event.py` + `models/__init__.py` 修改
3. `repositories/earnings_event_repository.py`（含 upsert_batch 的 None 判断逻辑）
4. FMP client `get_earnings_calendar` 方法
5. `services/cockpit/earnings_service.py`
6. 单元/集成测试（覆盖标准 3–11）
7. 全量 `pytest backend/tests/` 回归
8. Evaluator 自检清单逐条打勾
9. features.json 更新 + claude-progress.txt 追加
10. `git commit -m "feat(F204-a): Earnings Calendar 数据层（model + repo + FMP + service）"`

---

## 7. 风险与取舍

- **SQLite upsert 策略**：`INSERT OR REPLACE` 会删除旧行再插入（触发自增 id 变化，且 actual 字段被 NULL 覆盖）。必须用 `INSERT ... ON CONFLICT DO UPDATE SET`，只更新特定列。SQLAlchemy 的 `sqlite.insert(...).on_conflict_do_update(...)` 支持此语义；未来迁移 Postgres 时 `postgresql.insert` 同款 API 兼容。
- **FMP 单次 `from=today-7, to=today+30`**：合并为单次调用减少 API hits。缺点是无法区分"补拉已发生"和"拉取未来"。业务上两类都需要 upsert，没有区别处理，合并调用合理。
- **测试中无真实 FMP 调用**：使用 `FakeFMP`（conftest 中已有）+ 手写 side_effect。实际 FMP shape 验证在 F204-b E2E 中由 smoke test 覆盖。

---

👤 请确认：
1. 6 文件清单及各文件职责 → OK？
2. `upsert_batch` actual 字段 None 判断逻辑（保留旧值） → OK？
3. FMP 请求合并为单次 `from=today-7, to=today+30` → OK？
4. `cockpit_params.py` §4 EARNINGS 阈值由 F202 落地，F204 不建 → OK？

全部 OK 后，我将 features.json 更新、phase 推进至 `contract_agreed`，进入 Generator 模式开始写代码。
