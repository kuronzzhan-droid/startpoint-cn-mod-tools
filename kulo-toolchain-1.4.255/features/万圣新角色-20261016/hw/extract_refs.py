import hw_env, wf_assets
from pathlib import Path
OUT = hw_env.OUT / "art" / "refs"
for code in ("lady_android", "blade_witch", "crystal_swordman", "lich"):
    for lg in (f"character/{code}/ui/full_shot_1440_1920_0.png", f"character/{code}/ui/full_shot_1440_1920_1.png",
               f"character/{code}/ui/skill_cutin_0.png"):
        loc = wf_assets.locate(hw_env.STORE, lg)
        if not loc:
            print("missing", lg); continue
        data = loc[1].read_bytes()
        if data[:4] == b"\x89png":
            data = b"\x89PNG" + data[4:]
        p = OUT / f"{code}_{Path(lg).stem}.png"
        p.write_bytes(data); print(p.name, len(data))
