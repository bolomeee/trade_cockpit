# PRD 未决事项

> 创建：2026-04-16 | 最近更新：2026-04-22

## 已关闭（归档）

- ~~B1~~ ✅ 已补充"不包含"边界（实时行情、回测），保留多 watchlist 扩展空间
- ~~B2~~ ✅ 已补充空状态引导
- ~~B3~~ ✅ 已补充错误处理：系统日志区域、搜索 Alert、数据不足提示
- ~~B4~~ ✅ 已扩展 Journal 操作类型为 买/卖/加仓/减仓/观望

---

## 待处理

### T-001：补齐 v1.1 Workbench 新 widget 的 design-spec 章节

**背景**：`docs/设计/design-spec.md` 当前的"页面 1/1a/2/2a/3"章节是 v1.0 Dashboard/Journal/Logs 的视觉规格。v1.1 Workbench 重构后新增的以下 widget **在 spec 里完全没有章节**：

| Widget | Registry ID | 现状 |
|--------|-------------|------|
| MarketBreakoutWidget | `scanner.breakouts` | 代码已实现（含 Breakout/Pullback tabs），spec 空白 |
| FundamentalsWidget | `sma150.fundamentals` | 代码已实现（F107 系列），spec 仅作为 StockDetailModal 一部分描述 |
| PullbackWidget | `sma150.pullbacks` | 代码已实现，spec 无独立章节 |
| ChartWidget | `sma150.chart` | lightweight-charts，spec 仅在页面 1a 提及 |
| QuickAddWidget | `journal.quickadd` | 代码已实现，spec 无独立章节 |

**要做什么**（由下一个 session 接手）：
1. 参考现有"页面 1：Dashboard"章节格式，为上述 5 个 widget 各补一个章节
2. 每个章节包含：组件层级 / 样式细节 / 交互 / 四种状态（正常/空/加载/错误）/ 字段映射引用
3. 紧凑表 widget（MarketBreakout）遵循 `v1.1 · Workbench` 下的「Widget 紧凑表通用规格」小节，无需重复规则，引用即可
4. 若设计稿缺失，在章节开头标注"❌ 无原始 Figma，按代码现状反向文档化"

**不包含**：v1.0 已有 spec 的 SignalCard（已在 2026-04-22 加了实现偏离）、TopNav、MarketOverview。

**入口命令**：用户说"补齐 widget spec" 或直接读取本条（T-001）即可进入该任务。
