"""Explicit chain-era entrance rules; no live-value copying or drift exemptions."""

ENTRANCE_DIR = "battle/action/enemy/action/mod/five_boss_v3/"


def entrance_program(self_only=False):
    return ENTRANCE_DIR + "fb3_buff$entrance" + ("_self" if self_only else "")


def entrance_library(params):
    from . import five_boss_v2 as f
    def resistance(frames, value):
        return ["ACToleranceOfElement", f._range(frames), 254, f._range(value), f._range(1)]
    block = [f._cond(-17, f._ac_value("ACToleranceOfDebuff", 9999999, params["debuff_resistance"], 1),
                     cancelable=False, key="fb3_debuff_res", force=True)]
    block += [f._cond(-17, resistance(9999999, value), key=f"fb3_def_{i}", force=True)
              for i, value in enumerate(params["defense_layers"])]
    player = [f._cond(0, f._ac_value("ACAttackPoint", params["player_frames"], params["player_attack"], 1),
                      key="fb3_atk_down"),
              f._cond(0, resistance(params["player_frames"], params["player_resistance"]), key="fb3_def_down")]
    return {entrance_program(True): f._root(block),
            entrance_program(): f._root(block + [f._find_all(33, player)])}


def clone_pre(spec, inherited, explicit, signature, programs, slot):
    from . import five_boss_v2 as f
    pre = f.strip_v1_curse(inherited) + explicit + signature + programs
    if spec.get("entrance"):
        # Mother rows may already carry an entrance from a different formation.
        pre = [p for p in pre if p not in (entrance_program(), entrance_program(True))]
        pre.append(entrance_program(slot != 0))
    return list(dict.fromkeys(pre))


def wave_programs(spec, variant, wave, slot):
    from . import five_boss_v2 as f
    carrier = variant.group_kind == 1 or slot == 0
    names = (variant.entry_affixes if wave == 0 else []) + variant.affixes if carrier else []
    if spec["rounds"][variant.round].get("dedupe_player_affixes") and slot != 0:
        names = [name for name in names if name.startswith("enrage_")]
    return [f.affix_program(name) for name in names]
