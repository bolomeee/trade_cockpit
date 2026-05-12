# Sprint Contract：F213-b — News Article Auto-Translate 前端 ArticleModal 改造

> 状态：草案，待用户确认 | 起草：2026-05-07
> 父 Feature：F213 News Article Auto-Translate (DeepSeek via /api/ai)
> 拆分：F213-a ✅ done（后端 4 文件） / **F213-b（本 sprint，前端 3 文件）**
> 依赖：
>   - F213-a ✅（后端 `translate_article` task 已落地，REGISTRY/tier/endpoint 全部就绪）
>   - F211-a2 ✅（per-task model override 基建）
>   - 已有 `callAiTask` 通用前端封装（`src/cockpit/lib/api/aiApi.ts`，AiNewsSummaryBar 验证过）
>   - 已有 `stripHtml` util（`src/components/news/newsSummaryUtils.ts`）
>   - 已有 sonner toast 系统（`src/main.tsx` 已挂 `<Toaster position="bottom-right" />`）
>   - 已有 `@tanstack/react-query` v5（AiNewsSummaryBar 已实践 useQuery 模式）
> 引用文档：
>   - API-CONTRACT.md §POST /api/ai/{task_type}（task_type=translate_article，已 8 enum）
>   - DECISIONS.md D064 / D069 / D075 / D084
>   - features.json#F213 acceptance_criteria #3 / #4 / #5
>   - F213-a-contract.md §1.2（前后端边界 + HTML 剥离前端约定）

---

## 0. 背景与定位

F213-a 已让后端 `/api/ai/translate_article` 可用：传入 `{title, contentText, targetLang}`，返回 `{titleZh, contentZh}`，命中 `ai_memos` 缓存时 `meta.cacheHit=true`。

F213-b 完成"用户视角的最后一公里"：

1. ArticleModal 打开时**自动**触发翻译（无需点按钮）
2. loading 期不阻塞用户阅读 — 显示原文 + 顶部"正在翻译..."轻量指示
3. 成功后用译文替换 `title` + `contentHtml` 渲染区域
4. 失败时回落到原文 + 顶部 sonner toast 错误提示
5. 同一篇文章重复打开 — react-query cache (内存层) 命中或 ai_memos cache (服务端层) 命中，0 token 0 cost

**关键约束**：

1. **修改最小化**：复用现有 `ArticleModal.tsx`（路径 `src/components/common/ArticleModal.tsx`，News 页 + Workbench NewsWidget 都用同一个 — 改一处覆盖两处）。
   > ⚠️ SESSION-HANDOFF.md 中提到的路径 `src/workbench/widgets/News/ArticleModal.tsx` 不准确，实际文件位于 `src/components/common/ArticleModal.tsx`。本 sprint 沿用真实路径，不新建 `widgets/News/` 目录。
2. **API 客户端走类型化薄封装**：在 `src/lib/api/translateArticle.ts` 新建一个文件，导出 `translateArticle(input)` 函数，内部用 `callAiTask<TranslateArticleInput, TranslateArticleOutput>`。
   - 不直接在 ArticleModal 里裸调 `callAiTask`（未来 F211-c 增加监控/埋点时只改一处）。
   - 类型定义与后端 `TranslateArticleInput / Output` 1:1 对齐（camelCase）。
3. **状态管理用 react-query useQuery**：
   - queryKey: `['translate-article', articleKey(article)]`
   - enabled: `!!article && contentText.length > 0`
   - retry: 1（避免单次网络抖动直接 toast）
   - staleTime: Infinity（同一篇文章首次拉到译文就缓存到关闭浏览器；服务端 ai_memos 是兜底）
   - gcTime: 5 min（关闭 modal 5 分钟内重新打开仍走内存）
4. **HTML 剥离前端做**（与 F211-a1 news_summarizer 同约定）：
   - 用 `stripHtml(article.contentHtml)` 拿到纯文本 → 传给后端的 `contentText`
   - 后端返回的 `contentZh` 是纯文本（含段落分隔符），前端用 `<p>` 拆段落渲染（不走 dangerouslySetInnerHTML）
5. **不动其他 widget / page**：不改 NewsWidget.tsx / News.tsx / AiNewsSummaryBar.tsx。
6. **不引入新依赖**：sonner / react-query / dompurify 全部已在。
7. **不改后端**：F213-a 已交付的 4 文件不动。
8. **不持久化译文到 localStorage**：刷新页面后重新点开走 ai_memos 缓存命中（meta.cacheHit=true，0 cost）。这是 F213 设计意图（D069 兜底）。

---

## 1. 实现范围

### 1.1 包含

#### 1.1.1 `frontend/src/lib/api/translateArticle.ts`（新建，~35 行）

**职责**：translate_article task 的类型化薄封装。

```ts
import { callAiTask, type AiTaskResponse } from '@/cockpit/lib/api/aiApi'

export type TranslateArticleInput = {
  title: string
  contentText: string
  targetLang?: 'zh-CN'  // 默认走后端 default
}

export type TranslateArticleOutput = {
  titleZh: string
  contentZh: string
}

export type TranslateArticleResponse = AiTaskResponse<TranslateArticleOutput>

export function translateArticle(
  input: TranslateArticleInput,
): Promise<TranslateArticleResponse> {
  return callAiTask<TranslateArticleInput, TranslateArticleOutput>(
    'translate_article',
    input,
  )
}
```

> 不导出 `noCache` 选项（F213 场景下永远希望命中 ai_memos 缓存）。

#### 1.1.2 `frontend/src/components/common/ArticleModal.tsx`（修改，预计 +60/-5 行）

**改造点**：

a. 新增 `useQuery` 拉取译文：
```ts
const { data, isLoading, isError } = useQuery({
  queryKey: ['translate-article', article ? articleKey(article) : null],
  queryFn: () => translateArticle({
    title: article!.title,
    contentText: stripHtml(article!.contentHtml),
  }),
  enabled: !!article && (article.contentHtml?.length ?? 0) > 0,
  staleTime: Infinity,
  gcTime: 5 * 60 * 1000,
  retry: 1,
})
```

b. 渲染逻辑（替换现有标题与正文区域）：
- **标题**：`data?.output.titleZh ?? article.title ?? 'Untitled'`
- **正文**：
  - 若 `data?.output.contentZh` → 按 `\n\n` 拆段，逐段 `<p>` 渲染（无需 dangerouslySetInnerHTML，Chinese 译文是纯文本）
  - 否则 → 现有 `dompurify` 清洗 `contentHtml` + `dangerouslySetInnerHTML`（loading 期与失败回退路径都走这里）

c. 顶部 loading/状态条（紧贴标题下方，meta 上方）：
| 状态 | 显示 |
|------|------|
| isLoading | "正在翻译..." 灰字 + Loader2 旋转图标（lucide-react，已在依赖） |
| isError | "翻译失败，显示原文" 灰字（不显示重试按钮，简化交互；toast 已通知） |
| data?.meta.cacheHit | "已缓存" 小徽标（与 AiNewsSummaryBar `cache-badge` 同样式） |
| data 且非 cacheHit | 不显示状态条（成功且非命中无需打扰） |

d. 错误 toast（`useEffect` 监听 isError）：
```ts
useEffect(() => {
  if (isError) toast.error('文章翻译失败，已显示原文')
}, [isError])
```

e. **不**改动现有 ESC 关闭、Tab 焦点、`markAsRead`、ticker badges、Portal 渲染、aria-label / role="dialog" 等无关逻辑。

#### 1.1.3 `frontend/src/components/common/__tests__/ArticleModal.test.tsx`（新建，~280 行）

**测试组（14 用例）**：

- **AM1-AM3 基础渲染回归**（保留现有行为）：
  - article=null → null（不渲染）
  - article 提供 → 渲染 dialog + 标题 + ticker badges
  - ESC 键 → onClose 触发
- **AM4-AM5 HTML 剥离**：
  - article.contentHtml 含 `<script>` → 不进入 translateArticle 的 contentText（mock translateArticle 收到 stripHtml 结果）
  - article.contentHtml 为空字符串 → useQuery enabled=false（mock translateArticle 不被调用）
- **AM6-AM8 loading 状态**：
  - 渲染时立即显示原文标题 + "正在翻译..." 文案 + Loader2 图标
  - loading 期间 ESC 仍可关闭
  - 第一次渲染时 translateArticle 被调用 1 次，参数 = `{title, contentText: stripHtml(html)}`
- **AM9-AM10 success 状态**：
  - resolve `{titleZh, contentZh, meta:{cacheHit:false}}` → 标题切换为 titleZh，正文按 `\n\n` 拆段渲染
  - resolve `meta.cacheHit=true` → 显示"已缓存"徽标
- **AM11-AM12 error 状态**：
  - reject (ApiError) → 标题保持原文，正文走 dompurify 路径，"翻译失败"文案显示
  - error 触发 sonner toast.error 一次（mock toast）
- **AM13 缓存复用**：
  - 同一篇文章（同 articleKey）切换打开关闭再打开 → translateArticle 只被调用 1 次（react-query 内存命中，gcTime 内）
- **AM14 切换文章**：
  - 第一次打开 article A → translateArticle 调用参数为 A
  - 关闭再打开 article B → translateArticle 第二次调用参数为 B
  - queryKey 区分 articleKey(A) vs articleKey(B)

**测试技术栈**：
- vitest + @testing-library/react + @tanstack/react-query
- `vi.hoisted` mock `translateArticle`、`toast`（同 AiNewsSummaryBar.test.tsx 模式）
- 每个 it 用独立 `QueryClient`（`gcTime:0` 保证不跨用例污染；AM13 例外，复用同一 client）
- `useReadArticlesStore` 用 vi.mock 替换 markAsRead noop（避免触碰 zustand store）

### 1.2 排除（不在本 sprint）

- ❌ 后端任何代码（F213-a 已交付）
- ❌ 翻译结果持久化到 localStorage（D069 ai_memos 已兜底）
- ❌ 用户手动切换"显示原文 / 译文"开关（acceptance_criteria 未提；可作 F213-c 后续增强）
- ❌ `targetLang` 选择器（当前固定 zh-CN）
- ❌ 译文段落按 markdown 渲染（后端 SYSTEM_PROMPT 没要求 markdown 输出，按 `\n\n` 拆段足够）
- ❌ 改 NewsWidget.tsx / News.tsx / AiNewsSummaryBar.tsx（共用 ArticleModal 自动生效）
- ❌ `.env` 真实配置 DeepSeek key（属用户运维，F213-a contract §6 已写示例）
- ❌ E2E 测试（Playwright，本 sprint 单元 + 集成测试已覆盖关键路径；E2E 留给 acceptance 阶段）
- ❌ 监控埋点（F211-c 监控规划范畴）

---

## 2. 预计修改文件清单（3 个 — 远低于 6 文件预算）

| # | 文件 | 操作 | 行数 |
|---|------|------|------|
| 1 | `frontend/src/lib/api/translateArticle.ts` | 新建 | ~35 |
| 2 | `frontend/src/components/common/ArticleModal.tsx` | 修改 | +60/-5 |
| 3 | `frontend/src/components/common/__tests__/ArticleModal.test.tsx` | 新建 | ~280 |

**文档前置（不计入文件预算）**：

| 文件 | 操作 |
|------|------|
| `claude-progress.txt` | 追加 F213-b contract 协商记录 |
| `features.json` F213 | sub_sprints.F213-b: design_needed → contract_agreed；iteration_history 追加一条 |

> ⚠️ 本 sprint 不需要前置改任何系统设计文档（API-CONTRACT / DATA-MODEL / DECISIONS）— F213-a 已全部就绪。

---

## 3. 完成标准（Evaluator 测试用例）

| # | 测试描述 | 层级 | 工具 | 预期 |
|---|---------|------|------|------|
| AM1 | article=null 时 ArticleModal 不渲染任何 DOM | 单元 | vitest+RTL | container.firstChild === null |
| AM2 | article 提供时渲染 dialog + 标题 + tickers | 单元 | vitest+RTL | 找到 role=dialog + 标题文本 + ticker 按钮 |
| AM3 | ESC 键触发 onClose | 单元 | vitest+RTL | onClose mock 被调用 1 次 |
| AM4 | contentHtml 含 `<script>` → mock translateArticle 收到的 contentText 不含 script tag | 单元 | vitest mock | 参数 contentText 是 stripHtml 结果 |
| AM5 | contentHtml 为空 → translateArticle 不被调用（enabled=false）| 单元 | vitest mock | mockTranslateArticle 调用次数 === 0 |
| AM6 | loading 时显示原文标题 + "正在翻译..." 文案 + Loader2 图标 | 单元 | vitest+RTL | 找到原标题 + 翻译中文案 + 图标 |
| AM7 | loading 期间 ESC 仍可关闭 | 单元 | vitest+RTL | onClose 被调用 |
| AM8 | translateArticle 第一次渲染被调用 1 次，参数正确 | 单元 | vitest mock | mock 收到 `{title, contentText, targetLang? omit}` |
| AM9 | resolve 后标题切为 titleZh，正文按 \n\n 拆段渲染 | 单元 | vitest+RTL | 找到译文标题；找到 N 个 `<p>` |
| AM10 | meta.cacheHit=true → 显示"已缓存"徽标 | 单元 | vitest+RTL | 找到带 cache 文案的 element |
| AM11 | reject → 标题保持原文，正文走 dompurify 路径，显示"翻译失败"文案 | 单元 | vitest+RTL | 原文渲染 + 失败文案可见 |
| AM12 | error 触发 sonner toast.error 一次 | 单元 | vitest mock toast | mockToastError 调用次数 === 1 |
| AM13 | 同 article 关闭再打开（同一 QueryClient）→ translateArticle 仅 1 次 | 单元 | vitest mock | 调用次数 === 1 |
| AM14 | 切换 article A→B → translateArticle 调用 2 次，参数分别为 A/B | 单元 | vitest mock | 调用次数 === 2 + 参数顺序匹配 |
| LIB1 | translateArticle 函数转发 callAiTask('translate_article', input) | 单元 | vitest mock callAiTask | mockCallAiTask('translate_article', expected) 被命中 |
| REGRESSION-FE | 全量前端测试套件回归 | 全量 | `pnpm test --run` | 全通过，无新增失败 |
| REGRESSION-BE | 全量后端测试套件回归（确认前端改动未污染） | 全量 | `pytest backend/tests/` | 5 预存失败保持（F213-a 已知），无新增 |

---

## 4. 自检清单（Generator 完成后 Evaluator 模式使用）

- [ ] 前端单元测试 AM1-AM14 + LIB1 全部通过（≥15 通过）
- [ ] 全量前端测试套件无新增失败
- [ ] 全量后端测试套件无新增失败（仅确认未误改）
- [ ] `pnpm tsc --noEmit` 类型检查通过（0 error）
- [ ] `pnpm lint`（如项目配置）通过，无新增 warning
- [ ] ArticleModal.tsx 不引入硬编码颜色 / 字号（沿用 `var(--color-*)`、`var(--font-size-*)` token）
- [ ] translateArticle.ts 类型与后端 schemas/translate_article.py 字段名 1:1 对齐（camelCase）
- [ ] 不直接在 ArticleModal 调用 callAiTask（必须走 translateArticle 封装）
- [ ] 不引入新依赖（package.json 不变）
- [ ] 不修改 News.tsx / NewsWidget.tsx / AiNewsSummaryBar.tsx（共用 ArticleModal 自动覆盖）
- [ ] 不持久化译文到 localStorage（仅 react-query 内存层）
- [ ] features.json F213.sub_sprints.F213-b 升 done
- [ ] features.json F213 status：所有 sub_sprint 全 done → 触发 consistency-check C1 invariant 决定父 feature 是否升 done（默认保持 in_progress 等待 acceptance）
- [ ] features.json F213.iteration_history 追加 generator 完成记录
- [ ] git wip commit 按步骤分批（translateArticle.ts → ArticleModal.tsx → 测试）
- [ ] 无 console.error / 无未捕获 warning（开发服务器跑通时观察）
- [ ] 浏览器手动验证：
  - [ ] 打开任一英文新闻 → loading → 显示中文标题 + 中文正文
  - [ ] 关闭再打开同一篇 → 立即出中文（react-query 命中）
  - [ ] DevTools Network 看到 `POST /api/ai/translate_article` 第二次响应 `meta.cacheHit=true`（如果未关闭 staleTime 内不会重发）

---

## 5. 开发顺序（Generator 模式不得颠倒）

1. **新建** `frontend/src/lib/api/translateArticle.ts`（类型 + 函数）
2. **新建** `frontend/src/components/common/__tests__/ArticleModal.test.tsx` 的 LIB1 用例（先验封装层）
3. **修改** `frontend/src/components/common/ArticleModal.tsx`（注入 useQuery + 渲染分支 + toast）
4. **补全** ArticleModal.test.tsx 的 AM1-AM14 用例
5. 跑 `pnpm test --run src/components/common/__tests__/ArticleModal.test.tsx` → 全过
6. 跑 `pnpm test --run` 全量回归 → 无新增失败
7. 跑 `pnpm tsc --noEmit` 类型检查
8. 跑 `pytest backend/tests/` 验证后端测试无回归（仅排查误改）
9. 启动 dev server 手动验证（参见 §4 自检清单末段）
10. 切换 Evaluator 模式，逐条对照 §3 / §4
11. 全部通过 → 调用 consistency-check skill (mode=interactive) 升 sub_sprint phase
12. 收尾 commit `feat(F213-b): ArticleModal auto-translate via DeepSeek`

每步完成后 wip commit（CLAUDE.md 规则 7）。

---

## 6. 风险与降级

| 风险 | 影响 | 降级 |
|------|------|------|
| DeepSeek 限流 / 网络抖动 | 翻译失败 | useQuery retry:1 + sonner toast + 回退原文 dangerouslySetInnerHTML（用户不阻塞） |
| 译文 `\n\n` 拆段丢段落 | 排版退化 | `<p>` 间距用 `var(--space-*)`，即使一段也可读 |
| react-query cache key 冲突 | 文章内容串台 | queryKey 用 `articleKey(article)`（已经是 url 或 publishedAt+title 哈希，唯一） |
| stripHtml 输出超 20000 字符 | 后端 ValidationError | UI 不裂；toast 错误；用户可用原文回退（极长正文罕见，超长建议留 F213-c 后端做截断） |
| ArticleModal 高频打开关闭 | useQuery 重复触发 | staleTime:Infinity + gcTime 5min，5 分钟内重打开 0 网络 |
| 后端 SYSTEM_PROMPT 偶尔输出 markdown 标记 | `**` 等显式呈现 | 接受首版退化；可后续在前端去除 `**`/`*` 做轻量净化 |

---

## 7. 不变量（Generator 期间不得违反）

- 现有 ArticleModal 行为（dialog 打开/关闭、ESC、focus trap、ticker 选择回调、markAsRead）不被破坏
- 后端 F213-a 4 文件不被修改
- 不引入新前端依赖
- 不修改 News.tsx / NewsWidget.tsx / AiNewsSummaryBar.tsx
- localStorage 不写入译文
- 译文渲染不走 dangerouslySetInnerHTML（直接 React `<p>{text}</p>`，避免 XSS 面）
- 原文渲染保留 dompurify 清洗（向后兼容）

---

## 8. 开放问题（Generator 阶段第 1 步前必须解决）

| Q | 问题 | 默认方案 | 备选 |
|---|------|---------|------|
| Q1 | API 客户端文件位置：`frontend/src/lib/api/translateArticle.ts` 还是 `frontend/src/cockpit/lib/api/translateArticle.ts`？ | **默认**：`src/lib/api/translateArticle.ts`（与 news.ts/journal.ts 同级，因为译文功能服务于 News，不属于 cockpit）| `cockpit/lib/api/`（贴近 aiApi 现有位置） |
| Q2 | loading 期间是否禁用 ticker 按钮 / 关闭按钮？ | **默认**：不禁用（用户可随时关 / 切 ticker；翻译 background 进行不阻塞）| 禁用（更"严格"但牺牲交互） |
| Q3 | error 时是否显示重试按钮？ | **默认**：不显示（toast 已通知；下次重新打开自动重试 + ai_memos 命中可省 cost）| 显示重试按钮（增加视觉噪音） |
| Q4 | 译文 `\n\n` 拆段；若后端返回单段（无 `\n\n`）？ | **默认**：整段渲染为单个 `<p>`（自然降级）| 强制按句号拆 |
| Q5 | 是否在 cacheHit 时显示徽标？ | **默认**：显示"已缓存"小灰字（与 AiNewsSummaryBar 一致体验）| 不显示（更安静） |
| Q6 | translateArticle 函数是否暴露 `noCache` 参数？ | **默认**：不暴露（F213 场景永远希望命中缓存省 token） | 暴露（未来若加"强制重译"按钮可用） |
| Q7 | useQuery `staleTime` 与 `gcTime` 取值？ | **默认**：`staleTime: Infinity` + `gcTime: 5 * 60 * 1000`（5 分钟）| 全部 0 退化为每次重新拉 |

**用户回应**：默认全采纳即可（如有修改在确认时一并指明）。

---

## 9. 与 acceptance 阶段的衔接

F213-b Evaluator 通过后，调用 consistency-check：
- C1：F213-b 升 done → F213-a 已 done → 父 F213 sub_sprints 全 done 但 status 暂停在 in_progress（acceptance 未跑）
- C4 / C5：F213-b iteration_history + sub_sprints 双向一致

随后通知用户：
1. 在 `backend/.env` 配置 `AI_TASK_OVERRIDES_JSON`（参见 F213-a-contract §6）
2. 触发 acceptance skill 跑 F213 验收 →
3. 验收通过则父 F213 phase → done，关闭。

---

## 10. 用户确认须知

回复"Contract 同意"或等价 OK 即视为确认。确认后我将：

1. 更新 features.json F213.sub_sprints.F213-b: design_needed → contract_agreed
2. 追加 features.json#F213.iteration_history 一条 contract_agreed 记录
3. 追加 claude-progress.txt
4. 生成 SESSION-HANDOFF.md（含 Sprint Contract 摘要 + 开发顺序 + 下一 session 恢复指令）
5. **停止本 session**，提示用户用 Sonnet 开新 session 走 Generator 模式（feature-dev skill A-1 末段强制）
