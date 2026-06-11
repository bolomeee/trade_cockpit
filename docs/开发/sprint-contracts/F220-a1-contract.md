---
status: deprecated
feature: F220
sub_sprint: F220-a1
date: 2026-06-10
confirmed_at: 2026-06-10
revision_needed_at: 2026-06-10
deprecated_at: 2026-06-10
file_count: 4
parent_split: F220-a 全量 7 文件 → F220-a1 后端核心(4) + F220-a2 前端展示(3)，用户 2026-06-10 确认
deprecated_reason: 用户 2026-06-10 裁决放弃自算正常化 P/E，主位直接用 FMP raw priceToEarningsRatioTTM（现状 F104 已透传，零代码满足）。重谈期 5 票探针显示 raw 对 4/5 已准且自动处理货币，唯 DUOL 类一次性虚低不修正（接受）。F220-a1/a2/c 整体 deprecated，held 代码已丢弃。详见 docs/验收/v2.6-F220-a1-acceptance.md
---

> ⚠️ **本合约已 DEPRECATED（2026-06-10）**。F220-a1 正常化 P/E 方案放弃，P/E 改用 FMP raw（现状即满足）。以下原合约内容仅作历史留档。

# F220-a1 Sprint Contract — 正常化 P/E 核心（后端切片）

> 生成：2026-06-10 | 状态：草案 → 待用户 ack
> Feature：[F220](docs/需求/features.json) Fundamentals 估值指标增强 — 正常化 P/E 体系
> Sub-sprint：F220-a1（F220-a 拆分后第 1 片；后端闭环，纯算法 + service 编排 + schema）
> 前置：F102 / F104 / F218 done（Fundamentals widget + FMP 基本面接入 + FMP 季报端点已上线）
> 下游：F220-a2（前端 FundamentalsCard 主位 + 追溯折叠区，F220-a1 done 后开启）

> 引用文档：
> - [API-CONTRACT.md §GET /api/stocks/:ticker/fundamentals](docs/系统设计/API-CONTRACT.md) — 正常化字段 + traceability 子对象契约（本切片实现 normalizedPe/normalizedEps/normalizedTtmEarnings + traceability，degradeReason 枚举）
> - [DATA-MODEL.md §DailyPayloadCache](docs/系统设计/DATA-MODEL.md) — endpoint="fundamentals" payload 复用，无新表
> - [DECISIONS.md §D104/§D106/§D107](docs/系统设计/DECISIONS.md) — 税率防循环 / 成员门控 / 降级不回退 raw（本切片落地）
> - [ARCHITECTURE.md §Normalized Valuation](docs/系统设计/ARCHITECTURE.md) — 模块位置 + 编排链 + 架构守约（禁 import cockpit）
> - [pool_helpers.py](backend/app/services/cockpit/pool_helpers.py) — `compute_*_from_*` 纯函数模式样板（**仅照其风格，禁 import**）
> - [last_close_loader.py](backend/app/services/cockpit/last_close_loader.py) — 当前价解析模式样板（**仅内联复刻，禁 import**，cockpit 命名空间）
> - [stock_detail_service.py:220](backend/app/services/stock_detail_service.py) — `get_fundamentals` 编排接入点
> - [F219-a-contract.md](docs/开发/sprint-contracts/F219-a-contract.md) — 后端 indicator + schema 扩展同款结构样板

---

## 0. 背景与定位

当前 `get_fundamentals` 直接透传 FMP `/ratios-ttm.priceToEarningsRatioTTM`，原始 GAAP P/E 极易被一次性会计项目失真（DUOL FY2025 含一次性递延税资产转回 ~$222.7M，原始 P/E ~13× 假象便宜，正常化后 ~28×）。

F220-a1 实现**正常化 P/E 主锚**的后端闭环：纯函数算法（季报归一化 → 防循环平均有效税率 → 异常季税后营业利润 NOPAT 替代 → TTM 正常化 EPS → 正常化 P/E）+ `get_fundamentals` 成员门控编排 + 当前价解析 + schema 扩展 + same-day cache。**只做正常化 P/E 核心**，交叉验证指标 P/(FCF−SBC)、EPS 加速度、预期修正、时序表写入全部归后续 sub-sprint。

---

## 1. 实现范围

### 1.1 新建 `backend/app/services/normalized_valuation.py`（纯函数，workbench 命名空间）

全部无 IO / 无 DB / 无日志，照 `cockpit/pool_helpers.py` 的 `compute_*_from_*` 纯函数模式（`_to_float` 容错 + None 传播），**禁止 import 它**。本切片函数：

```python
# (a) 季报归一化（仅利润表；现金流归 F220-b）
def normalize_income_quarter(raw: dict) -> dict | None:
    # 解析 netIncome / operatingIncome / incomeTaxExpense / incomeBeforeTax /
    #       weightedAverageShsOutDil；period 标识 date/period/fiscalYear
    # 缺关键字段 → None
    ...

# (b) 防循环平均有效税率（D104，设计文档点名的关键防护）
def compute_normal_tax_rate(quarters: list[dict]) -> tuple[float | None, list[str]]:
    # 升序、已归一化。seed = 仅 incomeBeforeTax>0 且 0≤rate≤0.50 的季（rate=tax/ibt）
    # 取最近 ≤4 个正常季均值；无可信种子 → (None, [])
    # ⚠️ 绝不复用净利润异常判定（循环依赖）；用税率自身边界独立筛
    ...

# (c) 税后营业利润 + 异常季判定（阈值 20%）
def classify_quarters(quarters: list[dict], tax_rate: float, threshold: float = 0.20) -> list[dict]:
    # nopat = operatingIncome * (1 - tax_rate)
    # operatingIncome≈0 → abnormal=False, deviate=None（不可判定）
    # else deviate = (netIncome - nopat)/abs(nopat); abnormal = abs(deviate) > threshold
    # usedEarnings = nopat if abnormal else netIncome
    # → {label, gaapNi, nopat, deviatePct, abnormal, usedEarnings, reason}
    ...

# (d) TTM 正常化盈利 / EPS / P/E（含降级）
def compute_normalized_pe(classified_last4: list[dict], diluted_shares, price) -> dict:
    # len<4 → degrade("insufficient_quarters")
    # ttm = Σ usedEarnings(最近4季)
    # diluted_shares 缺/≤0 → None；norm_eps = ttm/diluted_shares
    # norm_eps≤0 → degrade("negative_normalized_eps")
    # price None → degrade("no_price")
    # → {normalizedPe, normalizedEps, normalizedTtmEarnings, degradeReason}
    ...
```

> 顶层硬编码常量（带注释来源 D104/计划 §R2）：`ABNORMAL_DEVIATE_THRESHOLD = 0.20`、`TAX_RATE_MIN = 0.0`、`TAX_RATE_MAX = 0.50`、`TTM_QUARTERS = 4`、`QUARTERLY_LIMIT = 8`。

### 1.2 修改 `backend/app/services/stock_detail_service.py`：`get_fundamentals` 编排

在现有 same-day cache 短路（保留，命中含新字段直接返回）之后、原始 ratios/key-metrics 组装之后，追加正常化编排：

```python
# 成员门控（D106）：watchlist active OR trend pool 成员
stock = self.stocks.get_by_ticker(ticker)        # 已有
is_member = (stock is not None and stock.is_active) or self._is_pool_member(ticker)
if not is_member:
    payload[...正常化字段...] = None
    payload["traceability"] = {"degradeReason": "out_of_scope"}
else:
    quarters_raw = self.fmp.get_income_statement_quarterly(ticker, limit=8)  # 复用 F218 方法（返 raw dict）
    price, price_source = self._resolve_current_price(ticker, stock)
    # normalize → compute_normal_tax_rate → classify_quarters → compute_normalized_pe
    # 组装 normalizedPe/Eps/TtmEarnings + traceability(currentPrice/priceSource/
    #   dilutedShares/avgEffectiveTaxRate/taxRateSourceQuarters/abnormalQuarters/degradeReason)
upsert_today_payload(self.db, ticker, ENDPOINT_FUNDAMENTALS, payload)   # 含新字段
```

新增私有方法（同文件内）：
- `_is_pool_member(ticker) -> bool`：直接 `select(CockpitPoolCache.ticker).where(...==ticker)`（导入 **model** `app.models.cockpit_pool_cache`，**非** cockpit service；坐实待查-1，service 已用 `select` 风格一致）。
- `_resolve_current_price(ticker, stock) -> tuple[float|None, str|None]`：watchlist active → `daily_bars` 最新 close（同 LastCloseLoader Step2 子查询）；否则 → FMP `get_daily_bars(ticker, today-30, today)` 取末根 close（内联复刻 `_fmp_latest_close`，**禁 import cockpit**）。两路皆失败 → (None, None)。fail-open。

**fail-open（D107）**：季报拉取异常 / 不足 / 价缺失 → 正常化字段 None + degradeReason，`get_fundamentals` 仍返 200，原始 priceToEarnings/priceToSales/peg/roce/freeCashFlow/marketCap/sharesFloat 照常。

### 1.3 修改 `backend/app/schemas/stock_detail.py`：`Fundamentals` 扩展 + 2 子模型

```python
class AbnormalQuarter(CamelModel):
    label: str
    gaap_ni: float | None = None
    nopat: float | None = None
    deviate_pct: float | None = None
    abnormal: bool
    used_earnings: float | None = None
    reason: str | None = None

class TraceabilityBlock(CamelModel):
    current_price: float | None = None
    price_source: str | None = None
    diluted_shares: float | None = None
    avg_effective_tax_rate: float | None = None
    tax_rate_source_quarters: list[str] = []
    abnormal_quarters: list[AbnormalQuarter] = []
    degrade_reason: str | None = None

class Fundamentals(CamelModel):
    # ...既有字段保留（priceToEarnings 作 raw 不动）...
    normalized_pe: float | None = None
    normalized_eps: float | None = None
    normalized_ttm_earnings: float | None = None
    traceability: TraceabilityBlock | None = None
```

> `price_to_earnings` 等既有字段维持 `float | None`（已是）；现有行为零变化。

### 1.4 明确排除（本 sprint 不做，归后续 sub-sprint）

- **现金流解析 / P/(FCF−SBC) / 自洽红旗 / 市值自算** → F220-b（a1 只 fetch 利润表，不 fetch cash-flow）
- **EPS 加速度（normalized_eps_series + 二阶差分）** → F220-d
- **预期修正（analyst-estimates / estimateRevision）** → F220-e
- **normalized_pe_history 时序表写入 + normalizedPePercentile 字段** → F220-c（本切片 schema 不含 percentile）
- **pFcfRaw/pFcfAdj/sbcSensitiveFlag/epsAcceleration/estimateRevision schema 字段** → 各自 sub-sprint 增量加（a1 schema 只加 normalizedPe/Eps/TtmEarnings + traceability）
- **所有前端文件**（FundamentalsCard / types / WidgetRegistry）→ F220-a2
- **NTM / forward P/E、阈值参数化** → 不做（硬编码常量）

---

## 2. 预计修改文件（共 4 个）

| 文件路径 | 改动类型 | 说明 |
|---------|---------|------|
| `backend/app/services/normalized_valuation.py` | 新增 | 纯函数：normalize_income_quarter / compute_normal_tax_rate（防循环）/ classify_quarters / compute_normalized_pe + 阈值常量 |
| `backend/tests/test_normalized_valuation.py` | 新增 | 单测：**防循环回归（硬要求）** + 异常季判定 + TTM/降级 + DUOL fixture + service 门控/fail-open |
| `backend/app/services/stock_detail_service.py` | 修改 | `get_fundamentals` 成员门控编排 + `_is_pool_member` + `_resolve_current_price`；fail-open；payload 含新字段 |
| `backend/app/schemas/stock_detail.py` | 修改 | `Fundamentals` +4 字段 + 新 `TraceabilityBlock` / `AbnormalQuarter` 子模型 |

✅ **4 文件，6-file 上限内，无需例外授权。**

👤 用户确认文件清单 + §5 假设后，方可进入 Generator。

---

## 3. 文档同步

| 阶段 | 文档 | 状态 |
|------|------|------|
| **开发前** | API-CONTRACT.md §GET /fundamentals 正常化字段 + traceability | ✅ 已于 system-design confirmed @ 2026-06-10 |
| **开发前** | DATA-MODEL.md §DailyPayloadCache F220 复用注记 | ✅ 已 confirmed |
| **开发前** | DECISIONS.md D104/D106/D107 | ✅ 已 confirmed（D105 市值自算归 F220-b 落地） |
| **开发后** | DECISIONS.md | 若 Generator 期间出现文档未覆盖的非显而易见决策（如 FMP IBT 字段名变体处置）→ 追加 D108+ |

---

## 4. 可测试的完成标准

| # | 标准描述 | 测试层级 | 工具 |
|---|---------|---------|------|
| 1 | `normalize_income_quarter` 解析 netIncome/operatingIncome/incomeTaxExpense/incomeBeforeTax/weightedAverageShsOutDil；缺关键字段 → None | 单元 | pytest |
| 2 | **防循环（硬要求）**：构造含一次性税项的季报序列（某季 rate<0 / 某季 rate>0.50 / 某季 IBT≤0），`compute_normal_tax_rate` 剔除全部污染季，均值仅来自 0≤rate≤0.50 且 IBT>0 的正常季，返回正确来源季度 label 列表 | 单元 | pytest |
| 3 | `compute_normal_tax_rate` 全季 IBT≤0 或越界 → 返回 (None, [])（触发 no_tax_seed 降级） | 单元 | pytest |
| 4 | `classify_quarters`：GAAP NI 偏离 NOPAT >20% → abnormal=True 且 usedEarnings=nopat；≤20% → abnormal=False 且 usedEarnings=netIncome | 单元 | pytest |
| 5 | `classify_quarters`：operatingIncome≈0 → deviate=None, abnormal=False（不可判定不误判替换） | 单元 | pytest |
| 6 | `compute_normalized_pe`：classified<4 → degradeReason=insufficient_quarters；norm_eps≤0 → negative_normalized_eps；price None → no_price；happy → price/norm_eps | 单元 | pytest |
| 7 | **DUOL fixture 端到端**：含 Q3 一次性税项的 8 季利润表 → 正常化 P/E ∈ [25,30]×（raw≈13×）；Q3 标 abnormal + deviatePct；税率排除 Q3、来源季度列出 | 单元 | pytest |
| 8 | `get_fundamentals` 成员门控：非 watchlist 非 pool ticker → 正常化字段 None + traceability.degradeReason="out_of_scope"，原始 TTM 指标照常返回 | 集成 | pytest + TestClient |
| 9 | `get_fundamentals` fail-open：成员但季报<4 → degradeReason=insufficient_quarters，endpoint 仍 200，原始 P/S/PEG/ROCE/FCF 照常 | 集成 | pytest + TestClient |
| 10 | `_resolve_current_price`：watchlist → daily_bars 末 close；pool-非watchlist → FMP EOD 末根；两路失败 → (None,None) | 单元 | pytest（mock db/fmp） |
| 11 | `GET /api/stocks/{ticker}/fundamentals` 成员响应含 normalizedPe + traceability（camelCase）；schema 校验通过 | 集成 | pytest + TestClient |
| 12 | 全量后端 pytest 无新增失败（对比 F219 baseline） | 回归 | pytest |

---

## 5. 关键假设（A-1 假设外显，请用户确认 ⚠️ 项）

| # | 假设 | 来源 | 需确认 |
|---|------|------|--------|
| 1 | FMP `/income-statement?period=quarter` raw dict 含 `incomeTaxExpense` / `incomeBeforeTax`（或 `incomeBeforeIncomeTaxes` 变体）/ `weightedAverageShsOutDil` 字段；Generator 对真实响应核对字段名，缺失走 None 传播（待查-2 相邻） | 推断（FMP 标准字段）+ fail-open | ⚠️ 是（实现时核对，但不阻断本合约） |
| 2 | `_resolve_current_price` **内联复刻** LastCloseLoader 模式（watchlist→daily_bars / pool→FMP EOD 末根），**不 import** cockpit | ARCHITECTURE 守约 + D106 | ⬜ 否（守约强制） |
| 3 | pool 成员判断 = `get_fundamentals` 内直接 `select(CockpitPoolCache.ticker)` 读模型（坐实待查-1），**不新建 repository、不 import cockpit service**；若你更想要独立只读 repository（+1 文件=5，仍 ≤6），请在 ack 时指出 | 极简 + D106（service 已用 select 风格） | ⚠️ 是（默认直读，可改 repository） |
| 4 | a1 仅 fetch 利润表（不 fetch cash-flow）；P/(FCF−SBC) 整体归 F220-b | 范围切分 | ⬜ 否 |
| 5 | 阈值硬编码常量（异常 20% / 税率 0–50% / TTM 4 季 / limit=8），不参数化 | D104 + R2 | ⬜ 否 |
| 6 | DUOL 实测验收（非单测 fixture）需 DUOL ∈ watchlist 或 pool；若不在，验收前手动加入 watchlist | 推断 | ⬜ 否（验收期处理） |

> 规则：假设 1、3 标 ⚠️。假设 1 是运行期事实（fail-open 兜底，不阻断合约）；假设 3 是极简默认（可在 ack 时改为独立 repository）。两者均不改变 4 文件结论与算法逻辑，故**随合约一并 ack**，无需单独前置停。

---

## 6. Evaluator 自检清单

开发完成后，Evaluator 模式逐条检查：

- [ ] `cd backend && pytest tests/test_normalized_valuation.py -v` 全通过（含防循环回归 + DUOL fixture）
- [ ] `cd backend && pytest`（全量回归）无新增失败（对比 F219 baseline）
- [ ] `normalized_valuation.py` 零 import `cockpit/*`（grep 校验）；纯函数无 db/httpx/logging
- [ ] `_resolve_current_price` / `_is_pool_member` 不 import cockpit service（仅 model + fmp + daily_bars）
- [ ] API 响应 camelCase 符合 API-CONTRACT.md（normalizedPe / traceability.degradeReason 等）
- [ ] 字段命名符合 DATA-MODEL.md（payload 复用 daily_payload_cache）
- [ ] 降级路径：4 种 degradeReason + out_of_scope 全部有测试覆盖，**绝不回退 raw**（断言 normalizedPe=None 时 priceToEarnings 仍在但前端不当主位）
- [ ] 无硬编码魔法值散落（阈值集中常量）
- [ ] 无 print / 调试日志残留
- [ ] 非显而易见决策（如 IBT 字段名变体处置）已追加 DECISIONS.md
- [ ] 实现范围严格等于 §1（无 P/FCF / 无 EPS 加速度 / 无时序写入 / 无前端）
- [ ] 修改文件严格等于 §2 清单（4 文件，无新增无遗漏）
- [ ] features.json `F220.sub_sprints['F220-a1']` → done（Evaluator 通过 + acceptance 后）

---

## 7. 完成后的衔接

- F220-a1 `done` → F220-a2（前端）进入 contract：FundamentalsCard 主位正常化 P/E 大字 + raw 副标 + `<details>` 追溯折叠区 + WidgetRegistry 高度上调 + types（3 文件）
- 之后 F220-b（P/(FCF−SBC) 双版本 + 红旗）→ F220-c（时序表）→ F220-d（EPS 加速度）→ F220-e（预期修正）
- F220 整体 needs_review 等 acceptance（全部 sub-sprint done 后，DUOL 实测）

---

👤 **请确认：① 4 文件清单；② §5 假设（尤其 ⚠️ 1/3：FMP 字段核对走 fail-open、pool 成员直读模型 vs 独立 repository）；③ 完成标准。确认后我执行 A-1 收尾（落盘 confirmed + features.json + SESSION-HANDOFF + commit），然后按 skill 铁律停在本 session，Generator 开发在新 session 进行。**

---

## Contract 修订 — 2026-06-10（acceptance 验收发现设计偏差）

> 状态：confirmed → **revision_needed**。Generator 已按原合约实现完毕、Evaluator + 29 单测全过（含 DUOL fixture），但 **acceptance live DUOL 实测**（真实 FMP，read-only smoke）暴露算法口径偏差，验收 **NOT PASS**，回退 needs_review → contract_agreed。完整验收记录：[docs/验收/v2.6-F220-a1-acceptance.md](../../验收/v2.6-F220-a1-acceptance.md)。

**变更原因（验收发现需求理解偏差）**：

原始 §1.1(c) `classify_quarters` + §4 标准 #4/#7 假定 DUOL 仅 2025Q3（一次性递延税项）为异常季，正常化 P/E 落 [25,30]×。**live DUOL 实测推翻此假定**：

| 项 | 设计/B1 期望 | live 实际 |
|---|---|---|
| raw priceToEarnings | ≈13× | 13.06× ✅ |
| normalizedPe | [25,30]× | **45.3×** ❌ |
| 异常季 | 仅 2025Q3 | **8 季全异常**（deviatePct 0.22–1.12，唯 2025Q3=8.40 是真离群）❌ |
| TTM 正常化盈利 | ~$373M | $127M（全 NOPAT）|

**根因**：`NOPAT = operatingIncome × (1−taxRate)` 同时剔除「一次性项目」与「结构性经常性非经营收入」。DUOL 每季有 ~$8–12M 经常性利息收入（IBT−opInc）+ 多个低税季（8% / 3.6% / −0.4%），使 GAAP NI 结构性高出 NOPAT 22%+，20% 阈值因此把每一季都判异常 → 全量 NOPAT 替代 → 正常化盈利坍塌、P/E 虚高到 45×。代码忠于合约，**偏差在合约算法本身**：20% NOPAT 规则未区分「一次性」与「结构性非经营收入」。

**待重谈（feature-dev 重新协商时由用户定口径）**：
- §1.1(c) `classify_quarters` 异常判定口径 —— 候选方向：(a) 大幅提高 deviate 阈值（只捕 8.4 类真离群值，DUOL 数据中一次性 8.40 vs 结构性 ≤1.12 有清晰断层）；(b) 改用 cohort 中位数/MAD 相对法（季偏离显著高于本票自身基线才判异常）；(c) 把结构性经常性非经营收入纳回「正常盈利」，NOPAT 仅用于剥离真一次性项目。
- §4 标准 #4（>20% → abnormal）+ #7（B1：DUOL∈[25,30]×、仅 Q3 异常）随口径同步修订；[25,30] 区间需按修订后口径 + 当前价（117.86，非设计时 258.7）重新标定。

**不变（保留已实现代码，仅 classify_quarters 待改）**：normalize_income_quarter / compute_normal_tax_rate（防循环 D104）/ compute_normalized_pe（TTM+降级）/ get_fundamentals 成员门控编排 / _resolve_current_price / schema / fail-open / 字段名（live 已验证全在）。

**修订后的 acceptance_criteria**：⬜ 待 feature-dev 重谈 session 精化方向 c 算法后填写（见下「修订方向已定」）。届时 phase contract_agreed → in_progress 重走 Generator。

---

### 修订方向已定（2026-06-10 用户拍板）

5 样本跨公司探针（DUOL/NKE/NVO/NTDOY/GRAB，详见 [验收记录](../../验收/v2.6-F220-a1-acceptance.md)）暴露三层系统性问题，用户裁决两项变更 + 一项边缘待处理：

**变更 1 — classify 口径改为方向 c（重定义正常盈利）**
- 原（§1.1(c)）：deviate = (NI − NOPAT)/|NOPAT|，>20% 即判异常并用 NOPAT 替代 → 误把**经常性非经营收入**（利息等）当异常剥离。
- 新口径：**正常盈利 = 经营利润 + 经常性非经营收入**（默认 `usedEarnings = GAAP netIncome`，保留经常性利息等）；NOPAT/替代**仅用于剥离真一次性项目**。
- ⚠️ **核心待精化（feature-dev 重谈定）**：「真一次性项目」的识别机制。候选信号——
  - (i) 极端有效税率季（如 DUOL 2025Q3 rate=−529%）→ 税项一次性；
  - (ii) 某季 NI 相对**自身基线**（最近 N 季 NI 中位数 ± k×MAD）显著离群 → 一次性（吸收方向 b 的"自身基线相对"思想）；
  - (iii) 一次性季的替代值口径（用经营+经常性非经营的近期均值？还是仅剔除异常税项？）。
- 普适性约束（重谈验收须满足）：NKE/NVO 这类干净公司 → 0 异常季、正常化≈raw；DUOL → 仅 2025Q3 一次性税项被剥离（≈35× 量级，非 45×）；不得对"非经营收入占比高"的公司无差别全季剥离。

**变更 2 — 新增货币闸（必修硬伤）**
- `reportedCurrency != "USD"` → 正常化字段 None + **新 degradeReason `unsupported_currency`**，绝不吐出币种错配的错误值（NTDOY=JPY / NVO=DKK 实测会静默错成 0.1×/1.5×）。
- ADR 折算（×汇率 ×ADR 比例）留后续 sub-sprint，本切片只做闸。
- 📌 doc-first 联动：需在 API-CONTRACT.md §fundamentals degradeReason 枚举增补 `unsupported_currency`（重谈定稿时走 system-design 变更协议，先文档后代码）。

**边缘 3 — 转盈/亏损公司税率代表性（GRAB）**
- `compute_normal_tax_rate` 对 GRAB（真实税负 0%~68% 跳动）筛出 3.3% 非代表性低率。重谈时评估：是否对税率种子季数/离散度设下限，无足够稳定种子 → `no_tax_seed` 降级而非用偏低率。

**保留不变（已实现、Evaluator 通过的部分）**：`normalize_income_quarter`（+IBT 变体回退、live 已验证字段名全在）/ `compute_normal_tax_rate` 防循环骨架（D104，仅边缘 3 待评估）/ `compute_normalized_pe`（TTM+降级）/ `get_fundamentals` 成员门控编排 / `_resolve_current_price` / schema / fail-open。**仅 `classify_quarters` 重写 + 新增货币闸 + (可能) 税率种子下限。**
