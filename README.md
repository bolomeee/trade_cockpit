# Stock Portal

个人投资工作台：单页面承载可拖拽 widget（持仓、走势、基本面、新闻、扫描和 AI 观点）。版本变化见 [CHANGELOG.md](CHANGELOG.md)。

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | React + TypeScript + Vite + Tailwind CSS |
| 后端 | FastAPI + Python + SQLAlchemy + APScheduler |
| 数据 | SQLite（Docker bind mount） |
| 运行环境 | Docker Compose（开发、测试、生产的唯一受支持入口） |

## 前置条件

只需安装 Docker Desktop（含 Docker Compose）。不需要在本机安装或维护 Node、npm、pnpm、Python 或 uv。

首次运行时复制环境变量模板；外部数据与 AI 功能按需填写密钥。

```bash
cp .env.example .env
```

`.env` 不会提交。注释必须单独成行，不要写成 `KEY= # comment`，否则 Compose 会把注释当作值的一部分。

## 生产模式

```bash
make up
```

| 服务 | 地址 |
|---|---|
| 前端 Workbench | http://localhost:8080 |
| 后端 API | http://localhost:8001 |
| OpenAPI Docs | http://localhost:8001/docs |

容器内后端端口固定为 `8000`，Compose 统一发布为宿主机 `8001`。数据库持久化在 `./backend/data`。

```bash
make logs       # 查看全部服务日志
make verify     # 构建、等待 healthcheck、验证两个入口
make down       # 停止并移除容器（保留 bind-mounted 数据）
```

## 开发与测试

开发模式运行容器化 Vite 和 FastAPI reload：

```bash
make dev
```

`make dev` 会停止生产 profile，因为两者都按约定使用宿主机后端端口 `8001`；回到生产模式时运行 `make up`。

访问前端 http://localhost:5173；其 `/api` 请求会在 Docker 网络中代理至开发后端。开发后端仍发布到 http://localhost:8001，使用独立的 `backend/data/dev.db`，且默认关闭 scheduler。

```bash
make test       # 后端 pytest + 前端 Vitest
make lint       # 后端 Ruff + 前端 ESLint
make build      # 构建生产镜像
make config     # 校验 Compose 解析结果
```

所有命令使用镜像中锁定的 Python/uv/Node/pnpm 版本。依赖升级必须同步更新锁文件和容器工具链版本，而不是依赖开发机全局安装。

## 配置原则

后端配置优先级为：进程环境变量（Compose）> 根目录 `.env` > 明确的 development 默认值。生产环境必须显式提供 `DATABASE_URL`；Compose 已固定为容器内的 `/app/data/prod.db`。因此从任意工作目录启动都不会意外创建或使用不同的 SQLite 数据库。

## 项目文档

| 文档 | 路径 |
|---|---|
| 项目总纲 | [CLAUDE.md](CLAUDE.md) |
| 产品需求 | [docs/需求/PRD.md](docs/需求/PRD.md) |
| 架构 | [docs/系统设计/ARCHITECTURE.md](docs/系统设计/ARCHITECTURE.md) |
| 数据模型 | [docs/系统设计/DATA-MODEL.md](docs/系统设计/DATA-MODEL.md) |
| API 合约 | [docs/系统设计/API-CONTRACT.md](docs/系统设计/API-CONTRACT.md) |
| 技术决策 | [docs/系统设计/DECISIONS.md](docs/系统设计/DECISIONS.md) |

## License

Private / Personal Use.
