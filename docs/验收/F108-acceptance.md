# 验收记录：F108 /fundamentals /pullbacks 放开到任意 ticker

**日期**：2026-04-22
**Feature**：F108（反向补契约）
**验收人**：用户
**结论**：✅ 通过

---

## 技术测试（Evaluator 已完成）

| 范围 | 结果 |
|------|------|
| F108 集成测试 test_stock_detail.py | 30/30 通过 |
| 全量回归 pytest | 280/280 通过 |

---

## 用户验收确认

| 检查项 | 结果 |
|-------|------|
| Scanner 点非 watchlist ticker → Fundamentals Tab 不报 404 | ✅ |
| Scanner 点非 watchlist ticker → Pullbacks Tab 不报 404（显示空态）| ✅ |
| 已在 watchlist 的 ticker → Fundamentals / Pullbacks 行为与之前一致 | ✅ |

---

## 交付物

| 文件 | 说明 |
|------|------|
| `backend/app/services/stock_detail_service.py` | get_fundamentals / get_pullbacks 移除 _resolve_active_stock |
| `backend/tests/test_stock_detail.py` | 修复 2 个旧测试 + 新增 5 个测试用例 |
| `docs/系统设计/API-CONTRACT.md` | fundamentals / pullbacks 404 语义更新 |
| `docs/系统设计/DECISIONS.md` | 追加 D047（D041 on-demand 语义延伸） |

---

## 已知问题 / 后续

- Pullbacks 对非 watchlist ticker 返回空列表（不做 FMP on-demand 计算），空态文案如需差异化留给后续 UX 迭代
