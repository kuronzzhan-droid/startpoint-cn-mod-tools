# 水杰拉德：治疗/护盾/双攻/驱散/全抗/受疗与槽上限 实现调研（2026-10-18）

只读调研，未改任何数据或代码。

**取证来源**
- 官方技能树：用 `out/万圣新角色-20261016/research/dsl_index.json` 收录的 1330 个程序，到官方 store `D:/WF/resources/game/wf-assets/upload` 里解开，共 958 棵官方树。自制角色的树不在官方 store，因此自动排除。
- 官方词条：`D:/WF/resources/game/wf-decrypted/master/ability/{ability,leader_ability}.csv`。CSV 的列号 = 布局列号 + 1，因为首列是键。
- 反编译源码：`D:/WF/decompile-complete-20261014/scripts`。下文写「X.as:行」的都在这里。
- 角色名与 id：来自本地编辑器 `GET :8790/api/characters`。

---

## 0. 通用速查（六项都会用到）

**DSL 文件定位**
- `action_skill` 表一行 = `code, 等级(1/2), 名称, 描述, 图标类别, …, cells[7]=程序路径`。
- 等级 2 是「＋」版，例如 `…/rare5/vesta_caster$vesta_caster_2`。
- store 逻辑路径 = `程序路径 + ".action.dsl.amf3.deflate"`（见 `wf_dsl.dsl_logical`）。
- 治疗型角色图标类别统一写 `dynamic/skill/heal`。

**选择器**（`boot_ffc6.as:1039-1064`）

| 码 | 含义 |
|---|---|
| 33 | ALL_PARTY_MEMBERS：主小队 + 技能目标多球（含协力球） |
| 34 | 队长 |
| 35 | 除自身外 |
| 37 | LOWEST_RELATION_HEALTH_POINT_MEMBER：HP 比例最低者 |
| 49 | 全部敌人 |
| 82 | 主小队，不含多球 |
| 97 | 主小队（作为一个 Squad 实体） |
| 113 | PRIMARY_SQUAD_MEMBERS：主小队成员 |
| 114 | 主小队除自身 |
| 145 | ALL_SUB_SQUADS_MEMBERS：全部多球小队成员 |

**内置主体**
- `-17` = 自身；`-18` = 球。
- `-33` = `Mate`，即联机队友。只在技能 ActionType 下绑定（`ActionEvaluationResolver.as:169`）。

**`FindAllSubjects` 参数**
- 形状：`FindAllSubjects(绑定号, 选择器, f1, f2, f3, f4, f5, ["DoNothing"], Block)`。
- `f1..f5` 是角色组码数组：组内 OR、组间 AND，空数组 = 不过滤。
- 组码由 `SpecialEfficacy_Impl_.resolveCharacterSlayerTarget` 解析：1..6 = 火水雷风光暗，**2 = 水**；4097 起 = 职业类。
- 这套组码也用于 `CreateRatioHeal` 的「对 X 属性效果提升」参数。

**跨机能送的内容**（memory `wf-coop-relay-and-fixed-speed`）
- `-33` / `TargetMate` 只能送 NormalHeal / RatioHeal / ConditionChanges / ConditionCancels。
- Barrier 送过去 = INTERNAL ERROR，进战斗即崩。

**HP 判定是快照**
- `ActionEvaluationResolver.preresolve()`（:597）在动作开始时遍历整棵树，包括 `Wait` 事件体。
- 它对非敌方 `FindAllSubjects` 预先求值，并缓存 `ConditionalsHealthPointRatio`(54) / `ConditionalsHealthPointRatioOf`(55) 的结果。
- 因此所有 HP 判定都按「发动瞬间」计算。同一技能里先回血，不会改变后面的分档或满血判定。

---

## 1. 全体参战者治疗：按各自当前 HP 分档，下限 5%、上限 50%

### 1.1 现有治疗机制全表

| 机制 | 写法 / 参数 | 计算（源码） | 官方先例 |
|---|---|---|---|
| **DSL 比例治疗** | `CreateRatioHeal(主体, kind, 比率SLv, 组码[], 组加成SLv, HealHitEffect)`<br>kind：**1 = 目标当前 HP**，**2 = 目标最大 HP**；写其他值时 kind 为 null，必崩 | `ActionEvaluator.as:3195` → `RatioHealCalculator`：治疗量 = 目标HP × 比率 × (1 + 组加成，仅目标匹配组码时) × (1 + 目标受疗加成)，向下取整，最少 1；被禁疗时为 0 | 官方 294 处**全部 kind=2**；kind=1 有 **0 例** |
| DSL 固定值治疗 | `CreateNormalHeal(主体, 基础量SLv, 组码[], 组加成SLv, effect)` | `NormalHealCalculator`：(基础量 + 0~2 随机) × 组加成 × (1+受疗) × (1±5%) | 官方技能 **0 例** |
| 按施法者最大 HP / 攻击力治疗 | **不存在** | RatioHeal 只读被治疗者的 HP；NormalHeal 是常数 | — |
| 按损失 HP 回复（越残越多） | **没有原生公式** | 只能用 `ConditionalsHealthPointRatioOf` 分档组合出来 | 分档治疗官方 0 例，但组件都有先例 |
| 持续回复 | `CreateCondition(…, [["ACRegeneration", [帧SLv], [每跳HP SLv]]] …)` | `MemberImpl.applyRegeneration`：**每 120 帧（2 秒）**回固定 HP，走 FixedHeal，吃受疗加成；官方每跳 40~200 HP | 221054 鹰森诚司 `psychic_seiji_2`（33，360 帧，80→125）；151002 拉杰尔特 `prince_zero_2`（33，600 帧，75→100）；151171 玉子 `magatama_spirit_2`（113+145） |
| 词条：比例治疗 | 瞬发 kind **206** RatioHeal，固定按被治疗者最大 HP（`MemberImpl.as:7810`） | ability 56 行 / leader 6 行 | 221002 莉洁儿 `2210023`（HpLow 50% → 触发者 17.5→35%）；leader 121183 普·莉莉艾（Fever → 全队水 3.5→5%） |
| 词条：固定治疗 / 持续回复 | 207 FixedHeal（官方 0 行）；17 ConditionRegeneration（8 行） | — | 2510013 蒂亚（Fever → 全队光） |

**官方「全体参战者」治疗模板**：三条并列——主小队、多球、联机队友。

```
FindAllSubjects(0,113,[],[],[],[],[],["DoNothing"], Block[ CreateRatioHeal(0,2,S(r),[2],S(0.5),["GenericHealHitEffect"]) ])
FindAllSubjects(1,145,[],[],[],[],[],["DoNothing"], Block[ CreateRatioHeal(1,2,S(r),[2],S(0.5),["GenericHealHitEffect"]) ])
CreateRatioHeal(-33,2,S(r),[2],S(0.5),["GenericHealHitEffect"])
```

水属性先例（`_2` 版数值）：
- 121051 玛姆娜莉亚 `holy_mother_2`：8→10%
- 121159 妮丝艾丝 `vesta_caster_2`：8→10%
- 121117 蒂亚 `sing_android_2halfanv_2`：8→10%
- 121008 拉杰尔特 `prince_zero_smr20_2`：5.6→8%

`[2]` + `S(0.5)` 就是文案里的「【对水属性角色效果提升】」，水属性目标 ×1.5。

只治疗 HP 最低者：251008 伊路米 `illusionist_2`，`FindAll(37)` 8→10%。

### 1.2 按成员 HP 分支

- 写法：`ConditionalsHealthPointRatioOf(主体, 阈值int, THEN, ELSE)`。
- 判定（resolver case 55，`ActionEvaluationResolver.as:822`）：`当前HP×100 ≥ 阈值×最大HP` 时走 THEN，否则走 ELSE。
- 主体可以是 `FindAllSubjects` 的绑定号。官方同形状写法：
  - 161159 尼尔娅娜 `rector_sorcerer_playable_2`：`FindAllSubjects(4,113,[6],…){ ConditionalsHealthPointRatioOf(4,50,{CreateRatioAttack…},{}) }`
  - 131116 露米拉卡 `little_vampire_2`：同样形状，选择器 114。
  - 161183 澄波响 `psychic_teleport_playable_2`：`ConditionalsHealthPointRatioOf(-17,40,{},{Wait 300 → CreateRatioHeal(-17,2,0.2)})`
- ⚠ **新发现：对 `-33` 用 HP 分支必崩。** `Mate.getRealCurrentHealthPoint/MaximumHealthPoint` 直接抛 INTERNAL ERROR（`pinball/battle/action/dsl/Mate.as:332-342`），所以联机队友没法分档，只能给平值治疗。

### 1.3 推荐方案

主小队（113）和多球（145）各套一条 10 档链；联机队友（-33）给平值。阈值和比率都是裸 int / SLv。

| HP（发动瞬间） | ≥90% | ≥80% | ≥70% | ≥60% | ≥50% | ≥40% | ≥30% | ≥20% | ≥10% | <10% |
|---|---|---|---|---|---|---|---|---|---|---|
| 回复最大 HP | 5% | 10% | 15% | 20% | 25% | 30% | 35% | 40% | 45% | 50% |

结构：`ConditionalsHealthPointRatioOf(b,90,{heal 5%}, Block[ ConditionalsHealthPointRatioOf(b,80,{heal 10%}, … Block[heal 50%]) ])`

**注意事项**
1. **上限会被放大。** 「上限 50%」是基础比率。保留 `[2]/0.5` 时，水属性成员最高实得 75%，再乘受疗加成。要硬卡 50%，就把组码写成 `[]`、组加成写 0，或把整张表降档。
2. **数值远超官方。** 官方全队治疗 8~10%，自身治疗最高 20%。50% 属于远超官方的数值，交给作者定平衡。
3. **分支体写法。** 必须写 `["Block",[]]`，不能写 `DoNothing`（memory：F1009）。阈值是裸 int；比率必须是 `[{min,max}]`，写裸数值会 F1034。
4. **满血成员的回复会浪费。** HP ≥90% 的人也会吃 5%，这是设计内的。

---

## 2. 自身 HP 满（100%）时，赋予自身最大 HP 15% 的护盾

### 2.1 自身 HP 条件

- 写法：`ConditionalsHealthPointRatio(阈值int, THEN, ELSE)`，命令 54。
- 判定：`发动瞬间自身当前HP×100 ≥ 阈值×最大HP`（`ActionEvaluationResolver.as:135-136, 814`）。写 **100 = 满血**。
- 官方阈值只用过 30/45/50/60（8 个角色、16 棵树）。100 没有先例，但走的是同一个比较式，结论可靠。
- 先例：
  - 321011 克菈菈 `junior_yearngirl_2`：`(60, THEN=自身攻击+全队PF伤害+攻击判定, ELSE=火抗+CreateRatioHeal(-17))`，文案「【生命值60%以上时】…【生命值未满60%时】…」。
  - 161009 绀野纯子 `konno_junko_2`：`(45, THEN=Block[], ELSE=FindAllSubjects(1,33,[6]){CreateBarrier(1,0.045→0.06)})`。这就是「HP 条件 → 屏障」的现成先例。
  - 231038 托·蕾蕾妮 `little_wizard_2`（阈值 50）。
- 等价写法：`ConditionalsHealthPointRatioOf(-17,100,…)`，同样是快照。

### 2.2 护盾 / 屏障

- 写法：`CreateBarrier(主体, 比率SLv, ["GenericBarrierHitEffect"])`，命令 58。
- 计算（`BarrierCalculator`）：屏障量 = 向下取整(**目标**最大 HP × 比率)，最少 1。主体写 `-17`，就是自身最大 HP 的 15%。
- 先例：
  - 自身：251029 赛希莉亚 `woman_knight_1anv_2`（-17，8→10%）；161008 爱丽丝 `alice_smr20_2`（-17，8→10%）。
  - 全队：121070 见岛勇希 `psychic_yuki_2`（33 + 水，5.5→7%）；151014 菲拉梅里亚 `lamp_guide_2`（33，4→5%）。
- **屏障不是状态（condition）。**
  - 它是独立的屏障槽（`HealthPointGaugeImpl.addBarrier`），每人只有一个。
  - 新值大于剩余值才覆盖（`BarrierHpGaugeImpl.canOverride`），不叠加，没有时长。
  - 不计入 buff 数，也不会被驱散。
- **词条侧**：瞬发 227 Barrier，同样按目标最大 HP 计算。ability 16 行：
  - 221011 杰拉尔 `2210113`：开场自身 25→50%。
  - `2210116`：HpLow 80% 触发，限 1 次，5→10%。
  - 121008 拉杰尔特 `1210081`：全队水 7.5→15%。
  - leader 表没有官方行。

### 2.3 推荐写法与注意事项

```
ConditionalsHealthPointRatio(100, Block[ CreateBarrier(-17, S(0.15), ["GenericBarrierHitEffect"]) ], Block[])
```

- **护盾不能给联机队友。** 屏障送 -33 或 TargetMate = INTERNAL ERROR。本项只给自身，没有问题。
- **同一技能的治疗不会让自己「变满血」。** 因为判定是快照，自己从 95% 回满也拿不到盾。如果设计意图是「回满就给盾」，需要改成 `Wait` 之后另起一个动作，或换成 629 能力触发。
- **15% 超过官方。** 官方自身屏障最高 10%，属平衡提示。
- **文案建议**：「发动时若自身生命值为100%，赋予自身屏障（最大生命值15%）」。这不违反 memory 里禁止「生命值100%以下」恒真文本的规则——那条禁的是恒真写法，这里是真条件。
- **如果改走词条 HP 门**：前置 8 HpHigh、87 Barrier 的 puller 列不能留空，否则 C7050（memory `wf-precondition-puller-c7050`）。

---

## 3. 全队 2 个独立的攻击力 +150%

### 3.1 CreateCondition 12 参权威布局

来源：`ActionEvaluator.as:3249`，命令 21。

| 位 | 含义 | 推荐值 |
|---|---|---|
| p0 | 主体 | 绑定号 |
| p1 | `[AC…]` 状态列表 | `[["ACAttackPoint",[帧],[强度],[层数上限]]]`，例如 `S(900)`=15 秒、`S(1.5)`=+150%、`S(1)` |
| p2 | 命中率 SLv（概率） | `S(1)`。casino_dealer 写 0.25 是赌博设定，别照抄 |
| p3 | 命中演出 | `["GenericConditionHitEffect"]` |
| p4 | cancelable（可驱散） | `true` |
| p5 | 跳过同动作去重 | `false`（官方 17/1278 处写 true） |
| p6 | **discriminationKey 区分键** | 见 3.2 |
| p7 | linkedHitCheckKind | `null` |
| p8 | isInvisible | `false` |
| p9 | 付与对象种类 | 1 = Member / 2 = Squad / 3 = 不检查；错配报 C16102 |
| p10 | 层倍率 SLv | `S(1)`（官方恒为 1） |
| p11 | forceApply | `false` |

### 3.2 为什么必须写不同的 key

1. **同一次施放会去重。** `createConditionChangeHash = str(AC列表)+str(命中率)+cancelable+key`。同一次施放里对同一目标哈希相同的第二条，会在 p5=false 时**直接 return**。
2. **相同 id 会合并。** 状态 id（`ConditionId_Impl_._new`）：
   - key 为空时，id = `N//派生/内容体@battleId`，内容相同即同一个 id，只会合并刷新。
   - key 不为空时，id = `D//派生/构造名/key/@battleId`。

⇒ **两条完全相同的攻击 buff 如果不写不同 key，实际只生效 1 条，也只算 1 个 buff。**

**官方正解**：121159 妮丝艾丝 `vesta_caster_2`，文案「赋予水属性角色及水属性协力球2个攻击力提升效果」。

```
FindAllSubjects(0,113,[2],…){ CreateCondition(0,[ACAttackPoint(900,0.65→0.75,1)],S(1),Generic,true,false,"一個目",null,false,1,S(1),false)
                              CreateCondition(0,[同上],…,"二個目",…) }
FindAllSubjects(1,145,[2],…){ 同样两条 }
```

另一个先例：121153 索媞艾丝 `ruin_lady_meteor23_2`，key 为 `攻撃力アップ1` / `攻撃力アップ2`，1200 帧，0.65→0.75。

### 3.3 是否算 2 个 buff

**算。**
- `ConditionSlot.getTotalBuffCounts`(:4517) 和 `getTargetConditionCount`(:4903) 都按状态**条目**逐条计数。
- 官方水属性「点灯」词条正是吃这两条：during_trigger **38 ConditionCountAttackPointUp**（攻击力提升状态数，限 6 次）。
  - 妮丝艾丝 1211591~1211596 / leader 121159
  - 索媞艾丝 1211531~1211535
- 第 5 项的全属性抗性会再 +1 个 buff。屏障和治疗不计数。

### 3.4 数值与重复施放

- **强度累加。** 状态强度按 strength × magnification 求和，两条合计 +300%。
- **超官方区间。** 官方单条最高 1.2→1.4（151063 奈芙提姆 `ruin_girl_smr21_2`），1.5 超出官方区间，属平衡提示。
- **重复施放只刷新。** key 固定时，再次发动只会刷新这两条，不会叠到 4 条。

### 3.5 是否送联机队友

- 可以用 `CreateCondition(-33, …, p9=3)`，ConditionChanges 能跨机。先例：141069 雷恩 `mercenary_smr21_2`。
- 妮丝艾丝没有送。是否送由设计决定。

---

## 4. 消除全体敌人 2 个强化效果（官方叫「消除强化」）

### 4.1 写法

`DeleteCondition(主体, 状态类别, 上限int, cancelableKind int, key, 同步模式)`，命令 22（`ActionEvaluator.as:3433` → `resolveDeletionalCondition` → `ConditionCancelCalculator`）。

| 参数 | 取值 |
|---|---|
| 状态类别 `DCAll(N)` | N 是方向，不是个数：1 = 强化+弱体，**2 = 只删强化**，3 = 只删弱体（memory） |
| 上限 | 实删 = min(上限, 候选数)。候选列表经 `reverse()`，**最新的先删** |
| cancelableKind | **0 = 只删可驱散的**（官方 145 处几乎全写 0），1 = 只删不可驱散的，2 = 全删 |
| key | `""` = 不限分组 |
| 同步模式 | `["Default"]` |

**删不掉的**（`ConditionSlot.chooseConditionsToCanceled:7246` 附近）：
- quest 初始状态里，只有四种伤害耐性在白名单内可删，其余都删不掉。
- boss pre_action 里写了 cancelable=false 的状态，cancelableKind=0 时删不到。

### 4.2 官方先例

| 角色 | 树 | 写法 | 文案 |
|---|---|---|---|
| 261023 塞尔玛 | `illegal_herbalist_2` | `FindAllSubjects(0,49,…){ CreateCondition(0,[ACAttackPoint(900,-0.15→-0.2,1)]…); DeleteCondition(0,["DCAll",2],1,0,"",["Default"]) }` | 「全体敌人…消除一个强化效果」 |
| 141045 涅维亚 | `beast_shaman_2` | 命中目标 `DeleteCondition(7,["DCAll",2],2,0,"",["Default"])` | 「消除两个强化效果」 |
| 231020 露娜露 | `fox_scientist_hw20_2` | 命中目标，上限 2 | 「消除2个强化效果」 |

### 4.3 推荐写法与注意事项

```
FindAllSubjects(3,49,[],[],[],[],[],["DoNothing"], Block[ DeleteCondition(3,["DCAll",2],2,0,"",["Default"]) ])
```

- 词条侧**没有**「消除敌方强化」的内容。527 DeleteConditionDebuff 是解除己方弱体，所以只能走 DSL。
- 49 = 全部敌人，按塞尔玛先例写。

---

## 5. 全队全属性抗性 +15%，持续 15 秒

### 5.1 写法

```
CreateCondition(b, [["ACToleranceOfElement", S(900), 254, S(0.15), S(1)]], S(1), ["GenericConditionHitEffect"], true, false, "", null, false, 3, S(1), false)
```

AC 参数：`[帧SLv, 元素码裸int, 值SLv, 层数上限SLv]`。

| 元素码 | 含义 |
|---|---|
| 1..6 | 火水雷风光暗 |
| **254** | 全属性 |
| 255 | 随持有者属性 |

### 5.2 官方先例（完全同参）

- 341004 奈丝卡 `casino_dealer_2`：`FindAllSubjects(0,33){… ACToleranceOfElement(900,254,0.125→0.15,1)}`，p9=3。它的 p2=0.25 是赌博概率，我们写 1。
- 151002 拉杰尔特 `prince_zero_2`：33，900 帧，0.15→0.2。同一块里还有攻击、弱体抗性、持续回复。
- 121070 见岛勇希 `psychic_yuki_2`：33 + 水过滤 `[2]`，720 帧，0.25→0.3。
- 251029 赛希莉亚 `woman_knight_1anv_2`：只给自身。

### 5.3 注意事项

- **15% 的实际减伤。** 正抗性按「伤害 ÷ (1+r)」计算，15% 时受伤 ≈ ×0.87；r=1 也只是减半（memory `wf-element-immunity-channel`）。定值 / 比例伤害无视属性抗性。
- **词条 36 不能替代。** 词条 36 ResistanceAllElement 是常驻效果，不是 15 秒，所以不能用它。

---

## 6. 词条：受疗提升 与 技能槽相关

### 6.1 列号对照（布局列号，0 基，不含 CSV 首列键）

| 表 | 发动方式 | 触发 | 内容 kind | 目标 | 目标组 | 强度（Lv1 / 满级） | 其他 |
|---|---|---|---|---|---|---|---|
| ability（126 列） | c5（0 瞬发 / 1 持续） | 瞬发 c27；持续 c97 | 瞬发 **c47**；持续 **c109** | c48 / c110 | c49 / c111 | c51/c52；持续 c113/c114 | 前置1 c6~c12；**持续行 c85 必须写 `(None)`** |
| leader_ability（124 列） | c3 | 瞬发 c25；持续 c95 | 瞬发 **c45**；持续 **c107** | c46 / c108 | c47 / c109 | c49/c50；持续 c111/c112 | 前置1 c4~c10 |

- 强度单位：1000 = 1%，例如 7500 = 7.5%。
- 目标码：0 自身 / 5 全队 / 7 触发者 / 2 队长 / 9-10 HP 最低者。
- 组：`Blue` = 水；`(None)` = 不限。

### 6.2 受疗提升（EaseOfHeal）

源码：`MemberAbilityTotalizerImpl.getTotalEaseOfHeal` = 瞬发 + 持续 + 限时之和。所有治疗计算器都乘 (1 + 此值)。持续回复（FixedHeal）也吃这个加成；联机续关回复不吃。

| kind | 官方行 | 先例（★为推荐 donor） |
|---|---|---|
| 瞬发 **195** EaseOfHeal | ability 15 / leader 13 | leader：★121183 普·莉莉艾（`guild_front_girl_playable`，c25=0 开场，c46=5，c47=Blue，7500→10000）；221002 莉洁儿（(None)，10→15%）；321010 莉可（Blue，22.5→30%）<br>ability：★3210074 诲谕 `depraved_monk_4`（c27=0，c48=5，c49=(None)，2→4%）；2430011 亚里莎（4→8%）；1310021 卡莉奥丝特罗（c27=23 技能发动，限 5 次，每次 2.5→5% 叠加） |
| 持续 **43** EaseOfHeal | ability 4 | 2510533 萨莉哈 `desert_priest_3`（c97=1 HpLow 60%，c110=7 触发者，5→10%） |
| 196 EaseOfHealWithLength | 官方 0 行 | 不推荐 |

**推荐**：照抄 leader 121183 或 ability 3210074 作 donor，只改 c47/c49 强度。

### 6.3 技能槽

| kind | 作用 | 官方行 | 先例 / 注意 |
|---|---|---|---|
| 瞬发 **245** SecondSkillGauge | 技能槽**最大值**（memory：枚举名叫 SecondSkillGauge，`wf_describe` 会误渲染成「2号位技能槽」） | ability 22 / leader 2 | ability：★3210026 崔丝塔 `urban_soldier_6`（开场自身 12.5→25%）；1211653 岚梅 `amulet_bosslady_3`（前置 2 共鸣 Blue 600000，自身 10→20%）；1211893 茶露亚（c27=57 Member 600000 限 1，全队 Blue 10→20%）<br>leader：131122 绮拉（共鸣雷，全队 Yellow 10→15%）；131170 塔吉斯 |
| 持续 **124** SecondSkillGauge | 同上，持续版 | 官方 ability/leader **0 行** | 自制杰拉德 149999 队长技已真机生效（1.4.251）。作者纪律：常驻效果优先用瞬发 245（memory `wf-no-hplow-text-discipline`） |
| 瞬发 **211** SkillGauge | **立即充入**技能槽 | 官方 472 / 53 行 | 例：alk_2（键 12）开场自身 50→100%；leader 141003 丛云 全队 Green 30→50%。被 ClosedInterval 截顶 |
| 瞬发 **35** / 持续 **3** SkillGaugeCharging | 充能速度 | 67 / 16 行 | 实测游戏内上限 50%。例：1211654 岚梅（共鸣，全队 Blue 2.5→5%）；1211595 妮丝艾丝（持续触发 38 = 每个攻击力提升状态 +0.625→1.25%，限 6 次） |
| 212 / 701-703 / 709-711 | — | 官方 0 行 | 写进去 = 赌 F1009，**禁用** |

---

## 7. 整技草案（已做形状校验，未上真机）

用 `hw_kitlib` 风格的构件写出：

```python
S=lambda a,b=None:[{"min":a,"max":a if b is None else b}]
C=lambda *a:["Command",list(a)];  B=lambda *s:["Block",list(s)]
fa=lambda bind,sel,*body,g=():C("FindAllSubjects",bind,sel,list(g),[],[],[],[],["DoNothing"],B(*body))
heal=lambda s,r:C("CreateRatioHeal",s,2,S(r),[2],S(0.5),["GenericHealHitEffect"])
cond=lambda s,ac,key="":C("CreateCondition",s,[ac],S(1),["GenericConditionHitEffect"],True,False,key,None,False,3,S(1),False)
def ladder(b):   # 90→5% … 10→45%，<10%→50%
    node=B(heal(b,0.50))
    for thr,r in reversed([(90,.05),(80,.10),(70,.15),(60,.20),(50,.25),(40,.30),(30,.35),(20,.40),(10,.45)]):
        node=B(C("ConditionalsHealthPointRatioOf",b,thr,B(heal(b,r)),node))
    return node[1][0]
tree=["ActionDsl",1,["None"],False,False,False,False,False,False,False,0,B(
  C("ConditionalsHealthPointRatio",100,B(C("CreateBarrier",-17,S(0.15),["GenericBarrierHitEffect"])),B()),   # ②
  fa(0,113,ladder(0)), fa(1,145,ladder(1)), heal(-33,0.10),                                                   # ① -33 只能平值
  fa(2,33,cond(2,["ACAttackPoint",S(900),S(1.5),S(1)],"wg_atk_1"),                                           # ③ 两个 key
         cond(2,["ACAttackPoint",S(900),S(1.5),S(1)],"wg_atk_2"),
         cond(2,["ACToleranceOfElement",S(900),254,S(0.15),S(1)])),                                           # ⑤
  fa(3,49,C("DeleteCondition",3,["DCAll",2],2,0,"",["Default"])),                                             # ④
)]
```

**已做的校验**
- `wf_dsl.encode_amf3` 往返逐字节一致，3075 B。
- `wf_client_legality` 三项检查均为空：lookup_scope / subject_binding / element(水)。
- 与 958 棵官方树按（构造名，参数位）做类型签名差分：**0 处差异**。

**未做的**
- 演出：ShowEffect、StopBall 都没有。
- 真机：没有验证。
- `ConditionalsHealthPointRatio(100)` 这个阈值、10 层嵌套分档、-33 平值治疗，三者都是「组件有先例、组合无先例」，建议先上测试服跑一遍。
