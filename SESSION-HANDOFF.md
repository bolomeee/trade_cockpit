# SESSION-HANDOFF.md

> 生成时间：2026-04-19
> 当前分支：`feat-newfeature`（从 main 切出，v1.1.0 已发布）
> 刚完成：**system-design 变更 — D034 数据源从 Polygon 迁移至 FMP（仅文档）**
> 下一步：**feature-dev 接手 F104，按 3 个 sprint 实施迁移**

---

## 本 Session 完成的内容

### 背景
v1.1.0 Workbench 发布后，用户确认 Polygon Stocks Starter **缺 CapEx 字段**导致 FCF 无法真算（F103 卡住）。同价位 FMP Starter 实测一次 `/stable/ratios-ttm` 直出 PE / PS / PEG / ROCE / FCF 全部 5 项 + marketCap，决定整体替换。

### 产出（四份文档 + 一份 features.json）

1. **`docs/系统设计/DECISIONS.md` 追加 D034**（~120 行）
   - 触发原因、4 方案对比（A 整体替换 / B 仅 fundamentals / C 升级 Polygon / D 换其他；采用 A）
   - 6 条风险 + 回滚路径（polygon_client.py 保留作 revert 锚点）
   - P0/P1 迁移影响清单表（17 个文件/模块，对应 feature-dev 的 Sprint 切分）
   - frontmatter `confirmed_at: 2026-04-19`

2. **`docs/系统设计/ARCHITECTURE.md`**
   - 系统边界图外部依赖框 Polygon → FMP `/stable/`
   - 新增"外部数据源：FMP /stable/ 端点映射"章节：端点映射表（搜索/日线/指数/10Y/基本面）、rate limit 对比（5/min → 300/min token bucket burst 50）、实时性边界、endpoint 常量集中管理约定
   - 依赖层级规则 + 目录结构：`external/fmp_client.py` 主，`polygon_client.py` DEPRECATED 保留
   - env 变量：新增 `FMP_API_KEY`，`POLYGON_API_KEY` 标 legacy
   - frontmatter `confirmed_at: 2026-04-19`

3. **`docs/系统设计/API-CONTRACT.md`**
   - `/api/stocks/:ticker/fundamentals`：新增 `roce` 字段；完整字段语义表（源 / null 语义 / 计算口径）；`source: "fmp"`；errors 追加 `EXTERNAL_API_ERROR 502`
   - `/api/stocks/search`：说明改 FMP `search-symbol` + `search-name` 两阶段，D028 排序规则保留
   - `/api/stocks/:ticker/chart`：数据源切 FMP `historical-price-eod/full`，schema 零变化
   - `/api/market/overview`：SPX/NDX 走 `^GSPC/^NDX`，TNX 走 `/treasury-rates.year10`；DB symbol 保持 `SPX/NDX/TNX`
   - 全局错误码 `EXTERNAL_API_ERROR` 说明改 FMP
   - frontmatter `confirmed_at: 2026-04-19`

4. **`docs/需求/features.json`**
   - F103 标 `phase: deprecated`，新增 `superseded_by: F104` + `deprecated_at` + `deprecated_reason`，保留审计痕迹
   - 新增 **F104「数据源迁移到 FMP」**：P0，`phase: ready_to_dev`，3 sessions，17 个预计变更文件，10 条验收标准
   - 顶层 `_infrastructure_note` + `completion_rate` 同步更新
   - JSON 语法已验证通过

### 未动

- ❌ 任何代码（本次约束：只出文档）
- ❌ `DATA-MODEL.md`（字段命名、表结构、枚举全部保留，FMP 在 service 边界做映射）
- ❌ Frontend 类型定义（`Fundamentals` / `ChartPoint` / `MarketIndex` 零改动是 D034 的强约束）
- ❌ `.env.example`（等 feature-dev S1 实装时改）

---

## 当前状态

- 工作目录：`/Users/wonderer/Desktop/Claude workspace/stock_portal`
- 分支：`feat-newfeature`（status clean，本次文档变更未提交）
- 未提交文件：
  - `docs/系统设计/DECISIONS.md`
  - `docs/系统设计/ARCHITECTURE.md`
  - `docs/系统设计/API-CONTRACT.md`
  - `docs/需求/features.json`
- pipeline status：`system_design` 保持 `done`（变更协议场景，不是重走 init）

---

## 下一步任务（F104，feature-dev 接手）

按 DECISIONS D034 的影响清单切 3 个 Sprint：

### Sprint 1：FMP 客户端 + 测试替身
- 新建 `backend/app/external/fmp_client.py`（httpx，300/min token bucket burst 50，集中声明 endpoint 常量）
- 封装 5 个方法：`search_tickers` / `get_daily_bars` / `get_index_recent_bars` / `get_treasury_10y_latest` / `get_ratios_ttm`
- `config.py` 新增 `fmp_api_key`，`polygon_api_key` 改注释 legacy
- `.env.example` + `.env` 加 `FMP_API_KEY`
- `backend/tests/test_polygon_client.py` → 重命名 `test_fmp_client.py`，新 case 覆盖端点/rate limit/错误处理
- `backend/tests/conftest.py` 新增 `fake_fmp` fixture（同既有 `fake_polygon` 接口签名）
- `polygon_client.py` 顶部加 `DEPRECATED` 标记（不删文件，不删 tests 外的引用）

**验收**：新 `fmp_client.py` 单元测试全通；既有 162 个 pytest 暂时不动，仍用 fake_polygon。

### Sprint 2：服务层 + 路由迁移
- `dependencies.py`：`get_polygon_client` → `get_fmp_client`
- `main.py` + `routers/data.py` + `services/refresh_job.py`：factory 类型重命名
- `services/watchlist_service.py`：两阶段搜索（`search-symbol` 前缀 → `search-name` fallback），**保留 D028 的"前缀命中优先"排序**
- `services/data_refresh_service.py`：`get_daily_aggs` 调用点 + bar 映射器（Agg.timestamp ms → FMP date YYYY-MM-DD）
- `services/market_refresh_service.py`：指数 `^GSPC/^NDX` 映射为 DB 的 `SPX/NDX`；`/treasury-rates` 读 `year10`
- 162 个既有 pytest 全量迁到 `fake_fmp` fixture，契约层回归而非真打 API
- 新增 ≥5 个 `@pytest.mark.live` smoke test（默认 skip，手动打真实 FMP）

**验收**：`pytest` 全绿；`POST /api/data/refresh` 在 30 只 watchlist 下 <60s。

### Sprint 3：Fundamentals 真实接入 + UI 清理
- `services/stock_detail_service.py`：`_mock_fundamentals` 删除，改调 `fmp.get_ratios_ttm` + 字段映射（见 API-CONTRACT 字段语义表）
- 前端 `FundamentalsWidget.tsx`：删除 "Mock Data" 提示条；`source === 'fmp'` 无 banner
- 联调：真实 AAPL 响应对比用户实测数据（P/E 33.84 / P/S 9.12 / PEG 5.75 / ROCE 65.03% / FCF $104B）

**验收**：F104 的 10 条 acceptance_criteria 全过；pnpm build + pytest 全绿。

---

## 未决事项 / 需警戒

1. **FMP 300/min 文档未验证**：Sprint 1 实装时若 live smoke test 触发 429，回退到保守 token bucket（建议 60/min），并在 DECISIONS 追记
2. **FMP 搜索语义差异**：`search-symbol` 子串匹配是否能严格前缀？实装时若发现无法重现 D028 的"前缀优先"排序，需在 service 层手动排序，不要降级 UX
3. **indices 端点选型**：`quote` vs `historical-price-eod/full`——前者实时快但可能在盘中变化；本项目 EOD 场景推荐用 EOD full 取最新两条算 change_pct，Sprint 2 实装时确认
4. **`search-symbol` / `search-name` 分页**：FMP Starter 是否有默认 limit？若 <20 需考虑合并两次调用结果
5. **ratios-ttm 的 PEG 口径**：FMP 基于 5 年增长率推算；与 Bloomberg/Yahoo 惯用的 1 年 forward 不同。用户已接受（实测 AAPL PEG 5.75 = 5 年口径），不需改
6. **polygon_client.py 的 tests**：`test_polygon_client.py` 重命名为 `test_fmp_client.py` 后，原 test 不保留（polygon 不再被 import，deprecated 模块不需测试）；回滚时可从 git 恢复

---

## 相关文档

- 决策：`docs/系统设计/DECISIONS.md` D034（本次主决策） + D002/D032（原 fundamentals mock 决策，已被 D034 取代）
- 架构：`docs/系统设计/ARCHITECTURE.md#外部数据源fmp-stable-端点映射d034`
- 合约：`docs/系统设计/API-CONTRACT.md`（`/fundamentals`、`/search`、`/chart`、`/overview`）
- 需求：`docs/需求/features.json` F103（deprecated）+ F104（ready_to_dev）
- 代码锚点：`backend/app/external/polygon_client.py`（现状，Sprint 1 后标 DEPRECATED）
