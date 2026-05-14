# Sprint Contract：F110-a Watchlist 批量添加接口（后端）

> 日期：2026-04-22 | 状态：**待确认，暂不执行**
> 父 Feature：F110 Watchlist CSV 导入/导出
> 依赖：F001（`POST /api/watchlist` 单条添加）、D034（FMP 作为外部数据源）
> 引用文档：
>   `docs/系统设计/API-CONTRACT.md#Watchlist（/api/watchlist）`
>   `docs/系统设计/DATA-MODEL.md#Stock`（字段权威）

---

## 背景

F110 总体目标：Watchlist 支持 CSV 批量导入（"in" 图标）和导出（"out" 图标）。经 6 文件原则拆分：
- **F110-a（本 Sprint）**：后端批量添加接口 `POST /api/watchlist/bulk`
- **F110-b（下一 Sprint）**：前端 CSV UI，调用本 sprint 产出的接口

为什么需要 bulk 接口而非前端循环单条：
1. 减少 N 次 HTTP 往返延迟
2. 一次数据库事务可汇报"重复 / 未找到"清单，前端可在单个 toast 中反馈
3. 避免前端并发导致的 FMP rate-limit 触发

---

## 本次实现范围

### 1. `backend/app/schemas/watchlist.py`（修改）

新增以下 schema：

```python
class BulkAddRequest(BaseModel):
    tickers: list[str] = Field(..., min_length=1, max_length=200)

class BulkAddResult(BaseModel):
    added: list[WatchlistCreatedItem]
    skipped_duplicate: list[str]   # 已在 watchlist 的 ticker（大写）
    not_found: list[str]           # FMP 查不到的 ticker（大写）
```

### 2. `backend/app/services/watchlist_service.py`（修改）

新增方法 `bulk_add_stocks(tickers: list[str]) -> dict[str, Any]`：

- 遍历传入 ticker 列表
- 每个 ticker：
  - `strip().upper()` 规范化；跳过空字符串；去重（本次请求内）
  - 调用现有 `self.add_stock(ticker)`（复用校验、FMP lookup、DB 写入、backfill 逻辑）
  - 捕获 `APIError`：
    - `code == "DUPLICATE"` → 加入 `skipped_duplicate`
    - `code == "NOT_FOUND"` → 加入 `not_found`
    - 其他（如 `EXTERNAL_API_ERROR`）→ 抛出，中止整个 batch（返回 502）
- 返回 `{"added": [build_created_payload(stock), ...], "skipped_duplicate": [...], "not_found": [...]}`

> **决策点 D-F110a-1**：单个 ticker FMP 网络失败时的策略——"快速失败"而非"容错继续"。理由：避免半成功状态（已添加 50 个，51 个网络失败，52 个又成功）造成前端和用户认知混乱。需要记入 DECISIONS.md。

### 3. `backend/app/routers/watchlist.py`（修改）

新增路由：

```python
@router.post(
    "/bulk",
    response_model=ResponseEnvelope[BulkAddResult],
    status_code=status.HTTP_200_OK,  # 批量，不用 201
)
def bulk_add(
    payload: BulkAddRequest,
    service: WatchlistService = Depends(get_watchlist_service),
) -> ResponseEnvelope[BulkAddResult]:
    result = service.bulk_add_stocks(payload.tickers)
    return ResponseEnvelope(data=BulkAddResult.model_validate(result))
```

### 4. `backend/tests/test_watchlist_api.py`（修改）

新增测试用例（使用现有 `fmp_stub` fixture 模式）：

| # | 测试 | 期望 |
|---|------|------|
| T1 | bulk 添加 3 个全新 ticker | 200，`added=3, skipped_duplicate=0, not_found=0` |
| T2 | bulk 包含 1 个已存在 + 2 个新 | 200，`added=2, skipped_duplicate=["EXISTING"]` |
| T3 | bulk 包含 1 个 FMP 不存在的 ticker | 200，`not_found=["FAKE"]` |
| T4 | bulk 混合 新/重复/无效 | 200，三个桶各有一项 |
| T5 | bulk 大小写混合 `["aapl", "MSFT"]` | 全部规范化为大写，写入成功 |
| T6 | bulk 含重复 ticker `["AAPL", "aapl"]` | 仅写入一次（`added=1`） |
| T7 | bulk 空数组 | 422 VALIDATION_ERROR |
| T8 | bulk 超过 200 个 | 422 VALIDATION_ERROR |
| T9 | FMP lookup 抛异常（非 NOT_FOUND） | 502 EXTERNAL_API_ERROR，整个 batch 中止 |

### 5. `docs/系统设计/API-CONTRACT.md`（修改）

在 `POST /api/watchlist` 段落之后插入 `POST /api/watchlist/bulk` 文档：
- 用途、请求体、成功响应示例（含三个桶）、错误码（VALIDATION_ERROR / EXTERNAL_API_ERROR）
- 明注：单次请求上限 200；不保证原子性（部分 ticker 写入后失败会保留已写入的）

### 6. `docs/需求/features.json`（修改）

- 在 `_version_groups` 新增 v1.4 分组（或追加到 v1.3），登记 F110
- 新增 F110 顶层条目 + `subtasks.F110-a` / `subtasks.F110-b`
- F110-a 初始 `phase: "contract_agreed"`，指向本合约文件

---

## 明确排除

- 前端 CSV 解析 / 文件选择 / 下载按钮 → F110-b
- 前端 `bulkAddStocks` API 客户端 → F110-b
- CSV 文件格式标题行校验 → F110-b（前端职责）
- `GET /api/watchlist` 返回结构变更 → 不在本 feature
- 批量删除接口 → 不在本 feature（未来可 `DELETE /bulk`）
- 异步任务化（后台跑 backfill 队列） → 不在本 feature；backfill 沿用现有"每条同步调用 DataRefreshService"

---

## 预计修改文件（共 6 个）

| # | 文件 | 类型 | 改动 |
|---|------|------|------|
| 1 | `backend/app/schemas/watchlist.py` | 修改 | +`BulkAddRequest` / `BulkAddResult` |
| 2 | `backend/app/services/watchlist_service.py` | 修改 | +`bulk_add_stocks()` |
| 3 | `backend/app/routers/watchlist.py` | 修改 | +`POST /api/watchlist/bulk` |
| 4 | `backend/tests/test_watchlist_api.py` | 修改 | +9 个 bulk 测试 |
| 5 | `docs/系统设计/API-CONTRACT.md` | 修改 | 新增 bulk endpoint 文档 |
| 6 | `docs/需求/features.json` | 修改 | 登记 F110 / F110-a / F110-b |

DECISIONS.md 追加 D-F110a-1（如需记录"快速失败"策略）不计入 6 文件上限，作为决策记录在结尾追加。

---

## 可测试的完成标准

| # | 标准 | 测试层级 | 工具 |
|---|------|----------|------|
| 1 | `POST /api/watchlist/bulk` 返回 200 + `{added, skipped_duplicate, not_found}` 三桶 | 集成 | pytest + TestClient |
| 2 | 已存在 ticker 落入 `skipped_duplicate` 桶，未触发重复写入 | 集成 | pytest |
| 3 | FMP 不存在的 ticker 落入 `not_found` 桶 | 集成 | pytest + FMP stub |
| 4 | 请求内大小写混合 / 重复 ticker 正确规范化去重 | 单元 | pytest |
| 5 | 空数组 / 超过 200 个 → 422 | 集成 | pytest |
| 6 | FMP 非 NOT_FOUND 异常 → 502，batch 中止 | 集成 | pytest + FMP mock raise |
| 7 | 每个新增 ticker 触发 backfill（沿用 `add_stock` 行为） | 集成 | pytest 观察 repo/bar 状态 |
| 8 | API-CONTRACT.md bulk 段落存在且示例与实现一致 | 文档 | grep/人工 |
| 9 | features.json F110-a phase 为 `needs_review`（通过 Evaluator 后） | 文档 | 人工 |

---

## Evaluator 自检清单

- [ ] `pytest backend/tests/test_watchlist_api.py -v` 全部通过（含新增 9 条）
- [ ] 全量回归 `pytest backend/tests/ -v` 通过
- [ ] `curl -X POST localhost:8000/api/watchlist/bulk -d '{"tickers":["AAPL"]}'` 手工验证响应结构
- [ ] API-CONTRACT.md 示例响应 JSON 可与实际响应 diff 对比
- [ ] features.json 解析有效（`python -c "import json; json.load(open('docs/需求/features.json'))"`）
- [ ] DECISIONS.md 如有追加 D-F110a-1 已写明"快速失败"理由

### 代码质量检查
- [ ] `bulk_add_stocks` 函数行数 ≤ 50
- [ ] 无重复逻辑（复用 `add_stock` 而非 copy-paste FMP lookup）
- [ ] 无硬编码魔法值（200 上限写入常量 `BULK_ADD_MAX = 200`）
- [ ] 异常处理遵循 boundary 原则（per-ticker APIError 捕获，其他冒泡）

### 回归测试
- 既有 `POST /api/watchlist` 单条路径不变：`added_stock_single` / `duplicate_ticker_409` / `not_found_404` 原测试全部通过
- `GET /api/watchlist` 返回结构无变化
- backfill 机制：bulk 后的多个 ticker 应像单条一样触发 `DataRefreshService`（不修改 backfill 逻辑本身）

---

## F110-b（前端）前置依赖清单

F110-a 完成后，F110-b 可直接使用：
1. `POST /api/watchlist/bulk` endpoint（本 sprint 产出）
2. 响应 schema 固定为 `{added: WatchlistCreatedItem[], skipped_duplicate: string[], not_found: string[]}`
3. CSV 上传流程："解析 CSV → 取 ticker 列 → 调用 bulk → 展示三桶结果 toast"

---

## 暂停点（2026-04-22）

本合约**已起草，待用户确认后**方可进入 Generator 模式。用户表示"写好 contract 后停一下，要新开 session"，**本 session 不启动开发**。

下个 session 恢复指令（选其一）：
- "做 F110-a" / "开始开发 F110-a" → 进入 Generator
- "修改合约：[具体内容]" → 调整本文件后再确认
