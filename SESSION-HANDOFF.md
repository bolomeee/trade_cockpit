# SESSION-HANDOFF — F206-c1 Done

> 生成：2026-04-26 | 阶段：done
> 当前 active sprint：**F206-c2 PendingOrdersWidget**（下一个）

---

## 已完成内容（本 session）

### F206-c1 PositionListWidget — 完成

**新建文件（生产）：**
- `frontend/src/cockpit/lib/api/cockpitPositionsApi.ts` — 4 endpoint client + TS types（Position / PositionSummary / GetPositionsResponse / PositionInput / PositionPatch）
- `frontend/src/cockpit/widgets/PositionListWidget.tsx` — 主 widget（状态过滤 + summary 顶条 + 表格 + 对话框触发）
- `frontend/src/cockpit/widgets/_positionListRow.tsx` — 拆分子组件（RiskSummaryBar / InlineEditRow / PositionRow，因 350 行限制）
- `frontend/src/cockpit/dialogs/PositionFormDialog.tsx` — new/edit 双模式表单（react-hook-form v7 + zod v4）
- `frontend/src/cockpit/dialogs/_positionFormSchemas.ts` — zod schemas 拆分（因 350 行限制）

**新建文件（测试）：**
- `frontend/src/cockpit/lib/api/__tests__/cockpitPositionsApi.test.ts` — S1–S4（12 tests）
- `frontend/src/cockpit/widgets/__tests__/PositionListWidget.test.tsx` — S5–S13（15 tests）
- `frontend/src/cockpit/dialogs/__tests__/PositionFormDialog.test.tsx` — S14–S17（10 tests）

**修改文件：**
- `frontend/src/cockpit/CockpitRegistry.ts` — 注册 `cockpit.position-list` manifest
- `frontend/src/cockpit/__tests__/CockpitRegistry.test.ts` — S18 tests（3 tests）
- `docs/设计/design-spec.md` §1057 — nextAction 设计偏离回写
- `docs/系统设计/DECISIONS.md` — D076 设计偏离决策
- `frontend/src/cockpit/components/AiSetupExplainerPopover.tsx` — 修复 TS1355（`as const` on conditional → 显式类型）
- `docs/需求/features.json` — F206-c1 phase: done，active_sprint → F206-c2
- `claude-progress.txt` — 进度追加

**关键技术决策：**
- Zod v4：`invalid_type_error` → `error`（breaking change，影响 number schema）
- target2r/target3r 用 `setValueAs` 而非 `valueAsNumber`，避免 NaN 阻断 superRefine
- FilterBtn 必须在 component 外定义（ESLint react-refresh/only-export-components）
- 非组件 helpers（fmt2 等）从 _positionListRow.tsx 移除 export（同一规则）
- `form.watch()` 用 local useState 替代（react-hooks/incompatible-library）

**测试结果：**
- S1–S18 全过，160/160 tests pass
- lint: 新建/修改文件零 warning/error（存量 lint errors 均为 pre-existing）
- build: `pnpm -C frontend run build` ✅

---

## 当前状态

| 项 | 值 |
|---|---|
| Feature | F206 Position Manager |
| Sprint | F206-c1 ✅ done |
| 下一 Sprint | F206-c2 PendingOrdersWidget（需起草 contract） |
| 后端依赖 | `/api/cockpit/pending-orders` 4 endpoint 已上线（F206-b1 ✅） |

---

## 下一步任务（F206-c2）

F206-c2 = PendingOrdersWidget 前端，镜像 c1 结构：

**预计文件：**
1. `cockpitPendingOrdersApi.ts` — 4 endpoint client（GET/POST/PATCH/DELETE /api/cockpit/pending-orders）
2. `PendingOrdersWidget.tsx` + `_pendingOrdersRow.tsx`（若超 350 行则拆）
3. `PendingOrderFormDialog.tsx` + `_pendingOrderFormSchemas.ts`（若需要）
4. `CockpitRegistry.ts` 新增 `cockpit.pending-orders` manifest

**关键字段（来自 API-CONTRACT §pending-orders）：**
- PendingOrder: id / ticker / setupType / entryPrice / stopPrice / shares / riskPct / expiresAt / status / distanceToTriggerPct / createdAt / updatedAt
- Status 枚举：ACTIVE / TRIGGERED / CANCELLED / EXPIRED
- GET response 不含 summary（与 positions 不同）

**注意：**
- F206-c1 测试文件命名规范：`__tests__/XxxWidget.test.tsx`（RTL + msw）
- EarningsRiskDot 不适用于 PendingOrders（无 earnings 字段）
- distanceToTriggerPct 可能需要自定义格式化

---

## 未决事项

- 存量 ESLint errors（8 个 pre-existing，不在 F206-c1 范围）：
  - `aiApi.test.ts`: beforeEach unused
  - `MarketRegimeWidget.tsx`: Date.now() impure
  - `AddStockCard.tsx` / `CsvImportDialog.tsx`: setState in effect（4 errors）
  - `JournalEntryForm.tsx`: form.watch incompatible-library warning
  - `button-group.tsx` / `button.tsx` / `toggle.tsx`: only-export-components（shadcn ui files）
  - 建议：开专项 session 修复，不混入 feature session

---

## 恢复指令

```
继续开发 F206-c2 PendingOrdersWidget。
读取 SESSION-HANDOFF.md + API-CONTRACT.md §pending-orders + design-spec.md §Widget 8，
起草 F206-c2 Sprint Contract，用户确认后进入 Generator 模式。
```
