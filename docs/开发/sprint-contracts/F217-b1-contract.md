# F217-b1 Sprint Contract — Cockpit Phase C DB 层：legacy 列 + PULLBACK 软删

> 生成：2026-05-15 | 状态：草案 → 待用户确认
> Feature：[F217](docs/需求/features.json) Phase C — Capitulation Reversal 严格重写
> Sub-sprint：F217-b1 (C4 DB 层)
> 前置：F217-a done @ 2026-05-15；DATA-MODEL §SetupSnapshot 含 legacy 软删说明；DECISIONS D095 已落地

---

## 1. 实现范围

### 包含

#### C4-a — alembic 021 schema 迁移（NP1=A 已确认）
- **新建** `backend/alembic/versions/021_f217b1_setup_snapshots_legacy.py`
  - `revision = "021_f217b1_setup_snapshots_legacy"`
  - `down_revision = "020_f216d1_setup_weekly_stage_column"`
- `upgrade()`:
  1. `op.add_column("setup_snapshots", sa.Column("legacy", sa.Boolean(), nullable=False, server_default=sa.false()))`
     - 用 `server_default=sa.false()` 是为了已有 PULLBACK + NONE + BREAKOUT + … 行在加列瞬间都获得 `legacy=false` 默认值（不阻塞迁移）
  2. `op.execute("UPDATE setup_snapshots SET legacy = 1 WHERE setup_type = 'PULLBACK'")`
     - SQLite 用 1/0 表示 boolean（与现有 `Boolean` 字段如 `ready_signal` 一致）
  3. `op.alter_column("setup_snapshots", "legacy", server_default=None)`
     - 移除 server_default — 之后由 model `default=False` 接管（避免 server_default 在新插入 row 时与 ORM 默认值产生分叉）
- `downgrade()`:
  - `op.drop_column("setup_snapshots", "legacy")`
  - **不**自动撤销 UPDATE — 因为 legacy 列被删，原 PULLBACK 行恢复"可见"（这符合 downgrade 语义"回到迁移前状态"）

#### C4-b — SetupSnapshot model 字段
- 在 `backend/app/models/setup_snapshot.py` SetupSnapshot 类末尾（`scanned_at` 之前或之后）加：
  ```python
  legacy: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
  ```
- 不加 index（legacy 选择性低，且查询永远是 `legacy=false` 的等值过滤；走全表 + 主键过滤更高效，与现有 `(ticker, scan_date)` UNIQUE 索引配合够用）

#### C4-c — SetupSnapshotRepository.purge_legacy_pullback() 方法
- 在 `backend/app/repositories/setup_snapshot_repository.py` 加：
  ```python
  def purge_legacy_pullback(self) -> int:
      """Mark all setup_type='PULLBACK' rows as legacy=true. Idempotent."""
      stmt = (
          update(SetupSnapshot)
          .where(SetupSnapshot.setup_type == "PULLBACK")
          .where(SetupSnapshot.legacy == False)  # noqa: E712 — SQLAlchemy 需要 == False
          .values(legacy=True)
      )
      result = self.db.execute(stmt)
      self.db.commit()
      return int(result.rowcount or 0)
  ```
  - 注意：用 `where(legacy == False)` 是为了 idempotent — 第二次调用 rowcount=0，不会重复 commit-touched rows
  - import 增加 `update`：`from sqlalchemy import delete, select, update`

#### C4-d — 读取路径加 legacy 过滤（防止 legacy 行渗漏到 API/UI）
两个读取路径必须同步过滤 `legacy=false`：

1. **`SetupSnapshotRepository.get_latest_all_active`** (L44-55) 内部 select 加 `.where(SetupSnapshot.legacy == False)`
2. **`SetupSnapshotRepository.get_latest_for_tickers`** — 该方法直接委托给 `get_latest_all_active`（L57-58），自动覆盖，无需独立改
3. **`decision_service.py:69-74`** 直接 select：加 `.where(SetupSnapshot.legacy == False)`

> `upsert_batch` 不动 — 新插入行依赖 model `default=False`；on-conflict update 不包含 legacy key（因为 `rows[0]` 不含 legacy），既不清也不改现有 legacy 值，符合预期。
> `delete_before` 不动 — 物理删除老快照与 legacy 状态无关。

#### C4-e — integration tests
- **新建** `backend/tests/test_setup_snapshot_purge.py`：≥6 条 integration tests（详见第 3 节 T1-T8）

### 排除（不在本 sprint）

- ❌ **Pydantic Literal 加/删 CAPITULATION** — F217-b2 / F217-b4
- ❌ **测试 fixture 批量去 PULLBACK** — F217-b3
- ❌ **前端 chips + 紫色 badge + decision_service capitulationEvidence 填充逻辑** — F217-c
- ❌ **user_settings.preferred_setups 默认值 JSON 迁移**（D095 决策 6）— 暂留 F217-c 或独立微 sprint；user_settings 是单行单用户 (`id=1`)，且 PULLBACK 在 b4 前仍是合法 Literal，不阻塞 b1
- ❌ **CAPITULATION_ENABLED feature flag**（D095 决策 6 应急方案）— b1 不引入；如需紧急关闭，直接 revert 迁移
- ❌ **手动数据修复脚本**（如 backfill 历史 PULLBACK 为 CAPITULATION）— SRS 设计意图是 PULLBACK 历史本来就不该是 capitulation 候选，不存在"backfill"需求

### 协商结果（NP）

| # | 决议 |
|---|------|
| NP1 | **A**：alembic 021 加 `legacy BOOLEAN NOT NULL DEFAULT false` 列；upgrade 同步 `UPDATE … WHERE setup_type='PULLBACK'`；`purge_legacy_pullback()` 等价幂等方法保留供未来调用（如 backup restore 后） |
| NP-b1-1 | server_default 仅用于迁移时的"加列默认"，**迁移结束立刻 `alter_column` 移除 server_default**，之后由 ORM `default=False` 接管，避免双默认源分叉 |
| NP-b1-2 | downgrade 只 drop_column，**不**自动撤销 UPDATE（标准 alembic 语义：回到 schema 前状态即可，数据语义恢复由列消失自然带来） |
| NP-b1-3 | 读取过滤覆盖 **2 个 repo 方法 + 1 个 decision_service 直接 select**（共 3 处），不引入 query helper / scoped query（YAGNI；仅 3 处直接加 `.where` 更清晰） |

---

## 2. 预计修改文件清单（5 个）

| # | 路径 | 类型 |
|---|------|------|
| 1 | `backend/alembic/versions/021_f217b1_setup_snapshots_legacy.py` | **新建** |
| 2 | `backend/app/models/setup_snapshot.py` | 修改（加 legacy 字段） |
| 3 | `backend/app/repositories/setup_snapshot_repository.py` | 修改（加 purge 方法 + get_latest_all_active 加 legacy 过滤） |
| 4 | `backend/app/services/cockpit/decision_service.py` | 修改（select 加 `.where(legacy == False)`） |
| 5 | `backend/tests/test_setup_snapshot_purge.py` | **新建** |

✅ 5 文件，留 1 文件 buffer。后续发现遗漏文件必须二次协商。

---

## 3. 完成标准 — Evaluator 验收清单

### 测试矩阵（共 10 条）

| # | 测试描述 | 层级 | 工具 |
|---|---------|------|------|
| T1 | alembic upgrade 021 后 `PRAGMA table_info(setup_snapshots)` 含 `legacy INTEGER NOT NULL` 列（SQLite 把 Boolean 存为 INTEGER 0/1）；downgrade 021 后该列消失 | 集成 | pytest + alembic command API |
| T2 | upgrade 021 同时把已有 setup_type='PULLBACK' 的行 legacy 置为 1；其它 setup_type 行 legacy=0 | 集成 | pytest（pre-insert 3 行：PULLBACK / BREAKOUT / NONE → upgrade → 查询验证） |
| T3 | `SetupSnapshotRepository.purge_legacy_pullback()` 第一次调用 rowcount = PULLBACK 行数；第二次调用 rowcount = 0（idempotent） | 单元 | pytest |
| T4 | `purge_legacy_pullback()` 不影响其它 setup_type 行的 legacy 值（不会误标 BREAKOUT/NONE/CAPITULATION 为 legacy） | 单元 | pytest |
| T5 | `get_latest_all_active(["X"])` 当 X 的最新行 legacy=true 时返回空列表（被过滤掉，不 fallback 到次新行）— 即 legacy 行**完全不可见**而非"再往前看一行" | 单元 | pytest |
| T6 | `get_latest_for_tickers(["X"])` 与 `get_latest_all_active` 行为一致（委托关系不破） | 单元 | pytest |
| T7 | `decision_service.compute_decision_data(db, "X")` 当 X 最新行 legacy=true 且无 override 时抛 `LookupError`（与"无 snapshot"语义对齐 → 404）；当 X 有 legacy=true 历史行 + legacy=false 较旧行时，**返回较旧的 legacy=false 行**（即 legacy 完全不参与选择） | 集成 | pytest |
| T8 | `setup_service.compute_and_store_all` 新插入行 legacy=0（依赖 ORM `default=False`）；on-conflict update 同一 (ticker, scan_date) 时不修改原 legacy 值（即 rows 字典不含 legacy key 的副作用验证） | 集成 | pytest（mock universe + bars → 验证 setup_snapshots.legacy） |
| T9 | `delete_before(cutoff)` 物理删除老快照不区分 legacy 状态（行为同 b1 前） | 单元 | pytest |
| T10 | **全量回归**：`uv run pytest backend/tests/ -x` 全通过；diff vs 开工前 = **0 新增失败**；F217-a 引入的 `test_capitulation_reversal.py` 全部继续通过 | 集成 | pytest |

### 自检清单（Evaluator 模式）

- [ ] T1-T10 全部通过
- [ ] **Lint**：`ruff check backend/alembic/versions/021_*.py backend/app/models/setup_snapshot.py backend/app/repositories/setup_snapshot_repository.py backend/app/services/cockpit/decision_service.py backend/tests/test_setup_snapshot_purge.py` 无新增 warning
- [ ] **死代码**：无未使用 import；`update` 已加入 setup_snapshot_repository.py 的 sqlalchemy import
- [ ] **硬编码**：`'PULLBACK'` 字符串只出现在 alembic UPDATE / purge_legacy_pullback / 测试 fixture 三处；其它代码不新增 PULLBACK 字面量
- [ ] **alembic upgrade/downgrade 双向**：在干净 sqlite 上 upgrade → downgrade → upgrade 闭环可重复执行
- [ ] **Migration safety**：upgrade 不依赖任何 ORM 加载（纯 op.add_column + op.execute SQL）— 这样即使 model 未加 legacy 字段也能跑（向前兼容）
- [ ] **F217-b2 解耦**：Pydantic Literal 中 PULLBACK 仍 valid（NP2=Y），b1 完全不动 schemas/ai/schemas
- [ ] **claude-progress.txt** 追加 Generator 完成进度
- [ ] **不修改文档**：DATA-MODEL / API-CONTRACT / DECISIONS 本 sprint 不动（已在 F217 system-design 阶段落地）

### 代码质量自检

- [ ] alembic 021 文件 docstring 说明用途（"F217-b1: setup_snapshots.legacy column + soft-delete PULLBACK rows"）
- [ ] `purge_legacy_pullback` docstring 明确 "Idempotent — safe to call multiple times"
- [ ] `get_latest_all_active` 加 legacy 过滤后保留原有 active_tickers 短路逻辑（空列表早返回）
- [ ] decision_service 改动加 inline comment：`# F217-b1: exclude soft-deleted legacy rows`（这是少数 WHY 不显而易见的地方）
- [ ] 不引入 try-except 吞 SQLAlchemyError；不引入 print debug

---

## 4. 开发顺序（Generator 模式逐步执行）

> ⚠️ 禁用 `git add -A`。每步显式列文件名。

### Step 1 — alembic 021 迁移脚本
1. 新建 `backend/alembic/versions/021_f217b1_setup_snapshots_legacy.py`，按 §1 C4-a 写 upgrade/downgrade
2. 验证（最小）：在 dev DB backup 副本上跑 `uv run alembic upgrade head`，再 `uv run alembic downgrade -1`，再 `uv run alembic upgrade head`，无异常
3. WIP commit：
   ```bash
   git add backend/alembic/versions/021_f217b1_setup_snapshots_legacy.py
   git commit -m "wip(F217-b1): alembic 021 setup_snapshots.legacy column + PULLBACK soft-delete"
   ```

### Step 2 — SetupSnapshot model 加 legacy 字段
1. 修改 `backend/app/models/setup_snapshot.py` 加 `legacy: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)`
2. 验证（最小）：`python -c "from app.models.setup_snapshot import SetupSnapshot; print(SetupSnapshot.__table__.columns['legacy'])"` 输出列定义
3. WIP commit：
   ```bash
   git add backend/app/models/setup_snapshot.py
   git commit -m "wip(F217-b1): SetupSnapshot.legacy field (Boolean, default False)"
   ```

### Step 3 — Repository purge 方法 + 读取路径过滤
1. 修改 `backend/app/repositories/setup_snapshot_repository.py`：
   - import 增加 `update`
   - 加 `purge_legacy_pullback()` 方法
   - `get_latest_all_active` select 链加 `.where(SetupSnapshot.legacy == False)`
2. 验证（最小）：`uv run pytest backend/tests/ -k setup_snapshot -v`（看现有 repo 测试是否仍过）
3. WIP commit：
   ```bash
   git add backend/app/repositories/setup_snapshot_repository.py
   git commit -m "wip(F217-b1): repo purge_legacy_pullback + get_latest legacy filter"
   ```

### Step 4 — decision_service legacy 过滤
1. 修改 `backend/app/services/cockpit/decision_service.py` L69-74 select 链加 `.where(SetupSnapshot.legacy == False)` + 1 行 inline comment
2. 验证（最小）：`uv run pytest backend/tests/test_decision_f203b2.py -v` 仍全过（fixture 中 legacy 字段默认 False，不应破坏现有断言）
3. WIP commit：
   ```bash
   git add backend/app/services/cockpit/decision_service.py
   git commit -m "wip(F217-b1): decision_service exclude legacy rows"
   ```

### Step 5 — integration tests 新建
1. 新建 `backend/tests/test_setup_snapshot_purge.py`：T1-T9 全覆盖
2. 验证：`uv run pytest backend/tests/test_setup_snapshot_purge.py -v` 全绿
3. WIP commit：
   ```bash
   git add backend/tests/test_setup_snapshot_purge.py
   git commit -m "wip(F217-b1): integration tests for legacy column + purge + read filter"
   ```

### Step 6 — 全量回归 + Final commit
1. `uv run pytest backend/tests/ -x` 全跑一遍
2. 记录回归结果到 Evaluator 报告（T10）
3. 如有 F217-b1 引入的新失败 → 回 Step 3/4 修复，**计入熔断**（连续 3 次失败强制停止）
4. 全绿后：
   ```bash
   git add backend/alembic/versions/021_f217b1_setup_snapshots_legacy.py \
           backend/app/models/setup_snapshot.py \
           backend/app/repositories/setup_snapshot_repository.py \
           backend/app/services/cockpit/decision_service.py \
           backend/tests/test_setup_snapshot_purge.py
   git commit -m "feat(F217-b1): setup_snapshots.legacy column + PULLBACK soft-delete (Phase C DB layer)"
   ```
   不 squash WIP commits（保留 bisect 颗粒度）

---

## 5. 回滚方式

- **代码层**：WIP commits 颗粒度，任意 step 失败可 `git reset --hard <prev-wip>` 退回
- **数据库层**：
  - 标准 alembic downgrade：`uv run alembic downgrade -1` → drop legacy 列，所有原 PULLBACK 行恢复"可见"
  - 紧急完全回滚到 b1 前：dev 用 `cp data/app.db.bak-YYYYMMDD data/app.db`；prod 不适用（本项目无 prod）
- **观察期**：建议 b1 部署后**等待 1 个 daily cron 周期**（24h），观察 setup_monitor 是否仍显示历史 PULLBACK 行（应该消失）；如果仍显示 → decision_service 或 setup_service 还有未覆盖的读取路径，开 hotfix sprint

---

## 6. Generator 模式恢复指令（A-2）

```
继续开发 F217-b1，Sprint Contract 已确认。
读取 SESSION-HANDOFF.md + docs/开发/sprint-contracts/F217-b1-contract.md，
进入 Generator 模式，从 §4 开发顺序 Step 1（alembic 021 迁移）开始。
```

---

## 7. 风险与备注

- ⚠️ **server_default 双默认源风险**：alembic upgrade 在 add_column 时用 `server_default=sa.false()`（为了已有 row 落默认值），紧接着 `alter_column server_default=None`（避免与 ORM `default=False` 分叉）。如果忘记 alter_column 第二步，新插入 row 会同时被 server_default 和 ORM default 设置 — SQLite 中无实际冲突但语义混乱
- ⚠️ **decision_service 是 repo 外唯一直接查询**：通过 §1 grep 全量扫描确认（`grep -rn "select(SetupSnapshot)" backend/`）。如果未来有人在 service 层加新的直接查询，必须同步加 legacy 过滤 — **建议在 D095 加一句"SetupSnapshot 所有读取路径必须过滤 legacy=false"**（不在本 sprint 改，留待 b 全部完成后批量更新 DECISIONS）
- ⚠️ **F217-b2 解耦**：本 sprint 不动 Pydantic Literal — PULLBACK 仍是 valid Literal，已有 user_settings.preferred_setups JSON 含 PULLBACK 仍然合法（不会被 schema 校验拒）。b2/b3/b4 串行推进期间，PULLBACK Literal → fixture → 删 Literal
- ⚠️ **CAPITULATION 已可写入**：F217-a 完成后 setup_service 已可产生 setup_type='CAPITULATION' 行；alembic 021 上线后这些行 legacy=false 正常可见。即 b1 上线后 SetupMonitor 立刻能看到 CAPITULATION 行（如果当日有触发），但 UI 仍是默认 badge（紫色 badge 要等 F217-c）
- ⚠️ **父 feature F217 不升 done**：F217-b1 完成后 phase=needs_review，sub_sprints={a:done, b1:done, b2:design_needed, b3:design_needed, b4:design_needed, c:design_needed}。父 status 保持 in_progress；consistency-check C1 应通过

---

## 8. 用户确认签字位

请确认以下条款（缺一项不可进 Generator）：

- [ ] **范围**：§1「包含/排除」边界 OK，5 文件清单准确（DB 4 + decision_service 1）
- [ ] **协商点**：NP1=A 已确认；新增 NP-b1-1（server_default 立刻撤销）/ NP-b1-2（downgrade 只 drop_column）/ NP-b1-3（3 处直接加 where，不引入 query helper）OK
- [ ] **测试**：T1-T10 完成标准合理；T7 关键 — "legacy=true 不 fallback 到次新行"是设计决策（legacy 行完全不可见）
- [ ] **回滚**：标准 alembic downgrade 可逆；不引入 CAPITULATION_ENABLED flag

确认后我会：
1. 把 F217-b1 的 sub_sprint 状态从 `design_needed` 升 `contract_agreed`
2. features.json `_pipeline_status.active_sprint_phase` 更新为 `contract_agreed`
3. 生成 SESSION-HANDOFF.md
4. **停止**，让你开新 session 进 Generator 模式
