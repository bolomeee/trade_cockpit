# SESSION-HANDOFF — 2026-04-25（F203-b1 contract_agreed）

> 覆盖上一版（F203-a needs_review）。
> F203-a 仍 needs_review；F203-b 拆为 b1 + b2；F203-b1 Sprint Contract 已用户确认，待 Generator 落地。

---

## 当前状态

| Feature | 状态 |
|---------|------|
| F200-a / F200-b | ✅ done |
| F201-a / F201-b | ✅ done |
| F204-a / F204-b | ✅ done |
| F202-a / F202-b / F202-c | ✅ done |
| F203-a | 🔍 needs_review |
| **F203-b1** | **📋 contract_agreed** |
| F203-b2 | ⬜ ready_to_dev（依赖 b1）|
| F203-c | ⬜ ready_to_dev（依赖 a）|
| F203-d | ⬜ ready_to_dev（依赖 b2）|

---

## F203-b 拆分（方案 B：__init__.py 注册行不计入 6 文件主清单）

| 子 Sprint | 范围 | 主清单 |
|---|---|---|
| **F203-b1（本次起草）** | UserSettings 全栈 | 6 文件 |
| F203-b2 | Decision 全栈（decision_service + cockpit_params §4 + schema + router + tests）| 6 文件 |

---

## F203-b1 Sprint Contract 摘要

> 完整内容：[`docs/开发/sprint-contracts/F203-b1-contract.md`](docs/开发/sprint-contracts/F203-b1-contract.md)

### 范围
UserSettings 数据 + 接入：`GET/PUT /api/cockpit/user-settings`，单行 id=1（CHECK 约束），首启自动插默认行。

### 主清单（6 文件）

| # | 文件 | 类型 |
|---|------|------|
| 1 | `backend/app/models/user_settings.py` | 新建 |
| 2 | `backend/alembic/versions/011_f203b1_user_settings.py` | 新建（含 `INSERT ... VALUES (1, ...)` data migration）|
| 3 | `backend/app/repositories/user_settings_repository.py` | 新建（get / get_or_default / upsert）|
| 4 | `backend/app/schemas/cockpit/user_settings.py` | 新建（UserSettingsData / UserSettingsResponse / UserSettingsUpdate）|
| 5 | `backend/app/routers/cockpit/user_settings.py` | 新建（GET + PUT）|
| 6 | `backend/tests/test_user_settings_f203b1.py` | 新建（S1–S13）|

### 注册行（不计入主清单）

- `backend/app/routers/cockpit/__init__.py`：+ user_settings_router；**同时清理脏区**：删除 `decision_router` 残留 import 和 `include_router(decision_router)` 两行（留给 F203-b2 加回）
- `backend/app/models/__init__.py`：已预置 UserSettings import，**不再改动**（落 model 文件后自动生效）

### 已确认的关键约定（Generator 必须遵守）

1. PUT 请求体 partial update：`model_dump(exclude_unset=True)`，未传字段不覆盖原值
2. `default_risk_per_trade_pct` 校验 `[0, 5]`（与 single_trade 同档）
3. `accountSize > 0` / `maxExposurePct ∈ [0, 100]` / `singleTradeRiskPct ∈ [0, 5]` → Pydantic 自动 422
4. 表为空时 GET 返回 `updatedAt=null`（不替成 `now()`）
5. Alembic data migration 走 raw SQL `op.execute("INSERT ... VALUES (1, ...)")`，避开 model import 时序问题
6. `get_or_default()` 表为空时**不写库**（用 `SELECT COUNT(*)` 验证）
7. response data 全 camelCase（accountSize / maxExposurePct / singleTradeRiskPct / defaultRiskPerTradePct / baseCurrency / updatedAt）
8. D070：user_settings 4 字段**不进** cockpit_params.py
9. D066：所有持久化必须走 DB，不走 localStorage

### 完成标准（13 条）

S1–S6 单元（repo）/ S7 alembic upgrade+downgrade+upgrade / S8–S12 集成（TestClient）/ S13 全量回归（仅 test_news_api 1 条 pre-existing）

详见 contract §3。

---

## ⚠️ 已知预置脏区（开工第 1 步必须处理）

工作树未提交修改：

- `backend/app/models/__init__.py`：`from app.models.user_settings import UserSettings` 已加；**落 model 文件即修复**
- `backend/app/routers/cockpit/__init__.py`：`from app.routers.cockpit.decision import router as decision_router` + `include_router(decision_router)` 已加但 `decision.py` 不存在；**F203-b1 必须删除这两行**（b2 加回）

→ 当前 backend 无法启动；F203-b1 第 1 + 5 步落地后恢复。

---

## 开发顺序（Generator 严格按序）

1. `models/user_settings.py` 落地 → 验证 `from app.models import UserSettings` 通过
2. `alembic/versions/011_f203b1_user_settings.py` 写迁移 → upgrade/downgrade/upgrade 三步循环验证（S7）
3. `repositories/user_settings_repository.py` + 单元测试 S1–S6
4. `schemas/cockpit/user_settings.py`
5. `routers/cockpit/user_settings.py` + `routers/cockpit/__init__.py` 注册（同时清理 decision_router 脏区）
6. 集成测试 S8–S12
7. 全量 `pytest backend/tests/` 回归（S13）
8. Evaluator 自检清单逐条
9. `features.json` F203-b1 phase=`needs_review`；`claude-progress.txt` 追加
10. `git commit -m "feat(F203-b1): UserSettings 数据/接入栈（model + alembic + repo + router）"`

---

## 下一 Session 恢复指令

建议用 **Sonnet** 开新 session，粘贴：

```
继续开发 F203-b1，Sprint Contract 已确认。
读取 SESSION-HANDOFF.md + docs/开发/sprint-contracts/F203-b1-contract.md，
进入 Generator 模式，从开发步骤 1 开始。
```
