# Sprint Contract：F214 — Chart Widget "Add to Watchlist" 按钮

> 状态：已确认 | 起草：2026-05-08 | 确认：2026-05-08
> Feature：F214 ChartWidget Add to Watchlist
> 依赖：
>   - 现成 `addStock(ticker)` API（`src/lib/api/watchlist.ts`，POST /api/watchlist）
>   - 现成 `useQuery(['signals'])` 数据（ChartWidget 已用其取 companyName）
>   - 现成错误码映射约定（参 AddStockCard：DUPLICATE / NOT_FOUND）
>   - lucide-react `CirclePlus` / `Loader2` 图标
> 引用文档：
>   - API-CONTRACT.md §POST /api/watchlist
>   - design-spec.md（ChartWidget 章节将在完成后追加按钮交互注记）
>   - features.json#F214 acceptance_criteria

---

## 0. 背景与定位

News 页和 Workbench 页共用同一个 `ChartWidget` 组件（`WidgetRegistry.ts:26 / :76`）。当用户在 News 上看到一只感兴趣的票时，需要切到 Workbench 页 → 用 AddStockCard 搜索 → 添加到 watchlist。流程冗长。

F214 在 ChartWidget 右下角加一个"+"按钮，直接把当前 chart 的 ticker 加入 watchlist。因为两页共用同一组件，按钮在两页都出现（用户已确认方案 1A），Workbench 上同样是个有用的快捷操作。

**关键约束**：

1. **修改最小化**：仅改 `ChartWidget.tsx` 一个文件（含可选的同目录测试）
2. **不动后端**：复用现成 `POST /api/watchlist`
3. **不动共享 store / 不改 useAppStore**
4. **零成本判定"已在 watchlist"**：复用 ChartWidget 已经在调的 `useQuery(['signals'])`，`signals.some(s => s.ticker === symbol)` 即可判定
5. **不引入新依赖**：lucide-react 已有 `CirclePlus`，react-query / addStock 都现成

---

## 1. 实现范围

### 1.1 包含

- 在 `ChartWidget` 主返回 div（`position: relative` wrapper）右下角浮一个圆形按钮
- 按钮 icon 为 lucide-react `CirclePlus`（idle / hover）/ `Loader2` 旋转（pending）
- 点击调用 `addStock(symbol)` mutation
- 已在 watchlist（symbol 存在于 signals 列表）时，按钮 disabled，title="已在 watchlist"
- 成功后 invalidate `['signals']` 和 `['watchlist']` 两个 query key（沿用 AddStockCard 模式），按钮基于 signals 重新判定后自动变 disabled
- 失败映射：DUPLICATE → "该股票已在 watchlist"；NOT_FOUND → "股票代码无效"；其他 → "添加失败，请重试"
- 错误展示方式：按钮短暂显示错误状态（推荐：button 的 `title` 属性写错误文案 + button 边框变红 / icon 变红 ~3s 自动恢复 idle；不弹 toast）

### 1.2 排除

- 不弹成功 toast（按钮变 disabled 即反馈，已和用户确认）
- 不加 prop 控制可见性（两页都显示）
- 不改 News.tsx / Workbench / WatchlistWidget / useAppStore
- 不改 PriceChart.tsx（按钮浮在 ChartWidget 的 wrapper div 上，不进入 chart 内部）
- 不修改 DATA-MODEL / API-CONTRACT
- 不引入新外部依赖
- symbol === null 时不渲染按钮（沿用 EmptySymbol 早返回路径）

---

## 2. 预计修改文件清单

**核心修改（1 个）**：
- `frontend/src/workbench/widgets/ChartWidget.tsx`（修改）

**新增测试（1 个，可选但推荐）**：
- `frontend/src/workbench/widgets/__tests__/ChartWidget.test.tsx`（新建）

**总计**：2 个文件，远低于 6 文件上限。

> 备注：仓库内 `frontend/src/cockpit/widgets/__tests__/CockpitChartWidget.test.tsx` 已有 widget 测试样例可参照；如运行后发现项目未配置 vitest 对 workbench 目录的测试 setup，则将测试文件改放到与 CockpitChartWidget 测试同模式的目录。Generator 阶段以实际 vitest 配置为准。

---

## 3. 完成标准（可测试）

| # | 标准 | 测试层级 | 工具 |
|---|------|---------|------|
| 1 | symbol 存在且未在 signals 列表时，按钮可点击且 enabled | 单元 | Vitest + RTL，mock useQuery |
| 2 | symbol 已在 signals 列表时，按钮 disabled，title 含"已在 watchlist" | 单元 | Vitest + RTL |
| 3 | 点击按钮触发 `addStock(symbol)`，pending 期 icon 替换为 Loader2 | 单元 | Vitest + RTL，mock api |
| 4 | 成功后调用 `queryClient.invalidateQueries({ queryKey: ['signals'] })` 和 `['watchlist']` | 单元 | Vitest spy on QueryClient |
| 5 | 错误码 DUPLICATE 时按钮显示 "已在 watchlist" 错误态文案 | 单元 | Vitest + RTL，mock ApiError |
| 6 | 错误码 NOT_FOUND 时按钮显示 "股票代码无效" 文案 | 单元 | 同上 |
| 7 | symbol === null 时整个 ChartWidget 走 EmptySymbol 分支，按钮不渲染 | 单元 | Vitest + RTL |
| 8 | 视觉：按钮在 widget 右下角，z-index 高于 chart 不被价格刻度遮挡 | 人工 | 浏览器 5173 |
| 9 | News 页和 Workbench 页都能看到按钮且行为一致 | 人工 | 浏览器 5173 |

---

## 4. Evaluator 自检清单

### 功能测试
- [ ] 标准 1-7 全部通过（vitest 对应文件全绿）
- [ ] 标准 8-9 浏览器手验通过

### 全量回归
- [ ] `pnpm --filter frontend test`（或项目实际命令）通过，无新增失败
- [ ] 现有 ChartWidget 在 Workbench / News 页其他场景不受影响（symbol 切换、loading、error 路径）

### 代码质量
- [ ] `pnpm --filter frontend lint` 通过，无新 warning
- [ ] 颜色 / 间距 / 字号严格使用 tokens.css CSS 变量，无硬编码
- [ ] 无新增 console.error / console.warn
- [ ] 无死代码、无重复逻辑（错误码映射可参考 AddStockCard 提取，也可内联，单文件内联即可）
- [ ] 函数 < 50 行，单文件改动控制在合理范围

### 文档同步
- [ ] DECISIONS.md：本 sprint 无新决策，**不写**
- [ ] design-spec.md：在 ChartWidget 章节追加一段 "右下角 Add to Watchlist 按钮交互" 说明（含 idle / disabled / pending / error 四种状态）
- [ ] API-CONTRACT.md：无变更
- [ ] DATA-MODEL.md：无变更

### 视觉
- [ ] icon 大小 18-20px（与 widget 视觉协调，参考 WatchlistWidget 的 14-20px 区间）
- [ ] 按钮位置 `position: absolute; right: 8px; bottom: 8px`（如视觉冲突可微调，但不能与 lightweight-charts 的 watermark 或价格刻度重叠）
- [ ] hover / disabled / pending / error 四态视觉清晰可辨

---

## 5. 实现要点（给 Generator 参考）

### 文件位置与挂点
- 唯一改动文件：`frontend/src/workbench/widgets/ChartWidget.tsx`
- 按钮挂在已有 `position: relative` 的 wrapper div（`ChartWidget.tsx:51`），与 symbol/companyName label 平级，但定位在右下角

### 状态判定（无新 query）
```ts
// 复用现有 signals query
const isInWatchlist = signals?.some((s) => s.ticker === symbol) ?? false
```

### Mutation
```ts
const queryClient = useQueryClient()
const [errorMsg, setErrorMsg] = useState<string | null>(null)
const addMutation = useMutation({
  mutationFn: () => addStock(symbol!),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['signals'] })
    queryClient.invalidateQueries({ queryKey: ['watchlist'] })
    setErrorMsg(null)
  },
  onError: (err) => {
    const code = err instanceof ApiError ? err.code : 'UNKNOWN'
    if (code === 'DUPLICATE') setErrorMsg('该股票已在 watchlist')
    else if (code === 'NOT_FOUND') setErrorMsg('股票代码无效')
    else setErrorMsg('添加失败，请重试')
    // 3s 后清错（用 setTimeout 或 useEffect 清理）
  },
})
```

### 视觉规范
- 按钮容器：`position: absolute; right: 8px; bottom: 8px; zIndex: 2`
- icon 颜色：idle = `var(--color-text-secondary)`；hover = `var(--color-primary)` 或 token 中已有的强调色；disabled = 半透明；error = `var(--color-error)`
- 不写硬编码 hex（除非现有 ChartWidget 已经在用如 `#f59e0b` MA5 那种约定色，这种走原有约定）

### 测试样例骨架
参照 `frontend/src/cockpit/widgets/__tests__/CockpitChartWidget.test.tsx` 的 mock 方式，需要 mock：
- `useAppStore`（提供 selectedSymbol）
- `getSignals` API（提供含/不含目标 ticker 的 signals 列表）
- `getStockChart` API（避免真实网络）
- `addStock` API（success / DUPLICATE / NOT_FOUND / 通用 error）

---

## 6. 开发顺序（Generator 阶段，不得跳步）

1. 读取 `frontend/src/workbench/widgets/ChartWidget.tsx` 当前内容（已经在 contract 阶段读过，Generator 阶段重读确认无 drift）
2. 读取 `frontend/src/components/features/dashboard/AddStockCard.tsx`（错误码映射模式）
3. 在 ChartWidget 内加入 button 组件 + mutation，遵循上方实现要点
4. 运行 vitest，确认无回归（先跑现有测试套件）
5. 新建 `__tests__/ChartWidget.test.tsx`，写标准 1-7 的 7 个用例
6. 运行新测试，确保 7/7 通过
7. 浏览器手验：News 页和 Workbench 页各检查一次（标准 8-9）
8. lint 通过
9. 全量回归 `pnpm test` 通过
10. 更新 design-spec.md 的 ChartWidget 章节
11. WIP commit（按 step 粒度，禁用 `git add -A`）
12. Evaluator 自检 → 全清后切 needs_review，调用 consistency-check (mode=interactive)

---

## 7. 风险与对策

| 风险 | 对策 |
|------|------|
| signals query 还在 loading 时 isInWatchlist 误判为 false → 用户点了之后才走 DUPLICATE 错误 | 可接受。signals 通常 30s 内有缓存（`staleTime: 30 * 1000`），重复打开 ChartWidget 时立即可用；首次加载短暂的"按钮可点"窗口期靠后端 DUPLICATE 错误兜底 |
| Workbench 上按钮和已有 WatchlistWidget 功能重叠 | 用户确认接受（方案 1A），且交互入口不同，没有冲突 |
| lightweight-charts 的 price scale 在右侧，按钮 right: 8px 可能压在价格数字上 | Generator 阶段浏览器目检，必要时调整为 right: 48px（让出 price scale 宽度），或改为 left-bottom 位置 |
| 现有 widget 测试 setup 是否覆盖 workbench/widgets/__tests__ | Generator 阶段先跑一遍 vitest 确认；若未覆盖，沿用 cockpit 模式新增配置或换目录 |

---

## 8. 不在本 sprint 范围

- 删除按钮（reverse 操作）：用户已经能在 WatchlistWidget 删除，不重复
- 批量加入：现有 CSV 导入已覆盖
- 跨 symbol 一键加入（如 NewsWidget 文章里点 ticker 直接加 watchlist）：另行评估，超出本 sprint
- 国际化 i18n：项目尚未引入 i18n 框架，沿用现有中文硬文案
