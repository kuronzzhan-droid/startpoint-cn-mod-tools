"""Validate Orochi's embedded head references in an in-memory candidate."""


def validate_heads(rows, reports, table, builder, validation):
    orochi = validation.get("orochi", {})
    if not orochi:
        return
    levels = table(builder.BOSS_LEVEL)
    for report in reports:
        level = int(rows[report["round"]][95])
        for code in set(report["bosses"]) & set(orochi):
            parent = builder.rbb.validate_boss_ref(builder.rbb.BossRef(3, code), level, validation)
            if not parent.ok or parent.selected_level is None:
                continue  # The ordinary reference gate reports the parent failure.
            row = builder.cells(orochi[code][str(parent.selected_level)])
            heads = row[24].split(",") if len(row) > 24 and row[24] else []
            if len(heads) != 8 or len(set(heads)) != 8:
                report["errors"].append(f"orochi {code} c24 requires eight distinct heads")
            for head in heads:
                valid = builder.rbb.validate_boss_ref(builder.rbb.BossRef(1, head), level, validation)
                if not valid.ok or not isinstance(levels.get(head), str) or not levels[head]:
                    report["errors"].append(f"orochi {code} missing/unusable head {head}: {valid.reason}")
            report["ok"] = not report["errors"]
