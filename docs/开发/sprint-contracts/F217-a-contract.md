# F217-a Sprint Contract — Cockpit Phase C 后端 setup_service 重写

> 生成：2026-05-15 | 状态：草案 → 待用户确认
> Feature：[F217](docs/需求/features.json) Phase C — Capitulation Reversal 严格重写
> Sub-sprint：F217-a (C1 + C2 + C3 后端逻辑重写)
> 前置：DATA-MODEL / API-CONTRACT / DECISIONS frontmatter status=confirmed @ 2026-05-15；D095 已落地

---

## 1. 实现范围

### 包含

#### C1 — cockpit_params.py 参数层重写
- `SETUP.TYPES` 列表：移除 `"PULLBACK"`，新增 `"CAPITULATION"`（保持其它 6 个不变）
- `SETUP.REGIME_PREFERRED_SETUPS`（5 个 regime keys）：`"PULLBACK"` → `"CAPITULATION"`
- `SETUP.REGIME_AVOID_SETUPS`（5 个 regime keys）：`"PULLBACK"` → `"CAPITULATION"`
- **删除** 4 个 PULLBACK Pydantic Field：`PULLBACK_ZONE_ABOVE_MA50_PCT` / `PULLBACK_STOP_MA21_PCT` / `PULLBACK_FLOOR_MA50_PCT` / `PULLBACK_FALLBACK_SUPPORT_PCT`
- **新增** 10 个 CAPITULATION_* Pydantic Field：

| Field | 类型 | 默认 | range | 用途 |
|-------|------|------|-------|------|
| `CAPITULATION_DROP_LOOKBACK_MIN_DAYS` | int | 5 | 3–15 | 条件 1 累计跌幅滑动窗最小天数 |
| `CAPITULATION_DROP_LOOKBACK_MAX_DAYS` | int | 10 | 5–20 | 条件 1 累计跌幅滑动窗最大天数 |
| `CAPITULATION_DROP_PCT` | float | 10.0 | 5–30 | 条件 1 累计跌幅阈值（绝对值百分比） |
| `CAPITULATION_VOL_Z_MIN` | float | 2.5 | 1.5–5.0 | 条件 2 当日 volume z-score 下限 |
| `CAPITULATION_ATR_TR_MULTIPLIER` | float | 2.0 | 1.5–4.0 | 条件 3 当日 true_range / ATR14 倍数下限 |
| `CAPITULATION_CLOSE_UPPER_BIN` | float | 0.333 | 0.1–0.5 | 条件 4 close 在 (high–low) 范围内上 X 分位起算的"脱底" |
| `CAPITULATION_NO_NEW_LOW_LOOKAHEAD_DAYS` | int | 2 | 1–5 | 条件 5 次日不创新低观察窗 |
| `CAPITULATION_SWING_LOW_LOOKBACK` | int | 30 | 10–60 | 条件 6 swing low 检测窗 |
| `CAPITULATION_RS_NO_NEW_LOW_DAYS` | int | 5 | 3–15 | 条件 7 RS line 未创新低观察窗 |
| `CAPITULATION_STOP_BUFFER_PCT` | float | 1.5 | 0.5–5.0 | stop 在当日 low 下方的安全垫 |

#### C2 — setup_service.py 核心重写
- `SETUP_PULLBACK = "PULLBACK"` → `SETUP_CAPITULATION = "CAPITULATION"`
- `_ACTIONABLE_TYPES` 同步：`{BREAKOUT, CAPITULATION, RECLAIM, EARNINGS_DRIFT}`
- **新增** 局部 helper `_compute_atr_value(highs, lows, closes, period)` → 调用 `_indicators.compute_wilder_atr(...)[-1]`（标量返回 latest ATR）
- **新增** `_detect_swing_lows(lows: list[float], lookback: int) -> list[int]`：返回 swing low 索引降序列表（swing low = `lows[i] < lows[i-1] and lows[i] < lows[i+1]`，仅看后 `lookback` 个 bars）
- **新增** `_is_capitulation_reversal(closes, highs, lows, volumes, spy_closes) -> bool`：实现 7 条 AND 门（详见第 3 节 T4-T7）
- **删除** `_classify_setup_type` 中 PULLBACK 分支（原 L161-170）及所有 `SETUP.PULLBACK_*` 引用
- **删除** `_is_pullback` 函数（如存在 — 当前是 inline 在 `_classify_setup_type` 中无独立函数，删除其分支即可）

#### C3 — _classify_setup_type 优先级升级
- 新优先级：`BROKEN → EXTENDED → EARNINGS_DRIFT → CAPITULATION → BREAKOUT → RECLAIM → NONE`
- CAPITULATION 与 BREAKOUT/RECLAIM 互斥（同一日同标的命中 CAPITULATION 后短路返回）
- 函数签名扩展：增加 `volumes: list[int]` + `spy_closes: list[float]` 参数（CAPITULATION 判定所需），`compute_and_store_all` 调用处同步传参
- CAPITULATION 命中时计算：
  - `entry = round(closes[-1] * (1 + SETUP.ENTRY_TICK_PCT / 100), 4)`
  - `stop = round(lows[-1] * (1 - SETUP.CAPITULATION_STOP_BUFFER_PCT / 100), 4)`
  - `t2r, t3r = _targets(entry, stop)`
- 更新函数 docstring "Priority" 行

#### 共享 utility 抽取
- 新建 `backend/app/services/cockpit/_indicators.py`：包含 `compute_wilder_atr(highs, lows, closes, period) -> list[float]` 纯函数（返回完整 ATR series，Wilder 平滑：seed=SMA(TR,period)，之后 `(prev * (period-1) + TR) / period`）
- 重构 `chart_service.py::_compute_atr_series` 调用 `compute_wilder_atr`（保持原 `[{"date", "value"}]` 输出格式 — `_compute_atr_series` 继续负责把 list[float] 包成 dict 列表）
- setup_service `_compute_atr_value` 内部调用 `compute_wilder_atr` 后取 `[-1]`

#### 测试新建 + fixture 迁移
- 新建 `backend/tests/test_capitulation_reversal.py`：≥14 条 pure tests（详见第 3 节）
- 修改 `backend/tests/test_setup_f202a.py`：
  - `test_s4_upsert_batch_updates_on_conflict`：fixture 字符串 `"PULLBACK"` → `"BREAKOUT"`（仅是 repository upsert 行为测试，不依赖语义）
  - `test_s15_pullback_in_zone`（约 L350-376）：原期望 `PULLBACK`，新行为下相同 MA fixtures（trend_score=4, close 接近 MA21, 无 capitulation 条件）应返回 NONE — 改名 `test_s15_pullback_zone_now_returns_none` 并断言 `st == "NONE"`，注释引用 D095 / F217-a 说明历史 PULLBACK 已废除

### 排除（不在本 sprint）

- ❌ **Pydantic Literal schemas 更新**（position / pending_order / 4 AI schemas，共 6 文件）— 留到 **F217-b**，与 alembic 021 同步引入 `"CAPITULATION"` 到 Literal 并**保留 `"PULLBACK"`** 占位直到 DB 软删完成
- ❌ **DB schema 迁移、历史 PULLBACK 行软删、`user_settings.preferred_setups` JSON 迁移** — **F217-b**
- ❌ **前端 chips + 紫色 badge + cockpitDecisionApi 类型** — **F217-c**
- ❌ **Decision endpoint capitulationEvidence 字段填充逻辑** — 由 F217-c 协商，本 sprint 不动 `decision_service.py`
- ❌ 既有非 setup_service 测试 fixture 中残留的 `"PULLBACK"` 字符串（test_f215a / test_regime_f201b / test_decision_f203b2 / test_setup_f216d2 / test_ai_schemas_f211a1 / test_ai_gateway_e2e_f208c / test_pool_service）— 不影响 F217-a 功能（user_settings.preferred_setups 是 opaque JSON，AI Literal 因保留 PULLBACK 仍 valid），由 F217-b alembic 021 + Literal 更新完成后再批量清理

### 协商结果（NP）

| # | 决议 |
|---|------|
| NP1 | ATR 算法**重构为共享 utility**：新建 `backend/app/services/cockpit/_indicators.py`，chart_service + setup_service 共用 |
| NP2 | 信号触发位置 **bar[-1] 当日触发**；条件 5「次日不创新低」数据不足时跳过（视为通过），不引入延后信号 |
| NP3 | CAPITULATION entry/stop：`entry = close*(1+tick)` / `stop = bar[-1].low*(1-1.5%)`（`CAPITULATION_STOP_BUFFER_PCT` 默认 1.5%） |
| NP4 | RS line 计算来源：`_is_capitulation_reversal` 内部 `rs_line[i] = closes[i] / spy_closes[i]`，签名扩展 `spy_closes` 参数 |

---

## 2. 预计修改文件清单（6 个）

| # | 路径 | 类型 |
|---|------|------|
| 1 | `backend/app/services/cockpit/cockpit_params.py` | 修改 |
| 2 | `backend/app/services/cockpit/setup_service.py` | 修改 |
| 3 | `backend/app/services/cockpit/_indicators.py` | **新建** |
| 4 | `backend/app/services/cockpit/chart_service.py` | 修改（重构 `_compute_atr_series` 调用共享 util） |
| 5 | `backend/tests/test_capitulation_reversal.py` | **新建** |
| 6 | `backend/tests/test_setup_f202a.py` | 修改（test_s4 + test_s15 fixture 迁移） |

✅ **6 文件命中上限**。后续如发现遗漏文件，必须二次协商，不得偷加。

---

## 3. 完成标准 — Evaluator 验收清单

### 测试矩阵（共 14 条）

| # | 测试描述 | 层级 | 工具 |
|---|---------|------|------|
| T1 | 常量重命名验证：`SETUP_CAPITULATION = "CAPITULATION"` 存在；`SETUP_PULLBACK` 已删除；`grep "PULLBACK" backend/app/services/cockpit/{setup_service,cockpit_params}.py` 仅在 history 注释（无活跃代码引用） | 静态 | grep + pytest |
| T2 | `_indicators.compute_wilder_atr(highs, lows, closes, 14)` 用 Wilder ATR：seed=SMA(TR,14)，之后 `(prev*13+TR)/14`；TR=max(H-L, abs(H-prevC), abs(L-prevC))；输入长度 < period+1 时返回 `[]` | 单元 | pytest |
| T3 | chart_service `_compute_atr_series` 重构后输出与重构前**逐位浮点对齐**（用同一 bars 输入对比 `value` 字段，diff < 1e-9）— 用现有 chart fixture | 集成 | pytest（保留并扩展 test_chart_f203a 现有 ATR 断言） |
| T4 | `_detect_swing_lows(lows, 30)` 返回降序 swing low 索引列表；swing low 定义 `lows[i] < lows[i-1] and lows[i] < lows[i+1]`；只看最后 lookback 个 bars；至少 0 / 1 / 2+ 个 swing low 三种 case 都覆盖 | 单元 | pytest |
| T5 | **CAPITULATION 7 条 AND 门 happy path**：构造合成 bars (close 5 日累计跌 12% / 当日 vol z≈2.8 / TR=2.3×ATR14 / close 在 H-L 区间上 1/3 / 不存在 lookahead → 条件 5 跳过 / higher_low vs 倒数第二个 swing low / rs_line 5 日未新低) → `_is_capitulation_reversal` 返回 True | 单元 | pytest |
| T6 | **7 条门每条单独失败**（7 个 sub-test）：drop=-8% / vol_z=2.0 / TR=1.5×ATR / close 在 H-L 下 1/3 / lookahead 创新低 / lower_low（vs 倒数第二个 swing low）/ rs_line 创新低 → 每个返回 False | 单元 | pytest |
| T7 | 数据不足分支：bars 长度 < `SWING_LOW_LOOKBACK + 2` → 返回 False（不抛异常）；bars 刚好等于阈值 → 正常评估 | 单元 | pytest |
| T8 | 条件 5「次日不创新低」尾部数据处理：当 bars 不含 today+1 / today+2 → 条件 5 视为通过；当 bars 含 today+1 且 today+1.low > today.low → 通过；当 today+1.low <= today.low → False | 单元 | pytest |
| T9 | **优先级测试**（5 个 sub-test）：BROKEN (close<MA150) + CAPITULATION 全满足 → BROKEN；EXTENDED + CAPITULATION → EXTENDED；EARNINGS_DRIFT + CAPITULATION → EARNINGS_DRIFT；CAPITULATION + BREAKOUT 候选 → CAPITULATION（投降底优先）；CAPITULATION + RECLAIM → CAPITULATION | 单元 | pytest |
| T10 | `_classify_setup_type` docstring "Priority" 行更新为新顺序；代码扫描无 `SETUP.PULLBACK_*` 引用 | 静态 | grep + pytest collect |
| T11 | `_ACTIONABLE_TYPES` 等于 `{"BREAKOUT", "CAPITULATION", "RECLAIM", "EARNINGS_DRIFT"}` | 单元 | pytest |
| T12 | `compute_and_store_all` 调用 `_classify_setup_type` 时传入 `volumes` + `spy_closes`；setup_snapshots 行不再产生 `setup_type=PULLBACK`；CAPITULATION 命中时 `entry` / `stop` 符合 NP3 公式 | 集成 | pytest (sqlite fixture) |
| T13 | `test_setup_f202a.py`：test_s4 fixture 字符串 BREAKOUT；test_s15 重命名 + 期望 NONE；所有 f202a 测试通过 | 集成 | pytest |
| T14 | **全量回归**：`uv run pytest backend/tests/ -x` 全通过；diff vs 开工前 = **0 新增失败**；如有预先存在的失败，列入报告但不阻塞 | 集成 | pytest |

### 自检清单（Evaluator 模式）

- [ ] T1-T14 全部通过
- [ ] **Lint**：`ruff check backend/app/services/cockpit/ backend/tests/test_capitulation_reversal.py backend/tests/test_setup_f202a.py` 无新增 warning
- [ ] **死代码**：4 个 `PULLBACK_*` Pydantic Field 已删除；setup_service 内无 `SETUP.PULLBACK_*` 引用；`_is_pullback` 函数已删（如存在）
- [ ] **硬编码阈值**：CAPITULATION 7 条门的阈值全部读自 `SETUP.CAPITULATION_*` 配置；entry/stop 公式中的 1.5% 也读自 config
- [ ] **函数长度**：`_is_capitulation_reversal` 函数不超过 80 行（复杂判定可抽 sub-helpers，如 `_check_drop`、`_check_close_in_upper_bin`）
- [ ] **chart_service 回归**：所有 `test_chart_*` 系列通过，ATR series 数值与重构前对齐
- [ ] **claude-progress.txt** 追加 Generator 完成进度
- [ ] **不修改文档**：DATA-MODEL / API-CONTRACT / DECISIONS 本 sprint 不动（system-design 已完成）

### 代码质量自检

- [ ] `_indicators.py` 模块 docstring 说明用途（"Reusable technical indicator pure functions used by chart_service and setup_service"）
- [ ] `_is_capitulation_reversal` 7 条门逻辑顺序与 SRS § 五 Setup 4 一致，每条门加注释引用条件编号
- [ ] 无 try-except 吞错；无 `print` debug 残留

---

## 4. 开发顺序（Generator 模式逐步执行）

> ⚠️ 禁用 `git add -A`。每步显式列文件名。

### Step 1 — 共享 utility 抽取
1. 新建 `backend/app/services/cockpit/_indicators.py`：实现 `compute_wilder_atr(highs, lows, closes, period) -> list[float]`
2. 验证（最小）：`python -c "from app.services.cockpit._indicators import compute_wilder_atr; print(compute_wilder_atr([100,101,102,...], [...], [...], 14))"` 无 import 错误
3. WIP commit：
   ```bash
   git add backend/app/services/cockpit/_indicators.py
   git commit -m "wip(F217-a): _indicators.compute_wilder_atr shared utility"
   ```

### Step 2 — chart_service ATR 重构
1. 修改 `_compute_atr_series` 调用 `compute_wilder_atr`（保持 `[{"date","value"}]` 输出 schema）
2. 运行 `uv run pytest backend/tests/test_chart_*.py -v`，断言 0 失败
3. WIP commit：
   ```bash
   git add backend/app/services/cockpit/chart_service.py
   git commit -m "wip(F217-a): chart_service ATR refactor to shared util"
   ```

### Step 3 — cockpit_params 参数层重写
1. 删 4 个 PULLBACK_* Field
2. 加 10 个 CAPITULATION_* Field
3. 更新 SETUP.TYPES + REGIME_PREFERRED_SETUPS + REGIME_AVOID_SETUPS
4. 验证：`python -c "from app.services.cockpit.cockpit_params import SETUP; print('CAPITULATION' in SETUP.TYPES)"` 返回 True
5. WIP commit：
   ```bash
   git add backend/app/services/cockpit/cockpit_params.py
   git commit -m "wip(F217-a): cockpit_params TYPES/REGIME maps + CAPITULATION_* params"
   ```

### Step 4 — setup_service 核心重写
1. 改 `SETUP_PULLBACK` → `SETUP_CAPITULATION`，更新 `_ACTIONABLE_TYPES`
2. 加 `_compute_atr_value(highs, lows, closes, period)` local wrapper
3. 加 `_detect_swing_lows(lows, lookback)`
4. 改 `_classify_setup_type`：扩展签名 (+ volumes, spy_closes)，删 PULLBACK 分支，加 CAPITULATION 分支（含 inline 7 条门逻辑 OR 调用 `_is_capitulation_reversal`），更新 docstring
5. 改 `compute_and_store_all` 传 volumes + spy_closes 给 `_classify_setup_type`
6. 验证（最小）：`uv run pytest backend/tests/test_setup_f202a.py::test_s15* -v`（旧 PULLBACK 测试**预期失败**，是 Step 6 要修的）
7. WIP commit：
   ```bash
   git add backend/app/services/cockpit/setup_service.py
   git commit -m "wip(F217-a): setup_service Capitulation Reversal + priority升级"
   ```

### Step 5 — test_capitulation_reversal.py 新建 pure tests
1. 写 T1-T11 共 14+ 条 pure tests（T12-T14 是集成层 / 回归层）
2. 验证：`uv run pytest backend/tests/test_capitulation_reversal.py -v` 全绿
3. WIP commit：
   ```bash
   git add backend/tests/test_capitulation_reversal.py
   git commit -m "wip(F217-a): pure tests 14+ for capitulation reversal"
   ```

### Step 6 — test_setup_f202a.py fixture 迁移
1. test_s4：fixture 字符串 `"PULLBACK"` → `"BREAKOUT"`（断言同步）
2. test_s15：重命名 → `test_s15_pullback_zone_now_returns_none`；断言 `st == "NONE"`；加注释引用 D095
3. 验证：`uv run pytest backend/tests/test_setup_f202a.py -v` 全绿
4. WIP commit：
   ```bash
   git add backend/tests/test_setup_f202a.py
   git commit -m "wip(F217-a): test_setup_f202a fixture migration (PULLBACK→NONE/BREAKOUT)"
   ```

### Step 7 — 全量回归 + Final commit
1. `uv run pytest backend/tests/ -x` 全跑一遍
2. 记录回归结果（新失败 / 预先失败 / 全绿）到 Evaluator 报告
3. 如有 F217-a 引入的新失败 → 回 Step 4 修复，**计入熔断**（连续 3 次失败强制停止）
4. 全绿后：
   ```bash
   git add <本 sprint 全部修改文件>
   git commit -m "feat(F217-a): Capitulation Reversal 严格重写 (Phase C 后端)"
   ```
   不 squash wip commits（保留 bisect 颗粒度）

---

## 5. 回滚方式

- **代码层**：WIP commits 颗粒度，任意 step 失败可 `git reset --hard <prev-wip>` 退回
- **数据层**：F217-a 不动 DB schema 也不 backfill 历史快照行；新写入的 `setup_type=CAPITULATION` 行如需回滚，等下一次 daily cron 自然覆盖
- **配置层**：暂不引入 `CAPITULATION_ENABLED` flag（D095 决策 6 中提到的应急方案）；如需紧急 disable，直接 revert commit 即可

---

## 6. Generator 模式恢复指令（A-2）

```
继续开发 F217-a，Sprint Contract 已确认。
读取 SESSION-HANDOFF.md + docs/开发/sprint-contracts/F217-a-contract.md，
进入 Generator 模式，从 §4 开发顺序 Step 1（_indicators 抽取）开始。
```

---

## 7. 风险与备注

- ⚠️ **chart_service 重构是本 sprint 唯一非本质改动**（用户 NP1 显式选择共享 utility）。Step 2 必须验证 chart_service 所有测试 0 失败，否则立即停止报告（不绕过）
- ⚠️ **`_is_capitulation_reversal` 在 prod 数据上预期触发非常稀疏**（每月几只），D095 已记录这是 SRS 设计意图，**不是 bug**。回归测试用合成 bars 验证 happy path；prod 数据触发频率验证留到 F217-c 完成后由 acceptance skill 在真实环境跑 1 周
- ⚠️ **Pydantic Literal 不在本 sprint 范围**：production 代码仍允许 PULLBACK Literal 入参（向后兼容）；新 CAPITULATION 字符串通过 `schemas/cockpit/setup.py::SetupItemResponse.setup_type: str`（已是 str 不是 Literal）正常返回。F217-b alembic 021 + Pydantic 更新会在 F217-b Sprint Contract 单独协商
- ⚠️ **F217-a 完成后 → phase=needs_review**；consistency-check 验证 sub_sprints 一致性后通知用户验收。父 feature F217 不升 done（F217-b/c 待开发）

---

## 8. 用户确认签字位

请确认以下条款（缺一项不可进 Generator）：

- [ ] **范围**：§1「包含/排除」边界 OK，6 文件清单准确
- [ ] **协商点**：NP1（共享 util）/ NP2（bar[-1] 当日）/ NP3（close+tick / low-1.5%）/ NP4（rs_line 内算）全部确认
- [ ] **测试**：T1-T14 完成标准合理；CAPITULATION 触发稀疏性是设计意图（非 bug）
- [ ] **回滚**：WIP commit 颗粒度可接受；不引入 CAPITULATION_ENABLED feature flag

确认后我会：
1. 把 F217-a 的 phase 从 `design_needed` 升 `contract_agreed`（**注**：跳过 `ready_to_dev` — 本 sprint 纯后端无 UI，与 F216-a/b/e 同模式）
2. features.json `_pipeline_status.active_sprint_phase` 更新为 `contract_agreed`
3. 生成 SESSION-HANDOFF.md
4. **停止**，让你开新 session 进 Generator 模式
