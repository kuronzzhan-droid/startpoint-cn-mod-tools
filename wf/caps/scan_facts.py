"""Mechanism primitives ported from the reviewed 108-character matrix scanner."""
from __future__ import annotations

SYSTEM_KINDS = {  # (block, kind) -> 能力名
    ("during", "422"): "kind422冲刺参数(APK#03)",
    ("during", "423"): "kind423回槽来源限制(APK#31/#30)",
    ("during", "424"): "kind424伤害类型转换(APK#20)",
    ("instant", "724"): "kind724 Fever比例(APK#04)",
}
PF_OVERRIDE = {("instant", "722"), ("during", "419")}
INVOKE_SKILL = ("instant", "629")
CHARGE_CAP_UNIQUE = "13999010"
KYLE_UNIQUES = {"13999011", "13999012"}
SUNBURN_UNIQUE = "1499901"
BTA_CONVERT = {101, 102, 104, 131, 132, 133}
# DSL 里值得在矩阵里点名的官方原语(C 层线索)
DSL_MARKERS = {"CreateRatioAttack": "比例伤害(真伤)", "ACPoison": "中毒", "RotateHitArea": "旋转判定区",
               "ACElementResistance": "属性抗性改写", "RemoveMultiball": "移除协力球"}
# 已知按角色写死的 APK 补丁(来源:ghmain/apk-patches/README 与各目录 README)
PER_CHAR_APK = {
    "149990": ["白晒伤减抗(APK#05)", "白Fever语音路由(APK#06)"],
    "129992": ["准备音轮换129992(APK#07/#15)"],
    "139993": ["准备音(APK#15)"],
    "159998": ["准备音(APK#15)"],
    "149999": ["准备音轮换149999(APK#65)"],
    "139990": ["凯尔直击参数(APK#54/#56)", "PF追加命中静默(APK#55)"],
    "159991": ["稻穗视觉预载(APK#32)"],
    "139995": ["九尾PF连击快照(APK#01)"],
}
UNISON_PRE = {"201", "203"}       # UnisonWithMain / OwnerIsUnison
UNISON_TRIG = {"198", "59"}        # 合击触发位 / UnisonMyself
MAIN_ONLY_PRE = {"202"}            # OwnerIsMain


def cell(row, i):
    return row[i].strip() if i < len(row) else ""


class Layout:
    """ability(126)/leader_ability(124)列位,来自 ability_enum_map.json。"""

    def __init__(self, enum_map: dict, kind: str):
        lay = enum_map["layouts"][kind]
        self.blocks = {k: int(v) for k, v in lay["blocks"].items()}
        self.fields = enum_map["block_fields"]
        heads = {note.split(" ")[0]: int(name[1:]) for name, note in lay["head"]}
        self.trigger = heads["trigger"]
        self.awake_kind = heads["awake_kind"]
        self.awake_level = heads["awake_level"]
        self.unisonable = heads.get("unisonable")

    def col(self, block, field):
        base = self.blocks[block]
        key = "precondition" if block.startswith("precondition") else block
        for off, name, _ in self.fields[key]:
            if name == field:
                return base + int(off)
        raise KeyError((block, field))

    def unique_cols(self):
        out = []
        for block in self.blocks:
            key = "precondition" if block.startswith("precondition") else block
            for off, name, _ in self.fields.get(key, []):
                if name == "unique_condition_id":
                    out.append(self.blocks[block] + int(off))
        return out


def walk(value):
    if isinstance(value, list):
        yield value
        for child in value:
            yield from walk(child)
    elif isinstance(value, dict):
        for child in value.values():
            yield from walk(child)


def dsl_facts(tree) -> dict:
    """DSL 树里与机制相关的事实:ACUnique/DCUnique 引用、特效路径、buffTargetAs 转换值、marker。"""
    uniques, effects, bta, cmds = set(), set(), set(), set()
    if isinstance(tree, list) and len(tree) > 10 and tree[0] == "ActionDsl" and isinstance(tree[10], int):
        if tree[10] in BTA_CONVERT:
            bta.add(tree[10])
    for node in walk(tree):
        if not node:
            continue
        head = node[0]
        if isinstance(head, str) and head in DSL_MARKERS:
            cmds.add(head)
        if head in ("ACUnique", "DCUnique") and len(node) > 1 and isinstance(node[1], (int, float)):
            uniques.add(str(int(node[1])))
        elif head == "SpecifyEffectDirectly" and len(node) > 1 and isinstance(node[1], str):
            effects.add(node[1])
        elif head == "CreateHitArea" and len(node) > 24 and isinstance(node[24], int) and node[24] in BTA_CONVERT:
            bta.add(node[24])
        elif head == "Command" and len(node) > 1 and isinstance(node[1], list) and node[1] and isinstance(node[1][0], str):
            cmds.add(node[1][0])
    return {"uniques": uniques, "effects": effects, "bta": bta, "cmds": cmds}


def dsl_logical(path: str) -> str:
    return path if path.endswith(".amf3.deflate") else path + ".action.dsl.amf3.deflate"
