---
status: confirmed
drafted_at: 2026-05-21
confirmed_at: 2026-05-21
sprint: F219-a
parent_feature: F219
file_count_authorization: 8-file exception (user-approved 2026-05-21, 与 F217-c2c / F218-d7b 同先例)
np_decisions: NP-1/2/3/4/5 全部 A（用户 2026-05-21 一次性按推荐确认）
---

# F219-a Sprint Contract — MACD Divergence 后端切片（indicator + persist + endpoint schema）

> 生成：2026-05-21 | 状态：✅ 已确认 → 进入 Generator（下一 session）
> Feature：[F219](docs/需求/features.json) Cockpit Phase E — MACD Divergence 早衰报警（最小化方案）
> Sub-sprint：F219-a（Phase E 2 sub-sprint 第 1 个；后端闭环）
> 前置：F215 + F217 done（volume gate + CAPITULATION 严格门已上线，本切片只增字段、不动 ready gate / 7-AND gate / EXTENDED 判定）
> 下游：F219-b（前端切片，PositionListWidget bearish 标识 + SetupMonitorWidget bullish chip 展示，F219-a done 后开启）

> 引用文档：
> - [DATA-MODEL.md §SetupSnapshot 426-482](docs/系统设计/DATA-MODEL.md) — 新增 `macd_divergence` 列定义位置
> - [API-CONTRACT.md §GET /api/cockpit/setup-monitor 1130-1199](docs/系统设计/API-CONTRACT.md) — items[] 新增 `macdDivergence` 字段位置
> - [API-CONTRACT.md §GET /api/cockpit/positions](docs/系统设计/API-CONTRACT.md) — items[] 新增 `macdDivergence` 字段位置
> - [_indicators.py](backend/app/services/cockpit/_indicators.py) — `compute_wilder_atr` 同款 pure function 风格样板
> - [setup_service.py](backend/app/services/cockpit/setup_service.py) — nightly compute pipeline 接入点
> - [F215-a-contract.md](docs/开发/sprint-contracts/F215-a-contract.md) — 后端 indicator + schema 扩展同款样板（本合同结构对齐）
> - [DECISIONS.md](docs/系统设计/DECISIONS.md) — 完成后追加 D098 + D099（见 §文档同步）

---

## 0. 背景与定位

Ross Cameron 慢交易方法移植讨论的产出（2026-05-21 session）：MACD 的 line/signal 交叉、0 轴判定、histogram 加速在本项目已有的 `trend_score` / `vol_zscore` / `weekly_stage` 体系下**全部冗余**。**唯一独立有效的用法是 divergence（背离）**：

- **Bearish divergence**（价 20 日新高、MACD 不新高）→ 持仓早衰报警，比 EXTENDED 触发早 2–3 周
- **Bullish divergence**（价 20 日新低、MACD 不新低）→ CAPITULATION 候选的**辅助证据**，**不进 7-AND 门**

F219-a 实现"计算 + 持久化 + 经由现有 2 个 endpoint 暴露"的后端闭环，不动 ready gate、不动 CockpitChart overlay、不接入 AI / DecisionPanel chip 区。

---

## 1. 实现范围

### 1.1 MACD 配置常量（`cockpit_params.py` 新增 `MACD` 类）

```python
class MACD:
    FAST: int = 12               # 短期 EMA 周期（Cameron 标准，不开放调参）
    SLOW: int = 26               # 长期 EMA 周期
    SIGNAL: int = 9              # signal line EMA 周期（本切片不消费，仅 line 序列）
    DIVERGENCE_LOOKBACK: int = 20  # 价 / MACD 新极值的回看窗口（与 SETUP.EXTENDED 同量级）
    MIN_BARS_REQUIRED: int = 50    # SLOW + SIGNAL + LOOKBACK 上下界保护
```

### 1.2 Pure indicator 函数（`_indicators.py` 追加 2 个）

```python
def compute_macd_series(closes: list[float], fast: int, slow: int) -> list[float | None]:
    """MACD line = EMA(closes, fast) - EMA(closes, slow)。
    复用与 chart_service `_compute_ema_series` 相同 α=2/(period+1)、seed=SMA(period) 算法。
    返回与 closes 同长度的 list；前 (slow-1) 位无效填 None。
    """
    ...

def detect_macd_divergence(
    closes: list[float],
    macd_line: list[float | None],
    lookback: int,
) -> str | None:
    """检测最近 lookback 个交易日的 price-vs-MACD 背离。
    规则：
      - bearish: closes[-1] == max(closes[-lookback:]) AND macd_line[-1] < max(macd_line[-lookback:])
      - bullish: closes[-1] == min(closes[-lookback:]) AND macd_line[-1] > min(macd_line[-lookback:])
      - 同时满足（病态）或都不满足 → None
      - macd_line 末尾任何位置为 None（短历史）→ None
    返回 'bearish' / 'bullish' / None。
    """
    ...
```

### 1.3 DB schema（`db/models.py` + alembic 025）

`SetupSnapshot` 新增 1 列：

```python
macd_divergence = Column(String(8), nullable=True)  # 'bearish' / 'bullish' / None
```

alembic `025_f219a_setup_macd_divergence.py`：upgrade 加列 nullable，downgrade 删列；不回填（短历史一段时间内 NULL 是预期）。

### 1.4 setup_service.py 集成

在 `_compute_setup_snapshot(ticker, bars, ...)` 主流程末尾（trend_score / quality / ready_signal 都算完之后）追加：

```python
macd_line = compute_macd_series(closes, MACD.FAST, MACD.SLOW)
macd_divergence = detect_macd_divergence(closes, macd_line, MACD.DIVERGENCE_LOOKBACK) \
    if len(closes) >= MACD.MIN_BARS_REQUIRED else None
snapshot.macd_divergence = macd_divergence
```

**不影响 ready_signal 8-AND gate；不影响 _classify_setup_type 优先级链**（保持 BROKEN → EXTENDED → EARNINGS_DRIFT → CAPITULATION → BREAKOUT → RECLAIM → NONE）。

### 1.5 endpoint schema 扩展（不新增 endpoint）

- `schemas/cockpit/setup.py` `SetupMonitorItem` 新增 `macd_divergence: str | None`，序列化为 `macdDivergence`
- `schemas/cockpit/position.py` `PositionItem` 新增 `macd_divergence: str | None`，序列化为 `macdDivergence`
- `position_service.py` 在现有 setup_snapshot join 中加一列读取，写入 PositionItem

### 1.6 明确排除（本 sprint 不做）

- 任何前端文件（widget / API client / token）— 全部归 F219-b
- DecisionPanel / CockpitChart overlay / AI Contradictions 接入 — 永不做
- MACD histogram、signal line、0 轴判定的任何消费 — 永不做
- swing-pivot 版本的 divergence 检测算法 — 不做，仅使用 lookback 内"新极值 vs 反向极值"的简单规则
- `?macd_fast=...` 之类的查询参数 — 不开放
- 回填历史 `macd_divergence`（旧行保持 NULL 直到下次 cron 自然填充）

---

## 2. 预计修改文件（共 8 个）

| 文件路径 | 改动类型 | 说明 |
|---------|---------|------|
| `backend/app/services/cockpit/cockpit_params.py` | 修改 | 新增 `MACD` 类（FAST=12 / SLOW=26 / SIGNAL=9 / DIVERGENCE_LOOKBACK=20 / MIN_BARS_REQUIRED=50） |
| `backend/app/services/cockpit/_indicators.py` | 修改 | 追加 `compute_macd_series(closes, fast, slow)` 与 `detect_macd_divergence(closes, macd_line, lookback)` 两个 pure function；复用现 EMA 思路（α=2/(p+1)，seed=SMA(p)） |
| `backend/app/services/cockpit/setup_service.py` | 修改 | `_compute_setup_snapshot` 末尾追加 macd_divergence 计算与持久化；不动 setup_type 分类链与 ready_signal 8-AND |
| `backend/app/services/cockpit/position_service.py` | 修改 | 现有 setup_snapshot join 增加读取 `macd_divergence`，落到 PositionItem 字段 |
| `backend/app/db/models.py` | 修改 | `SetupSnapshot` 增加 `macd_divergence = Column(String(8), nullable=True)` |
| `backend/alembic/versions/025_f219a_setup_macd_divergence.py` | 新增 | upgrade 加 nullable 列；downgrade 删列；不回填 |
| `backend/app/schemas/cockpit/setup.py` | 修改 | `SetupMonitorItem` 新增 `macd_divergence: str \| None`（输出 `macdDivergence`） |
| `backend/app/schemas/cockpit/position.py` | 修改 | `PositionItem` 新增 `macd_divergence: str \| None`（输出 `macdDivergence`） |

⚠️ **8 文件**：超出 6-file 默认上限。请求 8-file 例外，先例 F217-c2c（10 file）/ F218-d7b（10 file）。

👤 用户确认文件清单 + 例外授权后，方可进入开发。

---

## 3. 文档同步（开发前/后必做）

| 阶段 | 文档 | 改动 |
|------|------|------|
| **开发前** | DATA-MODEL.md §SetupSnapshot 字段表 | 在 `weekly_stage` 行下方插入 `macd_divergence` 行：`String(8) \| ❌ \| 价 vs MACD 20 日背离分类：'bearish'（价新高 MACD 不新高）/ 'bullish'（价新低 MACD 不新低）/ NULL（无背离或 bars<50）。不参与 ready_signal 8-AND gate（F219 / D098）` |
| **开发前** | DATA-MODEL.md §SetupSnapshot SQLAlchemy 模型段 876-899 | 在 `suggested_action` 行后追加 `macd_divergence = Column(String(8), nullable=True)` |
| **开发前** | API-CONTRACT.md §GET /api/cockpit/setup-monitor 1130-1199 | items[] 示例 JSON 在 `weeklyStage` 下方追加 `"macdDivergence": "bearish"`；字段说明区追加：`macdDivergence: 'bearish' \| 'bullish' \| null；price/MACD 20 日背离（F219 / D098）。不进 readySignal 8-AND` |
| **开发前** | API-CONTRACT.md §GET /api/cockpit/positions | items[] 示例 + 字段说明同步追加 `macdDivergence` |
| **开发后** | DECISIONS.md | 追加 **D098**：MACD 体系裁剪到 divergence 一项保留作为持仓早衰报警；line/signal 交叉、0 轴、histogram 在 trend_score / vol_zscore / weekly_stage 体系下冗余，不实现 |
| **开发后** | DECISIONS.md | 追加 **D099**：divergence 检测使用"lookback=20 内新极值 vs 反向极值"简单规则，不采用 swing-pivot；MACD 参数 12/26/9 硬编码不开放调参 |

---

## 4. 可测试的完成标准

| # | 标准描述 | 测试层级 | 工具 |
|---|---------|---------|------|
| 1 | `compute_macd_series(closes, 12, 26)` 对一个手算 fixture（100 个 close 单调递增 / 单调递减 / 正弦波）输出对齐到 1e-6 精度；前 25 位为 None | 单元 | pytest |
| 2 | `compute_macd_series` 对 `len(closes) < SLOW` 返回全 None list | 单元 | pytest |
| 3 | `detect_macd_divergence`：构造 closes 末位为 20 日新高 + macd_line 末位非 20 日新高 → 返回 `'bearish'` | 单元 | pytest |
| 4 | `detect_macd_divergence`：构造 closes 末位为 20 日新低 + macd_line 末位非 20 日新低 → 返回 `'bullish'` | 单元 | pytest |
| 5 | `detect_macd_divergence`：closes 末位既非 lookback 内新高也非新低 → 返回 `None` | 单元 | pytest |
| 6 | `detect_macd_divergence`：macd_line 末位为 None（短历史）→ 返回 `None` | 单元 | pytest |
| 7 | `detect_macd_divergence`：同时满足 bearish + bullish 的病态构造（极短 lookback + 平坦序列）→ 返回 `None`，不抛异常 | 单元 | pytest |
| 8 | `setup_service._compute_setup_snapshot` 在 bars>=50 时写入 `macd_divergence` 字段；bars<50 时写入 `None` | 单元 | pytest（mock bars） |
| 9 | alembic upgrade `025` 后 `setup_snapshots` 表含 `macd_divergence` 列；downgrade 后列消失；upgrade→downgrade→upgrade 三段干净 | 集成 | pytest（alembic test fixture） |
| 10 | `GET /api/cockpit/setup-monitor` 响应 items[] 每行含 `macdDivergence` 字段，类型 `string \| null` | 集成 | pytest httpx + TestClient |
| 11 | `GET /api/cockpit/positions` 响应 items[] 每行含 `macdDivergence` 字段 | 集成 | pytest httpx + TestClient |
| 12 | `ready_signal` 计算逻辑零变化：用一组 `ready=true` fixture 跑前后对比，所有 ready 标的不变 | 回归 | pytest |
| 13 | 全量后端 pytest 套件无新增失败 | 回归 | pytest |

---

## 5. 已确认的协商点（2026-05-21）

| # | 协商点 | 决定 |
|---|--------|------|
| **NP-1** | divergence 检测算法 | **A**：lookback=20 内 "末位 == 极值 vs 反向" 简单规则（不采用 swing-pivot） |
| **NP-2** | 0 轴过滤 | **A**：不启用；bearish/bullish 不强制 MACD 正负 |
| **NP-3** | 病态兜底 | **A**：同时命中 / macd None → 一律返回 `None`，不抛异常 |
| **NP-4** | `position_service` 暴露时机 | **A**：本 sprint 一起暴露 PositionItem.macdDivergence（避免 F219-b 既动前端又动后端 schema） |
| **NP-5** | cron 阶段位置 | **A**：setup_service 内同 batch（nightly 22:10 UTC 与 trend_score / quality 同事务一次算完） |
| **文件清单** | 8-file 例外授权 | **批准**（与 F217-c2c / F218-d7b 同先例） |

---

## 6. Evaluator 自检清单

开发完成后，Evaluator 模式逐条检查：

- [ ] `cd backend && pytest tests/cockpit/test_indicators_macd.py -v` 全通过（新增 7 个单元用例）
- [ ] `cd backend && pytest tests/cockpit/test_setup_service.py -v` 含 macd_divergence 写入断言
- [ ] `cd backend && pytest tests/cockpit/test_setup_router.py tests/cockpit/test_position_router.py -v` 含 `macdDivergence` 字段断言
- [ ] `cd backend && alembic upgrade head && alembic downgrade -1 && alembic upgrade head` 三段干净
- [ ] `cd backend && pytest` 全量回归无新增失败
- [ ] ready_signal 行为零变化（验收标准 #12 通过）
- [ ] DATA-MODEL.md / API-CONTRACT.md 已按 §3 完成同步（开发前完成）
- [ ] DECISIONS.md 追加 D098 + D099（开发后）
- [ ] 无硬编码 MACD 参数遗漏（全部从 `MACD` 类读取）
- [ ] 无 `print` / 调试日志残留
- [ ] ruff / mypy 通过（如项目 lint pipeline 包含）
- [ ] features.json `F219.sub_sprints['F219-a']` 从 `planned` → `done`（Evaluator 通过后）

---

## 7. 完成后的衔接

- F219-a `done` → `consistency-check` C1 触发 → features.json `F219.sub_sprints['F219-a']` 升 `done`
- F219-b 进入 contract 协商：PositionListWidget bearish ⚠️ 标识 + tooltip + SetupMonitorWidget CAPITULATION 行 bullish chip + 2 个 API client 类型同步（预计 4 文件，6-file 内）
- F219 整体 needs_review 等待 acceptance（F219-b done 后）

---

👤 **本 Contract 已于 2026-05-21 用户确认（按推荐方案全 A + 8-file 例外授权）。下一 session 进入 Generator 模式开始开发。**
