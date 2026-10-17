"""Native Inaho PF Lv3 charge and Fever attack balance changes."""
from copy import deepcopy
import hashlib

import wf_mod_tool as core
from wf_client_legality import client_legality_problems

BASE_HASHES = {
    "1399951": "bd5b31c1065bba95d0adaa353a9198af9e8f11a5dd0224357c1f0bd05e107898",
    "1399953": "393cba110c315ca9763a97fc5516e8eba60b5eed1dff7fbd4bf48fbd323c2d80",
    "1399954": "d1370274a980cd987f8ca3754bccbe20fccb49b3f01c988329ed9542168763b9",
}


def revise_native(texts: dict[str, str]) -> dict[str, str]:
    """Use verified native Fever/PF triggers; never approximate ratio changes."""
    if set(texts) != set(BASE_HASHES):
        raise ValueError("expected exactly Inaho ability keys 1, 3 and 4")
    for key, digest in BASE_HASHES.items():
        if hashlib.sha256(texts[key].encode()).hexdigest() != digest:
            raise ValueError("unknown Inaho 1.4.774 ability input")
    rows = {key: core.read_csv_lines(text) for key, text in texts.items()}
    first, third, fourth = (rows[key] for key in BASE_HASHES)
    first[0][51:53] = ["37500", "75000"]
    charge = deepcopy(third[3])
    charge[0], charge[1] = first[0][0], "true"
    charge[6], charge[27] = "12", "65"  # Fever; exactly one PF Lv3.
    charge[51:53] = ["2500", "5000"]
    first.append(charge)
    attack = deepcopy(fourth[0])
    attack[0], attack[1] = third[0][0], "false"
    third.append(attack)
    fourth[0][113:115] = ["150000", "150000"]
    for group in rows.values():
        for row in group:
            problems = client_legality_problems("ability", row)
            if problems:
                raise ValueError("; ".join(problems))
    return {key: core.write_csv_lines(group) for key, group in rows.items()}
