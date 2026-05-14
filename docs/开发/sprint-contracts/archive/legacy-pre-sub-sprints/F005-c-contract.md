# F005-c Sprint Contract

> 创建：2026-04-17 | 状态：confirmed

## 范围
包含：lightweight-charts 依赖引入、PriceChart 组件（Candles + MA150 + Pullback markers）、Modal 接入 chart 查询。
排除：marker hover 交互（P2）、时段切换、深色主题。

## 预计修改文件（5）
- frontend/package.json
- frontend/pnpm-lock.yaml
- frontend/src/components/features/stock-detail/PriceChart.tsx（新建）
- frontend/src/components/features/stock-detail/StockDetailModal.tsx
- docs/系统设计/DECISIONS.md

## 新依赖
- lightweight-charts v5.1.0（TradingView 官方）。API 来源：context7 `/tradingview/lightweight-charts`。

## 完成标准
| # | 测试 | 层级 |
|---|------|------|
| 1 | pnpm build 通过 | 类型 |
| 2 | pnpm lint 无新增警告 | 静态 |
| 3 | Modal 打开渲染 Candles + MA150，无 console error | 浏览器 |
| 4 | Pullback markers 在对应日期显示向下三角（--color-signal-buyzone） | 浏览器 |
| 5 | 关闭再打开不同股票，chart 正确销毁重建 | 浏览器 |
| 6 | Loading/Error/短周期(<150 日) 状态处理正确 | 浏览器 |
| 7 | 颜色/尺寸用 tokens，无硬编码 | 审查 |
| 8 | 回归：F003 Dashboard / F002 watchlist 正常 | 浏览器 |

## 自检清单
- [ ] pnpm build 通过
- [ ] pnpm lint 无新增警告
- [ ] useEffect cleanup 调用 chart.remove()
- [ ] tokens.css 变量，无硬编码
- [ ] 无 console.error
- [ ] DECISIONS.md 追加记录
- [ ] features.json F005-c.phase → needs_review
