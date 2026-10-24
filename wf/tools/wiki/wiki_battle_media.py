"""Resolve pinned native proof into public battle media; never write game data."""
from __future__ import annotations

from bisect import bisect_left
import hashlib
import io
import json
import math
from pathlib import Path
import re

from PIL import Image
import wf_assets
from wf_pixelart_vfx import entry_for_frame, restore_frame
from wf_wiki_pixel_output import checked_path
from wf_wiki_pixel_render import family, sequence_frames, tree, webp
from wf_wiki_ui_assets import atlas_entries, crop_sprite

PUBLIC_ID = re.compile(r"c[0-9a-f]{12}\Z")
MEDIA_URL = re.compile(r"media/(?:[a-z-]+/)?[0-9a-f]{64}\.(?:webp|mp3)\Z")
SOURCE_NAMES = {"sprite_sheet.png", "sprite_sheet.atlas.amf3.deflate",
                "pixelart.frame.amf3.deflate", "pixelart.timeline.amf3.deflate"}
ORIGINS = {"新增MOD", "灰服独立角色资料", "改版官方"}
COFFIN = "battle/common/layer0/.gen/coffin/f0089"
CUES = {"deploy": r"战斗开始(?: \d+)?", "ready": r"技能准备(?: \d+)?",
        "cast": r"技能发动(?: \d+)?", "death": r"阵亡(?: \d+)?"}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _number(value, limit=8192):
    if type(value) not in (int, float) or not math.isfinite(value) or abs(value) > limit:
        raise ValueError("原生动作坐标无效")
    return value


class Reader:
    def __init__(self):
        self.watched = {}

    def read(self, path, expected, limit=32 * 1024 * 1024):
        path = checked_path(path)
        if not re.fullmatch(r"[0-9a-f]{64}", str(expected)) or path.stat().st_size > limit:
            raise ValueError("来源哈希或大小无效")
        raw = path.read_bytes()
        if digest(raw) != expected:
            raise ValueError("来源哈希发生变化")
        self.watched[path] = expected
        return raw

    def pin(self, spec):
        if not isinstance(spec, dict) or set(spec) != {"path", "sha256"}:
            raise ValueError("原生来源需要精确路径和哈希")
        return self.read(spec["path"], spec["sha256"])

    def media(self, site, url):
        if not isinstance(url, str) or not MEDIA_URL.fullmatch(url):
            raise ValueError("公开媒体 URL 路径无效")
        return self.read(site / url, Path(url).stem)

    def verify(self):
        for path, expected in self.watched.items():
            if not path.is_file() or digest(path.read_bytes()) != expected:
                raise ValueError("媒体验证期间来源哈希发生变化")


def _script(raw, prefix):
    text = raw.decode("utf8").strip()
    if not text.startswith(prefix) or not text.endswith(";"):
        raise ValueError("公开数据脚本格式不匹配")
    return json.loads(text[len(prefix):-1])


def _rgba(image):
    # Hidden RGB under alpha=0 is not visible content and may differ after WebP.
    image = image.convert("RGBA")
    zero = Image.new("RGBA", image.size)
    zero.paste(image, mask=image.getchannel("A").point(lambda a: 255 if a else 0))
    return zero.tobytes()


def _public_frames(raw):
    frames, durations = [], []
    with Image.open(io.BytesIO(raw)) as im:
        if im.format != "WEBP" or max(im.size) > 8192 or im.width * im.height > 16_777_216:
            raise ValueError("公开像素格式或大小无效")
        if not 1 <= im.n_frames <= 3601:
            raise ValueError("公开像素帧数无效")
        for i in range(im.n_frames):
            im.seek(i); im.load()
            frames.append(im.convert("RGBA")); durations.append(im.info.get("duration", 0))
    return frames, durations


def _same_frames(expected, durations, actual, actual_durations):
    if len(expected) != len(actual):
        return False
    if len(actual) > 1 and durations != actual_durations:
        return False
    return all(a.size == b.size and _rgba(a) == _rgba(b) for a, b in zip(expected, actual))


def _native_action(raw, name):
    sheet, index, sequences = family(raw)
    sequence = next((s for s in sequences if s["name"] == name), None)
    if sequence is None:
        return None
    frames, durations = sequence_frames(sheet, index, sequence)
    boxes, position = [], sequence["begin"]
    while position <= sequence["end"]:
        original = restore_frame(sheet, entry_for_frame(index, position))
        if original.getbbox():
            boxes.append(original.getbbox())
        position = index[0][bisect_left(index[0], position)] + 1
    left, top = min(b[0] for b in boxes) - 2, min(b[1] for b in boxes) - 2
    origin = tree(raw["pixelart.frame.amf3.deflate"])
    anchor = (-_number(origin["x"]) - left, -_number(origin["y"]) - top)
    return frames, durations, anchor


def _image_def(url, size, anchor, duration=0, animated=False):
    return {"url": url, "width": size[0], "height": size[1], "anchorX": anchor[0],
            "anchorY": anchor[1], "duration": duration, "animated": animated}


def _action(reader, site, action, native, missing):
    frames, durations, anchor = native
    poster = action.get("poster", {})
    static, _ = _public_frames(reader.media(site, poster.get("url")))
    if not _same_frames(frames[:1], [], static, []):
        raise ValueError("公开静帧与本角色原生动作无法匹配，拒绝猜测锚点")
    if (poster.get("width"), poster.get("height")) != static[0].size:
        raise ValueError("公开静帧尺寸声明不匹配")
    result = _image_def(poster["url"], static[0].size, anchor)
    animation, actual_durations = _public_frames(reader.media(site, action.get("url")))
    if (_same_frames(frames, durations, animation, actual_durations)
            and (action.get("width"), action.get("height")) == frames[0].size
            and action.get("durationMs") == sum(durations)
            and action.get("animated") == (len(animation) > 1)):
        result = _image_def(action["url"], frames[0].size, anchor,
                            sum(durations) / 1000, len(animation) > 1)
    else:
        missing.append(f"{action['kind']} 动画来源未匹配，使用已验证同角色静帧")
    result["poster"] = _image_def(poster["url"], static[0].size, anchor)
    return result


def _voices(reader, site, chunk, overrides):
    pools = {cue: [] for cue in (*CUES, "se")}
    for voice in chunk.get("voices", []):
        if voice.get("category") not in ("战斗", "battle"):
            continue
        cue = next((key for key, pattern in CUES.items()
                    if re.fullmatch(pattern, voice.get("label", ""))), None)
        if cue is None:
            continue
        url = voice.get("audio")
        raw = reader.media(site, url)
        if not url.endswith(".mp3") or not wf_assets.mp3_probe(raw, 2047)["frames"]:
            raise ValueError("公开语音格式无效")
        if url not in pools[cue]:
            pools[cue].append(url)
    if not isinstance(overrides, dict) or set(overrides) - set(pools):
        raise ValueError("未知语音事件覆盖")
    for cue, urls in overrides.items():
        if (not isinstance(urls, list) or len(set(urls)) != len(urls)
                or any(url not in pools[cue] for url in urls)):
            raise ValueError("语音覆盖不是已核实的本角色对应事件来源")
        pools[cue] = urls
    return pools


def _coffin(reader, spec):
    raw = {key: reader.pin(spec["sources"][key]) for key in ("sheet", "atlas", "frame")}
    with Image.open(io.BytesIO(wf_assets.png_decode(raw["sheet"]))) as image:
        if max(image.size) > 8192 or image.width * image.height > 16_777_216:
            raise ValueError("原生棺材图集过大")
        sheet = image.convert("RGBA")
    entries = [e for e in atlas_entries(tree(raw["atlas"])) if e["n"] == COFFIN]
    if len(entries) != 1 or (entries[0].get("fw"), entries[0].get("fh")) != (64, 64):
        raise ValueError("原生棺材 f0089 必须是 64×64 原帧")
    entry = entries[0]
    if any(type(entry.get(key)) is not int for key in ("x", "y", "w", "h", "fw", "fh", "fx", "fy")):
        raise ValueError("原生棺材几何必须是整数")
    dx, dy = -entry["fx"], -entry["fy"]
    width, height = (entry["h"], entry["w"]) if entry.get("r") else (entry["w"], entry["h"])
    if min(dx, dy) < 0 or dx + width > 64 or dy + height > 64:
        raise ValueError("原生棺材偏移越界")
    image = crop_sprite(sheet, entry)
    if not image.getbbox():
        raise ValueError("原生棺材不能为透明帧")
    origin = tree(raw["frame"])
    anchor = (-_number(origin["x"]), -_number(origin["y"]))
    encoded = webp([image])
    return _image_def(f"media/battle/{digest(encoded)}.webp", (64, 64), anchor), encoded


def _native_se(reader, specs, rules, pending):
    """Curated same-body event mapping, proven by native timeline + audio hash."""
    pools = {cue: [] for cue in ('deploy', 'cast', 'attack', 'death')}
    if not isinstance(rules, list) or len(rules) > 8 or not isinstance(specs, dict):
        raise ValueError("原生音效证据格式无效")
    required = set()
    for rule in rules:
        if (not isinstance(rule, dict) or set(rule) != {'cue', 'timeline', 'sound', 'sequence', 'begin', 'decodedSha256'}
                or rule['cue'] not in pools or type(rule['begin']) is not int
                or not re.fullmatch(r'battle/[a-z0-9_/]+\.timeline\.amf3\.deflate', str(rule['timeline']))
                or not re.fullmatch(r'sound_effect/[a-z0-9_/]+', str(rule['sound']))):
            raise ValueError("原生音效事件登记无效")
        audio_key = rule['sound'] + '.mp3'
        required.update((rule['timeline'], audio_key))
        if rule['timeline'] not in specs or audio_key not in specs:
            raise ValueError("缺少原生音效来源证据")
        timeline = tree(reader.pin(specs[rule['timeline']]))
        sequence = [s for s in timeline.get('sequences', []) if s.get('name') == rule['sequence']
                    and s.get('begin', -1) <= rule['begin'] <= s.get('end', -1)]
        sound = [s for s in timeline.get('sounds', []) if s.get('path') == rule['sound']
                 and s.get('begin') == rule['begin'] and s.get('loop') == 1]
        if len(sequence) != 1 or len(sound) != 1:
            raise ValueError("原生音效不是已登记的一次性动作事件")
        raw = wf_assets.mp3_decode(reader.pin(specs[audio_key]))
        probe = wf_assets.mp3_probe(raw, 2047)
        if digest(raw) != rule['decodedSha256'] or not probe['frames'] or probe['end'] != len(raw):
            raise ValueError("原生音效解码哈希或 MP3 格式无效")
        url = f'media/battle/{digest(raw)}.mp3'
        pending[url] = raw
        if url not in pools[rule['cue']]:
            pools[rule['cue']].append(url)
    if set(specs) != required:
        raise ValueError("原生音效证据含未登记来源")
    return pools


def resolve_native_media(repo: Path, evidence: dict, output: Path) -> dict:
    """Only pinned files are read; verified native media is written outside inputs.

    Evidence is private: {schema:1,site:{path,catalogSha256,pixelsSha256},
    characters:{publicId:{sources:{nativeFilename:{path,sha256}}}},
    coffin:{sources:{sheet,atlas,frame}}}. Output contains no source paths.
    """
    repo, output = checked_path(repo), checked_path(output)
    if evidence.get("schema") != 1:
        raise ValueError("媒体证据版本无效")
    site = checked_path(evidence["site"]["path"])
    for protected in (repo, site):
        if output == protected or output in protected.parents or protected in output.parents:
            raise ValueError("媒体输出不能覆盖来源或放入游戏/冻结站点目录")
    reader = Reader()
    catalog = _script(reader.read(site / "data.js", evidence["site"]["catalogSha256"]), "window.WF_WIKI = ")
    pixels = _script(reader.read(site / "data/pixel-previews.js", evidence["site"]["pixelsSha256"]), "window.WF_PIXEL_PREVIEWS=")
    selected = [c for c in catalog["characters"] if c.get("origin") in ORIGINS]
    roster = {c["id"]: c for c in selected}
    if len(roster) != len(selected):
        raise ValueError("公开 MOD 白名单角色重复")
    if not roster or set(roster) != set(evidence["characters"]) or any(not PUBLIC_ID.fullmatch(cid) for cid in roster):
        raise ValueError("媒体证据必须精确覆盖公开 MOD 白名单")
    override_path = checked_path(repo / "mod-tools/wiki-battle/media-overrides.json")
    overrides = (json.loads(reader.read(override_path, digest(override_path.read_bytes())))
                 if override_path.is_file() else {"schema": 1, "characters": {}})
    if overrides.get("schema") != 1 or set(overrides.get("characters", {})) - set(roster):
        raise ValueError("媒体覆盖含未知角色")
    result, pending = {}, {}
    for cid, character in roster.items():
        specs = evidence["characters"][cid]["sources"]
        if set(specs) != SOURCE_NAMES:
            raise ValueError("原生像素输入必须是四个明确文件")
        raw = {name: reader.pin(spec) for name, spec in specs.items()}
        actions = {a["kind"]: a for a in pixels["characters"][cid]["actions"]}
        missing, verified = [], {}
        override = overrides["characters"].get(cid, {})
        if set(override) - {"voices", "anchors", "nativeSe"}:
            raise ValueError("未知媒体覆盖字段")
        if not isinstance(override.get("anchors", {}), dict) or set(override.get("anchors", {})) - {"idle", "skill_ready"}:
            raise ValueError("未知动作锚点覆盖")
        for kind, native_name in (("idle", "neutral"), ("skill_ready", "skill_ready")):
            native = _native_action(raw, native_name)
            if kind not in actions or native is None:
                if kind == "idle":
                    raise ValueError("缺少可核实的本角色待机动作")
                verified[kind] = dict(verified["idle"]["poster"])
                missing.append("准备动作尚未确认，使用已验证同角色待机静帧")
                continue
            verified[kind] = _action(reader, site, actions[kind], native, missing)
            expected = override.get("anchors", {}).get(kind)
            if expected and expected != {k: verified[kind][k] for k in ("url", "anchorX", "anchorY")}:
                raise ValueError("已登记锚点与本次原生验证不一致")
        avatar = character.get("icon") or character.get("media", {}).get("square0")
        reader.media(site, avatar)
        chunk = catalog["dataManifest"]["chunks"]["character:" + cid]
        if not re.fullmatch(r"data/[A-Za-z0-9_-]+\.js", chunk["url"]):
            raise ValueError("角色分包路径无效")
        body = _script(reader.read(site / chunk["url"], chunk["sha256"]),
                       'window.WF_WIKI_CHUNKS = window.WF_WIKI_CHUNKS || {};\n'
                       f'window.WF_WIKI_CHUNKS["character:{cid}"] = ')
        if body.get("id") != cid:
            raise ValueError("语音分包不是当前角色")
        voices = _voices(reader, site, body, override.get("voices", {}))
        se_cues = _native_se(reader, evidence['characters'][cid].get('nativeSe', {}),
                            override.get('nativeSe', []), pending)
        for cue, label in (("deploy", "出战"), ("ready", "准备"), ("cast", "发动")):
            if not voices[cue]:
                missing.append(f"{label}暂无已核实台词，使用原生音效" if se_cues.get(cue) else f"{label}音源尚未确认")
        result[cid] = {"avatar": avatar, "actions": verified, "voices": voices, "missingCues": missing}
        if any(se_cues.values()):
            result[cid]['seCues'] = se_cues
    coffin, encoded = _coffin(reader, evidence["coffin"])
    pending[coffin['url']] = encoded
    if any(output == path or output in path.parents for path in reader.watched):
        raise ValueError("输出会覆盖已核验原生来源")
    reader.verify()
    destinations = {checked_path(output / url): raw for url, raw in pending.items()}
    if any(path.exists() and path.read_bytes() != raw for path, raw in destinations.items()):
        raise ValueError("现有原生媒体输出哈希不符")
    for path, raw in destinations.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_bytes(raw)
    return {"media": result, "coffin": coffin}
