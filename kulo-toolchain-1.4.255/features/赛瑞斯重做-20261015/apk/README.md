# v32h-pflv4-feveritems：修 v32g 一进游戏就崩 8013 的问题

**v32g 作废**：真机一进游戏、在任何战斗之前就崩 `ClientError 8013 UniqueConditionTable 的主表尚未加载`，调用栈是 TerrainHandler/readHandler。
- v32g 的未签名包已改名为 `*.apk.bak-crash-C8013`。
- 目录里的 `*-v32g-*.signed.apk` 不是本脚本生成的，同样带着这个崩溃，不要装。

**原因**：`LeadingLogicAssetCacheLoadingManager` 把 master 表和 terrain 放进同一个 MultiTask 并行读（`LeadingLogicAssetCacheLoadingManager.as:62-85`）。进游戏时的全局预载中，如果 terrain 先读完，unique_condition 主表还没加载。B4 在这时调用 `getMasterTable`，没加载就抛 8013（`LogicAssetContainer.as:448-457`）。

## 改动
1. **撤掉 B4**：TerrainHandler/readHandler 与基线逐字节相同（sha 72347789…1ef7）。
   - 不需要 B4 的依据：B3 的调用链是 `resolveDirectInstantItem(...).resolvePathCollection(builder)` → `DirectInstantItemSource.resolvePathCollection` → `ExecutableInstantItemSource.resolvePathCollection`，这一步会同时 `addAnimationLayout(animation_path)` 和 `addActionDsl(program_path:元素)`，也就是道具的动画和 DSL 都进了战斗资源清单（`AssetPathCollectionBuilder.addActionDslDetail` → action 集）。
   - 官方「敌人/可破坏物掉落道具」只靠这一条路预载：`ZoneSource.resolvePathCollection` → `InstantItemOdds.resolvePathCollection` → 同一个 `ExecutableInstantItemSource.resolvePathCollection`，没有任何 TerrainHandler 侧的预载，掉落道具照样能用。
2. **所有读主表的注入代码改用不抛异常的 API**：`ILogicAssetContainer.getMasterTableMaybe`（接口 `ILogicAssetContainer.as:33`，实现 `LogicAssetContainer.as:473-484`，未加载时返回 null；池里现成的 multiname，取自 `TrimmedImageRepository/<ctor>`）。
   - unique_condition 表或 direct_instant_item 表任一为 null，候选表就当作空：B1 只停用箭头、不出道具；B3 不预载。都不会抛异常。
3. **执行时机复核**：
   - B1 和 B2 只在 Fever 开始和结束时执行，属于战斗期。B2 不读任何表。
   - B3 只在 `BattleQuestBaseImpl.resolvePathCollection`（case 13-16）里执行，调用方是 `BattleAssetPathCollectionBuilder.leadingLogicLoadedHandler`（`:89-92`），也就是战斗或技能预览的资源收集阶段，晚于进游戏。
   - 补丁会调用原版的 `resolveDirectInstantItem`，它内部仍用原版的 `getMasterTable` 读 DirectInstantItem、ExecutableInstantItem、Level、AtkCurve 这几张表。这和官方 case 9 在同一阶段的读法相同，B3 也已先确认 direct_instant_item 表已加载。
4. **新增静态检查**：
   - 三个补丁体里调用会抛异常的 `getMasterTable` 的次数，补丁前后都是 0；
   - 被补的方法只限这 3 个战斗期或战斗收集期的方法；
   - TerrainHandler 体未变。
   - 离线用例新增「主表未加载」：B1 与 B3 都不抛异常；B3 与原版相同；B1 不出道具。

## 哈希
| 项 | sha256 |
|---|---|
| B1 activate after（v32h） | 564c53a71437a31fc9a5d5494e993fad94895482d5090f5421943d66763b1450 |
| B2 deactivate after（与 v32g 相同） | be565848a5c9bccb1030b57a98799a4fde637418f8601d76009fc45aa3422e9b |
| B3 resolvePathCollectionForDashPanel after（v32h） | 164473bf19953ddd7de88ab02c0814f6b22a2c8b813259d907408225065a79fc |
| 测试服 SWF / `out/世界弹射测试服-v32h-pflv4-feveritems.apk` | 3514be1b9938360fdbfcf6163f277c866eebbc45fd45669a8fb867c364222dc9 / 47d7270f9bb3f18a9f7c8cf571514476650f991049313f21618b500d667f0f37 |
| 本地 wf SWF / `local/wf-local-pflv4h.apk` | ecf85536dd8fc87b6cfc1f627b77ef141ac50d8451db3196081b7d6b562050ef / a826f546b68510b5a28f55e27c461a7a8be0d0e7b60f3203fdcfb5a1e40997f1 |

- 两个包都从 v32f 构建，只替换 SWF，其余 4174 个成员不变，已做 zipalign -p 4，未签名。
- 验证两条线各 29 项全过，报告是 `out/verify-report-v32h.json` 和 `local/verify-report-local-v32h.json`。
- 主 ABC 只有 3 个体变了，常量池零追加。
- v32g 的 SWF 不能作为重放输入：它的 B1 体 sha 既不是原体也不是 v32h 的补丁体，会被拒，必须从 v32f 构建。
- 脚本快照在 `snapshots/v32h/`。

真机检查清单、数据约定、ITEM_LV 的理由都与下面的 v32g 节相同，只是不再有 B4。补充一项：**进游戏、进主页、进任意关卡都不能出现 8013**。

# v32g-pflv4-feveritems：Fever 箭头 → 随机道具（通用词条）

v32f（P1-P3）之上加 4 个单方法补丁 B1-B4，主 ABC 常量池零追加。任何角色只要队长技给自己挂上标记状态，就能用，补丁里没有写死角色。
脚本：`feveritems_patches.py`（补丁本体，顶部是常量）、`feveritems_apply.py`（重放）、`build_feveritems_apk.py`（打包，`--local` 打本地线）、`verify_feveritems.py`（验证）、`feveritems_datacheck.py`（数据自检）。快照在 `snapshots/v32g/`。产物都**未签名**，没有装到任何设备。

## 数据侧要准备的东西（unique_condition 1299901 的含义）
- **标记**：本 Battle 的**队长**身上，有 uid 在 **1299901–1299909** 之间的 unique condition，且层数 > 0（官方 `getConditionAccumulationCount(Unique(uid))` 计数）。
  - 一共 9 个槽位，每个槽位对应一套候选表。几个槽位同时成立时，取 uid 最小的。赛瑞斯用 1299901。
  - 挂法：队长技首行 trigger 0 Initial + content 461 ConditionUnique，上限写 2（不要写 (None) 或 1，见 wf-unique-cap-none-trap）。
  - 建议 duration 99999999、cancelable false、remove_on_coffin false（队长倒下也保留标记）。
- **候选表 = 该行的 string_id**，格式：`fever:items:<键1>|<键2>|...[:标签]`
  - 键 = `master/battle/yakumono/direct_instant_item` 的行键，写**基键**，不带 `_fever`。客户端会自己拼上 `"_" + "fever"` 再交给原版 `resolveDirectInstantItem`。
  - 分隔符用 `|`，不用逗号，避免 CSV 转义。
  - 可选的第 4 段标签只是为了让 string_id 唯一（两个槽位用同一套表时要加），客户端忽略。
  - 赛瑞斯这行：`fever:items:hp_recovery_small|skill_charge_middle|accumulation_attack_power_up_25_500|condition_piercing:seris`
    - 回血：hp_recovery_small，官方 FEVER 地形用了 18 次
    - 技能充能：skill_charge_middle，21 次
    - 攻击 UP：accumulation_attack_power_up_25_500，237 次，最常见
    - 贯通：condition_piercing，22 次
    - 4 个键都是官方 `DIRECT_INSTANT_ITEM#*_FEVER` 已经在用的，资源和 DSL 都已验证过。`feveritems_datacheck.py` 对 live（WF_TIP=206）检查结果为 OK。
  - 为什么不用 `wfx:` 前缀：WFX 注册表规定 `wfx` 家族的 string_id 必须是 `wfx:<数字code>:<arg>:<value>:<flags>:<label>`，label 只允许 `[A-Za-z0-9_]`，装不下一串道具键；不合规会被 wfx_gate 当作写错拒绝。而且这条 APK 线里没有 wfx-core，池里也没有 "wfx" 字符串。所以用独立前缀 `fever:items:`，两段都是池里现成的字符串。以后要并进 WFX，在注册表登记这个前缀即可，不冲突。
  - 运行时处理：键不在 direct_instant_item 里会被**静默丢弃**；行不存在、前缀不对、表为空时，**有标记 = 箭头停用但不出道具**。
  - 必须先跑数据自检：`WF_TIP=206 python feveritems_datacheck.py "<string_id>"`。executable 表或 level 表缺行时，预载会崩。
- **ITEM_LV = 100**：
  - 官方 FEVER 道具的等级取 zone.enemyLevel，补丁运行时拿不到这个值。
  - 4 个候选的道具 DSL 全是常数（min=max：回血 10%、充能 0.5、攻击 +25% 上限 20 层、贯通 900 帧），等级对强度**没有影响**。
  - 等级只需要落在 atk 曲线 `atk_basic_normal` 的定义域 1..100 内，否则 C14520。100 正好是曲线端点，也对应高难本的满级；以后要是放进按 SLv 缩放的道具，也是满级强度。

## 行为
- **B1 `YakumonoManagerImpl/activate`（Fever 开始）**：播完原有的 shine SE 后，找第一块 FEVER 箭头，取它的 squadManager 读队长标记。
  - 无标记：只多几次无副作用的计数查询，副作用逐条与原版相同。
  - 有标记：
    - 所有 FEVER 箭头**不 activate**，保持关闭，也不播 open/RotationPanelOpen。
    - 每块箭头的坐标上，如果还没有 DirectInstantItemImpl，就建一个 FEVER 道具。
    - 构造参数与官方地形里的 FEVER 道具完全相同：`resolveDirectInstantItem(key_fever, 100)`、箭头自己的 rotationPanelAnimation。
    - 建好后 `yakumonoes.add` + `gear.addChild`，同一个循环里由原版代码 activate → popItem。
  - 抽签：`createSeparativeRandomNumberGenerator(uid + ((int(x)<<14) ^ int(y)))` 后取一次 randomFloat。种子是本 Battle 的 separative 种子（=本 Battle id），不碰掉落和 DSL 的随机流，没有 Math.random。所以种类由「本 Battle id + 标记 uid + 箭头坐标」决定，联机各端的副本一致。
  - **每区第一次 Fever 抽一次，之后这一区内箭头一直被替换，不重抽**：同坐标已有道具就跳过。以后的 Fever 中道具按官方 FEVER 道具规则重新出现，吃掉后按 frames_to_repop 重刷。
  - 新区重新抽。同一 Battle 里，同一坐标、同一标记会抽到同一种。
- **B2 `YakumonoManagerImpl/deactivate`（Fever 结束）**：同样的标记判定。有标记时，只跳过「FEVER 箭头且 state=Deactivated（从没开过）」的 deactivate，不多播 close/RotationPanelClose。道具和其他物件照原版收起。无标记时与原版相同。
- **B3 `BattleQuestBaseImpl/resolvePathCollectionForDashPanel`** 和 **B4 `TerrainHandler/readHandler`（loadedHandler 之前）**：不门控。对 9 个槽位里所有有效的候选键做预载：B3 预载道具动画和 DSL 的路径，B4 预载逻辑层的道具 DSL `program_path:元素`。
  - 只有真的存在 `fever:items:` 行时才会多出预载项。没有行时与原版相同。
  - 不按队长门控，因为预载早于读到队伍。代价是：只要库里有任意一行，所有带加速板的关卡都会多载这几个小道具件。

## 哈希
| 项 | sha256 |
|---|---|
| B1 activate before → after | 28ed4051…0ab5 → 5c94bf3e26372654b8a8506a1ce6aebe99536a534840582d34fa9b393a43d3b0 |
| B2 deactivate before → after | 997dbf34…5309 → be565848a5c9bccb1030b57a98799a4fde637418f8601d76009fc45aa3422e9b |
| B3 resolvePathCollectionForDashPanel before → after | e3ccc6d9…47e6 → 56f931cd60f3c7808476c6a060b2d2b9fc0889fc9c38507737a06efb4aef4e4e |
| B4 readHandler before → after | 72347789…1ef7 → 95bc35829e18396b2bbad0112f1a4738a88bbea25d3674f3bc1af28727f6bd7e |
| 测试服 SWF / `out/世界弹射测试服-v32g-pflv4-feveritems.apk` | 12ba08065e4e4a68fa8ecf893a57b1d65049f8432554fefd93c78818a7f6c2bb / da9241aed543e2b20be31d96d9a7fa94dfd569561f3d75dbae66b8fa15e891fd |
| 本地 wf SWF / `local/wf-local-pflv4g.apk` | 28183630e0cd23b7f47196e438d75ea5af54042fb5aaf8f8ce2359c186a7e061 / 8c25171fd14b8abc86c49c910f7fadc16d222667b4c6118bdf620d050a53f43e |
| 基线（v32f）测试服 / 本地 APK | 51dd8cd3…33c4 / 6afb1352…7d22 |

四个原体在两条线和 vanilla 上都相同，所以 B1-B4 也能单独打到别的 APK 上（按体 sha 锁定，对不上就拒绝）。两个 APK 都只替换了 SWF 一个成员，其余 4174 个成员逐字节不变，并做了 zipalign -p 4。

## 静态 + 离线验证（`verify_feveritems.py`，两条线各 28 项全过；报告 `out/verify-report-v32g.json`、`local/verify-report-local-v32g.json`）
- 重放逐字节一致；幂等（再打一次 = already_present）。四个目标体各改 1 字节的副本都被拒。
- 只有 boot_ffc6 变了。92601 个方法体里 92597 个逐字节相同。常量池和各表零追加。
- 栈和作用域模拟都在 header 内：B1 [5,14,1,2]，B2 [3,8,1,2]，B3 [3,8,1,1]，B4 [3,18,1,2]。所有回跳都落在 avm_label 上。
- 补丁体里没有 Math.random 和 fromCharCode。新增的字符串只有池里现成的 `: | fever items _ x y`。
- 离线执行（avm_fi 跑真实字节码）：
  - B1 无标记：6 种情形 × 2 次 Fever，日志都与原版相同，不读表，不抽签。
  - B1 有标记：
    - 箭头停用；每块 FEVER 箭头的坐标上出一个道具，种类与独立重算的 Xorshift 结果一致。
    - 第二次 Fever 不重抽。
    - 1140 个坐标上的抽签分布为 4 种各约 25%。
    - 选槽位、过滤键、坏表、同坐标已有道具这几种情形都有单独用例。
  - B2：只跳过从没开过的 FEVER 箭头。
  - B3/B4：没有行时与原版相同；有行时按槽位和键的顺序预载。

## 真机要看什么
1. **装包**：联机时房间里所有人必须装**同一个 v32g APK**。没装的客户端会把有标记玩家的副本模拟成箭头推球，球路会分叉。装完清 cache/app。
2. **赛瑞斯当队长**（数据侧已经发了 1299901 这一行，并在队长技 Initial+461 挂上标记），进一张有 Fever 箭头的图，比如 `haniwa_carnival_dark_direct` 一类，全库有 677 张。
   - 第一次 Fever：所有箭头不打开；原箭头位置上出现旋转台道具，有 InstantItemAppeared 和 RotationPanelOpen 演出；种类是回血/充能/攻击UP/贯通之一。
   - 吃到道具：效果与官方同名 FEVER 道具相同，例如攻击 UP 叠层，贯通约 15 秒。
   - Fever 结束：道具收起，有 close 和 RotationPanelClose；箭头不播 close。
   - 再次 Fever：同位置、同种类的道具重新出现；不推球，箭头也不打开。
   - 进下一区：重新抽。
   - 观感：关闭的箭头底座上叠着道具和旋转台，需要确认能接受（research §5-2）。
   - 不出现 C8016 / C14502 / C14520 / 8013 / 取时间轴报错。
3. **标记缺失 = 不变**：
   - 其他角色当队长，或赛瑞斯不当队长：箭头与 v32f 完全一致，Fever 开启推球。
   - 赛瑞斯在副位：标记只看队长，所以不触发。
4. **联机**：双人同装 v32g，有标记的一方在两台设备上看到的道具种类和位置应当一致。另一方是普通队长时，他的副本照常显示箭头。
5. **没有 Fever 箭头的图、只有官方 FEVER 道具的图**：行为与 v32f 一致。官方道具与箭头同坐标时不会重复建。
6. **P1-P3（PF Lv4）**：与 v32f 相同，这 3 个体逐字节没变。

## 已知限制
- 队长倒下时，如果他的状态槽被隐藏（官方 `get_isInvisibleSlot`），计数会是 0，这时进 Fever 箭头照常打开。Fever 结束时 B2 也按无标记处理，前后一致。
- 标记在一次 Fever 中途被移除时，B2 会照原版对未打开的箭头播一次 close，只影响观感。
- 每一区的第一次 Fever 都会多一次 B1 扫描，复杂度 O(箭头数×物件数)，物件只有几十个。

# 赛瑞斯 PF Lv4 客户端补丁（v32f-pflv4）

> **v32f** 在 v32e 基础上，按作者喜好恢复 v32d 的红色闪圈：进入就绪时、以及就绪期间每 60 帧，重放官方 twinkle "three"，并加 red(true)（`TWINKLE_RED=True`、`TWINKLE_EVERY=60`）。
> v32e 的修复都保留：charge 不强制显示、spark 变红、只有一声 skill_ready、没有 HitEffect、8 档渐变。P2 的字节与 v32d 完全相同。

| v32f 项 | sha256 |
|---|---|
| P2 / P3 after | 850b7356ba86f981b98d73d4d3619484acf2e7b2b0ff9f4ee8814113b7e9b8f0 / 379ac4029668dbf388a33ee321940f77837f1911d14c3f06f19f66c553377375 |
| 测试服 SWF / `out/世界弹射测试服-v32f-pflv4.apk` | 10cf1685e5e13a1469e13b8eec0ec42b78715dcdc52639eabe7f6582013f4544 / 51dd8cd35f22cf7143967623dce6aace628539f050a197181004b62e8b5433c4 |
| 本地 wf SWF / `local/wf-local-pflv4f.apk` | 0562c73d47cd97f6705c785c61bf30b1a073c94fa3581657d2095a651b0beced / 6afb1352a8122c8fe20420fec1837be76aac25e67915f2e235588740b89f7d22 |

## 以下为 v32e 记录

> **v32e 修订**（v32d 产物没动，脚本快照在 `snapshots/v32d/`）：
> - 就绪时不再强制显示 charge（涨条件），交回官方逻辑，满了就隐藏。
> - twinkle（整根弹板大小的 Lv3 辉光）只在进入就绪时重放一次，不再每 60 帧重放，也不再加 red()。原因：red() 纯红偏移会把这块白/青辉光整块填成实心红，就是真机上那两大团糊红。缩放一直是官方原值，补丁没改过。想要红色闪光，把 `TWINKLE_RED` 改成 True 后重算 sha。
> - 就绪 = bg/fg 满红（0xFF4040）+ 官方 Lv3 spark 强制显示并 red() + 进入时一次官方 Lv3 闪光（原色）+ 一声 skill_ready。渐变 8 档不变。

| v32e 项 | sha256 |
|---|---|
| P2 / P3 after | e5e9189070daef3c66d91e55a6e86b044095cb4c9113ae92ef8509d31d4246fb / 0c8a88ca7016a9325dd99ee1ec8c4ca5405f0032b16bd2e80cd1f438c0713994 |
| 测试服 SWF / `out/世界弹射测试服-v32e-pflv4.apk` | 6770cb3bc509d883caf2e115dbb621ed1c7efaf295b165a9e29493cfffc4523a / e1eb9c5ec1fee9251ea9bd94fc8da1d8d86bde4f4b10ae5219476bb26a205f75 |
| 本地 wf SWF / `local/wf-local-pflv4e.apk` | f41dc31c8e32e3a07fa5b898e9cdda1d6d59b2ae3f5936a2f9e7cc49dfbad440 / 2d3665b8becac24ebb0d8aefb14cf3a409ccb7446126557e3be26357ceb08e3e |

## 装备机兵武器后弹板仍是默认皮肤：排查结论
- **皮肤功能是官方原版代码，不是 APK 补丁**：`BattleFlipperImpl/run`（sha 8ddcceda…）和 `BattleEquipmentLogic/isFlipperSkinUnlocked`（sha 529d8c00…）在这三份 SWF 里逐字节相同：本地 wf 基线 97864b79…、测试服 v31、vanilla 原版。我们的 P1–P3 也不碰这两个方法，也不碰皮肤字段。所以两条 APK 线没有区别，补丁也不干扰皮肤。
- **生效需要同时满足 4 个条件**（全部来自原版代码）：
  1. 本地选项 `applicationOption.flipperSkin.enable`（设置里的「弹板皮肤」开关），没有存过时默认开启；
  2. master 表 `master/equipment_enhancement/equipment_flipper_skin/flipper_skin.orderedmap` 有这件装备的行；
  3. 这件装备的特殊强化等级 ≥ 该行的 enhancement_level。机兵 6 件要求 120，100012 延续的黄金要求 0；
  4. 战斗开始时按队伍成员顺序扫主武器，第一个满足条件的生效。只看武器槽，不看魂。
- **本地服数据核对**（localsrv 的 1.4.212 CDN 和 `.database/wdfp_data.db`，只读，包含 WAL）：
  - 皮肤表 7 行都在；
  - 6 件机兵武器在 players_equipment 里都是 enhancement_level=120；
  - Party G（slot 7）= 赛瑞斯 129999 / 121183 / 121171，其中 121183 装着 5010073 朱安里克。
  - 服务端下发 `user_equipment_list.enhancement_level`（client-player-snapshot.ts:116），客户端由 PlayerLogic:3072 读入 enhancementLevel。
  - 数据层面没有问题。
- **最可能的原因（按可能性排序）**：
  1. 强化等级是直接改库改到 120 的，但客户端还在用登录时缓存的旧存档（强化 0）。需要完全重登或重启游戏，让客户端重新拉取 user_equipment_list。
  2. 设置里「弹板皮肤」被关掉了。
  3. 进的不是 Party G，或者用了固定编队模式。FixedPartyLogic:655 会把 enhancementLevel 写成 0，皮肤必然不生效。
- **真机自检**：
  1. 打开朱安里克的装备详情：特殊强化应显示 Lv120，并且出现「弹板皮肤」按钮（OwnedEquipmentDetailWithProtectionDialog 只在已解锁时允许点）；
  2. 设置里确认「弹板皮肤」开着；
  3. 用 Party G 进普通关卡。
  - 想排除强化等级的影响，可以装备 100012「延续的黄金」：它要求 0 级，只要拥有就生效。
  - 还看不到的话，抓一段客户端日志，或者把设备的 applicationOption 本地存档发过来。我这边 adb 没有连上任何设备，没查设备状态。

## 以下为 v32d 记录

> **v32d 修订**（v32c 的产物没动，脚本快照在 `snapshots/v32c/`）：
> - 周期电弧整段删除。v32c 的 paralysis_ball 看起来像 boss 被麻痹。现在 P2 不再放任何 HitEffect。
> - 就绪视觉改成「PF3 变红」：用的是弹板上本来就有的官方 Lv3 充能件。
>   - P2：进入就绪时、以及就绪期间每 60 帧，执行 `playheadTwinkleAnimation.gotoAndPlay("three")`。这和原码升到 Lv3 时的调用完全相同，那条时间轴 `sounds:[]`，无声。charge/spark 的 Lv3 循环段 "three" 本来就在播。
>   - P3：就绪时强制显示 charge 和 spark（comboFixed 时不强制），对 twinkle/charge/spark 左右共 6 件调 `red(true)`。red 是官方受击闪红用的纯红颜色偏移，不是乘法染色。离开就绪时调 `red(false)`。只在颜色变化那一帧调用。
>   - 为什么不用乘法染色：官方 Lv3 件是青/黄/白色（charge d 件为 (0,221,249)，spark 件为 (108,255,243)），R 接近 0，乘 0xFF4040 会变成接近黑色，所以必须用颜色偏移。v32c 对 spark 用的 set_color 已删除。
> - bg/fg 本体的 8 档渐变保持不变。这里乘法染色没问题，因为 Lv3 本体帧是青白色，默认弹板平均 (164,228,241)，乘完是清楚的红。
> - 声音：新增的只有进入就绪时的一声 `se_player_skill_ready`。twinkle/charge/spark 时间轴都没有声音。

## 弹板皮肤适配（机兵武器）
- **数据**：皮肤登记表 `master/equipment_enhancement/equipment_flipper_skin/flipper_skin.orderedmap`，键是装备 ID。全游戏只有一套皮肤 `flipper_steampunk`，在 store131 里有 7 行：
  - 6 件机兵武器，特殊强化 Lv120 解锁：5010073 朱安里克（剑，红机兵）、5020042 哈尔波曼（斧，碧机兵）、5070044 亚弗登特（拳，暗机兵）、5080032 凯斯莫里（盾，橙机兵）、5090047 阿罗朗德涅莫（饰品，苍机兵）、5100020 哈里萨尔瓦（枪，闪机兵）；
  - 1 行自制：100012 延续的黄金（主线 12 章宝珠），强化 0 级即生效。
  - 这 7 行全部指向同一套资源：
    - animation `flipper_skin/flipper_steampunk`（出场动画，.gen 零件）
    - movie clip `flipper_skin/flipper_steampunk/f`（40 帧，帧布局与默认 flipper/f 相同）
    - 附加动画 `flipper_steam`（.gen 蒸汽）
  - 没有别的皮肤资源。store131 不是最新的 live 表；live 表如果后来又加了行，只要指向同一套资源，结论不变。
- **渲染路径**：皮肤生效后，`BattleFlipperImpl.replacedFlipperImageListIds/AnimationPath` 换成皮肤路径。`BattleFlipperView` 仍然创建同样的 backgroundL/R、foregroundL/R 四个 MovieClip，只是纹理换成 steampunk 的 f0000–f0039；尺寸按 366×204、偏移 96 硬编码。twinkle/charge/spark 三个充能件与默认弹板相同。另外多一个附加蒸汽动画 `additionalAnimationLeft/Right`，activated 时可见。
- **v32d 是否已覆盖**：已覆盖。P3 染色的就是这同一组 MovieClip 和 Lv3 件，不分皮肤。
  - steampunk 的 Lv3 帧（f0008）在官方图集里也是青白色，平均 (153,237,251)，乘法红的效果和默认弹板一致，不会发脏，所以不需要按皮肤单独处理。
  - 已加离线测试：在蒸汽朋克几何（宽 366、偏移 96）下，非 Lv4 时与原版完全相同；Lv4 时只多出染色、red() 和可见性变化。
  - 附加蒸汽动画不染色，蒸汽仍然是原色。
- **风险**：记忆里有一次「冰焰」重染，live 的 layer0.png 里 steampunk 的 .gen 零件可能已经是冰蓝色。即便如此，主帧 f0008 仍偏青白，乘法红效果相近。这一点需要真机确认。
- **真机怎么查**：
  1. 拿到上面任一件机兵武器，强化到 Lv120，或者直接装备 100012「延续的黄金」；
  2. 本地选项里打开「弹板皮肤」总开关；
  3. 皮肤按队伍槽位顺序取第一个命中的装备，所以把这件装备放在第一个带装备的槽位；
  4. 赛瑞斯当队长进战斗，确认弹板是蒸汽朋克外观，再看渐变、就绪红光和提示音。


| v32d 项 | sha256 |
|---|---|
| P2 / P3 after | 850b7356ba86f981b98d73d4d3619484acf2e7b2b0ff9f4ee8814113b7e9b8f0 / 99a129180d79c8a19e97a0e88f2bb68917063820ad30b88170bd69779deb3431 |
| 测试服 SWF | 83c160411956d03cbbd55be60610a33ab2f4091e31a79485dd6cbf92eb6c3f62 |
| `out/世界弹射测试服-v32d-pflv4.apk`（未签名） | 7e7015d355b19199ac08a866d616a8ccabc22378658bd488730cf8a9035f3349 |
| 本地 wf SWF | ac12e092ce62a8d17f16695706061b71d14aeee9c26cfebb3e0432b74f5a0d56 |
| `local/wf-local-pflv4d.apk`（未签名） | 6a00d6fe537262b4203f2543951d974014a835005791d3a1fec4338ebe2ed897 |

## 以下为 v32c 记录

> **v32c 修订**：v32b 真机可用，作者反馈两点：
> 1. 官方弹板变色是随充能逐步推进的渐变，我们的是一下子变全红；
> 2. 音效太多太吵。
>
> v32b、v32 的产物都没动。v32b 的脚本快照在 `snapshots/v32b/`。

## v32c 改了什么

### 渐变（P2 + P3）
- **官方怎么推进**：Lv3 时充能比例恒为 1，弹板本体已经停在 Lv3 帧，charge 和 spark 两个动画被隐藏。官方的「进度条」只覆盖 0→Lv3 这一段。
  - 本体帧号 = `rot*10 + 档位*2 + blink`。
  - 遮罩 `mask.scaleX` 随 `getPowerFlipChargeRate` 推进，fixedBackground 被它裁成充能条。
  - charge、spark 两个动画都分 one / two / three 三段。
- **P2 新逻辑**：档位为 3 且队长有 forLevels=4 行时，计算
  - `step = clamp(int((连击 - Lv3有效阈值) * 8 / (100 - 阈值)), 0, 7)`
  - Lv3 有效阈值 = `maskBit ^ comboCalculator.getPowerFlipNumComboChargeLv3()`，已含倒数减免。ComboCalculatorImpl 是这个接口的唯一实现。
  - 结果写进 `prevPowerFlipChargeLv`：充能中 = `10+step`，就绪 = 4。
  - 判断「有 Lv4 行」仍然复用 10 帧一次的节流查询，查询现在覆盖整个 Lv3 区间；其余帧从上一帧的 prev 推出。
  - 原逻辑用的档位变量 local3 不再改写；新状态单独存在 local7。所以 Lv3 的官方演出和音效照常。
- **P3 新逻辑**：bg/fg 四个 MovieClip 按 `k = step+1`（1..8）逐通道算 `255 - (255 - 目标值) * k / 9`，就绪时直接用满色 `LV4_COLOR`。颜色只在档位变化那一帧写，整个充能过程最多写 8 次。
  - 实测档位色：0xffeaea → 0xffd5d5 → 0xffc0c0 → 0xffabab → 0xff9595 → 0xff8080 → 0xff6b6b → 0xff5656 → 就绪 0xff4040。
  - spark 只在就绪时强制可见。
- **没有 Lv4 行的角色**：每一帧都与原版逐字节等价（离线模拟逐帧比对通过）。
  - 唯一的额外开销：Lv3 期间每 10 帧多一次无副作用的 override 查询。
  - prev 的值始终 ≤3，P3 走白色分支，而白色正是原值，所以不会写颜色。

### 声音（P2）
v32c 只剩一个新增提示音：进入就绪时播一次 `se_player_skill_ready`。

| 效果 | v32b 会触发的声音 | v32c |
|---|---|---|
| 进入就绪 | se_player_skill_ready ×1 | 不变：×1。预载组，调用方式与原版 Lv3 充能音相同 |
| 周期电弧（每 20 帧，左右各一个） | `thunder_small` 时间轴自带 `sounds:[sound_effect/thunder/se_electric_attack]`，每次 2 发，**这就是吵的来源** | 改成 `battle/common/layer0/condition/paralysis_ball`，时间轴 `sounds:[]`，**无声** |
| 弹板染色、spark | 无 | 无 |
| 官方原有声音（Lv1–3 充能音、se_flipper、PF 的 kaitengiri 等） | 不变 | 不变 |

- **paralysis_ball 的依据**：
  - 在 `BattleAssetPathCollectionBuilder.addCommonAssets` 第 710 行，属于函数顶层的 `addAnimationLayouts`，不在任何条件分支里，所以无条件加载。原版 MemberImpl 第 6049 行也在用这个路径。字符串在池 #16870。
  - 它的序列是 13 帧 loop。用 FixedPosition（index 2）放出时，`SimpleEffect.willRemove` 在 `frameCount > totalFrames` 后回收，不会常驻。
- **候选对比**（时间轴 sounds 字段都从解包数据读出）：

| 候选 | sounds | 结论 |
|---|---|---|
| paralysis_ball | 无 | 选用 |
| attack_to_hostile_smash | 无 | 8 帧，形状是冲击波不是电弧 |
| shine | `se_light_sharp_reflection` | 有声，排除 |

### 「Lv4 进度条」可选方案（没做）
在 P3 里复用官方的遮罩充能条：充能中时 fg 染 LV4_COLOR、bg 保持白色，再把 `mask.scaleX` 按 `(step+1)/8` 改写。这样 fixedBackground（白）会被逐渐裁掉，露出下面的红色 fg，效果就是官方那种「条」从白推到红。
- 也可以让 charge 动画按条的末端坐标显示 `three` 段。
- 成本：只在 draw 末尾多几次赋值，不需要新资源。
- 风险：mask 是官方每帧都写的值，需要在原码写完之后再覆盖；如果开着蒸汽朋克皮肤，`flipperImageWidth` 不同，需要真机核对。


## 以下为 v32b 记录

> **v32b 修订**：v32 的 P2 走懒加载播放 `sound_effect/thunder/se_charge_with_electricity`，真机一进入 Lv4 就绪就崩 `ClientError 8022 用于延迟加载的SoundAssetCache不存在`（`SoundAssetContainer.getDelayLoadAssetCache` 在战斗里找不到 index 99/100 的延迟缓存）。
> v32b 改成播放 `sound_effect/battle_common/se_player_skill_ready`，用的是与原版 Lv3 充能音完全相同的调用 `viewOrder.playSoundEffect(Me, path)`。
> - 这个音为什么一定已加载：它在 sound_effect_asset_iosbundled 里 loading=6；`BattleAssetPathCollectionBuilder.addCommonAssets` 第 560 行 `bookSoundFromMaster(6)` 无条件预载这一组；每场战斗的 `addBattleAssets` 第 773 行、技能预览 `AssetResolver` 第 2570 行都会调 addCommonAssets。原版 `MemberImpl` 第 870 行也用同一个调用播这个音。
> - 闪电 `thunder_small` 在 addCommonAssets 第 757 行的顶层 `addAnimationLayouts` 里（不在任何 if 分支里）无条件加载。官方雷属性命中特效也用这个路径（ActionDslAssetResolver 第 242 行）。
> - 选音过程：作者要「清脆」，所以把 APK bundle.zip 里的 SE 解码后测了一遍：

| 候选 | 时长 | 能量中心频率 | 主音高 | 3kHz 以上能量 | 起音 | 结论 |
|---|---|---|---|---|---|---|
| **se_player_skill_ready** | 1.19s | 5.2kHz | 5.5kHz | 65% | 6ms | **选用**：最亮、最短、起音最快 |
| se_boss_weakpoint_appearance | 1.35s | 5.3kHz | 1.8kHz | 57% | 4ms | 噪声成分较多，而且在 boss 战里有固定含义 |
| se_fever_time_yakumono_shine | 1.41s | 2.8kHz | 2.6kHz | 22% | 4ms | 音色最纯，但 Fever 中弹板物会频繁播放，容易被淹没 |
| （se_combo_power_flip_max_lv3） | 2.06s | 4.0kHz | 2.6kHz | 52% | 0ms | 就是普通 Lv3 充能音，听不出区别 |

> se_player_charge_completed 也在预载组里，但主 ABC 池里没有这条字符串。另外 v32b 不再用 fromCharCode 运行时拼字符串，P2 的 header 也回落到 [8,7,1,2]。


v31-overlimit120 基础上改 3 个方法，P-code 单方法拼接。没有回编整类，主 ABC 常量池零追加。每个补丁单独登记，可以重放：原 sha 打补丁，已打过的 sha 跳过，其他 sha 整包拒绝。
本目录产物都**未签名**，也没有装到任何设备。

## 三个补丁
档位整数一直是 3。所谓「Lv4」就是 Lv3 换成另一棵 DSL：数据侧用一行 forLevels 含 4 的 override，DSL 放在 **lv3 列**。

| ID | 方法 | 做什么 |
|---|---|---|
| P1 | `MemberImpl/startPowerFlip` | 队长分支里多一个判断：`param2==3`，且 `(ball as BallImpl).kyubiPowerFlipInitialCombo >= 100`（v28 写的拍板前连击快照，原始 int）。满足时先查 `getPowerFlipOverrides(4)`，非 null 就用它，后面照常走 lv3 列和 lv3 伤害乘区。查不到就回到原来的 `getPowerFlipOverrides(param2)`。登记了守卫：`BallImpl/resolveCollisionForPrimaryOrSummons` 的 sha 必须是 v28 版 |
| P2 | `BattleFlipperImpl/update` | 「Lv4 就绪」= 档位 3、当前连击 ≥100、`battle.abilityTotalizer.getPowerFlipOverrides(4)` 非 null，前两条短路。这个查询每次调用都会 new 一个 activation 和闭包，所以只在 `frameCount%10==0` 那帧查，其余帧沿用上一帧结果。结果写进 `prevPowerFlipChargeLv=4`，这个字段只有本类和 P3 读。进入就绪时，用 `viewOrder.playSoundEffect(Me, "sound_effect/battle_common/se_player_skill_ready")` 播一次（v32b，预载音，调用方式与原码 Lv3 充能音相同）。就绪期间每 20 帧在左、右弹板各放一个 `thunder_small` HitEffect，参数为 (FixedPosition, false, path, false, null)。从 4 退回 3 但没拍板时，charge/spark 不打回 "one"。基线用 v29/v31 字节，newfunction 62995/62996 原样保留 |
| P3 | `BattleFlipperView/draw` | 只在 activated 分支末尾生效。`prevPowerFlipChargeLv==4` 时 spark 强制可见（comboFixed 时不强制），bg/fg 四个 MovieClip 的 `.color` 和 spark 的 `set_color` 设成 `LV4_COLOR`。离开 Lv4 写回 0xFFFFFF，spark 的可见性由原逻辑每帧重置。颜色只在 `backgroundL.color != 目标` 那一帧写 |

可调常量都在 `pflv4_patches.py` 顶部：`LV4_COLOR=0xFF4040`、阈值 100、查询间隔 10 帧、闪电间隔 20 帧、闪电偏移 DX=120 / DY=20。改了常量，after sha 要重算。

## 常量池缺项和替代做法
- （v32 才有）`se_charge_with_electricity` 不在池里，当时是运行时拼出来的，现在已经废弃。v32b 的 SE 用池 #66230。
- int `0xFF4040` 不在 int 池里，改成 `pushshort/lshift/bitor` 运行时算出来。`0xFFFFFF` 用池里现成的 int #7。
- 其余 multiname 都是现成的：BallImpl、kyubiPowerFlipInitialCombo、getLazySoundPlayer（BattleViewOrder 接口名）、playSoundEffectWithRepeat、HitEffect/Simple/FixedPosition、show、color、set_color、visible、prevPowerFlipChargeLv。闪电路径用池 #16669。

## 哈希
| 项 | sha256 |
|---|---|
| 基线 APK `世界弹射测试服-v31-overlimit120.apk`（未签名） | e9d4db2ebabf6a9c41f06daeac1a0a48f5b975de4678c4211f4dcf89c60c1749 |
| 基线 SWF（unsigned 与 .signed.apk 里的逐字节相同） | b473110bc12f8264dd784804d3434aa9a825ad7edcf8644feaa5874c920c6c6e |
| P1 before → after | 675b4a9e…7f51 → 0aaa43db85c048dda9784925de22fccc38068f638449fcb59938420f12fc2d6b |
| P2 before → after | 24a82efa…9679 → 222e9770adac9c939205a6a75a65ba8375a5dddeb6e563f597c1fa8d17c56eb0（v32 为 0f43d214…，已作废，重放时会被拒） |
| P3 before → after | f41af0aa…cf11 → d6036a328608693e2e7a49267284511d40d44eb9f3f22a03840f28a7e8e78cb7 |
| **v32c** P2 / P3 after | d5ddf03a33be3cdd5de52f872f66cdbdba583426f22e6e7202a80e8ef3f3acb7 / 44877e65b088f180b544ecb1431103c4ccc3f1dc48185fc7ba48ec94ce1986d3 |
| **v32c** 测试服 SWF | 5e2e7e8f2576dbe38c85ae25f4ae1a09746f69576e9aea111fc3d5fc8372d5a1 |
| **v32c** 测试服 APK `out/世界弹射测试服-v32c-pflv4.apk`（未签名） | 8ab546e02841bc6c710bb8a238cb5a8eef910d7cd0a6e40d533f82a33cfeb71b |
| **v32c** 本地 wf SWF | 533a8323bb5ac0ffb6f4d2e117680ed588ef7acf3b175b2136b20648166ab469 |
| **v32c** 本地 wf APK `local/wf-local-pflv4c.apk`（未签名） | 222d1e4088241f20d990912d687a3913670a97ff7129bfcb8a4a70d9b1504eac |
| v32b P2 / P3 after | 222e9770… / d6036a32… |
| 输出 SWF（测试服 v32b） | 06aa4e01489549900144ba5fd0c287135e7cd26da76dad3121216e1a7ae68808 |
| 输出 APK `out/世界弹射测试服-v32b-pflv4.apk`（zipalign 过，未签名） | 84a0a799a622a3cb247775acc12b8cb8b880d6c8417e8f0b5b6fb37b0d729328 |
| 本地 wf 基线 `wf-local-overlimit120.apk` / SWF | 3153b82adb70fd83cbbb8468b7aa1a0c0d8bc53ef44ae8a8e5c4b1e44fcdb903 / 97864b79b533d2e28627e3fa3990939b6d2558b73e4a0743b73d3a9e481ff465 |
| 本地 wf 输出 SWF | 7c160b8b7b0b3a9fcfdf3f24383f2e82294d2a11d63952aa8f679fa19b2517fd |
| 本地 wf APK `local/wf-local-pflv4b.apk`（zipalign 过，未签名） | a77b93613cb5af07323d0bb45527e3c8d553d77c54d197728ec3c0d1ad0953d5 |
| （作废）v32 输出 SWF / APK | f3cc83f9… / 698dae61… |

APK 只替换了 SWF 一个成员。其余 4174 个成员内容逐字节相同，压缩方式也不变，AndroidManifest 不变，bundle.zip 不变。

## 静态验证（`verify_pflv4.py`：v32b 测试服 34 项、本地 wf 33 项全过，结果见 `out/verify-report-v32b.json` 和 `local/verify-report-local-v32b.json`）
- 重放结果逐字节一致；对输出再重放，三个补丁都是 already_present，输出不变（幂等）。
- 拒绝测试：vanilla 原版 SWF 在 P1 守卫处被拒；目标体改动 1 字节的副本被拒。
- 只有 `boot_ffc6` 变了。主 ABC 共 92601 个方法体，其中 92598 个逐字节相同，变化的正好是 3 个目标体。所有常量池和表都没变。
- 栈和作用域模拟都在 header 范围内：P1 [27,20,1,2]，P2 [16,8,1,2]，P3 [6,24,1,2]。
- `prevPowerFlipChargeLv` 在基线里只有 BattleFlipperImpl 读写，打补丁后多了 P3 的一处只读。`kyubiPowerFlipInitialCombo` 的写点仍然只有 BallImpl 一处。
- 离线执行（`avm_ext.py` 跑真实字节码，对象用模拟）：
  - P1：180 个组合中，174 个选中的 PowerFlipLogic 与原版完全相同，6 个换成了 override(4)。
  - P2：没有 Lv4 行时，91 帧的日志和 prev 与原版完全相同；有 Lv4 行时，只多播一次预载 SE（不走懒加载），闪电按周期出现，坐标正确，其余帧与原版相同。另做了静态检查：P2 体内没有 getLazySoundPlayer、playSoundEffectWithRepeat、fromCharCode，体内所有 SE 路径都属于 loading=6 组。
- 拒绝测试补充：v32 的 SWF 和本地 v32 SWF（P2 是旧 sha）都会被拒。
  - P3：非 Lv4 的 48 个组合与原版完全相同；进入和离开 Lv4 各只写一次颜色。
- 补丁前后的 P-code：`pcode/diff/P{1,2,3}.{before,after}.pcode.txt`。

## 重放 / 构建
```
python pflv4_apply.py IN.swf OUT.swf --report r.json --dump DIR
python build_pflv4_apk.py   # 测试服（当前 v32f）
WF_PFLV4_BASE_APK=D:/WF/out/角色超限-120/apk/out/wf-local-overlimit120.apk WF_PFLV4_OUT=D:/WF/out/赛瑞斯重做-20261015/apk/local/wf-local-pflv4f.apk python build_pflv4_apk.py
python verify_pflv4.py base/v31.swf work/v32.swf --unrelated <原版SWF> --json out/verify-report.json
```

## 数据侧前提
- 赛瑞斯的 leader_ability 需要一行 override，forLevels 为 "4"，id 为 `override_<code>_lv4`，DSL 放在 lv3 列（lv1/lv2 列指 empty）。
- 用 722（instant）时注意：totalizer 只有**一个** instant 槽位，后写的会覆盖先写的。如果赛瑞斯还有其他 722（比如形态切换），Lv4 行会被冲掉。这种情况改用 419（during，可以加固有 22 门控）。
- 没有任何 forLevels 含 4 行的角色，行为与 v31 完全一样。

## 必须上真机验证
1. 赛瑞斯当队长、有 Lv4 行：连击 ≥100 时拍板，打出的是 Lv4 DSL（范围、倍率、演出）。连击 99 时拍板仍是 Lv3。非队长位不触发。
2. 弹板效果：进入就绪约 1/6 秒内变红；spark 可见并染红；左右弹板周期性出现黄白闪电，位置 DX/DY 需要实调；清脆提示音（skill_ready）只播一次，不出现 8022/C8010。确认它和同一时刻的「技能就绪」音不会混淆。拍板后、或连击跌破 100 后恢复原样。
3. 普通队长、其他角色：弹板、音效、PF 与 v31 一致，看 Lv3 光效和 se_combo_power_flip_max_lv3。
4. 蒸汽朋克弹板皮肤开启时，染色和 spark 是否正常。
5. 联机：全员装 v32。弹板效果只在本机显示。Lv4 DSL 需要每台客户端都装 v32；没装的人在副本里看到的是 Lv3。确认 Impact 结果同步不出现错血或掉线。
6. 安装后清 cache/app（AIR SWF 缓存）。

## v32c 真机验收
1. 赛瑞斯当队长、有 Lv4 行：到 Lv3 后（约 ≤1/6 秒内）弹板开始从白往红渐变，连击越接近 100 越红，共 8 档；到 100 时满红，spark 显示红色电光，左右出现**无声**的黄色电弧（每 20 帧一次），提示音 skill_ready 只响一次。
2. 拍板后恢复白色；连击 99 时拍板打的仍是 Lv3。
3. 有倒数减免（Lv3 阈值降低）的队伍：渐变起点跟着降低。
4. 其他角色当队长：弹板颜色、声音与 v31 一致。
5. 听感：除官方原有声音外，只多一声 skill_ready。若嫌渐变跨度大，可调 `GRADIENT_STEPS`、`LV4_COLOR`；电弧频率调 `FX_EVERY`。
