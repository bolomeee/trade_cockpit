# SESSION-HANDOFF — F210-b Generator 启动

> 生成时间：2026-04-25
> 上一个 session：F210-a ✅ done + regime hotfix 2853e3b + F210-b Sprint Contract 协商
> 下一个 session：F210-b Generator 模式（前端开发）
> 当前 branch：cockpit

---

## 1. 立即执行指令（粘贴到新 session）

> 继续开发 F210-b，Sprint Contract 已确认。
> 读取本文件 + `docs/开发/sprint-contracts/F210-b-contract.md`，
> 进入 Generator 模式，从开发顺序 step 8a 开始。
> （前端 sprint，DB / Repository / Service 已跳过）

---

## 2. F210 整体状态

| 子 sprint | phase | 说明 |
|----------|-------|------|
| F210-a | ✅ done | 后端 schemas + trade_plan guardrail；含 2853e3b regime 5 值 hotfix |
| **F210-b** | 🤝 **contract_agreed**（本 sprint）| SetupMonitor "AI 排序" 集成 |
| F210-c | ⬜ design_ready | DecisionPanel "Generate AI Plan" 集成 |

---

## 3. 上一阶段完成内容

### 3.1 F210-a regime hotfix（commit 2853e3b）

**缺陷**：`candidate_ranker.regime` Literal 只列了 4 值（CONSTRUCTIVE / NEUTRAL / CAUTION / RISK_OFF），但 `market_regime_service.py` 实际输出 5 值（RISK_ON / CONSTRUCTIVE / NEUTRAL / DEFENSIVE / RISK_OFF）。`cockpitRegimeApi.RegimeLabel` 与 backend 一致。Cockpit 真实调用遇 RISK_ON / DEFENSIVE 会被 422 拒。

**修复**：
- `backend/app/ai/schemas/candidate_ranker.py` line 53 替换为 5 值 Literal（移除从未产出的 CAUTION）
- `backend/tests/test_ai_schemas_f210a.py` 新增 `test_I5b_all_five_regime_values_accepted`

**验证**：F210-a 测试 32/32 pass；全量 621/621 pass。

### 3.2 F210-b Sprint Contract 已确认

合约：`docs/开发/sprint-contracts/F210-b-contract.md`

**5 个开放问题全部采默认方案**：
- Q1 不过滤 EXTENDED/BROKEN/NONE，全部 slice(0, 20) 后送 AI
- Q2 按钮位置：Filter Tabs 同行右侧
- Q3 result panel：行内 push down 表格（非 popover）
- Q4 错误态：不提供 retry 按钮
- Q5 inputKey 不排序 ticker（filter 切换是预期触发新请求）

---

## 4. 预计修改文件（共 3 个，远低于 6 上限）

| 路径 | 操作 | 预计行数 |
|------|------|---------|
| `frontend/src/cockpit/components/AiCandidateRankerSection.tsx` | 新建 | +200 |
| `frontend/src/cockpit/widgets/SetupMonitorWidget.tsx` | 修改 | +15 |
| `frontend/src/cockpit/widgets/__tests__/SetupMonitorWidget.test.tsx` | 修改 | +220 |

**附加（不计 6 上限，规则 8 回写）**：
- `docs/设计/design-spec.md` Widget 5 — 补 "AI 排序" 段（约 +10 行）
- `docs/设计/data-mapping.md` — 新增 §Cockpit-5.c（约 +20 行）

---

## 5. 开发顺序（按合约 §4 严格执行）

```
1-6. 跳过（前端 sprint）
7. 单元/集成测试 → 与 step 8 交叠
8. 前端组件
   8a. 新建 AiCandidateRankerSection.tsx（类型 + buildInput + useQuery + 5 状态渲染）
       → wip(F210-b): candidate ranker section component
   8b. SetupMonitorWidget.tsx 集成 regime useQuery + 挂载 section
       → wip(F210-b): widget integration + regime fetch
   8c. SetupMonitorWidget.test.tsx 扩展 §R 11 用例（R1-R11）
       → wip(F210-b): tests §R green
9. design-spec / data-mapping 回写（规则 8）
   → chore(F210-b): design-spec + data-mapping for AI rank
10. tsc + lint + 全量 vitest 回归
11. Evaluator 模式自检（合约 §5 清单）
12. Evaluator 通过 → 最终 commit feat(F210-b): SetupMonitor AI rank top 3
```

---

## 6. 关键技术约束（Generator 必须遵守）

- **regime 来源**：`useQuery({queryKey: ['cockpit-regime'], queryFn: getCockpitRegime, staleTime: 5*60*1000})`，与 MarketRegimeWidget 自动共享缓存
- **字段名适配**：前端 `regimeData.marketScore` → schema `regimeScore`（组件内构造 input 时转换）
- **截断**：前端 `items.slice(0, 20)` 在 build input 前完成
- **缓存**：`staleTime/gcTime = 24 * 60 * 60 * 1000`（与服务端 ai_memos 24h 对齐）
- **inputKey**：`${regime ?? ''}|${tickers.slice(0,20).join(',')}`（filter 切换自然触发新请求）
- **action badge 三色**：enter→`var(--color-signal-breakout)` / watch→`var(--color-log-warn)` / wait→`var(--color-text-muted)`
- **Cache 徽章**：`meta.cacheHit === true` → "Cached"；否则 "Generated · {modelUsed}"
- **关闭 ✕**：仅 setOpen(false)，不 invalidate query（缓存保留）
- **CandidateInput 9 字段精确集**：ticker / setupType / setupQuality / trendScore / rsPercentile / distanceToEntryPct / rewardRisk / earningsRisk / readySignal — 不传 stockName / volumeStatus / entryPrice / stopPrice / target* / scanDate / suggestedAction

---

## 7. 测试模板

`SetupMonitorWidget.test.tsx` 已有 F209-c §S 11 用例（setup_explainer popover），`makeRoutedFetch` 路由 mock 模板可直接复用。新增 §R 11 用例。

需补充的路由：
- `/cockpit/regime` → 返回 `{ regime: 'CONSTRUCTIVE', marketScore: 65, ... }`
- `/ai/candidate_ranker` → 按场景返回 200（topCandidates 3 项）/ 502 / never-resolve（加载态）

R11 缓存命中可参考 F209-c §S 缓存测试的 fetch spy 计数模式。

---

## 8. 启动检查（Generator 接手前确认）

- [x] hotfix 已提交（2853e3b）
- [x] 当前分支 `cockpit`
- [x] features.json `_pipeline_status.active_sprint = "F210-b"`，`active_sprint_phase = "contract_agreed"`
- [x] features.json `F210.sub_phases.F210-b.phase = "contract_agreed"` + contract 路径已写入
- [x] backend 全量 pytest 621/621
- [x] 合约文件 docs/开发/sprint-contracts/F210-b-contract.md 存在
- [ ] **建议在新 session（Sonnet）执行 §1 立即指令**

---

## 9. 未决事项 / 待 acceptance（Generator 不处理，留 acceptance 阶段）

- 视觉验证：result panel 在 widget 默认 5 行高内的占位（合约 §7 风险 7）
- 真实 cache hit smoke：调一次 meta.cacheHit=false；24h 内复调 meta.cacheHit=true
- AI 输出 `topCandidates[].ticker` 不在当前 items 集合内的视觉容错（合约 §7 风险 4）
