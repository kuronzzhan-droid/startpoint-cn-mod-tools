"""Independent, version-bound mode drafts; never a game/store write target."""
import json
import os
import threading

from wf.deliver.changeset import member_name
from wf.view.safety import local_output
from .drafts import DraftError, now, sha256

MODES = ("five", "rogue")


class ViewInputs:
    def __init__(self, source):
        self.source, self.inputs = source, {}
        self._raw = {}

    def read(self, logical):
        if logical in self._raw:
            raw = self._raw[logical]
            if raw is None:
                raise FileNotFoundError(logical)
            return raw
        for root in ("common", "medium", "android"):
            key = root + ":" + logical
            try:
                raw = self.source.view.read_member(member_name(root, logical))[0]
            except FileNotFoundError:
                self.inputs[key] = None
                continue
            self.inputs[key] = sha256(raw)
            self._raw[logical] = raw
            return raw
        self._raw[logical] = None
        raise FileNotFoundError(logical)

    def verify(self):
        if hasattr(self.source.view, "verify"):
            self.source.view.verify()
        self._verify_inputs()

    def verify_read(self):
        """Revalidate a cached read: chain, ZIP stats and every hashed input."""
        view = self.source.view
        check = getattr(view, "verify_read", None) or getattr(view, "verify", None)
        if check:
            check()
        self._verify_inputs()

    def _verify_inputs(self):
        for key, digest in self.inputs.items():
            root, logical = key.split(":", 1) if ":" in key else ("common", key)
            try:
                raw = self.source.view.read_member(member_name(root, logical))[0]
                actual = sha256(raw)
            except FileNotFoundError:
                actual = None
            if actual != digest:
                raise DraftError("预览输入发生变化：" + logical)


class ModeStore:
    def __init__(self, root):
        self.root = root
        self.lock = threading.RLock()

    def directory(self, mode):
        if mode not in MODES:
            raise DraftError("未知模式")
        return local_output(self.root / mode)

    def load(self, mode):
        path = self.directory(mode) / "changeset.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text("utf8"))
        if data.get("subjectKind") != "mode" or data.get("characterId") != mode:
            raise DraftError("模式草稿身份不匹配")
        return data

    def save(self, mode, version, payload, inputs, preview, expected_revision):
        with self.lock:
            old = self.load(mode)
            if (old or {}).get("revision", 0) != expected_revision:
                raise DraftError("草稿已被其他窗口修改，请重新载入")
            revision, stamp = (old or {}).get("revision", 0) + 1, now()
            data = {"schema": "wf-studio-mode/1", "subjectKind": "mode", "characterId": mode,
                    "code": mode, "baseView": version, "createdAt": (old or {}).get("createdAt", stamp),
                    "updatedAt": stamp, "savedAt": stamp, "revision": revision, "savedRevision": revision,
                    "payload": payload, "inputs": inputs, "preview": preview, "changes": []}
            folder = self.directory(mode)
            folder.mkdir(parents=True, exist_ok=True)
            target = local_output(folder / "changeset.json")
            if target.exists() and target.stat().st_nlink > 1:
                raise DraftError("草稿文件不能是硬链接")
            temporary = local_output(folder / "changeset.tmp")
            if temporary.exists():
                raise DraftError("存在未完成的草稿临时文件")
            with temporary.open("x", encoding="utf8") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2, allow_nan=False)
            os.replace(temporary, target)
            return data
