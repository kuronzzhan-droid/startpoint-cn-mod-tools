"""Audit identities must cover the implementation behind the small entrypoint."""
from wf.tools.rogue._source_digest import source_digest


def test_each_loaded_section_and_entrypoint_changes_audit_identity(tmp_path):
    entrypoint = tmp_path / "rogue_build.py"
    entrypoint.write_bytes(b"# facade\n")
    sections = ("policy.py", "compile.py")
    for section in sections:
        (tmp_path / section).write_bytes(section.encode())
    baseline = source_digest(entrypoint, sections)
    assert source_digest(entrypoint, sections) == baseline
    for name in (entrypoint.name, *sections):
        source = tmp_path / name
        original = source.read_bytes()
        source.write_bytes(original + b"\n# changed\n")
        assert source_digest(entrypoint, sections) != baseline
        source.write_bytes(original)
    assert source_digest(entrypoint, tuple(reversed(sections))) != baseline
