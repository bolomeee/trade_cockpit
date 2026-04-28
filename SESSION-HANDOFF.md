# SESSION-HANDOFF — F206-c2 PendingOrdersWidget

> 生成时间：2026-04-28 | Branch: cockpit | 阶段：Contract 协商完成 → 待 Generator

---

## 已完成（本 Session）

**F206-c2 Sprint Contract 协商 + drift 修复**

1. 用户确认合约 §7 6 项（D060-a + 5 项实现细节）
2. 合约 [`docs/开发/sprint-contracts/F206-c2-contract.md`](docs/开发/sprint-contracts/F206-c2-contract.md) frontmatter: drafted → confirmed
3. 修正 features.json 的 F206 status drift：之前错标 done/2026-04-26，实际 c2 未做即跳 F207
   - F206 status → `in_progress`，phase → `contract_agreed`
   - active_sub_sprint = `F206-c2`
   - sub_sprints 字段化（a/b1/b2/c1=done，c2=contract_agreed）
   - 追加 `_status_drift_note` 留痕
   - iteration_history 追加 c2 contract_agreed 记录
4. 顶层 `_pipeline_status.active_sprint` → `F206-c2` / phase → `contract_agreed`
5. claude-progress.txt 追加本次记录

---

## 已确认决策（Generator 阶段需落地到 DECISIONS.md）

| ID | 决策 |
|----|------|
| **D060-a** | v1.9 PendingOrder `[Triggered]` 后**不**自动创建 Position，仅切 status + toast 提示用户去 Positions widget 手工录入。理由：避免 backend 联动事务复杂度，v1.9 选择手工二次录入。后续如反馈痛点可开 F206-d 或并入 F207 ActionList |
| — | distance 颜色按**绝对值**阈值：`|x|>5%` 灰（`--color-text-muted`）/ `1≤|x|≤5` 默认 / `|x|<1` 加粗（`font-bold`） |
| — | Edit dialog **不**暴露 status 字段；status 转换只走行按钮 `[Triggered]/[Cancel]`，避免双入口 |
| — | `[Cancel]` 直接 PATCH 无确认（reversible）；`[Triggered]` 弹 AlertDialog + toast 引导 |
| — | defaultLayout `{ x: 6, y: 8, w: 6, h: 8, minW: 4, minH: 6 }`（与 c1 PositionList 同行右侧） |
| — | category 复用 `'position'`，不新增 `'order'`（避免改 `CockpitWidgetCategory` union） |

---

## 当前状态

- Branch: `cockpit`，工作区 clean
- 系统设计文档：ARCHITECTURE / DATA-MODEL / API-CONTRACT / design-spec / component-plan 均 confirmed
- features.json `active_sprint` = `F206-c2`，phase = `contract_agreed`
- F207 在 drift 期间已完成（done），F206-c2 是 v1.9 真正的收尾

---

## 下一步任务（下一 Session）

### 立即执行：Generator 模式

```
继续开发 F206-c2，Sprint Contract 已确认。
读取 SESSION-HANDOFF.md + docs/开发/sprint-contracts/F206-c2-contract.md，
进入 Generator 模式，从开发步骤 1 开始。
```

### Generator 开发顺序（合约 §5）

| Step | 内容 | WIP commit message |
|------|------|---------------------|
| 1 | `cockpitPendingOrdersApi.ts` + 单测 → vitest 通过 | `wip(F206-c2): cockpitPendingOrdersApi` |
| 2 | `_pendingOrderFormSchemas.ts` + `PendingOrderFormDialog.tsx` + 测试 | `wip(F206-c2): PendingOrderFormDialog` |
| 3 | `_pendingOrderRow.tsx` + 单测（distance 颜色 3 档 + 按钮可见性） | `wip(F206-c2): _pendingOrderRow` |
| 4 | `PendingOrdersWidget.tsx` + 测试 | `wip(F206-c2): PendingOrdersWidget` |
| 5 | `CockpitRegistry.ts` 注册 manifest + DECISIONS.md 追加 D060-a + design-spec.md §Widget 8 链接回写 | `wip(F206-c2): registry + 决策回写` |
| 6 | lint + test + build → Evaluator S1–S20 | 最终 `feat(F206-c2): PendingOrdersWidget + PendingOrderFormDialog`（封 F206 收尾） |

### Evaluator 验收（合约 §3 / §4）

- S1–S20 全部通过
- 文件 ≤ 6 生产文件 + 3 测试文件
- 字段命名严格对照 API-CONTRACT.md §Pending Orders（camelCase）
- distance 颜色 3 档按绝对值
- 仅 ACTIVE 行渲染 `[Triggered][Cancel]`
- queryKey `['cockpit-pending-orders', status]`，staleTime 30s
- 不 invalidate `['cockpit-positions']`
- DECISIONS.md D060-a 已落地
- 全量回归 `pnpm -C frontend test` + lint + build 全通过

---

## 未决事项

| # | 事项 | 影响 |
|---|------|------|
| 1 | F207 在 F206-c2 之前完成（drift 期间） | F207 ActionList 在缺少 PendingOrdersWidget 的情况下做出来了；需在 F206-c2 完成后回归测试 ActionList 显示 pending_orders 是否仍正常 |
| 2 | D060-a 落地后续观察 | 用户使用一段时间后，若手工双录痛点明显，再开 F206-d 或并入 F207 |

---

## 恢复 Checklist（下次 Session 必读）

- [ ] 读 [`docs/开发/sprint-contracts/F206-c2-contract.md`](docs/开发/sprint-contracts/F206-c2-contract.md) 全文
- [ ] 读 [`docs/系统设计/API-CONTRACT.md`](docs/系统设计/API-CONTRACT.md) §Pending Orders（GET/POST/PATCH/DELETE）
- [ ] 读 [`docs/系统设计/DATA-MODEL.md`](docs/系统设计/DATA-MODEL.md) §Entity: PendingOrder
- [ ] 读 [`docs/设计/design-spec.md`](docs/设计/design-spec.md) §Widget 8 PendingOrdersWidget
- [ ] 读 [`docs/设计/component-plan.md`](docs/设计/component-plan.md) §PendingOrdersWidget / §PendingOrderFormDialog / §Cockpit-4 react-query / §Cockpit-5 目录
- [ ] 参考代码：[`frontend/src/cockpit/widgets/PositionListWidget.tsx`](frontend/src/cockpit/widgets/PositionListWidget.tsx)（c1 实现，c2 风格基线）
- [ ] 参考代码：[`frontend/src/cockpit/lib/api/cockpitPositionsApi.ts`](frontend/src/cockpit/lib/api/cockpitPositionsApi.ts)（c1 api client 模式）
- [ ] 检查后端口径：`backend/app/services/cockpit/pending_order_service.py::_enrich`（distance/risk）
- [ ] 确认 `SetupTypeBadge` 共享组件位置（c2 行渲染要复用）
- [ ] 进入 Generator 模式，从 Step 1 开始
