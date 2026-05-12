# Sprint Contract：F211-d1 — 平仓 hook + journal_entries.ai_review 迁移

> 状态：草案 | 起草：2026-04-29 | 父 Feature：F211 AI Contradiction Detector + News Summarizer + Journal Assistant
> 拆分位置：F211-a1 ✅ done / F211-a2 ✅ done / F211-b ✅ done / F211-c ✅ done / **F211-d1（本 sprint）** / F211-d2
> 拆分理由：原 F211-d 范围（平仓 hook + ai_review 迁移 + 月度 cron）合计 7 文件，超 6 文件预算；2026-04-29 用户确认拆为 d1+d2，d1 = 平仓 hook + 迁移（5 文件），d2 = 月度 cron（4 文件，依赖 d1 落地的 journal_review_service）
> 依赖：
>   - F206-a ✅（Position 模型 / PositionService.update_position / PATCH /api/cockpit/positions/{id}）
>   - F208-c ✅（AiGateway.run + ai_memos 写入）
>   - F211-a1 ✅（journal_assistant Pydantic schema 注册到 REGISTRY，complex tier）
>   - F211-a2 ✅（per-task model override 基建，complex tier 可单独切模型）
> 引用文档：
>   - features.json F211 acceptance_criteria："Position Manager 关闭持仓（手动录入平仓）时自动触发 journal_assistant，写入 journal_entry 的 ai_review 字段"
>   - DATA-MODEL.md line 211-243（JournalEntry 表结构）+ line 559（"留待 F211 feature-dev 阶段 Alembic 迁移"）+ line 764-780（SQLAlchemy 模型源代码）
>   - API-CONTRACT.md line 1485-1512（PATCH /api/cockpit/positions/{id}）+ line 1511（"v2.0 已上线，异步触发 F211 journal_assistant，失败不阻塞"）+ line 1655-1735（POST /api/ai/{task_type}）
>   - DECISIONS.md（D064 / D068 / D069 / D070 / D075，本次将追加 D076）
>   - backend/app/ai/schemas/journal_assistant.py（input/output 权威；mode='trade' 子 payload `TradeReviewPayload`）
>   - backend/app/ai/gateway.py（AiGateway.run 接口与 GatewayResult 形态）
>   - backend/app/services/cockpit/position_service.py:111-134（update_position 现状）
>   - backend/app/routers/cockpit/positions.py:62-72（PATCH 路由现状）
>   - backend/app/services/refresh_job.py:399-413（_session_scope 跨线程 session 模式）

---

## 0. 背景与定位

DATA-MODEL.md line 559 明文标记：positions OPEN→CLOSED 时**自动触发 F211 `journal_assistant`**，将复盘结果写入 `journal_entries.ai_review` 字段；该字段是"v2.0 新字段，**非本 Epic 加**，留待 F211 feature-dev 阶段 Alembic 迁移"。

F211-a1 已完成 `journal_assistant` schema 双模式（trade + monthly）注册；F208-c 已暴露 `POST /api/ai/{task_type}` 与 `AiGateway.run`。F211-d1 落地"平仓即触发 trade 模式 review + 持久化到 journal_entries.ai_review"的端到端链路。月度 monthly 模式留 d2。

### 关键约束

1. **不阻塞 PATCH 响应**：journal_assistant 走 complex tier，~5–15s；PATCH 必须立刻返回 CLOSED 后的 PositionItem，AI 调用走 FastAPI `BackgroundTasks` 在响应后执行（**采用 Q2 默认方案**）。
2. **失败不回滚**：BackgroundTask 内 gateway 抛 `AiProviderError` / `AiSchemaError` / `AiGuardrailViolation` / `AiBudgetExceeded` → SystemLog WARN + ai_review 留 null；positions 已 CLOSED **不回滚**（API-CONTRACT.md 已声明"失败不阻塞"）。
3. **JournalEntry 自动生成**：当前 PATCH positions 不写 journal_entries。本 sprint 在 close hook 内**自动 INSERT 一条 SELL `journal_entry`**（**Q3 默认方案**），ai_review 写到该 entry。若同 ticker + 同 date + action=SELL 已存在 → 复用最早一条，不重复 INSERT；若复用条已有 ai_review（手工或上次 hook 已写）→ 跳过 gateway 调用（避免重复打 LLM）。
4. **ai_review 列类型**：SQLite-friendly，使用 `Text` + 应用层 `json.dumps/loads`（**Q1 默认方案**），与 `ai_memos.input_json` / `output_json` 一致；DTO 中暴露为 dict。
5. **跨线程 session**：BackgroundTask 不能复用请求 session（SQLAlchemy Session 非线程安全，FastAPI 在 response 后关闭请求 session）。task 内通过注入的 `SessionLocal` factory 开新 session（沿用 `refresh_job._session_scope` 同款 pattern）。
6. **不动前端**：本 sprint 仅后端落库；ai_review 在 PositionItem / JournalEntry DTO 中**暴露**字段（前端可读），但**不实现**前端展示（Q8 默认）。
7. **不引入新依赖**：FastAPI `BackgroundTasks` 内置；ai gateway / ai schemas 已有；alembic 已配置。

### 月度复盘（明确不在本 sprint）

- monthly cron 注册 / `_journal_monthly_tick` / `journal_review_service.monthly_review_for_month` / `config.journal_monthly_cron_*` settings — 全部留给 F211-d2
- F211-d1 写的 `journal_review_service` **仅含 trade 模式接口**（`trade_review_for_position`），d2 在同一文件追加 monthly 方法

---

## 1. 实现范围

### 1.1 包含

#### A. 新建 Alembic 迁移 `017_f211d1_journal_entries_ai_review.py`（第 1 文件）

位置：`backend/alembic/versions/017_f211d1_journal_entries_ai_review.py`

```python
"""F211-d1: journal_entries.ai_review (Text/JSON, nullable) + ai_review_memo_id (Integer, nullable, FK→ai_memos.id)
revision: 017
down_revision: 016
"""
def upgrade():
    op.add_column('journal_entries', sa.Column('ai_review', sa.Text(), nullable=True))
    op.add_column('journal_entries', sa.Column('ai_review_memo_id', sa.Integer(), nullable=True))
    # 不加 FK 约束（D069 ai_memos 180 天滚动清理，FK 会阻塞清理）；只保留 nullable Integer 引用

def downgrade():
    op.drop_column('journal_entries', 'ai_review_memo_id')
    op.drop_column('journal_entries', 'ai_review')
```

**字段说明**：
- `ai_review`：JSON 字符串，schema 与 `JournalAssistantOutput.trade` 子 payload 对齐：`{"planVsActualScore":int, "entryQuality":str, "stopDiscipline":str, "mistakes":[str], "lesson":str}`。读取时 `json.loads` 解为 dict。
- `ai_review_memo_id`：指向 `ai_memos.id` 的弱引用（无 DB 级 FK），用于审计 / 调试时定位完整 input/output。180 天后 ai_memos 行被清理，本字段保留但解引用失败 → 应用层接受 dangling 引用。

#### B. `models/journal_entry.py` 加列 + DTO 输出（第 2 文件）

位置：`backend/app/models/journal_entry.py`

```python
ai_review = Column(Text, nullable=True)
ai_review_memo_id = Column(Integer, nullable=True)
```

同步修改 `services/journal_service.py::_to_dto`：

```python
import json
...
ai_review = None
if entry.ai_review:
    try:
        ai_review = json.loads(entry.ai_review)
    except (json.JSONDecodeError, TypeError):
        ai_review = None  # corrupt JSON in DB → silent null，不抛
return {
    ..."ai_review": ai_review,
    "ai_review_memo_id": entry.ai_review_memo_id,
}
```

**DTO 字段命名**：snake_case `ai_review` + `ai_review_memo_id`（沿用现有 journal DTO 风格 `stock_name` / `position_size`）。journal API response 由现有 `journal.py` schema 处理；本 sprint **不动** journal API 响应 schema（向后兼容：旧字段不变，新字段对未升级前端透明）。

#### C. 新建 `journal_review_service.py`（第 3 文件，纯后端业务层）

位置：`backend/app/services/cockpit/journal_review_service.py`（新建）

```python
"""F211-d1: JournalReviewService — generate AI review for closed positions.

trade mode: single-position post-exit review。月度 monthly mode 留给 F211-d2。
"""
import json
import logging
from typing import Callable

from sqlalchemy.orm import Session

from app.ai.errors import AiBudgetExceeded, AiProviderError, AiSchemaError, AiGuardrailViolation
from app.ai.gateway import AiGateway
from app.models.journal_entry import JournalEntry
from app.models.position import Position
from app.models.stock import Stock
from app.repositories.journal_repository import JournalRepository
from app.repositories.stock_repository import StockRepository

logger = logging.getLogger(__name__)
SessionFactory = Callable[[], Session]


class JournalReviewService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._gateway = AiGateway(db)

    def trade_review_for_position(self, position_id: int) -> int | None:
        """Background-task-safe entry. Returns journal_entry_id on success, None on any failure."""
        try:
            position = self._db.get(Position, position_id)
            if position is None or position.status != "CLOSED":
                logger.warning("trade_review skipped: position %s not found or not CLOSED", position_id)
                return None

            stock = self._db.query(Stock).filter(Stock.ticker == position.ticker).first()
            if stock is None:
                logger.warning("trade_review skipped: ticker %s not in watchlist", position.ticker)
                return None

            entry = self._upsert_sell_journal_entry(stock_id=stock.id, position=position)
            if entry.ai_review:
                logger.info("trade_review skipped: journal_entry %s already has ai_review", entry.id)
                return entry.id

            input_dict = self._build_trade_input(position)
            result = self._gateway.run(task_type="journal_assistant", input_dict=input_dict)

            entry.ai_review = json.dumps(result.output, ensure_ascii=False, sort_keys=True)
            entry.ai_review_memo_id = result.memo_id
            self._db.commit()
            return entry.id

        except (AiProviderError, AiSchemaError, AiGuardrailViolation, AiBudgetExceeded) as e:
            logger.warning("trade_review AI error position=%s: %s: %s", position_id, type(e).__name__, e)
            self._db.rollback()
            return None
        except Exception:  # noqa: BLE001 — top boundary, must not raise into BackgroundTask runtime
            logger.exception("trade_review unexpected error position=%s", position_id)
            self._db.rollback()
            return None

    def _upsert_sell_journal_entry(self, *, stock_id: int, position: Position) -> JournalEntry:
        """Find or create a SELL journal_entry on the close date for this ticker."""
        close_date = position.closed_at.date() if position.closed_at else position.updated_at.date()
        existing = (
            self._db.query(JournalEntry)
            .filter(
                JournalEntry.stock_id == stock_id,
                JournalEntry.action == "SELL",
                JournalEntry.date == close_date,
            )
            .order_by(JournalEntry.id.asc())
            .first()
        )
        if existing is not None:
            return existing
        entry = JournalEntry(
            stock_id=stock_id,
            action="SELL",
            price=position.close_price,
            date=close_date,
            position_size=float(position.shares),
            stop_loss=position.stop_price,
            target_price=position.target_2r,
            reason="auto: position closed",
            reference=None,
        )
        self._db.add(entry)
        self._db.flush()  # populate id without commit (commit happens after AI succeeds)
        return entry

    def _build_trade_input(self, position: Position) -> dict:
        entry_date = position.entry_date.isoformat()
        exit_date = (position.closed_at or position.updated_at).date().isoformat()
        holding_days = (position.closed_at.date() - position.entry_date).days if position.closed_at else 0
        risk_per_share = position.entry_price - position.stop_price
        r_multiple = round((position.close_price - position.entry_price) / risk_per_share, 2) if risk_per_share > 0 else 0.0
        return {
            "mode": "trade",
            "trade": {
                "ticker": position.ticker,
                "setupType": position.setup_type,
                "setupQuality": None,  # not tracked at position level
                "plannedEntry": position.entry_price,
                "plannedStop": position.stop_price,
                "plannedTarget2r": position.target_2r,
                "actualEntry": position.entry_price,  # F206 doesn't track partial fills
                "actualExit": position.close_price,
                "shares": position.shares,
                "entryDate": entry_date,
                "exitDate": exit_date,
                "holdingDays": max(holding_days, 0),
                "rMultiple": r_multiple,
                "preTradeNotes": (position.notes or None),
            },
        }
```

#### D. `position_service.py` 加 close hook（第 4 文件）

位置：`backend/app/services/cockpit/position_service.py`

```python
# 现有 import 扩展
from fastapi import BackgroundTasks
from typing import Callable
from sqlalchemy.orm import Session
from app.services.cockpit.journal_review_service import JournalReviewService

SessionFactory = Callable[[], Session]

# update_position 签名扩展
def update_position(
    self,
    position_id: int,
    patch: PositionUpdate,
    background_tasks: BackgroundTasks | None = None,
    session_factory: SessionFactory | None = None,
) -> PositionItem | None:
    row = self._repo.get_by_id(position_id)
    if row is None:
        return None

    pre_status = row.status  # capture for transition detection
    patch_data = patch.model_dump(exclude_unset=True, by_alias=False)

    if patch_data.get("status") == "OPEN" and row.status == "CLOSED":
        raise APIError("VALIDATION_ERROR", "Cannot reopen a CLOSED position", 422)

    self._repo.update(position_id, patch_data)
    updated_row = self._repo.get_by_id(position_id)
    if updated_row is None:
        return None

    # F211-d1: trigger AI review on OPEN→CLOSED transition (async, fail-soft)
    if (
        pre_status == "OPEN"
        and updated_row.status == "CLOSED"
        and background_tasks is not None
        and session_factory is not None
    ):
        background_tasks.add_task(
            _trade_review_background,
            session_factory,
            updated_row.id,
        )

    closes = self._loader.load([updated_row.ticker])
    today = date.today()
    return self._enrich(...)


# module-level top-of-file
def _trade_review_background(session_factory: SessionFactory, position_id: int) -> None:
    """Run in FastAPI BackgroundTask after response. Opens a fresh DB session."""
    db = session_factory()
    try:
        JournalReviewService(db).trade_review_for_position(position_id)
    finally:
        db.close()
```

**Router 改造（同文件不算，仅 1 行）**：`positions.py::update_position` 加 `BackgroundTasks` 注入 + `SessionLocal` factory 注入，转给 service。本改动非常小（~6 行 diff），**复用现有 `dependencies.get_db_session_factory` 若不存在则 inline `from app.database import SessionLocal`**。

⚠️ **注意**：positions.py 路由文件改动算入第 4 文件之内（同 service 文件 sprint，路由层修改 ≤ 8 行作为同 sprint 集成代价计入 service 计数；明确不另开第 8 文件）。如果用户在协商阶段反对此合并计数，则切分为：position_service（第 4）+ positions.py（第 5）+ test 合并（替换 5 → ↓）。**默认方案：合并第 4，positions.py 改动作为 service 模块同 sprint 必要集成。**

#### E. 测试 `test_journal_review_service_f211d1.py`（第 5 文件）

位置：`backend/tests/test_journal_review_service_f211d1.py`（新建）

测试用例（共 15 个，5 单元 + 8 集成 + 2 e2e）：

| # | 类型 | 用例 |
|---|---|---|
| U1 | 单元 | `_build_trade_input` 正常 position → input dict 结构与 schema 匹配（Pydantic `JournalAssistantInput(**input)` 不抛） |
| U2 | 单元 | `_build_trade_input` rMultiple 计算：entry=100, stop=95, exit=110 → r=2.0 |
| U3 | 单元 | `_build_trade_input` setup_type / notes 缺失 → setupType=None / preTradeNotes=None，不抛 |
| U4 | 单元 | `_build_trade_input` risk_per_share = 0（不应发生但防御）→ rMultiple=0.0 不抛 ZeroDivision |
| U5 | 单元 | `_upsert_sell_journal_entry` 复用：已有同 ticker+date+SELL → 不重复 INSERT，返回原 entry |
| I1 | 集成 | `trade_review_for_position` 正常路径（gateway mock 成功）→ 写入新 SELL entry + ai_review JSON + ai_review_memo_id |
| I2 | 集成 | `trade_review_for_position` 已有 SELL entry 且 ai_review 已填 → 跳过 gateway，返回原 id（mock gateway 不被调用 assertion） |
| I3 | 集成 | `trade_review_for_position` AiProviderError → ai_review 留 null，返回 None，positions row 不回滚 |
| I4 | 集成 | `trade_review_for_position` AiBudgetExceeded → 同上，log WARN |
| I5 | 集成 | `trade_review_for_position` AiGuardrailViolation → 同上 |
| I6 | 集成 | `trade_review_for_position` position 不存在 → 早返回 None，不打 gateway |
| I7 | 集成 | `trade_review_for_position` ticker 不在 watchlist（无 stock 行）→ 早返回 None，log WARN |
| I8 | 集成 | `trade_review_for_position` position.status != CLOSED → 早返回 None，防御重入 |
| E1 | e2e | PATCH /api/cockpit/positions/{id} status=OPEN→CLOSED → 响应 200 立即返回 + BackgroundTask 调度（用 `TestClient` + `app.dependency_overrides` 注入 mock JournalReviewService，断言 `trade_review_for_position` 被调用 1 次） |
| E2 | e2e | PATCH 同上但 pre_status=CLOSED（已经是 CLOSED）→ BackgroundTask **不**调度 |

**测试基础设施**：
- 复用现有 `tests/conftest.py` 的 `db_session` / `client` fixture
- mock AiGateway 用 `monkeypatch.setattr("app.services.cockpit.journal_review_service.AiGateway.run", fake_run)`
- `fake_run` 返回 `GatewayResult(output={"mode":"trade","trade":{...合规...}}, memo_id=999, ...)`

#### F. `features.json` 更新（不计入 6 文件预算 — 文档/状态字段，与 a1/a2/b/c 协商一致不计）

变更：
1. `sub_sprints["F211-d1"]: "design_needed"` → `"contract_agreed"`
2. `iteration_history` 追加：
   ```json
   {
     "date": "2026-04-29",
     "subtask": "F211-d1",
     "phase": "contract_agreed",
     "summary": "...",
     "contract": "docs/开发/sprint-contracts/F211-d1-contract.md",
     "contract_agreed_at": "2026-04-29"
   }
   ```
3. `_pipeline_status.active_sprint` 已为 `F211-d1`（C8 已修复）

#### G. `DECISIONS.md` 追加 D076（不计入 6 文件预算 — 文档）

```markdown
## D076: F211-d1 close hook 异步策略 + ai_review 列形态
日期：2026-04-29 | Feature: F211-d1
方案：
1. PATCH /api/cockpit/positions/{id} OPEN→CLOSED 触发 FastAPI `BackgroundTasks`，不阻塞响应
2. BackgroundTask 内开新 SQLAlchemy session（不复用请求 session）
3. journal_entries 加 ai_review (Text/JSON 字符串) + ai_review_memo_id (Integer, no DB FK)
4. 平仓自动 INSERT/复用 SELL journal_entry（同 ticker+date 的 SELL 复用，避免重复打 LLM）
5. 任何 AI 错误（Provider / Schema / Guardrail / Budget）→ ai_review 留 null，positions 已 CLOSED 不回滚
理由：
- 异步：journal_assistant complex tier ~5–15s，不能阻塞 PATCH 响应
- Text 列：与 ai_memos.input_json/output_json 一致，避开 SQLite JSON 类型移植性问题
- 无 FK：D069 ai_memos 180 天滚动清理，FK 会阻塞清理；ai_review_memo_id 接受 dangling
- 复用 SELL entry：避免同一交易多次平仓尝试时重复打 LLM 烧 budget
对应代码：position_service._trade_review_background, journal_review_service.trade_review_for_position
未通过 Context7 验证：FastAPI BackgroundTasks 是 SDK 稳定 API，不需要外部文档查询
```

### 1.2 排除（明确不在 d1 内）

- ❌ 月度复盘 cron（refresh_job + config + journal_review_service.monthly_review_for_month + 测试）→ F211-d2
- ❌ 前端 ai_review 展示组件（PositionManager 平仓后 UI）→ 未来 F211-e 或 v1.10 视设计需求
- ❌ ai_review 历史回填脚本（已有 CLOSED positions 反向生成 review）→ 不在范围内，需要可手动通过管理脚本触发
- ❌ journal_assistant 月度 schema 变更 / 新 task_type 注册（schema 已 F211-a1 完成，本 sprint 0 行 schema 改动）
- ❌ position.notes / pending_order 影响（本 sprint 只读 position 字段，不改 PendingOrder 流程）
- ❌ 跨股票批量复盘 / 多 position 同时平仓的并发控制（FastAPI BackgroundTasks 默认顺序执行，单用户场景无并发；不引 Lock）
- ❌ 重试机制（gateway 失败即终态，不调度重试 task；用户可通过未来管理 endpoint 手动触发）
- ❌ ai_review 的 PATCH/PUT API（用户不可手动覆盖 AI 输出；如需修订改 reason 字段）
- ❌ test_position_service 现有测试的扩展（除 E1/E2 e2e 用例外，position_service 现有单测不动；新签名带默认参数 `None` 向后兼容）
- ❌ data-mapping.md / design-spec.md 更新（无视觉 / 数据映射决策）

---

## 2. 预计修改文件清单（共 5 个，1 个余量）

| # | 文件 | 操作 | 估行数 |
|---|------|------|--------|
| 1 | `backend/alembic/versions/017_f211d1_journal_entries_ai_review.py` | 新建 | ~25 |
| 2 | `backend/app/models/journal_entry.py` + `app/services/journal_service.py::_to_dto` | 修改 | +5 / +6 |
| 3 | `backend/app/services/cockpit/journal_review_service.py` | 新建 | ~140 |
| 4 | `backend/app/services/cockpit/position_service.py` + `app/routers/cockpit/positions.py`（路由 +6 行 BackgroundTasks 注入） | 修改 | +30 / +6 |
| 5 | `backend/tests/test_journal_review_service_f211d1.py` | 新建 | 15 case，~400 |

**辅助变更（不计入 6 文件预算）**：
- `docs/需求/features.json`（status 字段更新）
- `docs/系统设计/DECISIONS.md`（D076）
- `claude-progress.txt`（contract_agreed 记录）
- `SESSION-HANDOFF.md`（生成）

⚠️ 文件 #2 和 #4 各合并了两处 module 改动（model + service::\_to\_dto；service + router）。这种合并是因为单 module 改动 < 10 行 + 与父 module 强耦合，**仅在两处合计 ≤ 50 行 / 用同一 commit message 时才允许**。如审阅认为应拆开 → 触发再次拆分（成 d1a + d1b）。**默认方案：维持 5 文件计数。**

---

## 3. 完成标准（可测试）

| # | 标准 | 测试层级 | 工具 |
|---|------|---------|------|
| C1 | Alembic upgrade → journal_entries 表多 ai_review (Text) + ai_review_memo_id (Integer) 两列 | 集成 | pytest + alembic upgrade head |
| C2 | Alembic downgrade → 两列消失 | 集成 | pytest + alembic downgrade -1 |
| C3 | journal_service._to_dto 返回字典含 `ai_review` (dict) 和 `ai_review_memo_id` (int)；存 null 时返回 None | 单元 | pytest |
| C4 | journal_service._to_dto 处理 corrupt JSON：ai_review='not_json' → 返回 None，不抛 | 单元 | pytest |
| C5 | U1-U5 全过：_build_trade_input + _upsert_sell_journal_entry 行为正确 | 单元 | pytest |
| C6 | I1-I8 全过：trade_review_for_position 8 路径正确 | 集成 | pytest |
| C7 | E1：PATCH 平仓 → 响应 200 < 1s，BackgroundTask 调度且 trade_review_for_position 被调用 1 次 | e2e | pytest TestClient |
| C8 | E2：CLOSED→CLOSED 不重复触发 | e2e | pytest TestClient |
| C9 | mypy --strict 0 新增错误（baseline pre-existing 4 项不算） | 静态 | mypy |
| C10 | ruff check 0 新增 violation | 静态 | ruff |
| C11 | 全量后端 pytest ≥ baseline（F211-c 后 893+ 通过），无 NEW 失败 | 回归 | pytest |
| C12 | API-CONTRACT.md line 1511 行为兑现：实测 PATCH 响应 < 1s，AI 错误时不影响 200 响应 | 集成 | pytest 计时 + force AiProviderError |

---

## 4. Evaluator 自检清单

代码：
- [ ] C1-C12 全过
- [ ] alembic 017 文件 down_revision 正确指向 016（最新一个）
- [ ] journal_entries 新列 nullable=True 默认（已有数据 0 行迁移成本）
- [ ] BackgroundTask 内任何 raise 都被捕获（top-level Exception boundary）；FastAPI 日志无未处理异常
- [ ] `journal_review_service` 不直接 import `position_service`（避免循环）；只 import 模型 / 仓库 / gateway
- [ ] `_build_trade_input` 输出过 `JournalAssistantInput(**dict)` Pydantic 验证（在测试中 assert）
- [ ] gateway 调用前/后 commit 时序：先 flush 拿到 entry.id，gateway 成功后才 commit；失败 rollback（避免半生 SELL entry 留库）
- [ ] `closed_at` 为 timezone-aware（Position.closed_at DateTime UTC，需 .date() 不会报错）
- [ ] PATCH 路由 `BackgroundTasks` 通过 FastAPI Depends 注入，service 签名带默认 None 保持向后兼容（直接 `service.update_position(id, patch)` 仍可用）

数据：
- [ ] alembic upgrade 后 SELECT * FROM journal_entries 现有 0 行不受影响
- [ ] 复用 SELL entry 时 `position_size`/`stop_loss`/`target_price` 不被覆盖（仅 ai_review 字段写入）
- [ ] ai_review JSON 持久化使用 `ensure_ascii=False, sort_keys=True`（与 ai_memos canonical 风格一致）

文档：
- [ ] DECISIONS.md D076 已追加
- [ ] features.json sub_sprints / iteration_history 更新完整
- [ ] DATA-MODEL.md line 559 注释自然兑现，无需改 schema（字段已声明）；如 frontmatter 仍 confirmed 则不动
- [ ] claude-progress.txt 追加 F211-d1 contract_agreed 与各开发步骤
- [ ] SESSION-HANDOFF.md 更新

回归（不可跳过）：
- [ ] 全量后端 pytest 跑一遍，对比 F211-c 验收基线（893+ pass）
- [ ] 失败计数 ≤ 基线，否则打回 Generator
- [ ] consistency-check (mode=interactive) C5 通过：sub_sprints["F211-d1"] entry ↔ 合约文件存在
- [ ] consistency-check C1 invariant：F211-d1 升 done 后，d2 仍 design_needed → 父 F211 status 不能升 done

---

## 5. 开发顺序（Generator 模式）

> ⚠️ 不得跳步、不得颠倒。每完成一步，wip commit + claude-progress.txt 追加。**禁用 `git add -A`**。

**步骤 1：预检（不写实现）**
- 跑 `cd backend && alembic current` 确认头是 016
- 读 `backend/app/models/position.py` 确认 closed_at / close_price / shares / stop_price / target_2r / setup_type / notes 字段名一致
- 读 `backend/app/ai/gateway.py::GatewayResult / GatewayMeta` 确认 `result.output` 是 dict、`result.memo_id` 是 int
- 读 `backend/tests/conftest.py` 确认 `db_session` / `client` / `app` fixture 可用
- 读 `backend/app/database.py` 确认 `SessionLocal` 是 module-level callable（factory）
- 读 `backend/tests/test_ai_gateway_e2e_f208c.py` 任意一个 case，复用 fake gateway pattern

→ 不 commit（预检不改文件）

**步骤 2：Alembic 迁移（第 1 文件）**
- 新建 `017_f211d1_journal_entries_ai_review.py`，upgrade 加两列，downgrade 删两列
- 跑 `alembic upgrade head` → 应成功
- 跑 `alembic downgrade -1` → 应成功
- 跑 `alembic upgrade head` 复位

→ wip commit：`wip(F211-d1): alembic 017 ai_review columns`

**步骤 3：Model + DTO（第 2 文件）**
- 改 `journal_entry.py` 加两列
- 改 `journal_service.py::_to_dto` 加 ai_review JSON 解码 + ai_review_memo_id 透传
- 跑现有 `pytest tests/test_journal_*.py` → 应不影响（新字段透传 None）

→ wip commit：`wip(F211-d1): journal_entry model + DTO ai_review fields`

**步骤 4：JournalReviewService（第 3 文件）**
- 新建 `journal_review_service.py`，落地 `trade_review_for_position` + `_upsert_sell_journal_entry` + `_build_trade_input`
- 单测 U1-U5 + I1-I8 同步写

→ wip commit：`wip(F211-d1): JournalReviewService trade mode + 13 tests`

**步骤 5：position_service close hook + router（第 4 文件）**
- `position_service.update_position` 加 `background_tasks` / `session_factory` 默认 None 参数
- 加 module-level `_trade_review_background` 函数
- `routers/cockpit/positions.py::update_position` 加 `BackgroundTasks` 注入 + `from app.database import SessionLocal`，转给 service
- E1/E2 e2e 测试

→ wip commit：`wip(F211-d1): position close hook + 2 e2e`

**步骤 6：回归 + 静态检查（不 commit 单独，并入下一步）**
- 跑全量 `pytest backend/tests/` → 对比基线
- 跑 `mypy backend/app` / `ruff check backend/app` → 确认 0 新增违例
- 跑 `pytest --collect-only | grep f211d1 | wc -l` → 应 ≥ 15

**步骤 7：合并 Evaluator 后 squash？**
- 默认保留 wip commit 细粒度（feature-dev 规则 7：默认不 squash）
- Evaluator 自检全过后，最终 commit：
  ```
  git add backend/alembic/versions/017_f211d1_journal_entries_ai_review.py \
          backend/app/models/journal_entry.py \
          backend/app/services/journal_service.py \
          backend/app/services/cockpit/journal_review_service.py \
          backend/app/services/cockpit/position_service.py \
          backend/app/routers/cockpit/positions.py \
          backend/tests/test_journal_review_service_f211d1.py \
          docs/需求/features.json \
          docs/系统设计/DECISIONS.md \
          claude-progress.txt
  git commit -m "feat(F211-d1): position close hook + journal_entries.ai_review migration"
  ```

---

## 6. 开放问题（用户协商时拍板，未列项即采默认）

| # | 问题 | 默认方案 | 备选 |
|---|------|---------|------|
| Q1 | ai_review 列类型 | `Text` + json.dumps/loads | SQLite JSON 类型（兼容性差） |
| Q2 | 平仓 hook 同步/异步 | `BackgroundTasks` 异步，失败不阻塞 | 同步阻塞 PATCH（用户体验差） |
| Q3 | 平仓是否自动 INSERT SELL journal_entry | ✅ INSERT；同 ticker+date 已有则复用 | 不 INSERT，ai_review 写 positions（违反 DATA-MODEL.md） |
| Q4 | 已有 SELL entry 的 ai_review 是否覆盖 | ❌ 跳过 gateway，避免重复打 LLM | 强制覆盖（烧 budget） |
| Q5 | ai_review_memo_id 是否加 DB FK | ❌ 不加（D069 滚动清理冲突） | 加 FK + ON DELETE SET NULL |
| Q6 | gateway 失败时 positions 是否回滚 | ❌ 不回滚（API-CONTRACT 已声明） | 回滚 → 用户体验更差，且 PATCH 已返回 200 |
| Q7 | service 签名加 BackgroundTasks 必选还是可选 | 可选（默认 None，向后兼容） | 必选（破坏现有 unit test） |
| Q8 | 本 sprint 是否含前端展示 | ❌ 仅后端落库 | 含前端 → 6 文件超额，需进一步拆分 |
| Q9 | 文件 #2/#4 合并计数是否成立 | ✅ 合并，5 文件 | 拆开成 7 文件，触发 d1a/d1b 二次拆分 |
| Q10 | 测试基础设施新增 fake gateway helper 是否抽 conftest | ❌ inline 在测试文件内 | 抽到 conftest（污染其他模块） |

---

## 7. 风险与回避

1. **FastAPI BackgroundTasks 失效场景**：若任务在 worker 重启时排队尚未执行 → 该次 ai_review 永久丢失。**接受**：用户可手动在未来管理 endpoint（不在本 sprint）触发回填，或忽略（CLOSED 仍是 CLOSED，positions 状态正确）。
2. **session 跨线程泄漏**：BackgroundTask 内 finally close session。如 commit 抛异常 → rollback 路径已覆盖。pytest E1/E2 验证 SQLAlchemy session 计数无泄漏（用 `db_session` fixture 末尾自检）。
3. **gateway budget 超限**：AiBudgetExceeded 在 trade hook 中静默 → 用户不知道 ai_review 没填。**接受**：作为 D069 月预算策略一部分，Logs 页可看 SystemLog WARN（v1.0 已实现）。
4. **journal_assistant complex tier 模型**：F211-a2 已支持 per-task model override；用户可在 `.env.AI_TASK_OVERRIDES_JSON` 单独切 journal_assistant 模型 / cost。本 sprint 0 行配置改动。
5. **schema_version 不变**：`journal_assistant` v1，不会触发 D069 ai_memos cache invalidate。
6. **`alembic 017` revision 编号竞争**：F211 其它分支同时迭代会冲突。**前提**：当前 016 是最新，d1 是唯一的下一 revision；如 d2 后续也需迁移，递增到 018。

---

## 8. 与 F211-d2 接口（前置约定）

F211-d2 将在 `journal_review_service.py` 同文件追加 `monthly_review_for_month(year_month: str)` 方法。本 sprint **预留**：
- `JournalReviewService.__init__` 已注入 `db: Session`，d2 直接复用
- `_build_trade_input` 命名约定 `_build_<mode>_input`，d2 加 `_build_monthly_input`
- 测试文件 `test_journal_review_service_f211d2.py` 独立，不与本 sprint 测试合并

d2 不需要回头改 d1 落地的代码 / 模型 / 迁移。

---

## 9. 用户确认

请回复：

A. **接受合约 + 默认方案**（推荐）
B. 修改某条 Q（指出 Q# 与改动方向）
C. 重新拆分（如反对 #2/#4 合并计数 → 拆 d1a/d1b）

确认后执行：
1. `features.json` 更新 sub_sprints["F211-d1"]: contract_agreed + iteration_history 追加
2. `claude-progress.txt` 追加 contract_agreed 记录
3. 生成 SESSION-HANDOFF.md
4. **强制停止**，开新 session 用 Sonnet 进入 Generator 模式从步骤 1 开始
