"""The public CLI emits exactly one JSON line and uses the shared weapon store."""
import json
from types import SimpleNamespace

from test_boss_shop_weapon import state  # noqa: F401
from test_studio_weapon_routes import app  # noqa: F401
from test_studio_weapon_p0_icons import png
from wf.studio import draft


def execute(app, capsys, *arguments):
    code = draft.main(["--drafts", str(app.ops.store.root), "--server-dir", str(app.weapons.server_dir),
                       "weapon", *arguments])
    out = capsys.readouterr().out.splitlines()
    assert len(out) == 1
    return code, json.loads(out[0])


def test_cli_list_show_clone_materials_icon(app, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(draft, "_ops", lambda args: SimpleNamespace(source=app.source))
    code, listed = execute(app, capsys, "list", "--q", "5010005")
    assert code == 0 and listed["result"]["count"] == 1
    code, cloned = execute(app, capsys, "clone", "--from", "5010005", "--to", "5950001", "--code", "cli_weapon")
    assert code == 0 and cloned["result"]["weaponId"] == "5950001"
    code, shown = execute(app, capsys, "show", "5950001")
    assert code == 0 and shown["result"]["changeset"]["changes"][0]["params"]["requests"][0]["weapon"]["code"] == "cli_weapon"
    request = tmp_path / "materials.json"
    request.write_text(json.dumps({"stages": [{"productId": "595000101", "costs": [{"itemId": "1", "amount": 11}]}]}))
    code, edited = execute(app, capsys, "materials", "5950001", "--request", str(request))
    assert code == 0 and edited["result"]["changeset"]["revision"] == 2
    request = tmp_path / "icon.json"
    request.write_text(json.dumps({"kind": "weapon", "png": png((20, 20))}))
    code, imported = execute(app, capsys, "icon", "5950001", "--request", str(request))
    assert code == 0 and imported["result"]["icons"][0]["size"] == [20, 20]


def test_cli_error_is_one_json_line_and_does_not_save(app, monkeypatch, capsys):
    monkeypatch.setattr(draft, "_ops", lambda args: SimpleNamespace(source=app.source))
    code, result = execute(app, capsys, "clone", "--from", "5010005", "--code", "../invalid")
    assert code == 1 and result["ok"] is False
    assert not app.weapons.store.characters()
