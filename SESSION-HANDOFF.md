# SESSION HANDOFF

> 生成时间：2026-04-25
> 当前阶段：F209-c 🔍 needs_review（Generator 完成，待 Acceptance）
> 当前 branch：cockpit

---

## 本 session 完成的事

**F209-c Generator 模式（Step 8a → 11）**

| 步骤 | 内容 | 状态 |
|------|------|------|
| 8a | 新建 AiSetupExplainerPopover.tsx（类型 + buildInput + useQuery + 4 状态）| ✅ |
| 8b | SetupMonitorWidget.tsx 加第 10 列 `?` + 条件渲染 | ✅ |
| 8c | SetupMonitorWidget.test.tsx §S 11 用例 | ✅ 89/89 tests pass |
| 9 | design-spec.md line 973 偏离标注（hover→click）| ✅ |
| 10 | tsc + lint（新文件 0 warning）| ✅ |
| 11 | Evaluator 自检 12 项 | ✅ |

---

## 当前代码状态

### 新建文件

**`frontend/src/cockpit/components/AiSetupExplainerPopover.tsx`**（~200 行）
- Props：`ticker / setupType(BREAKOUT|PULLBACK|RECLAIM) / trendScore / rsPercentile / entryPrice / stopPrice`
- `buildSetupExplainerInput`：BREAKOUT→breakout / PULLBACK→pullback / RECLAIM→reversal；trend 60/40 阈值；rs passthrough；risk={entry,stop}
- `useQuery`：`enabled: open`（点击才请求）/ staleTime=gcTime=24h / retry=false / queryKey=['ai','setup_explainer',ticker,setupType]
- 4 状态：loading（3×Skeleton data-testid=ai-explainer-skeleton）/ error（data-testid=ai-explainer-error "AI 暂不可用"）/ success（data-testid=ai-explainer-label|quality|why-watch|risks）/ closed（不发请求）
- QualityBadge inline（A/B/C/D 均支持；data-testid=ai-explainer-quality）
- 按钮 `e.stopPropagation()` 阻止冒泡到 `<tr onClick>`

**`frontend/src/cockpit/widgets/__tests__/SetupMonitorWidget.test.tsx`**（11 用例）
- makeRoutedFetch 路由：`/cockpit/setup-monitor` + `/ai/setup_explainer`
- mockSetSelectedTicker via `vi.mock('@/store/cockpitStore', ...)`
- S1-S6：按钮渲染/不渲染 / S7：stopPropagation / S8：POST body 映射 / S9：Skeleton / S10：成功渲染 / S11：502 + 行点击仍可用

### 修改文件

**`frontend/src/cockpit/widgets/SetupMonitorWidget.tsx`** (+16 行)
- import AiSetupExplainerPopover
- `<Th width="5%">?</Th>` 追加第 10 列
- SetupRow 末尾追加 `<td>`：仅 BREAKOUT/PULLBACK/RECLAIM 且 entryPrice>0 && stopPrice>0 渲染 popover，其余 setup 空 td

**`docs/设计/design-spec.md`** line 973（+2 行）
- 偏离标注：hover → click，features.json acceptance_criteria 优先

---

## Git 历史

```
76b5c08 chore(F209-c): design-spec deviation note
d8f61b6 wip(F209-c): tests §S green
539f350 wip(F209-c): widget integration
c07e49d wip(F209-c): popover component skeleton
48cc654 chore(F209-c): sprint contract agreed
```

---

## 下一步：Acceptance（建议新 session）

### Acceptance 触发指令

```
F209-c needs_review 进入 Acceptance。
读取 SESSION-HANDOFF.md + docs/开发/sprint-contracts/F209-c-contract.md
运行 Acceptance 检查：
1. 启动前后端（pnpm dev + uvicorn port 8001）
2. 浏览器视觉验证：? 按钮位置 / popover 对齐 / Quality 徽章色 / 加载态
3. 后端 smoke：实际调用 setup_explainer，验证 cacheHit（第二次=true）
4. 全量 pnpm test --run 回归
5. 完成后更新 features.json F209-c.phase = done，生成 SESSION-HANDOFF.md
```

### Acceptance 重点核查

| 项目 | 关键点 |
|------|--------|
| C1 视觉 | BREAKOUT/PULLBACK/RECLAIM 行右侧出现 `?`，其余不出现 |
| C2 对齐 | `?` 在 Earn 右侧第 10 列，不破坏已有列宽 |
| C3 API body | Network 面板：`setup` 字段为小写映射值；`noCache: false` |
| C4 stopPropagation | 点击 `?` 不改变 CockpitChart 面板选中 ticker |
| C5 Skeleton | 弱网 or 实际 LLM 延迟期间 popover 内 3 个 Skeleton 可见 |
| C6 成功 | label（粗体）+ Quality 徽章（色正确）+ whyWatch + mainRisks 列表 |
| C7 错误 | 关掉后端 LLM 服务后：popover 内显示"AI 暂不可用" |
| C8 缓存 | 同行第二次点击：Network 无新 POST 请求 |
| Q1 | trendScore 实际值域是否 0-100（60/40 阈值是否合理）|
| Q3 | 5% 列宽视觉是否够宽 |

---

## 启动开发环境命令

```bash
# 后端（端口 8001，匹配 vite proxy）
cd "/Users/wonderer/Desktop/Claude workspace/stock_portal/backend"
uv run uvicorn app.main:app --reload --port 8001

# 前端（端口 5173）
cd "/Users/wonderer/Desktop/Claude workspace/stock_portal/frontend"
pnpm dev
```

如果 5173 被占：`lsof -ti:5173,5174,5175 | xargs kill`

---

## features.json 当前状态

| Feature | Phase | 说明 |
|---------|-------|------|
| F209-a | ✅ done | AI 后端 schema 注册 |
| F209-b | ✅ done | Market Narrator 前端集成 |
| **F209-c** | **🔍 needs_review** | **本次完成，待 Acceptance** |
| F210 | ⬜ design_ready | Candidate Ranker + Trade Plan |
| F211 | ⬜ design_ready | Contradiction + News + Journal |

---

## 引用文档

| 文档 | 用途 |
|------|------|
| docs/开发/sprint-contracts/F209-c-contract.md | Sprint 权威（含 Acceptance §5 自检清单）|
| frontend/src/cockpit/components/AiSetupExplainerPopover.tsx | 主要新文件 |
| frontend/src/cockpit/widgets/__tests__/SetupMonitorWidget.test.tsx | 测试覆盖 |
| docs/设计/design-spec.md line 972-973 | 偏离标注位置 |
