# SESSION HANDOFF — F217-b4 needs_review，待用户验收

> 生成：2026-05-16
> 项目：MA150 Tracker → Workbench → Cockpit
> 当前 Sprint：F217-b4（Cockpit Phase C Pydantic Literal 收紧 — 删 PULLBACK）
> phase：`needs_review` ← Generator + Evaluator 全部完成，等用户验收

---

## 1. F217-b4 已完成（Generator + Evaluator）

### 实现内容

6 个 Pydantic schema 的 `setup_type` / `setupType` Literal 元组删除 `"PULLBACK"` 字面量：

| # | 文件 | 行号 | 改动 |
|---|------|------|------|
| 1 | `backend/app/schemas/cockpit/position.py` | L12 | `_VALID_SETUP_TYPES` −`"PULLBACK", ` |
| 2 | `backend/app/schemas/cockpit/pending_order.py` | L11 | `_VALID_SETUP_TYPES` −`"PULLBACK", ` |
| 3 | `backend/app/ai/schemas/trade_plan.py` | L45 | `TradePlanInput.setupType` −`"PULLBACK", ` |
| 4 | `backend/app/ai/schemas/candidate_ranker.py` | L42 | `CandidateInput.setupType` −`"PULLBACK", ` |
| 5 | `backend/app/ai/schemas/contradiction_detector.py` | L41 | `_SETUP_TYPE` −`"PULLBACK", ` |
| 6 | `backend/app/ai/schemas/journal_assistant.py` | L52 | `_SETUP_TYPE` −`"PULLBACK", ` |

diff 对称性：每文件 1 行 `−"PULLBACK", `，与 b2 加 CAPITULATION 形成镜像。

### Evaluator 验收结果

| # | 测试 | 结果 |
|---|------|------|
| T1 | grep 6 文件 `"PULLBACK"` = 空（exit 1） | ✅ |
| T2 | grep 6 文件 `"CAPITULATION"` 各 ≥1 | ✅ 6 文件各 1 命中 |
| T3 | REPL 6 schema 构造 PULLBACK 抛 ValidationError | ✅ 全 6 `literal_error` |
| T4 | REPL 6 schema 构造 CAPITULATION 通过 | ✅ 全 6 接受 |
| T5 | `test_setup_snapshot_purge.py` | ✅ 12/12 |
| T6 | `test_setup_f202a.py`（含 test_s15_pullback_zone_now_returns_none） | ✅ 27/27 |
| T7 | 全量回归 | ✅ 1095 passed / 8 预存失败 / **0 新增失败** |

预存 8 失败（非本 sprint 引入，与 b3 基线完全一致）：
`test_ai_schemas_f209 D1 / test_ai_schemas_f211a1 R5/R6 / test_regime_f201b S4 / test_decision_f215b AlembicRoundtrip / test_fmp_client / test_regime_f201a S14 / test_schema`

### Commits

| Commit | 内容 |
|--------|------|
| `f8c1ada` | wip(F217-b4): cockpit schemas Literal -PULLBACK |
| `242c4b7` | wip(F217-b4): trade_plan Literal -PULLBACK |
| `909052a` | wip(F217-b4): candidate_ranker Literal -PULLBACK |
| `6486372` | wip(F217-b4): contradiction_detector Literal -PULLBACK |
| `18264fe` | wip(F217-b4): journal_assistant Literal -PULLBACK |
| `8f98db4` | feat(F217-b4): Pydantic schemas Literal -PULLBACK (backward-compat window closed) |

---

## 2. 下一步：用户验收

验收时需确认以下内容（与 T1-T7 对应）：

1. `git diff HEAD~6..HEAD` 查看 6 文件的 diff — 每文件仅 1 行 `−"PULLBACK", `
2. `grep -rn '"PULLBACK"' backend/app/schemas/` — 应无命中
3. T7 全量回归结果：1095 passed 8 预存失败 0 新增
4. `purge_legacy_pullback` 不动（`git diff` 验证 `setup_snapshot_repository.py` 零变更）

验收通过后：
- features.json `F217-b4` → `"done"`
- features.json `active_sprint` → `"F217-c"`（或先 design_needed）
- 生成 `docs/验收/v2.2.0-F217-b4-acceptance.md`

---

## 3. F217 整体状态

| Sub-sprint | 状态 | 备注 |
|-----------|------|------|
| F217-a | done ✅ | setup_service 重写 + 34 pure tests |
| F217-b1 | done ✅ | DB legacy 列 + purge_legacy_pullback |
| F217-b2 | done ✅ | 6 schema Literal +CAPITULATION |
| F217-b3 | done ✅ | 7 测试 fixture PULLBACK→CAPITULATION |
| **F217-b4** | **needs_review 🔄** | **本 sprint，等用户验收** |
| F217-c | design_needed | 前端 chips + 紫色 badge（b4 done 后启动） |

b 系列全部完成（b4 done 后）→ F217-c 可启动：前端 `SetupType` 类型 + chips + 紫色 badge。

---

## 4. 下个 Session 恢复指令（验收后）

用户验收通过后，开新 session 粘贴：

```
F217-b4 验收通过，请将 features.json F217-b4 → done，并生成
docs/验收/v2.2.0-F217-b4-acceptance.md，
然后协商 F217-c Sprint Contract（前端 SetupType/chips/紫色 badge）。
```

---

## 5. 未决事项

- [ ] 用户验收 F217-b4（T1-T7 全过，diff 对称性确认）
- [ ] F217-c Sprint Contract 协商（前端类型 SetupType + chips + CAPITULATION 紫色 badge）
- [ ] `user_settings.preferred_setups` JSON 默认值运行时迁移（排除在 b 系列外，F217-c 或独立微 sprint）
- [ ] Lint F401 position.py `import pydantic` unused import（b2 遗留，非 F217 范围，可独立 chore 清理）
