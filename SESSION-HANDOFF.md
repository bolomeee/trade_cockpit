# SESSION HANDOFF

> 生成时间：2026-04-25
> 当前 Skill：feature-dev（F208-a Sprint Contract 已确认，待进入 Generator 模式）
> 当前 Feature：F208-a — AI 基座（依赖 + ai_memos 表 + 配置层）
> 上一阶段：v1.8 全部 done；本阶段：v2.0 Cockpit P2 AI 层启动

---

## 完成的内容（本 session）

1. **F208 拆分**（按职责清晰，每子 sprint ≤6 文件）
   - F208-a 依赖 + ai_memos 表 + 配置层（6 文件）
   - F208-b gateway 核心模块 errors/memo_repo/budget/routing（6 文件）
   - F208-c gateway 主流程 + LiteLLM + `/api/ai/{task_type}` endpoint（6 文件）
   - 依赖链：F208-a → F208-b → F208-c → F209/F210/F211

2. **features.json 更新**
   - `_iteration_log` v2.0 added：F208 → F208-a/b/c
   - 原 F208 记录替换为 F208-a/b/c 三条独立记录（参考 F200-a/b 格式）
   - F209/F210/F211 `dependencies` 中的 `"F208"` → `"F208-c"`
   - `_pipeline_status`：`current_iteration` v1.8 → v2.0；`active_sprint` → `F208-a`；`active_sprint_phase` → `contract_agreed`
   - `last_updated` → `2026-04-25-F208-split-into-a-b-c`

3. **F208-a Sprint Contract 已确认**（用户 2026-04-25 接受）
   - 落盘：`docs/开发/sprint-contracts/F208-a-contract.md`
   - 6 文件清单（精确 6 个，不超限）
   - 9 条完成标准 + 7 步 Generator 顺序 + Evaluator 自检清单

---

## 中断位置

Sprint Contract 协商完成，**强制停止于 Generator 模式之前**（按 feature-dev SKILL A-1 规定，Contract 确认后必须开新 session 进 Generator，不在同一 session 中继续）。

---

## Sprint Contract 执行状态

**当前 Contract**：`docs/开发/sprint-contracts/F208-a-contract.md`

| 开发步骤 | 状态 |
|---------|------|
| Sprint Contract 协商 | ✅ 已确认 |
| DATA-MODEL 确认（§AiMemo 已存在） | ✅ 不需改动 |
| API-CONTRACT 确认（本 sprint 不涉及 endpoint） | ✅ 不适用 |
| pyproject.toml 加 litellm | ⬜ 未开始 |
| config.py 加 7 个 AI 字段 | ⬜ 未开始 |
| AiMemo ORM + 注册 | ⬜ 未开始 |
| 数据库迁移（Alembic 012） | ⬜ 未开始 |
| 测试 test_ai_memo_schema_f208a | ⬜ 未开始 |
| 全量回归 | ⬜ 未开始 |
| Evaluator 评估 | ⬜ 未开始 |

---

## 已创建/修改的文件（本 session）

- `docs/需求/features.json` — 修改（F208 拆分 + 依赖更新 + pipeline status）
- `docs/开发/sprint-contracts/F208-a-contract.md` — 新建
- `claude-progress.txt` — 追加 F208 拆分 + F208-a Contract 协商记录
- `SESSION-HANDOFF.md` — 本文件，覆盖更新

⚠️ 这些是 docs/进度类改动，**未 commit**。下一 session 进 Generator 前，先按规则 7"sprint 间杂项"立即 commit：

```bash
git add docs/需求/features.json docs/开发/sprint-contracts/F208-a-contract.md claude-progress.txt SESSION-HANDOFF.md
git commit -m "chore(F208): 拆为 F208-a/b/c + F208-a Sprint Contract 确认"
```

然后再进入 Generator 步骤 1。

---

## 遗留决策

无（D064/D069 已定方案，本 sprint 仅执行，不需新决策）。

---

## F208-a Sprint Contract 摘要

**实现范围**（详见 contract 文件）：

1. `backend/pyproject.toml` 增 `litellm>=1.83,<2.0`
2. `backend/app/config.py` Settings 增 7 字段：
   - `ai_model_default` / `ai_model_critical` / `ai_model_complex`
   - `openai_api_key`
   - `ai_monthly_budget_usd` / `ai_memo_cache_ttl_hours` / `ai_schema_version`
3. `backend/app/models/ai_memo.py` 新建（13 字段对齐 DATA-MODEL §AiMemo）
4. `backend/app/models/__init__.py` 注册 AiMemo
5. `backend/alembic/versions/012_f208a_ai_memos.py` 建表 + 2 个复合索引：
   - `ix_ai_memos_task_input_created` (task_type, input_hash, created_at DESC) — dedup 查询
   - `ix_ai_memos_created_at_desc` — budget SUM 月度扫描
6. `backend/tests/test_ai_memo_schema_f208a.py` 5 个测试（columns / upgrade / downgrade / Numeric 精度 / env override）

**Generator 开发顺序**（详见 contract §4）：
```
1. pyproject.toml + uv lock                         → wip commit
2. config.py 加 7 字段                              → wip commit
3. ai_memo.py + models/__init__.py 注册              → wip commit
4. alembic 012 迁移 + 双向手动验证                    → wip commit
5. test_ai_memo_schema_f208a.py + pytest 通过        → wip commit
6. 全量回归 uv run pytest -m 'not live'              → 进 Evaluator
```

每步严格按文件名 `git add <path>`，**禁用 `git add -A`**。

---

## 下一个 Session 继续的指令

> ⚠️ 建议用 **Sonnet** 开新 session（Contract 已定，纯执行阶段无需 Opus）。复制以下指令：

```
继续开发 F208-a，Sprint Contract 已确认。
请读取：
- SESSION-HANDOFF.md
- CLAUDE.md
- docs/开发/sprint-contracts/F208-a-contract.md
- claude-progress.txt（最后部分）

第一步：先把 docs/进度类改动按 chore(F208) 提交。
然后进入 Generator 模式，从开发顺序步骤 1 开始：
backend/pyproject.toml 加 litellm>=1.83,<2.0 → uv lock。
```
