# Sprint Contract：F213-a — News Article Auto-Translate 后端 schema + tier 注册

> 状态：草案，待用户确认 | 起草：2026-05-07
> 父 Feature：F213 News Article Auto-Translate（DeepSeek via /api/ai）
> 拆分：**F213-a（本 sprint，后端 4 文件）** / F213-b（前端 ArticleModal 改造 + API client + 测试，3 文件）
> 依赖：
>   - F208-c ✅（AiGateway 主流程 + REGISTRY 模式 + guardrail 注册机制）
>   - F211-a2 ✅（per-task model override 基建：base_url / api_key / cost rate 全部由 `AI_TASK_OVERRIDES_JSON` env 驱动；routing.py L80-115）
>   - F209-a ✅（schema 文件模板：SCHEMA_VERSION / SYSTEM_PROMPT / Pydantic 风格）
> 引用文档：
>   - API-CONTRACT.md §POST /api/ai/{task_type}（统一入口；本 sprint 需把 enum 7 → 8）
>   - DATA-MODEL.md §Entity: AiMemo（复用现有 task_type 枚举；本 sprint 需补 translate_article）
>   - DECISIONS.md D064（tier 路由）/ D069（ai_memos 去重缓存）/ D075（per-task override）
>   - features.json#F213（acceptance_criteria 5 条；sub_sprints 2 entry）
>   - backend/app/ai/schemas/__init__.py（REGISTRY 注册模板）
>   - backend/app/ai/routing.py L12-22（_TASK_TIER 字典 + L80-115 override 解析）
>   - backend/app/ai/schemas/news_summarizer.py（最相近的兄弟 schema：news 输入字段、HTML 处理约定）

---

## 0. 背景与定位

F211-a1 落地时，已经在 routing.py / schemas/__init__.py 建立了"加新 task = 加 schema 文件 + REGISTRY 注册一行 + _TASK_TIER 加一行"的标准三步走。F213-a 完全沿用这个流程，**不动 gateway / endpoint / DB schema / 前端**，只在后端补一个 task 让 `/api/ai/{task_type}` 多接受 `task_type=translate_article`。

DeepSeek 通过 F211-a2 已建好的 per-task override 机制接入，**不需要改 routing.py 的解析逻辑**，只需要：

1. `_TASK_TIER` 加一行 `translate_article: "default"`（任何 tier 都行，因为 override 会接管 model 选择，但默认 tier 不污染高价模型）
2. 部署时把 DeepSeek 的 base_url / api_key / model_id 写进 `AI_TASK_OVERRIDES_JSON` env

本 sprint **不**写部署文档，env 配置示例放在 contract §6 让用户后续手动配置 `.env`。

**关键约束**：

1. 翻译任务**无 deterministic 数字锚点**也**无 BANNED_PHRASES**（不像 F210 trade_plan / F211 news_summarizer），所以**不注册 guardrail**（保持 schemas/__init__.py guardrail 注册块整洁）。
2. 字段命名走 **D074 camelCase**。
3. `SCHEMA_VERSION = "v1"`。
4. Input 字段保持精简：`title`（str）+ `contentText`（str，HTML 剥离责任在前端 F213-b，与 F211-a1 news_summarizer 同约定）。可选 `targetLang: Literal["zh-CN"] = "zh-CN"` 字段保留扩展面，**默认中文**。
5. Output 字段：`titleZh: str` + `contentZh: str`，与 input 一对一翻译，不做摘要、不做 sentiment、不做 catalysts（那些是 news_summarizer 的活）。
6. **不**注册到现有 BANNED_PHRASES 体系；翻译结果不需要 guardrail 校验（输出是中文文本，guardrail 模板专为英文 LLM 输出设计，复用反而误伤）。
7. 测试沿用 F211-a1 测试组织模式：`test_ai_schemas_f213a.py`，单元测试覆盖 input/output schema 边界 + REGISTRY 完整性 + routing tier 命中。

---

## 1. 实现范围

### 1.1 包含

#### 1.1.1 `backend/app/ai/schemas/translate_article.py`（新建，~60 行）

**职责**：定义 `translate_article` task 的 input/output schema + SYSTEM_PROMPT，**不含 guardrail**。

**Input 字段（3 项，camelCase）**：
| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `title` | str | min_length=1, max_length=500 | 文章原文标题（英文） |
| `contentText` | str | min_length=1, max_length=20000 | 文章正文纯文本（HTML 已被前端剥离） |
| `targetLang` | Literal["zh-CN"] | 默认 "zh-CN" | 目标语种；当前固定中文，预留扩展 |

`model_config = {"extra": "forbid"}`（与现有 schema 一致）。

**Output 字段（2 项，camelCase）**：
| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `titleZh` | str | min_length=1, max_length=500 | 中文译文标题 |
| `contentZh` | str | min_length=1, max_length=25000 | 中文译文正文（中文比英文略短，预留 1.25× buffer） |

**SYSTEM_PROMPT**（与测试脚本 `test_translate_news.py` 验证过的提示词同源，但更严格）：
```
你是专业的金融新闻翻译员。将输入的英文新闻翻译成简洁、准确的中文。

严格规则：
1. 公司名、人名、机构名、股票代码（如 "Microsoft"、"NASDAQ: MSFT"、"Tigress Financial"）必须保留原文，不得意译。
2. 数字（金额、百分比、日期）保留原值，单位（%、$、亿、百万）按中文金融报道惯例转换。
3. 标题简洁有力，正文段落清晰。
4. 不增加任何注释、解释、评论或来源标注。
5. 输出必须严格遵循 JSON schema：{ "titleZh": "...", "contentZh": "..." }
```

**SCHEMA_VERSION = "v1"**。

**不导出 `guardrail` 函数**（与 candidate_ranker / echo 同例 — REGISTRY 入口可缺 guardrail）。

#### 1.1.2 `backend/app/ai/schemas/__init__.py`（修改，约 +3 行）

- 新增 `from app.ai.schemas import translate_article as _ta`
- `REGISTRY` 字典加一行：`"translate_article": SchemaPair(_ta.TranslateArticleInput, _ta.TranslateArticleOutput, _ta.SYSTEM_PROMPT)`
- **不**调用 `_gr.register("translate_article", ...)`

#### 1.1.3 `backend/app/ai/routing.py`（修改，约 +1 行）

- `_TASK_TIER` 字典加一行：`"translate_article": "default"`（注释说明 F213 + DeepSeek override）

#### 1.1.4 `backend/tests/test_ai_schemas_f213a.py`（新建，~250 行，约 25 单元测试）

测试组：
- **TI1-TI5 input 边界**：
  - 空 title / contentText 拒绝
  - 超长拒绝（501 / 20001）
  - 含 emoji / 中英混排正常
  - targetLang 非 "zh-CN" 拒绝
  - extra 字段拒绝
- **TO1-TO4 output 边界**：
  - 空 titleZh / contentZh 拒绝
  - 超长拒绝（501 / 25001）
  - extra 字段拒绝
  - 实际中文样本（混 ASCII 公司代码）通过
- **R1-R3 REGISTRY 完整性**：
  - `REGISTRY["translate_article"]` 存在
  - input_schema / output_schema 类型正确
  - SYSTEM_PROMPT 非空
- **G1 guardrail 缺席**：
  - `guardrail.run("translate_article", output_dict)` 返回 None / 空（即 no-op，不抛错）
- **TT1-TT3 routing tier**：
  - `resolve_tier("translate_article") == "default"`
  - `known_task_types()` 包含 "translate_article"，长度 9（含 echo），与 API-CONTRACT 8 enum 对齐
  - `resolve("translate_article")` 在无 override 时返回 default tier model（settings.ai_model_default）；有 override 时返回 override 配置（mock settings.ai_task_overrides_json 为含 translate_article 的 JSON 字符串）

### 1.2 排除（不在本 sprint）

- ❌ 前端任何代码（属于 F213-b）
- ❌ DEEPSEEK_API_KEY 或 DEEPSEEK_BASE_URL 写入 `app/config.py` Settings 字段（D075 既定 — 不进 settings.py 单独字段，全部走 ai_task_overrides_json）
- ❌ 修改 gateway.py / guardrail.py / endpoint
- ❌ 改 ai_memos 表或 cache 逻辑（D069 现有去重已可用）
- ❌ guardrail 注册（翻译输出无英文 BANNED_PHRASES 适用面）
- ❌ 集成测试 hit 真实 DeepSeek（contract §3 集成测试用 mocked LiteLLM）
- ❌ 部署 / `.env` 实际配置（写在 contract §6 "部署提示"由用户手动落到 `.env`）
- ❌ ARCHITECTURE.md "DeepSeek as LiteLLM provider" 一节（属于 system-design 协议范畴；本 sprint 仅在 DECISIONS.md 写决策）

---

## 2. 预计修改文件清单（4 个 — 在 6 文件预算内）

| # | 文件 | 操作 | 行数 |
|---|------|------|------|
| 1 | `backend/app/ai/schemas/translate_article.py` | 新建 | ~60 |
| 2 | `backend/app/ai/schemas/__init__.py` | 修改 | +3 |
| 3 | `backend/app/ai/routing.py` | 修改 | +1 |
| 4 | `backend/tests/test_ai_schemas_f213a.py` | 新建 | ~250 |

**Generator step 1-2 文档前置（不计入文件预算，符合先例）**：

| 文件 | 操作 |
|------|------|
| `docs/系统设计/API-CONTRACT.md` | 把 7 enum 扩成 8 enum，新增 translate_article 一行；不增加新章节（仍是同一 endpoint） |
| `docs/系统设计/DATA-MODEL.md` §Entity:AiMemo | 把 task_type 枚举表加 translate_article 一行 |
| `docs/系统设计/DECISIONS.md` | 新增 D084 "DeepSeek 通过 per-task override 接入，不进 settings 字段" |
| `claude-progress.txt` | 追加 F213-a contract 协商记录 |

> ⚠️ 这 4 个文档变更必须在 Generator 写代码**之前**完成（CLAUDE.md：改 API → 先更新 API-CONTRACT）。

---

## 3. 完成标准（Evaluator 测试用例）

| # | 测试描述 | 层级 | 工具 | 预期 |
|---|---------|------|------|------|
| TI1 | input.title 为空字符串 | 单元 | pytest | ValidationError |
| TI2 | input.title 长度 501 | 单元 | pytest | ValidationError |
| TI3 | input.contentText 长度 20001 | 单元 | pytest | ValidationError |
| TI4 | input 含未知字段（如 sourceUrl） | 单元 | pytest | ValidationError(extra=forbid) |
| TI5 | input.targetLang = "en-US" | 单元 | pytest | ValidationError(Literal mismatch) |
| TI6 | input 合法（带 emoji 与 NASDAQ:MSFT 混排）| 单元 | pytest | 通过校验 |
| TO1 | output.titleZh 为空 | 单元 | pytest | ValidationError |
| TO2 | output.contentZh 长度 25001 | 单元 | pytest | ValidationError |
| TO3 | output 含未知字段 | 单元 | pytest | ValidationError |
| TO4 | output 合法中文样本（含 NASDAQ:MSFT） | 单元 | pytest | 通过 |
| R1 | REGISTRY["translate_article"] 存在 | 单元 | pytest | True |
| R2 | REGISTRY[...].input_schema is TranslateArticleInput | 单元 | pytest | True |
| R3 | REGISTRY[...].system_prompt 非空且包含"金融"关键字 | 单元 | pytest | True |
| G1 | guardrail.run("translate_article", {...}) | 单元 | pytest | 不抛错（no-op） |
| TT1 | resolve_tier("translate_article") | 单元 | pytest | == "default" |
| TT2 | known_task_types() 长度 9 含 translate_article | 单元 | pytest | True |
| TT3 | resolve(...)，无 override，返回 settings.ai_model_default | 单元 | monkeypatch | 通过 |
| TT4 | resolve(...)，monkeypatch override 为 deepseek，返回 deepseek model + base_url + api_key | 单元 | monkeypatch | 通过 |
| INT1 | （集成）通过 AiGateway 调用 mocked LiteLLM，translate_article 任务全程跑通 | 集成 | pytest + respx mock | 200 + output schema 校验通过 |
| INT2 | （集成）AiMemo 缓存命中：相同 input 第二次调用 cacheHit=true | 集成 | pytest + 内存 ai_memos | meta.cacheHit=true |
| REGRESSION | 全量测试套件（约 880+）回归 | 全量 | pytest | 全通过，无新增失败 |

---

## 4. 自检清单（Generator 完成后 Evaluator 模式使用）

- [ ] 单元测试 TI1-TI6 / TO1-TO4 / R1-R3 / G1 / TT1-TT4 全部通过（≥17 通过）
- [ ] 集成测试 INT1-INT2 全部通过
- [ ] 回归测试：全量后端测试套件无新增失败
- [ ] mypy 检查通过（与现有 ai/schemas/*.py 同标准）
- [ ] API-CONTRACT.md 已更新（task_type 枚举 7 → 8）
- [ ] DATA-MODEL.md §AiMemo 已加 translate_article 枚举行
- [ ] DECISIONS.md D084 已追加
- [ ] features.json F213-a phase = "done"，F213 phase = "in_progress"（保持，因为 F213-b 未做）
- [ ] features.json F213.iteration_history 追加一条 generator 完成记录
- [ ] schemas/__init__.py 注册顺序与现有保持（按字母 / 引入顺序，不打乱）
- [ ] 无硬编码 DeepSeek base_url 或 api_key（必须走 settings.ai_task_overrides_json）
- [ ] schemas/translate_article.py 顶部 docstring 注明 F213-a + SCHEMA_VERSION
- [ ] 测试文件 docstring 注明 F213-a + 测试组编号映射
- [ ] 无 console.error / 无未捕获 warning
- [ ] git wip commit 按步骤分批（schema → __init__ → routing → tests）

---

## 5. 开发顺序（Generator 模式不得颠倒）

1. **更新 API-CONTRACT.md**：在 task_type 枚举段把 7 enum 扩成 8 enum（加 `translate_article`），写明 default tier + DeepSeek per-task override。
2. **更新 DATA-MODEL.md** §AiMemo task_type 枚举表：加 translate_article 一行。
3. **追加 DECISIONS.md D084**：DeepSeek 接入策略（per-task override，不进 settings 字段，理由）。
4. **新建** `backend/app/ai/schemas/translate_article.py`（schema + system_prompt）。
5. **修改** `backend/app/ai/schemas/__init__.py`（import + REGISTRY 一行）。
6. **修改** `backend/app/ai/routing.py`（_TASK_TIER 一行）。
7. **新建** `backend/tests/test_ai_schemas_f213a.py`（25 测试）。
8. 跑 `pytest backend/tests/test_ai_schemas_f213a.py -v` → 全过。
9. 跑 `pytest backend/tests/ -v` 全量回归 → 无新增失败。
10. 切换 Evaluator 模式，逐条对照 §3 / §4。

每步完成后 wip commit（按 §4 末条规则）。

---

## 6. 部署提示（不属本 sprint，给用户参考）

F213-b 落地后实测前，需要在 `backend/.env` 配置：

```bash
AI_TASK_OVERRIDES_JSON='{"translate_article":{"model":"deepseek/deepseek-v4-flash","base_url":"https://api.deepseek.com","api_key":"sk-ed66526c39af46508a4a33c7e8bd95a2","input_cost_per_1m":0.14,"output_cost_per_1m":0.28}}'
```

> ⚠️ 价格 0.14 / 0.28 是本起草时点 DeepSeek v4-flash 公开报价的占位估值，Generator 阶段会通过 Context7 / DeepSeek docs 重新验证；如不确定，临时设 0 让 ai_memos 不报 cost 也可以。

---

## 7. 开放问题（Generator 阶段 第 1 步前必须解决）

| Q | 问题 | 默认方案 | 备选 |
|---|------|---------|------|
| Q1 | LiteLLM 当前安装版本是否支持 `deepseek/deepseek-v4-flash` 原生 provider？ | **默认**：用 `deepseek/deepseek-v4-flash`（需 Generator 通过 Context7 查 LiteLLM 文档确认）。**回退**：用 `openai/deepseek-v4-flash` + `base_url=https://api.deepseek.com`（OpenAI-兼容路径，DeepSeek 官方文档已确认其 API 与 OpenAI 兼容） | — |
| Q2 | contentText max_length 20000 字符是否够？ | 默认 20000（约 5000 token，覆盖 99% 新闻文章） | 调到 30000 |
| Q3 | targetLang 字段是否真有必要保留扩展？ | **保留**（成本几乎为零，且未来可能加日/韩） | 删掉，固定中文 |
| Q4 | content_html 剥离 → contentText 由前端做还是后端做？ | **前端**（与 F211-a1 news_summarizer 同约定，避免后端引 BeautifulSoup） | 后端做（增加依赖） |
| Q5 | DeepSeek 价格 input_cost_per_1m / output_cost_per_1m 取多少？ | Generator 通过 Context7 / DeepSeek docs 查最新值（本起草占位 0.14 / 0.28） | 设 0（不追踪此 task 成本） |

**用户回应**：默认全采纳即可（如有修改在确认时一并指明）。

---

## 8. 风险与降级

| 风险 | 影响 | 降级 |
|------|------|------|
| DeepSeek 限流 / 网络抖动 | 翻译失败 | F213-b ArticleModal 已设计 fallback：失败时显示原文 + toast |
| LiteLLM 不识别 deepseek/v4-flash 模型 | gateway 抛错 | Q1 备选路径 OpenAI-兼容 base_url + api_key |
| AI_TASK_OVERRIDES_JSON 格式错 | parse warn，回落到 ai_model_default（可能用 openai 替代）| routing.py 已有 try/except + log.warning，行为可见但不阻塞 |
| 翻译结果失真（金融术语错译） | 用户体验降级 | system_prompt 已强制保留公司名/股票代码/数字；后续可加 BANNED_PHRASES 灰名单 |

---

## 9. 不变量（Generator 期间不得违反）

- 现有 8 个 task（含 echo）的测试全部保持通过
- gateway.py / guardrail.py / endpoint 不被修改
- AiMemo 表结构不变（仅枚举值扩展）
- 不引入新 Python 依赖（litellm 已在 ARCHITECTURE）
- 不在代码中硬编码任何 api_key / base_url

---

**确认须知**

用户回复"Contract 同意"或等价 OK，即视为确认。确认后：
1. features.json F213-a sub_sprint 维持 `design_needed`（此 contract 阶段还未到 contract_agreed）
2. 我将更新 sub_sprint 状态为 `contract_agreed`
3. 追加 features.json#F213.iteration_history 一条 contract_agreed 记录
4. 更新 claude-progress.txt
5. 生成 SESSION-HANDOFF.md
6. **停止本 session**，提示用户用 Sonnet 开新 session 走 Generator 模式（per skill A-1 末段强制要求）
