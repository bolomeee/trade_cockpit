# F217-b3 Sprint Contract — Cockpit Phase C 测试 fixture 批量去 PULLBACK

> 生成：2026-05-16 | 状态：草案 → 待用户确认
> Feature：[F217](docs/需求/features.json) Phase C — Capitulation Reversal 严格重写
> Sub-sprint：F217-b3（测试 fixture 批量去 PULLBACK，向后兼容窗口的最后一步）
> 前置：F217-a done @ 2026-05-15；F217-b1 done @ 2026-05-15；F217-b2 done @ 2026-05-16（Pydantic Literal 已含 CAPITULATION，PULLBACK 暂保留）；DATA-MODEL §SetupSnapshot 与 D095 已落地

---

## 1. 实现范围

### 包含

#### B3-a — 6 个测试 fixture 文件批量替换 `PULLBACK` → `CAPITULATION`

按父 sprint F217-b 规划，逐文件改 fixture 数据中 `PULLBACK` 字面量。**全部 9 行字面量替换，无逻辑改动**：

| # | 文件 | PULLBACK 出现位置 | 行数 | 改后 |
|---|------|------------------|------|------|
| 1 | `backend/tests/test_setup_f216d2.py` | L195 `preferred_setups=json.dumps(["BREAKOUT", "PULLBACK"])` | 1 | `…, "CAPITULATION"]` |
| 2 | `backend/tests/test_pool_service.py` | L393 `for signal_type in ("BREAKOUT", "PULLBACK"):` | 1 | `("BREAKOUT", "CAPITULATION")` |
| 3 | `backend/tests/test_ai_schemas_f211a1.py` | L350 `{"ticker": "MSFT", "setupType": "PULLBACK", …}` + L371 `{"setupType": "PULLBACK", "tradeCount": 1, …}` + L373 `"keyLessons": ["Continue to cut losses quickly on PULLBACK setups."]` | 3 | `"CAPITULATION"` × 2 + `"…on CAPITULATION setups."` |
| 4 | `backend/tests/test_regime_f201b.py` | L54 fixture `preferred_setups=json.dumps(["BREAKOUT", "PULLBACK"])` + L87 assert `data["preferredSetups"] == ["BREAKOUT", "PULLBACK"]` | 2 | `"CAPITULATION"` 同步两处 |
| 5 | `backend/tests/test_f215a.py` | L244 `preferred_setups=json.dumps(["BREAKOUT", "PULLBACK", "RECLAIM"])` | 1 | `"CAPITULATION"` |
| 6 | `backend/tests/test_decision_f203b2.py` | L81 `preferred_setups='["BREAKOUT","PULLBACK"]'` | 1 | `"CAPITULATION"` |

**合计 9 行替换**。每行都是字符串字面量级别的 `s/PULLBACK/CAPITULATION/`，**保留同一上下文语义**（同样是「用户偏好/扫描信号/closed trade fixture」），不引入新分支或新 setup_type 组合。

#### B3-b — 不动的内容

- **不改** 任何测试函数名（即使含 "pullback" 单词，函数名是历史命名，改名属 refactor 不在范围）
- **不改** 任何注释/docstring 中的 `PULLBACK` 字面量描述（属说明性文本；如 F217-a 已在 `test_setup_f202a.py::test_s15_pullback_zone_now_returns_none` 留下 `D095 / F217-a: SETUP_PULLBACK abolished` 注释，b3 不动）
- **不改** `test_capitulation_reversal.py`（F217-a 引入的 guard tests，故意断言 PULLBACK 已删，**不能**误改）
- **不改** `test_setup_snapshot_purge.py`（F217-b1 引入的 legacy 软删 integration tests，故意插入 PULLBACK 行验证 purge，**不能**误改）
- **不改** `test_signal_engine.py` / `test_signal_service.py` / `test_stock_detail.py` 中的 `pullback` / `Pullback` / `pullbackMarkers` — 这是**图表 pullback marker** 与 cockpit `setup_type` 完全无关的领域概念（详 v1.0 K线服务 / `app/models/pullback.py` / `app/services/signal_service.py::detect_pullbacks`），**绝对不能改**
- **不改** `test_market_api.py` / `test_market_scanner_detectors.py` 中的 `b2_ma_pullback` / `B2_MA_PULLBACK` — 这是 Market Breakout Scanner（F105）的信号 type，与 cockpit setup_type 完全独立，**绝对不能改**
- **不改** `test_setup_f202a.py` L104 `preferred_setups=json.dumps(["BREAKOUT", "PULLBACK"])` — 见 NP-b3-2（preferred_setups 是 `list[str]` 非 Literal，b4 不会破坏，保留无害）
- **不改** `test_ai_schemas_f209.py` L43/L52/L57/L163 中的小写 `"pullback"` — 这是 `setup_explainer` schema 的小写 Literal `Literal["pullback", "breakout", "reversal", …]`，F217-b2 未触及该 schema，b4 也不会触及（详 NP-b3-3）

### 排除（不在本 sprint）

- ❌ **`backend/tests/test_ai_gateway_e2e_f208c.py` L458 `setupType: "PULLBACK"` 迁移** — 详 NP-b3-1。该文件**不在父 F217-b 规划的 6 文件清单内**，但 b4 删 candidate_ranker Literal PULLBACK 后会直接破坏该 fixture。需用户决策（A. 纳入 b3 突破 6 文件上限 / B. 入 b4 让 b4 变 fixture+Literal 复合 sprint / C. 独立 b3.5 sprint）
- ❌ **Pydantic Literal 删 PULLBACK** — F217-b4
- ❌ **前端 cockpitDecisionApi SetupType / chips / 紫色 badge** — F217-c
- ❌ **`decision_service` 写入 capitulationEvidence 字段** — F217-c
- ❌ **`user_settings.preferred_setups` JSON 默认值迁移**（DB 已有用户偏好行）— F217-c 或独立微 sprint
- ❌ **新增 `CAPITULATION_ENABLED` flag** — D095 决策 6 应急方案，b 系列不引入

### 协商点（NP）

> 父 sprint F217-b 已确认 NP1=A（DB 软删）/ NP2=Y（Literal 暂保留 PULLBACK）。
> 子 sprint F217-b2 已确认 NP-b2-1~b2-4。
> 下面是 b3 子 sprint 内新出现的 3 个细决策，其中 NP-b3-1 是范围决策（影响是否突破 6 文件上限）。

| # | 议题 | 选项 | 推荐 | 理由 |
|---|------|------|------|------|
| **NP-b3-1** ⚠️ 范围决策 | `test_ai_gateway_e2e_f208c.py` L458（`_CR_INPUT.candidates[1].setupType = "PULLBACK"`）发现在父 F217-b 规划之外，未来 b4 会破坏。如何处置？ | A. **纳入本 b3 → 7 文件**（突破 6 文件上限 1 个，单行替换无新逻辑，最简单可执行）<br>B. **入 b4** → b4 由"纯 Literal 删除"变"fixture 1 行+Literal 收紧"复合 sprint<br>C. **独立 b3.5 sprint** 处理这 1 文件（开新 contract、新协商、新 commit 流程）<br>D. **保留 PULLBACK 字面量并 mark `pytest.skip` 该 fixture 中含 PULLBACK 的测试**（绕过验证，损失 1 test 覆盖） | **A** | 真正阻塞 b4 的是 fixture 漏改而非"6 文件硬性上限"——上限的本意是限制 sprint 复杂度，1 行 trivial 字符串替换不会增加复杂度；选项 B 把 b4 复杂化没必要；选项 C 为 1 文件开 sprint 噪音过大；选项 D 减少覆盖 unacceptable。**A 的实际 diff 与其他 6 文件同质，**唯一代价是文件数 7 而非 6。需用户**明确同意突破上限**，按 feature-dev 规则不得自行扩张。 |
| **NP-b3-2** | `test_setup_f202a.py` L104 `preferred_setups=["BREAKOUT","PULLBACK"]` 是否要同步迁移？ | A. 不动（保留 PULLBACK，b4 不会破坏因为 `preferred_setups` 是 `list[str]` 非 Literal）<br>B. 顺手改为 `CAPITULATION` 保持视觉一致 | **A** | `cockpit_settings.preferred_setups` 字段在所有处都是 `list[str]`（见 `app/models/market_regime_snapshot.py:26` + `app/schemas/cockpit/regime.py:50`），未走 Pydantic Literal 路径；b4 Literal 收紧不会影响该字段；这个 fixture 实际是 F202-a 用户偏好测试上下文，与"PULLBACK setup 类型存在"无强相关；**改它需把 test_setup_f202a.py 算入 b3 → 8 文件超上限**；保留无害。如果未来 D095 决策 5 `preferred_setups` 默认值迁移启动，再统一处理。 |
| **NP-b3-3** | `test_ai_schemas_f209.py` 中小写 `"pullback"` 是否在范围内？ | A. 不动（小写 `pullback` 是 `setup_explainer` schema 的独立 Literal，F217 全系列未触及）<br>B. 也改为 `"capitulation"` 同步语义 | **A** | `app/ai/schemas/setup_explainer.py:50 setup: Literal["pullback", "breakout", "reversal", "range", "gap_fill"]` — 这是另一套小写 setup type 字面量集合（F211 引入），与 cockpit `setup_type` 完全独立（cockpit 是 8 大写 enum：BREAKOUT/RECLAIM/EARNINGS_DRIFT/EXTENDED/BROKEN/NONE + 新增 CAPITULATION）；F217 任何阶段都不动 setup_explainer schema；保留无害。 |

---

## 2. 预计修改文件清单

### 主流（推荐 NP-b3-1=A 后）：7 个文件，**突破 6 文件上限 1 个**

| # | 路径 | 类型 | 改动幅度 |
|---|------|------|---------|
| 1 | `backend/tests/test_setup_f216d2.py` | 修改 | 1 行字面量替换 |
| 2 | `backend/tests/test_pool_service.py` | 修改 | 1 行字面量替换 |
| 3 | `backend/tests/test_ai_schemas_f211a1.py` | 修改 | 3 行字面量替换（2 fixture + 1 keyLessons 字符串） |
| 4 | `backend/tests/test_regime_f201b.py` | 修改 | 2 行字面量替换（1 fixture + 1 assert） |
| 5 | `backend/tests/test_f215a.py` | 修改 | 1 行字面量替换 |
| 6 | `backend/tests/test_decision_f203b2.py` | 修改 | 1 行字面量替换 |
| **7** ⚠️ | **`backend/tests/test_ai_gateway_e2e_f208c.py`** | 修改 | 1 行字面量替换（`_CR_INPUT.candidates[1].setupType`） |

合计 7 文件、10 行字面量替换。**全为 `s/PULLBACK/CAPITULATION/` 字符串替换**，无逻辑变更、无函数签名变更、无新增测试函数。

⚠️ **关于 6 文件上限**：feature-dev skill 规则要求超 6 必须停止并由用户授权。本 contract 在此暂停，**等用户明确同意 NP-b3-1=A 后**才进入 Generator。如用户选 B/C/D，按对应方案重组（B/D 维持 6 文件；C 把 7th 拆为独立 b3.5 contract）。

### 备选（NP-b3-1=B/C/D）：6 文件（同父 F217-b 规划）

如选 B：本 b3 仍是 6 文件；7th 留给 b4。
如选 C：本 b3 仍是 6 文件；7th 走 b3.5。
如选 D：本 b3 仍是 6 文件；7th 在 b4 用 `pytest.skip` 标记并接受测试覆盖损失。

---

## 3. 完成标准 — Evaluator 验收清单

### 测试矩阵（共 9 条）

| # | 测试描述 | 层级 | 工具 |
|---|---------|------|------|
| T1 | 6 (或 7，视 NP-b3-1) 文件中**所有 `PULLBACK` 字面量**已替换为 `CAPITULATION`（除排除清单中的合法保留） | 静态 | `grep -n '"PULLBACK"\|"\''PULLBACK'\''"' backend/tests/test_setup_f216d2.py backend/tests/test_pool_service.py backend/tests/test_ai_schemas_f211a1.py backend/tests/test_regime_f201b.py backend/tests/test_f215a.py backend/tests/test_decision_f203b2.py` 输出空（如 NP-b3-1=A，再 grep `test_ai_gateway_e2e_f208c.py` 也输出空） |
| T2 | 6 (或 7) 文件中存在 `"CAPITULATION"` 字面量（替换实际生效） | 静态 | `grep -c '"CAPITULATION"' …` 每行 ≥1 |
| T3 | `test_setup_f216d2.py` 单文件运行通过 | 集成 | `uv run pytest backend/tests/test_setup_f216d2.py -v` |
| T4 | `test_pool_service.py` 单文件运行通过 | 集成 | `uv run pytest backend/tests/test_pool_service.py -v` |
| T5 | `test_ai_schemas_f211a1.py` 单文件运行通过 | 集成 | `uv run pytest backend/tests/test_ai_schemas_f211a1.py -v` |
| T6 | `test_regime_f201b.py` 单文件运行通过（含 assert 断言改动） | 集成 | `uv run pytest backend/tests/test_regime_f201b.py -v` |
| T7 | `test_f215a.py` 单文件运行通过 | 集成 | `uv run pytest backend/tests/test_f215a.py -v` |
| T8 | `test_decision_f203b2.py` 单文件运行通过；如 NP-b3-1=A，再加 `test_ai_gateway_e2e_f208c.py` | 集成 | `uv run pytest backend/tests/test_decision_f203b2.py …` |
| T9 | **全量回归**：`uv run pytest backend/tests/ -x` 全通过；diff vs 开工前 = **0 新增失败**（预存失败 stash 沿用 b2 报告基线 1095 passed / 8 预存 skip/fail） | 集成 | pytest |

### 自检清单（Evaluator 模式）

- [ ] T1-T9 全部通过
- [ ] **Lint**：`ruff check backend/tests/test_setup_f216d2.py backend/tests/test_pool_service.py backend/tests/test_ai_schemas_f211a1.py backend/tests/test_regime_f201b.py backend/tests/test_f215a.py backend/tests/test_decision_f203b2.py` 无新增 warning（如 NP-b3-1=A 加 `test_ai_gateway_e2e_f208c.py`）
- [ ] **死代码**：替换后无遗留注释如 `# was PULLBACK`、无未使用 import
- [ ] **未误改排除清单文件**：`test_capitulation_reversal.py` / `test_setup_snapshot_purge.py` / `test_setup_f202a.py` / `test_ai_schemas_f209.py` / `test_signal_*.py` / `test_market_*.py` / `test_stock_detail.py` / `test_schema.py` 完全不动（`git diff --stat` 验证）
- [ ] **未改测试函数名**：函数名中如有 `pullback` 字串保留（保留 git blame 连续性）
- [ ] **未动 schema / service / router 任何 backend/app/ 文件**：`git diff --stat backend/app/` 输出空
- [ ] **断言改动一致**：`test_regime_f201b.py` L54 fixture 改 → L87 assert 也改（避免漏改一边导致测试假通过/假失败）
- [ ] **claude-progress.txt** 追加 Generator 完成进度

### 代码质量自检

- [ ] 每文件 git diff 行数 = 表 1 列「行数」（无意外改动）
- [ ] 6/7 文件改动均为字符串字面量替换，无新分支、无新 fixture、无新测试函数
- [ ] `keyLessons` 中 "Continue to cut losses quickly on PULLBACK setups." → "Continue to cut losses quickly on CAPITULATION setups."（保留句法，仅替换 setup 类型名）

---

## 4. 开发顺序（Generator 模式逐步执行）

> ⚠️ 禁用 `git add -A`。每步显式列文件名。
> 6 (或 7) 处改动彼此独立，无依赖关系。
> Step 顺序与父 sprint 文件清单一致，便于 commit log 对照。

### Step 1 — `test_setup_f216d2.py`

1. 改 L195 `preferred_setups=json.dumps(["BREAKOUT", "PULLBACK"])` → `["BREAKOUT", "CAPITULATION"]`
2. 验证：`uv run pytest backend/tests/test_setup_f216d2.py -v` 全过
3. WIP commit：
   ```bash
   git add backend/tests/test_setup_f216d2.py
   git commit -m "wip(F217-b3): test_setup_f216d2 fixture PULLBACK→CAPITULATION"
   ```

### Step 2 — `test_pool_service.py`

1. 改 L393 `for signal_type in ("BREAKOUT", "PULLBACK"):` → `("BREAKOUT", "CAPITULATION")`
2. 验证：`uv run pytest backend/tests/test_pool_service.py -v` 全过
3. WIP commit：
   ```bash
   git add backend/tests/test_pool_service.py
   git commit -m "wip(F217-b3): test_pool_service fixture PULLBACK→CAPITULATION"
   ```

### Step 3 — `test_ai_schemas_f211a1.py`

1. 改 L350 `setupType: "PULLBACK"` → `"CAPITULATION"`
2. 改 L371 `setupType: "PULLBACK"` → `"CAPITULATION"`
3. 改 L373 `"Continue to cut losses quickly on PULLBACK setups."` → `"…on CAPITULATION setups."`
4. 验证：`uv run pytest backend/tests/test_ai_schemas_f211a1.py -v` 全过
5. WIP commit：
   ```bash
   git add backend/tests/test_ai_schemas_f211a1.py
   git commit -m "wip(F217-b3): test_ai_schemas_f211a1 fixture PULLBACK→CAPITULATION"
   ```

### Step 4 — `test_regime_f201b.py`（注意 fixture + assert 双改）

1. 改 L54 fixture `preferred_setups=json.dumps(["BREAKOUT", "PULLBACK"])` → `["BREAKOUT", "CAPITULATION"]`
2. 改 L87 assert `data["preferredSetups"] == ["BREAKOUT", "PULLBACK"]` → `["BREAKOUT", "CAPITULATION"]`
3. 验证：`uv run pytest backend/tests/test_regime_f201b.py -v` 全过（特别确认 L87 assert 不再失败）
4. WIP commit：
   ```bash
   git add backend/tests/test_regime_f201b.py
   git commit -m "wip(F217-b3): test_regime_f201b fixture + assert PULLBACK→CAPITULATION"
   ```

### Step 5 — `test_f215a.py`

1. 改 L244 `preferred_setups=json.dumps(["BREAKOUT", "PULLBACK", "RECLAIM"])` → `["BREAKOUT", "CAPITULATION", "RECLAIM"]`
2. 验证：`uv run pytest backend/tests/test_f215a.py -v` 全过
3. WIP commit：
   ```bash
   git add backend/tests/test_f215a.py
   git commit -m "wip(F217-b3): test_f215a fixture PULLBACK→CAPITULATION"
   ```

### Step 6 — `test_decision_f203b2.py`

1. 改 L81 `preferred_setups='["BREAKOUT","PULLBACK"]'` → `'["BREAKOUT","CAPITULATION"]'`
2. 验证：`uv run pytest backend/tests/test_decision_f203b2.py -v` 全过
3. WIP commit：
   ```bash
   git add backend/tests/test_decision_f203b2.py
   git commit -m "wip(F217-b3): test_decision_f203b2 fixture PULLBACK→CAPITULATION"
   ```

### Step 7 — `test_ai_gateway_e2e_f208c.py`（仅在 NP-b3-1=A 时执行）

1. 改 L458 `_CR_INPUT.candidates[1]` 的 `"setupType": "PULLBACK"` → `"CAPITULATION"`
2. **不改** L485 `reason: "Solid pullback to support."`（自由文本 reason 不通过 Literal 校验，且与 setup_type enum 无强绑定；如要语义对齐，留给 F217-c 一起调整）
3. 验证：`uv run pytest backend/tests/test_ai_gateway_e2e_f208c.py -v` 全过
4. WIP commit：
   ```bash
   git add backend/tests/test_ai_gateway_e2e_f208c.py
   git commit -m "wip(F217-b3): test_ai_gateway_e2e_f208c CR input fixture PULLBACK→CAPITULATION (unblock b4 Literal tightening)"
   ```

### Step 8 — 全量回归 + Final commit

1. 跑 T1/T2 grep 校验
2. `uv run pytest backend/tests/ -x` 全跑
3. 记录回归结果到 Evaluator 报告（T9）
4. 如有 b3 引入的新失败 → 回 Step N 修复，**计入熔断**（连续 3 次失败强制停止）
5. 全绿后：
   ```bash
   git add backend/tests/test_setup_f216d2.py \
           backend/tests/test_pool_service.py \
           backend/tests/test_ai_schemas_f211a1.py \
           backend/tests/test_regime_f201b.py \
           backend/tests/test_f215a.py \
           backend/tests/test_decision_f203b2.py
   # 如 NP-b3-1=A，加：
   # backend/tests/test_ai_gateway_e2e_f208c.py
   git commit -m "feat(F217-b3): test fixtures PULLBACK→CAPITULATION (unblock b4 Literal tightening)"
   ```
   不 squash WIP commits（保留 bisect 颗粒度）

---

## 5. 回滚方式

- **代码层**：6 (或 7) WIP commits 颗粒度，任意 step 失败可 `git reset --hard <prev-wip>` 退回；最坏情况 `git reset --hard <pre-b3>` 完全撤回
- **数据库层**：本 sprint **不动 DB**，无回滚需求
- **运行时**：本 sprint **只动测试 fixture**，不动 production 代码，**无运行时风险**
- **观察期**：本 sprint 完成后**无需观察期** — fixture 替换在本 sprint 内已通过 T3-T8 单文件 + T9 全量回归验证

---

## 6. Generator 模式恢复指令（A-2）

```
继续开发 F217-b3，Sprint Contract 已确认。
读取 SESSION-HANDOFF.md + docs/开发/sprint-contracts/F217-b3-contract.md，
进入 Generator 模式，从 §4 开发顺序 Step 1（test_setup_f216d2.py）开始。
```

---

## 7. 风险与备注

- ⚠️ **NP-b3-1 是范围决策，影响是否突破 6 文件上限**：必须用户**明确同意 NP-b3-1=A** 才能进入 7 文件模式；选 B/C/D 时 b3 维持 6 文件、第 7 文件后置处理
- ⚠️ **`test_regime_f201b.py` 双改对称**：L54 fixture 和 L87 assert 必须同步改，否则断言会假失败或假通过
- ⚠️ **不要误改 keyLessons 中的 PULLBACK 字符串以外的内容**：`test_ai_schemas_f211a1.py` L373 是教训文本，只替换 setup 类型词，保留句法
- ⚠️ **不要误改 reason 字段中的自由文本**：`test_ai_gateway_e2e_f208c.py` L485 `"Solid pullback to support."` 是 LLM 解释性 reason，与 `setupType` 字面量无 Literal 绑定（F217-c 可视语义统一性决定是否一并迁移）
- ⚠️ **绝对不动排除清单**：详 §1 B3-b；误改 `test_capitulation_reversal.py` / `test_setup_snapshot_purge.py` 会破坏 F217-a/b1 的 guard tests
- ⚠️ **b4 串行依赖**：b3 done → b4 才能跑（b4 删 Literal 中的 PULLBACK，依赖 b3 fixture 已全部不含 PULLBACK）
- ⚠️ **父 feature F217 不升 done**：F217-b3 完成后 sub_sprints={a:done, b1:done, b2:done, b3:done, b4:design_needed, c:design_needed}。父 status 保持 in_progress；consistency-check C1 应通过
- ⚠️ **回归基线**：F217-b2 done 时全量回归 1095 passed / 8 预存（详 b2 acceptance 报告）。b3 完成时应保持 1095 passed + 0 新增失败

---

## 8. 用户确认签字位

请确认以下条款（缺一项不可进 Generator）：

- [ ] **NP-b3-1 选择**：A（7 文件 ✅ 推荐） / B / C / D
- [ ] **范围**：§1「包含/排除」边界 OK，文件清单准确，排除清单理解一致
- [ ] **协商点**：NP-b3-2=A（test_setup_f202a.py 不动） / NP-b3-3=A（setup_explainer 小写 pullback 不动）
- [ ] **测试**：T1-T9 完成标准合理；不新建测试文件
- [ ] **回滚**：纯 fixture 字面量替换无运行时风险

确认后我会：
1. 把 F217-b3 的 sub_sprint 状态从 `design_needed` 升 `contract_agreed`
2. features.json `_pipeline_status.active_sprint_phase` 更新为 `contract_agreed`
3. 在 F217.iteration_history 追加 contract_agreed 节点
4. 追加 claude-progress.txt
5. 生成 SESSION-HANDOFF.md
6. **停止**，让你开新 session 进 Generator 模式
