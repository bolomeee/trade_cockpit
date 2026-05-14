# Sprint Contract：F106-b 多信号扫描 API 层（后端）

> 日期：2026-04-21 | 状态：**反向补契约**
> 依赖：F106-a（scanner_params / 4 条 detector / signal_type 字段）
> 引用文档：
>   API-CONTRACT.md#GET-/api/market/breakouts
>   DECISIONS.md#D039（FMP SMA 主用 / EOD 回退）
>   scanner_params.py#DEFAULT_API_SIGNAL_TYPES
>   features.json#F106#acceptance_criteria[6-7]

---

## 本次实现范围（Sprint B：API / 外部客户端适配）

### 1. `backend/app/routers/market.py`（修改）
- `GET /api/market/breakouts` 新增 `?type=` query 参数：
  - 不传 → 默认 `P.DEFAULT_API_SIGNAL_TYPES`（= a1/a2/b2，legacy 不返回）
  - 传 `?type=legacy_crossover,a1_stage_breakout` → 按逗号分割过滤，仅返回这些类型
  - 非法 signal_type → `400` `HTTPException`，detail 列出非法值
  - 空串 / 全空 → 当作未传处理
- 响应每条 item 追加字段：`signal_type / slope_value / volume / volume_ratio_20`（volume* 可空）
- 过滤层下传给 repository：调用 `get_latest_snapshot(signal_types=...)`

### 2. `backend/app/schemas/market.py`（修改）
- `BreakoutItemOut` 追加字段：
  - `signal_type: str`（必填）
  - `slope_value: float`（必填，MA150 斜率）
  - `volume: int | None = None`
  - `volume_ratio_20: float | None = None`
- 保持 `CamelModel` 输出 camelCase（`signalType / slopeValue / volume / volumeRatio20`）

### 3. `backend/app/external/fmp_client.py`（修改）
- `_SMA_DEFAULT_WINDOW_DAYS: 35 → 90` calendar days（对齐 `scanner_params.FETCH_WINDOW_CALENDAR_DAYS`，满足 A1 60 交易日横盘检测）
- `get_company_screener_page` 签名扩展：
  - `is_etf: bool = False` 改 `is_etf: bool | None = None`（None 则不下传该参数）
  - 新增 `is_fund: bool | None = None`
- `get_screener_universe` 调用改为 `is_fund=False`（显式排除 mutual fund，保留普通股 + ADR + ETF，覆盖 F105 原有范围）
- `get_ma150_series_or_eod` 返回的 bar 中需包含 `volume` 字段（若 FMP 已返回则透传，A1 规则强依赖）

### 4. `backend/app/repositories/market_breakout_repository.py`（微调，若 F106-a 未涵盖）
- 确保 `get_latest_snapshot(signal_types: tuple[str, ...] | None = None)` 支持过滤参数
- 返回的 item 含 `signal_type / slope_value / volume / volume_ratio_20` 字段（从 model 读取）

### 5. `docs/系统设计/API-CONTRACT.md`（修改）
- `GET /api/market/breakouts` 小节：
  - 追加 `?type=` query 参数描述（默认值、合法枚举、非法返回 400）
  - items[] 字段追加 `signalType / slopeValue / volume / volumeRatio20`
  - 示例 response body 替换为含多 signalType 的新样例

---

## 明确排除

- scanner 核心计算（→ F106-a）
- 前端类型定义 + widget Tabs 改造（→ F106-c）

---

## 预计修改文件（共 5 个）

| # | 文件 | 类型 | 改动 |
|---|---|---|---|
| 1 | `backend/app/routers/market.py` | 修改 | `?type=` + 4 新字段透传 + 400 校验 |
| 2 | `backend/app/schemas/market.py` | 修改 | `BreakoutItemOut` 追加 4 字段 |
| 3 | `backend/app/external/fmp_client.py` | 修改 | SMA 窗口 35→90 + `is_fund` 参数 + universe 调用 |
| 4 | `backend/app/repositories/market_breakout_repository.py` | 修改 | `get_latest_snapshot(signal_types=)` 过滤 |
| 5 | `docs/系统设计/API-CONTRACT.md` | 修改 | `/api/market/breakouts` 契约条目 |

> 说明：文件 4 与 F106-a 的 repo 改动可能重叠，两个 contract 声明本字段归属以避免遗漏；实际 commit 会体现为一次 repo.py 改动。

---

## 可测试的完成标准

| # | 标准 | 层级 |
|---|---|---|
| 1 | `GET /api/market/breakouts` 默认仅返回 a1/a2/b2；legacy 不出现 | 集成 |
| 2 | `?type=legacy_crossover` → 仅返回 legacy | 集成 |
| 3 | `?type=a1_stage_breakout,b2_ma_pullback` → 仅返回这两类 | 集成 |
| 4 | `?type=foo` → 400，detail 含 `invalid signal_type: foo` | 集成 |
| 5 | `?type=` 空串 → 当默认处理，200 | 集成 |
| 6 | response items[] 每条含 `signalType / slopeValue / volume / volumeRatio20`（volume 可为 null）| 集成 |
| 7 | FMP SMA 请求窗口为 90 calendar days（单元层断言 query 参数）| 单元 |
| 8 | `get_company_screener_page(is_fund=False)` → 请求参数含 `isFund=false`，不含 `isEtf` | 单元 |
| 9 | API-CONTRACT.md 新条目通过文档对比与代码一致 | 手工 |
| 10 | `pytest backend/tests/` 全量回归全绿 | 集成 |

---

## Evaluator 自检清单

- [ ] `pytest backend/tests/test_market_router.py`（或等价文件）新增 5 条用例（默认 / legacy / 多类 / 非法 / 空串）
- [ ] `pytest backend/tests/test_fmp_client.py` 新增 SMA 窗口 + `is_fund` 单元测试
- [ ] `pytest backend/tests/` 全量回归全绿
- [ ] mypy `routers/market.py` / `schemas/market.py` / `external/fmp_client.py` 严格通过
- [ ] 响应字段名一致：OpenAPI schema 中 `signalType / slopeValue / volumeRatio20` 为 camelCase
- [ ] API-CONTRACT.md 的请求参数、响应示例、错误码均与实现一致
- [ ] features.json `F106.phase` 流转到 `testing`（由 F106-c 完成后统一流转到 needs_review）

### 代码质量检查
- [ ] `?type=` 解析与验证逻辑 ≤ 15 行
- [ ] 无硬编码 signal_type 字面量（均走 `scanner_params` 常量）
- [ ] `BreakoutItemOut` 字段顺序与 DATA-MODEL.md 对齐

### 回归测试
- 全量 pytest + `pnpm --filter frontend typecheck`（前端不动但要确认 OpenAPI 变更没破坏 codegen，如有）

---

⚠️ **反向补契约**：fmp_client 的 SMA 窗口从 35→90 已改，需要 Evaluator 确认既有 F105 测试在新窗口下仍绿（F105 legacy crossover 只读近端 bar，理论无影响，但需验证）。
