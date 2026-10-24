"""Unified schema and evidence-aware rules with five explicit result states."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from wf.paths import REPOSITORY
from wf.rules.catalog import catalog, result, with_metadata
from wf.view.safety import local_output

SCHEMAS = {
    "wf-balance-recipe/1": ("balance-recipe.schema.json", "balance"),
    "wf-change-set/1": ("change-set.schema.json", "delivery"),
    "wf-delivery-manifest/1": ("delivery-manifest.schema.json", "delivery"),
    "wf-character-text/1": ("character-text.schema.json", "text"),
    "wf-capability/1": ("capability.schema.json", "capability"),
    "wf-apk-provides/1": ("provides.schema.json", "capability"),
}


def read_document(filename):
    from wf.balance.recipe import RecipeLoader
    import yaml
    try:
        return yaml.load(Path(filename).read_text(encoding="utf-8-sig"), Loader=RecipeLoader)
    except yaml.YAMLError as error:
        raise ValueError(f"invalid JSON/YAML: {error}") from error


def schema_results(document, schema_name):
    import jsonschema
    definition = json.loads((REPOSITORY / "schemas" / schema_name).read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(definition)
    errors = sorted(validator.iter_errors(document), key=lambda error: str(error.path))
    if errors:
        return [result("schema", "问题", "结构不符合 JSON Schema", blocking=True,
                       errors=[{"path": "/".join(map(str, error.path)), "message": error.message} for error in errors])]
    return [result("schema", "满足", f"符合 {schema_name}")]


def balance_checks(document, filename):
    from wf.balance.engine import apply_recipe
    from wf.balance.inputs import open_inputs
    from wf.balance.recipe import validate_recipe
    validate_recipe(document)
    results = [result("delivery.forward-edge", "满足", "目标版本高于来源版本")]
    if "input" not in document:
        return results + [result("ability.old-values", "未执行", "未给 input，尚未与真实旧值比较")]
    view, verify = open_inputs(document, filename.resolve())
    generated = apply_recipe(document, view)
    verify()
    results.extend([result("ability.old-values", "满足", f"已在内存执行 {len(generated.changes)} 个断言操作"),
                    result("ability.instant-fields", "满足", "实际输出行已通过既有合法性检查")])
    return results


def check_file(filename):
    filename = Path(filename)
    try:
        document = read_document(filename)
        schema = document.get("schema") if isinstance(document, dict) else None
        if schema == "wf-boss/1":
            from wf.rules.boss import check_boss
            return check_boss(document)
        if schema in SCHEMAS:
            schema_name, scope = SCHEMAS[schema]
        elif isinstance(document, dict) and "requires" in document and document.get("schemaVersion") == 2:
            schema_name, scope = "requires.schema.json", "requires"
        else:
            return with_metadata([result("schema", "未执行", "无法识别格式版本，未进行结构或规则校验")], "unknown")
        results = schema_results(document, schema_name)
        if results[0]["status"] == "问题":
            return with_metadata(results, scope)
        if schema == "wf-capability/1":
            from wf.caps.registry import validate_capability
            validate_capability(document)
            results.append(result("capability.registration", "满足", "能力字段、补丁归属及哈希待补标记一致"))
        elif scope == "balance":
            results.extend(balance_checks(document, filename))
        elif schema == "wf-change-set/1":
            from wf.deliver.changeset import load_changeset
            load_changeset(filename)
            results.append(result("delivery.forward-edge", "满足", "已验证前进版本、输入成员 SHA-256 和重复目标"))
        elif scope == "requires":
            pending = document["requires"]["capabilityResolution"] in {"pending-m2", "partial"}
            results.append(result("capability.unknown", "待验证" if pending else "未执行",
                "依赖推导不完整，空列表不表示无依赖" if pending else "已推导或声明依赖，尚未提供目标 provides.json 做匹配"))
        elif schema == "wf-delivery-manifest/1":
            from wf.check_delivery import check_delivery
            results.extend(check_delivery(document, filename.parent))
        elif scope == "text":
            from wf.text.rules import check_character
            from wf.text.standard import coverage
            findings = check_character(document)
            issues = [finding for finding in findings if finding["state"] == "问题"]
            pending = [finding for finding in findings if finding["state"] == "待验证"]
            results.append(result("text.wording", "问题" if issues else "待验证" if pending else "满足",
                                  "按实际可见字段检查恒真条件、命名与重复强化", blocking=bool(issues), findings=findings))
            results.append(result("text.visible-sources", "未执行",
                                  "快照字段已齐；此文件检查不重新读取客户端和服务端来源"))
            surfaces = [field for field in ("action_skill", "custom_ability_string", "desc_override") if document.get(field)]
            results.extend(result(entry["rule"], entry["state"], entry["requirement"],
                                  blocking=entry["state"] == "问题", boundary=entry["boundary"])
                           for entry in coverage(surfaces, findings))
        return with_metadata(results, scope)
    except (ValueError, OSError, KeyError, TypeError) as error:
        return [result("input", "问题", str(error), blocking=True)]


def main(argv=None):
    parser = argparse.ArgumentParser(prog="wf check")
    parser.add_argument("target", help="文件，或 dsl / rules / caps / compat / text / boss")
    parser.add_argument("files", nargs="*", type=Path)
    parser.add_argument("--kind", type=int, help="DSL 调用 kind；能力动作用 629")
    parser.add_argument("--json", type=Path)
    parser.add_argument("--requires", type=Path)
    parser.add_argument("--provides", type=Path)
    parser.add_argument("--tip", help="boss 只读视图版本；默认跟随 manifest 最高启用版本的完整依赖链")
    parser.add_argument("--base-version", default="1.4.131")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--extra-manifest", type=Path, action="append", default=[])
    parser.add_argument("--store", type=Path)
    parser.add_argument("--zip-dir", type=Path, action="append")
    parser.add_argument("--lock", type=Path)
    parser.add_argument("--baseline", type=Path, help="boss 属性变化前的 wf-boss/1 快照")
    parser.add_argument("--context", type=Path, help="boss 自制内容/选门/三人图集等设计上下文 JSON")
    args = parser.parse_args(argv)
    if args.target == "rules":
        document = catalog()
        failed = False
    elif args.target == "compat":
        if not args.requires or not args.provides or args.files:
            parser.error("wf check compat --requires X --provides Y")
        from wf.caps.compat import check_compat
        try:
            results = check_compat(read_document(args.requires), read_document(args.provides),
                                   delivery_dir=args.requires.parent)
        except (ValueError, OSError, KeyError, TypeError) as error:
            results = [result("input", "问题", str(error), blocking=True)]
        document = {"schema": "wf-check-results/1", "results": results}
        failed = any(entry["blocking"] for entry in results)
    elif args.target == "boss":
        if not args.files:
            parser.error("wf check boss 需要副本 ID、kind:path 或 wf-boss/1 快照文件")
        from wf.rules.boss_cli import check_inputs
        try:
            files = check_inputs(args)
        except (ValueError, OSError, TypeError, KeyError) as error:
            files = [{"file": "boss inputs", "results": [result("input", "问题", str(error), blocking=True)]}]
        document = {"schema": "wf-check-results/1", "files": files}
        failed = any(r["blocking"] for f in files for r in f["results"])
        failed |= any(all(r["status"] in {"未执行", "不适用"} for r in f["results"]) for f in files)
    elif args.target in {"caps", "text"}:
        if args.target == "caps":
            from wf.caps.registry import load_registry
            load_registry()
            filenames = args.files or sorted((REPOSITORY / "wf/caps").glob("*.yml"))
        else:
            filenames = args.files
        if not filenames:
            parser.error(f"wf check {args.target} 需要输入文件")
        files = []
        for filename in filenames:
            expected = {"wf-capability/1"} if args.target == "caps" else {"wf-character-text/1"}
            try:
                value = read_document(filename)
                if not isinstance(value, dict) or value.get("schema") not in expected:
                    raise ValueError(f"wf check {args.target} 输入类型不匹配")
                results = check_file(filename)
            except (ValueError, OSError, TypeError) as error:
                results = [result("input", "问题", str(error), blocking=True)]
            files.append({"file": str(filename), "results": results})
        document = {"schema": "wf-check-results/1", "files": files}
        failed = any(r.get("blocking") for f in files for r in f["results"])
        failed |= any(all(r["status"] in {"未执行", "不适用"} for r in f["results"]) for f in files)
    elif args.target == "dsl":
        from wf.dsl.check import check_tree, read_tree
        if not args.files:
            parser.error("wf check dsl 需要一个或多个树文件")
        files = []
        for filename in args.files:
            try:
                results = check_tree(read_tree(filename), kind=args.kind)
                for entry in results:
                    entry["blocking"] = entry["status"] == "问题"
            except (ValueError, OSError, KeyError) as error:
                results = [result("input", "问题", str(error), blocking=True)]
            files.append({"file": str(filename), "results": with_metadata(results, "dsl")})
        document = {"schema": "wf-check-results/1", "files": files}
        failed = any(r["blocking"] for f in files for r in f["results"])
    else:
        if args.files:
            parser.error("只检查一个结构化文件；多个 DSL 文件使用 check dsl")
        results = check_file(args.target)
        document = {"schema": "wf-check-results/1", "file": args.target, "results": results}
        failed = any(r.get("blocking") for r in results) or all(r["status"] in {"未执行", "不适用"} for r in results)
    output = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    if args.json:
        target = local_output(args.json)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(output, encoding="utf-8")
    print(output, end="")
    return int(failed)
