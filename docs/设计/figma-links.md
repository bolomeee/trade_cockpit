# Figma 设计稿索引

> 最后更新：2026-04-17 | 维护者：design-bridge skill
> 所有页面设计稿的权威入口。design-spec.md / component-plan.md / data-mapping.md 中提到的 Figma 节点均以此文档为锚点。

---

## 页面级设计文件

| 序号 | 页面 | 路由 | Figma 链接 | 关联 Feature |
|------|------|------|-----------|-------------|
| 1 | Dashboard（首页） | `/` | https://www.figma.com/design/Wk5znwTAjGZXPeDDKLtVSb/stock_portal?node-id=0-1&m=dev | F001, F002, F003, F004, F005, F006 |
| 2 | Trade Journal（交易日志） | `/journal` | https://www.figma.com/design/uoZCLcuEglJh87mfP15C9o/trade_journal?node-id=0-1&m=dev | F007 |
| 3 | System Logs（系统日志） | `/logs` | https://www.figma.com/design/ReibtcedQZ2Zynr5goIUGG/system_logs?node-id=0-1&m=dev | F008 |

---

## File Key 速查

Figma MCP 读取时使用的 `fileKey`：

| 页面 | fileKey |
|------|---------|
| Dashboard | `Wk5znwTAjGZXPeDDKLtVSb` |
| Trade Journal | `uoZCLcuEglJh87mfP15C9o` |
| System Logs | `ReibtcedQZ2Zynr5goIUGG` |

---

## Figma 文件覆盖关系说明

**Dashboard 文件（stock_portal）包含**：
- 首页主视图（SignalBoard、Market Overview、Trade Journal Widget、Refresh 按钮）
- 个股 150MA 详情 Modal（F005，Dashboard 弹窗，无独立路由）
- Add Stock 快捷表单（F001 的搜索+添加 UI）

**Trade Journal 文件**：
- 独立 `/journal` 页面（完整日志列表 + 详细编辑表单）

**System Logs 文件**：
- 独立 `/logs` 页面（日志表格 + 级别过滤器）
