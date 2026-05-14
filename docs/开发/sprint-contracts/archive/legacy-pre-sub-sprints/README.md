# Legacy Sprint Contracts — Pre-`sub_sprints` Convention

> 归档日期：2026-05-13
> 归档原因：consistency-check C5 drift 清理
> 触发：v1.9 发版前 project-commiter strict 闸门拒绝（C5 ×45 + F111 谜题）

---

## 为什么归档

`feature-dev` 套件早期对一个 feature 的多 sprint 拆分采用**多合约文件**而非 `features.json` 中的 `sub_sprints` 字段（约 2026-04 之前）。引入 `sub_sprints` 字段后，新 feature（F200+ 大多数）走"父 feature 含 `sub_sprints` 字典 + 每个子 sprint 一个合约"的模式；但历史扁平 feature（F001-F006, F104-F106, F109-F113, F203, F210）保留了多合约的形式，没回填 `sub_sprints` 字段。

`consistency-check` 的 C5 规则不识别这种历史模式，把所有这类合约报为**孤立合约**（contract file 存在但 features.json 中找不到对应 feature.id 或 sub_sprints key）。在没有真正做错事的前提下，C5 报出 45 项 🔴 严重违例，project-commiter strict 模式因此阻塞发版。

归档把这些合约挪出 sprint-contracts 根目录，避开 C5 扫描；同时通过 git 历史完整保留，可在 archive 中查阅。

## 归档内容（45 个文件）

| 父 feature | 状态 | 归档的合约 |
|-----------|------|-----------|
| F001 Watchlist 管理 | done | F001-a/b/c-contract.md |
| F003 数据获取与调度 | done | F003-a/b/c-contract.md |
| F005 个股 150MA Modal | done | F005-a/b/c-contract.md |
| F006 大盘概览 | done | F006-a/b/c-contract.md |
| F104 FMP 数据源迁移 | done | F104-s1/s2/s2c/s3-contract.md |
| F105 Market Breakout Scanner | done | F105-a1/a2/a3/a4/a5/b/c-contract.md |
| F106 Multi-Signal Scanner | done | F106-a/b/c-contract.md |
| F109 Widget UI 规范 | done | F109-a/b-contract.md |
| F110 Watchlist CSV | done | F110-a-contract.md |
| F111 同日 ticker 缓存 | **未进 features.json**（废弃规划，2026-04-22 草拟，功能未实现） | F111-a-contract.md |
| F112 News Widget | done | F112-a/b/b1/b2-contract.md |
| F113 News 缓存与增量刷新 | done | F113-a/b/c-contract.md |
| F203 Decision Panel Widget | done | F203-a/b1/b2/c/d-contract.md |
| F210 AI Candidate Ranker + Trade Plan | done | F210-a/b/c-contract.md |

## 仍在 sprint-contracts 根目录的合约（保留原位）

走 `sub_sprints` 字段约定的 feature，及单合约扁平 feature（F002/F004/F107/F108 等）保留原位，正常参与 C5 扫描。

## 注意事项

- **不要把归档合约文件复制回 sprint-contracts 根目录** — 会重新触发 C5 违例
- 如要复活 F111 的缓存设计，请走 project-init 迭代模式新增 feature，不要复用 F111-a-contract.md（合约内容已过时）
- 未来若需要给某历史 feature 回填 `sub_sprints` 字段（schema-pure 路径），请同时把对应 archive 合约文件移回根目录（成对）
