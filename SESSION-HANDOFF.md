# SESSION-HANDOFF.md

> 生成时间：2026-04-17（覆盖上一版 F001-b Generator 前 handoff）
> 当前 Skill：无活跃 Skill（F001-b 全流程完成）
> 下一 Feature：**F001-c Frontend AddStock/搜索/删除交互**（ready_to_dev，等待 Sprint Contract 协商）

---

## 本 Session 完成的内容

### F001-b Frontend Watchlist 读取展示（✅ done，commit `c49b2ba` + `49c8e16` + `8f79ec4`）

**Generator**：10 文件实现数据层 + SignalBoard 组件 + Dashboard 四态

新建（10 文件）：
- `frontend/src/types/watchlist.ts` — WatchlistItem / LatestSignal / DataStatus / SignalType
- `frontend/src/lib/api/client.ts` — fetch 封装，解析 `{ data, error }` 信封
- `frontend/src/lib/api/watchlist.ts` — `getWatchlist()` 类型安全包装
- `frontend/src/components/features/dashboard/SignalBadge.tsx` — 5 状态 badge，只用 token 变量
- `frontend/src/components/features/dashboard/SignalCard.tsx` — 单卡片（ticker/name/distance/badge）
- `frontend/src/components/features/dashboard/SignalBoard.tsx` — grid 3/2/1 列，信号优先级排序
- `frontend/src/components/common/EmptyState.tsx` — 全局通用空态
- `frontend/src/components/common/ErrorState.tsx` — 全局通用错误态（含重试）
- `frontend/src/components/ui/skeleton.tsx` — shadcn Skeleton（shadcn add skeleton 安装）
- `frontend/.claude/launch.json` — preview 服务器配置

修改（3 文件）：
- `frontend/src/pages/Dashboard.tsx` — useQuery 接入，loading/empty/error/ready 四态
- `frontend/src/main.tsx` — QueryClientProvider 包裹
- `frontend/vite.config.ts` — 添加 dev proxy `/api` → `localhost:8000`

新增依赖：
- `@tanstack/react-query` v5（D017，用户 2026-04-17 批准）

**Evaluator**：pnpm build 零 TS 错误，F001-b 文件 lint 零问题，4 种状态 preview 验证通过

**验收**：用户手验 4 种状态全部通过

### 顺带修复的 Bug

**config.py .env 路径问题**（commit `49c8e16`）
- 现象：`cd backend && uv run uvicorn app.main:app --reload` 启动后 API 返回 500（POLYGON_API_KEY not set）
- 根因：`SettingsConfigDict(env_file=".env")` 从 CWD 查找，但 `.env` 在项目根目录而非 `backend/`
- 修复：改用 `Path(__file__).parent.parent.parent / ".env"` 绝对路径定位
- 影响：现在可以从任意目录启动后端，不受 CWD 影响

### 文档更新

- `docs/系统设计/API-CONTRACT.md` — 补充 GET /api/watchlist 响应中的 `dataStatus` 字段（F001-a 遗漏）
- `docs/系统设计/DECISIONS.md` — 追加 D017（@tanstack/react-query）+ D018（Vite dev proxy）
- `docs/开发/sprint-contracts/F001-b-contract.md` — Sprint Contract 存档
- `docs/验收/v1.0-acceptance.md` — 追加 F001-b 验收记录

---

## 中断位置

无中断。F001-b 全流程完整收尾（Contract → Generator → Evaluator → 验收 → commit）。

---

## Sprint Contract 执行状态

| Sprint | Phase | 备注 |
|--------|-------|------|
| F001-a Backend | ✅ done | commit `87c1483` + `befccd0` |
| F001-b Frontend 读取展示 | ✅ done | commit `c49b2ba` + `49c8e16` + `8f79ec4` |
| F001-c Frontend 交互 | ⬜ ready_to_dev | **下一 Sprint**，未起草 Contract |

F001（父级）：`in_progress`（等 c 完成再整体归档）

---

## F001-c 进场前已知条件

### 范围（从 component-plan.md + design-spec.md 继承）

- **AddStockCard**（`src/components/features/dashboard/AddStockCard.tsx`）
  - Input（受控）+ 搜索结果 Combobox 下拉（GET /api/stocks/search，debounce 300ms）
  - 搜索无结果：Alert 提示"未找到匹配的股票"
  - 选中后调 POST /api/watchlist，成功后 `invalidateQueries(['watchlist'])`
  - 添加成功后清空 Input

- **删除功能**（在现有 SignalCard 上加 Delete 按钮）
  - 悬停时显示删除图标（lucide `Trash2`）
  - 点击调 DELETE /api/watchlist/:ticker，成功后 `invalidateQueries(['watchlist'])`
  - 无二次确认（MVP 简化，design-spec 未画）

- **Dashboard.tsx 侧边栏**：接入 AddStockCard（现在是空 `<div style={{width:'158px'}}`）

### 已知的 shadcn 组件需求

- `Combobox`（或 `Command` 组件）— 尚未安装，F001-c 需要 `npx shadcn add combobox`
- design-spec 建议用 shadcn Combobox 实现搜索下拉

### 协商时要确认的关键决策

1. **搜索触发时机**：debounce 300ms + 最少 1 字符？还是 2 字符起搜？
2. **搜索结果唯一时**：直接添加还是仍需用户确认？（design-spec 说唯一则直接 POST，多个则下拉选择）
3. **删除确认**：无二次确认直接删（MVP 简化），还是加 shadcn AlertDialog？
4. **loading 态**：AddStock 按钮提交中 spinner？删除中卡片 disabled 态？
5. **测试策略**：F001-c 有实际 mutation，是否引入 msw mock 写 Vitest 集成测试？

### API 接口（F001-a 已实现，可直接使用）

- `GET /api/stocks/search?q={query}` — 返回 `StockSearchItem[]`（ticker/name/exchange/type）
- `POST /api/watchlist { ticker }` — 201 + WatchlistCreatedItem
- `DELETE /api/watchlist/{ticker}` — 200 + `{ ticker, removed: true }`

---

## 必读文档清单（下一 Session）

| 顺序 | 文档 | 重点 |
|------|------|------|
| 1 | SESSION-HANDOFF.md | 本文件 |
| 2 | docs/设计/design-spec.md §Dashboard AddStockCard 交互 | 搜索下拉、唯一结果处理 |
| 3 | docs/系统设计/API-CONTRACT.md §stock-search + §watchlist POST/DELETE | 请求/响应格式 |
| 4 | docs/设计/component-plan.md §AddStockCard | props 契约、职责边界 |
| 5 | frontend/src/pages/Dashboard.tsx | 当前 Sidebar 空位置 |
| 6 | frontend/src/components/features/dashboard/SignalCard.tsx | 删除按钮加在这里 |

---

## 环境快照

- git branch：`main` · 最新 commit：`8f79ec4`（F001-b 验收归档）
- 工作树：clean
- 后端启动：`cd backend && uv run uvicorn app.main:app --reload`（现在从任意目录均可）
- 前端启动：`cd frontend && pnpm dev`（localhost:5173，/api 自动代理到 localhost:8000）
- docker 全栈：`docker compose up -d`（localhost:8080；改代码必须 `--build`）
- pytest 基线：38 通过
- 已安装前端依赖：@tanstack/react-query v5、shadcn skeleton

---

## 下一个 Session 继续指令

```
我回来了，请按顺序读取：
1. SESSION-HANDOFF.md（本文件）
2. docs/设计/design-spec.md（Dashboard AddStockCard 交互段落）
3. docs/系统设计/API-CONTRACT.md §stocks-search + §watchlist（POST/DELETE）
4. docs/设计/component-plan.md §AddStockCard
5. frontend/src/pages/Dashboard.tsx（当前 Sidebar 空位）
6. frontend/src/components/features/dashboard/SignalCard.tsx

然后触发 feature-dev skill，起草 F001-c Sprint Contract：
  - 范围：AddStockCard（搜索 + 添加）+ SignalCard 删除按钮
  - 协商：搜索最少字符数、唯一结果是否直接添加、删除二次确认
  - 确认是否引入 shadcn Combobox（新依赖需批准）
Contract 用户确认后进 Generator。
```
