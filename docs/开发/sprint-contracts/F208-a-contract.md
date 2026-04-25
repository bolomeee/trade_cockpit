# Sprint Contract：F208-a — AI 基座（依赖 + ai_memos 表 + 配置层）

> 状态：已确认 | 起草：2026-04-25 | 用户确认：2026-04-25
> 父 Feature：F208 LLM Gateway（v2.0 Cockpit P2 AI 层基座）
> 兄弟：F208-b（gateway 核心模块）/ F208-c（gateway 主流程 + endpoint）
> 引用文档：
>   - DATA-MODEL.md §AiMemo（字段权威）
>   - DECISIONS.md D064（LiteLLM + 单一动态 endpoint，依赖 + env 在本 sprint 落地）
>   - DECISIONS.md D069（ai_memos 双用途 + schema_version 失效，索引设计）

---

## 0. 背景与定位

F208 LLM Gateway 总预计 ~18 文件（参见 features.json v2.0 _iteration_log），超 6 文件上限。按职责清晰拆为 3 个子 sprint：

- **F208-a（本 Sprint，6 文件）**：依赖 + ai_memos 表 + 配置层 — 给 b/c 提供运行底座，本 sprint 不写任何业务逻辑
- **F208-b**：gateway 核心模块（errors / memo_repo / budget / routing），4 个支撑模块 + 测试，6 文件
- **F208-c**：gateway 主流程 + LiteLLM 集成 + `/api/ai/{task_type}` endpoint，6 文件

F208-a 完成后：`ai_memos` 表存在于 SQLite + 7 个 AI 相关 env 在 Settings 中可读 + `litellm` 出现在 lockfile。但 gateway / endpoint 尚不存在（属 F208-b/c）。

依赖链：F208-a → F208-b → F208-c → F209/F210/F211。

---

## 1. 实现范围

### 1.1 依赖

新增 `backend/pyproject.toml` `[project].dependencies`：

```
"litellm>=1.83,<2.0",
```

D064 已通过 context7 文档验证 LiteLLM Router / `response_format=Pydantic` / fallbacks / budget 四项核心能力，版本 pin 由 D064 决议。

执行 `uv lock`（在 `backend/` 目录），lockfile 解析必须成功，传递依赖（openai / tokenizers 等）属预期，不阻塞。

### 1.2 配置层（Settings 7 个新字段）

`backend/app/config.py` Settings 类追加（顺序与 D064/D070 / DATA-MODEL §AiMemo 对齐）：

```python
# v2.0 F208 AI Gateway (D064 / D069)
ai_model_default: str = "gpt-5.4-nano"      # default tier (F209 / F211 contradiction/news)
ai_model_critical: str = "gpt-5.4-mini"     # critical tier (F210)
ai_model_complex: str = "gpt-5.4"           # complex tier (F211 journal_assistant)
openai_api_key: str = ""                    # F208-c 调用 LiteLLM 时使用
ai_monthly_budget_usd: float = 20.0         # 月度熔断阈值 (D069)
ai_memo_cache_ttl_hours: int = 24           # memo dedup 命中窗口 (D069)
ai_schema_version: str = "v1"               # schema 失效旗标 (D069)
```

字段命名遵循 pydantic_settings 自动 snake_case 与 env UPPER_SNAKE 互转规则（已验证 `app_env` / `fmp_api_key` 等历史字段）。

### 1.3 ORM 模型

新文件 `backend/app/models/ai_memo.py`：

```python
from sqlalchemy import Column, Integer, String, Text, Numeric, DateTime
from datetime import datetime, timezone

from app.models import Base


class AiMemo(Base):
    __tablename__ = "ai_memos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_type = Column(String(32), nullable=False, index=True)
    input_hash = Column(String(64), nullable=False, index=True)
    input_json = Column(Text, nullable=False)
    output_json = Column(Text, nullable=False)
    schema_version = Column(String(16), nullable=False)
    model_used = Column(String(64), nullable=False)
    tier = Column(String(16), nullable=False)
    tokens_in = Column(Integer, nullable=False)
    tokens_out = Column(Integer, nullable=False)
    cost_usd = Column(Numeric(10, 6), nullable=False)
    latency_ms = Column(Integer, nullable=False)
    created_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
```

字段类型与 DATA-MODEL.md §AiMemo 13 字段表 1:1 对齐。`task_type` / `input_hash` / `created_at` 各自带 `index=True`（基础列索引），复合索引由 Alembic 迁移单独创建（见 1.4）。

### 1.4 Alembic 迁移

新文件 `backend/alembic/versions/012_f208a_ai_memos.py`：

- `revision = "012_f208a_ai_memos"`
- `down_revision = "011_f203b1_user_settings"`
- `upgrade()`：
  - `op.create_table("ai_memos", ...)` 13 列，类型与 1.3 ORM 完全对齐
  - `op.create_index("ix_ai_memos_task_input_created", "ai_memos", ["task_type", "input_hash", sa.text("created_at DESC")])` — dedup 查询主索引
  - `op.create_index("ix_ai_memos_created_at_desc", "ai_memos", [sa.text("created_at DESC")])` — budget SUM 月度扫描
  - 注：列级 `index=True` 由 SQLAlchemy 在 `create_table` 时自动建索引，名称形如 `ix_ai_memos_task_type` / `ix_ai_memos_input_hash` / `ix_ai_memos_created_at`；显式复合索引名避免与列索引冲突
- `downgrade()`：drop 2 个显式复合索引 + drop 表（列级索引随 drop_table 自动清除）

### 1.5 模型注册

`backend/app/models/__init__.py` 在末尾追加：

```python
from app.models.ai_memo import AiMemo  # noqa: E402
```

并在 `__all__` 末尾加 `"AiMemo"`。

### 1.6 测试

新文件 `backend/tests/test_ai_memo_schema_f208a.py`，包含：

1. `test_ai_memo_columns_match_data_model` — 反射 `AiMemo.__table__.columns`，断言 13 列名 + 类型 + nullable 与 DATA-MODEL 对齐
2. `test_alembic_upgrade_creates_ai_memos_table` — 在临时 SQLite 上跑 `alembic upgrade head`，查询 `sqlite_master` 验证 `ai_memos` 表 + 2 个复合索引存在
3. `test_alembic_downgrade_removes_ai_memos` — `downgrade -1` 后表消失，再 `upgrade head` 重新出现
4. `test_ai_memo_write_read_roundtrip` — 写 1 条记录，读回 `cost_usd` 应严格 `Decimal("0.012340")`（精度不丢），按 `(task_type, input_hash)` 查询命中
5. `test_settings_loads_ai_env_overrides` — 通过 `monkeypatch.setenv("AI_MODEL_DEFAULT", "claude-haiku-4-5")` + `Settings()` 验证字段被覆盖

测试参考 `backend/tests/conftest.py` 现有 fixture（`engine` / `session_factory`），不引入新 fixture。

---

## 2. 预计修改文件清单（精确 6 个）

| # | 文件路径 | 改动类型 | 说明 |
|---|---------|---------|------|
| 1 | `backend/pyproject.toml` | 修改 | `[project].dependencies` 增 `litellm>=1.83,<2.0` |
| 2 | `backend/app/config.py` | 修改 | Settings 增 7 个 AI 字段 |
| 3 | `backend/app/models/ai_memo.py` | 新增 | AiMemo ORM 模型 |
| 4 | `backend/app/models/__init__.py` | 修改 | 注册 AiMemo（追加 import + `__all__`） |
| 5 | `backend/alembic/versions/012_f208a_ai_memos.py` | 新增 | 建表迁移 + 2 个复合索引 |
| 6 | `backend/tests/test_ai_memo_schema_f208a.py` | 新增 | 5 个测试用例 |

不超 6 文件上限。`backend/uv.lock` 由 `uv lock` 命令自动重写，不计入"修改文件"清单（它是衍生产物，diff 会很大但属预期）。

---

## 3. 可测试的完成标准

| # | 标准描述 | 测试层级 | 工具 |
|---|---------|---------|------|
| 1 | `litellm` 出现在 `backend/uv.lock`，版本满足 `>=1.83,<2.0` | 集成 | `grep -E '^name = "litellm"' backend/uv.lock` + 邻近 version 行匹配 |
| 2 | `Settings()` 实例化成功，7 个 AI 字段全部可读，默认值符合 1.2 | 单元 | pytest |
| 3 | `monkeypatch.setenv("AI_MODEL_DEFAULT", "foo")` 后 `Settings().ai_model_default == "foo"` | 单元 | pytest |
| 4 | `AiMemo.__table__.columns` 13 列名/类型/nullable 全部对齐 DATA-MODEL §AiMemo | 单元 | pytest |
| 5 | `alembic upgrade head` 在临时 DB 成功，`ai_memos` 表存在 | 集成 | pytest（直接调用 alembic Python API） |
| 6 | 复合索引 `ix_ai_memos_task_input_created` + `ix_ai_memos_created_at_desc` 在 `sqlite_master` 中存在 | 集成 | pytest |
| 7 | `alembic downgrade -1` 回到 011 后表消失；再 `upgrade head` 重新出现，幂等 | 集成 | pytest |
| 8 | 写入 cost_usd=Decimal("0.012340") 读回精度不丢 | 集成 | pytest |
| 9 | 全量回归 `uv run pytest -m 'not live'` 通过率不低于 main 分支水平（不引入新红色） | 回归 | pytest |

---

## 4. Generator 开发顺序

```
1. backend/pyproject.toml 加 litellm 依赖 → uv lock
   wip commit: "wip(F208-a): pin litellm dependency"

2. backend/app/config.py 加 7 个 AI 字段
   wip commit: "wip(F208-a): settings add 7 ai fields"

3. backend/app/models/ai_memo.py 新建 + __init__.py 注册
   wip commit: "wip(F208-a): AiMemo orm model"

4. backend/alembic/versions/012_f208a_ai_memos.py 新建
   alembic upgrade/downgrade 双向手动验证一次
   wip commit: "wip(F208-a): alembic 012 ai_memos migration"

5. backend/tests/test_ai_memo_schema_f208a.py 新建
   pytest 全跑通
   wip commit: "wip(F208-a): ai_memos schema tests"

6. 全量回归 uv run pytest -m 'not live'
   （无新失败则进入 Evaluator）
```

每步严格按文件名 `git add <path>`，**禁用 `git add -A`**。

---

## 5. Evaluator 自检清单

- [ ] §3 表格 9 条全部 ✅
- [ ] 字段命名 100% 对照 DATA-MODEL.md（含大小写）
- [ ] 无硬编码值（默认值集中在 config.py / 索引名集中在迁移）
- [ ] Alembic `down_revision = "011_f203b1_user_settings"` 链路正确
- [ ] 无新增 pytest warning（DeprecationWarning 等）
- [ ] DECISIONS.md 不需要新决策（D064/D069 已定方案，本 sprint 仅执行）
- [ ] `git status` 干净，所有改动按文件名显式 commit
- [ ] 全量回归通过率不低于 main

---

## 6. 风险点

- **R1（lockfile diff 大）**：`uv lock` 拉入 LiteLLM 传递依赖（openai / tokenizers / 等），lock 改动很大。属预期，记录到 progress 即可
- **R2（字段顺序）**：DATA-MODEL §AiMemo 表格顺序与 ORM 字段声明顺序一致即可，索引位置以语义为准（task_type / input_hash / created_at 三个高频查询字段建索引）
- **R3（Numeric 精度）**：SQLite 实际不严格区分 Numeric/Float，但 SQLAlchemy 层会在读出时还原 Decimal；测试 8 必须断言 `Decimal` 类型而非 float

---

👤 用户确认：2026-04-25。开发进入 F208-a Generator 模式（建议新 session）。
