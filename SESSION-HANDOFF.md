# SESSION-HANDOFF.md

> 生成时间：2026-04-22
> 当前分支：`feat-newfeature`（v1.2.0 发布后持续迭代中）
> 当前 Skill：feature-dev（Evaluator 反向补契约链路暂停）
> 刚完成：**F106 Multi-Signal Scanner 全链路 done + F107 股价图 Vol/MA5/MA20 反向补契约 done**
> 下一步：**新 session 协商 F107-b1 Sprint Contract（Generator 模式）**

---

## 本 Session 完成的内容

### 1. F106-c 前端 Multi-Signal Widget（Generator 收尾）
- commit `1c53f88` — shadcn Tabs 引入 + Stage/Pullback 双 Tab 拆分 + Legacy/Stage/Pullback 三段渲染
- **D048** 追加到 DECISIONS.md：**前端 vitest / @testing-library/react 基建延至 v1.4**。本 sprint 及后续 F107/F108/F109 的 contract 单元测试门禁统一降级为：typecheck + build + docker E2E + 代码审查
- F106-c contract 自检表全勾；移除 `tabsListVariants` 导出修掉 react-refresh/only-export-components lint 报错

### 2. F106 验收 → done
- commit `10c2e19` — features.json F106-c phase→done、F106 status/phase→done
- F106 Multi-Signal Scanner 全链路交付：A1 stage breakout / A2 slope flip / B2 ma pullback / legacy_crossover 四种信号 + 后端 `/api/market/breakouts?type=` 过滤 + 前端 shadcn Tabs 分区

### 3. F107 股价图 Vol + MA5/MA20 反向补契约（Evaluator）
- commit `3b923a0` — 代码零改动，仅核对 + 补文档：
  - PriceChart.tsx：HistogramSeries（priceScaleId='volume'，scaleMargins top 0.8/bottom 0）+ shortMaData rolling window O(N) + 双 priceScale + ResizeObserver + chart.remove() cleanup 全部通过
  - ChartWidget.tsx：左上 absolute 3 行图例（MA5 #f59e0b / MA20 #8b5cf6 / MA150 蓝）确认
  - design-spec.md 第 250-258 行补 F107 增强小节（短均线配色 = TradingView 社区惯例；volume scaleMargins 约定）
  - F107-contract.md Evaluator 自检 7/9 ✅（余 2 条浏览器手工视觉交用户验收）
- 硬门禁：tsc -b + vite build（371ms）✅；docker 后端 `/api/stocks/AAPL/chart` 250 bars + 101 MA150 points ✅

### 4. F107-b Vol/Float 比率增强 Plan（未 commit，已 approved）
- 用户诉求："成交量 bar 能看见但看不到数字，真正想看的是'当日成交量 ÷ shares_float'的**百分比数值**"
- 经 plan 模式 + AskUserQuestion 3 问定稿，plan 文件：`~/.claude/plans/tingly-jumping-pebble.md`
- 决策：**拆成 F107-b1（后端）+ F107-b2（前端）**；crosshair hover 联动，默认显示最新一天；所有历史 bar 统一使用当前 float

---

## 当前状态

- 工作目录：`/Users/wonderer/Desktop/Claude workspace/stock_portal`
- 分支：`feat-newfeature`
- 已提交 commits（本 session 3 个）：
  - `1c53f88` feat(F106-c): multi-signal widget — shadcn Tabs + stage/pullback split
  - `10c2e19` chore(F106): accept F106-c — F106 Multi-Signal Scanner done
  - `3b923a0` feat(F107): chart volume histogram + MA5/MA20 overlay
- 工作树未提交文件（**全部是 pre-session 的用户手改，留给对应 reverse-contract sprint 落地，勿动**）：
  - F108 scope：`backend/app/services/stock_detail_service.py`、`docs/系统设计/DATA-MODEL.md`
  - F109 scope：`frontend/src/App.tsx`、`frontend/src/components/features/topnav/TopNav.tsx`、`frontend/src/components/features/dashboard/AddStockCard.tsx`、`frontend/src/workbench/WidgetShell.tsx`、`frontend/src/workbench/widgets/FundamentalsWidget.tsx`、`frontend/src/workbench/widgets/PullbackWidget.tsx`、`frontend/src/workbench/widgets/QuickAddWidget.tsx`、`frontend/src/workbench/widgets/WatchlistWidget.tsx`
  - 其他：`backend/uv.lock`（待 sprint 内确认归属）
  - Untracked：`README.md`、`docs/开发/sprint-contracts/F108-contract.md`、`F109-a-contract.md`、`F109-b-contract.md`、`docs/需求/SIGNAL-CATALOG.md`

---

## 功能状态总表

| Feature | Status | Phase | 说明 |
|--------|--------|-------|------|
| F106 Multi-Signal Scanner | ✅ done | done | a/b/c 全交付 |
| F107 股价图 Vol + MA5/20 | ✅ done | done | 反向补契约完成 |
| F107-b1 后端 shares_float | ⬜ | contract_needed | 5 业务文件，Generator 模式 |
| F107-b2 前端 Vol/Float 显示 | ⬜ | contract_needed | 3 业务文件 |
| F108 /fundamentals & /pullbacks 放开 | ⬜ | contract_agreed | 反向补契约（D047） |
| F109-a Widget 间距 | ⬜ | contract_agreed | 反向补契约 |
| F109-b TopNav 重做 | ⬜ | contract_agreed | 反向补契约 |

---

## 下一步任务（新 session 第一件事）

**协商 F107-b1 Sprint Contract**，Generator 模式，后端 shares_float 数据链路。

### 参考
- **Plan 文件**：`~/.claude/plans/tingly-jumping-pebble.md`（完整设计，approved）
- **Contract 模板**：`~/.claude/skills/feature-dev/references/sprint-contract-template.md`

### F107-b1 核心设计（从 plan 抽取）
- **5 业务文件**（不违反 6-file 原则）：
  1. `backend/app/external/fmp_client.py` — 新增 `get_profile(ticker)` 方法，命中 `/api/v3/profile/{ticker}`，返回带 `sharesFloat || floatShares` 的 dict
  2. `backend/app/models/stock.py` — `Stock` 表加 `shares_float: int | None` + `shares_float_fetched_at: datetime | None` 两列
  3. `backend/alembic/versions/004_f107b1_shares_float.py` — add_column ×2
  4. `backend/app/services/stock_detail_service.py` — `/chart` 路径返回时拼接 sharesFloat（DB 缓存 24h TTL；miss 则调 fmp_client.get_profile 回写）
  5. `backend/app/schemas/stock_detail.py` — ChartResponse 新增 `shares_float: int | None`
- **决策已定**（无需再问用户）：A1 `/chart` 端点捎带 sharesFloat；B3 DB 缓存 24h TTL；C1 FMP `/profile` with `sharesFloat || floatShares` fallback
- **测试门禁**（按 D048 降级）：typecheck、pytest（新 3 case：get_profile mock / service cache hit/miss）、alembic upgrade→downgrade smoke、docker `/api/stocks/AAPL/chart` 返回带 shares_float

### 新 Session 启动指令

```
我回来了，请读取：
- SESSION-HANDOFF.md
- CLAUDE.md
- ~/.claude/plans/tingly-jumping-pebble.md（F107-b 完整 plan）
- docs/需求/features.json（F107-b 尚未登记，协商 contract 时同步补 F107-b1/b2 feature 条目）
- claude-progress.txt（最后 60 行）

然后进入 feature-dev Generator 模式，协商 F107-b1 Sprint Contract
（后端 shares_float 链路，5 业务文件）。
```

---

## 未决事项 / 需警戒

1. **F107-b 在 features.json 中尚未登记**：协商 F107-b1 contract 时需同步补 F107-b / F107-b1 / F107-b2 条目（priority P1，dependencies F107），避免 contract 引用悬空
2. **shares_float 在 FMP 的字段名漂移**：`/profile` 端点同时存在 `sharesFloat` 和 `floatShares`，实装时用 `payload.get('sharesFloat') or payload.get('floatShares')` 双路取值，并在 fmp_client 单元测试覆盖两种 fixture
3. **DB 缓存 TTL 24h 的边界**：FMP profile 字段变动频率低，但 split/ipo 后 float 会跳变；Contract 内需记一条 "D049 候选：shares_float 刷新触发条件（暂定 24h 硬 TTL，若 split 场景出 bug 再议）"
4. **F107-b2 需从 FundamentalsCard.tsx 抽 formatPercent 到新 `lib/format.ts`**：避免在 PriceChart 和 FundamentalsCard 两处重复；这件事登记在 plan 的 F107-b2 scope 内
5. **工作树的 pre-session 用户手改**：开新 session 切 contract 前 **不要** 为了 clean 状态而暂存/commit 这些改动，它们是 F108/F109 的业务变更，需要在各自 reverse-contract sprint 里审查后提交

---

## 相关文档

- 决策：`docs/系统设计/DECISIONS.md` — D047（F108 前置）、D048（前端测试基建延至 v1.4）
- 契约：`docs/开发/sprint-contracts/F106-contract.md`（a/b/c）、`F107-contract.md`
- 需求：`docs/需求/features.json` — F106 done / F107 done / F108 F109 contract_agreed
- 设计：`docs/设计/design-spec.md` 第 250-258 行 F107 增强小节
- 进度：`claude-progress.txt` 尾部两个条目（F107 验收 + session 暂停）
- Plan：`~/.claude/plans/tingly-jumping-pebble.md`（F107-b 完整设计）
