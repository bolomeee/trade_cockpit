# SESSION-HANDOFF — F219-b 完成 → F219 needs_review

> 生成：2026-05-21 (Sonnet 4.6) | 用途：下一 session 进入 acceptance 阶段
> 触发：F219-b Evaluator 通过，F219 整体升 needs_review

---

## 1. 当前状态

| 字段 | 值 |
|------|-----|
| `F219.phase` | **needs_review** |
| `F219.sub_sprints["F219-a"]` | done（后端：indicator + persist + endpoint schema） |
| `F219.sub_sprints["F219-b"]` | done（前端：PositionList ⚠️ + SetupMonitor MACD+ chip） |
| `_pipeline_status.active_sprint` | null |
| 最新 commit | `9637300 feat(F219-b): MACD divergence 前端 ⚠️ + MACD+ chip 切片` |

---

## 2. F219-b 完成内容（本 session）

**改动 6 文件**：

| 文件 | 改动 |
|------|------|
| `frontend/src/cockpit/lib/api/setupMonitorApi.ts` | 新增 `export type MacdDivergence`；`SetupItem` 加 `macdDivergence` 字段 |
| `frontend/src/cockpit/lib/api/cockpitPositionsApi.ts` | import `MacdDivergence`；`Position` 加 `macdDivergence` 字段 |
| `frontend/src/cockpit/widgets/_positionListRow.tsx` | `PositionRow` ticker cell 注入 ⚠️ span（OPEN + bearish） |
| `frontend/src/cockpit/widgets/SetupMonitorWidget.tsx` | Setup 列 inline-flex + CAPITULATION+bullish 渲染 'MACD+' chip |
| `frontend/src/cockpit/widgets/__tests__/PositionListWidget.test.tsx` | fixture 加 `macdDivergence: null`；新增 S14-1~3（3/3 全绿） |
| `frontend/src/cockpit/widgets/__tests__/SetupMonitorWidget.test.tsx` | fixture 加 `macdDivergence: null`；新增 M1~3（3/3 全绿） |

**文档同步（Evaluator 阶段）**：
- `docs/设计/design-spec.md` — 新增 §F219-b MACD Divergence 视觉规格段落
- `docs/设计/data-mapping.md` — 新增 macdDivergence 字段映射表
- `docs/系统设计/DECISIONS.md` — 新增 D102（不抽 MacdDivergenceBadge）+ D103（触发收紧 NP-3）
- `docs/需求/features.json` — F219-b: done；F219.phase: needs_review；追加 needs_review iteration_history

**Evaluator 结果**：
- `pnpm tsc --noEmit` 零错误
- 新增测试 6 个全绿（S14-1~3 + M1~3）
- 全量回归：37 failed | 330 passed（与 F219-b 改动前基线完全一致，零新增失败）

---

## 3. 未提交改动（遗留）

```
M backend/uv.lock      ← F219-a 遗留，与前端无关（可在 acceptance 后与发版一起处理）
M claude-progress.txt  ← 本 session 协商记录
```

---

## 4. 下一步：acceptance skill

F219 phase = `needs_review` → 触发 acceptance。

**验收清单（合同 §4）**：

| # | 验收标准 | 方法 |
|---|---------|------|
| 1 | `pnpm dev` 启动，PositionList 中 OPEN+bearish 持仓 ticker 后出现 ⚠️ | 真机 EOD 后观察 |
| 2 | hover ⚠️ → tooltip 显示 'bearish divergence detected, consider partial exit at 2R' | 真机 |
| 3 | CLOSED 持仓 bearish 行无 ⚠️ | 真机 |
| 4 | SetupMonitor CAPITULATION+bullish 行 Setup 列 SetupTypeBadge 右侧出现绿色 'MACD+' | 真机 EOD |
| 5 | non-CAPITULATION 行无 'MACD+' | 真机 |
| 6 | Ready / Near filter tab 数字与添加 macdDivergence 字段前一致 | 单元测试 M3 已覆盖 |

**前提**：EOD 跑完后 `setup_snapshots.macd_divergence` 有非 null 数据，才能看到真实渲染。

---

## 5. Pre-existing test failures（不阻塞）

以下失败是 F219-b 之前已存在，本切片未引入：
- `SetupMonitorWidget.test.tsx` §R-R11（ai-rank-close testid 已移除）
- `SetupMonitorWidget.test.tsx` §S 系列（AiSetupExplainerPopover ? button testid 问题）
- `TopNav.test.tsx` S12/S13（TooltipProvider 缺失）

---

## 6. 下一 session 恢复指令

```
F219 phase = needs_review，F219-b 已完成（前端 ⚠️ + MACD+ chip，6 文件）。
触发 acceptance skill，验收 F219 整体（含后端 EOD 实际落数据 + 两个 widget 真机渲染）。
```
