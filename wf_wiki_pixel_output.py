"""Bounded, content-addressed pixel output with verified incremental reuse."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from wf_wiki_pixel_render import ACTIONS, LABELS
from wf_wiki_paths import is_junction

URL = re.compile(r"media/pixels/[0-9a-f]{64}\.webp")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def checked_path(path):
    path = Path(path).absolute()
    if any(p.is_symlink() or is_junction(p) for p in (path, *path.parents)):
        raise ValueError("像素导出路径不能含符号链接或目录联接")
    return path.resolve()


class PixelOutput:
    def __init__(self, output, repo, store):
        self.root = checked_path(output)
        for protected in (Path(repo).resolve(), Path(store).resolve().parent):
            if self.root == protected or self.root in protected.parents:
                raise ValueError("像素输出不能覆盖来源或其上级目录")
        if self.root.is_relative_to(Path(store).resolve().parent):
            raise ValueError("像素输出不能放在游戏数据目录")
        if self.root.is_relative_to(Path(repo).resolve()) and not self.root.is_relative_to(Path(repo).resolve() / "work"):
            raise ValueError("仓库内像素导出只允许 work 目录")
        marker = checked_path(self.root / ".wf-wiki-export.json")
        if not marker.is_file() or json.loads(marker.read_bytes()).get("generator") != "wf_wiki":
            raise ValueError("像素增量导出需要已有的 Wiki 输出目录")
        for relative in ("media/pixels", "data"):
            checked_path(self.root / relative).mkdir(parents=True, exist_ok=True)
        self.verified = {}

    def path(self, relative):
        if not URL.fullmatch(relative) and relative not in ("data/pixel-previews.json", "data/pixel-previews.js"):
            raise ValueError("像素输出路径不在指定范围")
        return checked_path(self.root / relative)

    def write(self, relative, raw):
        target = self.path(relative)
        if target.is_file() and target.read_bytes() == raw:
            return
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".pixels-", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(raw)
        try:
            self.path(relative)  # Recheck before atomic replacement.
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)

    def save(self, raw):
        url = f"media/pixels/{digest(raw)}.webp"
        self.write(url, raw)
        self.verified[url] = len(raw)
        return url

    def valid_media(self, url):
        if not isinstance(url, str) or not URL.fullmatch(url):
            return False
        if url in self.verified:
            return True
        path = self.path(url)
        if not path.is_file():
            return False
        raw = path.read_bytes()
        if digest(raw) != path.stem:
            return False
        self.verified[url] = len(raw)
        return True

    def reusable(self, record, revision):
        if not isinstance(record, dict) or record.get("sourceRevision") != revision:
            return False
        if set(record) != {"sourceRevision", "poster", "actions", "unavailable", "note"}:
            return False
        if (not isinstance(record["unavailable"], list)
                or any(not isinstance(item, dict) or set(item) != {"kind", "label", "reason"}
                       or item["kind"] not in ("special_pose", "skill")
                       or item["label"] != LABELS[item["kind"]]
                       or item["reason"] != "动作资源暂不能完整预览" for item in record["unavailable"])):
            return False
        def poster(value):
            return (isinstance(value, dict) and set(value) == {"url", "width", "height"}
                    and all(type(value[k]) is int and 0 < value[k] <= 8192 for k in ("width", "height"))
                    and self.valid_media(value["url"]))
        actions = record.get("actions")
        if not poster(record.get("poster")) or not isinstance(actions, list) or not actions:
            return False
        kinds = set()
        for action in actions:
            if not isinstance(action, dict) or set(action) != {"kind", "label", "url", "poster", "width", "height", "durationMs", "animated", "loop"}:
                return False
            kind = action["kind"]
            if not isinstance(kind, str) or kind in kinds or LABELS.get(kind) != action["label"]:
                return False
            kinds.add(kind)
            if (not poster(action["poster"]) or not self.valid_media(action["url"])
                    or any(action[k] != action["poster"][k] for k in ("width", "height"))
                    or type(action["durationMs"]) is not int or not 0 < action["durationMs"] <= 60_017
                    or type(action["animated"]) is not bool or type(action["loop"]) is not bool):
                return False
        return all(kind in kinds for _, kind, _ in ACTIONS)

    def previous(self):
        try:
            value = json.loads(self.path("data/pixel-previews.json").read_bytes())
            return value.get("characters", {}) if value.get("format") == 1 else {}
        except (OSError, ValueError, AttributeError):
            return {}

    def publish(self, index):
        raw = json.dumps(index, ensure_ascii=False, separators=(",", ":"))
        self.write("data/pixel-previews.js", ("window.WF_PIXEL_PREVIEWS=" + raw.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029") + ";\n").encode("utf-8"))
        self.write("data/pixel-previews.json", (raw + "\n").encode("utf-8"))
