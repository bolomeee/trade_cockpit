# Sprint Contract：F113-c — 已读状态 + 5日新闻窗口

> 状态：done | 起草：2026-04-23 | 验收：2026-04-23
> 父 Feature：F113 News 缓存与增量刷新
> 依赖：F113-b（done）

---

## 0. 背景

两个并行目标：
1. **已读状态**：点开文章后列表行变淡（opacity-50），跨刷新保持，永不自动清空。
2. **5日窗口**：把 F113-b 的"仅今日"改为"滚动5天"，持久化保留5天内条目，5天以上修剪。

---

## 1. UX 决策（已确认）

- 已读行：`opacity-50`，不加 badge/icon
- 已读标记：永久保留，不清空
- 新闻窗口：滚动5天（初次拉取 `since=<5d-ago>`，save 时修剪）

---

## 2. 修改文件（5 个）

| # | 文件 | 说明 |
|---|------|------|
| 1 | `src/lib/news-persist.ts` | 固定 key `ma150.news.v1`，5日修剪，导出 `articleKey` |
| 2 | `src/hooks/useNewsArticles.ts` | 初次 fetch 改为 `since=fiveDaysAgoIso()`，limit=200 |
| 3 | `src/store/useReadArticlesStore.ts` | 新建：zustand persist，key `ma150.news.read.v1` |
| 4 | `src/workbench/widgets/NewsWidget.tsx` | NewsRow 已读行 `opacity-50` |
| 5 | `src/components/common/ArticleModal.tsx` | 打开时调 `markAsRead(articleKey(article))` |

---

## 3. 完成标准（全部通过）

| # | 标准 | 结果 |
|---|------|------|
| 1 | 点开文章关闭后该行 opacity-50 | ✅ |
| 2 | 刷新页面已读状态保持 | ✅ |
| 3 | 文章列表含5天内数据 | ✅ |
| 4 | F113-b Refresh 按钮回归正常 | ✅ |
| 5 | `pnpm build` 无 TS 错误 | ✅ |
