# Sprint Contract：F205-e Pool Cache（RS + Fundamental 周级预算）

> 日期：2026-04-28 | 状态：needs_review（829 passed，0 failed）
> 父 Feature：F205 Pool Builder Widget（v1.9 Cockpit P1）
> 前置 Sprint：F205-a ✅ / F205-b ✅ / F205-c ✅ / F205-d ✅ done
> 引用文档：
>   - `docs/系统设计/API-CONTRACT.md` §GET /api/cockpit/pool（行 1322–1388）
>   - `docs/系统设计/DATA-MODEL.md`（待新增 §CockpitPoolCache）
>   - `docs/系统设计/DECISIONS.md` D079（pool helpers + fail-open）/ D080（universe 数据策略）
>   - `backend/app/services/cockpit/pool_service.py`（F205-c 交付，本 sprint 改读 cache）
>   - `backend/app/services/refresh_job.py`（APScheduler，加新 cron）

---

## 0. Sprint 定位

F205-d 验收发现性能问题：filter 改动 → 后端从头跑漏斗，每次都打 FMP（~10–30s）。本 sprint 把**最贵的两层**（RS percentile + fundamental revenue growth）改为**周级预算**，写入 `cockpit_pool_cache` 表，查询时直接读 DB。

漏斗各层的频率重新分配：

| 层 | 数据源 | 现状 | 本 sprint 后 |
|---|---|---|---|
| tradable | universe（已每月刷新） | 实时 SQL | 不变 |
| trend | market_breakout_scans（已每日 job） | 实时 SQL | 不变 |
| **RS** | FMP get_daily_bars（昂贵） | 每请求实时算 | **每周日预算 → 读 cache** |
| **fundamental** | FMP get_financial_growth（昂贵） | 每请求实时算 | **每周日预算 → 读 cache** |
| action | setup_snapshots（已每日 job） | 实时 SQL | 不变 |

预期收益：filter 改动响应时间 30s → < 500ms。

---

## 1. 待用户确认的 5 个开放问题

请逐条确认（默认推荐方案标 ★）：

| # | 问题 | 选项 | 推荐 |
|---|------|------|------|
| Q1 | Cache 范围 | A. 仅 trend-passing tickers（~50 个，FMP 调用少） / B. **全部 universe tickers（~600 个，trend 变化时 cache 仍可用）** ★ | B |
| Q2 | Cron 时机 | A. 每周一 06:30 UTC（避开 setup_cron 22:30 / earnings_cron 05:30） ★ / B. 每周日 23:00 UTC | A |
| Q3 | Cache miss 行为 | A. 返回空漏斗 + 警告日志 ★ / B. fallback 到实时 FMP 计算（恢复慢） / C. 返回 503 | A |
| Q4 | 50MA 字段是否一并缓存 | A. **是，cache 表加 `ma50` + `last_close` 列**（保留 distanceTo50maPct 字段值）★ / B. 否，distanceTo50maPct 改为 null | A |
| Q5 | 手动触发 | A. **本 sprint 不加**，用 CLI 脚本（`python -c "..."`） ★ / B. 加 admin endpoint POST /api/admin/refresh-pool-cache（多 1–2 个文件） | A |

---

## 2. 本次实现范围（基于推荐方案）

### 2.1 新建 cockpit_pool_cache 表（迁移 + 模型）

文件：`backend/alembic/versions/016_f205e_pool_cache.py` + `backend/app/models/cockpit_pool_cache.py`

表结构：

```sql
CREATE TABLE cockpit_pool_cache (
  ticker TEXT PRIMARY KEY,
  rs_percentile REAL NOT NULL,
  ma50 REAL,                 -- 250d 序列后 50 日均值
  last_close REAL,           -- 250d 序列最后一日 close
  revenue_growth_yoy REAL,   -- 可 null（FMP 未返回 → fail-open）
  computed_at DATETIME NOT NULL
);
CREATE INDEX ix_cockpit_pool_cache_computed_at ON cockpit_pool_cache(computed_at);
```

- 表整表替换式更新（每周一次）：service 在事务内 `DELETE FROM cockpit_pool_cache; INSERT ...`
- 不存 trend/setup/earnings 等已每日刷新的字段（避免数据双写不一致）

### 2.2 新建 PoolCacheService（写 cache）

文件：`backend/app/services/cockpit/pool_cache_service.py`

职责：

1. 加载所有 universe tickers（不过滤 trend，Q1=B）
2. 并发拉 FMP 250d bars（`_FMP_MAX_WORKERS=6`，复用现有 ThreadPoolExecutor 模式）
3. 计算 `rs_percentile`（通过 `compute_rs_percentile_map`，复用 F205-b helpers）
4. 并发拉 FMP financial-growth，提取 `revenue_growth_yoy_pct`
5. 写入 `cockpit_pool_cache` 表（事务内 DELETE + INSERT）
6. 写入 `system_logs`：`{level: OK, source: pool_cache, message: "rebuilt N=600 elapsed=4m32s"}`
7. 返回 `PoolCacheResult(status, upserted, elapsed_seconds, error)`

API：

```python
class PoolCacheService:
    def __init__(self, db: Session, fmp: FmpClient) -> None: ...
    def rebuild(self) -> PoolCacheResult: ...
```

### 2.3 改 PoolService 读 cache（关键变更）

文件：`backend/app/services/cockpit/pool_service.py`（修改）

变更：

- `_compute_rs_layer()`：删掉 FMP bars 调用，改为读 `cockpit_pool_cache`，构造 `percentile_map` + `closes_by_ticker`（用 `ma50` / `last_close` 重建 distance_to_50ma 计算所需）
- `_filter_fundamental()`：删掉 FMP financial-growth 调用，改为读 cache 的 `revenue_growth_yoy` 列
- `_make_item()` 的 `compute_distance_to_50ma_pct(close, ma50)` 改用 cache 的 `last_close` 和 `ma50`
- 删除 `_fetch_bars_concurrent`（不再需要）
- **Cache miss 处理（Q3=A）**：cache 表为空时返回 `funnel: {tradable, trend, rs:0, fundamental:0, action:0}, items: []`，写一条 WARN 日志
- 字段 `_FMP_MAX_WORKERS` / `_BARS_LOOKBACK_DAYS` 移到 `pool_cache_service.py`

### 2.4 注册周级 cron

文件：`backend/app/services/refresh_job.py`（修改）

新增 job 定义：

```python
POOL_CACHE_JOB_ID = "cockpit_pool_cache_rebuild"
# 每周一 06:30 UTC（Q2=A）：
#   - 避开 universe_cron（每月 1 日 05:00）
#   - 避开 earnings_cron（每日 05:30）
#   - 给 daily refresh + setup tick（前一日 22:30）留 8h buffer
POOL_CACHE_CRON = "30 6 * * 1"

def _pool_cache_tick(session_factory, fmp_factory):
    try:
        with _session_scope(session_factory) as db:
            PoolCacheService(db, fmp=fmp_factory()).rebuild()
    except Exception:
        logger.error("pool cache tick failed\n%s", traceback.format_exc())

# 在 start_scheduler() 中注册:
sched.add_job(
    _pool_cache_tick,
    trigger=CronTrigger.from_crontab(POOL_CACHE_CRON, timezone="UTC"),
    id=POOL_CACHE_JOB_ID,
    args=[session_factory, fmp_factory],
    replace_existing=True,
)
```

### 2.5 测试

文件：`backend/tests/test_pool_service.py`（修改）

- 把现有 9 个 PoolService 测试的 fixture 从 "mock FmpClient 返回 bars / growth" 改为 "在 cockpit_pool_cache 表 seed 数据"（fixture helper 简化）
- **新增 PoolCacheService 测试组**（约 6–8 个）：
  - `rebuild()` 正常路径：写入 N 行，elapsed 合理
  - `rebuild()` FMP 单 ticker bars 失败 → 该 ticker 不入 cache，其他成功
  - `rebuild()` financial-growth 缺数据 → revenue_growth_yoy 写 null（fail-open，D079）
  - `rebuild()` 整表替换：旧 cache 行被清空再插入
  - PoolService cache miss → 返回空 funnel + 写 WARN 日志（Q3=A）

### 2.6 排除

- ❌ 手动触发 admin endpoint（Q5=A，留待 F205-f 或独立 sprint）
- ❌ 前端任何改动
- ❌ 不修改 universe_refresh_service / scanner / setup_service
- ❌ 不动 React Query staleTime

---

## 3. 预计修改文件清单（共 6 个，命中上限）

| # | 文件 | 状态 |
|---|------|------|
| 1 | `backend/alembic/versions/016_f205e_pool_cache.py` | 新建 |
| 2 | `backend/app/models/cockpit_pool_cache.py` | 新建 |
| 3 | `backend/app/services/cockpit/pool_cache_service.py` | 新建 |
| 4 | `backend/app/services/cockpit/pool_service.py` | 修改 |
| 5 | `backend/app/services/refresh_job.py` | 修改 |
| 6 | `backend/tests/test_pool_service.py` | 修改（含 PoolCacheService 测试） |

✅ 6 ≤ 6 文件原则上限。

注：`docs/系统设计/DATA-MODEL.md` 需追加 §CockpitPoolCache 节，归类为 docs 改动不计入 6 文件。

---

## 4. 完成标准（可测试）

| # | 标准 | 测试层级 | 工具 |
|---|------|---------|------|
| 1 | `cockpit_pool_cache` 表迁移成功，列结构正确 | 单元 | alembic upgrade + inspect |
| 2 | `PoolCacheService.rebuild()` 写入正确行数（mock FMP 返回 N 个 ticker） | 单元 | pytest |
| 3 | `rebuild()` 整表替换：先 DELETE 旧行再 INSERT | 单元 | pytest |
| 4 | `rebuild()` 单 ticker bars 失败：该 ticker 不入 cache，其他不受影响 | 单元 | pytest |
| 5 | `rebuild()` financial-growth 缺数据：`revenue_growth_yoy=null`（D079 fail-open） | 单元 | pytest |
| 6 | `PoolService.get_pool()` 读 cache：不打任何 FMP，结果正确 | 单元 | pytest（FmpClient mock 断言 0 calls） |
| 7 | Cache 为空时：返回空 funnel + 写 WARN 日志（Q3=A） | 单元 | pytest |
| 8 | Cron 注册：scheduler 启动后 `POOL_CACHE_JOB_ID` 在 jobs 列表 | 单元 | pytest（autostart=False） |
| 9 | distanceTo50maPct 与 F205-c 旧实现行为一致（用 cache 的 ma50/last_close） | 单元 | pytest |
| 10 | TypeScript / 前端无改动 → 前端测试不应受影响 | 回归 | pnpm test |
| 11 | 后端全量回归通过（≥ 820 + 新增） | 回归 | pytest |
| 12 | 手动 CLI 触发 rebuild 后调 `/api/cockpit/pool` 返回非空 funnel | 集成（手动） | curl + python -c |

---

## 5. Evaluator 自检清单

- [ ] 单元测试全部通过
- [ ] 后端全量回归通过（820 + 新增）
- [ ] PoolService 修改后 **不再 import** ThreadPoolExecutor / FmpClient bars 调用
- [ ] cron 注册后 jobs 列表包含 `cockpit_pool_cache_rebuild`
- [ ] cache 表迁移可 upgrade + downgrade
- [ ] 新表 schema 与 contract §2.1 完全一致（含 index）
- [ ] PoolCacheService 写日志：成功 OK / 失败 ERROR
- [ ] cache miss 路径有日志（便于排查）
- [ ] 字段命名：cache 表 `revenue_growth_yoy`（snake，DB），Pydantic 层透过 to_camel 转 camelCase
- [ ] 文档：`DATA-MODEL.md` 追加 §CockpitPoolCache，`DECISIONS.md` 追加 D081（pool 周级预算决策）

### 代码质量检查

- [ ] Lint 通过，无新增 warning
- [ ] PoolService 修改后行数 < 修改前（删除 FMP 逻辑）
- [ ] 无重复代码（pool_helpers.py 的纯函数照常复用）
- [ ] `cockpit_pool_cache_repository` 不新建（直接在 service 用 SQLAlchemy 是可以的）

---

## 6. 开放问题与风险

### 已识别风险

1. **首次部署时 cache 为空**：用户必须手动跑一次 `PoolCacheService.rebuild()` 才能看到数据。需在 SESSION-HANDOFF 明确写 CLI 触发命令。
2. **FMP rate limit**：~1200 calls / 周（600 bars + 600 growth），低频，影响小。
3. **Cron 与 universe_refresh 时序**：每月 1 日 universe 刷新后，可能新增/移除 ticker。Cache 在下个周一 06:30 才更新，期间新加入的 ticker 在 pool 里看不到 RS（cache miss → 该 ticker 不在 percentile_map → 进不了 RS 层）。可接受。
4. **测试改动较大**：现有 PoolService 9 个测试都要改 fixture。如果某条测试很复杂导致改动超 50 行，考虑拆 F205-f。

### 待用户决策（重申 Q1–Q5）

请逐条回复 1A/1B…5A/5B 确认。也可提出修改建议。

---

## 7. 开发顺序（Generator 阶段）

1. 新建迁移 + 模型 → `alembic upgrade head` 验证 → wip commit
2. 新建 `pool_cache_service.py`（rebuild 函数 + dataclass）→ wip commit
3. 新增 PoolCacheService 6 个测试（在 test_pool_service.py 末尾追加）→ 通过 → wip commit
4. 修改 `pool_service.py` 改读 cache → wip commit
5. 适配现有 PoolService 测试（fixture 改 seed cache）→ 通过 → wip commit
6. 修改 `refresh_job.py` 注册 cron + 测试 → wip commit
7. `pytest` 全量回归 → DECISIONS.md 追加 D081 → DATA-MODEL.md 追加 §CockpitPoolCache → 最终 commit `feat(F205-e): pool cache 周级预算`

---

## 8. 验收（acceptance）测试要点

- 手动触发 `PoolCacheService.rebuild()` 一次（CLI）
- 调 `GET /api/cockpit/pool`（默认参数）：response < 500ms，非空 funnel
- 改 filter（如 rsPercentileMin=50）：response < 500ms（与默认参数同量级）
- 检查 `system_logs`：source=pool_cache 有最近一条 OK 记录
