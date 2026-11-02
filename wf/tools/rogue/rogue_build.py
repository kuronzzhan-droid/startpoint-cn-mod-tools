"""Online Abyss builder, with legacy import and monkeypatch compatibility.

The reviewed source is divided into explicit responsibility sections. They are
compiled unchanged into this module's globals so online caches, dataclasses,
monkeypatches and private Studio instances keep the original single-module
contract. No user input selects or rewrites executable source. The first port
preserves the online algorithm; further ordinary module extraction is separate.
"""
from pathlib import Path as _SectionPath

_SECTIONS = (
    '_build_policy.py',
    '_build_hp_evidence.py',
    '_build_identity.py',
    '_build_native_pool.py',
    '_build_schedule.py',
    '_build_curses.py',
    '_build_hp_audit.py',
    '_build_audit_verify.py',
    '_build_special_graphs.py',
    '_build_special_evidence.py',
    '_build_special_plans.py',
    '_build_special_clones.py',
    '_build_hp_materialize.py',
    '_build_main.py',
)


def tool_source_sha256():
    """Bind audit receipts to every loaded source section and this entrypoint."""
    from wf.tools.rogue._source_digest import source_digest
    return source_digest(_SectionPath(__file__), _SECTIONS)


for _section in _SECTIONS:
    _source = _SectionPath(__file__).with_name(_section)
    exec(compile(_source.read_bytes(), str(_source), "exec"), globals())
del _section, _source

if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
