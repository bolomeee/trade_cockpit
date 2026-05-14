# SESSION-HANDOFF — F216-a Sprint Contract 已确认（contract_agreed）

> 生成时间：2026-05-14
> 当前 sprint：F216-a — Weekly Aggregation Service (Phase B / B1)
> 下一阶段：Generator 模式（建议新 session 用 Sonnet 启动）

---

## 已完成内容（本 session）

### 1. F214 收尾
- F214 ChartWidget Add to Watchlist 最终验收通过，features.json 翻 `done`，写 [v1.9-F214-acceptance.md](docs/验收/v1.9-F214-acceptance.md)

### 2. consistency-check drift 清理（release gate 解锁）
- 45 个 legacy pre-sub_sprints 合约 `git mv` 到 `docs/开发/sprint-contracts/archive/legacy-pre-sub-sprints/`，写归档 README
- C5 违例 45 → 0；C2 误报澄清后 0；全部检查清零
- commit `3f3d90f` 已收口（含 F215-a contract / F215-a 验收记录补提交、F215-b 文档同步补提交）

### 3. F216 Phase B 启动
- F216 (Cockpit Phase B — Weekly Stage Layer) 注册到 features.json
- 5 sub-sprints: F216-a / b / c / d / e
- F216-a Sprint Contract 起草并 **全部按推荐方案确认 4 协商点**：
  - NP1 weeks=50 不扩窗
  - NP2 weekly bar.date = 本周最后实际交易日
  - NP3 unknown ticker → APIError(NOT_FOUND)
  - NP4 daily_bars<4 → 返回空不抛错
- F216-a sub_sprint status: `design_needed` → `contract_agreed`

---

## F216-a Sprint Contract 摘要

**Contract 文件**：[F216-a-contract.md](docs/开发/sprint-contracts/F216-a-contract.md)

**实现范围（3 个文件，远低于 6 上限）**：

| 文件 | 类型 | 说明 |
|------|------|------|
| `backend/app/services/cockpit/weekly_chart_service.py` | 新建 | `aggregate_daily_to_weekly` 纯函数 + `WeeklyChartService.get_weekly_chart` |
| `backend/app/services/cockpit/cockpit_params.py` | 修改 | 追加 `WEEKLY` 配置组（DEFAULT_WEEKS=50 / WEEKLY_MAS=[10,30,40] / MIN_DAILY_BARS_FOR_WEEKLY=4） |
| `backend/tests/test_weekly_chart_service.py` | 新建 | 10 条测试（9 单元 + 1 回归） |

**关键约束**：
- 零 FMP 调用（仅从 `daily_bars` 读取）
- 复用 `chart_service._compute_ma_series` 算 Weekly MA 10/30/40，不重新实现 SMA
- 沿用 `app.services.watchlist_service.APIError` 错误类型
- `weeks=50` 默认（与 DAILY_BAR_WINDOW=250 匹配）
- ISO 周分组：`bar.date.isocalendar()[:2]` 作为分组键

**完成标准（10 条）**：
1. `aggregate_daily_to_weekly([])` → `[]`
2. 标准 5 个交易日 → 1 个 weekly bar，date=周五
3. 跨周分组：10 个交易日 → 2 个 weekly bars
4. 短周（周一-周四）→ weekly bar.date=周四
5. 孤立单日 → 1 个 weekly bar 等于该日 OHLC
6. `get_weekly_chart("UNKNOWN")` → APIError("NOT_FOUND")
7. `get_weekly_chart("AAPL", weeks=50)` 在 mock 250 行返回 ~50 个 weekly_bars
8. daily_bars<4 行 → 返回空 weekly_bars + 空 weekly_mas，不抛错
9. `WEEKLY.DEFAULT_WEEKS==50 and WEEKLY.WEEKLY_MAS==[10,30,40]`
10. 全量后端 pytest 无新增失败（test_decision_f203b.py 预存 ImportError 例外）

---

## 开发顺序（Generator 阶段，不得跳步）

按 Contract §6：

1. 重读 `backend/app/services/cockpit/chart_service.py` 的 `_compute_ma_series`（lines 24-40）和 `_bars_from_db`（lines 215-235）确认接口
2. 重读 `backend/app/services/cockpit/cockpit_params.py` 当前最末位置，确认在哪里追加 `WEEKLY` 类
3. 在 cockpit_params.py 追加 `WEEKLY` 配置组
4. 新建 `weekly_chart_service.py`：先写 `aggregate_daily_to_weekly` 纯函数 + WeeklyBarDict TypedDict
5. 跑标准 1-5 测试（pure function）确认聚合正确
6. 在 `weekly_chart_service.py` 加 `WeeklyChartService` 类 + `get_weekly_chart`
7. 跑标准 6-9 测试确认 service 集成正确
8. 跑全量后端 pytest，确认标准 10 无回归
9. 追加 DECISIONS.md 决策记录（编号 D090 — 查 DECISIONS.md 最大号 +1）
10. Generator 收尾 WIP commit（**不要 `-A`，显式列 3 个文件**）
11. Evaluator 自检 → 全清后切 needs_review，调用 consistency-check (mode=interactive)

---

## 已知限制

- F216 整体只覆盖 50 周历史（DAILY_BAR_WINDOW=250 限制）
- plan §Phase B 验证 §3 的"NVDA 2022 Stage 3 历史回测"不在本期范围
- 5 年历史回测留待未来"daily_bars 扩窗"专项 feature

---

## 当前 git 状态

- 分支：`improve_against_plan`
- 最新 commit：`3f3d90f` chore: F214 acceptance + drift cleanup + backfill F215-a artifacts
- 本 session 尚未 commit 的文件：
  - `docs/需求/features.json`（F216 注册 + F216-a contract_agreed）
  - `docs/开发/sprint-contracts/F216-a-contract.md`（新合约文件）
  - `claude-progress.txt`（追加 F216 启动条目）
  - `SESSION-HANDOFF.md`（本文件）

⚠️ 建议在 Generator 开始前由本 session 顺手收一个 `docs(F216-a):` commit 把这 4 个 doc 文件落地，避免 Generator session 一上来就要清理这些散落改动。

---

## 恢复指令（下一 session）

新 session 推荐用 **Sonnet**。复制粘贴：

```
继续开发 F216-a，Sprint Contract 已确认。
读取 SESSION-HANDOFF.md + docs/开发/sprint-contracts/F216-a-contract.md，
进入 Generator 模式，从开发顺序步骤 1 开始。
```

---

## 项目整体功能状态

| Feature | 状态 |
|---------|------|
| F000 – F213 | ✅ done |
| F214 ChartWidget Add to Watchlist | ✅ done（本 session 验收通过） |
| F215 Cockpit Phase A | ✅ done |
| **F216 Cockpit Phase B Weekly Stage Layer** | 🔄 **in_progress** |
| └─ F216-a Weekly Aggregation Service | 🤝 contract_agreed |
| └─ F216-b/c/d/e | ⬜ design_needed |
| F217 Phase C (Capitulation 重写) | ⬜ 未规划 |
| F218 Phase D (Repricing Trigger) | ⬜ 未规划 |
