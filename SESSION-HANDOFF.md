# SESSION-HANDOFF — F218-d2 Generator 启动

> 生成：2026-05-18 (Opus 4.7) | 用途：下一 session 接入 F218-d2 Generator
> Skill 链：feature-dev A-3 Contract（F218-d2 ✅ confirmed @ 本 session） → **本 handoff** → feature-dev A-2 Generator（Sonnet 新 session 执行）

---

## 1. 本次 session 完成内容

### 1.1 F218-d2 Sprint Contract 起草并确认

- 文件：[docs/开发/sprint-contracts/F218-d2-contract.md](docs/开发/sprint-contracts/F218-d2-contract.md) (status=confirmed)
- 范围：T1 EARNINGS_ACCEL detector 实装（d1 skeleton 留下的第 1 个占位 `_detect_earnings_acceleration` → 真实业务逻辑）
- 3 文件 / 10 测试 / 不动 API / 不动前端 / 不动 cron / 不动 alembic

### 1.2 NP-d2-1 ~ NP-d2-7 关键决策（全部按推荐）

| # | 议题 | 确认结论 |
|---|------|---------|
| NP-d2-1 | 加速判定 | 严格单调递增 `yoy[0] < yoy[1] < yoy[2]`（非允许持平 / 非每步最小增量） |
| NP-d2-2 | 触发依据 | EPS 单独判定（revenue 仅作 evidence 副产物，缺失不阻断） |
| NP-d2-3 | 数据完整性 | 6 季 actual EPS 全齐才判定；任一缺失返 None（不插值不均值） |
| NP-d2-4 | confidence 阈值 | 仅看最近一季：`yoy[-1] ≥ 0.30 → 0.8`，否则 0.5（DATA-MODEL.md 业务规则原文） |
| NP-d2-5 | quarter label | earnings_date 日历季度 `"YYYYQN"`（不加 alembic 023 fiscal_quarter 列） |
| NP-d2-6 | repo 新方法名 | `get_recent_completed_for_ticker(ticker, limit=8)`（与既有 `get_next_earnings` 对称） |
| NP-d2-7 | 负基准 | 上年同期 EPS ≤ 0 → 整体返 None（不做负基准除法） |

### 1.3 features.json 更新

- `F218.sub_sprints.F218-d2`: `design_needed` → `contract_agreed`
- `F218.iteration_history`: 追加 contract_agreed 条目（2026-05-18，subtask=F218-d2）
- `_pipeline_status.active_sprint`: 保持 `F218-d2`

### 1.4 progress 日志更新

- `claude-progress.txt` 追加 [2026-05-18 ⑤] feature-dev A-3 Contract 协商：F218-d2 段

---

## 2. 当前状态

```
F218 phase: in_progress
F218-d1: done
F218-d2: contract_agreed  ← Generator 模式即将启动
F218-d3a ~ d7b: design_needed（排队，本次范围外）
_pipeline_status.active_sprint: F218-d2
```

---

## 3. 下一步任务（Sonnet 新 session 执行）

### 3.1 恢复指令

```
继续开发 F218-d2，Sprint Contract 已确认。
读取 SESSION-HANDOFF.md + docs/开发/sprint-contracts/F218-d2-contract.md，
进入 Generator 模式，按 3 步开发顺序推进：
  1) repo +方法 get_recent_completed_for_ticker（+ 最小 pytest 单测验证通过）
  2) service detector 实装：
     - import EarningsEventRepository
     - __init__ 内 self._earnings = EarningsEventRepository(db)
     - 5 个模块级常量 T1_LOOKBACK_QUARTERS=6 / T1_REQUIRED_QUARTERS=3 / T1_HIGH_CONFIDENCE_YOY=0.30 / T1_HIGH_CONFIDENCE_SCORE=0.8 / T1_DEFAULT_CONFIDENCE=0.5
     - _detect_earnings_acceleration 占位 → 真实主体（参考 contract §1.2 完整伪代码）
     - 模块级 helper _quarter_label(d: date) -> str
  3) 新文件 backend/tests/test_repricing_trigger_earnings_accel.py，10 测试 / 3 class（repo 2 + detector 7 + 端到端 1），按 contract §3 测试用例表逐条实现
每步通过最小验证后 wip commit。
完成后 Evaluator 模式按 contract §4 自检清单逐条检查；全部通过后 phase → needs_review，提示用户验收。
```

### 3.2 3 步开发顺序（细节）

**Step 1 — EarningsEventRepository 新方法**
- 文件：`backend/app/repositories/earnings_event_repository.py`
- 在既有 3 方法（upsert_batch / get_next_earnings / delete_before）之后追加 `get_recent_completed_for_ticker(ticker, limit=8) -> list[EarningsEvent]`
- 过滤：`eps_actual IS NOT NULL`；排序：`earnings_date DESC`；limit 截断
- wip commit：`wip(F218-d2): EarningsEventRepository.get_recent_completed_for_ticker`

**Step 2 — RepricingTriggerService T1 实装**
- 文件：`backend/app/services/cockpit/repricing_trigger_service.py`
- 改动：import EarningsEventRepository / __init__ 注入 / 5 T1_* 模块常量 / _detect_earnings_acceleration 占位换实装 / 文件底部追加 `_quarter_label` 模块函数
- 关键算法（见 contract §1.2 完整伪代码）：
  ```
  rows = self._earnings.get_recent_completed_for_ticker(ticker, limit=6)
  if len(rows) < 6: return None
  recent = rows[:3]  # [Q-1, Q-2, Q-3] (DESC 顺序)
  prior  = rows[3:]  # [Q-1y, Q-2y, Q-3y]
  for cur, prv in zip(recent, prior):
      if prv.eps_actual is None or prv.eps_actual <= 0: return None  # NP-d2-7
      eps_yoy.append(cur.eps_actual / prv.eps_actual - 1.0)
      # revenue_yoy 同步计算（缺失/负基准 → None，不阻断）
  eps_yoy.reverse()  # 时间正向 [Q-3, Q-2, Q-1]
  if not (eps_yoy[0] < eps_yoy[1] < eps_yoy[2]): return None  # NP-d2-1 严格单调
  confidence = 0.8 if eps_yoy[-1] >= 0.30 else 0.5  # NP-d2-4
  quarters = [_quarter_label(r.earnings_date) for r in reversed(recent)]
  return DetectorResult(confidence, {eps_yoy_growth, revenue_yoy_growth, quarters})
  ```
- wip commit：`wip(F218-d2): _detect_earnings_acceleration T1 implementation`

**Step 3 — 10 测试**
- 文件（新）：`backend/tests/test_repricing_trigger_earnings_accel.py`
- 3 class 分组：
  - `TestEarningsEventRepoRecentCompleted` — 测试 1, 2
  - `TestDetectEarningsAcceleration` — 测试 3, 4, 5 (3 case 参数化), 6, 7, 8, 9 (3 case 参数化)
  - `TestEarningsAccelEndToEnd` — 测试 10
- 沿用 conftest.py `db_session` fixture
- 端到端测试需借 `compute_and_store_all_triggers` 验证 d1 主入口与 d2 detector 协同（hit → upsert / re-scan miss → soft expire）
- wip commit：`wip(F218-d2): T1 earnings acceleration tests (10 cases)`

### 3.3 Evaluator 自检

按 [contract §4](docs/开发/sprint-contracts/F218-d2-contract.md) 逐条检查；重点：
- 10 新测试全绿 + d1 既有 14 测试不回归 + 全量回归无新增失败
- EARNINGS_ACCEL evidence_json schema 严格对齐 DATA-MODEL.md（3 字段 / 列长 3）
- F204 既有 test_earnings_f204a/b 不回归（repo 只加方法，不改既有签名）

通过后：
1. F218-d2 phase → `needs_review`
2. iteration_history 追加 needs_review 条目
3. 提示用户验收

---

## 4. 未决事项

| 事项 | 优先级 | 负责 sprint |
|------|-------|------------|
| `StockRepository.get_active_tickers()` 方法仍未创建（service 用 `list_active()` 列表推导） | 低 | 可选：任意 sprint 中顺手加，不阻塞 |
| `test_schema.py::test_all_tables_created` EXPECTED_TABLES 未含 `weekly_stage_snapshots` / `repricing_triggers` | 低 | 建议 F218-d7a 一并修 |
| T3 D4b NLP 升级 | 低 | 独立 issue，F218 范围外 |

---

## 5. 关键引用

- F218-d2 合约：[docs/开发/sprint-contracts/F218-d2-contract.md](docs/开发/sprint-contracts/F218-d2-contract.md)
- F218-d1 合约（同形态参考）：[docs/开发/sprint-contracts/F218-d1-contract.md](docs/开发/sprint-contracts/F218-d1-contract.md)
- DATA-MODEL §RepricingTrigger（EARNINGS_ACCEL evidence_json schema + 业务规则）：[docs/系统设计/DATA-MODEL.md](docs/系统设计/DATA-MODEL.md)
- ARCHITECTURE §Cockpit Repricing Trigger Service（T1 模块边界）：[docs/系统设计/ARCHITECTURE.md](docs/系统设计/ARCHITECTURE.md)
- d1 skeleton 文件：
  - [backend/app/services/cockpit/repricing_trigger_service.py](backend/app/services/cockpit/repricing_trigger_service.py)
  - [backend/app/repositories/repricing_trigger_repository.py](backend/app/repositories/repricing_trigger_repository.py)
  - [backend/app/models/repricing_trigger.py](backend/app/models/repricing_trigger.py)
- T1 数据源（既有 F204 成果）：
  - [backend/app/repositories/earnings_event_repository.py](backend/app/repositories/earnings_event_repository.py)
  - [backend/app/models/earnings_event.py](backend/app/models/earnings_event.py)
- 进度日志：[claude-progress.txt](claude-progress.txt)
