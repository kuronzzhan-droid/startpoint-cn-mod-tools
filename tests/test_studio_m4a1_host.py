"""GET/HEAD must reject rebound hosts before reading drafts or session HTML."""
import json

import pytest

from test_studio_drafts import live, _request
from wf.studio.guard import GuardError, WriteGuard


@pytest.mark.parametrize("host", [None, "", "attacker.test", "localhost:1", "127.0.0.1:8790.attacker.test"])
def test_read_host_validation_rejects_untrusted_names(host):
    with pytest.raises(GuardError, match="Host"):
        WriteGuard(8790).check_host({"Host": host})


@pytest.mark.parametrize("method", ["GET", "HEAD"])
@pytest.mark.parametrize("path", ["/api/drafts/7", "/api/drafts/7/file?path=files/private.png",
                                  "/api/drafts/7/ability", "/"])
def test_rebinding_cannot_read_draft_or_session_token(live, method, path):
    port, guard, app = live
    status, body = _request(port, method, path, headers={"Host": f"attacker.test:{port}"})
    assert status == 403 and guard.token.encode() not in body
    if method == "GET":
        assert json.loads(body)["code"] == "studio_bad_host"


def test_local_get_remains_available_without_write_token(live):
    port, guard, app = live
    status, body = _request(port, "GET", "/api/drafts/7", headers={"Host": f"localhost:{port}"})
    assert status == 200 and json.loads(body)["status"]["state"] == "clean"
