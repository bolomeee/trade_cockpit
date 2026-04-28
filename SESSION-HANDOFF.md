# SESSION-HANDOFF — F211-a2 Contract Agreed

> 生成时间：2026-04-28 | Branch: cockpit | 阶段：F211-a2 🟡 contract_agreed
> 本 session 模型：Opus 4.7（Architect 模式 / Contract 协商）

---

## ⚠️ 当前两个 contract_agreed sprint（互不依赖，可并行开 session）

| Sub_sprint | 状态 | Contract |
|-----------|------|---------|
| **F206-c2** | 🟡 contract_agreed（PendingOrdersWidget 前端） | docs/开发/sprint-contracts/F206-c2-contract.md |
| **F211-a2** | 🟡 contract_agreed（per-task model override 基建） | docs/开发/sprint-contracts/F211-a2-contract.md |

---

## 1. F211-a2 Contract 摘要

### 范围

D064 三 tier 之上叠加**可选**的 per-task model override，env-driven、单 JSON 字段、fail-soft。
未配置 `AI_TASK_OVERRIDES_JSON` 时所有现有行为完全不变（877 测试零回归）。

### 5 文件清单

| # | 路径 | 操作 |
|---|------|------|
| 1 | `backend/app/config.py` | 修改：加 `ai_task_overrides_json: str = ""` 字段 |
| 2 | `backend/app/ai/routing.py` | 修改：新 `ResolvedRoute` dataclass + `_parse_overrides` + `resolve()` 升签；保留 `resolve_tier`/`resolve_model` 旧 API |
| 3 | `backend/app/ai/gateway.py` | 修改：`_call_litellm` 透传 `api_base` + 新 `_ensure_cost_registered` lazy hook（线程安全幂等） |
| 4 | `backend/tests/test_ai_routing_overrides.py` | 新建：13 用例（命中 / fallback / 损坏 JSON / register 幂等 / 异常吞咽）|
| 5 | `docs/系统设计/DECISIONS.md` | 追加 D075（D064 兄弟决策） |

测试扩展（不计入 5 文件，与 F211-a1 同处理）：
- `backend/tests/test_ai_core_modules_f208b.py`：1 处适配（resolve 返回 dataclass）
- `backend/tests/test_ai_gateway_e2e_f208c.py`：追加 C13c override e2e
- `.env.example`：追加 `AI_TASK_OVERRIDES_JSON=` 注释行

### 关键设计决定（已固化在 contract §1.2）

1. register_model 注入位置 = gateway lazy hook，**不**放 main.py lifespan
2. api_key fallback：`override.api_key` 空 → `settings.openai_api_key`（兼容现有 OPENAI_API_KEY）
3. cost 单位：用户填 per-1M-token；register 前 `/ 1_000_000`
4. fail-soft：JSON 损坏 / register 失败 → log warning + fallback，**绝不**阻塞 startup
5. 向后兼容：`resolve_tier` / `resolve_model` 旧签名保留，仅 `resolve()` 返回值变 dataclass

---

## 2. 开发顺序（Generator 模式严格执行）

1. **context7 查 `/websites/litellm`（CLAUDE.md 强制）**：
   - `litellm.completion()` 形参是 `api_base` 还是 `base_url`（版本敏感，contract Q1）
   - `litellm.register_model({...})` 当前签名 + `input_cost_per_token` 字段名（contract Q2）
   - `litellm.completion_cost(response, model=...)` 是否优先使用 register_model 注入的价
   - **若发现分歧** → 停下来更新 contract §1.1 代码草案 + D075 决策，再继续
2. config.py 加 `ai_task_overrides_json` 字段 → wip commit
3. routing.py 改签名 + override 解析 → 跑 13 个 routing override 单元测试 → wip commit
4. `.env.example` 加注释行 → wip commit
5. gateway.py `_ensure_cost_registered` + `_call_litellm` 透传 + `AiGateway.run` 调用方式 → 跑 e2e（含新 C13c）→ wip commit
6. test_ai_core_modules_f208b.py 适配 resolve 返回值 → 全量回归 `pytest backend/tests` → wip commit
7. DECISIONS.md 追加 D075 → wip commit
8. mypy 全绿 + smoke → 进 Evaluator 模式

---

## 3. Evaluator 自检清单（详见 contract §5）

测试通过性：13 routing 测试 + C13c e2e + test_ai_core_modules_f208b 适配 + 全量 ≥ 878 passed
代码质量：mypy 全绿；`_REGISTERED_COSTS` 测试间清理 fixture；保持 litellm lazy import；log.warning 用 `%s`
合约/文档同步：D075 已追加；`.env.example` 行已加；features.json sub_sprints["F211-a2"]=done + iteration_history
行为正确性：未配 override 行为完全等价；override 命中时 ai_memos.cost_usd ≠ 内置 pricing；JSON 坏时仍能 startup
consistency-check (mode=interactive)：C1（父 feature 因 b/c/d 未完保持 in_progress，**不**升 done）/ C4 / C5

---

## 4. 开放问题（contract §6，全采默认）

| Q# | 默认采 |
|----|--------|
| Q1 | 暂按 `api_base`，Generator 步骤 1 context7 验证后调整 |
| Q2 | Generator 步骤 1 验证 register_model 注入价是否被 completion_cost 使用；不行则手算 cost |
| Q3 | 不支持 extra_headers / timeout / max_retries（未来 a3 sprint） |
| Q4 | _REGISTERED_COSTS 不支持运行时清除（重启 backend 即可） |
| Q5 | 不在 startup 校验 override 的 task_type 属于 known_task_types |
| Q6 | 沿用 `Decimal(str(...))`，不额外 quantize |
| Q7 | 不增 `meta.route_source` 字段（meta.modelUsed 已足够区分） |

---

## 5. 下一步选项（独立 session）

### 选项 A：F211-a2 Generator（推荐 — 本次 Architect 产出物的直接落地）

**指令**：
```
继续开发 F211-a2，Sprint Contract 已确认。
读取 SESSION-HANDOFF.md + docs/开发/sprint-contracts/F211-a2-contract.md，
进入 Generator 模式，从开发步骤 1（context7 查 LiteLLM 形参与 register_model 行为）开始。
```

### 选项 B：F206-c2 Generator（PendingOrdersWidget 前端，与 a2 并行）

**指令**：
```
继续开发 F206-c2，Sprint Contract 已确认。
读取 SESSION-HANDOFF.md + docs/开发/sprint-contracts/F206-c2-contract.md，
进入 Generator 模式，从开发步骤 1 开始。
```

### 选项 C：F211-b（DecisionPanel Contradictions 区前端，新 contract 协商）

依赖 F211-a1 ✅，不依赖 a2，可并行。需在 Architect 模式起草新 contract。

---

## 6. F211 五段拆分当前状态

| sub_sprint | 范围 | 状态 |
|-----------|------|------|
| F211-a1 | 3 task schema + REGISTRY + guardrail | ✅ done |
| **F211-a2** | per-task model override 基建 | 🟡 contract_agreed |
| F211-b | DecisionPanel Contradictions 区前端 | ⬜ design_needed |
| F211-c | News 页 AI 摘要 bar 前端（tokens/cost 展示） | ⬜ design_needed |
| F211-d | 平仓 hook + journal_entries.ai_review 迁移 + 月度 cron | ⬜ design_needed |

依赖链：`a1 ✅ → {a2 / b / c / d}`，全部可并行。

---

## 7. 关键引用文档

- F211-a2 Contract：docs/开发/sprint-contracts/F211-a2-contract.md（**本 sprint 主文档**）
- F211-a1 Contract §8（骨架预览）：docs/开发/sprint-contracts/F211-a1-contract.md line 466-480
- F206-c2 Contract：docs/开发/sprint-contracts/F206-c2-contract.md
- D064 三 tier 决策：docs/系统设计/DECISIONS.md line 1378
- D069 ai_memos 双用途：docs/系统设计/DECISIONS.md line 1491
- D070 AI 配置走 .env：docs/系统设计/DECISIONS.md line 1512（特别 line 1527）
- 当前 routing.py：backend/app/ai/routing.py（45 行）
- 当前 gateway.py `_call_litellm`：backend/app/ai/gateway.py line 41-80
- Settings 类：backend/app/config.py line 35-43（v2.0 F208 AI Gateway 字段块）
- LiteLLM context7：`/websites/litellm`（Generator 步骤 1 强制查）

---

## 8. 历史快照

- **F211-a2**：🟡 contract_agreed（2026-04-28 Architect）
- **F211-a1**：✅ done（2026-04-28）
- **F210（critical-tier AI）**：✅ done
- **F209（default-tier AI）**：✅ done
- **F208（AI Gateway）**：✅ done
- **F207（Action List）**：✅ done
- **F206（Position Manager）**：🟡 in_progress（c2 contract_agreed）
- **F205**：✅ done
