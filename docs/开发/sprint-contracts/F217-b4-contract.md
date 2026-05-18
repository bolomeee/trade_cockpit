# F217-b4 Sprint Contract — Cockpit Phase C Pydantic Literal 收紧（删 PULLBACK）

> 生成：2026-05-16 | 状态：草案 → 待用户确认
> Feature：[F217](docs/需求/features.json) Phase C — Capitulation Reversal 严格重写
> Sub-sprint：F217-b4（Pydantic Literal 收紧，向后兼容窗口关闭）
> 前置：
>   - F217-a done @ 2026-05-15（cockpit_params / setup_service 重写）
>   - F217-b1 done @ 2026-05-15（DB legacy 列 + purge_legacy_pullback）
>   - F217-b2 done @ 2026-05-16（6 schema Literal +CAPITULATION 保留 PULLBACK）
>   - F217-b3 done @ 2026-05-16（7 测试 fixture PULLBACK→CAPITULATION）

---

## 1. 实现范围

### 包含

#### B4-a — 6 个 Pydantic schema 的 Literal 收紧

从每个 schema 现有 `setup_type` / `setupType` Literal 定义中**删除** `"PULLBACK"` 字面量。CAPITULATION 与其余 6 个字面量保留，元组缩为 7 元素：

| # | 文件 | Literal 形式 | 行号 | 改后值 |
|---|------|-------------|------|--------|
| 1 | `backend/app/schemas/cockpit/position.py` | 模块别名 `_VALID_SETUP_TYPES` | L12 | `"BREAKOUT", "CAPITULATION", "RECLAIM", "EARNINGS_DRIFT", "EXTENDED", "BROKEN", "NONE"` |
| 2 | `backend/app/schemas/cockpit/pending_order.py` | 模块别名 `_VALID_SETUP_TYPES` | L11 | 同上 |
| 3 | `backend/app/ai/schemas/trade_plan.py` | 内联 Literal `TradePlanInput.setupType` | L45 | 同上 |
| 4 | `backend/app/ai/schemas/candidate_ranker.py` | 内联 Literal `CandidateInput.setupType` | L42 | 同上 |
| 5 | `backend/app/ai/schemas/contradiction_detector.py` | 模块别名 `_SETUP_TYPE` | L41 | 同上 |
| 6 | `backend/app/ai/schemas/journal_assistant.py` | 模块别名 `_SETUP_TYPE` | L52 | 同上 |

> 删除位置：CAPITULATION 紧邻 PULLBACK 之后（b2 NP-b2-2=A 已对齐），diff 仅 `-"PULLBACK", `，与 b2 增量形成镜像。

#### B4-b — 必须保留（不动）

- `backend/app/repositories/setup_snapshot_repository.py:42-45` `purge_legacy_pullback()` 方法
  - 函数名、docstring、`.where(SetupSnapshot.setup_type == "PULLBACK")` 中的 PULLBACK 字符串**必须保留** — 这是 b1 的 DB 行幂等清理方法，查询的是历史 DB 字符串数据，与 Pydantic Literal 完全独立
- `backend/tests/test_ai_gateway_e2e_f208c.py:485` `"Solid pullback to support."` 自由文本 `reason` 字段（b3 NP-b3-3 已确认保留）
- `backend/tests/test_setup_f202a.py:104` `preferred_setups=json.dumps(["BREAKOUT", "PULLBACK"])`（b3 NP-b3-2 已确认：`user_settings.preferred_setups` 是 `list[str]` 非 Literal，b4 不破）
- `backend/tests/test_setup_f202a.py:354-368` 函数名 `test_s15_pullback_zone_now_returns_none` + 注释 — 描述 D095/F217-a 的历史背景，无 Pydantic 构造
- `backend/tests/test_stock_detail.py` / `test_signal_*.py` / `test_market_scanner_detectors.py` / `test_schema.py` 中的小写 `pullback` — 图表 marker / signal engine / B2_MA_PULLBACK 信号，与 cockpit setup_type 完全独立
- 任何 `SYSTEM_PROMPT` / `BANNED_PHRASES` / `guardrail()` — b2 NP-b2-4=A 已确认不动

### 排除（不在本 sprint）

- ❌ **前端 cockpitDecisionApi `SetupType` 类型 / chips / 紫色 badge** — F217-c
- ❌ **`decision_service` 写入 `capitulationEvidence` 字段** — F217-c
- ❌ **`user_settings.preferred_setups` JSON 默认值迁移 `PULLBACK → CAPITULATION`** — F217-c 或独立微 sprint（API-CONTRACT 文档已更新默认值，但运行时迁移未做）
- ❌ **新增 `CAPITULATION_ENABLED` flag** — D095 决策 6 应急方案，b 系列不引入
- ❌ **`purge_legacy_pullback()` 调用编排到 startup / cron** — 该方法目前是手工触发，编排属独立运维任务
- ❌ **AI schema `reason` 自由文本中 "pullback" 词的政策性禁用** — 不是 Literal 范围
- ❌ **抽出共享 Literal 别名模块** — b2 NP-b2-3=A 已确认 YAGNI

### 协商点（NP）

> 父 sprint F217-b 已确认 NP1=A（DB 软删）/ NP2=Y（Literal 暂保留后再删）。
> b2 已确认 NP-b2-1=A（不新建测试文件）/ NP-b2-2=A（CAPITULATION 紧邻 PULLBACK 后）/ NP-b2-3=A（不抽别名）/ NP-b2-4=A（不动 prompt）。
> b3 已确认 NP-b3-1=A（突破 6 文件上限至 7）/ NP-b3-2=A（user_settings JSON 不动）/ NP-b3-3=A（reason 自由文本不动）。
> 下面是 b4 子 sprint 新出现的 3 个细决策。

| # | 议题 | 选项 | 推荐 | 理由 |
|---|------|------|------|------|
| **NP-b4-1** | 是否新建"负断言"测试守护 PULLBACK 不再可接受 | A. 不新建测试文件，T3 用 REPL 验证 ValidationError 写入 Evaluator 报告<br>B. 新建 `backend/tests/test_schemas_pullback_rejected.py`（6 schemas × 1 参数化测试）<br>C. inline 加 6 行断言到 `test_ai_schemas_f211a1.py` | **A** | 6 文件命中上限无 buffer；负断言一旦写入会变成"反向 fixture 维护负担"（未来若需要重新接受类似旧字面量，会绊倒）；T1 grep 守护（"6 文件 Literal 行 0 命中 PULLBACK"）已是结构化防回归；T7 全量回归自然暴露任何漏改的构造点；选项 B/C 会让 b4 文件数 6→7 超上限且违背"删 Literal = 纯减法"语义 |
| **NP-b4-2** | 删除时的精确 diff 形态 | A. 单行删字面量 + 一个逗号 + 一个空格（`-    "BREAKOUT", "PULLBACK", "CAPITULATION", ...` → `+    "BREAKOUT", "CAPITULATION", ...`），git diff 显示每文件 1 增 1 删<br>B. 跨多行重排（每个 Literal 元素一行） | **A** | b2 加 CAPITULATION 时已用 A 形式（紧邻 PULLBACK 后插入单 token），本 sprint 反向操作保持 diff 对称；B 形式会污染 6 文件 git blame；现行单行紧凑形式可读性已足够（7 字面量 ≤ 80 字符宽） |
| **NP-b4-3** | 是否在 DECISIONS.md 追加 b4 收紧的小决策记录 | A. 不追加 — D095 已记录"枚举替换 PULLBACK→CAPITULATION"，b4 是 D095 决策的实施收尾<br>B. 追加 D095.7「Literal 收紧时序：b2 加 → b3 fixture 迁移 → b4 删」<br>C. 追加独立编号 D096 | **A** | D095 决策本身已明确替换语义；b 系列拆分时序在 F217.sub_sprint_notes + b2/b3/b4 contracts 中可追溯；DECISIONS 应承载"为什么这样定"而非"按什么顺序执行"；若用户希望保留时序记录，可走 B（追加 D095.7），不建议 C |

---

## 2. 预计修改文件清单（6 个，全部修改无新建）

| # | 路径 | 类型 | 改动幅度 |
|---|------|------|---------|
| 1 | `backend/app/schemas/cockpit/position.py` | 修改 | 1 处 Literal 元组 −1 字面量 |
| 2 | `backend/app/schemas/cockpit/pending_order.py` | 修改 | 1 处 Literal 元组 −1 字面量 |
| 3 | `backend/app/ai/schemas/trade_plan.py` | 修改 | 1 处 inline Literal −1 字面量 |
| 4 | `backend/app/ai/schemas/candidate_ranker.py` | 修改 | 1 处 inline Literal −1 字面量 |
| 5 | `backend/app/ai/schemas/contradiction_detector.py` | 修改 | 1 处 Literal 别名 −1 字面量 |
| 6 | `backend/app/ai/schemas/journal_assistant.py` | 修改 | 1 处 Literal 别名 −1 字面量 |

✅ 6 文件命中上限，**无 buffer**。如 Generator 期间发现遗漏的 Literal 定义点必须停下来二次协商。

---

## 3. 完成标准 — Evaluator 验收清单

### 测试矩阵（共 7 条，无新增 test 文件，依赖现有套件 + 全量回归 + 静态 grep + REPL）

| # | 测试描述 | 层级 | 工具 |
|---|---------|------|------|
| T1 | grep 验证：6 文件中 `Literal[` / `_VALID_SETUP_TYPES` / `_SETUP_TYPE` 行**不再包含** `"PULLBACK"` | 静态 | `grep -E '"PULLBACK"' backend/app/schemas/cockpit/position.py backend/app/schemas/cockpit/pending_order.py backend/app/ai/schemas/trade_plan.py backend/app/ai/schemas/candidate_ranker.py backend/app/ai/schemas/contradiction_detector.py backend/app/ai/schemas/journal_assistant.py` 输出为空（exit 1） |
| T2 | grep 验证：6 文件中 `"CAPITULATION"` 字面量仍存在 | 静态 | `grep -c '"CAPITULATION"' <6 files>` 每行 ≥1 |
| T3 | REPL 验证：用 `setup_type='PULLBACK'` 构造 6 schema 的 Create/Update/Input 全部抛 `pydantic.ValidationError`（写入 Evaluator 报告，不入测试套件 NP-b4-1=A） | 单元 | `python -c "from pydantic import ValidationError; from app.schemas.cockpit.position import PositionCreate; try: PositionCreate(...setupType='PULLBACK'); except ValidationError as e: print('OK', e.errors()[0]['type'])"` 输出 `OK literal_error`（对 6 schema 各跑一次） |
| T4 | REPL 验证：用 `setup_type='CAPITULATION'` 构造 6 schema 不抛错（保留 b2 接受性） | 单元 | 同 T3 模式但期望成功，写入 Evaluator 报告 |
| T5 | 现有 `purge_legacy_pullback()` 测试继续通过（验证：删 Literal PULLBACK 不影响 DB 字符串查询） | 集成 | `uv run pytest backend/tests/test_setup_snapshot_purge.py -v` 全过 |
| T6 | 现有 `test_setup_f202a.py::test_s15_pullback_zone_now_returns_none` 与 `preferred_setups=json.dumps(["BREAKOUT", "PULLBACK"])` 用例继续通过（验证：JSON list[str] 不受 Literal 收紧影响） | 集成 | `uv run pytest backend/tests/test_setup_f202a.py -v` 全过 |
| T7 | **全量回归**：`uv run pytest backend/tests/` 全跑；diff vs F217-b3 done 基线 = **0 新增失败**；F217-a `test_capitulation_reversal.py`（34 tests）+ F217-b1 `test_setup_snapshot_purge.py`（12 tests）+ F217-b2 b2 集成 + F217-b3 b3 迁移后的 7 文件全部继续通过 | 集成 | pytest |

### 自检清单（Evaluator 模式）

- [ ] T1-T7 全部通过
- [ ] **Lint**：`ruff check backend/app/schemas/cockpit/position.py backend/app/schemas/cockpit/pending_order.py backend/app/ai/schemas/trade_plan.py backend/app/ai/schemas/candidate_ranker.py backend/app/ai/schemas/contradiction_detector.py backend/app/ai/schemas/journal_assistant.py` 无新增 warning（接受 F217-b2 已识别的预存 position.py F401 unused import — 非本 sprint 引入）
- [ ] **死代码**：无 b2/b3 期间遗留的 `# TODO: remove PULLBACK after b4` 注释（如有，b4 一并删除）
- [ ] **diff 对称性**：6 个文件 git diff 形态 = "1 行修改：-`"BREAKOUT", "PULLBACK", "CAPITULATION", ...` +`"BREAKOUT", "CAPITULATION", ...`"，与 b2 的镜像反向
- [ ] **CAPITULATION 字面量位置不动**：6 处 CAPITULATION 仍紧邻 BREAKOUT 之后（b2 NP-b2-2 顺序保持）
- [ ] **不动 SYSTEM_PROMPT**：4 个 AI schema 的 SYSTEM_PROMPT 未变更（grep 验证 `SYSTEM_PROMPT` 块字节级别一致）
- [ ] **不动 guardrail/BANNED_PHRASES**：无副作用改动
- [ ] **不动 prod 代码**：`backend/app/services/` / `backend/app/routers/` / `backend/app/repositories/` 零变更（grep 6 文件之外 git diff 应为空）
- [ ] **不动 `purge_legacy_pullback`**：`setup_snapshot_repository.py:42-45` 字节级别一致（关键 DB 历史数据清理路径）
- [ ] **claude-progress.txt** 追加 Generator + Evaluator 完成进度
- [ ] **不修改文档**：DATA-MODEL / API-CONTRACT 本 sprint 不动（b 系列已在 F217 system-design 阶段落地）；DECISIONS 按 NP-b4-3=A 不追加

### 代码质量自检

- [ ] 6 处改动每处只动 1 行 Literal，其余文件内容字符级别不变（git diff 显示每文件 1 增 1 删）
- [ ] 删除时仅删 `"PULLBACK", `（含末尾逗号 + 空格），不留多余空格或孤逗号
- [ ] 不引入 try-except；不引入 print；不引入 inline 注释（理由：Literal 收紧自解释）

### 回归测试（必选）

完成 T1-T6 后，跑全量套件 T7：

| 测试范围 | 通过 | 失败 | 跳过 |
|---------|------|------|------|
| 6 schema 文件相关 import / round-trip（T3+T4 REPL） | 6/6 + 6/6 | 0 | 0 |
| `test_setup_snapshot_purge.py` | 12/12 | 0 | 0 |
| `test_setup_f202a.py` | N/N | 0 | 0 |
| **全量回归** | 1095/1095 | 8（预存非本 sprint） | – |

> 注：F217-b3 done 时基线为 `1095 passed 8 预存失败`。b4 完成后必须严格对齐该数字，否则视为 b4 引入新失败。

---

## 4. 开发顺序（Generator 模式逐步执行）

> ⚠️ 禁用 `git add -A`。每步显式列文件名。
> 6 处改动彼此独立，**Step 1-6 顺序与 b2 镜像**（cockpit schemas → AI schemas，单类内字母序）。
> Step 1 与 Step 2 合并为 1 wip commit（cockpit schemas 共 2 文件改动语义相同），Step 3-6 各 AI schema 独立 wip commit。

### Step 1+2 — Cockpit schemas（position + pending_order）

1. 改 `backend/app/schemas/cockpit/position.py:12` `_VALID_SETUP_TYPES` 元组，删除 `"PULLBACK", `
2. 改 `backend/app/schemas/cockpit/pending_order.py:11` 同样改动
3. 验证（最小）：
   ```bash
   python -c "from app.schemas.cockpit.position import _VALID_SETUP_TYPES as A; from app.schemas.cockpit.pending_order import _VALID_SETUP_TYPES as B; from typing import get_args; assert 'PULLBACK' not in get_args(A); assert 'PULLBACK' not in get_args(B); assert 'CAPITULATION' in get_args(A); print('OK')"
   ```
4. WIP commit：
   ```bash
   git add backend/app/schemas/cockpit/position.py backend/app/schemas/cockpit/pending_order.py
   git commit -m "wip(F217-b4): cockpit schemas Literal -PULLBACK"
   ```

### Step 3 — AI trade_plan

1. 改 `backend/app/ai/schemas/trade_plan.py:45` `TradePlanInput.setupType` 内联 Literal，删除 `"PULLBACK", `
2. 验证：
   ```bash
   python -c "from pydantic import ValidationError; from app.ai.schemas.trade_plan import TradePlanInput; \
   try: TradePlanInput(ticker='X', setupType='PULLBACK', entry=100, stop=90, target2r=120, target3r=130, size=10, rewardRisk=2.0, accountRiskPct=1.0, deterministicHash='abcdefgh'); raise AssertionError('should have rejected') \
   except ValidationError: print('OK rejected'); \
   t=TradePlanInput(ticker='X', setupType='CAPITULATION', entry=100, stop=90, target2r=120, target3r=130, size=10, rewardRisk=2.0, accountRiskPct=1.0, deterministicHash='abcdefgh'); assert t.setupType=='CAPITULATION'; print('OK accepted')"
   ```
3. WIP commit：
   ```bash
   git add backend/app/ai/schemas/trade_plan.py
   git commit -m "wip(F217-b4): trade_plan Literal -PULLBACK"
   ```

### Step 4 — AI candidate_ranker

1. 改 `backend/app/ai/schemas/candidate_ranker.py:42` `CandidateInput.setupType` 内联 Literal，删除 `"PULLBACK", `
2. 验证：构造 `CandidateInput(..., setupType='PULLBACK', ...)` 抛 ValidationError；`setupType='CAPITULATION'` 仍通过
3. WIP commit：
   ```bash
   git add backend/app/ai/schemas/candidate_ranker.py
   git commit -m "wip(F217-b4): candidate_ranker Literal -PULLBACK"
   ```

### Step 5 — AI contradiction_detector

1. 改 `backend/app/ai/schemas/contradiction_detector.py:41` `_SETUP_TYPE` 别名，删除 `"PULLBACK", `
2. 验证：`ContradictionDetectorInput(setupType='PULLBACK', ...)` 抛 ValidationError；`setupType='CAPITULATION'` 通过
3. WIP commit：
   ```bash
   git add backend/app/ai/schemas/contradiction_detector.py
   git commit -m "wip(F217-b4): contradiction_detector Literal -PULLBACK"
   ```

### Step 6 — AI journal_assistant

1. 改 `backend/app/ai/schemas/journal_assistant.py:52` `_SETUP_TYPE` 别名（自动覆盖 `TradeReviewPayload.setupType` / `ClosedTradeBrief.setupType`），删除 `"PULLBACK", `
2. 验证：`TradeReviewPayload(setupType='PULLBACK', ...)` 与 `ClosedTradeBrief(setupType='PULLBACK', ...)` 抛 ValidationError；`'CAPITULATION'` 通过
3. WIP commit：
   ```bash
   git add backend/app/ai/schemas/journal_assistant.py
   git commit -m "wip(F217-b4): journal_assistant Literal -PULLBACK"
   ```

### Step 7 — 全量回归 + Final commit

1. 跑 T1（grep PULLBACK = 空）/ T2（grep CAPITULATION = 6 行）静态校验
2. 跑 T3+T4 REPL 矩阵（6 schema × 拒绝 + 接受），结果记入 Evaluator 报告
3. 跑 T5（test_setup_snapshot_purge）+ T6（test_setup_f202a）局部回归
4. 跑 T7 全量回归 `uv run pytest backend/tests/`，对齐 b3 done 基线 `1095 passed 8 预存失败 0 新增失败`
5. 如有 b4 引入新失败 → 回 Step N 修复，**计入熔断**（连续 3 次失败强制停止并报告）
6. 全绿后 Final commit：
   ```bash
   git add backend/app/schemas/cockpit/position.py \
           backend/app/schemas/cockpit/pending_order.py \
           backend/app/ai/schemas/trade_plan.py \
           backend/app/ai/schemas/candidate_ranker.py \
           backend/app/ai/schemas/contradiction_detector.py \
           backend/app/ai/schemas/journal_assistant.py
   git commit -m "feat(F217-b4): Pydantic schemas Literal -PULLBACK (backward-compat window closed)"
   ```
   不 squash WIP commits（保留 bisect 颗粒度，与 b2/b3 风格一致）

---

## 5. 回滚方式

- **代码层**：6 个 wip commits 颗粒度，任意 step 失败可 `git reset --hard <prev-wip>` 退回；最坏情况 `git reset --hard <pre-b4>` 完全撤回（即恢复 b2 等价状态：6 schema Literal 含 PULLBACK + CAPITULATION）
- **数据库层**：本 sprint **不动 DB**，无回滚需求；`purge_legacy_pullback()` 方法 + 历史 PULLBACK 行的 `legacy=True` 标记保持不变
- **运行时**：纯减法 Literal 收紧。**风险**：若 b3 漏改某个测试 fixture 仍构造 `setup_type='PULLBACK'`，b4 后该测试会立刻失败（这是预期信号，不是 bug）。修复路径：补改 fixture（不计入 b4 文件数 — 视为 b3 补丁，独立 `chore(F217-b3): patch missed PULLBACK fixture` commit）
- **观察期**：b4 完成后**无需观察期** — 后续 F217-c 在前端类型与 chips 加 CAPITULATION 时，b4 收紧已为类型联合声明做完最后清理

---

## 6. Generator 模式恢复指令（A-2）

```
继续开发 F217-b4，Sprint Contract 已确认。
读取 SESSION-HANDOFF.md + docs/开发/sprint-contracts/F217-b4-contract.md，
进入 Generator 模式，从 §4 开发顺序 Step 1+2（cockpit schemas）开始。
```

---

## 7. 风险与备注

- ⚠️ **6 文件命中上限，无 buffer**：如 Generator 期间发现遗漏的 Literal 定义点（如其它 schemas 文件、Annotated 类型别名），必须**停下来**二次协商，不得自行扩张到第 7 文件
- ⚠️ **b3 完整性依赖**：b4 删 PULLBACK 字面量后，任何残留构造 `setup_type='PULLBACK'` 的 Pydantic 调用会立刻抛 ValidationError。b3 验收时已逐文件 grep 验证 7 个迁移文件无 PULLBACK 残留，且全量回归通过 — b4 风险窗口已最小化。如全量回归仍出现 PULLBACK 相关失败，按 §5 回滚路径补 fixture
- ⚠️ **不触动 `purge_legacy_pullback`**：该方法的 `"PULLBACK"` 字符串是 DB 行数据查询条件（针对 b1 之前历史写入的 setup_snapshots 行），与 Pydantic Literal 完全独立。绝对不能因为"统一去 PULLBACK"误删
- ⚠️ **AI Prompt 行为不变**：4 个 AI schema 的 SYSTEM_PROMPT 未提及 PULLBACK 也未提及 CAPITULATION（b2 NP-b2-4=A 已确认 prompt 不枚举 setup_type），b4 不动 prompt 安全
- ⚠️ **父 feature F217 不升 done**：F217-b4 完成后 sub_sprints={a:done, b1:done, b2:done, b3:done, b4:done, c:design_needed}。父 status 保持 in_progress；consistency-check C1 应通过（c 未 done 父不升）；c 才是 F217 收官
- ⚠️ **`user_settings.preferred_setups` JSON 默认值未运行时迁移**：API-CONTRACT 已声明默认 `PULLBACK → CAPITULATION`，但 b4 不动 DB JSON 字段。若用户安装时 user_settings 含 `["BREAKOUT", "PULLBACK"]`，运行时该字符串作为 list[str] 仍合法（不走 Literal）；前端 chips 在 F217-c 才解释 CAPITULATION 含义 — 本 sprint 影响为零
- ⚠️ **F217-c 解锁**：b4 完成后 b 系列全部 done，c 可启动；前端类型 `SetupType` 同样需要做 PULLBACK→CAPITULATION 切换 + chips/badge UI（c 子 sprint 自己的 Contract 协商）

---

## 8. 用户确认签字位

请确认以下条款（缺一项不可进 Generator）：

- [ ] **范围**：§1「包含/排除」边界 OK，6 文件清单准确（无新建测试文件，全部 6 个 schema 修改，删字面量 + 一个逗号 + 一个空格）
- [ ] **协商点**：NP-b4-1=A（不新建负断言测试，REPL 入报告）/ NP-b4-2=A（单行删字面量保 diff 对称）/ NP-b4-3=A（不追加 DECISIONS 记录，D095 已覆盖）
- [ ] **测试**：T1-T7 完成标准合理；T3/T4 REPL 验证只入 Evaluator 报告，不入测试套件；T7 对齐 b3 done 基线 `1095 passed 8 预存`
- [ ] **回滚**：纯减法 Literal 收紧，唯一风险窗口是 b3 遗漏的 fixture 残留（b3 验收已 grep + 全量回归双重防御）
- [ ] **保留项**：`purge_legacy_pullback` 中的 PULLBACK 字符串 / `test_ai_gateway_e2e_f208c.py:485` 自由文本 / `test_setup_f202a.py:104` JSON list[str] 三处必须保留不动

确认后我会：
1. 把 F217-b4 的 sub_sprint 状态从 `design_needed` 升 `contract_agreed`
2. features.json `_pipeline_status.active_sprint_phase` 更新为 `contract_agreed`
3. 在 F217.iteration_history 追加 contract_agreed 节点
4. 追加 claude-progress.txt
5. 生成 SESSION-HANDOFF.md
6. **停止**，让你开新 session 进 Generator 模式
