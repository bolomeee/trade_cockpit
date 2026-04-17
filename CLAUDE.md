# CLAUDE.md
> 更新：2026-04-16 | 阶段：project-init ✅ → system-design (next)
> ⚠️ 每次 session 开始必读。细节在各文档内，不在此重复。

## 项目
**MA150 Tracker**：个人美股投资辅助 app，围绕 150 日均线自动识别交易信号

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

## 操作前必须引用
- 改数据库 → DATA-MODEL.md，有变更先更新再动代码
- 改/增 API → API-CONTRACT.md，有变更先更新再动代码
- 写前端 → design-spec.md + API-CONTRACT.md
- 技术决策 → 完成后追加 DECISIONS.md

## 开发时文档查询（强制）
使用以下技术时，必须先通过 context7 MCP 查询最新文档，不得凭记忆编写：
| 技术 | context7 library ID |
|------|-------------------|
| Tailwind CSS v4 | `/websites/tailwindcss` |
| shadcn/ui | `/shadcn-ui/ui` |
| lightweight-charts | `/tradingview/lightweight-charts` |
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

## Context 不足
立即生成 SESSION-HANDOFF.md，不简化，不跳步
