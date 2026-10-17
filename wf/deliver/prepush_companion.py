"""道具伴随表检查。"""
from __future__ import annotations

from .prepush_base import *

ITEM = "master/item/item.orderedmap"
ITEM_QUEST_SEARCH = "master/search/item_quest_search.orderedmap"
EII = "master/battle/item/executable_instant_item.orderedmap"
EII_LEVEL = "master/battle/item/executable_instant_item_level.orderedmap"


def check_companion(args, view: View, old: View | None, rep: Report, allow_iqs: set[str]):
    items = view.table(ITEM)
    if items is None:
        rep.add("WARN", "companion", "companion.item.skipped", "视图里没有 item 表,道具伴随检查跳过")
    else:
        old_items = set(old.table(ITEM) or {}) if old is not None else None
        def is_new(k):
            return old_items is not None and k not in old_items
        ids_path = args.server_dir / "assets" / "item_ids.json"
        if ids_path.is_file():
            ids = {str(x) for x in json.loads(ids_path.read_text("utf-8"))}
            for k in sorted(set(items) - ids, key=lambda s: (len(s), s)):
                name = row(items[k])[2] if isinstance(items[k], str) and len(row(items[k])) > 2 else ""
                rep.add("ERROR" if (is_new(k) or old_items is None) else "WARN", "companion",
                        f"companion.item_ids:{k}",
                        f"道具 {k}({name})在客户端 item 表里,但不在服务端 assets/item_ids.json")
        iqs = view.table(ITEM_QUEST_SEARCH)
        if iqs is not None and old_items is not None:
            for k in sorted(set(items) - set(iqs) - old_items - allow_iqs, key=lambda s: (len(s), s)):
                name = row(items[k])[2] if isinstance(items[k], str) and len(row(items[k])) > 2 else ""
                rep.add("WARN", "companion", f"companion.item_quest_search:{k}",
                        f"新道具 {k}({name})没有 item_quest_search 行(获取途径页空白)")
        elif iqs is not None and args.custom_item_min is not None:
            for k in sorted(set(items) - set(iqs) - allow_iqs, key=lambda s: (len(s), s)):
                if k.isdigit() and int(k) >= args.custom_item_min:
                    name = row(items[k])[2] if isinstance(items[k], str) and len(row(items[k])) > 2 else ""
                    rep.add("WARN", "companion", f"companion.item_quest_search:{k}",
                            f"自制道具 {k}({name})没有 item_quest_search 行(获取途径页空白)")
    eii, lvl = view.table(EII), view.table(EII_LEVEL)
    if eii is None or lvl is None:
        rep.notes.append("executable_instant_item(_level) 不在视图里,C8601 检查跳过")
    else:
        for k in sorted(set(eii) - set(lvl)):
            rep.add("ERROR", "companion", f"companion.eii_level:{k}",
                    f"即时道具 {k} 没有 executable_instant_item_level 行(C8601)")


