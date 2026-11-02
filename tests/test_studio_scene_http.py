"""The new HTTP surface fails closed before reads or writes on invalid input."""
import json

import pytest

from test_studio_deliver_routes import _FakeSource
from wf.studio.drafts import DraftStore
from wf.studio.server import StudioApp


@pytest.mark.parametrize("payload", [{}, None, [], {"schema": "wrong"}, {"schema": "wf-boss-scene/1", "id": "../escape"}])
def test_studio_scene_bad_schema_is_400_not_500_or_disk_write(tmp_path, payload):
    root = tmp_path / "drafts"
    app = StudioApp(_FakeSource(), drafts=DraftStore(root))
    response = app.dispatch("POST", "/api/scenes/hell-pumpkin/preview", {}, {"payload": payload})
    assert response.status == 400 and json.loads(response.body)["error"]
    assert not root.exists()


def test_studio_scene_schema_is_readable_and_opening_has_no_write_method(tmp_path):
    root = tmp_path / "drafts"
    app = StudioApp(_FakeSource(), drafts=DraftStore(root))
    response = app.dispatch("GET", "/api/scenes/schema", {})
    assert response.status == 200 and json.loads(response.body)["$id"] == "wf-boss-scene/1"
    response = app.dispatch("POST", "/api/studio/opening", {}, {"server": "local"})
    assert response.status == 405
    assert not root.exists()


@pytest.mark.parametrize("query", [{"server": ["production"]}, {"root": ["untrusted"]},
    {"server": ["local", "test175"]}, {"execute": ["true"]}])
def test_studio_opening_rejects_target_and_action_injection(tmp_path, query):
    app = StudioApp(_FakeSource(), drafts=DraftStore(tmp_path / "drafts"))
    response = app.dispatch("GET", "/api/studio/opening", query)
    assert response.status == 400
    assert not (tmp_path / "drafts").exists()
