# 数据表速查(手写)

每条:**改什么 → 谁读(客户端界面/类 · 服务端文件)→ 必须同改的伴随表 → 坑**。
客户端读取类的全量列表看 [gen-client-master-tables.md](gen-client-master-tables.md);服务端读哪些 JSON 看 [gen-server-json.md](gen-server-json.md)。
列号 cN = orderedmap 行内第 N 列(0 起),客户端解析在 `pinball/master/generated/<Camel>Values.as` 的 `parseAtN`。

## 错误码一行速查(每行独立可 rg)

- 错误码=C8601 | 场景=新增即时道具/商店商品 | 原因=executable_instant_item 键缺 executable_instant_item_level 行,或商店商品行缺 | 检查=bughunt-20261014/out/c8601_fix_verify.py
- 错误码=U_3be147 | 场景=改 quest battle_enemy_level 或新敌人 | 原因=GeneralEnemySourceHelper.getSurjectivity 找不到 key≥lv 的等级行 | 检查=bughunt-20261014/builder/level_gap_check.py
- 错误码=C7050 | 场景=能力前置/角色元素 | 原因=kind 8/9/87/187/188/200/205 前置列留空,或可玩角色 element=6,或队长表写了只属能力表的 kind | 检查=无脚本,按本页「角色本体」
- 错误码=C8016 | 场景=深渊连战色替/boss 改属性 | 原因=召唤物时间轴未预载 | 检查=给召唤物加预载垫片
- 错误码=C8251 | 场景=多波关卡 | 原因=zone c7/c8 没填 | 检查=无
- 错误码=C8004 | 场景=新小图标/券图标 | 原因=取图不在已加载图集(独立新路径) | 检查=无
- 错误码=C16102 | 场景=CreateCondition | 原因=c10 付与对象种类错配(Member 写 3,球写 2) | 检查=无
- 错误码=2265 | 场景=语音 speech 表 | 原因=constraint 可见数为 0 | 检查=无
- 错误码=U_1d93f4 | 场景=三人五重房 | 原因=战斗图集超 4096² | 检查=无
- 错误码=F1034/F1009 | 场景=DSL 编码 | 原因=包装壳或裸数值进 Array 参(F1034)/分支体写 DoNothing 或 AS3 空引用(F1009) | 检查=wf_dsl_sig

## 文案类

| 想改 | 真正生效的表 | 客户端读取 | 坑 |
|---|---|---|---|
| 角色详情页的技能描述 | `master/skill/action_skill`,**每一档**的 c1 | `ActionSkillLogic`、`DialogCharacterSkillDescriptionVariationTranslator`、`LearnWindow` | 只改角色文本表游戏里看不到(1.4.200 事故)。每档都要改,只改最高档会出现低档旧文 |
| 技能强化效果文案 | `ability` + `custom_ability_string` | `AbilityDescriptionGenerator`、`AbilityDescriptionTools`、`InstantAbilityDescriptionGenerator` | 强化只写在队长/能力条目,技能描述里不要重复写强化效果(作者 0927 规范) |
| 能力/队长技条目文案 | `ability`、`leader_ability` 的描述列;覆盖文案走 desc_override | `AbilityDescription*` | leader 124 列 / ability 126 列,列位不同、枚举同一套;一个键最多 9-10 条记录,只读第一行会漏 |
| 角色语音台词 | speech 表(zlib 五列 CSV) | — | constraint 可见数为 0 会崩 2265 |
| box 的 `character_text.json` | **只给服务端用**:admin-clairvoyance、任务战斗事实 | 客户端不读 | 改它不会改变游戏内任何文字 |

## 道具 / 战斗物件

| 想改 | 必须同改 | 不同改的后果 | 检查工具 |
|---|---|---|---|
| 新增即时道具 | `master/battle/item/executable_instant_item` + `master/battle/yakumono/direct_instant_item` + `executable_instant_item_level` | 缺等级行 = C8601 | `bughunt-20261014/out/c8601_fix_verify.py`(每个 eii 键必须有等级行);bh_items.py 里有同样检查。dummy_variants.py 是首个踩坑脚本 |
| 新增场地物件/判定区 | 地形 + action DSL | 见 memory 的 DSL 陷阱卡 | `wf_dsl_sig` 核对参数形状 |

## 敌人 / 关卡等级

| 想改 | 必须同改 | 后果 | 检查工具 |
|---|---|---|---|
| quest 的 `battle_enemy_level` | boss 与它所有召唤物的等级表,沿 quest → field_data → zone → boss/zako → action DSL → esdl → SpawnFunnel/SpawnAlterEgo 整条链都要有 ≥ 该等级的行 | U_3be147(`GeneralEnemySourceHelper.getSurjectivity` 找不到 key≥lv 的行就抛) | `bughunt-20261014/builder/level_gap_check.py`(退出码 1 = 有缺口;tier0 必崩,tier1/2 只报告) |
| 敌人显示等级 | 等级表 field 列 | — | 敌等级 = field 列 − 3(rogue 塔实证) |
| 多波关卡 | 地形层数决定波数,不是 zone 行数;多波须填 zone c7/c8 | C8251 | — |
| 改 boss 属性/换色 | 召唤物要加预载垫片 | C8016(时间轴未加载) | — |

## 商店 / 经济

| 想改 | 必须同改 | 后果 |
|---|---|---|
| 领主币商店自制商品 | 商品行 + `boss_coin_shop_item_category_map.json` + 客户端商品行 | 缺行 = C8601;category_map 缺 = 买不了 |
| 五重单人消耗 | 键 = `<category>_<questId>` | solo_entry 拒绝 = 400 |

## 角色本体

| 想改 | 落点 | 坑 |
|---|---|---|
| 元素 | token 只在 `character_groups`,伤害属性随 c3 | 可玩角色写 element=6(Colorless)会崩 C7050 |
| 新增角色 | character + 组 + 玛纳板(节点 ID = 角色ID×2 拼板序) + special 槽(★4 获取演出) | special 槽缺 = 硬 throw;服务端镜像 mana_board 要用客户端 generated 行原样 |
| 能力前置条件 | kind 8/9/87/187/188/200/205 留空 = C7050;202/203 留空才对 | — |
| 固有状态上限 | 写 (None) 或 1 = 按层数读的门全部失效;门控写 2,无上限写 99 | — |

## 发布前最低检查

1. 改了文案:确认改的是上面「真正生效的表」,不是派生/服务端文本。
2. 改了等级或新增敌人:跑 `level_gap_check.py`,退出码必须为 0。
3. 新增道具:每个 eii 键都有 `executable_instant_item_level` 行。
4. 平表新增行要压缩,否则行解不出(preflight 查不出,会污染 live 表)。
