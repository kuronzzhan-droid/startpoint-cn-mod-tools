"""Draft compilation must inspect generated text even without ability ops."""
from types import SimpleNamespace

import pytest
import wf_quest_lib as codec

from test_m1_text import workspace  # noqa: F401
from test_m51_text_rules import changed
from wf.studio.deliver_bridge import compile_draft
from wf.studio.deliver_media import MediaResult
from wf.studio.drafts import DraftError
from wf.text.model import CUSTOM, LEADER


def test_compile_draft_rejects_raw_139985_style_override_before_staging(workspace, monkeypatch):
    source = changed(workspace, {LEADER: {"1": "lady_android_halloween,0"},
        CUSTOM: {"desc_override_lady_android_halloween": "自身攻击力+100%"}})
    texts = source.table(CUSTOM)
    texts["desc_override_lady_android_halloween"] = "自身为队长时，自身攻击力+100%"
    output = MediaResult(members={("common", CUSTOM): codec.build_node(texts)})
    monkeypatch.setattr("wf.studio.deliver_media.compile_media", lambda *args: output)
    with pytest.raises(DraftError, match="text.standard.leader-slot"):
        compile_draft(SimpleNamespace(view=source.view), None, {"changes": []})
