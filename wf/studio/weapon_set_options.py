"""Read current view options without hard-coded material identities or labels."""
from wf.boss import schema as s
from wf.boss.reader import BossReader
from wf.boss.shop_model import ITEM, ENH_CATEGORY
from wf.boss.edit_state import BossEditState


def options(source, server_dir=None):
    tables = BossReader(source)
    state = BossEditState(source, server_dir=server_dir)
    inventory = state.server("assets/item_ids.json", required=False) if server_dir is not None else []
    available = state.server_original.get("assets/item_ids.json") is not None
    if available and not isinstance(inventory, list):
        raise ValueError("server item_ids must be a list")
    ids = set(map(str, inventory)) if available else set()
    materials = []
    for path, text in s.iter_leaves(tables.table(ITEM)):
        row = s.parse_rows(text)[0]
        materials.append({"id": path[0], "name": s.cell(row, 2), "icon": s.cell(row, 3),
                          "serverAvailable": path[0] in ids if available else None})
    categories = {}
    for kind, logical in (("enhancement", ENH_CATEGORY), ("exchange", s.SHOP_CATEGORY)):
        categories[kind] = [{"id": path[0], "code": s.cell(row, 0),
            "name": s.cell(row, 3) if kind == "enhancement" else s.cell(row, 0),
            "order": s.cell(row, 1), "row": row, "table": logical}
            for path, text in s.iter_leaves(tables.table(logical)) for row in s.parse_rows(text)]
    products = [{"id": path[0], "categoryId": s.cell(row, 0), "name": s.cell(row, 6),
                 "row": row, "table": s.SHOP}
                for path, text in s.iter_leaves(tables.table(s.SHOP)) for row in s.parse_rows(text)]
    return {"version": source.version, "categories": categories, "materials": materials, "products": products,
            "serverInputAvailable": available, "runtime": "未执行",
            "notes": ["兑换类目没有独立名称列，name 返回原生 code；展示横幅复用母本。",
                      "材料来自当前 item 表，保存时还检查服务端 item_ids 及图集引用。"]}
