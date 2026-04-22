# Sprint Contract — F107-b3：Fundamentals 增加 Float 绝对值显示

> 协商日期：2026-04-22
> 依赖：F107-b1（shares_float DB cache + FMP fallback）/ F107-b2（图表 Vol/Float 比率）

## 1. 范围

### 包含
- 后端 `/api/stocks/:ticker/fundamentals` 响应顶层新增 `sharesFloat: int | null`
- 复用 F107-b1 已有的 `_resolve_shares_float_for_watchlist`（24h TTL DB 缓存 + FMP `/stable/shares-float` 回源），不新增 service 方法、不新增缓存层
- 前端 `Fundamentals` 类型 + `FundamentalsCard` 新增一行 "Float"，单位 `15.23B / 1.52B / 987.65M`（与现有 `formatCurrency` 同口径，无 `$` 前缀）
- API-CONTRACT.md / DECISIONS.md（D054）追加

### 排除
- 不动 `/chart` 的 sharesFloat（F107-b1 已交付）
- 不动 watchlist 校验（F108 范围）
- 不引入新的格式化工具函数（在 FundamentalsCard 内部加 `formatShares` 即可，避免跨文件耦合）
- 不动 stocks 表 schema、不写新 alembic 迁移

## 2. 预计修改文件（共 7 个，已确认豁免 6 文件上限）

| # | 文件 | 类型 | 改动要点 |
|---|------|------|---------|
| 1 | `backend/app/services/stock_detail_service.py` | 修改 | `get_fundamentals` 内 `stocks.get_by_ticker(ticker)` → `_resolve_shares_float_for_watchlist(stock)` → 拼入 `sharesFloat`；stock 不存在或 active=False 时 `sharesFloat = None`（不抛错，与现有 chart fallback 语义对齐） |
| 2 | `backend/app/schemas/stock_detail.py` | 修改 | `Fundamentals` 增 `shares_float: int \| None = None` |
| 3 | `backend/tests/test_stock_detail.py` | 修改 | 新增 2 用例（见 §4） |
| 4 | `frontend/src/types/stockDetail.ts` | 修改 | `Fundamentals` 接口增 `sharesFloat: number \| null` |
| 5 | `frontend/src/components/features/stock-detail/FundamentalsCard.tsx` | 修改 | 内部 `formatShares(n)` 函数；`right` 列追加 `{ label: 'Float', value: f ? formatShares(f.sharesFloat) : null }` |
| 6 | `docs/系统设计/API-CONTRACT.md` | 修改 | fundamentals §响应示例 + 字段表追加 sharesFloat |
| 7 | `docs/系统设计/DECISIONS.md` | 修改 | 追加 D054 |

## 3. 关键契约

### 3.1 字段语义
- `sharesFloat: int | null`
- 数据源：`stocks.shares_float`（24h TTL，由 F107-b1 D050 缓存）；DB miss / 过期 → FMP `/stable/shares-float` 回源并写回；ticker 不在 watchlist / inactive → `null`
- null 语义：FMP 无 `floatShares` 也无 `sharesFloat` 字段 / 非 watchlist / FMP 调用失败（吞错保留 stock.shares_float 旧值）

### 3.2 前端单位格式（B1 已确认）
```
n >= 1e9  → `${(n/1e9).toFixed(2)}B`     // 15.23B
n >= 1e6  → `${(n/1e6).toFixed(2)}M`     // 987.65M
n < 1e6   → `${n.toLocaleString()}`      // 极少见的兜底
n == null → '—'
```
不带 `$` 前缀（区分于 marketCap / FCF 的货币口径）。

### 3.3 行位置
`right` 列追加为最后一行，顺序为 `ROCE / FCF / Float`。`left` 列保持 `P/E / P/S / PEG` 不动。

## 4. 测试用例

### 后端
| # | 用例 | 层级 | 工具 |
|---|------|------|------|
| 1 | watchlist ticker 命中 DB 缓存：fundamentals 响应 sharesFloat == 缓存值，无 FMP 调用 | 集成 | pytest + TestClient + fake_fmp |
| 2 | watchlist ticker DB 无值：fundamentals 触发 FMP get_shares_float，回写 DB，响应携带值 | 集成 | pytest |
| 3 | （可选回归）已有 `test_fundamentals_merges_ratios_and_key_metrics` 等 4 个用例补 `sharesFloat` 字段断言（None 默认） | 集成 | pytest |

### 前端
- 类型 + build 通过即可（`pnpm typecheck && pnpm build`）。无新增 vitest 用例（formatShares 是 4 行内联函数）。

### E2E
- `docker compose up`，访问任一 watchlist ticker 的详情面板，Fundamentals 卡片显示 `Float: 15.23B`；切换至无 sharesFloat 的 ticker 显示 `—`，无 console.error。

## 5. Evaluator 自检清单

- [ ] 后端：`pytest backend/tests/test_stock_detail.py -v` 全通过（含新增 2 用例）
- [ ] 后端：`pytest backend/tests/ -q` 全量回归不降级
- [ ] 前端：`pnpm typecheck` 通过
- [ ] 前端：`pnpm build` 通过
- [ ] API 响应：`curl /api/stocks/AAPL/fundamentals` 顶层有 `sharesFloat`，类型 number 或 null
- [ ] UI 对照 design：FundamentalsCard 显示 6 行（左 3 + 右 3），Float 在右列末位，格式 `xx.xxB / xx.xxM`
- [ ] null 状态显示 `—`，无 console.error
- [ ] API-CONTRACT.md 字段表 + 响应示例已更新
- [ ] DECISIONS.md D054 已追加（"fundamentals 响应携带 sharesFloat，复用 F107-b1 缓存路径"）
- [ ] features.json：F107-b3 phase → needs_review，estimated_files_changed 修正为实际 7 个

## 6. 不在本 Sprint 内的事项
- F108：fundamentals/pullbacks 放开 watchlist 限制
- 共享 `formatShares` 工具到 `lib/format.ts`（后续若多处复用再抽）
