"""Compare automatic view against an independently supplied studio ZIP list.

Run as ``python -m scripts.verify_m1_view --extra-list <file>``. Reads only the
explicit reference list; neither it nor expected packages drive the new view.
"""
import argparse
import hashlib
import json
from pathlib import Path

from wf.view import ManifestView
from wf.view.base149 import HistoricalView
from wf.view.safety import local_output, restrict_writes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extra-list", type=Path, required=True)
    parser.add_argument("--tip", default="1.4.224")
    parser.add_argument("--output", type=Path, default=Path("work/m1/view/acceptance.json"))
    args = parser.parse_args()
    restrict_writes()
    actual = ManifestView(args.tip)
    reference = HistoricalView(tip=206, extra_zips=[Path(line.strip()) for line in
        args.extra_list.read_text(encoding="utf-8-sig").splitlines() if line.strip()])
    assert set(actual.index) == set(reference.index), "overlay member sets differ"
    checked = []
    for name in sorted(actual.index):
        produced, _ = actual.read_member(name)
        expected, _ = reference.read_member(name)
        assert produced == expected, f"member differs: {name}"
        checked.append({"member": name, "sha256": hashlib.sha256(produced).hexdigest()})
    characters = actual.characters()
    expected_characters = reference.load("master/character/character.orderedmap")
    assert characters == expected_characters
    assert len(characters) == 602
    actual.verify()
    report = {"tip": args.tip, "characters": len(characters), "matched_members": len(checked),
              "zip_count": len(actual.zips), "reference_zip_count": len(reference.zips),
              "all_character_entries_equal": True, "all_overlay_members_equal": True,
              "reference_list_sha256": hashlib.sha256(args.extra_list.read_bytes()).hexdigest(),
              "members": checked}
    target = local_output(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    actual.save_lock(target.with_suffix(".lock.json"))
    print(json.dumps({key: value for key, value in report.items() if key != "members"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
