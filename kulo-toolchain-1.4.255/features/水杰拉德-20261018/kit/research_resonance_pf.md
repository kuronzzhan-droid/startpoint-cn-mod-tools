# 水杰拉德 kit 调研：属性共鸣 / 强化弹射 / 治疗转伤害（2026-10-18，只读调研）

## 结论速览

- **「X属性共鸣」= 前置条件 kind 2（Member）+ 角色组填属性串 + 阈值 600000（6 人）**。ability 表在 c6/c9/c10/c11，leader 表在 c4/c7/c8/c9。它数的是全队 6 个槽：3 个主位加 3 个合击位，空槽不算，和谁当队长无关。客户端文案只在「单一属性组且人数 = 6」时显示「X属性共鸣」。
- **「任意属性共鸣」客户端已经原生支持，不用打补丁**：前置条件 kind **208 SameElementMember**，战斗时取「同一属性最多的人数」，再和阈值比较。官方先例在 ability_soul 表：5090051、5090055、5090056，阈值都是 600000。文案和「未发动原因」也是原生的。**不要用 kind 5 ElementVariety**：它在战斗里数的是「有几种不同属性」，意思完全不同。
- 任意属性图标：ability 文本里的六个属性图标来自 `icon_tag` 表（CDN 主表）。图片在 APK bundle 的 `scene/general/sprite_sheet` 图集里，名字是 `round_ability_<色>`。同一张图集里已经有 `element_any`，但它只是白色方框，和圆标风格不一样。加一行 icon_tag 就能引用它，不用改 APK。要做新的彩虹圆标就得重新打包这张图集（4096×4071，已经接近满）。
- **进 Fever 时立刻打出全部 PF 类型**：每种类型一行 629 InvokeSkill，挂瞬发触发 **8（Fever 开始）**，执行官方 Lv3 整树的副本。做副本时根头 `tree[10]` 写 **133**（靠 v28 起每个包都带的伤害分类补丁，按 PF Lv3 结算），并删掉 `SetPowerFilpSuppress` 和 `NotifyPowerflipEnd`（1.4.221 实证，不删就崩 U_e66385）。官方 PF 共 5 族：knight 剑士、fighter 格斗、ranged 射击、supporter 辅助、special 特殊，每族 Lv1 到 Lv3 共 15 棵树，store 里都有。
- **Fever 中 PF 伤害翻倍**：首选持续行，持续触发 4（Fever）配持续效果 **413 SeparatedTermPowerFlipDamage**，强度 100000（+100%），面板标「独立伤害乘区5」。乘区5 和「PF LvN 伤害」类加成共用同一个 (1+Σ)。如果要严格等于原生 PF 的 2 倍，改用队长位 419 挂 Fever，换成倍率 ×2 的覆盖树。
- **Fever 中连击 +30**：用瞬发效果 **489 ConditionComboBoost**（拍板清零后回填，相当于连击保底），挂触发 8，强度 3000000。不同角色的 489 状态 ID 不同，会**相加叠加**，所以能和赛瑞斯的 40 叠成 70（上限 9999）。注意：赛瑞斯这一行的 flip_limit 写的是 (None)，实际效果是第一次进 Fever 之后永久生效，不止 Fever 期间。
- **码 27 溢出治疗**：基础伤害 = 溢出量 × Σ(value×层数)/10000，是**固定数值，不乘攻击力**。之后照常吃能力伤害加成、属性相克、敌方属性抗性和能力抗性等原生乘区。**普通（非溢出）治疗转伤害，官方和现有补丁都没有**，需要新码。设计见 §B4。

**口径**：

- 列号是去掉 CSV 首列键之后的 0 基索引，和本地编辑器、`CN-Mod字段手册.md` 一致。
- leader_ability 从 c3 起都等于 ability 列号 −2（因为 leader 表少了 unisonable 和 rarity 两列）。
- `file:line` 一律指 `D:\WF\decompile-complete-20261014\scripts\` 这棵树。
- 官方数据取自 `D:\WF\resources\game\wf-decrypted\master\`。

---

## A1 「X属性共鸣」的数据和求值

### 列位

| 用途 | ability 列 | leader 列 | 值 |
|---|---|---|---|
| 前置条件1 kind | c6 | c4 | 2=Member，208=SameElementMember，3=MySelf，43=队长是某组，12=Fever，186=NotFever |
| 前置条件1 阈值（SLv1 / 满级） | c9 / c10 | c7 / c8 | 600000 = 6 人（100000 = 1） |
| 前置条件1 角色组 | c11 | c9 | `Red/Blue/Yellow/Green/White/Black`，逗号分隔表示 OR |
| 前置条件2（同构） | c13、c16/c17、c18 | c11、c14/c15、c16 | 常用来放 12 或 186（Fever 门） |
| 前置条件3（同构） | c20… | c18… | |
| 瞬发触发 kind / 触发来源 / 来源角色组 | c27 / c28 / c29 | c25 / c26 / c27 | |
| 瞬发触发阈值 | c30 / c31 | c28 / c29 | |
| 瞬发触发自身角色组（kind 57/58 用） | c36 | c34 | |

官方统计（共 5083 行）：

- ability 表中前置条件1 = 2 的有 108 行，阈值全是 600000，组是单一属性（蓝 22、暗 22、风 20、光 19、火 14、雷 10）。
- leader 表中 = 2 的有 125 行，同样全是 600000。
- kind 208 在 ability 和 leader 两表都是 **0 行**，只在 ability_soul 表有 3 行。
- kind 5 只出现在其他列位，用作异色队门槛。

**「另一种形式 23/7/Green」不是共鸣**：c27=23 是 SkillInvoke（发动技能），c28=7 是 TotalOfParty，c29=Green 是触发来源角色组。合起来的意思是「风属性角色发动技能时（全队累计）」。官方 54 行。

c36 角色组配触发 57（Member）也能做「开局按编成人数」的瞬发，例如 `1211893 dryad_hw23_3`：57、c36、600000。

### 属性串

`OrCharacterGroup_Impl_.resolve`（`pinball/common/data/ability/_OrCharacterGroup/OrCharacterGroup_Impl_.as:47-148`）的映射：

- Red=0、Blue=1、Yellow=2、Green=3、White=4、Black=5、Colorless=6。Colorless 是敌人专属，可玩角色写 6 会 C7050。
- 不在属性和类型名单里的串，依次查 gender、race、character_tag 三张表，都查不到就抛 **ClientError 2038**。

### 客户端求值链

1. 解析：`pinball/common/data/ability/pre/AbilityPreconditionMasterValueTools.as`
   - `:38` case 2 → `InitialAbilityTriggerKind.Member(groups, threshold, Some(1))`
   - `:45` case 5 → `Variety(Element, …)`
   - `:555-556` case 208 → `SameElementMember(threshold)`
2. 战斗内判定：`BattleAbilitySource.as:285` 对每个前置条件调 `getInstantAbiltyCount`，结果 >0 才算激活。具体计数在 `pinball/common/data/character/BattleCharacterLogic.as:1610 getInstantAbiltyCountWithoutLimit`：
   - `:1627-1628` Member：`floor(party.matchCharacterGroup(groups)/N)`，Some(1) 封顶为 1。
   - `:1691-1692` Variety：`floor(party.getVariety(kind)/N)`。`getVariety` 用 StringSet 去重，数的是**属性种类数**。
   - `:1758-1759` SameElementMember：`floor(party.getNumberOfSameElement()/N)`。
3. 队伍计数：`pinball/common/data/party/BattlePartyLogic.as`
   - `:96-118 matchCharacterGroup`：遍历 `get_allCharacters()`（`:255-258` = mainCharacters 拼接 unisonCharacters，None 跳过），逐个调 `BattleCharacterLogic.matchCharacterGroup`。
   - `:477-511 getNumberOfSameElement`：按 `get_element()` 分组计数，取最大值。
4. 单角色匹配：`BattleCharacterLogic.as:538-580`，Element 组比较 `toColorlessable(get_element())`。`get_element()` 在 `:889-898` 有缓存，`getElement()` 在 `:2059-2166`：官方只对合击位走 720 OverrideCharacterElement，v35b 在这里加了自适应属性。
5. 文案：`pinball/common/data/ability/description/InstantAbilityDescriptionGenerator.as:640-652`，只有「单个 Element 组且 count==6」才取 ui_string `ability_description_instant_trigger_kind_member_element_unified` = `::element_full::共鸣`（ui_string.csv:3827）。其他情况走通用的「编成 N 名」文案。

**注意（未用到但有坑）**：`InitialAbilityTriggerKindTools.matchCharacter`（`.../instant/InitialAbilityTriggerKindTools.as`）里的 case 5 写的是「某一属性人数 ≥N」，和战斗计数口径不同。这个函数只被 `getElement()` 的 720 路径调用（`BattleCharacterLogic.as:2130/2149`）。720 行里如果放 208 前置会直接 `throw INTERNAL ERROR ba087c5d`（`:2124-2128`），放 2 前置有自引用 `get_element` 递归的风险。**结论：720 行不要挂编成类前置。**

### 「共鸣」的精确含义

- 全队 6 槽（3 主位 + 3 合击）中，该属性角色数 ≥ 阈值。官方阈值恒为 6，也就是 6 人全同属性。缺一个合击位就永远达不到。
- 计数和队长无关。每个持有者各自判定，但看到的是同一个队伍计数。
- 队长技（leader_ability）只在 slot0 主位生效（`getAvailableAbilities` 里 `param2==0` 才追加队长技）。所以「X属性共鸣时」的队长技要求本人当队长，共鸣计数本身仍然数全队。v35b `wfx_unlock_` 位掩码可以放开合击位和队友的队长技。

---

## A2 「任意属性共鸣」

### 推荐：原生 kind 208（零补丁）

- ability 行：c6=`208`，c9=c10=`600000`，c11 留空。也可以放在前置条件2：c13=208，c16/c17=600000。
- leader 行：c4=`208`，c7=c8=`600000`。
- 开局一次性瞬发可以用瞬发触发 **257 SameElementMember**（`InstantAbilityTriggerMasterValueTools.as:784-785`）。
- **效果目标和触发来源不要再写属性组**。阈值 6 时全队同属性，「该属性角色」等于全队：
  - 目标用 party（无组）。
  - 触发来源用 5 OneOfParty 或 7 TotalOfParty，不填组。
  - 这样就完全不需要「动态属性组」。
- 原生文案：ui_string:474 `在队伍内相同属性角色编入 ::count:: 名`。count=6 时 is_max 成立，显示「在队伍内相同属性角色编入 6 名」。不满足时显示 ui_string:886「由于同属性角色数量为 N 而无法发动」（`AbilityDisabledReasonResolver.as:376-380`）。
- 想显示「任意属性共鸣」有两种做法：
  1. 按行写 `desc_override_<c0>`（custom_ability_string）。
  2. 直接把 ui_string:474 改成「任意属性共鸣」。这是全局修改，会连带官方 3 条魂珠，不过它们阈值也是 6，语义等价。ui_string 是 CDN 主表（`master/string/ui_string.orderedmap` 在 store 里，不在 APK bundle），纯数据就能改。
- 编辑器 / wf_describe 对 208 的翻译**未核实**。上线前要过 describe 和门禁。

### 图标

- 内联图标解析在 `pinball/ui/display/text/_UiText/InlineIconContainer.as:65-90`：`<icon id='x'>` → `asset.getIconTag(x).path` → 取图。**icon_tag 里没有对应 id 会空引用崩溃（F1009 类）**。所以新 id 必须先在 `master/string/icon_tag.csv` 里加行（CDN 主表）。
- 现有六个圆标在 icon_tag.csv:1-6：`red…black` → `scene/general/sprite_sheet/vector_icon_color-assets/round_ability_<色>`，颜色 0xFFFFFF，scale 1。属性名到图标标签的映射在 `pinball/common/data/general/ElementKindTools.as:106-125`，经 ui_string:932-937 `element_kind_<色>_icon`。
- 这张图集是 **APK bundle** 里的 `scene/general/sprite_sheet.atlas`（`production/bundle/94/c238c788…`，PNG 4096×4071）。里面已有 `element_any`（34×35，白色方框）、`element_any_medium`、`party_attribute_icon`、`element_<色>`。
  - 方案 a（零资产）：icon_tag 加一行 `any_element,scene/general/sprite_sheet/vector_icon_color-assets/element_any,0xFFFFFF,1`。缺点是风格不统一。
  - 方案 b（零资产，推荐）：文案里连续写六个现有圆标，`<icon id='red'>  <icon id='blue'>  …`（照抄原 ui_string 的两个尾随空格占位）。
  - 方案 c：画新的彩虹圆标，要重打 general 图集并发 APK。图集已经接近 4096 上限，代价大。

### 和 adaptive-element-v1（v35b）的关系

- 自适应改的是 `BattleCharacterLogic.getElement`。规则：已学会 `wfx_adaptive_<能力键>` 的能力，且自己不是队长时，取 slot0 队长的 `get_originalElement()`。
- 开战快照（`CalculatedBattleCharacterLogic` / `SquadMemberSource`）、`BattlePartyLogic.matchCharacterGroup` 和 `getNumberOfSameElement` 读的都是同一个 `get_element()` 缓存，所以**自适应后的属性参与共鸣计数，kind 2 和 208 都一样**（run2/party/notes.md:44）。
- 编成画面和属性限定关走 OwnedCharacter 路径，仍按原属性。所以编成界面可能显示不满足，进战斗后实际满足。界面差异**未核实**。
- 搭配建议：水杰拉德带自适应，加上自己的共鸣行用 208，放进任何单属性队都不会破坏共鸣，自己的门也能满足。**他当队长时保持水属性**，这时要求全队是水。

### 如果坚持做「新属性串」补丁（只有阈值 <6 或需要「共鸣属性角色」动态目标时才值得做）

先说明：阈值 6 已经可以用 208 零补丁实现。下面的草图只在需要更灵活的场景时才有意义。

1. **数据**：character_tag 表加一行 `AnyElement,共鸣属性`，让 resolve 走 `CharacterGroup.CharacterTag` 分支，不触发 2038。文案里的组名也取这一列。character_tag 现有 3 行。
2. **补丁 1（核心，单方法）**：`BattlePartyLogic/matchCharacterGroup(Array):int` 入口插入约 12 条指令：`groups.length==1 && groups[0].index==4 && groups[0].params[0]=="AnyElement"` 时 `return this.getNumberOfSameElement()`，否则落回原 #0。常量池只追加 1 个字符串，不新增类或槽。这一处就能让前置 2、瞬发 57、编成计数文案都按「任一属性最多人数」生效。
3. **补丁 2（可选，动态目标）**：给 `SquadMemberSource/matchCharacterGroup`（战斗目标判定用，`pinball/common/data/battle/squadMember/SquadMemberSource.as:209`）和 `BattleCharacterLogic/matchCharacterGroup` 的 case 4 加判断：AnyElement 等价于「自身属性 == 队伍主属性」。但 SquadMemberSource 拿不到队伍引用，得在开战快照时缓存队伍主属性（静态槽），侵入性大，**不推荐**。
4. **按 v35 惯例交付**：输入 v35e（`89461f67…`），方法体 sha+header 双锁。验证用真实字节码 avm_interp 对照：老数据逐项一致，新案例覆盖 6 同属性 / 5+1 / 3+3 / 空槽 / 自适应 / character_tag 缺失。变异必须变红。除目标方法外逐字节不变。`--from-v34` 串联重放一致。归档编号接 **132**。capability 草稿可叫 `any-element-group-v1`。

### v35 补丁链惯例

依据 run5/README、registry-draft.json、TASK1..5：

- 每轮一个 `runN\`，只在该目录写文件。输入 SWF 的 sha 对不上就停。
- 只准做三件事：单方法指令级拼接、给已有类追加助手方法或静态槽、往常量池追加字符串。
- 禁止 FFDec 整类回编（F1069 前科）。不能 getlex 新类进战斗。主表只用不抛异常的读法（先 exists 再 get）。回跳必须落在真实 avm_label 上。
- 锁文件：baseline-locks（原 sha/header）和 release-locks（最终 sha）。已打过返回 `already_present`，未知 sha 拒绝。
- 验证四件套：真实字节码解释器做旧/新对照、变异复审（末轮基线必须全绿）、其余方法逐字节不变、v34 串联重放。
- 交付物：registry-draft（capability / effect_codes / effect_flags_overrides / custom_ability_string_patterns）、`apk-patches-additions\NNN-*`、中文 README。

---

## B1 进 Fever 时立刻触发全部 PF 类型

### 官方 PF 树

角色的 PF 类型由 `speciality_type` 决定（`SpecialityTypeTools.as:91-108` 0..4 → knight/fighter/ranged/supporter/special，`GeneralCharacterLogic.as:102`）。`PowerFlipLogic.as:34-77` 用 `<路径>:<属性>` 作为键取 DSL。逻辑路径是 `battle/action/power_flip/action/<族>$<族>_lv<N>.action.dsl.amf3.deflate`。`D:\WF\resources\game\wf-assets\upload` 里 15 棵全有；kulo 视图 store 缺 knight/ranged/supporter 时，从 APK `assets/bundle.zip` 取（hw/research/apk_pf 有现成副本）。

| 族（中文类型） | Lv3 结构要点 | suppress | 629 执行风险 |
|---|---|---|---|
| knight 剑士 | 圆 280 骑球（-18，AB/CD）110 帧，6.3/段，最多 5 段 | 110 | **已实证**：塞里奥尔 1.4.222 |
| fighter 格斗 | 90 帧内撞敌（CollisionOfBallAndEnemy）后 StopBall 24 帧，GH 扇形 7 段 | 90+24 | 撞不到敌人就零伤害；StopBall 会停球。未核实 |
| ranged 射击 | 3 道 4000 长光束（EF 挂 -18）：0.75×NWay2、1.33×NWay2、3.75×1 | 35 | EF 挂球是安全的；未核实 |
| supporter 辅助 | Wait 29 后 NotifyEnd；全屏 1500×2000 4.0×1；全队攻击 +50%（240 帧）、贯通和浮游（150 帧） | 无 | 只删 NotifyPowerflipEnd；未核实 |
| special 特殊 | 光环 90 帧，撞敌后圆 350：4×3 段 + 9×1 | 90+30 | 同 fighter，要撞敌；未核实 |

各族 Lv1/Lv2 同路径换 `_lv1`/`_lv2`。官方 `power_flip_action` 表另外只有 5 行：special、ruin_girl/thunder_dragon（=empty）、`override_psycho_reaper_meteor23`、`override_wind_spgirl_4anv`。

### 触发和先例

- 「进入 Fever」= **瞬发触发 kind 8**：`InstantAbilityTriggerMasterValueTools.as:44-46` 的 `Count(3, 阈值)`。在 `FeverPointGaugeImpl.as:360-371` `enterFeverState` 里，先切到 Fever 状态，再 `countUp(3)`，所以触发时 Fever 持续判定已经为真。c30/c31 写 100000，每次进 Fever 都触发。Fever 结束是 184（`:190`），Fever 中按帧是 248。
- 先例：
  - 赛瑞斯 `1299993` 用 8 + 629 放龙息，作者真机验收过。
  - 索维 `1211773` 用 8 + 226 连击。
  - 塞里奥尔 `hw_kit_seriol.py:pf3_tree` 用 629 跑 knight_lv3：根头 `t[10]=133`，递归删掉 `SetPowerFilpSuppress`/`NotifyPowerflipEnd`。1.4.221 没删时崩 U_e66385，1.4.222 修复。
- 伤害归属：629 原生把 ActionKind 硬编码为 AbilitySkill，归技能伤害（memory wf-invokeskill-629）。v28 起的伤害分类补丁（`D:\WF\air-platform-20261017\client-patch\author-content-1043\rules\damage.py`，归档 20-damage-type-conversion）会让 `Environment.getBuffTargetAs` 透传 101/102/104/131..133。根头写 133 后，`createdByPowerFlipAction=true`、`powerFlipChargeLv=3`，于是伤害标签、PF 分档、乘区5 和 PF 耐性都按 PF Lv3 算。

### 推荐数据做法

- 5 个新 DSL：`battle/action/skill/action/ability_skill/<code>_pf_<族>$<code>_pf_<族>`，内容是官方 Lv3 树副本。
  - 改 `tree[10]=133`，递归删掉两条 PF 专用命令，其余（判定区、特效、`CreateNormalAttack` 元素 255 跟随施放者属性、震屏）原样保留。
  - 用 `wf_dsl.encode_amf3` 往返自检。构建后断言 `CreateNormalAttack` 还在（吸取 1.4.228「删整句」事故教训）。
- 5 行 ability 记录，可以放在同一个能力键下（一键最多 9-10 条）。每行写：
  - c47=`629`，c70=字符串键，c71=路径
  - c27=`8`，c30/c31=`100000`
  - 前置条件按需：例如 c6=208 共鸣
  - c1=false（主位）。memory 记录过「629 副位禁用」，这条未核实，按主位做最稳。
- **5 棵树建议错开**：c46 `instant_delay` 以秒为单位（客户端乘 60），例如 0、0.4、0.8、1.2、1.6。避免同一帧特效面片峰值（memory wf-maou-fx-lag）。官方用 c46 的只有 2 行，**629 配 delay 未核实**。
- 风险：
  1. fighter 和 special 只在 90 帧内球撞到敌人才出伤。
  2. 一场战斗额外加载 4 族 PF 特效图集，碰战斗图集预算（剩余约 1.5Mpx，memory wf-atlas-budget-1016），需要实测三人房。
  3. 133 转换后算真 PF 攻击，可能会派发 PF 命中类触发（15-17、180-183）。因为触发源是 Fever 开始，不会递归，但要确认队里有没有「PF 命中时」的词条会被白蹭。

---

## B2 Fever 中强化弹射伤害翻倍

PF 乘区顺序见 `pinball/online/battle/impact/attack/NormalAttackCalculator.as:422-474`：

- 通用池 `(1 + PowerFlipDamage + PF特攻 + LvNDamageAdd)`，在 `:422-445`。
- **乘区5** `(1 + PowerFlipLvNDamage + SeparatedTermPowerFlipDamage)`，在 `:447-462`，只对 `createdByPowerFlipAction` 且档位 1-3 生效。
- 场地 `SeparatedTerm2ndPowerFlipDamage`，在 `:466-474`。

`getStatModifierSeparatedTermPowerFlipDamage` = 战斗级合计 + 状态（`MemberImpl.as:3500-3503`）。持续行按 sum 累加（`BattleAbilityTotalizerImpl.as:217-221`）。

| 方案 | 写法 | 结果 | 评价 |
|---|---|---|---|
| **A（推荐）** | ability：c5=1，c97=`4`（Fever），c109=`413`，c113/c114=`100000`，可加 c6=208/c9/c10=600000；leader：c3=1，c95=4，c107=413，c111/112=100000 | 乘区5 +100%，面板「（独立伤害乘区5）」 | 纯数据。官方 413 只有 3 行，强度都只有 3-6%，100% 远超官方档。乘区5 里如果还有 PF LvN 伤害或其他 413（比如赛瑞斯龙形 15%），结果是 ×(1+Σ)，不是严格 ×2。不要挂累积瞬发触发（C2308 前科），用持续行 |
| B（精确 ×2） | 队长位 419 during，持续触发 4，指向 override 键。三档树用本族官方树，`CreateNormalAttack` 倍率全部 ×2 | 原生 PF 伤害严格 2 倍，和任何加成池都无关 | 只在**本人是队长**时生效，只换本人这一族。419 条件求值时 enemy=null，Fever 不需要敌人上下文，可行。实现量大 |
| C | DSL `StartModifierField` 的 SeparatedTerm2ndDamage(PF) | 真正独立的一层 | 场地是全场单槽，会和其他场地互相覆盖，而且时长固定不跟 Fever 结束。不推荐 |

B1 那 5 棵转成 PF Lv3 的树，在 Fever 中同样吃方案 A 的乘区5。

Fever 相关条件汇总：

- 前置条件：12 Fever、186 NotFever
- 持续触发：4 Fever、193 NotFever
- 瞬发触发：8 进入 Fever、184 Fever 结束、248 FeverFrame
- 持续累积触发 248 的官方先例：`1510993 airship_captain_3`

---

## B3 Fever 中连击 +30（可和他人叠加）

### 机制

- 489 ConditionComboBoost 的解析在 `InstantAbilitySource.as:4765-4782`：结果是**战斗级状态**，时长恒为 ETERNAL（99999 帧，`CommonBattleConstants.as:42`），叠层上限 1。flip_limit 取 c62，number 取 c59/c60。
- 拍板时序（`BallImpl.as:773-846`）：先算充能档，然后 `expire()` 把连击清零，再 `addCombo(getComboBoostCount())` 回填，上限 9999。`getComboBoostCount` 在 `:2102-2109`，等于小队 conditionSlot 合计加上场地合计。
- 合计方式（`ConditionSlot.as:4451`）：所有 content index 32 的状态，`Σ value × magnification` **直接相加**。
- 状态 ID（`pinball/online/battle/impact/condition/_ConditionId/ConditionId_Impl_.as:23-60`）是 `N//IA-<能力地址>/<body>@<battleId>`，不同角色、不同能力行的地址不同，所以是**独立的两个状态，相加叠加**。同一行再次触发时受叠层上限 1 约束，不会自叠。
- 文案：ui_string:589「连击加成效果[连击 ::count::]」。

### 赛瑞斯 129999 的实现

数据来自编辑器 `/api/characters/129999/ability`，构建器在 `D:\WF\out\赛瑞斯重做-20261015\build\seris_rework.py:345`：

- **队长技第 5 行**：c4=2 Blue≥6，c25=`8`，c45=`489`，c49/c50=`4000000`（40），c57/c58=100000，**c60 flip_limit=(None)**，c72=1。克隆自索维 121177。官方索维写的是 flip_limit 9（9 次拍板），赛瑞斯按作者「不限次」改成了 (None)。结果是**第一次 Fever 之后整场连击保底 40**，不只限 Fever 期间。设计稿 v2:50 写的是「持续 10 次弹射」，和现行数据不一致，需要作者确认。
- 队长技第 6 行：c25=26（自己弹射）+ 226 追加连击 3。
- 龙形技能 DSL 里有 `AddCombo 30`（`seris_rework.py:239` `add_combo=30`）。
- 能力 2 的第 3 行：触发 4（冲刺）+ 226 追加连击 8，CT 60 帧。

### 推荐

- **只要「Fever 中拍板后保底 +30」并和赛瑞斯叠加**：ability 行写 c27=8、c30/c31=100000、c47=`489`、c51/c52=`3000000`、c59/c60=`100000`、c74=`1`，c62 写 `9` 或 `10`（官方口径约等于一次 Fever 的拍板次数）。前置条件按需，可加 208。和赛瑞斯同队时保底是 40+30=70。
- **要严格限定在 Fever 期间**：瞬发触发 6（BallFlip）或 26（自己弹射），配前置条件2 c13=`12`（Fever），内容 `226` 追加连击，强度 3000000，CT=0，次数 (None)。每次拍板在清零后再加 30，效果等同于只在 Fever 中生效的保底，并和 489 相加（`AbilitySlotImpl.as:2289-2299`，上限 9999）。官方没有「Fever 门 + 每拍板 226」的先例（226 在官方共 46 行），**需要金丝雀验证**。
- **进 Fever 时一次性 +30**：官方先例有索维 `1211773`（8 + 226，15 连击）和 `2210173`（8 + 226，40 连击）。

---

## B4 治疗转伤害

### 码 27（overflow-heal-damage-v1，v35b）精确口径

- 采样：在 `MemberImpl/applyHeal` 原 #190 `returnvoid` 前插入（`run2/overflow/patches.py:17`），传入 `_loc4_ - _loc6_`，即总治疗量减有效治疗量（Decimal100）。原方法在 `MemberImpl.as:8316-8360`。
- 排除：拒绝治疗、来自敌方、statsBattleId 不同、createdByCoopCommand、协力球、拿不到治疗者。
- 倍率：治疗者（`originMemberIndex`）身上 `wfx:27:<arg>:<value>:0:<label>`，按 Σ(value×当次层数)/10000 计。arg 0 打全体敌人，arg 1 打最近敌人。
- 结算：同一治疗者 30 逻辑帧聚合一次，在 `SquadManagerImpl/updatePhase` 里 tick。
- 伤害：调治疗者自己的 `applyInstantAbilityEnemyDamage`，reference=3。`AbilityDamageShot.finish`（`AbilityDamageShot.as:159-212`）在原 switch 之前把 reference 3 映射成 `MaxHpParameter(strength, 1)`。到了 `NormalAttackCalculator.as:203-228`，基础值 = strength，**不读攻击力**。
- 后续乘区：属性相克系数（`:234-235`）、敌方属性抗性（`:237-264`）、角色和状态特攻、能力伤害池与独立能力乘区（因为 `createdByAbility=true`）、敌方能力抗性和各类减伤。统计归能力伤害，属性取治疗者当前属性（含自适应）。
- 实测样例（run2 README）：基础 40，能力增伤 +100%，能力抗性 25%，结果 60。
- **总结：是固定数值（溢出 HP × 倍率），不按攻击力缩放，但吃能力伤害加成。**

### 普通（非溢出）治疗转伤害：现有通道都不行

- 官方瞬发触发 19 HealCount（被治疗次数，`InstantAbilityTriggerMasterValueTools.as:77-79`）和 78 HealHigh（单次治疗量 ≥ 绝对 HP 阈值，`MemberImpl.as:8333` 传的是 `cure` 绝对值，`MemberAbilityTriggerImpl.as:136-165`），都只能按「次数」触发固定倍率的能力伤害，**不能按治疗量比例**。
- 可以凑一个近似版：19 或 78 + 388/269-286，实现「每次被治疗时对全体敌人造成 X 倍伤害」。但做不到「每 1% 造成 1 倍」。
- ModifierField `ConvertToAttack` 是伤害类型加成转换，和治疗无关。v33/v34 归档 01-99 和 v35 的 112-131 都没有治疗转伤害。

### 新码设计草图（建议 v35f，码 30，`heal.effective_pct_attack_damage`）

- 数据：`wfx:30:<arg 0全敌/1最近>:<value>:<cap>:<label>`。持有者 = 治疗者，和 27 一致。如果要「队伍受到的任何治疗都算」，可以加 flags 位切换成受治疗者持有。
- 采样：在 `applyHeal` 同一个出口，取有效治疗量 `_loc6_` 和受治疗者 `getRealMaximumHealthPoint()`，算 `pct = _loc6_ / maxHP × 100`，然后 `acc[arg] += pct × Σ(value×层)/10000`。一次群体治疗按每个受治疗者分别累加。
- 结算：复用码 27 的 30 帧队列和 emit 助手，但 reference 用 **2（原生 AttackParameter，基础 = 治疗者总攻击力 × acc，吃攻击 buff）**。`AbilityDamageShot.finish` 不用改。
- 例：「每回复 1% HP 对全体敌人造成 1 倍伤害」= `wfx:30:0:10000:0:hidden_heal_dmg`。cap 表示单次结算倍率上限（0 = 不限），建议必填：满血治疗 50% 会一次打出 50 倍攻击。
- 改动面：`MemberImpl/applyHeal` 在 v35b 插入块上叠加，多传 `_loc6_`，sha 锁要更新。追加 1 个 record 助手。27 和 30 的累加器按 code+arg 分桶。还要登记 effect_codes[30]，以及 capability `heal-damage-v2`（或给 overflow-heal-damage-v1 加 revision）。
- 验证：先对照 27 的老行为逐项一致，再测新场景：正好补满、0 治疗、拒绝治疗、持续回复、30 帧内多次治疗、cap 生效、自适应属性。变异必须变红。

---

## 待核实

1. 编辑器和 wf_describe 对前置 208、触发 257 的翻译与门禁。
2. 629 跑 fighter、special、ranged、supporter 树的真机表现（只有 knight 实证过）；c46 延迟配 629 的组合。
3. 一场额外加载 4 族 PF 特效后的三人房图集余量。
4. 「Fever 门 + 每拍板 226」没有官方先例。
5. 赛瑞斯 489 flip_limit=(None) 导致整场生效，是否符合设计意图。
6. 自适应角色在编成界面和战斗里的共鸣显示差异。
7. icon_tag 新增行的金丝雀测试（缺行会崩，行级合并的推论要验证）。
