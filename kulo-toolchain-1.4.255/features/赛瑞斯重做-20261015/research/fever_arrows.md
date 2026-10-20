# Fever 箭头 → 随机道具 可行性调研(2026-10-15)

源:`D:/WF/decompile-complete-20261014/scripts`(下文 `S/` = `.../scripts/pinball/`),live 视图 WF_TIP=206。
结论先行:**纯数据(队长技/能力/629 DSL/场地效果)做不到**。箭头是地形 TMX 里烤死的物件,运行时没有任何数据口能关掉它或在原位刷道具。要做只能打客户端补丁:2 个战斗方法 + 2 个预载方法,全是单方法拼接,和现有补丁栈不冲突。

## 1. 「Fever 箭头」到底是什么

- 本体:**DashPanel(加速板)**,有 4 个子类 Fixed/Smart/Serial/Rotating(`S/scene/battle/battle/zone/yakumono/dashPanel/`)。它是地形 TMX 物件,类型串形如 `DASH_PANEL_FIXED#45_FEVER`,解析在 `S/terrain/YakumonoParser.as:131-145`,id 转小写在 :186-189。
- 出现时机写在类型串后缀里:`_always/_usual/_fever` → `YakumonoAvailableTime` 的 Always(0)/OnlyFeverMode(1)/OnlyUsual(2)(`S/common/data/battle/yakumono/ObjectTypeTools.as:101-116`)。速度、冷却由 `BattleQuestBaseImpl.resolveDashPanel*` 写死(`S/common/data/quest/battle/BattleQuestBaseImpl.as:1620-1712`),**没有对应的 master 表**。
- 建对象:进区时 `TerrainParser.createZone` 按 TMX 列表逐个 new(`S/scene/battle/battle/terrain/TerrainParser.as:648-722`,case 13-16 是 DashPanel,case 9 是 DirectInstantItem)。
- 开关链:
  - Fever 开始:`FeverPointGaugeImpl.as:364` → `ZoneImpl.enterFeverMode`(`ZoneImpl.as:1726-1734`)→ `YakumonoManagerImpl.activate()`(`YakumonoManagerImpl.as:350-361`,先播 `se_fever_time_yakumono_shine`,再对每个物件调 `activate()`)。
  - Fever 结束:`ZoneImpl.exitFeverMode`(:1676-1680)→ `YakumonoManagerImpl.deactivate()`(:271)。
  - DashPanel 自身:`activate()`(`DashPanelBase.as:576-593`)对 FEVER 板调 onActivated,把碰撞 mask 设为 16,播 open 动画,外圈换成 `rotation_panel_active`;`deactivate()`(:551-568)反过来。碰到球时 `resolveCollision`(:374-414)调 `changePhysicalBehavior(DashPanel(vx,vy))` 把球推走。
- 全库统计(1258 个地形全部解析,0 失败;脚本在 scratchpad 的 scan_terrain.py):
  - DashPanel:`_fever` 2757 个 / `_always` 451 / `_usual` 15。**677 个地形有 Fever 箭头**,另外 581 个没有。
  - DirectInstantItem(地上直接摆的道具):`_always` 1918 / `_fever` 483。

### 场上的「道具」
- 两类,定义在 `S/common/data/item/InstantItem.as`:
  - **Executable**:吃到就以 `ActionType.InstantItem` 执行一段道具 DSL,在 `InstantItemManagerImpl.addAcquiredItem`(:206-250)。
  - **Obtainable**:玛纳之类的收集计数。
- 主表:`master/battle/item/executable_instant_item`(live 39 行,列=动画路径,程序路径)。有回血大中小、技能充能大中小、攻击 UP 及累积攻击 UP 各种变体、贯通、飞行、加速、无敌、净化、减伤、追加直击等,外加我方自制的 `wf_dummy_skill_charge_half`。
- 摆放表:`master/battle/yakumono/direct_instant_item`(46 行,列=kind,eii_id,oii_id,frames_to_repop)。
- 刷新逻辑在 `DirectInstantItemImpl.update`(:152-210):被吃掉后等 frames_to_repop 帧再长出来。FEVER 物件只在 Fever 中重新长。
- **官方「Fever 中出道具」已经有现成形态**:`DIRECT_INSTANT_ITEM#xxx_FEVER`。它站在旋转台上(`DirectInstantItemImpl.run` :280-500 的 FEVER 分支),和箭头共用 `rotation_panel_active` 演出。
  - 185 个地形用了这种形态,其中 142 个有 Fever 道具但没有 Fever 箭头,也就是把箭头换成了道具。
  - 最常见:`ACCUMULATION_ATTACK_POWER_UP_25_500_FEVER` 237 个,其次是贯通、充能、回血。
  - 但它是**按关卡烤死、固定种类**,不是随机,也和队长无关。
- 「随机」的官方来源只有一个:敌人、可破坏物掉落,在 `InstantItemManagerImpl.draw`(:134-200)。每条 odds 行只对应**一种**道具,按概率决定掉不掉(`instant_item_odds` 36 行),掉的东西直接给到球的位置。全库**没有「从多种道具里随机挑一种」的机制**(`InstantItemOddsCandidate` 类存在,但这条路径没有用到它,推断)。

## 2. 现有数据通路逐个排查(都不能把箭头换成道具)

| 候选 | 结论 | 依据 |
|---|---|---|
| 队长技 / 能力内容 kind | 无 | ability_enum_map 全部枚举里不含 Item/Yakumono/Panel 类 kind。trigger 4/5 "Dash" 与箭头无关(推断,未追到触发点) |
| StartModifierField / StartBuffField | 无 | 26 种场地效果全是数值乘区(memory 场地效果卡),getter 只被成员和球消费,碰不到 yakumono |
| DSL 命令全表(110+ 个) | 无 | `S/battle/action/dsl/ActionDslCommand.as:60` 的命令表里没有生成道具、开关 yakumono 的命令。`ChangeFieldAssets` 只能换箭头和旋转台的**动画**(`DashPanelFixed.as:64-69`),推球的行为照旧,而且换的是全场所有板 |
| quest / zone / 地形 | 能做,但不是队长技 | 把地形里的 `DASH_PANEL_*_FEVER` 改成 `DIRECT_INSTANT_ITEM#*_FEVER`,这是官方 142 个地形的做法。缺点:逐关改、种类固定、对所有队伍生效 |
| 纯数据近似方案 | 能做,但没有实体道具,箭头也还在 | 队长技 trigger 8 Fever(或 248 FeverFrame)→ 629 InvokeSkill。DSL 里用 `ProbabilityWeight`/`ConditionalsProbability` 随机走一个分支,分支内容照抄道具 DSL(`battle/action/item/action/*`,只用 CreateCondition/AddSkillPoint/CreateNormalHeal 这些命令)。效果=「Fever 时随机获得一种道具效果」。注意:ProbabilityWeight 在官方 action DSL 里有没有先例**未核**(按阴性结论纪律,用前先跑正向对照) |

## 3. 客户端补丁方案(单方法 P-code 拼接)

**标记**:队长技首行用 trigger 0 Initial + content 461 ConditionUnique,给自己挂一个新的固有状态 UID_FA。上限写 2,不要写 (None) 或 1,见 wf-unique-cap-none-trap。补丁判定:`gear.absorb(SquadManager).getLeader().getConditionAccumulationCount(ConditionTargetKind.Unique(UID_FA)) > 0`。相关代码 `SquadManagerImpl.as:912`、`ConditionTargetKind.as:188`。
- 为什么不读 PlayerLogic:`Battle.as:1279` 建地形时拿的是 GlobalLogic 的**本机玩家**,联机时给队友副本建地形也用它,会判错人。读本 Battle 自己的队长才对每个副本都正确。
- 后备方案:直接比对队长角色 ID,写死在补丁里。

**B1 `YakumonoManagerImpl/activate`(主补丁,原方法 :350-361,pcode 在 `.../yakumono/YakumonoManagerImpl.pcode:1152-1200`)**:在函数开头插入,只在标记成立时生效。
- 遍历 `yakumonoes`,挑出 `is DashPanelBase && values.availableTime.index==1` 的板。如果该板坐标上**还没有**我们建的道具,就新建一个:
  - 选道具:`rng.randomFloat()*N` 从候选表 CANDIDATES 里挑一个 id。
  - `src = new DirectInstantItemSource(id, YakumonoAvailableTime.OnlyFeverMode(null), LV, absorb(BattleQuestLogic).recommendedElement, p.asset)`
  - `it = new DirectInstantItemImpl({x:p.x, y:p.y}, src, p.rotationPanelAnimation)`
  - `yakumonoes.add(it); gear.addChild(it)`。gear.addChild 会触发 it.run(),初始状态是 Inactivated。后面原有的循环会对它调 activate → onActivated → popItem,道具就出现了(推断,需真机确认)。
- 原有循环改为:标记成立时**跳过**上面那类箭头板,箭头保持关闭,也不播 open 演出。其余物件和无标记的战斗行为完全不变。
- 用到的类(DirectInstantItemImpl、Source、AvailableTime)在战斗 ABC 里已被 TerrainParser 和本类引用,不是新引入的类(推断 multiname 在同一 ABC,拼接前要核)。

**B2 `YakumonoManagerImpl/deactivate`(:271)**:标记成立时同样跳过那类箭头板。否则一个从没开过的板会被调 onDeactivated,多播一次 close 动画和 `RotationPanelClose` 特效(`DashPanelBase.as:551-568`)。我们建的道具走官方 FEVER 道具的 deactivate(`DirectInstantItemImpl.as:772`),原样收起。

**B3/B4 预载(必须做)**:新建的道具动画和道具 DSL 不在关卡的预载清单里,运行时取不到资源会崩(C8016 / 取时间轴抛异常一类)。
- B3 `BattleQuestBaseImpl/resolvePathCollectionForDashPanel`(:1393-1396,原方法只有一行 addSoundEffect):追加 `for c in CANDIDATES: resolveDirectInstantItem(c, LV).resolvePathCollection(param1)`,负责动画和展示层。官方 case 9 就是这么写的(:1518 附近)。
- B4 `TerrainHandler/readHandler`(`S/asset/logic/_LeadingLogicAssetCache/TerrainHandler.as:241`):在 :326 `loadedHandler(param1)` 之前,对每个候选调一次 `resolveDirectInstantItem(c)`(:86-107),负责逻辑层的道具 DSL `program_path:元素`。
- B3/B4 **不做门控**:只在有箭头的关卡里多预载几个小道具件。B3 每块板调一次,builder 是否去重未核(推断它是集合)。
- 公共演出 `instant_item_acquired/appeared/shining` 本来就无条件预载(`BattleAssetPathCollectionBuilder.as:678`),旋转台件也是(:733)。

**参数**:
- **LV**:运行时拿不到 zone.enemyLevel,Zone 上没有这个 getter。道具攻击曲线 `atk_basic_normal` 只定义了 1..100(live 表),越界报 C14520。LV 还决定道具 DSL 用的 SLv,会影响回血和 buff 强度。建议先用常量 1 或 100,和官方同名道具真机对比数值后再定。
- **候选 CANDIDATES**:必须是 direct_instant_item 里已有的键,例如 hp_recovery_small、skill_charge_small、accumulation_attack_power_up_25_500、condition_piercing、condition_speedup、attack_power_up_once。注意 frames_to_repop:1800 以上基本每次 Fever 只出一次;想多刷用 skill_charge_large_wait_short(300 帧)这一类。也可以新增键,新增时 eii 必须带 level 行,否则 C8601。
- **「随机」的粒度**:每个区第一次进 Fever 时,每块板各抽一次,之后固定。想每次 Fever 都重抽,要在 B2 里 removeChild 旧道具(`YakumonoManagerImpl.as:180`),dispose 时视图能否正常清掉要真机验。

**现有补丁栈冲突检查:无。**
- `pflv4_patches.py` 改的是 MemberImpl/startPowerFlip、BattleFlipperImpl/update、BattleFlipperView/draw。
- `overlimit_patches.py` O1-O7 全是角色超限相关逻辑。
- `v28-patched-methods` 列表里没有 Yakumono*/DashPanel*/DirectInstantItem*/TerrainHandler/BattleQuestBaseImpl,只有 AssistYakumonoSource 系,和本方案无关。
- coop-fix 只改了 `BattleDerailleur/getDeferralLevel`。

## 4. 联机与确定性
- 联机时每个客户端会**本地按输入重放队友的 Battle 副本**(coop-fix REPORT §停帧隔离:`BattleScenePlayingStateImpl.as:370-390` 把帧分发给各副本)。所以新增逻辑必须确定、并且只依赖本 Battle 的数据:
  - 标记读本 Battle 的队长,不读 GlobalLogic。
  - 禁用 Math.random。
- 随机数源可选:
  - (a) **复用 `InstantItemManagerImpl.random`**:种子是 `createRandomNumberGenerator(1234567)`(:117-120),基种子是 `smallestBattleId`(`Battle.as:1172` → `RandomSeedFactoryImpl`),全房间一致。代价是占用掉落随机流,但只影响有标记的战斗。
  - (b) **自建 `createSeparativeRandomNumberGenerator(新常量)`**:种子是本 Battle 的 id,DSL 的概率分支也用这一路(`ActionManagerImpl.as:159`,常量 379345)。不会扰动掉落。**推荐 (b)**。
- 道具效果走 `zoneManager.executeAction(ExecutableInstantItemAction…)`,与官方吃道具完全同路。
- 风险:
  - **房间里所有人必须装同一个补丁 APK**。否则未打补丁的客户端会把有标记玩家的副本模拟成箭头推球,球路分叉(推断,未验证副本是否有状态校正)。
  - memory 记录联机只广播 FeverStart、不同步 Fever 结束,所以各端道具收起的时机可能差几帧,这和官方 FEVER 道具的现状一样。

## 5. 待真机验证
1. gear.addChild 之后 run() 是否立即执行,以及接下来 activate 能否正确把道具弹出。
2. 道具和关闭状态的箭头底座叠在一起,观感是否可以接受。
3. LV 取值对道具强度的影响。
4. 无标记的战斗、无 Fever 箭头的关卡,行为与原版逐帧一致(回归)。
5. 双人联机时,有标记一方在两台设备上看到的道具种类一致。
