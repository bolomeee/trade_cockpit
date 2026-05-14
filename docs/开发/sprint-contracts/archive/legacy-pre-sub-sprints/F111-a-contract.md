# Sprint Contract：F111-a — 同日 ticker on-demand 数据缓存（后端）

> 状态：in_progress | 开始：2026-04-22

## 1. 实现范围

**包含：**
- 新增表 `daily_payload_cache(id, ticker, endpoint, as_of_date, payload_json, cached_at)`
  - 联合唯一索引 `(ticker, endpoint, as_of_date)`
  - `endpoint` 枚举常量：`ENDPOINT_CHART = "chart"` | `ENDPOINT_FUNDAMENTALS = "fundamentals"`
- `stock_detail_service.get_chart` fallback 分支（非 watchlist ticker）：
  - 先查 `daily_payload_cache` 当日命中 → 直接返回 payload（不打 FMP）
  - miss → 原有 FMP 逻辑 → 成功后写入缓存
- `stock_detail_service.get_fundamentals`（所有 ticker，统一）：
  - 先查 `daily_payload_cache` 当日命中 → 返回
  - miss → FMP 双端点 → 成功后写入
- 当日 = `cached.as_of_date == date.today()`（server local date）
- 错误路径不缓存（FMP httpx error → 仍抛 502，不写表）
- 空结果不缓存（FMP 返回空 dict/None 不写表，走原有 null 路径）

**排除：**
- Watchlist ticker chart（`_chart_from_watchlist` 已无 FMP 调用，不改）
- Pullbacks 端点（F108 已定义，无 FMP 调用）
- 前端 React Query 配置（F111-b 独立 Sprint）
- 手动清缓存 API

## 2. 预计修改文件（共 7 个）

| # | 文件 | 类型 |
|---|------|------|
| 1 | `backend/alembic/versions/005_f111a_daily_payload_cache.py` | 新建（Alembic 迁移） |
| 2 | `backend/app/models/daily_payload_cache.py` | 新建（ORM 模型 + repo 函数） |
| 3 | `backend/app/models/__init__.py` | 修改（加 2 行 import + __all__ 条目） |
| 4 | `backend/app/services/stock_detail_service.py` | 修改（get_chart fallback + get_fundamentals 接入缓存） |
| 5 | `backend/tests/test_stock_detail.py` | 修改（加缓存命中/穿透/跨日失效用例） |
| 6 | `docs/系统设计/DATA-MODEL.md` | 修改（新增 DailyPayloadCache 实体描述） |
| 7 | `docs/系统设计/DECISIONS.md` | 修改（追加 D055） |

## 3. 完成标准

| # | 标准 | 层级 | 工具 |
|---|------|------|------|
| 1 | 非 watchlist ticker 首次 `/chart` → 打 FMP 且写入缓存 | 集成 | pytest + FakeFMP call count |
| 2 | 同日第二次 `/chart`（同 client / same db session engine）→ 不打 FMP，结果一致 | 集成 | pytest |
| 3 | 非 watchlist ticker 首次 `/fundamentals` → 打 FMP 双端点且写入缓存 | 集成 | pytest |
| 4 | 同日第二次 `/fundamentals` → 零 FMP 调用（ratios_calls + key_metrics_calls 不增加）| 集成 | pytest assert len |
| 5 | 跨日（monkeypatch date.today() + 1 天）→ 缓存失效，重新打 FMP | 单元 | monkeypatch |
| 6 | FMP 抛 httpx error → 不写缓存 + 返回 502 | 单元 | FakeFMP exc |
| 7 | FMP 返回空结果 → 不写缓存，返回 null 字段（原有行为不变）| 单元 | pytest |
| 8 | Watchlist ticker `/chart` 行为不变（仍零 FMP，读 daily_bars）| 回归 | 既有测试通过 |
| 9 | Alembic upgrade + downgrade 通过 | 手动 | alembic CLI |
| 10 | 全量后端回归：`pytest backend/tests` 100% 通过 | 回归 | pytest |

## 4. Evaluator 自检清单

- [ ] 单元测试全部通过
- [ ] 集成测试全部通过（FMP 调用次数验证）
- [ ] 全量回归通过（既有 F105-F110 相关测试无退化）
- [ ] 新表字段命名符合 DATA-MODEL.md snake_case 规范
- [ ] `/chart` 和 `/fundamentals` 响应 JSON 格式与 API-CONTRACT.md 完全一致
- [ ] 错误路径不缓存（502 场景验证）
- [ ] 无硬编码魔法值（endpoint 枚举为常量）
- [ ] DECISIONS.md 追加 D055
- [ ] Alembic upgrade/downgrade 双向通过
- [ ] Lint 通过
