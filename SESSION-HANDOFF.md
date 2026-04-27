# SESSION HANDOFF — F205-b Sprint Contract 已确认

> 生成时间：2026-04-27
> 当前 Skill：feature-dev（Sprint Contract 协商完成，等待 Generator 模式启动）
> 当前 Feature：F205 Pool Builder Widget — sub_sprint **F205-b**（FMP 增量 + Pool 计算 helpers）
> phase：`contract_agreed`

---

## 1. 本 session 完成

仅完成 Sprint Contract 协商，**未写任何代码**。

- ✅ 起草并确认 `docs/开发/sprint-contracts/F205-b-contract.md`
- ✅ 更新 `docs/需求/features.json`：
  - `last_updated` → `2026-04-27-F205-b-contract-agreed`
  - `active_sprint_phase` → `contract_agreed`
  - F205 sub_sprints.F205-b → `contract_agreed`
  - F205 estimated_files_changed 追加 4 个 F205-b 文件
- ✅ 追加 `claude-progress.txt`

---

## 2. Sprint Contract 摘要

### 范围（pure building blocks，**不**包含 PoolService / router）

1. **FMP 客户端增量**：`backend/app/external/fmp_client.py` 加 `get_financial_growth(symbol)` 方法
   - 调 `/stable/financial-growth?period=annual&limit=1`
   - 返回 `dict | None`（None = 空数组 / 网络异常 / HTTP 错误）
   - 复用现有 token bucket + 6-concurrency semaphore + 429 retry
2. **`backend/app/services/cockpit/pool_helpers.py` 新建**，5 个纯函数：

| 函数 | 职责 |
|------|------|
| `compute_return_ratio_250d(closes, spy_closes)` | 250 日 stock_return / spy_return；序列不足 / spy_return≈0 → None |
| `compute_rs_percentile_map(ratio_by_ticker)` | population-agnostic 百分位 rank（mid-rank ties），与 setup_service `_percentile_rank` 公式一致 |
| `compute_distance_to_50ma_pct(close, ma50)` | (close - ma50) / ma50 × 100；ma50 None/0 → None |
| `extract_revenue_growth_yoy_pct(payload)` | 从 FMP financial-growth 返回值读 revenueGrowth × 100 |
| `passes_fundamental_sanity(growth_pct, threshold_pct)` | None → True（fail-open，决策见 D079） |

3. **决策落档**：DECISIONS.md 追加 D079
4. **测试覆盖**：18 条标准（详见 contract §3）

### 显式排除

- ❌ 不写 PoolService / router / schema（F205-c）
- ❌ 不动 setup_service.py（保留双 RS 实现）
- ❌ 不动 F106 scanner / 不新建数据库表
- ❌ 不写 trend-subset materializer / 批量 FMP / 缓存（F205-c）
- ❌ 不动前端

### 文件计数：4/6（合约预算余 2，无需拆分）

| # | 文件 | 改动 |
|---|------|------|
| 1 | `backend/app/external/fmp_client.py` | 修改 |
| 2 | `backend/app/services/cockpit/pool_helpers.py` | 新建 |
| 3 | `backend/tests/test_pool_helpers_f205b.py` | 新建 |
| 4 | `backend/tests/test_fmp_client.py` | 修改 |

附加文档（不计入 6 文件）：`docs/系统设计/DECISIONS.md` 追加 D079。

---

## 3. 开发顺序（Generator 模式按此执行，不得跳步）

1. **读 Contract**：`docs/开发/sprint-contracts/F205-b-contract.md` 全文
2. **核对 DATA-MODEL / API-CONTRACT 无需改动**（本 sprint 不涉及表结构 / 公开 API），快速确认即可跳过
3. **Step 1 — FMP 客户端增量**
   1. 用 context7 查 FMP `/stable/financial-growth` 最新文档（`/websites/fmp_api`，若 ID 不存在则 fallback 到 web search）
   2. 阅读 `fmp_client.py` 现有 `get_ratios_ttm` / `get_key_metrics_ttm` 模式（重点：错误处理、retry 调用风格、返回类型）
   3. 实现 `get_financial_growth(symbol) -> dict | None`，**与现有方法风格严格一致**
   4. 在 `test_fmp_client.py` 加用例（成功 / 空数组 / HTTPError / 429 retry）
   5. `pytest backend/tests/test_fmp_client.py` 通过
   6. **WIP commit**：`wip(F205-b): fmp_client get_financial_growth`（显式 add 2 个文件，禁用 -A）
4. **Step 2 — pool_helpers.py 5 个纯函数**
   1. 阅读 setup_service.py 中现有 `_compute_return` / `_percentile_rank`，记下公式和 ties 处理
   2. 新建 `backend/app/services/cockpit/pool_helpers.py`，5 个函数 + 模块 docstring
   3. **铁律**：模块顶部不 import 任何 `app.*` / `logging` / `Session` / `httpx`
   4. 边界条件全部 graceful 降级（None / 空字典 / False），不抛异常
   5. **WIP commit**：`wip(F205-b): pool_helpers pure module`（显式 add 1 个文件）
5. **Step 3 — pool_helpers 测试**
   1. 新建 `backend/tests/test_pool_helpers_f205b.py`，覆盖 contract §3 第 5–17 条
   2. 测试 #8 #9 调用 setup_service 的 `_percentile_rank` 做 reference 对比，**确保两套实现行为一致**
   3. 测试 #17 用 grep / AST 验证 pool_helpers.py 无 `app.*` import
   4. `pytest backend/tests/test_pool_helpers_f205b.py` 通过
   5. **WIP commit**：`wip(F205-b): pool_helpers tests`
6. **Step 4 — DECISIONS.md 追加 D079**
   - 内容：FMP `/financial-growth?period=annual&limit=1` 选择、RS 公式（与 setup_service 一致）、fail-open 决策、双实现作为已知技术债（dedup 推到后续）
   - **WIP commit**：`docs(F205-b): D079`
7. **Step 5 — Evaluator 模式自检**
   1. 切换 QA 视角，逐条对照 contract §4 自检清单
   2. 全量回归 `pytest backend/`：期望 758 + N（N = 新增用例数），无新失败
   3. 静态验证 pool_helpers.py 纯净度（grep）
   4. 输出 Evaluator 评估报告
8. **Step 6 — 全部通过后**
   - phase → `needs_review`
   - 最终 commit：`feat(F205-b): FMP financial-growth + pool helpers`（可选 squash 之前 WIP，**默认保留**）
   - 更新 features.json + claude-progress
   - 通知用户进入 acceptance

---

## 4. 关键约束（Generator 模式必读）

1. **6-file 已用 4 个**，剩 2 个余量。若开发中发现需要新增第 5 / 6 个文件（例如 conftest 加 fixture），先停下来报告
2. **不得修改 setup_service.py**。这是规避 F202-a 回归的硬约束。如果发现必须改，停下来报告（视为 scope creep）
3. **pool_helpers.py 必须是纯模块**：无 IO、无 logger、无 SQLAlchemy。Evaluator 会 grep 验证
4. **RS 算法必须与 setup_service `_percentile_rank` 完全一致**（mid-rank ties），测试 reference 对比
5. **WIP commit 显式列文件名，禁用 `git add -A`**（feature-dev 规则 7）
6. **新依赖引入流程**：本 sprint 应该不需要新依赖；若发现需要，按规则 9 停下报告

---

## 5. 下一 Session 恢复指令

**Sonnet 新 session 粘贴**：

```
继续开发 F205-b，Sprint Contract 已确认。
读取 SESSION-HANDOFF.md + docs/开发/sprint-contracts/F205-b-contract.md，
进入 Generator 模式，从开发步骤 1 开始。
```

---

## 6. 当前 git 状态

- 分支：`cockpit`
- 已修改未提交：
  - `SESSION-HANDOFF.md`（本文件，重写）
  - `docs/需求/features.json`（F205-b → contract_agreed + estimated_files_changed 追加）
  - `claude-progress.txt`（追加 contract 协商记录）
  - `docs/开发/sprint-contracts/F205-b-contract.md`（**新建**，本 session 产物）
- F205-a 残留未提交（来自上一 session 的 acceptance 阶段）：
  - `backend/alembic/versions/015_f205a_universe_extra_fields.py`（新）
  - `backend/app/models/market_scan_universe.py` / `repositories/...` / `services/universe_refresh_service.py`
  - `backend/tests/test_market_scan_repositories.py` / `test_schema.py` / `test_universe_refresh_service.py`
  - `backend/uv.lock`
  - `docs/系统设计/DATA-MODEL.md` / `DECISIONS.md`
  - `docs/验收/v1.9-F205-a-acceptance.md`（新）

⚠️ Generator 模式开始前，先做一次 `git status` 清点：F205-a 的残留改动应作为独立 commit（feat(F205-a): ... 或先 chore(F205-a): wrap up），**不要混进 F205-b 的 commit**。这是 feature-dev 规则 7"sprint 之间杂项 commit"的明确要求。

---

## 7. 遗留事项

- F205-a 工作树残留改动 11 个文件，需在 F205-b 开发开始前作为独立 commit 清理（见上文 §6）
- F205-a `needs_review` 状态下未走 acceptance skill，但 claude-progress 显示已"验收通过"且生成了 `docs/验收/v1.9-F205-a-acceptance.md` — 状态稍有 drift，建议下个 session 开始前先把 F205-a 残留 commit 进去
