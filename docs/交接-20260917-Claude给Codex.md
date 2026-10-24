# 交接 · Claude → Codex · 2026-09-17

> 作者当次要求：「做完写个交接给codex」。本文件是**这一段工作的完整交接**，
> 不是历史归档。读法：先看 §1 现状与占用，再按 §5 的待办挑活。
> 标注口径：【事实】有命令/代码证据；【判断】我的推断；【待拍板】需要作者点头。

---

## 1. 现状

| 项 | 值 |
|---|---|
| legacy 链尾 | 【事实】**1.4.903** |
| flow 账本 base | 【事实】**1.4.896**，其上 3 条 release（s7-tekuto 897、s7-yuki 898、campus-nephtim 899） |
| 本机 8001 | 【事实】2026-09-17 03:48 分离式重启，PID 145260；操作前用 `./start-cn.bat -CheckOnly` 重核 |
| `mod-tools/work/sync_pending.json` | 【事实】`[]` |
| 我的占用 | **已释放**。`mod-tools/wf_seasonal7_kit_{tekuto,yuki}.py`、`mod-tools/wf_gacha_seasonal7_*.py`、`mod-tools/wf_pack_push_keys.py`、`work/character_packs/{s7-tekuto,s7-yuki,seasonal7-20260916}/` 我这一轮写完了，没有在途改动 |

⚠ **flow 账本 base 1.4.896 ≠ 链尾 1.4.903**：下一次**整包 `flow publish`** 之前必须先经作者授权
`reanchor`，否则铸中段边、投递为零（记忆卡 `wf-flow-ledger-dual-tail`）。
899→903 这四条边都是 `wf_publish` 裸表边（见 §2），账本不记录它们。

---

## 2. 这一轮上了什么

| 边 | 内容 | 通路 |
|---|---|---|
| 1.4.899 | 校园奈芙 169989 能力1/3 数值减半（机制未动） | 整包 `flow publish` |
| 1.4.900 | 两个自制卡池的概率/兑换/排序修订（见 §3） | 裸表边（`gacha_odds` 两张） |
| 1.4.901 | 特克托 139993 **能力2** 改成按「引擎启动」层数成长、不设上限 | 裸表边（`ability.orderedmap`） |
| 1.4.902 | 见岛勇希 129991 三条口径修正（见 §4.2） | 裸表边（`ability` + `leader_ability`） |
| 1.4.903 | 见岛勇希能力1 新增「每达成 75 连击 → 连击 +15」（见 §4.3） | 裸表边（`ability.orderedmap`） |

**为什么 900-903 走裸表边而不是整包发布**：CLAUDE.md 授权分级里「整包 `flow publish`」
要作者在当次请求里明确说；这几次作者只说了改内容。走的是常设授权那条路径
（键级改 live store + `wf_publish` 裸表边），并且**两个包的 workspace 候选都已经回写**
（`--step kit,manifest,status` 重建，同一任务的一部分，不是可选项）。
⇒ 这两个包现在「live == 包」，随时可以整包发布，不会把行退回去。

---

## 3. 卡池修订（1.4.900）

作者原话：批 5 个角色和 15 个小 Boss 在深渊池 0.1% 并加入兑换、小 Boss 兑换排在 mod 之后官方之前；
本次 7 个角色深渊 0.2% 不可兑换、竞速 1% 置顶且开兑换；竞速池小 Boss 同样的排序。

**算术口径（新记忆卡已写进 `wf-gacha-two-layer-odds`）**：两池都是「五星档权重合计恒定、
官方角色吃余数」的设计 ⇒ **显示% = odds / 10000**（深渊 15%/150000、竞速 95%/950000），
0.1%=1000、0.2%=2000、1%=10000。副作用是官方那一档必然跟着动
（深渊 0.035%→0.039%、竞速 0.220%→0.190%），这是固定合计下的必然结果。

**工具**（都带门禁，27 项测试）：
- `mod-tools/wf_gacha_seasonal7_pools.py` —— 纯函数 `revise(gacha)`，带基线断言与结果断言
- `mod-tools/wf_gacha_seasonal7_apply.py` —— **文本级拼接**落盘。`assets/gacha.json` 官方段用
  `json.dumps` 默认分隔符、两个 mod 卡池段用紧凑分隔符，整文件重序列化会改上万行无关字节；
  写前先证明「原样读出再紧凑写回 == 原始字节」
- 改完必须 `wf_gacha_odds_sync.py --apply`（客户端显示表）+ `wf_publish` 裸表边 +
  **重启服务端**（`assets/gacha.json` 是静态 import）
- 改前两池快照冻结在 `mod-tools/tests/fixtures/gacha_pools_before_seasonal7.json.gz`；
  `LiveGachaMatchesRevisionTest` 反过来核对 live 文件确实等于算出来的结果

⚠ `assets/gacha.json` 是作者 WIP 单行 16MB JSON，**没有提交**；改前快照
`assets/gacha.json.bak-s7pools-20260917-034354`。

---

## 4. 两个角色的行改动

### 4.1 特克托 139993 能力2（1.4.901）

作者：「能力2改为，自身对引擎启动每上升1，自身攻击力+50%，技能伤害+50%，不设置上限」

两条**瞬发**行（技能发动限3次 → 攻击 50→100% 最大300% / 技伤 25→50% 最大150%）
整键换成两条**持续**行：

    c5=1 / c85=(None) / c97=134 / c98=0 / c100=c101=100000 / c102=(None) /
    c104=13999301 / c108=false / c109=0(攻击力) 或 2(技能伤害) / c110=0(自身) / c113=c114=50000

**引擎取证**（反编译，`弹国服/scripts/`）：
- `DuringAbilityTriggerMasterValue.as:32` —— idx **134 = ConditionAccumulationCountUnique**（累积层数）、
  idx **194 = ConditionCountUnique**（实例个数，461 叠层固有恒为 1）⇒ 「每层」只能用 134
- `AbilityValues.as` `parseAt97` 的 134 分支给出 c98/c100,101/c102/c104 的语义；
  `parseAt102`：`"(None)" → Option.None`，**空串会 `Std.parseInt("")` ⇒ 上限 0**，所以无上限必须写 `(None)`
- 乘算落点：`DuringConditionAccumulationChecker.as:34-35` = `floor(层数 / threshold)` 再过 `TriggerLimitTools.limit`，
  → `DuringCheckerImpl.as:40` = `initialCount × triggerChecker.getActiveCount() × accumulationCount`，
  → `DuringCheckerWithDecimal.as:43` / `DuringCheckerWithInt.as:38` = `value × activeCount`
- 面板（客户端自渲染，本角色无 `desc_override_*`）：
  「自身的「引擎启动」等级每提升 1 级时，自身攻击力 + 50 % ＆ 技能伤害 + 50 %」，**后面什么都不跟**

**顺手修掉的潜伏 bug**：`wf_seasonal7_kit_tekuto._fill_sentinels` 原来两张表都读 `c3` 当触发模式，
但 **ability 的模式列是 `c5`**（`c3` 是 awake_kind）。到第四轮只产瞬发行（两列同为 `'0'`）所以没暴露。
已改成 `MODE_COL = {"leader_ability": 3, "ability": 5}`（取法 = precondition1 块基址 − 1，
与 `wf_seasonal7_kit_zantetsu.row_gate` / `wf_client_legality.py:124-125` 同一算法）。
live 实测：ability `c5='0'` → `c39='(None)'`/`c85=''`（4358 行），`c5='1'` → 反过来（1076 行）。

**新增门禁 `accumulation_cap_problems()`**：被 during-134 按层数计数的固有，
叠层上限 `c4` 必须是 >1 的整数 —— `Condition.get_accumulatable() = maxAccumulation > 1`
（`Condition.as:291-294`），为 false 时层数根本不计，**词条静默零收益而面板照样写「每提升1级」**。
这是能力2 改成 during-134 之后**新增**的失效面，旧的瞬发行完全不读固有层数。

⚠【判断】**唯一零先例点**：「134 + `c109=2`(SkillDamage) + `c102=(None)`」这个精确组合官方 0 例
（官方 134+c109=2 的 5 行上限全是数字）。攻击力侧（`c109=0`）有 live 先例
（`ability[1399943]#3`，雷吉斯能力3，1.4.883 起在线）。**技能伤害那条建议真机看一眼面板**。

### 4.2 见岛勇希 129991 三条（1.4.902）

| id | 作者原话 | 改法 |
|---|---|---|
| R28 | 队长技自身拥有护盾期间应该是水属性角色**攻击力**+500% | leader#3 during_content `c107` 2 SkillDamage → 0 AttackPoint |
| R29 | 能力2 的 75 连击水属性角色技能槽 **+5%** | ability 1299912#1 `c51/c52` 3000 → 5000 |
| R30 | 能力3 的共鸣时每当直击应该是**水属性角色合计**直击 50 次不是只有自身 | ability 1299913#1 `c28` 0 Myself → **7 TotalOfParty** + `c29='Blue'` |

**R30 是一条会骗人的面板**：`wf_describe` 对 instant trigger 20 一律渲染「编成直接攻击」，
与 puller 无关 ⇒ 改前面板写着「编成」而机制只数自身。改后机制与面板一致。
`AbilityValues.parseAt28` case `"7"` = `TotalOfParty{character_groups: c29}`；
live 全表 instant puller=7 共 145 行，trigger 20 + puller 7 共 17 行，
**donor `1510573#1` 自己就是这形状**（本 kit 一轮把它改成了 Myself）。

**行锁机制**：yuki 的 22 条行 sha 锁在二轮 `plan.json`（外部方案，不改）。
本轮新增 `work/character_packs/seasonal7-20260916/revision5-20260917/yuki/rows.json`
（`s7-revision-row-lock/1`）只记被覆盖的三条，每条带 `row_sha256_before` + `row_sha256`；
`K._locked_rows(revision, revision5)` 逐格断言 before、再校验补丁后的行 sha == 锁值
⇒ plan 被人改过会立刻报错，不会静默沿用旧覆盖。

### 4.3 见岛勇希能力1 新增一条（1.4.903）

`ability[1299911]` 加第 3 条：**水属性共鸣时，每达成 75 连击 → 连击 +15**
（instant_trigger **12 Combo** + instant_content **226 追加连击**，`c34='(None)'` 不限次数）。

- 「每达成 N 连击」是真的：`ThresholdComboListener.update` 比 `floor(prev/N)` 与 `floor(now/N)`，
  **每跨过一个整数倍触发一次**（一次跨多个就循环触发多次）。
- 不自激：加的 15 连击自身只贡献 15/75 = 20% 的额外进度，收敛。
- 数值取本角色同族口径（能力2 是「每 75 连击 → 全队水技能槽 5%」）。
- `226` 全表 74 行 target 列留空 —— 连击是全局计数器，没有「给谁」之分，所以不写 target/组。
- 行锁的 `adds` 段：追加行只能接在该键末尾、索引连号；plan 里没有成品行兜底，donor 漂移直接报错。

---

## 5. 待办 / 待拍板（按优先级）

1. **【已落地，但只做了一半】见岛勇希能力1** —— 作者原话「连击强化效果持续12s，
   每获得1连击额外获得2连击」**引擎侧两处都对不上**：
   - `AdditionalConditionKindTools.resolveTime` 的 ComboBoost 分支（case 32）直接
     `return ETERNAL_CONDITION_THRESHOLD` ⇒ **ACComboBoost 没有时间维度**，寿命只由
     `ballFlipLimit`（`params[0]`，`ActionEvaluator` case 32 → `Option.Some`）按**弹射次数**计
   - 连击的真实来源是 `EnemyImpl.createCombo()`（每次命中 +1）与 `BallImpl:843`
     弹射时的 `addCombo(getComboBoostCount())`，**前者没有任何倍率通道**
     ⇒ 「每获得1连击额外获得2连击」= 连击乘区，引擎里不存在
   现行值 `ACComboBoost(ballFlipLimit=3, combo=5)`；官方 15 处的取值范围
   `ballFlipLimit ∈ {1,2,3,5}`、`combo ∈ {2,3,5,6,10,15,30}`。
   问过作者，澄清是「和达到多少连击赋予攻击力技能槽那些差不多，达到多少连击加连击」
   ⇒ 已落成词条行（§4.3）。**仍未动**的是 1299911#1 的技能强化本体（536 + 分支里的
   ACComboBoost「3次弹射每次+5」）：它是技能分支效果不是阈值触发，换掉会让 536 行、CAS 键、
   语音路由 c9-16(kind 3) 与 switched_action_skill 一起失去意义 ⇒ **要不要一并换掉/删掉，等作者说**。
2. **【待拍板】战斗图集预算已超阈**：`wf_atlas_budget_check.py` 报 RED，归因 `pre-existing` ——
   不加任何新包时 layer0/layer1 已占 90.4%／92.3%（`seris_dragon_king` 单角色 17.7%）。
   897/898/899 三次发布是带 `-SkipAtlasCheck` 过的。建议瘦 `seris_dragon_king`。
3. **【待拍板】上批 4 个包里 17 行自认领表行比 live 旧**（bianca/celtie/scutum/white_tiger_summer）：
   rebase 只归位未声明行、修不了自认领行，preflight 也不报。
   另 `white_tiger_summer` 的 ownership 绑定已断（无 manifest 命中账本哈希），只剩裸表边通路。
4. 【判断·可顺手】另外 90 个包的 `ability.orderedmap` 快照仍停在各自发布时的版本（本轮之前就是这样）。
   1399932/129991x 不被它们认领 ⇒ 任一包再发时 flow preflight 会以 `unclaimed_change` 挡下、
   rebase 归位，**不会静默回滚**。真正修不了的是第 3 条那种自认领陈旧行。
5. 【判断】`s7-tekuto` / `s7-yuki` 两个包各有 6 / 2 个**别家**的共享表影子键落后 live
   （校园奈芙 1.4.899 后发布）。整包发布前的 `preflight → rebase` 会归位；
   `impl/yuki/run_gates.py` 已把这类「别人后发布」与「我们动了别人的键」分开判（前者只记 info）。

---

## 6. 新增/改动的工具（都在 `mod-tools/`，已提交）

| 文件 | 作用 |
|---|---|
| `wf_gacha_seasonal7_pools.py` / `wf_gacha_seasonal7_apply.py` | 卡池修订纯函数 + 文本级拼接落盘 |
| `wf_pack_push_keys.py` | **新**：把包内**指定外层键**按键级推到 live store（其余键保留原压缩字节）。改一条词条行却不做整包发布时的标准通路，配 `wf_publish --tables` 铸边 |
| `wf_atlas_budget_check.py` + `atlas_budget_roster.json` | 发布前的战斗图集预算闸（阈值 90%，`-SkipAtlasCheck` 可过） |
| `wf_seasonal7_build.py` | `--step inspect` 新增 `--installed-package-dir`：角色已发布过时不给这个参数 flow 会以 `active ownership hash exists but installed manifest was not supplied` 报 rc=2 |
| `wf_seasonal7_kit_tekuto.py` | `MODE_COL` 修模式列 bug、`REV5_*` + `apply_rev5_ability2`、`accumulation_cap_problems` |
| `wf_seasonal7_kit_yuki.py` | `REVISION5_REL` + `row_sha_lock` + `_locked_rows(revision, revision5)`、三条配方改值 |

测试：`test_gacha_seasonal7_pools`(27) / `test_pack_push_keys`(12) / `test_atlas_budget_check`(44) /
`test_seasonal7_*`(337) 全绿。

---

## 7. 我没碰的东西

- `src/`、`web/`、`admin/`、`assets/` 里除 `gacha.json` 之外的文件
- Codex 的深渊武器共鸣（1.4.895）与慢通关铭牌（1.4.896）—— 只读不改
- 任何远端推送、公开链/overlay/分享包投递、灰服投递、APK、设备直推
