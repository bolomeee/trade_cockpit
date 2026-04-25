# Sprint Contract：F200-a — Cockpit 前端骨架（路由 + RGL 容器 + Stores）

> 状态：草案 | 起草：2026-04-24
> 父 Feature：F200 Cockpit 页面框架
> 兄弟：F200-b（TopNav 接入 + 后端目录占位，独立 Sprint）
> 引用文档：
>   - ARCHITECTURE.md §前端依赖层级 + §目录结构约定
>   - design-spec.md §Cockpit 全局结构 + §Cockpit 网格规格 + §默认布局
>   - component-plan.md §Cockpit-2（组件清单）+ §Cockpit-3（组件边界）
>   - DECISIONS.md D060（Cockpit 独立第三页）+ D060-a（沿用 RGL 引擎）+ **D070（本 Sprint 落地：Pydantic 参数约定）**

---

## 0. 背景与定位

F200 Cockpit 页面框架预计总文件数 8–9（超 6 文件上限），按 A-1 规则拆分为：

- **F200-a（本 Sprint，6 文件）**：前端路由 + RGL 容器 + 两套 store + 占位 widget；可通过直接访问 `/cockpit` 验证拖拽/缩放/持久化
- **F200-b（后续 Sprint）**：TopNav 加 Cockpit 入口 + ResetLayout 条件渲染 + backend `routers/cockpit/` / `services/cockpit/` 空目录占位

F200-a 完成后，功能上"能访问 `/cockpit`、看到 RGL 网格、拖拽/缩放/刷新后布局保留"；但 TopNav 上还没有 Cockpit 链接（需要知道 URL 直接访问）。这是**有意拆分**，不是遗漏。

---

## 1. 实现范围

### 1.1 路由入口

新文件 `frontend/src/pages/Cockpit.tsx`：
- 与 `workbench/Workbench.tsx` / `pages/News.tsx` 模式一致
- 只做 lazy load 包装 + 渲染 `<CockpitShell />`
- 不做数据获取、不订阅 store

`frontend/src/App.tsx` **修改**：
- 顶部 `const Cockpit = lazy(() => import('@/pages/Cockpit'))`
- Routes 新增 `<Route path="/cockpit" element={<Cockpit />} />`

### 1.2 CockpitShell（RGL 容器）

新文件 `frontend/src/cockpit/CockpitShell.tsx`：
- 复刻 `workbench/Workbench.tsx` 模式（react-grid-layout + useContainerWidth + verticalCompactor）
- 网格参数按 design-spec §Cockpit 网格规格：`cols=12, rowHeight=40, margin=[12, 12]`（注：Workbench 当前用 `[6, 6]`，Cockpit 按 design-spec 要求用 `[12, 12]`；design-spec 明确 Cockpit 与 Workbench 视觉一致但 margin 走规格值，以规格为准）
- 每个 widget 外层 wrap 一个**内联的最小 frame**（36px 标题栏 + `.widget-handle` 类 + 内容区），**不引入** WidgetShell 组件（D060 约束下暂不做 shared 提取，留给 F200-b 或后续 cockpit widget feature 落地时统一决策）
- 标题栏背景 `#ebf2fa`，padding 规范沿用 v1.1 WidgetShell 规格
- `handleChange`：接 `onLayoutChange` → `setLayout`
- 初次挂载 layout 为空数组时注入 `getCockpitDefaultLayout()`

### 1.3 CockpitRegistry

新文件 `frontend/src/cockpit/CockpitRegistry.ts`：
- 导出 `type CockpitWidgetCategory = 'regime' | 'setup' | 'decision' | 'chart' | 'earnings' | 'position' | 'pool' | 'action'`
- 导出 `type CockpitWidgetManifest = { id, title, component, defaultLayout: Omit<LayoutItem,'i'>, category }`
- 导出 `COCKPIT_WIDGET_REGISTRY: Record<string, CockpitWidgetManifest>`
- **F200-a 只注册 1 个占位 widget**：
  ```ts
  'cockpit.placeholder': {
    id: 'cockpit.placeholder',
    title: 'Cockpit Placeholder',
    component: PlaceholderWidget,
    defaultLayout: { x: 0, y: 0, w: 4, h: 8, minW: 3, minH: 4 },
    category: 'regime',
  }
  ```
  F201 时替换为 MarketRegimeWidget，后续每个 cockpit feature 追加 manifest
- 导出 `getCockpitDefaultLayout(): LayoutItem[]` — 遍历 manifest 生成
- **不 import** `workbench/WidgetRegistry.ts`（ESLint 已有 no-restricted-imports 或将于 F200-b 加；本 Sprint 代码层面保证隔离）

### 1.4 useCockpitLayoutStore（布局持久化 store）

新文件 `frontend/src/cockpit/useCockpitLayoutStore.ts`：
- 与 `workbench/useLayoutStore.ts` 镜像：zustand + persist
- localStorage key：`ma150.cockpit.layouts.v1`，version=1
- API：`layout / setLayout / reset(defaultLayout)`
- **不 import** useAppStore / useLayoutStore

### 1.5 cockpitStore（cockpit 范围内 client state）

新文件 `frontend/src/store/cockpitStore.ts`：
- 放在 `store/` 目录与 `useAppStore.ts` 并列（遵循 ARCHITECTURE.md 目录结构约定）
- zustand（**无 persist**，运行时内存态）
- F200-a 只落 `selectedTicker: string | null` + `setSelectedTicker(t: string | null)`
- 预留 shape 让 F201+ 后续追加（`selectedSetup / mas / timeframe` 等）但本 Sprint **不实现**
- **不 import** useAppStore

### 1.6 占位 Widget

新文件 `frontend/src/cockpit/widgets/PlaceholderWidget.tsx`：
- 最简实现：居中文字 "Cockpit 骨架 ✓ 拖我 / 改尺寸 / 刷新保留"
- 文字色 `var(--color-text-secondary)`
- 无数据获取、无 store 订阅
- F201 开发时此文件可删除（manifest 里换成 MarketRegimeWidget）

---

## 2. 预计修改文件（共 6 个，达到 6 文件上限）

| # | 文件 | 类型 | 说明 |
|---|------|------|------|
| 1 | `frontend/src/pages/Cockpit.tsx` | 新建 | 路由入口，lazy 包装 CockpitShell |
| 2 | `frontend/src/cockpit/CockpitShell.tsx` | 新建 | RGL 容器 + 内联 widget frame + 默认布局注入 |
| 3 | `frontend/src/cockpit/CockpitRegistry.ts` | 新建 | widget manifest + getCockpitDefaultLayout |
| 4 | `frontend/src/cockpit/useCockpitLayoutStore.ts` | 新建 | zustand + persist（key: ma150.cockpit.layouts.v1） |
| 5 | `frontend/src/store/cockpitStore.ts` | 新建 | zustand 运行时 state（selectedTicker） |
| 6 | `frontend/src/cockpit/widgets/PlaceholderWidget.tsx` | 新建 | 最小占位，F201 时替换 |

**不计入 6 文件的额外改动**：
- `frontend/src/App.tsx` — 新增 `/cockpit` 路由（1 行 import + 1 行 Route，视作"接入"不是"实现"；但下述 Evaluator 会审到）
- `docs/系统设计/DECISIONS.md` — 追加 **D070**（Cockpit 参数管理约定：Pydantic BaseModel + description + range validator + 单一 `cockpit_params.py`）
- `docs/需求/features.json` — F200 拆分为 F200-a / F200-b；F200-a phase 推进至 `contract_agreed` → `in_progress` → `needs_review`
- `claude-progress.txt` — Sprint 条目

> App.tsx 计入第 7 文件会超限。基于 D010（脚手架例外豁免）精神，本 Sprint 对 App.tsx 的改动**仅限 2 行**（lazy import + Route），视作"路由表登记"，豁免计入 6 文件。若未来 App.tsx 改动 >5 行，立即拆回 F200-b。

---

## 3. D070 预定稿（与本 Contract 一起确认）

```markdown
## D070：Cockpit 参数管理用 Pydantic BaseModel 单文件集中

时间：2026-04-24（F200-a 起草同步确定）

### 决策
Cockpit 所有算法阈值 / 权重 / 规则参数（F201–F211）统一落到 `backend/app/services/cockpit/cockpit_params.py`，用 Pydantic v2 `BaseModel` 组织，每个字段必须带 `Field(description=..., ge=..., le=...)`；文件内按 feature 分 section，命名前缀 `REGIME_* / SETUP_* / DECISION_* / EARNINGS_* / SHARED_*`。

### 不做
- 不做 .env 覆盖、不做 DB 读取、不做运行时热更新 — 改参数仍是"改代码重启"
- 不做 YAML / JSON 配置文件
- 不做 admin UI

### 不进这个文件的参数
- cron 时间（REGIME_CRON_* 等）→ `.env`
- user_settings 4 字段（account_size / max_exposure_pct / ...）→ DB 表
- AI 模型名 / 预算 / memo TTL → `.env`（ARCHITECTURE.md 已定）
- 前端默认布局 / debounce → 前端代码

### 理由
- 集中常量 → 调参 / 审计 / 测试断言只改一处
- Pydantic 结构化 → 启动时自动校验阈值范围，且为未来可视化预留 schema
- 单文件 → 跨 feature 共享常量零冗余

### 先例
D045 scanner_params.py 是同款模式（但为纯 Python 常量，不带 Pydantic）

### Evaluator 强制检查（写入每个 F201–F204 Sprint Contract 自检）
- [ ] service 代码内无魔法数字 / 字符串字面量阈值
- [ ] 所有阈值通过 `from app.services.cockpit.cockpit_params import X` 引入
- [ ] 每个 cockpit_params.py 内新加字段必带 description + range
- [ ] 启动时 Pydantic 校验通过
```

### 关于 F200-a 本身是否建 `cockpit_params.py`

**不建**。F200-a 纯前端骨架，**零后端参数**。`cockpit_params.py` 由 **F201 Sprint** 首次创建（§0 SHARED 部分 + §1 F201 REGIME 部分同时落地）。本 Sprint 只**立规矩**（D070），不**起文件**。

---

## 4. 完成标准（可测试）

| # | 标准 | 层级 | 工具 |
|---|------|------|------|
| 1 | `pnpm build` 通过，无 TS error / ESLint error | 编译 | pnpm |
| 2 | `pnpm dev` 启动后直接访问 `http://localhost:5173/cockpit` 渲染出 RGL 网格 + 占位 widget | 手动 E2E | preview_* 工具 |
| 3 | 拖动占位 widget 到新位置，刷新页面后位置保留 | 手动 E2E | preview_* 工具 |
| 4 | resize 占位 widget 到新尺寸，刷新页面后尺寸保留 | 手动 E2E | preview_* 工具 |
| 5 | 清空 `localStorage.ma150.cockpit.layouts.v1` 后刷新，回到默认布局 | 手动 E2E | preview_eval |
| 6 | `localStorage.ma150.workbench.layouts.v5` 不被 cockpit 读写（反之亦然）：在 /cockpit 拖动后 workbench key 的值字节级未变化 | 手动 E2E | preview_eval |
| 7 | `cockpitStore.setSelectedTicker('NVDA')` 不会改变 `useAppStore` 的任何字段（分别读取确认独立） | 手动 E2E | preview_eval |
| 8 | 其他路由（`/` / `/news` / `/journal` / `/logs`）渲染与 F200-a 前一致，无回归 | 回归 | preview_snapshot + 目测 |

单元测试本项目前端无 Jest/Vitest 基建（D048 延迟），不强求；**但**下列断言通过代码阅读与 preview_eval 人工确认：

| # | 自证逻辑 | 验证方式 |
|---|---------|---------|
| U1 | `getCockpitDefaultLayout()` 长度 = `Object.keys(COCKPIT_WIDGET_REGISTRY).length` | 阅读 + preview_eval 在 DevTools 跑 |
| U2 | `useCockpitLayoutStore.reset(default)` 调用后 `layout` 等于 default | preview_eval |
| U3 | cockpitStore 订阅不污染 useAppStore：两个 store 实例各自独立 | 阅读 import 树 |

---

## 5. Evaluator 自检清单

- [ ] 6 个新文件全部存在，路径与表 2 一致
- [ ] `pnpm build` 零 error
- [ ] `cockpit/CockpitShell.tsx` 的 import 列表**不含** `@/workbench/*`、`@/store/useAppStore`、`@/hooks/useRefreshStatus`
- [ ] `cockpit/CockpitRegistry.ts` 的 import 列表**不含** `@/workbench/*`
- [ ] `cockpit/useCockpitLayoutStore.ts` 的 import 列表**不含** `@/workbench/useLayoutStore`、`@/store/useAppStore`
- [ ] `store/cockpitStore.ts` 的 import 列表**不含** `@/store/useAppStore`、`@/workbench/*`
- [ ] localStorage key 字符串精确等于 `ma150.cockpit.layouts.v1`（grep 确认）
- [ ] 所有新文件颜色/间距/字体走 `var(--…)` token，无 hex 硬编码（允许 WidgetShell 标题底色 `#ebf2fa` 按 D046 豁免）
- [ ] 路由 `/cockpit` 从 App.tsx 可达
- [ ] DECISIONS.md 追加 D070 完整内容
- [ ] features.json 拆分 F200 为 F200-a / F200-b，F200-a phase 推进
- [ ] claude-progress.txt 追加 Sprint 条目
- [ ] 回归：其他 4 个路由在 preview 下渲染与改动前一致
- [ ] 无 `console.log` / `console.error` 遗留

### 代码质量检查

- [ ] 无死代码（未用 import / 未调用函数）
- [ ] 无硬编码魔法值（网格配置通过常量对象暴露，而非散落）
- [ ] `PlaceholderWidget` 代码 <30 行，无多余抽象
- [ ] 所有 zustand store 类型完整，无 `any`

### 回归测试

前端无自动测试套件 → 手动对 4 个既有路由逐个走一遍 smoke 路径：
- `/` Workbench 打开，拖动 WatchlistWidget，刷新后位置保留（证明 `ma150.workbench.layouts.v5` 未被污染）
- `/news` 打开列表有内容
- `/journal` 列表渲染
- `/logs` 列表渲染

---

## 6. 非目标（明确不做，留给 F200-b 或后续）

- TopNav Cockpit 入口（F200-b）
- TopNav ResetLayout 条件渲染（仅 /cockpit 可见）（F200-b）
- TopNav 齿轮按钮（F203 UserSettingsDialog 时再加）
- MarketOverviewBar 在 /cockpit 的显隐决策（design-spec 默认三页都显示 SPX/NDX/TNX，本 Sprint 沿用既有 App.tsx 无改动）
- ESLint `no-restricted-imports` rule 加强（F200-b 或后续专项 Sprint；本 Sprint 靠人眼 + Evaluator 审）
- shared WidgetShell 提取（任何 cockpit widget feature 首次需要时再决策：提 shared / 复制 / inline）
- backend `routers/cockpit/` / `services/cockpit/` 目录占位（F200-b）
- `cockpit_params.py` 首次落地（F201-a）

---

## 7. 开发顺序

1. `useCockpitLayoutStore.ts` + `cockpitStore.ts`（两个 store，互不依赖，可先写）
2. `CockpitRegistry.ts` + `PlaceholderWidget.tsx`（manifest 需要 widget 组件引用）
3. `CockpitShell.tsx`（组合上述三者，核心 RGL 逻辑）
4. `pages/Cockpit.tsx`（lazy 包装）
5. `App.tsx` route 登记
6. `pnpm dev` + preview 手动 E2E 跑完 8 条完成标准
7. 文档：DECISIONS.md D070 / features.json / claude-progress.txt
8. Evaluator 模式走完自检清单 → `git add -A && git commit -m "feat(F200-a): Cockpit 前端骨架（路由 + RGL + stores）"`

---

## 8. 风险与取舍

- **RGL margin `[12, 12]` vs Workbench `[6, 6]`**：design-spec 明确 Cockpit 用 `[12, 12]`。这会让 Cockpit 视觉密度略低于 Workbench。确认保持，不动 Workbench。
- **占位 widget 的必要性**：没有占位的话，空 registry 导致 RGL 挂不出东西，E2E 无法验证拖拽/缩放。PlaceholderWidget 存在至 F201 落地时**删除**，不是长期资产。
- **App.tsx 的 2 行改动豁免 6-文件**：基于 D010 脚手架豁免精神；一旦 App.tsx 需要改动超过 10 行，立即回退到 F200-b。
- **D060 cross-import 零 enforce**：本 Sprint 仅靠 Evaluator 人眼审 + grep。真正的 ESLint 规则放 F200-b（需要改 eslint.config.js，单独 1–2 文件成本）。
- **WidgetShell 不提取**：component-plan.md 提到"WidgetShell 共享跨页"是目标态；F200-a 采用 inline frame 而非强行提 shared，避免牵连 workbench 文件改动。首个真实 cockpit widget（F201 MarketRegime）落地时再决策是提 `components/widgets/WidgetShell.tsx` 还是 `cockpit/CockpitWidgetShell.tsx`。

---

👤 请确认：
1. 6 文件清单 + App.tsx 2 行豁免 → OK？
2. D070 内容（Pydantic + 单文件 + 不做热更新 / YAML / UI）→ OK？
3. margin `[12, 12]` 按 design-spec 不与 Workbench 对齐 → OK？
4. PlaceholderWidget 作为临时占位，F201 时删除 → OK？

全部 OK 后，我把 F200 拆成 F200-a/F200-b 写进 features.json，phase 推进到 `contract_agreed`，进入 Generator 模式开始写代码。
