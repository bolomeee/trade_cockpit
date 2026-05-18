---
status: confirmed
drafted_at: 2026-05-18
confirmed_at: 2026-05-18
sprint: F218-d1
parent_feature: F218
---

# F218-d1 Sprint Contract — Framework: model + alembic 022 + repository + service skeleton

> 生成：2026-05-18 | 状态：草案 → 待用户确认
> Feature：[F218](docs/需求/features.json) Cockpit Phase D — Repricing Trigger 完整框架（5 类）
> Sub-sprint：F218-d1（Phase D 10 sub-sprint 第 1 个，框架层）
> 前置：F215/F216/F217 全部 done；F218 system-design 变更协议完成（4 文档 confirmed @ 2026-05-18）
> 下游：F218-d2/d4/d5/d3a/d6a（全部依赖本 sub-sprint 的 service skeleton + repository + 表）

> 引用文档：
> - [DATA-MODEL.md](docs/系统设计/DATA-MODEL.md) §RepricingTrigger — 字段表 + evidence_json schema + soft expire 模型 + UQ ticker+trigger_type+detected_date
> - [DECISIONS.md](docs/系统设计/DECISIONS.md) §D096 — 5 类框架 + evidence_json 单列设计（vs 5 张子表 / 定长字段 / 并发 detector / 硬删过期全部放弃）
> - [ARCHITECTURE.md](docs/系统设计/ARCHITECTURE.md) §Cockpit Repricing Trigger Service — 模块位置 + 5 detector 串行调度 + cron 22:40 UTC + 模块 import 边界
> - [F216-b-contract.md](docs/开发/sprint-contracts/F216-b-contract.md) — 同形态 sub-sprint（新表 + repo + service skeleton）参考样式

---

## 0. 背景与定位

F218 Phase D 第 1 步 — **只搭框架，不实现任何 detector 逻辑**。本 sub-sprint 提供后续 d2/d3b/d4/d5/d6b 五个 detector sub-sprint 的"插槽"：service skeleton 暴露 5 个 `_detect_*` 占位方法（返回 `None`，不命中），主入口 `compute_and_store_all_triggers(date)` 已完整实现串行调度 + soft expire + upsert 持久化逻辑。

**为什么 d1 不动 API/前端**：
- 路由 + cron 留给 F218-d7a（独立 sub-sprint，service 全部 detector 实装后再上线）
- 前端留给 F218-d7b
- 本 sub-sprint 只交付**持久化层 + 服务调度骨架**，保证 d2 开始就能往里塞 detector 实现

**为什么 d1 不需要 detector 的真实数据**：
- service skeleton 内 5 个 `_detect_*` 占位方法返回 `None`，`compute_and_store_all_triggers` 调用后无新行写入是预期行为（测试也按此断言）
- soft expire 逻辑可独立测试：手动 fixture 注入 `active=true` 行 + 当日 detector 返回 None → 行 `active` 应翻 false

---

## 1. 实现范围

**包含**：

### 1.1 ORM Model
**新文件** `backend/app/models/repricing_trigger.py`：

```python
"""F218-d1: RepricingTrigger ORM model — cockpit Phase D 5-class repricing signal per ticker."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, Date, DateTime, Float, Integer, String, Text, UniqueConstraint,
)

from app.models import Base


class RepricingTrigger(Base):
    __tablename__ = "repricing_triggers"
    __table_args__ = (
        UniqueConstraint(
            "ticker", "trigger_type", "detected_date",
            name="uq_repricing_trigger_ticker_type_date",
        ),
    )

    id            = Column(Integer, primary_key=True, autoincrement=True)
    ticker        = Column(String(10), nullable=False, index=True)
    trigger_type  = Column(String(24), nullable=False)
    detected_date = Column(Date, nullable=False, index=True)
    confidence    = Column(Float, nullable=False, default=0.5)
    evidence_json = Column(Text, nullable=False)
    active        = Column(Boolean, nullable=False, default=True, index=True)
    computed_at   = Column(
        DateTime, nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
```

### 1.2 Model Registration
**修改** `backend/app/models/__init__.py`：在 `CockpitPoolCache` import 后追加 1 行：

```python
from app.models.repricing_trigger import RepricingTrigger  # noqa: E402
```

### 1.3 Alembic Migration
**新文件** `backend/alembic/versions/022_f218_repricing_triggers.py`：
- `revision = "022_f218_repricing_triggers"`，`down_revision = "021_f217b1_setup_snapshots_legacy"`
- `upgrade()`：创建 `repricing_triggers` 表，含：
  - 5 字段独立 column
  - `uq_repricing_trigger_ticker_type_date` 唯一约束
  - `ix_repricing_triggers_ticker`、`ix_repricing_triggers_detected_date`、`ix_repricing_triggers_active` 三个独立索引
- `downgrade()`：drop 三索引 + drop table

### 1.4 Repository
**新文件** `backend/app/repositories/repricing_trigger_repository.py`：

```python
class RepricingTriggerRepository:
    def __init__(self, db: Session) -> None: ...

    # ── Write ──
    def upsert(self, data: dict) -> RepricingTrigger:
        """INSERT OR UPDATE by (ticker, trigger_type, detected_date) UQ.
        覆盖 confidence / evidence_json / active / computed_at；ticker/trigger_type/detected_date 不变。
        """

    def soft_expire(self, ticker: str, trigger_type: str, current_date: date) -> int:
        """Mark all active=true rows for (ticker, trigger_type) where detected_date < current_date as inactive.
        Returns count of rows updated. 用于 detector re-scan 未命中时的软过期。
        """

    # ── Read ──
    def get_active_for_ticker(self, ticker: str) -> list[RepricingTrigger]:
        """All active=true triggers for a ticker, ordered by detected_date DESC."""

    def get_all_active(
        self,
        trigger_type: str | None = None,
        limit: int = 100,
    ) -> tuple[list[RepricingTrigger], int]:
        """All active=true triggers market-wide, ordered by detected_date DESC then confidence DESC.
        Returns (rows, total_count) — total_count ignores limit (for widget '显示 N / 总 M').
        """

    # ── Retention（F218 ARCHITECTURE: REPRICING_TRIGGER_RETENTION_DAYS=365 在 active=false 行上硬删）──
    def delete_expired_inactive(self, cutoff: date) -> int:
        """Hard-delete active=false rows with detected_date < cutoff. active=true rows are never deleted by this method.
        Returns count deleted.
        """
```

### 1.5 Service Skeleton
**新文件** `backend/app/services/cockpit/repricing_trigger_service.py`：

```python
"""F218-d1: RepricingTriggerService skeleton — 5-class串行 detector 调度 + soft expire.

5 个 detector 的真实实装由后续 sub-sprint 完成：
  - F218-d2 → _detect_earnings_acceleration（T1）
  - F218-d3b → _detect_margin_expansion（T2）
  - F218-d4 → _detect_new_product（T3 D4a）
  - F218-d5 → _detect_sector_cycle（T4）
  - F218-d6b → _detect_balance_inflection（T5）

本 sub-sprint 5 个 _detect_* 均返回 None（不命中），主入口仍可端到端跑通：
  - 既有 active 行 + 当日未命中 → soft expire 翻 false
  - 无既有行 + 不命中 → 无副作用
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.repositories.repricing_trigger_repository import RepricingTriggerRepository
from app.repositories.stock_repository import StockRepository

logger = logging.getLogger(__name__)

# 5 类 trigger_type 枚举常量（与 DATA-MODEL.md §RepricingTrigger 对齐）
TRIGGER_TYPES = (
    "EARNINGS_ACCEL",
    "MARGIN_EXPANSION",
    "NEW_PRODUCT",
    "SECTOR_CYCLE",
    "BALANCE_INFLECTION",
)


@dataclass
class DetectorResult:
    """detector 返回类型。命中 → 实例；未命中 → None。"""
    confidence: float          # 0.0-1.0
    evidence: dict[str, Any]   # 按 trigger_type 区分 schema（DATA-MODEL.md §RepricingTrigger evidence_json schema）


class RepricingTriggerService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self._repo = RepricingTriggerRepository(db)
        self._stocks = StockRepository(db)

    # ── Public ───────────────────────────────────────────────────────────────
    def compute_and_store_all_triggers(self, scan_date: date | None = None) -> dict[str, int]:
        """主入口：遍历 active stocks，对每个 ticker 串行跑 5 detector，写入 / soft expire。

        Returns: {trigger_type: hit_count} 用于日志/监控（含 0 命中类型）。
        """
        scan_date = scan_date or datetime.now(timezone.utc).date()
        active_tickers = self._stocks.get_active_tickers()  # 复用既有方法
        hit_counts = {t: 0 for t in TRIGGER_TYPES}

        for ticker in active_tickers:
            for trigger_type, detector_fn in self._detector_map().items():
                try:
                    result = detector_fn(ticker, scan_date)
                except Exception:  # noqa: BLE001
                    logger.exception(
                        "repricing detector failed: ticker=%s type=%s", ticker, trigger_type,
                    )
                    continue

                if result is None:
                    # 未命中 → soft expire 既有 active 行（如有）
                    self._repo.soft_expire(ticker, trigger_type, scan_date)
                    continue

                # 命中 → upsert
                self._repo.upsert({
                    "ticker": ticker,
                    "trigger_type": trigger_type,
                    "detected_date": scan_date,
                    "confidence": result.confidence,
                    "evidence_json": json.dumps(result.evidence),
                    "active": True,
                    "computed_at": datetime.now(timezone.utc),
                })
                hit_counts[trigger_type] += 1

        logger.info("repricing triggers computed: date=%s counts=%s", scan_date, hit_counts)
        return hit_counts

    # ── Detector 占位 ──（d2-d6b 各自实装一个）─────────────────────────
    def _detect_earnings_acceleration(
        self, ticker: str, scan_date: date,
    ) -> DetectorResult | None:
        """T1 — F218-d2 实装。当前返回 None（不命中）。"""
        return None

    def _detect_margin_expansion(
        self, ticker: str, scan_date: date,
    ) -> DetectorResult | None:
        """T2 — F218-d3b 实装。当前返回 None。"""
        return None

    def _detect_new_product(
        self, ticker: str, scan_date: date,
    ) -> DetectorResult | None:
        """T3 D4a — F218-d4 实装。当前返回 None。"""
        return None

    def _detect_sector_cycle(
        self, ticker: str, scan_date: date,
    ) -> DetectorResult | None:
        """T4 — F218-d5 实装。当前返回 None。"""
        return None

    def _detect_balance_inflection(
        self, ticker: str, scan_date: date,
    ) -> DetectorResult | None:
        """T5 — F218-d6b 实装。当前返回 None。"""
        return None

    # ── Internal ─────────────────────────────────────────────────────────
    def _detector_map(self) -> dict[str, Any]:
        """trigger_type → detector function. 调度顺序与 TRIGGER_TYPES 一致。"""
        return {
            "EARNINGS_ACCEL":    self._detect_earnings_acceleration,
            "MARGIN_EXPANSION":  self._detect_margin_expansion,
            "NEW_PRODUCT":       self._detect_new_product,
            "SECTOR_CYCLE":      self._detect_sector_cycle,
            "BALANCE_INFLECTION": self._detect_balance_inflection,
        }
```

### 1.6 Tests（合并 repo + service skeleton）
**新文件** `backend/tests/test_repricing_trigger_skeleton.py`：

涵盖以下断言（按 §3 测试用例表展开），合并 repository unit + service skeleton integration，便于单文件本 sprint 自包含。

---

## 2. 预计修改文件

| # | 文件路径 | 改动类型 | 说明 |
|---|---------|---------|------|
| 1 | `backend/app/models/repricing_trigger.py` | 新增 | ORM model + UQ + 3 索引 |
| 2 | `backend/app/models/__init__.py` | 修改 | +1 行 import |
| 3 | `backend/alembic/versions/022_f218_repricing_triggers.py` | 新增 | 表创建 + UQ + 3 索引 / downgrade |
| 4 | `backend/app/repositories/repricing_trigger_repository.py` | 新增 | upsert / soft_expire / get_active_for_ticker / get_all_active / delete_expired_inactive |
| 5 | `backend/app/services/cockpit/repricing_trigger_service.py` | 新增 | skeleton：5 占位 detector + compute_and_store_all_triggers + soft expire + upsert 调度 |
| 6 | `backend/tests/test_repricing_trigger_skeleton.py` | 新增 | repo CRUD + service skeleton 端到端（5 detector 全 None 跑通 + soft expire） |

**合计 6 文件**，命中 6 文件原则上限。✅

---

## 3. 可测试的完成标准

| # | 标准描述 | 测试层级 | 工具 |
|---|---------|---------|------|
| 1 | `RepricingTriggerRepository.upsert()` 首次插入 → 返回新行，DB 内 active=true / confidence/evidence_json 正确 | 单元 | pytest（SQLite in-memory fixture） |
| 2 | `.upsert()` 二次同 (ticker, trigger_type, detected_date) → 不创建新行，覆盖 confidence/evidence_json/active/computed_at；id 不变 | 单元 | pytest |
| 3 | `.soft_expire(ticker, trigger_type, current_date)` → 既有 detected_date < current_date 的 active=true 行翻 false；不动 active=false 历史行；返回更新行数 | 单元 | pytest |
| 4 | `.get_active_for_ticker(ticker)` → 仅返回该 ticker active=true 行，按 detected_date DESC；无命中返回空 list（不抛 404） | 单元 | pytest |
| 5 | `.get_all_active(trigger_type=None, limit=100)` → 全表 active=true，按 detected_date DESC、confidence DESC；返回 (rows, total_count)，total_count 忽略 limit | 单元 | pytest |
| 6 | `.get_all_active(trigger_type="MARGIN_EXPANSION")` → 仅返回该类型 active 行 | 单元 | pytest |
| 7 | `.delete_expired_inactive(cutoff)` → 仅删 active=false 且 detected_date < cutoff 行；active=true 行不动；返回删除数 | 单元 | pytest |
| 8 | UQ 违反 (ticker+trigger_type+detected_date) 时 `upsert()` 走 ON CONFLICT 分支不抛错（验证 SQLite insert.on_conflict_do_update 正确） | 单元 | pytest |
| 9 | `RepricingTriggerService.compute_and_store_all_triggers()` 5 detector 全返回 None + 无既有 active 行 → 返回 `{type: 0}`，DB 无新行 | 集成 | pytest（fixture 注入 active_tickers）|
| 10 | `.compute_and_store_all_triggers()` 5 detector 全返回 None + 注入既有 active 行 → 既有行翻 active=false（验证 soft expire 自动触发） | 集成 | pytest |
| 11 | `.compute_and_store_all_triggers()` 某 detector 抛异常 → 单 ticker 单 type 失败被 logger.exception 捕获，其他 ticker / 其他 type 继续跑（验证错误隔离） | 集成 | pytest + monkeypatch 注入抛错 detector |
| 12 | `DetectorResult` dataclass 字段（confidence: float, evidence: dict）正确序列化为 evidence_json（`json.dumps`） | 单元 | pytest |
| 13 | alembic upgrade → 表/UQ/3 索引存在；downgrade → 全部清理；与既有 021 顺序无冲突 | 集成 | pytest + sqlite fixture（沿用 conftest.py 既有 alembic fixture）|
| 14 | `TRIGGER_TYPES` 常量与 DATA-MODEL.md §RepricingTrigger 枚举 5 选 1 字面一致（EARNINGS_ACCEL/MARGIN_EXPANSION/NEW_PRODUCT/SECTOR_CYCLE/BALANCE_INFLECTION） | 单元 | pytest（直接 assert 元组内容） |

预期测试数：**14 个**（合并到单文件 `test_repricing_trigger_skeleton.py`，按 Repo / Service / Migration / Constants 4 个 class 分组）。

---

## 4. Evaluator 自检清单

开发完成后 Evaluator 模式逐条检查：

- [ ] 14 个测试全部通过（`cd backend && uv run pytest tests/test_repricing_trigger_skeleton.py -v`）
- [ ] 全量后端回归通过（`cd backend && uv run pytest`），无新增失败
- [ ] alembic 022 在新建 DB 上 upgrade/downgrade 双向跑通（既有 conftest fixture 验证）
- [ ] `RepricingTrigger` model 字段与 [DATA-MODEL.md §RepricingTrigger](docs/系统设计/DATA-MODEL.md) 字段表一致（snake_case 命名、类型、nullable、default、UQ name 完全对齐）
- [ ] `TRIGGER_TYPES` 5 元组与 [DATA-MODEL.md §RepricingTrigger](docs/系统设计/DATA-MODEL.md) trigger_type 枚举字面一致
- [ ] service skeleton 5 个 `_detect_*` 方法签名 `(self, ticker: str, scan_date: date) -> DetectorResult | None` 一致（d2-d6b 后续直接 override 不改签名）
- [ ] `compute_and_store_all_triggers` 调度顺序与 [ARCHITECTURE.md §Cockpit Repricing Trigger Service](docs/系统设计/ARCHITECTURE.md) 5 detector 串行顺序一致
- [ ] soft expire 边界正确：仅翻 `detected_date < current_date` 的 active=true 行（不动当日新行、不动历史 active=false）
- [ ] 错误隔离：单 detector 异常被 logger.exception 捕获，不中断 ticker × detector_type 笛卡尔积循环
- [ ] 无 `print()` / `console.error` 遗留；所有日志走 `logger.info` / `logger.exception`
- [ ] `repricing_trigger_service.py` import 边界符合 [ARCHITECTURE.md §Cockpit Repricing Trigger Service](docs/系统设计/ARCHITECTURE.md) 模块边界（本 sprint 只 import `RepricingTriggerRepository` + `StockRepository`，不 import journal_service / watchlist_service / signal_engine 等）

### 代码质量检查
- [ ] 无死代码 / 注释掉的代码块
- [ ] 无硬编码魔法值（5 trigger_type 已抽 `TRIGGER_TYPES` 常量）
- [ ] 函数长度 ≤ 50 行（`compute_and_store_all_triggers` 主循环预计 ~30 行，符合）
- [ ] 错误处理完整：detector 异常用 `logger.exception` + `continue`（不吞错且不中断）

### 回归测试
- [ ] 后端全量 `uv run pytest` 通过
- [ ] 既有 cockpit 服务（regime/setup/weekly_stage/pool_cache）未受 model `__init__.py` 改动影响

---

## 5. 关键设计决策（执行前确认）

| # | 议题 | 推荐方案 | 备选方案 |
|---|------|---------|---------|
| **NP-d1-1** | `soft_expire` 触发时机 | **detector 内调度**（service 主循环里 detector 返回 None 立即 soft_expire） | 独立 cron tick 每日凌晨扫描翻 active=false |
| **NP-d1-2** | `DetectorResult` 类型放置位置 | **service 文件顶部 dataclass**（与 service skeleton 同模块） | 独立 `schemas/repricing_trigger.py` 文件 |
| **NP-d1-3** | 5 `_detect_*` 占位实现 | **全部 `return None`**（不命中，端到端跑通） | 抛 `NotImplementedError`（强制每个 sub-sprint 替换） |
| **NP-d1-4** | 测试文件粒度 | **合并 1 文件**（repo + service skeleton + migration + 常量，14 测试按 class 分组） | 拆 3 文件（test_repricing_trigger_repository / test_repricing_trigger_service_skeleton / test_repricing_trigger_migration） |
| **NP-d1-5** | service 内 active tickers 来源 | **`StockRepository.get_active_tickers()`**（复用 setup_service / weekly_stage_service 同源） | 限定 cockpit pool 内 ticker（PoolCacheService） |

### 推荐理由速览

- **NP-d1-1 推荐 detector 内调度**：soft expire 与 detection 强耦合（同一 ticker × type 同一 scan_date 决策），同循环原子，无需新 cron 调度复杂度。备选方案 = 多 cron 调度，运维负担高。
- **NP-d1-2 推荐 service 模块内**：`DetectorResult` 是 service 内部约定，不暴露给 router / API（router 直接读 ORM model）。独立 schemas 文件适用于 Pydantic 出 API 的场景，本 dataclass 不出 service。
- **NP-d1-3 推荐 `return None`**：d2-d6b 启动时只需 override 方法体，签名不变；CI 全绿（不会因 `NotImplementedError` 中断 service 端到端测试）；soft expire 逻辑在 d1 就能完整测试。
- **NP-d1-4 推荐合并 1 文件**：F216-b 同形态参考；14 测试单文件可读性好，便于一次性看完 framework 行为；class 分组提供逻辑边界。
- **NP-d1-5 推荐 active tickers**：与 setup_service / weekly_stage_service 一致，避免 d1 引入"trigger 适用范围 = 全 active vs cockpit pool"的二选一决策（这是 sizing 问题，留给 d3a/d6a sprint 时若发现 FMP quota 紧张再优化）。

---

## 6. 不在范围（本 sprint 排除）

- ❌ 5 个 detector 的真实业务逻辑（d2/d3b/d4/d5/d6b 各负责一个）
- ❌ FMP key-metrics-ttm / ratios / balance-sheet / cash-flow 接入（d3a/d6a）
- ❌ pool_cache_service.py 改动（d3a/d6a）
- ❌ stock_key_metrics_quarterly / stock_fundamentals_quarterly 两表（d3a/d6a）
- ❌ refresh_job.py cron 注册（d7a — 因为 d1 service skeleton 全 None 即使 cron 跑也无副作用，不必先注册）
- ❌ router + 2 endpoint（d7a）
- ❌ 前端任何文件（d7b）
- ❌ design-spec.md / tokens.json / data-mapping.md / component-plan.md（d7b）
- ❌ DECISIONS.md 追加（本 sprint 无新决策，d1 全部决策已在 system-design 阶段 D096/D097/D098 落地；NP-d1-1~5 是实施级别决策由本 contract 承载，不需要 D099+）

---

## 7. 用户待确认

1. **NP-d1-1/2/3/4/5** 五项决策：全部按推荐？还是有需要调整的？
2. **Contract 整体是否同意进入 Generator 模式开发**？

确认后我会：
1. 更新 features.json：F218-d1 phase 改 `contract_agreed`；F218 父 phase 由 `design_needed` 改 `in_progress`；`_pipeline_status.active_sprint` 填 `F218-d1`
2. 追加 F218 iteration_history 一条 contract_agreed 记录（subtask=F218-d1）
3. 更新 claude-progress.txt
4. 生成 SESSION-HANDOFF.md（含 d1 6 步开发顺序 + 恢复指令）
5. **强制停止本 session**（feature-dev skill 铁律），输出 Sonnet 新 session 恢复指令
