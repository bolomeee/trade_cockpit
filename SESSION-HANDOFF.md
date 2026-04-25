# SESSION HANDOFF

> 生成时间：2026-04-25
> 当前阶段：F210-a ✅ done（620/620 tests pass）
> 当前 branch：cockpit
> 上一阶段：F209-c ✅ done（acceptance 通过，含一次 trendScore 阈值 P0 修复）

---

## 本 session 完成的事

**F210-a：后端 schemas + trade_plan guardrail（D068）**

按契约 §4 Generator 模式严格执行完毕：

| 步骤 | 内容 | 状态 |
|------|------|------|
| 8a | 新建 `backend/app/ai/schemas/candidate_ranker.py` | ✅ |
| 8b | 新建 `backend/app/ai/schemas/trade_plan.py`（含 guardrail）| ✅ |
| 8c | 修改 `backend/app/ai/schemas/__init__.py`（REGISTRY +2 行 + register +1 行）| ✅ |
| 8d | 跑 `test_ai_schemas_f210a.py -v` → **31/31 pass**（I1-I9/O1-O6/TI1-TI4/G1-G7/R1-R5）| ✅ |
| 9 | 扩展 `test_ai_gateway_e2e_f208c.py` 添加 C9/C10 → **2/2 pass** | ✅ |
| 10 | 全量 `uv run pytest backend/tests/` → **620/620 pass** | ✅ |
| 10 | `uv run mypy backend/app/ai/schemas/` → **0 errors**（4 pre-existing errors 在 memo_repo/gateway，同 F209-a 基线）| ✅ |
| 11 | Evaluator 自检全通过 | ✅ |

**4 项决策执行确认**：
- Q1：candidates > 20 → `max_length=20` 严格 422（silent truncate deferred to F210-b）
- Q2：guardrail 不复算 SHA-256（仅比 entry/stop/size 三字段）
- Q3：candidate_ranker 不做 BANNED_PHRASES 扫描
- Q4：candidate_ranker 输出硬性 3 项

**关键实现细节**：
- `HASH_PRICE_DECIMALS` 从 `cockpit_params.DECISION` import，单一来源不漂移
- `guardrail._HOOKS["trade_plan"]` 已注册；`candidate_ranker` 未注册（R3/R4 验证）
- C9：trade_plan size 被 LLM 篡改 → `AiGuardrailViolation`，`AiMemo` 数量不增
- C10：candidate_ranker 合法输出 → memo 入表，无 guardrail 调用

---

## Git 历史

```
ec4b4a3 wip(F210-a): e2e guardrail test (C9/C10) + unit tests (I/O/TI/G/R)
14f0210 wip(F210-a): registry wiring
37f2e06 wip(F210-a): trade_plan schema + guardrail
1755e31 wip(F210-a): candidate_ranker schema
f725fa5 chore(F209-c): acceptance passed — phase=done
```

---

## features.json 当前状态

| Feature | Phase |
|---------|-------|
| F209-a / b / c | ✅ done |
| **F210-a** | ✅ **done**（2026-04-25，33 tests）|
| F210-b | design_ready |
| F210-c | design_ready |
| F211 | design_ready |
| F205 / F206 / F207 | design_ready |

---

## 下一步：F210-b — SetupMonitor "AI 排序" 集成（建议新 session + Sonnet）

**触发**：在新 session 说"开始 F210-b"。

**F210-b 核心任务**（参契约 §8 骨架预览）：
1. 新建 `frontend/src/cockpit/components/AiCandidateRankerSection.tsx`
   - 顶部按钮 + 加载/成功/错误三态 + top 3 列表 + 缓存命中徽章
2. 修改 `SetupMonitorWidget.tsx`
   - 表格上方追加按钮区，点击调 `callAiTask<CandidateRankerInput, CandidateRankerOutput>('candidate_ranker', ...)`
   - 输入从当前 items[] 取 `slice(0, 20)` 并按 §1.1.1 字段映射
3. 扩展 `SetupMonitorWidget.test.tsx` §R 段（~10 用例：按钮渲染 / slice 截断 / top 3 展示 / 错误态 / cache）

**后端输入映射（F210-a schema → widget items）**：
- `regime` / `regimeScore` → Cockpit regime store
- `candidates[].ticker` → SetupSnapshot.ticker
- `candidates[].setupType` → SetupSnapshot.setup_type（大写枚举 BREAKOUT/PULLBACK/...）
- `candidates[].trendScore` → SetupSnapshot.trend_score（0-5）
- `candidates[].rsPercentile` → SetupSnapshot.rs_percentile
- `candidates[].distanceToEntryPct` → SetupSnapshot.distance_to_entry_pct
- `candidates[].rewardRisk` → SetupSnapshot.reward_risk
- `candidates[].earningsRisk` → SetupSnapshot.earnings_risk（SAFE/CAUTION/DANGER）
- `candidates[].readySignal` → SetupSnapshot.ready_signal（bool）

**前端 API 函数**：`callAiTask` 已在 F209 封装，F210-b 直接复用（需确认入参泛型格式）

**注意**：candidates.length < 3 时，前端主动不发请求（契约 Q4 决策）

---

## 引用文档

| 文档 | 用途 |
|------|------|
| docs/开发/sprint-contracts/F210-a-contract.md | F210-a 契约（含 §8 F210-b 骨架）|
| docs/系统设计/API-CONTRACT.md line 1655-1734 | POST /api/ai/{task_type} 统一 envelope |
| docs/设计/design-spec.md line 945-973 | Widget 5 SetupMonitor AI 排序区域视觉规格 |
| backend/app/ai/schemas/candidate_ranker.py | F210-b 输入/输出字段权威 |

## 启动开发环境命令

```bash
# 后端（端口 8001）
cd "/Users/wonderer/Desktop/Claude workspace/stock_portal/backend"
uv run uvicorn app.main:app --reload --port 8001

# 前端（端口 5173）
cd "/Users/wonderer/Desktop/Claude workspace/stock_portal/frontend"
pnpm dev

# 回归测试
cd "/Users/wonderer/Desktop/Claude workspace/stock_portal/backend"
uv run pytest tests/ -v
```
