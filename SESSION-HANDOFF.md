# SESSION HANDOFF

> 生成时间：2026-04-25
> 当前阶段：F209-b 🤝 contract_agreed → 等待 Generator 模式开发
> 当前 branch：cockpit

---

## 本 session 完成的事

**F209-b：Sprint Contract 协商完成**

| 步骤 | 输出 | 状态 |
|------|------|------|
| 读取 ARCHITECTURE / DATA-MODEL / API-CONTRACT / design-spec / data-mapping / features.json | 全部 confirmed | ✅ |
| 起草 Sprint Contract | `docs/开发/sprint-contracts/F209-b-contract.md` | ✅ |
| 用户确认 5 项关键技术决策 | sector 归一化 / 1h cooldown / 错误文案 / useQuery 模式 / scope 收敛 | ✅ |
| 更新 features.json | F209-b phase → `contract_agreed`，active_sprint=F209-b | ✅ |
| 更新 claude-progress.txt | 追加 Contract 协商记录 | ✅ |

---

## Sprint Contract 摘要

### 实现范围（共 4 文件，未越界）

| 文件 | 类型 | 说明 |
|------|------|------|
| `frontend/src/cockpit/lib/api/aiApi.ts` | 🆕 新建 | 通用 `callAiTask<TIn, TOut>` + `MarketNarratorInput/Output` 类型 |
| `frontend/src/cockpit/widgets/MarketRegimeWidget.tsx` | ✏️ 修改 | 末尾追加 `<AiMarketNotes>` 子组件，**现有 4 区块 0 行改动** |
| `frontend/src/cockpit/lib/api/__tests__/aiApi.test.ts` | 🆕 新建 | §A 7 单测（成功/noCache/各错误码/网络错误） |
| `frontend/src/cockpit/widgets/__tests__/MarketRegimeWidget.test.tsx` | ✏️ 修改 | §S14 6 集成测试 + 路由式 fetch mock helper |

### 关键技术决策（用户已确认）

1. **sector state 5→3 归一化在前端做**（CockpitRegimeData 5 值 → MarketNarratorInput 3 值）：
   - `Strong` / `Constructive` → `Strong`
   - `Weak` / `Defensive` → `Weak`
   - `Neutral` → `Neutral`
   - ⚠️ Generator 阶段需回写 DECISIONS.md（D075 候选编号）
2. **前端 1h cooldown + 后端 24h server cache 双层**：用 react-query `dataUpdatedAt` 判 disabled
3. **错误统一文案"AI 暂不可用"**：不细分 502/429/网络（features.json AC 第 5 条原文）
4. **react-query `useQuery` + `forceNoCache` ref 单数据流**：自动首次拉取 + 手动 Refresh noCache 共用一个 query
5. **本 sprint 不做**：Cached `{age}` 副文案 / schemaVersion 过期提示 / modelUsed/tokens tooltip / 错误重试按钮 / 错误细分文案

---

## 开发顺序（Generator 模式从 Step 1 开始，不得跳步）

| Step | 内容 | wip commit |
|------|------|---------|
| 1 | `aiApi.ts` 新建 + §A 7 单测全通过 | `wip(F209-b): step1 aiApi.ts + tests` |
| 2 | `<AiMarketNotes>` 子组件骨架（loading/error/empty 外壳） | `wip(F209-b): step2 widget skeleton` |
| 3 | sector state 归一化 + useQuery + Refresh + 1h cooldown | `wip(F209-b): step3 query + cooldown` |
| 4 | §S14 6 集成测试通过 | `wip(F209-b): step4 integration tests` |
| 5 | Evaluator §3 全量回归 + §4 自检逐条 | `feat(F209-b): market narrator frontend integration` |
| 6 | features.json phase → needs_review + claude-progress + DECISIONS D075 | `chore(F209-b): phase needs_review + D075` |

---

## Evaluator 自检清单（开发完成后使用）

- [ ] §A aiApi 单测 7/7
- [ ] §S14 widget 集成 6/6
- [ ] §S1-S13 既有测试 0 回归
- [ ] frontend 全量 `pnpm vitest run` 通过
- [ ] backend 全量 `uv run pytest tests/` 仍 587 通过（sanity check）
- [ ] 4 文件未越界
- [ ] aiApi.ts 不含 widget 专属逻辑（保持通用，F209-c 可复用）
- [ ] MarketRegimeWidget 现有 4 区块 0 行改动（diff 验证）
- [ ] 无 console.error 遗留
- [ ] 颜色/字体/尺寸全部走 `var(--color-*)` / `var(--font-size-*)`，无硬编码
- [ ] sector state 归一化函数有显式测试覆盖
- [ ] Refresh cooldown 用 `dataUpdatedAt`，未引入 `setInterval`
- [ ] 所有错误统一显示"AI 暂不可用"
- [ ] 无新外部依赖（不动 package.json）
- [ ] features.json#F209-b phase = needs_review
- [ ] sector 归一化决策已写入 DECISIONS.md

---

## 引用文档

| 文档 | 节段 |
|------|------|
| API-CONTRACT.md | §POST /api/ai/{task_type}（line 1655-1734） |
| DATA-MODEL.md | §AiMemo（仅参考，前端不直接读 DB） |
| design-spec.md | §Widget 1 MarketRegimeWidget AI Market Notes（line 808-822） |
| data-mapping.md | §Cockpit-1.e + §Cockpit-AI-Wrapper（line 407-417 / 776-797） |
| DECISIONS.md | D064 / D069 / D074 |
| backend/app/ai/schemas/market_narrator.py | I-O Pydantic schema 权威 |
| docs/开发/sprint-contracts/F209-b-contract.md | 本 sprint Contract |

---

## 恢复指令（粘贴到新 session）

```
继续开发 F209-b，Sprint Contract 已确认。
读取 SESSION-HANDOFF.md + docs/开发/sprint-contracts/F209-b-contract.md，
进入 Generator 模式，从 Step 1（新建 frontend/src/cockpit/lib/api/aiApi.ts + §A 7 单测）开始。
```

---

## features.json 当前状态

| Feature | Phase | 说明 |
|---------|-------|------|
| F209-a | ✅ done | AI 后端 schema 注册（market_narrator + setup_explainer） |
| **F209-b** | 🤝 contract_agreed | Market Narrator 前端集成（**本 sprint，待 Generator**） |
| F209-c | ⬜ design_ready | Setup Explainer popover（依赖 F209-a + F209-b + F202-c） |

active_sprint = F209-b · active_sprint_phase = contract_agreed

---

## git 状态

branch：cockpit
本 session 文档变更（未 commit，待 Generator Step 1 wip commit 一起带入或独立 chore commit）：
- `docs/开发/sprint-contracts/F209-b-contract.md`（新建）
- `docs/需求/features.json`（F209-b phase + active_sprint）
- `claude-progress.txt`（追加 Contract 协商记录）
- `SESSION-HANDOFF.md`（本文件覆写）

最近 commits：
- 10b4aa0 chore(F209-a): acceptance passed — phase=done + migration 012 applied
- ecfad9e chore(F209-a): progress log + SESSION-HANDOFF (needs_review)
- cf3c715 feat(F209-a): market_narrator + setup_explainer schema registration — 587 tests pass
