---
feature_id: F007-c
feature_name: 交易日志 Journal — 新建/编辑 Dialog
status: done
created_at: 2026-04-17
completed_at: 2026-04-17
---

# Sprint Contract：F007-c

## 范围

**本次包含**：
- 引入 `react-hook-form` + `zod` + `@hookform/resolvers`；shadcn `select.tsx` / `label.tsx`（CLI 生成）
- `JournalEntryForm.tsx`：9 字段纯表单，zod schema 校验，`Controller` 接 shadcn Select + Action=WATCH 禁用 Position
- `JournalEntryDialog.tsx`：Dialog 容器，mode=new/edit，提交 POST/PUT，成功回调 invalidate
- `Journal.tsx`：解锁 `+New Entry` 与行 `Edit` 按钮；管理 Dialog open + mode + editing entry
- DECISIONS.md D028（本 Sprint 引入的依赖与理由，context7 2026-04-17 验证）
- features.json：F007-c phase → done

**本次排除**：
- Dashboard JournalQuickAddCard（→ F007-d）
- FilterCard 回迁到 shadcn Select（保留 F007-b 的原生 select 偏离，单开任务处理样式统一）

## 预计修改文件（5 + 2 个）

新建 / 修改的"业务代码"：
- `frontend/src/components/features/journal/JournalEntryForm.tsx`（新建）
- `frontend/src/components/features/journal/JournalEntryDialog.tsx`（新建）
- `frontend/src/pages/Journal.tsx`（修改：解锁按钮 + Dialog 状态）

新增的"依赖与基础组件"（CLI / package.json 产出）：
- `frontend/src/components/ui/select.tsx`（shadcn CLI 生成）
- `frontend/src/components/ui/label.tsx`（shadcn CLI 生成）
- `frontend/package.json`（新增 3 依赖）
- `frontend/pnpm-lock.yaml`（自动）
- `docs/系统设计/DECISIONS.md`（D028）

业务代码 3 个，未超 6 上限；基础设施文件不计入逻辑复杂度。

## 完成标准

| # | 标准 | 层级 | 工具 |
|---|------|------|------|
| 1 | 点击 + New Entry 打开 Dialog，Title="New Trade Entry"；各字段空 | E2E | preview_click |
| 2 | 提交全空 → 字段级红字（Ticker/Action/Price/Date required） | 校验 | preview |
| 3 | 合法新建 → POST 201 → Dialog 关闭 → 列表刷新出现新行 | E2E | preview+fetch |
| 4 | Ticker 不在 watchlist → Footer 红字错误（422/404 from API） | 错误处理 | preview |
| 5 | 行 Edit 打开 Dialog，Title="Edit Trade Entry"，字段预填 | E2E | preview |
| 6 | Edit 提交 → PUT 200 → 刷新行 | E2E | preview |
| 7 | Action=WATCH 时 Position 输入禁用（disabled） | 交互 | preview |
| 8 | Price/Position/StopLoss/Target 非数字或 ≤ 0 → 字段错误 | 校验 | preview |
| 9 | Cancel 关闭 Dialog 不提交 | 交互 | preview_click |
| 10 | pnpm build 通过，无 TS 错误 | 构建 | pnpm build |
| 11 | 回归：Dashboard / /journal 列表过滤/删除/展开仍然工作 | 回归 | preview |

## Evaluator 自检清单

- [ ] 全部 11 条通过
- [ ] schema 字段名严格 camelCase，匹配 API-CONTRACT
- [ ] Controller 接 Select（非手写 onChange），字段 name 走 RHF
- [ ] reset() 在 mode 切换或 initialEntry 变化时触发，避免脏预填
- [ ] 错误状态分字段级（`field.error.message`）+ 表单级（提交 mutation 的 ApiError）
- [ ] 颜色/字体 tokens，无硬编码
- [ ] 函数 ≤ 50 行；若超则拆分内部组件
- [ ] DECISIONS.md D028 已追加
- [ ] 全量 pnpm build 通过，无新增 TS 错误

## 依赖版本锁（context7 2026-04-17）

- react-hook-form ^7.72
- zod ^4.3
- @hookform/resolvers ^5.2
- shadcn cli latest（生成 select/label 基于 radix-ui）

## 风险

- **zod v4 vs v3 API 差异**：zodResolver 已自动检测；仍需留意 `z.string().min(1)` 等链式在 v4 的兼容
- **日期**：用 `<input type="date">` 避免 calendar 组件；提交时格式统一 YYYY-MM-DD
- **ticker 大小写**：前端 uppercase 后提交
