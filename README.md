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

### 端口与访问方式

| 用途 | 正确地址 | 说明 |
|---|---|---|
| 生产网页 | `http://localhost:8080` | Nginx 托管的 React 页面；日常在浏览器中使用此地址。 |
| 生产 API / 运维接口 | `http://localhost:8001` | FastAPI 的宿主机端口；脚本、OpenAPI 和手动刷新任务使用此地址。 |
| 开发网页 | `http://localhost:5173` | 仅在执行 `make dev` 后使用；对应独立的开发数据库。 |
| 容器内后端 | `http://backend:8000` | 仅 Docker 网络内部使用，不能作为宿主机命令地址。 |

`8080` 会将普通 `/api/*` 请求代理到生产后端，适合页面访问；但 Nginx 对耗时请求有超时限制。**所有手动管理刷新命令都应直接请求 `8001`，不要通过 `8080`，也不要在生产环境使用 `5173`。**

### Pool Builder 数据刷新与故障恢复

Pool Builder 右上角的刷新按钮只会重新读取已经生成的候选池，不会抓取市场数据或重建缓存。正常情况下，生产调度器会按 UTC 自动执行：

| 任务 | 默认时间（UTC） | 北京时间 | 作用 |
|---|---:|---:|---|
| Universe refresh | 每周一 05:00 | 周一 13:00 | 更新可扫描股票池。 |
| Market scanner | 工作日 06:15 | 工作日 14:15 | 扫描 Universe，生成趋势 / 突破快照。 |
| Pool cache rebuild | 工作日 06:30 | 工作日 14:30 | 计算 RS 与基本面缓存，供 Pool Builder 展示。 |

首次启动、数据库恢复、或上述任务失败时，按以下顺序手动补跑；每个命令必须等待返回 JSON 后再执行下一条：

```bash
# 1. 更新 Universe
curl -sS -X POST http://localhost:8001/api/admin/refresh-universe

# 2. 扫描趋势 / 突破信号（可能需要数分钟）
curl -sS -X POST http://localhost:8001/api/admin/refresh-scanner

# 3. 重建 Pool Builder 的 RS 与基本面缓存（可能需要数分钟）
curl -sS -X POST http://localhost:8001/api/admin/refresh-pool-cache
```

第 3 步成功后刷新 `http://localhost:8080/cockpit` 页面。若命令返回 `504 Gateway Time-out`，通常表示请求误经 `8080` 的 Nginx；改用上面的 `8001` 地址重试。可用以下接口检查刷新链条：

```bash
curl -sS http://localhost:8001/api/refresh-health
curl -sS http://localhost:8001/api/cockpit/pool
```

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
