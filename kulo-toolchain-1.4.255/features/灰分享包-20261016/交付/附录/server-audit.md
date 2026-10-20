# 服务端第三轮审计

固定灰基线224aa2a663b7756fc8a34c0f37f1ae61ad81800c，目标136→220。26文件/1438操作，冲突0，获取途径排除0。

# 第三轮服务端 GM 与训练副本审计

GM 武器只带本体与已有武器的使用配套；正式服不开放获取。

逐个解析我方 169 个服务端 JSON、灰基线 169 个 JSON 与合并视图 170 个 JSON。
精确 GM 引用：灰基线 0 条；我方 48 条；合并视图 48 条。未知 GM 引用将中止构建。

## 收入的 GM 行

| 文件 | 键/ID | 分类依据 | 我方与交付值 |
|---|---|---|---|
| `assets/equipment_dissolve.json` | `5990001` | 已有武器熔炼产生同名魂珠，属于消耗已有武器的使用配套 | `{"ability_soul_id":5990001,"obtain_source":1,"generate_ability_soul":true,"max_level":5}` |
| `assets/equipment_dissolve.json` | `5990002` | 已有武器熔炼产生同名魂珠，属于消耗已有武器的使用配套 | `{"ability_soul_id":5990002,"obtain_source":1,"generate_ability_soul":true,"max_level":5}` |
| `assets/equipment_dissolve.json` | `5990003` | 已有武器熔炼产生同名魂珠，属于消耗已有武器的使用配套 | `{"ability_soul_id":5990003,"obtain_source":1,"generate_ability_soul":true,"max_level":5}` |
| `assets/equipment_dissolve.json` | `5990004` | 已有武器熔炼产生同名魂珠，属于消耗已有武器的使用配套 | `{"ability_soul_id":5990004,"obtain_source":1,"generate_ability_soul":true,"max_level":5}` |
| `assets/equipment_dissolve.json` | `5990005` | 已有武器熔炼产生同名魂珠，属于消耗已有武器的使用配套 | `{"ability_soul_id":5990005,"obtain_source":1,"generate_ability_soul":true,"max_level":5}` |
| `assets/equipment_dissolve.json` | `5990006` | 已有武器熔炼产生同名魂珠，属于消耗已有武器的使用配套 | `{"ability_soul_id":5990006,"obtain_source":1,"generate_ability_soul":true,"max_level":5}` |
| `assets/equipment_element.json` | `5990001` | 武器属性注册 | `-1` |
| `assets/equipment_element.json` | `5990002` | 武器属性注册 | `-1` |
| `assets/equipment_element.json` | `5990003` | 武器属性注册 | `-1` |
| `assets/equipment_element.json` | `5990004` | 武器属性注册 | `-1` |
| `assets/equipment_element.json` | `5990005` | 武器属性注册 | `-1` |
| `assets/equipment_element.json` | `5990006` | 武器属性注册 | `-1` |
| `assets/equipment_ids.json` | `5990001` | 合法装备 ID 注册，不发放装备 | `5990001` |
| `assets/equipment_ids.json` | `5990002` | 合法装备 ID 注册，不发放装备 | `5990002` |
| `assets/equipment_ids.json` | `5990003` | 合法装备 ID 注册，不发放装备 | `5990003` |
| `assets/equipment_ids.json` | `5990004` | 合法装备 ID 注册，不发放装备 | `5990004` |
| `assets/equipment_ids.json` | `5990005` | 合法装备 ID 注册，不发放装备 | `5990005` |
| `assets/equipment_ids.json` | `5990006` | 合法装备 ID 注册，不发放装备 | `5990006` |
| `assets/equipment_lookup.json` | `5990001` | 武器名称、稀有度与种类显示 | `{"name":"【测试服专用】GM·全能","rarity":"5","category":"剑"}` |
| `assets/equipment_lookup.json` | `5990002` | 武器名称、稀有度与种类显示 | `{"name":"【测试服专用】GM·充能","rarity":"5","category":"饰品"}` |
| `assets/equipment_lookup.json` | `5990003` | 武器名称、稀有度与种类显示 | `{"name":"【测试服专用】GM·槽上限","rarity":"5","category":"盾"}` |
| `assets/equipment_lookup.json` | `5990004` | 武器名称、稀有度与种类显示 | `{"name":"【测试服专用】GM·直击","rarity":"5","category":"拳"}` |
| `assets/equipment_lookup.json` | `5990005` | 武器名称、稀有度与种类显示 | `{"name":"【测试服专用】GM·连击","rarity":"5","category":"斧"}` |
| `assets/equipment_lookup.json` | `5990006` | 武器名称、稀有度与种类显示 | `{"name":"【测试服专用】GM·不屈连击","rarity":"5","category":"弓"}` |
| `assets/equipment_max_level.json` | `5990001` | 武器强化上限 | `5` |
| `assets/equipment_max_level.json` | `5990002` | 武器强化上限 | `5` |
| `assets/equipment_max_level.json` | `5990003` | 武器强化上限 | `5` |
| `assets/equipment_max_level.json` | `5990004` | 武器强化上限 | `5` |
| `assets/equipment_max_level.json` | `5990005` | 武器强化上限 | `5` |
| `assets/equipment_max_level.json` | `5990006` | 武器强化上限 | `5` |
| `assets/item_ids.json` | `5990001` | 合法魂珠 ID 注册，不发放物品 | `5990001` |
| `assets/item_ids.json` | `5990002` | 合法魂珠 ID 注册，不发放物品 | `5990002` |
| `assets/item_ids.json` | `5990003` | 合法魂珠 ID 注册，不发放物品 | `5990003` |
| `assets/item_ids.json` | `5990004` | 合法魂珠 ID 注册，不发放物品 | `5990004` |
| `assets/item_ids.json` | `5990005` | 合法魂珠 ID 注册，不发放物品 | `5990005` |
| `assets/item_ids.json` | `5990006` | 合法魂珠 ID 注册，不发放物品 | `5990006` |
| `assets/item_lookup_cnmod.json` | `5990001` | 已有魂珠名称显示 | `"【测试服专用】GM·全能魂珠"` |
| `assets/item_lookup_cnmod.json` | `5990002` | 已有魂珠名称显示 | `"【测试服专用】GM·充能魂珠"` |
| `assets/item_lookup_cnmod.json` | `5990003` | 已有魂珠名称显示 | `"【测试服专用】GM·槽上限魂珠"` |
| `assets/item_lookup_cnmod.json` | `5990004` | 已有魂珠名称显示 | `"【测试服专用】GM·直击魂珠"` |
| `assets/item_lookup_cnmod.json` | `5990005` | 已有魂珠名称显示 | `"【测试服专用】GM·连击魂珠"` |
| `assets/item_lookup_cnmod.json` | `5990006` | 已有魂珠名称显示 | `"【测试服专用】GM·不屈连击魂珠"` |
| `assets/item_sale.json` | `5990001` | 玩家出售已有魂珠所得玛纳，不是购买商品 | `{"category":5,"sale_price":500,"sellable":true}` |
| `assets/item_sale.json` | `5990002` | 玩家出售已有魂珠所得玛纳，不是购买商品 | `{"category":5,"sale_price":500,"sellable":true}` |
| `assets/item_sale.json` | `5990003` | 玩家出售已有魂珠所得玛纳，不是购买商品 | `{"category":5,"sale_price":500,"sellable":true}` |
| `assets/item_sale.json` | `5990004` | 玩家出售已有魂珠所得玛纳，不是购买商品 | `{"category":5,"sale_price":500,"sellable":true}` |
| `assets/item_sale.json` | `5990005` | 玩家出售已有魂珠所得玛纳，不是购买商品 | `{"category":5,"sale_price":500,"sellable":true}` |
| `assets/item_sale.json` | `5990006` | 玩家出售已有魂珠所得玛纳，不是购买商品 | `{"category":5,"sale_price":500,"sellable":true}` |

## 刻意不收的服务端获取途径行

我方服务端JSON终态没有直接引用GM ID的商品/掉落/奖励/任务/兑换/邮件礼包行；客户端商品和通用服务端目录另行审计。

本项服务端直接行计数为 0；这不代表客户端商品行也为 0。详见第三轮客户端排除明细和通用目录源码审计。

`equipment_dissolve` 消耗玩家已有武器生成其魂珠；`item_sale` 消耗玩家已有魂珠获得玛纳。两者不凭空发放 GM 武器。

## 恢复的训练副本

| 文件 | quest id | 名称 | 我方与交付值 |
|---|---|---|---|
| `assets/practice_quest.json` | `1103` | 仅直击木人·无 | `{"name":"仅直击木人·无","clearRewardId":1,"bRankTime":600000,"aRankTime":600000,"sRankTime":600000,"sPlusRankTime":600000,"rankPointReward":0,"characterExpReward":0,"manaReward":0,"poolExpReward":0,"scoreRewardGroup":0}` |
| `assets/practice_quest.json` | `1104` | 仅能力木人·无 | `{"name":"仅能力木人·无","clearRewardId":1,"bRankTime":600000,"aRankTime":600000,"sRankTime":600000,"sPlusRankTime":600000,"rankPointReward":0,"characterExpReward":0,"manaReward":0,"poolExpReward":0,"scoreRewardGroup":0}` |
| `assets/practice_quest.json` | `1105` | 仅技伤木人·无 | `{"name":"仅技伤木人·无","clearRewardId":1,"bRankTime":600000,"aRankTime":600000,"sRankTime":600000,"sPlusRankTime":600000,"rankPointReward":0,"characterExpReward":0,"manaReward":0,"poolExpReward":0,"scoreRewardGroup":0}` |
| `assets/practice_quest.json` | `1106` | 仅强化弹射木人·无 | `{"name":"仅强化弹射木人·无","clearRewardId":1,"bRankTime":600000,"aRankTime":600000,"sRankTime":600000,"sPlusRankTime":600000,"rankPointReward":0,"characterExpReward":0,"manaReward":0,"poolExpReward":0,"scoreRewardGroup":0}` |
| `assets/practice_quest.json` | `1107` | 仅直击木人们·无 | `{"name":"仅直击木人们·无","clearRewardId":1,"bRankTime":600000,"aRankTime":600000,"sRankTime":600000,"sPlusRankTime":600000,"rankPointReward":0,"characterExpReward":0,"manaReward":0,"poolExpReward":0,"scoreRewardGroup":0}` |
| `assets/practice_quest.json` | `1108` | 仅能力木人们·无 | `{"name":"仅能力木人们·无","clearRewardId":1,"bRankTime":600000,"aRankTime":600000,"sRankTime":600000,"sPlusRankTime":600000,"rankPointReward":0,"characterExpReward":0,"manaReward":0,"poolExpReward":0,"scoreRewardGroup":0}` |
| `assets/practice_quest.json` | `1109` | 仅技伤木人们·无 | `{"name":"仅技伤木人们·无","clearRewardId":1,"bRankTime":600000,"aRankTime":600000,"sRankTime":600000,"sPlusRankTime":600000,"rankPointReward":0,"characterExpReward":0,"manaReward":0,"poolExpReward":0,"scoreRewardGroup":0}` |
| `assets/practice_quest.json` | `1110` | 仅强化弹射木人们·无 | `{"name":"仅强化弹射木人们·无","clearRewardId":1,"bRankTime":600000,"aRankTime":600000,"sRankTime":600000,"sPlusRankTime":600000,"rankPointReward":0,"characterExpReward":0,"manaReward":0,"poolExpReward":0,"scoreRewardGroup":0}` |
| `assets/practice_quest.json` | `1111` | 全伤害木人·无 | `{"name":"全伤害木人·无","clearRewardId":1,"bRankTime":600000,"aRankTime":600000,"sRankTime":600000,"sPlusRankTime":600000,"rankPointReward":0,"characterExpReward":0,"manaReward":0,"poolExpReward":0,"scoreRewardGroup":0}` |
| `assets/practice_quest.json` | `1112` | 全伤害木人们·无 | `{"name":"全伤害木人们·无","clearRewardId":1,"bRankTime":600000,"aRankTime":600000,"sRankTime":600000,"sPlusRankTime":600000,"rankPointReward":0,"characterExpReward":0,"manaReward":0,"poolExpReward":0,"scoreRewardGroup":0}` |
| `assets/practice_quest.json` | `1113` | 能量瓶木人·无 | `{"name":"能量瓶木人·无","clearRewardId":1,"bRankTime":600000,"aRankTime":600000,"sRankTime":600000,"sPlusRankTime":600000,"rankPointReward":0,"characterExpReward":0,"manaReward":0,"poolExpReward":0,"scoreRewardGroup":0}` |
| `assets/practice_quest.json` | `1114` | 伤害圈木人·无 | `{"name":"伤害圈木人·无","clearRewardId":1,"bRankTime":600000,"aRankTime":600000,"sRankTime":600000,"sPlusRankTime":600000,"rankPointReward":0,"characterExpReward":0,"manaReward":0,"poolExpReward":0,"scoreRewardGroup":0}` |
| `assets/practice_quest.json` | `1115` | 能量瓶木人们·无 | `{"name":"能量瓶木人们·无","clearRewardId":1,"bRankTime":600000,"aRankTime":600000,"sRankTime":600000,"sPlusRankTime":600000,"rankPointReward":0,"characterExpReward":0,"manaReward":0,"poolExpReward":0,"scoreRewardGroup":0}` |
| `assets/practice_quest.json` | `1116` | 伤害圈木人们·无 | `{"name":"伤害圈木人们·无","clearRewardId":1,"bRankTime":600000,"aRankTime":600000,"sRankTime":600000,"sPlusRankTime":600000,"rankPointReward":0,"characterExpReward":0,"manaReward":0,"poolExpReward":0,"scoreRewardGroup":0}` |
| `assets/practice_quest.json` | `1117` | 超·结实假人(经典) | `{"name":"超·结实假人(经典)","clearRewardId":1,"bRankTime":600000,"aRankTime":600000,"sRankTime":600000,"sPlusRankTime":600000,"rankPointReward":0,"characterExpReward":0,"manaReward":0,"poolExpReward":0,"scoreRewardGroup":0}` |
| `assets/practice_quest.json` | `1118` | 超·极速假人 | `{"name":"超·极速假人","clearRewardId":1,"bRankTime":600000,"aRankTime":600000,"sRankTime":600000,"sPlusRankTime":600000,"rankPointReward":0,"characterExpReward":0,"manaReward":0,"poolExpReward":0,"scoreRewardGroup":0}` |
| `assets/practice_quest.json` | `1119` | 超·强力假人 | `{"name":"超·强力假人","clearRewardId":1,"bRankTime":600000,"aRankTime":600000,"sRankTime":600000,"sPlusRankTime":600000,"rankPointReward":0,"characterExpReward":0,"manaReward":0,"poolExpReward":0,"scoreRewardGroup":0}` |
| `assets/practice_quest.json` | `1120` | 超·诅咒假人 | `{"name":"超·诅咒假人","clearRewardId":1,"bRankTime":600000,"aRankTime":600000,"sRankTime":600000,"sPlusRankTime":600000,"rankPointReward":0,"characterExpReward":0,"manaReward":0,"poolExpReward":0,"scoreRewardGroup":0}` |
| `assets/practice_quest.json` | `1121` | 超·守护假人 | `{"name":"超·守护假人","clearRewardId":1,"bRankTime":600000,"aRankTime":600000,"sRankTime":600000,"sPlusRankTime":600000,"rankPointReward":0,"characterExpReward":0,"manaReward":0,"poolExpReward":0,"scoreRewardGroup":0}` |
| `assets/practice_quest.json` | `1122` | 超·痛苦假人 | `{"name":"超·痛苦假人","clearRewardId":1,"bRankTime":600000,"aRankTime":600000,"sRankTime":600000,"sPlusRankTime":600000,"rankPointReward":0,"characterExpReward":0,"manaReward":0,"poolExpReward":0,"scoreRewardGroup":0}` |
| `assets/practice_quest.json` | `1123` | 超·痛苦假人们 | `{"name":"超·痛苦假人们","clearRewardId":1,"bRankTime":600000,"aRankTime":600000,"sRankTime":600000,"sPlusRankTime":600000,"rankPointReward":0,"characterExpReward":0,"manaReward":0,"poolExpReward":0,"scoreRewardGroup":0}` |

## 验证边界

未核实：本审计为离线数据及源码静态证据，不运行服务端。
