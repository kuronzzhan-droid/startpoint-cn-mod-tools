# damage-type-rules-v1：DSL 伤害类型完整转换（2026-10-15 核实）

## 结论
这项能力**已经在**以下三个 APK 里，不需要再打补丁，也没有产出新 APK：
- 测试服 v29-coop `世界弹射测试服-v29-coop.apk`（be91bc50…）
- 测试服 v30-perf `世界弹射测试服-v30-perf.signed.apk`（6cc03e50…）
- 本机 com.leiting.wf `installed_base/wf_installed.apk`（bb525d93…）

三者的相关方法体逐字节相同。来源是 battle-rules 补丁。canonical 源码在 `D:/WF/out/q1056/rv4p/client-patch/battle-rules/damage.py`。
`wf_damage_type_override.py --check` 会锁定这几个方法的哈希，再用指令解释器直接执行 APK 里的真实字节码做核验。
用 `--apk/--out` 调用时，已含该能力的 APK 会以 exit 3 拒绝；原版 APK 会以 exit 4 拒绝，请改用 battle-rules 构建器，因为要新增方法和 trait，单方法拼接做不到；未知基线以 exit 5 拒绝。

## 涉及的方法（battle-rules 已改，本次未改任何方法）
| 方法 | sha256 前缀 | 作用 |
|---|---|---|
| `Environment/getBuffTargetAs` | 3534ccee6777 | 方法头插入，遇到 101/102/104/131/132/133 时原样返回。原版 default 分支会把它们变成 0 |
| `ImpactSourceContent$/NormalAttack` | 9377796ffd22 | 方法头插入：`param1 = MemberImpl.wfConvertNormalAttack(param1)` |
| `MemberImpl$/wfConvertNormalAttack`（新增） | d75e6f800238 | 遇到标记值时清空 7 个来源标志，只置目标那一个（独占），并把 buffTargetAs 和 powerFlipChargeLv 归 0。PF 标记会把 Lv 设为 1/2/3 |
| `AbilityTotalizer.wfResolveDamageType`（新增） | — | 角色级 424 规则，仅在非标记值、攻击者为 Member 时调用。没有规则时返回 0，不做改动 |

与其他叠层补丁**无重叠**：v29-coop 只改 `BattleDerailleur/getDeferralLevel`，v30-perf 只改 `MasterBinaryMap/getIndex`。

## 取值语义（判定区 `CreateHitArea` params[23] 或根头 tree[10]）
- **0**：继承外层；根头为 0 时是自动档，按动作种类判断（技能 DSL 和 629 都算技能）。与原版逐字节一致。
- **1/2/3/4**：原版行为。只切换通用增伤池，来源标志不变。所以显示、统计、独立乘区、耐性、试炼条、计数仍然按动作种类算。官方的 10 个判定区写的是 4，它们不受影响。
- **101 技能 / 102 能力 / 104 直击 / 131-133 PF Lv1-3**：完整转换。来源标志被改写后，下面这些都按目标类型算：
  - 通用池：`NormalAttackCalculator` 390/422/477/531
  - 独立乘区：直击 410/693、二次乘区、`statModifierAdditionalDirectAttackDamage` 路径；PF 分档和 413；技能 499/521；能力乘区
  - 敌方耐性：直击、PF、技能（含 SkillInvoker）、能力
  - 试炼条：`matchTrial`
  - 飘字样式和累计伤害指示：`EnemyImpl.applyAttack`、`EffectManagerImpl`、`DamageIndicatorManager`
  - 伤害统计：`BattleZoneStats`、`BattleZoneMemberStats`、结算 `NormalAttackStats`
  - 伤害类型计数：`enemyDamageCountUp`、`countUpSkillHit`、`countUpDamageByAbility`；PF 标记还会走 PF 命中计数
  - Fever 来源：`FeverPointReason`
  - 战斗分数
- **其他未知值（5-100、103、134 等）**：读作 0。旧 APK 读到 101+ 也读作 0，即自动档，不崩。

不在转换范围内的：真实直击次数，即 `DirectAttackScheduler` 的 `directAttackCount` 和直击次数触发，只有球真正撞到敌人才计；固定伤害和比例伤害；倍率本身；命中次数。

已知交互：如果 APK 带有 hitfx-silence，它会把「直击且 hitEffect=None」的命中静音。罗尔夫的命中特效是 `Fine`，不受影响；以后新写的 104 判定区不要配 `None` 命中特效。

## 数据（只随含该能力的 APK 发）
`cursed_abyss/build/rolf_direct_104.py` 默认只做 dry run，加 `--write` 才写 zip（applies_on 1.4.203 → 1.4.204）。改动是把罗尔夫 149986 三棵树中的 6 个判定区从 4 改成 104。
风巨蜥 149998 从 1.4.198 起就已经是 102（根头和 25 个判定区），不需要改。
