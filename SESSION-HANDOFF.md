# SESSION HANDOFF

> 生成时间：2026-04-25
> 当前 Skill：feature-dev（F208-c Sprint Contract 协商完成）
> 当前 Feature：F208-c — AI Gateway 主流程 + LiteLLM 集成 + `/api/ai/{task_type}` endpoint
> 上一阶段：F208-b 用户验收通过 → done
> 本阶段：F208-c Sprint Contract 草案 → 用户 6 项全确认 → 已确认
> 下一阶段：F208-c Generator 模式（建议开新 session，Sonnet）

---

## 完成的内容（本 session）

1. 读取：CLAUDE.md / SESSION-HANDOFF.md / features.json / F208-b-contract.md / DATA-MODEL §AiMemo / API-CONTRACT §POST /api/ai/{task_type} / DECISIONS D064/D068/D069 / 现有 backend/app/ai/ 4 个模块 / main.py / routers/cockpit/__init__.py / sprint-contract-template.md
2. 文件清单清点：原计划 7 文件超限，压缩到 6 文件（envelope 内联 routers/ai.py）
3. 起草 F208-c Sprint Contract 草案
4. 用户提出加 OpenAI key live smoke，Contract 调整：移除 §1.2 "live smoke 排除"、追加 §1.1.6 §C live smoke 测试块、追加 §3 标准 #15、追加 §5 live smoke 自检 4 项
5. 用户 6 项确认全部 ✅，Contract 状态 → 已确认
6. 文档同步：features.json + claude-progress.txt + 本文件重写

---

## Sprint Contract 摘要

### 实现范围（6 主文件 + 1 微调）

| # | 文件 | 改动 | 内容 |
|---|------|------|------|
| 1 | `backend/app/ai/gateway.py` | 新建 | `AiGateway` 类 + `_call_litellm` lazy import + `GatewayResult/Meta` dataclass |
| 2 | `backend/app/ai/guardrail.py` | 新建 | `register/run` + 模块级 `_HOOKS` 注册表，默认 no-op |
| 3 | `backend/app/ai/schemas/__init__.py` | 新建 | `SchemaPair` NamedTuple + `REGISTRY` dict + 内置 echo 测试 task |
| 4 | `backend/app/routers/ai.py` | 新建 | endpoint + Request/Response envelope（内联）+ 错误码映射 |
| 5 | `backend/app/main.py` | 修改 2 行 | import + include_router(prefix="/api/ai") |
| 6 | `backend/tests/test_ai_gateway_e2e_f208c.py` | 新建 | §A 7 路径 + §B endpoint + §C live smoke |

附加微调（不计入主清单）：
- `backend/app/ai/routing.py` — `_TASK_TIER` 加一行 `"echo": "default"` + "test-only" 注释

### 关键技术决策

- **LiteLLM lazy import**：`import litellm` 仅在 `_call_litellm()` 函数内部，gateway 模块顶层 import 不依赖 litellm（便于离线 CI / 减少启动开销）
- **写 memo 仅在 guardrail 通过后**：provider/schema/budget/guardrail 错误均不写表
- **echo task**：仅 F208-c 自测桩，**不**在 API-CONTRACT 7 enums 内 → `POST /api/ai/echo` HTTP 应 422，echo 测试通过 `AiGateway.run("echo", ...)` 直调（绕过 endpoint）
- **endpoint Literal 校验**：严格只接受 7 个生产 task_type（market_narrator / setup_explainer / candidate_ranker / trade_plan / contradiction_detector / news_summarizer / journal_assistant）
- **错误码映射**：复用既有 `APIError` + `main.py` 现成 `handle_api_error` JSON handler，不新增 handler
- **测试 §B 临时注册**：用 fixture try/finally 保证 cleanup，避免 REGISTRY 全局污染

### 测试覆盖（§3 共 15 条标准）

- §A：gateway 7 路径（success / cache hit / cache miss / no_cache=True / budget 超限 / output schema 失败 / guardrail 违规）—— 用 echo + monkeypatch `_call_litellm`
- §B：endpoint envelope alias + 6 个错误码映射 —— TestClient + 临时注册 market_narrator schema
- §C：1 条 `@pytest.mark.live` live smoke —— 真实打 OpenAI（echo），未设 `OPENAI_API_KEY` 时 `pytest.skip`，默认 `pytest -m 'not live'` 不触发

### 开发顺序（§4，Generator 模式必须按此推进）

1. `schemas/__init__.py` — SchemaPair + REGISTRY + echo
2. `guardrail.py` — register/run + _HOOKS
3. `routing.py` 微调 — 加 echo 一行（含注释）
4. `gateway.py` — `_call_litellm` lazy import + `AiGateway.run()` 主流程
5. `routers/ai.py` — endpoint + envelope + 错误码映射
6. `main.py` — 注册 router 2 行
7. 测试 §A（7 路径）→ wip commit
8. 测试 §B（endpoint）→ wip commit
9. 单模块回归 + 全量回归（≥ 520 基线）
10. （可选）测试 §C live smoke：用户提供 key 后跑一次

每完成一步且通过最小验证（编译/类型/单测）立即按 §2 文件清单 wip commit（禁用 `git add -A`）。

---

## 用户提供的 OpenAI Key 处理约定

- 用户在 `backend/.env` 中设置 `OPENAI_API_KEY=sk-...`（`.env` 已在仓库根 `.gitignore` 第 5 行覆盖）
- F208-a 已落地的 `settings.openai_api_key` 字段直接读取
- live smoke `pytest -m live` 跑一次：echo task → 真实 OpenAI → ai_memos 写入真实 row（cost_usd > 0）
- key 绝不出现在代码 / 测试常量 / git 历史 / log

---

## 文件状态（本 session 改动）

| 文件 | 改动 |
|------|------|
| `docs/开发/sprint-contracts/F208-c-contract.md` | 新建（Contract 草案 → 已确认） |
| `docs/需求/features.json` | F208-c：status `planned`→`in_progress`，phase `design_ready`→`contract_agreed`，estimated_files_changed 改为 6 主文件 + minor，acceptance_criteria + test_cases 增加 live smoke；last_updated；active_sprint_phase `design_ready`→`contract_agreed` |
| `claude-progress.txt` | 追加 F208-c Contract 协商条目 |
| `SESSION-HANDOFF.md` | 本文件（重写） |

---

## 遗留事项

无新决策（D064/D068/D069 已覆盖；如 Generator 阶段发现偏离需追加 DECISIONS）。

> ⚠️ Generator 阶段必须用 context7 查询当前版本 LiteLLM（`>=1.83,<2.0`，pyproject 已 pin）的 `completion(response_format=Pydantic)` / `completion_cost()` / `usage` 字段语义，**不得凭记忆编写**（CLAUDE.md "开发时文档查询" 强制规则）。

---

## 下一步

**强制停止本 session**。Contract 已确认但 Generator 不在本 session 进行（feature-dev skill A-1 末尾铁律）。

### 下一个 Session 继续的指令

```
继续开发 F208-c，Sprint Contract 已确认。

请按顺序读取：
- SESSION-HANDOFF.md
- docs/开发/sprint-contracts/F208-c-contract.md（本 sprint 实现合约）
- CLAUDE.md（项目约束）
- docs/系统设计/DATA-MODEL.md（§AiMemo，13 列字段权威）
- docs/系统设计/API-CONTRACT.md（§POST /api/ai/{task_type} envelope 与错误码）
- docs/系统设计/DECISIONS.md（D064 / D068 / D069）
- backend/app/ai/（确认 F208-b 4 个模块 errors/memo_repo/budget/routing 已就位）
- backend/app/main.py（确认现有 router 注册结构）

进入 Generator 模式，从 Contract §4 开发顺序 step 1（schemas/__init__.py）开始。

⚠️ Generator 强制规则：
- 每步通过最小验证后立即 wip commit（禁用 git add -A，按 §2 文件清单显式 add）
- LiteLLM 集成前先用 context7 查询 `>=1.83,<2.0` 当前 API（completion / response_format / completion_cost / usage 字段）
- gateway.py 顶层不得 `import litellm`（懒加载 §3 #13）
- 错误码映射严格对照 API-CONTRACT，不自行发明
- echo 仅 F208-c 自测，不暴露给 endpoint Literal
- 用户已提供 OpenAI key（在 backend/.env 中）：live smoke 阶段直接跑 `uv run pytest tests/test_ai_gateway_e2e_f208c.py -m live`
```

建议用 **Sonnet** 模型开新 session 执行 Generator（成本更低，速度更快，本 sprint 文件量适中）。
