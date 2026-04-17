# Sprint Contract：F000-b 前端脚手架 + 路由基座

> 日期：2026-04-17 | 状态：草案（待确认）
> 引用文档：
>   ARCHITECTURE.md#前端 · ARCHITECTURE.md#目录结构约定 · component-plan.md#路由容器 · design-spec.md#全局布局 · features.json#F000-b
> 豁免：DECISIONS D010（脚手架 6 文件规则豁免，F000-b 明确覆盖）

---

## 本次实现范围

**包含**：
- `frontend/` 目录初始化：Vite 6 + React 18 + TypeScript 5
- Tailwind CSS v4 通过 `@tailwindcss/vite` 插件接入（无 tailwind.config.ts / 无 postcss.config）
- `@import "tailwindcss"` + 引入 `tokens.css` 作为设计变量来源
- 将项目根 `src/styles/tokens.css` **移动**至 `frontend/src/styles/tokens.css`（权威位置对齐 ARCHITECTURE.md），并删除孤立的根 `src/` 目录
- `react-router-dom` v6：BrowserRouter + Routes，3 路由 `/`、`/journal`、`/logs`
- 3 个空页面组件 `Dashboard.tsx` / `Journal.tsx` / `Logs.tsx`（只渲染 `<h1>` 占位 + 一个 shadcn Button 演示放在 Dashboard）
- shadcn/ui 接入（`shadcn init -t vite` 非交互式 + `add button`）、生成 `components.json`、路径别名 `@/` 经 Vite + TS 配置
- `frontend/.gitignore` · `frontend/.env.example` · `frontend/README.md` 不新建（CLAUDE.md 规范无要求）

**明确排除（本次不做）**：
- react-query / TanStack Query 安装与 QueryClientProvider（留待 F001 首次用时引入）
- TopNav / MarketOverviewBar 等任何业务 Widget（component-plan 里的业务组件都不做）
- 任何 API service 层、hooks、types（留到对应 feature）
- Dockerfile / nginx.conf（归属 F000-c）
- 单元测试框架（Vitest）配置（本脚手架不写测试代码，脚手架验收以 "pnpm dev + 浏览器访问" 为主）
- lightweight-charts、react-day-picker 等功能库（留到对应 feature）

---

## 预计修改文件

> 本 Sprint 受 D010 脚手架例外覆盖，不触发 6 文件硬规则。
> 自动生成的锁文件（`pnpm-lock.yaml`）和依赖安装后的 `node_modules` 不列入。

| 文件路径 | 改动类型 | 说明 |
|---------|---------|------|
| `frontend/package.json` | 新增 | Vite + React 18 + TS + Tailwind v4 + react-router-dom + shadcn 依赖声明 |
| `frontend/pnpm-lock.yaml` | 新增（自动） | pnpm 生成 |
| `frontend/vite.config.ts` | 新增 | `@tailwindcss/vite` 插件 + `@/` 路径别名 + React 插件 |
| `frontend/tsconfig.json` | 新增 | Vite 脚手架默认（引用 app + node） |
| `frontend/tsconfig.app.json` | 新增 | `baseUrl` + `paths: {"@/*": ["./src/*"]}` |
| `frontend/tsconfig.node.json` | 新增 | Vite 默认 |
| `frontend/index.html` | 新增 | 根 HTML，挂载 `#root` |
| `frontend/components.json` | 新增 | shadcn 配置（style `new-york` / baseColor `neutral` / cssVariables `true` / `@/` 别名） |
| `frontend/.gitignore` | 新增 | node_modules / dist / .env 等 |
| `frontend/src/main.tsx` | 新增 | `createRoot` + `<BrowserRouter><App /></BrowserRouter>` + 引入 `index.css` |
| `frontend/src/App.tsx` | 新增 | `<Routes>` 挂载 3 路由 |
| `frontend/src/index.css` | 新增 | `@import "tailwindcss";` + `@import "./styles/tokens.css";` |
| `frontend/src/styles/tokens.css` | 移动 | 从项目根 `src/styles/tokens.css` 移入 |
| `frontend/src/pages/Dashboard.tsx` | 新增 | `<h1>Dashboard</h1>` + 一个 shadcn `<Button>Hello</Button>` |
| `frontend/src/pages/Journal.tsx` | 新增 | `<h1>Journal</h1>` |
| `frontend/src/pages/Logs.tsx` | 新增 | `<h1>Logs</h1>` |
| `frontend/src/lib/utils.ts` | 新增 | shadcn 的 `cn()` 辅助函数（clsx + tailwind-merge） |
| `frontend/src/components/ui/button.tsx` | 新增（由 shadcn CLI 生成） | Button 组件 |
| `src/styles/tokens.css` | 删除 | 已移动到 frontend/ |
| `src/styles/`（空目录） | 删除 | 连带清理 |
| `src/`（空目录） | 删除 | 连带清理 |
| `docs/系统设计/DECISIONS.md` | 修改 | 追加 D011（Tailwind v4 放弃 tailwind.config.ts，改用 Vite 插件 + CSS import） |
| `docs/需求/features.json` | 修改 | F000-b 填写 `estimated_files_changed` + phase 推进 |
| `claude-progress.txt` | 修改 | 追加 Sprint 日志 |

👤 用户确认文件列表合理后，方可进入开发。

---

## 可测试的完成标准

脚手架性质 Sprint，以 "dev server 启动 + 手动浏览器验证" 为主，不写单元/E2E 测试。

| # | 标准描述 | 测试层级 | 工具 |
|---|---------|---------|------|
| 1 | `cd frontend && pnpm install` 无错误 | 手动 | pnpm |
| 2 | `pnpm dev` 成功启动 Vite，输出 `http://localhost:5173` 可访问，无构建错误无 TypeScript 错误 | 手动 | Vite HMR |
| 3 | `pnpm build` 成功生成 `dist/`，无类型错误 | 手动 | tsc + Vite |
| 4 | 浏览器访问 `/` 渲染 `<h1>Dashboard</h1>` + 一个可见的 shadcn Button（样式来自 shadcn，非原生按钮） | 手动 | 浏览器 |
| 5 | 访问 `/journal` 渲染 `<h1>Journal</h1>` | 手动 | 浏览器 |
| 6 | 访问 `/logs` 渲染 `<h1>Logs</h1>` | 手动 | 浏览器 |
| 7 | Dashboard 页面上加一个 `className="text-red-500"` 的元素验证 Tailwind v4 生效（文字变红） | 手动 | 浏览器 |
| 8 | Dashboard 页面上加一个 `style={{ color: 'var(--color-signal-breakout)' }}` 元素验证 tokens.css 生效（文字显示蓝色 `#2962ff`） | 手动 | 浏览器 DevTools |
| 9 | `@/pages/Dashboard` 等 `@/` 别名导入在 Vite 和 tsc 下均解析正常 | 手动 | tsc --noEmit |
| 10 | 路由跳转后 URL 正确改变，且浏览器刷新当前路由不白屏 | 手动 | 浏览器 |

第 7–9 条所用的 demo 元素在验收通过后可以删除或保留为占位，由 Generator 判断。

---

## Evaluator 自检清单

开发完成后，Evaluator 模式逐条检查：

- [ ] `pnpm install` 干净通过
- [ ] `pnpm dev` 启动无错误，终端无红字 warning（deprecation warning 除外）
- [ ] `pnpm build` 通过，无 TS 错误
- [ ] 3 个路由逐个访问均正确渲染
- [ ] Tailwind v4 工作（任一 utility class 生效）
- [ ] tokens.css 变量可在 JSX 里通过 `var(--color-*)` 引用并渲染
- [ ] shadcn Button 成功渲染且有 shadcn 原生样式（非 UA 默认按钮）
- [ ] `@/` 路径别名在 Vite 运行时 + `tsc --noEmit` 下均工作
- [ ] `frontend/` 目录结构对齐 ARCHITECTURE.md（pages / components / hooks / services / lib / styles / types；脚手架阶段只需创建已用到的目录）
- [ ] 浏览器 DevTools Console 无 error（warning 若为库自身 deprecation 允许保留）
- [ ] D011 已追加到 DECISIONS.md（若最终采用 Vite 插件方案）
- [ ] `claude-progress.txt` 已追加本 Sprint 条目
- [ ] features.json 的 F000-b phase 从 `contract_agreed` → `in_progress` → `testing` → `needs_review` 按阶段更新
- [ ] 项目根 `src/` 目录已清理，工作树干净

---

## 关键技术决策记录（预留，完成后补入 DECISIONS.md）

**D011：Tailwind v4 集成方式**
- 采用 `@tailwindcss/vite` 插件 + `@import "tailwindcss"`（v4 官方推荐，已通过 Context7 验证）
- 放弃 ARCHITECTURE.md 目录结构中列出的 `tailwind.config.ts`（v4 下非必需；主题 token 由 `tokens.css` 提供）
- 若未来需要 tailwind plugin 或自定义 preset 再补 `tailwind.config.ts`

---

👤 用户确认本 Contract 后，开发开始。
