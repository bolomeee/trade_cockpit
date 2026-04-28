# SESSION-HANDOFF — F211-b Contract Agreed

> 생성시간：2026-04-28 | Branch: cockpit | 阶段：F211-b 🟡 contract_agreed
> 본 session 모델：Opus 4.7（Architect 모드）

---

## ⚠️ 현재 contract_agreed sprint 두 개 병행 가능

| Sub_sprint | 状态 | Contract |
|-----------|------|---------|
| **F211-b** | 🟡 contract_agreed（DecisionPanel Contradictions 区前端） | docs/开发/sprint-contracts/F211-b-contract.md |
| **F206-c2** | 🟡 contract_agreed（PendingOrdersWidget 前端） | docs/开发/sprint-contracts/F206-c2-contract.md |

두 sprint 모두 시작 가능. 의존성 없음.

---

## 1. F211-b 협상 결과

### 범위
DecisionPanelWidget 内 "AI Contradictions" 区前端. 결구 镜像 F210-b 의 AiTradePlanSection（lazy trigger / 6 态状态机 / cache badge / divider）. **0 行后端改动**, F211-a1 의 contradiction_detector schema + F208-c 의 `/api/ai/{task_type}` 통용 endpoint 복용.

### 5 文件 변경 계획 (≤6 上限)

| # | 文件 | 状态 | 备注 |
|---|------|------|------|
| 1 | `frontend/src/cockpit/components/AiContradictionsSection.tsx` | 新建 | ~250 行, 镜像 AiTradePlanSection |
| 2 | `frontend/src/cockpit/widgets/DecisionPanelWidget.tsx` | 修改 | ~10 行 diff (引入 + 渲染 divider, calcDaysUntil import 切换) |
| 3 | `frontend/src/cockpit/widgets/__tests__/DecisionPanelWidget.test.tsx` | 修改 | +7 새 case |
| 4 | `frontend/src/cockpit/lib/utils/dates.ts` | 新建 | calcDaysUntil 추출 (DRY, F211-c 도 复用) |
| 5 | `docs/需求/features.json` | 修改 | 본 session 已更新 |

### 核심 约束 (개발期 불가 偏离)

1. **0 行后端 改动** — schema / endpoint / guardrail 已就绪
2. **lazy 触发** — 默认 collapsed, 회피 LLM 滥用 (D069 月预산)
3. **input 13 字段 混合 来源**:
   - 8 个 from `CockpitDecisionData` (decision API response)
   - 5 个 from cache 复용:
     - `trendScore` / `rsPercentile` / `readySignal` ← `['setup-monitor', undefined]` 의 items.find(ticker)
     - `regime` / `regimeScore (= marketScore)` ← `['cockpit-regime']`
   - `daysToEarnings` ← calcDaysUntil(decision.earningsDate)
4. **缺数据 降级** — setupMonitor 中 ticker 不存在 → trigger disabled + tooltip "需 Setup Monitor 数据"
5. **severity tag 颜色 token**:
   - HIGH = `--color-error`
   - MEDIUM = `--color-signal-warning`
   - LOW = `--color-text-muted` (배경) / `--color-text-secondary` (전경)
6. **queryKey** = `['ai', 'contradiction_detector', ticker, deterministicHash]`, **24h cache** (与 trade_plan 一致)
7. **6 态状态机** 沿用 AiTradePlanSection: closed / loading / success-with / success-empty / error 502 / error 409
8. **409 분기 保留** — contradiction_detector 当前后端无 hash guardrail, 但前端 template 与 trade_plan 一致, 미래 zero-change

### 개방 문제 결과 (Q1-Q10 全部默认方案)

| Q# | 결정 |
|----|------|
| Q1 | trigger 文案: "Generate AI Contradictions" |
| Q2 | 列表 prefix: HIGH/MEDIUM=⚠ , LOW=· |
| Q3 | calcDaysUntil **抽到** lib/utils/dates.ts |
| Q4 | severity token 如上 (开发 step 1 实测验证) |
| Q5 | setup-monitor queryKey 复용 (无 filter) |
| Q6 | 409 분기 **保留** |
| Q7 | "Recommendation: {text}" 前缀 |
| Q8 | 不展示 token cost preview (cache badge 已足够) |
| Q9 | 不前端 cap contradictions 数 (schema 已限 max=5) |
| Q10 | divider 与 trade_plan 同款 |

---

## 2. 다음 session 개발 순서 (Generator 모드)

```
1. 예검 (≤30 min)
   - grep --color-signal-warning / --color-error / --color-text-muted in frontend/src/styles/tokens.css (or 대응 token 파일)
   - grep ['setup-monitor' / ['cockpit-regime' 의 정확한 queryKey 写法
   - 读 backend/app/ai/schemas/contradiction_detector.py 全文 (input/output 13 + 2 필드 1:1 매핑)
2. helper 추출
   - 신건 frontend/src/cockpit/lib/utils/dates.ts (calcDaysUntil)
   - DecisionPanelWidget.tsx 의 line 23-27 calcDaysUntil 삭제 후 import 切换
   - 跑 widget 既有 vitest 0 회귀 → wip commit
3. AiContradictionsSection 骨架
   - closed + disabled 2 态 + props + queryKey 占位
4. 类型 + input builder
   - 与 backend schema 1:1 알아인
5. state machine 완성
   - loading / success-with / success-empty / error 502 / error 409
6. severity tag 视觉
   - 步骤 1 grep 결과대로 inline style
7. DecisionPanelWidget 集成
   - import + 렌더 divider + section
8. 测试 (DecisionPanelWidget.test.tsx +7 case)
   - 1: closed trigger 渲染
   - 2: loading skeleton
   - 3: success with 3 contradictions (HIGH/MED/LOW 각 1)
   - 4: success empty (recommendation only)
   - 5: error 502 → "AI 暂不可用"
   - 6: error 409 → 红色 banner
   - 7: setupMonitor 缺 ticker → trigger disabled
   - 8 (集成): trade_plan + contradictions 两个 section divider 都在
9. Evaluator 모드
   - vitest 全套 + tsc --noEmit + biome check
   - 自검 list 일일이 체크
10. features.json 갱신 + 최종 commit + SESSION-HANDOFF.md
```

각 2-3 step 마다 wip commit (Generator 规则 7).

---

## 3. 引용 문서

- F211-b contract: docs/开发/sprint-contracts/F211-b-contract.md (방금 작성, 권위)
- 视觉 참고: docs/设计/design-spec.md line 978-1014 + line 1119
- 컴포넌트 매핑: docs/设计/component-plan.md line 348, 351, 433, 456
- API: docs/系统设计/API-CONTRACT.md line 1660-1718
- backend schema: backend/app/ai/schemas/contradiction_detector.py
- 결구 template: frontend/src/cockpit/components/AiTradePlanSection.tsx (1:1 모방)
- callAiTask: frontend/src/cockpit/lib/api/aiApi.ts (이미 통용, 무 변경)

---

## 4. 다음 Session 起动 指令

```
继续开发 F211-b，Sprint Contract 已确认。
读取 SESSION-HANDOFF.md + docs/开发/sprint-contracts/F211-b-contract.md，
进入 Generator 模式，从开发步骤 1（预检：grep tokens.css 中
--color-signal-warning / --color-error / --color-text-muted；
grep setup-monitor / cockpit-regime queryKey；
读 backend contradiction_detector schema）开始。
```

⚠️ 절대 step 1 의 token 검증 / queryKey 검증 / schema 1:1 대조 **꺼지 마라**. 이 3 가지가 contract 의 5 处 가장 fragile 가설.

---

## 5. F211 5 段 现황

| sub_sprint | 范위 | 状态 |
|-----------|------|------|
| F211-a1 | 3 task schema + REGISTRY + guardrail | ✅ done |
| F211-a2 | per-task model override 基建 (D075) | ✅ done |
| **F211-b** | DecisionPanel Contradictions 区前端 | 🟡 contract_agreed |
| F211-c | News 页 AI 摘要 bar 前端 | ⬜ design_needed |
| F211-d | 평창 hook + journal_entries.ai_review 迁移 + 월별 cron | ⬜ design_needed |

依存: a1 ✅ + a2 ✅ → {b / c / d}, 全 병렬 가능.

---

## 6. 历史 스냅샷

- **F211-b**: 🟡 contract_agreed (2026-04-28 Architect)
- **F211-a2**: ✅ done (2026-04-28 Generator)
- **F211-a1**: ✅ done
- **F210（critical-tier AI）**: ✅ done
- **F209（default-tier AI）**: ✅ done
- **F208（AI Gateway）**: ✅ done
- **F207（Action List）**: ✅ done
- **F206（Position Manager）**: 🟡 in_progress（c2 contract_agreed）
- **F205**: ✅ done
