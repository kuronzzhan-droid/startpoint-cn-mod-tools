"""Apply the 629 gate before creating any delivery archive."""
from wf.dsl.gate import check_629_actions
from wf.dsl.references import ABILITY_TABLES, ACTION_SKILL, DSL_SUFFIX

from .changeset import write_json
from .prepush_base import View


def check_candidate(out, members, baseline, base_store=None):
    for _, entry in members.values():
        logical = entry["logical_path"]
        if entry["root"] != "common" and (
                logical in ABILITY_TABLES or logical == ACTION_SKILL or logical.endswith(DSL_SUFFIX)):
            raise ValueError(f"问题: combat table/DSL must use common root: {logical}")
    fallback = View([], base_store) if base_store is not None else None

    def read(logical):
        if baseline is not None:
            return baseline.read_raw(logical)
        raw = fallback.raw(logical) if fallback is not None else None
        if raw is None:
            raise FileNotFoundError(logical)
        return raw

    overrides = {entry["logical_path"]: raw for raw, entry in members.values()
                 if entry["root"] == "common"}
    report = check_629_actions(read, overrides=overrides, changed_logicals=set(overrides))
    write_json(out / "dsl-629.json", report)
    if report["status"] == "问题":
        messages = "; ".join(finding["message"] for finding in report["findings"])
        raise ValueError(f"问题: 629 gate blocked delivery: {messages}")
    return report
