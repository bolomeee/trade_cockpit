# SESSION HANDOFF

> 生成时间：2026-04-25
> 当前阶段：F209-c 📋 contract_agreed（待 Generator 模式开发）
> 当前 branch：cockpit

---

## 本 session 完成的事

**F209-c Sprint Contract 协商**

| 步骤 | 内容 | 状态 |
|------|------|------|
| 读取 acceptance_criteria + schema + design-spec | features.json#F209-c / setup_explainer.py / §Widget5 | ✅ |
| 识别核心字段不匹配（SetupItem.setupType vs schema.setup）| 7 大写 vs 5 小写 | ✅ |
| 与用户 4 项决策对齐 | 全 yes | ✅ |
| context7 查 shadcn/ui Popover 最新 API | 受控 open + asChild | ✅ |
| Sprint Contract 落盘 | docs/开发/sprint-contracts/F209-c-contract.md | ✅ |
| features.json 更新 | F209-c.phase = contract_agreed / active_sprint = F209-c | ✅ |
| claude-progress.txt 追加 | Contract 协商日志 | ✅ |

---

## Sprint Contract 摘要

**完整文档**：[docs/开发/sprint-contracts/F209-c-contract.md](docs/开发/sprint-contracts/F209-c-contract.md)

### 实现范围
SetupMonitorWidget 第 10 列加 `?` 按钮，仅 `BREAKOUT/PULLBACK/RECLAIM` 三种 setup 显示。点击打开 shadcn `Popover`，调 `POST /api/ai/setup_explainer`，渲染 4 状态（loading Skeleton / success label+quality+whyWatch+mainRisks / error "AI 暂不可用" / closed 不请求）。

### 4 项已确认决策
| # | 决策 | 选择 |
|---|------|------|
| 1 | setup 映射 | BREAKOUT→breakout / PULLBACK→pullback / RECLAIM→reversal；其余 4 种 setup 不渲染按钮 |
| 2 | 触发方式 | **点击**（非 hover，与 features.json 一致；design-spec line 972 待 step 9 加偏离标注）|
| 3 | 缓存策略 | 不写前端 cooldown；react-query `gcTime=24h` + 服务端 `ai_memos` 双层 |
| 4 | 视觉布局 | 独立第 10 列 `?`，width=5%，align="end" |

### 预计修改文件（共 3 个）
| 路径 | 操作 |
|------|------|
| `frontend/src/cockpit/components/AiSetupExplainerPopover.tsx` | 新建（~130 行）|
| `frontend/src/cockpit/widgets/SetupMonitorWidget.tsx` | +12 行 |
| `frontend/src/cockpit/widgets/__tests__/SetupMonitorWidget.test.tsx` | +220 行（§S 11 用例）|

附加规则 8 回写：`docs/设计/design-spec.md` line 972 加 hover→click 偏离标注（不计入 6 文件上限）。

---

## 下个 Session 起点：F209-c Generator 模式

**触发指令**（粘贴到新 session，建议 Sonnet）：

```
继续开发 F209-c，Sprint Contract 已确认。
读取 SESSION-HANDOFF.md + docs/开发/sprint-contracts/F209-c-contract.md，
进入 Generator 模式，从开发顺序 step 8a 开始
（AiSetupExplainerPopover.tsx 新建）。
```

### 开发顺序（严格执行，每步完成后立即 wip commit）

| Step | 内容 | 验证 | commit msg |
|------|------|------|-----------|
| 8a | 新建 `AiSetupExplainerPopover.tsx`（类型 + buildInput + useQuery + 4 状态渲染）| tsc 通过 | `wip(F209-c): popover component skeleton` |
| 8b | `SetupMonitorWidget.tsx` 加第 10 列 + 条件渲染按钮 | 浏览器手动验证渲染 | `wip(F209-c): widget integration` |
| 8c | `SetupMonitorWidget.test.tsx` §S 11 用例（S1-S11）| `pnpm test --run` 全绿 | `wip(F209-c): tests §S green` |
| 9 | `design-spec.md` line 972 加偏离标注（规则 8）| grep 验证 | `chore(F209-c): design-spec deviation note` |
| 10 | `pnpm tsc --noEmit` + `pnpm lint` 全绿 | 工程门禁 | — |
| 11 | Evaluator 自检（11 项 + 全量回归）| Contract §5 自检清单 | feat(F209-c) 收尾 |

### Contract 关键条款（避免回看）

**输入构造**（buildSetupExplainerInput）：
```ts
setup: BREAKOUT→'breakout' / PULLBACK→'pullback' / RECLAIM→'reversal'
trend: trendScore>=60→'up' / <=40→'down' / else 'sideways'
rs: rsPercentile（int → float OK）
risk: { entry: entryPrice, stop: stopPrice }
```

**Quality 徽章**：popover 内 inline 渲染（含 'D'），不复用 SetupQualityBadge（避免改组件签名）。

**按钮 e.stopPropagation()**：阻止冒泡到 `<tr onClick>` 的 setSelectedTicker。

**测试 mock**：复用 F209-b 的 `makeRoutedFetch`（位于 MarketRegimeWidget.test.tsx），按 URL 路由 setup-monitor + setup_explainer。

---

## 启动开发环境的标准命令

```bash
# 后端（端口 8001，匹配 vite proxy）
cd "/Users/wonderer/Desktop/Claude workspace/stock_portal/backend"
uv run uvicorn app.main:app --reload --port 8001

# 前端（端口 5173）
cd "/Users/wonderer/Desktop/Claude workspace/stock_portal/frontend"
pnpm dev
```

如果 5173 被占：`lsof -ti:5173,5174,5175 | xargs kill`

> 上一 session 教训：vite proxy 指向 `127.0.0.1:8001`，**不是 8000**。

---

## features.json 当前状态

| Feature | Phase | 说明 |
|---------|-------|------|
| F209-a | ✅ done | AI 后端 schema 注册 |
| F209-b | ✅ done | Market Narrator 前端集成 |
| **F209-c** | **📋 contract_agreed** | **本次 Contract 完成，待 Generator 启动** |
| F210 | ⬜ design_ready | Candidate Ranker + Trade Plan |
| F211 | ⬜ design_ready | Contradiction + News + Journal |

---

## 引用文档

| 文档 | 用途 |
|------|------|
| docs/开发/sprint-contracts/F209-c-contract.md | **本 sprint 唯一权威**，开发期间必随时回看 |
| backend/app/ai/schemas/setup_explainer.py | I/O Pydantic schema（字段命名权威）|
| frontend/src/cockpit/lib/api/aiApi.ts | callAiTask 入口（不改）|
| frontend/src/cockpit/widgets/MarketRegimeWidget.tsx#AiMarketNotes | F209-b 实现参考（4 状态渲染、ApiError 处理）|
| frontend/src/cockpit/widgets/__tests__/SetupMonitorWidget.test.tsx | 现有 SetupMonitor 测试（待扩展 §S）|
| frontend/src/cockpit/widgets/__tests__/MarketRegimeWidget.test.tsx | makeRoutedFetch 路由 mock 参考实现 |
| docs/设计/design-spec.md §Widget 5（line 945-973）| SetupMonitor 视觉规格 + line 972 待打偏离标注 |
| API-CONTRACT.md（line 1655-1734）| /api/ai/{task_type} 统一 envelope + 错误码 |
