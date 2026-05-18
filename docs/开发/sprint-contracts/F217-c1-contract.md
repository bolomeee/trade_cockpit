# F217-c1 Sprint Contract — Cockpit Phase C 后端 capitulationEvidence 接口实装

> 生成：2026-05-18 | 状态：草案 → 待用户确认
> Feature：[F217](docs/需求/features.json) Phase C — Capitulation Reversal 严格重写
> Sub-sprint：F217-c1（C5-back，backend evidence wiring）
> 前置：
>   - F217-a done @ 2026-05-15（cockpit_params / setup_service 7 AND 门）
>   - F217-b1 done @ 2026-05-15（DB legacy 列 + purge_legacy_pullback）
>   - F217-b2 done @ 2026-05-16（6 schema Literal +CAPITULATION）
>   - F217-b3 done @ 2026-05-16（7 测试 fixture PULLBACK→CAPITULATION）
>   - F217-b4 done @ 2026-05-16（6 schema Literal -PULLBACK 收紧）
> 下游：F217-c2（前端 chips+badge+token+design-spec，依赖本 sprint backend 接口产出）

> 引用文档：
> - DATA-MODEL.md §SetupSnapshot — setup_type 枚举 / volume_zscore 列（已存在）
> - API-CONTRACT.md §Cockpit Decision (GET /api/cockpit/decision/{ticker}) — 响应字段 `capitulationEvidence: { volZscore, drop5dPct, reversalDay } | null`（L1390/L1396-1424，已落地 2026-05-15）
> - DECISIONS.md §D095 子决策 5（API 字段可选 / 仅 CAPITULATION 时非 null）
> - 上游代码：backend/app/services/cockpit/setup_service.py `_is_capitulation_reversal`（7 AND 门内已计算 drop_5d_pct + reversal_day 作为门禁，本 sprint 抽出可复用 helper）

---

## 0. 拆分背景（c → c1 + c2）

原 F217-c 估计"前端 4-5 文件"在 2026-05-18 协商时预扫描发现：

- backend `decision_service.py` / `schemas/cockpit/decision.py` 未实装 `capitulationEvidence`（API-CONTRACT 已定义但 backend 仅落了文档）
- frontend 修改 + tokens.css + design-spec + 5 个测试 fixture（PULLBACK union 收紧后 TS 编译失败）合计 9-11 文件，远超 6 上限
- 必须先 backend 把 evidence 接口实装，frontend chips 才有真实数据可读

拆分方案（用户已确认 2026-05-18）：
- **F217-c1（本 sprint）**：backend evidence 接口实装，4 文件，可独立验证
- **F217-c2（下一 sprint）**：frontend + tokens.css + design-spec，预估 9-11 文件协商时再评估是否二次拆 c2a/c2b

NP-c 系列决策（用户已全部按推荐确认 2026-05-18）：
- NP-c-1=A：evidence 数据来源 — decision_service 实时查 DailyBar 调 setup_service 抽出的 module-level helper（volume_zscore 直接读 setup_snapshot 列）
- NP-c-2=A：（c2 范围）token 重命名
- NP-c-3=A：（c2 范围）SetupTypeBadge union 直接替换
- NP-c-4=A：（c2 范围）design-spec 在 c2 sprint 中同步更新
- NP-c-5=A：volume_zscore 直接读 setup_snapshot.volume_zscore 列（已存在不重算）

---

## 1. 本次实现范围

**包含**：
1. `backend/app/schemas/cockpit/decision.py` 新增 `CapitulationEvidence` Pydantic camelCase 模型 + `DecisionData.capitulation_evidence: CapitulationEvidence | None = None`
2. `backend/app/services/cockpit/setup_service.py` 抽出 module-level helper `compute_capitulation_evidence(closes, highs, lows) -> dict | None`，复用现有 `_check_close_in_upper_bin` + `SETUP.CAPITULATION_CLOSE_UPPER_BIN` 等常量，输出 `{drop_5d_pct: float, reversal_day: bool}`（NP-c1-1=A 返回 dict 不返回 Pydantic 模型保解耦）
3. `backend/app/services/cockpit/decision_service.py` 在 `setup_type=="CAPITULATION"` 时：
   - 调 helper 拿 drop_5d_pct + reversal_day（实时 select `DailyBar` 拉最近 ≥ 6 行，inline `select` 与现有 `_earnings_risk_and_date` 风格一致 — NP-c1-4=A）
   - vol_zscore 直接从已查询的 `snapshot.volume_zscore` 取（已存在列 — NP-c-5=A）
   - 组装 `CapitulationEvidence`，否则 `capitulation_evidence=None`
   - 防御：snapshot.volume_zscore is None **或** helper 返回 None **或** bars 不足 → `capitulation_evidence=None`（NP-c1-3=A，chip 不渲染而非 N/A）
4. `backend/tests/test_decision_f217c1.py` 新建，覆盖 T1-T8（详见 §3）

**明确排除（本次不做）**：
- frontend `cockpitDecisionApi.ts` 类型扩展（F217-c2）
- frontend `setupMonitorApi.ts` SetupType union 收紧（F217-c2）
- frontend `SetupTypeBadge.tsx` CAPITULATION 紫色 badge（F217-c2）
- frontend `DecisionPanelWidget.tsx` 3 chips 渲染（F217-c2）
- frontend tokens.css 紫色 token 重命名（F217-c2）
- frontend design-spec.md setup color 表 + chips 视觉规格新增（F217-c2）
- 5 个前端测试 fixture PULLBACK→CAPITULATION（SetupMonitorWidget.test.tsx / MarketRegimeWidget.test.tsx / DecisionPanelWidget.test.tsx / cockpitApis.test.ts / cockpitPoolApi.test.ts — F217-c2，union 收紧后 TS 编译失败连锁修复）
- 在 `setup_snapshots` 表新增 drop_5d_pct / reversal_day 列（NP-c-1=B 已拒，本 sprint 不做 DB 迁移）
- CAPITULATION_ENABLED feature flag
- decision_service 5-10 日窗口扫描寻找最佳 drop（chip 固定取 5 日 — API-CONTRACT L1424 已锁）
- `_compute_volume_zscore` helper 在 decision_service 重复调用（用 snapshot 已存列）

---

## 2. 预计修改文件（共 4 个 — 6 上限内含 2 文件 buffer）

| # | 文件路径 | 改动类型 | 说明 |
|---|---------|---------|------|
| 1 | `backend/app/schemas/cockpit/decision.py` | 修改 | 新增 `CapitulationEvidence(_CamelModel)` 3 字段（vol_zscore: float / drop_5d_pct: float / reversal_day: bool）+ `DecisionData.capitulation_evidence: CapitulationEvidence \| None = None`。alias_generator=to_camel 自动产 `volZscore` / `drop5dPct` / `reversalDay` / `capitulationEvidence`。 |
| 2 | `backend/app/services/cockpit/setup_service.py` | 修改 | 抽 module-level `def compute_capitulation_evidence(closes, highs, lows) -> dict \| None`，复用 `_check_close_in_upper_bin` + `SETUP.CAPITULATION_CLOSE_UPPER_BIN`。drop_5d_pct = `(closes[-1] - closes[-6]) / closes[-6] * 100` 保留 1 位小数（API-CONTRACT L1422 一致）；reversal_day = `_check_close_in_upper_bin(closes[-1], highs[-1], lows[-1], SETUP.CAPITULATION_CLOSE_UPPER_BIN)`。bars 不足（len<6 或 closes[-6]==0）→ `None`。**不动 `_is_capitulation_reversal` 内部逻辑**（避免行为漂移，guard tests 不破）。 |
| 3 | `backend/app/services/cockpit/decision_service.py` | 修改 | `compute_decision` 在 snapshot 存在且 `setup_type=="CAPITULATION"` 时：inline `select(DailyBar).where(DailyBar.stock_id==...).order_by(DailyBar.date.desc()).limit(6)` 拉 bars（注意 reverse 为升序传 helper），调 `compute_capitulation_evidence`，配合 `snapshot.volume_zscore` 组 `CapitulationEvidence`。任一前置失败 → `capitulation_evidence=None`。需要 stock_id：snapshot 没有 stock_id 列，得通过 `Stock.ticker==ticker` 查 stock_id（同样 inline select）；或直接 `select(DailyBar).join(Stock).where(Stock.ticker==ticker)`。返回 `DecisionData(..., capitulation_evidence=evidence)`。 |
| 4 | `backend/tests/test_decision_f217c1.py` | 新建 | 8 测试 T1-T8 覆盖 evidence 字段（详见 §3）。沿用现有 `test_decision_f203b2.py` 的 fixture 模式（setup 真实 db_session + 插 Stock/DailyBar/SetupSnapshot/UserSettings/MarketRegimeSnapshot）。 |

👤 用户确认 4 文件列表合理后，方可进入开发。

---

## 3. 可测试的完成标准

| # | 标准描述 | 测试层级 | 工具 |
|---|---------|---------|------|
| T1 | `CapitulationEvidence` 模型可构造，3 字段 to_camel 序列化为 `volZscore` / `drop5dPct` / `reversalDay` | 单元 | pytest + pydantic |
| T2 | `compute_capitulation_evidence(closes, highs, lows)` happy path：bars 充足且 close 在上 1/3 → `{drop_5d_pct: -12.4, reversal_day: True}`（合成 6 行 bars 验证浮点精度 1 位小数） | 单元 | pytest |
| T3 | `compute_capitulation_evidence` 返回 None：bars < 6 / closes[-6] == 0 / 空列表 三个分支 | 单元 | pytest |
| T4 | `compute_capitulation_evidence` reversal_day=False 分支：close 在 H-L 下 2/3 → `reversal_day=False`（drop_5d_pct 仍正常计算） | 单元 | pytest |
| T5 | `compute_decision` setup_type=CAPITULATION 且 snapshot.volume_zscore=2.71 且 bars 充足 → `capitulation_evidence` 非 None 且 3 字段填充正确，response model_dump(by_alias=True) 含 `capitulationEvidence.volZscore=2.71` / `drop5dPct=-12.4` / `reversalDay=True` | 集成 | pytest + 测试 DB |
| T6 | `compute_decision` setup_type=BREAKOUT → `capitulation_evidence is None`（非 CAPITULATION 一律不填充） | 集成 | pytest + 测试 DB |
| T7 | `compute_decision` setup_type=CAPITULATION 但 snapshot.volume_zscore=None（数据异常）→ `capitulation_evidence is None`（防御 NP-c1-3=A） | 集成 | pytest + 测试 DB |
| T8 | `compute_decision` setup_type=CAPITULATION 但 DailyBar 仅有 3 行（bars 不足）→ `capitulation_evidence is None`（helper 返回 None） | 集成 | pytest + 测试 DB |
| T9 | 全量回归：现有 `test_decision_f203b2.py` / `test_decision_f215b.py` / `test_capitulation_reversal.py` / `test_setup_snapshot_purge.py` 共 N tests 0 新增失败（基线对齐 b4 done = 1095 passed 8 预存失败） | 回归 | pytest |

---

## 4. 开发顺序（7 步，每步对应 1 wip commit）

每完成一步且最小验证通过（单测/编译），按 §7 显式 `git add <本步文件>` + `git commit -m "wip(F217-c1): <step>"`。

| Step | 内容 | 验证 | wip commit message |
|------|------|------|---------------------|
| 1 | `backend/app/schemas/cockpit/decision.py` 新增 `CapitulationEvidence` 模型 + `DecisionData.capitulation_evidence` 字段（默认 None） | `python -c "from app.schemas.cockpit.decision import CapitulationEvidence, DecisionData; ..."` 构造 + model_dump(by_alias=True) 验证 camelCase | `wip(F217-c1): decision schema CapitulationEvidence` |
| 2 | `backend/app/services/cockpit/setup_service.py` 新增 module-level `compute_capitulation_evidence(closes, highs, lows) -> dict \| None`（不动 `_is_capitulation_reversal`） | REPL 调 happy + insufficient + zero-divisor 三例 | `wip(F217-c1): setup_service compute_capitulation_evidence helper` |
| 3 | `backend/tests/test_decision_f217c1.py` T1-T4 helper + schema 4 测试落地 + 通过 | `pytest backend/tests/test_decision_f217c1.py -k "T1 or T2 or T3 or T4"` | `wip(F217-c1): T1-T4 schema + helper pure tests` |
| 4 | `backend/app/services/cockpit/decision_service.py` 在 `compute_decision` 末尾构造前增加 evidence 计算分支（inline select DailyBar join Stock 拉 6 行 bars，调 helper，组 CapitulationEvidence）；传入 `DecisionData(..., capitulation_evidence=evidence)` | `pytest backend/tests/test_decision_f203b2.py` 0 失败（兼容性） | `wip(F217-c1): decision_service capitulationEvidence wiring` |
| 5 | `test_decision_f217c1.py` T5-T8 集成测试落地 + 通过 | `pytest backend/tests/test_decision_f217c1.py` 8/8 | `wip(F217-c1): T5-T8 decision_service integration tests` |
| 6 | Evaluator 自检（§5） + 全量回归 T9 + ruff | `pytest backend/tests/ -x` + `ruff check backend/` | （无 commit，验证步） |
| 7 | Sprint 收尾 final commit（按文件名显式 add 4 文件） | git status 清 | `feat(F217-c1): backend capitulationEvidence wiring` |

**禁用 `git add -A`**，每步按上表文件显式 add。

---

## 5. Evaluator 自检清单

开发完成后，Evaluator 模式逐条检查：

- [ ] 单元测试 T1-T4 全部通过（`pytest backend/tests/test_decision_f217c1.py -k "T1 or T2 or T3 or T4"`）
- [ ] 集成测试 T5-T8 全部通过（`pytest backend/tests/test_decision_f217c1.py -k "T5 or T6 or T7 or T8"`）
- [ ] 回归 T9：`test_decision_f203b2.py` / `test_decision_f215b.py` / `test_capitulation_reversal.py` / `test_setup_snapshot_purge.py` 0 新增失败
- [ ] 全量后端 pytest 通过基线 1095 passed 8 预存失败 0 新增失败
- [ ] API 响应格式与 API-CONTRACT.md L1396-1424 一致：`capitulationEvidence` 仅 setupType=CAPITULATION 时非 null，3 字段 camelCase 名一致
- [ ] DecisionData / CapitulationEvidence Pydantic alias 验证 `model_dump(by_alias=True)` 产 `capitulationEvidence` / `volZscore` / `drop5dPct` / `reversalDay`
- [ ] 数据库字段命名：未新增表/列，仅读 `setup_snapshots.volume_zscore` + `daily_bars.{close,high,low}`，命名与 DATA-MODEL.md 一致
- [ ] 无 `_is_capitulation_reversal` 行为改变（guard `test_capitulation_reversal.py` 34 tests 全过）
- [ ] 无 `purge_legacy_pullback` 字节级别变更（grep + git diff 验证）
- [ ] 无 console / print / logger 遗留（生产路径）
- [ ] ruff `backend/` 0 新增 warning（基线 b4 done = position.py F401 预存）
- [ ] DECISIONS.md 无新决策追加（D095 已覆盖 evidence 字段语义；本 sprint 仅实装）
- [ ] git status 清，4 文件全 commit

### 代码质量检查
- [ ] 无死代码（compute_capitulation_evidence 未在 decision_service 外被废调用）
- [ ] 无硬编码魔法值：upper_bin 用 `SETUP.CAPITULATION_CLOSE_UPPER_BIN`；5-day window 固定 `closes[-6]` 注释引 API-CONTRACT L1424 注脚
- [ ] 函数长度合理（compute_capitulation_evidence < 30 行；decision_service evidence 分支 < 20 行）
- [ ] 无重复代码块（`_check_close_in_upper_bin` 直接复用，不重写）
- [ ] 错误处理完整：bars 查询 None / volume_zscore None / closes[-6]=0 三个边界全 evidence=None 不抛

---

## 6. 回滚策略

发现破坏性回归时按以下顺序回滚：

1. `git revert <feat-commit>` 删除 evidence 实装（最快）
2. 若 evidence 字段被 frontend c2 已消费（c2 已进入 testing 阶段后才会出现这种场景）→ 不能简单 revert，需先 hot-fix decision_service 永远返回 `capitulation_evidence=None`，再排查 root cause

**回滚不需要 DB 迁移**（本 sprint 0 DB 改动）。
**回滚不破坏 c2 后向兼容**：c2 前端代码必须按"可选字段 + null 检查"模式消费（API-CONTRACT 已声明 nullable），revert 后前端不会崩。

---

## 7. Git Commit 规范

- **WIP（每步）**：`git add <本步文件>` + `git commit -m "wip(F217-c1): <step>"`，**禁用 `-A`**
- **Final**：`git add backend/app/schemas/cockpit/decision.py backend/app/services/cockpit/setup_service.py backend/app/services/cockpit/decision_service.py backend/tests/test_decision_f217c1.py` + `git commit -m "feat(F217-c1): backend capitulationEvidence wiring"`
- 不 squash wip commits（默认保留细粒度便于 bisect）

---

## 8. 风险与注意

- **行为漂移风险**：setup_service 抽 helper 时若不慎改动 `_check_close_in_upper_bin` 签名或常量引用，将破坏 `_is_capitulation_reversal` Gate 4 → guard test_capitulation_reversal.py 立刻报警。抽 helper 时**只新增 module-level 函数**，不动既有函数体。
- **DailyBar 查询性能**：每次 CAPITULATION decision 多 1 次 6-row select（join Stock），对 cockpit 单 ticker 请求可忽略；若未来 batch 化（不在本 sprint），需重新评估。
- **CAPITULATION 触发稀疏**：测试用例需要构造 setup_type=CAPITULATION 的 snapshot（直接 insert 即可，不必复现 7 AND 门）+ 6 行合成 bars 验证 helper。集成测试不依赖 setup_service 真实 scan。
- **vol_zscore 数据契约**：API-CONTRACT 声明 vol_zscore "必 ≥ 2.5"；helper 不重新校验阈值（CAPITULATION 触发已保证）；若历史数据脏（vol_zscore < 2.5 但 setup_type=CAPITULATION），仍照常返回真实值（不强行 clamp）。
- **5-day window 选择**：API-CONTRACT L1424 注脚明确"chip 展示固定取 5 日值以保持稳定可读性"；helper 不实现"5-10 日最佳窗口扫描"。

---

👤 用户确认本 Contract 后，本 session 强制停止，开 Sonnet 新 session 进入 Generator 模式从 Step 1 开始。
