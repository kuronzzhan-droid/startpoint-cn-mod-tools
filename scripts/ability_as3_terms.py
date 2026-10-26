"""Small-table joins whose official text comes from outside ability enums."""
import re


def element_group_keys(reader):
    resolver = next((f for f in reader.functions if f["class"] == "OrCharacterGroup_Impl_" and f["name"] == "resolve"), None)
    names = next((f for f in reader.functions if f["class"] == "ElementKindTools" and f["name"] == "getFullName"), None)
    display = next((f for f in reader.functions if f["name"] == "stringfyCharacterGroups"), None)
    if not resolver or not names or not display:
        return {}
    call = re.search(r"ElementKindTools\.getFullName", display["body"])
    if not call:
        return {}
    result = {}
    # Named branches in OrCharacterGroup; Yellow is the validated else arm.
    pattern = r'if\(_loc13_ == "(\w+)"\)\s*\{\s*_loc12_ = (\d+);'
    branches = [(m[1], int(m[2]), m.start()) for m in re.finditer(pattern, resolver["body"])]
    yellow = re.search(r'if\(_loc13_ != "Yellow"\).*?_loc12_ = (\d+);', resolver["body"], re.S)
    if yellow:
        branches.append(("Yellow", int(yellow[1]), yellow.start()))
    for name, index, offset in branches:
        for number, text, _ in reader.select(names["body"], names["line"], {"param1": index}):
            for key in re.findall(r'"(element_kind_\w+_full)"', text):
                result[name] = [{"key": key, "status": "as3", "evidence": [
                    f'{resolver["path"]}:{resolver["line"] + resolver["body"].count(chr(10), 0, offset)}',
                    f'{display["path"]}:{display["line"] + display["body"].count(chr(10), 0, call.start())}',
                    f'{names["path"]}:{number}']}]
    return result
