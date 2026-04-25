# SESSION HANDOFF

> 生成时间：2026-04-25
> 当前阶段：F208 全系列完成（a/b/c 均 done）→ 下一个 F209
> 当前 branch：cockpit

---

## F208 完成状态

| Feature | 内容 | 状态 |
|---------|------|------|
| F208-a | AI 基座 + ai_memos 表 + LiteLLM 依赖 + 配置 | ✅ done |
| F208-b | core modules: errors / memo_repo / budget / routing | ✅ done |
| F208-c | AiGateway 编排 + LiteLLM + POST /api/ai/{task_type} | ✅ done |

---

## 下一个 Feature：F209

**F209**：Market Narrator + Setup Explainer

- 两个 AI task，均走 `default` tier（`gpt-5.4-nano`）
- 后端：在 `backend/app/ai/schemas/` 新建各自 schema 文件，在 `REGISTRY` 注册
- 前端：两个 Workbench widget，调 `/api/ai/market_narrator` + `/api/ai/setup_explainer`
- 不动 gateway / endpoint 框架代码

---

## 关键技术背景（接 F209 必读）

### AI Gateway 架构（F208 完成的基座）

```
POST /api/ai/{task_type}
  → routers/ai.py（7 Literal enum + camelCase envelope）
  → AiGateway.run(task_type, input_dict, no_cache=False)
      1. schemas.get_schemas(task_type) → (input_schema, output_schema)
      2. input_schema(**input_dict) 校验
      3. compute_input_hash
      4. find_cached（TTL + schema_version）→ 命中直接返回
      5. assert_within_budget
      6. routing.resolve(task_type) → (tier, model_id)
      7. _call_litellm(model, input_dict, output_schema, api_key)
      8. output_schema(**raw) 校验
      9. guardrail.run
      10. AiMemoRepository.write
      11. 返回 GatewayResult
```

### F209 只需做的事

```python
# backend/app/ai/schemas/market_narrator.py
from pydantic import BaseModel
from app.ai.schemas import REGISTRY, SchemaPair

class MarketNarratorInput(BaseModel):
    symbol: str
    # ... 其他字段（对照 API-CONTRACT F209 章节）

class MarketNarratorOutput(BaseModel):
    narrative: str
    # ...

REGISTRY["market_narrator"] = SchemaPair(MarketNarratorInput, MarketNarratorOutput)
```

然后在 `schemas/__init__.py` import 这个文件让注册生效。

### D072 重要提示

`litellm.completion_cost(response)` 必须传 `model=model` 参数，否则 OpenAI 返回的版本化名称（`gpt-5.4-nano-2026-03-17`）会导致查价失败，cost_usd=0。gateway.py 已修复，F209 测试中注意验证。

### live smoke 运行方式

```bash
cd backend
set -a && source .env && set +a
uv run pytest tests/ -m live -s -v
```

（pytest 不自动 source .env，必须显式 export）

---

## 下一 Session 启动指令

```
准备开发 F209（Market Narrator + Setup Explainer）。

请读取：
- SESSION-HANDOFF.md
- docs/需求/features.json（F209 条目）
- docs/系统设计/API-CONTRACT.md（F209 相关接口）
- docs/系统设计/DATA-MODEL.md（AiMemo 字段权威）

进入 feature-dev Sprint Contract 协商流程。
```

---

## git 状态

branch：cockpit
最近 commits：
- f051313 chore(F208-c): 验收通过 → done
- 82026f8 chore(F208-c): Evaluator 通过 → needs_review + D072 cost fix
- 862cee6 wip(F208-c): AiGateway main flow + LiteLLM lazy import + /api/ai/{task_type} endpoint
