# Sprint Contract：F205-b FMP 增量 + Pool 计算 helpers（trend 子集）

> 日期：2026-04-27 | 状态：草案
> 父 Feature：F205 Pool Builder Widget（v1.9 Cockpit P1）
> 前置 Sprint：F205-a ✅ done（universe 表已加 sector/industry/last_price/last_volume）
> 引用文档：
>   - `docs/系统设计/API-CONTRACT.md` §GET /api/cockpit/pool（消费方，F205-c 实现）
>   - `docs/系统设计/DATA-MODEL.md` §SetupSnapshot / §MarketScanUniverse
>   - `docs/系统设计/DECISIONS.md` D034（FMP 主数据源）/ D044（速率限制）/ D078（universe 持久化字段）
>   - `backend/app/services/cockpit/setup_service.py`（已内联 RS 计算逻辑，本 sprint **不重构**）

---

## 0. Sprint 定位说明（避免误读）

F205 拆 4 子 sprint：
- F205-a ✅：universe 表字段扩展（已完成）
- **F205-b（本 sprint）**：纯计算 helper + 1 个 FMP 客户端方法增量。**不**写 PoolService，**不**写 router，**不**做编排，**不**碰前端
- F205-c：PoolService（编排 + 缓存 + 漏斗组装）+ `GET /api/cockpit/pool` router
- F205-d：前端 PoolBuilderWidget

> ⚠️ F205-a 合约里"与下游 sub-sprint 的接口约定"段把 F205-b 描述为 "pool service" — 那是写 F205-a 时尚未细分的措辞，以**本合约和 features.json sub_sprints 字段为准**：F205-b 仅交付 building blocks，pool 漏斗的组装在 F205-c。

本 sprint 的关键约束："**helpers 必须是种群无关（population-agnostic）的纯函数**"。setup_service.py 现有 RS 计算是 watchlist 范围（~20 ticker），pool 漏斗的 RS 范围是 trend 子集（数百 ticker）— 同一份逻辑两套调用方，本 sprint 提供可被两边复用的纯函数版本，但**不动 setup_service.py**（避免 F202-a 回归风险，dedup 推到 F205-c 之后或独立技术债 sprint）。

---

## 1. 本次实现范围

**包含（4 项）**：

### 1.1 FMP 客户端增量：`get_financial_growth(symbol)`

- 新增方法在 `backend/app/external/fmp_client.py`
- 调用 FMP `/stable/financial-growth?symbol={symbol}&period=annual&limit=1`
- 返回 `dict | None`（None 表示未找到 / 网络异常 / 空数组）
- 解析最新一年的 `revenueGrowth`（FMP 返回 decimal，如 0.0202 表 2.02%），转为 percent（×100）后塞回 dict 暴露
- 共享既有 token bucket + 6-concurrency semaphore（D044），不要新建限流器
- 429 自动退避 + Retry-After 解析复用现有 `_request_with_retry`（如已抽出），无则直接复用现有调用模式
- ⚠️ 不实现批量版本（`get_financial_growth_batch`）— pool 漏斗在 F205-c 的 PoolService 里串行/并发调用本方法，缓存策略也由 F205-c 决定

### 1.2 新建 `backend/app/services/cockpit/pool_helpers.py`：5 个纯函数

| 函数 | 签名 | 职责 |
|------|------|------|
| `compute_return_ratio_250d(closes, spy_closes)` | `(list[float], list[float]) -> float \| None` | 给定 ticker 250 日 close + SPY 250 日 close，返回 `(stock_return / spy_return)`；任一序列长度不足或 spy_return 接近 0 → None |
| `compute_rs_percentile_map(ratio_by_ticker)` | `(dict[str, float \| None]) -> dict[str, float]` | 给定 {ticker: ratio}（None 视为底部），返回 {ticker: 百分位 0-100}；空字典返回空字典；ties 用 mid-rank（与 setup_service 当前 `_percentile_rank` 行为一致） |
| `compute_distance_to_50ma_pct(close, ma50)` | `(float, float \| None) -> float \| None` | `(close - ma50) / ma50 * 100`，保留 4 位小数；ma50 None / 0 → None；不抛异常 |
| `extract_revenue_growth_yoy_pct(financial_growth_payload)` | `(dict \| None) -> float \| None` | 从 `get_financial_growth` 返回值中读 `revenueGrowth` 字段并 ×100；payload None / 字段缺 / 类型异常 → None |
| `passes_fundamental_sanity(growth_yoy_pct, threshold_pct)` | `(float \| None, float) -> bool` | growth_yoy_pct None → 默认放行（见决策段）；否则 `growth_yoy_pct >= threshold_pct` |

**所有函数必须**：
- 纯函数：无 IO、无 DB、无 logger 依赖
- 完整 type hint
- 1-2 行 docstring 说明 *为什么* 边界条件这样处理（如 `ma50=0` 怎么办、`spy_return≈0` 怎么办），不写 *是什么*（"乘以 100 转 percent" 不写）
- 容错：所有可预见的 None / 0 / 空序列必须 graceful 降级（返回 None / False / 空字典），**不**抛异常给调用方

### 1.3 决策落档

在 `docs/系统设计/DECISIONS.md` 追加 **D079**：
- F205-b 引入 FMP `/financial-growth?period=annual&limit=1` 作为 revenue YoY 来源
- RS percentile 算法：`stock_return_250d / spy_return_250d` → percentile rank within population；ties = mid-rank
- `passes_fundamental_sanity`：growth 数据缺失（None） → 默认放行（fail-open），**不**因 FMP 数据缺失淘汰整个 ticker
- helpers 暂不重构 setup_service.py 的内联 RS 逻辑（双实现存在但行为一致），dedup 列入技术债，下游 sprint 视情况合并

### 1.4 测试覆盖（详见第 3 节）

---

**明确排除（本次不做）**：

- ❌ 不写 `PoolService` / `pool_service.py`（F205-c）
- ❌ 不写 `routers/cockpit/pool.py`（F205-c）
- ❌ 不写 `schemas/cockpit/pool.py`（F205-c）
- ❌ 不动 `setup_service.py`（避免 F202-a 回归）
- ❌ 不动 `market_scanner_service.py`（F106 scanner 不变）
- ❌ 不新建数据库表 / 迁移脚本（trend 子集动态从 `market_breakout_scans` SELECT，缓存在 F205-c）
- ❌ 不写 trend-subset materializer（"读 F106 最新 scan + 拉 250d closes" 这一步是编排层，归 F205-c）
- ❌ 不写批量 FMP 拉取 / 并发调度（F205-c 决定）
- ❌ 不动前端
- ❌ 不暴露任何 HTTP endpoint
- ❌ 不修改 `cockpit_params.py` 的 RS / fundamental 阈值（沿用 F202-a 设定 + 新增 pool 专用阈值留给 F205-c）

---

## 2. 预计修改文件

| # | 文件路径 | 改动类型 | 说明 |
|---|---------|---------|------|
| 1 | `backend/app/external/fmp_client.py` | 修改 | 新增 `get_financial_growth(symbol) -> dict \| None` 方法；复用现有 token bucket + retry |
| 2 | `backend/app/services/cockpit/pool_helpers.py` | 新建 | 5 个纯函数（见 §1.2）；模块顶部 docstring 说明定位（"F205-b: pool funnel 计算 helpers，纯函数，由 F205-c 编排"） |
| 3 | `backend/tests/test_pool_helpers_f205b.py` | 新建 | 单元测试覆盖 §1.2 全部 5 个函数 + 全部边界条件（详见 §3） |
| 4 | `backend/tests/test_fmp_client.py` | 修改 | 新增 `test_get_financial_growth_*` 用例（成功 / 空数组 / 网络异常 / 字段缺失） |

**附加文档更新**（不计入 6 文件硬上限）：
- `docs/系统设计/DECISIONS.md` — 追加 D079
- `docs/系统设计/API-CONTRACT.md` — **不动**（FMP 内部方法不暴露在公开 API；如需备查，由 F205-c 在 pool endpoint 文档里反向引用）

文件计数：**4/6**（远在硬上限内，无需拆分）

---

## 3. 可测试的完成标准

| # | 标准描述 | 测试层级 | 工具 |
|---|---------|---------|------|
| 1 | `get_financial_growth("AAPL")` mock FMP 返回标准 payload `[{"symbol":"AAPL","date":"2024-09-30","revenueGrowth":0.0202}]` → 返回 dict 且 `revenueGrowth=0.0202` | 单元 | pytest + httpx mock |
| 2 | `get_financial_growth("XYZ")` mock FMP 返回 `[]` → 返回 None | 单元 | pytest + httpx mock |
| 3 | `get_financial_growth("AAPL")` mock FMP 抛 HTTPError / 超时 → 返回 None，**不**向上抛异常（与现有 ratios-ttm 错误处理风格一致） | 单元 | pytest + httpx mock |
| 4 | `get_financial_growth` 触发 429 → 自动退避 + Retry-After 解析 + 重试通过（沿用现有 retry 装饰器） | 单元 | pytest + httpx mock |
| 5 | `compute_return_ratio_250d([100]*250, [100]*250)` → 0.0 / 0.0 = None（spy_return≈0） | 单元 | pytest |
| 6 | `compute_return_ratio_250d` ticker 250 日 +20%、SPY 250 日 +10% → ≈ 2.0 | 单元 | pytest |
| 7 | `compute_return_ratio_250d` 任一序列长度 < 250 → None | 单元 | pytest |
| 8 | `compute_rs_percentile_map({"A":1.0, "B":2.0, "C":3.0})` → `A=16.67, B=50.0, C=83.33`（mid-rank 百分位，与 setup_service `_percentile_rank` 同公式） | 单元 | pytest |
| 9 | `compute_rs_percentile_map({"A":1.0, "B":1.0, "C":2.0})` ties 用 mid-rank → `A=B=33.33, C=83.33` | 单元 | pytest |
| 10 | `compute_rs_percentile_map({})` → `{}` | 单元 | pytest |
| 11 | `compute_rs_percentile_map({"A":None, "B":1.0})` → A 视为底部（最小值），返回值 ∈ [0,100] 不抛异常 | 单元 | pytest |
| 12 | `compute_distance_to_50ma_pct(110, 100)` → 10.0；`compute_distance_to_50ma_pct(95, 100)` → -5.0 | 单元 | pytest |
| 13 | `compute_distance_to_50ma_pct(100, None)` / `compute_distance_to_50ma_pct(100, 0)` → None | 单元 | pytest |
| 14 | `extract_revenue_growth_yoy_pct({"revenueGrowth":0.0202})` → 2.02 | 单元 | pytest |
| 15 | `extract_revenue_growth_yoy_pct({"revenueGrowth":"N/A"})` / `{"revenueGrowth":None}` / `{}` / `None` → None（容错） | 单元 | pytest |
| 16 | `passes_fundamental_sanity(15.0, 10.0)` → True；`passes_fundamental_sanity(8.0, 10.0)` → False；`passes_fundamental_sanity(None, 10.0)` → True（fail-open，决策见 D079） | 单元 | pytest |
| 17 | `pool_helpers.py` 模块**无** SQLAlchemy / Session / Repo / Logger import；`grep "from app\." pool_helpers.py` 输出为空（pure module 验证） | 静态 | grep / 人工 |
| 18 | 全量回归：`pytest backend/` 总数 = 758 + 新增用例数，无新失败、无原失败 | 回归 | pytest |

---

## 4. Evaluator 自检清单

开发完成后，Evaluator 模式逐条检查：

### 功能正确性
- [ ] `pytest backend/tests/test_pool_helpers_f205b.py` 全部通过
- [ ] `pytest backend/tests/test_fmp_client.py` 全部通过（含新增用例）
- [ ] 全量回归 `pytest backend/` 通过；758 → 758 + N（N = 新增用例数）；**无新失败**
- [ ] FMP 调用错误（HTTPError / 超时 / 429）下 `get_financial_growth` 返回 None，不抛异常给调用方
- [ ] 5 个 helper 在所有边界（None / 空序列 / 长度不足 / 0 / 字符串） 下不抛异常

### 设计纯净度
- [ ] `pool_helpers.py` 不 import 任何 `app.*` 模块（除 `from __future__ import annotations`）
- [ ] `pool_helpers.py` 不 import `logging` / `Session` / `Repository` / `requests` / `httpx`
- [ ] 5 个 helper 全部无副作用（不写文件 / 不打日志 / 不改全局状态）
- [ ] `_compute_return` / `_percentile_rank` 在 setup_service 中**未被修改**（diff 验证 setup_service.py 仅在 import 处或完全不动）

### 命名 / 文档规范
- [ ] 函数名 snake_case，与 §1.2 表格一致
- [ ] 5 个函数全部完整 type hint（参数 + 返回值）
- [ ] 每个函数 1-2 行 docstring，说明 *为什么* 容错而非 *是什么*
- [ ] FMP 方法 `get_financial_growth` docstring 注明 D079 引用 + period=annual 选择理由

### 决策记录
- [ ] DECISIONS.md 已追加 D079（FMP financial-growth；RS 算法；fail-open；不重构 setup_service 的双实现）
- [ ] D079 中明确"双实现是已知技术债，dedup 不在本 sprint 范围"

### 代码质量
- [ ] Lint 通过（项目已配置的 linter）
- [ ] 无 print / pdb / 调试代码
- [ ] 无未引用 import / 死代码
- [ ] 无硬编码魔法值（百分位常数、RS 阈值通过参数传入而非函数内写死）

### 回归
- [ ] `test_setup_service.py` / `test_setup_*.py` 全部通过（确认未误改 setup_service.py 内联逻辑）
- [ ] `test_market_scanner_service.py` 通过（确认未误改 F106）

---

## 5. 与下游 sub-sprint 的接口约定（仅备查）

F205-c（PoolService）将这样使用本 sprint 交付物：

```python
from app.services.cockpit.pool_helpers import (
    compute_return_ratio_250d,
    compute_rs_percentile_map,
    compute_distance_to_50ma_pct,
    extract_revenue_growth_yoy_pct,
    passes_fundamental_sanity,
)
from app.external.fmp_client import FmpClient

# F205-c 内伪代码：
trend_tickers = breakout_repo.get_latest_scan_tickers()  # F106 hits
spy_closes = market_index_repo.get_spy_closes(days=250)
ratios = {
    t: compute_return_ratio_250d(get_closes(t), spy_closes)
    for t in trend_tickers
}
rs_map = compute_rs_percentile_map(ratios)
# rs_map[ticker] -> percentile, 在 trend 子集内 rank
```

F205-c 负责：缓存（DailyPayloadCache 或新表）、并发调度（FMP rate-limit-aware）、漏斗组装、错误隔离日志。

F205-d（前端）：消费 F205-c 的 `GET /api/cockpit/pool` JSON，本 sprint 与前端零交互。

---

## 6. 风险与权衡（备案）

| 风险 | 缓解 |
|------|------|
| RS 双实现（setup_service 内联 + pool_helpers）行为漂移 | D079 明确：本 sprint 公式必须与 setup_service 当前 `_percentile_rank` / `_compute_return` 完全一致；测试用例 #8 #9 用相同输入对比两套实现的输出（在 test_pool_helpers 中调用 setup_service 私有函数做 reference 对比） |
| FMP `/financial-growth` 字段名漂移（`revenueGrowth` 重命名） | 测试 #15 覆盖字段缺失场景 → fail-open；监控由 F205-c PoolService 加 SystemLog WARN 计数（不在本 sprint） |
| `get_financial_growth` 在 pool 漏斗里被 N×100 调用（每次刷新拉 trend 子集所有 ticker） | 本 sprint 不解决；F205-c 加缓存层（24h TTL，参考 D055 DailyPayloadCache 模式） |
| pool_helpers 与 setup_service 重复代码增加维护成本 | 已识别为技术债，列在 D079；建议在 F205-c 完成且 pool 漏斗稳定后开 F205-x 重构 sprint |

---

👤 用户确认本 Contract 后，feature-dev skill 将：
1. 更新 `features.json`：F205-b → `contract_agreed`；`active_sub_sprint` 保持 `F205-b`；写入 `estimated_files_changed` 列表
2. 追加 `claude-progress.txt`（Contract 协商完成记录）
3. 生成 `SESSION-HANDOFF.md`（含 Contract 摘要 + 开发顺序 + 下 session 恢复指令）
4. **强制结束 session**，建议 Sonnet 新 session 进入 Generator 模式
