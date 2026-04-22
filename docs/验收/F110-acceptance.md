# 验收记录：F110 Watchlist CSV 导入/导出

**日期**：2026-04-22
**Feature**：F110（含 F110-a 后端 + F110-b 前端）
**验收人**：用户
**结论**：✅ 通过

---

## 技术测试（Evaluator 已完成）

| 范围 | 结果 |
|------|------|
| F110-a 后端 TB1–TB9 | 9/9 通过 |
| 全量回归 pytest | 273/275（2 个为 F108 预先存在失败，与 F110 无关） |
| pnpm tsc --noEmit | 无报错 |
| 预览截图验证 | Dialog、Tabs、Import/Download 按钮均正常渲染 |

---

## 用户验收确认

| 检查项 | 结果 |
|-------|------|
| Upload/Download 图标按钮位于搜索栏右侧 | ✅ |
| 点击 Upload 弹出导入 Dialog（文件/文本 Tabs）| ✅ |
| 文本粘贴 → 新 ticker 导入 → 三桶结果展示 | ✅ |
| 重复 ticker 落入 skippedDuplicate | ✅ |
| 无效 ticker 落入 notFound | ✅ |
| 大小写自动规范化 | ✅ |
| Download → 下载 watchlist-YYYY-MM-DD.csv | ✅ |
| 空输入时 Import 按钮 disabled | ✅ |
| Dialog 关闭后状态重置 | ✅ |
| 含标题行 CSV 自动跳过 | ✅ |

---

## 交付物

| 文件 | 说明 |
|------|------|
| `backend/app/schemas/watchlist.py` | BulkAddRequest / BulkAddResult schema |
| `backend/app/services/watchlist_service.py` | bulk_add_stocks() |
| `backend/app/routers/watchlist.py` | POST /api/watchlist/bulk |
| `backend/tests/test_watchlist_api.py` | TB1–TB9 集成测试 |
| `frontend/src/components/features/dashboard/CsvImportDialog.tsx` | 导入 Dialog |
| `frontend/src/workbench/widgets/WatchlistWidget.tsx` | Upload/Download 入口 |
| `docs/系统设计/API-CONTRACT.md` | bulk endpoint 文档 |
| `docs/系统设计/DECISIONS.md` | D-F110a-1 快速失败策略 |

---

## 已知问题 / 后续

- F108（fundamentals/pullbacks 放开）有 2 个测试待修复，与 F110 无关
- 导出功能基于前端已有数据（无后端接口），若未来需要服务端导出可扩展
