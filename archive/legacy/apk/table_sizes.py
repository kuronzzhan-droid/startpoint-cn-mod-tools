"""Count rows of server-side master JSON tables (proxy for client master sizes; read-only)."""
import json
import sys
from pathlib import Path
from wf.paths import root_path

ASSETS = root_path('startpoint-cn-kulo/assets')


def rows(value):
    if isinstance(value, dict):
        return len(value)
    if isinstance(value, list):
        return len(value)
    return 0


def leaf_rows(value, depth=0):
    """Rows at the deepest dict level that holds lists (master json is key -> [rows])."""
    if isinstance(value, dict):
        if value and all(isinstance(v, list) for v in value.values()):
            return len(value)
        return sum(leaf_rows(v, depth + 1) for v in value.values())
    return 1


def main():
    result = []
    for path in sorted(ASSETS.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf8"))
        except Exception as error:  # noqa: BLE001
            result.append((path.name, "ERR " + str(error)[:40], ""))
            continue
        result.append((path.name, rows(data), leaf_rows(data)))
    result.sort(key=lambda r: -(r[2] if isinstance(r[2], int) else 0))
    for name, top, leaf in result[: int(sys.argv[1]) if len(sys.argv) > 1 else 60]:
        print(f"{name:50s} top={top} leaf={leaf}")


if __name__ == "__main__":
    main()
