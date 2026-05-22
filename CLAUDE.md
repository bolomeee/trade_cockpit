# CLAUDE.md
> 更新：2026-04-18 | 阶段：v1.0.0 ✅ → v1.1.0 Workbench 重构
> ⚠️ 每次 session 开始必读。细节在各文档内，不在此重复。

## 项目
**MA150 Tracker → Workbench**：个人投资工作台，单页面承载多个可拖拽 widget（持仓 / 走势 / 基本面 / 新闻 / 扫描 / AI 观点 …）。v1.0.0 的 SMA150 Dashboard / Journal / Logs 作为首批 widget 内嵌在 Workbench 中。

核心原则：**加新功能 = 加一个 widget + 一个后端 endpoint + 注册一行**，不动布局、不影响现有功能。

## 文档导航
| 文档 | 路径 |
|------|------|
| 产品需求 | docs/需求/PRD.md |
| 功能调度 | docs/需求/features.json |
| 架构（技术约束） | docs/系统设计/ARCHITECTURE.md |
| 数据模型（字段权威） | docs/系统设计/DATA-MODEL.md |
| API 合约 | docs/系统设计/API-CONTRACT.md |
| 技术决策 | docs/系统设计/DECISIONS.md |
| 视觉规格 | docs/设计/design-spec.md |
| 进度日志 | claude-progress.txt |

## 加新 Widget 的标准流程
1. 后端（若需要新数据）：`app/routers/` 新增 router → service → repository，遵循既有分层
2. 前端：
   - 写 widget 组件（在 `src/workbench/widgets/`），复用现有 `components/features/*`
   - 在 `src/workbench/WidgetRegistry.ts` 注册一行 manifest
3. 完成。不需要改 Workbench 框架、不需要改其他 widget、不需要改数据库。

## 操作前必须引用
- 改数据库 → DATA-MODEL.md，有变更先更新再动代码
- 改/增 API → API-CONTRACT.md，有变更先更新再动代码
- 写前端 widget → WidgetRegistry.ts + design-spec.md + API-CONTRACT.md
- 技术决策 → 完成后追加 DECISIONS.md
- 端口/URL → ARCHITECTURE.md「运行端口」表（**后端永远 8001**；前端 dev=5173 / 发版 Nginx=8080；不要把后端写成 8080）

## 开发时文档查询（强制）
使用以下技术时，必须先通过 context7 MCP 查询最新文档，不得凭记忆编写：
| 技术 | context7 library ID |
|------|-------------------|
| Tailwind CSS v4 | `/websites/tailwindcss` |
| shadcn/ui | `/shadcn-ui/ui` |
| lightweight-charts | `/tradingview/lightweight-charts` |
| react-grid-layout | `/react-grid-layout/react-grid-layout` |
| zustand | `/pmndrs/zustand` |
| FastAPI | `/websites/fastapi_tiangolo` |
| SQLAlchemy 2.0 | `/websites/sqlalchemy_en_20` |
| Polygon.io (Massive) Python Client | `/massive-com/client-python` |

## 必须停止并报告
- 文档之间存在矛盾
- 需要做非显而易见的技术决策
- 架构变更影响超过 2 个文件
- 引入新外部依赖或付费服务

## 测试门禁
in_progress → testing → needs_review，不得跳过 testing 阶段

## 歧义优先级
DATA-MODEL > API-CONTRACT > design-spec > 写"待决策"通知用户

## Phase 结束
每个开发阶段（phase）完成后，必须：
1. 生成 `SESSION-HANDOFF.md`，不简化，不跳步，包含：已完成内容、当前状态、下一步任务、未决事项
2. 告知用户："**Phase 已完成，SESSION-HANDOFF.md 已更新，建议开启新 session 继续下一阶段。**"

## Context 不足
立即生成 SESSION-HANDOFF.md，不简化，不跳步
