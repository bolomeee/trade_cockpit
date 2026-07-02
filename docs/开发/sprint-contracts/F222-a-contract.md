---
status: confirmed
feature: F222
sub_sprint: F222-a
date: 2026-07-02
confirmed_at: 2026-07-02
---

# F222-a Sprint Contract — Watchlist 颜色标记：后端读路径（Stock.label_color 列 + GET /api/signals 暴露）

> 生成：2026-07-02 | 状态：草案 → 待确认
> Feature：[F222](docs/需求/features.json) Watchlist 颜色标记
> Sub-sprint：F222-a（共 3 个 sub-sprint 的第 1 个；backend 读路径）
> 前置：F001 done（Watchlist 管理已上线）；system-design 阶段已完成 DATA-MODEL / API-CONTRACT / design-spec / component-plan 全部更新（本 sprint 开发前无需再改任何设计文档）
> 下游：F222-b（backend 写路径：`PUT /api/watchlist/{ticker}/color` + repo/service/router + 测试，F222-a done 后开启）→ F222-c（frontend：ColorTagButton/Popover + WatchlistWidget 接入，需 a+b 都 done 才能联调）
>
> 引用文档：
> - [DATA-MODEL.md §Stock](docs/系统设计/DATA-MODEL.md) — `label_color` 字段定义 + 枚举值表（2026-07-02 system-design 已确认）
> - [API-CONTRACT.md §Signals GET /api/signals](docs/系统设计/API-CONTRACT.md) — `labelColor` 字段定义（2026-07-02 system-design 已确认）
> - [DECISIONS.md D110](docs/系统设计/DECISIONS.md) — 字段/挂载点/token 设计决策
> - [signal.py](backend/app/schemas/signal.py) / [signal_service.py](backend/app/services/signal_service.py) — 待修改文件
> - [025_f219a_setup_macd_divergence.py](backend/alembic/versions/025_f219a_setup_macd_divergence.py) / [test_setup_macd_f219a.py](backend/tests/test_setup_macd_f219a.py) — 同类型 nullable 枚举列 + 迁移测试样板（本合同结构对齐）

---

## 0. 背景与定位

F222（Watchlist 颜色标记）因预计修改文件数（14 个，backend 9 + frontend 5）超出 6-file 上限，拆分为 3 个 sub-sprint：F222-a（backend 读路径）→ F222-b（backend 写路径）→ F222-c（frontend）。

F222-a 只做"列存在 + 只读暴露"：新增 `Stock.label_color` 列，让 `GET /api/signals` 响应携带 `labelColor` 字段。此时字段恒为 `null`（写入口尚不存在），但整条读路径（DB → repo → service → schema → API）先跑通、有测试覆�盖，降低 F222-b 落地写入口时的联调风险。

---

## 1. 实现范围

### 1.1 Stock 模型新增列（`backend/app/models/stock.py`）

在 `shares_float_refreshed_at` 之后追加：

```python
label_color = Column(String(10), nullable=True)  # F222: 'red' / 'yellow' / 'blue' / None
```

### 1.2 alembic migration（新文件 `backend/alembic/versions/026_f222_stock_label_color.py`）

```python
"""F222-a: stocks label_color column (Watchlist color tagging)

Revision ID: 026_f222_stock_label_color
Revises: 025_f219a_setup_macd_divergence
Create Date: 2026-07-02
"""
from alembic import op
import sqlalchemy as sa

revision = "026_f222_stock_label_color"
down_revision = "025_f219a_setup_macd_divergence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "stocks",
        sa.Column("label_color", sa.String(10), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("stocks", "label_color")
```

不回填：新列，已有行自然为 `NULL`。

### 1.3 `SignalBoardItem` schema 新增字段（`backend/app/schemas/signal.py`）

```python
from typing import Literal  # 新增 import

class SignalBoardItem(CamelModel):
    ticker: str
    name: str
    signal_type: str
    date: date
    close_price: float
    ma150_value: float | None = None
    distance_pct: float | None = None
    slope_positive: bool | None = None
    slope_value: float | None = None
    label_color: Literal["red", "yellow", "blue"] | None = None  # 新增（F222），序列化为 labelColor
```

`Literal[...]` 而非泛化 `str | None`：与既有 `DataStatus = Literal["loading", "insufficient", "ready"]`（`schemas/watchlist.py`）风格一致，且与 F222-b 写路径请求体 schema 类型对齐。

### 1.4 `signal_service.py` 传值（`_build_board_item()`）

```python
def _build_board_item(stock: Stock, signal: Signal) -> dict[str, Any]:
    return {
        "ticker": stock.ticker,
        "name": stock.name,
        "signalType": signal.signal_type,
        "date": signal.date,
        "closePrice": signal.close_price,
        "ma150Value": signal.ma150_value,
        "distancePct": signal.distance_pct,
        "slopePositive": signal.slope_positive,
        "slopeValue": signal.slope_value,
        "labelColor": stock.label_color,  # 新增（F222）
    }
```

只读，不做值校验（校验只在 F222-b 的写路径 Pydantic schema 层做一次；读路径信任已持久化数据，与项目现有分层惯例一致）。

### 1.5 明确排除（本 sprint 不做）

- `GET /api/watchlist`、`GET /api/signals/:ticker`（`SignalLatest` / `TickerSignalDetail` / `SignalHistoryEntry`）—— 均不加 `labelColor`；API-CONTRACT.md 只在 `GET /api/signals` 一处新增该字段
- 任何写入口（`PUT /api/watchlist/{ticker}/color`、repository/service 写方法、`schemas/watchlist.py` 的 `UpdateColorRequest`）—— 归 F222-b
- 任何前端文件（组件 / API client / 类型 / CSV 导出）—— 归 F222-c
- 历史数据回填 —— 新列，已有行自然为 `NULL`，无需回填

---

## 2. 预计修改文件（共 5 个）

| 文件路径 | 改动类型 | 说明 |
|---------|---------|------|
| `backend/app/models/stock.py` | 修改 | 新增 `label_color = Column(String(10), nullable=True)` |
| `backend/alembic/versions/026_f222_stock_label_color.py` | 新增 | upgrade 加列 nullable；downgrade 删列；不回填 |
| `backend/app/schemas/signal.py` | 修改 | 新增 `from typing import Literal`；`SignalBoardItem` 新增 `label_color: Literal["red","yellow","blue"] \| None = None`（序列化为 `labelColor`） |
| `backend/app/services/signal_service.py` | 修改 | `_build_board_item()` 返回 dict 新增 `"labelColor": stock.label_color` |
| `backend/tests/test_watchlist_label_color_f222a.py` | 新增 | migration 升降级 cycle 测试 + `GET /api/signals` labelColor 字段测试（默认 null / 显式值透传两种） |

👤 用户确认文件列表合理后，方可进入开发。

---

## 3. 文档同步

已在 system-design 阶段（本会话更早完成）全部同步，**本 sprint 开发前无需再改任何文档**：

- DATA-MODEL.md §Stock：`label_color` 字段 + 枚举值表已写入
- API-CONTRACT.md §Signals：`GET /api/signals` 的 `labelColor` 字段已写入
- DECISIONS.md：D110 已记录字段 / 挂载点 / token 设计决策

唯一例外：若 Generator 阶段发现实现细节与已写文档不符，按规则 5 停下改文档再继续，不得静默偏离。

---

## 4. 可测试的完成标准

| # | 标准描述 | 测试层级 | 工具 |
|---|---------|---------|------|
| 1 | alembic upgrade head 后 `stocks` 表含 `label_color` 列 | 集成 | pytest + alembic |
| 2 | alembic downgrade -1 后 `label_color` 列消失 | 集成 | pytest + alembic |
| 3 | upgrade → downgrade → upgrade 三段干净 | 集成 | pytest + alembic |
| 4 | `GET /api/signals`：未设置 `label_color` 的 stock，响应项 `labelColor` 为 `null` | 集成 | pytest + TestClient |
| 5 | `GET /api/signals`：直接在 DB 设置 `stock.label_color = "red"` 后，响应项 `labelColor == "red"` | 集成 | pytest + TestClient |
| 6 | 全量后端 pytest 套件无新增失败 | 回归 | pytest |

---

## 5. 已确认的协商点

本 sprint 无非显然技术决策分叉——字段类型、迁移策略、camelCase 序列化方式均直接沿用 DATA-MODEL.md / DECISIONS.md D110 / 既有代码惯例（`Literal[...]` 风格、`soft_delete` 同款 migration 结构），无需用户在多个合理方案间选择。

---

## 6. Evaluator 自检清单

开发完成后，Evaluator 模式逐条检查：

- [ ] `cd backend && pytest tests/test_watchlist_label_color_f222a.py -v` 全通过（新增 5 个用例）
- [ ] `cd backend && alembic upgrade head && alembic downgrade -1 && alembic upgrade head` 三段干净
- [ ] `cd backend && pytest` 全量回归无新增失败
- [ ] API 响应格式符合 API-CONTRACT.md §Signals 定义（`labelColor` 字段名 / 类型 / 位置）
- [ ] 数据库字段命名符合 DATA-MODEL.md §Stock 定义（`label_color`）
- [ ] 无 `print` / 调试日志残留
- [ ] 无死代码（未使用 import 等）
- [ ] ruff / mypy 通过（如项目 lint pipeline 包含）
- [ ] **实现范围严格等于本 Contract §1**（无超出、无遗漏；尤其未误动 `GET /api/watchlist` 或 `/api/signals/:ticker`）
- [ ] **修改文件严格等于本 Contract §2 清单**（5 个，无新增无遗漏）
- [ ] features.json `F222.sub_sprints['F222-a']`：Generator 开始时 `contract_agreed` → `in_progress`；Evaluator 通过后 → `done`

---

## 7. 完成后的衔接

- F222-a `done` → 触发 consistency-check C1：检查 sibling sub_sprint（F222-b / F222-c）是否也全部 done；未全部 done 则父 feature F222 保持 `in_progress`，**不得**误升 `done`
- F222-b 进入 Sprint Contract 协商：写入口 `PUT /api/watchlist/{ticker}/color`（`schemas/watchlist.py` 新增 `UpdateColorRequest` + `stock_repository.py` 新增 `set_label_color` + `watchlist_service.py` 新增 `update_color` + `routers/watchlist.py` 新增路由 + `tests/test_watchlist_api.py` 新增测试，预计 5 文件，6-file 内）
- F222-c（frontend）需等 F222-a + F222-b 都 done 才能真正联调（读依赖 a，写依赖 b）
- F222 整体 `needs_review` 等待 acceptance（a + b + c 全部 done 后）

---

👤 **待用户确认。** 确认后将执行：Step 3（frontmatter → confirmed；features.json 的 `sub_sprints`/`_pipeline_status.active_sprint` 更新；追加 claude-progress.txt；更新 SESSION-HANDOFF.md）→ Step 4（git commit）→ Step 5（输出新 session 指令并停止，本 session 不进入 Generator）。
