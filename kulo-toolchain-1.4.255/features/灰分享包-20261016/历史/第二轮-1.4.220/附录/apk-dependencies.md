# APK 数据依赖静态审计

此文供主说明引用。证据为本机最终v33文本档案及生成源码；没有运行灰APK，灰现有APK是否已含这些能力均为**未核实**。未收APK、签名、keystore、.so。

用户提到的PR #43路径 `docs/client-apk-patches-v33/` 在当前本地 `kulo origin/main` 树中未找到；PR当前状态未联网核实。以下采用 `D:\WF\apkp1016\apk-patches\` 本地档案，不把PR存在等同灰已部署。

## 功能与依赖

| 功能/数据 | 必须保留的补丁 | 缺失后的行为/已知错误 | 服务端源码要求 |
|---|---|---|---|
| 五星角色超限 Lv120（瓦格纳 111183；护花使龙/休尔特 141099）；character_status 的120级行、超限结晶10000320、悖论之核10000302、character_overlimit.json、等级觉醒任务 | O1、O2、O3、O4、O5、O6、O7、bundle-level-cap、bundle-experience、bundle-pedestal-atlas | 缺 O1/内置上限表则仍受官方4次突破限制；缺 O2/O3/O4/O5 则结晶筛选、重复角色限制与双道具可突破次数显示不一致。缺101–120经验表时，同房客户端读取120级角色存在缺行报错风险；准确错误码未核实。不能把内置表同键放 CDN：设计说明记录主键冲突7051。 | 需要。灰 origin/main 不存在 src/lib/character-overlimit.ts；必须移植每角色突破/经验上限、零重复角色超限、一次请求不跨官方边界、等级觉醒任务与 extra_costs 校验后原子双扣等源码。只应用 assets JSON 行不够。 |
| 超限台座全身/半身 _6、_7；第5次突破起_6、第8次突破且Lv120且首盘全觉醒时_7 | O6、O7、bundle-pedestal-atlas | 缺 O6/O7 则仍显示旧台座；只改方法而缺APK内置24帧图集会请求不存在资源，具体错误码未核实。CDN包不能替代该APK内置图集依赖。 | 台座显示本身不需要新服务端源码；超限资格仍依赖上项服务端规则。 |
| 赛瑞斯 129999 PF Lv4 override 与红色充能提示；forLevels含4的override、override_seris_dragon_lv4、底层PF档位保持3 | P1、P2、P3、九尾拍板前连击快照 | 缺P1不能在100连击拍板时优先选Lv4 override；缺P2/P3没有相应八档渐变、红光与就绪提示。当前实现底层仍为Lv3，不能据此断言旧APK必崩。若错误地让真实档位流到4，已知取DSL空引用F1009、攻击计算2702。早期P2懒加载提示音曾报8022，最终v32f已修复。 | 该PF选择/演出不需要新服务端源码；同房须使用一致客户端，否则队友副本可能呈现不同PF。 |
| Fever 箭头换随机道具（赛瑞斯及挂同类标记的队长）；unique_condition 1299901..1299909、string_id fever:items:候选键、direct_instant_item及配套level/program/动画 | B1、B2、B3、B5 | 完全未装B系时该约定只是普通Unique标记，旧客户端继续开Fever箭头，箭头换道具不生效；这点来自源码规则推断，未在灰APK运行。只装部分/旧版B系曾报8013（主表未加载）、8601（空标记槽）、14502（rotationPanelAnimation=None）、8037（候选DSL未leading预载），最终v32l采用安全取表及Some(backgroundAnimation)。不能把这些中间错误冒称完全无补丁必崩。B4已撤销。 | 候选随机与资源预载在客户端执行，无新服务端源码要求；各端须同数据/同补丁以维持副本一致。 |
| 通用技能准备 alt 语音轮换；正常/变身skill_ready连续_alt_N文件，最多5条，缺号停止 | V1、V2、V3 | 未装V1不会按通用规则轮换，未装V2战斗不预载新增alt，未装V3图鉴不列出新增alt。全部未装时通常只播放原有准备音，未发现专用必崩码；部分混装的具体错误码未核实。V1保留5个既有专用轮换角色逻辑。 | 不需要新服务端源码。 |
| 杰拉德149999及5个既有专用角色的准备音轮换；white_wolf_gerald原句与skill_ready_alt_1..3、149990/129992/139993/159998既有专用准备音 | 65-gerald-149999-ready-voice、06-summer-bai-voice、07-gerald-129992-ready-voice、15-author-ready-voices | 149999在最终v33已有专用四拍轮换、预载与图鉴；缺专用补丁则不能仅靠V1–V3假定已解决，因为V1明确跳过white_wolf_gerald等5个已有专用角色。最终HudMemberStatus P-code含149999 alt_1/2/3分支。早期voice193_build.py的限制不代表219+v33终态。缺文件时专用分支保留原生音，未发现专用必崩码。 | 不需要新服务端源码。 |
| 凯尔 kyle_moon 终态直击、充能与PF表现；Unique13999010充能上限、Unique13999011/13999012直击倍率、PF追加命中attack_to_hostile_hit且randomRotation=false | 53-charge-cap-unique、54-kyle-direct-multiplier、55-kyle-pf-marker-silence、56-kyle-direct-merge | 缺53仍受官方充能上限；缺54不会执行数据层数约定的凯尔队长直击公式；缺55追加PF有重复数字/音效/闪烁；缺56多段逐次调度，性能收益不生效。以上未发现专用必崩码。 | 以上战斗行为不需要新服务端源码。 |
| 含新能力枚举422/423/424/724的角色平衡与重做；422冲刺参数、423回槽来源限制、424伤害类型转换、724按满槽比例增减Fever | 03-dash-parameter-422、04-fever-ratio-724、20-damage-type-conversion、31-gauge-gain-rules | 未支持的能力枚举解析可能报C7050。即使仅靠DSL标记而未走新枚举，缺完整伤害类型转换仍可能把101/102/104/131–133按旧类别结算，统计/耐性/计数/乘区错误。早期423循环VerifyError #1021为已修中间实现，不能当作最终数据固有缺陷。 | 词条战斗解释不需要新服务端源码；按结算统计再判断是否有配套服务端校验，灰部署状态未核实。 |
| 角色/队长技作者自定义文案；CustomAbilityStringTable desc_override_<string_id> | 02-panel-description-override | 无补丁时按旧模板描述，作者覆盖文案不生效；旧不安全取表版在CustomAbilityStringTable未加载时报8013。最终实现缺表回退原文。 | 不需要新服务端源码；技能正文仍须正确action_skill各档文本。 |
| 双形态角色、重设计像素与hidden_机制状态；ModDualForm标签/Unique22、frame.scale、UniqueConditionTable string_id以hidden_开头 | 21-dual-form-animation、45-render-frame-scale、58-hidden-unique-icons | 缺21不切special形态/不按约定预载；缺45自制像素占屏与设计不一致；缺58机制状态会显示并占图标页数。未发现专用错误码；灰APK现状未核实。 | 不需要新服务端源码。 |
| 诅咒/深渊装备与能力魂门控（如最终包保留8000101–8000115）；8000101..8000115、精确Single/Multi副本白名单、直接装备强化Lv120例外 | 11-abyss-equipment-mode-gate | 缺门控时强力装备/魂珠的适用范围可能失守，且直接装备与魂珠例外不一致。不是已知必崩问题。PARADOX r4若只使用普通表/DSL无独立补丁编号；是否另需专用客户端逻辑未核实。 | 须另核对服务端装备/编队准入规则；本审计未把客户端门控等同服务端保护。 |
| 新增高等级领主战/共同决战与属性耐性配置；quest->field_data->zone->general_*等级行、关卡sub_name属性伤害配置（若采用） | 44-quest-element-resistance（有该数据约定时） | 普通新副本表和官方DSL本身不必然需要新增APK补丁；若用sub_name耐性约定而缺44，属性耐性不生效。若general_*最高等级不足，则是数据配套缺口，可报U_3be147，须靠prepush level检查，不能用APK依赖说明掩盖。 | 开放、次数、掉落、联机准入等须有对应服务端JSON行；是否另含专用机制源码需按实际副本逐项核对，未核实。 |

## 编号与方法对照

P/B等字母编号在perf补丁里有重名；此处P1–P3特指v32f PF，B1/B2/B3/B5特指v32l Fever，不是perf2的同名字母。

| 补丁 | 方法/资源 |
|---|---|
| O1 | `GeneralCharacterLogic/get_maxOverLimitStep` |
| O2 | `OwnedOverLimitLogic/getOwnAwakingCrystalToOverLimit` |
| O3 | `OwnedOverLimitLogic/getAwakingCrystalToOverLimit` |
| O4 | `OwnedOverLimitLogic/getOverLimitState` |
| O5 | `OwnedCharacterLogic/getPossibleOverLimitCountByItem（已构建双道具版）` |
| O6 | `GeneralCharacterLogic/getPedestalImagePath` |
| O7 | `GeneralCharacterLogic/getHalfPedestalImagePath` |
| P1 | `MemberImpl/startPowerFlip` |
| P2 | `BattleFlipperImpl/update` |
| P3 | `BattleFlipperView/draw` |
| B1 | `YakumonoManagerImpl/activate` |
| B2 | `YakumonoManagerImpl/deactivate` |
| B3 | `BattleQuestBaseImpl/resolvePathCollectionForDashPanel` |
| B5 | `BattleQuestBaseImpl/leadingResolvePathCollection` |
| V1 | `HudMemberStatus/update` |
| V2 | `BattleCharacterLogic/resolveFollowingPathCollection` |
| V3 | `CharacterVoiceLogic/createVoicePathMap` |

O1–O7之外仍须保留APK内置两张表与台座图集；不允许用CDN同键去覆盖APK内置行。O5是已构建的双道具版，后续零核调整未构建，不应写成终态。B4已撤销。

## 证据边界

- F1009/2702指真实PF档位误传4，不是本次安全Lv3+override数据在旧APK的必然结果。
- Fever的8013/8601/14502/8037有特定不完整/中间实现前提，完整缺B系通常是功能不生效；灰实包行为未核实。
- 通用语音轮换无已证实的专用必崩码；不要编造。
- Lv120联机伙伴也须有101–120经验表；档案记录缺行风险，准确码未核实。
- 服务端JSON更新不等于服务端已具备超限源码；灰origin/main缺该模块为本次git show直接核实。

## 本地来源

- `D:\WF\apkp1016\apk-patches\02-panel-description-override\README.md`；SHA-256 `564084cc46507b775f1e7f43a8a5b385abb006a7bb87fa6209ed2a76d1f1d1da`。
- `D:\WF\apkp1016\apk-patches\03-dash-parameter-422\README.md`；SHA-256 `2808862d8f5dad94944a1fab5da6d7b6b18985c7645f6fb7762f1eb9c866f9e3`。
- `D:\WF\apkp1016\apk-patches\04-fever-ratio-724\README.md`；SHA-256 `970164658af4e35ed9bb1d7272e5ede69690f4c84a070e3733a057ee946e289f`。
- `D:\WF\apkp1016\apk-patches\06-summer-bai-voice\README.md`；SHA-256 `81de2e3aa889298524fd2db7dff2fe68a4cbe76ad3bd8ad80edc8dfac6cafe2d`。
- `D:\WF\apkp1016\apk-patches\07-gerald-129992-ready-voice\README.md`；SHA-256 `3b1847ae7ce3a8485f0d36c950fc60310170d346eb79d70c156b826ff40531e9`。
- `D:\WF\apkp1016\apk-patches\101-overlimit-paradox-core-item\README.md`；SHA-256 `eaae6a18c3c1b473c6a54db01bf029ce7e94498c78378c168c755e9da012d9d8`。
- `D:\WF\apkp1016\apk-patches\11-abyss-equipment-mode-gate\README.md`；SHA-256 `5eeed520537dc75ac86ff40c472f02aabf2f1942c99da9ddc3cf448341f3d17b`。
- `D:\WF\apkp1016\apk-patches\15-author-ready-voices\README.md`；SHA-256 `3730683b579933b17b5b58863180c376024db2ae241833b7e8bdb17400b9c3bb`。
- `D:\WF\apkp1016\apk-patches\20-damage-type-conversion\README.md`；SHA-256 `af6bbda011d7edc53326ef20d08e8e7bc236aae5d2fc6f450a6a2b534eecf62c`。
- `D:\WF\apkp1016\apk-patches\21-dual-form-animation\README.md`；SHA-256 `35f386240ad0461e8e851c41ebbff8d454c59104bf521289825a49716bfc537c`。
- `D:\WF\apkp1016\apk-patches\31-gauge-gain-rules\README.md`；SHA-256 `b8d724dc605d78a20dbdc504a4ca9f348ba7cdbec8694d2dc273d538ea9f4193`。
- `D:\WF\apkp1016\apk-patches\44-quest-element-resistance\README.md`；SHA-256 `9cdd92974eb053199d7843472204a85ece0ec9d24220721c82bf0a609d120302`。
- `D:\WF\apkp1016\apk-patches\45-render-frame-scale\README.md`；SHA-256 `e9c37a9e1c9aa7311c2feee783c58bec0adb3bfcbb6ccd7ad9fca4b6374bc874`。
- `D:\WF\apkp1016\apk-patches\53-charge-cap-unique\README.md`；SHA-256 `437a45a9e6cd88b52975bb0ca72b1aa36ff0ecb8e3be775e4ebc3c951626172e`。
- `D:\WF\apkp1016\apk-patches\54-kyle-direct-multiplier\README.md`；SHA-256 `247d3bcd0c723b7bb87e2a7c7432b35c37c041acbce630b6d1d00317673f415c`。
- `D:\WF\apkp1016\apk-patches\55-kyle-pf-marker-silence\README.md`；SHA-256 `0486cdc270389e52310122f0cfd493ac0e302f93c4b19ed8d4459e0abd83024a`。
- `D:\WF\apkp1016\apk-patches\56-kyle-direct-merge\README.md`；SHA-256 `a2478cc1dd1e199dad2f831022fdbddf42d479de840d927c3cb190b4cca691d6`。
- `D:\WF\apkp1016\apk-patches\58-hidden-unique-icons\README.md`；SHA-256 `cf1232c5ce38277bbdcc27931cc2a128ca568ecf394a78dc4ac3e5d4a6bdb3b8`。
- `D:\WF\apkp1016\apk-patches\65-gerald-149999-ready-voice\README.md`；SHA-256 `5b7eceb10119dda9d1ea6d2c31cb2ed4c8ed40d491b8d4c1d48949778499c3cb`。
- `D:\WF\apkp1016\apk-patches\78-overlimit-crystal-buttons\README.md`；SHA-256 `2d926a0923e656f2e712e209d27018392c801caad0907fd5d912781708704152`。
- `D:\WF\apkp1016\apk-patches\79-overlimit-experience\README.md`；SHA-256 `2dbc197b943fffd8f301692a3b33be0ea5bbff4ea5ff4393e5d181a4aaae69e1`。
- `D:\WF\apkp1016\apk-patches\80-overlimit-full-pedestal\README.md`；SHA-256 `4a153339b24a2e8ffe0820d0f6a076be234b92d36a08be77abd28e8543283853`。
- `D:\WF\apkp1016\apk-patches\81-overlimit-half-pedestal\README.md`；SHA-256 `93cd17d2822e2d7457e3b50a59d5de308ffcbb6731ef4a0872724a3f7d935f1e`。
- `D:\WF\apkp1016\apk-patches\82-overlimit-level-cap\README.md`；SHA-256 `aea9cb095d16912b5b3fc273a14ecff5cef43b097a665eecc71d5e0bd915f83b`。
- `D:\WF\apkp1016\apk-patches\83-overlimit-max-step\README.md`；SHA-256 `5089a1ae301a94beb6d9331d4901b52b8ccde58894fffd4f14e097962f7d2ece`。
- `D:\WF\apkp1016\apk-patches\86-overlimit-pedestal-atlas\README.md`；SHA-256 `3de665bd1fc502f0234dd5d78ebaef88ca4dc002e365c7ca3aa89372924989ba`。
- `D:\WF\apkp1016\apk-patches\87-pf-lv4-color\README.md`；SHA-256 `56900c21adfaf2a272245537479fc5dd1f9a930c13fc75579de40e99ade0a48c`。
- `D:\WF\apkp1016\apk-patches\88-pf-lv4-dsl\README.md`；SHA-256 `1ed6c014f0f68167770c77794919202ea7579bbe12d863a1ef711d608ff21974`。
- `D:\WF\apkp1016\apk-patches\89-pf-lv4-ready\README.md`；SHA-256 `1a684642b6169145089e34536126a4316ac2a2712b7c67ff4dba09e6d52ba586`。
- `D:\WF\apkp1016\apk-patches\90-fever-arrow-close\README.md`；SHA-256 `71e3594d155a31ccaaf0ab26e12bfa233023fe17a9b91fcac02ffc5ddb97cb23`。
- `D:\WF\apkp1016\apk-patches\91-fever-arrow-items\README.md`；SHA-256 `fe0067f300d1c1af75baca6822af29ca710c9375d588fb63676237e7dbed6e16`。
- `D:\WF\apkp1016\apk-patches\92-fever-items-preload\README.md`；SHA-256 `e796c7482e4d0d286ef932568c7d0efe48ffca55f1a9734dbcaab61bccaf074c`。
- `D:\WF\apkp1016\apk-patches\93-fever-items-leading-dsl\README.md`；SHA-256 `7aced241a8d7f34fe4ae88d728069ce987349457d16198db91a21f5ca06497d7`。
- `D:\WF\apkp1016\apk-patches\94-generic-ready-gallery\README.md`；SHA-256 `56e2de3ad5f73cbeb5e7cc605d596088b10f575dc9f9cfbdce1abf127eaa2d2c`。
- `D:\WF\apkp1016\apk-patches\95-generic-ready-preload\README.md`；SHA-256 `30d813103373ce7d0ecd00583c728214a1369a2c4e25aeedb119ccd622215587`。
- `D:\WF\apkp1016\apk-patches\96-generic-ready-rotation\README.md`；SHA-256 `c6a9f77c874a0fa5c2698ffd047e3f40648a9e85dc246c6dbc8c3bddf3abb9c9`。
- `D:\WF\apkp1016\apk-patches\96-generic-ready-rotation\pcode\boot_ffc6--HudMemberStatus_update.pcode.txt`；SHA-256 `ffee0e18968ace50e816cc0705c8f9a46c25ee600f585c0f2d3fa403fd9835db`。
- `D:\WF\apkp1016\apk-patches\README.md`；SHA-256 `ebee98a24f5cbdfc24ad9f0ee6b2879ad9f57d04f74d58adebc07d2de05c5ef8`。

补充：`D:\WF\out\角色超限-120\设计说明.md` 第79–100行附近列内置表7051与同房经验表限制；`server-patch/0001-*.patch` 明列7个源文件/配置及单测；`D:\WF\out\赛瑞斯重做-20261015\pf_lv4_client.md` 记录真实档位4的崩溃根因。
