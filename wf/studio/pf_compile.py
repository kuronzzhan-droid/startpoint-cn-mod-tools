"""Replay PF drafts into the normal studio delivery member set."""
from __future__ import annotations

import csv
import io
from pathlib import Path
import zlib

import wf_mod_tool as core
from wf.dsl.references import DSL_SUFFIX, linked_programs
from .deliver_media import encode_tree, tree as decode_tree
from .drafts import DraftError, sha256, validate
from .pf_catalog import PfCatalog, PF_TABLE, decode_program
from .pf_dsl import ELEMENTS, effects_map, remap, summary, transform


def vacant(source, store, catalog, key, *, owner=None):
    from .ids import canonical, check_id
    canonical("power_flip_action", key)
    if key in catalog.keys:
        raise DraftError("PF 新键已被 CDN 或 APK 内置表占用：" + key)
    result = check_id(source, "power_flip_action", key, drafts_root=store.root)
    conflicts = [o for o in result["owners"] if not (owner is not None and o["source"] == "draft"
                                                    and o["owner"] == owner)]
    if conflicts:
        raise DraftError("PF 新键已被其他草稿预留：" + key)


def _programs(catalog, donor, spec):
    scales = spec["scale"] if isinstance(spec["scale"], list) else [spec["scale"]] * 3
    effects = effects_map(spec.get("effects", {}))
    members, trees, levels, paths, matched = {}, {}, [], [], set()
    for level, (original, root_tree, scale) in enumerate(zip(donor["row"], donor["trees"], scales), 1):
        prefix = f"battle/action/power_flip/studio/{spec['key']}$lv{level}"
        root_logical = original.removesuffix(DSL_SUFFIX) + DSL_SUFFIX
        mapping = {root_logical: prefix + DSL_SUFFIX}
        originals = {}

        def visit(logical, value=None):
            if logical in originals:
                return
            if len(originals) >= 256:
                raise DraftError("PF 子程序图超过 256 个节点")
            if value is None:
                raw = catalog.read(logical)
                if raw is None:
                    raise DraftError("PF 子程序缺失：" + logical)
                value = decode_program(raw, logical)
            originals[logical] = value
            for linked in sorted(linked_programs(value)):
                mapping.setdefault(linked, prefix + "_sub_" + sha256(linked.encode())[:16] + DSL_SUFFIX)
                visit(linked)

        visit(root_logical, root_tree)
        replacements = {**mapping, **{k.removesuffix(DSL_SUFFIX): v.removesuffix(DSL_SUFFIX)
                                      for k, v in mapping.items()}}
        for logical, value in originals.items():
            changed = transform(value, spec["element"], scale, effects, matched)
            changed = remap(changed, replacements)
            target = mapping[logical]
            if catalog.read(target) is not None:
                raise DraftError("PF 新 DSL 路径已存在：" + target)
            raw = encode_tree(changed)
            if decode_tree(raw) != changed:
                raise DraftError("PF DSL 编码后语义往返不一致：" + target)
            members["common", target], trees[target] = raw, changed
        paths.append(prefix)
        levels.append({"level": level, "path": prefix, **summary(trees[prefix + DSL_SUFFIX])})
    if set(effects) != matched:
        raise DraftError("母本未引用指定特效族：" + ", ".join(sorted(set(effects) - matched)))
    return paths, members, trees, levels, scales


def prepare(source, spec, *, client_profile=None, apks=None, cache_dir=None):
    validate(spec, "pfActionCloneRequest")
    catalog = PfCatalog(source, client_profile=client_profile, apks=apks, cache_dir=cache_dir)
    donor = catalog.resolve(spec["source"])
    paths, members, trees, levels, scales = _programs(catalog, donor, spec)
    from .pf_dependencies import prepare_dependencies
    dependencies, checks = prepare_dependencies(catalog, trees, ELEMENTS.index(spec["element"]))
    for warning in catalog.warnings:
        checks.append({"level": "warn", "code": "pf.bundle-unchecked", "message": warning})
    checks.append({"level": "info", "code": "pf.lifecycle",
                   "message": "三档命令、生命周期和判定标记保留；只改命中元素、倍率、指定特效与私有子程序路径"})
    return {"catalog": catalog, "paths": paths, "members": members, "inputs": dict(catalog.inputs),
            "key": spec["key"], "source": donor["key"], "sourceKind": donor["source"],
            "element": spec["element"], "elementCode": ELEMENTS.index(spec["element"]) + 1,
            "scale": scales, "levels": levels, "dependencies": dependencies, "checks": checks,
            "warnings": list(catalog.warnings)}


def table_bytes(source, entries):
    raw = source.raw(PF_TABLE)
    table = (core.read_orderedmap_raw_rows_from_bytes(raw, PF_TABLE) if raw is not None
             else core.OrderedMap(PF_TABLE, [], [], Path(PF_TABLE)))
    for key, paths in entries:
        if key in table.keys:
            raise DraftError("PF 表目标键已存在：" + key)
        stream = io.StringIO(newline="")
        csv.writer(stream, lineterminator="\n").writerow(paths)
        table.keys.append(key)
        table.rows.append(zlib.compress(stream.getvalue().encode("utf-8")))
    return core.build_orderedmap_raw_rows(table)


def compile_pf(source, store, draft, *, client_profile=None, apks=None, cache_dir=None):
    members, entries, assertions, checks = {}, [], [], []
    if draft["baseView"] != source.version:
        raise DraftError("PF 草稿基线版本与当前视图不一致")
    for change in draft["changes"]:
        if change["kind"] != "pf_action_clone":
            continue
        validate(change, "change")
        spec = change["params"]["spec"]
        if (change["target"]["key"] != spec["key"] or change["params"]["reservations"]
                != {"power_flip_action": [spec["key"]]}):
            raise DraftError("PF 草稿目标键或 reservations 与请求不一致")
        if spec["key"] in {key for key, _ in entries}:
            raise DraftError("PF 草稿包含重复新键")
        result = prepare(source, spec, client_profile=client_profile, apks=apks, cache_dir=cache_dir)
        vacant(source, store, result["catalog"], spec["key"], owner=draft["characterId"])
        if result["inputs"] != change["params"]["inputs"]:
            raise DraftError("PF 母本、APK 或预载依赖输入已变化，请重建草稿")
        if members.keys() & result["members"].keys():
            raise DraftError("PF 草稿生成了重复 DSL 路径")
        members.update(result["members"])
        entries.append((spec["key"], result["paths"]))
        checks.extend(result["checks"])
        assertions.append({"kind": "pf_action_clone", "key": spec["key"], "source": spec["source"],
                           "levels": result["levels"], "dependencies": result["dependencies"]})
    if entries:
        members["common", PF_TABLE] = table_bytes(source, entries)
    return members, assertions, checks


def extend_compiled(compiled, source, store, draft, **options):
    members, servers, server_before, assertions, checks = compiled
    added, changes, results = compile_pf(source, store, draft, **options)
    if members.keys() & added.keys():
        raise DraftError("PF 与其他草稿修改了同一交付成员")
    return {**members, **added}, servers, server_before, [*assertions, *changes], [*checks, *results]
