"""Append the local battle to one pinned Wiki snapshot; never deploy or rebuild its Worker."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import gzip
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

from wf_wiki_battle_content import build_content
from wf_wiki_paths import is_junction

REPO = Path(__file__).resolve().parents[1]
UI_ROOT = Path(__file__).resolve().parent / "wiki"
FROZEN_MANIFEST_SHA256 = "e1a7353d53be2404b6a1b8b3b7989fd14820479b3ebeff902218ca83f4596aa7"
UI_REPLACEMENTS = frozenset({"index.html", "router.js", "pages.js", "dungeons.js"})
BATTLE_ASSETS = frozenset({"battle-" + name + ".js" for name in
    ("loader", "model", "targets", "effects", "waves", "clock", "media", "render", "input", "storage", "selection", "page")} | {"battle.css"})
# Keep the small source module separate, but deliver it with its renderer so
# battle still adds 16 public files and no additional network round trip.
SOURCE_FRAGMENTS = frozenset({"battle-vfx.js"})
RESERVED = frozenset({"_worker.js", "_headers", "_routes.json"})
MAX_STATIC_FILES, MAX_ADDED_FILES = 20000, 16
MAX_FILE_BYTES, MAX_CONTENT_BYTES = 25 * 1024 * 1024, 256 * 1024
DEFINITION_FILES = tuple("characters-" + element + ".json" for element in
                         ("fire", "water", "thunder", "wind", "light", "dark")) + ("stages.json",)


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _relative(name):
    _require(isinstance(name, str) and re.fullmatch(r"[A-Za-z0-9_./-]+", name)
             and not name.startswith("/") and all(p not in ("", ".", "..") for p in name.split("/")), "不安全的相对路径")
    return name


def _safe_path(path):
    path = Path(os.path.abspath(path))
    for part in (path, *path.parents):
        _require(not part.is_symlink() and not is_junction(part), "拒绝链接或重解析路径：" + str(part))
    return path


def _inventory(root):
    _require(root.is_dir(), "缺少冻结目录")
    result = {}
    for directory, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            _safe_path(Path(directory) / name)
        for name in files:
            path = Path(directory) / name
            key = _relative(path.relative_to(root).as_posix())
            _require(path.is_file(), "拒绝非普通文件")
            result[key] = path
    return result


def _entries(files):
    def measure(item):
        name, file = item
        _require(file.stat().st_size < MAX_FILE_BYTES, "单文件超过公开包限制：" + name)
        raw = file.read_bytes()
        return name, {"path": name, "bytes": len(raw), "sha256": _sha(raw)}
    with ThreadPoolExecutor(max_workers=8) as pool:
        return dict(pool.map(measure, sorted(files.items())))


def _frozen(site):
    manifest = _safe_path(site.with_name(site.name + "-sha256.json"))
    raw = manifest.read_bytes()
    _require(_sha(raw) == FROZEN_MANIFEST_SHA256, "冻结清单未获确认或已变化")
    data = json.loads(raw)
    old, folded = {}, set()
    for item in data["files"]:
        name = _relative(item["path"])
        _require(name.casefold() not in folded, "冻结清单路径重复")
        folded.add(name.casefold())
        old[name] = item
    files = _inventory(site)
    _require(set(files) == set(old) and _entries(files) == old, "冻结输入文件缺失、额外文件或哈希变化")
    _require(RESERVED <= set(old) and UI_REPLACEMENTS <= set(old), "冻结包缺少入口或 Worker")
    return files, old, manifest


def _head():
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO).decode().strip()


def _committed(paths):
    names = [p.resolve().relative_to(REPO.resolve()).as_posix() for p in paths]
    head = _head()
    raw = subprocess.run(["git", "cat-file", "--batch"], cwd=REPO, check=True,
        input="".join(head + ":" + name + "\n" for name in names).encode(), capture_output=True).stdout
    result, offset = {}, 0
    for path in paths:
        end = raw.index(b"\n", offset)
        fields = raw[offset:end].split()
        _require(len(fields) == 3 and fields[1] == b"blob", "未提交源码：" + str(path))
        size = int(fields[2])
        result[path] = raw[end + 1:end + 1 + size]
        offset = end + 2 + size
    return result


def _public_text(name, raw):
    text = raw.decode("utf-8")
    forbidden = r"(?<!\w)[A-Za-z]:[\\/]|file://[A-Za-z/]|https?://(?:localhost|127\.|10\.|192\.168\.)|-----BEGIN .*PRIVATE KEY|sourceMappingURL|sourceURL"
    secret = r'''(?<![\w-])(?:api[_-]?key|password|passwd|access[_-]?token|refresh[_-]?token|client[_-]?secret)["']?\s*[:=]\s*(["'])([^"'\r\n]+)\1'''
    _require(not re.search(forbidden, text, re.I) and not re.search(secret, text, re.I), "公开内容包含私密路径或凭据：" + name)


class _References(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.scripts, self.styles = [], []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        if tag == "script":
            _require("src" in data and "defer" in data, "首页只允许 defer 外部脚本")
            self.scripts.append(_relative(data["src"].split("?", 1)[0]))
        if tag == "link" and data.get("rel") == "stylesheet":
            self.styles.append(data["href"].split("?", 1)[0])


def _html(base, source, blobs, version):
    before, after = _References(base), _References(source)
    _require(after.scripts.count("battle-loader.js") == 1 and
        [s for s in after.scripts if s != "battle-loader.js"] == before.scripts,
        "首页只能按原顺序增加 battle-loader")
    _require(not (set(before.scripts) & BATTLE_ASSETS) and "battle.css" not in after.styles,
             "首页不得加载运行时或玩法样式")
    loader_at = after.scripts.index("battle-loader.js")
    tag = f'<script src="battle-loader.js?v={version}" data-battle-version="{version}" defer></script>'
    # Edit the frozen HTML, not a fresh whole-site export or unrelated source WIP.
    if loader_at + 1 < len(after.scripts):
        next_script = re.escape(after.scripts[loader_at + 1])
        pattern = r'<script\b[^>]*\bsrc="' + next_script + r'(?:\?[^"<>]*)?"[^>]*>'
        base, count = re.subn(pattern, lambda m: tag + "\n  " + m.group(), base, count=1)
        _require(count == 1, "首页脚本锚点缺失")
    else:
        _require("</head>" in base, "首页 head 缺失")
        base = base.replace("</head>", tag + "\n</head>", 1)
    for name in UI_REPLACEMENTS - {"index.html"}:
        base = re.sub(r'src="' + re.escape(name) + r'(?:\?[^"<>]*)?"',
                      'src="' + name + '?v=' + _sha(blobs[name])[:12] + '"', base)
    _require(_References(base).scripts == after.scripts and _References(base).styles == before.styles,
             "首页原有脚本或样式变化")
    return base.encode("utf-8")


def _media_urls(content):
    def image_urls(image):
        yield image["url"]
        if "poster" in image:
            yield from image_urls(image["poster"])
    yield from image_urls(content["coffin"])
    for media in content["media"].values():
        yield media["avatar"]
        for image in media["actions"].values():
            yield from image_urls(image)
        for field in ("voices", "seCues"):
            for pool in media.get(field, {}).values():
                yield from pool


def _media(content, site, evidence, old):
    added = {}
    for name in sorted(set(_media_urls(content))):
        _relative(name)
        _require(name.startswith("media/"), "媒体必须使用站内 media/ 路径")
        path = site / name if name in old else evidence.parent / "battle-native-media" / name
        path = _safe_path(path)
        _require(path.is_file(), "媒体引用不存在：" + name)
        actual = _sha(path.read_bytes())
        _require(Path(name).stem == actual, "媒体内容寻址哈希不符：" + name)
        if name not in old:
            _require(name.startswith("media/battle/") and path.suffix in (".webp", ".mp3"), "未允许的新增媒体")
            added[name] = path
    return added


def _prepare(site, output, definitions, evidence):
    site, output, definitions, evidence = map(_safe_path, (site, output, definitions, evidence))
    _require(not os.path.lexists(output) and output.parent.is_dir(), "目标必须是已有父目录下的新目录")
    _require(not output.is_relative_to(site) and not site.is_relative_to(output)
             and not output.is_relative_to(REPO.resolve()), "拒绝覆盖源目录或仓库")
    _require(not output.with_name(output.name + "-receipt.json").exists(), "目标回执已存在")
    files, old, manifest = _frozen(site)
    source_paths = sorted((_safe_path(UI_ROOT / n) for n in UI_REPLACEMENTS | BATTLE_ASSETS | SOURCE_FRAGMENTS))
    source_paths += [_safe_path(definitions / n) for n in DEFINITION_FILES]
    tool_paths = [Path(__file__).resolve(), Path(__file__).with_name("wf_wiki_battle_content.py").resolve(),
                  Path(__file__).with_name("wf_wiki_battle_native.py").resolve(),
                  Path(__file__).with_name("wf_wiki_paths.py").resolve()]
    source_paths += tool_paths
    source_commit = _head()
    committed = _committed(source_paths)
    _require(all(p.read_bytes() == raw for p, raw in committed.items()), "源码与已提交版本不符")
    source = {p.name: committed[p] for p in source_paths if p.parent == UI_ROOT}
    evidence_bytes = evidence.read_bytes()
    content = build_content(site, definitions, json.loads(evidence_bytes))
    payload = ("window.WF_BATTLE_CONTENT = " + json.dumps(content, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c") + ";\n").encode("utf-8")
    _require(len(payload) <= MAX_CONTENT_BYTES, "玩法内容超过 256 KiB 预算")
    additions = _media(content, site, evidence, old)
    blobs = {name: raw for name, raw in source.items() if name != "index.html" and name not in SOURCE_FRAGMENTS}
    blobs["battle-render.js"] = source["battle-vfx.js"] + b"\n;\n" + source["battle-render.js"]
    blobs["data/battle-content.js"] = payload
    versions = {n: _sha(raw) for n, raw in sorted(blobs.items())}
    versions.update({"source/" + n: _sha(source[n]) for n in SOURCE_FRAGMENTS | {"battle-render.js"}})
    versions.update({"definition/" + p.name: _sha(committed[p]) for p in source_paths if p.parent == definitions})
    version = _sha(json.dumps(versions, sort_keys=True, separators=(",", ":")).encode())[:16]
    blobs["index.html"] = _html((site / "index.html").read_text(encoding="utf-8"), source["index.html"].decode(), blobs, version)
    for name, raw in blobs.items():
        _public_text(name, raw)
    expected = dict(old)
    expected.update(_entries(additions))
    expected.update({n: {"path": n, "bytes": len(raw), "sha256": _sha(raw)} for n, raw in blobs.items()})
    added = sorted(set(expected) - set(old))
    _require(len(set(expected) - RESERVED) <= MAX_STATIC_FILES, "公开文件超过 20000 硬限")
    _require(len(added) <= MAX_ADDED_FILES, "新增文件超过 16 项预算")
    _require(set(expected) - set(old) == BATTLE_ASSETS | {"data/battle-content.js"} | set(additions), "新增路径超出白名单")
    _require(all(expected[n] == item for n, item in old.items() if n not in UI_REPLACEMENTS), "旧数据或 Worker 发生变化")
    _require(all(item["bytes"] < MAX_FILE_BYTES for item in expected.values()), "公开文件过大")
    for name, raw in blobs.items():
        for ref in re.findall(r'''["']((?:data/)?battle[-A-Za-z0-9./]+\.(?:js|css))["']''', raw.decode()):
            _require(ref in expected, "玩法静态引用缺失：" + ref)
    inputs = {p: _sha(raw) for p, raw in committed.items()}
    inputs.update({manifest: FROZEN_MANIFEST_SHA256, evidence: _sha(evidence_bytes)})
    inputs.update({p: p.stem for p in additions.values()})
    report = {"schema": 1, "version": version, "characters": len(content["characters"]),
        "files": len(expected), "staticFiles": len(set(expected) - RESERVED), "added": added,
        "modified": sorted(n for n in old if old[n] != expected[n]), "addedMedia": sorted(additions),
        "oldPayloadUnchanged": True, "workerUnchanged": all(old[n] == expected[n] for n in RESERVED),
        "frozenManifestSha256": FROZEN_MANIFEST_SHA256, "sourceCommit": source_commit,
        "sourceHashes": {**versions, "source/index.html": _sha(source["index.html"])},
        "toolHashes": {p.name: inputs[p] for p in tool_paths}, "mediaEvidenceSha256": _sha(evidence_bytes),
        "bytes": {n: {"raw": len(raw), "gzip": len(gzip.compress(raw, mtime=0))} for n, raw in sorted(blobs.items())},
        "manifest": sorted(expected.values(), key=lambda x: x["path"])}
    return site, output, files, old, blobs, additions, expected, inputs, report


def build_candidate(site_root: Path, output: Path, definitions_root: Path, media_evidence: Path, *, check_only=False) -> dict:
    site, output, files, old, blobs, added, expected, inputs, report = _prepare(
        site_root, output, definitions_root, media_evidence)
    _require(all(_sha(p.read_bytes()) == sha for p, sha in inputs.items()), "构建输入期间发生变化")
    _require(_head() == report["sourceCommit"], "构建输入 HEAD 发生变化")
    if check_only:
        return report
    output.mkdir()
    for name, path in {**files, **added}.items():
        if name in blobs:
            continue
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)  # Independent bytes: never hard-link the frozen release.
    for name, raw in blobs.items():
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    _require(_entries(_inventory(output)) == expected, "候选包最终哈希不符")
    _require(_entries(_inventory(site)) == old, "构建期间冻结源发生变化")
    _require(all(_sha(p.read_bytes()) == sha for p, sha in inputs.items()), "构建期间输入发生变化")
    _require(_head() == report["sourceCommit"], "构建期间 HEAD 发生变化")
    output.with_name(output.name + "-receipt.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("site-root", "output", "definitions", "media-evidence"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args(argv)
    report = build_candidate(args.site_root, args.output, args.definitions, args.media_evidence, check_only=args.check_only)
    print(json.dumps({key: report[key] for key in ("version", "characters", "staticFiles", "added", "modified")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
