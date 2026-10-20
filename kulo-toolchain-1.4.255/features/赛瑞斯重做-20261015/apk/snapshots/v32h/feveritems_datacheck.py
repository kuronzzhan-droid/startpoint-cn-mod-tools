"""Fever 道具候选表数据自检（只读 live 视图）。

usage: WF_TIP=206 python feveritems_datacheck.py "fever:items:hp_recovery_small|skill_charge_middle|..."
检查每个键：direct_instant_item 有行且是 Executable(0)、executable_instant_item 有行、executable_instant_item_level 有行、
atk 曲线覆盖 ITEM_LV；并检查 string_id 语法与补丁一致（前两段 fever:items，键用 | 分隔，不含逗号/空白）。
补丁运行时会静默丢弃 direct_instant_item 里不存在的键，但其他三张表缺行会在预载/建道具时崩，所以发布前必须跑这个。
"""
import sys

sys.path.insert(0, r"D:/WF/out/kulo-patch-toolkit/cursed_abyss/build")
from live149 import flat, nested  # noqa: E402

sys.path.insert(0, __file__.rsplit("\\", 1)[0].rsplit("/", 1)[0])
import feveritems_patches as F  # noqa: E402


def check(sid):
    errs = []
    parts = sid.split(F.SID_SEP)
    if len(parts) < 3 or tuple(parts[:2]) != F.SID_TAG:
        return [f"string_id 必须以 {F.SID_TAG[0]}:{F.SID_TAG[1]}: 开头，并带第三段候选表"], []
    if any(c in sid for c in ", \t"):
        errs.append("string_id 不要含逗号或空白")
    keys = [k for k in parts[2].split(F.KEY_SEP) if k]
    dii = flat("master/battle/yakumono/direct_instant_item.orderedmap")
    eii = flat("master/battle/item/executable_instant_item.orderedmap")
    lvl = flat("master/battle/item/executable_instant_item_level.orderedmap")
    curve = nested("master/battle/item/executable_instant_item_atk_curve.orderedmap")
    for k in keys:
        if k.endswith(("_fever", "_always", "_usual")):
            errs.append(f"{k}: 写基键，不要带可用时间后缀（客户端自己拼 _fever）")
        row = dii.get(k)
        if not row:
            errs.append(f"{k}: direct_instant_item 无此行（运行时会被丢弃）")
            continue
        kind, eid = row[0][0], row[0][1]
        if kind != "0":
            errs.append(f"{k}: 不是 Executable 道具（kind={kind}）")
            continue
        if eid not in eii:
            errs.append(f"{k}: executable_instant_item 无 {eid}（会崩）")
        lv = lvl.get(eid)
        if not lv:
            errs.append(f"{k}: executable_instant_item_level 无 {eid}（会崩）")
        else:
            c = curve.get(lv[0][0], {})
            dom = sorted(int(x) for x in c)
            if not dom or not dom[0] <= F.ITEM_LV <= dom[-1]:
                errs.append(f"{k}: atk 曲线 {lv[0][0]} 定义域 {dom[:1]}..{dom[-1:]} 不含 ITEM_LV={F.ITEM_LV}（C14520）")
    return errs, keys


if __name__ == "__main__":
    sid = sys.argv[1]
    errs, keys = check(sid)
    print("keys:", keys)
    print("OK" if not errs else "\n".join("ERROR " + e for e in errs))
    sys.exit(1 if errs else 0)
