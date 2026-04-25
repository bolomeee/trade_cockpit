# SESSION HANDOFF

> 生成时间：2026-04-25
> 当前 Skill：feature-dev（F208-b Sprint Contract 协商完成）
> 当前 Feature：F208-b — AI Gateway 核心模块（errors / memo_repo / budget / routing）
> 上一阶段：F208-a 用户验收通过 → done
> 本阶段：F208-b Sprint Contract 起草 + 用户确认 5 项设计点 → contract_agreed
> 下一阶段：F208-b Generator 模式（**新 session 执行**）

---

## 完成的内容（本 session）

1. 读取上下文：features.json F208-b 条目、F208-a contract、SESSION-HANDOFF（旧版）、DATA-MODEL §AiMemo（13 列）、DECISIONS D064/D069/D070、config.py / conftest.py / 现有 Repository 风格样本
2. 起草 Sprint Contract：[`docs/开发/sprint-contracts/F208-b-contract.md`](docs/开发/sprint-contracts/F208-b-contract.md)
3. 5 项设计点用户确认（2026-04-25）：
   - memo_repo 用 Repository class 风格（统一现有 `JournalRepository` / `UserSettingsRepository`，`self.db` 命名）
   - 不写 `error_code` 列（DATA-MODEL v2.0 schema 表无此列）
   - budget `mtd ≥ cap` 即抛错（含等号）
   - `AiError` 基类保留（便利 endpoint 兜底）
   - routing 用模块级 dict（D070 不适用）
4. Contract 内 memo_repo 章节、测试章节、§3 完成标准、Generator 步骤、§6 风险点 R5 全部按 class 风格更新
5. features.json：F208-b phase → `contract_agreed`，description 补充设计点摘要，`_pipeline_status.active_sprint_phase` → `contract_agreed`，`last_updated` 更新
6. claude-progress.txt：追加 F208-b Contract 协商完成条目

---

## Sprint Contract 摘要（F208-b）

### 实现范围
4 个纯 Python 支撑模块 + 配套测试，**不打 LLM、不暴露 endpoint、不实例化 LiteLLM client**。F208-c 在此基础上编排成 `AiGateway.run()`。

### 6 文件清单（精确 6 个，纯新增）

| # | 文件 | 内容 |
|---|------|------|
| 1 | `backend/app/ai/__init__.py` | 包初始化（仅 docstring） |
| 2 | `backend/app/ai/errors.py` | `AiError` 基类 + `AiProviderError` / `AiSchemaError` / `AiBudgetExceeded` / `AiGuardrailViolation` |
| 3 | `backend/app/ai/memo_repo.py` | `AiMemoRepository` class（`find_cached` / `write`）+ 模块级 `compute_input_hash` + `_canonical_json` |
| 4 | `backend/app/ai/budget.py` | `month_to_date_cost` + `assert_within_budget`（默认读 settings.ai_monthly_budget_usd） |
| 5 | `backend/app/ai/routing.py` | 模块级 `_TASK_TIER` dict（7 task_type）+ `resolve_tier` / `resolve_model` / `resolve` / `known_task_types` |
| 6 | `backend/tests/test_ai_core_modules_f208b.py` | 16 测试（unit + 集成，复用 conftest db_session fixture） |

### 14 条完成标准 + 16 测试 + 5 风险点
详见 contract §3 / §1.6 / §6。

---

## Generator 开发顺序（新 session 执行）

```
1. backend/app/ai/__init__.py + errors.py
   wip commit: "wip(F208-b): ai package + errors module"

2. backend/app/ai/routing.py
   wip commit: "wip(F208-b): routing task_type → tier → model"

3. backend/app/ai/memo_repo.py
   wip commit: "wip(F208-b): AiMemoRepository write + find_cached"

4. backend/app/ai/budget.py
   wip commit: "wip(F208-b): budget month_to_date + assert_within_budget"

5. backend/tests/test_ai_core_modules_f208b.py
   pytest 全跑通
   wip commit: "wip(F208-b): core modules unit + integration tests"

6. 全量回归 uv run pytest -m 'not live'
   预期 519 passed（503 基线 + 16 新增），无新失败
```

每步严格按文件名 `git add <path>`，**禁用 `git add -A`**。

---

## 文件状态

| 文件 | 改动 |
|------|------|
| `docs/开发/sprint-contracts/F208-b-contract.md` | 新建（已确认） |
| `docs/需求/features.json` | F208-b phase + description + active_sprint_phase + last_updated |
| `claude-progress.txt` | 追加 F208-b Contract 协商完成条目 |
| `SESSION-HANDOFF.md` | 本文件（重写） |

本 session **未触碰任何代码文件**，仅文档 / 配置层。

---

## 待提交

本 session 4 个文档改动尚未 commit。建议在新 session 进 Generator **之前**先单独 commit 一次：

```bash
git add "docs/开发/sprint-contracts/F208-b-contract.md" \
        "docs/需求/features.json" \
        claude-progress.txt \
        SESSION-HANDOFF.md
git commit -m "chore(F208-b): Sprint Contract 协商确认 → contract_agreed"
```

不与 Generator 步骤混 commit，保持原子。

---

## 遗留决策

无。D064 / D069 已定方案，本 sprint 仅执行；D070 经判定不适用（routing 表是静态 dispatch，非可调阈值）。

---

## 下一个 Session 继续的指令

```
继续开发 F208-b，Sprint Contract 已确认。

请读取（按顺序）：
- SESSION-HANDOFF.md
- docs/开发/sprint-contracts/F208-b-contract.md
- CLAUDE.md
- docs/系统设计/DATA-MODEL.md（§AiMemo，13 列字段权威）
- docs/系统设计/DECISIONS.md（D064 / D069）
- backend/app/config.py（确认 7 个 AI 字段已就位）
- backend/app/models/ai_memo.py（确认 ORM 与 contract 1.3 章节一致）

进入 Generator 模式，从开发步骤 1 开始：
  Step 1: 新建 backend/app/ai/__init__.py + backend/app/ai/errors.py
          wip commit "wip(F208-b): ai package + errors module"

每步完成后立即按 contract §4 的命名做 wip commit，
禁用 git add -A，逐文件 git add。

5 步全部完成 + 全量回归通过后，自动切换 Evaluator 模式按 §5 自检清单评估。
```
