"""Fields actually consumed by the selected trigger mode and constructor."""
import wf_describe
import wf_client_legality


def active_fields(row, table):
    layout = wf_describe.layout(table)
    if len(row) != layout["ncols"]:
        return {}
    blocks = layout["blocks"]
    mode = row[blocks["precondition1"] - 1]
    em = wf_describe.enum_map()
    active = list(wf_client_legality.TRIGGER_MODE_BLOCKS.get(mode, ()))
    if mode == "0":
        active += ["instant_precontent", "instant_delay"]
    if mode == "2":
        active += ["opening"]
    result = {}
    for block in active:
        base = blocks[block]
        group = "precondition" if block.startswith("precondition") else block
        case_key = "instant_trigger" if group == "during_accumulation_trigger" else group
        fields = em["cases"].get(case_key, {}).get(row[base], {}).get("fields", {})
        for offset, field, _ in em["block_fields"].get(group, []):
            if (field == "kind" or field.split(".")[0] in fields or
                    block == "instant_delay" or block == "opening" and row[base] in {"0", "1", "2"}):
                result[base + offset] = (block, field)
    return result
