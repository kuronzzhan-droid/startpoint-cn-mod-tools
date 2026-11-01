"""Regression cases from the C source audit; all mutations use pytest tmp_path."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from test_studio_apply import enabled, case
from test_studio_rehearsal import put, snapshot
from wf.studio import apply_io as io, apply_local as local
from wf.studio.rehearsal import rehearse, markdown
from wf.studio.rehearsal_io import read_json, json_bytes


@pytest.mark.parametrize("flag", [True, False])
def test_real_studio_build_local_candidate(tmp_path, monkeypatch, flag):
    from test_studio_deliver_bridge import case as build_case, build
    from wf.studio import deliver_bridge as bridge
    data = build_case.__wrapped__(tmp_path, monkeypatch)
    compile_original = bridge.compile_draft
    def compile_with_checks(*args, **kwargs):
        compiled = list(compile_original(*args, **kwargs))
        compiled[4] = [{"state": "满足", "code": "voice.valid", "message": "合成语音检查"},
                       {"state": "满足", "code": "portrait.valid", "message": "合成立绘检查"}]
        return tuple(compiled)
    monkeypatch.setattr(bridge, "compile_draft", compile_with_checks)
    result = build(data, allow_unknown_client=True)
    assert result["ok"], result
    root = tmp_path / "local-server"
    (root / "assets/asset-patch/active").mkdir(parents=True)
    put(root / io.MANIFEST, {"cdn_version": "1.4.132", "patches": [{"type": "patch",
        "enabled": True, "version": "1.4.132", "depends_on": "1.4.131"}]})
    profile = tmp_path / "local-profile.json"
    put(profile, {"servers": {"local": {"root": str(root), "apply_enabled": flag}}})
    monkeypatch.setenv("WF_PATHS_PROFILE", str(profile))
    monkeypatch.setattr(io, "APPLIED", tmp_path / "receipts")
    folder = data[-1] / "delivery"
    original = snapshot(folder)
    preview = rehearse(folder, write=False)
    assert preview["ok"] is flag
    dry = local.apply(folder, dry_run=True)
    applied = local.apply(folder)
    assert dry["ok"] is flag and applied["ok"] is flag
    if flag:
        assert "可应用到本地服，不可直接推 175" in markdown(preview)
        assert "向测试服 175 复制" not in "".join(preview["manualSteps"])
        entry = read_json(root / io.MANIFEST)["patches"][-1]
        assert "local_test_only" not in json.dumps(entry)
    else:
        assert any(c["rule"] == "rehearsal.local-test-only" and c["blocking"] for c in preview["checks"])
    assert snapshot(folder) == original


@pytest.mark.parametrize("field", ["draft_checks", "safety_checks", "client_compatibility"])
def test_missing_declared_checks_block_apply(enabled, field):
    root, folder, _ = enabled
    put(folder / "delivery-manifest.json", {field: {"report": "missing.json"} if field == "client_compatibility" else "missing.json"})
    with pytest.raises((OSError, ValueError)):
        local.delivery_checks(folder)


@pytest.mark.parametrize("row", [{"state": "问题"}, {"status": "问题"}, {"blocking": True}, {"level": "error"}])
def test_draft_problem_checks_still_block(enabled, row):
    _, folder, _ = enabled
    put(folder / "draft-checks.json", [row])
    with pytest.raises(ValueError, match="阻断"):
        local.delivery_checks(folder)


@pytest.mark.parametrize("raw", ['{"x":NaN}', '{"x":Infinity}', '{"x":-Infinity}', '{"x":1e999}', '{"x":1,"x":2}'])
def test_invalid_server_json_is_rejected(enabled, raw):
    root, folder, _ = enabled
    candidate = folder / "server/assets/table.json"
    candidate.parent.mkdir(parents=True)
    candidate.write_text(raw, "utf-8")
    before = snapshot(root)
    assert not local.apply(folder)["ok"]
    assert snapshot(root) == before
    with pytest.raises(ValueError):
        json_bytes({"x": float("nan")})


def test_apply_preserves_unmodified_rows_and_rejects_out_json(enabled):
    root, folder, _ = enabled
    raw = b'{\n "old" : [ 1,  2 ],\n "nested":{"keep":7}\n}\n'
    (root / "assets/rows.json").write_bytes(raw)
    put(folder / "server/assets/rows.json", {"nested": {"add": 8}, "new": 9})
    assert local.apply(folder)["ok"]
    output = (root / "assets/rows.json").read_bytes()
    assert b'"old" : [ 1,  2 ]' in output and b"\r\n" not in output
    assert local.unapply(folder)["ok"]
    assert (root / "assets/rows.json").read_bytes() == raw
    put(folder / "server/out/config.json", {"key": 1})
    assert not local.apply(folder)["ok"]
    assert not (root / "out").exists()


def test_undeclared_server_candidate_rejected(enabled):
    root, folder, _ = enabled
    put(folder / "assert-box.json", {"files": []})
    put(folder / "server/assets/extra.json", {"key": 1})
    result = rehearse(folder, write=False)
    assert not result["ok"] and "未声明" in str(result["checks"])


def test_reparse_point_rejected_without_path_is_junction(enabled, monkeypatch):
    root, _, _ = enabled
    original = Path.lstat
    def reparse(path):
        result = original(path)
        if path == root / "assets":
            return SimpleNamespace(st_mode=result.st_mode, st_file_attributes=0x400)
        return result
    monkeypatch.setattr(Path, "lstat", reparse)
    with pytest.raises(ValueError, match="链接"):
        io.target(root, "assets/table.json")


@pytest.mark.parametrize("source", ["WF_SERVER", "WF_CDN_DIR", "sibling"])
def test_backups_and_locks_exclude_all_input_roots(enabled, monkeypatch, source):
    root, folder, profile = enabled
    protected = root.parent / "protected"
    if source == "sibling":
        config = read_json(profile)
        config["servers"]["other"] = {"root": str(protected)}
        put(profile, config)
    else:
        monkeypatch.setenv(source, str(protected))
    monkeypatch.setattr(io, "APPLIED", protected / "receipts")
    with pytest.raises(ValueError, match="之外"):
        io.receipt_folder(folder, root)
    with pytest.raises(ValueError, match="之外"):
        with io.server_lock(root):
            pytest.fail("protected lock created")
    assert not protected.exists()
