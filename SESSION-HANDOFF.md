# SESSION-HANDOFF.md

> 生成时间：2026-07-02
> 当前 Skill：feature-dev（类型 A 主流程 → A-1 Sprint Contract 协商，F222-c 已确认）
> 当前 Feature：F222 — Watchlist 颜色标记 → Sub-sprint F222-a（backend 读路径，✅ done）→ F222-b（backend 写路径，✅ done）→ F222-c（frontend，✅ Contract 已确认，未开发）
> 分支：`new_dev`（未合并 main）

---

## 完成的内容

1. **F222-c 前序门禁检查**：F222 依赖 F001（phase=done）✓ 满足；本项目 features.json 无 `_sprint_plan` 字段，跳过该子步骤并已告知用户。
2. **A-1 Sprint Contract 协商**：读取 CLAUDE.md / DATA-MODEL.md / API-CONTRACT.md（Watchlist + Signals 两节）/ design-spec.md（§F222）/ component-plan.md（§F222）+ 现有代码（WatchlistWidget.tsx / lib/api/watchlist.ts / types/signal.ts / types/watchlist.ts / components/ui/popover.tsx）。发现 `tokens.css` 缺失 `--color-label-*` token（design-spec.md 已登记、D110 已预期，但实现层遗漏），已同步补入 features.json 的 `estimated_files_changed`。
3. **关键假设澄清**（AskUserQuestion，用户已选择）：
   - 颜色更新失败（非 NOT_FOUND）→ sonner toast 提示；NOT_FOUND → 静默 invalidate（镜像 delete 逻辑）
   - CSV 导出未标记行 → 字面值 `none`；颜色列位置 → 追加在 `name` 之后
4. **Sprint Contract 落盘 + 用户 ack + 确认**：[F222-c-contract.md](docs/开发/sprint-contracts/F222-c-contract.md)（status: confirmed），6 个文件，含完整代码级实现细节（含事件冒泡隔离方案：Radix `Popover.Close` + 触发按钮/PopoverContent 双重 `stopPropagation`）。
5. **收尾**：features.json（`sub_sprints['F222-c']` → `contract_agreed`，`_pipeline_status.active_sprint` → `F222-c`，`active_sprint_phase` → `contract_agreed`，`iteration_history` 追加 `contract_agreed` 记录）+ claude-progress.txt 追加记录 + `chore(F222-c)` commit（本文件生成后执行）。

## 中断位置

F222-c **Sprint Contract 协商完成，已确认**，尚未进入 Generator。按规则本 session 到此为止，不得直接开始写代码。下一步是开新 session，触发 Generator 模式，从开发步骤 1（`tokens.css` 加 3 个 token）开始，按 Contract §1.1 → §1.6 顺序执行。

## Sprint Contract 执行状态

**F222-a Contract**：[docs/开发/sprint-contracts/F222-a-contract.md](docs/开发/sprint-contracts/F222-a-contract.md) — 全部完成

**F222-b Contract**：[docs/开发/sprint-contracts/F222-b-contract.md](docs/开发/sprint-contracts/F222-b-contract.md) — 全部完成

**F222-c Contract**：[docs/开发/sprint-contracts/F222-c-contract.md](docs/开发/sprint-contracts/F222-c-contract.md) — 已确认，未开发

| 开发步骤 | 状态 |
|---------|------|
| DATA-MODEL 确认 | ✅（复用 F222-a 已确认的 `label_color` / `labelColor` 定义，本 sprint 无需再改文档） |
| API-CONTRACT 确认 | ✅（`PUT /api/watchlist/{ticker}/color` 已由 F222-b 实现；`GET /api/signals` 已带 `labelColor`） |
| tokens.css 新增 token | ⬜ |
| types/signal.ts（LabelColor + 字段） | ⬜ |
| lib/api/watchlist.ts（updateColor） | ⬜ |
| ColorTagButton.tsx（新建） | ⬜ |
| WatchlistWidget.tsx 接入 + CSV | ⬜ |
| WatchlistWidget.test.tsx（TC1–TC9） | ⬜ |
| Evaluator 评估 | ⬜ |

## 已创建/修改的文件

**F222-c Contract §2 清单（6 个，全部未开始）**：
- `frontend/src/styles/tokens.css` — ⬜ 未开始
- `frontend/src/types/signal.ts` — ⬜ 未开始
- `frontend/src/lib/api/watchlist.ts` — ⬜ 未开始
- `frontend/src/components/features/dashboard/ColorTagButton.tsx` — ⬜ 未开始（新建）
- `frontend/src/workbench/widgets/WatchlistWidget.tsx` — ⬜ 未开始
- `frontend/src/workbench/widgets/__tests__/WatchlistWidget.test.tsx` — ⬜ 未开始（新建）

**本 session 状态文件**：
- `docs/需求/features.json` — 完成（`sub_sprints['F222-c']` → `contract_agreed`；`estimated_files_changed` 补 `tokens.css`）
- `claude-progress.txt` — 完成
- `docs/开发/sprint-contracts/F222-c-contract.md` — 完成（status: confirmed）
- `SESSION-HANDOFF.md` — 本文件

**遗留未处理（与本 sprint 无关，来自更早阶段，本 session 未处理）**：`.claude/launch.json`、`docs/需求/PRD.md` 仍是未提交状态。

## 本 session 产物 checksum(git sha)

⚠️ 下一 session 进 F222-c Generator 前，**必须**先核对本表 sha 与当前 `git log -1 --format=%H -- <path>` 一致（这是 F002-a 漏洞的第二道防线，Generator pre-flight 强制检查项）。

| 产物 | 路径 | 最后 commit sha | uncommitted? |
|------|------|----------------|-------------|
| F222-c Sprint Contract | `docs/开发/sprint-contracts/F222-c-contract.md` | `<PENDING_COMMIT>` | ⬜ |
| features.json | `docs/需求/features.json` | `<PENDING_COMMIT>` | ⬜ |
| claude-progress.txt | `claude-progress.txt` | `<PENDING_COMMIT>` | ⬜ |
| HEAD | — | `<PENDING_COMMIT>` | — |

**下一 session 验证步骤**（必须先于 Generator 第一行代码）：

```bash
git log -1 --format=%H -- "docs/开发/sprint-contracts/F222-c-contract.md"
# 必须 == 表中"最后 commit sha"
git log -1 --format=%H -- "docs/需求/features.json"
# 必须 == 表中"最后 commit sha"
git rev-parse HEAD
# 必须 ≥ 表中 HEAD sha（可以推进，但不能在本次 commit 之前）
```

任一不匹配 → **不要进 Generator**，先排查仓库状态变化原因（rebase / reset / 漏 commit）。

## 遗留决策（需要用户回答）

无阻塞性遗留问题。F222-c 的 2 个产品行为决策（错误提示方式、CSV 空值表示）已在本 session 协商中由用户拍板；另 2 处纯实现细节技术决策（Popover 关闭机制、事件冒泡隔离范围）无产品行为分歧，未征询，已直接写入 Contract §1.4/§5。

## 下一个 Session 继续的指令

```
继续开发 F222-c，Sprint Contract 已确认。
读取 SESSION-HANDOFF.md + docs/开发/sprint-contracts/F222-c-contract.md，
进入 Generator 模式，从开发步骤 1（tokens.css 加 3 个 --color-label-* token）开始。
```
