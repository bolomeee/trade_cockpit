# SESSION-HANDOFF.md

> 生成时间：2026-06-11
> 当前 Skill：feature-dev（类型 A 主流程，A-1 收尾）
> 当前 Feature：F220-b — P/(FCF−SBC) 双版本（现金流交叉视角）
> 当前 sub_sprint：**F220-b**　phase=`contract_agreed`

---

## 完成的内容（本 session）

- ✅ 前序门禁检查：F220-b 父级依赖 F102/F104/F218 全 done；sub_sprints.F220-b design_needed→contract_agreed 合法转移
- ✅ 暴露并解决阻塞矛盾：上游正常化 P/E（F220-a1/a2/c）已 deprecated，原自洽红旗锚 `normalizedPe` 恒 null → 红旗永不亮
- ✅ A-1 前置 AskUserQuestion 三项重定义用户拍板（见下「关键决策」）
- ✅ Sprint Contract 起草 + confirmed：`docs/开发/sprint-contracts/F220-b-contract.md`
- ✅ A-1 收尾：features.json / claude-progress.txt / 本 HANDOFF 更新 + commit

## 关键决策（A-1 前置，用户 2026-06-11 拍板）

| 项 | 落定 | 影响 |
|---|------|------|
| 自洽红旗 `sbcSensitiveFlag` | **砍掉** | 不进 schema / 契约 / 代码 |
| P/FCF 市值分子 | **FMP key-metrics-ttm marketCap** | 推翻 D105 自算 Diluted×price（自洽对比需求随 normalizedPe 废弃消失；FMP marketCap 极简 + ADR 货币正确） |
| pFcf 成员门控 | **watchlist(active)∪pool**（D106 落地） | 非成员 → pFcf=null；pool 直读 CockpitPoolCache model，不 import cockpit |

## 中断位置

A-1 完整收尾，Contract confirmed + commit。**按 skill A-1 铁律停在本 session，未进 Generator。**

## Sprint Contract 执行状态

**当前 Contract**：docs/开发/sprint-contracts/F220-b-contract.md（status: confirmed）

| 开发步骤 | 状态 |
|---------|------|
| doc-first（API-CONTRACT/DECISIONS/DATA-MODEL 修订）| ⬜（Generator step 0） |
| _compute_p_fcf 纯函数 + _is_pool_member | ⬜ |
| stock_detail_service get_fundamentals 编排 | ⬜ |
| schema + 前端 types/FundamentalsCard | ⬜ |
| 单元 + 集成测试 | ⬜ |
| E2E（preview）| ⬜ |
| Evaluator 评估 | ⬜ |

## 实现要点（Generator 直接照 Contract §1）

- `_compute_p_fcf(quarters, market_cap)`：FCF=Σ最近4季(OCF+capex，capex 按符号直接加)；pFcfRaw=marketCap/FCF（FCF≤0→None）；pFcfAdj=marketCap/(FCF−ΣSBC)（≤0→None）；<4 季或某季 OCF/capex 缺→(None,None)；SBC 缺→按 0；OCF 用 operatingCashFlow，缺回退 netCashProvidedByOperatingActivities
- 成员门控：`(stock active) or _is_pool_member(ticker)`；非成员→pFcf=None 且不调 get_cash_flow_quarterly
- fail-open：现金流拉取 HTTPError / market_cap None → pFcf=None，endpoint 仍 200，原始指标照常
- 复用 F218 `fmp.get_cash_flow_quarterly(ticker, limit=4)`，**不改 fmp_client**

## 已创建/修改的文件（本 session，均产物文档）

- `docs/开发/sprint-contracts/F220-b-contract.md` — 新建（confirmed）
- `docs/需求/features.json` — sub_sprints.F220-b→contract_agreed + active_sprint + iteration_history
- `claude-progress.txt` — 追加 F220-b A-1 条目

## 本 session 产物 checksum(git sha)

⚠️ 下一 session 进 Generator 前必须比对本表 sha 与当前 `git log -1 --format=%H -- <path>`，不匹配 → 退回 A-1 修复。

| 产物 | 路径 | 最后 commit sha | uncommitted? |
|------|------|----------------|-------------|
| Sprint Contract | `docs/开发/sprint-contracts/F220-b-contract.md` | `__HEAD__` | ⬜ |
| features.json | `docs/需求/features.json` | `__HEAD__` | ⬜ |
| claude-progress.txt | `claude-progress.txt` | `__HEAD__` | ⬜ |
| HEAD | — | `__HEAD__` | — |

**下一 session 验证步骤**（必须先于 Generator 第一行代码）：

```bash
git log -1 --format=%H -- "docs/开发/sprint-contracts/F220-b-contract.md"
git log -1 --format=%H -- "docs/需求/features.json"
git rev-parse HEAD   # 必须 ≥ 表中 HEAD sha
```

任一不匹配 → **不要进 Generator**，先排查仓库状态变化原因。

## 遗留决策（需要用户回答）

无。三项核心决策已在 A-1 前置确认；FMP 现金流字段名（待查-2）由 Generator 对真实响应核对，走 fail-open，不阻断。

## 下一个 Session 继续的指令

```
继续开发 F220-b，Sprint Contract 已确认。
读取 SESSION-HANDOFF.md + docs/开发/sprint-contracts/F220-b-contract.md，
进入 Generator 模式（A-2 pre-flight 后 contract_agreed→in_progress），
从 step 0（doc-first 三文档修订）开始。
```

> 建议用 Sonnet 开启新 session（纯执行，合约已锁）。
