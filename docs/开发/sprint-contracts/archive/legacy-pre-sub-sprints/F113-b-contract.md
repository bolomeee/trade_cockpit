# Sprint Contract：F113-b — News 前端持久化 + 增量刷新

> 状态：draft | 起草：2026-04-23
> 父 Feature：F113 News 缓存与增量刷新
> 依赖：F113-a（`?since` / `?window` 后端参数已就绪）
> 兄弟：F113-a（done）、F113-c（已读状态，planned）

---

## 0. 背景

F113-a 已就绪：后端支持 `?window=calendar-1d`（缓存优先）和 `?since=<iso>`（增量）。但前端仍每次挂载都重拉全量数据（`useNewsArticles` → `getNewsArticles(limit)` → `?window=calendar-1d`），刷新页面浪费 FMP 配额且有白屏延迟。

本 Sprint 目标：

1. **跨刷新/跨 session 持久化**：文章存 localStorage，今日数据直接从本地读，无需等待网络
2. **增量刷新**：Refresh 按钮调 `?since=<最新 publishedAt>`，只拉新文章并合并到现有列表
3. **当日数据隔离**：localStorage key 带日期后缀，换日自动放弃旧数据拉新

---

## 1. 实现范围

### 1.1 localStorage 持久化策略

- 存储 key：`ma150.news.v1.<YYYY-MM-DD>`（服务端 date 取自 `new Date().toISOString().slice(0,10)`）
- 每次数据更新后写 localStorage；写入失败（quota exceeded）静默忽略
- 每次写入时清理 `ma150.news.v1.*` 前缀的旧日 key
- **不使用 `@tanstack/react-query-persist-client`**（见 D058）

### 1.2 `useNewsArticles` hook 行为

| 场景 | 行为 |
|------|------|
| 今日首次打开（localStorage 无今日数据） | `staleTime: 0` → 立即 fetch `?window=calendar-1d&limit=50` → 写 localStorage |
| 今日二次打开（localStorage 有今日数据） | `initialData` 立即显示，`staleTime: Infinity` 不自动 refetch |
| 手动 Refresh | 调 `?since=<最新 publishedAt>` → 合并 → 写 localStorage |
| 首次打开 + `since` 模式（边界情况：无初始数据时 Refresh） | 回退 `?window=calendar-1d` |

**新增返回值**：
```typescript
refresh: () => void
isRefreshing: boolean  // true = 增量 fetch 进行中
```

### 1.3 合并去重规则

- 去重 key：`url`（若存在）否则 `publishedAt[:19] + "|" + title[:80]`
- 合并顺序：新文章 prepend 到现有列表前（保持时间倒序）
- 合并后写 localStorage

### 1.4 Refresh 按钮（`NewsWidget`）

- 位置：table header 行右侧（`flex justify-between items-center` 包一行）
- 形态：图标按钮（`lucide-react` 的 `RefreshCw`），旋转动画在 `isRefreshing` 时
- 禁用：`isRefreshing` 时 disabled

**API 调用变更**（`lib/api/news.ts`）：

| 旧签名 | 新签名 |
|--------|--------|
| `getNewsArticles(limit?: number)` | `getNewsArticles(params?: NewsArticlesParams)` |

```typescript
interface NewsArticlesParams {
  limit?: number
  since?: string   // ISO-8601
  window?: 'calendar-1d' | 'none'
}
```

---

## 2. 预计修改文件（4 个）

| # | 文件 | 类型 | 说明 |
|---|------|------|------|
| 1 | `src/lib/api/news.ts` | 修改 | 支持 `since` / `window` 参数 |
| 2 | `src/lib/news-persist.ts` | 新建 | localStorage 读写 + merge 逻辑 |
| 3 | `src/hooks/useNewsArticles.ts` | 重写 | initialData + useMutation refresh |
| 4 | `src/workbench/widgets/NewsWidget.tsx` | 修改 | Refresh 按钮 + isRefreshing |

**无新依赖**（见 D058）

---

## 3. 完成标准

| # | 标准 | 验证方式 |
|---|------|---------|
| 1 | 首次打开 News 页 → 网络有请求（`?window=calendar-1d`） → 文章显示 | DevTools Network |
| 2 | 刷新页面 → 文章立即显示（无白屏）→ 无网络请求 | DevTools Network |
| 3 | 换日（模拟 date 变化）→ 重新 fetch | 手动修改 localStorage key 日期 |
| 4 | Refresh 按钮点击 → 网络请求包含 `since=<iso>` 参数 | DevTools Network |
| 5 | Refresh 返回新文章 → 新文章出现在列表顶部，旧文章仍保留 | 目视 |
| 6 | 无新文章时 Refresh → 列表不变，无重复条目 | 目视 |
| 7 | Refresh 进行中 → 按钮旋转 + disabled | 目视 |
| 8 | `pnpm build` 无 TypeScript 错误 | CI |

---

## 4. Evaluator 自检清单

- [ ] `loadTodayArticles` 解析失败（JSON 损坏）→ 返回 `null`，不抛异常
- [ ] `saveTodayArticles` 写 localStorage 失败 → 静默忽略，不影响 UI
- [ ] 合并逻辑：同一篇文章不出现两次（刷新前后 key 相同）
- [ ] `isRefreshing` 在 mutation 结束后回到 `false`
- [ ] `useNewsArticles` 的 `staleTime` 在 `persisted !== null` 时为 `Infinity`（不自动 refetch）
- [ ] F112-a 回归：`?window=calendar-1d` 默认行为不破坏（News 页首次加载仍显示文章）

---

## 5. 非目标

- 已读状态（F113-c）
- `meta.truncated` 前端展示（留给后续迭代）
- ServiceWorker / 离线模式
- 跨 tab 同步

---

## 6. 开发顺序

1. `lib/api/news.ts` 参数扩展
2. `lib/news-persist.ts` 工具函数
3. `hooks/useNewsArticles.ts` 重写
4. `widgets/NewsWidget.tsx` 加 Refresh 按钮
5. 浏览器验证（dev server）
