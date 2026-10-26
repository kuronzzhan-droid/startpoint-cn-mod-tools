"""Capability affordances must use the same provides gate as template edits."""
import json

import pytest

from test_boss_shop_weapon import state  # noqa: F401
from test_studio_weapon_routes import app, call  # noqa: F401
from test_studio_weapon_p0_evidence import add_native_branch
from test_studio_weapon_p0_icons import atlas, png
from weapon_delivery_fixture import case
from wf.boss.weapon_templates import _invoke_evidence


def test_missing_provides_stays_unexecuted(app):
    code, document = call(app, "GET", "/capabilities")
    gate = document["invoke629"]
    assert code == 200 and gate["supported"] is False
    assert gate["evidence"]["status"] == "unavailable"
    assert all(c["provided"] is None for c in gate["capabilities"])
    assert gate["checks"][0]["status"] == "未执行"
    assert not app.weapons.store.root.exists()


@pytest.mark.parametrize("missing", [None, "capability", "record", "link"])
def test_capability_flags_agree_with_template_gate(app, tmp_path, missing):
    fixture = case(tmp_path / "evidence")
    add_native_branch(fixture, invoke=True)
    path = fixture["provides"]
    document = json.loads(path.read_bytes())
    if missing == "capability":
        document["provides"] = document["provides"][1:]
    elif missing == "record":
        document["patches"] = []
    elif missing == "link":
        document["provides"][1]["patches"] = []
    path.write_text(json.dumps(document), "utf-8")
    app.weapons.editor.provides = path
    _, report = call(app, "GET", "/capabilities")
    assert report["invoke629"]["supported"] is (missing is None)
    from types import SimpleNamespace
    target = SimpleNamespace(client_provides=path)
    if missing is None:
        _invoke_evidence(target)
    else:
        with pytest.raises(ValueError):
            _invoke_evidence(target)
    assert report["scope"] == "provides-declaration" and report["runtime"] == "未执行"


@pytest.mark.parametrize("kind,item_id,size", [("weapon", None, [20, 20]),
                                             ("soul", None, [40, 40]), ("material", "1", [40, 40])])
def test_icon_dimensions_have_one_json_shape(app, kind, item_id, size):
    atlas(app.source.view.files)
    request = {"kind": kind, "png": png(tuple(size))}
    if item_id:
        request["item_id"] = item_id
    code, report = call(app, "POST", "/5010005/icon", request, {"preview": ["true"]})
    assert code == 200
    icon = report["icons"][0]
    assert icon["size"] == size
    assert icon["atlasSize"] == (None if kind == "weapon" else [100, 100])
