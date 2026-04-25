# SESSION HANDOFF

> 生成时间：2026-04-25
> 当前阶段：F209-a Sprint Contract 已确认 → 待新 session 进入 Generator 模式
> 当前 branch：cockpit

---

## 本 session 完成的事

**F209-a：AI 后端 schema 注册（market_narrator + setup_explainer）— Sprint Contract 协商**

| 输出 | 状态 |
|------|------|
| `docs/开发/sprint-contracts/F209-a-contract.md` | ✅ 新建（草案 → 已确认） |
| `docs/需求/features.json` F209-a phase | ✅ design_ready → contract_agreed |
| `claude-progress.txt` | ✅ 追加协商记录 |

**用户已确认 4 项**（§8）：
1. ✅ §1.1 范围（4 文件、不改 gateway/router）
2. ✅ §6 D-1：schema 字段命名 camelCase（与 API-CONTRACT 示例一致）
3. ✅ §6 约束-2：SYSTEM_PROMPT 仅写入常量，不接入 LiteLLM messages
4. ✅ §3 完成标准 + §5 自检清单

---

## Sprint Contract 摘要（详见 contract 文件）

### 实现范围
- **`backend/app/ai/schemas/market_narrator.py`**（新建，~110 行）
  - `MarketNarratorInput`：regime / marketScore / subscores / sectors（嵌套 BaseModel）
  - `MarketNarratorOutput`：headline / summary / riskPosture / preferredSetups / avoid / warnings
  - 模块常量：`SCHEMA_VERSION="v1"` / `SYSTEM_PROMPT` / `BANNED_PHRASES`（6 条）
  - `def guardrail(input_dict, output_dict)`：扫描 output 文本击中 BANNED_PHRASES 抛 `AiGuardrailViolation`

- **`backend/app/ai/schemas/setup_explainer.py`**（新建，~80 行）
  - `SetupExplainerInput`：ticker / trend / rs / setup / risk(entry, stop)
  - `SetupExplainerOutput`：label / quality / whyWatch / mainRisks
  - 同样 SCHEMA_VERSION + SYSTEM_PROMPT + BANNED_PHRASES + guardrail 函数

- **`backend/app/ai/schemas/__init__.py`**（修改 +10 行）
  - import 两个新模块 + `app.ai.guardrail`
  - REGISTRY 追加两条 SchemaPair；删除 6 条占位注释
  - `_gr.register("market_narrator", _mn.guardrail)` / 同理 setup_explainer（模块加载副作用）

- **`backend/tests/test_ai_schemas_f209.py`**（新建，~280 行）
  - §A schema 字段约束（Pydantic 单测）
  - §B REGISTRY 注册校验
  - §C guardrail 注册副作用 + 6 条禁词命中
  - §D endpoint 端到端（mock LiteLLM + TestClient）+ 422/409 错误码
  - §E live smoke `@pytest.mark.live`（market_narrator 1 次，验证 D072 cost fix）

### 关键决策
- **字段命名 = camelCase**（D-1 → 落地为 DECISIONS.md D074）
- **SYSTEM_PROMPT 暂不接入 LiteLLM messages**（接入留给后续 chore sprint）
- **Live smoke 仅跑 market_narrator**（省 token；setup_explainer 走 mock 集成）

### 完成标准（13 条，详见 contract §3）
schema 字段约束 / REGISTRY 注册 / guardrail 注册 / 6 条禁词 / 两个 endpoint 端到端 mock 集成 / 错误码映射 / live smoke 真实计费 / 全量回归 0 失败 / lazy import litellm。

---

## 开发顺序（Generator 模式遵循）

| Step | 内容 | wip commit |
|------|------|-----------|
| 1 | `market_narrator.py`（含嵌套类 + 常量 + guardrail 函数） | `wip(F209-a): step1 market_narrator schema` |
| 2 | `setup_explainer.py`（同结构） | `wip(F209-a): step2 setup_explainer schema` |
| 3 | `schemas/__init__.py` import + REGISTRY + guardrail.register | `wip(F209-a): step3 registry + guardrail wiring` |
| 4 | tests §A+§B+§C 单元测试 | `wip(F209-a): step4 unit tests` |
| 5 | tests §D 集成测试（mock LiteLLM + TestClient） | `wip(F209-a): step5 endpoint integration tests` |
| 6 | tests §E live smoke skeleton | `wip(F209-a): step6 live smoke` |
| 7 | Evaluator：全量回归 + 自检清单 + DECISIONS.md D074 + features.json phase=needs_review + 终态 commit | `feat(F209-a): ...` |

---

## 关键引用文档

- Contract：`docs/开发/sprint-contracts/F209-a-contract.md`
- API-CONTRACT.md §POST /api/ai/{task_type}（line 1653-1734，含 market_narrator 输入/输出示例）
- F208-c 测试参考：`backend/tests/test_ai_gateway_e2e_f208c.py`（§B fixture `market_narrator_schema` 范式可复用）
- 已存在的 schemas：`backend/app/ai/schemas/__init__.py`（echo 占位 + 6 条注释将被替换）
- guardrail 框架：`backend/app/ai/guardrail.py`（registry pattern，支持 register + run）

---

## features.json 当前状态

| Feature | Phase | 说明 |
|---------|-------|------|
| F201-c | ✅ done | MarketRegimeWidget |
| **F209-a** | 🤝 contract_agreed | AI 后端 schema 注册（待 Generator） |
| F209-b | ⬜ design_ready | Market Narrator 前端（依赖 F209-a） |
| F209-c | ⬜ design_ready | Setup Explainer popover（依赖 F209-a + F209-b + F202-c） |

---

## ⚠️ 下一 Session 必读

1. 用 **Sonnet** 新开 session（避免烧 Opus 跑 Generator）
2. 第一条消息粘贴：

```
继续开发 F209-a，Sprint Contract 已确认。
读取 SESSION-HANDOFF.md + docs/开发/sprint-contracts/F209-a-contract.md，
进入 Generator 模式，从开发步骤 1（market_narrator.py）开始。
```

3. Generator 模式铁律：
   - 每 step 完成立即 wip commit，禁用 `git add -A`，按文件名显式 add
   - 步骤间不跳序、不批量
   - 遇到 contract 范围外的需求停下来报告，不自行扩张
   - Evaluator 阶段全量 `pytest backend/tests/` 0 失败才能流转 needs_review

4. 字段命名已锁定 camelCase，不要被 features.json AC 中"内部 snake_case"误导（该写法已在 contract §6 D-1 标记为不实施，原因：与"不改 gateway/router"冲突）

---

## git 状态

branch：cockpit
最近 commits：
- 3ece838 chore(F201-c): features.json phase→done + progress log + SESSION-HANDOFF
- 33266b4 feat(F201-c): MarketRegimeWidget — 65 tests pass

本 session 待 commit 的改动（chore 类，应在结束前独立 commit）：
- `docs/开发/sprint-contracts/F209-a-contract.md`（新建）
- `docs/需求/features.json`（F209-a phase + last_updated）
- `claude-progress.txt`（协商记录）
- `SESSION-HANDOFF.md`（本文件）

建议提交 message：
```
chore(F209-a): Sprint Contract 协商完成（contract_agreed）+ SESSION-HANDOFF
```
