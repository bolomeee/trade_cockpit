# SESSION-HANDOFF — 2026-04-22 (F112-b 重拆)

## 立即执行指令（给下一个 session）

**开启新 session 后，说**：
> 继续开发 F112-b1

触发 `/feature-dev` skill 的类型 E2（开发恢复）+ 类型 A-2（Generator 模式）。

---

## 上下文摘要

### F112 News Widget 整体进展

| 子任务 | phase | 合约 | 备注 |
|--------|-------|------|------|
| F112-a（后端 `/api/news/articles`） | ✅ done | [F112-a-contract.md](docs/开发/sprint-contracts/F112-a-contract.md) | commit 7cf3cfd + 010169c |
| F112-b（老合约，路径 B — 只加 Workbench widget） | ❌ SUPERSEDED | [F112-b-contract.md](docs/开发/sprint-contracts/F112-b-contract.md) | commit aa86e7a — 验收发现需求理解偏差 |
| **F112-b1（导航 + /news + NewsTable）** | 🟢 contract_agreed | [F112-b1-contract.md](docs/开发/sprint-contracts/F112-b1-contract.md) | **下一步起点** |
| F112-b2（ArticleModal + Chart 复用 + ticker 联动） | 🟢 contract_agreed | [F112-b2-contract.md](docs/开发/sprint-contracts/F112-b2-contract.md) | b1 完成后执行 |

### 为何拆分

最初 F112 计划 a/b/c 三步，用户验收时明确了真实意图：
1. TopNav 加 `News` 入口
2. `/news` 路由，仍用 react-grid-layout
3. News widget 改为 **table**，点击行弹 modal（50% 透明遮罩 + 圆形关闭）
4. 同页放 Chart widget（复用首页同款），点 modal 里的 ticker 时 → 关闭 modal + chart 切到该 ticker，当日数据复用 F111-a 缓存

F112-b（路径 B 老合约）方向错了，拆成 F112-b1（骨架）+ F112-b2（交互/联动）。F112-c 合并到 F112-b2。

### 当前代码状态（`git log --oneline`）

```
aa86e7a feat(F112-b): NewsWidget — Workbench 新闻卡片列表   ← 需在 F112-b1 部分消化
010169c docs(F112-a): 验收通过，phase → done
7cf3cfd feat(F112-a): News 后端 API — FMP /fmp-articles 代理
```

### 不需要 revert commit aa86e7a

F112-b1 的修改会自然消化 aa86e7a 的遗留：
- `NewsWidget.tsx`：保留组件文件，**重写**为 table 形式（不是 revert）
- `WidgetRegistry.ts`：把 `news.articles` manifest id 改为 `news.table`，同时移除 Workbench 默认布局对它的引用
- `useNewsArticles.ts` / `lib/api/news.ts` / `types/news.ts`：原样复用

所以不需要 `git revert aa86e7a`。按 F112-b1 合约直接改就是了。

### 用户已拍板的决策（F112-b 需求对齐轮次）

| Q | 决策 |
|---|------|
| Workbench 首页 NewsWidget | **移除**（News 只出现在 /news 页） |
| News 页布局持久化 | **独立**（新建 `useNewsLayoutStore`，key `ma150.news.layouts.v1`） |
| NewsTable 列 | Date / Site / Title / Tickers |
| chart ticker 联动 | 复用 `useAppStore.selectedSymbol` |
| modal 内点 ticker | **关闭 modal + 切 chart** |
| 范围 | **拆 F112-b1 + F112-b2** |

### 测试门禁（项目现状）

- 后端：`pytest backend/tests` 312/312（F112-a 覆盖 24/24）
- 前端：无测试框架（项目约定），`pnpm build` + `pnpm lint` + preview 手动验证
- 本机 dev：前端 `pnpm --dir frontend dev` (5173) + 后端 `uv run uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload`

### 文档状态

- `docs/系统设计/API-CONTRACT.md` — News 章节已追加（F112-a）
- `docs/系统设计/DATA-MODEL.md` — 无改动
- `docs/系统设计/DECISIONS.md` — 无新条目（DOMPurify 决策待 F112-b2 追加）
- `docs/设计/design-spec.md` — **仍无 News 章节**；F112-b1/b2 的视觉决策写在各自合约里作为"本地视觉决策"。未来若有 Figma 覆盖以 Figma 为准。

### 下一 session 注意事项

1. 读 `F112-b1-contract.md` 第 2 节确认 7 文件清单
2. 起手改 `WidgetRegistry.ts`（rename + 分派），再改 Workbench.tsx 跟进，否则 build 会挂
3. 老 `ma150.workbench.layouts.v5` localStorage 里可能仍有 `news.articles` id → Workbench.tsx 第 47 行 `if (!manifest) return <div />` 已兼容，不会崩，但首页可能多一个空占位。用户可手动点"重置布局"清理。验收时一并确认。
4. 完成 Evaluator 自检后，phase → `needs_review`，commit，等用户验收再进 F112-b2
