---
status: confirmed
feature: F220
sub_sprint: F220-b
date: 2026-06-11
confirmed_at: 2026-06-11
file_count: 6
parent_split: F220-a/a1/a2/c 正常化方案 deprecated（2026-06-10，P/E 改用 FMP raw）。F220-b 在上游归零后独立重定义 —— 详见 §0
---

# F220-b Sprint Contract — P/(FCF−SBC) 双版本（现金流交叉视角）

> 生成：2026-06-11 | 状态：草案 → 待用户 ack
> Feature：[F220](docs/需求/features.json) Fundamentals 估值指标增强
> Sub-sprint：F220-b（红旗已砍、上游正常化 P/E 已 deprecated 后的独立重定义版）
> 前置：F102 / F104 / F218 done（Fundamentals widget + FMP 基本面接入 + FMP 季报端点已上线）

> 引用文档：
> - [API-CONTRACT.md §GET /api/stocks/:ticker/fundamentals](docs/系统设计/API-CONTRACT.md) — F220 字段块（本切片激活 `pFcfRaw` / `pFcfAdj`，**移除** `sbcSensitiveFlag`，并把 pFcf 市值口径从「自算」改回「FMP marketCap」；Generator step 0 doc-first 修订）
> - [DECISIONS.md §D105 / §D106](docs/系统设计/DECISIONS.md) — D105 自洽红旗+自算市值（本切片**推翻**：红旗砍、市值改 FMP）/ D106 成员门控（本切片**落地**）
> - [stock_detail_service.py:220](backend/app/services/stock_detail_service.py) — `get_fundamentals` 编排接入点
> - [fmp_client.py:551 `get_cash_flow_quarterly`](backend/app/external/fmp_client.py) — F218 已存在，本切片复用，**不改 fmp_client**
> - [cockpit_pool_cache.py](backend/app/models/cockpit_pool_cache.py) — pool 成员只读判断（直读 model，禁 import cockpit service）
> - [F220-a1-contract.md](docs/开发/sprint-contracts/F220-a1-contract.md) — 成员门控 / fail-open / camelCase schema 同款结构样板（已 deprecated，仅参考结构）

---

## 0. 背景与定位（上游归零后的重定义）

F220-b 原设计（registry + system-design v2.6）是「P/(FCF−SBC) 双版本 + **自洽红旗** `sbcSensitiveFlag`」，红旗规则 = `|pFcfAdj − normalizedPe| / normalizedPe > 0.40`。

**2026-06-10 用户裁决放弃整个正常化 P/E 方案**（F220-a1/a2/c → deprecated，P/E 直接用 FMP raw）。这斩断了红旗的锚 —— `normalizedPe` 永不实现、恒 null，按契约兜底「任一为 null → false」红旗永远不亮，形同虚设。

2026-06-11 三项重定义决策（用户 AskUserQuestion 拍板）：

| 决策 | 选择 | 理由 |
|------|------|------|
| 自洽红旗 `sbcSensitiveFlag` | **砍掉** | 锚（normalizedPe）已废，无意义对比 |
| P/FCF 市值分子 | **FMP key-metrics-ttm `marketCap`** | 极简（已拉取，零额外调用）；P/FCF 教科书口径；ADR(JPY/DKK) 货币自动正确（自算 Diluted×price 有货币错配坑）。推翻 D105 自算口径 |
| pFcf 成员门控 | **门控 watchlist(active) ∪ pool**（D106 落地） | 季报现金流拉取走 FMP 配额，限于小集合；非成员 → null |

**最终范围**：纯现金流交叉视角双版本估值 —— `pFcfRaw = marketCap / FCF`、`pFcfAdj = marketCap / (FCF − SBC)`，SBC 当真实股东成本。无红旗、无新表、无新 endpoint、无 fmp_client 改动。

---

## 1. 实现范围

### 1.1 修改 `backend/app/services/stock_detail_service.py`：`get_fundamentals` 追加 pFcf 编排

在现有 same-day cache 短路（保留，命中含新字段直接返回）之后、原 payload 组装时，追加成员门控 + 现金流编排：

```python
# 成员门控（D106）：watchlist active OR trend pool 成员
stock = self.stocks.get_by_ticker(ticker)        # 已有（shares_float 已用）
is_member = (stock is not None and stock.is_active) or self._is_pool_member(ticker)

p_fcf_raw = p_fcf_adj = None
if is_member and market_cap is not None:
    try:
        cf = self.fmp.get_cash_flow_quarterly(ticker, limit=4)   # 复用 F218，raw dict list
    except httpx.HTTPError:
        cf = None                                                # fail-open：拉取失败 → 两字段 null
    if cf:
        p_fcf_raw, p_fcf_adj = _compute_p_fcf(cf, market_cap)

payload["pFcfRaw"] = p_fcf_raw   # 实际写入用 schema 字段名（见 §1.2）
payload["pFcfAdj"] = p_fcf_adj
```

新增**模块级纯函数**（同文件，无 db/无 IO，禁 import cockpit）：

```python
def _compute_p_fcf(quarters: list[dict], market_cap: float) -> tuple[float | None, float | None]:
    # 取最近 4 季；<4 季 → (None, None)
    # 每季解析：OCF（operatingCashFlow，缺则 netCashProvidedByOperatingActivities 回退）
    #           capex（capitalExpenditure，多为负，按符号直接加）
    #           SBC（stockBasedCompensation，缺 → 0）
    # 任一季 OCF 或 capex 缺 → 该指标整体不可算（None 传播）
    # fcf_ttm = Σ(OCF + capex);  fcf_adj = fcf_ttm − Σ SBC
    # p_fcf_raw = market_cap / fcf_ttm  if fcf_ttm > 0 else None
    # p_fcf_adj = market_cap / fcf_adj  if fcf_adj > 0 else None
    ...
```

新增私有方法 `_is_pool_member(ticker) -> bool`：`self.db.query(CockpitPoolCache.ticker).filter(CockpitPoolCache.ticker == ticker).first() is not None`（导入 **model** `app.models.cockpit_pool_cache`，**非** cockpit service；坐实待查-1）。

> 复用同文件已有 `_as_float` 解析现金流字段（容错 None 传播）。

### 1.2 修改 `backend/app/schemas/stock_detail.py`：`Fundamentals` +2 字段

```python
class Fundamentals(CamelModel):
    # ...既有字段全部保留不动...
    p_fcf_raw: float | None = None   # alias pFcfRaw
    p_fcf_adj: float | None = None   # alias pFcfAdj
```

> 不加 `sbcSensitiveFlag`（已砍）；不加 traceability（F220-a 已废）。

### 1.3 修改 `frontend/src/types/stockDetail.ts`：`Fundamentals` 接口 +2 可选字段

```ts
pFcfRaw?: number | null
pFcfAdj?: number | null
```

### 1.4 修改 `frontend/src/components/features/stock-detail/FundamentalsCard.tsx`：双版本 P/FCF 行

`buildMetrics` 右栏（或左栏）加两行，复用既有 `formatRatio` + `'—'` 兜底：
- `{ label: 'P/FCF', value: formatRatio(f?.pFcfRaw) }`
- `{ label: 'P/FCF(−SBC)', value: formatRatio(f?.pFcfAdj) }`

> 现有 6 指标（P/E·P/S·PEG·ROCE·FCF·Float）→ 8 指标。具体 left/right 分栏在 Generator 按视觉平衡定（2 栏各 4 行）；null → 既有 `'—'` 路径，无新状态分支。

### 1.5 修改 `backend/tests/conftest.py`：`FakeFMP` 增 `get_cash_flow_quarterly` 桩

测试基础设施：现有 `FakeFMP` 无此方法，成员编排路径会 AttributeError。加 `cash_flow_results: dict[str, list]` + `get_cash_flow_quarterly(symbol, limit)` 桩（同 `key_metrics_results` 风格）。**纯测试桩，非生产文件。**

### 1.6 修改 `backend/tests/test_stock_detail.py`：F220-b 用例

`_compute_p_fcf` 纯函数单测（直接 import）+ `get_fundamentals` 集成（门控 / fail-open / 双字段）。详见 §4。

### 1.7 明确排除（本 sprint 不做）

- **自洽红旗 `sbcSensitiveFlag`** → 砍掉，不实现
- **自算市值（Diluted×price）/ 当前价解析 / 季报股本拉取** → 用 FMP marketCap，不做
- **EPS 加速度 / 预期修正 / 时序表写入** → F220-d / F220-e（已 deprecated 的 c 不在内）
- **ADR 货币折算** → 不做（FMP marketCap 已内含正确货币，pFcf 比值无量纲）
- **fmp_client 任何改动** → 复用现有 `get_cash_flow_quarterly`

---

## 2. 预计修改文件（共 6 个）

| 文件路径 | 改动类型 | 说明 |
|---------|---------|------|
| `backend/app/services/stock_detail_service.py` | 修改 | `get_fundamentals` 成员门控 + 现金流编排 + `_compute_p_fcf` 纯函数 + `_is_pool_member`；fail-open |
| `backend/app/schemas/stock_detail.py` | 修改 | `Fundamentals` +`pFcfRaw`/`pFcfAdj` |
| `frontend/src/types/stockDetail.ts` | 修改 | `Fundamentals` 接口 +2 可选字段 |
| `frontend/src/components/features/stock-detail/FundamentalsCard.tsx` | 修改 | 双版本 P/FCF 行（2 栏各 4 行） |
| `backend/tests/conftest.py` | 修改 | `FakeFMP.get_cash_flow_quarterly` 桩（测试基础设施） |
| `backend/tests/test_stock_detail.py` | 修改 | `_compute_p_fcf` 单测 + 门控/fail-open/双字段集成 |

✅ **6 文件，6-file 上限内，无需例外授权。**

👤 用户确认文件清单 + §5 假设后，方可进入 Generator。

---

## 3. 文档同步（doc-first，Generator step 0 先于代码）

| 阶段 | 文档 | 改动 |
|------|------|------|
| **开发前** | API-CONTRACT.md §fundamentals | ① F220-b 字段块：`sbcSensitiveFlag` 标移除（红旗砍）；② `pFcfRaw/pFcfAdj` 市值口径从「自算 Diluted×price」改「FMP key-metrics-ttm marketCap」；③ 补成员门控（D106）+ FCF=Σ4季(OCF+capex)、Adj=−ΣSBC 口径说明 |
| **开发前** | DECISIONS.md §D105 | 修订/补记：F220-b 砍自洽红旗 + 市值改 FMP marketCap（自算口径前提随 normalizedPe 废弃而消失；FMP marketCap 极简且 ADR 货币正确）；D106 成员门控落地于 pFcf |
| **开发前** | DATA-MODEL.md §DailyPayloadCache | pFcf 两字段并入 fundamentals payload（Text JSON），无新表 —— 已有复用注记，至多补一句 |
| **开发后** | DECISIONS.md | Generator 期出现文档未覆盖的非显而易见决策（如 FMP OCF 字段名变体处置）→ 追加 D 记录 |

> ⚠️ 这是对 confirmed 系统设计文档的字段级修订，属 feature-dev 规则 2「改/增 API 先更新文档再动代码」范畴，由 Generator step 0 落地，不另起 system-design skill。

---

## 4. 可测试的完成标准

| # | 标准描述 | 测试层级 | 工具 |
|---|---------|---------|------|
| 1 | `_compute_p_fcf`：4 季正常数据 → pFcfRaw = marketCap/Σ(OCF+capex)、pFcfAdj = marketCap/(FCF−ΣSBC)，数值正确 | 单元 | pytest |
| 2 | `_compute_p_fcf`：capex 负号直接加（OCF=100, capex=−30 → FCF=70 贡献），不取绝对值不二次取反 | 单元 | pytest |
| 3 | `_compute_p_fcf`：FCF_ttm ≤ 0 → pFcfRaw=None；FCF−SBC ≤ 0 → pFcfAdj=None（互不影响） | 单元 | pytest |
| 4 | `_compute_p_fcf`：<4 季 → (None, None)；某季 OCF 或 capex 缺 → (None, None)；SBC 缺 → 按 0 计 | 单元 | pytest |
| 5 | `_compute_p_fcf`：OCF 用 `operatingCashFlow`，缺则回退 `netCashProvidedByOperatingActivities` | 单元 | pytest |
| 6 | `get_fundamentals` 成员门控：非 watchlist 非 pool ticker → pFcfRaw/pFcfAdj=None，不调用 `get_cash_flow_quarterly`，原始 TTM 指标照常 | 集成 | pytest + FakeFMP |
| 7 | `get_fundamentals` 成员（pool-only，非 watchlist）→ 走现金流编排，pFcf 字段有值 | 集成 | pytest + FakeFMP |
| 8 | `get_fundamentals` fail-open：成员但现金流拉取抛 HTTPError / 不足 4 季 → pFcf=None，endpoint 仍 200，原始 P/S/PEG/ROCE/FCF/marketCap 照常 | 集成 | pytest + FakeFMP |
| 9 | `get_fundamentals` 成员但 `market_cap` 为 None → pFcf=None（不除零），其余照常 | 集成 | pytest + FakeFMP |
| 10 | `GET /api/stocks/{ticker}/fundamentals` 响应 camelCase 含 `pFcfRaw`/`pFcfAdj`；schema 校验通过 | 集成 | pytest + TestClient |
| 11 | 前端 FundamentalsCard 渲染 P/FCF + P/FCF(−SBC) 两行；null → `'—'`；无 console.error | E2E | preview 工具 |
| 12 | 全量后端 pytest + 前端 vitest 无新增失败（对比当前 baseline） | 回归 | pytest / vitest |

> 验收期（acceptance，非本 sprint）：DUOL live 实测 pFcfAdj 量级合理（原设计标 [20,22]×，当前价已非设计时点，量级核对为主不卡死区间）；需 DUOL ∈ watchlist 或 pool。

---

## 5. 关键假设（A-1 假设外显）

| # | 假设 | 来源 | 需确认 |
|---|------|------|--------|
| 1 | FCF = Σ最近4季(operatingCashFlow + capitalExpenditure)，capex 按符号直接加（多为负）；FCF−SBC = FCF − Σ stockBasedCompensation | 设计文档 + FMP 标准字段（待查-2） | ⚠️ 口径已随合约确认；FMP 字段名 Generator 对真实响应核对，缺失走 None 传播（fail-open，不阻断） |
| 2 | P/FCF 市值分子 = FMP key-metrics-ttm marketCap（已在 get_fundamentals 拉取） | 用户 2026-06-11 拍板 | ✅ 已确认 |
| 3 | sbcSensitiveFlag 砍掉，不进 schema/契约 | 用户 2026-06-11 拍板 | ✅ 已确认 |
| 4 | pFcf 成员门控 watchlist(active)∪pool；pool 判断直读 CockpitPoolCache model（不新建 repository、不 import cockpit service） | 用户 2026-06-11 拍板 + D106 | ✅ 已确认 |
| 5 | `_compute_p_fcf` 内联于 stock_detail_service.py（不新建独立模块）—— 保 6 文件预算 + 极简（compute ~15 行） | 极简 + 6-file 预算 | ⬜ 否 |
| 6 | DUOL 实测验收需 DUOL ∈ watchlist 或 pool；不在则验收前手动加入 | 推断 | ⬜ 否（验收期处理） |

> 三项核心决策（假设 2/3/4）已于 A-1 前置 AskUserQuestion 确认。假设 1 的 FMP 字段名是运行期事实（fail-open 兜底），假设 5 是极简默认，均随合约一并 ack。

---

## 6. Evaluator 自检清单

开发完成后，Evaluator 模式逐条检查：

- [ ] `cd backend && pytest tests/test_stock_detail.py -v` 全通过（`_compute_p_fcf` 单测 + 门控/fail-open 集成）
- [ ] `cd backend && pytest`（全量回归）无新增失败（对比当前 baseline）
- [ ] 前端 `pnpm test`（vitest）无新增失败
- [ ] `_compute_p_fcf` 纯函数零 import db/httpx/cockpit；`_is_pool_member` 仅 import model（非 cockpit service）
- [ ] API 响应 camelCase 符合 API-CONTRACT.md（pFcfRaw / pFcfAdj）
- [ ] capex 符号处理正确（直接加，不取绝对值）—— 单测断言守住
- [ ] 降级路径：<4 季 / FCF≤0 / FCF−SBC≤0 / 拉取失败 / 非成员 / marketCap 缺 全部 → null 且 endpoint 200，**绝不抛错拖垮 widget**
- [ ] doc-first 三文档（API-CONTRACT / DECISIONS / DATA-MODEL）已在 code 前修订
- [ ] sbcSensitiveFlag 确实未出现在任何代码/schema/类型（grep 校验「砍掉」落实）
- [ ] 无硬编码魔法值散落；无 print / 调试日志残留
- [ ] 实现范围严格等于 §1（无红旗 / 无自算市值 / 无 fmp_client 改动 / 无新表）
- [ ] 修改文件严格等于 §2 清单（6 文件，无新增无遗漏）
- [ ] 非显而易见决策（如 OCF 字段名变体处置）已追加 DECISIONS.md
- [ ] 通过 → `F220.sub_sprints['F220-b']` → needs_review，调 consistency-check (C1/C4/C5)

---

## 7. 完成后的衔接

- F220-b `needs_review` → acceptance（DUOL live 实测 pFcf 量级）→ done
- 之后 F220-d（EPS 加速度，⚠️ 原依赖正常化 EPS 序列已废，重启时须改用 GAAP EPS 或一并评估）/ F220-e（预期修正方向，独立，027 表 + weekly cron 保留）
- F220 整体 status 由 consistency-check C1 invariant 决定（所有存活 sub-sprint done 才升）—— 注意 a1/a2/c 为 deprecated 不计入存活集

---

👤 **请确认：① 6 文件清单；② §5 假设（核心 2/3/4 已确认，余 1/5/6 随合约 ack）；③ §4 完成标准。确认后我执行 A-1 收尾（落盘 confirmed + features.json + SESSION-HANDOFF + commit），然后按 skill 铁律停在本 session，Generator 开发在新 session 进行。**
