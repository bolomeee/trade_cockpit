# SESSION-HANDOFF — F207-a needs_review

> 生成：2026-04-27 | 阶段：**F207-a Evaluator 通过 → needs_review**
> 当前 active sprint：**F207-a**（Evaluator 自检全通过，待用户验收）

---

## 当前状态

| 项 | 值 |
|---|---|
| F207-a phase | **needs_review** |
| 单元测试 | 16/16 ✅ |
| 集成测试 | 6/6 ✅ |
| 全量回归 | 744/744 ✅（基线 722，+22） |
| WIP commits | 3 个（skeleton / classifier / router+integration） |
| DECISIONS.md | D075 F207-a §7 Q1-Q8 已追加 |
| 下一步 | 用户验收（acceptance） 或 最终 feat commit + 开始 F207-b |

---

## F207-a 交付物清单

| # | 文件 | 状态 |
|---|---|---|
| 1 | `backend/app/services/cockpit/action_service.py` | ✅ 新建，280 行 |
| 2 | `backend/app/routers/cockpit/actions.py` | ✅ 新建，63 行 |
| 3 | `backend/app/routers/cockpit/__init__.py` | ✅ 修改，+2 行 |
| 4 | `backend/tests/test_action_service.py` | ✅ 新建，16 单元 |
| 5 | `backend/tests/test_actions_router.py` | ✅ 新建，6 集成 |

---

## Evaluator 自检要点

**全部通过。** 一条已报告注意事项：

- `_classify_position`（~72 行）和 `build_today_actions`（~70 行）超 50 行上限
- 两函数逻辑内聚（分别是 5 优先级规则分支 / IO + 分类 + 排序），**建议保留现状**
- 用户若认可则进入最终 feat commit

---

## Rule Engine 核心逻辑（验收参考）

### _classify_position 优先级

| 优先级 | 条件 | 动作 / 栏 |
|---|---|---|
| 1 | last_close ≤ stop | must_act `raise_stop`（"stop already breached"） |
| 2 | regime ∈ {DEFENSIVE, RISK_OFF} | must_act `tighten_stop` |
| 3 | days_until_earnings ≤ 2 | must_act `reduce_before_earnings` |
| 4 | rule=raise_stop（R≥2.0, stop<entry） | must_act `raise_stop`（R-multiple 模板） |
| 5 | 否则 | no_action `stable_position` |

### _classify_pending_order 优先级

| 优先级 | 条件 | 动作 / 栏 |
|---|---|---|
| 1 | setup BROKEN | must_act `cancel_order` |
| 2 | distance ≤ 3% 且 last_close < entry | monitor `approaching_trigger` |
| 3 | 否则 | 不展示 |

### must_act 排序

`tighten_stop > reduce_before_earnings > raise_stop > cancel_order`，同类内 ticker 字典序

---

## 风险与注意事项

- **ruff 未安装**：手动代码质量检查通过。如需 ruff，在 pyproject.toml dev 依赖加 `ruff>=0.4`
- **F207-b 前端 sprint**：widget 槽位 x:0 y:16 w:12 h:6（全宽），需注册到 CockpitRegistry；`refs` 弱类型 dict 已在 rationale 表中固定每个 actionType 的字段集，前端按表实现
- **历史踩坑**（仍适用于 F207-b）：
  1. Radix Select 在 Dialog 内 JSDOM 无法 click：`vi.mock('@/components/ui/select')`
  2. react-hook-form dirtyFields 必须组件渲染阶段订阅
  3. localStorage 旧布局不含新 widget：验收提示用户用 Reset Layout 按钮

---

## 恢复指令

**验收 F207-a：**
```
F207-a needs_review，请验收。
读取 SESSION-HANDOFF.md，检查 backend endpoint GET /api/cockpit/actions/today 是否符合 API-CONTRACT.md §1584-1651。
```

**跳过验收直接最终 commit + 开始 F207-b：**
```
F207-a Evaluator 已通过，确认跳过验收直接 feat commit，然后开始 F207-b Sprint Contract 协商。
读取 SESSION-HANDOFF.md + docs/开发/sprint-contracts/F207-a-contract.md。
```

**仅开始 F207-b（已完成验收后）：**
```
继续开发 F207-b（ActionListWidget 前端）。
读取 SESSION-HANDOFF.md + docs/系统设计/API-CONTRACT.md §GET /api/cockpit/actions/today + docs/设计/design-spec.md §Widget 9。
进入 Sprint Contract 协商。
```
