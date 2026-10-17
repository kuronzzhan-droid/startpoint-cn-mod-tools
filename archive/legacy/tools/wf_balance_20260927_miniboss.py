"""十五名小动物（wf_miniboss_roster.ROSTER，含 139996 机枪魔块·雷）：2026-09-27 作者确认的技能槽修订。

规则（作者 2026-09-27 逐条确认）：
1. 能力 1-6 里条件触发（instant_trigger c27≠0）的「技能槽+X%」（instant_content 211）：
   强度 c51/c52 → 5000（5%），CT c35 → 900 帧（15 秒）；原本就是 5% 的只改 CT；限次 c34 原样保留
   （Sec-2600Li 复活加槽 c34=2 保留，CT 同样写 900）。
2. 能力里的技能充能速度（instant 35 c51/c52、during 3 c113/c114）高于 5% 的降到 5%；
   本来 ≤5% 的（含按层每层 2.5%/3%）不动。
3. 开局加槽（211 且 c27=0）与队长技全部不动。

共 31 个能力键 / 40 行 / 97 格，外加对应的 31 条 ``desc_override_<code>_N`` 面板（只改数值与 CT，格式照旧）。

纯函数：只转换 ``read()`` 给出的 live 输入，不写任何文件；候选回写、发布由批次暂存脚本统一做
（接口见 ${WF_ROOT}/out/平衡调整批次-20260927/module_contract.md）。
生成器 wf_miniboss_water/wind/fire/other.py 与面板 wf_miniboss_text.TEXTS 已同步：
``build_abilities`` / ``ability_panel_rows`` 的输出与 ``revise()`` 逐键相同，revise 运行时也会核对，
不一致即拒绝（重跑 wf_miniboss_ability_revision 不会回退本次改动）。
"""
from __future__ import annotations

from copy import deepcopy
from functools import partial
import hashlib
import json

import wf_client_legality as legality
import wf_describe as describe
from wf_miniboss_kits import build_abilities
from wf_miniboss_roster import BY_ID, ROSTER
from wf_miniboss_text import ability_panel_rows

SOURCE = "wf_balance_20260927_miniboss.py"
SPEC = ("作者 2026-09-27 确认：能力里条件触发的技能槽+X% 统一 5%/CT15秒（限次保留）；"
        "技能充能速度 >5% 的降到 5%；开局加槽与队长技不动")
REFILL = "5000"      # 5%（×100000 / 100）
CT_FRAMES = "900"    # 15 秒 × 60 帧；这批 c35 全按帧存（live 原值 120/180/480/0）
CHARGE_CAP = 5000
STRENGTH_COLS = {"I211": (51, 52), "I35": (51, 52), "D3": (113, 114)}

#: 逐行改动清单（行号 1 基）：I211 = 条件加槽 (原强度, 原CT帧)；I35 / D3 = 充能速度 (原强度)。
ROWS = (
    # 129998 水灵幽魂
    ("1299984", 1, "I35", "20000"),
    ("1299984", 2, "I211", "10000", "120"),   # 强化弹射
    ("1299984", 3, "I211", "15000", "120"),   # 发动技能
    ("1299986", 3, "D3", "20000"),            # 持有8层怨念（限1）
    # 139996 机枪魔块·雷
    ("1399964", 1, "I35", "15000"),
    ("1399964", 2, "I211", "25000", "120"),   # 发动技能
    ("1399965", 3, "I211", "15000", "120"),   # Lv3强化弹射
    # 129996 蓝色海妖
    ("1299964", 2, "I35", "15000"),
    ("1299964", 3, "I211", "8000", "120"),    # 受到治疗
    # 149994 风暴恶魔拉比
    ("1499946", 1, "I211", "10000", "180"),   # 持有8层岚痕 + 强化弹射
    ("1499946", 2, "I211", "8000", "120"),    # 风属性合计直击20次
    # 159999 Sec-2600Li
    ("1599994", 3, "I35", "15000"),
    ("1599995", 3, "I211", "10000", "180"),   # 每受伤5次
    ("1599996", 3, "I211", "50000", "0"),     # 复活（c34=2 保留）
    # 129995 彷徨铠甲·水
    ("1299952", 2, "I211", REFILL, "120"),    # 每受伤3次，原本 5%
    ("1299955", 2, "I211", REFILL, "120"),    # 全队，持有12层 + 强化弹射，原本 5%
    ("1299956", 2, "I211", "20000", "120"),   # 发动技能
    # 149993 哈宁绿
    ("1499935", 1, "I211", REFILL, "180"),    # 全队，碰撞8次，原本 5%
    ("1499936", 1, "D3", "15000"),            # 全队，持有6层埴（限1）
    ("1499936", 2, "I35", "15000"),
    # 119995 炎枪见习兵
    ("1199954", 1, "I35", "20000"),
    ("1199955", 1, "I211", REFILL, "180"),    # 全队，每30连击，原本 5%
    ("1199956", 2, "I211", "15000", "120"),   # 发动技能
    # 149992 彷徨铠甲·风
    ("1499925", 1, "D3", "15000"),            # 全队，浮游中
    ("1499925", 2, "I211", "10000", "480"),   # 全队，获得浮游
    ("1499926", 2, "I211", "15000", "120"),   # 发动技能
    # 129994 哈宁蓝Z
    ("1299942", 2, "I211", REFILL, "120"),    # 获得攻击buff的角色（c48=7），原本 5%
    ("1299945", 1, "D3", "15000"),            # 全队，持有5层补时（限1）
    ("1299946", 2, "I211", "20000", "120"),   # 发动技能
    # 119993 红蝮蛇
    ("1199935", 3, "I211", "10000", "180"),   # 火属性合计直击25次
    ("1199936", 2, "I211", "15000", "120"),   # 发动技能
    # 129993 冰冻虎鲸
    ("1299932", 2, "I211", "8000", "120"),    # 水属性合计直击30次
    ("1299936", 1, "I211", "20000", "120"),   # 发动技能
    # 169993 黑之下忍
    ("1699934", 2, "I35", "20000"),
    ("1699934", 3, "I211", "20000", "120"),   # 发动技能
    # 149991 疾风狂熊
    ("1499912", 2, "I211", "15000", "120"),   # 发动技能
    ("1499914", 2, "I35", "20000"),
    # 119994 哈宁红Z
    ("1199941", 2, "I211", "10000", "120"),   # 火属性合计直击30次
    ("1199944", 1, "I35", "20000"),
    ("1199944", 2, "I211", "10000", "180"),   # 获得追加直击
)

#: 按规则保留、且与改动同键或易被误认为漏改的行（行号 1 基）。
KEPT = (
    ("1299964", 1, "开局加槽 60%（c27=0）"),
    ("1699934", 1, "开局加槽 75%（c27=0）"),
    ("1199941", 1, "开局加槽 70%（c27=0）"),
    ("1599995", 2, "受伤回血 206 的 CT 180 帧不属于本规则"),
    ("1499944", 2, "每层岚痕充能 +2.5%（最多8层）≤5%"),
    ("1199935", 1, "每层毒环充能 +3%（最多5层）≤5%"),
    ("1299932", 1, "每层涨潮充能 +3%（最多5层）≤5%"),
    ("1199931", 3, "全队充能 +5% 未超过 5%"),
)

#: 新面板（逐字）：只改数值与 CT，沿用单行「；」格式；槽3（主位 MAIN 前缀）不在本批。
PANELS = {
    "1299984": "自身技能充能速度+5%；强化弹射时，自身技能槽+5%（CT：15秒）；自身发动技能时，自身技能槽+5%（CT：15秒）。",
    "1299986": "水属性角色全属性抗性+10%；自身发动技能时，恢复水属性角色5%生命值（CT：5秒）；持有8层怨念时，自身技能充能速度+5%。",
    "1399964": "自身技能充能速度+5%；自身发动技能时，自身技能槽+5%（CT：15秒）。",
    "1399965": "强化弹射时，连击+6；强化弹射所需连击数-3；发动Lv3强化弹射时，自身技能槽+5%（CT：15秒）。",
    "1299964": "战斗开始时，自身技能槽+60%；自身技能充能速度+5%；自身受到治疗时，自身技能槽+5%（CT：15秒）。",
    "1499946": "持有8层岚痕时，强化弹射使自身技能槽+5%（CT：15秒）；风属性角色合计每直接攻击20次，自身技能槽+5%（CT：15秒）。",
    "1599994": "光属性角色对减益敌人的攻击力+75%；战斗开始时，自身技能槽+75%；自身技能充能速度+5%。",
    "1599995": "光属性角色复活所需撞击次数-1；自身每受伤5次，恢复光属性角色3%生命值（CT：3秒），并使自身技能槽+5%（CT：15秒）。",
    "1599996": "自身发动技能时，获得交战模式，持续15秒；交战模式中，强化弹射伤害+50%；自身复活时，自身技能槽+5%（CT：15秒，最多2次）。",
    "1299952": "每持有1层装甲刻痕，水属性角色攻击力+10%（最大+120%）；自身每受伤3次，自身技能槽+5%（CT：15秒）。",
    "1299955": "水属性角色能力伤害+80%；持有12层装甲刻痕时，强化弹射使水属性角色技能槽+5%（CT：15秒）。",
    "1299956": "水属性角色能力造成的伤害+15%（独立乘区）；自身发动技能时，自身技能槽+5%（CT：15秒）。",
    "1499935": "自身与敌人每碰撞8次，风属性角色技能槽+5%（CT：15秒）；自身发动技能时，恢复风属性角色5%生命值（CT：5秒）。",
    "1499936": "持有6层埴时，风属性角色技能充能速度+5%；自身技能充能速度+5%。",
    "1199954": "自身技能充能速度+5%；战斗开始时，自身获得相当于最大生命值15%的屏障。",
    "1199955": "每达成30连击，火属性角色技能槽+5%（CT：15秒）。",
    "1199956": "自身生命值+25%；自身发动技能时，自身技能槽+5%（CT：15秒）。",
    "1499925": "浮游效果中，风属性角色技能充能速度+5%；获得浮游效果时，风属性角色技能槽+5%（CT：15秒）。",
    "1499926": "自身生命值+25%；自身发动技能时，自身技能槽+5%（CT：15秒）。",
    "1299942": "水属性角色攻击力提升效果时间+25%；水属性角色获得攻击力提升效果时，该角色技能槽+5%（各自CT：15秒）。",
    "1299945": "持有5层补时时，水属性角色技能充能速度+5%；强化弹射时，获得1层补时，持续20秒（CT：3秒）。",
    "1299946": "水属性角色直接攻击造成的伤害+15%（独立乘区）；自身发动技能时，自身技能槽+5%（CT：15秒）。",
    "1199935": "每持有1层毒环，火属性角色技能充能速度+3%（最大+15%）；火属性角色火属性抗性+20%；火属性角色合计每直接攻击25次，自身技能槽+5%（CT：15秒）。",
    "1199936": "火属性角色技能造成的伤害+15%（独立乘区）；自身发动技能时，自身技能槽+5%（CT：15秒）。",
    "1299932": "每持有1层涨潮，水属性角色技能充能速度+3%（最大+15%）；水属性角色合计每直接攻击30次，自身技能槽+5%（CT：15秒）。",
    "1299936": "自身发动技能时，自身技能槽+5%（CT：15秒）；自身生命值+25%。",
    "1699934": "战斗开始时，自身技能槽+75%；自身技能充能速度+5%；自身发动技能时，自身技能槽+5%（CT：15秒）。",
    "1499912": "战斗开始时，自身技能槽+75%；自身发动技能时，自身技能槽+5%（CT：15秒）；自身生命值+30%。",
    "1499914": "持有7层山鸣时，自身直接攻击分为2次，总伤害不变；自身技能充能速度+5%。",
    "1199941": "战斗开始时，自身技能槽+70%；火属性角色合计每直接攻击30次，自身技能槽+5%（CT：15秒）；自身发动技能时，获得2层窑火（最大5层）。",
    "1199944": "自身技能充能速度+5%；自身获得追加直接攻击效果时，自身技能槽+5%（CT：15秒）。",
}

#: 输入基线（digest(read(kind, key))，2026-09-27 live 快照 tests/fixtures/balance_20260927_miniboss.json）。
BEFORE = {
    ("ability", "1299984"): "88a285b643b4046570f124f85dd477f98cfdd58d4d60915cd987fcaac1739269",
    ("ability", "1299986"): "4828437a7ac33d2e71de262f7d90266aee7675f5db55d8851f707cd9740ce4d1",
    ("ability", "1399964"): "a756472adbc56f1306dd4a89c3a56511079a11d423caf4aafe05e0213e1bed52",
    ("ability", "1399965"): "53dc485685cd2050f81948ca21a89873482db4cfd53cc08fabaece833ea0cd85",
    ("ability", "1299964"): "7771d59cff436494f99ea69e09a9523af4439ba832d75903142e46ff7164b882",
    ("ability", "1499946"): "e6d87b3c9da5427b9c14a83b24e33d92f5512a0fdc93afc89f1f90bf6e9a76d3",
    ("ability", "1599994"): "579460276391622e7b8bdec24ea14ea5be05676989b797b19268b27bf36618bc",
    ("ability", "1599995"): "4201c2e7c8720233b71cec976dbac64e484ea5e788a7169e208b7095c45f44a7",
    ("ability", "1599996"): "b1ccd5f40ae077ff7b2518c4e4da516961d4919714e1c325a8d3a770ba413f8b",
    ("ability", "1299952"): "a2f3ea1983505899d96e1be065d8d4d5f0a5b5a924e08920565335ed62bc7583",
    ("ability", "1299955"): "8780186a5f1aaaa2dcc12e1e64963b0830d87dd01cfd4220792e79ebcd587571",
    ("ability", "1299956"): "0ce6beef8762538db1cd7589e8a7aeba8f60abd5504abe5ba853f90c8a0b5f7f",
    ("ability", "1499935"): "dbfddec523b86fd0a50070b31a8d79e5f8cbc71887c9f4a03801809938515e61",
    ("ability", "1499936"): "e12aa55a738901c14942ce8a3cea5d5a8a8451fd32e7bd341d01ebed0f389fad",
    ("ability", "1199954"): "61cc0609499d9f4f45724b5c6c5d56de9a27bed02f4fa9bc7df0139dc250c8fd",
    ("ability", "1199955"): "50203afc9b7f717f3a082c45b3d76ddd1d6e768dbcfb22248164bb6cc8479e5c",
    ("ability", "1199956"): "b80d27ae2871a5c303e7243e3af43fa2d79b7b07a13a472dce2ce37d6c51060b",
    ("ability", "1499925"): "a8de00ef21f23d1c6de6852a38577e04892f77cc01ea4d5adb9e9482c2c86a93",
    ("ability", "1499926"): "7fb263629187f1bfe1be346771cd1556802462f49e7f12a72118c9653bc86c50",
    ("ability", "1299942"): "7a8fa5ca17aab64b608cb45939bd7617801778e64c9a5a0d715384a07e982464",
    ("ability", "1299945"): "e41d10bd51b155b499669a5e9beb9119f533f78d564a47d66b03a33f71a525a8",
    ("ability", "1299946"): "d7dd8edeb208398f65b11dc7f7d36b055d394fd9e34bacb7c5e9b525832e40b6",
    ("ability", "1199935"): "7cba4d5a80211f19d5851b369482fa1118de74571505e932ae0cfb3d6ce84f56",
    ("ability", "1199936"): "0b3be0774f561bb74341b6ecdff4a7fd85c5e115f94ea1b9622b28ab8c082377",
    ("ability", "1299932"): "c57e9ada28510443ad074733831ef8d5a6c583664cae782aaba96e2478a76497",
    ("ability", "1299936"): "d3f69d50b9dfc0b0da6889205bc65b8eca3865599b09d2f7568363e3ef00fa5c",
    ("ability", "1699934"): "ca3cde857ddf8c0c8c5849ce39f6d9ce22fa9443614e75822cbe4d5dcf6b90df",
    ("ability", "1499912"): "5a18f24d668aa96d5302eac10b3a114dfcdfc57ae2d63b64ef65bab117faaeef",
    ("ability", "1499914"): "b0c40570e3ebdfcdd011d616f5d9db1b875ee6954e068c97c812cd922f21de57",
    ("ability", "1199941"): "3912a40b63c590126a28d1d411d82a52e88cadd09d606127fc2d9424ed1a7940",
    ("ability", "1199944"): "cfa76f3faa2d743a248c5bdeef8da70ecc0234632554d6bf9d57cb1881762fb6",
    ("cas", "desc_override_ghost_girl_playable_4"): "076d046deb3d5c436d3ea4ac0226ac46b3d7a53afc00a4e015932ae15a4b9db3",
    ("cas", "desc_override_ghost_girl_playable_6"): "728069be18acfa4c6f222f6fb355d09343bcad9b3c710958f24b8dd28d99c905",
    ("cas", "desc_override_cube_boss_playable_4"): "874b01067d5d035810aaf7d3b982b89702a8d71bd6fa1ab6a96d461285372265",
    ("cas", "desc_override_cube_boss_playable_5"): "84443602844d596dc74e861a6313d2fbe315da4fd88a1b1637bb2d7b18dd322f",
    ("cas", "desc_override_clione_playable_4"): "b4bd34908e46ca6ee8b70a92ad99be65c1259a8b6a0916d700994378f17ac5ac",
    ("cas", "desc_override_one_eyed_rabbit_playable_6"): "83f14b8b8977c70572f3ac4bed4fff1cae6712c30292e68b82b65be49e352db7",
    ("cas", "desc_override_security_robot_playable_4"): "9d49322044b2cc5631c6080ec0efdfa21c80e492a3fc2d6348442ab89eb63ce0",
    ("cas", "desc_override_security_robot_playable_5"): "70c74d069358d1bd453354f69597bbd70db9f6a132cbc4079323acae39767180",
    ("cas", "desc_override_security_robot_playable_6"): "afdd09a6bf3ec3f618d0b52902b3f09b3383c6c3d954aad0f3edff05ffbf2fd8",
    ("cas", "desc_override_wander_armor_water_playable_2"): "137504fed0d5caa94d1cfd5365c1e72040d2cb531d35875c5a9be21412afb5fb",
    ("cas", "desc_override_wander_armor_water_playable_5"): "7b7040d4594567568a17855902547b617f2ec0af4fe8d8acb0f0e0c460fe2616",
    ("cas", "desc_override_wander_armor_water_playable_6"): "b31ae26d2f230845ac2b6a6d2ae5c7612bb19ebc8e7fe93179b181d93ebb0636",
    ("cas", "desc_override_haniwa_green_playable_5"): "42bd97aba1c0dec96a078759960c0ac5dc68af54caac91c2515b35d388e28d1b",
    ("cas", "desc_override_haniwa_green_playable_6"): "6cb2a509561e80d68e72ac4db9796865a61ef9a0fade18ccc0c2edc12382d29d",
    ("cas", "desc_override_dog_soldier_playable_4"): "ff9b476ca5c8420b939a21a66a4b2fbaf519611d016288d5f073b35f03caab53",
    ("cas", "desc_override_dog_soldier_playable_5"): "6ecdeb7ce2986acf94d7d15b0814a866c878945e257093fe02e76fe68b856cf0",
    ("cas", "desc_override_dog_soldier_playable_6"): "286542b2826dce5db4c8325ea3f43fdbcfa431356367c1c2daccbeb016b522c3",
    ("cas", "desc_override_wander_armor_wind_playable_5"): "8210803ce3ca8dd55e148388049b91b2c6534fee65b84eca60b8bb01dc7cf088",
    ("cas", "desc_override_wander_armor_wind_playable_6"): "286542b2826dce5db4c8325ea3f43fdbcfa431356367c1c2daccbeb016b522c3",
    ("cas", "desc_override_haniwa_blue_playable_2"): "8264688db9e24963fbc09cb42cb6df5da180bc712673bf826aaa51a6ac7574b0",
    ("cas", "desc_override_haniwa_blue_playable_5"): "29ee39bb55af7533d840a461dc261cad7fd8f9b51c80231181902b3a6d2a2e62",
    ("cas", "desc_override_haniwa_blue_playable_6"): "55df8d837ae05324a0a24a2110de89e2113caca85cfa62641b38061a1bb86667",
    ("cas", "desc_override_cobra_playable_5"): "04b0bc660beda90b4bd7e3a864300c68dec83a20e57f616ad077de6a7cbce268",
    ("cas", "desc_override_cobra_playable_6"): "079dfc91514766c372ebf0ac5a63176831d6b28c60bec63aa076689c96ffd9fe",
    ("cas", "desc_override_killer_whale_playable_2"): "6c089c6c0f5778c4e517cbba6f972d34cc692e95a2a645585e2c8bbcdd93c15c",
    ("cas", "desc_override_killer_whale_playable_6"): "773685b828a26ea9c61d7fe3dea7a394da800a2d466e55857246cf0ec01e34b1",
    ("cas", "desc_override_genin_playable_4"): "8d5bc2b312be3884df16b17dcd1deb173c571cd4fd6ee9f384449b9ccf16143a",
    ("cas", "desc_override_big_bear_monster_playable_2"): "ee6824a017dc567f04c3efca6c34dd1a370bbbaf988549b2e0d9d98e393fc9bd",
    ("cas", "desc_override_big_bear_monster_playable_4"): "3042335d12169e84c2eae73cee0f8205aba687699e3c69f56f1b2dcd2f5ca543",
    ("cas", "desc_override_haniwa_playable_1"): "18ea4e099d3a6398e7fa11e630835a8a788375f374f2a632cb7504509efa42aa",
    ("cas", "desc_override_haniwa_playable_4"): "4d19437945a4ec65ebe9ea9f76e7ea8b7ee06500e80b4454383e0ed1a0b158c1",
}

#: 顶层候选 work/character_packs/<package_id>（active owner；169993 → genin）的 manifest 现值均为
#: 1.0.0（2026-09-27 核对），本次 +1。miniboss-rework-20260912/<code> 副本不回写。
PACKAGE_VERSION = "1.0.1"
CANDIDATE_NOTE = ("只回写本次改动的能力键与面板键；顶层候选其余能力/队长/状态/文本键仍是 2026-09-12 前 v0 内容，"
                  "禁止从这些候选整包 flow publish；禁止以 miniboss-rework-20260912 为 root 重跑 "
                  "wf_content_revision_patch（会把 90 个能力键退回 v1 并覆盖本次改动）")


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def panel_key(ability_key: str) -> str:
    return f"desc_override_{BY_ID[ability_key[:6]].code}_{ability_key[6:]}"


def expected_cells(spec) -> dict:
    """一条 ROWS 记录 → {列: (旧值, 新值)}。"""
    _, _, family, strength, *ct = spec
    cells = {} if strength == REFILL else {c: (strength, REFILL) for c in STRENGTH_COLS[family]}
    if family == "I211":
        cells[35] = (ct[0], CT_FRAMES)
    return cells


def _over_cap(row, cols) -> bool:
    return any(int(row[c]) > CHARGE_CAP for c in cols)


def apply_rule(rows: list[list[str]]) -> list[list[str]]:
    """把作者规则套到一个能力键的全部行上（不改输入）。"""
    out = deepcopy(rows)
    triggers = describe.enum_map()["cases"]["instant_trigger"]
    for row in out:
        if len(row) != 126:
            raise ValueError("unexpected ability row width")
        if row[5] == "0" and row[47] == "211" and row[27] not in ("", "0"):
            if "cooltime" not in triggers[row[27]]["fields"] or any(row[53:55]):
                raise ValueError(f"unreviewed skill-gauge row shape: trigger {row[27]}")
            row[51] = row[52] = REFILL
            row[35] = CT_FRAMES
        elif row[5] == "0" and row[47] == "35" and _over_cap(row, STRENGTH_COLS["I35"]):
            row[51] = row[52] = REFILL
        elif row[5] == "1" and row[109] == "3" and _over_cap(row, STRENGTH_COLS["D3"]):
            row[113] = row[114] = REFILL
    return out


def _plan_for(cid: str) -> dict:
    """{能力键: {行下标(0 基): {列: (旧, 新)}}}"""
    plan = {}
    for spec in ROWS:
        if spec[0][:6] == cid:
            plan.setdefault(spec[0], {})[spec[1] - 1] = expected_cells(spec)
    return plan


def _baseline(cid: str, read) -> dict:
    """读取并锁定本角色全部输入；任何一项漂移都拒绝（fail closed）。"""
    inputs = {}
    for kind, key in UNIT_BEFORE[cid]:
        value = read(kind, key)
        if value is None or digest(value) != BEFORE[kind, key]:
            raise ValueError(f"unreviewed live baseline: {kind}:{key}")
        inputs[kind, key] = deepcopy(value)
    return inputs


def _diff(old, new) -> dict:
    if len(old) != len(new):
        raise ValueError("row count changed")
    return {i: {c: (x, y) for c, (x, y) in enumerate(zip(a, b)) if x != y}
            for i, (a, b) in enumerate(zip(old, new)) if a != b}


def row_problems(row: list[str], cas_keys) -> list[str]:
    return (legality.client_legality_problems("ability", row)
            + legality.declared_block_field_problems("ability", row)
            + legality.invoke_skill_string_problems(row, cas_keys, "ability"))


def revise_character(cid: str, read) -> dict:
    char = BY_ID[cid]
    inputs = _baseline(cid, read)
    plan = _plan_for(cid)
    ability, changed = {}, []
    for key, rows in plan.items():
        new = apply_rule(inputs["ability", key])
        seen = _diff(inputs["ability", key], new)
        if seen != rows:
            raise ValueError(f"rule result differs from the reviewed plan: {key}: {seen}")
        ability[key] = new
        changed += [{"key": key, "row": i + 1, "cells": {str(c): list(v) for c, v in cells.items()}}
                    for i, cells in sorted(seen.items())]
    cas = {}
    for key in plan:
        old = inputs["cas", panel_key(key)]
        if len(old) != 1 or len(old[0]) != 1 or old[0][0] == PANELS[key]:
            raise ValueError(f"unexpected panel preimage: {panel_key(key)}")
        cas[panel_key(key)] = [[PANELS[key]]]

    # 生成器一致性：重跑 wf_miniboss_kits / wf_miniboss_text 必须得到同样的行与面板。
    kit, _ = build_abilities(cid)
    panels = ability_panel_rows(cid, kit)
    drift = sorted([k for k, rows in ability.items() if kit[k] != rows]
                   + [k for k, rows in cas.items() if panels[k] != rows])
    if drift:
        raise ValueError(f"generator differs from the revision: {drift}")

    problems = [f"ability {key}#{i}: {p}" for key, rows in ability.items()
                for i, row in enumerate(rows) for p in row_problems(row, set(cas))]
    if problems:
        raise ValueError("; ".join(problems))
    return {
        "ability": ability, "leader": {}, "cas": cas, "text": {}, "table": {},
        "action": {}, "dsl": {}, "server_text": {}, "new_programs": [],
        "notes": {
            "source": SOURCE, "spec": SPEC, "character": char.name,
            "changed": changed,
            "kept_by_rule": [{"key": k, "row": r, "why": why} for k, r, why in KEPT if k[:6] == cid],
            "generator": "wf_miniboss_kits.build_abilities / wf_miniboss_text.ability_panel_rows == revise()",
            "candidate": CANDIDATE_NOTE,
            "runtime_verified": False,
        },
    }


def _unit_before(cid: str) -> tuple:
    keys = sorted({spec[0] for spec in ROWS if spec[0][:6] == cid})
    return tuple([("ability", k) for k in keys] + [("cas", panel_key(k)) for k in keys])


UNIT_BEFORE = {char.cid: _unit_before(char.cid) for char in ROSTER}
if (set(BEFORE) != {item for items in UNIT_BEFORE.values() for item in items}
        or set(PANELS) != {spec[0] for spec in ROWS}):
    raise ImportError("BEFORE / PANELS / ROWS are out of sync")

UNITS = [dict(CID=char.cid, CODE=char.code, NAME=char.name,
              PACKAGES=[char.package_id], PACKAGE_VERSION={char.package_id: PACKAGE_VERSION},
              CAPABILITIES=[], REVIEWED_DRIFT={},
              BEFORE={item: BEFORE[item] for item in UNIT_BEFORE[char.cid]},
              revise=partial(revise_character, char.cid))
         for char in ROSTER]
