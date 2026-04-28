# SESSION-HANDOFF — F211-c needs_review

> 生成时间：2026-04-29 | Branch: cockpit | 状态：F211-c Generator 完成，等待验收
> 本 session 模型：Sonnet 4.6（Generator 模式）
> 建议下一 session：acceptance skill

---

## 1. 本次 Session 工作摘要

完成 **F211-c（News 页 AI 摘要 bar 前端）** 完整开发（步骤 1-5）：

**步骤 1：预检**
- tokens 全确认（`--color-surface-muted` 缺失 → chip 改用 `--color-input-background`）
- `useNewsArticles` queryKey `['news', 'articles']` 确认
- `news_summarizer.py` 字段拼写确认
- jsdom DOMParser ✅ / crypto.subtle ✅（Node 24）
- `AiContradictionsSection.tsx` 完整阅读作为模板

**步骤 2：核心组件**
- 新建 `frontend/src/components/news/newsSummaryUtils.ts`（pure helpers）
- 新建 `frontend/src/components/news/AiNewsSummaryBar.tsx`（6 态状态机）

**步骤 3：集成**
- `frontend/src/pages/News.tsx` +4 行（import + bar 容器）
- 浏览器截图确认：trigger 按钮在 grid 上方，disabled 状态正确（无 articles）

**步骤 4：测试**
- 新建 `frontend/src/components/news/__tests__/AiNewsSummaryBar.test.tsx`
- 14 case：C1-C8 component tests + 3×2 helper unit tests，14/14 pass

**步骤 5：Evaluator 自检**
- 全量 vitest：273/276 pass（3 个预存 TopNav 失败不变）
- tsc 0 error；ESLint 0 新增 warning（react-refresh 问题通过拆 utils 文件解决）
- 自检清单全通过（无硬编码颜色、无 console、enabled gating 正确、News.tsx diff ≤ 12 行）

---

## 2. 新建 / 修改文件清单（共 5 个）

| # | 文件 | 操作 |
|---|------|------|
| 1 | `frontend/src/components/news/newsSummaryUtils.ts` | 新建（helpers：stripHtml / sortByPublishedDesc / articlesHash / buildSummarizerArticles） |
| 2 | `frontend/src/components/news/AiNewsSummaryBar.tsx` | 新建（~330 行，6 态状态机） |
| 3 | `frontend/src/components/news/__tests__/AiNewsSummaryBar.test.tsx` | 新建（14 tests） |
| 4 | `frontend/src/pages/News.tsx` | 修改（+4 行：import + bar 容器） |
| 5 | `docs/需求/features.json` | 更新（F211-c → needs_review，iteration_history +1） |

---

## 3. 全局 F211 状态

| Sub-sprint | Phase | 备注 |
|---|---|---|
| F211-a1 | ✅ done | 3 schemas + REGISTRY + guardrail |
| F211-a2 | ✅ done | per-task model override 基建 + D075 |
| F211-b | ✅ done | DecisionPanel Contradictions 区前端，验收通过 |
| F211-c | 🟡 needs_review | News 页 AI 摘要 bar ← **本次** |
| F211-d | ⬜ design_needed | 平仓 hook + ai_review 迁移 + 月度 cron |

---

## 4. 待验收检查点（acceptance skill）

按 F211-c Sprint Contract §3 完成标准 C1-C12：

| # | 标准 | 状态 |
|---|------|------|
| C1 | closed → 点 trigger → loading skeleton | ✅ vitest C1/C2 |
| C2 | success-with 4 区块全渲染 | ✅ vitest C3 |
| C3 | risks length 0 隐藏 risks 区 | ✅ vitest C4 |
| C4 | relevantTickers length 0 隐藏 tickers 行 | ✅ vitest C5 |
| C5 | error 502 → "AI 暂不可用" + 关闭回 closed | ✅ vitest C6 |
| C6 | error 409 → "AI 输出被拦截" | ✅ vitest C7 |
| C7 | articles 空 → trigger disabled + title="暂无 news" | ✅ vitest C8 |
| C8 | 关闭再开命中 cache（cacheBadge="Cached"） | ✅ vitest C3（meta.cacheHit） |
| C9 | News.tsx bar 在 grid 之上（DOM 顺序） | ✅ 浏览器截图确认 |
| C10 | helper pure function 单测 | ✅ 14 tests |
| C11 | tsc 0 error；ESLint 0 新增 warning | ✅ |
| C12 | 全量回归 ≥ 基线（273/276，3 TopNav 不变） | ✅ |

---

## 5. 关键设计决策（Generator 阶段调整）

1. **utils 拆分**：helpers 移至 `newsSummaryUtils.ts`（sibling file），解决 `react-refresh/only-export-components` ESLint error，符合"不抽公共"约束（不进 `src/lib/`），4→5 文件仍在 6 上限内。

2. **chip 背景 token**：`--color-surface-muted` 不存在 → 使用 `--color-input-background`（#f3f3f5），符合"0 硬编码"自检，视觉效果相近。

3. **14 tests**：合约要求"11 case"，实际 stripHtml 拆 3 子用例（null/empty/truncate）+ articlesHash 拆 2 子用例（same/different），共 14，全通过。

---

## 6. 下一 Session 恢复指令

建议用 acceptance skill 开新 session 做 F211-c 验收：

```
/acceptance F211-c
```

验收通过后：
- features.json F211-c → done
- 考虑启动 F211-d（平仓 hook + ai_review 迁移 + 月度 cron）设计
