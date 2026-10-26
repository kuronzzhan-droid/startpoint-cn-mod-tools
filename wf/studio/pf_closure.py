"""Shared donor closure validation for catalog and cloning."""
from wf.dsl.references import linked_programs
from .drafts import DraftError
from .pf_dsl import nodes


def closure(catalog, logical, tree=None):
    from .pf_catalog import decode_program
    found = {}

    def visit(path, value=None):
        if path in found:
            return
        if len(found) >= 256:
            raise DraftError("PF 子程序图超过 256 个节点")
        if value is None:
            raw = catalog.read(path)
            if raw is None:
                raise DraftError("PF 子程序缺失：" + path)
            value = decode_program(raw, path)
        if any(n[0] in {"CreateRatioAttack", "CreateFixedAttack"} for n in nodes(value)):
            raise DraftError("该 PF 含比例或固定伤害，尚不支持按攻击倍率克隆")
        found[path] = value
        for child in sorted(linked_programs(value)):
            visit(child)
    visit(logical, tree)
    return found
