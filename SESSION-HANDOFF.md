# SESSION-HANDOFF — F218-d7a contract_agreed → 下一步 Generator

> 生成：2026-05-20 (Opus 4.7) | 用途：下一 session 用 Sonnet 进入 feature-dev A-2 Generator

---

## 1. 当前状态

| 字段 | 值 |
|------|-----|
| `_pipeline_status.active_sprint` | **F218-d7a** |
| `_pipeline_status.active_sprint_phase` | **contract_agreed** |
| `F218.phase` | in_progress |
| `F218.active_sub_sprint` | F218-d7a |
| `F218.active_sprint_phase` | contract_agreed |
| `F218.sub_sprints["F218-d6b"]` | done |
| `F218.sub_sprints["F218-d7a"]` | **contract_agreed** |
| `F218.sub_sprints["F218-d7b"]` | design_needed |

F218-d6b 已 acceptance 通过 → done。F218-d7a Sprint Contract 已确认，**未进入 Generator**。

---

## 2. F218-d7a Sprint Contract 摘要

**目标**：Repricing Trigger 后端环闭合 —— cron 调度 + HTTP 出口。

**实现范围**（详见 `docs/开发/sprint-contracts/F218-d7a-contract.md`）：

| 模块 | 改动 |
|------|------|
| cron | refresh_job.py 注册 `REPRICING_TRIGGER_JOB_ID @ 22:40 UTC weekdays`，调度 `RepricingTriggerService.compute_and_store_all_triggers()` |
| router | 新建 `/api/cockpit/repricing-triggers` 2 endpoint（单标的 `GET /{ticker}` + 全市场 `GET ` 含 `triggerType?` / `limit?` filter） |
| schema | 新建 Pydantic（CamelModel 基类；evidence 为 `dict[str, Any]` + 手动 snake→camel 转 key） |
| tests | 3 cron + 8 router = 11 测试 |

**预计修改文件（6 = 上限）**：

| # | 文件 | 类型 |
|---|------|------|
| 1 | `backend/app/services/refresh_job.py` | 改 |
| 2 | `backend/app/routers/cockpit/repricing_triggers.py` | 新 |
| 3 | `backend/app/routers/cockpit/__init__.py` | 改 |
| 4 | `backend/app/schemas/cockpit/repricing_trigger.py` | 新 |
| 5 | `backend/tests/test_f218_d7a_repricing_cron.py` | 新 |
| 6 | `backend/tests/test_f218_d7a_repricing_router.py` | 新 |

**关键决策**（NP-d7a-1~10 全部按推荐已确认）：

| # | 决策 |
|---|------|
| 1 | cron 顶部常量 `REPRICING_TRIGGER_CRON = "40 22 * * 1-5"`，不动 config.py |
| 2 | tick 签名保留 `fmp_factory`（`# noqa: ARG001`）与同模块周期 tick 对齐 |
| 3 | tick 错误吞咽 `except Exception: logger.error(...)` |
| 4 | service 实例化用 `_session_scope` 上下文 |
| 5 | router prefix=`/repricing-triggers`，tag=`cockpit-repricing` |
| 6 | ticker upper → regex `^[A-Z0-9.\-]+$` → `APIError("VALIDATION_ERROR", ..., 422)` |
| 7 | evidence Pydantic `dict[str, Any]` + 手动 snake→camel 转 key（不为 5 类 evidence 写 union） |
| 8 | 全市场 `computedAt = max(rows.computed_at).isoformat()`，表空 → `datetime.now(timezone.utc).isoformat()` |
| 9 | `triggerType` 用 FastAPI Query Literal（alias=`triggerType`），自动 422 |
| 10 | `limit` 用 `Query(default=100, ge=1, le=500)`，自动 422 |

---

## 3. 开发顺序（Generator 模式，7 步，每步 wip commit）

| # | 步骤 | 文件 | 最小验证 |
|---|------|------|---------|
| 1 | `refresh_job.py` 改动（+常量 / +import / +add_job 块 / +tick 函数） | 1 | `python -c "from app.services import refresh_job"` 跑通 |
| 2 | cron 单测（`test_f218_d7a_repricing_cron.py` 3 tests S1/S2a/S2b） | 5 | 3 tests 全绿 |
| 3 | `schemas/cockpit/repricing_trigger.py` 新建（6 Pydantic 类 + TriggerType Literal） | 4 | import 通 |
| 4 | `routers/cockpit/repricing_triggers.py` 新建（2 endpoint + camelCase 转换 helper） | 2 | 编译通 |
| 5 | `routers/cockpit/__init__.py` include | 3 | `app.openapi()` 含 2 路径 |
| 6 | router 集成测试（`test_f218_d7a_repricing_router.py` 8 tests R1-R8） | 6 | 8 tests 全绿 |
| 7 | 全量回归 → Evaluator 自检 → consistency-check (C1/C4/C5) → phase=needs_review | — | 11 新测试 + d1-d6b + 全量回归（≤ 9 pre-existing） |

每步通过最小验证后立即 wip commit，**显式按文件名 add，禁 `git add -A`**：

```bash
git add <本步骤涉及的具体文件>
git commit -m "wip(F218-d7a): [step 名称]"
```

---

## 4. 已确认的引用文档

- `docs/系统设计/ARCHITECTURE.md` §Cockpit Repricing Trigger Service 533-593（cron 22:40 UTC / router 位置 / 模块边界）
- `docs/系统设计/API-CONTRACT.md` §Cockpit Repricing Triggers 1988-2106（2 endpoint 完整契约 + 错误响应）
- `docs/系统设计/DATA-MODEL.md` §RepricingTrigger 1080-1129（5 类 evidence_json schema）
- `docs/开发/sprint-contracts/F218-d7a-contract.md` — **本 sprint 合约（已 confirmed）**
- `docs/开发/sprint-contracts/F218-d6b-contract.md` — 上游声明本 sprint 下游
- `backend/app/services/refresh_job.py` — 现有 9 cron 模式样板
- `backend/tests/test_weekly_stage_cron_f216e.py` — 同模式 cron 测试样板（S1/S2a/S2b）
- `backend/app/routers/cockpit/regime.py` — 同 namespace router 样板

---

## 5. 不在范围

- ❌ 前端 widget / API client / DecisionPanel chip（→ d7b）
- ❌ 4 设计文档任何修改（status=confirmed，严格无新增 drift）
- ❌ T1-T5 detector 逻辑变更（d2-d6b 收工）
- ❌ retention 调度接线（`delete_expired_inactive` 已实装但 cron 留独立 issue）
- ❌ DECISIONS.md 追加（D096-D098 已覆盖）

---

## 6. consistency-check 结果（2026-05-20，scope=F218）

- C1 / C2 / C3 / C5 / C6 / C8：✅ clean
- C4：已自动修（追加 F218-d7a contract_agreed iteration_history entry）
- C7：d6a/d6b pre-existing minor，不在本 sprint 范围，留 acceptance 收官时统一补

```
__CONSISTENCY_CHECK_RESULT__: severe=0 medium=0 minor=2 (pre-existing) exit=0
```

---

## 7. 下一 session 启动指令

**用 Sonnet 开新 session，粘贴**：

> 继续开发 F218-d7a，Sprint Contract 已确认。
> 读取 SESSION-HANDOFF.md + docs/开发/sprint-contracts/F218-d7a-contract.md，
> 进入 feature-dev Generator 模式，从开发步骤 1（refresh_job.py 改动）开始。

---

## 8. 未决事项

无。10 设计决策已全部确认；6 文件预算明确；11 测试规划完整。
