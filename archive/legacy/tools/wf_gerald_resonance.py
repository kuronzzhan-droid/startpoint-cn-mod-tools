"""Known-input water-resonance gates for Gerald's second-board abilities."""
from copy import deepcopy
import hashlib

import wf_mod_tool as core
from wf_client_legality import client_legality_problems

BASE_HASHES = {
    "1299924": "d5f3d2f0697b60f1460d56890680db0bf4c0649c5e5420d342428914cab10410",
    "1299925": "354a4d01bcfda7c13614e1713b4c9948411ce83d1a7e4f91718047f78a5fc431",
    "1299926": "1207e9deee2b68820e5fd3e5a48afbe1cbb957ccd4d12b2f056c818646f0861a",
}
WATER_RESONANCE = ["2", "", "", "600000", "600000", "Blue", ""]


def revise_ability(key: str, text: str) -> str:
    """Change four condition blocks; reject drift and preserve all effect fields."""
    if key not in BASE_HASHES:
        raise ValueError("only Gerald abilities 4, 5 and 6 are supported")
    rows = core.read_csv_lines(text)
    if len(rows) != 2 or any(len(row) != 126 for row in rows):
        raise ValueError("unexpected Gerald ability layout")
    selected = (0, 1) if key == "1299924" else (0,)
    previous = ["0" if key == "1299924" else "42", "", "", "", "", "", ""]
    normalized = deepcopy(rows)
    for index in selected:
        if rows[index][6:13] not in (previous, WATER_RESONANCE):
            raise ValueError("unexpected existing ability condition")
        normalized[index][6:13] = previous
    digest = hashlib.sha256(core.write_csv_lines(normalized).encode()).hexdigest()
    if digest != BASE_HASHES[key]:
        raise ValueError("Gerald ability effect or trigger differs from the approved baseline")
    for index in selected:
        rows[index][6:13] = WATER_RESONANCE
    for row in rows:
        problems = client_legality_problems("ability", row)
        if problems:
            raise ValueError("; ".join(problems))
    # The unchanged c34 keeps ability 4's charge unlimited and its attack capped.
    return core.write_csv_lines(rows)
