# 服务端合并记录

共同祖先使用 kulo 提交 `7e6d55b62eacca91ca7e557a02b5b9af6e2495a9` 的服务端 assets。该提交说明明确移除旧 1.4.131 救援铃增量、将有效 CDN 终点恢复为 1.4.130。灰端为 `224aa2a663b7756fc8a34c0f37f1ae61ad81800c` 的 `origin/main` assets；我方终态为 `D:/WF/out/角色超限-120/localsrv219/assets`。没有把客户端 `store131` 当成服务端祖先。

三方规则：我方相对祖先未改的内容保留灰端；双方同列同值保留灰端；仅我方改的列取我方终态；双方同列不同值的真实冲突默认取灰，并把祖先/灰/我方值记录到 `server-audit.json`。对象递归按键、同长表行按列合并；根级 ID 列表追加我方新增项；`character_id` / `id` 对象列表按身份合并。服务端真实冲突为 0。

输出为 25 文件、1369 个顶层键更新或 ID 追加条目，完整值、预期基线与具体改列路径见 `交付/server-entries.json`。1369 是应用操作数，不是角色、武器或副本实体数。

| 文件 | 操作数 |
|---|---:|
| boss_battle_quest_cnmod.json | 45 |
| boss_coin_shop.json | 28 |
| boss_coin_shop_item_category_map.json | 126 |
| cdndata/character_text.json | 9 |
| character_awake_extension.json | 2 |
| character_overlimit.json（新文件） | 7 |
| equipment_awakening_material.json | 1 |
| equipment_dissolve.json | 54 |
| equipment_element.json | 63 |
| equipment_enhancement_shop.json | 378 |
| equipment_ids.json | 63 |
| equipment_lookup.json | 63 |
| equipment_max_level.json | 63 |
| event_item_shop.json | 1 |
| event_item_shop_id_map.json | 9 |
| hard_multi_event_quest.json | 27 |
| item_ids.json | 100 |
| item_lookup_cnmod.json | 91 |
| item_sale.json | 99 |
| mana_board.json | 14 |
| mana_node.json | 1 |
| mission_char_awake_cnmod.json | 8 |
| mission_char_awake_reward_cnmod.json | 8 |
| rare_score_reward_cnmod.json | 37 |
| score_reward_cnmod.json | 72 |

剔除项共 69 处服务端记录引用：`practice_quest.json` 的 1103–1123 共 21 木人行；GM 5990001–5990006 在 `equipment_dissolve`、`equipment_element`、`equipment_ids`、`equipment_lookup`、`equipment_max_level`、`item_ids`、`item_lookup_cnmod`、`item_sale` 共 8 文件各 6 处，合计 48 处。实体数仍为 6 把 GM 武器和 21 个训练木人。客户端表键/资源的剔除统计另计，不与本数相加冒充实体数。服务端未发现其他 GM 商店或掉落引用；递归精确 ID 扫描已在合并结果中排除这些 ID。

我方删去 `boss_coin_shop_item_category_map.json` 的祖先键 202045，灰端也已删除；本构建器不生成删除操作，记录在 `skipped_deletions`。这不构成真实三方冲突。

保留分类 98 魂珠兑换：54 件为 `8000101–8000124`、`5910101–5910129`、`5920001` 的魂珠；单价 999 禁忌星铁 10000311、限购 999，来源 `soul_shop204_price999.py` 明确作者 1015 改价，属于作者内容。它不包含 GM 武器。领主武装本体为另一个 54 件集合 `5930001/5930002 ... 5930261/5930262`。

应用脚本验证已完成：在本工作区中用只读 Git 导出的灰 assets 副本执行完整 dry-run 和 apply，25 文件输出逐字节等于合并视图；再次应用被拒绝且所有文件 SHA256 不变；脏键被拒绝、重复 JSON 键被拒绝、根级 ID 已存在被拒绝；CRLF/LF、UTF-8 BOM、非目标键原始空格与字节保持不变。验证明细在 `server-verification.json`。应用脚本先核对整个批次再写入，默认只核对，只有 `--apply` 才写。

源码支持缺口：灰 `origin/main` 没有超限 Lv120 实现，附件见 `交付/服务端源码补充/`。纯源码补丁已在内存逐 hunk 核对至来源字节，未编译、未运行、未部署。其余数据由灰现有通用 assets 导入器读取；这些数据在灰实际运行环境中的行为未核实。

149999 杰拉德的服务端资料旧文案在灰基线、我方终态和合并视图中完全相同，并未列入本次 `server-entries.json`。客户端本次做了资料描述与技能终态一致的显式归一化；服务端该旧文案不属于本次导入，保留灰原值，不额外增加服务端改动。

重跑：`python 交付/build/server_merge.py`；随后 `python 交付/build/server_verify.py`；源码补充 `python 交付/build/server_source_supplement.py`。合并后的完整服务端 JSON 视图位于 `cache/server-merged-assets/`，供本地静态 prepush 使用；没有改写灰仓库。
