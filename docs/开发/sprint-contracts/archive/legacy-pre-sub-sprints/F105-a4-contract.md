# Sprint Contract：F105-a4 Breakouts 读端点（router + schema + 测试）

> 日期：2026-04-21 | 状态：草案
> 依赖：F105-a1 ✅ done · F105-a2 🔍 needs_review · F105-a3 ✅ done
> 引用文档：
>   API-CONTRACT.md#GET-/api/market/breakouts（权威响应形态）
>   DATA-MODEL.md#MarketBreakoutScan
>   DECISIONS.md#D040（只存最新快照）
>   backend/app/repositories/market_breakout_repository.py（`get_latest_snapshot` 已就绪，返回 `BreakoutSnapshot | None`）
>   backend/app/routers/market.py（既有 `GET /api/market/overview` 作为风格基准）
>   backend/app/schemas/market.py（`MarketIndexOut` + `CamelModel` 既有风格）
>   backend/app/schemas/watchlist.py（`ResponseEnvelope[T]` 泛型包装）

---

## 本次实现范围

**包含**：

### 1. `backend/app/schemas/market.py`（修改）
- 新增两个 Pydantic 模型（`CamelModel` 派生，自动 snake_case → camelCase）：
  - `BreakoutItemOut`：字段对照 API-CONTRACT `items[]`
    - `ticker: str`
    - `company_name: str`
    - `close_price: float`
    - `ma150_value: float`
    - `pct_above_ma150: float`
    - `market_cap: int`
    - 说明：slope/scan_date/scanned_at 不在 item 级别输出；价格类数值由 router 侧 `round(x, 2)` 后塞入（schema 不做取整，避免双重处理）
  - `BreakoutSnapshotOut`：
    - `scan_date: date | None`
    - `scanned_at: datetime | None`
    - `items: list[BreakoutItemOut]`
    - `total: int`

### 2. `backend/app/routers/market.py`（修改）
- 新增 `GET /api/market/breakouts`，`response_model=ResponseEnvelope[BreakoutSnapshotOut]`
- 实现：
  - `snap = MarketBreakoutRepository(db).get_latest_snapshot()`
  - `snap is None` → 返回 `{scanDate: null, scannedAt: null, items: [], total: 0}`
  - 非空 → 遍历 `snap.items`，构造 `BreakoutItemOut(ticker=..., company_name=..., close_price=round(m.close_price, 2), ma150_value=round(m.ma150_value, 2), pct_above_ma150=round(m.pct_above_ma150, 2), market_cap=int(m.market_cap))`
  - 排序由 repository 保证（已按 `pct_above_ma150 ASC`），router 不再排序
  - 纯读：不触发扫描，不捕获数据库异常（由 FastAPI 默认 500 处理，符合 API-CONTRACT）

### 3. `backend/tests/test_market_api.py`（修改，追加用例，不动既有）
新增用例（5 条，全部通过 `client` fixture + `db_session` 直接操作 `MarketBreakoutRepository`）：
- `test_breakouts_empty_returns_null_scan_date`：表空 → `data == {"scanDate": null, "scannedAt": null, "items": [], "total": 0}`
- `test_breakouts_returns_latest_snapshot_sorted_asc`：seed 3 行（同一 scan_date，pct 分别 8.2/1.5/4.7）→ items 按 pct 升序 [1.5, 4.7, 8.2]；total=3；字段集等于 `{ticker, companyName, closePrice, ma150Value, pctAboveMa150, marketCap}`
- `test_breakouts_only_latest_scan_date`：seed 两个 scan_date（旧日期 2 行 + 新日期 1 行），通过不同 `scanned_at` 区分 → 只返回新 scan_date 的 1 行，`scanDate` 等于新日期
- `test_breakouts_rounds_prices_to_two_decimals`：seed 一行 `close_price=850.5051, ma150_value=812.309, pct_above_ma150=4.7013` → 响应中分别为 850.51 / 812.31 / 4.70；`marketCap` 原样整数返回
- `test_breakouts_response_envelope_shape`：响应外层是 `{"data": {...}, "message": "success"}`（与既有 `overview` 风格一致）

---

## 明确排除（不在本 Sprint）
- 扫描触发逻辑（F105-a3 已完成）
- `/api/stocks/:ticker/chart` on-demand fallback（F105-b）
- 前端 widget（F105-c）
- 历史快照 / 手动触发扫描 端点（API-CONTRACT 明确不提供）
- 错误响应特殊处理（FastAPI 默认即满足）

---

## 预计修改文件（共 3 个）

| # | 文件路径 | 改动类型 | 说明 |
|---|---------|---------|------|
| 1 | `backend/app/schemas/market.py` | 修改 | 追加 `BreakoutItemOut` + `BreakoutSnapshotOut` |
| 2 | `backend/app/routers/market.py` | 修改 | 追加 `GET /api/market/breakouts` handler |
| 3 | `backend/tests/test_market_api.py` | 修改 | 追加 5 条用例 |

👤 用户确认后进入开发。

---

## 可测试的完成标准

| # | 标准描述 | 测试层级 | 工具 |
|---|---------|---------|------|
| 1 | 空快照返回 `scanDate: null`, `scannedAt: null`, `items: []`, `total: 0` | 集成 | pytest + TestClient |
| 2 | 有命中快照时按 `pctAboveMa150` 升序返回，total 正确 | 集成 | pytest |
| 3 | 多个 scan_date 时只返回最新一次 scan_date 的条目 | 集成 | pytest |
| 4 | 价格字段四舍五入到 2 位小数；`marketCap` 原样整数 | 集成 | pytest |
| 5 | 响应外层为 `ResponseEnvelope`（`{data, message:"success"}`）| 集成 | pytest |
| 6 | 字段名 camelCase，与 API-CONTRACT 严格一致 | 集成 | pytest set equality |
| 7 | `pytest backend/tests/` 全量回归全绿 | 集成 | pytest |
| 8 | `mypy backend/app/routers/market.py backend/app/schemas/market.py` 严格通过 | 静态 | mypy |

---

## Evaluator 自检清单

- [ ] `pytest backend/tests/test_market_api.py` 全绿（既有 4 条 + 新增 5 条 = 9 条）
- [ ] `pytest backend/tests/` 全量回归全绿（F001–F105-a3）
- [ ] `mypy backend/app/routers/market.py backend/app/schemas/market.py` 严格通过
- [ ] 响应字段集与 API-CONTRACT 544–569 行字节级一致（含 camelCase key、`null` 空态、`total` 字段）
- [ ] router handler ≤ 50 行
- [ ] 无硬编码 / 无魔法值（取整位数 `2` 为行内字面量，仅出现在 `round(x, 2)` 处，不抽常量）
- [ ] router 不做排序（依赖 repository 已排序），不做过滤，不捕获异常
- [ ] `features.json` F105.subtasks.F105-a4.phase 流转 `contract_agreed → in_progress → testing → needs_review`
- [ ] claude-progress.txt 追加 F105-a4 完成记录
- [ ] DECISIONS.md 无需新增条目（本 Sprint 纯合约实现）

### 代码质量检查
- [ ] 无死代码 / 无 print
- [ ] 单函数 ≤ 50 行
- [ ] 无重复代码（item 构造单一出口）

### 回归测试
- 当前 feature 全绿后运行 `pytest backend/tests/` 全量
- 新增失败若由 a4 引入 → 打回 Generator；预先存在则标注并上报用户

---

👤 确认此 Contract 后开始开发。
