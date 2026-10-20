# 弹板 Lv4 红光+闪电 客户端调研(只读)

S = D:/WF/decompile-complete-20261014/scripts/pinball/scene/battle/battle/,F = S/flipper/。【推断】= 没有逐行核实或没上真机。

## 结论
1. 弹板发光**没有独立的光效层**。它就是弹板本体 starling `MovieClip` 换帧(`battle/common/layer0/flipper/f*`,在 `battle/common/layer0.png` 公共图集里),另外叠两层 parts 动画:twinkle/spark(charge 和 spark 到 Lv3 时会隐藏)。
2. 推荐方案 (a):改两个方法,P-code 单方法拼接,不加类、不加字段、不加资源。
   - `BattleFlipperImpl/update`:判定「Lv4 就绪」,把结果编码进现有字段 `prevPowerFlipChargeLv=4`;跨入 Lv4 时播雷 SE;每 N 帧在左右弹板各放一个现成的闪电 HitEffect
   - `BattleFlipperView/draw`:读 `prevPowerFlipChargeLv==4`,给 4 个弹板 MovieClip 染红,给 twinkle 叠 `red()`
3. 方案 (b)「新增弹板帧」不建议。要重打公共图集 layer0(全战斗共享,有 4096² 预算/C8004 风险)、改帧号公式 `getCurrentFrame`,弹板皮肤(蒸汽朋克)也得各配一套。
4. 联机没有同步问题。弹板逻辑和视图都只在本机自己的 battle 里创建,队友副本里没有弹板。
5. 重叠:`update` 在 v28/v29 里只有 newfunction 编号噪声,可以改,但**必须拿 v29 字节当基线**;`draw` 在现有栈里任何地方都没被改过。

## 1. 现状管线
**逻辑侧 BattleFlipperImpl(F/BattleFlipperImpl.as)**
- 只有自己的 battle 才创建:S/zone/ZoneImpl.as:747 `battle.__isMyBattle__() ? some(new BattleFlipperImpl) : none`;每帧由 ZoneImpl:387-390 调 `update()`
- `run()` :355-359 建 5 个 Playhead,时间线路径:
  - 本体 `battle/common/layer0/flipper`(皮肤开启时换成 `flipper_animation_path`,:309-316)
  - `.../flipper_powerflip_charge` :579、`.../flipper_powerflip_twinkle` :441、`.../flipper_powerflip_spark` :446、`.../flipper_guide_point` :498
  - 帧图列表 `getFixedAppearanceImageList` :501-513 = `battle/common/layer0/flipper/f`(皮肤开启时换成 `flipper_movie_clip_path`)
- `update()` :131-262
  - :157 `_loc3_ = comboCalculator.getPowerFlipChargeLv()`
  - :158-162 档位下降时 charge/spark 跳 "one"
  - :163-183 档位上升时按 1..3 切换 twinkle/charge/spark 序列
  - :184-196 充能音:`se_combo_power_flip_max_lv1/2/3`(sound_effect/battle_common/,走 `viewOrder.playSoundEffect(Me,…)`,不受 activated 门控)
  - :198 `prevPowerFlipChargeLv = comboCalculator.getPowerFlipChargeLv()`
  - 档位为 4 时两个 switch 都落空,不崩
- `prevPowerFlipChargeLv` 只有本类自己读写(:62、:118、:158/:163、:198、:392),全仓 grep 没有其他读者。所以可以借这个字段存 Lv4 状态
- 每帧便宜可读的值:
  - 连击:`comboIndicator.getCurrentCombo()` = `maskBit ^ comboCalculator.getCombo()`(S/zone/combo/ComboIndicator.as:311-314,已经解过掩码)
  - Lv4 行存在:`battle.abilityTotalizer.getPowerFlipOverrides(4) != null`(S/ability/BattleAbilityTotalizerImpl.as:336-385)。instant(722)命中时是 O(1);只靠 during(419)时每次调用都会 new 一个闭包。没有现成的缓存查询
  - 这个查询和 startPowerFlip 用的是同一个 battle 级 totalizer(MemberImpl.as:977),所以发光和实际打出 Lv4 的判据一致

**视图侧 BattleFlipperView(F/BattleFlipperView.as)**
- 只有 owner==-1(本机)才创建:S/../view/BattleView.as:1863 `case 88: new BattleFlipperView`;他人 battle 分支 :2418 的 case 88 是空的
- 构造器 :141-200 建以下对象:
  - `fixedAppearanceAnimationL/R`(出场动画)
  - `backgroundL/R`、`foregroundL/R`:`getFlipperAnimation` :264-273,starling `MovieClip`,`textureSmoothing=NONE`
  - `chargeAnimationL/R`、`twinkleAnimationL/R`、`sparkAnimationL/R`:flatomo PartsAnimation
  - 图层:flipperLayer / flipperChargeLayer / flipperTwinkleLayer
- `draw()` :275-473 每帧执行
  - :333 取 ChargeRate,驱动 mask 宽度(fixedBackground 被 mask 截出充能条)
  - :436-440 rate==0 或 1 时隐藏 charge/spark。Lv3 恒为 1(ComboCalculatorImpl.as:263-282 case 3 return 1),**所以 Lv3 时可见的只有本体帧和 twinkle**
  - :459-471 本体帧号 `getCurrentFrame(rot, lv, blink, isFg)`(:255-258)= `rot*10 + (lv' + (lv==0?0:1))*2 + blink`,其中 fg 用 `getNextLevel`
    - bg 帧号:lv0→0、lv1→4、lv2→6、lv3→8
    - fg 帧号:lv0→2、lv1→6、lv2→8、lv3→8
    - 每个旋转档 10 帧,4 档共 40 帧【推断】
  - starling `MovieClip.set currentFrame` 越界抛 ArgumentError(starling/display/MovieClip.as:393-398),印证了「档位整数不能真变 4」
- HUD:没有 PF 等级显示。ComboIndicator.onComboCreated :238-261 只在 lv0-2 播 `se_combo_power_flip_charge_lv2`

**染色能力(全是现成 API)**
- 战斗内 Mesh 默认样式是 BattleDefaultMeshStyle(view/style/BattleDefaultMeshStyle.as:8,继承 ColorOffsetStyle;BattleView.setupMeshDefaultStyle :2442)
  - `red(true)` = 加偏移 R+1/G-1/B-1,整片纯红,即受击闪红,:91-110
  - `setDefaultColorOffset(r,g,b)` :78-89
- `Mesh.color` 是乘法 tint(starling/display/Mesh.as:245,MeshStyle.as:227-242)。每次 set 都会 `setVertexDataChanged`,**必须先比较再写**
- flatomo `PartsAnimation.red(b)` 自带幂等判断(flatomo/animation/parts/PartsAnimation.as:443-451)。另有 `set_color`(带 previousColor 守卫,:288)和 `setColorTransform(mul,r,g,b)` :304
- 每帧调 red() 有先例:MemberView.as:444 `character.red(member.isDamageFlashing())`
- 滤镜先例:CutinQuestClearView.as:38-57 用 ColorMatrixFilter.adjustHue。要离屏渲染,移动端更贵,只作备选

## 2. 方案 (a):两个方法的补丁
**A. `BattleFlipperImpl/update`(基线 v29:newfunction 编号是 62995/62996,不是 orig 的 63455/63456)**
```
// 替换 #0063-#0068(:157)
lv = comboCalculator.getPowerFlipChargeLv();
if (lv == 3 && comboIndicator.getCurrentCombo() >= 100
    && battle.abilityTotalizer.getPowerFlipOverrides(4) != null) lv = 4;   // 短路:只在 Lv3 且 ≥100 时才查
// :158 「<」分支:加 if !(lv==3 && prev==4),避免从 4 掉回 3 时把 charge 打回 "one"(看不见,但更干净)
// :163 「>」分支里补 lv==4:twinkle 跳 "three"(或保持),并
//   viewOrder.getLazySoundPlayer(BattleSoundMode.Me) → Some(p) → p.playSoundEffectWithRepeat("sound_effect/thunder/se_charge_with_electricity",1,1)
// :198 改成 prevPowerFlipChargeLv = lv(getlocal_3,这时 _loc3_ 还没被导引点代码复用)
// 新增:if (lv==4 && frameCount % 24 == 0) 在左右各放一个
//   battle.effectManager.show(EffectKind.Simple(SimpleEffectKind.HitEffect(
//     SimpleEffectPosition.FixedPosition(flipperLeft.flipper.x ± dx, flipperLeft.flipper.y), false, PATH, false, null)))
```
- HitEffect 能放任意已加载路径(S/effect/EffectManagerImpl.as:439-451)
  - 第 2 参填 false:不消耗特效 RNG(Xorshift(1234567),:70,只给特效用)
  - key 填 null:`supressHitEffect` 遇 null 直接返回 false(:103-106),不会被节流
- 视图走 hitEffectLayer(BattleView.as:1643-1656),只在本机显示;SimpleEffect 播完序列自动回收(SimpleEffect.as willRemove/case 2)
- 坐标系:弹板 view 直接用 `flipper.x/y`(BattleFlipperView:150-153),PF 公共特效用 ball.x/y,两者同一坐标系。dx≈±60 是初值,要在真机上调【推断】
- 自己的 battle 里 `canPlayEffect` 恒为 true(:674-679);跨入 Lv4 时 :163 `4>3` 成立只播一次 SE,放 PF 后走 `<` 分支恢复原样

**B. `BattleFlipperView/draw`(插在 :471 之后,activated 分支内)**
```
lv4 = (flipper astype BattleFlipperImpl).prevPowerFlipChargeLv == 4;
c = lv4 ? 0xFF5050 : 0xFFFFFF;
if (backgroundL.color != c) {            // 守卫:只在状态切换的那一帧写
   backgroundL.color = backgroundR.color = foregroundL.color = foregroundR.color = c;
   // 可选:四个 MovieClip 的 style(BattleDefaultMeshStyle).setDefaultColorOffset(lv4?0.25:0, lv4?-0.1:0, lv4?-0.1:0)
   twinkleAnimationLeft.red(lv4); twinkleAnimationRight.red(lv4);
}
```
- 每帧开销只有 1 次 astype、1 次字段读、1 次 color 比较,切换那一帧才写顶点;染色在 MovieClip 上,皮肤开启也生效
- 乘法 tint 的效果取决于 Lv3 帧原本的颜色。白、金色光会变红,蓝色光会变暗,要真机调色(乘法 + offset 组合)【推断】

**开销与安全**
- 只有 `lv==3 && combo≥100` 才查 override,数据侧建议 Lv4 行用 722 instant(O(1))。若改用 419,该区间内每帧会 new 一个闭包,可以改成 `frameCount%6==0` 才查,沿用上一帧的结果
- 拼接需要的 multiname 全是别处已用过的公有名:
  - getCurrentCombo、abilityTotalizer、getPowerFlipOverrides、effectManager
  - EffectKind/Simple、SimpleEffectKind/HitEffect、SimpleEffectPosition/FixedPosition(用例见 S/impact/ImpactHitEffectManager.as:82)
  - getLazySoundPlayer、playSoundEffectWithRepeat、color、red、prevPowerFlipChargeLv
  - 预计都在原池范围内【推断:要逐个查 ABC 池】。header 的 max_stack/local_count 按需调大,做法同 perf v30
- 不要用非懒加载的 `playSoundEffect` 播非 battle_common 音:没加载会抛 C8010(pinball/asset/sound/SoundAssetContainer.as:119-123)。懒加载通路 `loadAndPlayWithDetail` 在 ProductionSoundSection.as:228-253,要求音效在 SoundEffectAssetTable 里;首次播放有加载延迟【推断】
- 也可以零风险复用 `se_combo_power_flip_max_lv3` 加 `se_player_kaitengiri`,但辨识度低

## 3. 现有 APK 栈重叠核对
| 方法 | v28/v29(analysis/v28-patched-methods) | perf v30 / coop v29 / 超限 O1-O7 |
|---|---|---|
| BattleFlipperImpl/update | 有文件,diff 只差 2 行:#0182 `newfunction [63455→62995]`、#0202 `[63456→62996]`。原因是 v28 增删方法导致闭包 method 索引整体平移,没有语义改动。v29-vs-original.json 的 changed 列表里也没有它 | 无 |
| BattleFlipperView/draw | 无 | 无 |
| ComboIndicator/* | 无 | 无 |
| EffectManagerImpl/show | 无 | 无 |
| MemberImpl/startPowerFlip(前一份报告) | 无 | 无 |

- 「只是跳转/编号噪声」的含义:补丁必须基于 v29 的 update 字节计算偏移,并原样保留 newfunction 62995/62996。拿 orig 的 pcode 去拼,会把两个闭包指到错误的方法上

## 4. 联机
- 弹板逻辑只在 `__isMyBattle__` 时存在(ZoneImpl:747),视图只在 owner==-1 时存在(BattleView.as:1863 和 :2418)。每台客户端只画自己的弹板
- 红光、闪电、SE 都是本地纯表现,不进网络命令,也不影响确定性
- 闪电 HitEffect 走自己 battle 的 effectManager,owner=-1,只有自己看得到
- SE 用 `BattleSoundMode.Me`,他人 battle 里 owner≠-1 时直接返回 {}(BattleView.as:4447-4450)
- 唯一的联机要求来自前一份报告:Lv4 的 DSL 本体需要全员同 APK。发光补丁本身不加新要求;没装补丁的人只是看不到自己的红光

## 5. 可直接复用的现成资源(都由 addCommonAssets 无条件加载,文件:pinball/asset/builder/BattleAssetPathCollectionBuilder.as)
| 用途 | 逻辑路径 | 加载位置 | 说明 |
|---|---|---|---|
| 闪电(首选) | battle/common/layer0/condition/paralysis_ball | :710 无条件 | 麻痹电弧,黄色;MemberImpl.as:6049 在用 |
| 闪电 | battle/effect/hit/normal_damage/thunder_small/thunder_small | :757 无条件 | 雷属性命中特效 |
| 闪电 | battle/effect/hit/condition/enfeebling_paralysis/enfeebling_paralysis | :710 无条件 | 麻痹付与命中 |
| 冲击 | battle/common/layer0/attack_to_hostile_smash | :645 无条件 | |
| 红色粒子 | battle/common/layer0/effect_particle_attribution/effect_particle_attribution_red_large/medium/small | :702 **仅 WeightSavingMode==0** | 省电模式下没加载会崩,不要用,或者先判模式 |
| PF 原生 | battle/common/layer0/flipper_powerflip_spark / _twinkle / _shot3 | :599 | spark 在 Lv3 被隐藏,可在 draw 里强制显示、染红、贴到弹板上(备选) |

- 不建议用(只在对应角色或boss在场时才加载,不在就崩 C8003/8004【推断】):
  - battle/effect/hit/normal_damage/thunder_light(有独立 atlas)
  - skill_unique/thunder_archer、electro_girl、thunder_dragon 等
  - enemy_unique/*thunder*
- 现成闪电资源**都不是红色**。HitEffect 的视图从弹板这里够不着,没法再染色。要「红色闪电」只有三条路:
  1. 接受黄电 + 红弹板
  2. Lv4 角色自带的 PF DSL/特效包里放一个红闪电资源,并在 lv4 DSL 里引用,保证随角色预载;HitEffect 再指向这个路径【推断:由角色 DSL 引用的 parts 会随战斗预载,需金丝雀验证】
  3. 方案 B 的 draw 里改走 spark 强显染红
- 音效候选(sound_effect/,要走懒加载):
  - thunder/se_charge_with_electricity(蓄电,最贴「就绪」)
  - thunder/se_lightning
  - thunder/se_far_thunder_strong
  - battle_special/se_thunder_skill_chain_attack_small

## 6. 方案 (b) 新帧,不建议
- 本体帧在公共图集 `battle/common/layer0.png` / `layer0.atlas.amf3.deflate` 的子纹理 `battle/common/layer0/flipper/f*` 里。帧距每旋转档写死为 10,需要另改:
  - `getCurrentFrame`(static,4 处调用)
  - MovieClip 帧数
  - 蒸汽朋克皮肤 `flipper_skin/flipper_steampunk` 的对应帧
- 重打 layer0 公共图集牵连所有战斗(图集预算 4096²、C8004);仍然要改 update/draw 才能切到新帧,收益只是「原生画的红帧」
