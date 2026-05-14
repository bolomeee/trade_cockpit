---
name: F203-b2 Sprint Contract
description: Cockpit Decision 计算服务 + GET /api/cockpit/decision/{ticker} 接入栈
status: 草案
---

# Sprint Contract：F203-b2 Decision 服务（entry/stop/size + regime/user 联合 cap）

> 日期：2026-04-25 | 状态：草案
> 引用文档：
> - `docs/系统设计/API-CONTRACT.md` §`GET /api/cockpit/decision/{ticker}`（行 1155–1216）
> - `docs/系统设计/DATA-MODEL.md` §SetupSnapshot / §UserSettings / §EarningsEvent / §MarketRegimeSnapshot
> - `docs/系统设计/DECISIONS.md` D068（F210 确定性护栏 / deterministicHash）/ D070（cockpit_params §4）
> - 已有依赖：F202-a SetupSnapshot 表 + repo（已 done）/ F203-b1 user_settings repo（needs_review）/ F201-a market_regime_snapshots（done）/ F204 earnings_events（done）

---

## 本次实现范围

**包含**：
1. **§4 DECISION 参数**：在 `cockpit_params.py` 追加 `CockpitDecisionParams`，集中所有魔法值（hash 算法、价格小数位、effectiveRiskPct 取整规则、null/默认值）。
2. **DecisionService**：依据 ticker 从 setup_snapshots 取最新一行 → 应用 entry/stop/risk_pct 的 override → 与 regime cap、user_settings cap 取 min → floor(account_size × risk_pct/100 / (entry-stop)) 计算 suggestedShares → 拼装 target2r/target3r/positionValue/accountRiskPct/rewardRisk/earningsRisk/earningsDate/deterministicHash。
3. **Decision schema**：Pydantic v2 出参模型（驼峰对齐 API-CONTRACT，Decimal 序列化为 number 2 位小数；hash 16 进制字符串）。
4. **Decision router**：`GET /api/cockpit/decision/{ticker}`，3 个 query override，统一错误码（404 NOT_FOUND / 422 VALIDATION_ERROR）。
5. **重新注册 decision_router** 到 `routers/cockpit/__init__.py`（b1 已清理脏区，本次加回）。
6. **测试**：service 单元（计算正确性 + cap 联合 + earnings_risk 分级 + hash 确定性）、router 集成（200/404/422、override、ticker 大小写归一）。

**明确排除（本次不做）**：
- 前端 DecisionCardWidget UI（属于 F203-d）。
- F210 AI guardrail 校验（本次只产出 hash，不做反向校验）。
- user_settings PUT 表单（属于 F203-d 前端）。
- 任何 schema 变更（DATA-MODEL 不动）。

---

## 预计修改文件（共 6 个，正好达到上限）

| # | 文件路径 | 改动类型 | 说明 |
|---|---------|---------|------|
| 1 | `backend/app/services/cockpit/cockpit_params.py` | 修改 | 追加 `CockpitDecisionParams` (§4) + 模块级 `DECISION = ...` 单例 |
| 2 | `backend/app/services/cockpit/decision_service.py` | 新建 | `compute_decision(db, ticker, entry_override, stop_override, risk_pct_override) → DecisionDTO`；不可变、无副作用 |
| 3 | `backend/app/schemas/cockpit/decision.py` | 新建 | `DecisionResponse`（envelope `{data, message}`）+ `DecisionData`（驼峰字段，Decimal→float quantize 0.01） |
| 4 | `backend/app/routers/cockpit/decision.py` | 新建 | `@router.get("/decision/{ticker}")`，prefix `/api/cockpit`，依赖 `Session = Depends(get_db)` |
| 5 | `backend/app/routers/cockpit/__init__.py` | 修改 | 加 `from app.routers.cockpit.decision import router as decision_router` 并 `include_router` |
| 6 | `backend/tests/test_decision_f203b2.py` | 新建 | service + router 全部测试（pytest，沿用 F203-b1 的 in-memory SQLite + TestClient 模式） |

---

## 关键决策与计算细节（开发期需对照）

### 1. risk_pct 联合 cap（API-CONTRACT 行 1175）
```
caps = [user_settings.single_trade_risk_pct, regime.single_trade_risk_pct]
if risk_pct_override is not None:
    caps.append(risk_pct_override)   # override 只能向下，不能拉高
effective_risk_pct = min(caps)
```
- regime 取 `market_regime_snapshots` 最新一行；无记录时按 `cockpit_params.REGIME.SINGLE_TRADE_RISK_PCT["NEUTRAL"]` 兜底（§4 参数化）。
- user_settings 行不存在 → 走 b1 默认值（不写库）。
- 若 effective_risk_pct ≤ 0 → suggestedShares=0、positionValue=0（不抛错；RISK_OFF 场景）。

### 2. entry/stop 默认来源
- 默认从 `setup_snapshots` 最新一行取 `entry_price` / `stop_price` / `setup_type` / `setup_quality` / `reward_risk`（已由 F202-a 写入）。
- override 仅替换该字段，其他从 setup_snapshots 继承。

### 3. target2r / target3r
- `target2r = entry + 2 × (entry - stop)`
- `target3r = entry + 3 × (entry - stop)`
- `reward_risk` 直接来自 setup_snapshots（不重算；如 override 改了 entry/stop，则用新 entry/stop 重算 = 2.0 或 3.0 取决于哪个 target ≈ 用户的目标 —— 本次保持 setup_snapshots 原值，避免 override 副作用扩散；§4 加 `OVERRIDE_RECOMPUTE_RR: bool = False` 留扩展位）。

### 4. positionValue / accountRiskPct
- `risk_per_share = entry - stop`（Decimal 2 位）
- `suggested_shares = floor(account_size × effective_risk_pct/100 / risk_per_share)`
- `position_value = suggested_shares × entry`
- `account_risk_pct = (suggested_shares × risk_per_share) / account_size × 100`（向下两位小数，因 floor 之后实际 ≤ effective_risk_pct）

### 5. earningsRisk 分级（沿用 F202-a 已有阈值）
- 复用 `cockpit_params.SETUP.EARNINGS_DANGER_DAYS / EARNINGS_CAUTION_DAYS`。
- 查 `earnings_events` 取 ticker 未来最近一次：days_to <= DANGER → DANGER；<= CAUTION → CAUTION；> CAUTION → SAFE；无记录 → null（earningsDate 同步 null）。

### 6. deterministicHash（D068）
```
SHA-256(f"{ticker}|{entry:.2f}|{stop:.2f}|{effective_risk_pct:.4f}|{date_iso}").hexdigest()[:16]
```
- date_iso = setup_snapshots.snapshot_date（不是当前时间，保证可复现）。
- §4 参数化字段顺序与位数。

### 7. 错误处理
| 场景 | HTTP | code |
|------|------|------|
| ticker 在 setup_snapshots 无记录 且 没传 entry/stop override | 404 | NOT_FOUND |
| 计算后 entry ≤ stop（不论来自 setup 还是 override） | 422 | VALIDATION_ERROR |
| ticker 仅有部分 override（只传 entry 没传 stop） | 走 setup_snapshots 的另一条；都没有 → 404 |

---

## 可测试的完成标准

| # | 标准描述 | 测试层级 | 工具 |
|---|---------|---------|------|
| S1 | service：BREAKOUT setup（entry=850, stop=820）+ user(account=100k, risk=1%) + regime=CONSTRUCTIVE(cap=1%) → suggestedShares=33, positionValue≈28050, target2r=910, target3r=940 | 单元 | pytest |
| S2 | service：override risk_pct=0.5 时 effectiveRiskPct=0.5（向下生效）；override risk_pct=5 时仍取 min=1（不能拉高） | 单元 | pytest |
| S3 | service：regime=RISK_OFF 时 effectiveRiskPct=0 → suggestedShares=0, positionValue=0, accountRiskPct=0（不抛错） | 单元 | pytest |
| S4 | service：earnings 在 2 天后 → earningsRisk=DANGER；8 天后 → CAUTION；30 天后 → SAFE；无 earnings → null | 单元 | pytest |
| S5 | service：deterministicHash 同输入复现一致；entry 改 0.01 → hash 不同 | 单元 | pytest |
| S6 | service：override entry/stop 后 entry≤stop → ValueError（router 转 422） | 单元 | pytest |
| S7 | service：user_settings 行不存在 → 走默认值；market_regime_snapshots 空 → NEUTRAL 兜底 | 单元 | pytest |
| S8 | router：GET /api/cockpit/decision/NVDA 返回 200，envelope `{data:{...}, message:"success"}`，所有驼峰字段齐全 | 集成 | pytest+TestClient |
| S9 | router：query override `?entryOverride=900&stopOverride=860&riskPctOverride=0.5` 全链路覆盖 | 集成 | pytest+TestClient |
| S10 | router：未知 ticker → 404 NOT_FOUND | 集成 | pytest+TestClient |
| S11 | router：override entry≤stop → 422 VALIDATION_ERROR | 集成 | pytest+TestClient |
| S12 | router：ticker 大小写归一（小写 `nvda` 也命中 `NVDA`） | 集成 | pytest+TestClient |
| S13 | 全量回归：`pytest backend/tests/` 通过率不低于 b1 完成时（469 passed + 1 pre-existing） | 回归 | pytest |

> E2E 不在本 Sprint 范围（前端 DecisionCardWidget 在 F203-d）。

---

## Evaluator 自检清单

- [ ] S1–S7 单元测试全部通过
- [ ] S8–S12 集成测试全部通过
- [ ] S13 全量回归无新增失败
- [ ] 响应字段名严格对齐 API-CONTRACT.md 行 1180–1202（驼峰、字段全集、类型）
- [ ] 数据库字段读取严格对齐 DATA-MODEL.md（snake_case 入、camelCase 出）
- [ ] 无魔法值（所有阈值、位数、字段顺序在 cockpit_params §4）
- [ ] 所有错误码命中 API-CONTRACT 错误表
- [ ] 无 print/调试残留；类型提示完整
- [ ] DECISIONS.md 追加：D070 §4 参数清单 + override-recompute-RR 决策记录
- [ ] cockpit router `__init__.py` 启动无 ImportError（uvicorn 冷启）
- [ ] 代码质量检查通过（无死代码 / 无重复块 / 函数 ≤ 50 行）

---

👤 用户确认本 Contract 后，**当前 session 仅更新 phase=contract_agreed + SESSION-HANDOFF + claude-progress，然后停止**，由新 session 进入 Generator 模式。
