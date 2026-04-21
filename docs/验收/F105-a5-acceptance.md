# 验收记录：F105-a5 FMP 共享限流器 + Scanner 并发

**日期**：2026-04-21
**Sprint Contract**：docs/开发/sprint-contracts/F105-a5-contract.md
**Commit**：3c27a2e

## 决策收口

- 共享限流器：`_FmpRateLimiter`（token bucket + Semaphore(6)），通过 `default_rate_limiter()` 模块级单例注入所有生产 `FmpClient` 实例
- Scanner：`ThreadPoolExecutor(max_workers=6)`，主线程串行写 SystemLog（绕开 SQLite single-writer）
- OK 日志追加 `duration_s=X.XX workers=6`
- D044 已写入 DECISIONS.md

## 技术门禁

- ✅ backend/tests/ 全量回归 234/234（较 F105-c 后基线 227 增加 7 条新测试）
- ✅ mypy 目标文件：本次改动引入 0 新错误（2 条 SQLAlchemy `Column[str]→str` 遗留，非本 Sprint）
- ✅ 无新增外部依赖（`concurrent.futures` / `threading` 标准库）

## 验收条目

| # | 标准 | 结论 |
|---|------|------|
| 1 | 共享 limiter：两 FmpClient 共耗同一 bucket | ✅ test_shared_limiter_depletes_across_instances |
| 2 | Semaphore(6) 上限：第 7 个阻塞 | ✅ test_concurrency_semaphore_caps_inflight_at_limit |
| 3 | 异常路径释放 semaphore | ✅ test_semaphore_released_even_on_http_error |
| 4 | default_rate_limiter() 单例语义 | ✅ test_default_rate_limiter_is_process_singleton |
| 5 | Scanner 并发加速（12 × 200ms < 1.2s） | ✅ test_scan_runs_workers_in_parallel（peak=6） |
| 6 | OK 日志含 duration_s / workers | ✅ test_scan_ok_log_includes_duration_and_workers |
| 7 | D040 语义在并发下保留（全失败不清 snapshot） | ✅ test_scan_preserves_d040_semantics_under_concurrency |
| 8 | 现有 rate-limit 测试不破 | ✅ 40/40（test_fmp_client.py） |

## 过程备注

- 抽取 `_FmpRateLimiter` 后，`FmpClient.__init__` 新增 `rate_limiter` 可选参数：生产注入进程级单例；测试默认每实例私有 limiter（保持原有测试隔离语义，40 条现有测试 0 改动即通过）。
- per-worker 日志采集改为在 worker 内填充 `pending_logs` 列表，主线程聚合后串行写入 `SystemLogRepository`，避开 SQLite `check_same_thread=True` 风险；WARN-once 去重语义在主线程单点判定保留。
- `SCAN_WORKER_COUNT=6` 与 `_FmpRateLimiter.CONCURRENCY_LIMIT=6` 双重约束：即便 pool 扩容，semaphore 仍兜底。
- mypy 发现 `row.ticker` 的 `Column[str]` 问题沿用 F105-a4 的 `str(...)` 防御模式。

## 结论

验收通过，F105-a5 phase → done。
