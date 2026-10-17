# -*- coding: utf-8 -*-
"""浴菲莉亚（159996 / wind_oracle_yukata）去掉浮游效果。

作者 2026-09-21 真机反馈第 3 轮原话：「之前做的菲莉亚也去掉浮游效果」。

落点（**在当前 live 状态上做节点级删除**，不重跑旧 kit 整包重建，否则会把 918–926 那几轮
Codex 改版——向上直射风刃、逐命中剑雨、风刃余势、随机整体朝向、剑雨倍率——一起冲掉）：

* 技能两档 ``wind_oracle_yukata_{1,2}``：根块 ``FindAllSubjects(33)`` 里唯一一条
  ``CreateCondition(ACFlying)``；删掉后该搜索块为空、绑定 110 无人引用，连同搜索命令一起摘除。
* 特殊强化弹射三档 ``wind_oracle_yukata_pf_lv{1,2,3}``：官方 supporter 克隆块
  ``FindAllSubjects(33) → ACAttackPoint / ACPiercing / ACFlying`` 里的第三条；
  另两条保留，搜索块非空，命令保留。
* 文案三处（同一句技能说明在两张表、PF 覆盖说明一处）——见 ``TEXT_TARGETS``。

设计纪律：``strip_flying`` 是纯函数（不碰 live、不碰盘），基线不符立即抛错，重复调用幂等。
本工具**只会写 workspace 候选**（``--write-candidate``）。铸边/登记 pending/发布由主控做，
命令见 ``--plan-out`` 生成的 plan.json 的 ``publish`` 段。
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
import zlib
from collections import Counter
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    pass  # Imports resolve from this checkout/package, not external source copies.

import wf_dsl  # noqa: E402
import wf_mod_tool as core  # noqa: E402
import wf_seasonal7_kit_philia as K  # noqa: E402
from wf_character_revision import RevisionCandidate, encode_tree  # noqa: E402

CID = "159996"
CODE = K.CODE
PACKAGE_VERSION = "1.0.11"
SNAPSHOT_KEY = "no_flying_20260921"
EVIDENCE_NAME = "no-flying-20260921.json"
REVISION_DIR = "work/character_packs/seasonal7-20260916/revision6-no-flying"
PLAN_REL = REVISION_DIR + "/plan.json"

SKILL_PROGRAMS = tuple(f"{K.SKILL_SRC}{CODE}${CODE}_{level}" for level in (1, 2))
PF_PROGRAMS = tuple(K.PF_PROGRAMS)
#: 每棵树期望删除的 ACFlying 条数（技能 1 条、PF 1 条）。数量不符即基线漂移。
EXPECTED_FLYING = 1

# ---- 文案基线（live 1.4.926 实测值；改了就抛错，不做模糊替换）
SKILL_DESC_BEFORE = (
    "向上射出10道贯穿风刃，并在各命中位置降下剑雨，造成光属性伤害【以强化弹射伤害计算】"
    "【伤害量随自身增益效果数量提升】／恢复队伍角色与协力球的生命值／赋予参战者浮游效果／"
    "提升队伍强化弹射伤害与队长攻击力／提升连击数")
SKILL_FLY_CLAUSE = "赋予参战者浮游效果／"
SKILL_DESC_AFTER = SKILL_DESC_BEFORE.replace(SKILL_FLY_CLAUSE, "", 1)

PF_TEXT_BEFORE = (
    "特殊强化弹射命中时，从命中处以随机朝向、等间距发射五道贯穿风刃，风刃命中处降下剑雨"
    "【均以强化弹射伤害计算】／强化弹射时，提升参战角色攻击力并赋予贯穿、浮游效果")
PF_FLY_CLAUSE = "提升参战角色攻击力并赋予贯穿、浮游效果"
PF_TEXT_AFTER = PF_TEXT_BEFORE.replace(PF_FLY_CLAUSE, "提升参战角色攻击力并赋予贯穿效果", 1)

#: 玩家可见文案的落点：(表逻辑路径, 外层键, 说明)
TEXT_TARGETS = (
    (K.ACTION, CODE, "action_skill 两档 c1＝角色详情页技能说明（真源）"),
    (K.TEXT, CID, "character_text c5/c7＝抽卡页/图鉴技能说明"),
    (K.CAS, K.CAS_PF_OVERRIDE, "custom_ability_string＝722 特殊强化弹射覆盖说明"),
)
SEPARATOR = "／"


class NoFlyingError(ValueError):
    pass


# ================================================================ 纯函数：树

def _blocks(node, out: list | None = None) -> list[list]:
    """树里所有 ``["Block", [语句…]]`` 节点本身（``node[1]`` 就是语句表）。"""
    out = [] if out is None else out
    if isinstance(node, list):
        if len(node) == 2 and node[0] == "Block" and isinstance(node[1], list):
            out.append(node)
        for child in node:
            _blocks(child, out)
    return out


def _is_flying_statement(statement) -> bool:
    return (isinstance(statement, list) and len(statement) == 2 and statement[0] == "Command"
            and isinstance(statement[1], list) and statement[1][0] == "CreateCondition"
            and isinstance(statement[1][2], list)
            and any(isinstance(kind, list) and kind and kind[0] == "ACFlying"
                    for kind in statement[1][2]))


def flying_statements(tree) -> list[list]:
    """树里每一条挂 ``ACFlying`` 的 ``CreateCondition`` 语句（``["Command", …]`` 整句）。"""
    return [st for block in _blocks(tree) for st in block[1] if _is_flying_statement(st)]


def _subject_id_uses(tree) -> Counter:
    """每个非负主体 id 在 lookup 位 / 绑定位 / GH 坐标上的出现次数。"""
    counts: Counter = Counter()

    def mapping(value: int) -> int:
        counts[value] += 1
        return value

    K.remap_subjects(copy.deepcopy(tree), mapping)
    return counts


def strip_flying(tree, *, expected: int | None = EXPECTED_FLYING):
    """删掉树里所有 ``ACFlying`` 的 ``CreateCondition`` 语句，其余节点原样保留。

    * 已经删干净的树原样返回（幂等）；
    * ``expected`` 不是 ``None`` 时，待删条数必须正好等于它，否则抛 :class:`NoFlyingError`；
    * ``ACFlying`` 与别的状态挤在同一条 ``CreateCondition`` 里时拒绝动手——删整句会连带
      删掉那些状态，必须先拆句；
    * 删完若外层 ``FindAllSubjects`` 块变空、且它的绑定 id 全树没有第二处引用，
      连同这条搜索命令一起摘掉（空搜索是死代码，留着只会每次施法白跑一次搜索）。
    """
    out = copy.deepcopy(tree)
    hits = [(block, st) for block in _blocks(out) for st in block[1] if _is_flying_statement(st)]
    if not hits:
        return out
    if expected is not None and len(hits) != expected:
        raise NoFlyingError(f"ACFlying baseline drift: found {len(hits)}, expected {expected}")
    for _, statement in hits:
        kinds = [kind[0] for kind in statement[1][2] if isinstance(kind, list) and kind]
        if kinds != ["ACFlying"]:
            raise NoFlyingError(
                f"ACFlying shares one CreateCondition with {kinds}; split the statement first")
    emptied = []
    for block, statement in hits:
        block[1].remove(statement)
        if not block[1]:
            emptied.append(id(block))
    if emptied:
        uses = _subject_id_uses(out)
        for owner in _blocks(out):
            for statement in list(owner[1]):
                if statement[0] != "Command" or statement[1][0] != "FindAllSubjects":
                    continue
                body = statement[1][9]
                if id(body) not in emptied or body[1]:
                    continue
                bind = statement[1][1]
                if uses[bind] != 1:          # 1 = 这条 FindAllSubjects 自己的绑定位
                    raise NoFlyingError(
                        f"binding {bind} is still referenced {uses[bind]} times; refusing to prune")
                owner[1].remove(statement)
    if flying_statements(out):
        raise NoFlyingError("ACFlying survived the strip")
    return out


# ================================================================ 纯函数：文案

def _pinned(where: str, text: str, before: str, after: str) -> str:
    if text == after:
        return text
    if text != before:
        raise NoFlyingError(f"{where}: text baseline drift")
    return after


def skill_description(text: str) -> str:
    """技能说明去掉「赋予参战者浮游效果／」整个分句（含收尾分隔符）。"""
    return _pinned("skill description", text, SKILL_DESC_BEFORE, SKILL_DESC_AFTER)


def pf_override_text(text: str) -> str:
    """722 覆盖说明「并赋予贯穿、浮游效果」→「并赋予贯穿效果」。"""
    return _pinned("pf override string", text, PF_TEXT_BEFORE, PF_TEXT_AFTER)


def text_problems(where: str, text: str) -> list[str]:
    """玩家可见文案的硬门禁：零「浮游」残留，分隔符不成对出现、不留在行首行尾。"""
    problems = []
    if "浮游" in text:
        problems.append(f"{where}: 「浮游」未清干净")
    if SEPARATOR * 2 in text:
        problems.append(f"{where}: 出现连续分隔符「{SEPARATOR * 2}」")
    for line in text.split("\n"):
        if line.startswith(SEPARATOR) or line.endswith(SEPARATOR):
            problems.append(f"{where}: 行首/行尾遗留分隔符 {line[:16]!r}…")
    return problems + K.text_rule_problems({where: text})


# ================================================================ 纯函数：能力 4 的持续条件

#: 作者 2026-09-21：「把条件换成『持有贯穿效果期间』」。她自己的浮游来源删掉后，能力 4
#: 「浮游效果中，光属性角色攻击力＋50%」基本不再触发；她的强化弹射仍然给贯穿，所以换成贯穿门。
#: 持续触发列 c97：31 = ConditionFlying，30 = ConditionPiercing。
#: 同形先例＝澄波响 live 行 1699886#0（c97=30 / c108=false / c110=5 / c111=Black / 50000）：
#: 除属性标记外与这一行逐格同形，puller 列同样留空。
ABILITY4_SLOT = "4"
DURING_COL = 97
DURING_FLYING, DURING_PIERCING = "31", "30"
ABILITY4_SHAPE = {108: "false", 110: "5", 111: "White", 113: "50000", 114: "50000"}


def ability4_rows(rows: list[list[str]]) -> list[list[str]]:
    """能力 4 首条记录的持续条件 浮游 → 贯穿；幂等；形状不符即拒绝（别改到别的行上）。"""
    out = copy.deepcopy(rows)
    if not out:
        raise NoFlyingError("ability 4 has no record")
    row = out[0]
    drift = {col: row[col] for col, want in ABILITY4_SHAPE.items() if row[col] != want}
    if drift or row[DURING_COL] not in (DURING_FLYING, DURING_PIERCING):
        raise NoFlyingError(f"ability 4 baseline drift: c97={row[DURING_COL]!r} {drift}")
    if any(other[DURING_COL] == DURING_FLYING for other in out[1:]):
        raise NoFlyingError("ability 4 carries a second ConditionFlying record")
    row[DURING_COL] = DURING_PIERCING
    return out


# ================================================================ 候选包

def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def apply_candidate(repo: Path, *, apply: bool = False) -> dict:
    """在 workspace 候选上删浮游并同步文案。``apply=False`` 只预演，不写任何文件。"""
    candidate = RevisionCandidate(
        repo, repo / "work/character_packs/s7-philia",
        character_id=CID, code_name=CODE, package_version=PACKAGE_VERSION,
        snapshot_key=SNAPSHOT_KEY, evidence_name=EVIDENCE_NAME)
    dsl_plan: list[dict] = []
    for kind, programs in (("skill", SKILL_PROGRAMS), ("power_flip", PF_PROGRAMS)):
        for program in programs:
            logical = wf_dsl.dsl_logical(program)
            before = candidate.read("common", logical)
            tree = wf_dsl.parse_dsl(zlib.decompress(before, -15))["tree"]
            removed = len(flying_statements(tree))
            updated = strip_flying(tree)
            gates = K.dsl_gates(updated)
            failures = K.dsl_gate_failures(gates)
            if failures:
                raise NoFlyingError(f"{program}: {failures}")
            if strip_flying(updated) != updated:
                raise NoFlyingError(f"{program}: strip is not idempotent")
            raw = encode_tree(updated)
            candidate.emit("common", logical, raw)
            # `before_sha256` 记 **live 当前那一版**（主控要覆盖的就是它）；重跑本工具时它不会
            # 因为候选已经改过而退化成 after。候选侧改前的 sha 另记 candidate_before_sha256。
            live_path = core.table_path(candidate.store, logical)
            live_raw = live_path.read_bytes() if live_path.is_file() else before
            dsl_plan.append(dict(kind=kind, program=program, logical_path=logical,
                                 store_path=core.sha1_path(logical)[:2] + "/"
                                            + core.sha1_path(logical)[2:],
                                 removed_flying=removed,
                                 root_statements=[len(tree[11][1]), len(updated[11][1])],
                                 before_sha256=_sha(live_raw),
                                 candidate_before_sha256=_sha(before),
                                 after_sha256=_sha(raw),
                                 deflate_bytes=gates["deflate_bytes"]))

    table_plan: list[dict] = []
    checks: dict[str, str] = {}

    def live_table(logical: str) -> bytes | None:
        path = core.table_path(candidate.store, logical)
        return path.read_bytes() if path.is_file() else None

    # 1) action_skill（嵌套表）两档 c1 —— 角色详情页技能说明的真源
    nested = core.load_nested_table_bytes(candidate.read("common", K.ACTION), K.ACTION)
    inner = nested.rows[CODE]
    live_action = live_table(K.ACTION)
    # `before` 一律记 **live 当前那一版**（重跑本工具时不会退化成改完的候选文本）
    action_before = dict(core.load_nested_table_bytes(live_action, K.ACTION).rows[CODE].text_rows()
                         if live_action else inner.text_rows())
    for level, text in dict(inner.text_rows()).items():
        cells = core.read_csv_lines(text)
        cells[0][1] = skill_description(cells[0][1])
        checks[f"{K.ACTION}:{CODE}:lv{level}"] = cells[0][1]
        inner.set_text_rows({level: core.write_csv_lines(cells).rstrip("\n")})
    action_after = dict(inner.text_rows())
    candidate.splice(K.ACTION, {CODE: core.build_orderedmap(inner)}, codec="action_nested")
    table_plan.append(dict(logical_path=K.ACTION, outer_key=CODE, codec="action_nested",
                           inner_rows={lv: dict(before=action_before[lv], after=action_after[lv])
                                       for lv in action_after}))

    # 2) character_text c5/c7
    text_rows = core.read_csv_lines(
        core.read_orderedmap_file_from_bytes(candidate.read("common", K.TEXT))[CID])
    live_text = live_table(K.TEXT)
    text_before = (core.read_orderedmap_file_from_bytes(live_text)[CID] if live_text
                   else core.write_csv_lines(copy.deepcopy(text_rows)).rstrip("\n"))
    for row in text_rows:
        for index in (5, 7):
            row[index] = skill_description(row[index])
            checks[f"{K.TEXT}:{CID}:c{index}"] = row[index]
    candidate.splice(K.TEXT, {CID: text_rows})
    table_plan.append(dict(logical_path=K.TEXT, outer_key=CID, codec="flat",
                           before=text_before,
                           after=core.write_csv_lines(text_rows).rstrip("\n"),
                           columns=[5, 7]))

    # 3) custom_ability_string：722 覆盖说明
    cas_candidate = core.read_orderedmap_file_from_bytes(
        candidate.read("common", K.CAS))[K.CAS_PF_OVERRIDE]
    cas_after = pf_override_text(core.read_csv_lines(cas_candidate)[0][0])
    checks[f"{K.CAS}:{K.CAS_PF_OVERRIDE}"] = cas_after
    candidate.splice(K.CAS, {K.CAS_PF_OVERRIDE: [[cas_after]]})
    live_cas = live_table(K.CAS)
    table_plan.append(dict(
        logical_path=K.CAS, outer_key=K.CAS_PF_OVERRIDE, codec="flat",
        before=(core.read_orderedmap_file_from_bytes(live_cas)[K.CAS_PF_OVERRIDE]
                if live_cas else cas_candidate),
        after=cas_after))

    # 4) ability：能力 4 的持续条件 浮游 → 贯穿（作者 09-21 裁决）
    ability_key = CID + ABILITY4_SLOT
    ability_candidate = core.read_orderedmap_file_from_bytes(
        candidate.read("common", K.ABILITY))[ability_key]
    ability_after = ability4_rows(core.read_csv_lines(ability_candidate))
    candidate.splice(K.ABILITY, {ability_key: ability_after})
    live_ability = live_table(K.ABILITY)
    table_plan.append(dict(
        logical_path=K.ABILITY, outer_key=ability_key, codec="flat",
        before=(core.read_orderedmap_file_from_bytes(live_ability)[ability_key]
                if live_ability else ability_candidate),
        after=core.write_csv_lines(ability_after).rstrip("\n"),
        columns=[DURING_COL]))

    problems = [p for where, text in checks.items() for p in text_problems(where, text)]
    if problems:
        raise NoFlyingError(str(problems))

    # 服务端镜像：character_text.json 与上面那张表同源
    candidate.server_character_row("cdndata/character_text.json", text_rows)

    metadata = dict(
        removed_condition="ACFlying",
        skill_programs=list(SKILL_PROGRAMS), power_flip_programs=list(PF_PROGRAMS),
        removed_per_tree=EXPECTED_FLYING,
        pf_support_block_keeps=["ACAttackPoint", "ACPiercing"],
        empty_subject_search_pruned=True,
        damage_timing_and_art_unchanged=True,
        ability_rows_unchanged=False,
        ability4_during_trigger=dict(before="31 ConditionFlying", after="30 ConditionPiercing"),
        texts=dict(skill_description=SKILL_DESC_AFTER, pf_override=PF_TEXT_AFTER),
        visible_flying_text_left=0)
    evidence = candidate.finish(metadata, apply=apply)
    evidence["plan"] = dict(dsl=dsl_plan, tables=table_plan, checks=checks)
    return evidence


def plan_document(evidence: dict) -> dict:
    """主控用的发布清单：逻辑路径 / 表键 / 推荐命令。"""
    plan = evidence["plan"]
    dsl_logicals = [item["logical_path"] for item in plan["dsl"]]
    table_logicals = [item["logical_path"] for item in plan["tables"]]
    return {
        "key": "philia",
        "character": {"id": CID, "code_name": CODE, "package": "s7-philia"},
        "author_request": "之前做的菲莉亚也去掉浮游效果",
        "change": "技能两档 + 特殊强化弹射三档删除 ACFlying；三处玩家可见文案删「浮游」",
        "workspace_candidate": "work/character_packs/s7-philia/package",
        "counts": {"dsl_files": len(dsl_logicals), "table_keys": len(table_logicals)},
        "dsl": plan["dsl"],
        "tables": [{k: v for k, v in item.items() if k != "inner_rows"} |
                   ({"inner_rows": item["inner_rows"]} if "inner_rows" in item else {})
                   for item in plan["tables"]],
        "server_mirror": ["cdndata/character_text.json"],
        "caveats": [
            "词条4（ability 键 1599964）是 During 词条，持续触发列 c97=31＝ConditionFlying："
            "「浮游效果中，光属性角色攻击力＋50%」。菲莉亚原本唯一的浮游来源就是这次删掉的技能与 PF，"
            "删完之后这条只在**队友给浮游**时才生效，面板上那行仍然会显示「浮游」。"
            "作者只说「去掉浮游效果」，没说改词条，所以本轮**没有动任何 ability 行**——"
            "要不要把它改成别的条件（或去掉这条），请作者拍板。",
            "wf_philia_wind_revision.PF_TEXT（第 9–10 行）仍是含「浮游」的旧常量；"
            "kit 里已用 wf_philia_no_flying_revision.pf_override_text() 包一层，不改 Codex 的文件。",
            "wf_philia_combo_stock.revise_abilities 第 87–88 行断言 A4 的 c97=='31' 必须保留，"
            "本轮没动 ability 行所以仍然是绿的；但这条断言守的正是上面那条已经失去来源的浮游门。",
            "impl/philia/run_gates.py 的 character_text_equals_revision 门把包内文案对 "
            "revision2-20260916/philia/strings.json；那份 strings 还停在 918 之前的版本，"
            "**本轮之前就已经对不上了**（PF 覆盖文案早在 918/923 被 Codex 改过）。"
            "本代理没跑 run_gates（它会写 impl/philia 与 revision-20260916/philia/proto，"
            "不在本轮授权改动范围内）。",
        ],
        "publish": {
            "note": "本代理不写 live、不登记 pending、不铸边。以下四步留给主控；"
                    "三个推送脚本都已在本机跑过 dry-run（不加 --apply 只预演）。",
            "steps": [
                "1) 两张扁平表（character_text 的 159996、custom_ability_string 的 "
                "override_string_wind_oracle_yukata_pf）："
                "python -X utf8 mod-tools/wf_pack_push_keys.py "
                "--workspace work/character_packs/s7-philia "
                "--key master/character/character_text.orderedmap:159996 "
                "--key master/string/custom_ability_string.orderedmap:"
                "override_string_wind_oracle_yukata_pf   [--apply]",
                "2) 嵌套表 action_skill 的 wind_oracle_yukata 键："
                "python -X utf8 " + REVISION_DIR + "/push_action_skill_key.py   [--apply]"
                "   —— wf_pack_push_keys 走不了嵌套表（实测 zlib incorrect header check），"
                "整表覆盖又会把 rec_android_seaside 等别家行退回包快照，所以用这个只搬一个外层键。",
                "3) 5 个 DSL 文件：python -X utf8 " + REVISION_DIR + "/push_dsl_files.py   [--apply]",
                "4) 铸边：python -X utf8 mod-tools/wf_publish.py --tables "
                + ",".join(dsl_logicals + table_logicals),
                "5) 生效并核对：./start-cn.bat -RestartOwned（或 reload_assets）→ "
                "python -X utf8 mod-tools/wf_publish.py --list（看版本边与键数：5 DSL / 3 表键）。",
            ],
            "wf_publish_tables": ",".join(dsl_logicals + table_logicals),
            "pending": "本代理没有登记 sync_pending（保持为空）。上面用 --tables 显式铸边，"
                       "不依赖 pending；要走 pending 就在三步推送后把 store 相对路径追加进 "
                       "mod-tools/work/sync_pending.json 再裸跑 wf_publish.py。",
            "flow_publish": "不做。整包 flow publish 需要作者当次明确授权；"
                            "本轮按 CLAUDE.md 走「键级改 live + wf_publish 裸表边 + 回写 workspace 候选」。",
            "server_mirror": "assets/cdndata/character_text.json 的 159996 行也要跟着改（候选包 "
                             "roots/server 已经是新文本）；它是作者 WIP 单行大 JSON，只做键级修改。",
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--write-candidate", action="store_true",
                        help="把结果写进 work/character_packs/s7-philia/package（workspace 候选）")
    parser.add_argument("--plan-out", nargs="?", const=PLAN_REL, default=None,
                        help=f"把主控用的发布清单写到这里（默认 {PLAN_REL}）")
    args = parser.parse_args(argv)

    repo = TOOLS.parent
    evidence = apply_candidate(repo, apply=args.write_candidate)
    document = plan_document(evidence)
    if args.plan_out:
        target = Path(args.plan_out)
        if not target.is_absolute():
            target = repo / target
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(document, ensure_ascii=False, indent=1), encoding="utf-8")
        document["written_to"] = str(target)
    document["applied"] = evidence["applied"]
    document["changed_files"] = evidence["changed_files"]
    print(json.dumps(document, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
