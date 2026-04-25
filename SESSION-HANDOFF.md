# SESSION HANDOFF
> 更新：2026-04-25 | 阶段：v1.8 全部已开发 sprint 校准 done，待启动 P0 F208

---

## 当前状态

### 已完成（v1.8 sprint）

| Sprint | Phase | 验收 |
|---|---|---|
| F200-a Cockpit Shell | ✅ done | 验收合格 |
| F200-b TopNav + ResetLayout | ✅ done | 通过 |
| F201-a Market Regime 数据层 | ✅ done | 早前验收通过 |
| F201-b Market Regime 接入层 | ✅ done | 跟 F201-a 配套出货 |
| F202-a Setup 数据层 | ✅ done | 跟 F202-c 配套出货 |
| F202-b Setup 接入层 | ✅ done | 代码已合 |
| F202-c Setup 共享组件 | ✅ done | UI 验证通过 |
| F203-a/b1/b2/c/d Decision Cockpit | ✅ done | 全套已合 |
| F204-a Earnings 数据层 | ✅ done | 12/12 测试通过 |
| F204-b Earnings 接入层 | ✅ done | 已合 |

### features.json `_pipeline_status`
- `current_iteration`: v1.8
- `active_sprint`: null（待选）
- `active_sprint_phase`: null

---

## 本 session 主要产出

1. **F204-a 状态核对 + 清理** — `chore(F204-a)`：删 `sqlite_insert` 死 import、Contract §1.3 澄清 FMP 路径
2. **工作区大清扫（5 commit）** — F202-b 接入层、F203-b1 model 注册补丁、F200-a Cockpit Shell、F203-d a11y 收尾、docs 累积归档
3. **news bug 修复（2 commit）**:
   - `_fetch_with_cache` coverage 误判（虽然不在生产路径上）
   - **真正 bug**：`useNewsArticles.ts` 的 `staleTime: persisted ? Infinity : 0` 让 localStorage 有数据时永不自动 refetch；改为 5 分钟。同时把 ↻ 按钮换成蓝色（blue-500）
4. **features.json 全量校准** — F200-a/b、F201-b、F202-a/b、F202-c 全部推进至 `done`
5. **feature-dev skill 升级**（在 `~/.claude/skills/feature-dev/SKILL.md`）:
   - **A-2 Generator 模式**：新增"每完成一步且通过最小验证 → wip commit"
   - **规则 7**：禁用 `git add -A`，分 sprint 内（wip 检查点）/ sprint 收尾 / sprint 间杂项 三段式
   - **规则 7 新增 Session 结束清点**：`git status` 必须干净

---

## 下一步：启动 P0 F208

### F208 — Cockpit P2 AI 层基座

| 项目 | 说明 |
|---|---|
| 优先级 | **P0**（F209/F210/F211 三个 AI task 的依赖前置） |
| 范围 | 引入 `litellm` Python 依赖；新建 `backend/app/ai/` 模块 |
| 风险 | 文件数可能超 6 文件上限，Sprint Contract 协商时需评估是否拆 a/b |
| 前置 | 无（直接读 PRD + ARCHITECTURE.md 即可起草 Contract） |

### 触发指令（新 session 用）

```
准备开发 F208
```

新 session 启动后，feature-dev skill 会：
1. 读取 `docs/需求/features.json` 中 F208 的 acceptance_criteria
2. 读取 ARCHITECTURE.md / DATA-MODEL.md / API-CONTRACT.md（AI 相关章节）
3. 扫码估算文件清单 → 若 > 6 文件，停下来跟你协商拆 F208-a / F208-b
4. 输出 Sprint Contract 草案到 `docs/开发/sprint-contracts/F208-contract.md`
5. 暂停等你确认后才进入 Generator

⚠️ 新 session 启动后会按**新版规则 7** 执行 commit：
- WIP 检查点：每完成 migration / repo / service / router / 测试 / 前端 都 commit 一次
- 显式 add 文件，禁用 `git add -A`
- Session 结束前必做 `git status` 清点

---

## v1.8 之后未做的 P1/P2

| 优先级 | feature | 说明 |
|---|---|---|
| P1 | F205 | Cockpit P1 第一 widget — Setup 多维筛选漏斗 |
| P1 | F206 | positions/pending_orders 表（手动录入嘉信持仓） |
| P1 | F207 | 今日决策聚合 |
| P1 | F209 | AI default-tier — market regime narrative |
| P1 | F210 | AI critical-tier — candidate ranker |
| P2 | F211 | AI 混合 tier — contradiction detector |
| P1 | F103 | 财报数据真实接入（D034 待决） |

---

## 参考路径

| 文件 | 说明 |
|---|---|
| `docs/需求/features.json` | 状态权威，已全量校准 |
| `docs/系统设计/ARCHITECTURE.md` | F208 Sprint Contract 起草必读 |
| `docs/开发/sprint-contracts/` | 已归档 sprint contract，新 sprint 可参考格式 |
| `claude-progress.txt` | 进度日志，新 session 可读取最近条目 |
| `~/.claude/skills/feature-dev/SKILL.md` | 已升级 commit 规则 |
