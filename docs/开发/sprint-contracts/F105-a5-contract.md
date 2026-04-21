# Sprint Contract — F105-a5：FMP 共享限流器 + Scanner 并发拉取

**日期**：2026-04-21
**依赖**：F105-a3（scanner 服务已存在）
**前置阅读**：CLAUDE.md、ARCHITECTURE.md（限流策略）、`fmp_client.py:48-114`、`market_scanner_service.py:111-138`

---

## 现状（关键发现）

1. `FmpClient` 已内置 token bucket（capacity 50，refill 0.2s = 5 rps = **300 rpm**）和 429 重试，[fmp_client.py:48-100](backend/app/external/fmp_client.py)。
2. **但限流器是 per-instance 的**：DI 工厂（`dependencies.py:18`、`main.py:16`）每次调用 `FmpClient()` 都新建实例，bucket 不共享。Scanner / watchlist refresh / 用户手动操作并行触发时，三路 FmpClient 各自有独立 bucket，**进程总速率可超 300 rpm**，存在被 FMP 限流/封禁风险。
3. `FmpClient` 没有并发上限（Semaphore），瞬时可发任意条 in-flight 请求（受 token bucket 制约，但 burst 能短时冲到 50）。
4. Scanner 是**串行 for 循环**（[market_scanner_service.py:111](backend/app/services/market_scanner_service.py)），250 ticker × ~1s/请求 ≈ 4 分钟跑完，没有充分利用速率配额。

## 本次实现范围（必须做）

1. **共享限流器**：把 FmpClient 的 token bucket 状态从 instance-level 提升为 **可共享的 `_FmpRateLimiter` 实例**；`get_fmp_client()` / `_fmp_factory()` 注入**模块级单例**，进程内所有 FmpClient 实例共用一个 bucket。
2. **并发上限**：在 `_FmpRateLimiter` 内增加 `threading.Semaphore(6)`，`_request` 入口先 acquire semaphore 再走 bucket，确保任意时刻 in-flight ≤ 6。
3. **Scanner 改并发**：`MarketScannerService.run_scan` 把 active universe 的 for 循环改为 `concurrent.futures.ThreadPoolExecutor(max_workers=6)`，每个 ticker 一个 task；hits/scanned_ok/failed/fallback_used 用 `threading.Lock` 保护聚合；保持 D040 语义（全部失败不清旧 snapshot）。
4. **DECISIONS.md**：追加 D044（共享限流器 + 6 并发选型理由）。
5. **可观察性**：scan 完成的 OK 日志追加 `duration_s=<秒>` 字段，便于对比并发前后耗时差异。

## 排除范围（明确不做）

- universe 阈值不变（仍 50B）
- 不改 DATA-MODEL / API-CONTRACT / 前端
- 不改 watchlist refresh / market_refresh_service / 用户路径的串行行为（它们自动受益于共享限流器，不需要改并发）
- 不改 SMA → EOD fallback 触发逻辑
- 不改 cron 时间

## 预计修改文件（共 5 个）

1. `backend/app/external/fmp_client.py` — 抽出 `_FmpRateLimiter` 类（含 bucket + Semaphore），FmpClient 接收 limiter 注入，模块级 `default_rate_limiter()` 单例
2. `backend/app/dependencies.py` — `get_fmp_client()` 用模块级 limiter
3. `backend/app/main.py` — `_fmp_factory()` 同上
4. `backend/app/services/market_scanner_service.py` — for 循环 → ThreadPoolExecutor + Lock 聚合
5. `backend/tests/test_fmp_client.py` — 现有 rate 测试 fixture 改为注入新 limiter（避免共享状态污染）；新增 4 条用例（共享 limiter 跨实例生效、Semaphore 上限 6、Semaphore 与 bucket 顺序、injection contract）
6. `backend/tests/test_market_scanner_service.py` — 新增 1 条 concurrency 用例（fake FMP 每条 sleep 100ms、计时验证 250 条 < 串行的 50%）

> ⚠️ 6 文件原则上限。conftest.py 若需 fixture 复用，作为同一类型变更视作一处。

## 完成标准

| # | 标准 | 测试层级 | 工具 |
|---|------|---------|------|
| 1 | 共享 limiter：两个 FmpClient 实例 acquire 共用同一个 bucket | 单元 | pytest（fake clock） |
| 2 | Semaphore(6) 上限：6 个线程同时 `_acquire_concurrency` 后，第 7 个阻塞 | 单元 | pytest + threading |
| 3 | 全局速率上限 ≤ 5 rps：60s 窗口内最多 300 acquire（已有逻辑覆盖） | 单元 | pytest（fake clock，回归不破） |
| 4 | Scanner 并发：50 ticker × 100ms FMP mock，并发耗时 < 串行（< 50%） | 集成 | pytest + ThreadPoolExecutor |
| 5 | Scanner 并发下 hits/failed/fallback_used 聚合正确，与串行结果一致 | 集成 | pytest（同一 fake，对比串行/并发结果） |
| 6 | D040 语义保持：全部失败时不清 snapshot | 集成 | 复用现有测试，回归不破 |
| 7 | 全量回归 backend/tests/ 通过 | 全量 | pytest |
| 8 | DECISIONS.md 追加 D044 | 文档 | 人工 |

## 自检清单（Evaluator 模式使用）

- [ ] 单元测试：5 条新增 + 现有 rate-limit 测试全部通过
- [ ] 集成测试：scanner 并发 + 聚合一致性测试通过
- [ ] 全量回归：`uv run pytest` 全绿
- [ ] mypy 目标文件无新增错误
- [ ] 共享 limiter 模块级单例的生命周期清晰（首次访问时创建，进程内不变）
- [ ] Scanner 并发实现是 thread-safe（hits append、计数器、log_repo.create 都在 lock 内或线程安全）
- [ ] FastAPI 请求路径（用户触发 stock_detail / watchlist）的行为未改变
- [ ] 无新增依赖（`concurrent.futures` / `threading` 都是标准库）
- [ ] DECISIONS.md D044 已写入
- [ ] 代码无死代码、无硬编码魔法值（6 / 5 等以模块常量呈现）

## 技术决策预告（D044）

- **为什么进程级单例 limiter，而不是中间件 / 外部 redis**：单进程 SQLite 部署，进程内共享足够；不引入新基础设施
- **为什么 Semaphore(6) + bucket(5 rps) 双约束**：bucket 控速率（防长期超限），Semaphore 控并发（防 burst 在 200ms 内冲 50 个，对单端点不友好）。两者互补
- **为什么 ThreadPoolExecutor 而不是 asyncio**：FmpClient 用 sync httpx，改 async 会牵涉所有 caller；ThreadPool 改动局部
- **6 的来源**：用户实测安全边界，等价 ~5 rps × 1.2s 平均延迟

## 风险

- **测试侧污染风险**：模块级 limiter 在测试间会保留状态（tokens 数）。conftest 提供 fixture 重置或注入新 limiter，避免顺序依赖。
- **ThreadPoolExecutor 内 SystemLog 写入**：sqlite 在多线程下 default check_same_thread=True，会抛错。需要确认 log_repo.create 在 lock 内单线程串行写，或者用 main thread 收集 log 入参后批量写。

## Commit

Evaluator 全过 → `git commit -m "feat(F105-a5): shared FMP rate limiter + scanner concurrency"`
