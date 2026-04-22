# Sprint Contract：F107-b1 后端 shares_float 数据链路

> 日期：2026-04-22 | 状态：草案
> 引用文档：
>   Plan：`~/.claude/plans/tingly-jumping-pebble.md`（approved）
>   DATA-MODEL.md#Stock | API-CONTRACT.md#GET /api/stocks/{ticker}/chart | DECISIONS.md（D049–D052 待写入）
>   前置：F107 done（3b923a0）
>   后续：F107-b2（前端 Vol/Float 显示，依赖本 sprint）

---

## 本次实现范围

**包含**：
1. FMP 客户端新增 `get_company_profile(ticker)`，走 `/stable/profile`（实际路径 Context7 核准），提取 `sharesFloat || floatShares`，走既有 D044 rate limiter
2. Stock 表新增两列：`shares_float: int | None`、`shares_float_refreshed_at: datetime | None`（Alembic 004，nullable 默认 null，在线迁移安全）
3. `stock_detail_service.get_chart()` 末尾做 DB-first 缓存读 + 24h TTL miss 回源 FMP，结果写回 DB
4. `/api/stocks/{ticker}/chart` 响应顶层新增 `sharesFloat: int | null`（camelCase 别名，Pydantic schema 侧）
5. 文档同步：DATA-MODEL（Stock 新字段）、API-CONTRACT（/chart 响应）、DECISIONS（D049–D052）、features.json（补 F107-b / b1 / b2 三条目）

**明确排除（本次不做）**：
- 前端 ChartWidget 的比率显示与 crosshair 联动（F107-b2）
- 历史 shares_float 追踪（plan 已决策：所有 bar 用当前 float，design-spec 标"近似"）
- 主动批量预热 shares_float（按需懒加载即可，首次 /chart 调用后才有缓存）
- split/ipo 场景下的主动失效（D049 候选，待有 bug 再议）

---

## 预计修改文件（5 业务 + 3 文档，在 6 文件上限内）

| # | 文件路径 | 改动类型 | 说明 |
|---|---------|---------|------|
| 1 | `backend/app/external/fmp_client.py` | 修改 | 新增 `get_company_profile(ticker) -> dict`；复用 `_request` / rate limiter；双字段名兜底 `sharesFloat or floatShares` |
| 2 | `backend/app/models/stock.py` | 修改 | Stock ORM 加 `shares_float: Mapped[int \| None]`、`shares_float_refreshed_at: Mapped[datetime \| None]` |
| 3 | `backend/alembic/versions/004_f107b1_shares_float.py` | 新建 | `batch_alter_table` 加 2 列，均 nullable；downgrade 可回退 |
| 4 | `backend/app/services/stock_detail_service.py` | 修改 | `get_chart` 末尾：读 Stock 行，若 `shares_float_refreshed_at` 为空或 > 24h → 调 `fmp.get_company_profile`，写回 `shares_float` + 时间戳；payload 注入 `shares_float` |
| 5 | `backend/app/schemas/stock_detail.py` | 修改 | `ChartData`（或对应 response model）加 `shares_float: int \| None = None`，camelCase 别名 `sharesFloat` |

**文档（不计入 6 文件限制）**：
- `docs/系统设计/DATA-MODEL.md` — Stock 表追加两字段
- `docs/系统设计/API-CONTRACT.md` — `/stocks/{ticker}/chart` 响应补 `sharesFloat`
- `docs/系统设计/DECISIONS.md` — D049（/chart 携带 sharesFloat）、D050（24h TTL DB 缓存）、D051（FMP /profile 双字段名兜底）、D052（历史 bar 用当前 float）
- `docs/需求/features.json` — 补登 F107-b / F107-b1 / F107-b2（priority P1，deps F107）

👤 用户确认文件列表合理后，方可进入开发。

---

## 可测试的完成标准

| # | 标准描述 | 测试层级 | 工具 |
|---|---------|---------|------|
| 1 | `get_company_profile("AAPL")` 成功解出 sharesFloat，FMP 只返回 `floatShares`（无 `sharesFloat`）也能拿到值 | 单元 | pytest + httpx mock |
| 2 | FMP 返回空数组 / 字段缺失 / 404 → `get_company_profile` 返回 None，不抛；`/chart` 仍 200、`sharesFloat=null` | 单元 | pytest + httpx mock |
| 3 | DB 中 `shares_float_refreshed_at` 在 24h 内 → `get_chart` 不调 FMP（mock 断言 0 次调用）；超过 24h → 调一次并写回 | 单元 | pytest + mock |
| 4 | Alembic `upgrade head → downgrade -1 → upgrade head` 三次往返，无错误；schema 快照一致 | 集成 | pytest test_schema |
| 5 | docker compose E2E：`curl /api/stocks/AAPL/chart` 返回 `sharesFloat` 非 null 的 int；再次调用日志确认未打 FMP profile | E2E | curl + docker logs |
| 6 | 全量回归 ≥ 252/254（F108 预先 2 失败不阻塞，需在 Evaluator 报告标注） | 回归 | pytest |

---

## Evaluator 自检清单

开发完成后，Evaluator 模式逐条检查：

- [ ] 单元测试全部通过（`uv run pytest backend/tests/test_fmp_client.py backend/tests/test_stock_detail.py backend/tests/test_schema.py -v`）
- [ ] Alembic 三往返绿
- [ ] 全量回归 ≥ 252/254（预先失败标注）
- [ ] docker compose E2E：`/chart` 返回 sharesFloat，第二次调用不打 FMP
- [ ] API 响应格式符合 API-CONTRACT.md（camelCase `sharesFloat`）
- [ ] 数据库字段命名符合 DATA-MODEL.md（snake_case `shares_float` / `shares_float_refreshed_at`）
- [ ] 无 print / console 调试遗留；无新 lint warning
- [ ] 本次技术决策 D049–D052 已写入 DECISIONS.md
- [ ] features.json 已补 F107-b / b1 / b2 条目；b1 phase=testing→needs_review
- [ ] 无硬编码：24h TTL 提为常量（如 `_SHARES_FLOAT_TTL = timedelta(hours=24)`）；FMP profile 端点提为 `FMP_EP_PROFILE` 模块常量
- [ ] `get_company_profile` 走 `_rate_limited` 装饰器（与其他 FMP 方法一致，R6）
- [ ] Context7 已核验 FMP `/stable/profile` 响应字段（规则 9：新端点用法）

> 注：按 D048 降级，前端测试门禁延至 v1.4；b1 为纯后端，走完整 pytest + docker E2E。

---

## 风险与缓解（从 plan 继承）

| # | 风险 | 缓解 |
|---|------|------|
| R1 | FMP `/stable/profile` 实际路径与字段名不确定（plan 原写 `/api/v3/` 已与代码 `/stable/` 不一致） | Generator 第一步调 Context7 核验路径 + 字段名；单元测试用真实 fixture |
| R2 | 小盘 / ETF 无 float | 返回 null，DB 写 `refreshed_at` 避免反复请求；UI 侧 b2 显 `—` |
| R3 | 生产迁移 add column 停机 | 两列均 nullable 默认 null，在线安全 |
| R6 | 新方法突破共享 rate bucket | `get_company_profile` 必须走 `_rate_limited`；Evaluator 清单勾选 |

---

👤 用户确认本 Contract 后，开发开始（进入 Generator 模式，顺序：features.json 登记 → Context7 核验 FMP → 文档更新 → migration → model → schema → fmp_client → service → 测试 → Evaluator）。

---

## Evaluator 回写（2026-04-22）

**偏离**：合约原写 FMP `/stable/profile`；docker E2E 实测该端点在 Starter 档位不返回 `floatShares` / `sharesFloat` 任一字段（AAPL 响应均为 null）。

**实际实现**：改走 `/stable/shares-float` 专用端点，字段 `floatShares` 以整数返回。方法重命名 `get_company_profile` → `get_shares_float`；常量 `FMP_EP_PROFILE` → `FMP_EP_SHARES_FLOAT`；FakeFMP 属性 `profile_*` → `shares_float_*`。`sharesFloat` 兜底分支保留。

**回写范围**：D051 修订 / API-CONTRACT.md / DATA-MODEL.md / alembic 004 docstring / 单元测试 fixture 形态。

**E2E 验证**：AAPL `/chart` 返回 `sharesFloat: 14664480994`（FMP 实际值），第二次调用命中 Stock 表 24h TTL 缓存不再打 FMP。
