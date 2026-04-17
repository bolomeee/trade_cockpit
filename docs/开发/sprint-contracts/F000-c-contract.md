---
feature_id: F000-c
name: Docker Compose + Polygon Client
status: contract_agreed
drafted_at: 2026-04-17
confirmed_at: 2026-04-17
scaffolding_exempt: true  # D010 脚手架 6 文件豁免
---

# F000-c Sprint Contract

## 1. 实现范围

### 包含
- `docker-compose.yml`：frontend + backend 两服务，共享 network，backend SQLite 数据通过 volume 挂载持久化
- `backend/Dockerfile`：Python 3.12-slim + uv 安装依赖，生产以 uvicorn 启动
- `frontend/Dockerfile`：多阶段构建（Node 20 `pnpm build` → `nginx:alpine` 托管 `dist/`）
- `frontend/nginx.conf`：`/api/*` 反代到 `backend:8000`；其余走 SPA，fallback 到 `index.html`
- `backend/app/external/polygon_client.py`：封装 `massive.RESTClient`，内建 5 次/分钟 token-bucket rate limiter
- 对外方法：
  - `search_tickers(query: str, limit: int = 10)` → `list_tickers(search=q, market="stocks", active=True, limit=...)`
  - `get_previous_close(ticker: str)` → `get_previous_close_agg(ticker, adjusted=True)`
  - `get_daily_aggs(ticker, from_date, to_date)` → `list_aggs(ticker, 1, "day", from_=..., to=..., adjusted=True)`
- 单元测试 `tests/test_polygon_client.py`：
  - rate limit 第 6 次阻塞（mock 时间源）
  - 三个封装方法正确转发参数（mock RESTClient）
  - 缺失 API key 时抛 `RuntimeError`

### 不包含
- Polygon 真实网络联调（F003）
- APScheduler 调度（F003）
- 生产 HTTPS / 证书
- CI / 镜像推送

## 2. 预计修改文件（共 12 个，D010 豁免生效）

### 新建
- `backend/app/external/__init__.py`
- `backend/app/external/polygon_client.py`
- `backend/tests/test_polygon_client.py`
- `backend/Dockerfile`
- `backend/.dockerignore`
- `frontend/Dockerfile`
- `frontend/.dockerignore`
- `frontend/nginx.conf`
- `docker-compose.yml`
- `.env`（项目根，gitignored，含真实 POLYGON_API_KEY）
- `.env.example`（项目根，供 docker-compose 参考）

### 修改
- `backend/pyproject.toml`（+ `massive>=2.5.0`）
- `backend/uv.lock`（自动）

## 3. 关键技术约定

### 3.1 包选型
- PyPI：`massive>=2.5.0`（Polygon.io 官方改名后包，D013）
- 导入：`from massive import RESTClient`
- 环境变量保留 `POLYGON_API_KEY`（手动读取后显式传入 `RESTClient(api_key=...)`），不采用 `MASSIVE_API_KEY` 自动机制 — 避免跨项目迁移成本

### 3.2 Rate Limit 设计（D014）
Token bucket：
- 容量 5
- 补充速率：每 60/5 = 12 秒 1 个 token
- 调用前 `_acquire()`：有 token 立即扣 1 并放行；无 token `time.sleep(next_refill - now)`
- `threading.Lock` 保证并发安全

### 3.3 端口映射
- `frontend: 8080:80`（本机 80 占用）
- `backend` 不对外暴露端口，仅内部网络由 nginx 反代

### 3.4 nginx.conf 核心
```nginx
location /api/ {
  proxy_pass http://backend:8000/;
  proxy_set_header Host $host;
  proxy_set_header X-Real-IP $remote_addr;
}
location / {
  try_files $uri $uri/ /index.html;
}
```

### 3.5 Volume
- `./backend/data:/app/data` 存 `prod.db`
- docker 环境下 `DATABASE_URL=sqlite:////app/data/prod.db`

## 4. 完成标准（Evaluator 测试用例）

| # | 测试描述 | 层级 | 工具 |
|---|---------|------|------|
| 1 | `docker compose build` 无错误 | 构建 | docker |
| 2 | `docker compose up -d` 两容器均 running | 手动 | docker ps |
| 3 | `curl http://localhost:8080/` 返回 200 且含 SPA HTML | 手动 | curl |
| 4 | `curl http://localhost:8080/api/health` 返回 `{"status":"ok"}` | 手动 | curl |
| 5 | 容器重启后 `prod.db` 仍存在（volume 持久化） | 手动 | docker exec |
| 6 | `PolygonClient().search_tickers("AAPL")` 正确调用 `list_tickers(search="AAPL", ...)` | 单元 | pytest + mock |
| 7 | `PolygonClient().get_previous_close("AAPL")` 正确调用 `get_previous_close_agg` | 单元 | pytest + mock |
| 8 | `PolygonClient().get_daily_aggs("AAPL", "2026-01-01", "2026-04-17")` 参数正确 | 单元 | pytest + mock |
| 9 | 连续 6 次调用，第 6 次在窗口内等待（mock time 断言 sleep 被调用） | 单元 | pytest + mock |
| 10 | `POLYGON_API_KEY` 未设置时实例化抛 `RuntimeError` | 单元 | pytest |
| 11 | 回归：后端原 11 个测试全部通过 | 全量 | pytest |

## 5. Evaluator 自检清单

- [ ] `docker compose build` 无错误
- [ ] `docker compose up -d` 两服务 running ≥ 30s 不退出
- [ ] `curl localhost:8080/` 200
- [ ] `curl localhost:8080/api/health` 200 + `{"status":"ok"}`
- [ ] `cd backend && uv run pytest` 全部通过（新增 ≥ 5 + 原 11 = ≥ 16）
- [ ] `.env` 未被 git tracked（`git check-ignore .env` 返回 0）
- [ ] 无硬编码 magic number（rate limit 常量抽为 class 属性）
- [ ] DECISIONS 追加 D013 + D014

## 6. 风险

- R1：massive 库 2.5.x API 与早期 polygon-api-client 差异 → 开发时 `uv run python -c "from massive import RESTClient; help(RESTClient)"` 验证方法签名
- R2：Docker 首次构建慢（Node + Python 镜像）→ 可接受
- R3：若 `massive` PyPI 在 docker 内部网络无法安装 → 退回 `polygon-api-client` 并记录
