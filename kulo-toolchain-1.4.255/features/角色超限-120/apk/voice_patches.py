"""通用「技能准备语音轮换」APK 方法补丁（可重放，叠在 v32l 之上；框架 = perf-v30 的 perf2_core）。

规则：任何角色只要有 `<技能准备路径>_alt_1`、`_alt_2`…（最多 5 条，遇缺号停），
  技能准备语音按「原句 → alt_1 → alt_2 → … → 原句」轮流播放；战斗预载与语音图鉴同步带上这些文件。
  原句 = 引擎本来要播的那条（skill_ready 或 matched_skill_ready），所以形态切换角色也成立。
  已写死轮换的 5 个角色（夏日白 149990、玫瑰独角兽 129992、燕尾服 139993、斩铁 159998、杰拉德 149999）
  走原逻辑，这里整块跳过。

V1 HudMemberStatus/update                         轮换（复用 geraldReadyNext 计数器，对非写死角色它本来闲置）
V2 BattleCharacterLogic/resolveFollowingPathCollection  预载 alt
V3 CharacterVoiceLogic/createVoicePathMap         语音图鉴列出 alt
只用主 ABC 已有的常量池项（"_alt_1".substr(0,5) 得到 "_alt_"），不追加。
"""
from __future__ import annotations

import sys

sys.path.insert(0, r"D:/WF/perf-v30-20261015/tools")
from common import asm  # noqa: E402
from perf2_core import MAIN, Refused, splice_with_exits  # noqa: E402

# 本地栈模拟器缺 0xEF(debug,无栈效果)；只在本进程补上，不改共享工具
asm._POP_PUSH.setdefault(0xEF, (0, 0))

MAX_ALT = 5
SKIP_CODES = ("white_tiger_summer", "unicorn_lancer_rose", "super_robot_tailcoat", "samurai_robot_plum",
              "white_wolf_gerald")
SKIP_IDS = (149990, 129992, 139993, 159998, 149999)


def _require(cond, what):
    if not cond:
        raise Refused(what)


def _arg(abc, code, opname, name, nth=0):
    """方法体里第 nth 个 opname 且操作数名为 name 的指令的第一个操作数（多名/字符串/整数池下标）。"""
    hits = []
    for ins in code:
        if ins.name != opname:
            continue
        if opname == "pushstring":
            label = abc.strings[ins.args[0]].decode()
        elif opname == "pushint":
            label = abc.ints[ins.args[0]]
        else:
            label = abc.mn_name(ins.args[0])
        if label == name:
            hits.append(ins.args[0])
    _require(len(hits) > nth, f"{opname} {name!r} not found in body")
    return hits[nth]


def _present(abc, code, opname, values):
    """写死名单里本包实际出现的那些（旧包可能少几个角色，少的就走通用逻辑）。"""
    out = []
    for v in values:
        try:
            out.append(_arg(abc, code, opname, v))
        except Refused:
            pass
    return out


def _find(code, pred, what):
    hits = [i for i in range(len(code)) if pred(i)]
    _require(len(hits) == 1, f"{what}: {len(hits)} matches")
    return hits[0]


def _alt_prefix(base_src, m_substr, s_alt1):
    """栈上压入 String(base) + "_alt_1".substr(0,5)  → "<base>_alt_" 。base_src = 压 base 的指令列表。"""
    return base_src + [("coerce_s",), ("pushstring", s_alt1), ("pushbyte", 0), ("pushbyte", 5),
                       ("callproperty", m_substr, 2), ("add",), ("coerce_s",)]


# --------------------------------------------------------------------------------------------- V1
def v1_apply(abc, index, pool):
    body = abc.bodies[index]
    _require(body[1:5] == [7, 5, 1, 2] and not body[6] and not body[7], "HudMemberStatus/update header")
    code = asm.decode(body[5])
    V1_AT = _find(code, lambda i: code[i].name == "getlocal" and list(code[i].args) == [4]
                  and i + 2 < len(code) and code[i + 1].name == "getproperty"
                  and abc.mn_name(code[i + 1].args[0]) == "index" and code[i + 2].name == "lookupswitch", "V1 point")
    at = code[V1_AT]
    _require(at.name == "getlocal" and list(at.args) == [4] and code[V1_AT + 1].name == "getproperty"
             and abc.mn_name(code[V1_AT + 1].args[0]) == "index" and code[V1_AT + 2].name == "lookupswitch",
             "V1 insertion point shape")
    m_index = code[V1_AT + 1].args[0]
    m_params = _arg(abc, code, "getproperty", "params")
    m_idx = next(i.args[0] for i in code if i.name == "getproperty" and abc.multinames[i.args[0]][0] == 0x1B)
    m_char = _arg(abc, code, "getproperty", "character")
    m_csid = _arg(abc, code, "getproperty", "mainCharacterStringId")
    m_logic = _arg(abc, code, "getproperty", "logic")
    m_assets = _arg(abc, code, "getproperty", "logicAssets")
    m_exists = _arg(abc, code, "callproperty", "pinball.asset.logic:ILogicAssetContainer::existsVoiceFileReader")
    m_next = _arg(abc, code, "getproperty", "geraldReadyNext")
    m_next_set = _arg(abc, code, "setproperty", "geraldReadyNext")
    m_option = _arg(abc, code, "getlex", "haxe.ds::Option")
    m_some = _arg(abc, code, "callproperty", "Some")
    m_coerce_opt = _arg(abc, code, "coerce", "haxe.ds::Option")
    m_substr = pool.find("substr", 0x07)
    s_alt1 = _arg(abc, code, "pushstring", "_alt_1")
    skip = _present(abc, code, "pushstring", SKIP_CODES)
    src = [("getlocal", 4), ("getproperty", m_index), ("pushbyte", 0), ("ifne", "END"),
           ("getlocal_0",), ("getproperty", m_char), ("getproperty", m_csid), ("coerce_s",), ("setlocal", 5)]
    for s in skip:
        src += [("getlocal", 5), ("pushstring", s), ("ifeq", "END")]
    # local6 = "<原句>_alt_"；local7 = 计数器
    src += _alt_prefix([("getlocal", 4), ("getproperty", m_params), ("pushbyte", 0), ("getproperty", m_idx)],
                       m_substr, s_alt1) + [("setlocal", 6)]
    src += [("getlocal_0",), ("getproperty", m_next), ("convert_i",), ("setlocal", 7),
            ("getlocal", 7), ("pushbyte", 0), ("ifgt", "TRY"),
            # 计数器 0：本次播原句，下次试 alt_1
            ("getlocal_0",), ("pushbyte", 1), ("setproperty", m_next_set), ("jump", "END"),
            ("label", "TRY"),
            ("getlocal", 6), ("getlocal", 7), ("add",), ("coerce_s",), ("setlocal", 6),
            ("getlocal_0",), ("getproperty", m_char), ("getproperty", m_logic), ("getproperty", m_assets),
            ("getlocal", 6), ("callproperty", m_exists, 1), ("iffalse", "WRAP"),
            ("getlex", m_option), ("getlocal", 6), ("callproperty", m_some, 1), ("coerce", m_coerce_opt),
            ("setlocal", 4),
            ("getlocal_0",), ("getlocal", 7), ("increment_i",), ("setproperty", m_next_set), ("jump", "END"),
            ("label", "WRAP"),
            # alt_k 不存在：本次播原句，下次再从 alt_1 开始
            ("getlocal_0",), ("pushbyte", 1), ("setproperty", m_next_set)]
    code2, exc, merged, n = splice_with_exits(body, V1_AT, src, {}, incoming=asm.ENTER)
    body[1:5] = [7, 8, 1, 2]
    body[5] = code2
    return {"inserted_at": V1_AT, "inserted": n}


# --------------------------------------------------------------------------------------------- V2
def v2_apply(abc, index, pool):
    body = abc.bodies[index]
    _require(body[1:5] == [3, 12, 6, 7] and not body[6] and not body[7], "resolveFollowingPathCollection header")
    code = asm.decode(body[5])
    V2_AT = _find(code, lambda i: code[i].name == "getlocal" and list(code[i].args) == [5] and i + 1 < len(code)
                  and code[i + 1].name == "callproperty"
                  and abc.mn_name(code[i + 1].args[0]) == "get_powerFlipVoicePaths", "V2 point")
    _require(code[V2_AT].name == "getlocal" and list(code[V2_AT].args) == [5] and code[V2_AT + 1].name == "callproperty"
             and abc.mn_name(code[V2_AT + 1].args[0]) == "get_powerFlipVoicePaths", "V2 insertion point shape")
    m_plays = _arg(abc, code, "getproperty", "playsSkillReady")
    m_cid = _arg(abc, code, "getproperty", "characterId")
    m_assets = _arg(abc, code, "getproperty", "logicAssets")
    m_exists = _arg(abc, code, "callproperty", "pinball.asset.logic:ILogicAssetContainer::existsVoiceFileReader")
    m_add = _arg(abc, code, "callpropvoid", "pinball.asset.logic:IAssetPathCollectionBuilder::addSoundEffect")
    m_ready = _arg(abc, code, "callproperty", "get_skillReadyVoicePath")
    m_switched = _arg(abc, code, "callproperty", "get_switchedSkillReadyVoicePath")
    m_index = _arg(abc, code, "getproperty", "index")
    m_params = _arg(abc, code, "getproperty", "params")
    m_idx = next(i.args[0] for i in code if i.name == "getproperty" and abc.multinames[i.args[0]][0] == 0x1B)
    m_substr = pool.find("substr", 0x07)
    s_alt1 = pool.string("_alt_1")
    ints = _present(abc, code, "pushint", SKIP_IDS)
    src = [("getlocal_3",), ("getproperty", m_plays), ("iffalse", "END"),
           ("getlocal", 5), ("getproperty", m_cid), ("convert_i",), ("setlocal", 13)]
    for i in ints:
        src += [("getlocal", 13), ("pushint", i), ("ifeq", "END")]
    for tag, getter in (("R", m_ready), ("S", m_switched)):
        src += [("getlocal", 5), ("callproperty", getter, 0), ("coerce_a",), ("setlocal", 12),
                ("getlocal", 12), ("getproperty", m_index), ("pushbyte", 0), ("ifne", f"NEXT_{tag}")]
        src += _alt_prefix([("getlocal", 12), ("getproperty", m_params), ("pushbyte", 0), ("getproperty", m_idx)],
                           m_substr, s_alt1) + [("setlocal", 12)]
        for k in range(1, MAX_ALT + 1):
            src += [("getlocal", 5), ("getproperty", m_assets),
                    ("getlocal", 12), ("pushbyte", k), ("add",), ("coerce_s",),
                    ("callproperty", m_exists, 1), ("iffalse", f"NEXT_{tag}"),
                    ("getlocal_1",), ("getlocal", 12), ("pushbyte", k), ("add",), ("coerce_s",),
                    ("callpropvoid", m_add, 1)]
        src += [("label", f"NEXT_{tag}")]
    code2, exc, merged, n = splice_with_exits(body, V2_AT, src, {}, incoming=asm.ENTER)
    body[1:5] = [4, 14, 6, 7]
    body[5] = code2
    return {"inserted_at": V2_AT, "inserted": n}


# --------------------------------------------------------------------------------------------- V3
def v3_apply(abc, index, pool):
    body = abc.bodies[index]
    _require(body[1:5] == [4, 36, 1, 2] and not body[6] and not body[7], "createVoicePathMap header")
    code = asm.decode(body[5])
    # 技能准备列表 local21 建好之后、转成 UI 条目之前：第一个紧跟着读 local21 循环的 toPathWithEnabledByPath
    V3_AT = _find(code, lambda i: code[i].name == "findproperty"
                  and abc.mn_name(code[i].args[0]) == "toPathWithEnabledByPath"
                  and any(c.name == "getlocal" and list(c.args) == [21] for c in code[i:i + 16]), "V3 point")
    _require(code[V3_AT].name == "findproperty" and abc.mn_name(code[V3_AT].args[0]) == "toPathWithEnabledByPath"
             , "V3 insertion point shape")
    m_cid = _arg(abc, code, "getproperty", "characterId")
    m_assets = _arg(abc, code, "getproperty", "logicAssets")
    m_exists = _arg(abc, code, "callproperty", "pinball.asset.logic:ILogicAssetContainer::existsVoiceFileReader")
    m_push = _arg(abc, code, "callpropvoid", "http://adobe.com/AS3/2006/builtin::push")
    m_len = _arg(abc, code, "getproperty", "length")
    m_idx = next(i.args[0] for i in code if i.name == "getproperty" and abc.multinames[i.args[0]][0] == 0x1B)
    m_substr = pool.find("substr", 0x07)
    s_alt1 = pool.string("_alt_1")
    ints = _present(abc, code, "pushint", [v for v in SKIP_IDS if v != 149990])   # 图鉴原本就不含夏日白，通用补上
    src = [("getlocal_2",), ("getproperty", m_cid), ("convert_i",), ("setlocal", 36)]
    for i in ints:
        src += [("getlocal", 36), ("pushint", i), ("ifeq", "END")]
    src += [("getlocal", 21), ("getproperty", m_len), ("convert_i",), ("setlocal", 37)]   # 原句条数（≤2）
    for slot in (0, 1):
        src += [("getlocal", 37), ("pushbyte", slot), ("ifle", "END" if slot == 1 else "SKIP0")]
        src += _alt_prefix([("getlocal", 21), ("pushbyte", slot), ("getproperty", m_idx)], m_substr, s_alt1) \
            + [("setlocal", 38)]
        for k in range(1, MAX_ALT + 1):
            src += [("getlocal_2",), ("getproperty", m_assets),
                    ("getlocal", 38), ("pushbyte", k), ("add",), ("coerce_s",),
                    ("callproperty", m_exists, 1), ("iffalse", f"DONE{slot}"),
                    ("getlocal", 21), ("getlocal", 38), ("pushbyte", k), ("add",), ("coerce_s",),
                    ("callpropvoid", m_push, 1)]
        src += [("label", f"DONE{slot}")]
        if slot == 0:
            src += [("label", "SKIP0")]
    code2, exc, merged, n = splice_with_exits(body, V3_AT, src, {}, incoming=asm.ENTER)
    body[1:5] = [5, 39, 1, 2]
    body[5] = code2
    return {"inserted_at": V3_AT, "inserted": n}


LABELS = {"V1": ("HudMemberStatus/update", v1_apply),
          "V2": ("BattleCharacterLogic/resolveFollowingPathCollection", v2_apply),
          "V3": ("CharacterVoiceLogic/createVoicePathMap", v3_apply)}
# 每个已知底包一套 (before, after)；底包对不上任何一套 = 拒绝
VARIANTS = {
    "v32l": {"V1": ("d1ddeb0c1a7caade26c944642aff465b4be527d950aa5690fb334e2891990cbd",
                    "7858113b678d100259739c4716f0729c9f3dfc75498fd101efc37f9dbaf9e50c"),
             "V2": ("88aab37aa2caebb4436b4c97a1bdf03c6b48b0f01632b6e832ff34df86ef197c",
                    "d8d6141c41bcb2d9290f8cfcfe71d5618e65127a8bab1129779fe30b6924e8ea"),
             "V3": ("3db83e046bac5776fe9ca3ee12f5ce37517edfd03e43cd8ddd7a43cd3b8a0757",
                    "a3f3aa721b20af0547543fb26a0ab4227104248b6aee01289e66fea765dc14d7")},
    "local32l": {"V1": ("6e9410cdab300775dd5a584703a539c314237bebe12650a20cb06858d09486e7",
                        "03af2d0e51f167bdfbddbc63024eab857ff51ff843c15986afb545237a31f7f2"),
                 "V2": ("be6b2b0efb10cabf980c3a8ae39b0b80faf23dbc7b77788a248015603e79fee1",
                        "a0821604e1bf62cdcad4ae2a909d888d6b0623f8d96623b6bd6805f283312675"),
                 "V3": ("76793ea193c635de4becc8523969103cdde63ae98777db6431d13b8878b6005f",
                        "805998e36e1a816701aa8b751aa40aa88e195afd0b78c32aca649a6a235a2015")},
}


def patches(variant):
    return [{"id": k, "tag": MAIN, "label": LABELS[k][0], "before": b, "after": a, "apply": LABELS[k][1]}
            for k, (b, a) in VARIANTS[variant].items()]


PATCHES = patches("v32l")
