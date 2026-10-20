# -*- coding: utf-8 -*-
"""按源边统计功能涉及的角色、武器和数据表，只读输入。"""
import json
from collections import defaultdict
import content_audit as a


def group(version, name):
    if version in {153, 155, 156, 177, 178, 180, 181} or "gm-weapon6" in name:
        return None
    if 132 <= version <= 149:
        return "主线 Boss 领主战、共同决战与领主武装"
    if 150 <= version <= 152:
        return "诅咒武器 r4、深渊二期、PARADOX"
    if version in {207, 208, 210, 211, 214, 219}:
        return "角色超限 Lv120 与瓦格纳配套修复"
    if version == 209:
        return "赛瑞斯重做、Fever 道具与 PF Lv4"
    if version in {188, 213}:
        return "凉月与能力列修复"
    if version in {189, 190}:
        return "中秋大蛇活动收尾、MOD 卡池迁移"
    if version in {191, 192, 193, 194, 195, 217, 218}:
        return "立绘、UI 图标、语音及图集修复"
    if version == 204:
        return "禁忌星铁魂珠兑换商店"
    if version == 216:
        return "灰碧内容重合整合（冲突保留灰版）"
    if version in {157, 158}:
        return "公共魂珠图集与动画序列修复"
    if version == 131:
        return "皇后像素动画枢轴修复"
    return "角色平衡、基础数值、凯尔终态与运行配套修复"


def main():
    chain, logicals = a.load_chain(), a.get_logicals()
    final_index = {}
    for _, archive in chain:
        with a.zipfile.ZipFile(archive) as z:
            final_index.update({m: archive for m in z.namelist() if not m.endswith("/")})
    characters = a.parse(a.read_index(final_index, a.member("master/character/character.orderedmap")))
    texts = a.parse(a.read_index(final_index, a.member("master/character/character_text.orderedmap")))
    equipment = a.parse(a.read_index(final_index, a.member("master/item/equipment.orderedmap")))
    codes = {a.csvrow(v)[0]: k for k, v in characters.items()}
    index, groups = {}, {}
    for version, archive in chain:
        label = group(version, archive.name)
        info = groups.setdefault(label, {"character_ids": set(), "weapon_ids": set(), "tables": set(), "source_archives": []}) if label else None
        if info is not None:
            info["source_archives"].append(archive.name)
        with a.zipfile.ZipFile(archive) as z:
            for m in z.namelist():
                if m.endswith("/"):
                    continue
                old, new = a.parse(a.read_index(index, m)), a.parse(z.read(m))
                lp = logicals.get(m, "未核实")
                if info is not None:
                    if new is not None:
                        info["tables"].add(lp)
                        for key in set(old or {}) | set(new):
                            if (old or {}).get(key) == new.get(key):
                                continue
                            if lp.startswith("master/ability/") and lp.endswith("ability.orderedmap"):
                                cid = key[:6]
                                if cid in characters:
                                    info["character_ids"].add(cid)
                            elif lp.startswith("master/character/") and key in characters:
                                info["character_ids"].add(key)
                            if (lp in {"master/item/equipment.orderedmap", "master/item/equipment_status.orderedmap",
                                      "master/item/item.orderedmap", "master/ability/ability_soul.orderedmap"}
                                    or lp.startswith("master/equipment_enhancement/")) and key in equipment and key not in {str(i) for i in range(5990001, 5990007)}:
                                info["weapon_ids"].add(key)
                    if lp.startswith("character/"):
                        code = lp.split("/")[1]
                        if code in codes:
                            info["character_ids"].add(codes[code])
                index[m] = archive
    result = []
    for label, info in groups.items():
        result.append({"group": label,
                       "characters": [{"id": k, "name": a.csvrow(texts[k])[0] if k in texts else "未核实",
                                       "leader_ability_name": a.csvrow(characters[k])[18], "code": a.csvrow(characters[k])[0]}
                                      for k in sorted(info["character_ids"])],
                       "weapons": [{"id": k, "name": a.csvrow(equipment[k])[1] if k in equipment else "未核实"}
                                   for k in sorted(info["weapon_ids"])],
                       "tables": sorted(info["tables"]), "source_archives": info["source_archives"]})
    a.dump("function-groups.json", result)
    annex = a.ROOT / "交付/附录"
    annex.mkdir(parents=True, exist_ok=True)
    (annex / "function-groups.json").write_bytes((a.AUDIT / "function-groups.json").read_bytes())
    for info in result:
        print(info["group"], "characters", len(info["characters"]), "weapons", len(info["weapons"]))


if __name__ == "__main__":
    main()
