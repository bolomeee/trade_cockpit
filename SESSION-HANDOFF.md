# SESSION-HANDOFF — 2026-04-23 (F113 News 缓存与增量刷新)

## 立即执行指令（给下一个 session）

**开启新 session 后，说**：
> 继续开发 F113-a

触发 `/feature-dev` skill（或直接走 contract → implement → acceptance 流程）。当前 F113-a contract 已起草，**尚未 agreed**，第一步需要用户确认 contract。

---

## 上下文摘要

### F112 已全部完成（v1.6.0 发版）

| 子任务 | phase | commit |
|--------|-------|--------|
| F112-a（后端 `/api/news/articles`） | ✅ done | 7cf3cfd + 010169c |
| F112-b（老合约，路径 B） | ❌ SUPERSEDED | aa86e7a |
| F112-b1（导航 + /news + NewsTable） | ✅ done | 4f3ee25 |
| F112-b2（ArticleModal + Chart 复用 + ticker 联动） | ✅ done | 5b15a7c |
| v1.6.0 release | ✅ released | e546ff4 (+ tag v1.6.0) |

### F113 — 本 handoff 的主线

| 子任务 | phase | 合约 | 说明 |
|--------|-------|------|------|
| **F113-a（后端缓存 + 增量拉取）** | 🟡 draft | [F113-a-contract.md](docs/开发/sprint-contracts/F113-a-contract.md) | **下一步起点，需要 contract agreement 再实现** |
| F113-b（前端持久化 + 增量合并） | ⚪ planned | 待起草 | a 完成后起草 |
| F113-c（已读状态） | ⚪ planned | 待起草 | b 完成后起草 |

### 为何拆分 F113

用户反馈：News 每次刷新/软跳路由都重打 FMP，浪费配额且慢。同时希望：
1. 首次打开看"最近 1 个自然日"的新闻（不是 FMP 默认的 20 条滚动窗口）
2. 刷新时走增量（`since=<本地最新 publishedAt>`），而不是整列表重拉
3. 今天以内看过的文章（标题 + 全文）不再消耗网络
4. 已读文章视觉区分

由于整个链路跨前后端 + 新增依赖 + 新 DB 表，拆成 3 个 sprint 防止一次改动过大：

- **a = 后端能力**：新 `news_articles_cache` 表、API 增量参数、缓存降级
- **b = 前端持久化**：React Query persist 到 localStorage（跨刷新命中）+ Refresh 改走增量
- **c = 已读状态**：zustand persist + NewsRow 视觉

---

## F113-a 契约摘要（避免 session 切换后重读）

**范围**：后端 6 文件 —— `models.py` + Alembic migration 006 + `news_cache_repository.py`（新建）+ `news_service.py` + `routers/news.py` + `schemas/news.py`。

**核心决策点（contract 内已明确，用户已同意方向）**：

1. **新建 `news_articles_cache` 表，不复用 `daily_payload_cache`**。理由：daily_payload_cache 是"单 payload 覆盖式写"，news 是"多行增量 upsert 去重"，schema 语义不匹配。要在 **D057** 记录此决策。

2. **`article_key` 去重主键**：URL 优先，URL 为 null 时 fallback `SHA256(title + published_at)`。URL 原样不做 query 归一化（风险注释在 contract §7）。

3. **API 扩展**：
   - `limit` 上限从 50 提到 200（首屏可能覆盖 2 个自然日）
   - 新增 `since=<iso>` 增量模式：翻 FMP 最多 5 页，遇到 `date <= since` 停
   - 新增 `window=calendar-1d|none` 窗口策略；默认 `calendar-1d`（昨日 00:00 server local → now）
   - 响应加 `meta: { cache_hit, fmp_calls, truncated, fmp_error }`
   - F112-a 旧调用零改动可用（默认参数兼容）

4. **降级策略**：FMP 失败但缓存有数据 → 200 + `meta.fmp_error=true`（前端可提示 "数据可能不是最新"）。FMP 失败 + 缓存空 → 502。

5. **自然日 = server local date**。单用户本地部署假设，server TZ == user TZ。跨 UTC 边界运行用户可能看到日期漂移 1 天，F113 接受该风险（contract §7 记录）。

---

## F113-b 规划（提前锁定范围，a 完成后直接起草 contract）

**范围**：前端 5 文件 + 1 新依赖。

**预计修改文件**：

| # | 文件 | 类型 | 说明 |
|---|------|------|------|
| 1 | `frontend/package.json` + lockfile | 修改 | 新增 `@tanstack/react-query-persist-client` + `@tanstack/query-sync-storage-persister` |
| 2 | `frontend/src/main.tsx` 或 `QueryClient` 创建处 | 修改 | 用 `PersistQueryClientProvider` 包裹，persister 指向 localStorage，key `ma150.news.rq.v1` |
| 3 | `frontend/src/hooks/useNewsArticles.ts` | 修改 | `staleTime: Infinity`（不自动 refetch）；queryKey 带 `as_of_date`；persistKey 按自然日分段 |
| 4 | `frontend/src/lib/api/news.ts` | 修改 | `getNewsArticles({ since?, window? })` 支持新参数 |
| 5 | `frontend/src/components/features/topnav/RefreshButton.tsx` 或 `useRefreshStatus` | 修改 | Refresh 点击路径：拿 React Query 缓存里 `data[0].publishedAt` → 调 `?since=<iso>` → 合并新增项到 cache（`queryClient.setQueryData` 合并去重） |

**关键实现点**：
- **day-scoped key**：persistKey 包含 `getLocalDateString()`（`YYYY-MM-DD`），跨日自动失效（老 key 不被读取，localStorage 可以手动 GC 但一般不必）
- **合并去重**：`merge(oldData, newArticles)` 按 `article_key`（前端同样算法，或直接用 URL）去重，`published_at DESC` 排序
- **`staleTime: Infinity` + persist**：避免 React Query 自动 refetch 干扰（只靠 Refresh 按钮触发增量）
- **降级 UI**：`meta.fmp_error=true` 时 TopNav 显示一个小提示 "数据可能不是最新"

**新依赖决策**：引入 `@tanstack/react-query-persist-client` 记为 **D058**。选型对比（contract 时写）：
- ✅ react-query-persist-client：官方支持，零维护成本
- ❌ 自写 localStorage hook：重复造轮子，对 React Query 内部状态（dehydrate/hydrate）细节不熟容易漏

---

## F113-c 规划（a + b 完成后起草 contract）

**范围**：前端 3–4 文件。

**预计修改文件**：

| # | 文件 | 类型 | 说明 |
|---|------|------|------|
| 1 | `frontend/src/pages/useReadArticlesStore.ts` | 新建 | zustand persist，key `ma150.news.read.v1`；state: `Set<string>`（`article_key` 集合）；actions: `markAsRead(key)`, `isRead(key)` |
| 2 | `frontend/src/workbench/widgets/NewsWidget.tsx` | 修改 | NewsRow 读 `useReadArticlesStore.isRead(article_key)`，已读行加 `opacity-60` 或改 `text-muted-foreground` |
| 3 | `frontend/src/components/common/ArticleModal.tsx` | 修改 | `useEffect` 打开时调 `markAsRead(article_key)` |
| 4 | `frontend/src/lib/newsArticleKey.ts` | 新建（可选） | 与后端对齐的 `computeArticleKey(article)`：URL 优先，否则 hash(title + publishedAt)。若 hash 实现复杂可简化为 `url || ${title}|${publishedAt}`（不 hash） |

**UX 决策待敲**（等到起草 F113-c contract 时再问用户）：
- 已读后是否额外加 badge / icon（如小圆点）？还是仅 opacity 区分？
- "标记全部已读" / "清除已读" 操作按钮是否需要？
- 已读数据是否提供"跨设备"同步（本 Sprint 假定否，仅 localStorage 单浏览器）？

---

## 当前代码状态（`git log --oneline -6`）

```
e546ff4 chore: release v1.6.0
5b15a7c feat(F112-b2): ArticleModal + Chart widget 复用 + ticker 联动
4f3ee25 feat(F112-b1): News 页骨架 — /news 路由 + NewsTable widget
f98d421 docs(F112): 拆分 F112-b 为 F112-b1/b2；老合约标记 superseded
aa86e7a feat(F112-b): NewsWidget — Workbench 新闻卡片列表 (superseded by b1/b2)
010165f docs(F112-a): 验收通过，phase → done
```

**未提交变更**：仅 `docs/开发/sprint-contracts/F113-a-contract.md`（新建）、`docs/需求/features.json`（加 F113 entry）、`SESSION-HANDOFF.md`（本文件）。当前 contract **未 commit**，等 user agreement 后再 commit。

---

## 下一个 session 的动作清单

### Step 1：Contract agreement（F113-a）
1. 读 [F113-a-contract.md](docs/开发/sprint-contracts/F113-a-contract.md)
2. 向用户确认几个待定项：
   - 时区：server local date 假设是否 OK？
   - 上限 FMP 翻 5 页是否够？（若用户新闻阅读频率高可能 5 页不够覆盖"昨晚到现在"的累积）
   - 降级策略（FMP 失败 + 缓存有数据 → 200 + flag）是否接受？
3. 同意后更新 features.json F113-a.phase → `contract_agreed`，commit contract。

### Step 2：F113-a 实现
按 contract §6 顺序执行。关键里程碑：
- migration 006 成功 upgrade/downgrade
- `NewsCacheRepository` 单测
- `news_service` 增量翻页单测（mock FmpClient）
- 集成测试（缓存命中 / 降级 / 跳缓存）
- 文档同步（API-CONTRACT、DATA-MODEL、DECISIONS D057、features.json）

### Step 3：F113-a 验收 + 写 F113-b contract
- F113-a 生成 `docs/验收/v1.7.0-F113a-acceptance.md`（或 v1.6.1-a）
- 起草 F113-b contract（本 handoff §F113-b 规划 即是骨架，直接扩充即可）

### Step 4 & 5：F113-b 实现 + 验收 → F113-c 实现 + 验收

### Step 6：v1.7.0 发版
三子 sprint 完成后一起发版（或每个子 sprint 单独发 patch 版本，待届时决策）。

---

## 必读参考文件（session 间保持一致）

- [CLAUDE.md](CLAUDE.md)：项目约束（测试门禁、歧义优先级、context 不足处理）
- [docs/系统设计/DECISIONS.md](docs/系统设计/DECISIONS.md)：D055（daily_payload_cache 模式参考，F113-a 要记 D057 解释为何不复用）
- [docs/系统设计/DATA-MODEL.md](docs/系统设计/DATA-MODEL.md)：现有 schema + NewsArticleCache 需要新增的章节位置（DailyPayloadCache 之后）
- [docs/系统设计/API-CONTRACT.md#GET /api/news/articles](docs/系统设计/API-CONTRACT.md)：F112-a 已定义合约，F113-a 要扩展参数 + meta 字段

---

## 风险 / 未决事项

1. **server TZ 与 user TZ 不一致** → 自然日偏移。F113 接受该风险，生产环境 Docker 容器 `TZ=` 需显式设置。若未来上云多区域用户，需引入 `?tz=<IANA>` 参数并重新设计 as_of_date 字段（F113+1）。
2. **FMP URL 不稳定导致去重失效** → 已有 fallback 到 hash，但若 URL 带时间戳 query，同文会生成多份记录。F113-a 先观察实际数据，必要时加 URL 归一化到 F113-a 末尾或 F113-b。
3. **localStorage 容量** → 单日最多几百篇文章 × 约 5KB HTML = 几 MB，在 5MB localStorage 限额边缘。若日条目数预期超过此量，F113-b 要考虑：只 persist title/meta（不 persist contentHtml），打开 modal 时再按 `article_key` 查后端。本 handoff 暂不做此优化，先按全量 persist 验证。
4. **F112-a 回归风险** → F113-a 的 `list_articles` 签名扩展必须默认参数兼容，contract §完成标准#7 有覆盖，实现时注意。
