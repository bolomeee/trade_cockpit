# Sprint Contract：F211-d2 — 月度复盘 cron + journal_assistant monthly mode

> 状态：草案 | 起草：2026-04-29 | 父 Feature：F211 AI Contradiction Detector + News Summarizer + Journal Assistant
> 拆分位置：F211-a1 ✅ done / F211-a2 ✅ done / F211-b ✅ done / F211-c ✅ done / F211-d1 ✅ done / **F211-d2（本 sprint，收尾）**
> 拆分理由：F211-d 因 7 文件超 6 文件预算，2026-04-29 拆为 d1 + d2；d1 落地 trade 模式 + ai_review 列；本 sprint 仅 monthly cron。
> 依赖：
>   - F206-a ✅（Position 模型 / closed_at / status='CLOSED'）
>   - F208-c ✅（AiGateway.run + ai_memos 持久化 + memo_dedup 24h TTL）
>   - F211-a1 ✅（journal_assistant monthly schema：MonthlyReviewPayload + MonthlyReviewOutput + BANNED_PHRASES guardrail 已覆盖 monthly 字段）
>   - F211-a2 ✅（complex tier per-task model override）
>   - F211-d1 ✅（JournalReviewService 类骨架 + AiGateway 注入 + 异常分支模板）
> 引用文档：
>   - features.json F211 acceptance_criteria："journal_assistant 每月 1 号自动生成上月交易复盘报告（rule adherence / expectancy / setup-level performance）"
>   - DATA-MODEL.md（无 schema 变更；MonthlyReview 输出仅落 ai_memos，依赖 D069 滚动清理）
>   - API-CONTRACT.md（无新 endpoint；POST /api/ai/{task_type} 已支持 task_type=journal_assistant + mode=monthly）
>   - DECISIONS.md（D064 / D069 / D076；本次将追加 D077）
>   - backend/app/ai/schemas/journal_assistant.py:60-94（MonthlyReviewPayload/Output/guardrail，已实现）
>   - backend/app/services/cockpit/journal_review_service.py（d1 落地，本 sprint 同文件追加）
>   - backend/app/services/refresh_job.py:176-300（start_scheduler / 现有 7 个 cron job 注册 pattern）
>   - backend/app/services/refresh_job.py:399-413（_session_scope 跨线程 session pattern）
>   - backend/app/config.py:16-44（cron settings pattern）
>   - backend/tests/test_earnings_f204b.py:103-145（scheduler 注册测试 + tick swallow exception pattern）

---

## 0. 背景与定位

F211 acceptance_criteria 第 6 条："journal_assistant 每月 1 号自动生成上月交易复盘报告"。F211-a1 schema 已就绪（MonthlyReviewPayload / MonthlyReviewOutput），F211-d1 已落地 JournalReviewService 类骨架与 trade 模式；本 sprint 在同一类追加 `monthly_review_for_month(year_month: str)`，并在 refresh_job scheduler 注册 `_journal_monthly_tick`，每月 1 号触发一次。

### 关键约束

1. **0 行 schema / 迁移改动**：journal_assistant monthly schema 已 F211-a1 注册；不新增 task_type；guardrail 已覆盖 monthly 字段。
2. **0 张新表**：monthly review 输出**仅落 ai_memos**（AiGateway 已自动持久化 input/output），依赖 D069 滚动清理（180 天）+ 24h memo dedup。**不写 journal_entries**（避免新增 action 类型 / schema 变更 / 迁移）。
3. **跨线程 session**：cron tick 不能复用请求 session；用 `_session_scope(session_factory)` 在 tick 内开新 session（沿用 refresh_job 现有 7 个 tick 同款 pattern）。
4. **0 trades 月份**：上月 closed_count == 0 → 跳过 gateway 调用（MonthlyReviewPayload.closedTrades min_length=1 会拒绝空列表，主动跳过更清晰），log INFO，不抛。
5. **重入幂等**：依赖 gateway memo dedup（input_hash + 24h TTL）+ schema_version=v1。同月份 24h 内重复触发 → 命中 cache，**不重复烧 budget**；24h 后再触发会 cache miss → 重新打 LLM（接受：cron 每月只触发一次，低概率）。
6. **失败不重试**：tick 顶层 `try/except Exception` swallow（与 refresh_job 现有所有 tick 一致），SystemLog WARN，下月自然再来；**不调度重试 task / 不引退避**。
7. **不引入新依赖**：APScheduler / SQLAlchemy / journal_assistant schema / AiGateway 全部已有。
8. **不动前端**：本 sprint 仅后端落 ai_memos；用户消费方式留 v1.10 未来 feature（acceptance_criteria 仅约束"自动生成"，未约束 UI）。

### 与 F211-d1 的边界

- ✅ 复用 d1 的 `JournalReviewService.__init__(db)` / 依赖注入 / 异常分支模板
- ✅ 复用 `_session_scope` cross-thread session helper
- ❌ 不改 d1 落地的 trade 路径任何代码（`trade_review_for_position` / `_upsert_sell_journal_entry` / `_build_trade_input` 全部不动）
- ❌ 不改 alembic 017（journal_entries.ai_review 列与 monthly 模式无关）
- ❌ 不改 position_service / positions router（monthly 由 cron 触发，不经 PATCH）

---

## 1. 实现范围

### 1.1 包含

#### A. `journal_review_service.py` 追加 monthly 接口（第 1 文件，修改）

位置：`backend/app/services/cockpit/journal_review_service.py`

新增方法（追加到现有类内）：

```python
from datetime import date, datetime, timedelta, timezone

# 类内追加：
def monthly_review_for_month(self, year_month: str) -> int | None:
    """Background-task-safe entry. Returns ai_memos.id on success, None on skip / failure.

    year_month: 'YYYY-MM' (UTC).
    Skip cases (return None, no error):
      - 0 closed positions in the month
      - any AI error (Provider / Schema / Guardrail / Budget)
    """
    try:
        closed = self._fetch_closed_positions_for_month(year_month)
        if not closed:
            logger.info("monthly_review skipped: 0 closed positions in %s", year_month)
            return None

        input_dict = self._build_monthly_input(year_month, closed)
        result = self._gateway.run(task_type="journal_assistant", input_dict=input_dict)
        logger.info(
            "monthly_review ok month=%s memo_id=%s closed=%d",
            year_month, result.memo_id, len(closed),
        )
        return result.memo_id
    except (AiProviderError, AiSchemaError, AiGuardrailViolation, AiBudgetExceeded) as e:
        logger.warning(
            "monthly_review AI error month=%s: %s: %s",
            year_month, type(e).__name__, e,
        )
        return None
    except Exception:  # noqa: BLE001 — top boundary, swallow into cron
        logger.exception("monthly_review unexpected error month=%s", year_month)
        return None

def _fetch_closed_positions_for_month(self, year_month: str) -> list[Position]:
    """SELECT closed positions whose closed_at falls in [month_start, next_month_start), UTC."""
    year, month = (int(x) for x in year_month.split("-"))
    month_start = datetime(year, month, 1, tzinfo=timezone.utc)
    next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)
    next_start = datetime(next_year, next_month, 1, tzinfo=timezone.utc)
    return (
        self._db.query(Position)
        .filter(
            Position.status == "CLOSED",
            Position.closed_at >= month_start,
            Position.closed_at < next_start,
        )
        .order_by(Position.closed_at.asc())
        .limit(100)  # MonthlyReviewPayload.closedTrades max_length=100
        .all()
    )

def _build_monthly_input(self, year_month: str, closed: list[Position]) -> dict:
    return {
        "mode": "monthly",
        "monthly": {
            "month": year_month,
            "closedTrades": [self._brief_for_position(p) for p in closed],
        },
    }

def _brief_for_position(self, position: Position) -> dict:
    risk_per_share = position.entry_price - position.stop_price
    r_multiple = (
        round((position.close_price - position.entry_price) / risk_per_share, 2)
        if risk_per_share > 0
        else 0.0
    )
    closed_on = (position.closed_at or position.updated_at).date().isoformat()
    holding_days = (
        (position.closed_at.date() - position.entry_date).days
        if position.closed_at and position.entry_date
        else 0
    )
    return {
        "ticker": position.ticker,
        "setupType": position.setup_type or None,  # ClosedTradeBrief allows None
        "rMultiple": r_multiple,
        "holdingDays": max(holding_days, 0),
        "closedOn": closed_on,
    }
```

**字段映射来源（journal_assistant.py:74-86 ClosedTradeBrief）**：
- `ticker` ← position.ticker（必填）
- `setupType` ← position.setup_type（可 None；schema 允许）
- `rMultiple` ← `(close - entry) / (entry - stop)`，risk≤0 → 0.0（与 d1 _build_trade_input 同公式 / 同保护）
- `holdingDays` ← `closed_at.date() - entry_date`，缺一 → 0
- `closedOn` ← `closed_at.date().isoformat()`（YYYY-MM-DD）

不动方法：`trade_review_for_position` / `_upsert_sell_journal_entry` / `_build_trade_input` / `__init__` 全部保留 d1 实现。

#### B. `refresh_job.py` 注册 journal monthly cron（第 2 文件，修改）

位置：`backend/app/services/refresh_job.py`

变更：
1. 文件顶部加 import：
   ```python
   from app.services.cockpit.journal_review_service import JournalReviewService
   ```
2. JOB_ID 常量区追加：
   ```python
   JOURNAL_MONTHLY_JOB_ID = "f211_journal_monthly_review"
   ```
3. `start_scheduler` 内追加 add_job（在 `_pool_cache_tick` 注册块之后，`autostart` 检查之前）：
   ```python
   # F211-d2: monthly journal review cron (每月 1 号 06:00 UTC，错开 universe 05:00)
   sched.add_job(
       _journal_monthly_tick,
       trigger=CronTrigger(
           day=settings.journal_monthly_cron_day,
           hour=settings.journal_monthly_cron_hour,
           minute=settings.journal_monthly_cron_minute,
           timezone="UTC",
       ),
       id=JOURNAL_MONTHLY_JOB_ID,
       args=[session_factory],
       replace_existing=True,
   )
   ```
4. 文件底部 tick 区追加：
   ```python
   def _journal_monthly_tick(session_factory: SessionFactory) -> None:
       """APScheduler tick for F211-d2 monthly journal review: 1st of month 06:00 UTC."""
       try:
           year_month = _previous_month_utc(datetime.now(timezone.utc))
           with _session_scope(session_factory) as db:
               JournalReviewService(db).monthly_review_for_month(year_month)
       except Exception:  # noqa: BLE001
           logger.error("journal monthly tick failed\n%s", traceback.format_exc())


   def _previous_month_utc(now: datetime) -> str:
       """Return 'YYYY-MM' for the month preceding `now` (UTC). Pure function for testability."""
       first_of_this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
       last_of_prev = first_of_this_month - timedelta(days=1)
       return f"{last_of_prev.year:04d}-{last_of_prev.month:02d}"
   ```
   `datetime` / `timezone` / `timedelta` 已 import（top of file 现有 `from datetime import datetime, timezone` —— 步骤 1 实测确认 + 必要时补 `timedelta`）。

**只改 refresh_job.py 一个文件**，不改 main.py（main.py 已通过 lifespan 调用 start_scheduler，cron 注册自动生效）。

#### C. `config.py` 追加 cron settings（第 3 文件，修改）

位置：`backend/app/config.py`

追加 3 行（在现有 cron settings 区之后、AI 区之前）：

```python
# F211-d2 journal monthly review cron (1st of month 06:00 UTC, after universe at 05:00)
journal_monthly_cron_day: int = 1
journal_monthly_cron_hour: int = 6
journal_monthly_cron_minute: int = 0
```

`.env.example` 同步追加（不计入 6 文件预算 — 文档/示例配置，与 F211-a2 处理一致）：

```env
# F211-d2 journal monthly review cron (defaults: 1st of month 06:00 UTC)
# JOURNAL_MONTHLY_CRON_DAY=1
# JOURNAL_MONTHLY_CRON_HOUR=6
# JOURNAL_MONTHLY_CRON_MINUTE=0
```

#### D. 测试 `test_journal_review_service_f211d2.py`（第 4 文件，新建）

位置：`backend/tests/test_journal_review_service_f211d2.py`

测试用例（共 14 个，6 单元 + 5 集成 + 3 调度）：

| # | 类型 | 用例 |
|---|---|---|
| U1 | 单元 | `_previous_month_utc(now=2026-04-29 06:00 UTC)` → "2026-03" |
| U2 | 单元 | `_previous_month_utc(now=2026-01-15)` → "2025-12"（跨年） |
| U3 | 单元 | `_previous_month_utc(now=2026-03-01 00:00)` → "2026-02"（边界：1 号当天，应取上个月） |
| U4 | 单元 | `_brief_for_position` 正常字段 → schema `ClosedTradeBrief(**brief)` 不抛；rMultiple 计算正确 |
| U5 | 单元 | `_brief_for_position` setup_type=None → setupType=None，不抛 |
| U6 | 单元 | `_brief_for_position` risk_per_share≤0（防御）→ rMultiple=0.0，不抛 ZeroDivision |
| I1 | 集成 | `_fetch_closed_positions_for_month` 仅返回 closed_at 落在月内的 CLOSED positions（OPEN / 上月 / 下月 全部排除） |
| I2 | 集成 | `monthly_review_for_month` 0 trades → 跳过 gateway，返回 None，log INFO（用 caplog 断言；assert gateway.run **未被调用**） |
| I3 | 集成 | `monthly_review_for_month` 正常路径（gateway mock 成功）→ 返回 memo_id；输入 dict 过 `JournalAssistantInput(**input)` Pydantic 验证 |
| I4 | 集成 | `monthly_review_for_month` 上限 100：构造 105 个 closed positions → 仅取 closed_at 最早 100 条传入 gateway |
| I5 | 集成 | `monthly_review_for_month` 各类 AI 错误（AiProviderError / AiSchemaError / AiGuardrailViolation / AiBudgetExceeded）→ 全部返回 None，log WARN，不抛（参数化 4 子用例） |
| S1 | 调度 | `start_scheduler` 注册 `JOURNAL_MONTHLY_JOB_ID`：trigger.fields day=1 / hour=6 / minute=0 |
| S2 | 调度 | `_journal_monthly_tick` 正常路径：调用 JournalReviewService.monthly_review_for_month，参数为 _previous_month_utc(now) |
| S3 | 调度 | `_journal_monthly_tick` 内部异常被 swallow（与 _earnings_tick S7 同 pattern） |

**测试基础设施**：
- 复用 `tests/conftest.py` 的 `db_session` fixture（用于 I1/I2/I3/I4/I5）
- mock AiGateway：`monkeypatch.setattr("app.services.cockpit.journal_review_service.AiGateway.run", fake_run)`
- `fake_run` 返回 `GatewayResult(output={"mode":"monthly","monthly":{...}}, memo_id=999, ...)`，用 `make_dataclass` 或现有 GatewayResult fixture
- S1/S2/S3 沿用 `test_earnings_f204b.py:103-150` 的 scheduler 注册 + tick 测试 pattern；S2 用 `patch("app.services.refresh_job.JournalReviewService", return_value=mock_service)` 拦截
- I4 用 `freezegun` 或手工构造时间戳；不引入 freezegun（不在依赖列表），用 `datetime.now(timezone.utc).replace(...)` 构造 fixture

#### E. 不计入 6 文件预算的辅助变更

- `docs/需求/features.json`：sub_sprints["F211-d2"]: design_needed → contract_agreed（用户确认后）→ in_progress（Generator 启动后）→ done（Evaluator 通过后）；iteration_history 追加；`_pipeline_status.active_sprint` 由 F211-d1 切换到 F211-d2
- `docs/系统设计/DECISIONS.md`：追加 D077（F211-d2 月度复盘策略）
- `backend/.env.example`：journal_monthly_cron 三行注释示例
- `claude-progress.txt`：contract_agreed + 各开发步骤记录
- `SESSION-HANDOFF.md`：Generator 启动指令

### 1.2 排除（明确不在 d2 内）

- ❌ 月度复盘的前端展示组件（消费 ai_memos 输出）→ 留 v1.10 / 未来 feature
- ❌ 月度复盘的管理 API（手动触发 / 重跑 / 列表）→ 不在 P2 范围
- ❌ 历史月份回填脚本（已闭月反向生成 review）→ 用户可临时通过 Python REPL 调 `JournalReviewService(db).monthly_review_for_month("2026-03")` 触发，不写正式工具
- ❌ 月度复盘结果落 journal_entries（新增 action 类型 / schema 迁移）→ 仅落 ai_memos
- ❌ journal_assistant monthly schema 任何变更 → F211-a1 已锁定
- ❌ 跨年/跨月时区边界全部场景测试 → 仅覆盖 U1/U2/U3 三个代表点；接受余下边界由 _previous_month_utc 纯函数 + datetime 自然语义保证
- ❌ 月度 review budget 单独熔断 → 沿用 D069 月预算；月度复盘单次 call 估 < $0.5（complex tier，~3K tokens 输入 + 1K 输出），不显式预留
- ❌ ai_memos 表结构变更 → 不动
- ❌ 数据库迁移 → 0 alembic revision（保持 017 为 F211 epic 末尾）
- ❌ 多用户隔离 / user_id 过滤 → 当前系统单用户（D070），closed positions 全表扫描

---

## 2. 预计修改文件清单（共 4 个，2 个余量）

| # | 文件 | 操作 | 估行数 |
|---|------|------|--------|
| 1 | `backend/app/services/cockpit/journal_review_service.py` | 修改（追加 monthly 接口）| +75 |
| 2 | `backend/app/services/refresh_job.py` | 修改（+ JOB_ID 常量 + add_job + tick + _previous_month_utc helper + 1 行 import）| +35 |
| 3 | `backend/app/config.py` | 修改（+ 3 行 settings）| +4 |
| 4 | `backend/tests/test_journal_review_service_f211d2.py` | 新建（14 case）| ~350 |

**辅助变更（不计入 6 文件预算）**：
- `backend/.env.example`（3 行注释，与 F211-a2 处理一致）
- `docs/需求/features.json`（status 字段更新）
- `docs/系统设计/DECISIONS.md`（D077）
- `claude-progress.txt` / `SESSION-HANDOFF.md`

---

## 3. 完成标准（可测试）

| # | 标准 | 测试层级 | 工具 |
|---|------|---------|------|
| C1 | U1-U6 全过：`_previous_month_utc` + `_brief_for_position` 行为正确 | 单元 | pytest |
| C2 | I1 全过：`_fetch_closed_positions_for_month` 月份过滤正确（含跨月/跨年/OPEN 排除） | 集成 | pytest + sqlite |
| C3 | I2 全过：0 trades 不打 gateway，返回 None，log INFO | 集成 | pytest + caplog |
| C4 | I3 全过：正常路径返回 memo_id；input 过 `JournalAssistantInput(**input)` Pydantic 验证 | 集成 | pytest |
| C5 | I4 全过：105 closed → 取最早 100 | 集成 | pytest |
| C6 | I5 参数化 4 子用例全过：4 类 AI 错误 → 返回 None，不抛 | 集成 | pytest + monkeypatch |
| C7 | S1 全过：`start_scheduler` 注册 `JOURNAL_MONTHLY_JOB_ID`，trigger day=1/hour=6/minute=0 | 集成 | pytest + APScheduler |
| C8 | S2 全过：`_journal_monthly_tick` 调用 `JournalReviewService.monthly_review_for_month` 一次，参数 = `_previous_month_utc(now)` | 集成 | pytest + patch |
| C9 | S3 全过：tick 内部异常被 swallow | 集成 | pytest + monkeypatch |
| C10 | mypy --strict 0 新增错误（baseline pre-existing 4 项不算） | 静态 | mypy |
| C11 | ruff check 0 新增违例 | 静态 | ruff |
| C12 | 全量后端 pytest ≥ baseline（F211-d1 后 908+ 通过），无 NEW 失败 | 回归 | pytest |
| C13 | trade 路径完全不受影响：`test_journal_review_service_f211d1.py` 15 cases 全部仍通过 | 回归 | pytest |

---

## 4. Evaluator 自检清单

代码：
- [ ] C1-C13 全过
- [ ] `journal_review_service.py` 内 monthly 方法不引入对 `position_service` / `JournalEntry` / `Stock` 的新依赖（monthly 只读 Position；Stock/JournalEntry import 仅 trade 路径用）
- [ ] `_previous_month_utc` 是纯函数（no I/O），可独立单测
- [ ] `_fetch_closed_positions_for_month` 用 timezone-aware `datetime` 比较 `closed_at`（Position.closed_at 是 DateTime(timezone=True)）
- [ ] `_brief_for_position` 输出过 `ClosedTradeBrief(**dict)` Pydantic 验证（在 U4 中 assert）
- [ ] `monthly_review_for_month` 整体输出过 `JournalAssistantInput(**input)` Pydantic 验证（在 I3 中 assert）
- [ ] tick 顶层 `try/except Exception` 完备（与 _earnings_tick / _scanner_tick / _setup_tick 一致）
- [ ] cron trigger 用 `CronTrigger(day=..., hour=..., minute=...)`（不用 `from_crontab`，因 universe_cron 也是这种 pattern，统一）
- [ ] `JOURNAL_MONTHLY_JOB_ID` 字符串与现有 7 个 JOB_ID 命名风格一致
- [ ] settings 字段名 snake_case + cron_day/hour/minute 后缀，与 universe_cron_day 一致
- [ ] 不动 `trade_review_for_position` / `_upsert_sell_journal_entry` / `_build_trade_input` 任一行（diff 应仅在类内追加方法 + 顶部 import）

数据：
- [ ] `_fetch_closed_positions_for_month` 不会跨月泄漏：closed_at >= 月初 AND < 下月初（< 严格小于，不用 ≤）
- [ ] `limit(100)` 使用 ORDER BY closed_at ASC（最早 100 条；如超限，最近的会丢；可接受 — 月度复盘对早期更有归因价值）
- [ ] ai_memos 写入由 AiGateway 自动负责，本 sprint 0 行手工 INSERT

文档：
- [ ] DECISIONS.md D077 已追加
- [ ] features.json sub_sprints["F211-d2"]: done + iteration_history 追加 contract_agreed / done 两条
- [ ] **C1 invariant**：F211-d2 升 done 后，所有 sub_sprints (a1/a2/b/c/d1/d2) 均 done → 父 F211 status 升 done（在 acceptance 完成后）；本 sprint Evaluator 完成时父保持 in_progress 直至 acceptance
- [ ] `.env.example` journal_monthly_cron 注释三行
- [ ] claude-progress.txt 追加 F211-d2 各步骤
- [ ] SESSION-HANDOFF.md 更新

回归（不可跳过）：
- [ ] 全量后端 pytest 跑一遍，对比 F211-d1 验收基线（908+ pass）
- [ ] 失败计数 ≤ 基线，否则打回 Generator
- [ ] consistency-check (mode=interactive) C5 通过：sub_sprints["F211-d2"] entry ↔ 合约文件存在
- [ ] consistency-check C1 invariant：F211 父 feature status 由 consistency-check 自动决定，**不得**人为升 done

---

## 5. 开发顺序（Generator 模式）

> ⚠️ 不得跳步、不得颠倒。每完成一步，wip commit + claude-progress.txt 追加。**禁用 `git add -A`**，按文件名显式 add。

**步骤 1：预检（不写实现）**
- 跑 `cd backend && alembic current` 确认头是 017（d1 落地，无需新迁移）
- 读 `backend/app/services/refresh_job.py` 确认 `from datetime import ...` 已含 `timedelta`（若无补 import）
- 读 `backend/app/services/refresh_job.py` 确认 `_session_scope` / `SessionFactory` 类型别名
- 读 `backend/app/ai/gateway.py::GatewayResult` 复核 `result.memo_id: int`
- 读 `backend/tests/test_earnings_f204b.py:103-150` 复用 scheduler 注册 + swallow exception pattern
- 读 `backend/tests/conftest.py` 确认 `db_session` fixture 可用
- 读 `backend/app/models/position.py` 确认 `closed_at` 是 `DateTime(timezone=True)` / `entry_date` 字段类型

→ 不 commit（预检不改文件）

**步骤 2：config.py + .env.example（第 3 文件）**
- 加 3 行 settings
- `.env.example` 同步注释
- 跑 `python -c "from app.config import settings; print(settings.journal_monthly_cron_day)"` 验证

→ wip commit：`wip(F211-d2): config + env journal monthly cron settings`

**步骤 3：journal_review_service monthly 接口（第 1 文件）**
- 在 `journal_review_service.py` 类内追加 `monthly_review_for_month` / `_fetch_closed_positions_for_month` / `_build_monthly_input` / `_brief_for_position`
- 顶部加必要 import (`datetime / timezone / timedelta`)
- 同步写 U4-U6 + I1-I5（可能跨步骤但建议同 commit；如分两次提交也允许）
- 跑 U4-U6 + I1-I5 → 应通过

→ wip commit：`wip(F211-d2): JournalReviewService monthly mode + 9 tests`

**步骤 4：refresh_job 注册 cron + tick（第 2 文件）**
- 顶部加 `from app.services.cockpit.journal_review_service import JournalReviewService`
- 加 `JOURNAL_MONTHLY_JOB_ID` 常量
- `start_scheduler` 内追加 `sched.add_job(_journal_monthly_tick, ...)`
- 文件底部加 `_journal_monthly_tick` + `_previous_month_utc`
- 写 U1-U3（_previous_month_utc 单测）+ S1-S3
- 跑 U1-U3 + S1-S3 → 应通过

→ wip commit：`wip(F211-d2): refresh_job journal monthly cron + 6 tests`

**步骤 5：回归 + 静态检查**
- 跑全量 `pytest backend/tests/` → 对比基线 908+
- 跑 `mypy backend/app` / `ruff check backend/app` → 0 新增违例
- 跑 `pytest --collect-only -q backend/tests/test_journal_review_service_f211d2.py | tail -5` → 应 ≥ 14
- 检查 d1 tests `pytest backend/tests/test_journal_review_service_f211d1.py` → 应 15/15 全过

**步骤 6：文档收尾**
- DECISIONS.md 追加 D077
- features.json `sub_sprints["F211-d2"]: in_progress` → `done`（Evaluator 通过后才升）
- features.json iteration_history 追加 done 记录
- claude-progress.txt 追加完成记录

**步骤 7：最终 commit**
- 默认保留 wip commit 细粒度（feature-dev 规则 7）
- Evaluator 自检全过后：
  ```bash
  git add backend/app/services/cockpit/journal_review_service.py \
          backend/app/services/refresh_job.py \
          backend/app/config.py \
          backend/.env.example \
          backend/tests/test_journal_review_service_f211d2.py \
          docs/需求/features.json \
          docs/系统设计/DECISIONS.md \
          claude-progress.txt
  git commit -m "feat(F211-d2): monthly journal review cron"
  ```
- 触发 consistency-check (mode=interactive)：
  - C1 invariant：F211 所有 6 个 sub_sprints 升 done 后，父 status 升 done（acceptance 完成时）；本步骤通过即可，不强制升父
  - C4：iteration_history 已含 F211-d2 done 记录
  - C5：sub_sprints["F211-d2"] ↔ F211-d2-contract.md 双向一致

---

## 6. 开放问题（用户协商时拍板，未列项即采默认）

| # | 问题 | 默认方案 | 备选 |
|---|------|---------|------|
| Q1 | 月度复盘输出存储位置 | 仅 ai_memos（依赖 D069 + 24h dedup） | 新表 monthly_reviews（+1 张表 +迁移）/ journal_entries 加 action='MONTHLY_REVIEW' （+迁移） |
| Q2 | cron 时间 | 1 号 06:00 UTC（universe 05:00 之后 1h） | 1 号 04:00 UTC（universe 之前）/ 2 号触发（避开月初 API 拥堵）|
| Q3 | 0 trades 月份处理 | 跳过 gateway，log INFO，return None | 仍调用 gateway（违反 schema min_length=1） / 抛异常 |
| Q4 | year_month 推导 | `_previous_month_utc(datetime.now(timezone.utc))`（cron 在 1 号触发，今天-1 天=上月最末日，截 YYYY-MM）| 当前月（错误，会取本月）/ 显式参数注入 |
| Q5 | 重入 / 幂等控制 | 依赖 gateway memo dedup（input_hash + 24h TTL）+ schema_version=v1 | 数据库标记位（新表/列） / Redis lock |
| Q6 | 失败重试 | 不重试（与现有所有 cron tick 一致）；下月再来 | tenacity 退避 / APScheduler reschedule |
| Q7 | budget 超限时是否优先保 monthly | 不特殊处理（沿用 D069 月预算先到先得） | 月初保留 $X 给 monthly review |
| Q8 | 月度复盘是否含 OPEN positions（mid-month 状态） | ❌ 仅 closed_at 落在月内的 CLOSED | 含未平仓的 mid-month snapshot（需 schema 扩展） |
| Q9 | rMultiple 公式与 d1 是否完全一致 | ✅ 沿用 `(close - entry)/(entry - stop)`，risk≤0 → 0.0 | 重新定义（造成两套指标） |
| Q10 | closedTrades 超 100 的截取策略 | ORDER BY closed_at ASC 取最早 100 | DESC 取最近 100（早期更具归因价值，故 ASC）|
| Q11 | scheduler 注册测试是否单独文件 | 合并到 `test_journal_review_service_f211d2.py` | 抽 `test_refresh_job_f211d2.py`（+1 文件超预算） |
| Q12 | 是否提供管理 endpoint 手动触发 | ❌ 仅 cron 触发；用户通过 REPL `JournalReviewService(db).monthly_review_for_month("YYYY-MM")` | POST /api/cockpit/journal/monthly_review（需鉴权 + API-CONTRACT 更新）|
| Q13 | 是否前端展示入口 | ❌ 0 前端代码；消费方式留 v1.10 | 加 ManagerPanel 月度卡片（+ ≥3 文件超预算）|
| Q14 | journal_assistant monthly tier 是否调整 | ❌ 沿用 a1 / a2 配置（complex tier，可 .env override） | 单独切 default tier 节省成本 |
| Q15 | 是否在 main.py / lifespan 添加首次启动调用 | ❌ 仅 cron 触发；启动不补打 | 启动时检查"上月是否已 review"，未 review 则补打 |

---

## 7. 风险与回避

1. **APScheduler 调度漂移**：worker 在 1 号 06:00 时刻不在线 → 错过本月 cron。**接受**：APScheduler `misfire_grace_time` 默认 1s，超过即跳；下月再来。如严格需要可在未来加 `coalesce=True` + `misfire_grace_time=3600`，**本 sprint 不做**（与现有 7 个 cron 行为一致）。
2. **session 跨线程泄漏**：tick 用 `_session_scope` finally close；与 d1 _trade_review_background 同 pattern；S2/S3 不显式断言但 db_session fixture 末尾会自检。
3. **gateway budget 超限**：AiBudgetExceeded 在 monthly tick 中静默 → SystemLog WARN（v1.0 已实现）。下月新预算窗口自然恢复。
4. **schema_version 不变**：`journal_assistant` v1，不会触发 D069 ai_memos cache invalidate；如 a1 schema 后续升级，v1→v2 会自然失效旧 monthly memo（无需本 sprint 处理）。
5. **closedTrades 100 上限**：单月 >100 closed 极不可能（D070 单用户场景）；ASC 截取可保证早期归因；触发上限会丢失最近 trades，但 monthly review 仍生成（不抛）。
6. **0 trades 月份不写 ai_memos → 无审计痕迹**：用户无法通过 ai_memos 反推"我这月没交易"。**接受**：log INFO 留痕足矣；如未来需要可加 SystemLog（v1.10）。
7. **tick 调用时存在尚未平仓的 OPEN position**：被 _fetch_closed_positions_for_month 自然过滤（status != 'CLOSED'），不会误入 monthly。
8. **datetime now() 在 tick 内被冻结风险（pytest）**：S2 测试用 `patch("app.services.refresh_job.datetime")` 注入固定时间，避免依赖真实时钟。

---

## 8. F211 收尾约定

本 sprint 完成后：
- F211 父 feature 6 个 sub_sprints 全部 done（a1/a2/b/c/d1/d2）
- 父 status 由 acceptance skill 决定升 done（依赖 C1 invariant）
- 进入 acceptance 阶段：对照 features.json acceptance_criteria 6 条逐一勾选（前 5 条已由 a1-d1 兑现，第 6 条由 d2 兑现）
- F211-e（前端展示 / 管理 endpoint）若用户需要可立项，但**不在 F211 父 feature 范围内**，需 project-init 迭代模式新增

---

## 9. 用户确认

请回复：

A. **接受合约 + 默认方案**（推荐）
B. 修改某条 Q（指出 Q# 与改动方向）
C. 重新拆分 / 调整范围（如希望含 Q12 管理 endpoint → 本 sprint 文件超预算，需重新规划）

确认后执行：
1. `features.json` 更新 sub_sprints["F211-d2"]: contract_agreed + iteration_history 追加 + `_pipeline_status.active_sprint` = "F211-d2"
2. `claude-progress.txt` 追加 contract_agreed 记录
3. 调用 consistency-check skill (mode=interactive) 验证 sub_sprints ↔ 合约目录一致
4. 生成 SESSION-HANDOFF.md
5. **强制停止**，开新 session 用 Sonnet 进入 Generator 模式从步骤 1 开始
