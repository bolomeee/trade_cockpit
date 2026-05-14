# Sprint Contract：F105-a1 数据层脚手架（Market Breakout Scanner）

> 日期：2026-04-20 | 状态：草案
> 引用文档：
>   DATA-MODEL.md#MarketScanUniverse · DATA-MODEL.md#MarketBreakoutScan · DATA-MODEL.md#orm-schema
>   DECISIONS.md#D038 · DECISIONS.md#D040
>   ARCHITECTURE.md#外部数据源-fmp-stable-端点映射（仅作为下游 a2/a3 引用，本 Sprint 不涉及外部调用）

---

## 本次实现范围

**包含**：
- 新增 `market_scan_universe` / `market_breakout_scans` 两张表的 ORM 定义（SQLAlchemy 2.0，字段严格对照 DATA-MODEL.md L230–288 / L423–449）
- `models/__init__.py` 追加两个新 model 的 export（trivial）
- Alembic 迁移脚本 `002_f105_market_scan_tables.py`：create 两表 + 索引（`market_scan_universe.ticker` unique；`market_breakout_scans (scan_date, ticker)` unique + `scan_date`/`scanned_at` 普通索引）
- `MarketScanUniverseRepository`：
  - `upsert_many(rows)`：按 `ticker` upsert，已存在更新 `company_name/exchange/market_cap/last_seen_at`；新行 `added_at=now()`
  - `list_active(since: datetime)`：返回 `last_seen_at >= since` 的全部行，按 `ticker` 排序
  - `latest_refresh_time() -> datetime | None`：`MAX(last_seen_at)`
  - `count() -> int`：冷启动判空用
- `MarketBreakoutRepository`：
  - `replace_scan(scan_date, scanned_at, rows)`：**单事务**内 `DELETE FROM market_breakout_scans` → `INSERT ALL`（rows 为空也要合法：清空旧快照但仍记录？按 D040"成功获取所有扫描结果后才执行" — 本 Sprint 只实现方法；调用方决定是否调用）。方法内部使用 `session.begin_nested()` / `async with session.begin()`，异常回滚不得留空表
  - `get_latest_snapshot() -> (scan_date, scanned_at, items) | None`：读最新快照（按 `scanned_at DESC` 取 1 个 scan_date 分组），items 按 `pct_above_ma150 ASC` 排序
- 仓储单元测试 `tests/test_market_scan_repositories.py`：覆盖 upsert 幂等、last_seen_at 过滤、replace_scan 原子性（mid-transaction 抛错不清空旧表）、get_latest_snapshot 排序

**明确排除（本次不做）**：
- 任何 FMP 外部调用（留给 F105-a2）
- UniverseRefreshService / MarketScannerService / cron（留给 F105-a3）
- `GET /api/market/breakouts` 路由与 schema（留给 F105-a4）
- `SystemLog` 新增 source 枚举（`market_scanner` / `universe_refresher`） — 纯文档约定，无代码位点，在 a3 使用时加
- `.env` / `config.py` 的 `SCANNER_CRON_*` / `UNIVERSE_CRON_*`（留给 F105-a2 随 FMP key 一起加）

---

## 预计修改文件

> 6 文件 + 1 trivial edit。`models/__init__.py` 是 2 行 import 的 trivial edit（参照 F007-b 内联 JournalRow 的"不单开文件"惯例），用户已同意拆分计数。

| # | 文件路径 | 改动类型 | 说明 |
|---|---------|---------|------|
| 1 | `backend/app/models/market_scan_universe.py` | 新增 | `MarketScanUniverse` ORM，字段对照 DATA-MODEL L238–246 |
| 2 | `backend/app/models/market_breakout_scan.py` | 新增 | `MarketBreakoutScan` ORM，字段对照 DATA-MODEL L265–280，`UniqueConstraint(scan_date, ticker)` |
| 3 | `backend/alembic/versions/002_f105_market_scan_tables.py` | 新增 | 两表 DDL + 索引；`down_revision='001'`；downgrade drop 两表 |
| 4 | `backend/app/repositories/market_scan_universe_repository.py` | 新增 | upsert_many / list_active / latest_refresh_time / count |
| 5 | `backend/app/repositories/market_breakout_repository.py` | 新增 | replace_scan（单事务）/ get_latest_snapshot |
| 6 | `backend/tests/test_market_scan_repositories.py` | 新增 | 两仓储的单元测试（in-memory sqlite） |
| trivial | `backend/app/models/__init__.py` | 修改 | 增加 2 行 `from .market_scan_universe import MarketScanUniverse` 等 |

👤 用户确认后进入开发。

---

## 可测试的完成标准

| # | 标准描述 | 测试层级 | 工具 |
|---|---------|---------|------|
| 1 | `alembic upgrade head` 创建两张表；`PRAGMA table_info` 字段名/类型与 DATA-MODEL.md 一致（含 `BigInteger market_cap`、`Date scan_date`、`UniqueConstraint(scan_date, ticker)`） | 集成 | pytest + aiosqlite（复用 conftest 的 test engine）|
| 2 | `alembic downgrade -1` 干净移除两表，无残留索引 | 集成 | pytest + aiosqlite |
| 3 | `MarketScanUniverseRepository.upsert_many` 第二次以同 ticker 传入更新的 market_cap → 行数不变，字段被更新，`added_at` 保留首次值 | 单元 | pytest |
| 4 | `list_active(since)` 正确过滤 `last_seen_at < since` 的行 | 单元 | pytest |
| 5 | `MarketBreakoutRepository.replace_scan` 插入 3 行 → 再次 replace 插入 2 行 → 表只剩 2 行；scan_date 可变 | 单元 | pytest |
| 6 | `replace_scan` 在 INSERT 阶段模拟异常抛出后，事务回滚，旧快照（前一次的 3 行）仍在表中 | 单元 | pytest（monkeypatch 触发中途异常） |
| 7 | `get_latest_snapshot` 返回的 items 按 `pct_above_ma150 ASC` 升序；空表返回 `None` | 单元 | pytest |
| 8 | 新增 ORM 字段命名全部 snake_case；表名/列名与 DATA-MODEL.md 完全一致（diff check） | 单元 | pytest + inspect(Table) |

---

## Evaluator 自检清单

- [ ] `pytest backend/tests/test_market_scan_repositories.py` 全绿
- [ ] `pytest backend/tests/` 全量回归全绿（F001–F104 无回归）
- [ ] `alembic upgrade head` 在 clean db 上成功；`alembic downgrade -1` 干净
- [ ] ORM 字段命名与 DATA-MODEL.md L238–246 / L265–280 逐字段核对一致
- [ ] `market_breakout_scans (scan_date, ticker)` UniqueConstraint 存在；`market_scan_universe.ticker` unique 索引存在
- [ ] `replace_scan` 是 **单事务**（代码审阅确认 `async with session.begin()` 或等价）
- [ ] 无硬编码 magic value；无 print/未处理 await；无 console.error / Python warnings
- [ ] lint 通过（项目未单独配 linter，以 mypy 严格通过为准；F104 已通过）
- [ ] DECISIONS.md 无需新增条目（本 Sprint 只是 D038/D040 的执行，不产生新决策）
- [ ] claude-progress.txt 追加 F105-a1 完成记录
- [ ] features.json 中 F105.subtasks.F105-a1.phase 从 `contract_agreed`→`in_progress`→`testing`→`needs_review`

---

👤 确认此 Contract 后开始开发。
