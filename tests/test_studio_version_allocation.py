"""Delivery defaults share the read-only version allocation evidence."""
from types import SimpleNamespace

from wf.studio import versions
from wf.studio.deliver_routes import next_version as delivery_version
from test_studio_ids import Source, write


def test_historical_tip_skips_active_versions_and_reservations(tmp_path):
    active = tmp_path / "active"
    active.mkdir()
    (active / "pinball-1.4.282-1.4.283-1-data.zip").write_bytes(b"archive")
    (active / "pinball-1.4.283-1.4.284-1-data.zip").write_bytes(b"archive")
    (active / "pinball-1.4.285-1.4.286-1-candidate.zip").write_bytes(b"candidate")
    reservation = tmp_path / "reservations.json"
    write(reservation, {"1.4.285": {"purpose": "reserved", "owner": "test", "date": "2026-10-25"}})
    source = Source()
    source.view = SimpleNamespace(active=active)
    before = {p.name: p.read_bytes() for p in active.iterdir()}
    result = versions.next_version(source, reservations_file=reservation)
    assert result["next"] == "1.4.286"
    assert [x["version"] for x in result["skipped"]] == ["1.4.283", "1.4.284", "1.4.285"]
    assert result["skipped"][0]["source"] == "active"
    assert before == {p.name: p.read_bytes() for p in active.iterdir()}


def test_delivery_default_skips_declared_and_reserved_versions(tmp_path, monkeypatch):
    manifest = tmp_path / "manifest.json"
    write(manifest, {"patches": [{"version": "1.4.283", "enabled": False}]})
    reservation = tmp_path / "reservations.json"
    write(reservation, {"1.4.284": {"purpose": "reserved", "owner": "test", "date": "2026-10-25"}})
    monkeypatch.setattr(versions, "DEFAULT_RESERVATIONS", reservation)
    source = Source()
    source.view = SimpleNamespace(manifest=manifest, search_dirs=[], manifests=[])
    assert delivery_version(source.version, source=source) == "1.4.285"
