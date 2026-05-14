# Sprint Contract：F203-b1 — UserSettings 数据/接入栈

> 状态：草案 | 起草：2026-04-25
> 父 Feature：F203 Decision Panel
> 兄弟：F203-a ✅ done；**F203-b1（本 Sprint）**；F203-b2（Decision 服务/接入）；F203-c（Chart 前端）；F203-d（Decision Card + Settings 表单 前端）
> 引用文档：
>   - DATA-MODEL.md §UserSettings（L499–521 + L903–915 ORM 示例）
>   - API-CONTRACT.md §Cockpit User Settings（L1219–1267）
>   - DECISIONS.md D066（user_settings 单行 + 仓位公式）
>   - DECISIONS.md D070（cockpit 参数管理 — `user_settings` 4 字段**不进** cockpit_params.py，进 DB）

---

## 0. 背景与定位

F203-b 总文件 9 个，按 6 文件原则拆为 b1 + b2：

- **F203-b1（本 Sprint）**：UserSettings 全栈 — model + alembic（含默认行 data migration）+ repo + schema + router（`GET/PUT /api/cockpit/user-settings`）+ 测试
- **F203-b2**：Decision 全栈 — `decision_service` + `cockpit_params §4 DECISION` + schema + router（`GET /api/cockpit/decision/{ticker}`）+ 测试。b2 直接 `import UserSettingsRepository`，依赖 b1 已落表。

完成 b1 后：前端可单独通过 user-settings 端点读写账户参数；F203-d Settings 表单可独立开工，不再阻塞 b2。

### ⚠️ 已知预置脏区（开工时需处理）

工作树中已存在以下未提交修改，是早前会话预置但未完成的"半成品"：

- `backend/app/models/__init__.py`：已 `from app.models.user_settings import UserSettings` —— 但 `user_settings.py` 不存在，**当前 backend 无法启动**。本 Sprint 第 1 步落 model 文件即可让 import 成立，无需回滚 __init__.py。
- `backend/app/routers/cockpit/__init__.py`：已 `from app.routers.cockpit.decision import router as decision_router` 并 `include_router(decision_router)` —— 但 `decision.py` 不存在。本 Sprint **必须把这两行注释掉或删除**（留给 F203-b2 重新加回），否则 b1 落地后 backend 仍起不来。

---

## 1. 实现范围

### 1.1 `backend/app/models/user_settings.py`（新建）

完全照搬 DATA-MODEL.md L903–915：

```python
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Column, DateTime, Float, Integer, String

from app.models import Base


class UserSettings(Base):
    __tablename__ = "user_settings"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_user_settings_single_row"),
    )

    id = Column(Integer, primary_key=True)  # 常量 1
    account_size = Column(Float, nullable=False, default=100000.0)
    max_exposure_pct = Column(Float, nullable=False, default=80.0)
    single_trade_risk_pct = Column(Float, nullable=False, default=1.0)
    default_risk_per_trade_pct = Column(Float, nullable=False, default=0.75)
    base_currency = Column(String(8), nullable=False, default="USD")
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
```

### 1.2 `backend/alembic/versions/011_f203b1_user_settings.py`（新建）

revision id：`011_f203b1_user_settings`，down_revision：`010_f202a_setup_snapshots`。

```python
def upgrade() -> None:
    op.create_table(
        "user_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_size", sa.Float(), nullable=False, server_default=sa.text("100000.0")),
        sa.Column("max_exposure_pct", sa.Float(), nullable=False, server_default=sa.text("80.0")),
        sa.Column("single_trade_risk_pct", sa.Float(), nullable=False, server_default=sa.text("1.0")),
        sa.Column("default_risk_per_trade_pct", sa.Float(), nullable=False, server_default=sa.text("0.75")),
        sa.Column("base_currency", sa.String(8), nullable=False, server_default=sa.text("'USD'")),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_user_settings_single_row"),
    )
    # data migration: insert default id=1 row
    op.execute(
        "INSERT INTO user_settings (id, account_size, max_exposure_pct, single_trade_risk_pct, "
        "default_risk_per_trade_pct, base_currency, updated_at) "
        "VALUES (1, 100000.0, 80.0, 1.0, 0.75, 'USD', CURRENT_TIMESTAMP)"
    )

def downgrade() -> None:
    op.drop_table("user_settings")
```

### 1.3 `backend/app/repositories/user_settings_repository.py`（新建）

```python
class UserSettingsRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self) -> UserSettings | None:
        """返回 id=1 行；不存在返回 None（不写库）。"""

    def get_or_default(self) -> dict:
        """
        GET 端点用：行存在 → 返回 ORM dict；不存在 → 返回 DATA-MODEL 默认值 dict（不写库）。
        返回 dict 字段：account_size / max_exposure_pct / single_trade_risk_pct /
                       default_risk_per_trade_pct / base_currency / updated_at（None 当默认）。
        """

    def upsert(self, patch: dict) -> UserSettings:
        """
        PUT 端点用：取 id=1 行（无则建），按 patch 中存在的字段覆盖；
        刷新 updated_at；commit；refresh 后返回 ORM 实例。
        patch 中不存在的字段保留原值（partial update）。
        """
```

### 1.4 `backend/app/schemas/cockpit/user_settings.py`（新建）

```python
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class _CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class UserSettingsData(_CamelModel):
    account_size: float
    max_exposure_pct: float
    single_trade_risk_pct: float
    default_risk_per_trade_pct: float
    base_currency: str
    updated_at: datetime | None  # 行不存在时 None


class UserSettingsResponse(BaseModel):
    data: UserSettingsData
    message: str = "success"


class UserSettingsUpdate(_CamelModel):
    """PUT 请求体；所有字段可选；未传字段不覆盖。"""

    account_size: float | None = Field(default=None, gt=0)  # accountSize > 0 → 422
    max_exposure_pct: float | None = Field(default=None, ge=0, le=100)  # ∈ [0, 100]
    single_trade_risk_pct: float | None = Field(default=None, ge=0, le=5)  # ∈ [0, 5]
    default_risk_per_trade_pct: float | None = Field(default=None, ge=0, le=5)
    base_currency: str | None = Field(default=None, min_length=1, max_length=8)
```

> 校验范围严格按 API-CONTRACT.md 的错误响应表（accountSize > 0 / maxExposurePct ∈ [0,100] / singleTradeRiskPct ∈ [0,5]）。`default_risk_per_trade_pct` 合约未明列上限 → 沿用 [0,5] 与 single_trade 同档（保守，不放行 5%+）。

### 1.5 `backend/app/routers/cockpit/user_settings.py`（新建）

```python
router = APIRouter(prefix="/user-settings", tags=["cockpit-user-settings"])


def _get_repo(db: Session = Depends(get_db)) -> UserSettingsRepository:
    return UserSettingsRepository(db)


@router.get("", response_model=UserSettingsResponse)
def get_user_settings(repo: UserSettingsRepository = Depends(_get_repo)) -> UserSettingsResponse:
    return UserSettingsResponse(data=UserSettingsData(**repo.get_or_default()))


@router.put("", response_model=UserSettingsResponse)
def put_user_settings(
    patch: UserSettingsUpdate,
    repo: UserSettingsRepository = Depends(_get_repo),
) -> UserSettingsResponse:
    # patch.model_dump(exclude_unset=True, by_alias=False) → 仅传入字段进 upsert
    row = repo.upsert(patch.model_dump(exclude_unset=True, by_alias=False))
    return UserSettingsResponse(data=UserSettingsData.model_validate(row))
```

校验失败由 Pydantic 自动 422（与 chart router `?days=50` 等价）。

### 1.6 `backend/app/routers/cockpit/__init__.py`（修改 — 注册行）

- 新增 `from app.routers.cockpit.user_settings import router as user_settings_router`
- 新增 `router.include_router(user_settings_router)`
- **同时清理脏区**：删除 `from app.routers.cockpit.decision import router as decision_router` 及其 `include_router(decision_router)` 行（留给 F203-b2 重新加回）

> 方案 B 共识：__init__.py 注册行不计入 6 文件主清单。

### 1.7 `backend/tests/test_user_settings_f203b1.py`（新建）

参见 §3 完成标准 S1–S12。

---

## 2. 预计修改文件

**主清单（6 个）**：

| # | 文件 | 类型 |
|---|------|------|
| 1 | `backend/app/models/user_settings.py` | 新建 |
| 2 | `backend/alembic/versions/011_f203b1_user_settings.py` | 新建 |
| 3 | `backend/app/repositories/user_settings_repository.py` | 新建 |
| 4 | `backend/app/schemas/cockpit/user_settings.py` | 新建 |
| 5 | `backend/app/routers/cockpit/user_settings.py` | 新建 |
| 6 | `backend/tests/test_user_settings_f203b1.py` | 新建 |

**注册行（不计入主清单，方案 B）**：

| 文件 | 改动 |
|------|------|
| `backend/app/routers/cockpit/__init__.py` | +2 行（user_settings router 注册）/ -2 行（清理 b2 脏区） |

`backend/app/models/__init__.py` 已预置 UserSettings import，本 Sprint **不再修改**（落 model 文件即让 import 成立）。

---

## 3. 完成标准（可测试）

| # | 标准 | 层级 | 工具 |
|---|------|------|------|
| S1 | `UserSettingsRepository.get()` 表为空 → 返回 None；插入 id=1 后 → 返回 ORM 实例，字段值正确 | 单元 | pytest + in-memory SQLite |
| S2 | `get_or_default()` 表为空 → 返回 dict（account_size=100000.0 / max_exposure_pct=80.0 / single_trade_risk_pct=1.0 / default_risk_per_trade_pct=0.75 / base_currency='USD' / updated_at=None），**不触发 INSERT**（事后查表行数仍为 0） | 单元 | pytest |
| S3 | `get_or_default()` id=1 行存在 → 返回该行字段 dict，updated_at 非 None | 单元 | pytest |
| S4 | `upsert({'account_size': 200000})` 表为空 → 创建 id=1 行，account_size=200000，其他字段为默认值；返回的 updated_at 不为 None | 单元 | pytest |
| S5 | `upsert({'single_trade_risk_pct': 0.5})` 在已有行上 → 仅 single_trade_risk_pct 改 0.5，account_size/max_exposure_pct 等保留原值；updated_at 推进 | 单元 | pytest |
| S6 | `upsert({})` → 不抛错；id=1 行存在则仅推进 updated_at；不存在则创建带全默认值的行 | 单元 | pytest |
| S7 | Alembic 迁移 `011_f203b1_user_settings` upgrade → 表存在 + 唯一行 id=1 + 全字段为 DATA-MODEL 默认值；downgrade → 表消失 | 集成 | alembic command + raw SQL |
| S8 | `GET /api/cockpit/user-settings` 表为空 → 200，data 等于默认值 dict（updatedAt=null），表行数仍为 0 | 集成 | FastAPI TestClient |
| S9 | `GET /api/cockpit/user-settings` 表有 id=1 行 → 200，data 字段 camelCase（accountSize / maxExposurePct / singleTradeRiskPct / defaultRiskPerTradePct / baseCurrency / updatedAt） | 集成 | TestClient |
| S10 | `PUT /api/cockpit/user-settings` body `{"accountSize": 150000, "singleTradeRiskPct": 0.75}` → 200，response.data.accountSize=150000，default_risk_per_trade_pct 保留默认 0.75；DB 中 id=1 行真实更新 | 集成 | TestClient |
| S11 | `PUT` 422 矩阵：`{"accountSize": 0}` / `{"accountSize": -1}` / `{"maxExposurePct": 101}` / `{"maxExposurePct": -0.1}` / `{"singleTradeRiskPct": 5.1}` / `{"singleTradeRiskPct": -0.5}` 各自 422 | 集成 | TestClient（参数化 6 case） |
| S12 | `PUT` 后立即 `GET` → 返回值与 PUT 响应一致（持久化生效，无缓存问题） | 集成 | TestClient |
| S13 | 全量回归：`pytest backend/tests/` 通过，仅 `test_news_api` 1 条 pre-existing failure，无新增 | 回归 | pytest |

---

## 4. Evaluator 自检清单

### 文件存在性
- [ ] 主清单 6 文件全部存在，路径与 §2 一致
- [ ] `routers/cockpit/__init__.py` 已删除 `decision_router` 残留 import，新增 `user_settings_router` 注册
- [ ] 没有触碰 F203-b2 范围（`decision_service.py` / `decision.py` router / `cockpit_params.py §4` 均不在本 Sprint）

### D066 / D070 合规性
- [ ] model `__table_args__` 包含 `CheckConstraint("id = 1", ...)`
- [ ] 没有把 user_settings 4 字段写进 `cockpit_params.py`（D070 明确 user_settings 不进 cockpit_params）
- [ ] 没有任何"localStorage / 前端持久化"路径（D066：必须走 DB）

### Schema 合规性
- [ ] response data 字段为 camelCase（accountSize / maxExposurePct / singleTradeRiskPct / defaultRiskPerTradePct / baseCurrency / updatedAt）
- [ ] PUT 请求体支持 camelCase（`alias_generator=to_camel + populate_by_name=True`）
- [ ] PUT 422 校验范围严格匹配 API-CONTRACT.md（accountSize > 0 / maxExposurePct ∈ [0,100] / singleTradeRiskPct ∈ [0,5]）

### 数据正确性
- [ ] 默认行字段值与 DATA-MODEL.md L510–515 一一对应（account_size=100000 / max_exposure_pct=80 / single_trade_risk_pct=1.0 / default_risk_per_trade_pct=0.75 / base_currency='USD'）
- [ ] `get_or_default()` 在表为空时**不写库**（用直接 SQL `SELECT COUNT(*)` 验证）
- [ ] `upsert` 推进 `updated_at`（onupdate 触发或显式赋值）
- [ ] partial update：未传字段不覆盖原值（S5 验证）

### 测试
- [ ] S1–S13 全部通过
- [ ] S13 全量回归通过（仅 `test_news_api` pre-existing failure，标注于 Evaluator 报告）

### 代码质量
- [ ] 单个函数 ≤ 50 行
- [ ] 无 `print` / 未使用 import / 注释掉的代码块
- [ ] 无硬编码默认值散落在 repo / router（默认值仅在 model 列定义和 `get_or_default()` fallback 一处出现 — fallback dict 必须 `from app.models.user_settings import UserSettings` 或写常量字典；接受单点重复，但不得多点散落）
- [ ] router 不直接操作 `db` / 不直接读写 ORM（全部委托 repo）

---

## 5. 非目标（明确不做，留给 F203-b2 / b3）

- `decision_service.py`、`cockpit_params §4 DECISION`、`GET /cockpit/decision/{ticker}`、`deterministicHash` —— **F203-b2**
- 前端 `UserSettingsForm` / `userSettingsApi.ts` / Settings Drawer / Cockpit Registry 注册 —— **F203-d**
- 多用户 / 鉴权 / 行级权限 —— 不在 v1.x scope（D066 明确）
- 字段历史审计表 —— 不做（updated_at 单值已够）

---

## 6. 开发顺序

1. `models/user_settings.py` 落地 → `python -c "from app.models import UserSettings"` 验证 import 成立
2. `alembic/versions/011_f203b1_user_settings.py` 写迁移（含 INSERT 默认行）→ `alembic upgrade head` + `alembic downgrade -1` + `alembic upgrade head` 三步循环验证（S7）
3. `repositories/user_settings_repository.py`（get / get_or_default / upsert）+ 单元测试 S1–S6
4. `schemas/cockpit/user_settings.py` Pydantic
5. `routers/cockpit/user_settings.py` + `routers/cockpit/__init__.py` 注册（同时清理 decision_router 脏区）
6. 集成测试 S8–S12
7. 全量 `pytest backend/tests/` 回归（S13）
8. Evaluator 自检清单逐条
9. `features.json` 追加 F203-b1 phase=needs_review；`claude-progress.txt` 追加
10. `git commit -m "feat(F203-b1): UserSettings 数据/接入栈（model + alembic + repo + router）"`

---

## 7. 风险与取舍

- **CHECK(id=1) 与 SQLite 行为**：SQLite 支持 CHECK，UPSERT 不会触发约束失败（始终只用 id=1）。生产 Postgres 同样支持。
- **server_default vs Python default**：alembic 用 `server_default` 保证 INSERT DEFAULT 时落值；ORM 默认 `default=lambda` 保证应用层 INSERT 时落值。两层叠加冗余但安全。
- **base_currency 校验**：合约未明列错误码，本 Sprint 接受 `min_length=1, max_length=8`，前端只允许 USD（v1.x 单货币假设），不在后端做白名单（避免后续 EUR/HKD 加币时改后端）。
- **updated_at=None vs 当前时间**：API-CONTRACT.md 示例 GET 响应给出 `"updatedAt": "2026-04-24T10:00:00Z"`；表为空时返回 `null`（合约未禁止）。F203-d 前端做"行不存在"识别即可。如果用户更倾向"返回 now() 占位"，在 Generator 阶段告知调整。
- **脏区清理**：F203-b1 临时移除 b2 router 注册行。等 b2 落地时把这两行加回。

---

👤 请确认（v1 草案）：

1. **F203-b1 范围 = UserSettings 全栈（不含 Decision）** → OK？
2. **主清单 6 文件 + 注册行不计入（方案 B 共识）** → OK？
3. **PUT 请求体 partial update 语义**（`exclude_unset=True`，未传字段不覆盖）→ OK？
4. **`default_risk_per_trade_pct` 校验范围 [0, 5]**（合约未明列，与 single_trade 同档）→ OK？
5. **`updated_at=None` 当行不存在时 GET 返回 null**（不替成 now()）→ OK？
6. **alembic data migration 走 raw SQL `INSERT ... VALUES (1, ...)`** 而非 Python ORM bulk insert（避免 model import 时序问题）→ OK？
7. **脏区清理**：F203-b1 临时移除 `routers/cockpit/__init__.py` 的 `decision_router` 两行，b2 加回 → OK？

全部 OK 后切 Sonnet 新 session 进入 Generator 模式。
