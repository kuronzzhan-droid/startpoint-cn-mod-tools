"""Explicit historical fragment targets; ambiguous legacy names fail closed."""
from .drafts import DraftError
from .rehearsal_io import inside, read_json


def entry_targets(folder):
    manifest = inside(folder, "server-entries/merge-manifest.json")
    document = read_json(manifest) if manifest.is_file() else {}
    if not isinstance(document, dict) or not isinstance(document.get("operations", []), list):
        raise DraftError("merge-manifest operations 必须是数组")
    mapping = document.get("targets", {})
    if not isinstance(mapping, dict):
        raise DraftError("merge-manifest targets 必须是源文件到目标路径数组的对象")
    operations = {}
    for operation in document.get("operations", []):
        if not isinstance(operation, dict) or not isinstance(operation.get("file"), str):
            raise DraftError("merge-manifest operation 缺少 file")
        inside(folder / "server-entries", operation["file"])
        operations.setdefault(operation["file"], []).append(operation)
    ambiguous = {"character.json", "cdndata/character.json", "cdndata/character_text.json", "mana_node.json"}

    def targets(relative):
        selected = mapping.get(relative)
        if selected is None and relative in ambiguous:
            raise DraftError(f"历史服务端目标未核对：{relative}；请在 merge-manifest.targets 显式指定现用表（可一对多）")
        selected = selected if selected is not None else ["assets/" + relative]
        if not isinstance(selected, list) or not selected or any(not isinstance(v, str) for v in selected):
            raise DraftError(f"服务端目标映射必须是非空路径数组：{relative}")
        return selected
    return targets, operations


def unchanged_keys(before, after, pointer=""):
    from .rehearsal_server import _pointer
    if before == after:
        return [pointer or "/"]
    if isinstance(before, dict) and isinstance(after, dict):
        return [p for key in sorted(before.keys() & after.keys())
                for p in unchanged_keys(before[key], after[key], _pointer(pointer, key))]
    return []
