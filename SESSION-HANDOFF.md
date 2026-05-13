# SESSION-HANDOFF — F215-b Volume Accumulation 三件套（完成）

> 生成时间：2026-05-13 | 阶段：Evaluator pass → needs_review

---

## 已完成内容

F215-b 全部 10 个开发步骤 + Evaluator 自检 **已完成**。

### 实现文件（7 个核心文件 + 2 个测试文件）

| 文件 | 改动 |
|------|------|
| `backend/alembic/versions/018_f215b_setup_volume_accumulation.py` | 新建，add_column × 3，downgrade drop |
| `backend/app/models/setup_snapshot.py` | 新增 3 个 Mapped 字段 |
| `backend/app/services/cockpit/cockpit_params.py` | 追加 6 个 VOL_ACC_* 常量 |
| `backend/app/services/cockpit/setup_service.py` | 3 个纯函数 + BREAKOUT gate（D088）+ compute_and_store_all 写入 |
| `backend/app/schemas/cockpit/setup.py` | SetupItemResponse 新增 3 字段（to_camel 自动转 camelCase）|
| `frontend/src/cockpit/lib/api/setupMonitorApi.ts` | SetupItem type 新增 3 字段 |
| `frontend/src/cockpit/widgets/SetupMonitorWidget.tsx` | 新增 Vol Z 列（6%），列宽调整 |
| `backend/tests/test_setup_service_f215b.py` | 新建，21 个单元测试 |
| `backend/tests/test_decision_f215b.py` | 新建，7 个集成测试 |

### 副作用修复

- `backend/tests/test_setup_f202a.py::test_s14_classify_breakout` — 补传 `vol_zscore=2.0, ud_ratio=1.5` 以满足新 BREAKOUT gate，原测试逻辑不变

### 文档更新

- `docs/系统设计/DATA-MODEL.md` — SetupSnapshot 3 新列 + BREAKOUT gate 业务规则
- `docs/系统设计/API-CONTRACT.md` — setup-monitor response 3 camelCase 字段 + 降级行为说明
- `docs/系统设计/DECISIONS.md` — 追加 D087（三件套定义）、D088（BREAKOUT gate）、D089（不回填）
- `docs/需求/features.json` — F215-b status: `needs_review`

---

## 当前状态

- Git branch: `improve_against_plan`
- 最新 commit: `feat(F215-b): Volume Accumulation 三件套 + BREAKOUT 吸筹门槛 — Evaluator pass`
- F215-a: done, F215-b: needs_review → **F215 全部 sub_sprint 完成**

### 测试结果

| 测试集 | 结果 |
|--------|------|
| `backend pytest`（全量，排除 test_decision_f203b.py 预存坏文件）| 968 passed, 12 pre-existing failures |
| `F215-b backend tests` (28 tests) | 28/28 pass |
| `frontend vitest §V` (V1/V2/V3) | 3/3 pass |
| `frontend vitest §R` (R1-R10) | 10/10 pass |

---

## 下一步任务

F215 全部完成。建议：

1. **browser 验证**（可选）：起 dev server，在 SetupMonitorWidget 确认 Vol Z 列正常显示
2. **下一 feature**：查看 `features.json` 中下一个 pending feature 或 planning

---

## 注意事项

- `test_decision_f203b.py` 有预存 ImportError（DecisionService 不存在），已有 git untracked 状态，不属于 F215-b 范围
- 现有 BREAKOUT 候选数量在首次 `compute_and_store_all` 后会下降（D088 预期行为）
- alembic 018 需在生产环境手动运行 `alembic upgrade head`

---

## 恢复指令

无待续任务。如需继续开发，请查看 `features.json` 选择下一个 feature。
