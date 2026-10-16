# 客户端速查(手写)

全量类索引:[gen-client-classes.md](gen-client-classes.md);master 表读取类:[gen-client-master-tables.md](gen-client-master-tables.md)。

## 源码在哪

| 位置 | 状态 |
|---|---|
| `D:\WF\decompile-complete-20261014\scripts` | **首选**:补全版 AS3(gpt-6.1-sol, 2026-10-14,§§ 412→24,git 基线 202691d);同目录 pcode/ 是全量 P-code,out/REPORT.md 是补全与联机分析报告 |
| `D:\WF\_archive\kept\弹国服-tools-and-decompile\scripts` | 旧版反编译原档,**只读**;漏了 BattleDerailleur.addSocketCommand 的入队调用等,查联机别用它 |

文件名里的行号不可信:AS3 里 `"lineNumber"` 是原 Haxe 行号(如 Battle.hx 2264),和 .as 文件行号不同。

## 关键入口

| 子系统 | 类 | 路径(相对 scripts/) |
|---|---|---|
| 普通攻击伤害 | `NormalAttackCalculator` | pinball/online/battle/impact/attack/NormalAttackCalculator.as |
| 敌人等级取行 | `GeneralEnemySourceHelper.getSurjectivity` | pinball/common/data/battle/enemy/GeneralEnemySourceHelper.as(找不到 key≥lv 抛 U_3be147) |
| 结算分数 | `Battle` 约 2525 行:`scoreCalculator.getTimeMultiplier(…, isSinglePlayBossBattle)`、MVP/贡献分 | pinball/scene/battle/battle/Battle.as |
| 战斗种类判定 | `QuestIdBattleKindTools` | pinball/common/data/quest/id/QuestIdBattleKindTools.as |
| 联机 lockstep | pinball/online/、pinball/context/socket/(battle、lounge、dummy、empty)、pinball/context/remote/(real、operation、dummy) | — |
| 联机掉线判据 | `BattleDerailleur` / `BattleScenePlayingStateImpl`:队友落后 D≥48+24×8=**240 帧**→isolateAsForceAbort 转单人且**不重连**;开局缓冲 **15 帧**(=0.25s);战斗心跳 payload=**null**、约每 **9 次 update** 一发(服务端须转发);旧帧到达抛 **15001**。详见 `D:\WF\decompile-complete-20261014\out\REPORT.md` | pinball/scene/battle/derailleur/BattleDerailleur.as |
| 进战加载与图集 | `BattleStartProductionViewService` | pinball/loading/battle/BattleStartProductionViewService.as |
| 技能描述显示 | `ActionSkillLogic`、`DialogCharacterSkillDescriptionVariationTranslator`、`ActionSkillReportTools` | common/data/skill/action/、dialog/general/variation/、abilityDescription/actionSkill/ |
| 能力描述生成 | `AbilityDescriptionGenerator`、`AbilityDescriptionTools`、`AbilitySummerizeTools` | common/data/ability/description/ |
| master 表 | `<Camel>Table.as` + `<Camel>Values.as`(parseAtN = 第 N 列) | pinball/master/generated/(运行时在 master/runtime) |

## 常用 rg

```bash
rg -l "class NormalAttackCalculator" "D:\WF\decompile-complete-20261014\scripts"
rg -n "parseAt14" "D:\WF\decompile-complete-20261014\scripts\pinball\master\generated\CharacterValues.as"
rg --files "D:\WF\decompile-complete-20261014\scripts" | rg -i "socket"
```

## 坑

- 客户端补丁只准单方法 P-code 拼接;FFDec 整类回编在真机上不等价(战斗 F1069)。
- 装 APK 后必须删 `cache/app`,否则跑旧的解包 SWF。
- 真机 skill_cutin 读 android 根目录的 ATF,不读 PNG。
- 战斗图集预算 4096²,重型自制角色 5-6 个同场就溢出(三人五重房 U_1d93f4)。
