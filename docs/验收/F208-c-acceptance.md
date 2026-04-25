# 验收记录：F208-c AI Gateway 主流程 + LiteLLM + endpoint

**日期**：2026-04-25  
**Feature**：F208-c  
**版本**：v2.0（Cockpit P2 AI 层）  
**验收结论**：✅ 通过  
**Sprint Contract**：docs/开发/sprint-contracts/F208-c-contract.md

---

## 测试门禁（Evaluator 已完成）

| 测试集 | 结果 |
|--------|------|
| §A Gateway 7 路径（mock LiteLLM） | 7/7 ✅ |
| §A 单元（guardrail no-op / register / lazy import 校验） | 3/3 ✅ |
| §B Endpoint envelope + 6 错误码 + OpenAPI 可见 | 10/10 ✅ |
| §C live smoke（gpt-5.4-nano 真实 OpenAI） | 1/1 ✅ |
| 全量回归（`-m 'not live'`） | 540 passed ✅ |

---

## 业务逻辑确认（验收时实测）

| # | 验证项 | 结果 |
|---|-------|------|
| B1 | `POST /api/ai/echo` → 422 VALIDATION_ERROR | ✅ |
| B2 | `POST /api/ai/unknown_xyz` → 422 VALIDATION_ERROR | ✅ |
| B3 | `POST /api/ai/market_narrator`（未注册）→ 422 `unregistered task_type` | ✅ |
| B4 | OpenAPI `/api/ai/{task_type}` 可见，task_type 枚举 7 个 | ✅ |
| B5 | Gateway 7 路径：success / cache / no_cache / budget / provider / schema / guardrail | ✅ |
| B6 | camelCase envelope（memoId / taskType / cacheHit / tokensIn 等 alias） | ✅ |
| B7 | live smoke：echo task 真实 OpenAI，cost_usd > 0，memo 写入 | ✅ |

---

## Evaluator 发现并修复（验收期间）

| 问题 | 修复 | 决策 |
|------|------|------|
| `litellm.completion_cost(response)` 对 OpenAI 版本化 model name（`gpt-5.4-nano-2026-03-17`）查价失败，cost_usd=0 | `completion_cost(response, model=model)` 显式传短名 | D072 |

---

## 确认决策

| 项 | 决定 |
|---|------|
| AiGateway.run 103 行（超 §5.2 50 行约束） | 用户批准豁免（D071）—— 11 步线性编排，注释即步骤标签 |

---

## 验收结论

用户确认通过（2026-04-25）。

**F208 全系列状态**：
- F208-a（AI 基座 + ai_memos 表）：✅ done
- F208-b（core modules: errors / memo_repo / budget / routing）：✅ done
- F208-c（AiGateway 编排 + LiteLLM + endpoint）：✅ done

F209（Market Narrator + Setup Explainer）可以启动。
