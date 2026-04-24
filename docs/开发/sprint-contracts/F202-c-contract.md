# Sprint Contract：F202-c Setup Monitor 前端 Widget

> 状态：contract_agreed | 日期：2026-04-25

---

## 实现范围

**包含**：
- 3 个共享子组件（SetupTypeBadge / SetupQualityBadge / EarningsRiskDot）
- API client（setupMonitorApi.ts）
- SetupMonitorWidget（Filter Tabs + 行表 + ready 左侧高亮 + 行点击联动 cockpitStore）
- CockpitRegistry.ts 注册 SetupMonitorWidget（与 PlaceholderWidget 共存）

**不包含（v2.0）**：
- `[?]` hover 调 `POST /api/ai/setup_explainer`
- 行展开（target2r / target3r / trendScore 扩展列）

---

## 预计修改文件（共 6 个）

| # | 文件 | 类型 |
|---|------|------|
| 1 | `frontend/src/cockpit/components/SetupTypeBadge.tsx` | 新建 |
| 2 | `frontend/src/cockpit/components/SetupQualityBadge.tsx` | 新建 |
| 3 | `frontend/src/cockpit/components/EarningsRiskDot.tsx` | 新建 |
| 4 | `frontend/src/cockpit/lib/api/setupMonitorApi.ts` | 新建 |
| 5 | `frontend/src/cockpit/widgets/SetupMonitorWidget.tsx` | 新建 |
| 6 | `frontend/src/cockpit/CockpitRegistry.ts` | 修改：注册 SetupMonitorWidget |

---

## 完成标准

| # | 测试描述 | 层级 |
|---|---------|------|
| S1 | SetupTypeBadge BREAKOUT/PULLBACK/RECLAIM/EARNINGS_DRIFT/EXTENDED/BROKEN 渲染对应 token 颜色；NONE 渲染 "—" | 视觉 |
| S2 | SetupQualityBadge A/B/C 渲染对应颜色；null 渲染 "—" | 视觉 |
| S3 | EarningsRiskDot SAFE/CAUTION/DANGER 渲染对应颜色；DANGER 显示 "D-N" 数字 | 视觉 |
| S4 | Widget 初始 "All" tab，调用无 filter 参数的接口 | E2E |
| S5 | 切 "Ready" tab → 请求带 `?filter=ready`，列表只含 readySignal=true 的行 | E2E |
| S6 | readySignal=true 的行左侧有蓝色 `▍` 高亮条 | 视觉 |
| S7 | 行点击 → cockpitStore.selectedTicker 更新 | 单元/E2E |
| S8 | isLoading 时显示 skeleton/loading 状态；isError 显示错误文字 | E2E |
| S9 | CockpitRegistry 注册了 `cockpit.setup-monitor` manifest | 代码检查 |
| S10 | `pnpm build` 零 error；ESLint 无新增 warning | 构建 |

---

## Evaluator 自检清单

- [ ] 所有颜色只使用 `tokens.css` 的 CSS 变量，无 hex 硬编码
- [ ] 字段名与 API-CONTRACT §setup-monitor 100% 一致（特别是 `target2r`/`target3r` 无下划线）
- [ ] D060 合规：cockpit/ 内无任何 workbench/ 引用
- [ ] PlaceholderWidget 仍在 Registry 中（不被替换，共存）
- [ ] pnpm build 零 error
- [ ] 无 console.log 遗留
