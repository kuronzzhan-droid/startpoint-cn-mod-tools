# 官方全屏技能特效清单(水杰拉德特效调研)

2026-10-18 · 只读调研。数据源:`D:/WF/resources/game/wf-decrypted`(官方解密件,含 `_unnamed`)、缺件时读 `D:/WF/out/kulo-patch-toolkit/store131`;客户端源码:`D:/WF/decompile-complete-20261014/scripts`。没有改动任何游戏数据、服务端、编辑器或仓库代码。

## 0 结论先看

- **扫全了**:全部 401 个 `battle/effect/skill_unique/<code_name>/` 特效族(1294 个 `.parts`),加上技能 DSL 引用的通用件、命中件,共 1428 个特效,1423 个能解析。每个都逐帧算了包围盒,966 个做了真实墨迹覆盖率栅格化,再人工看图归类。
- **结果**:{{TIERS}} 个,涉及 126 名角色(全屏/叠色/散布三档)。
- **官方全屏件几乎是同一个套路**:ShowEffect 锚 `subject -1`(场地中心)、坐标系 AB、偏移 0、`scale` 不填(=parts 自带 s=1,parts 坐标直接就是 1080×1920 战场坐标)、寿命 PlayOnlyFirstSequence、层用 SuperForesideOfCharacter(最前)或 ForesideOfCharacter(角色前),背景件用 Backside。画面靠少量小贴图用矩阵铺开:中位 15 张图、每帧约 36 个面片、贴图放大中位 4.5 倍。
- **官方几乎不用颜色手段**:1423 个技能特效里用混合模式(Add/Screen 等)的是 0 个,全是普通 alpha;关键帧 `c` 颜色变换只有 21 个用,多是乘数为 0 的纯色剪影。官方换色靠"另做一套图集"(通用件分 `_red/_blue/_yellow/_green/_white/_black` 六套)。
- **水系辅助首推 5 个**(详见第 6 节,`预览_推荐候选_主选.png`):
  1. `drawing_witch_all`(拉绮夏,水★5 辅助):上下两道水浪卷入,水珠和闪光点缀。原技能就是"引出水流润泽队友+全队增益",最对口。
  2. `vesta_caster_all`(妮丝艾丝,水★5 治疗):双层水波纹带+水滴+星光,42 帧,本件只占 0.028 Mpx 图集,最省。
  3. `luca_playable_ripple`(卢卡,水★5 辅助):一滴水落下,同心涟漪层层铺满全屏。城市雨夜积水的意象最贴,但本件 0.27 Mpx,预算最重。
  4. `navy_officer_wave`(芙拉克西斯,水★5 辅助):屏幕底部潮水涌起并停住,2 张图 0.010 Mpx,适合当底层叠原创件。
  5. `ruin_lady_meteor23_beam`(索媞艾丝,水★5 辅助):水柱从天而降砸出水环。效果最强,但单帧面片峰值 1488,全库最高,有掉帧风险。
- 上面 5 个原色都在水蓝区(色相 180–213°),搬到新 code_name 下基本不用改色。若要和原角色区分(比如偏城市霓虹青或深海蓝),**改图集 PNG 的色相比改 `c` 字段可靠**。原因:`c` 只能对 RGB 统一乘一个数再加色,饱和色贴图会被洗白。

## 1 扫描方法与数量

| 步骤 | 做法 | 数量 |
|---|---|---|
| DSL 全扫 | 遍历 `wf-decrypted/battle/action/**/*.action.dsl.json`,递归找 `["Command",["ShowEffect",…]]`,记录路径、subject、层、寿命、坐标系、偏移、旋转、跟随开关、scale | 6956 份 DSL(技能 1084 + `alk$alk_1/2` 从 store131 补读 2 份;PF 46;其余为敌方);技能 DSL 中 ShowEffect 3702 条(直接路径 3272,按属性解析 430) |
| 特效清单 | `_manifest.csv` 里全部 `skill_unique/*.parts`,并上所有被 ShowEffect 引用的特效(含 `skill_general` 通用件按属性展开、`hit`、PF) | 1428 个;401 个 skill_unique 族全部被技能 DSL 引用;5 个缺件(通用件的 `_colorless` 变体,官方未下发) |
| 结构解析 | 读 `.parts`/`.timeline`/族图集 `.atlas`+`.png`:图层数、轨道、关键帧、矩阵、补间、`c` 字段、混合模式、序列、SE、图集尺寸、本件实际占用 | 1423 个 |
| 尺寸 | 离线复刻 flatomo 求值(嵌套 graphics、补间、帧框左上角锚点),逐帧算包围盒 × DSL 缩放(未填用 parts 的 s) | 1423 个 |
| 覆盖率 | 包围盒达到屏宽 50% 或屏高 40% 的,按 1px=20 战场单位栅格化 alpha(阈值 0.12),量峰值帧在以锚点为中心的 1080×1920 窗内的覆盖率、总面积、墨迹包围盒;另算一份"去掉纯色大底"的值 | 966 个 |
| 分档 | A 全屏:去纯色底后覆盖 ≥55%,或面积 ≥55% 且包围盒 ≥90% 宽、≥60% 高;B 半屏以上:覆盖 ≥30% 或面积 ≥35%;D 全屏叠色:只靠 ≤24px 小图拉成的纯色大底才覆盖 ≥50%;E 全场散布:墨迹包围盒 ≥85% 宽且 ≥60% 高但面积小;C 跨屏长线:单方向 ≥90% 宽或 ≥75% 高 | 见第 4 节 |
| 人工复核 | 每个 A/B/D/E 件渲染 3 帧(起/峰/收)看图,定视觉类型并写外观;E 档里的放射爆发类挪进 C;另补两个标了"全体演出"但覆盖略低的件(`rural_ladyship_flower_shine`、`reporter_ny20_all`) | 229 个人工定类;C 档 120 个按包围盒自动分子类 |

角色信息取 `master/character/character.csv`(第 2 列 code_name、第 4 列稀有度、第 5 列属性、第 28 列定位),中文名取 `character_text.csv`(多行记录已重新拼接),技能说明和图标类型取 `master/skill/action_skill.csv`。

## 2 客户端怎么播放技能特效(行号指 `decompile-complete-20261014/scripts`)

1. **DSL 命令**:`ShowEffect(名字, Effect, subject, LayerZDepth, EffectLifetime, CoordSysSource, x, y, rot, trackPos, trackDir, scale)`,见 `pinball/battle/action/dsl/ActionDslCommand.as:537-539`。Effect 有两种:`SpecifyEffectDirectly(路径)`,或 `ResolveByElement(基础路径, 元素)` 拼成 `<基础>/<名>_blue/<名>_blue`(`§const§/EffectTools.as:12-37`)。
2. **求值**:`pinball/scene/battle/battle/action/ActionEvaluator.as:2617-2648`(case 10)。依次做 `resolveCoordSys`;`param2.lookup(subject)` 取锚点对象;`resolveEffect`(976-988);scale 为 `Some` 就取值,`None` 就不设;最后调 `effectManager.show(...)`。
3. **内置锚点**:`ActionEvaluationResolver.as:152-155` 把 -1、-2、-17、-18 绑到全局环境。-1 = 场地区域正中心(`pinball/battle/action/dsl/SpecialPointZoneBoundsCC.as:18-19`);-2 = 左上角(`SpecialPointZoneBoundsLT.as:18-19`);-17 = 自身;-18 = 球或动作主体。正数是 DSL 里 `CreateReferencePoint`、`Find*Subjects` 绑的参考点或目标。**全屏件 = 锚 -1 + 偏移 (0,0)**,parts 原点就在屏幕中心,parts 里 ±540×±960 就是满屏。
4. **特效对象**:`ActionEffectManager.as:43-46` 新建 `ActionEffect`,构造在 `ActionEffect.as:87-178`:
   - Playhead 读 `.timeline`,timeline 里的 SE 会随帧播放;
   - 寿命分支(137-154):直接帧数 / SLv / PlayOnlyFirstSequence(=首序列长度)/ UntilTargetTerminates / 状态组剩余帧;
   - 同时有 `normal` 和 `angle_45` 序列时进入 8 向或 16 向吸附模式(157-164);
   - 位置 = 目标坐标 + (x,y) 按方向旋转(`stepPos`/`stepDir` 335-345)。方向 `calcDir`(496-517):AB 固定朝上,CD 取目标运动方向,EF 取 EF 方向,GH 指向另一对象;
   - track 开关为 true 时每帧跟随目标(347-357),目标消失就 fade;
   - 到期后如果有 `end` 序列,先播完 end 再删(`fade` 460-488)。
5. **视图层**:`ActionEffectView.as:32-94` 按 LayerZDepth 选层。0 Foreside → ForeLayer,1 Backside → BackLayer,2 SameAsCharacter → ZSortLayer(和角色按 y 排序),3 SuperForeside → FrontLayer(在命中特效层之上),4 NonPixelArt → UnconvertedLayer。己方主动、队友、敌方各有一套。`draw()`(124-143)每帧做 gotoAndStop、设 x/y/rotation;只有 scale 为 `Some` 时才覆盖缩放,否则沿用 parts 的 `s`(`flatomo/animation/Animation.as:38-39,121`,`flatomo/animation/parts/PartsAnimationSource.as:32`)。
6. **像素化(像素感从哪来)**:战场层 `pixelartXYLayer` 每帧被画进"屏幕/6"的 RenderTexture,再用最近邻放大 6 倍(`pinball/scene/battle/view/BattleView.as:4229-4245`、`4705-4716`;`BattleConstants.SCALE_RENDERER = 6`,`pinball/scene/battle/battle/BattleConstants.as:1448`)。BackLayer(`BattleView.as:2668-2676`)、角色 Z 排序层(3099)、ForeLayer/命中层/FrontLayer(3448-3504)都在 `pixelartXYLayer` 里。所以技能特效最后都落在约 180×320 的像素格上:贴图比"屏幕/6"更细没有意义,6 个战场单位才算 1 个像素。NonPixelArt 层(UnconvertedLayer,3600-3616)挂在 `starlingLocalLayer` 上,不经过 RenderTexture,按原生分辨率画,只跟相机平移(4720-4721)。官方技能里只有少数高清件用它,如 `kunoichi_1anv_name_high_definition` 大字、`darkness_high_definition`。另外,parts 贴图除非图项 `s=true`,都强制最近邻采样(`flatomo/animation/parts/PartsAnimation.as:149-157`);全库只有 `darkness_high_definition` 的 3 张图是 `s=true`。
7. **parts 动画本身(flatomo)**:
   - `GraphicsSource.as:160-177`:关键帧 `t` 低 16 位 = 停留帧数(缺省 1),`(t>>16)&3` = 补间类型(1 自定义贝塞尔、2 二次缓动);`m` = 矩阵索引<<12 | 混合<<8 | alpha;`c` 缺省 `0x64000000`(乘数 100%,加色 0)。
   - `PartsAnimationImageProvider.as:258-330`:逐层累乘矩阵、alpha、颜色变换。`c` 的最高字节是 RGB 统一乘数(百分比,277-281 行),低 24 位是 R/G/B 加量,**只能加不能减**。嵌套 graphics 的颜色 = 父乘数×子 + 父加量(328 行把父层的值传给子层)。所以在根层(g[0])关键帧写一个 `c`,就能给整个特效统一染色。颜色变换最后落到 `ColorTransformStyle.as:18-42`。
   - 混合模式枚举在 `flatomo/animation/LayoutTools.as:34-50`:0 继承、1 Add、2 Multiply、3 overlay_like、4 Screen。
   - 图像以帧框左上角为原点(`LayoutTools.apply` 26 行减 pivot,图集图片 pivot 通常为 0)。
8. **预载与图集**:`pinball/asset/logic/AssetPathCollectionBuilder.as:525-532` 从特效路径推出图集 `<目录>/<目录名>.png/.atlas`,不检查 code_name。`pinball/loading/battle/BattleStartProductionViewService.as:150,589`:`battle/effect/` 下的图集打进 layer0 的 4096² 大图集;多人房会把三队所有角色的技能特效图集合并装箱(超了就是 U_1d93f4,见记忆卡 wf-battle-atlas-budget)。

## 3 官方全屏特效的通用做法(A 全屏 + D 叠色共 125 个件、257 次调用的统计)

- **锚点**:subject -1 共 180 次(70%),其余是参考点或目标(0、1、3…)、-18 球、-17 自身。偏移 (0,0) 有 255 次,坐标系 AB 有 240 次。
- **缩放**:217 次不填 scale(用 parts 的 s=1)。只有"像素件"才在 DSL 写 s=3–6。
- **层**:SuperForeside 124、Foreside 119、Backside 14。背景常成对出现:`*_all` 配 `*_all_back`,或 `*_back` 配 `*_character`,如偶像四人组的舞台模板、`summoner_little_all_attack(_back)`。
- **寿命**:PlayOnlyFirstSequence 227 次。109/125 个只有一个 `neutral`(once)序列;少数是 start/loop/end 三段,`end` 会在 fade 时补播。长度中位 90 帧(60fps 下约 1.5 秒),最短 5、最长 277。90/125 个在 timeline 里带 SE。
- **构造**:中位 15 张贴图、25 个 graphics(嵌套层)、100 条轨道;每帧平均面片中位 36.5,最多 1488(`ruin_lady_meteor23_beam`);贴图被矩阵放大中位 4.5 倍;本件实际占图集中位 0.047 Mpx,最大 0.53 Mpx。122/125 个用了补间。
- **颜色**:0 个用混合模式。用 `c` 的全屏件只有 `psychic_nao_3halfanv_crack` 和 `tutorial_alk_blast`(全库共 21 个件:`battle_maid_xm19_area_square` 用 `0xfffc00` 做黄色剪影,`lakeside_guardian_whirlpool` 用 `0x43095254` 把漩涡染成青绿)。
- **官方自己就在跨角色复用**:`wind_oracle/all_wind_oracle`(菲莉亚)和 `aqua/aqua_all`(阿克娅)的 `.parts` 图层、轨道、矩阵逐字段相同,只改了 `.gen` 前缀;3 张 4×40 贴图像素差不超过 6 级;timeline 只差一条 SE(菲莉亚版多了 `sf/se_effect_skill_heal_wind_oracle`)。`golden_dragon_jr_shine` 是同款光幕的改版。偶像组的 `heavenly_four/template_action_skill_all(_back)` 直接以 template 命名,四人共用一套舞台结构。也就是说,"拷整族到新目录、改前缀、换 SE"本来就是官方做法。
- **一个技能通常叠多件**:角色身上的起手件(-18/-17)+ 全屏件(-1)+ 命中件(参考点),靠 DSL 的 `Wait` 事件错开。例:`drawing_witch$drawing_witch_2` 先在自身放 `drawing_witch_main`(直接寿命 65 帧),等 43 帧再放 `drawing_witch_all`;`vesta_caster_2` 先放 `vesta_caster_player`(-18),等 77 帧再放 `vesta_caster_all`。

## 4 全屏特效清单(按视觉类型)

说明:
- "档"见第 1 节。"帧·缩放·锚·层"里的缩放是 DSL 实际用到的值(未填 = parts 的 s),锚指 subject(参考点 n = DSL 局部绑定)。
- "构造":层 = graphics 数,轨 = 轨道数,图 = 贴图张数(括号里是最大一张的帧框),面片 = 平均每帧绘制数,c×n = 带非默认 `c` 的关键帧数。
- "图集":族共用图集尺寸(括号里是本件实际用到的图块面积)。
- 全部 349 个件都没有混合模式,下表不再单列。
- 【水】= 水属性角色,【辅助】= 定位 Supporter,【治疗】= Healer。同一表内按档(全屏→叠色→散布→半屏)、水属性优先排序。

{{BODY}}

## 5 水属性 / 辅助角色子集(A/D/E/B 档)

总览图:`预览_水属性与辅助角色.png`(蓝框 = 水属性)。

### 5.1 水属性角色({{NWATER}} 个)

{{WATER}}

### 5.2 辅助(Supporter)角色({{NSUPP}} 个)

{{SUPP}}

## 6 推荐候选(水系辅助技能)

预览:`预览_推荐候选_主选.png`(①–⑤,每行 7 帧均匀取样)、`预览_推荐候选_备选.png`(A–E)。下面的图集占用都指"只拷本件用到的图块重新装箱"后的面积;layer0 总预算 4096² ≈ 16.8 Mpx。

| # | 特效 | 来源角色·原技能 | 外观 | 关键数据 | 改色难度 | 搬家难度 | 建议用法 |
|---|---|---|---|---|---|---|---|
| ① | `skill_unique/drawing_witch/drawing_witch_all` | 拉绮夏 水★5 辅助;"瞳之印记":引出水流润泽队友,全队攻击提升+火抗提升 | 上下两道水浪从屏幕边缘卷入,水珠漂浮,星形闪光 | 109 帧·s1·锚 -1;22 层/98 轨/8 图(最大 341×183)/每帧约 46 面片;本件 0.126 Mpx(族图集 1343×122 和起手件共用);SE `light/se_light_shine`;色相 213° | 低:本来就是蓝。想要城市霓虹青,改图集色相即可;灰白水浪带也可以用根层 `c` 微调 | 低:拷图块 + 改 `.gen` 前缀;timeline 原样拷 | 主全屏件。照官方节奏:自身起手件 → Wait ~40 帧 → 全屏件 |
| ② | `skill_unique/vesta_caster/vesta_caster_all` | 妮丝艾丝 水★5 治疗;"心角之标·荣命":治疗+水属性攻击提升 | 上下两层水波纹带,水滴下坠,星光闪烁 | 42 帧(短促)·s1·锚 -1;17 层/39 轨/7 图(最大 139×39)/约 40 面片;本件 0.028 Mpx;SE `water/se_ice_blade_spin`;色相 183° | 最低 | 最低 | 治疗或增益生效瞬间的"潮汐闪光",可和①前后衔接 |
| ③ | `skill_unique/luca_playable/luca_playable_ripple` | 卢卡 水★5 辅助;"生长渴望":全体水伤+水属性攻击提升 | 一滴水落下,同心涟漪层层扩散铺满全屏后淡出 | 150 帧·s1·锚 -1;14 层/31 轨/9 图(环形大图 314×314)/约 8 面片(极省绘制);**本件 0.272 Mpx,预算最重**;SE `water/se_waterdrop`;色相 179° | 低 | 中:环贴图大,建议缩到 1/2 再用矩阵放大 2 倍(反正最后按 1/6 像素化,损失很小) | 城市雨夜积水的主意象;适合作为"开场",或配合"全场"增益 |
| ④ | `skill_unique/navy_officer/navy_officer_wave` | 芙拉克西斯 水★5 辅助(原为舰炮技能的底部浪) | 潮水从屏幕底边涌起并停住 | 115 帧·s1·锚 -1;9 层/25 轨/2 图(125×63)/约 28 面片;本件 0.010 Mpx;SE `water/se_water_large_explosion`;色相 197° | 最低 | 最低 | 做底层(Foreside/Backside),上面叠原创件(城市剪影、霓虹倒影),或和①、③同时播 |
| ⑤ | `skill_unique/ruin_lady_meteor23/ruin_lady_meteor23_beam` | 索媞艾丝 水★5 辅助;"曙光之辉":炮火暴雨全体水伤+水属性攻击提升 | 一根根水柱从天而降砸地,溅起水花和扩散水环 | 75 帧·s1·锚 -1;29 层/118 轨/13 图(82×82)/**平均 521、峰值 1488 面片**(全屏件里最高);本件 0.020 Mpx;SE 有 `water/se_water_giant_tidal_wave` 和 5 个 `sf/se_admin_cannon_bit_shot_once` 炮击声 | 低 | 中:要删减水柱数量降峰值(低端机和三人房有掉帧风险,见记忆卡 wf-maou-fx-lag);炮击 SE 要换 | "水柱赐福"大招版;原意偏攻击,用作辅助时建议只留 1/3 水柱 |

备选与可拆件:

- **A `holy_mother_all`**(玛姆娜莉亚 水★5 治疗):青色斜向光雨持续落下,两侧有雾带。122 帧,只有 2 张图(最大 500×200),本件 0.104 Mpx。最像"城市雨夜",适合做背景层,和①叠用。
- **B `student_president_all`**(露西娅妲 水★4 辅助):水流漩涡环绕扩散,之后水珠漂落。78 帧,0.115 Mpx。官方锚在 -17 自身(随角色走),适合"以自己为中心的增益光环"。
- **C `summoner_little_smr23_all`**(珂艾特 火★5 治疗,但素材是蓝色浪花和斜雨):浪从顶部拍下,中间一个黑洞,然后下斜雨。44 帧,0.098 Mpx。把黑洞那几条轨道隐藏(alpha 0)就是"浪潮拍下"。
- **D `aqua_all`**(阿克娅 水★5 治疗):3 张 4×40 的细线拼出整屏垂落光幕,本件只占 756 px 图集;菲莉亚的 `all_wind_oracle` 就是它的官方拷贝版。原色黄绿(73°)、偏白,是最适合用根层 `c` 染成水蓝的官方件。适合"天降治愈光幕"。
- **E 半屏级水辅助点缀**:`sleep_puppy_vt23_all`(泡泡/爱心沿四周漂,0.016 Mpx)、`nurse_pirate_smr22_all`(镜头光斑+大气泡,0.025 Mpx)、`sing_android_2halfanv_all`(舞台+水蓝丝带,0.095 Mpx,但 47 张图结构复杂)。
- **城市感原创件参考**(只借做法,不建议直接搬):`cyber_battergirl_all`(满屏 CRT 扫描线+弹窗)、`psychic_seiji_all`(故障方块)、`psychic_tomboygirl_hw22_wire`(霓虹线框)。它们都是"少量小图+矩阵铺满屏"的做法,自制霓虹路灯、雨幕、橱窗反光时可以照抄结构。

参考组合(一个技能,预算约 0.16 Mpx,≈ layer0 的 1%):起手件(角色身上 -18,原创或从 `drawing_witch_main` 改)→ Wait 约 40 帧 → ① 全屏水浪(官方挂"角色前"层)+ ④ 底部潮水(角色前或角色后)→ 增益生效时 ② 潮汐闪光。

## 7 复用到新 code_name 的步骤与坑

1. **目录**:放在 `battle/effect/skill_unique/<新code_name>/` 或它的子目录。图集必须叫 `<目录>/<目录名>.png/.atlas`(客户端按 `AssetPathCollectionBuilder.as:525-532` 推导)。跨 code_name 直接引用官方路径也能加载(记忆卡 wf-effect-family-under-codename,2026-09-10 更正),但想改色就必须拷一份。
2. **帧名两段式**:`<目录>/.gen/<parts基名>/<帧>`,parts 基名必须等于 `.parts` 文件名。搬家时把 `.atlas` 的 `n` 和 `.parts` 的 `i[].p` 前缀统一替换;三段式会让特效静默不显示(记忆卡 wf-flatomo-animation-format)。
3. **timeline 原样拷**:里面的 SE 路径也算预载引用,路径必须真实存在,否则进战斗报"数据不足"。
4. **只拷用到的图块重新装箱**:例如 `drawing_witch.png` 是全族共用的 1343×122,`_all` 只用 0.126 Mpx。多人房会把 3 队、最多 18 个不同角色的特效图集合并装进一张 4096²,自制角色要尽量瘦(记忆卡 wf-battle-atlas-budget)。
5. **DSL 照抄官方形状**:`["ShowEffect", 名, ["SpecifyEffectDirectly", 路径], -1, ["SuperForesideOfCharacter"], ["PlayOnlyFirstSequence"], ["AB"], 0, 0, 0, true, true, ["None"]]`。scale 不填就沿用 parts 的 s=1。起手件挂 -18 或 -17。改朝向用第 10 个参数 rot(弧度),不要动矩阵。
6. **改色两条路**:
   - (a) 改图集 PNG(色相或色带映射,alpha 和坐标不动)。推荐这条,可以任意配色。先例工具:`D:/WF/wt26_art_staging/16_新角色_杰拉尔水_九尾雷/03_杰拉尔水_技能特效/tools/recolor.py`(2026-09-06 给 unicorn_lancer 族做的"搬家+水色带映射",含往返校验)。
   - (b) 在 parts 根层(g[0])每个关键帧加 `c = (乘数%<<24)|(R<<16)|(G<<8)|B`。只能统一乘 RGB 再加色,适合白、灰、近白件(如 `aqua_all` 细线、光幕);饱和色件会发灰发白。乘数写 0 就变成纯色剪影。写完要用 `wf_dsl.encode_amf3` 做往返校验。
7. **验收**:纯染色可以信预览;加层、改关键帧这类结构改动,预览器不可信,必须真机金丝雀(记忆卡 wf-pf-fever-fx-craft)。如果走离线整包,改了技能特效集合要同步 `wf_offline_content.py` 的 `WORKSPACE_PROGRAM_EFFECTS`(记忆卡 wf-fx-production-pipeline)。
8. **自制件的坑**(基诺维、杰拉德踩过):矩阵要写居中平移 `x=-(W/2)·a`;关键帧必须带 `t`;`g[0].t` 要等于首序列 `end`;小帧硬放大会糊,官方放大中位 1×(全部件)、全屏件中位 4.5×。

## 8 局限与没能渲染的

- 预览是离线复刻渲染(`tools/fxlib.py`,按 GraphicsSource / PartsAnimationImageProvider 的逻辑累乘矩阵、alpha、`c`、补间),**没有模拟 1/6 RenderTexture 的像素化和 Starling 的实际采样**,颜色是叠在深色底上的近似。官方技能特效没有用混合模式,也没有 movie 段(kind 1),所以这两项不影响结果。
- 锚在角色、参考点、球上的件,预览一律把原点放在屏幕中心;随球移动(trackPos)的轨迹、一个技能里多件特效靠 Wait 错开的合成都没模拟,每件单独渲染。
- 5 个通用件 `_colorless` 变体(`miasma`、`generic_fire`、`heavy_charge`、`strengthen`、`circle`)没有数据,官方没下发;可玩角色的属性也不会是 6。
- `alk$alk_1/2` 两份 DSL 不在 wf-decrypted,是从 store131 读的(store131 是改过的 live 库);`alk$alk_3` 哪里都没有。特效文件 1333 个来自 wf-decrypted 具名件、88 个来自 `_unnamed`、2 个来自 store。
- 171 个 skill_unique 件没有被 ShowEffect 直接引用(命中特效、协力球就位特效,由攻击或召唤命令引用),只做了尺寸分析,没追引用链;其中只有 `gold_ship_multiball_ready_*` 进了半屏档。
- 敌方/boss 技能特效(`battle/effect/enemy_*`)和 PF 特效不在本次范围,已剔除 4 个 PF 大件。
- 墨迹阈值 0.12、栅格 20 单位/像素。极淡的半透明大图(如 `psychic_yamikawa_popup_ef`)覆盖率可能偏高。视觉类型是人工看图判断的,C 档 120 个只按包围盒自动分了子类。
- 少数助战、教程条目(`tutorial_alk`、`ability_skill_fire_dragon_zenith`、`devil_leader_assist_maou_multiball`、`resistance_princess_assist`)在角色表里没有行,中文名、属性显示为空或 None。

## 9 文件

- `全屏特效清单.md`:本文。
- 分类预览(每格 3 帧:起/峰/收,蓝框 = 水属性,宽度都 ≤1730px):`预览_全屏闪光压暗.png`、`预览_放射光爆.png`、`预览_从天而降.png`、`预览_波浪涟漪漩涡.png`、`预览_场地覆盖边框.png`、`预览_巨物召唤.png`、`预览_舞台烟花.png`、`预览_散布粒子.png`、`预览_巨型斩击.png`、`预览_贯穿光柱长线_1.png`(A/B 档)、`_2.png`、`_3.png`(C 档,每格 2 帧)。
- `预览_水属性与辅助角色.png`、`预览_推荐候选_主选.png`、`预览_推荐候选_备选.png`。
- `tools/`:调研脚本(只读),可以重跑或拿来预览改色效果。顺序:`scan_dsl.py` → `analyze.py` → `ink.py` → `tiers2.py`、`extra.py`、`hue.py` → `assemble.py` → `sheets.py`、`gen_md.py`。`fxlib.py` 是 parts 渲染器,`wfio.py` 负责读件(先 wf-decrypted,再 `_unnamed`,最后 store)。`rows.json` 是全部 349 条的机读数据。
