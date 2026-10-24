"""Character package primitives and effect family helpers."""
from __future__ import annotations
from .primitives import *
from .context import S7Pack

def clone_effect_family(pack: S7Pack, src_dir: str, dst_subdir: str,
                        fx_names: Iterable[str] | None = None, *, layout: str = "codename",
                        png_transform: Callable[[Any], Any] | None = None,
                        owner: str = "effects") -> dict[str, Any]:
    """把 ``battle/effect/skill_unique/<donor>/`` 复制到新角色命名空间。

    目录形态（记忆卡 wf-effect-family-under-codename + 09-10 更正）：
    - ``layout="codename"``（默认，基诺维先例）：``skill_unique/<code>/<dst_subdir>/``
    - ``layout="sibling"``（奈芙提姆先例）：``skill_unique/<code>_<dst_subdir>/``
    两种形态都满足预载器规则：sheet 必须是 ``<dir>/<dir>.png/.atlas``；atlas ``n`` 与 parts
    ``i[].p`` 的 ``<dir>/.gen/<基名>/<帧>`` 前缀整体改写；parts/timeline 基名保留；timeline 内嵌 SE
    路径原文保留。返回 ``{"prefix_map", "copied_bases", "effects", "missing_effects", "files", …}``。
    kit 改 DSL 引用一律用 :func:`rewrite_effect_refs`（按路径段只改写已复制的基名，并对 dst
    目录下的悬空引用报错）；``prefix_map`` 仅在整族复制且无缺失时非 None。
    """
    src_dir = src_dir.rstrip("/")
    if not src_dir.startswith("battle/effect/"):
        raise S7Error(f"effect family must live under battle/effect/: {src_dir}")
    if not re.fullmatch(r"[a-z0-9][a-z0-9_]*", dst_subdir):
        raise S7Error(f"invalid effect subdir {dst_subdir}")
    donor = src_dir.rsplit("/", 1)[-1]
    code = pack.spec.code
    if layout == "codename":
        dst_dir = f"battle/effect/skill_unique/{code}/{dst_subdir}"
    elif layout == "sibling":
        dst_dir = f"battle/effect/skill_unique/{code}_{dst_subdir}"
    else:
        raise S7Error(f"unknown effect layout {layout}")
    dst_name = dst_dir.rsplit("/", 1)[-1]
    prefix_map = {src_dir + "/": dst_dir + "/"}

    atlas_logical = f"{src_dir}/{donor}.atlas.amf3.deflate"
    sheet_logical = f"{src_dir}/{donor}.png"
    root, atlas_raw, atlas_src = pack.template_asset(atlas_logical)
    atlas = amf_parse(atlas_raw)
    bases = sorted({m.group(1) for item in atlas if isinstance(item, dict)
                    for m in [re.match(re.escape(src_dir) + r"/\.gen/([^/]+)/", str(item.get("n", "")))]
                    if m})
    pathlist = pack.root / "mod-tools/WF_PATHLIST_recovered.txt"
    if pathlist.is_file():
        for line in pathlist.read_text("utf-8").splitlines():
            line = line.strip()
            m = re.fullmatch(re.escape(src_dir) + r"/([^/]+)\.(parts|timeline)\.amf3\.deflate", line)
            if m:
                bases.append(m.group(1))
    wanted = sorted(set(fx_names) if fx_names is not None else set(bases))
    files, effects, missing = [], [], []

    def put(src_logical: str, dst_logical: str, data: bytes, source: str, src_raw: bytes) -> None:
        pack.write_asset(root, dst_logical, data, owner=owner)
        files.append({"source": src_logical, "target": dst_logical, "root": root,
                      "source_sha256": sha256(src_raw), "sha256": sha256(data), "provenance": source})

    new_atlas = replace_strings(atlas, prefix_map)
    atlas_names = {item["n"] for item in new_atlas if isinstance(item, dict) and "n" in item}
    put(atlas_logical, f"{dst_dir}/{dst_name}.atlas.amf3.deflate", amf_bytes(new_atlas),
        atlas_src, atlas_raw)
    _r, sheet_raw, sheet_src = pack.template_asset(sheet_logical)
    sheet_out = sheet_raw
    if png_transform is not None:
        sheet_out = png_store_bytes(png_transform(png_open(sheet_raw)))
    put(sheet_logical, f"{dst_dir}/{dst_name}.png", sheet_out, sheet_src, sheet_raw)
    texture_problems = []
    for base in wanted:
        present = False
        for kind in ("parts", "timeline"):
            logical = f"{src_dir}/{base}.{kind}.amf3.deflate"
            try:
                _root, raw, src = pack.template_asset(logical)
            except FileNotFoundError:
                continue
            present = True
            tree = amf_parse(raw)
            new_tree = replace_strings(tree, prefix_map) if kind == "parts" else tree
            data = raw if new_tree == tree else amf_bytes(new_tree)
            put(logical, f"{dst_dir}/{base}.{kind}.amf3.deflate", data, src, raw)
            if kind == "parts" and isinstance(new_tree, dict):
                refs = {i["p"] for i in new_tree.get("i", []) if isinstance(i, dict) and "p" in i}
                lost = sorted(refs - atlas_names)
                if lost:
                    texture_problems.append({"effect": base, "missing": lost[:10]})
        if present:
            effects.append({"source": f"{src_dir}/{base}", "target": f"{dst_dir}/{base}"})
        else:
            missing.append(base)
    if texture_problems:
        raise S7Error(f"cloned parts reference textures outside atlas: {texture_problems}")
    copied = sorted({e["target"].rsplit("/", 1)[-1] for e in effects})
    complete = fx_names is None and not missing
    result = {"src_dir": src_dir, "dst_dir": dst_dir, "layout": layout, "donor": donor,
              "dst_name": dst_name, "copied_bases": copied, "complete_family": complete,
              # 目录级前缀映射只在整族复制且无缺失时给出；子集复制必须用 rewrite_effect_refs，
              # 否则未复制特效的引用会被改到包内不存在的 dst 路径（进战斗数据不足/C8003）。
              "prefix_map": prefix_map if complete else None,
              "effects": effects, "missing_effects": missing, "files": files}
    registry = pack.read_evidence("effect-families.json", {}) or {}
    registry[dst_dir] = {k: v for k, v in result.items() if k != "files"} | {"file_count": len(files)}
    pack.write_evidence("effect-families.json", dict(sorted(registry.items())))
    return result


_EFFECT_BASE_RE = re.compile(r"(?:\.gen/)?([^/.]+)")


def rewrite_effect_refs(tree, family: Mapping[str, Any], *, strict: bool = False) -> tuple[Any, dict]:
    """按 ``clone_effect_family`` 的结果改写 DSL/任意树里的特效引用（按路径段，不做裸子串替换）。

    - ``<src_dir>/<基名>``（及 ``.parts/.timeline`` 后缀、``.gen/<基名>/`` 帧路径、sheet/atlas 名）
      只有基名在 ``copied_bases``（或是 donor sheet 名）时才改写到 ``<dst_dir>/``；
    - 未复制基名的引用保留原官方路径（跨 code 直接引用官方特效合法），列入 ``kept_donor``；
      ``strict=True`` 时对它们报错；
    - 改写后树里任何 ``<dst_dir>/`` 引用若指向未复制的基名（例如先前用错误前缀映射改过）一律报错。
    返回 ``(新树, {"rewritten": n, "kept_donor": [...]})``；输入树不变。
    """
    src_dir, dst_dir = family["src_dir"].rstrip("/"), family["dst_dir"].rstrip("/")
    copied = set(family.get("copied_bases") or [])
    sheet_names = {family.get("donor"), family.get("dst_name")} - {None}
    kept: set[str] = set()
    dangling: set[str] = set()
    count = 0

    def base_of(rest: str) -> str | None:
        m = _EFFECT_BASE_RE.match(rest)
        return m.group(1) if m else None

    def fix(value: str) -> str:
        nonlocal count
        if value.startswith(src_dir + "/"):
            base = base_of(value[len(src_dir) + 1:])
            if base in copied or base == family.get("donor"):
                rest = value[len(src_dir) + 1:]
                if base == family.get("donor") and base not in copied:
                    rest = rest.replace(family["donor"], family.get("dst_name", family["donor"]), 1)
                count += 1
                return f"{dst_dir}/{rest}"
            kept.add(value)
            return value
        if value.startswith(dst_dir + "/"):
            base = base_of(value[len(dst_dir) + 1:])
            if base not in copied and base not in sheet_names:
                dangling.add(value)
        return value

    def rec(node):
        if isinstance(node, str):
            return fix(node)
        if isinstance(node, list):
            return [rec(item) for item in node]
        if isinstance(node, dict):
            return {rec(k): rec(v) for k, v in node.items()}
        return node

    new_tree = rec(tree)
    if dangling:
        raise S7Error(f"effect refs under {dst_dir} point at bases that were not copied: {sorted(dangling)[:10]}")
    if strict and kept:
        raise S7Error(f"effect refs still point at donor {src_dir} (not copied): {sorted(kept)[:10]}")
    return new_tree, {"rewritten": count, "kept_donor": sorted(kept)}
