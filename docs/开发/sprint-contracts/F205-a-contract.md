# Sprint Contract：F205-a Universe 字段扩展（sector/industry/last_price/last_volume）

> 日期：2026-04-27 | 状态：草案
> 父 Feature：F205 Pool Builder Widget（v1.9 Cockpit P1）
> 引用文档：
>   DATA-MODEL.md §MarketScanUniverse | API-CONTRACT.md §GET /api/cockpit/pool（消费方）
> 决策上下文：本 session "F205 数据源 gap 报告" 的 决策 2-A（在 universe 表持久化 sector/price/volume，避免每次端点 hit 重新拉 screener）

---

## 本次实现范围

**包含**：

1. `market_scan_universe` 表加 4 列：`sector` / `industry` / `last_price` / `last_volume`
2. Alembic 迁移脚本（向上：加 4 列；向下：drop 4 列；空值兼容历史行）
3. SQLAlchemy 模型 `MarketScanUniverse` 同步增字段
4. Repository `UniverseUpsertRow` dataclass + `upsert_many` 写入 / 读取这 4 列
5. `UniverseRefreshService._parse_screener_row` 从 FMP screener 响应中读取 `sector` / `industry` / `price` / `volume` 并写入 universe 行（缺字段时存 null，不跳过该 ticker）
6. **字段级降级聚合日志**：service 在 refresh 内累加 4 个 counter（`sector_missing` / `industry_missing` / `price_missing` / `volume_missing`），写入现有 `"universe refreshed: ..."` SystemLog 消息末尾。冷启动时 ETF 等行常缺 sector，低计数视为正常；某字段计数 ≈ total 行数 → 视为 FMP schema breakage 异常信号（人工或后续监控发现）
7. **解析异常硬保护**：`_parse_screener_row` 内任何未预期异常（不只是 TypeError/ValueError）必须捕获并返回 None + 累加 `parse_exception` counter；service 在 refresh 末尾若 `parse_exception > 0` 写一条 WARN 级 SystemLog（含计数，不含逐行 detail，避免 1000 条噪声）
8. DATA-MODEL.md 同步更新 MarketScanUniverse 字段表 + 业务规则补充
9. 单元测试：`_parse_screener_row` 解析新字段（含缺字段降级、字段类型异常）+ Repository upsert 写入/读取新字段
10. 集成测试：universe refresh 端到端写入新字段（mock FMP），含降级 counter 的 SystemLog 验证

**明确排除（本次不做）**：

- 不新增任何 router / API endpoint —— /api/cockpit/pool 在 F205-c
- 不计算 RS percentile / ADV / fundamental / setup — F205-b 负责
- 不改 frontend — F205-d 负责
- 不修改 universe refresh cron 触发条件 / 频率
- 不动 `market_breakout_scans` 表（F205-b 才会触及）
- 不补 sector ETF 映射（前端 sector 显示策略由 F205-c/d 决定）
- **不为 last_price / last_volume 加任何"实时刷新"机制**：仅在 universe refresh cron（月级）时一并写入；这两列**不**用于 widget 展示价格，仅用于 pool funnel 的 tradable 层 filter（marketCapMin / priceMin 已有；advMin 在 F205-b 用 trend 子集 EOD 算，不依赖 last_volume）

> 关于 last_volume 的用法说明：universe 表的 `last_volume` 是"最近一次月级 refresh 当天"的成交量快照，**不**等同于 advMin filter 的 20 日均美元成交量。F205-b 的 advMin filter 仍走 trend 子集 EOD 计算。`last_volume` 仅作为冷启动期的极弱过滤参考（"近期是否有交易"），可选不暴露。本 sprint 先持久化字段，使用决策留给 F205-b/c。

---

## 预计修改文件

| # | 文件路径 | 改动类型 | 说明 |
|---|---------|---------|------|
| 1 | `backend/alembic/versions/015_f205a_universe_extra_fields.py` | 新增 | Alembic 迁移：alter `market_scan_universe` add 4 nullable 列；downgrade 删除 |
| 2 | `backend/app/models/market_scan_universe.py` | 修改 | SQLAlchemy 模型加 `sector` / `industry` / `last_price` / `last_volume`，全部 nullable |
| 3 | `backend/app/repositories/market_scan_universe_repository.py` | 修改 | `UniverseUpsertRow` 加 4 个 Optional 字段；`upsert_many` 在 INSERT 与 ON CONFLICT 两侧都写入 4 列 |
| 4 | `backend/app/services/universe_refresh_service.py` | 修改 | `_parse_screener_row` 解析 FMP 字段：`sector`（str/None）/`industry`（str/None）/`price`（float/None）/`volume`（int/None）；任何字段缺/类型错都降级为 None，**不跳过该 ticker** |
| 5 | `backend/tests/test_market_scan_repositories.py` | 修改 | 新增测试：upsert/读取 4 个新字段；含 None 字段；二次 upsert 用新值覆盖旧值 |
| 6 | `backend/tests/test_universe_refresh_service.py` | 修改 | 新增测试：FMP 响应含 / 缺 sector/industry/price/volume 时 service 行为；类型异常降级；DB 行字段验证 |

**附加文档更新**（不计入 6 文件硬上限，由 system-design 协议归 feature-dev 协同）：
- `docs/系统设计/DATA-MODEL.md` — MarketScanUniverse 字段表加 4 行 + 业务规则段补充
- `docs/系统设计/DECISIONS.md` — 追加 D078（universe 表持久化 sector/industry/screener 快照价/成交量；ADV 不在此层算）

文件计数：**6/6**（在硬上限内，无需进一步拆分）

---

## 可测试的完成标准

| # | 标准描述 | 测试层级 | 工具 |
|---|---------|---------|------|
| 1 | `MarketScanUniverse` ORM 实例可访问 `.sector`、`.industry`、`.last_price`、`.last_volume` 属性，全部允许 None | 单元 | pytest |
| 2 | `_parse_screener_row({"symbol":"AAPL","companyName":"Apple","marketCap":3000000000000,"exchange":"NASDAQ","sector":"Technology","industry":"Consumer Electronics","price":175.5,"volume":50000000})` 返回的 `UniverseUpsertRow` 4 个新字段值正确 | 单元 | pytest |
| 3 | `_parse_screener_row` 在缺 sector/industry/price/volume 任一字段时仍返回有效行（4 字段对应 None），不跳过 | 单元 | pytest |
| 4 | `_parse_screener_row` 在 price/volume 字段为非数字（如空字符串、"N/A"）时降级为 None，不抛异常 | 单元 | pytest |
| 5 | `MarketScanUniverseRepository.upsert_many` 写入 4 个新字段后，从 DB 重新查询能读回相同值 | 集成 | pytest + sqlite |
| 6 | 同一 ticker 二次 upsert：新字段值覆盖旧值（与 `company_name` / `exchange` / `market_cap` 行为一致） | 集成 | pytest + sqlite |
| 7 | `UniverseRefreshService.refresh()` 用 mock FMP（返回带新字段的 screener payload）跑一次后，DB 中 universe 行 4 个新字段非 None | 集成 | pytest + sqlite + mock FMP |
| 8 | Alembic upgrade head 在已有 universe 数据的库上能成功运行（旧行 4 字段为 None） | 集成 | pytest（生成测试库 → 升级） |
| 9 | Alembic downgrade 能回滚 4 列 | 集成 | pytest |
| 10 | mock FMP 返回 100 行其中 30 行缺 sector / 10 行 price 类型错 → SystemLog "universe refreshed" 消息内含 `sector_missing=30 price_missing=10` 等聚合计数 | 集成 | pytest + sqlite + mock SystemLogRepository |
| 11 | mock FMP 中夹杂 1 行触发 `_parse_screener_row` 内未预期异常（如 dict 缺 marketCap 但其他字段类型异常）→ refresh 完成后写入一条 `level=WARN` SystemLog 含 `parse_exception=1` | 集成 | pytest |
| 12 | 全量回归：`pytest backend/` 总数与变更前一致（除新增用例），无新失败 | 回归 | pytest |

---

## Evaluator 自检清单

开发完成后，Evaluator 模式逐条检查：

- [ ] `pytest backend/tests/test_universe_refresh_service.py backend/tests/test_market_scan_repositories.py` 全部通过
- [ ] 全量回归 `pytest backend/` 通过（无新失败）
- [ ] Alembic upgrade + downgrade 都能正常跑（手工跑一次空库 + 旧库）
- [ ] FMP 响应缺字段 / 字段类型异常时 service 不抛异常、不跳过 ticker
- [ ] 字段级降级 counter（sector/industry/price/volume）写入"universe refreshed" SystemLog 消息末尾，格式可被人工/后续监控读出
- [ ] 未预期解析异常 counter > 0 时额外写一条 WARN-level SystemLog；counter == 0 时不写额外日志（避免噪声）
- [ ] 模型字段命名严格符合 DATA-MODEL.md（snake_case：`sector` / `industry` / `last_price` / `last_volume`）
- [ ] DATA-MODEL.md 已更新 MarketScanUniverse 字段表
- [ ] DECISIONS.md 已追加 D078（universe 持久化 screener 快照字段；ADV 不在此层）
- [ ] 无 `print` / `pdb.set_trace` / 调试代码遗留
- [ ] 无未引用的 import / 死代码
- [ ] Repository `UniverseUpsertRow` dataclass 4 个新字段都用 `Optional[...]` / `| None` 类型注解
- [ ] 任何非显而易见的解析降级行为（特别是 price/volume 字符串容错）有 1-2 行注释说明 *为什么* 容错（而不是抽象描述）

---

## 与下游 sub-sprint 的接口约定（仅备查）

- F205-b（pool service）会在 `pool_service.tradable_layer()` 里 SELECT `market_scan_universe` 后按 marketCapMin / priceMin（用 `last_price`）过滤 → tradable count
- F205-b 的 ADV 计算与本 sprint 的 `last_volume` 字段**无直接关系**（ADV 走 trend 子集 EOD）
- F205-c 的 widget 显示 sector 列时直接读 `data.items[].sector`（来源链：universe.sector → pool_service.items 透传）

---

👤 用户确认本 Contract 后，将：
1. 更新 features.json：F205 加 `sub_sprints` 结构，F205-a 设为 `contract_agreed`，`active_sub_sprint=F205-a`
2. 更新 claude-progress.txt
3. 生成 SESSION-HANDOFF.md
4. **强制结束 session**，建议 Sonnet 新 session 进入 Generator 模式
