# 修复指令：F210-c earningsRisk=null 时 trade_plan 100% 422

> 类型：D（Bug 修复）| 触发：feature-dev 类型 D | 日期：2026-04-26
> 来源：v2.0-F210-c 验收阻断（[v2.0-F210-c-acceptance.md](../../验收/v2.0-F210-c-acceptance.md)）

## 现象

进入 `/cockpit`，从 SetupMonitor 选任意 ready 候选（当前数据下 VALE / AAPL / CIM 三只全适用），点 DecisionPanel 底部的 `Generate AI Plan` 按钮 → AI 区显示"AI 暂不可用"。

Network 显示 `POST /api/ai/trade_plan` 返回 **422 VALIDATION_ERROR**，errBody：
```
earningsRisk
  Field required [type=missing, input_value={}, input_type=dict]
```
（实际是因为 Pydantic Literal validate 失败把整个 body 当成空 dict 报错；真值 `earningsRisk: null`。）

## 根因

1. backend `backend/app/ai/schemas/trade_plan.py:48`：
   ```python
   earningsRisk: Literal["SAFE", "CAUTION", "DANGER"]   # 不接受 null
   ```
2. `GET /api/cockpit/decision/{ticker}` 在没有 earnings 数据时返回 `earningsRisk: null`（DATA-MODEL.md 允许 null）。
3. 前端 `frontend/src/cockpit/components/AiTradePlanSection.tsx:48`：
   ```ts
   earningsRisk: decision.earningsRisk,   // 直传，无兜底
   ```

## 修复方案（用户已确认 A — 2026-04-26）

### 方案 A — backend schema 接受 null（采用）

**改 1**：`backend/app/ai/schemas/trade_plan.py`
```python
earningsRisk: Literal["SAFE", "CAUTION", "DANGER"] | None = None
```

**改 2**：system prompt（同文件 SYSTEM_PROMPT 块）追加一句：
```
- earningsRisk null means no earnings data available; treat as SAFE for risk planning
```

**改 3**：前端 `AiTradePlanSection.tsx` `TradePlanInput` 类型同步加 `| null`（已经导入的 `EarningsRisk` 类型若已含 null 则无需改；否则就地 inline）。

### 方案 B — 前端兜底（备选）

`AiTradePlanSection.tsx:48`：
```ts
earningsRisk: decision.earningsRisk ?? 'SAFE',
```
**缺点**：语义错位（无数据 ≠ 安全），AI memo 会误判为低风险。

### 方案 C — decision API 强制返回 SAFE

改 `backend/app/services/cockpit/...` 的 decision service，无 earnings 数据时返回 SAFE 而非 null。
**缺点**：影响面最大，破坏 DATA-MODEL.md 的 null 语义；不推荐。

## 验收增量测试要求（修复后必加）

Evaluator 模式新增至少 1 个集成测试：

- T13：`mockDecision.earningsRisk = null` → 点击 `Generate AI Plan` → 请求成功（mock 返回 200）→ 渲染 memo / management（与 T7 同结构）
- 检查 body.input.earningsRisk 字段为 `null`（不是被 omit / 不是字符串 "null"）

## 修复后路径

1. feature-dev 类型 D 开 Sprint Contract（最多 4 文件改动）
2. Evaluator 新增 T13 + 跑全量回归
3. 通过后 phase 重置回 needs_review
4. 重新走 acceptance（继续 v2.0-F210-c-acceptance.md 未走完的 V4-V10 / B5-B7 / E1-E4）
