# Sprint Contract：F215-b — Volume Accumulation 三件套（z-score / OBV / U-D ratio）+ BREAKOUT 吸筹门槛

> 日期：2026-05-13 | 状态：🟡 待用户确认协商点
> 引用文档：
>   features.json `F215.sub_sprints.F215-b`（design_needed → contract_agreed）
>   API-CONTRACT.md §GET /api/cockpit/setup（items[] 新增字段）
>   DATA-MODEL.md §Entity: SetupSnapshot（新增 3 列）
>   DECISIONS.md（追加 D087 / D088 / D089）
>   F215-a 已完成可作为模式参照：docs/开发/sprint-contracts/F215-a-contract.md
>   完整改善计划：/Users/wonderer/.claude/plans/featrue-dev-replicated-goblet.md Phase A3
>   对照报告：docs/对比/cockpit-vs-srs-framework.md

---

## 本次实现范围

**包含**：

1. **A3-1 — `setup_snapshots` 新增 3 列**（alembic 018，可前向可回滚）：
   - `volume_zscore: FLOAT NULL` —— 当日 volume 相对 N 日均量的 z-score
   - `obv_trend: VARCHAR(4) NULL` —— `'UP' | 'DOWN' | 'FLAT'`
   - `up_down_volume_ratio: FLOAT NULL` —— 上涨日成交量 ÷ 下跌日成交量（O'Neil U/D ratio）
2. **A3-2 — `setup_service` 三项指标计算**：纯函数 `_compute_volume_zscore`、`_compute_obv_trend`、`_compute_up_down_volume_ratio`，在 `compute_and_store_all` 内为每只股票计算并写入快照。
3. **A3-3 — BREAKOUT 机构吸筹门槛升级**：在 `_classify_setup_type` 内，BREAKOUT 候选必须同时满足
   - `volume_zscore ≥ VOL_ACC_BREAKOUT_Z_MIN`（默认 1.5）
   - `up_down_volume_ratio ≥ VOL_ACC_BREAKOUT_UD_MIN`（默认 1.2）
   未达标的候选**直接降级为 NONE**（不再 fall-through 到 PULLBACK / RECLAIM；与 features.json 验收条款一致）。短历史导致 `volume_zscore is None` 的候选也按未达标处理。
4. **A3-4 — API / Schema 暴露**：`GET /api/cockpit/setup` 的 `items[]` 元素新增 `volumeZscore` / `obvTrend` / `upDownVolumeRatio`（snake → camel 由 alias_generator 自动处理）。
5. **A3-5 — `SetupMonitorWidget` 新增 'Vol Z' 列**：在 RS 与 Earn 之间插入一列（width 6%，从未使用的 6% 余量中分配；现有 10 列宽度总和 94% → 加入后 100%），数值 `toFixed(2)`，null → '—'。

**明确排除（本次不做）**：
- 不修改 chart / regime / 任何 F215-a 已落地代码
- 不增 OBV 序列 API（OBV 仅用作 trend 分类，不返回序列）
- 不动 ready_signal / quality / suggested_action 计算逻辑（BREAKOUT 降级后续公式自然按 NONE 走）
- 不动其他 setup 类型（PULLBACK / RECLAIM / EARNINGS_DRIFT / EXTENDED / BROKEN）的门槛
- 不在 widget 上为 'Vol Z' 加颜色徽章 / 排序 / 筛选（仅展示）
- 不写迁移数据回填脚本（新列对历史快照保持 NULL，待下次 cron 自然填充）

---

## 预计修改文件（方案 A：7 文件 — 推荐 / 方案 B：6 文件 — 备选）

### 方案 A — 7 文件（沿用 F215-a 的 cockpit_params 集中配置模式）

| # | 文件路径 | 改动类型 | 说明 |
|---|---------|---------|------|
| 1 | `backend/alembic/versions/018_<rev>_setup_volume_accumulation.py` | 新建 | `op.add_column` × 3：`volume_zscore` FLOAT、`obv_trend` VARCHAR(4)、`up_down_volume_ratio` FLOAT，全部 nullable。down_revision 指向 017。downgrade 反向 drop。 |
| 2 | `backend/app/models/setup_snapshot.py` | 修改 | `SetupSnapshot` 新增 3 个 `Mapped[float \| None]` / `Mapped[str \| None]` 字段映射（与 alembic 一致） |
| 3 | `backend/app/services/cockpit/cockpit_params.py` | 修改 | `CockpitSetupParams` 追加 6 个常量：`VOL_ACC_ZSCORE_WINDOW=50`、`VOL_ACC_OBV_LOOKBACK=20`、`VOL_ACC_OBV_FLAT_PCT=2.0`、`VOL_ACC_UD_WINDOW=50`、`VOL_ACC_BREAKOUT_Z_MIN=1.5`、`VOL_ACC_BREAKOUT_UD_MIN=1.2` |
| 4 | `backend/app/services/cockpit/setup_service.py` | 修改 | 新增 3 个纯函数 `_compute_volume_zscore` / `_compute_obv_trend` / `_compute_up_down_volume_ratio`；`_classify_setup_type` 签名新增 `vol_zscore: float \| None, ud_ratio: float \| None`，BREAKOUT 分支门槛升级（未达标 return NONE）；`compute_and_store_all` 内对每只股票计算并写入 3 字段；短历史 NONE 行同步填 None |
| 5 | `backend/app/schemas/cockpit/setup.py` | 修改 | `SetupItemResponse` 新增 `volume_zscore: float \| None` / `obv_trend: str \| None` / `up_down_volume_ratio: float \| None` |
| 6 | `frontend/src/cockpit/lib/api/setupMonitorApi.ts` | 修改 | `SetupItem` type 新增 `volumeZscore: number \| null` / `obvTrend: 'UP' \| 'DOWN' \| 'FLAT' \| null` / `upDownVolumeRatio: number \| null` |
| 7 | `frontend/src/cockpit/widgets/SetupMonitorWidget.tsx` | 修改 | `<thead>` 在 RS 与 Earn 之间插入 `<Th width="6%">Vol Z</Th>`；调整现有列宽（RS 6→5%、Earn 8→7%、Dist 10→9%，使 Vol Z 占 6% 并保持 100%）；`SetupRow` 同步新增 `<Td>{fmt2(item.volumeZscore)}</Td>` |

⚠️ **超出 6-file 原则 1 项**。换取的是「阈值集中配置在 cockpit_params」的项目一贯模式（F215-a / F206 / F211 全部如此），便于未来扫参与回归。

### 方案 B — 6 文件（严守 6-file 原则，常量内联）

去掉文件 3（cockpit_params.py），将 6 个 VOL_ACC_ 常量改写为 `setup_service.py` 文件顶部的模块级 `Final[int/float]` 常量。其余 6 个文件不变。

**代价**：阈值不在 SETUP 中心化配置中，未来想做 A/B 扫参或写入 settings 需要先回迁。F215-a 没走这条路。

👤 **协商点 #1（必须先决定）**：A or B？

---

## 待协商点（开发前必须敲定）

### #1 — 文件数 vs 配置模式（如上）

- 推荐 **A**：保留 cockpit_params 中心化配置，付出 7 文件代价。
- 备选 B：6 文件严守，常量在 setup_service 内联。

### #2 — Volume z-score 窗口

- 推荐 **N = 50**（与 O'Neil / Minervini 经典吸筹判定一致；SRS 报告未明确点名 N，但与 U/D ratio 同窗口减少参数）。
- 备选 N = 20（与 `VOLUME_MA_PERIOD` 复用，但语义偏短期）。

### #3 — OBV trend 判定规则

- 推荐 **比较法**：`obv[-1]` vs `obv[-VOL_ACC_OBV_LOOKBACK]`（默认 20 bars），相对变化 `(obv[-1]-obv[-N])/abs(obv[-N])`：
  - `> +VOL_ACC_OBV_FLAT_PCT/100` → `UP`
  - `< -VOL_ACC_OBV_FLAT_PCT/100` → `DOWN`
  - 其余 → `FLAT`
  - `abs(obv[-N]) == 0` 或历史不足 → `None`
- 备选：线性回归斜率。复杂度高、对短窗口无明显收益。

### #4 — Up-Down volume ratio 分母为零兜底

- 推荐 **return None**（无下跌日 = 无可比较基线，比强行报告无穷大或 999 更诚实；BREAKOUT 门槛 `≥1.2 AND vol_zscore≥1.5` 中 None 视为 fail，自动降级到 NONE，逻辑闭环）。
- 备选：clamp 上限（如 9.99），代价是污染数据语义。

### #5 — `obv_trend` 列长度

- 推荐 **VARCHAR(4)**（最长 'DOWN'，留 1 字符余量；SQLite 不强制长度但 PG 严格）。
- 备选 VARCHAR(8)（与现有 `volume_status` 对齐）。

### #6 — 现有快照行的迁移策略

- 推荐 **不回填，保持 NULL**，等下次 cron `compute_and_store_all` 自然写入。理由：
  - 历史快照的 bars 数据不在 setup_snapshots 本表，回填需要重跑全量 ETL，代价高；
  - F215-b 门槛只影响**未来的** BREAKOUT 候选，历史快照的 `setup_type` 字段不变更，无业务冲突。
- 备选：写一次性 backfill 脚本。当前不必要。

### #7 — 'Vol Z' 列在 Widget 中是否参与排序 / 筛选

- 推荐 **不参与**（仅展示数值），与当前 'RS' 列保持一致风格。后续若用户反馈再独立加列排序。

---

## 文档同步（开发前 / 后必做）

| 阶段 | 文档 | 改动 |
|------|------|------|
| **开发前** | DATA-MODEL.md §Entity: SetupSnapshot | 新增 3 列文档：`volume_zscore`（FLOAT，nullable，含义 + 窗口）、`obv_trend`（VARCHAR(4)，枚举 UP/DOWN/FLAT/NULL）、`up_down_volume_ratio`（FLOAT，nullable，含义） |
| **开发前** | API-CONTRACT.md §GET /api/cockpit/setup | `items[]` 响应示例追加 3 个 camelCase 字段；说明 BREAKOUT 候选未达 vol gate → setup_type=NONE 行为 |
| **开发后** | DECISIONS.md D087 | Volume Accumulation 三件套定义（z-score / OBV trend / U-D ratio）与窗口选择（50d / 20d）的理由 |
| **开发后** | DECISIONS.md D088 | BREAKOUT 吸筹门槛升级：z≥1.5 AND U/D≥1.2，未达标降级 NONE（不 fall-through），对历史回归的影响说明 |
| **开发后** | DECISIONS.md D089 | 历史快照不回填策略（仅前向生效） |

---

## 可测试的完成标准

| # | 标准描述 | 测试层级 | 工具 |
|---|---------|---------|------|
| 1 | `_compute_volume_zscore(volumes, 50)` 对已知输入返回数学正确的 z-score；`std==0` 时返回 None；`len(volumes) < 50+1` 时返回 None | 单元 | pytest |
| 2 | `_compute_obv_trend(closes, volumes, lookback=20, flat_pct=2.0)`：构造单调上涨序列返回 'UP'；单调下跌返回 'DOWN'；横盘 ±1% 内返回 'FLAT'；历史不足返回 None；`obv[-20]==0` 返回 None | 单元 | pytest |
| 3 | `_compute_up_down_volume_ratio(closes, volumes, 50)`：构造上涨日总量 / 下跌日总量比已知；无下跌日返回 None；历史不足返回 None | 单元 | pytest |
| 4 | `_classify_setup_type` 在 BREAKOUT 候选 + `vol_zscore=2.0, ud_ratio=1.5` 时返回 `BREAKOUT`；在 `vol_zscore=1.0, ud_ratio=1.5` 时返回 `NONE`（不 fall-through 到 PULLBACK）；在 `vol_zscore=2.0, ud_ratio=1.0` 时返回 `NONE`；在 `vol_zscore=None`（短历史）时返回 `NONE` | 单元 | pytest |
| 5 | `SetupSnapshotService.compute_and_store_all()` 写入的行包含 3 个新字段（非短历史 + 数据足够时为非 None；短历史时为 None） | 集成 | pytest（mock bars） |
| 6 | alembic upgrade 018 → 017 → 018 可往返，不损坏既有数据；upgrade 后老快照 3 列为 NULL | 集成 | pytest（一次性 in-memory engine） |
| 7 | `GET /api/cockpit/setup` 响应 `items[i]` 包含 `volumeZscore` / `obvTrend` / `upDownVolumeRatio`，camelCase 正确，类型符合 schema | 集成 | pytest httpx + TestClient |
| 8 | `SetupMonitorWidget` 渲染表头包含 'Vol Z' 列；`SetupRow` 在 `volumeZscore=1.83` 时显示 '1.83'，在 null 时显示 '—'；列宽总和保持 100% | 单元（前端） | vitest + @testing-library |
| 9 | 全量后端 pytest 套件无新增失败 | 回归 | pytest |
| 10 | 全量前端 vitest 套件无新增失败 | 回归 | vitest |
| 11 | 启动 dev server，`/cockpit` 页面 SetupMonitorWidget 列宽不挤压、新列显示数据无 console.error | 手测 | pnpm dev + 浏览器 |

---

## 回归风险

- **BREAKOUT 候选数量将下降**：这是预期行为（acceptance_criteria 明示）。建议在 D088 中显式记录"门槛升级前 → 升级后 BREAKOUT 候选数变化"，便于后续观察。开发完成后可加一段一次性 SQL 查询写入 progress：`SELECT COUNT(*) FROM setup_snapshots WHERE setup_type='BREAKOUT' AND scan_date >= today-7`，前后对比。
- **短历史股票（<51 bars）**：BREAKOUT 永远不会触发（z-score None → fail）。这是有意为之，符合 SRS"机构吸筹确认"语义。在 D087 文档化。

---

## Evaluator 自检清单

开发完成后，Evaluator 模式逐条检查：

- [ ] 单元测试通过（`cd backend && pytest tests/cockpit/test_setup_service.py tests/test_decision_f215b.py -v`）
- [ ] 集成测试通过（`cd backend && pytest tests/cockpit/test_setup_router.py tests/test_alembic_018.py -v`）
- [ ] 前端单元测试通过（`cd frontend && pnpm test`）
- [ ] 全量后端 pytest 通过（`cd backend && pytest`）
- [ ] 全量前端 vitest 通过（`cd frontend && pnpm test`）
- [ ] alembic upgrade 018 + downgrade 018 双向通过（在本地一次性 sqlite 验证）
- [ ] API 响应格式符合 API-CONTRACT.md（3 个 camelCase 字段已记录）
- [ ] DATA-MODEL.md 已更新 SetupSnapshot 字段表
- [ ] DECISIONS.md 追加 D087 + D088 + D089
- [ ] UI 对照 design-spec.md：SetupMonitorWidget 在 4 种状态下（正常 / 加载 / 空数据 / 错误）'Vol Z' 列渲染逻辑都不报错；列宽总和 100%
- [ ] 无 console.error 遗留
- [ ] Lint 通过（`pnpm lint` / 后端 ruff）
- [ ] 无死代码（删除任何调试 print/console.log）
- [ ] 无硬编码魔法值（z=1.5 / U/D=1.2 / 50d / 20d / 2% 全部通过 `SETUP.VOL_ACC_*` 或方案 B 顶部 Final 常量）

---

## 待你拍板的输入

1. **文件数：方案 A（7 文件，cockpit_params 集中）还是方案 B（6 文件，常量内联）？** ← 推荐 A
2. **z-score / U/D ratio 窗口：N=50 还是 N=20？** ← 推荐 50
3. **OBV trend 用比较法 + FLAT 阈值 2%？** ← 推荐 YES
4. **U-D ratio 分母为零兜底：return None？** ← 推荐 YES
5. **obv_trend 列长度：VARCHAR(4) 还是 VARCHAR(8)？** ← 推荐 4
6. **历史快照：保持 NULL 不回填？** ← 推荐 YES
7. **'Vol Z' 列：仅展示不排序不筛选？** ← 推荐 YES

👤 任一项不同意请直接指出；全部同意可回复"按推荐方案确认"，我即可进入 Generator 模式开始开发。
