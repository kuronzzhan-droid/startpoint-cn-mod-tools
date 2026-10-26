"""A new uploaded portrait defaults to a transparent icon backdrop (official convention).

贝瑞塔 1.4.299: the clone's square icon carried the parent's painted gradient, which the
recrop applied over the new art's transparent sky. The painted backdrop is now only offered.
"""
import io
import json

from PIL import Image

from wf.studio.portrait import PortraitService


class _Store:
    def __init__(self, files):
        self.files = files

    def read_file(self, cid, name):
        return self.files.get(name)


def _png(size=(64, 96)):
    stream = io.BytesIO()
    image = Image.new("RGBA", size, (0, 0, 0, 0))
    image.paste((200, 120, 90, 255), (16, 24, 48, 90))  # a visible figure; the rest stays transparent
    image.save(stream, format="PNG")
    return stream.getvalue()


def _service(monkeypatch, backdrop):
    store = _Store({"sources/portrait_0.png": _png(), "sources/portrait_0.json": json.dumps({}).encode()})
    service = PortraitService(source=None, assets=None, store=store)
    monkeypatch.setattr(service, "current_geometry", lambda cid, form: {"face": None})
    monkeypatch.setattr(service, "current_backdrop", lambda code, form: (True, backdrop))
    monkeypatch.setattr(service, "view_full_shot", lambda code, form: None)
    return service


def test_upload_ignores_painted_backdrop_but_offers_it(monkeypatch):
    painted = {"inner": [200, 180, 40], "outer": [60, 20, 80]}
    info = _service(monkeypatch, painted).source_info("139988", "x", "0", "thunder")
    assert info["upload"]["template"]["backdrop"] is None
    assert info["upload"]["currentBackdrop"] == painted


def test_upload_with_transparent_existing_icon_offers_nothing(monkeypatch):
    info = _service(monkeypatch, None).source_info("139988", "x", "0", "thunder")
    assert info["upload"]["template"]["backdrop"] is None
    assert "currentBackdrop" not in info["upload"]


def test_recrop_of_current_art_keeps_and_offers_existing_backdrop(monkeypatch):
    painted = {"inner": [200, 180, 40], "outer": [60, 20, 80]}
    service = _service(monkeypatch, painted)
    monkeypatch.setattr(service, "view_full_shot", lambda code, form: (Image.open(io.BytesIO(_png())), _png()))
    info = service.source_info("139988", "x", "0", "thunder")
    assert info["current"]["template"]["backdrop"] == painted
    assert info["current"]["currentBackdrop"] == painted
