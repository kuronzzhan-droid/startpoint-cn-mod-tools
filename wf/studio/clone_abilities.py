"""Independent character ability keys; shared donor effects retain their meaning."""
from .drafts import DraftError


def clone_abilities(source, spec, row, raw_tables, additions):
    from .clone_tables import T, rows
    # CharacterValues reads c17 as leader_ability.id and c19..24 as ability IDs.
    # The legacy tooling calls c17 character_id; it is not the outer character key.
    for logical, slots in ((T.LEADER, (17,)), (T.ABILITY, range(19, 25))):
        active = [slot for slot in slots if row[slot] not in ("", "(None)")]
        if not active:
            continue
        raw = source.raw(logical)
        if raw is None:
            raise DraftError(f"母本缺少能力表：{logical}")
        baseline = rows(raw, logical)
        raw_tables[logical] = raw
        patch = {}
        for slot in active:
            donor = row[slot]
            target = spec["to"] if slot == 17 else f"{spec['to']}{slot - 18}"
            if donor not in baseline:
                raise DraftError(f"母本能力键不存在：{logical}/{donor}")
            if target in baseline:
                raise DraftError(f"目标能力键已占用：{logical}/{target}")
            # Preserve every CSV record and shared string/effect reference.
            patch[target] = baseline[donor]
            row[slot] = target
        additions[logical] = patch
