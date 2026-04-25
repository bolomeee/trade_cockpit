# SESSION HANDOFF

> 生成时间：2026-04-25
> 当前阶段：F201-c Sprint Contract 已确认 → 待开新 session 进 Generator 模式
> 当前 branch：cockpit

---

## 本 session 完成的事

1. **发现 v1.0 遗漏**：F201 历史拆分中，前端 MarketRegimeWidget 从未实现，但 design-spec / data-mapping 都已经基于它描绘。
2. **拆分 F209**：原 F209（≥9 文件）违反 6 文件原则，拆为 F209-a（后端 schema）/ F209-b（Market Narrator 前端）/ F209-c（Setup Explainer popover）。
3. **新增 F201-c**：补齐 MarketRegimeWidget 前端实现，作为 F209-b 的前置。
4. **F201-c Sprint Contract 已确认**（用户全部 D1/D2/D3 同意）。

---

## features.json 当前状态

| Feature | Phase | Files | 依赖 |
|---------|-------|-------|------|
| **F201-c** | 📝 contract_agreed | 5 | F201-b |
| F209-a | ⬜ design_ready | 4 | F208-c |
| F209-b | ⬜ design_ready | 4 | F209-a + F201-c |
| F209-c | ⬜ design_ready | 3 | F209-a + F209-b + F202-c |

开发顺序：**F201-c → F209-a → F209-b → F209-c**（串行）

---

## F201-c Sprint Contract 摘要

**契约文件**：`docs/开发/sprint-contracts/F201-c-contract.md`

### 实现范围
- API client：`cockpitRegimeApi.ts`（GET /api/cockpit/regime）
- MarketRegimeWidget shell + 4 区块：
  - Score Hero（regime pill + marketScore + Allowed/Risk）
  - 6-dim Subscores（2×3 网格 + 进度条）
  - Indices Card（SPY/QQQ/IWM 3 行）
  - Sector Heatmap（11 ETF 3×4 网格）
- 4 种状态：正常 / 空（404）/ 加载（Skeleton）/ 错误（502 重试）
- CockpitRegistry：删 `cockpit.placeholder`，加 `cockpit.market-regime`
- 单元/集成测试

### 不做
- AI Market Notes（→ F209-b）
- Score Hero 浮层 / Sector 联动 / Index 联动（→ v1.9）

### 文件清单（5 个）
1. 新建 `frontend/src/cockpit/lib/api/cockpitRegimeApi.ts`
2. 新建 `frontend/src/cockpit/widgets/MarketRegimeWidget.tsx`
3. 修改 `frontend/src/cockpit/CockpitRegistry.ts`
4. 新建 `frontend/src/cockpit/widgets/__tests__/MarketRegimeWidget.test.tsx`
5. 修改 `frontend/src/cockpit/lib/api/__tests__/cockpitApis.test.ts`

### 已确认决策
- **D1 颜色 token**：sector/index state 复用 `--color-regime-*` 系列（不新增 token），具体映射表见 contract
- **D2 EmptyState**：404 不带 [手动触发] 按钮，POST recompute endpoint 未定义
- **D3 Subscore 满分**：硬编码常量 `SUBSCORE_MAX`，API 不返回 max

完成后将 D1 追加为 DXXX 到 DECISIONS.md。

---

## 开发顺序（Generator 模式逐步执行）

```
1. ✅ Sprint Contract 确认（已完成）
2. cockpitRegimeApi.ts 类型 + 函数 + 集成测试 → wip commit
3. CockpitRegistry.ts 修改（删 placeholder，加 market-regime）+ 注册测试 → wip commit
4. MarketRegimeWidget.tsx Score Hero + 子组件骨架（先静态数据） → wip commit
5. Subscores 网格 + Indices Card + Sector Heatmap → wip commit
6. 4 种状态（loading / error / empty / 正常）+ 单元测试 → wip commit
7. Evaluator 模式：跑全套测试 + pnpm build + 自检清单 → 通过后最终 commit
```

---

## 关键文档锚点

- API 字段权威：API-CONTRACT.md line 968-1023（GET /api/cockpit/regime）
- 视觉规格：design-spec.md line 768-832（Widget 1 wireframe + 4 状态表）
- 字段映射：data-mapping.md §Cockpit-1（1.a / 1.b / 1.c / 1.d）
- 颜色 token：frontend/src/styles/tokens.css（`--color-regime-*` line 72-76）
- 既有同类参考：DecisionPanelWidget.tsx / SetupMonitorWidget.tsx（structure / 测试风格）
- API client 参考：cockpitDecisionApi.ts（apiFetch 用法 + 类型定义风格）

---

## ⚠️ Generator 模式启动前必读

1. **6 文件不得超出**：5 个文件已是上限，若开发中发现需要新增第 6+ 个文件，必须停下报告。
2. **WIP commit 铁律**：每完成一步且通过最小验证，立即 `git add <具体文件>` + `git commit -m "wip(F201-c): ..."`。**禁用 `git add -A`**。
3. **颜色严禁硬编码**：所有颜色 / 字体 / 间距走 tokens.css CSS 变量。
4. **D060 合规**：cockpit/ 内不得引用 workbench/。
5. **API 字段命名**：camelCase（marketScore / allowedExposurePct / singleTradeRiskPct / aboveMa50 / aboveMa200 / rsTrend / changePct / preferredSetups / avoidSetups / computedAt）。

---

## 下一 Session 启动指令

**建议用 Sonnet 开新 session**（Generator 模式不需要 Opus 的高判断力，Sonnet 更经济），粘贴：

```
继续开发 F201-c，Sprint Contract 已确认。
读取 SESSION-HANDOFF.md + docs/开发/sprint-contracts/F201-c-contract.md，
进入 Generator 模式，从开发步骤 2（cockpitRegimeApi.ts）开始。
```

---

## git 状态

branch：cockpit

本 session 待提交（chore commit，跨 sprint 杂项）：
- M  `docs/需求/features.json`（F209 拆分 + 新增 F201-c）
- A  `docs/开发/sprint-contracts/F201-c-contract.md`
- M  `claude-progress.txt`
- M  `SESSION-HANDOFF.md`
- D  `backend/.env.example`（早先已删除，本次顺带提交）

最近 commits（F208 完成）：
- f051313 chore(F208-c): 验收通过 → done
- 82026f8 chore(F208-c): Evaluator 通过 → needs_review + D072 cost fix
- 862cee6 wip(F208-c): AiGateway main flow + LiteLLM lazy import + /api/ai/{task_type} endpoint
