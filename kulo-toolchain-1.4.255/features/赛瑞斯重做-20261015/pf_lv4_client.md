# PF Lv4 客户端调研(只读)

S = D:/WF/decompile-complete-20261014/scripts/pinball/scene/battle/battle/。这份反编译取自**原版 SWF**;v28/v29 叠加改动以 D:/WF/perf-v30-20261015/analysis/v28-patched-methods 为准(见 §3)。
【推断】= 推出来的,没有逐行读到。

## 结论
1. 让档位整数真的流到 4,有两处会硬崩:`MemberImpl.startPowerFlip` 取 DSL 时空引用(F1009);`ActionEvaluator` CreateNormalAttack 遇到大于 3 的档位抛 ClientError 2702。另有伤害取值变 NaN 等若干处问题。所以档位整数必须一直停在 3,「Lv4」只做成「Lv3 + 换一棵 DSL」。
2. 纯数据可以做到,但**旧配方(kind13 → Unique 条件 → 419+194)当次弹射不生效**。原因:Unique 条件经过 impact 队列,下一个阶段才落地;override 在同一次调用里就求值完了。记忆 wf-powerflip-override 里「同帧桥时序代码已验」这一条是错的。
   能用的数据方案是「722 开关对」:kind13(≥100)和 kind14(≤99)各挂一条 instant 722。这条通路全程同步,当次弹射就生效。
3. 真补丁只需改 1 个方法:`MemberImpl/startPowerFlip`。它不在现有 APK 栈的改动列表里,读的是 v28 九尾补丁已经写好的 `BallImpl.kyubiPowerFlipInitialCombo`(弹射瞬间、清零前的连击数)。
4. 联机走「输入复制 + 结果同步」:PF 档位不上网,每台客户端在队友副本里自己重算。只装一部分补丁会让队友副本演出不同步,必须全员同包。纯数据方案在各端结果一致。

## 1. 管线与档位边界
**拍板(BallImpl.resolveCollisionForPrimaryOrSummons,S/squad/ball/BallImpl.as)**
- :791 算档位 `_loc3_ = comboCalculator.getPowerFlipChargeLv()`
- :794 `powerFlipSuppressor.canInvoke(lv)`(PowerFlipSuppressorImpl:104,只做大小比较,4 也安全)
- :799 快照连击 `_loc6_`
- :803 正在放技能时档位置 0
- :808 `expire()` 清零连击
- :815 `notifyBallFlipWithCombo(1,_loc6_)`,用的是快照
- :836-843 ComboBoost 回填
- :846 `squad.startPowerFlipAction(lv)`
- :851-866 按档位 switch 1..3 计数 `countUp(6/7/8,18,19)`;4 落空,不计数也不崩
- :867 `notifyFlipExecuted(lv)`(BattleAbilityTriggerImpl:391,用 <= 比较,安全)

**档位计算(S/ComboCalculatorImpl.as)**
- `getPowerFlipChargeLv` :284-302 硬返回 0..3
- 阈值 9/15/39 在 boot_ffc6.as:9191-9193;`getPowerFlipNumComboChargeLv1/Lv3` :219-261 带倒数钳制
- `getPowerFlipChargeRate` :263-282 switch 0..3,default `return;`,档位为 4 时得 NaN
- `setPowerFlipChargeLevel` :102-156 只认 0..3(调试和技能预览用)

**Squad 层(S/squad/SquadImpl.startPowerFlipAction :387-460)**
- 档位 0 直接 return false
- 公共演出 `PowerFlip1/2/3` :432-441;得分 `power_flip_lv1..3` :442-454。两处都是 case 0 throw,4 落空(没有公共特效、不计分)
- 语音 `selectRandomPowerFlipVoice` :591 与档位无关;PF 没有 cut-in 通路【推断:没搜到】

**选 DSL(S/squad/member/MemberImpl.startPowerFlip :968-1090)**
- :975-982 只有 `isLeader()` 时才查 `abilityTotalizer.getPowerFlipOverrides(lv)`,非 null 就 `new PowerFlipLogic(id,…)`
- :985-997 switch:case 0 throw;case 1-3 取 `get_powerFlipActionLv1..3`(PowerFlipLogic.as:50-60,表里只有 lv1-3 三列)
- **档位为 4 时 `_loc5_` 保持 null,:998 `_loc5_.params[0]` 空引用崩(F1009)**
- :1038 `ActionKind.PowerFlip(id,lv)` 传入 DSL 执行上下文
- :1063-1084 stats 12-17 按 1..3 计,4 落空

**override 解析(S/ability/BattleAbilityTotalizerImpl.as)**
- `getPowerFlipOverrides` :336-385:先看 instant(722)的 `forLevels.indexOf(lv)`,再按行序扫 during(419)。forLevels 只是 int 数组,**任意整数都能当键**
- 722 的写点只有两个:构造时 :120 置 null,case 19 :628-635 赋值;**不会被清除,只能被覆盖**

**伤害**
- S/action/ActionEvaluator.evalCommand case 15 CreateNormalAttack :2706-2738:从 `ActionKind.PowerFlip` 取档位,**档位不在 0..3 就 throw ClientError 2702**
- online/battle/impact/attack/NormalAttackCalculator.as
  - :422-437 加算项 `getStatModifierPowerFlipLvDamageAdd(lv)`(MemberImpl:3722-3738)
  - :446-458 独立乘区 `getStatModifierPowerFlipLvDamage(lv)`(MemberImpl:3740-3771)
  - 两处都是 switch 0..3,default `return;`,档位为 4 时伤害变 NaN
- 结算统计 `NormalAttackStats.powerFlipChargeLv`(remote/quest/finish/NormalAttackStats.as:89,276)会上报服务端,服务端是否校验未知【推断】

**UI**
- `BattleFlipperImpl.update` :157-198:充能动画和 `se_combo_power_flip_max_lv1..3` 都按 1..3 switch,4 落空
- `BattleFlipperView.draw` :333 用 ChargeRate;:459 帧号 `getCurrentFrame` :255-258 = `rot*10 + (lv+1)*2 + blink`。档位为 4 时帧号是 10/11,窜进下一个旋转档的帧,最后一档时越界【推断:可能 RangeError】
- `PowerFlipChargeLv_Impl_.getNextLevel` 钳到 3
- `ComboIndicator.onComboCreated` :245 有 default,安全
- 自动战斗 `FlipLineSampler` / `RangedPowerFlipRunner` 只判 >0 / ==0,安全
- 画面上没有「PF 等级文字」,档位只靠弹板帧和音效表现

## 2. 纯数据 Lv4
**A. Unique 条件 + 419(194) 当次不生效。** instant 内容 0 → `MemberImpl.applyConditionChangeAbility` → `addSelfImpact`(:8725-8742)。只有 Invincible(index 13)加特定参数时才立即应用;Unique 是 index 31,走 `zoneManager.addImpact` → ZoneImpl:1982 → `ImpactManagerImpl._add` → `impactQueue.add`(:1597)。队列要等 `ZoneImpl.impactPhase` → `proceed`(:1078-1081 / :485)才处理,而 `startPowerFlip` 在拍板同一次调用里就求值了 override。结果是 Lv4 会落到**下一次**弹射。改用 419 的 ComboHigh 也不行,那时读到的是清零后的连击。

**B. 722 开关对(推荐的纯数据方案,同步通路已核实):**
- 链路:BallImpl:815 → `BallFlipWithComboListener.update`(_BattleAbilityTriggerImpl,高档 ≥ 阈值、低档 ≤ 阈值才触发)→ `thresholdCountUp` :222 → `AbilityTriggerHandler.countHandler` → `InstantAbility.apply` :1070(delay=0 时同步执行 `_apply`)→ `AbilitySlotImpl.applyInstantCommonBattle` :2261 → `Totalizer.applyInstantCommonContent` case 19 `OverridePowerFlip` :634。全在 :846 之前完成。
- v29 改过 `AbilitySlotImpl/applyInstant`,只加了 `wfGainCategory` 打标,`applyInstantCommonBattle` 调用还在,已核实。
- 两行 leader_ability:
  - 行1:instant trigger 13 `BallFlipWithComboHigh`(阈值 100,定点 ×100000 编码沿用记忆,未复核),content 722,id=`override_<code>_lv4`,levels "3"
  - 行2:instant trigger 14 `BallFlipWithComboLow`(阈值 99),content 722,id=角色平时 PF 的键,levels "1,2,3"。如果平时本身就有 override,填那个 override 的 id
- 必须条件:delay 0、无冷却、无触发上限。行2 是**必需**的,因为 722 一旦写入就不会被清除。
- 两条阈值互斥,每次拍板都会在 :846 之前把开关重新写一遍。召唤球拍板也会写开关,但不影响主球那一次弹射的判定【推断】。
- 风险:levels 写 "0" 是否能被解析没有验证;行2 指向原生键的语义【推断:可靠,两者都走 `new PowerFlipLogic(id)`】。需要在金丝雀上验证。

**C. 在 lv3 DSL 里用 `ConditionalsCombo`(ActionDslCommand 59)分支:**它读 `ActionEvaluationResolver.initialCombo`(:137 / :848)。原版这个值是清零后的连击;v28 的九尾补丁把它改成拍板快照,但**写死只对 `override_fox_oracle_autumn_dual_pf` 生效**(ActionEvaluationResolver ctor v29 #117-#149)。新角色用不上,除非再改这个方法(与 v28 重叠)。

**数据方案能/不能表现的**
- 只能表现 DSL 里写的东西:范围、倍率、特效、SE、语音(ShowEffect 的 sound)
- 弹板光效、充能音效仍是 Lv3
- 公共 `PowerFlip3` 特效、`se_player_kaitengiri`、`power_flip_lv3` 得分照常出现
- stats 14/17、任务/触发器把它算作 PF3 次数(PowerFlipLv3、countUp 8/18、ContinuousPowerFlipLv3 都会走)
- 「PF Lv3 伤害提升」类 buff 全部生效(乘区 lv=3)
- 不会触发 ClientError 2702
- 只在队长位生效

## 3. 最小真补丁
**现有 APK 栈改动的方法**
- 超限 O1-O7(D:/WF/out/角色超限-120/apk/overlimit_patches.py):`GeneralCharacterLogic/get_maxOverLimitStep`、`getPedestalImagePath`、`getHalfPedestalImagePath`;`OwnedOverLimitLogic/getOwnAwakingCrystalToOverLimit`、`getAwakingCrystalToOverLimit`、`getOverLimitState`;`OwnedCharacterLogic/getPossibleOverLimitCountByItem`。都是局外方法,与本次无重叠。
- perf v30(tools/perf2_patches.py):P1 `MasterBinaryMap/getIndex`、S1 `ShopFirstOpen$/productIds`、S2 `ShopTopScene/listCellEnabledResolver`、B1 `Restore/saveBattleRestore`、C1 `CharacterUseCaseBase/getListCharactersInParties`。无重叠。
- coop v29:只改了 `BattleDerailleur/getDeferralLevel`。无重叠。
- v28 历史栈:v28-patched-methods 共 1311 个方法有差异,大多只是跳转偏移或 newfunction 编号的噪声。与 PF 相关、**真有语义改动**的:
  - `BallImpl/resolveCollisionForPrimaryOrSummons`:每次拍板都写 `this.kyubiPowerFlipInitialCombo = maskBit^_loc6_`,即清零前的原始连击
  - `ActionEvaluationResolver/ctor`:九尾 id 过滤,见 §2C
  - `ActionEvaluator/evalCommand`:WFX `wfGaugeContext`
  - `AbilitySlotImpl/applyInstant`:`wfGainCategory`
  - `MemberImpl/applyInstantAbility`
  - `BattleAbilityTotalizerImpl/addDuringContent`:WFX 新 kind 21
- 只有跳转/编号噪声、无语义差异的:`ComboCalculatorImpl/decreaseComboTo`、`BattleFlipperImpl/update`、`NormalAttackCalculator/calculate`、`getPowerFlipOverrides`
- **`MemberImpl/startPowerFlip` 不在列表里**

**方案(只改 1 个方法:`MemberImpl/startPowerFlip`,用 P-code 单方法拼接)**,在 :975 的 isLeader 分支内:
```
if (isLeader()) {
  id = null;
  if (param2 == 3 && (ball as BallImpl) != null && BallImpl(ball).kyubiPowerFlipInitialCombo >= 100)
      id = battle.abilityTotalizer.getPowerFlipOverrides(4);   // 新键:forLevels 含 4
  if (id == null) id = battle.abilityTotalizer.getPowerFlipOverrides(param2);  // 原逻辑
  if (id != null) param1 = new PowerFlipLogic(id, param1.element, logicAssets);
}
```
- 数据:该角色的 leader_ability 挂一条 722(常驻 instant,触发器用 Initial)或 419(可加条件门),levels "4",id=`override_<code>_lv4`。lv4 DSL 放在**lv3 列**,因为 param2 仍是 3,后面的 switch 和伤害乘区都走 3;lv1/lv2 列指 empty。
- 其他角色:没有 forLevels 含 4 的行,`getPowerFlipOverrides(4)` 恒返回 null,走原逻辑,行为不变。多出的只是一次无副作用的查询(DuringChecker.getActiveCount 是纯读)。
- 读字段的写法照抄 v28 九尾补丁:`astype BallImpl` 之后 `getproperty kyubiPowerFlipInitialCombo`。字段里存的是原始 int,不用再异或 maskBit。
- 依赖:要求 APK 里已有 v28 的 BallImpl 补丁(v29/v30 已包含)。
- 阈值 100 可以写死;想做成数据驱动,可以约定 forLevels 键 = 1000+N 表示连击 ≥N(需要多写一段循环,不推荐)。

**可选的第 2/3 个方法(只为「看起来像 Lv4」,不碰伤害)**
- Lv4 演出放进 DSL(ShowEffect 加 SE/语音),不用补丁
- 如果要拍板前「Lv4 就绪」提示,只能在 `BattleFlipperImpl/update`(只有噪声差异,可以改)里加「连击跨过 100 且队长是该角色」时播一次 SE。弹板发光要新帧资源:getCurrentFrame 每个旋转档只有 10 帧,不建议做
- 如果要独立的「PF Lv4 伤害提升」词条乘区,需要再改 `MemberImpl.getStatModifierPowerFlipLvDamage`(:3740)并新增 totalizer 字段,成本明显变高,不建议

**不要做的事**:把档位整数改成 4。连带要改 `getPowerFlipChargeLv`、`getPowerFlipChargeRate`、`startPowerFlip`、`ActionEvaluator.evalCommand`(2702,与 v28 重叠)、两个 `getStatModifierPowerFlipLv*`、`NormalAttackCalculator`、`getCurrentFrame` 和弹板图集,另外 PowerFlipLogic 表里没有 lv4 列,而且要上报服务端统计,共 8 处以上。

## 4. 联机
- 每台客户端都给队友跑一份 `otherBattles` 副本(BattleScene.as:161/824),靠 `BattleUserCommand`(OperationOfFlipper、Ball 等)经 `BattleDerailleur.addSocketCommand`(derailleur/BattleDerailleur.as:568)驱动。**PF 档位不发包**,在副本里由复制出来的连击重算。
- 对敌伤害按结果同步:`ImpactResult.as:160` → `BattleZoneCoopCommand.Impact`。另外还有 EnemySync、FeverStart 等结果命令(BattleZoneCoopCommand)。
- 只部分玩家装补丁时:装了的人本机打 Lv4,没装的人看到的副本打 Lv3。范围、演出、PF 期间的球运动和副本内触发器都会不一致。伤害数值大概率以拥有者发出的 Impact 为准,不会直接错血【推断:副本自己产生的 impact 是否被抑制,没有逐行核实】;球位置靠 Ball 命令纠偏【推断】。
- 结论:补丁方案必须全员同 APK。纯数据方案 B 是确定性的,各端结果一致,只要求各端 master 数据相同。
