# 第三轮客户端准入审计

作者 2026-10-16 17:14：新木桩和武器收入，正式服不开放 GM 武器获取。

## 决策

恢复第一轮排除的全部 21 个训练副本（1103–1123）及 131 个顶层表键、62 个独立资源。
GM 5990001–5990006 恢复 25 个顶层表键（展开 31 个叶行）和 1 个直击 DSL；
图标复用公共 item/sprite_sheet 的 6 个已有条目，PNG/atlas 随公共配套保留。
GM 原脚本注明“觉醒 0 起满额，不需要强化”；保留 equipment_status 等级 1、5 终态。
没有新增独立强化/觉醒表键；不凭空创造数据。

## 刻意不收的 GM 获取途径行（客户端）

客户端获取途径行命中 0 个；本轮 excluded_rows=0，excluded_members=0。
源客户端链没有 GM 商店/掉落/奖励/任务/兑换/邮件/礼包行可剔除；未编造不存在的排除行。
服务端获取途径另见服务端准入明细；客户端本体中 item 是魂珠定义，equipment 是武器定义，均不构成发放入口。
所有可读表的精确武器 ID、mod_gm_* 和 gm_direct_hits 引用均落在本体表；
没有以 GM 为终点的奖励包装行，因此没有需要继续反向追踪的间接包装链。
如未来输入出现未分类引用或无法安全拆分的混合获取行，构建会报 blocker 并停止。

## 全表扫描范围

| 视图 | 候选成员 | 字典表 | 纯文本表 | 空占位 | 叶值 | GM 命中 |
|---|---:|---:|---:|---:|---:|---:|
| ours | 3278 | 2095 | 1 | 25 | 619040 | 31 |
| hui | 2361 | 2095 | 1 | 25 | 616939 | 0 |

已知 master 路径加上两条链实际变动成员一并扫描。缺失逻辑路径逐项保存在 JSON；
空占位均校验固定 16 字节编码、解压内容为四个零字节。没有无法解码的非空 master 表。
这属于本地静态数据审计，服务器实际开关及客户端运行效果未核实。

## 恢复收入的 GM 表键（完整值见同名 JSON 的 gm_body_rows）

| 表 | 键 | 最终来源 |
|---|---|---|
| master/ability/ability_soul.orderedmap | 5990001 | pinball-1.4.192-1.4.193-1-gm-weapon6-local.zip |
| master/ability/ability_soul.orderedmap | 5990002 | pinball-1.4.192-1.4.193-1-gm-weapon6-local.zip |
| master/ability/ability_soul.orderedmap | 5990003 | pinball-1.4.192-1.4.193-1-gm-weapon6-local.zip |
| master/ability/ability_soul.orderedmap | 5990004 | pinball-1.4.192-1.4.193-1-gm-weapon6-local.zip |
| master/ability/ability_soul.orderedmap | 5990005 | pinball-1.4.192-1.4.193-1-gm-weapon6-local.zip |
| master/ability/ability_soul.orderedmap | 5990006 | pinball-1.4.192-1.4.193-1-gm-weapon6-local.zip |
| master/item/equipment.orderedmap | 5990001 | pinball-1.4.192-1.4.193-1-gm-weapon6-local.zip |
| master/item/equipment.orderedmap | 5990002 | pinball-1.4.192-1.4.193-1-gm-weapon6-local.zip |
| master/item/equipment.orderedmap | 5990003 | pinball-1.4.192-1.4.193-1-gm-weapon6-local.zip |
| master/item/equipment.orderedmap | 5990004 | pinball-1.4.192-1.4.193-1-gm-weapon6-local.zip |
| master/item/equipment.orderedmap | 5990005 | pinball-1.4.192-1.4.193-1-gm-weapon6-local.zip |
| master/item/equipment.orderedmap | 5990006 | pinball-1.4.192-1.4.193-1-gm-weapon6-local.zip |
| master/item/equipment_status.orderedmap | 5990001 | pinball-1.4.192-1.4.193-1-gm-weapon6-local.zip |
| master/item/equipment_status.orderedmap | 5990002 | pinball-1.4.192-1.4.193-1-gm-weapon6-local.zip |
| master/item/equipment_status.orderedmap | 5990003 | pinball-1.4.192-1.4.193-1-gm-weapon6-local.zip |
| master/item/equipment_status.orderedmap | 5990004 | pinball-1.4.192-1.4.193-1-gm-weapon6-local.zip |
| master/item/equipment_status.orderedmap | 5990005 | pinball-1.4.192-1.4.193-1-gm-weapon6-local.zip |
| master/item/equipment_status.orderedmap | 5990006 | pinball-1.4.192-1.4.193-1-gm-weapon6-local.zip |
| master/item/item.orderedmap | 5990001 | pinball-1.4.206-1.4.207-1-overlimit120-wagner-local.zip |
| master/item/item.orderedmap | 5990002 | pinball-1.4.206-1.4.207-1-overlimit120-wagner-local.zip |
| master/item/item.orderedmap | 5990003 | pinball-1.4.206-1.4.207-1-overlimit120-wagner-local.zip |
| master/item/item.orderedmap | 5990004 | pinball-1.4.206-1.4.207-1-overlimit120-wagner-local.zip |
| master/item/item.orderedmap | 5990005 | pinball-1.4.206-1.4.207-1-overlimit120-wagner-local.zip |
| master/item/item.orderedmap | 5990006 | pinball-1.4.206-1.4.207-1-overlimit120-wagner-local.zip |
| master/string/custom_ability_string.orderedmap | gm_direct_hits | pinball-1.4.214-1.4.215-1-balance-1016-local.zip |

## 恢复收入的训练副本

| quest id | 名称 |
|---|---|
| 1103 | 仅直击木人·无 |
| 1104 | 仅能力木人·无 |
| 1105 | 仅技伤木人·无 |
| 1106 | 仅强化弹射木人·无 |
| 1107 | 仅直击木人们·无 |
| 1108 | 仅能力木人们·无 |
| 1109 | 仅技伤木人们·无 |
| 1110 | 仅强化弹射木人们·无 |
| 1111 | 全伤害木人·无 |
| 1112 | 全伤害木人们·无 |
| 1113 | 能量瓶木人·无 |
| 1114 | 伤害圈木人·无 |
| 1115 | 能量瓶木人们·无 |
| 1116 | 伤害圈木人们·无 |
| 1117 | 超·结实假人(经典) |
| 1118 | 超·极速假人 |
| 1119 | 超·强力假人 |
| 1120 | 超·诅咒假人 |
| 1121 | 超·守护假人 |
| 1122 | 超·痛苦假人 |
| 1123 | 超·痛苦假人们 |

131 个恢复表键和 62 个独立资源的完整值、路径及来源均列在 inclusion-policy-r3.json。

## 图标与本体来源

- D:\WF\out\kulo-patch-toolkit\cursed_abyss\build\gm_weapons.py：本体能力、共享图标模板及状态行。
- D:\WF\out\kulo-patch-toolkit\cursed_abyss\build\gm_weapon6.py：5990006 能力、状态与弓图标复用。
- 所有收入数据取固定我方 1.4.219 终态，不执行以上源构建脚本。
