# SESSION-HANDOFF

> 更新：2026-04-27 PM | 阶段：F205-d ✅ needs_review → 下一阶段待定
> 项目：MA150 Tracker → Cockpit
> 当前 active_sprint：**F205-d**（PoolBuilderWidget 前端） / phase=`needs_review`

---

## 已完成内容（截至本 session）

### F205-a / F205-b / F205-c ✅ done
- 后端 `GET /api/cockpit/pool` 已上线，820 全量回归通过

### F205-d ✅ 全部实现，needs_review
commit: `68ddbed` `feat(F205-d): PoolBuilderWidget 前端实现`

| 文件 | 状态 |
|------|------|
| `frontend/src/cockpit/lib/api/cockpitPoolApi.ts` | 新建 ✅ |
| `frontend/src/cockpit/lib/api/__tests__/cockpitPoolApi.test.ts` | 新建 ✅ (5 用例) |
| `frontend/src/cockpit/widgets/_poolFilterBar.tsx` | 新建 ✅ |
| `frontend/src/cockpit/widgets/PoolBuilderWidget.tsx` | 新建 ✅ |
| `frontend/src/cockpit/widgets/__tests__/PoolBuilderWidget.test.tsx` | 新建 ✅ (11 用例) |
| `frontend/src/cockpit/CockpitRegistry.ts` | 修改 ✅ |

**Evaluator 自检结论**（全部通过）：
- TypeScript `pnpm tsc --noEmit`：无错
- 前端全量回归：21 测试文件，254/254 通过
- API client 字段名与 API-CONTRACT.md 严格对应
- 颜色/字体/间距全部走 token，无硬编码 hex
- 非 watchlist null 字段显示 `—`（D080 合规）
- react-query staleTime 60_000ms，filter debounce 300ms
- `[+ Add]` 成功后同时 invalidate `['cockpit-pool']` + `['watchlist']`
- `cockpit.pool-builder` 注册 defaultLayout `{ x:0, y:22, w:12, h:10 }`

---

## 当前状态

| 项 | 值 |
|---|---|
| active_sprint | F205-d |
| active_sprint_phase | needs_review |
| F205-c phase | needs_review |
| 后端全量回归 | 820 passed |
| 前端全量回归 | 254 passed |

---

## 功能说明（F205-d 实现细节）

### cockpitPoolApi.ts
- 类型：`PoolFilters` / `PoolFunnel` / `PoolItem` / `PoolData`
- `getCockpitPool(filters)` → 拼接 query string，60s `AbortController` timeout
- 导出常量：`POOL_TIMEOUT_MS = 60_000`

### _poolFilterBar.tsx
- 受控 props：`value: PoolFilters`，`onChange`
- 内部维护 `local` state（即时 UI 更新），`FILTER_DEBOUNCE_MS = 300ms` 后调 `onChange`
- 9 个输入字段：marketCapMin / priceMin / advMin / trendScoreMin / rsPercentileMin / revenueGrowthYoyMin / sectors / setupTypes / limit
- 清理：`useEffect` 在 unmount 时 clearTimeout

### PoolBuilderWidget.tsx
- Funnel 5 段：各段 `aria-pressed`，点击高亮（不切换表格内容，F205-e）
- Filter Bar：默认展开（inline 一行）
- 候选表：13 列，包含所有 data-mapping.md §Cockpit-3 字段
- Add 按钮：`disabled` 当 `inWatchlist=true` 或正在提交
- `POOL_STALE_TIME_MS = 60_000`

### CockpitRegistry.ts
新增：
```ts
'cockpit.pool-builder': {
  id: 'cockpit.pool-builder',
  title: 'Pool Builder',
  component: PoolBuilderWidget,
  defaultLayout: { x: 0, y: 22, w: 12, h: 10, minW: 6, minH: 6 },
  category: 'pool',
}
```

---

## 下一步建议

F205 系列已完成（a/b/c/d），可以：
1. **验收 F205-d**：在 Cockpit 页面实际查看 PoolBuilderWidget 渲染效果
2. **开始 F206**（Earnings Calendar Widget，v1.9 P1 下一个）
3. **启动 F205-e**（Funnel 各层数据分层展示，需后端返回各层 items）

---

## 下一 Session 恢复指令

如继续 F205 验收：
> 验收 F205-d PoolBuilderWidget，打开 Cockpit 页面检查渲染效果和交互。

如开始 F206：
> 继续开发 F206。读取 SESSION-HANDOFF.md + docs/需求/features.json 确认下一个 sprint。
