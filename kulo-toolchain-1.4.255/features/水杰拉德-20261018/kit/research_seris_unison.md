# 赛瑞斯作为水杰拉德合击时的全套件可用性调研（只读，2026-10-19）

范围：水杰拉德 129989 当队长（slot0 主位），赛瑞斯 129999 当他的合击（slot0 合击），全队 6 水。客户端以 v35e（run5 `v35e.swf`）为准。数据以 1.4.238 视图 store 为准。本文没有改任何文件，只写了这份报告。

AS3 行号指 `D:/WF/decompile-complete-20261014/scripts/` 下的原版反编译文件。v35 补丁行号指 `D:/WF/v35-generic-20261018/run*/final-pcode/*.pcode.txt` 的指令序号（#NN）。

---

## 0. 结论（先看这里）

1. **只要数据写 `wfx_unlock_129989 = 3`，赛瑞斯几乎全部套件就能在杰拉德的合击位生效，不需要新补丁。** bit2 把他的 10 行队长技加进 slot0 的能力源。bit1 放开 1299993（8 行主位限定）。其余 4 个能力本来就能用（unisonable=true）。
2. **「自身」= Member 0**，也就是杰拉德这颗球的成员（主位杰拉德加合击赛瑞斯）。增益、固有 22、固有 1299901 都挂在 Member 0 上。强化弹射永远由 Member 0 发动（队长）。用到「角色」的开战前置按赛瑞斯本人判断。
3. **PF4 在 v35e 下已经能用。**
   - 能力源：Lv4 查询 `getPowerFlipOverrides(4)` 是全场共用的（Battle 级 totalizer），所以能查到赛瑞斯队长技第 7 行（419，等级 "4"，门 = Member 0 身上有固有 22）。
   - 门槛：读 `wfx_pf4_<队长角色id>`，这里是 `wfx_pf4_129989`。1.4.238 里**没有** `wfx_pf4_129999`，赛瑞斯当队长时用的就是默认 100 连击 / FF4040。所以杰拉德当队长、不写键，效果也一样。建议还是显式写 `wfx_pf4_129989 = 100:FF4040`。
   - 弹板渐变和就绪色同样走全场查询，跟着生效。
4. **唯一的硬冲突在 PF Lv1–3。** 一次弹射只能跑一棵树。结果取决于水杰拉德自己有没有 PF 覆盖：
   - **方案 A**：杰拉德自带 722，等级 "1,2,3"（例如克隆光杰拉德 PF 再翻倍）。PF1–3 永远是杰拉德的。赛瑞斯第 8、9 行（真龙特殊 PF、龙人 PF）被压掉。PF4 照样是赛瑞斯的「苍海怒涛」。这是我推荐的做法。
   - **方案 B**：杰拉德不带覆盖（对照表 v1 写的是原生「辅助」PF）。赛瑞斯三条 419 全部接管队长 PF：非 Fever 跑龙人 PF，龙形跑真龙特殊，PF4 跑苍海怒涛。字面上赛瑞斯全生效，但杰拉德自己的 PF 在赛瑞斯合击时永远看不到。
   - 杰拉德自己**不能有**等级含 4 的覆盖行，否则会和赛瑞斯抢 Lv4。
5. **做不到、或只能算外观问题的：**
   - 龙形像素小人：换图门判的是主位角色的标签，合击没有小人。
   - 吐息、回龙人的变身特效会播在杰拉德身上。可以纯改 DSL 修掉。
   - PF4 时的语音不是赛瑞斯专属。
   - 面板会显示赛瑞斯完整队长技文案。方案 A 下其中两句（龙人 PF、真龙 PF）不成立。
6. **v35f 不是必需的。** 有两个可选项：
   - P1 `pf-lv4-data-v2`：PF4 门槛和颜色按覆盖键找，不按队长找。
   - P2 `leader-unlock-v2`：解锁范围只限自己的合击，并且要求全队共鸣。

---

## 1. 机制底座（证据）

| 事实 | 证据 |
|---|---|
| 每个主位 slot 各算一个能力源，交给同 index 的 Member | `common/data/party/BattlePartyLogic.as:958-961`（`_createCalculatedBattleCharacterLogic` → `getAvailableAbilities(this, slot,…)`） |
| 原生合击能力通过 `getOpitionAbilitiesWithoutAbilitySoul` 并进主位的能力源。`add` 的 character 参数是**主位**。只有 slot==0 才追加队长技，origin 为 21000+i | `common/data/character/BattleCharacterLogic.as:1431-1474`、`2409-2490` |
| v35b 解锁读 slot0 队长的 `wfx_unlock_<leader_ability键>`，按位与 7，没有共鸣门 | run2 `BattleCharacterLogic__wfxPartyMask` #20-#44 |
| v35b bit1：在 unisonable 判断上 OR 掩码 bit1。主位方法按 `this` 判断，对**三个**合击位都生效 | run2 `getOpitionAbilitiesWithoutAbilitySoul` #88-#89；`party/patches.py` 第 10-11 行 |
| v35b bit2：slot k 主位的能力源追加 k 号合击的队长技。origin = 1021000+k·1000+i。`add(origin, trig, 合击角色, party, slot=k)` | `party/leaders.py`（`wfxExtraLeaders` / `wfxAddExtraLeaders`） |
| 开战前置（Initial 类）在组队时用 `param3.getInstantAbiltyCount` 求值，param3 是 add 传进来的角色 | `common/data/ability/BattleAbilitySource.as:253-436` |
| **「队长时」前置（InitialAbilityTriggerKind.Leader，index 6）只判 slot 号**：`param3==0`。原生合击能力在 slot0 时也是 true | `BattleCharacterLogic.as:1694-1696`。构造顺序见 `instant/InitialAbilityTriggerKind.as:19` |
| v35b 只在 1021000–1023999 号段把 Leader 改成 0、IsNotLeader 改成 1 | run2 `party/patches.py` 第 27-33 行 |
| 目标「自身」= 该能力槽所属的 Member（`slot.member`）。origin 百万位为 1 时记作合击（OriginMemberInfo.kind=1） | `scene/battle/battle/ability/AbilitySlotImpl.as:964-981`、`1946-1957`；`DuringAbility.as:166-199` |
| PF 覆盖（722 瞬发 / 419 持续）和 ChangeSkillFlag 存在 **Battle 级** totalizer，全场只有一份 | `ability/BattleAbilityTotalizerImpl.as:336-385`（查询）、`602-607`（536）、`628-635`（722 写入）、`703`（419 push）；`Battle.as:1210` |
| 查询规则：先看 722，**只有它的 forLevels 含当前档才拦截**；否则按注册顺序扫 419，取第一个激活的 | `BattleAbilityTotalizerImpl.as:344-383` |
| PF 只由队长 Member 发起。默认的树是队长主位角色的 PF（特性类型）；有激活的覆盖就换掉 | `squad/SquadImpl.as:387-419`、`squad/member/MemberImpl.as:968-983`、`isLeader` = primary && index==0 |
| v35a PF4：`param2==3 && 快照连击 >= cfg[0]` 时先查 `getPowerFlipOverrides(4)`，查不到再回落原档。cfg = `wfx_pf4_` + `battle.initialData.get_leaderCharacterId()`，按场缓存 | run1 `MemberImpl__startPowerFlip` #20-#58；`Battle$__wfxPf4Config`；`run1/pf/patches.py` |
| 弹板 Lv4 渐变每 10 帧查一次全场 `getPowerFlipOverrides(4)`，不判谁是队长 | run1 `pf/BattleFlipperImpl_update.txt` #81-#87；AS3 `scene/battle/battle/flipper/BattleFlipperImpl.as:131-` |
| 合击技能的 resolver 用 originMemberKind=1，换技能 flag 按 (index, kind) 读 | `squad/SquadManagerImpl.as:677-715`；`action/ActionEvaluationResolver.as:141-148`；`MemberImpl.as:1714` |
| 629 在持有成员身上执行，没有合击拦截。只用 `isByUnison` 决定 main 标志 | `MemberImpl.as:7782`、`8131-8160` |
| DSL `ConditionalsMainOrUnison`（命令 98）按 originMemberKind 分支 | `action/ActionEvaluator.as:4779-4791` |
| 双形态换图门判的是 `member.getCharacter().characterTags`，即**主位**标签。合击标签是另一个字段 | run3 `voice_dual/MemberView__draw.txt` #38-#46；`common/data/character/CalculatedBattleCharacterLogic.as:81` |
| PF 覆盖 DSL 按能力持有者的属性预载，执行时用队长 PF 的 element | `common/data/ability/during/CommonAbilityContentTools.as:37-47`；`MemberImpl.as:980` |

---

## 2. 赛瑞斯全套件逐项表

前提：v35e，`wfx_unlock_129989=3`，赛瑞斯在 slot0 合击，杰拉德是队长，6 水。
「原生」= 不靠解锁也能用。行号 rN 是同一键下的第 N 条记录（0 起）。列号见 `wf_describe.layout`：leader 表 124 列，ability 表 126 列。

### 2.1 队长技 `leader_ability` 129999（10 行，前置 1 全是 Member 水≥6：c4=2、c7/c8=600000、c9=Blue）

| 行 | 内容 | 依赖什么 | v35e 下 | 修法 / 说明 |
|---|---|---|---|---|
| r0 | Initial → 461 固有 **1299901**（`fever:items:…:seris`）给自身 | 原本「队长身上有标记」；v35a 改成「主小队任意成员，队长优先」 | ✅ 需要 bit2。标记挂在 Member 0（就是队长） | 无 |
| r1 | Initial → 50 FeverPoint 100% 自身 | 自身 | ✅ bit2。加在 Member 0 的攻击 Fever 上升率 | 无 |
| r2 | 持续·Fever → 攻击力 350% 自身 | 自身 | ✅ bit2 | 无 |
| r3 | 持续·Fever → 强化弹射伤害 450% 自身 | 自身 | ✅ bit2 | 无 |
| r4 | Fever≥1 → 489 连击加成 40 自身 | 自身 | ✅ bit2。和杰拉德的 489（+30）相加 | 无 |
| r5 | 自身弹射（26）→ 226 连击+3 | 弹射者 = 自身 | ✅ bit2 | 无 |
| r6 | Initial → 536 `change_skill_seris_dragon_king` | flag 按 OriginMemberInfo 存 | ✅ bit2。origin 1021006 → kind=1，存到 (0, 合击)。合击技能 resolver 用 kind=1 读同一个键，『苍海潮涌』的 `ConditionalsChangeSkillFlag` 分支生效 | **不要**把这行镜像进杰拉德自己的队长技：那样 origin 是 21xxx，kind=0，flag 会落到杰拉德主技能上 |
| r7 | 持续 194（固有 22 层≥1，限 1）→ **419 `override_seris_dragon_lv4` 等级 "4"** | 全场覆盖查询；需要 Member 0 有固有 22；需要 PF4 门槛 | ✅ bit2 + bit1（固有 22 来自 1299993 r3）。Fever 中连击≥门槛时，杰拉德的 PF3 换成苍海怒涛 | 门槛 / 颜色读 `wfx_pf4_129989`，缺省 100:FF4040，和赛瑞斯现状一致。建议显式写。杰拉德不能有等级含 4 的覆盖行 |
| r8 | 持续 194（固有 22）→ 419 `override_seris_dragon_special` "1,2,3" | 全场覆盖查询 | 方案 A ❌（被杰拉德 722 "1,2,3" 压掉）／方案 B ✅（龙形时接管 PF1–3） | 设计取舍，见 §4。不是 bug |
| r9 | 持续 HpLow≤100%（恒真）→ 419 `override_seris_human_powerflip` "1,2,3" | 全场覆盖查询 | 方案 A ❌／方案 B ✅（非龙形时接管 PF1–3） | 同上 |

### 2.2 能力 1299991–1299996

| 键·行 | 内容 | unisonable | 依赖 | v35e 下 | 修法 / 说明 |
|---|---|---|---|---|---|
| 1299991 r0 | Initial → 211 技能槽 25→50% 自身 | true | — | ✅ 原生 | — |
| 1299991 r1 | 55 强化弹射伤害 50→100% | true | — | ✅ 原生 | — |
| 1299991 r2 | 水≥6、非 Fever：自身技能发动 → 724 Fever+35% | true | — | ✅ 原生 | — |
| 1299991 r3 | **队长时(42)**、非 Fever：PF Lv3（CT 120 帧）→ 724 +5% | true | Leader = slot==0 | ✅ 原生（slot0 合击判为 true） | 放到 slot1/2 合击时不生效 |
| 1299991 r4 | **队长时**：Fever 结束 → 724 +30% | true | 同上 | ✅ 原生 | 同上 |
| 1299992 r0/r1 | **队长时**：持续 HpLow≤100% → 422 冲刺参数 30%/50%（c118=1/6） | true | 同上；422 是补丁 kind（只补 ability 表） | ✅ 原生，作用在 Member 0 的冲刺 | — |
| 1299992 r2 | 冲刺（CT 60 帧）→ 226 连击+8 | true | — | ✅ 原生 | — |
| 1299992 r3 | 非 Fever：冲刺（CT 120）→ 724 +2% | true | — | ✅ 原生 | — |
| 1299993 r0–r2 | 水≥6：持续 194 固有 22 → 攻击 300% / PF 300% / PF 独立乘区 15% 自身 | **false** | 主位限定 | ✅ 需要 bit1。作用在 Member 0 | — |
| 1299993 r3 | Fever → 461 固有 22 给自身 | false | — | ✅ bit1。固有 22 挂在 Member 0 | 杰拉德套件里不要再占用 uid 22 |
| 1299993 r4 | Fever 结束 → 528 删固有 22 | false | — | ✅ bit1 | — |
| 1299993 r5 | Fever 结束 → 629 `ability_skill_seris_revert` | false | 执行者 | ⚠ bit1 后能跑，但回龙人特效（`ShowEffect … -17`）播在杰拉德身上 | 改 DSL：把 ShowEffect 包进 `ConditionalsMainOrUnison`（主位分支播、合击分支空） |
| 1299993 r6 | Fever → 629 `ability_skill_seris_breath` | false | 执行者 | ⚠ bit1 后伤害和全屏龙息正常。化龙特效（-17）播在杰拉德身上。伤害按合击来源记（main=false）。属性 255 跟随上下文，水 | 同上，只包 `seris_transform` 那条 ShowEffect |
| 1299993 r7 | 水≥6、非 Fever：经过 900 帧 → 724 +15% | false | — | ✅ bit1 | — |
| 1299994 r0/r1 | 持续连击≥50/≥100 → PF 伤害 25→50% | true | — | ✅ 原生 | — |
| 1299995 r0/r1 | 非 Fever / Fever：冲刺（CT 120）→ 629 dash_h / dash_d | true | 执行者 | ✅ 原生，在 Member 0 位置冲撞，按合击来源记 | — |
| 1299996 r0/r1 | PF 伤害 25→50%，FeverPoint 15→30% | true | — | ✅ 原生 | — |

### 2.3 其他组件

| 组件 | 现状数据 | v35e 下 | 说明 |
|---|---|---|---|
| 技能 `seris_dragon_king`（作为合击技能） | DSL 里有 `ConditionalsChangeSkillFlag 1`（命中挂 PF 抗 / 水抗 -15%） | ✅ 原生；配合 r6（bit2）强化生效 | kind=1 一致，已核对 |
| 角色表技能切换 c9=1：ConditionExist(Unique 22) → c14 `seris_dragon_king` | 切到同一个技能 | ✅ 等于没切 | 按 Member 0 的状态判断（`SquadManagerImpl.as:683`） |
| 双形态标签 `ModDualForm`（c5）+ 固有 22 | MemberView 换图门判的是主位标签 | ❌ 不会出龙形小人 | 合击本来就没有小人。**不要**给杰拉德加 ModDualForm，否则会换成杰拉德的 ★5 获取演出 special 图 |
| 固有 22 `unique_seris_dragon_king` | 3600 帧，上限 1，强制，入棺移除 | ✅ | 杰拉德入棺时同样被移除，和赛瑞斯当主位时一致 |
| PF4 门槛 / 颜色 | 没有 `wfx_pf4_129999`，缺省 100 / FF4040 | ✅ 缺省值等同 | 写 `wfx_pf4_129989 = 100:FF4040` 保持一致 |
| Fever 箭头换道具 | 1299901 + fever-items-v2 | ✅ bit2 | — |
| 面板文案 | `desc_override_seris_dragon_king_leader` 等 | ⚠ v35b 会在面板列出赛瑞斯整段队长技文案；方案 A 下「龙人 / 真龙 PF」两句不成立 | 方案 A 建议在杰拉德队长技文案里注明「合击角色的强化弹射覆盖只有 Lv4 生效」，或接受 |
| 预载 | v35b `wfxPreloadExtraLeaders` 走 `LeaderAbilityLogic.resolvePathCollection` | ✅ 三条覆盖的 9 个 DSL 和 629 都会预载 | ⚠ 被压掉的覆盖也会预载，占图集（4096² 预算），未核实 |

---

## 3. 「自身」到底是谁，PF 谁来放

- **Member**：解锁后，赛瑞斯队长技的每一行都进 slot0 的 AbilitySlot。`slot.member` = Member 0。所以「自身 / Myself」类目标、持续触发里的「自身」来源、固有状态的 ConditionSlot，全部是 Member 0：杰拉德这颗球（主位杰拉德 + 合击赛瑞斯）。数值用 Member 0 的面板（主位 ATK + 合击 25%）。
- **角色判定**：开战前置（Initial 类）用 `add` 的角色参数。解锁队长行的角色是**赛瑞斯**（v35b 设计）。原生合击能力的角色是**主位杰拉德**（`getAvailableAbilities` 传 `this`）。赛瑞斯这些行只用了 Member（全队计数）、Leader（slot 号）、Fever/NotFever（运行时），所以和是谁无关。
- **origin 种类**：解锁队长行 1021000+ → kind=1（合击）。原生合击能力 1001000+ → kind=1。影响 ChangeSkillFlag 的键（见 r6）和 629 的 main 标志。
- **PF**：永远是队长 Member 0 用队长的球（-18）发动。默认树是杰拉德主位的特性 PF。只要全场有激活的覆盖就会被换掉，不管覆盖来自谁（队长技、合击、队友）。赛瑞斯的 Lv4 树由 Member 0 执行，吃 Member 0 的 PF Lv3 乘区（档位整数仍是 3），element 跟杰拉德的 PF（水）。
- **放在 slot1/2 合击时**（v35b 对三个合击位都生效）：赛瑞斯的「队长时」能力失效。队长技挂到 Member 1/2。但 419 覆盖仍是全场的：方案 B 下他的龙人 PF 会接管队长 PF。r7/r8 改看 Member 1/2 身上的固有 22。

---

## 4. 合击的 PF 覆盖和主位 PF 的关系；推荐设计

`getPowerFlipOverrides(lv)`（`BattleAbilityTotalizerImpl.as:336-385`）：

1. 722（瞬发，全场只存最后一次写入）的 forLevels 含 lv → 直接返回。
2. 否则按注册顺序扫 419，返回第一个「激活且 forLevels 含 lv」的。
3. 全部不中 → null，用队长特性 PF。

slot0 能力源的顺序是：原生能力（含合击 100x000）→ 杰拉德队长技 21000+ → 解锁的赛瑞斯队长技 1021000+。AbilitySlotImpl 按这个顺序建 DuringAbility，不排序（`AbilitySlotImpl.as:1946-1957`）。所以同档位时，杰拉德的 419 总排在赛瑞斯前面；杰拉德的 722 则直接拦截。

**推荐（方案 A，最干净）**
- 数据：
  - `wfx_unlock_129989 = 3`
  - `wfx_pf4_129989 = 100:FF4040`
- 杰拉德队长技：PF 覆盖用 **Initial + 722，等级写 "1,2,3"**（克隆光杰拉德那行，见 §6），**不要写 4**。全套件不要有等级含 4 的覆盖行，也不要占用 uid 22 / 1299901。
- 效果：
  - PF1–3 = 杰拉德的专属 PF（翻倍版）。
  - 水共鸣、Fever 中（固有 22 在 Member 0 上）、拍板连击≥100 → PF3 升级为赛瑞斯「苍海怒涛」（Lv4 树），弹板同步出渐变和红色就绪。
  - 赛瑞斯全部增益、Fever 回槽、冲刺、龙息、箭头道具、技能强化都生效。
  - 被放弃的只有「龙人 / 真龙形态下 PF1–3 换成赛瑞斯的树」，因为一次弹射只能跑一棵树。
- 可选纯数据外观修复：revert / breath 两个 DSL 的变身 ShowEffect 包进 `ConditionalsMainOrUnison`。赛瑞斯当主位时不变；当合击时不在杰拉德身上播。

**方案 B（如果作者要「字面上赛瑞斯全生效」）**
- 杰拉德不带任何 PF 覆盖（对照表 v1 的原生「辅助」PF）。
- 赛瑞斯三条 419 自动接管：
  - 平时：龙人 PF（射击+特殊）
  - 龙形：真龙特殊（全类型）
  - PF4：苍海怒涛
- 代价：赛瑞斯合击时，杰拉德自己的 PF 永远看不到。别的合击带 419 时规则一样（谁的 419 先注册谁赢）。

**不推荐：把赛瑞斯的行镜像进杰拉德自己的套件。**
- 会把杰拉德绑死在赛瑞斯身上。
- ChangeSkillFlag 会落到 kind 0，也就是杰拉德的主技能。
- 「队长时」那些行本来就原生可用，镜像是重复劳动。

---

## 5. v35f 可选补丁（不做也能满足需求）

都按 v35 链的惯例做：

- 只做单方法指令级拼接，或在已有类追加助手 / 静态槽；字符串池只在尾部追加。
- 每个被改方法用 v35e 方法体的 SHA+header 双锁。
- 读表只用 `getMasterTableMaybe` + exists → get。
- 不 getlex 新类，不整类回编。
- 老数据（无新键）和 v35e 逐字节等价，并做变异复审。

**P1 `pf-lv4-data-v2`：PF4 门槛 / 颜色跟着覆盖键走**
- 目的：赛瑞斯在任何队长下都用自己的门槛和颜色，不用每个队长写一份 `wfx_pf4_<队长>`。
- 新键：`wfx_pf4id_<Lv4覆盖键>`，例如 `wfx_pf4id_override_seris_dragon_lv4 = 100:FF4040`。
- 查找顺序：覆盖键 → `wfx_pf4_<队长>`（v35a）→ 默认。
- 实现：
  - 在已有类 `Battle$` 追加静态助手 `wfxPf4ConfigFor(battle, assets, totalizer)`。内部先 `totalizer.getPowerFlipOverrides(4)`（纯读：DuringChecker.getActiveCount），非空就读 `wfx_pf4id_`+id。解析复用 `wfxPfParseUInt`。缓存加一个静态槽，用弱键 Dictionary，按 battle → id 存。
  - 拼接点：
    - `MemberImpl/startPowerFlip` v35a #31-#36 的 `callproperty wfxPf4Config 2`，改成多压一个 `battle.abilityTotalizer` 再调新助手（AS3 `MemberImpl.as:975-982`）。
    - `BattleFlipperImpl/update` 的 3 处配置调用（v34 #106/#120/#127 换成的表达式，AS3 `BattleFlipperImpl.as:131-` 的 Lv3 段）。
    - `BattleFlipperView/draw` #777 的取色调用。
  - 查询每次多做一遍，无副作用。
- 不做 P1 也行：赛瑞斯现在本来就用默认值。

**P2 `leader-unlock-v2`：解锁范围和共鸣门（对齐文案「水属性共鸣时……自身……合击角色」）**
- 现状：v35b 掩码无条件，而且对三个合击位都生效。混色队也会解锁所有合击的主位限定能力和队长技。
- 新位：
  - bit 8 = 只解锁 slot0 自己的合击（就是杰拉德自己的搭档）。
  - bit 16 = 要求 `party.getNumberOfSameElement() >= 6`（`BattlePartyLogic.as:477`，和 kind 208 / 魂珠 5090051 同口径）。
- 拼接点：
  - v35b 追加的 `BattleCharacterLogic/wfxPartyMask`：#42 `pushbyte 7; bitand` 放宽，并在这里判 bit16，不满足就返回 0。
  - `wfxExtraLeaders` 的 UNISON 段：bit8 时加 `index==0` 判断。
  - `getOpitionAbilitiesWithoutAbilitySoul` 的 #85 插入块：bit8 时再与上 `index==0`。
- 这些是 v35b 自己的方法体，按新一轮重新锁。
- 先找作者确认文案口径再做。

**纯数据（不是补丁）**：§4 提到的 `ConditionalsMainOrUnison` 外观修复。

---

## 6. 附：光杰拉德 149999 的 PF 覆盖（克隆到水杰拉德用）

**队长技行**：`leader_ability` 149999 **r1**（第 2 条记录）
- c0 `black_wolf_knight`，c3=0（瞬发），前置 c4=0 Always（**不看共鸣**）
- c25=0 Initial
- c45=**722** PowerFlipOverride
- c80 = `white_wolf_gerald_pf`，c81 = `1,2,3`，c82 = `override_string_white_wolf_gerald`（custom_ability_string，文案「自身的强化弹射变为角色专属形态……」）

**power_flip_action 键** `white_wolf_gerald_pf`（`master/skill/power_flip_action.orderedmap`）对应 3 棵树。文件名是 `<程序路径>.action.dsl.amf3.deflate`，在 upload store：
- lv1 `battle/action/power_flip/action/override/white_wolf_gerald_pf$white_wolf_gerald_pf_lv1`
- lv2 `battle/action/power_flip/action/override/white_wolf_gerald_pf$white_wolf_gerald_pf_lv2`
- lv3 `battle/action/power_flip/action/override/white_wolf_gerald_pf$white_wolf_gerald_pf_lv3`

**树的结构**（三档相同）：
- 根 `ActionDsl`，buffTargetAs=0。
- `ConditionalsConditionAccumulationNumber(["DCUnique",1499989], 1, A, B)`：持有「时之刻印」1499989 走 A（持续加倍），否则走 B。1499989 来自 1499993 r0：光≥6 → 461，unisonable=false。
- 每个分支：
  - `SetPowerFilpSuppress`
  - `CreateHitArea("*", -18, AB, 圆, Center, Single, 寿命, CalculatedUsingMaxNumOfHits N)`
    - 生成块：`ShowEffect(回転切り演出, CD, UntilTargetTerminates, scale)`
    - 命中块：`CreateNormalAttack(2, 255, …, 倍率, …, Fine)` + `ShakeCamera 1`
  - `FindAllSubjects` → `CreateCondition`（队伍增益）
  - `Wait(N-2)` → `NotifyPowerflipEnd(-18)`

| 档 | 分支 | 抑制/寿命(帧) | 圆半径 | 最大命中 | 特效 scale | **每段攻击倍率（第 6 参）** | 第 13/14 参（未核实含义） | 结束 Wait | 增益 |
|---|---|---|---|---|---|---|---|---|---|
| 1 | A 刻印 | 140 | 175 | 6 | 3.5 | **3.25** | 1.5 / 6 | 138 | FindAllSubjects(1,33)：ACAttackPoint(150帧, 0.3)、ACPiercing 60、ACFlying 60 |
| 1 | B 普通 | 70 | 175 | 3 | 3.5 | **3.25** | 1.5 / 6 | 69 | 同上 |
| 2 | A | 180 | 200 | 8 | 4.0 | **4.75** | 2 / 6 | 178 | ATK(180帧, 0.4)、贯通 90、浮游 90 |
| 2 | B | 90 | 200 | 4 | 4.0 | **4.75** | 2 / 6 | 89 | 同上 |
| 3 | A | 220 | 350 | 10 | 7.0 | **6.3** | 2.5 / 8 | 218 | FindAllSubjects(4,33)：ATK(240帧, 0.5)、贯通 150、浮游 150；FindAllSubjects(4,33,**[5]**)：ACAdditionalDirectAttack(3600帧, 4段, 1.0) |
| 3 | B | 110 | 350 | 5 | 7.0 | **6.3** | 3 / 8 | 109 | 同上 |

**特效族**（1.4.238 upload，`battle/effect/powerflip/white_wolf_gerald_powerflip/`）：

| 文件 | 字节 |
|---|---|
| `white_wolf_gerald_powerflip.png` | 26,508 |
| `white_wolf_gerald_powerflip.atlas.amf3.deflate` | 592 |
| `white_wolf_gerald_powerflip_lv1.parts.amf3.deflate` | 446 |
| `white_wolf_gerald_powerflip_lv1.timeline.amf3.deflate` | 175 |
| `white_wolf_gerald_powerflip_lv2.parts.amf3.deflate` | 472 |
| `white_wolf_gerald_powerflip_lv2.timeline.amf3.deflate` | 175 |
| `white_wolf_gerald_powerflip_lv3.parts.amf3.deflate` | 11,231 |
| `white_wolf_gerald_powerflip_lv3.timeline.amf3.deflate` | 178 |

树里只引用这一族（ShowEffect 的 `SpecifyEffectDirectly` 三档各一条）。

**克隆到水杰拉德要改的地方**
1. 新 power_flip_action 键，例如 `white_wolf_gerald_aqua_pf`，指向 3 棵新树。队长行 Initial + 722，等级 **"1,2,3"**（不要 4，要给赛瑞斯 PF4 让路）。文案键另起一个。
2. 翻倍：只改 `CreateNormalAttack` 第 6 参（min/max 同改），两个分支都改：3.25→6.5，4.75→9.5，6.3→12.6。增益数值要不要也翻倍，请作者确认。
3. 属性：攻击属性写的是 255（跟随成员属性），水杰拉德自动变水，不用改。Lv3 的 `FindAllSubjects(4,33,[5])` 里的 5 是**光**（显式元素 = 内部+1），要改成 **[2]**（水）。
4. 刻印分支：`DCUnique 1499989` 换成水杰拉德自己的共鸣标记 uid（加一行 461 + unique_condition），或者直接复用 1499989 的名字和图标，但要另配发放行。
5. 特效族整族复制到新目录并改名（按「特效族挂 code_name 目录」规则），色相改成水。parts 内对图集的引用要跟着改名，具体字段未核实，复制后要做一次离线渲染核对。
6. 预载、门禁：新键、新 DSL、新特效族要全进包。用了新 power_flip_action 键，要先按惯例做金丝雀。

---

## 7. 未核实 / 风险

- 以上全部是读反编译源码和 v35 补丁 P-code 得出的。没有真机、没有联机、没有画面核对。联机时全员必须装同一个 v35e+ SWF（PF 档位和覆盖在每台客户端各自重算）。
- 629 从合击来源执行（main=false）时，伤害统计 / 乘区是否完全等同主位，没有逐行核对完。功能上没有拦截。
- PF 覆盖 DSL 按持有者属性预载、按队长 PF 属性执行。水配水一致；如果以后赛瑞斯在别的属性队长下合击，可能缺预载（C8016 一类），未核实。
- 图集预算：赛瑞斯三条覆盖（9 棵树，被压掉的也会预载）+ 629 特效，加上杰拉德的 PF / 五族 Fever 爆发 / 技能特效，三人房可能超 4096²。
- PF4 时的语音按原生的 `selectRandomPowerFlipVoice`（从存活成员中随机），不保证是赛瑞斯的。
- 第 13/14 个 `CreateNormalAttack` 数组参数的含义没有查。
- 水杰拉德的 leader_ability 键假定是 129989（角色表 c17 的值），以最终数据为准。
