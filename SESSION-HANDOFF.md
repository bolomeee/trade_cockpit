# SESSION-HANDOFF.md

> 生成时间：2026-06-12
> 状态：**stock_portal v2.6 功能开发收口** ✅
> 最后 Feature：F220（done）；active_sprint：null

---

## 里程碑：全项目功能开发完成

- **60 done + 1 deprecated（F103），无 in_progress / 未完成 feature。**
- `_pipeline_status.development = done`，`active_sprint = null`。
- F220-b（P/(FCF−SBC) 双版本）已 docker 上线（8001/8080），DUOL live pFcfAdj=20.98 ∈ [20,22]。
- 回归基线干净：后端 **1288 passed / 0 failed**、前端 **353 passed / 0 failed**（33 个预存陈旧测试本 session 已全部修复）。

## 本 session 完成的三块工作

1. **F220-b 全周期**：Generator + Evaluator + acceptance(live) + docker 部署上线。
2. **清理 33 个预存陈旧测试**（后端 11 + 前端 22）：均为代码有意演进、测试未跟上，零真实回归。回归基线现已干净。
3. **收尾 F220**：deprecate F220-d/e（d 地基正常化 EPS 已废需重设计；e 属未建的完整新 feature）→ F220 升 done；清理陈旧 acceptance_criteria(11→5)/notes；下游 API-CONTRACT/DATA-MODEL 同步标 d/e + 027 表 deprecated。

## 关键事实（供下一 session）

- **FMP key 在项目根 `.env`**（config.py 用 `parent.parent.parent/.env` 加载）；8001 是 docker 容器（重建镜像才纳入新后端代码）；活跃 DB=`backend/dev.db`，生产 DB=`backend/data/prod.db`（volume 挂载）。
- 部署 = `docker compose build && docker compose up -d`（context 含源码，烤入当前分支）；回滚镜像备份 `:rollback-pre-f220b`。
- alembic head 停在 `025`；026（normalized_pe_history）/027（analyst_estimate_snapshots）均 deprecated 不建表。

## 当前分支与未决

- 所有工作在 `indicator_enhance` 分支，**未并入 main**；本次部署**未打 tag**。
- **无关未跟踪文件**（非 stock_portal，属独立 edgar-reader 年报阅读项目，错放在 docs/，未动）：`docs/需求/.features.json.bak`、`docs/系统设计/FILING-EVENTS-CONTRACT.md`、`docs/设计/年报阅读*.md`。

## 下一步可选

```
# 正式发版（推荐——功能已收口）：
触发 project-commiter：打 tag v2.6.0 + 写 CHANGELOG + 并入 main
（会跑 strict consistency-check 闸门；发版前可重建 docker 镜像确保 8001 是最新代码）

# 或：清理错放的 edgar-reader 文档 / 转向该独立项目
```
