# Sprint Contract：F209-a — AI 后端 schema 注册（market_narrator + setup_explainer）

> 状态：草案，待用户确认 | 起草：2026-04-25
> 父 Feature：F209 Market Narrator + Setup Explainer（v2.0 Cockpit P2 AI 层）
> 兄弟：**F209-a（后端 schema，本 sprint）** / F209-b（Market Narrator 前端集成）/ F209-c（Setup Explainer Popover）
> 依赖：F208-c ✅ done（gateway 编排 + `/api/ai/{task_type}` + REGISTRY 已就位）
> 引用文档：
>   - API-CONTRACT.md §POST /api/ai/{task_type}（统一 envelope、错误码、market_narrator 输入/输出示例 line 1733-1734）
>   - DATA-MODEL.md §Entity: AiMemo（写入字段权威；不改）
>   - DECISIONS.md D064（LiteLLM + 单一动态 endpoint + tier 三档）
>   - DECISIONS.md D068（guardrail post-validate 框架）
>   - DECISIONS.md D069（ai_memos 双用途，TTL + schema_version 命中规则）
>   - DECISIONS.md D072（cost_usd 修复，本 sprint live smoke 须验证仍生效）
>   - features.json#F209-a acceptance_criteria

---

## 0. 背景与定位

F208-c 完成后，`backend/app/ai/` 已具备：
- `AiGateway.run(task_type, input_dict, no_cache)` 主流程
- `POST /api/ai/{task_type}` 统一 endpoint（7 个 task_type Literal 已枚举）
- `schemas/__init__.py` REGISTRY（仅含内部测试用 `echo` task）
- `routing.py` task→tier 映射（`market_narrator`/`setup_explainer` → `default`，已就位）
- `guardrail.py` registry（默认 no-op，可注册 hook）

本 sprint 在不改 gateway / router / routing 框架的前提下，**以纯"添加 schema 文件 + 注册"的方式**落地 F209 的两个 task：
1. `market_narrator`：根据 regime / marketScore / subscores / sectors，输出 headline + summary + riskPosture + preferredSetups + avoid + warnings
2. `setup_explainer`：根据 ticker / trend / rs / setup / risk，输出 label + quality + whyWatch + mainRisks

完成后 F209-b/F209-c 前端可直接调 `POST /api/ai/market_narrator` 与 `POST /api/ai/setup_explainer`，envelope 完全复用 F208-c 已有路径。

---

## 1. 实现范围

### 1.1 包含

#### 1.1.1 `backend/app/ai/schemas/market_narrator.py`（新建）

定义两个 Pydantic v2 BaseModel：

- `MarketNarratorInput`
  - 字段（**字段名 = camelCase，与 API-CONTRACT 示例 line 1733 完全一致**）：
    - `regime: Literal["RISK_ON","CONSTRUCTIVE","NEUTRAL","DEFENSIVE","RISK_OFF"]`
    - `marketScore: int = Field(ge=0, le=100)`
    - `subscores: MarketNarratorSubscores`（嵌套 BaseModel，6 个 int 字段：`spyTrend / qqqTrend / iwmBreadth / sectorParticipation / riskAppetite / volatilityStress`，全部 `ge=0`）
    - `sectors: list[MarketNarratorSector]`（嵌套 BaseModel：`symbol: str`，`closePct: float`，`state: Literal["Strong","Neutral","Weak"]`）
  - `model_config = {"extra": "forbid"}`
- `MarketNarratorOutput`
  - 字段（camelCase，与 API-CONTRACT line 1734 一致）：
    - `headline: str = Field(min_length=1, max_length=120)`
    - `summary: str = Field(min_length=1, max_length=600)`
    - `riskPosture: Literal["aggressive","balanced","cautious","defensive"]`
    - `preferredSetups: list[str] = Field(min_length=0, max_length=5)`
    - `avoid: list[str] = Field(min_length=0, max_length=5)`
    - `warnings: list[str] = Field(min_length=0, max_length=5)`
  - `model_config = {"extra": "forbid"}`
- 模块级常量：
  - `SCHEMA_VERSION = "v1"`
  - `SYSTEM_PROMPT: str` —— 给 LiteLLM 的系统指令（说明任务、字段含义、禁词约束）。**注**：F208-c 当前 `_call_litellm` 仅传 `messages=[{"role":"user", content=json}]`，未拼接 system prompt（见下方 §6 "已知约束 / 待决策"）。本 sprint 把 SYSTEM_PROMPT 写入模块文件以备后续接入；不改 gateway。
  - `BANNED_PHRASES: tuple[str, ...] = ("buy now", "sell now", "保证收益", "承诺收益", "忽略止损", "ignore stop")`
- 模块级函数：
  - `def guardrail(input_dict: dict, output_dict: dict) -> None:` 扫描 output 中的 `headline / summary / preferredSetups / avoid / warnings` 文本（拼接后小写），命中任一 `BANNED_PHRASES` 则 `raise AiGuardrailViolation(f"banned phrase: {phrase}")`。

#### 1.1.2 `backend/app/ai/schemas/setup_explainer.py`（新建）

- `SetupExplainerInput`
  - 字段：
    - `ticker: str = Field(min_length=1, max_length=10, pattern=r"^[A-Z][A-Z0-9.\-]*$")`
    - `trend: Literal["up","down","sideways"]`
    - `rs: float`（relative strength，允许任意 float，前端传什么是什么）
    - `setup: Literal["pullback","breakout","reversal","range","gap_fill"]`
    - `risk: SetupRisk`（嵌套 BaseModel：`entry: float`，`stop: float`；均 `gt=0`）
  - `model_config = {"extra": "forbid"}`
- `SetupExplainerOutput`
  - 字段：
    - `label: str = Field(min_length=1, max_length=60)`
    - `quality: Literal["A","B","C","D"]`
    - `whyWatch: str = Field(min_length=1, max_length=400)`
    - `mainRisks: list[str] = Field(min_length=1, max_length=5)`
  - `model_config = {"extra": "forbid"}`
- 模块级 `SCHEMA_VERSION = "v1"`、`SYSTEM_PROMPT`、`BANNED_PHRASES`（同上 6 条），以及 `guardrail(input_dict, output_dict)` 函数（扫描 `label / whyWatch / mainRisks`）。

#### 1.1.3 `backend/app/ai/schemas/__init__.py`（修改）

- 顶部新增 import：
  ```python
  from app.ai.schemas import market_narrator as _mn
  from app.ai.schemas import setup_explainer as _se
  from app.ai import guardrail as _gr
  ```
- 在 `REGISTRY` 中追加两行（保留 `echo`，删除两条注释占位）：
  ```python
  "market_narrator": SchemaPair(_mn.MarketNarratorInput, _mn.MarketNarratorOutput),
  "setup_explainer": SchemaPair(_se.SetupExplainerInput, _se.SetupExplainerOutput),
  ```
- 模块加载副作用：注册 guardrail
  ```python
  _gr.register("market_narrator", _mn.guardrail)
  _gr.register("setup_explainer", _se.guardrail)
  ```
  （用 `_gr` 别名，避免与 task 名 `guardrail` 字符串混淆）

#### 1.1.4 `backend/tests/test_ai_schemas_f209.py`（新建）

测试分组（pytest class 组织）：

- **§A — Schema 字段约束**（纯 Pydantic 单测，不碰 gateway/db）
  - `MarketNarratorInput` 接受 API-CONTRACT 示例输入；`extra` 字段被拒（ValidationError）；`marketScore` 越界（-1 / 101）被拒；`regime` 非枚举值被拒。
  - `MarketNarratorOutput` 同理：`headline=""` 被拒；`riskPosture="bullish"` 被拒（非枚举）；`extra` 字段被拒。
  - `SetupExplainerInput`：`ticker="aapl"` 被拒（pattern 大写）；`risk.entry<=0` 被拒；`extra` 字段被拒。
  - `SetupExplainerOutput`：`quality="E"` 被拒；`mainRisks=[]` 被拒（min_length=1）；`extra` 字段被拒。

- **§B — Registry 注册**
  - `from app.ai.schemas import REGISTRY, get_schemas`
  - `"market_narrator" in REGISTRY` 且 `get_schemas("market_narrator")` 返回 `SchemaPair`，`.input_schema is MarketNarratorInput`，`.output_schema is MarketNarratorOutput`。
  - `"setup_explainer"` 同理。

- **§C — Guardrail 注册副作用**
  - `from app.ai import guardrail as gr`
  - `gr._HOOKS["market_narrator"]` 等于 `market_narrator.guardrail`（identity check）；`setup_explainer` 同理。
  - 直接调 `market_narrator.guardrail({}, {"headline":"go buy now!", "summary":"...", "riskPosture":"aggressive", "preferredSetups":[], "avoid":[], "warnings":[]})` 抛 `AiGuardrailViolation` 且消息含 `"buy now"`。
  - 同函数对干净 output 不抛异常。
  - 中文禁词测试：`{"summary":"我们承诺收益翻倍"}` 类似 fixture 同样抛 `AiGuardrailViolation`。

- **§D — Endpoint 端到端（mock LiteLLM，复用 F208-c §B 风格）**
  - `POST /api/ai/market_narrator` with API-CONTRACT 示例 input：mock `_call_litellm` 返回合法 `MarketNarratorOutput` dict + cost=Decimal("0.001234")，断言 200、envelope 形如 `{data:{memoId, taskType:"market_narrator", schemaVersion:"v1", output:{...}, meta:{costUsd:0.001234, modelUsed, tier:"default", ...}}, message:"success"}`，且 `ai_memos` 表新增 1 行 `cost_usd > 0`（**D072 验证点**）。
  - `POST /api/ai/setup_explainer` 同理。
  - `POST /api/ai/market_narrator` mock 返回 `{"headline":"buy now!", ...}` → 409 `AI_GUARDRAIL_VIOLATION`，`ai_memos` 不新增行。
  - `POST /api/ai/market_narrator` body 缺少 `marketScore` → 422 `VALIDATION_ERROR`。

- **§E — Live smoke（`@pytest.mark.live`，缺 `OPENAI_API_KEY` 自动 skip）**
  - 单 case：真实调 `AiGateway(db).run("market_narrator", input_dict=API-CONTRACT 示例, no_cache=True)`，断言 `result.meta.cost_usd > 0`、`result.output` 通过 `MarketNarratorOutput` 校验、`ai_memos` 行 `cost_usd > 0`（**D072 fix 持续生效证据**）。
  - **不**同时跑 setup_explainer live，避免 token 浪费；features.json 仅要求 cost fix 在新 task 上验证一次。

### 1.2 不包含（明确排除）

- ❌ 修改 `gateway.py` / `routers/ai.py` / `routing.py`（"不改 gateway/router 框架"）
- ❌ 拼接 SYSTEM_PROMPT 到 LiteLLM `messages`（gateway 当前不支持，本 sprint 仅写入模块常量备用，见 §6）
- ❌ 任何前端改动（F209-b / F209-c 各自 sprint）
- ❌ 新增其他 5 个 task（candidate_ranker / trade_plan / contradiction_detector / news_summarizer / journal_assistant — 留给 F210/F211）
- ❌ 修改 `tokens.css` / 设计相关文件
- ❌ 修改 DATA-MODEL.md / API-CONTRACT.md（已含 F209 占位，无需新增）

---

## 2. 预计修改文件清单（共 4 个）

| # | 文件 | 操作 | 行数估计 |
|---|------|------|---------|
| 1 | `backend/app/ai/schemas/market_narrator.py` | 新建 | ~110 |
| 2 | `backend/app/ai/schemas/setup_explainer.py` | 新建 | ~80 |
| 3 | `backend/app/ai/schemas/__init__.py` | 修改（+10 行） | — |
| 4 | `backend/tests/test_ai_schemas_f209.py` | 新建 | ~280 |

未超 6 文件上限。

---

## 3. 完成标准

| # | 标准（可测试） | 测试层级 | 工具 / 位置 |
|---|---------------|---------|-----------|
| 1 | `MarketNarratorInput/Output` Pydantic v2，`extra="forbid"`，字段名与 API-CONTRACT 示例完全一致 | 单元 | §A pytest |
| 2 | `SetupExplainerInput/Output` 同上 | 单元 | §A pytest |
| 3 | 字段约束（regime / riskPosture / quality / setup Literal、ticker pattern、score 范围、文本长度） | 单元 | §A pytest |
| 4 | `REGISTRY["market_narrator"]` 与 `REGISTRY["setup_explainer"]` 存在，`get_schemas()` 可取出正确类 | 单元 | §B pytest |
| 5 | guardrail.\_HOOKS 在模块加载时被注册（market_narrator + setup_explainer 各 1 个 hook） | 单元 | §C pytest |
| 6 | guardrail 函数命中所有 6 条禁词（含中文 "承诺收益" / "忽略止损"），抛 `AiGuardrailViolation` | 单元 | §C pytest |
| 7 | `POST /api/ai/market_narrator` 端到端（mock LiteLLM）返回合规 envelope，`ai_memos` cost_usd>0 写入 | 集成 | §D TestClient |
| 8 | `POST /api/ai/setup_explainer` 端到端（mock LiteLLM）同上 | 集成 | §D TestClient |
| 9 | guardrail 拦截：mock 返回 `"buy now"` → 409 + `ai_memos` 不新增 | 集成 | §D TestClient |
| 10 | 输入 schema 校验失败 → 422 `VALIDATION_ERROR` | 集成 | §D TestClient |
| 11 | live smoke（`pytest -m live`，需 `OPENAI_API_KEY`）：market_narrator 真实调用，cost_usd>0，输出过 schema | 集成 | §E pytest |
| 12 | F208-c 现有 65 个测试 + F208-a/b 测试全部回归通过（**0 失败**） | 回归 | `pytest backend/tests/` |
| 13 | 模块顶部不直接 import `litellm`（保持 F208-c 标准 #13 lazy import） | 单元 | §A 静态断言 |

---

## 4. 风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| 字段命名 camelCase vs snake_case 决策 | 影响 LLM 输出形态、前端解析 | 见 §6 决策 D-1：本 sprint 选 camelCase（与 API-CONTRACT 示例字面一致），不动 gateway/router |
| guardrail 注册副作用在 `__init__.py` import 时执行，多次 import 重复注册 | 测试隔离风险 | `guardrail.register()` 实现是覆盖（dict 赋值）非 append，重复无害；§C 测试用 identity check 验证 |
| live smoke 真打 OpenAI 烧钱 | 成本 | 仅 market_narrator 1 次调用，`@pytest.mark.live` 默认 skip，CI 不跑 |
| LLM 实际输出 camelCase 不稳定（gpt-5.4-nano 偶尔 snake_case） | live smoke 偶发失败 | LiteLLM `response_format=Pydantic class`，OpenAI structured output 严格按 JSON schema 字段名（=Pydantic 字段名 camelCase）；若 live 发现偏差，记入 DECISIONS 并升级 D-1 决策 |
| Pydantic v2 嵌套 BaseModel 的 `extra="forbid"` 不会自动级联到嵌套类 | 子对象漏校 | 每个嵌套类（`MarketNarratorSubscores` / `MarketNarratorSector` / `SetupRisk`）独立声明 `model_config = {"extra": "forbid"}` |

---

## 5. Evaluator 自检清单

- [ ] 本 sprint 所有新增/修改文件已列入 §2 清单，未越界
- [ ] §A-§D pytest 全通过
- [ ] §E live smoke：本地 `OPENAI_API_KEY` 已设时手动跑过 1 次，cost_usd>0，输出过 schema（如未设 key，记录 "skipped" 即可，不阻塞）
- [ ] `pytest backend/tests/` 全量 0 失败（含 F201/F202/F203/F204/F208-a/b/c 全量回归）
- [ ] `backend/app/ai/schemas/__init__.py` 中无注释占位残留（删除 F208-c 留下的 6 条 `# "xxx": SchemaPair(...)`）
- [ ] 三个 schema 文件均含 `SCHEMA_VERSION = "v1"` 模块常量
- [ ] 6 条 BANNED_PHRASES（"buy now"/"sell now"/"承诺收益"/"保证收益"/"忽略止损"/"ignore stop"）在两个 schema 文件中**完全相同**（用模块常量定义，不复制粘贴漂移）
- [ ] 无 `import litellm` 在 schema 模块顶层
- [ ] 无硬编码字段名魔法值（全部由 Pydantic 字段定义驱动）
- [ ] DECISIONS.md 已追加 D074（schema 字段命名决策，见 §6 D-1）
- [ ] features.json#F209-a phase 更新为 `needs_review`，acceptance_criteria 全部勾选
- [ ] WIP commit 按步骤分次执行（schemas/market_narrator → schemas/setup_explainer → __init__.py → tests）

---

## 6. 已知约束与待决策

### D-1（本 sprint 决策，写入 DECISIONS.md = D074）：schema 字段命名 = camelCase

**问题**：features.json AC 写"camelCase 在 router 边界转换，schema 内部 snake_case"，但：
- F208-c 的 `routers/ai.py` **不做** camelCase↔snake_case 转换，直接把 `body.input` 原样传给 `pair.input_schema(**input_dict)`。
- 本 sprint 范围"不改 gateway/router 框架"。
- API-CONTRACT.md line 1733-1734 示例字段为 camelCase（`marketScore` / `riskPosture` / `preferredSetups`）。
- LiteLLM `response_format=Pydantic` 用 Pydantic 字段名生成 JSON schema 给 LLM；schema 字段名即客户端最终看到的输出字段名。

**决策**：schema 字段名直接采用 camelCase，与 API-CONTRACT 示例字面一致。AC 中"schema 内部 snake_case"作为 v2 改进项归档（需要先把 router 改造为 camel↔snake 自动转换），本 sprint 不做。

**理由**：
1. 与 API-CONTRACT 唯一权威示例一致，零阻抗。
2. 不需触碰 gateway/router 框架，Sprint 边界清晰。
3. Pydantic v2 模型内部用什么大小写不影响功能，命名规范是单纯约定。

**用户须确认**：是否接受此决策。若不接受（坚持 snake_case 内部），需扩大本 sprint 范围至 routers/ai.py 改造，或改为先做 v2 router 改造再做本 sprint。

### 约束-2：SYSTEM_PROMPT 暂不接入 LiteLLM messages

F208-c gateway 调用 `litellm.completion(messages=[{"role":"user", content=json.dumps(input_dict)}])`，**不传 system role**。本 sprint 在 schema 文件写入 `SYSTEM_PROMPT` 模块常量但不接入。原因：接入需要改 gateway（在 `_call_litellm` 多传一个 prompt 参数 + 从 `pair` 取 system_prompt），属于"改 gateway 框架"，超出 sprint 边界。

**后续**：在 F209-b 或独立 chore sprint 完成 system_prompt 接入。features.json AC 描述"Schema 内嵌 system prompt"在本 sprint 仅落地"内嵌"，不落地"接入"。

### 约束-3：D072 cost_usd 修复仅在 live smoke 验证

D072 修复 `cost_usd` 写入。本 sprint §D 集成测试 mock `_call_litellm` 返回 `Decimal("0.001234")`，验证 router→envelope→ai_memos 透传链路；§E live smoke 1 次真实调用 verify gpt-5.4-nano 实际计费链路。两者结合等价于"cost fix 在新 task 上仍生效"。

---

## 7. 开发顺序（Generator 模式遵循）

1. **Step 1**：写 `market_narrator.py`（含嵌套类 + SYSTEM_PROMPT + BANNED_PHRASES + guardrail 函数）→ `python -c "from app.ai.schemas.market_narrator import MarketNarratorInput; print(MarketNarratorInput.model_json_schema())"` 自检无错 → wip commit
2. **Step 2**：写 `setup_explainer.py`（同结构）→ 同自检 → wip commit
3. **Step 3**：改 `schemas/__init__.py`（import + REGISTRY + guardrail.register）→ `python -c "from app.ai.schemas import REGISTRY; assert 'market_narrator' in REGISTRY"` → wip commit
4. **Step 4**：写 `test_ai_schemas_f209.py` §A+§B+§C 单元测试 → 跑通 → wip commit
5. **Step 5**：补 §D 集成测试（mock LiteLLM + TestClient）→ 跑通 → wip commit
6. **Step 6**：补 §E live smoke `@pytest.mark.live` skeleton → wip commit
7. **Step 7**：Evaluator 模式：跑全量 `pytest backend/tests/` 回归 → 自检清单逐项核对 → 追加 DECISIONS.md D074 → 更新 features.json phase=needs_review → 终态 commit

每 step 完成后 `git add <显式文件名>` + `git commit -m "wip(F209-a): step N 描述"`。

---

## 8. 用户确认点

请回复确认以下 4 项：

1. ✅/❌ **§1.1 范围**：4 个文件、两个 task schema、guardrail 自动注册、不改 gateway/router
2. ✅/❌ **§6 D-1 字段命名 camelCase**：接受 schema 字段直接 camelCase 与 API-CONTRACT 示例一致；放弃"内部 snake_case"
3. ✅/❌ **§6 约束-2 SYSTEM_PROMPT 暂不接入**：本 sprint 仅写入模块常量，不改 gateway 拼接 messages
4. ✅/❌ **§3 完成标准 + §5 自检清单**

确认后：
- 我将更新 features.json phase → `contract_agreed`
- 生成 SESSION-HANDOFF.md
- 停止本 session，请你新开 Sonnet session 继续 Generator 模式
