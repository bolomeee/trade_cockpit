# Sprint Contract：F001-c Frontend AddStock 搜索 + 删除交互

> 日期：2026-04-17 | 状态：草案（等待用户最终确认）
> 引用文档：
>   API-CONTRACT.md#watchlist（POST / DELETE） | API-CONTRACT.md#stock-search
>   design-spec.md §Dashboard AddStockCard 交互（L100-L110） | component-plan.md §AddStockCard（L150-L153）
> 前置：F001-a ✅（后端 API 就绪，38 pytest 通过）+ F001-b ✅（Dashboard 四态展示就绪）

---

## 本次实现范围

**包含**：

### AddStockCard（新建）
- 受控 Input（placeholder `"e.g. AAPL"`），按 **Enter** 触发搜索（非 debounce 实时）
- Input 为空时 Enter 不生效
- 搜索通过 `GET /api/stocks/search?q={query}&limit=10` 完成
- 搜索结果通过 shadcn Popover + Command 下拉展示（Combobox 模式）
  - 每项显示 `ticker` + `name` + `exchange`
  - 点击某项 → 调用 `POST /api/watchlist { ticker }` → 成功后：
    - `invalidateQueries(['watchlist'])`
    - 清空 Input + 关闭下拉 + 重新 focus Input
- 搜索中下拉顶部显示 loading（spinner + 文案"搜索中..."）
- 搜索无结果：下拉内显示 shadcn Alert 文案"未找到匹配的股票"（而非 Combobox Empty state）
- 搜索 API 失败：下拉内显示内联错误 + 重试按钮
- 添加 mutation 进行中：被点击的下拉项 disabled + spinner
- 添加 mutation 失败：
  - `DUPLICATE (409)` → 下拉中该项下方显示"该股票已在 watchlist"
  - `NOT_FOUND (404)` → 下拉中该项下方显示"股票代码无效"
  - 其他 → "添加失败，请重试"（3 秒自动消失）
- 添加成功后无 toast（MVP 简化），通过 SignalBoard 新卡片出现作为反馈

### SignalCard（修改）
- 右上角新增删除按钮（lucide `Trash2` 图标，16px）
- 默认隐藏（opacity: 0），卡片 hover 时显示（opacity: 1，150ms transition）
- 点击删除按钮 → 弹出 shadcn `AlertDialog` 二次确认：
  - 标题："确认删除"
  - 描述："从 watchlist 中移除 **{ticker}**？"
  - 按钮："取消" / "删除"（destructive 变体）
- 确认后调用 `DELETE /api/watchlist/{ticker}` → 成功后 `invalidateQueries(['watchlist'])`
- Mutation 进行中：整张卡片 `opacity: 0.5` + `pointerEvents: none`，"删除"按钮显示 spinner
- Mutation 失败：AlertDialog 内显示内联错误"删除失败，请重试"，Dialog 不关闭
- ⚠️ 删除按钮的 `onClick` 必须 `stopPropagation`，防止触发 SignalCard 自身的 onClick（F005 未来会接 Modal）

### Dashboard.tsx（修改）
- 移除 `Sidebar` 的占位空 div（当前 L48）
- Sidebar 渲染 `<AddStockCard />`
- AddStockCard 内部自管 mutation，不通过 props 传递

### API 层（修改 / 新建）
- `lib/api/stocks.ts`（新建）：`searchStocks(q: string, limit?: number): Promise<StockSearchItem[]>`
- `lib/api/watchlist.ts`（修改）：追加
  - `addStock(ticker: string): Promise<WatchlistCreatedItem>`
  - `removeStock(ticker: string): Promise<{ ticker: string; removed: boolean }>`
- `types/stocks.ts`（新建）：`StockSearchItem`、`WatchlistCreatedItem` 类型

---

**明确排除（本次不做）**：
- Toast 通知（MVP 无 toast 系统）
- 搜索历史 / 推荐词
- 键盘完整导航增强（Arrow 键下拉选择已由 shadcn Command 默认支持，不额外定制）
- Vitest 自动化测试（项目未配置，超出本次范围）
- 点击 SignalCard 打开 StockDetailModal（F005）
- 真实后端数据完整路径验证（F001-a 已有 pytest 覆盖，本次仅前端集成）

---

## 交互决策记录（Contract 协商结果，2026-04-17）

| # | 决策点 | 采纳方案 | 原因 |
|---|--------|---------|------|
| 1 | 搜索触发时机 | **Enter 键触发**（非 debounce） | 用户偏好 / 减少 Polygon API 调用次数 |
| 2 | 唯一结果处理 | 统一走下拉选择，不自动 POST | 交互一致性；需偏离回写 design-spec.md L106 |
| 3 | 删除二次确认 | 需要，使用 shadcn AlertDialog | 用户偏好；防误删 |
| 4 | Mutation 状态 UI | Add：项 disabled+spinner；Delete：卡片半透明+spinner；失败内联 Alert | 用户确认 |
| 5 | 新依赖引入 | shadcn `command` + `popover` + `alert-dialog` + lucide `Trash2` | 用户批准，开发前 context7 查询最新用法 |

---

## 预计修改文件（业务代码 6 个，触 6 文件上限）

| # | 文件路径 | 改动类型 | 说明 |
|---|---------|---------|------|
| 1 | `frontend/src/types/stocks.ts` | 新增 | `StockSearchItem` + `WatchlistCreatedItem` 类型 |
| 2 | `frontend/src/lib/api/stocks.ts` | 新增 | `searchStocks(q, limit?)` API 封装 |
| 3 | `frontend/src/lib/api/watchlist.ts` | 修改 | 追加 `addStock()` / `removeStock()` mutation 函数 |
| 4 | `frontend/src/components/features/dashboard/AddStockCard.tsx` | 新增 | Input + Popover/Command 下拉 + add mutation |
| 5 | `frontend/src/components/features/dashboard/SignalCard.tsx` | 修改 | 右上角 Trash2 按钮 + AlertDialog + delete mutation |
| 6 | `frontend/src/pages/Dashboard.tsx` | 修改 | sidebar 占位替换为 `<AddStockCard />` |

**shadcn CLI 副产品（不计入 6 文件上限，参照 F001-b skeleton 先例）**：
- `frontend/src/components/ui/command.tsx`（`shadcn add command`）
- `frontend/src/components/ui/popover.tsx`（`shadcn add popover`）
- `frontend/src/components/ui/alert-dialog.tsx`（`shadcn add alert-dialog`）
- `frontend/src/components/ui/input.tsx`（如 shadcn add 连带安装）
- `frontend/src/components/ui/dialog.tsx`（alert-dialog 底层依赖，若 shadcn 连带安装）

👤 如用户认为 shadcn 副产品需计入上限，请在确认时指出，本次业务新建/修改才刚好=6。

---

## 设计偏离回写（规则 8）

F001-c 开发前需更新 `docs/设计/design-spec.md` 对应段落：

```markdown
> ⚠️ 实现偏离（2026-04-17，F001-c 开发期间）
> 原始设计（L104-L107）：
>   "结果唯一则直接 POST /api/watchlist；否则展示搜索结果下拉"
> 实际实现：
>   全部走下拉选择，不做"唯一结果自动添加"分支
> 原因：
>   交互一致性优先，避免用户输入同一 ticker 两次产生不同行为
>   （一次查到唯一直接添加，下次查到两条需点击）
```

此偏离也追加到 `docs/系统设计/DECISIONS.md` 作 D019。

---

## 可测试的完成标准

| # | 标准描述 | 测试层级 | 工具 |
|---|---------|---------|------|
| 1 | 空 Input 按 Enter 不触发搜索（网络无请求） | 手验 | Chrome DevTools Network |
| 2 | 输入"AAPL" + Enter → 下拉显示 AAPL 项（含 ticker / name / exchange） | 手验 | preview + Network |
| 3 | 搜索无结果（如输入 "ZZZZZZ"）→ 下拉显示"未找到匹配的股票" | 手验 | preview |
| 4 | 后端停掉后搜索 → 下拉显示错误 + 重试按钮 | 手验 | `pkill uvicorn` |
| 5 | 点击下拉项 → `POST /api/watchlist` 触发 → watchlist 新增该卡片 | 手验 | preview + Network |
| 6 | 添加已存在的 ticker（409）→ 下拉该项下方显示"该股票已在 watchlist" | 手验 | 重复添加 AAPL |
| 7 | 添加后 Input 清空 + 重新 focus | 手验 | preview |
| 8 | hover SignalCard → 右上角显示 Trash2 图标，移出时隐藏 | 手验 | preview |
| 9 | 点击 Trash2 → 弹出 AlertDialog，显示 "从 watchlist 中移除 AAPL？" | 手验 | preview |
| 10 | 点 AlertDialog 取消 → Dialog 关闭，卡片仍在 | 手验 | preview |
| 11 | 点 AlertDialog 删除 → `DELETE /api/watchlist/AAPL` → 卡片消失 | 手验 | preview + Network |
| 12 | Delete mutation 中卡片 opacity 0.5 + pointerEvents none | 手验 | preview（throttle） |
| 13 | 删除按钮点击不会同时触发 SignalCard 自身 onClick | 代码审查 | 看 `stopPropagation` |
| 14 | 所有颜色/间距只用 `--color-*` / `--spacing-*` token，无硬编码 hex/px | 代码审查 | grep `#` 硬编码 |
| 15 | `pnpm build` 零 TypeScript 错误 | 构建 | `pnpm build` |
| 16 | AddStockCard 响应式在 sidebar 158px 宽度下布局正常 | 手验 | preview |
| 17 | 搜索 Popover 宽度 ≥ Input 宽度（保证 ticker/name 可读） | 手验 | preview inspect |

---

## Evaluator 自检清单

开发完成后，Evaluator 模式逐条检查：

- [ ] pnpm build 通过（零 TS 错误）
- [ ] 17 条完成标准全部手验通过
- [ ] API 请求路径 `/api/stocks/search` / `/api/watchlist` / `/api/watchlist/:ticker` 正确
- [ ] 响应解析符合 API-CONTRACT.md 的 `{ data, error }` 信封
- [ ] 字段命名严格对照：`ticker`/`name`/`exchange`/`addedAt`/`dataStatus`/`latestSignal`（camelCase，DATA-MODEL.md 权威）
- [ ] 无 console.error 遗留
- [ ] 无硬编码颜色（grep 检查 `#` + 6 位 hex）
- [ ] 所有错误态有用户可理解的中文提示
- [ ] Delete 按钮 `stopPropagation` 正确
- [ ] design-spec.md L104-L107 偏离已回写
- [ ] DECISIONS.md 已追加 D019（搜索交互偏离）+ D020（shadcn command/popover/alert-dialog 依赖）
- [ ] 代码质量：无死代码、无魔法值（debounce 时长/limit 值提取常量）、函数 ≤50 行

---

👤 用户确认本 Contract 后，进入 Generator 模式。
   开发前第一步：通过 context7 查询 shadcn/ui Combobox + AlertDialog 最新用法。
