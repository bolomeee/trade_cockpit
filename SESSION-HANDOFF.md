# SESSION-HANDOFF.md

> 生成时间：2026-06-12
> 当前 Skill：feature-dev（A-2/A-3 完成）→ acceptance（live 通过）
> 当前 Feature：F220-b — P/(FCF−SBC) 双版本　phase=**`done`** ✅
> active_sprint：**null**（无进行中 sprint）

---

## F220-b 全流程已完成（done）

- ✅ A-2 pre-flight → step 0 doc-first（API-CONTRACT/DECISIONS/DATA-MODEL）→ 后端/前端/测试 → A-3 Evaluator 全绿
- ✅ acceptance live 实测：DUOL `pFcfRaw=13.87`、`pFcfAdj=20.98`（**精准落在设计 [20,22]×**）；L1–L5 全过
- ✅ sub_sprints.F220-b → done；父 F220 由 C1 守约保持 `in_progress`（存活子 d/e 仍 design_needed）

## 关键事实（供下一 session）

- **FMP key 在项目根 `.env`**（不是 backend/.env）；backend/app/config.py 用 `parent.parent.parent/.env` 加载根 .env
- **8001 上是 Docker 容器旧镜像（Jun 11，不含 F220-b）** → 部署环境需**重建镜像**才能让 8001 提供 pFcf 字段
- 活跃 DB = `backend/dev.db`（DUOL ∈ watchlist active）；same-day cache 表 `daily_payload_cache`（删当日行即可强制重算）

## commit 链（本 session 全部）

```
2110f18 docs(F220-b): acceptance live 通过 → done（DUOL pFcfAdj=20.98 ∈ [20,22]）
d3a0972 docs(F220-b): 验收记录（部分验收，live 量级待部署环境）
6993f82 docs(F220-b): SESSION-HANDOFF 更新至 needs_review/acceptance 交接
d3a0972…dee39aa feat(F220-b) + 4×wip + 84f9d02(漏 commit 补提)
```

## 未决 / 下一步

- **部署**：重建 8001 Docker 镜像纳入 F220-b（部署步骤，由 project-commiter / 部署流程处理）
- **v2.6 未整体完成**：父 F220 仍 in_progress（F220-d EPS 加速度 / F220-e 预期修正 待后续 feature-dev）。⚠️ F220-d 原依赖正常化 EPS 序列已废，重启时须改用 GAAP EPS 或一并评估
- **无关未跟踪文件**（非本 sprint，未动）：`docs/需求/.features.json.bak`、`docs/系统设计/FILING-EVENTS-CONTRACT.md`、`docs/设计/年报阅读*.md`（属「年报阅读」feature 规划，留对应 owner 处置）
- 预先存在的回归失败（后端 11 / 前端 22）独立于 F220-b，建议另开 session 排查

## 下一 session 可选指令

```
# 继续 F220 剩余子 sprint：
准备开发 F220-d（EPS 加速度）—— 注意原依赖正常化 EPS 已废，先评估改用 GAAP EPS

# 或发版（若决定 v2.6 部分发布）：
触发 project-commiter（会跑 strict consistency-check 闸门 + 重建 Docker）
```
