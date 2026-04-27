# SESSION-HANDOFF

> 更新：2026-04-27 PM | 阶段：F205-d Sprint Contract ✅ 已确认 → Generator 待启动
> 项目：MA150 Tracker → Cockpit
> 当前 active_sprint：**F205-d**（PoolBuilderWidget 前端） / phase=`contract_agreed`

---

## 已完成内容（截至本 session）

### F205-a / F205-b / F205-c ✅ done
（详见 `claude-progress.txt` 与 features.json）
- 后端 `GET /api/cockpit/pool` 已上线，820 全量回归通过

### F205-d Sprint Contract ✅ 协商完成（本 session）
- 文档：`docs/开发/sprint-contracts/F205-d-contract.md`
- features.json `F205-d.phase` = `contract_agreed`
- 6 个预计修改文件全部前端，命中 6 文件原则上限
- 三个开放问题已确认（funnel 仅高亮 / layout y=22 整行 / filter 默认展开）

---

## 当前状态

| 项 | 值 |
|---|---|
| active_sprint | F205-d |
| active_sprint_phase | contract_agreed |
| F205-c phase | needs_review |
| 后端全量回归 | 820 passed |
| 前端测试 | 待 F205-d 完成后回归 |

---

## F205-d Sprint Contract 摘要

### 实现范围
- **API client**：`cockpitPoolApi.ts`（getCockpitPool + 60s timeout + 类型定义）
- **Widget**：`PoolBuilderWidget.tsx`（Funnel 5 段 + Filter Bar + 候选表 + `[+ Add]`）
- **Filter 子组件**：`_poolFilterBar.tsx`（受控 + debounce 300ms）
- **Registry 注册**：CockpitRegistry.ts 新增 `cockpit.pool-builder`
- **测试**：API client 4 用例 + Widget 9–12 用例

### 6 个预计修改文件
```
frontend/src/cockpit/lib/api/cockpitPoolApi.ts            (新建)
frontend/src/cockpit/widgets/PoolBuilderWidget.tsx        (新建)
frontend/src/cockpit/widgets/_poolFilterBar.tsx           (新建)
frontend/src/cockpit/CockpitRegistry.ts                   (修改)
frontend/src/cockpit/widgets/__tests__/PoolBuilderWidget.test.tsx (新建)
frontend/src/cockpit/lib/api/__tests__/cockpitPoolApi.test.ts     (新建)
```

### 关键约束
- 字段命名以 `API-CONTRACT.md §GET /api/cockpit/pool` 为权威
- 非 watchlist 字段为 null 时显示 `—`（D080）
- react-query staleTime 60_000ms，filter debounce 300ms
- `[+ Add]` 调既有 `addStock(ticker)`，invalidate `['cockpit-pool']` + `['watchlist']`
- 颜色/字体/间距全部走 token，无硬编码 hex

---

## 开发顺序（Generator 阶段，新 session 执行）

1. 新建 `cockpitPoolApi.ts`（类型 + 函数 + 60s timeout） → wip commit
2. 新建 `cockpitPoolApi.test.ts` 4 用例 → 通过 → wip commit
3. 新建 `_poolFilterBar.tsx`（受控 + debounce） → wip commit
4. 新建 `PoolBuilderWidget.tsx`（Funnel + 表 + Add 按钮） → wip commit
5. 修改 `CockpitRegistry.ts` 注册 → wip commit
6. 新建 `PoolBuilderWidget.test.tsx` 9–12 用例 → 通过 → wip commit
7. `pnpm tsc --noEmit` + `pnpm test` 全量回归 → Evaluator 自检 → 最终 `feat(F205-d): ...` commit

---

## 关键文件参考

| 用途 | 路径 |
|------|------|
| Sprint Contract | `docs/开发/sprint-contracts/F205-d-contract.md` |
| API 接口 | `docs/系统设计/API-CONTRACT.md` §GET /api/cockpit/pool（行 1322–1388） |
| Widget 视觉规格 | `docs/设计/design-spec.md` 行 872–902 |
| 字段绑定 | `docs/设计/data-mapping.md` §Cockpit-3（行 439–488） |
| 组件边界 | `docs/设计/component-plan.md` 行 416–419 + Cockpit-4 表 |
| 最近邻参考 widget | `frontend/src/cockpit/widgets/SetupMonitorWidget.tsx` |
| Registry | `frontend/src/cockpit/CockpitRegistry.ts` |
| watchlist API（既有） | `frontend/src/lib/api/watchlist.ts::addStock` |

---

## 下一 Session 恢复指令

**开新 session（建议 Sonnet），粘贴**：

> 继续开发 F205-d，Sprint Contract 已确认。
> 读取 SESSION-HANDOFF.md + docs/开发/sprint-contracts/F205-d-contract.md，
> 进入 Generator 模式，从开发步骤 1（cockpitPoolApi.ts）开始。
