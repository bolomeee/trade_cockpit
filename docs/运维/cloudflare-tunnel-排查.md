# Cloudflare Tunnel 部署与排查记录

> 场景：Vultr (Ubuntu) 服务器上部署本项目生产环境（`make up` 后端口 8080/8001），
> 用 Cloudflare Tunnel 把域名指向 8080，前面挂 Cloudflare Access 做登录鉴权。

## 关键结论：两种 Tunnel，不要混用

Cloudflare 有两套完全独立的建 Tunnel 方式，**互不兼容，配置入口也不同**：

| 类型 | 创建方式 | 路由配置在哪 | systemd 服务命令 |
|---|---|---|---|
| **CLI 管理型（locally-managed）** | `cloudflared tunnel create <name>` | 服务器上的 `~/.cloudflared/config.yml`（`ingress:` 规则）| `cloudflared tunnel run --config ... --credentials-file ...` |
| **Dashboard 管理型（remotely-managed）** | Zero Trust 网页 → Networks → Tunnels → Create | 网页上的 **Hostname Routes**（原名 Public Hostname）| `cloudflared tunnel run --token <token>` |

**判断当前服务器用的是哪种**：

```bash
systemctl cat cloudflared
```

看 `ExecStart` 这一行：
- 有 `--token xxx` → Dashboard 管理型，本地 `config.yml` **完全不生效**，改了也没用，路由必须去网页的 Hostname Routes 页面配。
- 有 `--config .../config.yml` → CLI 管理型，路由改本地 `config.yml`。

⚠️ 之前踩的坑：本地手改 `~/.cloudflared/config.yml` 加 ingress 规则、`route dns` 都做了，但实际 systemd 跑的是 `--token` 模式的隧道，导致改了半天不生效，还报 `Error 1033`（Tunnel 未连接——因为 DNS 指向的是另一个、已经不存在/没在跑的隧道）。

## 排查顺序（下次遇到"域名打不开/指向不对/1033"时按这个走）

1. **确认 systemd 到底在跑哪种隧道**
   ```bash
   systemctl status cloudflared
   systemctl cat cloudflared
   ```

2. **确认这个隧道在 Cloudflare 端是否存在、有没有活跃连接**
   ```bash
   cloudflared tunnel list
   cloudflared tunnel info <name-or-uuid>
   ```
   `CONNECTIONS` 列有内容（比如 `1xsin08, 1xsin11...`）才算真的连上了。如果 `tunnel info` 报 `found 0 tunnels`，说明这个 tunnel 在 Cloudflare 端已经不存在（可能被误删），DNS/本地配置指向它也没用。

3. **确认 DNS 记录指向的 tunnel ID，和第 2 步实际在跑的 tunnel ID 是否一致**
   - Cloudflare 面板 → 对应域名 Zone → DNS → Records
   - 找到 `stock.xxx` 这条 CNAME，Target 应该是 `<tunnel-id>.cfargotunnel.com`
   - 这个 `<tunnel-id>` 必须和第 2 步查到的、真正在跑的隧道 ID 一致

4. **如果是 Dashboard 管理型（`--token`），去网页配路由**
   - Zero Trust → Networks → Tunnels → 点进对应隧道 → `Hostname Routes`（原 Public Hostname）
   - Add a public hostname：填 `stock.bolomee.cc` / `stock.bolomee.com`，Service Type 选 `HTTP`，URL 填 `localhost:8080`
   - 保存后 Cloudflare 会自动帮你建好/改好对应的 CNAME 记录，不需要手动改 DNS

5. **如果是 CLI 管理型，检查 `config.yml` 语法**
   ```bash
   cat -A ~/.cloudflared/config.yml   # 看有没有 Tab 缩进、冒号后缺空格等隐藏字符问题
   cloudflared tunnel ingress validate
   ```
   常见错误：`tunnel:2c2d9357...`（冒号后没空格）会导致 YAML 解析失败，报 `mapping values are not allowed in this context`。

## 遇到过的具体问题及原因

| 现象 | 原因 | 解决 |
|---|---|---|
| `cloudflared tunnel create` 报 "requires exactly 1 argument" | 终端粘贴命令时内容重复粘连（比如网络延迟导致回显和输入交叉） | 清空当前行，一次只粘贴一条命令重新执行 |
| `route dns` 报 YAML 解析错误 | `config.yml` 里 `tunnel:` 后面缺空格 | `sed -i 's/^tunnel:/tunnel: /'` 或重新用 `cat > ... << 'EOF'` 写入 |
| `route dns` 报 "A DNS record with this name already exists" | 该 hostname 已有旧的 A/CNAME 记录冲突 | `cloudflared tunnel route dns --overwrite-dns <name> <hostname>` 直接覆盖，或去面板手动删旧记录 |
| 访问域名显示"老的内容/老的端口" | 1. `config.yml` 里域名手误写错（如 `.com` 写成本该是 `.cc`，或反之）<br>2. 浏览器本地缓存/Cookie 残留 | 1. 检查 `config.yml` 域名拼写<br>2. 清该域名的站点数据 + 强制刷新（隐身模式能正常访问基本可确认是缓存问题） |
| 访问显示 `Error 1033` | DNS 记录指向的 tunnel ID 在 Cloudflare 端已不存在，或本地 `config.yml` 配置的隧道和 systemd 实际运行的隧道（`--token` 模式）不是同一个 | 按上面"排查顺序"第 1-4 步核对，统一到实际在跑的那个隧道 |
| 建了多个同名/相似名 tunnel（如 `stock-portal` / `stock_portal` / `stock_portal_vultre`）| 多次误操作/粘贴重复执行了创建命令 | `cloudflared tunnel delete <name>`（有冲突加 `-f`）清理不用的，只留一个，且要和 DNS/systemd 实际引用的 ID 对齐 |

## 安全提醒（长期有效）

后端全站（包括 `/api/admin/*` 等会触发外部 FMP/OpenAI 调用的接口）**没有任何鉴权**。用 Tunnel 后端口不再需要对公网开放，
但真正的访问控制要靠 **Cloudflare Access**（Zero Trust → Access → Applications），针对域名配置"只允许特定邮箱登录"的策略。
没配这层的话，任何知道域名的人都能直接用你的工作台、烧你的 API 额度。
