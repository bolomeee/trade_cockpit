---
status: confirmed
drafted_at: 2026-05-19
confirmed_at: 2026-05-19
sprint: F218-d4
parent_feature: F218
---

# F218-d4 Sprint Contract — T3 NEW_PRODUCT detector（D4a 关键词扫描）实装

> 生成：2026-05-19 | 状态：✅ 已确认（用户 NP-d4-1~10 全部按推荐 @ 2026-05-19）
> Feature：[F218](docs/需求/features.json) Cockpit Phase D — Repricing Trigger 完整框架（5 类）
> Sub-sprint：F218-d4（Phase D 10 sub-sprint 第 7 个；T3 NEW_PRODUCT **detector 实装**，D4a 关键词扫描，D4b NLP 升级**不在范围**）
> 前置：F218-d1 done（service skeleton + 5 占位）/ F218-d2 done（T1 实装样板）/ F218-d3a/d3b done（T2 数据层 + detector）
> 下游：F218-d5（T4 SECTOR_CYCLE detector，纯计算无新表）

> 引用文档：
> - [DATA-MODEL.md](docs/系统设计/DATA-MODEL.md) §RepricingTrigger 1080–1129（evidence_json schema §1099 NEW_PRODUCT 例 + confidence §1107 — T3 默认 0.5）
> - [DECISIONS.md](docs/系统设计/DECISIONS.md) D098（D4a 关键词扫描 vs D4b NLP 升级取舍 — 7 关键词 / ≥ 2 命中 / D4b 不在 F218 范围）
> - [ARCHITECTURE.md](docs/系统设计/ARCHITECTURE.md) §Cockpit Repricing Trigger Service
> - [F218-d2-contract.md](docs/开发/sprint-contracts/F218-d2-contract.md) / [F218-d3b-contract.md](docs/开发/sprint-contracts/F218-d3b-contract.md) — detector 实装样板（常量段 / DetectorResult / 测试分 class）
> - [backend/app/repositories/news_cache_repository.py](backend/app/repositories/news_cache_repository.py) — 既有 `get_cached(db, as_of_dates, since, limit)`，本 sprint 复用其行访问能力，新增 `get_recent_for_ticker` 函数

---

## 0. 背景与定位

F218-d1 留下的 5 个占位中第 3 个 `_detect_new_product` 现在实装。与 T1/T2 不同，T3 不读财务表，而读 `news_articles_cache` —— 现有 F113-a news_cache 已经稳定运行，仅需新增一个"按 ticker × 时间窗"的查询入口。

**核心语义（D098 + DATA-MODEL §1099）**：
- 扫描最近 30 日 `news_articles_cache` 中 **symbols 包含 ticker** 的所有 headlines
- 关键词集合 `{launch, unveil, introduce, release, AI, platform, new product}`（7 词，常量声明于 service 顶部，便于后续调参）
- 关键词命中总数 ≥ 2 次 → 触发（"命中 ≥ 2 次"按 D098 字面解读 = **跨所有该 ticker 文章的命中总次数**）
- confidence = **0.5（恒定）**（DATA-MODEL §1107 "其余维持 0.5"，T3 无高置信路径）
- evidence_json：`{"keyword_hits": [{"keyword": "AI", "count": 3}, …], "news_links": [...至多 5 条], "scan_window_days": 30}`

**关键设计承诺**：
- ❌ 不扫 news body / 不接 NLP（D098 方案 D / E 已显式放弃）
- ❌ 不动 `news_articles_cache` 表结构（不加 ticker 列；ticker → article 映射靠 `payload_json.symbols` 在 Python 层过滤）
- ❌ 不接 FMP 任何新 endpoint（news_cache 已有 producer）
- ❌ 不动 cron / API / 前端

---

## 1. 实现范围

### 1.1 `news_cache_repository.py` 新增 `get_recent_for_ticker`

**修改** `backend/app/repositories/news_cache_repository.py`，在末尾追加：

```python
def get_recent_for_ticker(
    db: Session,
    ticker: str,
    *,
    scan_date: date,
    lookback_days: int,
    limit: int = 200,
) -> list[NewsArticle]:
    """Return articles in [scan_date - lookback_days, scan_date] whose symbols list contains ticker.

    Filters by as_of_date window at SQL level, then deserializes payload_json and
    filters by ticker in symbols in Python (symbols is JSON inside payload_json, no
    portable SQL filter). Ordered by published_at DESC. limit caps DB-level rows
    fetched before Python filtering.
    """
    start = scan_date - timedelta(days=lookback_days)
    rows = (
        db.query(NewsArticleCache)
        .filter(NewsArticleCache.as_of_date >= start)
        .filter(NewsArticleCache.as_of_date <= scan_date)
        .order_by(NewsArticleCache.published_at.desc())
        .limit(limit)
        .all()
    )
    upper = ticker.upper()
    matched: list[NewsArticle] = []
    for r in rows:
        article = _row_to_article(r)
        symbols = [s.upper() for s in (article.symbols or [])]
        if upper in symbols:
            matched.append(article)
    return matched
```

顶部 import 段追加：`from datetime import timedelta`（既有 `from datetime import date, datetime, timezone`，合并即可）。

### 1.2 `repricing_trigger_service.py` 实装 `_detect_new_product`

**修改** `backend/app/services/cockpit/repricing_trigger_service.py`：

1. **顶部 import 段追加**：
   ```python
   from app.repositories import news_cache_repository as news_repo
   ```

2. **新增 T3 常量段**（位置：T2 常量段之后空一行）：
   ```python
   # T3 NEW_PRODUCT (D4a 关键词扫描) detector 参数 — D098
   T3_LOOKBACK_DAYS = 30
   T3_KEYWORDS = (
       "launch", "unveil", "introduce", "release",
       "AI", "platform", "new product",
   )
   T3_MIN_TOTAL_HITS = 2
   T3_MAX_NEWS_LINKS = 5
   T3_DEFAULT_CONFIDENCE = 0.5  # DATA-MODEL §1107: T3 无高置信路径
   T3_FETCH_LIMIT = 200          # news_cache 30 日内拉取上限（DB-level cap，预期 ticker 量级远 < 200）
   ```

3. **替换占位** `_detect_new_product`（删除 `return None`，按以下伪码实装）：

   ```python
   def _detect_new_product(
       self, ticker: str, scan_date: date,
   ) -> DetectorResult | None:
       """T3 D4a — 最近 30 日该 ticker 的 news headlines 关键词命中总数 ≥ 2 → 触发.

       关键词集合 T3_KEYWORDS（D098）；命中规则：title 大小写不敏感子串匹配；
       同一文章不同关键词都计入；同一关键词在同一标题出现多次按 1 次计（避免重复词刷量）.
       evidence：keyword_hits 按关键词聚合 count + news_links 按 published_at DESC 去重保留前 5.
       confidence 恒为 0.5（DATA-MODEL §1107，T3 无高置信路径）.
       """
       articles = news_repo.get_recent_for_ticker(
           self.db, ticker,
           scan_date=scan_date,
           lookback_days=T3_LOOKBACK_DAYS,
           limit=T3_FETCH_LIMIT,
       )
       if not articles:
           return None

       keyword_counts: dict[str, int] = {}
       hit_urls_in_order: list[str] = []  # 已是 published_at DESC（repo 排序）

       for art in articles:
           title_lower = (art.title or "").lower()
           hit_in_this_article = False
           for kw in T3_KEYWORDS:
               if kw.lower() in title_lower:
                   keyword_counts[kw] = keyword_counts.get(kw, 0) + 1
                   hit_in_this_article = True
           if hit_in_this_article and art.url and art.url not in hit_urls_in_order:
               hit_urls_in_order.append(art.url)

       total_hits = sum(keyword_counts.values())
       if total_hits < T3_MIN_TOTAL_HITS:
           return None

       # 按 count DESC 排序 keyword_hits（同 count 按 T3_KEYWORDS 原顺序稳定排序）
       keyword_hits = [
           {"keyword": kw, "count": keyword_counts[kw]}
           for kw in T3_KEYWORDS
           if kw in keyword_counts
       ]
       keyword_hits.sort(key=lambda x: x["count"], reverse=True)

       return DetectorResult(
           confidence=T3_DEFAULT_CONFIDENCE,
           evidence={
               "keyword_hits": keyword_hits,
               "news_links": hit_urls_in_order[:T3_MAX_NEWS_LINKS],
               "scan_window_days": T3_LOOKBACK_DAYS,
           },
       )
   ```

### 1.3 evidence_json schema（最终落地版）

```json
{
  "keyword_hits": [
    {"keyword": "AI", "count": 3},
    {"keyword": "launch", "count": 2}
  ],
  "news_links": ["https://…/article1", "https://…/article2"],
  "scan_window_days": 30
}
```

- `keyword_hits`：每个命中的关键词聚合 count；按 count DESC 排序，同 count 保留 T3_KEYWORDS 声明顺序；**未命中的关键词不出现**（DATA-MODEL §1099 example 仅列命中项）
- `news_links`：去重 URL 列表，按 published_at DESC，至多 5 条；可为空（命中文章无 url 时）
- `scan_window_days`：恒 30（与 T3_LOOKBACK_DAYS 同源，便于 UI 显示窗口）

与 DATA-MODEL.md §1099 example 1:1 对齐。

### 1.4 Tests

**新建** `backend/tests/test_repricing_trigger_new_product.py`，按 3 个 class 分组 10 个测试（对齐 d2/d3b 模式）：

| Class | # | 测试简述 |
|-------|---|---------|
| `TestNewsCacheGetRecentForTicker`（repo 新方法 ×3） | N1 | happy: 30 日窗口内 + symbols 含 ticker 的行返回，published_at DESC |
| | N2 | symbols 不含 ticker 的行跳过；symbols 含 lowercase 的也匹配（大小写归一） |
| | N3 | scan_date 之外 / scan_date - 30 之前的行被滤掉（边界严格） |
| `TestDetectNewProduct`（detector ×6） | N4 | happy: 2 篇文章共 3 次关键词命中（"AI" ×2 + "launch" ×1）→ 触发；keyword_hits 按 count DESC；news_links 含 2 个 URL；confidence=0.5 |
| | N5 | 单文章多关键词："NVDA unveils new platform with AI" 命中 unveil/AI/platform = 3 次 → 触发；同关键词在同标题多次出现按 1 次计（titles 含 "AI AI AI" → count=1） |
| | N6 | 总命中 = 1（仅 "launch"）→ 不触发（< T3_MIN_TOTAL_HITS）|
| | N7 | ticker 30 日内无 news（articles=[] 或全部 symbols 不含）→ return None |
| | N8 | news_links 至多 5 条：构造 7 篇命中文章 → 取前 5（按 published_at DESC） |
| | N9 | URL 去重 + 缺 URL 容错：3 篇命中但其中 1 篇 url=None → 仅 2 个 URL 进 news_links；不抛错 |
| `TestNewProductEndToEnd`（service ×1） | N10 | `compute_and_store_all_triggers` 端到端：seed 1 active stock + 4 篇命中 news → repricing_triggers 行 active=True trigger_type=NEW_PRODUCT；清空 news 再调用 → soft expire |

**Helper**：
- `_news(db, *, ticker, title, url, published_at, symbols, as_of_date)` 直接 INSERT NewsArticleCache（payload_json 自构造）
- 复用 d2/d3b 的 `_stock` helper

**conftest fixture**：复用既有 `db_session`（sqlite in-memory）。

---

## 2. 预计修改文件

| # | 文件路径 | 改动类型 | 说明 |
|---|---------|---------|------|
| 1 | `backend/app/repositories/news_cache_repository.py` | 修改 | +1 import (timedelta) / +1 函数 `get_recent_for_ticker` (~25 行) |
| 2 | `backend/app/services/cockpit/repricing_trigger_service.py` | 修改 | +1 import (news_repo) / +T3 常量段 7 行 / 替换 `_detect_new_product` 实装（~30 行） |
| 3 | `backend/tests/test_repricing_trigger_new_product.py` | 新建 | 10 测试 / 3 class |

**实际 3 文件**，远低于 6 文件上限。

---

## 3. 可测试的完成标准

| # | 标准描述 | 测试层级 | 工具 |
|---|---------|---------|------|
| 1 | `get_recent_for_ticker` happy：5 篇 news 跨 25 日，symbols 含 ticker 的 3 篇返回，按 published_at DESC | 单元 | pytest |
| 2 | `get_recent_for_ticker` symbols 大小写归一：payload.symbols=["nvda"] + ticker="NVDA" → 匹配；["AAPL"] + ticker="NVDA" → 不匹配 | 单元 | pytest |
| 3 | `get_recent_for_ticker` 时间窗严格：as_of_date < scan_date - 30 或 > scan_date 的行不返回；边界 scan_date - 30 包含 | 单元 | pytest |
| 4 | T3 detector happy（多文多词）：2 篇文章 titles=["AI launch event", "AI rollout"] → keyword_hits=[{"keyword":"AI","count":2},{"keyword":"launch","count":1}]；news_links 含 2 URL；confidence=0.5；scan_window_days=30 | 单元 | pytest |
| 5 | T3 detector 单文多词：1 篇 title="NVDA unveils new platform with AI" → 命中 unveil/platform/AI = 3 次 → 触发；keyword_hits 含 3 项；total_hits=3 ≥ 2 | 单元 | pytest |
| 6 | T3 detector 同词在同标题多次计 1：title="AI AI AI day" → keyword "AI" count=1（同标题内同关键词不刷量；多标题各计 1） | 单元（N5 子断言） | pytest |
| 7 | T3 detector 总命中 < 2：1 篇 title="quarterly launch report" 仅命中 "launch" 1 次 → return None | 单元 | pytest |
| 8 | T3 detector 空数据：ticker 30 日内 0 篇匹配 news → return None；不抛错 | 单元 | pytest |
| 9 | T3 detector news_links cap：7 篇命中文章（不同 url，published_at 递增） → news_links 取最新 5 个（DESC 顺序，与 article URL 出现顺序一致） | 单元 | pytest |
| 10 | T3 detector URL 去重 + null url 容错：3 篇命中，其中 1 篇 url=None → news_links 长度 2，无 None 项；不抛 AttributeError | 单元 | pytest |
| 11 | T3 detector keyword_hits 排序：4 命中分布 launch×1 + AI×3 → keyword_hits=[{"AI",3},{"launch",1}]（count DESC，同 count 按 T3_KEYWORDS 顺序） | 单元（嵌 N4/N5 断言） | pytest |
| 12 | `compute_and_store_all_triggers` 端到端：(1) seed 1 active Stock + 4 篇含 ticker symbols + 关键词 news；(2) 调用 → repricing_triggers 写 1 行 trigger_type=NEW_PRODUCT + active=True + evidence_json keyword_hits/news_links/scan_window_days 齐全；(3) 删 news 再调用 → 同行 active=False（soft expire） | 集成 | pytest |

预期测试数：**10 个**（N6/N11 嵌在 N5/N4 内一并断言）。单文件 `test_repricing_trigger_new_product.py`。

---

## 4. Evaluator 自检清单

- [ ] 10 个新测试全部通过（`cd backend && uv run pytest tests/test_repricing_trigger_new_product.py -v`）
- [ ] d1/d2/d3a/d3b 既有测试仍全绿（`uv run pytest tests/test_repricing_trigger_skeleton.py tests/test_repricing_trigger_earnings_accel.py tests/test_f218_d3a_key_metrics.py tests/test_repricing_trigger_margin_expansion.py -v`）
- [ ] 全量后端回归通过（`uv run pytest`）— 允许 d3b 记录的 9 个 pre-existing failures，不得新增
- [ ] `_detect_new_product` 签名不变 `(self, ticker: str, scan_date: date) -> DetectorResult | None`；返回类型与 T1/T2 一致
- [ ] evidence_json 3 个键齐全且类型正确（list[dict] / list[str] / int），与 DATA-MODEL.md §1099 example schema 1:1 对齐
- [ ] T3 detector fail-out（return None）而非 raise；任一字段 None / empty 不导致 AttributeError / KeyError
- [ ] `news_repo.get_recent_for_ticker` 时间窗包含 `scan_date - 30` 下边界（inclusive），上边界 `scan_date` 也 inclusive
- [ ] `news_articles_cache.symbols` 大小写归一（payload 内 "nvda" vs "NVDA" 不影响匹配）
- [ ] T3 常量段独立于 T1/T2 段，命名前缀 `T3_*` 清晰；关键词集合 T3_KEYWORDS 字面 7 项与 D098 一致
- [ ] T3 detector 不读 news body（仅 title）；不接 FMP；不动 cron / API / 前端
- [ ] news_links 不包含 None / 空字符串 / 重复 URL

### 代码质量检查
- [ ] `_detect_new_product` 函数长度 ≤ 50 行
- [ ] 无硬编码魔法值（2/5/30/0.5 全部抽 T3_* 常量；关键词字面集中在 T3_KEYWORDS）
- [ ] `get_recent_for_ticker` 无副作用、不写 DB
- [ ] 无注释掉的代码 / 死 import / 未使用变量
- [ ] news_cache_repository 既有 `compute_article_key` / `get_cached` / `upsert_many` / `_parse_dt` / `_serialize` / `_row_to_article` 全部不动

### 回归测试
- [ ] 后端全量 `uv run pytest` 通过（允许 9 pre-existing failures，不得新增）
- [ ] cockpit/setup/regime/pool_cache/repricing_trigger（d1+d2+d3a+d3b）未受 import / 字段命名改动影响
- [ ] news/news_service.py 既有调用 `cache_repo.get_cached` 不受影响（不改既有函数签名）
- [ ] 调用 `compute_and_store_all_triggers` 时 T3 detector 串行位置（第 3 个）与 d1 skeleton 一致；T4/T5 仍为占位（return None）

---

## 5. 关键设计决策（执行前确认）

| # | 议题 | 推荐方案 | 备选方案 |
|---|------|---------|---------|
| **NP-d4-1** | 关键词匹配方式 | **A：标题大小写不敏感子串（推荐）**：`kw.lower() in title.lower()`。简单、与 D098 字面"命中关键词"对齐；多词短语 "new product" 天然支持；接受 "AI" → "Ainsley" 偶发假阳（D098 §3.5 已明确接受高 recall 低 precision）。 | (a) **B：词边界 regex (`\bAI\b`)** — 减少假阳但 "AI Day" 命中、"OpenAI" 失败，且 multi-token "new product" 写正则更复杂 / (b) **C：tokenize + set 匹配** — 切词 + lower + set intersect；丢失 multi-word phrase "new product"（除非拼接），复杂 |
| **NP-d4-2** | "≥ 2 次"语义 | **A：跨该 ticker 所有文章关键词命中**总次数**（推荐）**：单文多词 + 多文累计都计；同关键词在同标题出现多次按 1 计避免词刷量。与 DATA-MODEL §1099 example 一致（count=3 + count=2 = 总 5 ≥ 2）。 | (a) **B：≥ 2 不同文章** — 单文多词无法触发，过严，D098 example 暗示 "AI ×3" 单词都能算多次 / (b) **C：≥ 2 不同关键词** — 同关键词多文章不触发，过严 / (d) **D：同关键词同标题多次计 N** — 词刷量风险（一篇 "AI AI AI" 标题假突破阈值） |
| **NP-d4-3** | ticker → 文章映射 | **A：as_of_date SQL 过滤 + Python 端 symbols 包含过滤（推荐）**：复用既有 news_articles_cache 表，不加 ticker 列；`get_recent_for_ticker` 拉 30 日窗口（DB-level limit=200）后 Python 解 payload_json 过滤。Cockpit pool ~50 ticker × 5 detector，30 日内 news 行数预估 < 200/ticker，性能可接受。 | (a) **B：加 ticker 列 + 倒排索引** — 表结构改动 + alembic 024 + 历史数据回填，本 sprint 不接受 / (b) **C：SQLite JSON_EXTRACT** — DB 特化，绑死 sqlite，违反 ARCHITECTURE 数据库无关原则 |
| **NP-d4-4** | T3_FETCH_LIMIT 默认值 | **200（推荐）**：30 日 × ~30 ticker-related articles/day（cockpit pool 平均），200 足够覆盖；提供 DB-level 安全阈防爆炸；从 Python 层进一步过滤 ticker。 | (a) **None / unbounded** — 假设 news_cache 体量大时拖慢 detector / (b) **50** — 30 日窗下 ticker 火热时（如 NVDA earnings 周）可能截断假阴 |
| **NP-d4-5** | confidence 策略 | **恒 0.5（推荐）**：DATA-MODEL §1107 "其余维持 0.5（D096 简化策略）"明确 T3 无高置信路径；可在 D4b NLP 升级时引入 score。本 sprint 不引入命中数 → confidence 映射。 | (a) **命中 ≥ 5 → 0.8** — DATA-MODEL §1107 未提，会引入未文档化阈值 / (b) **关键词权重加权** — D4b 范畴，本 sprint 排除 |
| **NP-d4-6** | news_links 排序 + cap | **published_at DESC + 去重 + 至多 5（推荐）**：与 DATA-MODEL §1099 example 默认顺序一致；前端 RepricingTriggerWidget 行点击展开可看最新 5 条；不展开则隐藏。url=None 的命中文章跳过（不计入 links 但仍计入 keyword_hits）。 | (a) **按命中关键词数排序** — 引入额外排序逻辑且 UI 期望时间顺序 / (b) **保留全部** — DATA-MODEL example 用 2 条示意，无明确上限，但 UI widget 列表挤压；5 条是合理 default |
| **NP-d4-7** | `get_recent_for_ticker` 放哪 | **`news_cache_repository.py` 模块级函数（推荐）**：与既有 `get_cached` / `upsert_many` / `compute_article_key` 同居所；模块级 + Session 注入风格（既有约定）；不改 NewsCacheRepository 类（该文件无 class，全模块函数）。 | (a) **新建 NewsCacheRepository 类** — 与既有风格不符，破坏 news_service.py import 模式 / (b) **放 RepricingTriggerService 内** — 跨域，news 是基础数据层不应耦合 cockpit detector |
| **NP-d4-8** | symbols 大小写处理 | **比较前都 upper（推荐）**：payload.symbols 历史数据可能含 "nvda" / "NVDA" / "Nvda"（FMP 输入未必规范），ticker 列约定全大写；统一 upper 比较避免假阴。 | (a) 严格大小写 — 历史脏数据失配 / (b) lower 比较 — 与项目约定 ticker upper 反向 |
| **NP-d4-9** | T3_KEYWORDS 字面 | **D098 原文 7 项不动（推荐）**：`launch, unveil, introduce, release, AI, platform, new product`。这是与 SRS / D098 一致的可追溯起点；上线后观察命中分布再调（D098 方案 E 已显式放弃"扩到 30+"）。 | (a) 增 "rollout, debut, announce" — 命中率升但 D098 决策刚定，先验证再加 / (b) 删 "AI"（假阳率最高） — 失去 NVDA / META AI 案例识别（D098 example） |
| **NP-d4-10** | T3 触发后是否要 `news_links` 携带 published_at | **否（推荐）**：DATA-MODEL §1099 example 只列 URL；UI 跳转时拉 news_service 详情；evidence 保持精简便于 JSON 序列化体积可控。 | (a) `[{"url":..., "published_at":...}]` — DATA-MODEL example 不一致，违反 schema 1:1 原则 |

### 推荐理由速览

- **NP-d4-1 子串 + lower**：与 D098 字面"命中关键词"对齐；写起来 30 行不到；"AI" 假阳率被 D098 §3.5 已经显式接受作为 D4a 的代价。
- **NP-d4-2 总命中 ≥ 2**：DATA-MODEL §1099 example 列出 `count=3` 和 `count=2` 共 5 hits 触发，暗示按命中"次数"累加；"同关键词同标题计 1" 防词刷量。
- **NP-d4-3 SQL 窗 + Python 过滤**：news 表不改是本 sprint 的最强约束（表结构改动 = 引 alembic 024 = 越 6 文件 + 跨 sprint 范围）；以 cockpit pool 量级，30 日 200 行内 Python 过滤 < 5ms，可接受。
- **NP-d4-5 恒 0.5**：DATA-MODEL §1107 文字已锁死；引入 "≥ N 命中 → 0.8" 等阈值属于 NP-d4-1/2 之后才有的 D4b 范畴。
- **NP-d4-7 模块函数同居所**：news_cache_repository.py 整文件无 class，全模块函数；新增 `get_recent_for_ticker` 是该文件的自然延伸；不引入新文件不破既有 import 模式。
- **NP-d4-8 upper 归一**：payload_json.symbols 历史数据来源 FMP（未必规范）；upper 比较 cost 几乎为 0，但能消除假阴。
- **NP-d4-9 D098 原文不动**：D098 决策刚 confirmed @ 2026-05-18，T3 上线 + 2-3 月数据收集后再迭代关键词集合更稳。

---

## 6. 不在范围（本 sprint 排除）

- ❌ D4b NLP 升级（嵌入相似度 / LLM 标签 / AiGateway 集成）— D098 显式独立 epic
- ❌ 扫描 news 全文 body / 摘要（D098 方案 D 放弃；仅 title）
- ❌ `news_articles_cache` 表结构改动（不加 ticker 列；不加 ticker 索引；不动既有 6 个函数）
- ❌ T4 SECTOR_CYCLE detector 实装（F218-d5）
- ❌ T5 BALANCE_INFLECTION detector + FMP balance-sheet/cash-flow（F218-d6a/d6b）
- ❌ refresh_job.py cron 注册（F218-d7a — 22:40 UTC RepricingTriggerService 调度）
- ❌ router + 2 endpoint `/api/cockpit/repricing-triggers*`（F218-d7a）
- ❌ 前端 widget + DecisionPanel chip 区（F218-d7b）
- ❌ DECISIONS.md 追加（D098 已覆盖；NP-d4-1~10 是实施级决策，本 contract 承载，不升 DXXX）
- ❌ ARCHITECTURE.md / DATA-MODEL.md / API-CONTRACT.md 修改（本 sprint 严格落地无新增 drift）
- ❌ T3 历史回测（NVDA H100 / META Llama / TSLA Cybertruck 等案例验证）— acceptance / d7b 收官时统一做
- ❌ T3 触发后对 setup / decision / position 等下游消费（d7b 前端展示阶段）
- ❌ 关键词集合调参 / 扩展（D098 §放弃方案 E，先观察再加）

---

## 7. 用户待确认

1. **NP-d4-1 ~ NP-d4-10** 十项决策：全部按推荐？还是有需要调整的？重点关注：
   - **NP-d4-1**（关键词匹配 = 子串 + lower）— 决定假阳率（"AI" → "Ainsley"）
   - **NP-d4-2**（≥ 2 总命中 vs 2 不同文章 vs 2 不同关键词）— 决定触发频率
   - **NP-d4-3**（SQL 窗 + Python 过滤，不加 ticker 列）— 决定本 sprint 文件预算
2. **evidence_json schema**（§1.3 最终落地版）是否同意？尤其 `keyword_hits` 排序（count DESC + T3_KEYWORDS 稳定序）与 `news_links` cap=5。
3. **Contract 整体是否同意进入 Generator 模式开发？**

确认后我会：
1. 更新 features.json：`F218-d4` sub_sprints state `design_needed` → `contract_agreed`；`_pipeline_status.active_sprint` 切到 `F218-d4`；`_pipeline_status.active_sprint_phase` → `contract_agreed`
2. 追加 F218 iteration_history 一条 `contract_agreed` 记录（subtask=F218-d4，date=2026-05-19）
3. 更新 claude-progress.txt
4. 生成 SESSION-HANDOFF.md（含 d4 3 步开发顺序：news_cache_repository.get_recent_for_ticker → T3 常量段 + detector 实装 → 10 测试）
5. **强制停止本 session**（feature-dev skill 铁律），输出新 session 恢复指令
