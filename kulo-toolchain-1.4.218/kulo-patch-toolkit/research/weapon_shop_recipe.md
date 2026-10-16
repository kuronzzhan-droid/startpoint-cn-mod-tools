# Boss 专属材料 → 武器商店 → Lv120 强化：配方（只读调研，2026-10-07）

证据来源：客户端表 = store131（`scratchpad/store131/production/upload`，含诅咒/PARADOX/羁绊）；本机未提交的 1.4.132–1.4.143 主线 boss 补丁 = `D:\WF\startpoint-cn-kulo\assets\asset-patch\active\*mainboss*.zip`；服务端 = `D:\WF\startpoint-cn-kulo`（工作区里 `assets/hard_multi_event_quest.json`、`boss_battle_quest_cnmod.json`、`asset-patch/manifest.json` 有本机未提交改动）；列含义 = `弹国服\scripts\pinball\master\generated\*Values.as`。我没有改任何文件。

## 结论先行

- **Lv120 强化只要改数据。** 客户端只从强化主表 c0 读上限，服务端只从强化商店 JSON 最后一阶读上限，两边都没写死 120。`src/` 不用改，SWF 也不用打补丁。受限目录（`src/multi/tcp|coordinator|room|state`、`src/workers`、persistence-coordinator、sqlite-*）都不碰，所以不需要 owner 点头。
- **共同决战页「交易所」打开的是通用兑换所（GeneralShop），不是本 boss 的商店。** `HardMultiEventQuestSelectScene.as:348`：按钮 3 = `SceneKind.GeneralShop`。活动道具兑换按钮对 HardMultiEvent 一律隐藏，因为 `EventItemShopKindTools.fromEventIdKindOptional` 遇到 EventIdKind 序号 13 返回 None，`EventExchangeItemTools.isExistExchangeableEventItem` 随之为 false。
  - 所以每个 boss 一个的武器店只能做成**领主币商店分类**：从领主战页右上「兑换道具」进，由 stage_node c6 决定是哪个分类。官方机兵的常驻版就是这么做的。
  - 要从共同决战页直达本 boss 的商店，得打客户端补丁。
- 现状要先知道：27 个 boss 的领主战和共同决战已经以本机 local 补丁存在（1.4.142/143，manifest 注明「仅本机开发服启用，不提交」）。
  - 9 个主线 boss 的 stage_node 80–88，c6 都借用不死王的分类 3，掉落展示也借不死王的币 40020–40022。
  - 服务端 `boss_battle_quest_cnmod.json` 里 1080001–1088005 掉落组借的是菲诺梅那的 11000944–948，实际掉的是机兵币。
  - 27 个共同决战（2080–2088、2035/2037–2041、2025–2030、2051–2056）服务端 scoreRewardGroupId 全是 7000015（暗机兵决战），客户端 c71 全是 11000935，两边对不上。
  - 另外 18 个官方 boss（女王 6、荒龙 6、精灵兽 6）本来就有专属银/金/紫币和专属领主币分类（见 §1.6）。

---

## 1. 官方机兵武器全链路（常驻版，2025-07-10 起）

### 1.1 武器与强化类目
| 武器 | id | 来源 boss | 强化后名（Lv70 换名换图） |
|---|---|---|---|
| 朱安里克 剑 | 5010073 | 红 | 朱安里克·改 |
| 哈尔波曼 斧 | 5020042 | 碧 | 哈尔波曼·改 |
| 亚弗登特 拳 | 5070044 | 暗 | 亚弗登特·改 |
| 凯斯莫里 盾 | 5080032 | 橙 | 凯斯莫里·改 |
| 阿罗朗德涅莫 饰 | 5090047 | 苍 | 阿罗朗德涅莫·改 |
| 哈里萨尔瓦 铳 | 5100020 | 闪 | 哈里萨尔瓦·改 |

强化类目 3：`equipment_enhancement_shop_category['3']` = `steam_robot_weapon,3,(None),机兵装备强化,dynamic/equipment_enhancement/steam_robot_weapon_banner,dynamic/equipment_enhancement/steam_robot_weapon_header,equipment_enhancement_steam_robot_weapon_how_to_play,Equipment_Enhancement_Steam_Robot_Weapon,2024-08-16 12:00:00,(None)`

### 1.2 客户端表（以 5020042 为例）
- `master/item/equipment.orderedmap['5020042']` = `axe_0042_raid,哈尔波曼,0,,,,item/equipment/general/axe_0042_raid_lv0,<说明>,5,true,5020042,5,500,true,1,1`
  - 列义（EquipmentValues）：c0 string_id；c1 名；c2 0=Equipment；c6 像素图；c7 说明；c8 max_level（觉醒上限 5）；c9 generate_ability_soul；c10 ability_soul_id；c11 稀有度；c12 售价；c13 可售；c14 抽卡权重；c15 obtain_source。
- `master/item/item.orderedmap['5020042']`：同 id 的「魂珠」道具行，形如 `axe_0042_raid,5020042,哈尔波曼魂珠,item/generated/ability_soul/...,(None),アビリティソウル,11,…`。
- `master/ability/ability_soul.orderedmap['5020042']`：本体词条，多行。
- `master/item/equipment_status.orderedmap['5020042']`：嵌套表 `{'1':'330,148','5':'495,221'}`，按觉醒等级给 HP,ATK。
- `master/equipment_enhancement/equipment_enhancement.orderedmap['5020042']` = `120,1,哈尔波曼·改,70,item/equipment/general/axe_0042_raid_lv70,1,<说明>,99,2024-10-11 12:00:00`
  - 列义：c0 **max_enhancement_level=120**；c1/c2 名字从第几级切换、切成什么；c3/c4 图标从第几级切换（70）、切成哪张；c5/c6 说明从第几级切换、切成什么；c7 pixelart_effect_level（从这一级起显示强化框，官方 99）；c8 开始时间。
- `master/equipment_enhancement/equipment_enhancement_status.orderedmap['5020042']`：嵌套表 `{'98':'0,0','99':'50,10','120':'50,10'}`，是强化附加的 HP,ATK。**最后一个键必须等于上限**，否则高于最后一个键的等级会空引用崩溃（见 PARADOX lv200 调研：`EquipmentEnhancementStatusLogic.as:117-120`）。
- `master/equipment_enhancement/equipment_enhancement_ability.orderedmap['5020042']`：强化词条，多行，布局 = ability_soul 往后挪 3 列。c0 slot，c1 learn_level，c2 max_power_level，c3–c4 战力。官方例子：
  - `0,1,99,…34…20000,40000`：1→99 级成长。
  - `3,100,120,…723,5,Red,,500,5000`：100→120 级，独立乘区从 0.5% 涨到 5%。
- `master/equipment_enhancement/equipment_enhancement_shop.orderedmap`：6 阶，键 2001–2004、2025、2026。例：`2002` = `3,(None),21,2,1,100,,,,,,(None),,(None),40401,10,40407,1,14040,10,(None),,2024-10-11 12:00:00,(None),90,,,,,5020042,70,5,…`（50 列）
  - 列义（EquipmentEnhancementShopValues）：c0 类目；c2 group；c3 阶；c4=1 Enhancement；c5 list_order；c11/c12 价格种类/数量（0 星导石、1 玛那、2 羁绊证）；c13 cost_item_schedule；c14–c21 四组材料 (id, 数量)；c22/c23 起止时间；c24 release_rank；**c29 equipment_id；c30 本阶上限；c31 需要的觉醒等级**。

### 1.3 「120 级」在数据里是什么
六阶的本阶上限 c30 依次是 **69 / 70 / 98 / 99 / 119 / 120**（119/120 两阶是 2025-06-19 加的）。69、98、119 三阶按级付料；70、99、120 是突破节点，单级、材料贵。效果在这几级生效：
- Lv70：换名、换图（ENH c1/c3）。
- Lv99：出强化框（ENH c7）。
- Lv100–120：词条按 learn/max 线性涨（EA 表）。

服务端 `assets/equipment_enhancement_shop.json`，同一套 6 阶，例：
```json
"2006": {"costs":[{"id":40402,"amount":10},{"id":40408,"amount":1},{"id":14040,"amount":10}],
 "rewards":[],"availableFrom":"2024-08-16 12:00:00","availableUntil":null,"stock":-1,
 "shopCategoryId":3,"groupId":…,"stage":2,"equipmentId":5010073,"enhancementMaxLevel":70,
 "requireAwakeningLevel":5,"enhancementPurchaseMode":"stage_benefit"}
```
5010073 六阶材料：40402×1/级 → 40402×10 + 40408×1 + 14040×10 → 40402×1/级 → 40402×10 + 14034×30 + 14042×1 → 10000095×1/级 → 10000095 + 10000096。

服务端逻辑：
- 列表：`src/routes/api/shop.ts:96 buildEnhancementSalesList`，每个 group 的上限取最后一阶的 enhancementMaxLevel。
- 购买：`shop.ts:404-487` 走 `src/lib/equipment-enhancement.ts`。
  - `findCurrentEquipmentEnhancementStage` 按 类目+组+武器 找当前阶。
  - `planEquipmentEnhancementPurchase` 检查觉醒等级是否 ≥ requireAwakeningLevel。
  - `resolveEquipmentEnhancementPurchaseMode`：**只有类目 1–4 且显式写了 stage_benefit 才「买 1 份升满本阶」；其余（类目 ≥5、自制）都是 per_level，买 N 份升 N 级，材料 ×N。**
- 写回 `players_equipment.enhancement_level`。

### 1.4 掉落
- **机兵降临讨伐 = 领主战**（`boss_battle_quest`，stage_node 60–66，quest 1060001–1066004/5）。
  - 客户端 `boss_battle_stage_node['1']['61']` = `降临讨伐,红嫉机兵,2,<bgm>,(None),,61,10000091,10000092,10000093,(None),<thumb>,<bg>,1000`
  - 列义：c6 = 领主币商店分类 id；c7–c10 = 掉落展示道具。
  - 客户端 `boss_battle_quest['1']['61']['4']`：c69 体力；**c70 score 组 11000550**；c71 SS 奖励。
  - 服务端 `assets/boss_battle_quest.json["1061004"].scoreRewardGroupId = 11000550`。`score_reward.json["11000550"]`：
    - 普通行：10000091 ×16/×15、10000092 ×5/×4、10000093 ×1。
    - 稀有池：11000921（1.0）、11000922（0.06）、11000925（0.02）、11000916（0.01，武器 5010073 本体）。
- **机兵共同决战 = hard_multi_event**（1001–1006 常驻）。
  - 客户端 `hard_multi_event['1001']` = `hard_multi_steam_robot_fire_constant,…,共同决战【红嫉机兵】,…`；c16–c19 是掉落展示（49300 共同决战功劳勋章）。
  - `hard_multi_event_quest['1001']['1']`：c12–c15 = 可见前置 BossBattle(1,61,4)；c70 体力 35；**c71 score 组 11000930**（49300、10000092、10000093、稀有 11001105）。
  - **服务端 mod 改过**：`assets/hard_multi_event_quest.json["1001001"].scoreRewardGroupId = 7000010`，客户端组名 `mech_decisive_7000010_*`。掉齿轮 40402 ×1，另 10% 进稀有组 700010 → 40408 蒸气核。颜色是克制属性：红 boss 掉苍齿轮，碧 boss 掉红齿轮。
- 结算代码：
  - 单人：`src/lib/quest/finish/single-finish-transaction.ts:285`。
  - 多人：`src/multi/http/battle.ts:718`。
  - 两条都走 `src/lib/quest.ts givePlayerScoreRewardsSync`。

### 1.5 武器与强化材料从哪来
- **武器本体**：领主币商店分类 61–66（= stage_node c6）。服务端 `boss_coin_shop.json["64"]["10028168"]` = `{"costs":[{"id":10000093,"amount":5}],"rewards":[{"type":4,"id":5020042,"count":1}],"availableFrom":"2025-07-10 12:00:00","availableUntil":null,"stock":5}`；`boss_coin_shop_item_category_map.json["10028168"]=64`。
  - 客户端 `boss_coin_shop['10028168']` = `64,(None),true,(None),,(None),哈尔波曼,10028168,1,30,<说明>,(None),item/equipment/general/axe_0042_raid_lv0,5,(None),,(None),10000093,5,(None),,(None),,(None),,2025-07-10 12:00:00,(None),1,5,(None),(None),5,4,5020042,1,…`
  - 限购 5 = 1 把本体 + 4 把觉醒。觉醒要 5 级，因为 requireAwakeningLevel = 5。
- **Lv119/120 材料**：机兵共通分类 60。10000093 ×2 换 10000095 全能齿轮（限 126 个）；10000093 ×40 换 10000096 融珠蒸气核（限 5 个）。另有菲诺梅那地狱级 11000948 的 mod 追加掉落。
- **14040 星空记忆晶**：分类 61–66 用 10000093 ×15 兑换；通用兑换所用 49100 兑换。
- **49300 勋章 → 交易所**：通用兑换所 `general_shop.json` 400002 等，换 14001–14015 记忆石/晶。

### 1.6 其余 18 个官方 boss 已有的币和分类（可直接复用）
| stage_node | boss | 分类 | 银/金/紫币 |
|---|---|---|---|
| 25–30 | 荒龙 ×6 | 23/24/25/27/28/29 | 40266–40289 |
| 35、37–41 | 女王 ×6 | 34–39 | 40257–59、40293–95、40305–07、10000010–12、10000043–45、10000081–83 |
| 51–56 | 精灵兽 ×6 | 51–56 | 10000112–10000129 |

主线 9 个 boss（80–88）没有自己的币和分类，目前借用分类 3 + 40020–40022。

---

## 2. mod 以前怎么加新武器（诅咒 59101xx / PARADOX 5920001 / 深渊 80001xx / 羁绊强化 / 幻想 1000xx）

生成器源码：
- `D:\WF\_archive\startpoint-cn-old\repo\mod-tools\wf_cursed_weapons.py`，`build()` 在 2577–2700 行，`_server_delta()` 在 2713 行。
- `wf_paradox_weapon.py`、`wf_bond_weapon_enhance.py` 同目录。
- kulo 里的工具：`tools/fantasy-gauntlet-mod-tools/build_fantasy_weapon_candidates.py`（765–835 行写服务端元数据）、`wf_equipment_enhancement_shop.py`。

### 2.1 客户端表（一把武器）
| 表 | 键 | 写法（诅咒的真实行） |
|---|---|---|
| `master/item/equipment.orderedmap` | 武器 id | `mod_cursed_gluttony_knife,饕餮餐刀,0,,,,item/equipment/mod/cursed/gluttony_knife_lv0,<说明≤57字>,5,false,5910101,5,500,true,1,1`（模板取 8000101） |
| `master/item/item.orderedmap` | **同一个 id** | `mod_cursed_5910101,5910101,饕餮餐刀魂珠,item/equipment/mod/cursed/gluttony_knife_lv0,(None),アビリティソウル,11,,,,,,0,,5,(None),500,5,9999,2021-09-15 12:00:00,(None),true,`（注释写明：缺这一行，ItemLogic 取不到就崩） |
| `master/ability/ability_soul.orderedmap` | 武器 id | 本体词条（多行） |
| `master/item/equipment_status.orderedmap`（嵌套） | 武器 id | `{'1':'330,148','5':'495,221'}` |
| `master/equipment_enhancement/equipment_enhancement.orderedmap` | 武器 id | `120,120,饕餮餐刀·解咒,120,item/equipment/mod/cursed/gluttony_knife_lv120,120,<≤54字>,120,2000-01-01 00:00:00`（模板取 5900101）；羁绊：`120,1,杜兰德尔·改,70,item/equipment/mod/bond/sword_0005_lv120,1,…,99,2000-01-01 00:00:00` |
| `…/equipment_enhancement_status.orderedmap`（嵌套） | 武器 id | `{'98':'0,0','99':'50,10','120':'50,10'}` |
| `…/equipment_enhancement_ability.orderedmap` | 武器 id | 成长行（learn 1 / max 119）＋ 补足行（learn = max = 120） |
| `…/equipment_enhancement_shop.orderedmap` | `<武器id><两位阶号>` | `591010101` = `6,(None),5910101,1,1,100,,,,,,(None),,(None),10000145,1,(None),,(None),,(None),,2000-01-01 00:00:00,(None),90,,,,,5910101,69,5,…`（50 列，模板取 5900110x） |
| `…/equipment_enhancement_shop_category.orderedmap` | 新类目号 | `6` = `cursed_weapon,-2,(None),诅咒武器·觉醒,dynamic/equipment_enhancement/cursed_weapon_banner,dynamic/equipment_enhancement/cursed_weapon_header,equipment_enhancement_epuration_weapon_how_to_play,equipment_enhancement_epuration_weapon,2000-01-01 00:00:00,(None)` |
| （按需）`master/character/unique_condition`、`master/string/custom_ability_string`、DSL `battle/action/skill/action/ability_skill/<dir>$<name>` | | 词条用到 629/固有状态时才要 |

- 已用的强化类目：5 深渊（c1=-1）、6 诅咒（-2）、7 羁绊（0）。c1 display_order 全表必须是互不相同的整数。
- 类目行的 c6/c7（how_to_play / help id）**只能用官方已有的值**，自己编一个 = C8601。
- `wf_bond_weapon_enhance.py:79` 的注释：ENH、EA、ENH_STATUS、ENH_SHOP、ENH_CATEGORY 必须在同一条边里发。缺 STATUS = C8013；缺 EA = 空引用。

### 2.2 资源文件
- **武器图标**：独立 PNG，20×20 RGBA，不进图集。
  - 本体：`item/equipment/mod/<包>/<名>.png`；Lv120 图：`…_lv120.png`。store131 实测：5910101、5920001、8000101 都是独立 PNG；官方武器图标在 `item/sprite_sheet` 图集里。
  - 风格：官方长物件尖端朝左上、柄朝右下，5★ 带闪星。
- **类目横幅**：`dynamic/equipment_enhancement/<x>_banner.png` 1000×184；`…_header.png` 1440×556。
- **领主币分类横幅**：1000×184，例 `quest/boss_battle/banner/mod_five_boss_exchange`。
- **PNG 编码**：所有自制 PNG 必须用 CDN 的小写签名 `\x89png`，用 `wf_assets.png_encode` / `wf_battle_atlas_repack.encode_png` 生成。
  - 否则 **C8105**：1.4.101 修过商店横幅；mainboss 1.4.138 自制横幅出过这个错，1.4.139 退回，1.4.140 换签名后好了。
- 未经真机验证：羁绊生成器提示，独立 PNG 的 `_lv120` 图在编成格可能需要客户端补丁 `equipment-enhanced-party-frame-v1`（b 版，修 setItemImage），否则重启前可能不显示。诅咒、深渊、PARADOX 前提相同。kulo 的 `client-patch/` 里没找到这个补丁目录。

### 2.3 服务端 JSON（`assets/`）
| 文件 | 写法 | 用途 |
|---|---|---|
| `equipment_ids.json` | 追加 id | 后台；五重掉落白名单 |
| `equipment_lookup.json` | `"5910101":{"name":"饕餮餐刀","rarity":"5","category":"剑"}` | 后台显示 |
| `equipment_max_level.json` | `"5910101":5` | `getEquipmentMaxLevel`，缺省为 1 |
| `equipment_element.json` | `"5910101":-1`（0 基属性，-1 = 无） | |
| `item_ids.json` | 追加 id（魂珠道具） | 后台、邮件校验 |
| `item_sale.json` | `"5910101":{"category":5,"sale_price":500,"sellable":true}` | |
| `equipment_dissolve.json` | `{"ability_soul_id":<id>,"obtain_source":1,"generate_ability_soul":true,"max_level":5}` | 诅咒和深渊没写，所以觉醒不给魂珠；官方机兵写了。觉醒上限也读这里，缺省为 5 |
| `equipment_enhancement_shop.json` | 每阶一个键，键与客户端相同，必须带 shopCategoryId、groupId、stage、equipmentId、enhancementMaxLevel、requireAwakeningLevel；建议显式写 `"enhancementPurchaseMode":"per_level"` | |
| `equipment_awakening_material.json` | 只有「用道具代替本体觉醒」时才写 materialByEquipment；id 不以 5 开头的 ★5 装备要写 rarityOverrides | |

- 稀有度直接取 `Math.floor(id/1e6)`（`src/lib/equipment-dissolve.ts`、`routes/api/equipment.ts:128`），影响觉醒和分解的工匠点。**新 ★5 武器 id 用 59xxxxx 段就不用写 override。** 已占用：5900101、5900911–16、5910101–29、5920001。
- **生效方式**：JSON 都是启动时 `require` 的，**改完必须重启服务端**。不用重新 tsc，因为 out/ 运行时直接读 `../../assets`。kulo 的 `POST /api/mod-admin/reload_assets` 只重载 rogue_event（`src/routes/api/modAdmin.ts`），记忆里「强化商店可热加载」那条不适用于 kulo。

### 2.4 已知崩溃坑
| 码 | 原因 |
|---|---|
| C7050 | 词条行某个 kind 列非零，而它的伴随列留了空串（堆栈 parseAtN = 出事的列）。诅咒/PARADOX 生成器用 `wf_client_legality.client_legality_problems` 拦。触发 kind 18/19/20/21/23/25/107/137/141/144/197/261 必须带 puller（c25）；装备表写 423 也是 C7050，要客户端补丁能力 `equipment-gauge-gain-rules-v1` |
| C2324 | 同一 slot 内，成长行后面还有更高 learn 的行 |
| C8013 | 缺强化 status |
| C2287 | 强化等级超过客户端上限 |
| C10013 | 装备 DSL 用了有属性的命中特效（Fine/Coarse/Slash/CriticalSlash） |
| C8601 | 商店、类目缺客户端行，或 how_to_play id 是自编的 |
| C8004 | 道具 c4 小图标不在图集里 |
| C8105 | PNG 签名不对 |

其他：
- puller 4/5/6/7/9 的角色组列写成空串，说明里会显示「null角色」，要写 `(None)`。
- 字数上限：装备说明 c7 ≤57、强化说明 c6 ≤54、领主币商店说明 c10 ≤60；生成器禁止半角逗号和换行。
- 时间：自制内容一律写 2000-01-01（服务端时钟被钉住）。

---

## 3. 新道具（boss 材料或币）＋掉落

### 3.1 客户端 `master/item/item.orderedmap`（23 列，ItemValues）
仿官方币写：`boss_coin_lich_1,40020,不死王瑞西塔尔的银币,item/materials/boss_coin/lich_1,item_icon/materials/boss_coin/boss_coin_1,<说明>,15,,,,,,,,6,2,3,3,9999,2015-12-31 23:59:59,(None),true,`
- c0 string_id；c1 显示顺序；c2 名；c3 缩略图（独立 PNG 20×20 可以，异步加载）。
- **c4 小图标必须是图集子纹理**：`item_icon/sprite_sheet`（40×40 帧）、`item/sprite_sheet`、`item_sec`、`scene/general` 之一。写成独立 PNG 路径，掉落展示、商店页、stage_node c7–c10 都会 C8004；写 (None) 则 C4208。
  - 官方币可以直接借 `item_icon/materials/boss_coin/boss_coin_1/2/3`（41×41）。
  - 自制图标要往 `item_icon/sprite_sheet` 追加帧，参考 `item_icon/materials/mod/five_boss/deep_crystal_v2`（40×40，sheet 970×343）。规矩：只向下扩画布，已有帧不动；先发图集，再发 c4。
- c5 说明（带 `\n` 要用引号）。
- c6 效果种类：15 = TradeItem（币、勋章）；1 = EquipmentEnhancement（强化材料，c12 填属性）；14 = Etc。
- c14 分类：币填 6，强化材料填 9。
- c15 ItemGroup：0 紫币 / 1 金币 / 2 银币；不用填 (None)。
- c16 售价；c17 稀有度；c18 持有上限；c19/c20 起止时间；c21 可售。
- 如果材料要在觉醒弹窗里显示（用道具代替本体觉醒），c3 还必须在 `item/sprite_sheet` 图集里，`DialogVariationTitleView` 是同步取图的。先例：1.4.129 把禁忌星铁补进图集，生成器 `repair_cursed_weapon_awaken_icon_preload_1_4_128.py`。
- 可选：`master/search/item_quest_search.orderedmap[<道具id>]`（获取途径）。行例：`2,1,61,4,1061004,3.43`（BossBattle）、`18,1001,,1,1001001,3.54`（HardMulti）。
- 服务端：`item_ids.json` 追加 id；`item_lookup.json` 或 `item_lookup_cnmod.json` 写 `"id":"名"`（只用于后台）。发道具没有白名单，也没有上限检查（`givePlayerItemSync`）。

### 3.2 掉落：服务端与客户端必须按位对齐
- 领主战：服务端 `boss_battle_quest.json` / `boss_battle_quest_cnmod.json`（cnmod 覆盖 base，`src/lib/boss/boss-tables.ts`）`["<quest>"].scoreRewardGroupId`。
- 共同决战：服务端 `hard_multi_event_quest.json["<quest>"].scoreRewardGroupId`。
- `score_reward.json`（或 `score_reward_cnmod.json`）组形状：
```json
"7000015":[{"position":1,"name":"","type":0,"reward_type":0,"count":1,"field5":0,"id":40405},
           {"position":2,"name":"","type":1,"id":700015,"rarity":0.1}]
```
  - type 0 普通行：reward_type 0 道具 / 4 玛那 / 5 经验 / 6 元素 / 7 以太；可加 `"ignore_drop_multiplier":true`。
  - type 1 稀有池：`rarity` = 进池概率。
- `rare_score_reward.json`（或 `_cnmod`）：`"700015":[{"name":"","type":0,"rarity":1.0,"id":40411,"count":1}]`。type：0 道具 / 1 装备 / 2 角色 / 3 星导石 / 4 玛那 / 5 经验。
- `clear_reward.json`：`"31":{"name":"","type":0,"id":11003,"count":1}`（首通）。
- **服务端语义**（`src/lib/quest.ts:42-230`）：
  - 普通行每次通关**全部发放**，field5 权重被忽略。数量 = count × `DROP_MULTIPLIER` 环境变量 ×（用加成点 ×2）。
  - 稀有行先按 `rarity` 掷一次，命中后在池内**均匀**挑一条，池内每条的 rarity 被忽略（代码里有 TODO）。
  - 返回给客户端 `drop_score_reward_ids:{group_id,index=position,number}` 和 `drop_rare_reward_ids:{group_id=稀有池id,index=池内序号+1}`。
- **客户端按 `ScoreRewardTable[group_id][index]`、`RareScoreRewardTable[group][index]` 直接取值**（`CommonScoreRewardLogic.as:32`、`RareScoreRewardLogic.as:32`）。所以 `master/reward/score_reward.orderedmap`、`rare_score_reward.orderedmap` 必须有同组号、同序号的行，缺了就是空引用。
  - 客户端 score 行：`mech_decisive_7000015_normal,0,0,40405,1,0,,`（c1 0 = 普通；c2 种类；c3 id；c4 数量；c5 权重）、`…_rare,1,,,,,700015,0.1`（c6 池 id；c7 概率）。
  - 客户端 rare 行：`mech_decisive_700015,0,40411,1,1,false`（c1 种类；c2 id；c3 数量；c4 概率；c5 是否稀有特效）。
- 关卡预览（选关页的「可能掉落」）：领主战 `boss_battle_quest` c70、共同决战 `hard_multi_event_quest` c71 填同一个组号。
  - 展示条：领主战 `boss_battle_stage_node` c7–c10、共同决战 `hard_multi_event` c16–c19。这些位置的道具 c4 必须在图集里。
- 只有八岐大蛇的「每通关固定 1/3 枚」写在代码里（`src/lib/boss/reward-profile.ts`）。新 boss 用 JSON 计数就够，不需要它。

---

## 4. 领主币分类和商品（要同步的四处）

1. 客户端 `master/shop/boss_coin_shop_category.orderedmap[<分类id>]`（13 列）。例 `99` = `mod_five_boss,2999,(None),2,1,99,1,1099001,(None),quest/boss_battle/banner/mod_five_boss_exchange,quest/boss_battle/background/mod_five_boss,,false`
   - c0 string_id；c1 display_order；c2 属性。
   - c3=2 表示可见前置是 BossBattle，c4–c6 = (1, stage, 1)，c7 = 前置 quest id。
   - c8 兑换截止时间；c9 横幅（1000×184 独立 PNG）；c10 背景图；c11 pickup 活动 id；c12 bool。
2. 客户端 `master/quest/boss_battle_stage_node.orderedmap['1'][<stage>]` 的 **c6 = 分类 id**（领主战页「兑换道具」按钮会无条件显示；分类缺行就 C8601）。9 个主线 boss 现在都是 3，要改成各自的新分类。
3. 客户端 `master/shop/boss_coin_shop.orderedmap[<商品id>]`（50 列，BossCoinShopValues）。例：`10028168`，见 §1.5。
   - c0 分类；c2 can_easy_buy；c6 名；c7 group；c8 stage；**c9 list_order（降序排；想排在后面写 0）**；c10 说明；c12 缩略图（装备填装备图标路径）；c13 稀有度。
   - c17–c24 四组 (成本 id, 数)；c25/c26 起止时间；c27 release_rank；c28 buy_max_count；c29 max_frequency；c30 daily_stock；c31 monthly_stock。
   - **c32 种类（0 道具 / 3 角色 / 4 装备 / 5 强化）；c33 id；c34 数量**；c35–c49 是 kind2–6。
   - 缺这一行，打开商店就 C8601。
4. 服务端 `assets/boss_coin_shop.json["<分类>"]["<商品>"]` = `{"costs":[{"id":…,"amount":…}],"rewards":[{"type":4,"id":<武器>,"count":1}],"availableFrom":"2000-01-01 00:00:00","availableUntil":null,"stock":5}`。
   - rewards.type 是 ShopItemRewardType：0 道具 / 1 经验 / 2 玛那 / 3 角色 / 4 装备 / 5 称号。
   - **再加** `assets/boss_coin_shop_item_category_map.json["<商品>"]=<分类>`。缺了 `getShopItemSync(BOSS_COIN)` 返回 null，商品能看到但买不了（`src/lib/assets.ts:808`）。
   - 获取途径是自动建索引的（`src/lib/how-to-get-sources.ts`）。

其他商店备查：
- **活动道具店**：客户端 `master/shop/event_item_shop`。c0 种类（0 Advent / 1 Story / 2 WorldStory / 3 ChallengeDungeon / 4 CollectItem / 5 Carnival / 6 Rush / 7 ScoreAttack），c1 活动 id，其余列同上，c32 种类。服务端 `event_item_shop.json[eventType][eventId][商品]` + `event_item_shop_id_map.json[商品]={eventType,eventId}`。**HardMultiEvent 用不了**（前面说过的转换失败；强行调用会抛 C3193）。
- **通用兑换所**（共同决战页的「交易所」）：客户端 `master/shop/general_shop`（例 `100001`：c9=2 羁绊证、c10=50、c29=4 装备、c30=5010005）。服务端 `general_shop.json` **加** `cdn_general_shop_whitelist.json`，不在白名单的商品会被 `shop.ts:818` 过滤掉。这是全局共用的店，不分 boss。

---

## 5. Lv120 要不要改代码

- **服务端**：不用改。
  - `shop.ts`、`equipment-enhancement.ts` 都按 JSON 的阶段上限和类目工作。类目 ≥5 自动按级付料，也就没有「买 1 份升满本阶」的问题。
  - 觉醒上限读 `equipment_dissolve.max_level`，缺省 5。
  - 联机快照（`src/multi/party-snapshot.ts`）会原样带上 enhancementLevel。
  - 可选的代码点：
    - Lv120 称号奖励写死在 `src/lib/equipment-degree-rewards.ts` 的 `EQUIPMENT_DEGREE_CATALOG`。
    - 固定币数写死在 `reward-profile.ts`。
    - 两处都在非受限目录。
- **客户端**：不用打补丁。上限 = 强化主表 c0；强化框 = c7；词条 learn/max 没有上限（见 `D:\WF\out\PARADOX-20260928\lv200-frame\设计.md` 第二节的取证）。
- **以下几种情况才需要客户端补丁**：
  - 共同决战页直达本 boss 的商店。
  - 用道具代替本体觉醒，对应 equipment-rules，需要补丁 APK。
  - 自定义强化框。
  - 独立 PNG 的 lv120 图在编成格显示（未验证）。
  - 装备词条用 423。

## 6. 建议的施工清单（每个 boss）
- **新币**：仿 10000091–93 做银/金/紫三档，或只做一档。
  - id 建议从 10000400 起，目前已占用到 10000311、10020066。
  - c4 走 `item_icon` 图集（追加 40×40 帧）；c3 用 20×20 独立 PNG。
- **领主战**：
  - stage_node c6 指向新分类，c7–c10 填新币。
  - `boss_battle_quest_cnmod.json` 换成新的 score 组。
  - 客户端 bbq c70 填同一组号，再补客户端 score/rare 表。
- **共同决战**：
  - 服务端 `hard_multi_event_quest.json` 的 scoreRewardGroupId 换成新组（掉强化材料）。
  - 客户端 hmq c71 填同一组号；hme c16–c19 改掉落展示。
  - 补客户端 score/rare 表。
- **商店**：
  - 每个 boss 一个领主币分类（18 个官方 boss 可以直接往已有的 23–29/34–39/51–56 里加商品；9 个主线 boss 要新建分类 + 横幅）。
  - 每个 boss 2 个武器商品（stock 5）。
  - 上面 §4 的四处同步。
- **武器**：
  - id 走 59xxxxx 段。
  - 写 §2.1 的全部客户端表和 §2.3 的全部服务端 JSON；新强化类目号建议 8，c1 选一个未用的整数。
  - 6 阶 69/70/98/99/119/120，材料用共同决战掉的东西。
- **发布**：
  - 客户端：kulo 走 `assets/asset-patch/active/pinball-<from>-<to>-N-<名>.zip`（成员 `production/upload/<sha1路径>`）+ `manifest.json` 条目。注意 manifest 尾部 1.4.132–1.4.143 是本机未提交的版本。
  - 服务端：改完 JSON 重启。

### 没核实的
- 羁绊生成器提到的「独立 PNG lv120 图在编成格消失」只是代码层结论。
- 客户端 score_reward 缺行时具体报哪个错码没验证，只看到是直接取值。
- 2080–2088 等 local 补丁的真机状态，只看了 manifest 的说明。
- `boss_coin_shop` c31 monthly_stock 在官方机兵行里是 5，含义没验证。
