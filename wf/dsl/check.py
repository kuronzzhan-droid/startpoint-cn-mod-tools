"""Signature and execution-context checks for ActionDSL JSON or binary trees."""
import json
from pathlib import Path
import zlib

from wf.rules.dsl_signature import DslSignatureError, validate_action_dsl
from .sanitize import forbidden_629


def read_tree(filename):
    target = Path(filename)
    if target.suffix == ".json":
        data = json.loads(target.read_text(encoding="utf-8-sig"))
        return data.get("tree", data) if isinstance(data, dict) else data
    from wf_dsl import parse_dsl
    raw = target.read_bytes()
    try:
        return parse_dsl(zlib.decompress(raw, -15) if target.suffix == ".deflate" else raw)["tree"]
    except (zlib.error, IndexError, KeyError, TypeError) as error:
        raise ValueError(f"invalid DSL payload: {error}") from error


def check_tree(tree, *, kind=None):
    results = []
    try:
        if (not isinstance(tree, list) or len(tree) != 12 or tree[0] != "ActionDsl"
                or not isinstance(tree[11], list) or len(tree[11]) != 2 or tree[11][0] != "Block"):
            raise DslSignatureError("ActionDsl 根必须为12项，索引11必须是唯一的动作 Block")
        validate_action_dsl(tree)
        results.append({"rule": "dsl.signature", "status": "满足", "message": "已登记的命令签名和参数类型匹配"})
    except (DslSignatureError, TypeError, IndexError) as error:
        results.append({"rule": "dsl.signature", "status": "问题", "message": str(error)})
    if kind is None:
        results.append({"rule": "dsl.629-lifecycle", "status": "未执行", "message": "未提供动作调用 kind，不能判定 629 上下文"})
    elif str(kind) != "629":
        results.append({"rule": "dsl.629-lifecycle", "status": "不适用", "message": f"调用 kind={kind}，不是能力动作 629"})
    else:
        findings = forbidden_629(tree)
        results.append({"rule": "dsl.629-lifecycle", "status": "问题" if findings else "满足",
                        "message": "能力动作含真实 PF 生命周期命令" if findings else "能力动作不含禁止命令",
                        "findings": findings})
    return results
