# SESSION-HANDOFF — F217-b1 已完成，等待验收

> 生成：2026-05-15
> 上一阶段：F217-b1 Generator + Evaluator 完成，consistency-check C4 修复
> 当前 phase：`needs_review`
> 下一阶段：用户验收 F217-b1 → 开启 F217-b2 Sprint Contract 协商

---

## 1. 本次完成摘要（F217-b1）

**目标**：为 setup_snapshots 加 `legacy` BOOL 列，把历史 PULLBACK 行软删（不可见），同步给所有读取路径加过滤。

### 实际修改文件（5 个）

| 文件 | 变更 |
|------|------|
| `backend/alembic/versions/021_f217b1_setup_snapshots_legacy.py` | **新建**：upgrade 加列+UPDATE+batch_alter_table 撤 server_default；downgrade drop_column |
| `backend/app/models/setup_snapshot.py` | `legacy: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)` |
| `backend/app/repositories/setup_snapshot_repository.py` | `purge_legacy_pullback()` 幂等方法 + `get_latest_all_active` 加 `.where(legacy==False)` |
| `backend/app/services/cockpit/decision_service.py` | L69-74 直接 select 加 `.where(legacy==False)` + inline comment |
| `backend/tests/test_setup_snapshot_purge.py` | **新建**：T1-T9 共 12 条 integration tests，全通过 |

### 关键技术点

- **alembic SQLite 限制**：`op.alter_column` 在 SQLite 不支持，改用 `op.batch_alter_table` context manager（env.py 已配 `render_as_batch=True`，但仅对 autogenerate 生效）
- **dev.db 路径**：`backend/dev.db`（不是 `data/*.db`）
- **upgrade/downgrade 闭环**：已验证；PULLBACK 7 行 legacy=1，其余 legacy=0

### 测试结果

| 范围 | 通过 | 失败 |
|------|------|------|
| T1-T9 (12 tests) | 12/12 | 0 |
| F217-a 回归 (34 tests) | 34/34 | 0 |
| decision_service (28 tests) | 28/28 | 0 |
| 全量回归 | 1049/1057 | 8（全部预存，stash 证明非 F217-b1 引入） |

### 预存失败清单（非本 sprint 引入）

| 文件 | 原因 |
|------|------|
| test_schema.py::test_all_tables_created | EXPECTED_TABLES 缺 `weekly_stage_snapshots`（019 migration 引入） |
| test_ai_schemas_f209.py::test_D1_market_narrator_success | tier 值不符 |
| test_ai_schemas_f211a1.py (R5/R6) | registry 解析 |
| test_decision_f215b.py (AlembicRoundtrip) | 018 migration 测试 |
| test_fmp_client.py (screener universe) | 去重逻辑 |
| test_regime_f201a/b.py | INDEX_ETFS 预期 3 实际 4（F217-a 已引入 VXX） |

---

## 2. Commit 历史（本次 sprint）

```
69203d2  wip(F217-b1): alembic 021 setup_snapshots.legacy column + PULLBACK soft-delete
a85f734  wip(F217-b1): SetupSnapshot.legacy field (Boolean, default False)
5ac20a0  wip(F217-b1): repo purge_legacy_pullback + get_latest legacy filter
1ade61b  wip(F217-b1): decision_service exclude legacy rows
a302023  wip(F217-b1): integration tests for legacy column + purge + read filter
9ff5ac2  feat(F217-b1): setup_snapshots.legacy column + PULLBACK soft-delete (Phase C DB layer)
e6c9f84  chore(F217-b1): iteration_history needs_review 节点补录 (consistency-check C4)
```

---

## 3. 项目当前状态快照

```
F217 — phase: in_progress (Cockpit Phase C — Capitulation Reversal 严格重写)
 ├── F217-a   — done ✅ (后端 setup_service 7 AND 门 + 34 pure tests)
 ├── F217-b1  — needs_review 🔍 ← 等待验收
 ├── F217-b2  — design_needed (Pydantic Literal 加 CAPITULATION, 6 files)
 ├── F217-b3  — design_needed (测试 fixture 去 PULLBACK, 6 files)
 ├── F217-b4  — design_needed (Pydantic Literal 删 PULLBACK 收紧)
 └── F217-c   — design_needed (前端 chips + 紫色 badge)
```

`_pipeline_status`: active_sprint=F217-b1, active_sprint_phase=needs_review, development=in_progress

---

## 4. 下一步任务

### 选项 A：验收 F217-b1（触发 acceptance skill）
- 对照设计意图确认：legacy=true 的 PULLBACK 行在 SetupMonitor 上消失
- 确认新 CAPITULATION 行（如有触发）正常可见（legacy=false）
- 验收通过后 F217-b1 → done

### 选项 B：直接开启 F217-b2 Sprint Contract 协商
- F217-b2：Pydantic Literal 加 CAPITULATION，6 files（含 schemas/cockpit/*.py）
- 预计文件：cockpit/setup_snapshot.py / decision.py / 其他 schema files（待 Sprint Contract 精确列出）

---

## 5. 风险提示（给下一 session）

1. **test_regime_f201a/b 失败根因**：INDEX_ETFS 含 VXX（4 个），测试预期 3 个 — 这是 F217-a 时引入 VXX 作为 capitulation 信号用途。下一个要动 cockpit_params.py 的 sprint（F217-b2）需要同步修复这两个测试
2. **test_schema.py 根因**：weekly_stage_snapshots 表在 EXPECTED_TABLES 缺席，需要在任意下一个 schema sprint 补全
3. **F217-b2 注意**：Pydantic Literal 改动会影响 API 校验层，需要同时确保 `test_setup_f202a.py` 中的 PULLBACK fixture 能过（F217-b3 前，PULLBACK 仍是 valid Literal）

---

## 6. 下一 Session 恢复指令

如需验收 F217-b1：
```
F217-b1 已完成，需要验收。
读取 SESSION-HANDOFF.md，
触发 acceptance skill 对 F217-b1 进行验收。
```

如需直接开 F217-b2：
```
F217-b1 已完成等待验收，暂跳，直接开 F217-b2 Sprint Contract 协商。
读取 SESSION-HANDOFF.md + docs/开发/sprint-contracts/（扫描相关合约）。
进入 feature-dev A-1 模式，准备开发 F217-b2。
```
