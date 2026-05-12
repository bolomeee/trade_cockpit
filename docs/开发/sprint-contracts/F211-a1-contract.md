# Sprint Contract：F211-a1 — AI Contradiction Detector + News Summarizer + Journal Assistant 后端 schemas

> 状态：草案，待用户确认 | 起草：2026-04-28
> 父 Feature：F211 AI Contradiction Detector + News Summarizer + Journal Assistant（v2.0 Cockpit P2 三 task 混合 tier）
> 拆分：**F211-a1（本 sprint，3 个 task 的 Pydantic schema）** / F211-a2（per-task model override 基建）/ F211-b（DecisionPanel Contradictions 区前端）/ F211-c（News 页 AI 摘要 bar 前端，含 tokens/cost 展示）/ F211-d（平仓 hook + journal_entries.ai_review 迁移 + 月度 cron）
> 依赖：
>   - F208-c ✅（AiGateway 主流程 + REGISTRY 显式占位 + guardrail.run + routing _TASK_TIER 已映射 contradiction/news/journal 三个 task）
>   - F209-a ✅（schema 文件模板：SCHEMA_VERSION / SYSTEM_PROMPT / BANNED_PHRASES / guardrail 函数模式）
>   - F210-a ✅（Pydantic 风格 + 测试组织模板）
> 引用文档：
>   - API-CONTRACT.md §POST /api/ai/{task_type}（line 1655-1734：统一 envelope / 错误码 / 7 task 枚举）
>   - DATA-MODEL.md §AiMemo（line 599-647：task_type 枚举表，contradiction/news/journal 已列入；schema_version 字段语义）
>   - DATA-MODEL.md §SetupSnapshot（line 420-466：contradiction_detector input 字段权威）
>   - DATA-MODEL.md §JournalEntry（v1 字段：action/price/date/reason；ai_review 列由 F211-d 迁移）
>   - DECISIONS.md D064（tier 路由）/ D070 line 1527（AI 模型走 .env 不进 cockpit_params.py）/ D074（schema 字段命名 camelCase）
>   - design-spec.md §Widget 6 line 1009-1013（AI Contradictions 区域承载）+ §Widget 9 line 1109-1119（AI Daily Brief 综合）
>   - data-mapping.md §Cockpit-6.d（line 662-669：contradictions[] / recommendation 字段映射）
>   - features.json#F211（acceptance_criteria 6 条；sub_sprints 5 entry）
>   - backend/app/ai/schemas/__init__.py（line 35-38：F211 REGISTRY 注册占位）
>   - backend/app/ai/routing.py line 12-14（_TASK_TIER 已映射 contradiction:default / news:default / journal:complex）
>   - backend/app/ai/schemas/setup_explainer.py（F209-a guardrail BANNED_PHRASES 函数模板）
>   - backend/app/schemas/news.py（NewsArticle FMP 字段：title/publishedAt/contentHtml/symbols/url/site）

---

## 0. 背景与定位

F208-c 已落地 AI Gateway 主流程：`schemas/__init__.py` 的 `REGISTRY` 是显式占位（line 35-38 注释 `"contradiction_detector": SchemaPair(...)`），`guardrail.run` 通过 registry 模式接入 `gateway.py` step 9，`routing.py` 的 `_TASK_TIER` 已经把 `contradiction_detector` / `news_summarizer` 映射到 `default` tier、`journal_assistant` 映射到 `complex` tier — **后端基础设施齐全，本 sprint 只补 3 个 schema + 各自 BANNED_PHRASES guardrail，不动 gateway / routing / endpoint 层**。

F211 整体覆盖 3 个 task + 3 个独立前端落点 + 1 张表迁移 + 1 个月度 cron：
- `contradiction_detector`（default）：DecisionPanel 底部 "Contradictions" 区
- `news_summarizer`（default）：News 页顶部 AI 摘要 bar
- `journal_assistant`（complex）：双模式 — 平仓时单笔复盘 + 月度策略审计

按 D010 + F208/F209/F210 既定先例，F211 拆 5 段（已经过 consistency-check C5/C6 校验）：

| 子 sprint | 范围 | 估计文件 |
|----------|------|---------|
| **F211-a1（本契约）** | 3 个 task 的 Pydantic schema + BANNED_PHRASES guardrail + REGISTRY 注册 + 单元测试 | 5 |
| F211-a2 | per-task model override 基建（env-driven，base_url/api_key/cost rate；config.py + routing.py + gateway.py + 测试 + DECISIONS.md 新决策） | 5 |
| F211-b | 前端 DecisionPanel Contradictions 区组件 + widget 集成 + 测试 | 3-4 |
| F211-c | 前端 News 页 AI 摘要 bar 组件 + News.tsx 集成 + 测试（含 tokens/cost 展示） | 3-4 |
| F211-d | 平仓 hook + journal_entries.ai_review Alembic 迁移 + JournalEntry 模型改 + 月度 cron + 测试 | 5-6 |

依赖链：`a1 → {a2 并行 / b / c / d}`。

本 sprint 不写任何前端代码、不改 gateway / endpoint / routing / DB schema，让 F211-b/c/d 直接基于稳定的 schema 契约启动。

**关键约束**：
1. 3 个 task **均无 deterministic 数字锚点**（不像 F210 trade_plan）→ 仅做 BANNED_PHRASES 文本扫描型 guardrail，沿用 F209-a setup_explainer / market_narrator 的 `combined-text-grep` 模板。
2. 字段命名走 **D074 camelCase**（与 F209/F210 一致），输入/输出字段在 Pydantic 内用 camelCase 直名，**不**走 alias。
3. `journal_assistant` 双模式（per-trade / monthly）通过 `mode: Literal["trade", "monthly"]` 字段 + `model_validator` 强制 payload-mode 一致性。**两种模式共用同一 task_type，REGISTRY 内单条 entry**（与"复用 ai_memos"决策一致）。
4. `news_summarizer` 输入接收纯文本字段（`contentText`），HTML 剥离责任在前端（F211-c）—— LLM 上下文不进 HTML 标签，避免 token 浪费 + prompt 注入风险。
5. SCHEMA_VERSION 全部初始 `"v1"`（与 F209/F210 一致）；未来 schema 演进时 bump 即可让旧 ai_memos 缓存自动失效（D069 cache invalidate 机制）。

---

## 1. 实现范围

### 1.1 包含

#### 1.1.1 `backend/app/ai/schemas/contradiction_detector.py`（新建，~110 行）

**职责**：定义 `contradiction_detector` task 的 input/output schema + SYSTEM_PROMPT + BANNED_PHRASES + guardrail（仅 banned phrase 扫描）。

**Input 字段（13 项，camelCase）**：
| 字段 | 类型 | 约束 | 来源 |
|------|------|------|------|
| `ticker` | str | min_length=1 max_length=10 pattern=`^[A-Z][A-Z0-9.\-]*$` | URL 路径或前端选择 |
| `setupType` | Literal[7 枚举] | BREAKOUT/PULLBACK/RECLAIM/EARNINGS_DRIFT/EXTENDED/BROKEN/NONE | SetupSnapshot.setup_type |
| `setupQuality` | Literal["A","B","C"] \| None | 可选 | SetupSnapshot.quality |
| `trendScore` | int | ge=0 le=5 | SetupSnapshot.trend_score |
| `rsPercentile` | float | ge=0 le=100 | SetupSnapshot.rs_percentile |
| `entry` | float | gt=0 | DecisionData.entryPrice |
| `stop` | float | gt=0 | DecisionData.stopPrice |
| `target2r` | float | gt=0 | DecisionData.target2r |
| `rewardRisk` | float | ge=0 | SetupSnapshot.reward_risk |
| `accountRiskPct` | float | ge=0 le=100 | DecisionData.accountRiskPct |
| `earningsRisk` | Literal["SAFE","CAUTION","DANGER"] \| None | None 兜底（参 F210-c earningsRisk-null 教训） | DecisionData.earningsRisk |
| `daysToEarnings` | int \| None | ge=0（可选） | EarningsEvent.days_until |
| `regime` | Literal[5 枚举] | RISK_ON/CONSTRUCTIVE/NEUTRAL/DEFENSIVE/RISK_OFF | MarketRegimeSnapshot.regime |
| `regimeScore` | int | ge=0 le=100 | MarketRegimeSnapshot.market_score |
| `readySignal` | bool | — | SetupSnapshot.ready_signal |

**Output 字段**：
```python
class Contradiction(BaseModel):
    type: Literal["earnings_risk", "reward_risk", "trend_quality",
                  "extension", "regime_misfit", "volume", "other"]
    severity: Literal["LOW", "MEDIUM", "HIGH"]
    text: str = Field(min_length=1, max_length=200)  # 一行说明
    model_config = {"extra": "forbid"}

class ContradictionDetectorOutput(BaseModel):
    contradictions: list[Contradiction] = Field(min_length=0, max_length=5)
    recommendation: str = Field(min_length=1, max_length=200)  # 总结一句
    model_config = {"extra": "forbid"}
```

**SYSTEM_PROMPT 要点**：
- 角色：风险审计型分析师；任务：找输入数据中的内在矛盾（技术面强 vs 财报近、R:R 低 vs 距 entry 远 等）
- 规则：每条 contradiction 一行 ≤200 字符；最多 5 条；severity 分 LOW/MEDIUM/HIGH；recommendation 一行总结建议（"延后开仓 / 减仓 50% / 等待 N 天 / OK 进场"等）
- 允许 contradictions 为空数组（无矛盾时输出 `[]`，recommendation 写 "No major contradictions"）
- BANNED_PHRASES 同 F209-a：buy now / sell now / 保证收益 / 承诺收益 / 忽略止损 / ignore stop

**guardrail**：扫 `recommendation + contradictions[].text` 拼接文本，命中 banned phrase 抛 `AiGuardrailViolation`。

#### 1.1.2 `backend/app/ai/schemas/news_summarizer.py`（新建，~95 行）

**职责**：对一批 news 综合摘要，输出 catalyst / sentiment / 相关 tickers / 风险列表。

**Input 字段**：
```python
class NewsArticleItem(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    contentText: str = Field(min_length=0, max_length=2000)  # 前端从 contentHtml 剥离 + slice
    tickers: list[str] = Field(min_length=0, max_length=20)  # 单条 article 提及的 ticker（NewsArticle.symbols）
    publishedAt: str = Field(min_length=10, max_length=40)  # ISO 8601 字符串，schema 不做日期解析
    model_config = {"extra": "forbid"}

class NewsSummarizerInput(BaseModel):
    articles: list[NewsArticleItem] = Field(min_length=1, max_length=30)  # 30 条上限（token 防爆）
    windowDays: int = Field(ge=1, le=30, default=5)  # 时间窗描述（非过滤参数）
    model_config = {"extra": "forbid"}
```

**Output 字段**：
```python
class NewsSummarizerOutput(BaseModel):
    catalystSummary: str = Field(min_length=1, max_length=500)  # 多句段落
    sentiment: Literal["positive", "neutral", "negative"]
    relevantTickers: list[str] = Field(min_length=0, max_length=10)  # AI 判定最相关 tickers
    risks: list[str] = Field(min_length=0, max_length=5)  # 风险/警示列表
    model_config = {"extra": "forbid"}
```

**SYSTEM_PROMPT 要点**：
- 角色：金融新闻分析师；任务：把零散 news 归纳为 catalyst（事件性总结）+ 总体 sentiment + 最相关 tickers + 风险点
- 规则：catalystSummary ≤500 字符；sentiment 三值之一；relevantTickers 最多 10（按 AI 判定的事件相关性，不是简单计数最多）；risks 最多 5 条
- 允许 risks / relevantTickers 为空数组
- BANNED_PHRASES 同上

**guardrail**：扫 `catalystSummary + risks[]` 拼接文本，命中抛 `AiGuardrailViolation`。

#### 1.1.3 `backend/app/ai/schemas/journal_assistant.py`（新建，~170 行，含双模式 + validator）

**职责**：双模式复盘 — 单笔出场后自动归因 + 月度策略审计。**单一 task_type，单一 REGISTRY entry**，通过 `mode` 字段分流。

**Input 结构**（discriminated by `mode`）：

```python
# ─── 子 payload：trade 模式 ───
class TradeReviewPayload(BaseModel):
    ticker: str = Field(min_length=1, max_length=10, pattern=r"^[A-Z][A-Z0-9.\-]*$")
    setupType: Literal[…7 枚举…] | None = None
    setupQuality: Literal["A","B","C"] | None = None
    plannedEntry: float = Field(gt=0)
    plannedStop: float = Field(gt=0)
    plannedTarget2r: float | None = Field(default=None, gt=0)
    actualEntry: float = Field(gt=0)
    actualExit: float = Field(gt=0)
    shares: int = Field(ge=1)
    entryDate: str = Field(min_length=10, max_length=10)  # YYYY-MM-DD
    exitDate: str = Field(min_length=10, max_length=10)
    holdingDays: int = Field(ge=0)
    rMultiple: float  # 实际 R 倍数（可负）
    preTradeNotes: str | None = Field(default=None, max_length=1000)
    model_config = {"extra": "forbid"}

# ─── 子 payload：monthly 模式 ───
class ClosedTradeBrief(BaseModel):
    ticker: str
    setupType: Literal[…7 枚举…] | None = None
    rMultiple: float
    holdingDays: int = Field(ge=0)
    closedOn: str = Field(min_length=10, max_length=10)
    model_config = {"extra": "forbid"}

class MonthlyReviewPayload(BaseModel):
    month: str = Field(pattern=r"^\d{4}-\d{2}$")  # "2026-04"
    closedTrades: list[ClosedTradeBrief] = Field(min_length=1, max_length=100)
    model_config = {"extra": "forbid"}

# ─── Root input ───
class JournalAssistantInput(BaseModel):
    mode: Literal["trade", "monthly"]
    trade: TradeReviewPayload | None = None
    monthly: MonthlyReviewPayload | None = None
    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def _check_mode_payload(self):
        if self.mode == "trade":
            if self.trade is None:
                raise ValueError("mode='trade' requires trade payload")
            if self.monthly is not None:
                raise ValueError("mode='trade' forbids monthly payload")
        else:  # monthly
            if self.monthly is None:
                raise ValueError("mode='monthly' requires monthly payload")
            if self.trade is not None:
                raise ValueError("mode='monthly' forbids trade payload")
        return self
```

**Output 结构**（同样 mode-discriminated）：

```python
class TradeReviewOutput(BaseModel):
    planVsActualScore: int = Field(ge=1, le=10)
    entryQuality: Literal["good", "fair", "poor"]
    stopDiscipline: Literal["good", "fair", "poor"]
    mistakes: list[str] = Field(min_length=0, max_length=5)
    lesson: str = Field(min_length=1, max_length=500)
    model_config = {"extra": "forbid"}

class SetupPerformance(BaseModel):
    setupType: str
    tradeCount: int = Field(ge=1)
    winRate: float = Field(ge=0, le=1)
    avgRMultiple: float
    model_config = {"extra": "forbid"}

class MonthlyReviewOutput(BaseModel):
    month: str = Field(pattern=r"^\d{4}-\d{2}$")
    overallExpectancy: str = Field(min_length=1, max_length=200)  # 一段总结
    ruleAdherence: int = Field(ge=1, le=10)
    setupPerformance: list[SetupPerformance] = Field(min_length=0, max_length=10)
    keyLessons: list[str] = Field(min_length=0, max_length=5)
    model_config = {"extra": "forbid"}

class JournalAssistantOutput(BaseModel):
    mode: Literal["trade", "monthly"]
    trade: TradeReviewOutput | None = None
    monthly: MonthlyReviewOutput | None = None
    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def _check_output_mode(self):
        if self.mode == "trade" and (self.trade is None or self.monthly is not None):
            raise ValueError("mode='trade' output requires trade payload only")
        if self.mode == "monthly" and (self.monthly is None or self.trade is not None):
            raise ValueError("mode='monthly' output requires monthly payload only")
        return self
```

**SYSTEM_PROMPT 要点**：
- 角色：交易复盘教练；trade 模式做 plan vs actual 归因；monthly 模式做策略级审计
- 规则：mode 字段必须 echo 输入值；不得跨模式输出；lesson / keyLessons 用第二人称（"You over-traded …"）
- BANNED_PHRASES 同上 + 额外加一条："you're a great trader" 等空泛奉承（暂不实施，预留扩展）—— **本 sprint 仅 6 个标准 banned phrase**

**guardrail**：扫 trade.lesson + trade.mistakes[] + monthly.overallExpectancy + monthly.keyLessons[] 拼接文本，命中抛 `AiGuardrailViolation`。

#### 1.1.4 `backend/app/ai/schemas/__init__.py`（修改，~+8 行）

替换 line 35-38 的 3 行注释占位 + 在 guardrail 注册段补 3 行：

```python
# 在 import 段补：
from app.ai.schemas import contradiction_detector as _cd
from app.ai.schemas import journal_assistant as _ja
from app.ai.schemas import news_summarizer as _ns

# REGISTRY 字典内补 3 行（替换 line 35-38 的占位注释）：
"contradiction_detector": SchemaPair(_cd.ContradictionDetectorInput, _cd.ContradictionDetectorOutput),
"news_summarizer":        SchemaPair(_ns.NewsSummarizerInput, _ns.NewsSummarizerOutput),
"journal_assistant":      SchemaPair(_ja.JournalAssistantInput, _ja.JournalAssistantOutput),

# Guardrail 注册段（紧跟 line 44 trade_plan 之后）：
_gr.register("contradiction_detector", _cd.guardrail)
_gr.register("news_summarizer", _ns.guardrail)
_gr.register("journal_assistant", _ja.guardrail)
```

#### 1.1.5 `backend/tests/test_ai_schemas_f211a1.py`（新建，~360 行 / ~38 用例）

参照 `tests/test_ai_schemas_f210a.py` 结构（class-per-task + 输入正/负 + 输出正/负 + guardrail + REGISTRY）：

| 类 | # | 用例 | 类型 |
|----|---|------|------|
| `TestContradictionInput` | CI1 | 完整字段 + 5 contradictions 边界 → 通过 | 单元 |
| | CI2 | earningsRisk=None / daysToEarnings=None → 通过（参 F210-c 教训） | 单元 |
| | CI3 | trendScore=6 → ValidationError | 单元 |
| | CI4 | rsPercentile=101 → ValidationError | 单元 |
| | CI5 | regime 非枚举 → ValidationError | 单元 |
| | CI6 | extra 字段 → ValidationError（extra=forbid） | 单元 |
| `TestContradictionOutput` | CO1 | 0 contradictions（空数组）+ recommendation → 通过 | 单元 |
| | CO2 | 5 contradictions（max 边界）→ 通过 | 单元 |
| | CO3 | 6 contradictions → ValidationError | 单元 |
| | CO4 | severity 非枚举 → ValidationError | 单元 |
| | CO5 | recommendation 缺失 → ValidationError | 单元 |
| | CO6 | text > 200 chars → ValidationError | 单元 |
| `TestContradictionGuardrail` | CG1 | 干净文本 → pass | 单元 |
| | CG2 | recommendation 含 "buy now" → AiGuardrailViolation | 单元 |
| | CG3 | contradictions[0].text 含 "ignore stop" → AiGuardrailViolation | 单元 |
| `TestNewsInput` | NI1 | 1 article（min 边界）→ 通过 | 单元 |
| | NI2 | 30 articles（max 边界）→ 通过 | 单元 |
| | NI3 | 31 articles → ValidationError | 单元 |
| | NI4 | 0 articles → ValidationError | 单元 |
| | NI5 | windowDays=0 / 31 → ValidationError；缺省 default=5 → 通过 | 单元 |
| | NI6 | contentText 超 2000 → ValidationError | 单元 |
| `TestNewsOutput` | NO1 | 完整字段 → 通过 | 单元 |
| | NO2 | sentiment 非枚举 → ValidationError | 单元 |
| | NO3 | relevantTickers > 10 → ValidationError | 单元 |
| | NO4 | risks 空数组 → 通过 | 单元 |
| `TestNewsGuardrail` | NG1 | 干净 → pass | 单元 |
| | NG2 | catalystSummary 含 "保证收益" → AiGuardrailViolation | 单元 |
| `TestJournalInput` | JI1 | mode=trade + trade payload → 通过 | 单元 |
| | JI2 | mode=monthly + monthly payload → 通过 | 单元 |
| | JI3 | mode=trade 但缺 trade payload → ValidationError（model_validator） | 单元 |
| | JI4 | mode=trade 但同时含 monthly → ValidationError | 单元 |
| | JI5 | mode=monthly 但 closedTrades 0 项 → ValidationError | 单元 |
| | JI6 | month 格式 "2026-4"（缺 0 padding）→ ValidationError | 单元 |
| `TestJournalOutput` | JO1 | mode=trade + trade output → 通过 | 单元 |
| | JO2 | mode=trade 但同时含 monthly → ValidationError | 单元 |
| | JO3 | planVsActualScore=11 → ValidationError | 单元 |
| `TestJournalGuardrail` | JG1 | trade.lesson 含 "buy now" → AiGuardrailViolation | 单元 |
| | JG2 | monthly.keyLessons 含 "忽略止损" → AiGuardrailViolation | 单元 |
| `TestRegistry` | R1 | `get_schemas("contradiction_detector")` 返回 SchemaPair | 单元 |
| | R2 | `get_schemas("news_summarizer")` 返回 SchemaPair | 单元 |
| | R3 | `get_schemas("journal_assistant")` 返回 SchemaPair | 单元 |
| | R4 | `guardrail._HOOKS` 包含三 task hook | 单元 |
| | R5 | `routing.resolve_tier("contradiction_detector")` → "default" | 单元 |
| | R6 | `routing.resolve_tier("news_summarizer")` → "default" | 单元 |
| | R7 | `routing.resolve_tier("journal_assistant")` → "complex" | 单元 |

> 测试文件复用 F210-a 测试的 fixture / helper 风格（直接构造 dict + Pydantic 校验）。

---

### 1.2 排除（明确不做）

- ❌ **不动 gateway.py / routing.py / endpoint ai.py**（routing 已正确映射 default/complex tier；endpoint 已动态 dispatch，新加 task 自动可用）
- ❌ **不动 cockpit_params.py**（D070 line 1527 明文：AI 模型参数走 .env，不进 cockpit_params；BANNED_PHRASES 是 schema 层文案，按 F209/F210 先例直留 schema 文件内）
- ❌ **不写前端**（F211-b/c/d 处理）
- ❌ **不动 ai_memos schema / Alembic**（无新字段；schema_version 字段已存在，本 sprint 沿用 "v1"）
- ❌ **不加 deterministic 数字 guardrail**（3 个 task 均无锚点；只做 BANNED_PHRASES 文本扫描）
- ❌ **不实现 per-task model override 基建**（F211-a2 单独处理）
- ❌ **不动 journal_entries 表 / JournalEntry 模型 / position_service**（F211-d 处理）
- ❌ **不加 e2e LiteLLM 真实调用测试**（F208-c 已覆盖 echo task；本 sprint 是纯 schema 单测，集成测试覆盖 gateway 在收到这 3 个 task_type 时能正确路由 + 写 ai_memos，复用 test_ai_gateway_e2e_f208c monkeypatch 套路）
- ❌ **不加文本超长 silent truncate**（articles>30 / contentText>2000 走 422 严格校验；前端 F211-c 入参前 slice）
- ❌ **不在 schema 内做日期解析**（entryDate / exitDate / publishedAt 仅 string 校验长度，业务层 F211-d 自行 parse）

---

## 2. 预计修改文件清单（共 5 个，符合 6 文件上限）

| 路径 | 操作 | 预计行数 |
|------|------|---------|
| `backend/app/ai/schemas/contradiction_detector.py` | 新建 | +110 |
| `backend/app/ai/schemas/news_summarizer.py` | 新建 | +95 |
| `backend/app/ai/schemas/journal_assistant.py` | 新建 | +170 |
| `backend/app/ai/schemas/__init__.py` | 修改 | +8 / -3（替换占位注释 + 加 register） |
| `backend/tests/test_ai_schemas_f211a1.py` | 新建 | +360 |

---

## 3. 完成标准（每条可测试）

| # | 完成标准 | 测试层级 | 工具 |
|---|---------|---------|------|
| C1 | `contradiction_detector` input 15 字段约束生效；earningsRisk/daysToEarnings 接受 None | 单元 | pytest |
| C2 | `contradiction_detector` output：contradictions 0-5 / recommendation 必填；severity 三枚举强校验 | 单元 | pytest |
| C3 | `contradiction_detector` guardrail：BANNED_PHRASES 命中（recommendation 或 contradictions[].text）→ AiGuardrailViolation | 单元 | pytest |
| C4 | `news_summarizer` input：articles 1-30 / windowDays default 5 / contentText ≤2000 | 单元 | pytest |
| C5 | `news_summarizer` output：sentiment 三枚举；relevantTickers ≤10；risks ≤5 | 单元 | pytest |
| C6 | `news_summarizer` guardrail：catalystSummary 或 risks 命中 banned → 抛 violation | 单元 | pytest |
| C7 | `journal_assistant` input：mode=trade ⇄ trade payload 强一致；mode=monthly ⇄ monthly payload 强一致；混用抛 ValidationError | 单元 | pytest |
| C8 | `journal_assistant` output：mode 字段强校验；trade/monthly payload 不可同时存在 | 单元 | pytest |
| C9 | `journal_assistant` guardrail：trade.lesson 或 monthly.keyLessons 命中 banned → violation | 单元 | pytest |
| C10 | REGISTRY：`get_schemas("contradiction_detector")` / `get_schemas("news_summarizer")` / `get_schemas("journal_assistant")` 三个 task_type 返回 SchemaPair | 单元 | pytest |
| C11 | guardrail hooks：`guardrail._HOOKS["contradiction_detector"]` / `["news_summarizer"]` / `["journal_assistant"]` 三个均已注册 | 单元 | pytest |
| C12 | routing：`resolve_tier` 对三 task 分别返回 default / default / complex（与 _TASK_TIER 现状一致） | 单元 | pytest |
| C13 | gateway e2e（复用 test_ai_gateway_e2e_f208c 的 monkeypatch 套路）：mock LLM 输出后 `task_type=contradiction_detector` 调用成功，memo 入表，guardrail 不阻断（无 banned phrase）；含 banned phrase 的响应 → 抛 AiGuardrailViolation 且 ai_memos count 不增 | 集成 | pytest + monkeypatch |
| C14 | 全量回归：`uv run pytest backend/tests/` 全绿（≥ 之前基线条数 + ~38） | 回归 | pytest |
| C15 | `uv run mypy backend/app/ai/schemas/` 无新错（与 F209/F210 同基线） | 工程 | mypy |
| C16 | 进程启动 smoke：`uv run python -c "from app.ai.schemas import REGISTRY; assert all(t in REGISTRY for t in ['contradiction_detector','news_summarizer','journal_assistant'])"` 退出码 0 | 工程 | python |
| C17 | features.json AC 对应：AC1（三 task schema 齐全 ✅ C1+C4+C7）/ AC2（contradiction:default + journal:complex ✅ C12）/ AC3-AC6（前端 / 月度 cron 在 F211-b/c/d）→ 本 sprint 满足 AC1+AC2 | 文档 | grep |

---

## 4. 开发顺序（Generator 模式严格执行）

```
1. 确认 DATA-MODEL.md 无需改动 → ✅（不动表）
2. 确认 API-CONTRACT.md 无需改动 → ✅（统一 envelope 已涵盖 7 task；schema 细节由 feature-dev 落地，line 1731-1732 明文允许）
3. 确认 routing.py 已映射三 task tier → ✅（line 12-14 已存在）
4. 数据库迁移 → ⏭ 跳过
5. Repository → ⏭ 跳过
6. Service → ⏭ 跳过
7. 单元测试 + Schema 落地交叠（TDD 风格）：
   7a. 新建 contradiction_detector.py（schema + SYSTEM_PROMPT + BANNED_PHRASES + guardrail）
       → 写 TestContradictionInput / Output / Guardrail (CI/CO/CG 共 15 用例) → 跑通
       → wip commit `wip(F211-a1): contradiction_detector schema + tests`
   7b. 新建 news_summarizer.py（schema + guardrail）
       → 写 TestNewsInput / Output / Guardrail (NI/NO/NG 共 12 用例) → 跑通
       → wip commit `wip(F211-a1): news_summarizer schema + tests`
   7c. 新建 journal_assistant.py（含 model_validator 双模式校验）
       → 写 TestJournalInput / Output / Guardrail (JI/JO/JG 共 11 用例) → 跑通
       → wip commit `wip(F211-a1): journal_assistant schema + tests`
   7d. 修改 schemas/__init__.py（REGISTRY 三行 + register 三行，替换占位注释）
       → 写 TestRegistry (R1-R7 共 7 用例) → 跑通
       → wip commit `wip(F211-a1): registry wiring`
8. 加 e2e 集成测试（C13）：在已有 `test_ai_gateway_e2e_f208c.py` 内追加（不计入 5 文件上限，规则 8 测试扩展许可），或新建 `test_ai_gateway_e2e_f211a1.py`
   → 默认追加到已有文件（避免文件爆炸）
   → wip commit `wip(F211-a1): e2e gateway integration`
9. 全量 pytest + mypy + uvicorn smoke 全绿
10. Evaluator 模式自检
```

每个 wip commit 必须 `git add` 显式列文件，**禁用 `git add -A`**（Sprint Contract 规则 7）。

---

## 5. Evaluator 自检清单

- [ ] 单元测试：CI1-CI6 / CO1-CO6 / CG1-CG3 / NI1-NI6 / NO1-NO4 / NG1-NG2 / JI1-JI6 / JO1-JO3 / JG1-JG2 / R1-R7 共 ~38 用例全部通过
- [ ] 集成测试 C13 通过（guardrail 命中时 ai_memos 计数不增）
- [ ] `uv run pytest backend/tests/ -v` 全绿（≥ 之前基线 + ~38）
- [ ] `uv run mypy backend/app/ai/` 无新错
- [ ] 启动 smoke：`uv run uvicorn app.main:app --port 8001` 不报 import 错（schemas/__init__.py 模块加载即触发 register）
- [ ] `curl -X POST localhost:8001/api/ai/contradiction_detector -H "Content-Type: application/json" -d '{"input":{...},"noCache":true}'` 在无 OPENAI_API_KEY 时收到 `AI_PROVIDER_ERROR`（502），不是 schema/registry 报错
- [ ] BANNED_PHRASES 列表与 F209-a / F210-a 完全一致（grep 比对 6 个标准 phrase）
- [ ] D074 字段命名：所有 input/output 字段均 camelCase 直名（不用 alias 风格）
- [ ] D070 合规：3 个 schema 文件无引入 cockpit_params；schema 内常量（max_length=30 / 2000 等）属 schema 层文案约束，不进 cockpit_params（同 F209/F210 先例）
- [ ] 颜色 / 前端 token 不涉及（纯后端 sprint）
- [ ] 无 `print` / `console.error` 残余
- [ ] **回归测试（强制）**：全量 pytest 通过；如有非本 sprint 引入的预先失败，标"预先存在"且报告用户
- [ ] **代码质量自检**：3 个 schema 文件均有 module docstring；所有 BaseModel 含 `model_config = {"extra": "forbid"}`；无硬编码魔法值（除 schema 文案约束）
- [ ] **`git status` 无遗留未提交改动**（Sprint Contract 规则 7 session 结束清点）

通过后：
- [ ] 更新 features.json：F211 sub_sprints 中 `F211-a1` 由 `design_needed` 直升 `done`（跳过 contract_agreed/in_progress/testing/needs_review 中间态由 Generator session 自然推进）
- [ ] 调用 **consistency-check (mode=interactive)** 验证 C1（父 F211 不可升 done — 仍有 a2/b/c/d 未完）+ C4（iteration_history 补 F211-a1 entry）+ C5（F211-a1-contract.md 已存在）
- [ ] 全清后通知用户验收

---

## 6. 开放问题

| # | 问题 | 默认 | 备选 |
|---|------|------|------|
| Q1 | `contradiction_detector` input 是否包含 `volumeContext`（如近 5 日成交量 / 平均量比）？features.json 提到"volume distribution" | **否**，本 sprint 仅 15 字段；volume 字段在 SetupSnapshot 现状不存在，避免新引入；"volume distribution" 留 future iteration | 加 `avgVolumeRatio: float \| None`，前端 F211-b 从 daily_bars 算 |
| Q2 | `news_summarizer.contentText` 上限 2000 字符（每条）+ 30 条（合计 60K），对 default tier nano 是否过大？ | **保留 2000**；前端 F211-c 实际上从 contentHtml 剥离时通常 ≤500；上限是防极端 | 降到 1000 保守 |
| Q3 | `journal_assistant.MonthlyReviewPayload.closedTrades` 上限 100 条，月成交>100 时如何？ | **强校验 100**；F211-d 月度 cron 自行 sort+top100；schema 不做截断 | 升到 200，对应模型升 critical tier（违 features.json AC2） |
| Q4 | `journal_assistant` mode 字段是否进 input 校验后冗余存到 output？（增加 round-trip 一致性） | **是**，output 也有 mode 字段，model_validator 校验 mode 与 payload 一致 | 仅 input 有 mode，output 由 payload 类型隐式表达 |
| Q5 | `contradiction_detector` 输出 `contradictions` 允许空数组（无矛盾时输出 `[]`），是否 acceptable？ | **是**，`min_length=0`；recommendation 写 "No major contradictions" | `min_length=1` 强制至少 1 条（即使是 LOW 级别的提示） |
| Q6 | journal_assistant 是否在本 sprint 加入"奉承话"反向 prompt（"avoid empty praise"）？ | **否**，仅 6 个标准 BANNED_PHRASES；扩展留 F211-d 实际用上后再调 | 加，但需补对应测试用例 |

> Q1/Q2/Q3/Q5 默认采用本表方案；Q4 默认采用（双向校验更安全）；Q6 默认不加（YAGNI）。

---

## 7. 风险

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| LiteLLM `response_format=Pydantic` 对双模式 discriminated union（journal_assistant）支持不一致 | 中 | LLM 输出可能 mode/payload 错位 → schema 二次校验失败 → AiSchemaError | gateway step 8 已有兜底；本 sprint 单测不依赖真 LLM；F211-d 真实调用时如频繁失败再考虑改成两个独立 task_type |
| `news_summarizer` 输入 30×2000=60K 字符可能触发 default tier nano 上下文限制 | 中 | LLM 报错 / 输出截断 | F211-c 前端实际 slice 通常 ≤500 char/条；F211-a2 完成后用户可改 base_url 用更大 context 模型；本 sprint 不优化 |
| `model_validator` 在 Pydantic v2 用法误差（after vs before） | 低 | 校验未执行 / 错误抛点 | 测试用例 JI3-JI4 / JO2 强制覆盖各种错位；CI 有 mypy + pytest 双保险 |
| BANNED_PHRASES 命中误伤合法内容（如 reason 中合理引用 "ignore stop"） | 低 | 用户 perceived 'AI 过敏' | 现状沿用 F209/F210 6 个 phrase；如 F211-c 上线后投诉再回收调整 |
| `routing._TASK_TIER` 已含三 task 但实际 model env 未配置 / 错配（complex tier 模型不存在） | 中 | journal_assistant 调用 502 | F211-a2 sprint 把 override 基建建好后用户可任意指定；本 sprint 仅校验 tier resolve，不验真模型 |

---

## 8. F211-a2 / b / c / d 骨架预览（仅供用户确认拆分合理性，非本 sprint 落地）

### F211-a2 — per-task model override 基建

**触发**：F211-a1 Evaluator 通过后开新 sprint（可与 b/c/d 并行）。

**核心**：
- 修改 `backend/app/config.py`：加 `ai_task_overrides_json: str = ""` 字段
- 修改 `backend/app/ai/routing.py`：`resolve()` 增 override lookup，未命中走 tier；返回 `(model, base_url, api_key, custom_input_cost, custom_output_cost)` 五元组
- 修改 `backend/app/ai/gateway.py`：调 LiteLLM 时透传 `api_base / api_key`；startup hook 调 `litellm.register_model({...})` 注入自定义价
- 新建 `backend/tests/test_ai_routing_overrides.py`：override 命中 / fallback / cost 注入测试
- 追加 `docs/系统设计/DECISIONS.md`：D-entry「per-task model override」（D064 兄弟决策）
- 用 context7 查 `/websites/litellm`（CLAUDE.md 强制）确认 `api_base` / `api_key` per-call 调用 + `register_model` 当前 API 形态

预计 5 文件。

### F211-b — DecisionPanel Contradictions 区前端

**核心**：
- 新建 `frontend/src/cockpit/components/AiContradictionsSection.tsx`（按钮 + 三色 chip 列表 + recommendation）
- 修改 `DecisionPanelWidget.tsx`：在 AI Trade Plan 下方追加 Contradictions 区
- 测试扩展（component test + widget test 段）

预计 3-4 文件。

### F211-c — News 页 AI 摘要 bar 前端（含 tokens / cost 展示）

**核心**：
- 新建 `frontend/src/components/news/AiNewsSummaryBar.tsx`（按钮 + catalystSummary + sentiment chip + relevantTickers + risks + **`meta.tokensIn/tokensOut/costUsd/modelUsed/cacheHit` 展示**）
- 修改 `frontend/src/pages/News.tsx`：顶部插入该 bar（独立于 NewsWidget）
- 前端 contentHtml → contentText 剥离 helper（DOMParser textContent，slice 到 ≤500 chars）
- 测试

预计 3-4 文件。

### F211-d — 平仓 hook + ai_review 迁移 + 月度 cron

**核心**：
- 新建 alembic migration `017_f211d_journal_entries_ai_review.py`：`journal_entries` 加 `ai_review TEXT` 列
- 修改 `backend/app/models/journal_entry.py`：加 `ai_review` 字段
- 修改 `backend/app/services/cockpit/position_service.py`：CLOSED 分支异步触发 journal_assistant（trade mode）+ 创建 journal_entry 行写 ai_review（**用户确认方案 B**：新建 entry，不复用最近一条）
- 新建 `backend/app/services/journal_review_service.py`：trade mode + monthly mode 调用 + ai_memos 写入
- 修改 `backend/app/services/refresh_job.py`：加 `journal_monthly_cron`（每月 1 号 06:00 UTC，复用 ai_memos 表）
- 测试 `backend/tests/test_journal_review_f211d.py`

预计 5-6 文件。

---

## 9. 用户确认点

确认 Contract 后我会：
1. 更新 features.json：F211-a1 sub_sprint 由 `design_needed` 升 `contract_agreed`；记录 `contract_agreed_at: 2026-04-28`；append 一条 iteration_history 记录（C5 trigger 闭合）
2. 更新 claude-progress.txt（追加 F211-a1 Contract 协商完成记录）
3. 生成新 SESSION-HANDOFF.md（覆盖上一份，下一步指向 F211-a1 Generator 模式）
4. **强制停止本 session**，建议你在新 session 开 Sonnet 进入 Generator 模式，粘贴指令：
   ```
   继续开发 F211-a1，Sprint Contract 已确认。
   读取 SESSION-HANDOFF.md + docs/开发/sprint-contracts/F211-a1-contract.md，
   进入 Generator 模式，从开发步骤 7a 开始。
   ```

不在同一 session 中继续进入 Generator 模式（feature-dev 规则）。
