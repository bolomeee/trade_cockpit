---
feature_id: F007-a
feature_name: 交易日志 Journal — 后端 API
status: done
created_at: 2026-04-17
completed_at: 2026-04-17
---

# Sprint Contract：F007-a

## 范围

**本次包含**：
- Repository 层：`journal_repository.py`（list with filter/limit/offset、get_by_id、create、update、delete）
- Service 层：`journal_service.py`（ticker → stock_id 映射、watchlist 校验、action 枚举校验、组装响应 DTO 含 stockName）
- Schemas：`journal.py`（`JournalEntryCreate` / `JournalEntryUpdate` / `JournalEntryOut` / `JournalListOut` / `JournalDeleteOut`，camelCase 别名）
- Router：`routers/journal.py` 四端点 `GET/POST/PUT/DELETE /api/journal`
- `main.py`：include journal router；注入 Depends 工厂
- 集成测试：`test_journal_api.py`（正/异常路径 + 字段命名验证 + 倒序/分页）

**本次排除**：
- 前端 /journal 页面与 Dialog（→ F007-b / F007-c）
- Dashboard QuickAdd 组件（→ F007-d）
- JournalEntry 表的 schema 变更（已在 F000-a 初始 migration 中创建，本次无需迁移）

## 预计修改文件（6 个）

- `backend/app/repositories/journal_repository.py`（新建）
- `backend/app/services/journal_service.py`（新建）
- `backend/app/schemas/journal.py`（新建）
- `backend/app/routers/journal.py`（新建）
- `backend/app/main.py`（修改：include router + dependency 工厂）
- `backend/tests/test_journal_api.py`（新建）

## 接口合约对齐（API-CONTRACT.md#journal）

| 端点 | 关键点 |
|------|------|
| GET /api/journal | 查询参数 ticker / action / limit(50) / offset(0)；返回 `{ items, total, limit, offset }`；按 `date DESC, id DESC` 排序 |
| POST /api/journal | 201；ticker 不在 watchlist → 404 NOT_FOUND；action 非法 → 422 VALIDATION_ERROR |
| PUT /api/journal/:id | 200；id 不存在 → 404；部分更新，字段均可选 |
| DELETE /api/journal/:id | 200 `{ id, deleted: true }`；id 不存在 → 404 |

**字段映射（snake_case ↔ camelCase）**：
- `stock.ticker → ticker`，`stock.name → stockName`
- `position_size → positionSize`，`stop_loss → stopLoss`，`target_price → targetPrice`
- `created_at → createdAt`，`updated_at → updatedAt`

**action 枚举**：BUY / SELL / ADD / REDUCE / WATCH（大写存库，API 大小写严格匹配）

## 完成标准

| # | 标准 | 层级 | 工具 |
|---|------|------|------|
| 1 | GET 空表返回 `{ items: [], total: 0, limit: 50, offset: 0 }` 200 | 集成 | TestClient |
| 2 | GET 多条时按 date 倒序 + 字段 camelCase（含 stockName） | 集成 | TestClient |
| 3 | GET 支持 ticker 过滤（返回仅该 ticker） | 集成 | TestClient |
| 4 | GET 支持 action 过滤（返回仅该 action，大写） | 集成 | TestClient |
| 5 | GET 支持 limit/offset 分页，`total` 反映过滤后总数 | 集成 | TestClient |
| 6 | POST 合法 payload → 201 + 返回完整 entry（含 stockName、createdAt） | 集成 | TestClient |
| 7 | POST ticker 不在 watchlist → 404 NOT_FOUND + error envelope | 集成 | TestClient |
| 8 | POST action 非法值 → 422 VALIDATION_ERROR | 集成 | TestClient |
| 9 | POST 缺 ticker/action/price/date → 422 VALIDATION_ERROR | 集成 | TestClient |
| 10 | PUT 部分字段更新，updated_at 刷新，未传字段保持 | 集成 | TestClient |
| 11 | PUT id 不存在 → 404 NOT_FOUND | 集成 | TestClient |
| 12 | DELETE 成功返回 `{ id, deleted: true }` 200 | 集成 | TestClient |
| 13 | DELETE id 不存在 → 404 NOT_FOUND | 集成 | TestClient |
| 14 | 全量回归 pytest 全过 | 回归 | pytest |

## Evaluator 自检清单

- [ ] 集成测试全部通过（pytest backend/tests/test_journal_api.py）
- [ ] 全量回归 pytest 全过
- [ ] 响应字段严格 camelCase，对齐 API-CONTRACT.md
- [ ] 数据库字段访问严格 snake_case，对齐 DATA-MODEL.md
- [ ] router 已在 main.py include
- [ ] 错误响应统一走 APIError → `{error: {code, message}}` envelope
- [ ] 无 print / logger.error 残留
- [ ] 函数 ≤ 50 行，无死代码，无魔法值
- [ ] DECISIONS.md 如有非显而易见决策已追加

## 开发顺序

1. 确认 DATA-MODEL 无改动（JournalEntry 字段齐备，无需迁移）
2. schemas/journal.py（Pydantic 模型 + camelCase 别名）
3. repositories/journal_repository.py（CRUD + 过滤/分页 + 排序）
4. services/journal_service.py（watchlist 校验 + DTO 组装 + APIError）
5. routers/journal.py（四端点）
6. main.py（include router + Depends 工厂）
7. tests/test_journal_api.py（14 用例）
8. 全量回归

## 风险 / 注意

- **并发 updated_at**：SQLAlchemy onupdate 依赖 flush；PUT 部分字段时需触发 flush 才更新
- **ticker 大小写**：API-CONTRACT 无明确规定；统一 upper() 处理（和 watchlist 保持一致）
- **limit 上限**：未在合约中硬性规定上限，设 200 以防滥用（不影响前端默认 50）
