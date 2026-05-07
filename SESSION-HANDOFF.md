# SESSION-HANDOFF — F213-a Generator 完成

> 生成时间：2026-05-07 | Branch: cockpit | 状态：F213-a done，F213-b design_needed
> 本 session 模型：Sonnet 4.6（F213-a Generator）

---

## 1. 已完成内容（本 session）

### 1.1 代码变更（5 文件）

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/app/ai/schemas/translate_article.py` | 新建 ~45 行 | TranslateArticleInput / Output / SYSTEM_PROMPT / SCHEMA_VERSION=v1；无 guardrail |
| `backend/app/ai/schemas/__init__.py` | +2 行 | import + REGISTRY 注册 translate_article |
| `backend/app/ai/routing.py` | +1 行 | `_TASK_TIER["translate_article"] = "default"` + D084 注释 |
| `backend/app/routers/ai.py` | +1 行 | `TaskTypeEnum` 7→8，加 translate_article |
| `backend/tests/test_ai_schemas_f213a.py` | 新建 ~260 行 | 28 测试（TI×10 / TO×7 / R×3 / G×2 / TT×4 / INT×2）全部通过 |

### 1.2 文档变更（3 文件）

| 文件 | 变更 |
|------|------|
| `docs/系统设计/API-CONTRACT.md` | POST /api/ai/{task_type} task_type 枚举 7→8，加 translate_article 行 |
| `docs/系统设计/DATA-MODEL.md` | §AiMemo task_type 枚举 6→8，加 translate_article 行 |
| `docs/系统设计/DECISIONS.md` | 追加 D084（DeepSeek per-task override 接入策略） |

### 1.3 测试文件修复（3 既有文件）

gateway.py `_call_litellm` 增加了 `system_prompt` 参数（前序 sprint 改动），导致旧 mock 签名不匹配，本 session 一并修复：
- `tests/test_ai_core_modules_f208b.py`：production_types 断言 7→8 + translate_article tier
- `tests/test_ai_gateway_e2e_f208c.py`：12 个 mock 函数补 `system_prompt=""` 参数
- `tests/test_ai_schemas_f209.py`：mock 函数补 `system_prompt=""` 参数

### 1.4 项目状态变更

- `docs/需求/features.json`：
  - F213-a sub_sprint: `contract_agreed` → `done`
  - F213 iteration_history 追加 generator_complete 记录
  - `_pipeline_status.active_sprint = "F213-b"` / `active_sprint_phase = "design_needed"`
- `claude-progress.txt`：追加 F213-a Generator 完成记录
- `SESSION-HANDOFF.md`：本文件

### 1.5 Commit 历史（本 session）

```
d140703 feat(F213-a): translate_article task schema + DeepSeek-ready  ← 最终 commit
c20e49b wip(F213-a): unit + integration tests + endpoint enum 7→8
0fa9a9b wip(F213-a): translate_article schema + REGISTRY + tier
67e9c7b wip(F213-a): docs prep — task_type 7→8 enum + D084 DeepSeek override
```

---

## 2. 当前状态

### 2.1 测试结果

| 范围 | 结果 |
|------|------|
| F213-a 专项 | 28/28 通过 |
| 全量回归 | 901 通过，5 个预存失败不变，**无新增失败** |

**5 个预存失败（与本 sprint 无关）**：
1. `test_ai_schemas_f211a1::test_R5_contradiction_detector_resolves_default`（tier 已升 critical，测试未同步）
2. `test_ai_schemas_f211a1::test_R6_news_summarizer_resolves_default`（同上）
3. `test_fmp_client::test_get_screener_universe_merges_three_exchanges_and_dedupes`（FMP 参数不匹配）
4. `test_regime_f201a::test_s14_cockpit_params_import_no_exception`（INDEX_ETFS 4 个，断言 3 个）
5. `test_regime_f201b::TestRegimeApiEndpoint::test_s4_indices_has_exactly_3_items`（同上）

### 2.2 工作区状态

未 commit 的上游遗留（不属本 sprint）：
- `backend/app/external/fmp_client.py`（M）
- `docs/cockpit-usage-guide.{png,svg}`（??）
- `docs/stock-portal-architecture.{png,svg}`（??）
- `docs/验收/playwright-report/`（??）
- `docs/验收/screenshots/`（??）
- `backend/test_translate_news.py`（??，前一轮 DeepSeek 验证脚本，可保留或 chore commit 删除）

---

## 3. 下一步：F213-b Sprint Contract 协商

F213-b 范围（前端，3 文件）：
1. `backend/app/external/translate_article_api.ts`（实际是前端 API client，新建）
2. `src/workbench/widgets/News/ArticleModal.tsx`（修改，自动调用翻译 + loading + fallback）
3. 前端测试文件（新建）

**开新 session 前需要**：
1. 读取 `docs/开发/sprint-contracts/F213-a-contract.md` §1.2 排除项中关于 F213-b 的描述
2. 开 Sprint Contract 协商：ArticleModal 打开时机、loading 状态、fallback 策略（失败显示原文）、toast 提示

**恢复 prompt（开新 session 后粘贴）**：

```
继续开发 F213，F213-a 已 done。
读取 SESSION-HANDOFF.md + docs/开发/sprint-contracts/F213-a-contract.md §1.2（F213-b 排除说明），
开始 F213-b Sprint Contract 协商。
```

---

## 4. 部署提示（F213-b 落地后才需要配置）

在 `backend/.env` 配置以下任一路径（F213-a 已建好 routing 支持）：

**OpenAI 兼容路径（推荐）**：
```bash
AI_TASK_OVERRIDES_JSON='{"translate_article":{"model":"openai/deepseek-v4-flash","base_url":"https://api.deepseek.com","api_key":"sk-ed66526c39af46508a4a33c7e8bd95a2","input_cost_per_1m":0.14,"output_cost_per_1m":0.28}}'
```

**原生 LiteLLM DeepSeek 路径**（需确认当前 LiteLLM 版本支持）：
```bash
AI_TASK_OVERRIDES_JSON='{"translate_article":{"model":"deepseek/deepseek-v4-flash","api_key":"sk-ed66526c39af46508a4a33c7e8bd95a2","input_cost_per_1m":0.14,"output_cost_per_1m":0.28}}'
```

> ⚠️ 价格 0.14 / 0.28 为 2026-05-07 时点 DeepSeek 公开报价，实际以 DeepSeek 官网为准。

---

## 5. 未决事项

1. **5 个预存测试失败**：非本 sprint 引入，建议开独立技术债 sprint 修复（R5/R6 是 F211-a 升级 tier 后未同步测试；S4/S14 是 VXX 加入 INDEX_ETFS 后未同步断言）。
2. **F213-b Sprint Contract**：下一 session 主要任务，需协商前端触发逻辑和 UI 设计。
3. **backend/test_translate_news.py**：DeepSeek 验证脚本，可在 F213-b sprint 末一并 `chore: remove` 提交。

---

## 6. 关键引用

- Sprint Contract：`docs/开发/sprint-contracts/F213-a-contract.md`
- 决策：D064 / D069 / D075 / D084（已追加）
- 实现：`backend/app/ai/schemas/translate_article.py`
- 测试：`backend/tests/test_ai_schemas_f213a.py`
