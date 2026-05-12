# SESSION-HANDOFF — F214 needs_review，等待用户验收

> 生成：2026-05-08 | Branch: cockpit
> 阶段：F214 phase = `needs_review`
> 上一阶段：F214 Generator 完成，consistency-check 全清

---

## 1. 当前位置

**Feature**：F214 — ChartWidget Add to Watchlist 按钮  
**phase**：`needs_review`  
**status**：`in_progress`（验收通过后切 done）  
**本次完成的工作**：Generator 模式全部 14 步执行完毕

---

## 2. 已完成内容

### 代码变更

| 文件 | 类型 | 说明 |
|------|------|------|
| `frontend/src/workbench/widgets/ChartWidget.tsx` | 修改 | 加 CirclePlus 浮动按钮 + useMutation + isInWatchlist + 3s 错误自动清除 |
| `frontend/src/workbench/widgets/__tests__/ChartWidget.test.tsx` | 新建 | 7 个单元测试，7/7 通过 |

### 关键技术决策

- 按钮位置从 `right:8px` 调整为 `right:70px`，避开 lightweight-charts price scale（约 62px 宽）
- `preview_click` 无法触发 React 合成事件；浏览器验证使用 `dispatchEvent(MouseEvent)`

### Commits（本 session）

```
cb74957 wip(F214): update features.json + design-spec for needs_review
9783dc8 wip(F214): ChartWidget tests (7/7)
6856dbc wip(F214): ChartWidget add-to-watchlist button
```

---

## 3. 验收要点（用户手动确认）

1. **按钮位置**：News 页和 Workbench 页的 ChartWidget 右下角均有 CirclePlus 按钮（`right:70px, bottom:8px`），不遮挡 price scale 数字
2. **idle 态**：选一个不在 watchlist 的 ticker，按钮 enabled，hover 变 primary 色
3. **add 成功**：点击后 signals invalidate，ticker 加入 signals 后按钮变 disabled + opacity 0.4 + title "已在 watchlist"
4. **already-in 态**：选已在 watchlist 的 ticker（如 AAPL），按钮直接 disabled
5. **错误态**：后端返回 DUPLICATE 时按钮显示红色边框 + title 显示错误文案，3s 后恢复

---

## 4. 遗留事项

- **C5（44处合约无 features.json entry）**：已知 drift，历史 feature 合约文件未拆分 sub_sprints，用户选择跳过
- **C4（F205/F207 iteration_history 缺失）**：同上，历史积累，跳过

---

## 5. 下一步

验收通过后：
1. 将 F214 `status` 改为 `done`，`phase` 改为 `done`
2. 调用 `project-commiter` 发版（v2.2.0 或按项目规划）
3. 清理 MCD 测试数据（本 session 添加 MCD 到 watchlist 做手验）
