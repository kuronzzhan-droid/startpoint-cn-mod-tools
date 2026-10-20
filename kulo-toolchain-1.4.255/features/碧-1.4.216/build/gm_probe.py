exec(open("icon_sheet.py",encoding="utf-8").read().split("CH = {")[0])
for s in ["item/sprite_sheet","item/equipment/sprite_sheet","item/equipment/general/sprite_sheet","item_icon/sprite_sheet","item/item_sprite_sheet"]:
    a=raw(s+".atlas.amf3.deflate"); p=raw(s+".png"); print(s, a is not None, p is not None)
    if a is not None:
        names=[e["n"] for e in wf_dsl.parse_dsl(zlib.decompress(a,-15))["tree"]]; print("  ", len(names), [n for n in names if "sword_0073" in n or "bow_0009" in n][:5], names[:3])
