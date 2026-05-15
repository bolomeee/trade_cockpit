# SESSION-HANDOFF — F216 全部完成，下一步：v2.0 release

> 生成时间：2026-05-15
> 当前分支：improve_against_plan
> F216 Cockpit Phase B — Weekly Stage Layer：✅ **done**（8/8 sub_sprints 完成）
> 下一阶段：v2.0 release（project-commiter skill 打 tag）

---

## 1. F216 完成摘要

所有 8 个 sub_sprint 已全部 done：

| Sub_sprint | 内容 | 状态 |
|-----------|------|------|
| F216-a | WeeklyStageService 数据层（weekly_stage_snapshots 表 + OLS slope 计算） | ✅ done |
| F216-b | weekly_stage_snapshots API + 前端 WeeklyStageWidget | ✅ done |
| F216-c1 | SetupItem.weeklyStage 字段 + weeklyStageTokens 提取 | ✅ done |
| F216-c2 | SetupMonitorWidget WS 列展示 | ✅ done |
| F216-d1 | weekly_stage 数据模型迁移（020_f216d1 alembic） | ✅ done |
| F216-d2 | weekly_stage 作为 ready_signal 第 8 条 AND 门（D093） | ✅ done |
| F216-d3 | SetupMonitorWidget WS 列（stage 数值展示） | ✅ done |
| F216-e | 22:20 UTC APScheduler cron（D094） | ✅ done |

父 feature F216：`status=done / phase=done / completed_at=2026-05-15`

---

## 2. 当前工作区状态（散落未提交项）

```
M backend/layouts/cockpit.json       (F216-c2 期间改动，未提交)
?? backend/alembic/versions/011_f203b_user_settings.py  (旧未提交 migration)
?? backend/tests/test_decision_f203b.py                  (旧未提交测试，import 有误)
?? docs/开发/sprint-contracts/F216-d2-contract.md        (F216-d2 漏 commit)
?? docs/开发/sprint-contracts/F216-d3-contract.md        (F216-d3 漏 commit)
?? docs/验收/v2.0-F216-d2-acceptance.md                  (F216-d2 漏 commit)
?? docs/验收/v2.0-F216-d3-acceptance.md                  (F216-d3 漏 commit)
?? SESSION-HANDOFF.md                                    (本次覆写)
```

**建议处理**（在 release 前）：
- `docs/开发/sprint-contracts/F216-d*.md` + `docs/验收/*.md`：`git add` + `chore` commit
- `backend/layouts/cockpit.json`：确认是否需要提交（视 F216-c2 验收结果）
- `backend/alembic/versions/011_f203b_user_settings.py` + `test_decision_f203b.py`：用户决策（提交还是丢弃 F203-b 开发残留）

---

## 3. 下一步：v2.0 release

触发 `project-commiter` skill，步骤：
1. 清理散落未提交项（见 §2）
2. 运行 consistency-check (mode=strict) 闸门
3. 更新版本号（v1.x.x → v2.0.0）
4. 写 changelog（F216 + F213 + F215 等本 release 所有 feature）
5. `git commit + git tag v2.0.0`

---

## 4. Phase C/D 规划（下一个 release 范围）

- F217：Phase C — Capitulation Reversal 重写
- F218：Phase D — Repricing Trigger
- 另起 sprint 规划，不在本 release 范围

---

## 5. 恢复指令

新 session 继续 v2.0 release：

> F216 已全部完成（done），下一步执行 v2.0 release。
> 读取 SESSION-HANDOFF.md，触发 project-commiter skill。
> 先清理散落未提交项，再打 tag。
