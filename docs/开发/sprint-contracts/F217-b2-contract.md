# F217-b2 Sprint Contract — Cockpit Phase C Pydantic Literal 扩展（加 CAPITULATION，暂留 PULLBACK）

> 生成：2026-05-15 | 状态：草案 → 待用户确认
> Feature：[F217](docs/需求/features.json) Phase C — Capitulation Reversal 严格重写
> Sub-sprint：F217-b2（Pydantic Literal 扩展，向后兼容窗口）
> 前置：F217-a done @ 2026-05-15；F217-b1 done @ 2026-05-15（DB 层 legacy 列已就绪，CAPITULATION 行可被写入与读取）；DATA-MODEL §SetupSnapshot 与 D095 已落地

---

## 1. 实现范围

### 包含

#### B2-a — 6 个 Pydantic schema 的 Literal 扩展

在每个 schema 现有 `setup_type` / `setupType` Literal 定义中**插入** `"CAPITULATION"`，**保留** `"PULLBACK"`（向后兼容窗口，b4 才删）：

| # | 文件 | Literal 形式 | 修改位置 | 改后值（顺序见 NP-b2-2） |
|---|------|-------------|---------|------------------------|
| 1 | `backend/app/schemas/cockpit/position.py` | 模块别名 `_VALID_SETUP_TYPES` | L11-13 | `"BREAKOUT", "PULLBACK", "CAPITULATION", "RECLAIM", "EARNINGS_DRIFT", "EXTENDED", "BROKEN", "NONE"` |
| 2 | `backend/app/schemas/cockpit/pending_order.py` | 模块别名 `_VALID_SETUP_TYPES` | L10-12 | 同上 |
| 3 | `backend/app/ai/schemas/trade_plan.py` | 内联 Literal（`TradePlanInput.setupType`） | L45 | 同上 |
| 4 | `backend/app/ai/schemas/candidate_ranker.py` | 内联 Literal（`CandidateInput.setupType`） | L42 | 同上 |
| 5 | `backend/app/ai/schemas/contradiction_detector.py` | 模块别名 `_SETUP_TYPE` | L41 | 同上 |
| 6 | `backend/app/ai/schemas/journal_assistant.py` | 模块别名 `_SETUP_TYPE` | L52 | 同上 |

> 别名一旦更新，所有引用该别名的字段（如 `journal_assistant.TradeReviewPayload.setupType` / `ClosedTradeBrief.setupType`，`contradiction_detector.ContradictionDetectorInput.setupType`，`position.PositionCreate.setup_type` / `PositionUpdate.setup_type`，`pending_order.PendingOrderCreate.setup_type` / `PendingOrderUpdate.setup_type`）自动获得新字面量，无需逐字段重复改。

#### B2-b — 不动的内容（避免溢出）

- **不改** 任何 `SYSTEM_PROMPT` 字符串 — 当前 prompt 不枚举 setup_type 取值，加 CAPITULATION 不需要 prompt 调整；prompt 行为合约变更属 F217-c 或后续微 sprint
- **不改** 任何响应 schema 中 `setup_type: str | None` / `setup_type: str` 字段（`PositionItem.setup_type` L99 / `PendingOrderItem.setup_type` L86 / `SetupPerformance.setupType` L128）— 这些是已经"宽容"的 str 类型，自然容纳 CAPITULATION
- **不改** `BANNED_PHRASES` / `guardrail()` 函数 — 与 setup_type 无关
- **不改** 任何 service 层 / router 层逻辑 — Literal 扩展是类型层变更
- **不动** `app/services/cockpit/cockpit_params.py` SETUP.TYPES — F217-a 已完成（CAPITULATION 已加，PULLBACK 已删）；本 sprint 不重复

### 排除（不在本 sprint）

- ❌ **测试 fixture 批量去 PULLBACK** — F217-b3（6 文件命中上限：`test_setup_f216d2` / `test_pool_service` / `test_ai_schemas_f211a1` / `test_f215a` / `test_regime_f201b` / `test_decision_f203b2`）
- ❌ **从 Literal 删 PULLBACK 字面量收紧** — F217-b4（必须 b3 fixture 迁移完成后才能跑，否则 fixture 校验失败）
- ❌ **前端 cockpitDecisionApi SetupType 类型 / chips / 紫色 badge** — F217-c
- ❌ **`decision_service` 写入 capitulationEvidence 字段** — F217-c
- ❌ **`user_settings.preferred_setups` JSON 默认值迁移** — F217-c 或独立微 sprint
- ❌ **新增 `CAPITULATION_ENABLED` flag** — D095 决策 6 应急方案，b 系列不引入
- ❌ **抽出共享 Literal 别名模块** — 见 NP-b2-3，YAGNI

### 协商点（NP）

> 父 sprint F217-b 已确认 NP1=A（DB 软删）/ NP2=Y（Literal 暂保留 PULLBACK）。
> 下面是 b2 子 sprint 内新出现的 4 个细决策。

| # | 议题 | 选项 | 推荐 | 理由 |
|---|------|------|------|------|
| **NP-b2-1** | 是否新建 b2 专属测试文件验证 CAPITULATION Literal 接受性 | A. 不新建测试文件，依赖 b3 fixture 迁移完整覆盖<br>B. 新建 `backend/tests/test_schemas_capitulation_literal.py`（参数化 6 schema round-trip）<br>C. inline 加断言到已有 `test_ai_schemas_f211a1.py` | **A** | Literal 扩展是纯加性、纯类型层；新增独立测试会让 b2 文件数 6→7（超父 sprint 明确的 6 文件命中上限）；b3 fixture 迁移会自然覆盖 CAPITULATION 解析路径；如果 Literal 拼写错误，b3/b4 阶段任一构造尝试会立刻 ValidationError 暴露 |
| **NP-b2-2** | CAPITULATION 在 Literal 元组中的位置 | A. 紧邻 PULLBACK 之后（`BREAKOUT, PULLBACK, CAPITULATION, RECLAIM, …`）<br>B. 末尾（`…, BROKEN, NONE, CAPITULATION`）<br>C. 按 setup_service classify 优先级排（`BROKEN, EXTENDED, EARNINGS_DRIFT, CAPITULATION, BREAKOUT, RECLAIM, NONE`） | **A** | Literal 元组顺序对运行时无影响（仅文档/类型提示）；A 让 git diff 最小（只 +1 单词不挪动其它）；语义上 "CAPITULATION 替换 PULLBACK" 视觉清晰；b4 删 PULLBACK 时 diff 变成在同位置删 1 单词，对应得起来 |
| **NP-b2-3** | 是否抽出共享 Literal 别名模块（DRY） | A. 保留现状，6 处独立加 CAPITULATION<br>B. 抽 `app/schemas/_setup_type_literal.py` 单一来源 | **A** | 跨包依赖代价（cockpit/schemas 与 ai/schemas 互相 import 一个新模块）+ 文件数 6→7 超上限 + 当前每处 Literal 各有独立用途上下文；YAGNI；如未来 setup_type 频繁变（不会，b 系列结束后稳定），再单独安排重构 sprint |
| **NP-b2-4** | 是否在 AI schemas SYSTEM_PROMPT 加一句"setupType 现含 CAPITULATION（投降反转）" | A. 不改 SYSTEM_PROMPT<br>B. 在 trade_plan / candidate_ranker / contradiction_detector / journal_assistant 4 处 SYSTEM_PROMPT 中提示 LLM 新字面量含义 | **A** | 当前 prompt 不枚举 setup_type 取值（依赖 schema validation 兜底）；改 prompt 会改 LLM 行为合约（属于 F217-c "AI 任务理解新 setup type" 范畴），且 b 系列还有 fixture / Literal 收紧 2 步未完，过早改 prompt 会让回归更难定位；如未来 LLM 输出对 CAPITULATION 处理质量差再补 |

---

## 2. 预计修改文件清单（6 个，全部修改无新建）

| # | 路径 | 类型 | 改动幅度 |
|---|------|------|---------|
| 1 | `backend/app/schemas/cockpit/position.py` | 修改 | 1 处 Literal 元组 +1 字面量 |
| 2 | `backend/app/schemas/cockpit/pending_order.py` | 修改 | 1 处 Literal 元组 +1 字面量 |
| 3 | `backend/app/ai/schemas/trade_plan.py` | 修改 | 1 处 inline Literal +1 字面量 |
| 4 | `backend/app/ai/schemas/candidate_ranker.py` | 修改 | 1 处 inline Literal +1 字面量 |
| 5 | `backend/app/ai/schemas/contradiction_detector.py` | 修改 | 1 处 Literal 别名 +1 字面量 |
| 6 | `backend/app/ai/schemas/journal_assistant.py` | 修改 | 1 处 Literal 别名 +1 字面量 |

✅ 6 文件命中上限，**无 buffer**。如 Generator 期间发现遗漏文件须二次协商。

---

## 3. 完成标准 — Evaluator 验收清单

### 测试矩阵（共 7 条，无新增 test 文件，全部通过现有测试 + 全量回归 + 静态校验）

| # | 测试描述 | 层级 | 工具 |
|---|---------|------|------|
| T1 | 6 个 schema 文件 import 不报错（Pydantic 在 import 时已构造 Literal） | 静态 | `python -c "from app.schemas.cockpit import position, pending_order; from app.ai.schemas import trade_plan, candidate_ranker, contradiction_detector, journal_assistant; print('OK')"` |
| T2 | 现有 PULLBACK 字面量仍被接受（向后兼容窗口未关）— 已有任何 fixture/测试构造 `setup_type='PULLBACK'` 的 ValidationError 不应出现 | 集成 | `uv run pytest backend/tests/ -k "PULLBACK or pullback" -v` 全过 |
| T3 | 用 `setup_type='CAPITULATION'` 构造 `PositionCreate` / `PositionUpdate` / `PendingOrderCreate` / `PendingOrderUpdate` 不报 ValidationError | 单元 | 临时 REPL 验证（`python -c "from app.schemas.cockpit.position import PositionCreate; PositionCreate(ticker='X', entryPrice=100, entryDate='2026-05-15', shares=10, stopPrice=90, setupType='CAPITULATION')"`），结果记录到 Evaluator 报告，**不入测试套件**（NP-b2-1=A） |
| T4 | 用 `setupType='CAPITULATION'` 构造 4 个 AI schema input（`TradePlanInput` / `CandidateInput` / `ContradictionDetectorInput` / `TradeReviewPayload` / `ClosedTradeBrief`）不报 ValidationError | 单元 | 同 T3，REPL 验证（写到 Evaluator 报告） |
| T5 | grep 验证：6 文件中 `Literal[` 行恰好包含 `"CAPITULATION"`（防止漏改某文件） | 静态 | `grep -E 'Literal\[.*CAPITULATION' backend/app/schemas/cockpit/position.py backend/app/schemas/cockpit/pending_order.py backend/app/ai/schemas/trade_plan.py backend/app/ai/schemas/candidate_ranker.py backend/app/ai/schemas/contradiction_detector.py backend/app/ai/schemas/journal_assistant.py \| wc -l` 输出 6 |
| T6 | grep 验证：6 文件中 `"PULLBACK"` 字面量仍存在（向后兼容窗口未关） | 静态 | `grep -c '"PULLBACK"' backend/app/schemas/cockpit/position.py backend/app/schemas/cockpit/pending_order.py backend/app/ai/schemas/trade_plan.py backend/app/ai/schemas/candidate_ranker.py backend/app/ai/schemas/contradiction_detector.py backend/app/ai/schemas/journal_assistant.py` 每行均输出 ≥1 |
| T7 | **全量回归**：`uv run pytest backend/tests/ -x` 全通过；diff vs 开工前 = **0 新增失败**；F217-a 引入的 `test_capitulation_reversal.py` 与 F217-b1 引入的 `test_setup_snapshot_purge.py` 全部继续通过 | 集成 | pytest |

### 自检清单（Evaluator 模式）

- [ ] T1-T7 全部通过
- [ ] **Lint**：`ruff check backend/app/schemas/cockpit/position.py backend/app/schemas/cockpit/pending_order.py backend/app/ai/schemas/trade_plan.py backend/app/ai/schemas/candidate_ranker.py backend/app/ai/schemas/contradiction_detector.py backend/app/ai/schemas/journal_assistant.py` 无新增 warning
- [ ] **死代码**：无未使用 import；无遗留注释（如临时 `# TODO: remove PULLBACK`）
- [ ] **硬编码完整性**：6 个 Literal 元组的 8 个字面量集合（含 CAPITULATION 与 PULLBACK 共存）逐一目测一致
- [ ] **NP-b2-2 一致性**：CAPITULATION 在 6 处 Literal 中位置一致（紧邻 PULLBACK 之后）
- [ ] **不动 SYSTEM_PROMPT**：4 个 AI schema 的 SYSTEM_PROMPT 字符串未变更
- [ ] **不动 guardrail/BANNED_PHRASES**：无副作用改动
- [ ] **不动 cockpit_params.py / setup_service.py / cockpit/decision_service.py**：F217-a/b1 的工作区
- [ ] **claude-progress.txt** 追加 Generator 完成进度
- [ ] **不修改文档**：DATA-MODEL / API-CONTRACT / DECISIONS 本 sprint 不动（已在 F217 system-design 阶段落地）

### 代码质量自检

- [ ] 6 处改动每处只动 1 行（Literal 元组），其余文件内容字符级别不变（git diff 显示每文件 1 增 1 删，或 1 增 0 删如果在多行 Literal 中）
- [ ] `Literal[…]` 元素之间空格风格保持原样（`"BREAKOUT", "PULLBACK", "CAPITULATION", "RECLAIM"` 与原 Literal 间距一致）
- [ ] 不引入 try-except；不引入 print；不引入 inline 注释（理由：Literal 扩展自解释）

---

## 4. 开发顺序（Generator 模式逐步执行）

> ⚠️ 禁用 `git add -A`。每步显式列文件名。
> 6 处改动彼此独立，**Step 1-6 可任意顺序**；为简化 commit 颗粒度，按"cockpit schemas → AI schemas，单类内字母序"提交。
> Step 1 与 Step 2 合并为 1 个 wip commit（cockpit schemas 共 2 文件改动语义相同），Step 3-6 各 AI schema 独立 wip commit。

### Step 1+2 — Cockpit schemas（position + pending_order）

1. 改 `backend/app/schemas/cockpit/position.py` L11-13 `_VALID_SETUP_TYPES` 元组，在 `"PULLBACK"` 后插入 `"CAPITULATION"`
2. 改 `backend/app/schemas/cockpit/pending_order.py` L10-12 同样改动
3. 验证（最小）：`python -c "from app.schemas.cockpit.position import PositionCreate, _VALID_SETUP_TYPES; from app.schemas.cockpit.pending_order import PendingOrderCreate, _VALID_SETUP_TYPES as B; from typing import get_args; print(get_args(_VALID_SETUP_TYPES)); print(get_args(B))"` 应输出含 `'CAPITULATION'` 与 `'PULLBACK'`
4. WIP commit：
   ```bash
   git add backend/app/schemas/cockpit/position.py backend/app/schemas/cockpit/pending_order.py
   git commit -m "wip(F217-b2): cockpit schemas Literal +CAPITULATION (keep PULLBACK)"
   ```

### Step 3 — AI trade_plan

1. 改 `backend/app/ai/schemas/trade_plan.py` L45 `TradePlanInput.setupType` 内联 Literal
2. 验证：`python -c "from app.ai.schemas.trade_plan import TradePlanInput; t = TradePlanInput(ticker='X', setupType='CAPITULATION', entry=100, stop=90, target2r=120, target3r=130, size=10, rewardRisk=2.0, accountRiskPct=1.0, deterministicHash='abcdefgh'); print(t.setupType)"` 输出 `CAPITULATION`
3. WIP commit：
   ```bash
   git add backend/app/ai/schemas/trade_plan.py
   git commit -m "wip(F217-b2): trade_plan Literal +CAPITULATION"
   ```

### Step 4 — AI candidate_ranker

1. 改 `backend/app/ai/schemas/candidate_ranker.py` L42 `CandidateInput.setupType` 内联 Literal
2. 验证：构造 `CandidateInput(ticker='X', setupType='CAPITULATION', setupQuality='A', trendScore=4, rsPercentile=80, distanceToEntryPct=0.5, rewardRisk=2.0, earningsRisk='SAFE', readySignal=True)` 不报错
3. WIP commit：
   ```bash
   git add backend/app/ai/schemas/candidate_ranker.py
   git commit -m "wip(F217-b2): candidate_ranker Literal +CAPITULATION"
   ```

### Step 5 — AI contradiction_detector

1. 改 `backend/app/ai/schemas/contradiction_detector.py` L41 `_SETUP_TYPE` 别名（自动覆盖 `ContradictionDetectorInput.setupType`）
2. 验证：构造 `ContradictionDetectorInput(setupType='CAPITULATION', …)` 不报错（最小 fixture 即可）
3. WIP commit：
   ```bash
   git add backend/app/ai/schemas/contradiction_detector.py
   git commit -m "wip(F217-b2): contradiction_detector Literal +CAPITULATION"
   ```

### Step 6 — AI journal_assistant

1. 改 `backend/app/ai/schemas/journal_assistant.py` L52 `_SETUP_TYPE` 别名（自动覆盖 `TradeReviewPayload.setupType` / `ClosedTradeBrief.setupType`）
2. 验证：构造 `TradeReviewPayload(setupType='CAPITULATION', …)` 与 `ClosedTradeBrief(setupType='CAPITULATION', …)` 不报错
3. WIP commit：
   ```bash
   git add backend/app/ai/schemas/journal_assistant.py
   git commit -m "wip(F217-b2): journal_assistant Literal +CAPITULATION"
   ```

### Step 7 — 全量回归 + Final commit

1. 跑 T5 / T6 grep 校验（6 处 `CAPITULATION` 全在；6 处 `PULLBACK` 全在）
2. `uv run pytest backend/tests/ -x` 全跑一遍
3. 记录回归结果到 Evaluator 报告（T7）
4. 如有 b2 引入的新失败 → 回 Step N 修复，**计入熔断**（连续 3 次失败强制停止）
5. 全绿后：
   ```bash
   git add backend/app/schemas/cockpit/position.py \
           backend/app/schemas/cockpit/pending_order.py \
           backend/app/ai/schemas/trade_plan.py \
           backend/app/ai/schemas/candidate_ranker.py \
           backend/app/ai/schemas/contradiction_detector.py \
           backend/app/ai/schemas/journal_assistant.py
   git commit -m "feat(F217-b2): Pydantic schemas Literal +CAPITULATION (PULLBACK kept for b3 window)"
   ```
   不 squash WIP commits（保留 bisect 颗粒度）

---

## 5. 回滚方式

- **代码层**：6 个 wip commits 颗粒度，任意 step 失败可 `git reset --hard <prev-wip>` 退回；最坏情况 `git reset --hard <pre-b2>` 完全撤回
- **数据库层**：本 sprint **不动 DB**，无回滚需求
- **运行时**：Literal 扩展是纯加性，**无运行时风险**；任何已序列化 PULLBACK JSON / DB 行（注：DB 已经在 b1 软删）继续被接受
- **观察期**：本 sprint 完成后**无需观察期** — Literal 扩展在 b3 fixture 迁移开始前不会有任何上游产生 CAPITULATION Pydantic 输入（`decision_service` 在 F217-a 已能产生 CAPITULATION setup_type，但它不经过这 6 个 schema 的 Literal 校验路径；setup_service 写 setup_snapshots 用 ORM model 直存，不走 Pydantic 校验）

---

## 6. Generator 模式恢复指令（A-2）

```
继续开发 F217-b2，Sprint Contract 已确认。
读取 SESSION-HANDOFF.md + docs/开发/sprint-contracts/F217-b2-contract.md，
进入 Generator 模式，从 §4 开发顺序 Step 1+2（cockpit schemas）开始。
```

---

## 7. 风险与备注

- ⚠️ **6 文件命中上限，无 buffer**：如 Generator 期间发现遗漏的 Literal 定义点（如其它 schemas 文件、ai 任务的 prompt 模板），必须**停下来**二次协商，不得自行扩张到第 7 文件
- ⚠️ **Literal 顺序一致性**：6 处必须全部按 NP-b2-2=A 的顺序（紧邻 PULLBACK 之后），便于 b4 删 PULLBACK 时 diff 对齐
- ⚠️ **PULLBACK 暂保留**：本 sprint 完成后 PULLBACK 仍是 valid Literal — 所有现存 PULLBACK fixture/测试继续通过；b3 把 fixture 全部迁到 CAPITULATION/BREAKOUT 后，b4 才删 PULLBACK Literal 收紧
- ⚠️ **b3 串行依赖**：b2 完成 → b3 可启动（b3 的 fixture 改写依赖 b2 的 CAPITULATION Literal 已可用）；b3 完成才能跑 b4
- ⚠️ **CAPITULATION 写入路径**：本 sprint 不引入新的写入路径，但 F217-a 后 setup_service 已能写 setup_snapshots.setup_type='CAPITULATION'，且 b1 的 DB 层已支持。本 sprint 只是让"如果有 Pydantic 校验路径接收 CAPITULATION，不会被拒"。
- ⚠️ **AI Prompt 行为不变**：4 个 AI schema 的 SYSTEM_PROMPT 未提及 CAPITULATION；如 LLM 在 b3 fixture 测试中输出 setupType='CAPITULATION' 行为质量差，属 F217-c 范围（与前端 chips 同步）
- ⚠️ **父 feature F217 不升 done**：F217-b2 完成后 sub_sprints={a:done, b1:done, b2:done, b3:design_needed, b4:design_needed, c:design_needed}。父 status 保持 in_progress；consistency-check C1 应通过

---

## 8. 用户确认签字位

请确认以下条款（缺一项不可进 Generator）：

- [ ] **范围**：§1「包含/排除」边界 OK，6 文件清单准确（无新建测试文件，全部 6 个 schema 修改）
- [ ] **协商点**：NP-b2-1=A（不新建测试文件） / NP-b2-2=A（CAPITULATION 紧邻 PULLBACK 之后） / NP-b2-3=A（不抽共享别名） / NP-b2-4=A（不动 SYSTEM_PROMPT）
- [ ] **测试**：T1-T7 完成标准合理；T3/T4 REPL 验证只入 Evaluator 报告，不入测试套件
- [ ] **回滚**：纯加性 Literal 扩展无运行时风险；不引入 CAPITULATION_ENABLED flag

确认后我会：
1. 把 F217-b2 的 sub_sprint 状态从 `design_needed` 升 `contract_agreed`
2. features.json `_pipeline_status.active_sprint_phase` 更新为 `contract_agreed`
3. 在 F217.iteration_history 追加 contract_agreed 节点
4. 追加 claude-progress.txt
5. 生成 SESSION-HANDOFF.md
6. **停止**，让你开新 session 进 Generator 模式
