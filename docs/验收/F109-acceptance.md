# 验收记录：F109 Widget UI 规范落实

**日期**：2026-04-22
**Feature**：F109-a + F109-b（反向补契约）
**验收人**：用户
**结论**：✅ 通过

---

## 技术测试（Evaluator 已完成）

| 范围 | 结果 |
|------|------|
| pnpm tsc --noEmit | 无报错 |
| pnpm build | 通过（202ms） |
| 硬编码值扩散检查 | 仅出现在 widget 外壳层 |
| 顺带修复 CsvImportDialog.tsx TS 过度窄化 | 已修复 |

---

## 用户验收确认

| 检查项 | 结果 |
|-------|------|
| 所有 widget title bar 底色统一 `#ebf2fa` | ✅ |
| Widget 内容区紧贴 Shell 上/左边缘（-5px 偏移） | ✅ |
| AddStockCard 搜索框 pill 形、10px 粗体 | ✅ |
| TopNav 品牌字「MA150 Tracker」可点击回首页 | ✅ |
| TopNav 右侧顺序：Last refresh → Refresh → ResetLayout（首页） | ✅ |
| MarketOverviewBar 无浮层按钮残留 | ✅ |
| `/journal` / `/logs` 页面不显示 ResetLayoutButton | ✅ |
| 搜索框 Popover + 添加功能回归正常 | ✅ |

---

## 交付物

| 文件 | 说明 |
|------|------|
| `frontend/src/workbench/WidgetShell.tsx` | title bar `#ebf2fa` 底色 |
| `frontend/src/workbench/widgets/WatchlistWidget.tsx` | `gap-1` + `-5px` 偏移 |
| `frontend/src/workbench/widgets/PullbackWidget.tsx` | `-5px` 偏移 |
| `frontend/src/workbench/widgets/FundamentalsWidget.tsx` | `-5px` 偏移 |
| `frontend/src/workbench/widgets/QuickAddWidget.tsx` | `-5px` 偏移 |
| `frontend/src/App.tsx` | 移除 ResetLayoutButton 覆盖层 |
| `frontend/src/components/features/topnav/TopNav.tsx` | NavLink 品牌字 + ResetLayoutButton 右侧挂载 |
| `frontend/src/components/features/dashboard/AddStockCard.tsx` | pill 样式简化 |
| `frontend/src/components/features/dashboard/CsvImportDialog.tsx` | 修复 TS 过度窄化（F110 遗留） |
| `docs/设计/design-spec.md` | TopNav v1.3 备案 + AddStockCard 搜索框小节 |
| `docs/系统设计/DECISIONS.md` | D046 widget 硬编码规范 |
