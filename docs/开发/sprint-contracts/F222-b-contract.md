---
status: confirmed
feature: F222
sub_sprint: F222-b
date: 2026-07-02
confirmed_at: 2026-07-02
---

# F222-b Sprint Contract — Watchlist 颜色标记：后端写路径（`PUT /api/watchlist/{ticker}/color`）

> 生成：2026-07-02 | 状态：草案 → 待确认
> Feature：[F222](../../需求/features.json) Watchlist 颜色标记
> Sub-sprint：F222-b（共 3 个 sub-sprint 的第 2 个；backend 写路径）
> 前置：F001 done（Watchlist 管理已上线）；F222-a done（`Stock.label_color` 列 + `GET /api/signals` 读路径已跑通并测试覆盖）；system-design 阶段已完成 DATA-MODEL / API-CONTRACT 全部更新（本 sprint 开发前无需再改任何设计文档）
> 下游：F222-c（frontend：`ColorTagButton`/Popover + `WatchlistWidget` 接入，需 a + b 都 done 才能真正联调）
>
> 引用文档：
> - [API-CONTRACT.md §Watchlist `PUT /api/watchlist/{ticker}/color`](../../系统设计/API-CONTRACT.md) — 请求/响应/错误码定义（2026-07-02 system-design 已确认）
> - [DATA-MODEL.md §Stock](../../系统设计/DATA-MODEL.md) — `label_color` 字段 + 枚举值表 + `is_active` 语义定义
> - [DECISIONS.md D110](../../系统设计/DECISIONS.md) — 字段/挂载点/token 设计决策
> - [schemas/watchlist.py](../../../backend/app/schemas/watchlist.py) / [stock_repository.py](../../../backend/app/repositories/stock_repository.py) / [watchlist_service.py](../../../backend/app/services/watchlist_service.py) / [routers/watchlist.py](../../../backend/app/routers/watchlist.py) / [tests/test_watchlist_api.py](../../../backend/tests/test_watchlist_api.py) — 待修改文件
> - [F222-a-contract.md](F222-a-contract.md) — 同 feature 前序 sub-sprint，本合同结构对齐

---

## 0. 背景与定位

F222（Watchlist 颜色标记）因预计修改文件数（14 个，backend 9 + frontend 5）超出 6-file 上限，拆分为 3 个 sub-sprint：F222-a（backend 读路径，done）→ F222-b（backend 写路径，本合约）→ F222-c（frontend）。

F222-b 补上"写入口"：新增 `PUT /api/watchlist/{ticker}/color`，让用户能设置/清除某个 watchlist ticker 的颜色标记。F222-a 已经让整条读路径（DB → repo → service → schema → API）跑通，本 sprint 只补对称的写路径，读写共用同一 `Stock.label_color` 列，不新增表、不新增字段。

---

## 1. 实现范围

### 1.1 `schemas/watchlist.py` 新增请求/响应模型

```python
class UpdateColorRequest(CamelModel):
    color: Literal["red", "yellow", "blue"] | None


class UpdateColorResponse(CamelModel):
    ticker: str
    label_color: Literal["red", "yellow", "blue"] | None = None
```

- `color` 无 default → 请求体必须显式带 `color` 键（可以是合法枚举值或 `null`），缺失该键触发 422 VALIDATION_ERROR（由既有全局 `RequestValidationError` handler 统一处理，无需新代码）。
- `UpdateColorResponse` 序列化为 `{"ticker": "AAPL", "labelColor": "red"}`，与 API-CONTRACT.md 响应示例一致。

### 1.2 `stock_repository.py` 新增 `set_label_color`

```python
def set_label_color(self, stock: Stock, color: str | None) -> Stock:
    stock.label_color = color
    self.db.commit()
    self.db.refresh(stock)
    return stock
```

与 `soft_delete` / `reactivate` 同款模式：直接 mutate 传入的 ORM 对象 + commit + refresh。

### 1.3 `watchlist_service.py` 新增 `update_color`

```python
def update_color(self, raw_ticker: str, color: str | None) -> Stock:
    ticker = raw_ticker.strip().upper()
    stock = self.repo.get_by_ticker(ticker)
    if stock is None or not stock.is_active:
        raise APIError("NOT_FOUND", f"ticker {ticker} not in watchlist", 404)
    return self.repo.set_label_color(stock, color)
```

- ticker 大小写不敏感（`.strip().upper()`），与 `add_stock`/`remove_stock` 一致。
- NOT_FOUND 判定沿用 `remove_stock()` 同款逻辑（行不存在 或 `is_active=False`），源自 DATA-MODEL.md 对 `is_active` 的定义"是否在 watchlist 中"。
- `color` 合法性完全交给 Pydantic `Literal[...]` 在 schema 层校验（枚举类型无"空白字符串"一类的漏网场景，不需要 service 层重复判断），与 F222-a 确立的"写入校验只在一层做"原则一致。

### 1.4 `routers/watchlist.py` 新增路由

```python
@router.put("/{ticker}/color", response_model=ResponseEnvelope[UpdateColorResponse])
def update_color(
    ticker: str,
    payload: UpdateColorRequest,
    service: WatchlistService = Depends(get_watchlist_service),
) -> ResponseEnvelope[UpdateColorResponse]:
    stock = service.update_color(ticker, payload.color)
    return ResponseEnvelope(
        data=UpdateColorResponse(ticker=stock.ticker, label_color=stock.label_color)
    )
```

### 1.5 `tests/test_watchlist_api.py` 追加测试

新增一段 `# F222-b: PUT /api/watchlist/{ticker}/color (TC1–TC7)`，延续既有 T/TB 编号风格，覆盖：

| 用例 | 场景 | 期望 |
|------|------|------|
| TC1 | 已存在的 active ticker，设 `color="red"` | 200，响应 `labelColor=="red"`；DB 持久化 |
| TC2 | 已有颜色的 ticker，传 `color=null` | 200，响应 `labelColor is None`；DB 清除为 `NULL` |
| TC3 | 路径参数小写 `aapl` | 200（大小写不敏感） |
| TC4 | `color` 传非法值（如 `"green"`） | 422，`error.code == "VALIDATION_ERROR"` |
| TC5 | ticker 从未加入过 watchlist | 404，`error.code == "NOT_FOUND"` |
| TC6 | ticker 已软删除（`is_active=false`） | 404，`error.code == "NOT_FOUND"` |
| TC7 | 请求体缺少 `color` 键 | 422，`error.code == "VALIDATION_ERROR"` |

### 1.6 明确排除（本 sprint 不做）

- `GET /api/watchlist`、`GET /api/signals`、`GET /api/signals/:ticker` 的任何改动 —— 读路径已在 F222-a 完成，本 sprint 不碰
- 任何前端文件（`ColorTagButton`、`WatchlistWidget`、API client、类型定义、CSV 导出）—— 归 F222-c
- 批量设置颜色的接口 —— 需求未提出，不做（YAGNI）
- DATA-MODEL.md / API-CONTRACT.md 文档改动 —— system-design 阶段已完整覆盖读写两路径，本 sprint 无需再改

---

## 2. 预计修改文件（共 5 个）

| 文件路径 | 改动类型 | 说明 |
|---------|---------|------|
| `backend/app/schemas/watchlist.py` | 修改 | 新增 `UpdateColorRequest` + `UpdateColorResponse` |
| `backend/app/repositories/stock_repository.py` | 修改 | 新增 `set_label_color(stock, color)` |
| `backend/app/services/watchlist_service.py` | 修改 | 新增 `update_color(ticker, color)`，含 NOT_FOUND 校验 |
| `backend/app/routers/watchlist.py` | 修改 | 新增 `PUT /{ticker}/color` 路由 |
| `backend/tests/test_watchlist_api.py` | 修改 | 追加 TC1–TC7 共 7 个用例 |

👤 用户确认文件列表合理后，方可进入开发。

---

## 3. 文档同步

已在 system-design 阶段（F222 立项时）全部同步，**本 sprint 开发前无需再改任何文档**：

- API-CONTRACT.md §Watchlist：`PUT /api/watchlist/{ticker}/color` 完整定义（请求/响应/错误码）已写入
- DATA-MODEL.md §Stock：`label_color` 字段 + 枚举值表已写入（F222-a 已消费过一次，本次复用同一定义）
- DECISIONS.md：D110 已记录字段 / 挂载点 / token 设计决策，覆盖读写两路径

唯一例外：若 Generator 阶段发现实现细节与已写文档不符，按规则 5 停下改文档再继续，不得静默偏离。

---

## 4. 可测试的完成标准

| # | 标准描述 | 测试层级 | 工具 |
|---|---------|---------|------|
| 1 | `PUT .../color` 设置 `red`/`yellow`/`blue` → 200，响应 `labelColor` 与请求一致，DB 持久化 | 集成 | pytest + TestClient |
| 2 | `PUT .../color` 传 `null` → 200，响应 `labelColor` 为 `null`，DB 清除 | 集成 | pytest + TestClient |
| 3 | ticker 路径参数大小写不敏感 | 集成 | pytest + TestClient |
| 4 | `color` 非法枚举值 → 422 VALIDATION_ERROR | 集成 | pytest + TestClient |
| 5 | ticker 从未加入 watchlist → 404 NOT_FOUND | 集成 | pytest + TestClient |
| 6 | ticker 已软删除（`is_active=false`）→ 404 NOT_FOUND | 集成 | pytest + TestClient |
| 7 | 请求体缺少 `color` 字段 → 422 VALIDATION_ERROR | 集成 | pytest + TestClient |
| 8 | 全量后端 pytest 套件无新增失败 | 回归 | pytest |

---

## 5. 已确认的协商点

本 sprint 无非显然技术决策分叉——请求/响应字段类型、NOT_FOUND 判定逻辑、repository 写入模式均直接沿用 API-CONTRACT.md / DATA-MODEL.md / F222-a 已确立的代码惯例（`Literal[...]` 风格、`soft_delete`/`reactivate` 同款 mutate-commit-refresh 模式、`remove_stock` 同款 NOT_FOUND 判定），无需用户在多个合理方案间选择。

---

## 6. Evaluator 自检清单

开发完成后，Evaluator 模式逐条检查：

- [ ] `cd backend && pytest tests/test_watchlist_api.py -v` 全通过（含新增 TC1–TC7）
- [ ] `cd backend && pytest` 全量回归无新增失败
- [ ] API 响应格式符合 API-CONTRACT.md §Watchlist `PUT .../color` 定义（字段名 / 类型 / 位置 / 错误码）
- [ ] 数据库字段命名符合 DATA-MODEL.md §Stock 定义（`label_color`）
- [ ] 无 `print` / 调试日志残留
- [ ] 无死代码（未使用 import 等）
- [ ] ruff / mypy 通过（如项目 lint pipeline 包含）
- [ ] **实现范围严格等于本 Contract §1**（无超出、无遗漏；尤其未误动 `GET /api/watchlist`、`GET /api/signals`、任何前端文件）
- [ ] **修改文件严格等于本 Contract §2 清单**（5 个，无新增无遗漏）
- [ ] features.json `F222.sub_sprints['F222-b']`：Generator 开始时 `contract_agreed` → `in_progress`；Evaluator 通过后 → `done`

---

## 7. 完成后的衔接

- F222-b `done` → 触发 consistency-check C1：检查 sibling sub_sprint（F222-a done / F222-c）是否也全部 done；F222-c 未 done 则父 feature F222 保持 `in_progress`，**不得**误升 `done`
- F222-c 进入 Sprint Contract 协商：frontend `ColorTagButton` + Popover 交互 + `WatchlistWidget` 接入 + API client + CSV 导出携带颜色列（a + b 都 done 后才能真正联调）
- F222 整体 `needs_review` 等待 acceptance（a + b + c 全部 done 后）

---

👤 **待用户确认。** 确认后将执行：Step 3（frontmatter → confirmed；features.json 的 `sub_sprints`/`_pipeline_status.active_sprint` 更新；追加 claude-progress.txt；更新 SESSION-HANDOFF.md）→ Step 4（git commit）→ Step 5（输出新 session 指令并停止，本 session 不进入 Generator）。
