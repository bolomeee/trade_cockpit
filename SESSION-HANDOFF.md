# SESSION HANDOFF

> 生成时间：2026-04-25
> 当前阶段：F208-c Evaluator 完成 → needs_review
> 下一阶段：用户验收 F208-c（acceptance skill）→ F209 开发

---

## 当前状态

**F208-c** Evaluator 全 23 条自检通过，status 已更新为 `needs_review`。

待用户验收后：
1. 执行 acceptance skill 完成 F208-c → `done`
2. 开始 F209（Market Narrator + Setup Explainer）Sprint Contract

---

## F208-c Evaluator 评估报告摘要

### 测试结果

| 测试集 | 结果 |
|--------|------|
| §A Gateway 7 路径（mock LiteLLM） | 7/7 ✅ |
| §A 单元（guardrail no-op / register / lazy import） | 3/3 ✅ |
| §B Endpoint envelope + 6 错误码 + OpenAPI | 10/10 ✅ |
| §C live smoke（gpt-5.4-nano 真实调 OpenAI） | 1/1 ✅ |
| 全量回归（-m 'not live'） | 540 passed ✅ |

### Evaluator 发现并修复的 Bug（D072）

**现象**：live smoke `cost_usd = Decimal("0")`，测试断言 `> 0` 失败。

**根因**：OpenAI 返回 `response.model = 'gpt-5.4-nano-2026-03-17'`（带日期版本号），`litellm.completion_cost(response)` 用 `response.model` 查定价库但查不到 → 抛异常 → `except Exception` 兜底 → `Decimal("0")`。

**修复**：`gateway.py:76` 改为 `litellm.completion_cost(response, model=model)`，显式传入我们发送的短名。

**教训（已存 memory）**：凡调用 `litellm.completion_cost(response)` 必须显式传 `model=` 参数。

### 代码质量决策（D071）

`AiGateway.run` 103 行 > §5.2 的 50 行约束。用户选择豁免：11 步线性流程，注释即步骤标签，拆方法不提升可读性。DECISIONS.md D071 已记录。

---

## 文件变更汇总（F208-c 全程）

| 文件 | 状态 |
|------|------|
| `backend/app/ai/gateway.py` | 新建（178 行，Evaluator 修复 L76） |
| `backend/app/ai/guardrail.py` | 新建（22 行） |
| `backend/app/ai/schemas/__init__.py` | 新建（44 行） |
| `backend/app/routers/ai.py` | 新建（105 行） |
| `backend/app/main.py` | 修改（+2 行） |
| `backend/app/ai/routing.py` | 修改（+1 行） |
| `backend/tests/test_ai_gateway_e2e_f208c.py` | 新建（434 行） |
| `backend/tests/test_ai_core_modules_f208b.py` | 维护（断言修复） |
| `docs/系统设计/DECISIONS.md` | 追加 D071 + D072 |
| `docs/需求/features.json` | F208-c → needs_review / eval_passed |

### Git commits（本 feature）

- `1f6b6e0` chore(F208-c): Sprint Contract 协商完成 → contract_agreed
- `862cee6` wip(F208-c): AiGateway main flow + LiteLLM lazy import + /api/ai/{task_type} endpoint
- 待 commit：Evaluator 修复（gateway.py L76 + DECISIONS + features.json + claude-progress.txt）

---

## 下一步

### 用户验收 F208-c

运行以下命令进行冒烟验证（可选）：

```bash
# 后端启动
cd backend && uv run uvicorn app.main:app --reload

# 验证 endpoint 可见
curl http://localhost:8000/openapi.json | python -m json.tool | grep -A5 'api/ai'

# 验证 7 Literal 枚举
curl -X POST http://localhost:8000/api/ai/echo \
  -H "Content-Type: application/json" \
  -d '{"input": {"text": "test"}}' 
# 预期 422 VALIDATION_ERROR（echo 不在 7 enums）
```

验收通过后执行 acceptance skill。

### 验收通过后：F209 开发

**F209**：Market Narrator + Setup Explainer（default tier，走 gpt-5.4-nano）

Sprint 要点：
1. 在 `backend/app/ai/schemas/` 新建 `market_narrator.py` + `setup_explainer.py`
2. 在 `REGISTRY` 注册两个 schema
3. 前端两个 widget 调 `/api/ai/market_narrator` + `/api/ai/setup_explainer`
4. 不动 gateway / endpoint 代码

---

## 环境注意事项

- **live smoke 运行方式**：`set -a && source backend/.env && set +a && uv run pytest ... -m live`（pytest 不自动 source .env）
- **gpt-5.4-nano**：OpenAI 返回版本化名称，LiteLLM completion_cost 必须传 `model=` 参数（D072 已修复）
- **全量回归**：`cd backend && uv run pytest -m 'not live' -q`（4s 内完成）
