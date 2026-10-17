"""克隆奈芙提姆的角色表与三层镜像；所有文件仅落入候选包。"""
from __future__ import annotations

import json
import re
import sys
import zlib

import wf_campus_nephtim_common as C
import wf_mod_tool as core

CID = str(C.CID)
TMPL = str(C.TMPL_ID)
CODE = C.CODE
TMPL_CODE = C.TMPL_CODE

TEXT = dict(
    name="奈芙提姆", furigana="NAIFUTIMU",
    profile="如今以成年大学生的身份学习现代文明的奈芙提姆。午后，她总会在校园咖啡厅给同伴留一个座位，用珍珠奶茶的甜度记录今天的心情。古代装置化作轻巧的随身终端，守护着这段难得的课余时光。",
    nickname="午后珍珠星光", leader="一起续杯的约定",
    skill1="午后星轨·甜蜜续杯", skill2="午后星轨·甜蜜续杯＋",
    desc1="以星光唤醒随身终端，赋予暗属性角色攻击力提升效果、赋予自身连击效果／赋予队伍贯通效果／向前方释放暗色星轨，对命中的敌人造成暗属性伤害并降低攻击力。",
    desc2="以星光唤醒随身终端，赋予暗属性角色攻击力提升效果、赋予自身连击效果／赋予队伍贯通效果／向前方释放暗色星轨，对命中的敌人造成暗属性伤害并降低攻击力。",
    cv="--",
)

ELEMENT_TOKENS = ("Red", "Blue", "Yellow", "Green", "White", "Black")


def csv_join(rows) -> str:
    return core.write_csv_lines(rows).rstrip("\n")


def write_flat(logical: str, new_rows: dict, root: str = "common"):
    om = core.load_table(logical, C.STORE)
    om.set_text_rows(new_rows)
    C.write_pkg(root, logical, core.build_orderedmap(om))
    return sorted(new_rows)


def _clone_blob(blob: bytes, remap) -> bytes:
    try:
        text = zlib.decompress(blob).decode("utf-8")
    except Exception:
        pass
    else:
        rows = core.read_csv_lines(text)
        for cells in rows:
            for i, cell in enumerate(cells):
                cells[i] = remap(cell)
        return zlib.compress(core.write_csv_lines(rows).rstrip("\n").encode("utf-8"))
    inner = core.read_orderedmap_raw_rows_from_bytes(blob, "nested")
    rebuilt = core.OrderedMap("nested", [remap(k) for k in inner.keys],
                              [_clone_blob(r, remap) for r in inner.rows], C.STORE)
    return core.build_orderedmap_raw_rows(rebuilt)


def clone_raw_outer(logical: str, src: str, dst: str, remap, root="common") -> None:
    om = core.read_orderedmap_file_raw_rows(C.addr(logical), logical)
    table = dict(zip(om.keys, om.rows))
    if src not in table:
        raise SystemExit("母本缺行 %s: %s" % (src, logical))
    blob = _clone_blob(table[src], remap)
    if dst in om.keys:
        om.rows[om.keys.index(dst)] = blob
    else:
        om.keys.append(dst)
        om.rows.append(blob)
    C.write_pkg(root, logical, core.build_orderedmap_raw_rows(om))


def identity(cell: str) -> str:
    return cell


def character_row():
    _k, rows = C.load_flat("master/character/character.orderedmap")
    row = C.csv_split(rows[TMPL])[0][:]
    assert len(row) == 37, len(row)
    row[0] = CODE                       # code_name
    row[2] = str(C.RARITY)              # ★5（母本已是 5，显式写死）
    row[3] = str(C.ELEMENT)             # 元素 1 = 水（母本同元素）
    row[8] = CODE                       # action_skill 外层键
    row[17] = CID
    row[18] = TEXT["leader"]
    for i in range(6):
        row[19 + i] = "%s%d" % (CID, i + 1)
    row[27] = CID                       # 系列本体 = 自己
    return row


def character_text_row():
    t = TEXT
    return [t["name"], t["furigana"], t["profile"], t["nickname"],
            t["skill1"], t["desc1"], t["skill2"], t["desc2"],
            "(None)", "(None)", t["leader"], t["cv"]]


def speech_placeholder() -> str:
    lg = "master/character/character_speech.orderedmap"
    om = core.read_orderedmap_file_raw_rows(C.addr(lg), lg)
    blob = dict(zip(om.keys, om.rows))[TMPL]
    rows = core.read_csv_lines(zlib.decompress(blob).decode("utf-8"))
    for cells in rows:
        assert len(cells) == 5, cells
        cells[4] = cells[4].replace(f"character/{TMPL_CODE}/", f"character/{CODE}/")
    return csv_join(rows)


def build():
    live_characters = C.load_flat('master/character/character.orderedmap')[1]
    live_abilities = C.load_flat('master/ability/ability.orderedmap')[1]
    live_leaders = C.load_flat('master/ability/leader_ability.orderedmap')[1]
    if CID in live_characters or CID in live_leaders:
        raise ValueError(f'角色或队长键已被生产数据占用: {CID}')
    if any(CODE == C.csv_split(text)[0][0] for text in live_characters.values()):
        raise ValueError(f'生产角色 code 已占用: {CODE}')
    if any(f'{CID}{slot}' in live_abilities for slot in range(1, 7)):
        raise ValueError('新角色能力键已被生产数据占用')
    claims = []
    cloned_text = {}   # 供元素 token 扫描 / 复核

    def claim(logical, keys, codec="flat", root="common", inner=None):
        claims.append({"codec_id": codec, "inner_keys": inner or [],
                       "logical_path": logical, "outer_keys": sorted(keys),
                       "root": root, "semantic_claims": []})

    crow = character_row()
    cloned_text["character"] = crow
    claim("master/character/character.orderedmap",
          write_flat("master/character/character.orderedmap",
                     {CID: csv_join([crow])}))
    trow = character_text_row()
    claim("master/character/character_text.orderedmap",
          write_flat("master/character/character_text.orderedmap",
                     {CID: csv_join([trow])}))

    claim("master/character/character_awake_status.orderedmap",
          write_flat("master/character/character_awake_status.orderedmap",
                     {CID: C.load_flat("master/character/character_awake_status.orderedmap")[1].get(TMPL, "0,0")}))

    for logical in ("master/character/character_status.orderedmap",
                    "master/character/character_gacha_sound.orderedmap",
                    "master/generated/character_image.orderedmap",
                    "master/character/full_shot_image_attribute.orderedmap"):
        clone_raw_outer(logical, TMPL, CID, identity)
        claim(logical, [CID], codec="raw_outer")

    lg = "master/generated/trimmed_image.orderedmap"
    _k, rows = C.load_flat(lg)
    trimmed = {}
    for stem in ("full_shot_1440_1920_0", "full_shot_1440_1920_1",
                 "skill_cutin_0", "skill_cutin_1"):
        src = "character/%s/ui/%s" % (TMPL_CODE, stem)
        trimmed["character/%s/ui/%s" % (CODE, stem)] = rows[src]
    claim(lg, write_flat(lg, dict(sorted(trimmed.items()))))

    old_pref, new_pref = str(C.TMPL_ID * 2), str(C.CID * 2)
    token = re.compile(r"^%s(\d{3})$" % re.escape(old_pref))

    def mana_remap(cell: str) -> str:
        m = token.match(cell)
        return new_pref + m.group(1) if m else cell

    for logical in ("master/generated/mana_board.orderedmap",
                    "master/mana_board/mana_node.orderedmap"):
        clone_raw_outer(logical, TMPL, CID, mana_remap)
        claim(logical, [CID], codec="raw_outer")

    for logical in ("master/mana_board/upskill.orderedmap",
                    "master/mana_board/mana_board2_open_condition.orderedmap",
                    "master/skill_preview/skill_preview_character.orderedmap",
                    "master/stance_detail/character_stance_detail.orderedmap"):
        _k, rows = C.load_flat(logical)
        claim(logical, write_flat(logical, {CID: rows[TMPL].replace(TMPL_CODE, CODE)}))
        cloned_text[logical.rsplit("/", 1)[-1]] = C.csv_split(rows[TMPL])[0]

    claim("master/character/character_speech.orderedmap",
          write_flat("master/character/character_speech.orderedmap",
                     {CID: speech_placeholder()}))

    code_token = re.compile(r"^%s(_\d+)?$" % re.escape(TMPL_CODE))

    def kit_remap(cell: str) -> str:
        m = code_token.match(cell)
        if m:
            return CODE + (m.group(1) or "")
        return cell

    lg = "master/ability/ability.orderedmap"
    _k, rows = C.load_flat(lg)
    ab_new = {}
    for i in range(1, 7):
        src = "%s%d" % (TMPL, i)
        cells = [[kit_remap(c) for c in line] for line in C.csv_split(rows[src])]
        ab_new["%s%d" % (CID, i)] = csv_join(cells)
        cloned_text["ability%d" % i] = cells
    claim(lg, write_flat(lg, ab_new))

    lg = "master/ability/leader_ability.orderedmap"
    _k, rows = C.load_flat(lg)
    cells = [[kit_remap(c) for c in line] for line in C.csv_split(rows[TMPL])]
    cloned_text["leader_ability"] = cells
    claim(lg, write_flat(lg, {CID: csv_join(cells)}))

    lg = "master/skill/action_skill.orderedmap"
    nested = core.load_nested_table(lg, C.STORE)
    src_inner = nested.rows[TMPL_CODE]
    src_rows = src_inner.text_rows()
    inner_rows = {}
    for key in src_inner.keys:
        cells = C.csv_split(src_rows[key])[0][:]
        cells[0] = TEXT["skill1"] if key == "1" else TEXT["skill2"]
        cells[1] = TEXT["desc1"] if key == "1" else TEXT["desc2"]
        cells[7] = "battle/action/skill/action/rare5/%s$%s_%s" % (CODE, CODE, key)
        inner_rows[key] = csv_join([cells])
        cloned_text["action_skill_%s" % key] = [cells]
    nested.rows[CODE] = core.OrderedMap(
        "%s#%s" % (lg, CODE), list(inner_rows),
        [v.encode("utf-8") for v in inner_rows.values()], C.addr(lg))
    C.write_pkg("common", lg, core.build_nested_table(nested, lg))
    claim(lg, [CODE], codec="action_nested",
          inner=[{"keys": list(inner_rows), "outer_key": CODE}])

    assets = C.ROOT / "assets"
    j = json.loads((assets / "cdndata/character.json").read_text("utf-8"))
    j[CID] = [crow]
    C.write_pkg("server", "cdndata/character.json",
                json.dumps(j, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))

    j = json.loads((assets / "cdndata/character_text.json").read_text("utf-8"))
    j[CID] = [trow]
    C.write_pkg("server", "cdndata/character_text.json",
                json.dumps(j, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))

    j = json.loads((assets / "character.json").read_text("utf-8"))
    j[CID] = {"element": C.ELEMENT, "name": TEXT["name"],
              "rarity": C.RARITY, "skill_count": 6}
    C.write_pkg("server", "character.json",
                json.dumps(j, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))

    j = json.loads((assets / "mana_node.json").read_text("utf-8"))
    j[CID] = {board: {new_pref + nid[len(old_pref):]: dict(node)
                      for nid, node in nodes.items()}
              for board, nodes in j[TMPL].items()}
    C.write_pkg("server", "mana_node.json",
                json.dumps(j, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))

    j = json.loads((assets / "mana_board.json").read_text("utf-8"))
    j[CID] = {board: {nid: [[mana_remap(cell) for cell in row] for row in node]
                      for nid, node in nodes.items()}
              for board, nodes in j[TMPL].items()}
    C.write_pkg("server", "mana_board.json", json.dumps(j, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    for logical in ("cdndata/character.json", "cdndata/character_text.json",
                    "character.json", "mana_node.json", "mana_board.json"):
        claim(logical, [CID], codec="json_object", root="server")

    C.EVIDENCE.mkdir(parents=True, exist_ok=True)
    (C.EVIDENCE / "table_claims.json").write_text(
        json.dumps(claims, ensure_ascii=False, indent=1), encoding="utf-8")
    (C.EVIDENCE / "cloned_cells.json").write_text(
        json.dumps(cloned_text, ensure_ascii=False, indent=1), encoding="utf-8")
    return claims


if __name__ == "__main__":
    cl = build()
    print("== 落表 %d 张" % len(cl))
    for e in cl:
        keys = e["outer_keys"]
        shown = keys if len(keys) < 7 else "%d键" % len(keys)
        print("   %-7s %-13s %s  keys=%s"
              % (e["root"], e["codec_id"], e["logical_path"], shown))
