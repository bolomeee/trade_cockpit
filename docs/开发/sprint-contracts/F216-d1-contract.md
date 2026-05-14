# Sprint Contract：F216-d1 — setup_snapshots 加 weekly_stage 列 (B4 地基)

> 日期：2026-05-14 | 状态：✅ 已确认（用户 2026-05-14 全部按推荐 NP1-NP7 拍板）
> Feature：F216 Cockpit Phase B — Weekly Stage Layer
> Sub-sprint：F216-d1（d 段第 1 个，DB schema 层；d2=service gate，d3=前端 WS 列）
> 父 feature 拆分理由：F216-d 原估 ~13 文件远超 6 文件单 sprint 上限，按父 feature `sub_sprint_notes` 预告 d1/d2/d3 三段切
> 依赖：
>   - F216-b done（weekly_stage_snapshots 表 + classify service + repo 已落地）
>   - F215-b done（alembic 018 setup_snapshots volume accumulation 三列 — F216-d1 的 alembic 020 紧跟 019 之后，链上完整）
> 引用文档：
>   - ARCHITECTURE.md（cockpit/ 模块层 + setup_snapshots 归"Cockpit Epic 新增"）
>   - DATA-MODEL.md §SetupSnapshot（字段表权威，本 sprint 将追加 weekly_stage 行）
>   - DATA-MODEL.md §WeeklyStageSnapshot（stage 字段类型与语义来源）
>   - 完整改善计划：/Users/wonderer/.claude/plans/featrue-dev-replicated-goblet.md §Phase B / B4
>   - features.json F216 acceptance_criteria 第 8 条："setup_snapshots 新增 weekly_stage (INT) 列；... alembic 020 可前向也可回滚"

---

## 0. 背景与定位

Phase B 第 4 步的"地基" — 给 `setup_snapshots` 加一列 `weekly_stage`，为：
- **F216-d2**：`setup_service._compute_ready_signal` 加 `weekly_stage == 2` 强制门禁（acceptance 第 8 条）+ `_row_to_dict` 输出 `weeklyStage`
- **F216-d3**：前端 SetupItem 类型 + "WS" 列渲染（acceptance 第 9 条）

提供存储槽位。本 sprint **只动 schema 三处（migration / model / DATA-MODEL.md 字段表）**，不动 service 逻辑、不动 ready_signal、不动前端、不动业务规则段、不动 DECISIONS（D093 留给 d2 真正实施门禁时写）。

**为什么这样切**：纯 schema 改动风险最低，独立 commit 让 alembic 020 可随时回滚而不连带回滚业务逻辑；d2 在已存在 schema 上做业务逻辑，单 review 集中观察 ready_signal 收紧 30-50% 的设计意图。

---

## 1. 实现范围

**包含**：

### 1.1 alembic 020 migration
**新文件** `backend/alembic/versions/020_f216d1_setup_weekly_stage_column.py`：

```python
"""F216-d1: setup_snapshots weekly_stage column (Stan Weinstein gate prep)

Revision ID: 020_f216d1_setup_weekly_stage_column
Revises: 019_f216b_weekly_stage_snapshots
Create Date: 2026-05-14
"""
from alembic import op
import sqlalchemy as sa

revision = "020_f216d1_setup_weekly_stage_column"
down_revision = "019_f216b_weekly_stage_snapshots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "setup_snapshots",
        sa.Column("weekly_stage", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("setup_snapshots", "weekly_stage")
```

### 1.2 ORM Model 更新
**修改** `backend/app/models/setup_snapshot.py`：在 `up_down_volume_ratio` 之后、`scanned_at` 之前追加：

```python
weekly_stage: Mapped[int | None] = mapped_column(Integer, nullable=True)
```

字段顺序保持 alembic 时间序（018 三列 → 020 一列追加在尾）。

### 1.3 DATA-MODEL.md §SetupSnapshot 字段表追加一行
位置：紧贴 `up_down_volume_ratio` 行之后、`scanned_at` 行之前：

```markdown
| weekly_stage | Integer | ❌ | Stan Weinstein Stage 1-4（0=UNKNOWN；NULL=该日 cron 未跑到 weekly_stage 阶段）。来源：weekly_stage_snapshots.stage 当日同 ticker upsert。ready_signal 强制要求 weekly_stage==2（F216-d2 实施） |
```

**业务规则段不动**（"业务规则" bullet list 中关于 ready_signal 的描述等 F216-d2 修改时一并加；本 sprint 只动字段表）。

**明确排除（留给后续 sub-sprint）**：

| 项 | 归属 |
|---|---|
| `setup_service.compute_and_store_all` 取 weekly_stage_snapshots 注入 weekly_stage | F216-d2 |
| `_compute_ready_signal` 加 stage==2 强制门禁 | F216-d2 |
| `_row_to_dict` 输出 `weeklyStage` | F216-d2 |
| `app/schemas/cockpit/setup.py` `SetupItemResponse` 加字段 | F216-d2 |
| `cockpit_params.py` 加 `READY_REQUIRE_STAGE2` 或类似 flag | F216-d2 |
| API-CONTRACT.md §setup-monitor 响应加 `weeklyStage` | F216-d2 |
| DECISIONS.md 加 D093（weekly_stage 作为 ready_signal 强制门禁的决策与权衡） | F216-d2 |
| 前端 `setupMonitorApi.ts` `SetupItem` 加 `weeklyStage` 字段 | F216-d3 |
| 前端 `SetupMonitorWidget.tsx` 加 "WS" 列 | F216-d3 |
| 前端 widget vitest | F216-d3 |
| 现存 setup_snapshots 历史行回填 weekly_stage | **永不做**（NULL 直至下次 cron 自然填充，与 F215-b 同 pattern） |

---

## 2. 预计修改文件（3 个，远低于 6 上限）

| # | 文件路径 | 改动类型 | 说明 |
|---|---------|---------|------|
| 1 | `backend/alembic/versions/020_f216d1_setup_weekly_stage_column.py` | 新增 | add_column / drop_column，紧跟 019 之后 |
| 2 | `backend/app/models/setup_snapshot.py` | 修改 | 追加 `weekly_stage: Mapped[int \| None] = mapped_column(Integer, nullable=True)` |
| 3 | `docs/系统设计/DATA-MODEL.md` | 修改 | §SetupSnapshot 字段表追加 weekly_stage 行；业务规则段不动 |

**不新建测试文件**（NP5）。理由：
- 模型字段 = 1 行 mapped_column，无独立逻辑可单测
- alembic 升降级由 evaluator 手工三段跑（upgrade → downgrade → upgrade）验证可重入，不引入 alembic 测试基础设施
- 全量回归 + 临时 ORM 验证脚本（不落仓库）足够覆盖

---

## 3. 协商点结论（NP1-NP7，全部按推荐拍板）

| NP | 选择 | 理由 |
|----|------|------|
| **NP1 列类型** | `Integer NULL` | 区分 NULL（cron 未跑）/ 0（已算 UNKNOWN）/ 1-4（真实 stage）三种语义；与 weekly_stage_snapshots.stage 同 Integer 类型 |
| **NP2 字段命名** | `weekly_stage` | 与 acceptance criteria 原文一致；与 weekly_stage_snapshots.stage 语义对应 |
| **NP3 索引** | 不加 | 该列从不作为独立查询条件，已有 (ticker, scan_date) 唯一索引覆盖；加索引浪费写性能 |
| **NP4 现存行回填策略** | 不回填，NULL | 与 F215-b 同 pattern；保持 migration 幂等性；下次 cron 自然填充 |
| **NP5 测试粒度** | 不新建测试文件 | 模型字段无逻辑可测；alembic 升降级 evaluator 手工三段跑；全量回归足够 |
| **NP6 列在 model 的位置** | 追加在末尾（up_down_volume_ratio 之后） | 保持 alembic 时间序；不破坏 _row_to_dict 字段顺序（d2 才动） |
| **NP7 DATA-MODEL.md 业务规则段是否提前写门禁** | 不写 | d1 只动字段表；业务规则与代码同步在 d2 修改 |

---

## 4. 可测试的完成标准

| # | 标准描述 | 测试层级 | 工具 / 验证方法 |
|---|---------|---------|----------------|
| 1 | `alembic upgrade head` 在干净 sqlite DB 上成功，`setup_snapshots` 表含 `weekly_stage INTEGER NULL` 列 | 集成 | `alembic upgrade head` + `PRAGMA table_info("setup_snapshots")` 包含 weekly_stage 列且 notnull=0 |
| 2 | `alembic downgrade -1` 后 `weekly_stage` 列消失 | 集成 | `alembic downgrade -1` + PRAGMA table_info 不含 weekly_stage |
| 3 | `alembic upgrade head` 再次成功（可重入） | 集成 | 第 2 步之后再 upgrade head，列回来 |
| 4 | ORM `SetupSnapshot(weekly_stage=2, ...)` 实例化 + commit + 回读 `.weekly_stage == 2` 成功 | 单元 | 临时 python 脚本（sqlite 内存 DB，不落仓库测试文件） |
| 5 | ORM `SetupSnapshot(weekly_stage=None, ...)` 也成功 commit | 单元 | 同上 |
| 6 | DATA-MODEL.md §SetupSnapshot 字段表含 weekly_stage 行；格式与上下行一致；业务规则段未提前写门禁 | 文档审查 | 人工 diff |
| 7 | 全量 `pytest backend/tests/` 无新增失败 | 回归 | 比对 F216-b 完成时的 baseline（994+ 通过） |
| 8 | `test_setup_f202a.py` API 响应字段集合未变化（d1 不暴露 weeklyStage 到 API） | 回归 | pytest 跑该文件，API 断言通过 |
| 9 | alembic 020 文件 frontmatter 字段（revision / down_revision）正确 | 静态 | 人工读文件首 15 行 |

---

## 5. Evaluator 自检清单

- [ ] alembic upgrade / downgrade / upgrade 三段验证通过（标准 1-3）
- [ ] ORM 实例化 weekly_stage=2 与 None 均通过（标准 4-5）
- [ ] DATA-MODEL.md 字段表新行格式与上下行一致；业务规则段未改（标准 6）
- [ ] 全量 pytest 通过，无新增失败（标准 7）
- [ ] `test_setup_f202a.py` 单独跑通过（标准 8）
- [ ] alembic 020 down_revision = "019_f216b_weekly_stage_snapshots"（标准 9）
- [ ] 模型字段命名 = `weekly_stage`（snake_case，对齐 weekly_stage_snapshots.stage 的语义）
- [ ] 业务规则段未提前写门禁逻辑（留给 d2）
- [ ] 无新增 pip / npm 依赖
- [ ] commit 仅含本 sprint 3 个文件（按 §2 清单显式 git add，禁用 -A）
- [ ] 代码质量：无死代码、无硬编码魔法值、无未使用 import
- [ ] consistency-check C1/C4/C5/C7 全清后再标 needs_review

---

## 6. WIP commit 节点

| # | 触发条件 | 命令 |
|---|---------|------|
| WIP 1 | alembic 020 + model 改动通过升降级 + ORM 验证 | `git add backend/alembic/versions/020_f216d1_setup_weekly_stage_column.py backend/app/models/setup_snapshot.py` → `git commit -m "wip(F216-d1): alembic 020 + setup_snapshot weekly_stage column"` |
| Final | DATA-MODEL.md 加行 + Evaluator 全清 | `git add docs/系统设计/DATA-MODEL.md` → `git commit -m "feat(F216-d1): setup_snapshots add weekly_stage column for stage gate"` |

⚠️ 禁用 `git add -A`。

---

## 7. 开发顺序（Generator 模式逐步执行）

1. 新建 `backend/alembic/versions/020_f216d1_setup_weekly_stage_column.py`（参考 018 同 pattern；revision/down_revision 严格按 §1.1）
2. 修改 `backend/app/models/setup_snapshot.py` 加 `weekly_stage` Mapped 字段
3. 跑 `alembic upgrade head` → `PRAGMA table_info("setup_snapshots")` 验证新列存在（notnull=0）
4. 跑 `alembic downgrade -1` → PRAGMA 验证列消失
5. 跑 `alembic upgrade head` 再次 → PRAGMA 验证列回来（可重入）
6. 临时 python 脚本验证 ORM `SetupSnapshot(weekly_stage=2)` / `None` 实例化 + 提交 + 回读
7. **WIP commit 1**（migration + model）
8. 跑全量 `pytest backend/tests/` 验证无新增失败
9. 修改 `docs/系统设计/DATA-MODEL.md` §SetupSnapshot 字段表追加 weekly_stage 行
10. Evaluator 自检 → **Final commit** → 调用 consistency-check (mode=interactive) C1/C4/C5/C7 → 标 phase=needs_review → 等待 acceptance

---

## 8. 风险与回滚

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| alembic 020 与 019 冲突 | 极低 | DB 升级失败 | 严格 down_revision="019_f216b_weekly_stage_snapshots" |
| 现存 dev sqlite DB 升级后破坏 setup_service | 低 | 单测失败 | 标准 7 全量回归 + 标准 8 setup_f202a 单独跑兜底 |
| 文档与代码不同步 | 低 | DATA-MODEL drift | NP7 限制 d1 只动字段表，业务规则段留给 d2，明确边界 |
| 历史行被误回填 | 极低 | 数据语义混淆 | NP4 明确不回填；migration 只 add_column |

**回滚方案**：`alembic downgrade -1`（标准 2 已验证可行），无业务逻辑变更需要回滚。

---

## 9. 后续衔接

F216-d1 done 后：
- F216-d2 立即可起：在 schema 已存在的前提下，集中实现 ready_signal 门禁逻辑 + service join + API 暴露
- F216-d3 等 d2 done 后再起（前端依赖 API 响应字段）

---

👤 用户已确认本 Contract（2026-05-14 全部按推荐 NP1-NP7）。下个 session（建议 Sonnet）从 §7 开发顺序步骤 1 开始。
