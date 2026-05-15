# Sprint Contract：F216-d2 — Weekly Stage 强制门禁接入 ready_signal

> 日期：2026-05-14 | 状态：✅ 已确认（用户 2026-05-14 NP1-NP8 全部按推荐拍板）
> Feature：F216 Cockpit Phase B — Weekly Stage Layer
> Sub-sprint：F216-d2（d 段第 2 个，service gate 层；d1=DB schema 已 done，d3=前端 WS 列）
> 父 feature 拆分理由：F216-d 原估 ~13 文件远超 6 文件上限，按 sub_sprint_notes 拆 d1/d2/d3
> 依赖：
>   - F216-b done（weekly_stage_snapshots 表 + WeeklyStageRepository.get_latest_for_tickers 已落地）
>   - F216-d1 done（setup_snapshots.weekly_stage INTEGER NULL 列 + ORM Mapped 字段已落地，DATA-MODEL 字段表已加行）
> 引用文档：
>   - ARCHITECTURE.md（cockpit/ 模块层）
>   - DATA-MODEL.md §SetupSnapshot（字段表已含 weekly_stage；本 sprint 在业务规则段加门禁 bullet 并把 ready_signal 描述 7→8）
>   - DATA-MODEL.md §WeeklyStageSnapshot（stage 字段语义来源）
>   - API-CONTRACT.md §GET /api/cockpit/setup-monitor（本 sprint 在响应加 weeklyStage + 8th AND 文案）
>   - 完整改善计划：/Users/wonderer/.claude/plans/featrue-dev-replicated-goblet.md §Phase B / B4
>   - features.json F216 acceptance_criteria 第 8 条："setup_service._evaluate_ready_signal 强制 weekly_stage == 2 才允许 ready_signal=true"

---

## 0. 背景与定位

Phase B 第 4 步的"主菜" — 把 Stan Weinstein Stage 接入 setup_service 的 ready_signal 7 条 AND 门，升级为 **8 条 AND 门**：
1. trend_score ≥ 4
2. rs_percentile ≥ 70
3. setup_quality ∈ {A, B}
4. distance_to_entry_pct ∈ [0, 3]
5. reward_risk ≥ 2
6. earnings_risk ≠ DANGER
7. regime ≠ RISK_OFF
8. **weekly_stage == 2**（本 sprint 新增）

**设计意图**（acceptance criteria 第 8 条原文）：
> setup_snapshots 新增 weekly_stage (INT) 列；setup_service._compute_ready_signal 强制 weekly_stage == 2 才允许 ready_signal=true

预期效果：ready_signal=true 标的数量减少 30-50%（设计文档 plan B 段写明），用户只看到处于 Stage 2 (Advancing) 的有效信号，回避 Stage 3 (Distribution) 顶部分布与 Stage 4 (Declining) 下跌中的低胜率 setup。

**为什么这样切**：
- d1（已 done）只动 schema，零业务风险
- d2（本 sprint）集中实现 service join + 门禁 + API 暴露 + 文档同步 — review 时一次看清"30-50% 减少"的设计取舍
- d3（待 sprint）只关心前端如何展示 WS 列

---

## 1. 实现范围

### 1.1 setup_service.py 三处改动

**A. `_compute_ready_signal` 加 `weekly_stage` 参数 + 8th AND 门**：

```python
def _compute_ready_signal(
    trend_score: int,
    rs_percentile: float,
    setup_quality: str | None,
    distance_to_entry_pct: float | None,
    reward_risk: float | None,
    earnings_risk: str,
    regime: str,
    weekly_stage: int | None = None,  # F216-d2 新增，default=None 保持调用方向后兼容
) -> bool:
    """8-condition AND gate (all must be True)."""
    allowed_qualities = _QUALITY_SETS.get(SETUP.READY_QUALITY_MIN, {"A", "B"})
    stage_ok = (not SETUP.READY_REQUIRE_STAGE2) or (weekly_stage == 2)
    return (
        trend_score >= SETUP.READY_TREND_MIN
        and rs_percentile >= SETUP.READY_RS_MIN
        and setup_quality in allowed_qualities
        and distance_to_entry_pct is not None
        and 0 <= distance_to_entry_pct <= SETUP.READY_DIST_MAX_PCT
        and reward_risk is not None
        and reward_risk >= SETUP.READY_REWARD_RISK_MIN
        and earnings_risk != "DANGER"
        and regime != "RISK_OFF"
        and stage_ok
    )
```

NULL/0 → `stage_ok=False`（与 NP3 一致）；flag off → 跳过门禁。

**B. `compute_and_store_all` join WeeklyStageRepository 注入 weekly_stage**：

在循环前一次性查所有 ticker 的最新 stage（避免 N+1）：

```python
from app.repositories.weekly_stage_repository import WeeklyStageRepository

# 在 __init__ 加 self.weekly_stage_repo = WeeklyStageRepository(db)
# compute_and_store_all 开头取所有 active ticker 的最新 stage：
active_tickers = [s.ticker for s in stocks]
stage_map = self.weekly_stage_repo.get_latest_for_tickers(active_tickers)
# stage_map: {ticker: WeeklyStageSnapshot}; 缺失 ticker 自动不存在 key

# 在 row 构造处取值：
weekly_stage_val = stage_map[stock.ticker].stage if stock.ticker in stage_map else None
```

把 `weekly_stage_val` 同时：
- 传给 `_compute_ready_signal(..., weekly_stage=weekly_stage_val)`
- 写入 row dict `"weekly_stage": weekly_stage_val`

**短数据分支**（`len(closes) < 10` 写 NONE row）：同样写 `"weekly_stage": weekly_stage_val`（即使 stage 已知，setup_type=NONE → quality=None → ready=False，stage 信息仅用于前端展示）。

**C. `_row_to_dict` 加 `weeklyStage`**：

```python
"weeklyStage": r.weekly_stage,
```

放在 `upDownVolumeRatio` 之后，保持字段时间序。

### 1.2 schemas/cockpit/setup.py

`SetupItemResponse` 追加：

```python
weekly_stage: int | None = None
```

放在 `up_down_volume_ratio` 之后。`alias_generator=to_camel` 自动转 `weeklyStage`。

### 1.3 cockpit_params.py §2 CockpitSetupParams

在 Ready signal 区（`READY_REWARD_RISK_MIN` 之后、Earnings risk 区之前）追加：

```python
# ── Stage 门禁（F216-d2 / D093）─────────────────────────────────────
READY_REQUIRE_STAGE2: bool = Field(
    default=True,
    description="If True, readySignal further requires weekly_stage==2 (Stan Weinstein Advancing). NULL/0/1/3/4 → ready=False. Off-switch for debug / pre-cron cold start.",
)
```

### 1.4 backend/tests/test_setup_f216d2.py（新建）

涵盖：

**纯函数层 `_compute_ready_signal`**：
- T1：`weekly_stage=2` + 其他全满足 → True
- T2：`weekly_stage=None` + 其他全满足 → False（NULL 视为不满足）
- T3：`weekly_stage=0`（UNKNOWN）→ False
- T4：`weekly_stage=1`（Base）→ False
- T5：`weekly_stage=3`（Distribution）→ False
- T6：`weekly_stage=4`（Declining）→ False
- T7：flag `READY_REQUIRE_STAGE2=False` 时 `weekly_stage=None/0/1/3/4` 都不影响（其他满足即 True）— 用 monkeypatch / model_copy
- T8：其他 7 条任一失败 + weekly_stage=2 → 仍然 False（stage 不能"挽救"其他条件）

**集成层 `compute_and_store_all`**：
- T9：seed 1 个 active stock + 完整 setup 满足前 7 条 + weekly_stage_snapshots(stage=2) → row.ready_signal=True, row.weekly_stage=2
- T10：同 T9 但 stage=4 → row.ready_signal=False, row.weekly_stage=4
- T11：同 T9 但 weekly_stage_snapshots 无该 ticker → row.ready_signal=False, row.weekly_stage=None
- T12：短数据分支（closes<10）→ row.weekly_stage 仍按 stage_map 取值（None 或实际 stage）
- T13：多 ticker（A stage=2, B stage=3, C 无 stage）→ ready 只 A 通过（前提其他 7 条都满足）

**API 输出层 `_row_to_dict`**：
- T14：ORM row(weekly_stage=2) → dict["weeklyStage"]=2
- T15：ORM row(weekly_stage=None) → dict["weeklyStage"]=None

### 1.5 docs/系统设计/API-CONTRACT.md

§GET /api/cockpit/setup-monitor 改动两处：

1. 响应示例 items[0] 加 `"weeklyStage": 2`（放 `upDownVolumeRatio` 之后）
2. 字段说明加：
   ```
   - `weeklyStage`：`number | null`；Stan Weinstein Stage 1-4（0=UNKNOWN；null=该日 weekly_stage cron 未跑到）；F216-d2 起作为 readySignal 第 8 条 AND 门
   ```
3. `readySignal` 描述更新：
   ```
   - `readySignal`: 8 条 AND 门（trend≥4 & rs≥70 & quality≥B & dist≤3% & R:R≥2 & earnings≠DANGER & regime≠RISK_OFF & weeklyStage==2）。weeklyStage 门禁可由 SETUP.READY_REQUIRE_STAGE2 关闭（F216-d2 / D093）
   ```

### 1.6 docs/系统设计/DATA-MODEL.md

§SetupSnapshot 改动两处：

1. 字段表 `ready_signal` 描述："全 7 条 AND 门" → "全 8 条 AND 门"，并附 stage==2 子句
2. 业务规则段加 bullet：
   ```
   - **Weekly Stage 门禁（F216-d2 / D093）**：`ready_signal` 第 8 条 AND 门要求 `weekly_stage == 2`（Stan Weinstein Advancing）；`NULL/0/1/3/4` 一律视为不满足 → `ready_signal=False`。预期减少 ready=true 标的 30-50%，回避 Stage 3 顶部分布与 Stage 4 下跌中的低胜率 setup。可通过 `SETUP.READY_REQUIRE_STAGE2=False` 关闭门禁（默认开启）。weekly_stage 来自 `weekly_stage_snapshots.stage` 最新一行 join（cron 顺序保证 regime→weekly_stage→setup）。
   ```

### 1.7 docs/系统设计/DECISIONS.md

追加：

```
## D093：F216-d2 weekly_stage 作为 ready_signal 第 8 条 AND 门

**日期**：2026-05-14
**决策**：在 `_compute_ready_signal` 原 7 条 AND 门基础上加 `weekly_stage == 2` 第 8 条；NULL/0/1/3/4 一律视为不满足；门禁由 `SETUP.READY_REQUIRE_STAGE2` (default=True) 控制。
**原因**：Stan Weinstein Stage 框架认为 Stage 2 (Advancing) 是唯一具备系统性正期望的阶段；Stage 3 顶部分布 + Stage 4 下跌中触发的 BREAKOUT/RECLAIM 胜率历史显著偏低。把 stage 接进 ready_signal 让 setup_monitor 自动屏蔽这两段，用户只看 Stage 2 的有效信号。
**放弃了什么**：
- 把 stage 一并降级 setup_type=NONE：会抹掉 watch/wait 中间态，用户失去"setup 存在但暂不可 enter"的视野（NP3 否决）
- 增加 suggested_action='stage_gate' 中间态：前端 enum/排序/map 全要同步改，冲击超 d2 scope
- NULL/0 → 跳过门禁的宽松路径：与 ready_signal 7 条 AND 门"NULL 即不满足"的语义不一致，且违背 acceptance criteria 第 8 条
**影响**：
- ready_signal=True 标的预期减少 30-50%（设计意图，文档化）
- 冷启动当天 weekly_stage cron 未跑前所有 ticker 的 ready=False（与 F215-b volume_zscore 短历史 pattern 一致）
- 前端 SetupMonitorWidget 后续 d3 加 WS 列展示 stage（让用户看到"为何 ready=false"）
**回滚方式**：env 或代码层把 `SETUP.READY_REQUIRE_STAGE2` 置 False，无 schema / migration 回滚需求
```

---

## 2. 预计修改文件（7 个，按 NP-A 用户同意单 sprint 处理）

| # | 文件路径 | 改动类型 | 改动规模 |
|---|---------|---------|---------|
| 1 | `backend/app/services/cockpit/setup_service.py` | 修改 | `_compute_ready_signal` 加参数+stage gate；`__init__` 加 weekly_stage_repo；`compute_and_store_all` join + 写 weekly_stage 字段（含短数据分支）；`_row_to_dict` 加 weeklyStage |
| 2 | `backend/app/schemas/cockpit/setup.py` | 修改 | `SetupItemResponse` 加 `weekly_stage: int \| None = None` |
| 3 | `backend/app/services/cockpit/cockpit_params.py` | 修改 | §2 Ready signal 区加 `READY_REQUIRE_STAGE2: bool = True` |
| 4 | `backend/tests/test_setup_f216d2.py` | 新建 | 15 条测试：T1-T8 纯函数 + T9-T13 集成 + T14-T15 row_to_dict |
| 5 | `docs/系统设计/API-CONTRACT.md` | 修改 | §setup-monitor 响应加 weeklyStage + 字段说明 + readySignal 描述 7→8 |
| 6 | `docs/系统设计/DATA-MODEL.md` | 修改 | §SetupSnapshot 字段表 ready_signal 描述 7→8；业务规则段加 Weekly Stage 门禁 bullet |
| 7 | `docs/系统设计/DECISIONS.md` | 修改 | 追加 D093 |

⚠️ 7 > 6 上限，用户已在 NP-A 显式同意单 sprint 处理（理由：3 个 doc 文件 < 30 行合计 bullet 级别同步，与代码强耦合，拆分无 review 价值）。Sprint 完成时 final commit 把 7 个文件一次性提交便于 review 一站式比对"门禁逻辑 ↔ 决策号 ↔ 字段描述 ↔ 业务规则"。

**明确排除（留给 F216-d3）**：

| 项 | 归属 |
|---|---|
| 前端 `setupMonitorApi.ts` `SetupItem` 类型加 `weeklyStage` 字段 | F216-d3 |
| 前端 `SetupMonitorWidget.tsx` 加 "WS" 列与 stage 渲染 | F216-d3 |
| 前端 vitest（widget WS 列与 stage 标签） | F216-d3 |
| `_compute_suggested_action` stage gate 中间态 | **永不做**（NP-Action） |
| `_classify_setup_type` 加 stage 降级 | **永不做**（NP-Scope） |
| `refresh_job` cron 顺序 regime→weekly_stage→setup 编排 | F216-e |

---

## 3. 协商点结论（NP1-NP8，全部按推荐）

| NP | 选项 | 选择 | 理由 |
|----|------|------|------|
| **NP-A 7文件单sprint** | 按 7 文件单 sprint 进行 | ✅ | 3 doc 文件 < 30 行 bullet 级同步，强耦合，拆分无 review 价值 |
| **NP-B 测试兼容** | weekly_stage default=None；fixture 加 weekly_stage=2 | ✅ | 现有 s10/s11 测试不挂；d2 专项测试覆盖 NULL/0/1/3/4 + flag on/off |
| **NP-C NULL 语义** | NULL/0 都视为不满足 → ready=False | ✅ | 与 ready_signal 7 条 AND 门同语义；冷启动当天全黑符合 F215-b pattern |
| **NP-D Flag 位置** | 默认 True，放 §2 SETUP Ready signal 区 | ✅ | 与 READY_TREND_MIN 等同区便于调参；逻辑在 setup_service 跨参数表 import 体感好 |
| **NP-E 取数策略** | 取最新一行不限 scan_date | ✅ | 复用现有 get_latest_for_tickers；cron 顺序保证本周最新；冷启动近期 stage 比 NULL 好 |
| **NP-F 测试粒度** | 新建 test_setup_f216d2.py | ✅ | 独立文件 scope 明确；acceptance review 隔离；d3 可参考同模式 |
| **NP-G 门禁范围** | 仅门禁 ready_signal | ✅ | 与 acceptance criteria 第 8 条严格一致；保留 watch/wait 中间态用户视野 |
| **NP-H Action 中间态** | 不加中间态复用 wait/watch | ✅ | 前端 d3 加 WS 列直接展示 stage；后端不破坏枚举 / map / 排序 |

---

## 4. 可测试的完成标准

| # | 标准描述 | 测试层级 | 工具 / 验证方法 |
|---|---------|---------|----------------|
| 1 | `_compute_ready_signal(weekly_stage=2, ...)` 满足前 7 条 → True | 单元 | T1 |
| 2 | `_compute_ready_signal(weekly_stage=None, ...)` 满足前 7 条 → False | 单元 | T2 |
| 3 | `_compute_ready_signal(weekly_stage=0, ...)` → False | 单元 | T3 |
| 4 | `_compute_ready_signal(weekly_stage=1/3/4, ...)` 任一 → False | 单元 | T4/T5/T6 参数化 |
| 5 | `READY_REQUIRE_STAGE2=False` 时 weekly_stage 不影响 ready | 单元 | T7（monkeypatch / model_copy） |
| 6 | 前 7 条任一失败 + weekly_stage=2 → 仍 False | 单元 | T8 |
| 7 | `compute_and_store_all` seed stage=2 → row.ready_signal=True, row.weekly_stage=2 | 集成 | T9（含全 fixture） |
| 8 | `compute_and_store_all` seed stage=4 → row.ready_signal=False, row.weekly_stage=4 | 集成 | T10 |
| 9 | `compute_and_store_all` weekly_stage_snapshots 无该 ticker → row.weekly_stage=None & ready=False | 集成 | T11 |
| 10 | 短数据分支（closes<10）仍写入 row.weekly_stage（按 stage_map 取值） | 集成 | T12 |
| 11 | 多 ticker join 正确（A=2 ready, B=3 not ready, C=None not ready） | 集成 | T13 |
| 12 | `_row_to_dict(row)` 含 `weeklyStage` 键，值与 r.weekly_stage 相等 | 单元 | T14/T15 |
| 13 | `SetupItemResponse(weekly_stage=2).model_dump(by_alias=True)["weeklyStage"] == 2` | 单元 | T16（schema 验证） |
| 14 | 全量 `pytest backend/tests/` 无新增失败 vs F216-d1 baseline（1019 passed） | 回归 | pytest 全跑 |
| 15 | `test_setup_f202a.py` 全部通过（s10/s11 测试 fixture 加 weekly_stage=2 后语义不变） | 回归 | pytest 单文件 |
| 16 | `test_setup_f202b.py` 全部通过（API 层无 schema 字段未声明错误） | 回归 | pytest 单文件 |
| 17 | `test_setup_service_f215b.py` 全部通过（volume_accumulation 不受影响） | 回归 | pytest 单文件 |
| 18 | API-CONTRACT.md §setup-monitor 含 weeklyStage 字段说明 + 8 条 AND 文案；DATA-MODEL.md §SetupSnapshot 业务规则段含门禁 bullet；DECISIONS.md 含 D093 | 文档审查 | 人工 diff |
| 19 | `READY_REQUIRE_STAGE2` Field 校验：bool 类型 + default=True + frozen 模型不可改 | 单元 | 通过 T7 隐式验证 |

---

## 5. Evaluator 自检清单

- [ ] 标准 1-13 全部通过（test_setup_f216d2.py 15+ 条）
- [ ] 标准 14 回归 1019+ passed 无新增失败
- [ ] 标准 15-17 三个老 setup 测试文件单独跑通过
- [ ] 标准 18 三份文档手工 diff 确认
- [ ] `_compute_ready_signal` 参数 weekly_stage default=None（向后兼容 s10/s11）
- [ ] `compute_and_store_all` 短数据分支 row dict 含 `weekly_stage` 键
- [ ] `_row_to_dict` weeklyStage 放在 upDownVolumeRatio 之后
- [ ] `SetupItemResponse.weekly_stage` 类型 `int | None = None`
- [ ] `READY_REQUIRE_STAGE2` 在 §2 Ready signal 区，紧邻 `READY_REWARD_RISK_MIN`
- [ ] 业务规则段 bullet 含 "F216-d2 / D093" + 30-50% 预期减少 + 关闭方式
- [ ] D093 含"放弃了什么"完整段（3 项），回滚方式明确为 flag toggle 无 schema 回滚
- [ ] 无新增 pip / npm 依赖
- [ ] commit 仅含本 sprint 7 个文件（按 §2 清单显式 git add，禁用 -A）
- [ ] 代码质量：无死代码、无硬编码 stage 数字（全走 SETUP.READY_REQUIRE_STAGE2 + literal 2）、无未使用 import
- [ ] consistency-check C1/C4/C5/C7 全清后再标 needs_review

---

## 6. WIP commit 节点

| # | 触发条件 | 命令 |
|---|---------|------|
| WIP 1 | `_compute_ready_signal` + `READY_REQUIRE_STAGE2` flag 改动 + T1-T8 纯函数测试全绿 | `git add backend/app/services/cockpit/setup_service.py backend/app/services/cockpit/cockpit_params.py backend/tests/test_setup_f216d2.py` → `git commit -m "wip(F216-d2): ready_signal 8th AND gate + stage flag + pure tests"` |
| WIP 2 | `compute_and_store_all` join + `_row_to_dict` + T9-T15 集成测试全绿 | `git add backend/app/services/cockpit/setup_service.py backend/app/schemas/cockpit/setup.py backend/tests/test_setup_f216d2.py` → `git commit -m "wip(F216-d2): compute_and_store_all join + row_to_dict + integration tests"` |
| WIP 3 | 老回归 test_setup_f202a / f202b / f215b 全绿 + 全量 pytest 1019+ 无新增失败 | `git add backend/tests/test_setup_f202a.py`（若 fixture 改动）→ `git commit -m "wip(F216-d2): fixture compat for 7→8 AND gate"`（仅当 s10/s11 fixture 真改动；NP-B 选项 a 通常不改 fixture） |
| Final | 3 份文档同步 + Evaluator 全清 | `git add docs/系统设计/API-CONTRACT.md docs/系统设计/DATA-MODEL.md docs/系统设计/DECISIONS.md` → `git commit -m "feat(F216-d2): weekly_stage as 8th ready_signal gate"` |

⚠️ 禁用 `git add -A`。

⚠️ **NP-B 提醒**：weekly_stage default=None + fixture `_ready_kwargs` 加 weekly_stage=2 — 这意味着 `test_setup_f202a.py` 的 `_ready_kwargs` helper **必须**修改一行加 `weekly_stage=2`，否则 s10 测试 fixture 默认 weekly_stage=None → ready=False，s10 断言 True 失败。这是 WIP 3 的真实改动来源（fixture 1 行变更）。

---

## 7. 开发顺序（Generator 模式逐步执行）

1. 读 F216-d2 contract（本文件）+ d1 contract 收尾 + setup_service.py / cockpit_params.py 当前内容（保 context）
2. 修改 `cockpit_params.py` §2 加 `READY_REQUIRE_STAGE2: bool = True`
3. 修改 `setup_service.py` `_compute_ready_signal` 加 weekly_stage 参数 + stage gate
4. 新建 `backend/tests/test_setup_f216d2.py`，写 T1-T8 纯函数测试
5. 跑 `pytest backend/tests/test_setup_f216d2.py -k "ready_signal"` 验证 T1-T8 全绿
6. 修改 `test_setup_f202a.py` `_ready_kwargs` 加 `weekly_stage=2`（若未加默认会破坏 s10）
7. 跑 `pytest backend/tests/test_setup_f202a.py` 验证 s10/s11 全绿
8. **WIP commit 1**
9. 修改 `setup_service.py` `__init__` 加 `self.weekly_stage_repo`；`compute_and_store_all` 开头 join；row 构造处注入 weekly_stage（含短数据分支）；`_row_to_dict` 加 weeklyStage
10. 修改 `schemas/cockpit/setup.py` `SetupItemResponse` 加字段
11. 追加 `test_setup_f216d2.py` T9-T15（集成 + row_to_dict + schema）
12. 跑 `pytest backend/tests/test_setup_f216d2.py` 全绿
13. **WIP commit 2**
14. 跑全量 `pytest backend/tests/` 验证 1019+ 通过无新增失败；如有 fixture 老 case 失败回到 step 6 排查
15. **WIP commit 3**（若 step 6 后还有遗漏的 fixture 改动）
16. 修改 `API-CONTRACT.md` §setup-monitor 响应示例 + 字段说明 + readySignal 描述 7→8
17. 修改 `DATA-MODEL.md` §SetupSnapshot 字段表 ready_signal 7→8；业务规则段加 Weekly Stage 门禁 bullet
18. 修改 `DECISIONS.md` 追加 D093
19. Evaluator 自检 → **Final commit** → 调用 consistency-check (mode=interactive) C1/C4/C5/C7 → 标 phase=needs_review → 等待 acceptance

---

## 8. 风险与回滚

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| s10/s11 测试 fixture 改漏 → 集成测试通过但单元回归挂 | 中 | 老回归挂 1-2 case | step 6/7 显式改 `_ready_kwargs` 并 step 14 全量跑兜底；若实在挂，回 step 6 用 `grep "_compute_ready_signal" backend/tests/` 找全所有调用点 |
| `WeeklyStageRepository.get_latest_for_tickers` SQLite 行为偏差（dedupe 逻辑） | 低 | 多 ticker 取错 stage | T13 多 ticker fixture 兜底；repo 已注释"Used by F216-d setup_service integration"说明专为此场景 |
| ready=False 标的暴增（>50% 减少）影响用户体验 | 中 | 用户找不到 enter 标的 | flag `READY_REQUIRE_STAGE2=False` 一键关闭；acceptance 阶段用户验收若觉得过严，调 flag 即可 |
| weekly_stage_snapshots 表为空（F216-b 已 done 但生产未跑 cron）→ 所有 ready=False | 中 | acceptance 当天用户看到全黑 | 文档化 cron 顺序依赖（D093 + 业务规则 bullet）；acceptance 前手动跑 `WeeklyStageService.compute_and_store_all()` 一次 |
| DATA-MODEL.md / API-CONTRACT.md / DECISIONS.md 三处描述漂移 | 低 | 文档不一致 | step 16-18 同步在一个 Final commit；consistency-check C7 兜底 |
| 短数据分支（closes<10）的 row 未写 weekly_stage 字段 → ORM/schema 校验失败 | 低 | 异常路径挂 | T12 显式覆盖；标准 6 自检明确写入 |

**回滚方案**：
- 业务层：set `SETUP.READY_REQUIRE_STAGE2 = False`（env override 或代码改一行），ready_signal 立刻退回 7 条 AND，无需 migration / 回退 commit
- 代码层：`git revert <final-commit>` 一次性回退 7 文件改动；d1 schema 列保留无碍

---

## 9. 后续衔接

F216-d2 done 后：
- F216-d3 立即可起：前端 `setupMonitorApi.ts` SetupItem 加 `weeklyStage` + `SetupMonitorWidget.tsx` 加 "WS" 列（依赖 API 响应字段已暴露）
- F216-e 等 d3 done 后再起：refresh_job cron 编排 regime→weekly_stage→setup 顺序（生产环境冷启动 watcher）

---

👤 用户已确认本 Contract（2026-05-14 NP-A 至 NP-H 全部按推荐拍板）。下个 session（建议 Sonnet）从 §7 开发顺序步骤 1 开始。
