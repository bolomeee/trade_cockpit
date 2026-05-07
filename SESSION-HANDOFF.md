# SESSION-HANDOFF — F213-a Sprint Contract 协商完成

> 生成时间：2026-05-07 | Branch: cockpit | 状态：F213-a contract_agreed，待新 session Generator 模式
> 本 session 模型：Opus 4.7（F213-a contract 协商）
> **下一 session：Sonnet，进入 F213-a Generator 模式**

---

## 1. 已完成内容（本 session）

### 1.1 项目状态变更

- `docs/需求/features.json`
  - 新增 F213 entry（News Article Auto-Translate）
  - sub_sprints：`F213-a: contract_agreed` / `F213-b: design_needed`
  - parent phase：`design_needed → contract_agreed`
  - `_pipeline_status.active_sprint = "F213-a"` / `active_sprint_phase = "contract_agreed"`
  - `last_updated = "2026-05-07"`
  - F213.iteration_history 追加 contract_agreed 记录

- `docs/开发/sprint-contracts/F213-a-contract.md`（新建，完整契约）
- `claude-progress.txt`（追加 F213-a Contract 协商完成记录）

### 1.2 决策

| 决策 | 选项 |
|------|------|
| API 设计 | C：复用 `/api/ai/{task_type}`（task_type=translate_article），不新建独立 endpoint |
| 缓存策略 | 仅 ai_memos（D069）按 input hash 去重；翻译结果不持久化到 news_articles_cache |
| 触发时机 | ArticleModal 打开时自动调用（F213-b） |
| 模型 | deepseek-v4-flash |
| 拆分 | F213-a 后端 4 文件 / F213-b 前端 3 文件 |
| DeepSeek 接入 | per-task override（D075）走 `AI_TASK_OVERRIDES_JSON` env，不进 settings.py 字段 |
| Q1-Q5 开放问题 | 全采默认方案（contract §7） |

---

## 2. 当前状态

### 2.1 Sprint Contract 执行位置

| # | 开发步骤 | 状态 |
|---|---------|------|
| - | Sprint Contract 协商 | ✅ 已确认 |
| 1 | 更新 API-CONTRACT.md（task_type 7→8 enum） | ⬜ 未开始 |
| 2 | 更新 DATA-MODEL.md §AiMemo 枚举 | ⬜ 未开始 |
| 3 | 追加 DECISIONS.md D084 | ⬜ 未开始 |
| 4 | 新建 `backend/app/ai/schemas/translate_article.py` | ⬜ 未开始 |
| 5 | 修改 `backend/app/ai/schemas/__init__.py` | ⬜ 未开始 |
| 6 | 修改 `backend/app/ai/routing.py` | ⬜ 未开始 |
| 7 | 新建 `backend/tests/test_ai_schemas_f213a.py` | ⬜ 未开始 |
| 8 | 运行单元测试 | ⬜ 未开始 |
| 9 | 全量回归测试 | ⬜ 未开始 |
| 10 | 切 Evaluator 模式自检 | ⬜ 未开始 |

### 2.2 测试通过情况

- 全部尚未执行（Generator 阶段开始后才触发）

### 2.3 工作区状态

- 本 session 修改的文件：
  - `docs/需求/features.json`
  - `docs/开发/sprint-contracts/F213-a-contract.md`（新建）
  - `claude-progress.txt`
  - `SESSION-HANDOFF.md`（本文件）

- **上游遗留（与本 sprint 无关，Generator 不应一并 commit）**：
  - `backend/app/external/fmp_client.py`（M）
  - `docs/cockpit-usage-guide.{png,svg}`（??）
  - `docs/stock-portal-architecture.{png,svg}`（??）
  - `docs/验收/playwright-report/`（??）
  - `docs/验收/screenshots/`（??）
  - `backend/test_translate_news.py`（??，前一轮 DeepSeek 验证脚本，可保留作参考或在 sprint 末单独 chore commit 删除）

---

## 3. 下一 session 恢复指令

⚠️ **强制开新 session**（feature-dev skill A-1 末段硬性要求：Contract 协商和 Generator 必须分 session 执行）

**模型**：Sonnet（feature-dev skill 推荐）

**恢复 prompt**（粘贴到新 session）：

```
继续开发 F213-a，Sprint Contract 已确认。
读取 SESSION-HANDOFF.md + docs/开发/sprint-contracts/F213-a-contract.md，
进入 Generator 模式，从开发顺序步骤 1（更新 API-CONTRACT.md）开始。
```

---

## 4. Generator 模式行动清单（开新 session 后执行）

按 `docs/开发/sprint-contracts/F213-a-contract.md` §5 顺序：

1. **读取**当前 `docs/系统设计/API-CONTRACT.md` POST /api/ai/{task_type} 段，把 7 enum 改成 8 enum，新增 `translate_article` 行（标注 F213 + DeepSeek per-task override）
2. **读取**当前 `docs/系统设计/DATA-MODEL.md` §Entity:AiMemo task_type 枚举表，加 `translate_article` 一行
3. **追加** `docs/系统设计/DECISIONS.md` 新增 D084（DeepSeek 接入：per-task override，不进 settings 字段）
4. WIP commit：`git add docs/系统设计/API-CONTRACT.md docs/系统设计/DATA-MODEL.md docs/系统设计/DECISIONS.md && git commit -m "wip(F213-a): docs prep — task_type 7→8 enum + D084 DeepSeek override"`
5. **新建** `backend/app/ai/schemas/translate_article.py`（模板参考 `news_summarizer.py`，去掉 BANNED_PHRASES / guardrail；input/output 字段见 contract §1.1.1）
6. **修改** `backend/app/ai/schemas/__init__.py`（import + REGISTRY 一行；**不**注册 guardrail）
7. **修改** `backend/app/ai/routing.py`（`_TASK_TIER["translate_article"] = "default"` + 注释）
8. WIP commit：`git add backend/app/ai/schemas/translate_article.py backend/app/ai/schemas/__init__.py backend/app/ai/routing.py && git commit -m "wip(F213-a): translate_article schema + REGISTRY + tier"`
9. **新建** `backend/tests/test_ai_schemas_f213a.py`（参考 `test_ai_schemas_f211a1.py` 结构；测试组 TI1-TI6 / TO1-TO4 / R1-R3 / G1 / TT1-TT4 / INT1-INT2 共约 22 个测试）
10. **运行** `cd backend && uv run pytest tests/test_ai_schemas_f213a.py -v` → 全过
11. WIP commit：`git add backend/tests/test_ai_schemas_f213a.py && git commit -m "wip(F213-a): unit + integration tests"`
12. **运行** `cd backend && uv run pytest -x` 全量回归 → 无新增失败
13. **切换 Evaluator 模式**，逐条对照 contract §3 / §4 自检清单
14. Evaluator 全过后：
    - features.json `F213-a → done`
    - F213.iteration_history 追加一条 generator_complete 记录
    - 调用 consistency-check skill (mode=interactive) 验 C1/C4/C5
    - 最终 commit：`git add ... && git commit -m "feat(F213-a): translate_article task schema + DeepSeek-ready"`

---

## 5. 未决事项

1. **Q1 在 Generator 步骤 5 前必须解决**：用 Context7 查 LiteLLM 当前安装版本是否原生支持 `deepseek/deepseek-v4-flash`。
   - 若支持 → schema 文件不变，部署时 `AI_TASK_OVERRIDES_JSON` 写 `{"model": "deepseek/deepseek-v4-flash", "api_key": "..."}`（无需 base_url）
   - 若不支持 → 用 OpenAI-兼容路径，部署时写 `{"model": "openai/deepseek-v4-flash", "base_url": "https://api.deepseek.com", "api_key": "..."}`
   - 两种情况都不影响本 sprint 4 个代码文件，只影响 contract §6 部署提示文案

2. **Q5 Generator 阶段查 DeepSeek 当前定价**，写入 contract §6 部署示例（input_cost_per_1m / output_cost_per_1m），仅作参考，不阻塞 sprint 完成。

3. F213-b（前端）需要单独的 Sprint Contract，**不在本 sprint 范围**。F213-a Generator 完成后再开协商。

---

## 6. 风险快照

| 风险 | 缓解 |
|------|------|
| 新 session 上下文丢失 | 本文件 + contract 文件已包含全部决策 |
| Generator 误改 fmp_client.py 等遗留改动 | §2.3 已列上游遗留；开发顺序 §4 显式列文件名 add，禁用 `git add -A` |
| LiteLLM 不识别 deepseek-v4-flash | Q1 已备 OpenAI-兼容回退路径 |
| 前置 3 个文档变更被遗漏 | Generator 步骤 1-3 强制先行；wip commit 4 切片粒度细，丢一步不丢全部 |

---

## 7. 关键引用

- Sprint Contract：`docs/开发/sprint-contracts/F213-a-contract.md`
- 父 feature：`docs/需求/features.json#F213`
- 前置基建：F208-c（gateway 主流程）/ F211-a2（per-task override）
- 决策依据：D064 / D069 / D075（→ D084 待 Generator 阶段追加）
- DeepSeek 验证脚本（前一轮）：`backend/test_translate_news.py`（API 已确认可用，模型 deepseek-v4-flash 翻译质量满足要求）
