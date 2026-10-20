import csv, io, re
from wfio import DEC
def load_names():
    txt = open(DEC / "master/character/character_text.csv", encoding="utf-8-sig").read()
    recs = []
    for line in txt.split("\n"):
        if re.match(r"^\d{2,7},", line) or not recs:
            recs.append(line)
        else:
            recs[-1] += " " + line
    names = {}
    for rec in recs:
        try:
            r = next(csv.reader(io.StringIO(rec)))
        except Exception:
            continue
        if len(r) >= 6 and r[0] not in names:
            names[r[0]] = {"name": r[1], "title": r[4], "skill": r[5], "skill_desc": r[6] if len(r) > 6 else ""}
    return names
