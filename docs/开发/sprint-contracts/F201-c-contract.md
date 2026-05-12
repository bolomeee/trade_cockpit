# Sprint Contract：F201-c Market Regime 前端 Widget

> 状态：草案 | 日期：2026-04-25
> 引用文档：
>   API-CONTRACT.md §GET /api/cockpit/regime（line 968-1023）
>   DATA-MODEL.md §Entity: MarketIndex / MarketRegimeSnapshot
>   design-spec.md §Widget 1：MarketRegimeWidget（line 768-832）
>   data-mapping.md §Cockpit-1（1.a / 1.b / 1.c / 1.d）
>   features.json#F201-c

---

## 实现范围

**包含**：
- API client：`cockpitRegimeApi.ts`（getCockpitRegime() → CockpitRegimeData）
- MarketRegimeWidget shell + 4 个区块：
  - **Score Hero**：regime pill + marketScore + allowedExposurePct + singleTradeRiskPct
  - **6-dim Subscores**：2×3 网格（spyTrend / qqqTrend / iwmBreadth / sectorParticipation / riskAppetite / volatilityStress），每格含数值 + 进度条
  - **Indices Card**：3 行 SPY/QQQ/IWM（close / changePct / aboveMa50 / aboveMa200 / rsTrend / state）
  - **Sector Heatmap**：11 ETF 的 3×4 网格（按 state 着色，悬浮 tooltip 显示 close + changePct）
- 4 种状态：正常 / 空（404 EmptyState）/ 加载（Skeleton）/ 错误（502 重试）
- CockpitRegistry：将 `cockpit.placeholder` 替换为 `cockpit.market-regime`（删除 PlaceholderWidget 注册项；保留 `PlaceholderWidget.tsx` 文件不删，以备将来未填槽位使用）
- 单元/集成测试覆盖 4 种状态 + 字段渲染 + Registry manifest

**明确排除（本次不做，留给 F209-b）**：
- AI Market Notes 区域（headline / summary / warnings / Refresh button） — F209-b
- Score Hero 点击展开浮层（6 子项详细计算依据） — v1.9 增强
- Sector 单元格点击 → SetupMonitor 应用 sector 过滤 — v1.9 增强
- Index 行点击 → setSelectedTicker 联动 — v1.9 增强
- 整 widget 顶部 Refresh 按钮（手动刷新接口） — 当前由 react-query staleTime 自动管理

---

## 预计修改文件（共 5 个，符合 6 文件原则）

| # | 文件路径 | 改动类型 | 说明 |
|---|---------|---------|------|
| 1 | `frontend/src/cockpit/lib/api/cockpitRegimeApi.ts` | 新建 | 封装 GET /api/cockpit/regime，导出 CockpitRegimeData 类型（与 API-CONTRACT 字段一一对应） |
| 2 | `frontend/src/cockpit/widgets/MarketRegimeWidget.tsx` | 新建 | Widget shell + 4 区块组件（内部子组件） |
| 3 | `frontend/src/cockpit/CockpitRegistry.ts` | 修改 | 删 `cockpit.placeholder` 注册项，新增 `cockpit.market-regime`（同位 `{x:0,y:0,w:4,h:8,minW:3,minH:4}`，category=`regime`） |
| 4 | `frontend/src/cockpit/widgets/__tests__/MarketRegimeWidget.test.tsx` | 新建 | 4 种状态 + 字段渲染单元测试（vitest + RTL） |
| 5 | `frontend/src/cockpit/lib/api/__tests__/cockpitApis.test.ts` | 修改 | 追加 `describe('S3 – cockpitRegimeApi', ...)` 块，含 OK / 404 / 502 三场景 |

⚠️ **不动**：
- `PlaceholderWidget.tsx`（保留文件，仅从 registry 移除）
- 后端任何文件（GET /api/cockpit/regime 在 F201-b 已交付）
- 其他 widget 文件
- DATA-MODEL.md / API-CONTRACT.md（无需变更）

---

## 关键技术决策（需用户确认）

### D1：颜色 token 映射（design-spec 未定义独立 sector/index state token）

`tokens.css` 当前只有 `--color-regime-*` 系列，没有 `--color-state-strong / --color-state-weak`。design-spec line 800-803 描述 sector heatmap "Strong=绿、Constructive=浅绿、Weak=橙、Defensive=红"，需要约定 token 复用规则：

| 维度 | enum 值 | 复用 token |
|------|--------|-----------|
| Sector state | Strong | `--color-regime-risk-on` (#10b981 绿) |
| Sector state | Constructive | `--color-regime-constructive` (#22c55e 浅绿) |
| Sector state | Weak | `--color-regime-defensive` (#f59e0b 橙) |
| Sector state | Defensive | `--color-regime-risk-off` (#ef4444 红) |
| Sector state | Neutral（占位用） | `--color-regime-neutral` (灰) |
| Index state | Bullish / Leading | `--color-regime-risk-on` |
| Index state | Constructive | `--color-regime-constructive` |
| Index state | Neutral | `--color-regime-neutral` |
| Index state | Weak | `--color-regime-defensive` |
| Index state | Defensive | `--color-regime-risk-off` |
| Subscore 进度条 | ≥80% / ≥60% / ≥40% / ≥20% / <20% | risk-on / constructive / log-warn / regime-defensive / regime-risk-off |

完成后将本表追加为 **DXXX：Cockpit Widget 1 颜色 token 映射** 到 DECISIONS.md。

### D2：404 EmptyState 文案

design-spec line 829："首日 regime 计算中，明日开盘后可见"，按钮 "[手动触发]" 调 `POST /api/cockpit/regime/recompute`。

⚠️ 该 POST endpoint **API-CONTRACT.md 中未定义**（搜索结果为空）。本 sprint **不实现该按钮**，EmptyState 仅显示文案，不带按钮。如果未来需要，由独立 sprint 补 POST 接口 + 按钮。

### D3：Subscore 满分参考来源

data-mapping.md 1.b 列出 6 个子项的"满分":
- spyTrend / 25
- qqqTrend / 20
- iwmBreadth / 15
- sectorParticipation / 20
- riskAppetite / 10
- volatilityStress / 10

**总和 = 100**，与 marketScore 0-100 一致。本 sprint 在 `MarketRegimeWidget.tsx` 中将这 6 个满分值定义为模块常量 `SUBSCORE_MAX`，不读 API（API 不返回 max）。

---

## 可测试的完成标准

| # | 标准描述 | 层级 | 工具 |
|---|---------|------|------|
| S1 | `cockpitRegimeApi.getCockpitRegime()` 调用 `/api/cockpit/regime`，OK 时返回完整 CockpitRegimeData 对象 | 集成 | vitest + fetch stub |
| S2 | API 返回 404 时抛 ApiError(NOT_FOUND)；502 时抛 ApiError(http=502) | 集成 | vitest |
| S3 | MarketRegimeWidget 正常态：Score Hero 渲染 regime pill（颜色按 D1 映射）+ score "{n} / 100" + Allowed/Risk 两行 | 单元 | RTL |
| S4 | 6-dim Subscores 渲染 6 个卡片，文本格式 `{label} {n} / {max}`，进度条宽度 = `n / max * 100%`，颜色按 D1 进度条规则 | 单元 | RTL |
| S5 | Indices Card 渲染 3 行：symbol / `$close`(2 dec) / `±changePct%`(2 dec, 涨绿跌红) / 50MA✓✗ / 200MA✓✗ / RS 箭头 / state 文本 | 单元 | RTL |
| S6 | Sector Heatmap 渲染 11 cells（XLK/XLY/XLF/XLI/XLE/XLV/XLC/XLP/XLU/XLB/XLRE 顺序），每 cell 背景按 state 着色，hover 显示 tooltip "close $X.XX, changePct ±X.XX%" | 单元 | RTL |
| S7 | Sector 数据 close=null 时 cell 显示 "—"，state="Neutral" 灰色，不抛错 | 单元 | RTL |
| S8 | 加载态：Score Hero / Subscores / Indices / Sectors 全部渲染 Skeleton | 单元 | RTL |
| S9 | 404 错误态：渲染 EmptyState 文字 "首日 regime 计算中，明日开盘后可见"，无 [手动触发] 按钮（D2） | 单元 | RTL |
| S10 | 502 错误态：渲染 "[加载失败，重试]"（点击重新触发 react-query refetch） | 单元 | RTL |
| S11 | CockpitRegistry 中存在 `cockpit.market-regime` manifest（id / title / component / defaultLayout / category=regime），不存在 `cockpit.placeholder` | 单元 | vitest |
| S12 | `getCockpitDefaultLayout()` 返回数组中含 `i: 'cockpit.market-regime'` 项，不含 `cockpit.placeholder` | 单元 | vitest |
| S13 | 整 widget 渲染时无 console.error / console.warn | 单元 | vitest（vi.spyOn console） |
| S14 | `pnpm build` 零 error；`pnpm lint`（若已配置）无新增 warning | 构建 | pnpm |

---

## Evaluator 自检清单

开发完成后逐条检查：

- [ ] 单元测试全部通过（`pnpm test`）
- [ ] 集成测试全部通过（fetch stub 的 OK / 404 / 502 三场景）
- [ ] 4 种状态人工对照 design-spec.md line 826-831 表格逐条匹配
- [ ] 字段名与 API-CONTRACT §GET /api/cockpit/regime 100% 一致（camelCase: marketScore / allowedExposurePct / singleTradeRiskPct / aboveMa50 / aboveMa200 / rsTrend / changePct / preferredSetups / avoidSetups / computedAt）
- [ ] 所有颜色 / 字体 / 间距只使用 tokens.css 的 CSS 变量，**无 hex 硬编码**
- [ ] D060 合规：`cockpit/` 内无任何 `workbench/` 引用
- [ ] CockpitRegistry 中 `cockpit.placeholder` 已删，`cockpit.market-regime` 已注册
- [ ] PlaceholderWidget.tsx 文件保留（不删）
- [ ] DECISIONS.md 已追加 DXXX（颜色 token 映射）
- [ ] `pnpm build` 零 error
- [ ] 无 console.log / console.error 遗留
- [ ] 全量回归测试通过：现有 CockpitChartWidget / DecisionPanelWidget / SetupMonitorWidget 测试无回归

---

## 开发顺序（Generator 模式逐步执行）

1. ✅ Sprint Contract 确认（本步骤）
2. cockpitRegimeApi.ts 类型 + 函数 + 集成测试 → wip commit
3. CockpitRegistry.ts 修改（删 placeholder，加 market-regime） + 注册测试 → wip commit
4. MarketRegimeWidget.tsx Score Hero + 子组件骨架（先静态数据） → wip commit
5. Subscores 网格 + Indices Card + Sector Heatmap → wip commit
6. 4 种状态（loading / error / empty / 正常）+ 单元测试 → wip commit
7. Evaluator 模式：跑全套测试 + pnpm build + 自检清单 → 通过后最终 commit

---

👤 用户确认本 Contract 后，按 skill 流程：
- 更新 features.json F201-c phase → `contract_agreed`
- 更新 claude-progress.txt
- 生成 SESSION-HANDOFF.md
- **停止本 session，建议开新 session 用 Sonnet 进入 Generator 模式**
