'墨斯伊克「自由之羽」（149997 mosiyike）：2026-09-27 平衡调整第二批（Down / 削韧）。\n\n口径（${WF_ROOT}/out/平衡调整批次-20260927/batch2/第二批施工口径.md，作者已拍板）B.2：强化弹射每级削韧上限 15 / 20 / 25，\n尽量正好顶到上限。设计稿 down_design.json 149997（按 live 1.4.1048 写；本模块按 live 1.4.1049 重读，结构与数值一致）：\n\n- PF 覆盖树（leader 149997#0 kind 722 → power_flip_action ``mosiyike_pf`` → lv1/lv2/lv3）= 官方辅助段（无攻击）＋\n  撞敌后按 Wait 错开发射的自走风刃（每发 CreateHitArea 1 段，onHit 一条 CreateNormalAttack p13=5），\n  Lv1/Lv2/Lv3 = 2/5/10 发 ⇒ 10/25/50。\n- 本模块：Lv1 10 ≤ 15 不动；Lv2 每发 p13 5→4（25→20）；Lv3 每发 5→2.5（50→25）⇒ 10/20/25，Lv2/Lv3 正好顶到上限。\n  与设计稿的差异：设计稿三档统一 5→2.5 得 5/12.5/25，Lv1/Lv2 低于上限（Lv1 本来就在上限内却被砍半）；\n  按口径 B.2「尽量正好顶到上限」取 10/20/25（同批白、莉莉丝、克劳斯同一取法）。若要回到设计稿，只改 ``PF_PLAN``\n  （Lv1 5→2.5、Lv2 5→2.5）与包内 build_pf.py 的 ``DETOUGHNESS``。\n- B.6：只改 CreateNormalAttack 的 p13（SLv 的 {min,max} 同改），其余逐字保留；整树 AMF3 往返一致（连 int/float 类型）\n  并过四道 DSL 门禁。\n\n候选：``work/character_packs/mosiyike``（active.json base_package_owners 引用）。候选 manifest 0.1.0 → 0.1.1。\n候选打开时有 29 条既有漂移（技能两档 DSL、护盾特效 5 件、语音 18 条、服务端镜像 3 件）：common 的 26 件与 live\n逐字节相同，服务端镜像里本角色 149997 的行与 assets 相同——都是候选文件已跟到 live、manifest 哈希未重封，\n与本次 PF 树无关，按已审漂移放行（``REVIEWED_DRIFT``，值 = 候选文件 sha256）。PF 三档在候选里与 manifest、live 三者一致。\n\n纯函数：只转换 ``read()`` 给出的 live 输入，不写任何文件（接口见 ${WF_ROOT}/out/平衡调整批次-20260927/module_contract.md）。\n生成器：``work/character_packs/mosiyike/build_pf.py`` 的纯函数 ``build_level(level)`` 与 live 三档逐节点相同，是现行生成源；\n已同步 ``DETOUGHNESS = {1: 5, 2: 4, 3: 2.5}``（每发风刃 p13，经 ``wave()`` 传入），测试断言生成器输出 == 本模块输出。\n该脚本 main() 会写包，禁止运行，只改源码。\n'
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
import json

import wf_client_legality as legality
import wf_dsl

CID = "149997"
CODE = "mosiyike"
PACKAGES = ["mosiyike"]
#: 候选 manifest 现值 0.1.0 → 递增。
PACKAGE_VERSION = {"mosiyike": "0.1.1"}
CAPABILITIES: list[str] = []
ELEMENT = 3  # master/character c3：风（0 基内部元素）

_R5 = "battle/action/skill/action/rare5/"
_SHIELD = "battle/effect/skill_unique/mosiyike/mosiyike_shield/"
_VOICE = "character/mosiyike/voice/"
#: 候选既有漂移（2026-09-27 审过：common 件与 live 逐字节相同；服务端镜像的 149997 行与 assets 相同）。
REVIEWED_DRIFT = {
    ("common", f"{_R5}mosiyike$mosiyike_1.action.dsl.amf3.deflate"):
        "07e3c40f8bdb1985511be967205bb30f64ae52f6eaae029d9d8146339520cf50",
    ("common", f"{_R5}mosiyike$mosiyike_2.action.dsl.amf3.deflate"):
        "7739a4f9458633ec09b234c39a86b13f253c8eef22a0ca406ecb3c299d04ca6b",
    ("common", f"{_SHIELD}mosiyike_shield.atlas.amf3.deflate"):
        "bc5831d426d10505f02d93d52ed66ed47de6a62c608f66ed7f0ee6509e0372f6",
    ("common", f"{_SHIELD}mosiyike_shield.png"):
        "23e77547506ebc095873b6c0307f02b0f9595775d817d86968c3eef834fc2a5d",
    ("common", f"{_SHIELD}mosiyike_shield_gather.parts.amf3.deflate"):
        "1a9522d65f162656bcbc3b35f24a800e5f07929160a744f35880b3fc9b8d748c",
    ("common", f"{_SHIELD}mosiyike_shield_gather.timeline.amf3.deflate"):
        "8dd61177f636c99b5eedc6b2f94cb3704729d3378895b95d96a82ec80f9fb9c6",
    ("common", f"{_SHIELD}mosiyike_shield_loop.parts.amf3.deflate"):
        "0fb5b83a7b4142912cbf482cb39099c4e32c384f074d69397903680fa01f7ba0",
    ("common", f"{_VOICE}ally/evolution.mp3"):
        "0a013012429e6c1844e7191d33f8847f57c4f0f65e60338cf220e31f15aed95c",
    ("common", f"{_VOICE}ally/join.mp3"):
        "e5addaf58804733fc5368960d7011a65664aabe3ccd65e4c361dc4eec0f2b6f8",
    ("common", f"{_VOICE}battle/battle_start_0.mp3"):
        "b042e233741a50a863b9efe2ebd3e195508e5c33c965a5a4910d3e1c2d525ec9",
    ("common", f"{_VOICE}battle/battle_start_1.mp3"):
        "72625ac949b4925a561f49663516224a5960c1a3698a67b4084a6ed29c530970",
    ("common", f"{_VOICE}battle/outhole_0.mp3"):
        "ad4eed12bcc1f1bf89437b1ea61822d0a87ea85083b3336ee3e71190ef2561d0",
    ("common", f"{_VOICE}battle/outhole_1.mp3"):
        "af595fcf3be5371960aa512090a46e3751b3c5b74e7801c0ec22ae000b72b2a6",
    ("common", f"{_VOICE}battle/power_flip_0.mp3"):
        "d5a6217a9d5e86bd1246880e4594b41d455d4bcd53953e4d6d3d9257438ecc34",
    ("common", f"{_VOICE}battle/power_flip_1.mp3"):
        "b529a7ca52a94e120fbe3f1f640783a3b172e9d4125afcb5c5206239fc502665",
    ("common", f"{_VOICE}battle/skill_0.mp3"):
        "f24a22f13e07e2b663eeb071a4124afcff2237e25b53458bf888b5837f977d90",
    ("common", f"{_VOICE}battle/skill_1.mp3"):
        "f9803a4bbd90b342744ccc08e9f252a7c57d9b99e31c9bc54ed419fbdaab360a",
    ("common", f"{_VOICE}battle/skill_ready.mp3"):
        "96923fdbb61b279c2a5a0d3259ff2c4a6e0589de47205fa34cd05080e42e2ecc",
    ("common", f"{_VOICE}battle/win_0.mp3"):
        "fc3da3232bd89a489d1d19f39d62f150a05165e7564859c9515ceb33b53105bf",
    ("common", f"{_VOICE}battle/win_1.mp3"):
        "63bbfc340e70b20a73d478a8b8f54505bc10f5a5ecf15740da516af9846f1af9",
    ("common", f"{_VOICE}home/amaminonakani.mp3"):
        "ccd816b33da4c8d152084d46e499a35023b22b46e9e1101568f059df660f15f6",
    ("common", f"{_VOICE}home/kaerarenumono.mp3"):
        "385fe7209c48fa4e712bbd430213ac02dcc74711e2fa083a6d74855a27a28270",
    ("common", f"{_VOICE}home/kiotsukero.mp3"):
        "654500e91f7b14af37c5a6150d065b8034fe3346db6b923b046380176a30e365",
    ("common", f"{_VOICE}home/kyokumo.mp3"):
        "055767ea9266339710b98c17519570b256ba08844a691989b025a98750058b53",
    ("common", f"{_VOICE}home/orenoshokuhiha.mp3"):
        "b94baac95182d2cfc60a8199014622b785f089688c551d8e13be724b8b3e68e6",
    ("common", f"{_VOICE}home/ryoriwa.mp3"):
        "e6bd0f331229308eccac6dda373bd8568274879308e69b5db3f7fd8e46060b34",
    ("server", "cdndata/character.json"):
        "51a8847198bcae333bd9e35403f4849ede56f73b267a496c0b1f9cc35d8cb8f2",
    ("server", "cdndata/character_text.json"):
        "4d3ab31184e7b6cae215cc2a2db92bf0c2e205af6b88ba4d91d843eba94f5303",
    ("server", "character.json"):
        "d74627e3a4d52d2d899f7cac00db2626c0bfcc7fdd6242b0a08617d776b0804a",
}

PF_ACTION = ("master/skill/power_flip_action.orderedmap", f"{CODE}_pf")
PF_LEVELS = (1, 2, 3)
PF_PROGRAMS = {level: f"battle/action/power_flip/action/override/{CODE}_pf${CODE}_pf_lv{level}"
               for level in PF_LEVELS}
#: 强化弹射每级削韧上限（口径 B.2）。
PF_CAP = {1: 15, 2: 20, 3: 25}
#: 每档：(风刃发数, 改前每发 p13, 改后每发 p13)。Lv1 10 已在上限内，不动。
PF_PLAN = {1: (2, 5, 5), 2: (5, 5, 4), 3: (10, 5, 2.5)}
#: 被改的档位（Lv1 不返回）。
CHANGED_LEVELS = tuple(level for level in PF_LEVELS if PF_PLAN[level][1] != PF_PLAN[level][2])
TOLERANCE = 1e-9

BEFORE = {
    ("table", PF_ACTION): "2c08944b28060e81a6ecbf12daf086ce609ee9709828737c2fd1e833ae575dd3",
    ("dsl", PF_PROGRAMS[1]): "0d48ffe946c1b15280777b1f334ff74fbb1fac084ad8d5e43d2ec5b37384bd0b",
    ("dsl", PF_PROGRAMS[2]): "c8cefcbde7751eeb10d411dff3107a1c2f9e9e67274b77cba4f39ac9bce1cea7",
    ("dsl", PF_PROGRAMS[3]): "dba89fcc169a4ce16bf9a6abf82046bf1df6f612828e12cc94f803f642cd6730",
}


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def _baseline(read) -> dict:
    """读取并锁定全部输入；任何一项漂移都拒绝（fail closed）。"""
    inputs = {}
    for kind, key in BEFORE:
        value = read(kind, key)
        if value is None or digest(value) != BEFORE[kind, key]:
            raise ValueError(f"unreviewed live baseline: {kind}:{key}")
        inputs[kind, key] = deepcopy(value)
    if inputs["table", PF_ACTION] != [[PF_PROGRAMS[level] for level in PF_LEVELS]]:
        raise ValueError("power_flip_action no longer points at the reviewed PF trees")
    return inputs


# ---------------------------------------------------------------- 单目标削韧


def _tag(node):
    return node[0] if isinstance(node, list) and node and isinstance(node[0], str) else None


def _area_hits(args) -> int:
    """判定区对单一目标的命中数：MaxNumOfHits，或「寿命 ÷ 最小间隔 + 1」，再与 Some 上限取小。"""
    lifetime, count, cap = args[13], args[14], args[15]
    if count[0] == "CalculatedUsingMaxNumOfHits":
        hits = count[1]
    elif count[0] == "SpecifyMinHitIntervalDirectly" and lifetime[0] == "SpecifyHitAreaLifetimeDirectly":
        hits = lifetime[1] // count[1] + 1
    else:
        raise ValueError(f"unreviewed hit-area count shape: {lifetime} / {count}")
    if cap[0] == "Some":
        hits = min(hits, cap[1][0]["max"])
    elif cap != ["None"]:
        raise ValueError(f"unreviewed hit-area cap shape: {cap}")
    return hits


def _p13(args):
    value = args[13]
    if (not isinstance(value, list) or len(value) != 1 or set(value[0]) != {"min", "max"}
            or value[0]["min"] != value[0]["max"]):
        raise ValueError(f"unreviewed CreateNormalAttack p13 shape: {value}")
    return value[0]["max"]


def hit_areas(tree) -> list[tuple[list, int, list]]:
    """[(CreateHitArea 参数, 单目标命中数, onHit 内 CreateNormalAttack 参数列表)]，按树序；遇未审形状拒绝。"""
    found = []

    def walk(node):
        if not isinstance(node, list):
            return
        tag = _tag(node)
        if tag and (tag.startswith("Conditionals") or tag == "Repeat"):
            raise ValueError(f"unreviewed branch/loop node: {tag}")
        if tag == "Command":
            args = node[1]
            if args[0] == "CreateNormalAttack":
                raise ValueError("CreateNormalAttack outside a hit area onHit block")
            if args[0] == "CreateHitArea":
                if (list(wf_dsl.iter_dsl_commands(args[20], "CreateNormalAttack"))
                        or list(wf_dsl.iter_dsl_commands(args[20], "CreateHitArea"))
                        or list(wf_dsl.iter_dsl_commands(args[23], "CreateHitArea"))):
                    raise ValueError("unreviewed nested hit-area shape")
                found.append((args, _area_hits(args),
                              list(wf_dsl.iter_dsl_commands(args[23], "CreateNormalAttack"))))
                return
            for child in args[1:]:
                walk(child)
            return
        for child in node:
            walk(child)

    walk(tree)
    return found


def detoughness(tree) -> float:
    """每次 PF 对单一目标的总削韧：Σ 判定区命中数 × onHit 里 CreateNormalAttack 的 p13。"""
    return round(sum(hits * _p13(a) for _, hits, attacks in hit_areas(tree) for a in attacks), 6)


def p13_census(tree) -> dict:
    return dict(Counter(_p13(a) for a in wf_dsl.iter_dsl_commands(tree, "CreateNormalAttack")))


# ---------------------------------------------------------------- DSL 改写


def _waves(tree, level: int) -> list:
    """每发风刃判定区：球锚定（-18）、坐标 EF、1 段、onHit 一条 CreateNormalAttack。"""
    waves, before, _ = PF_PLAN[level]
    areas = hit_areas(tree)
    shape = [(args[2], args[3], n, [_p13(a) for a in attacks]) for args, n, attacks in areas]
    if shape != [(-18, ["EF"], 1, [before])] * waves:
        raise ValueError(f"PF lv{level}: wind-blade preimage drift {shape}")
    return areas


def revise_pf_tree(tree, level: int) -> list:
    """PF 覆盖树第 level 档：每发风刃 p13 改到 PF_PLAN，其余节点逐字保持；不改输入。"""
    what = f"PF lv{level}"
    result = deepcopy(tree)
    if result[:11] != ["ActionDsl", 1, ["None"], *[False] * 7, 0]:
        raise ValueError(f"{what}: root header drift")
    waves, _, after = PF_PLAN[level]
    for _, _, attacks in _waves(result, level):
        attacks[0][13] = [{"min": after, "max": after}]
    total = detoughness(result)
    if total > PF_CAP[level] + TOLERANCE or abs(total - waves * after) > TOLERANCE:
        raise ValueError(f"{what}: detoughness {total} over cap {PF_CAP[level]}")
    return result


def dsl_problems(tree) -> list[str]:
    problems = []
    back = wf_dsl.parse_dsl(wf_dsl.encode_amf3(tree))["tree"]
    if json.dumps(back) != json.dumps(tree):   # 连 int/float 类型一起比
        problems.append("AMF3 roundtrip mismatch")
    problems += [f"element: {p}" for p in legality.action_dsl_element_problems(tree, ELEMENT)]
    problems += [f"subject: {p}" for p in legality.action_dsl_subject_binding_problems(tree)]
    problems += [f"scope: {p}" for p in legality.action_dsl_lookup_scope_problems(tree)]
    problems += [f"hit_target: {p}" for p in legality.action_dsl_hit_area_target_problems(tree)]
    return problems


def revise(read) -> dict:
    inputs = _baseline(read)
    before = {level: detoughness(inputs["dsl", PF_PROGRAMS[level]]) for level in PF_LEVELS}
    revised = {level: revise_pf_tree(inputs["dsl", PF_PROGRAMS[level]], level) for level in PF_LEVELS}
    if json.dumps(revised[1]) != json.dumps(inputs["dsl", PF_PROGRAMS[1]]):
        raise ValueError("PF lv1 must stay byte-identical (already within the cap)")
    dsl = {PF_PROGRAMS[level]: revised[level] for level in CHANGED_LEVELS}
    problems = [f"dsl {program}: {p}" for program, tree in dsl.items() for p in dsl_problems(tree)]
    if problems:
        raise ValueError("; ".join(problems))
    return {
        "ability": {}, "leader": {}, "cas": {}, "text": {}, "table": {}, "action": {},
        "dsl": dsl, "server_text": {}, "new_programs": [],
        "notes": {
            "source": "wf_balance_20260927b_mosiyike.py",
            "spec": "第二批施工口径 B.2（PF 每级 ≤15/20/25，尽量正好顶到上限）、B.6；down_design 149997（按 live 1.4.1049 重读）",
            "pf_detoughness": {f"lv{level}": [before[level], detoughness(revised[level])] for level in PF_LEVELS},
            "pf_wave_p13": {f"lv{level}": [PF_PLAN[level][1], PF_PLAN[level][2]] for level in PF_LEVELS},
            "deviation_from_design": ("设计稿三档统一 p13 5→2.5（5/12.5/25）；口径 B.2「尽量正好顶到上限」⇒ Lv1 10 在上限内不动，"
                                      "Lv2 5→4（20）、Lv3 5→2.5（25）。回到设计稿只需改 PF_PLAN 与 build_pf.DETOUGHNESS"),
            "candidate_drift": ("29 条既有漂移按已审放行：common 26 件与 live 逐字节相同，服务端镜像 3 件中本角色 149997 行与 "
                                "assets 相同；manifest 哈希未重封，非本次引入"),
            "generators": ("work/character_packs/mosiyike/build_pf.py：build_level(level) 与 live 三档逐节点相同；已同步 "
                           "DETOUGHNESS={1: 5, 2: 4, 3: 2.5}（经 wave() 传入 p13），生成器输出 == 本模块输出（不运行 main）"),
            "text_sync": "PF 覆盖文案「追加「苍穹风刃」特殊强化弹射」不含数值，无需同步",
            "runtime_verified": False,
        },
    }
