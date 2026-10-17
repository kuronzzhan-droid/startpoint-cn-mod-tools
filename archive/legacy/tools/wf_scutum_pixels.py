"""保留作者GIF全部帧，将像素脚底对齐官方角色基线。只写离线候选。"""
import io
from pathlib import Path
import zlib

import numpy as np
from PIL import Image

import wf_assets
import wf_dsl
from wf_campus_art_images import png, sha
from wf_character_revision import encode_tree
from wf_scutum_seed import CODE, TEMPLATE_CODE
from wf_scutum_pixel_timeline import exposure_runs, loop_frames, retime


def read_frames(path):
    raw = Path(path).read_bytes()
    source = Image.open(io.BytesIO(raw))
    if source.size != (260, 300) or not getattr(source, 'is_animated', False):
        raise ValueError('requires original 260x300 animated source; static preview is not sufficient')
    frames, durations = [], []
    for index in range(source.n_frames):
        source.seek(index)
        image = source.convert('RGBA')
        sprite = image.resize((26, 30), Image.Resampling.NEAREST)
        if not np.array_equal(np.asarray(image), np.asarray(sprite.resize(image.size, Image.Resampling.NEAREST))):
            raise ValueError('source frame is not a lossless 10x pixel grid')
        duration = source.info.get('duration', 0)
        if not isinstance(duration, int) or duration <= 0 or sprite.getbbox() is None:
            raise ValueError('empty frame or invalid source duration')
        array = np.asarray(sprite).copy()
        array[array[:, :, 3] == 0] = 0
        frames.append(Image.fromarray(array))
        durations.append(duration)
    return raw, frames, durations


def _read(seed, logical):
    key = 'common', logical
    return seed.outputs[key] if key in seed.outputs else seed.read(*key)


def build(seed, source_path, output):
    raw, frames, durations = read_frames(source_path)
    period = loop_frames(durations)
    bottom = max(frame.getbbox()[3] for frame in frames)
    fy, fx = bottom - 129, -115
    unique, indices = [], []
    for frame in frames:
        existing = next((i for i, image in enumerate(unique) if image.tobytes() == frame.tobytes()), None)
        if existing is None:
            existing = len(unique)
            unique.append(frame)
        indices.append(existing)
    sheet = Image.new('RGBA', (32 * len(unique), 32))
    for i, frame in enumerate(unique):
        sheet.alpha_composite(frame, (i * 32, 0))
    prefix = f'character/{CODE}/pixelart/'
    counts, sequences = {}, {}
    for stem, animation in (('sprite_sheet', 'pixelart'), ('special_sprite_sheet', 'special')):
        frame_path = prefix + animation + '.frame.amf3.deflate'
        timeline_path = prefix + animation + '.timeline.amf3.deflate'
        frame = wf_dsl.parse_dsl(zlib.decompress(_read(seed, frame_path), -15))['tree']
        # Always start from official timing, including on repeated revisions.
        source_timeline = seed.official(timeline_path.replace(CODE, TEMPLATE_CODE))
        timeline = wf_dsl.parse_dsl(zlib.decompress(source_timeline, -15))['tree']
        timeline = retime(timeline, period)
        atlas = [dict(n=frame['name'] + f'{end:04d}', x=indices[pose] * 32, y=0,
                      w=26, h=30, fx=fx, fy=fy, fw=256, fh=256)
                 for end, pose in exposure_runs(timeline, durations)]
        frame.update(x=-128, y=-128, scale=3, smoothing=False)
        seed.emit('common', prefix + stem + '.atlas.amf3.deflate', encode_tree(atlas))
        seed.emit('common', prefix + stem + '.png', wf_assets.png_encode(png(sheet)))
        seed.emit('common', frame_path, encode_tree(frame))
        seed.emit('common', timeline_path, encode_tree(timeline))
        counts[animation] = len(atlas)
        sequences[animation] = timeline['sequences']
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / 'source.gif').write_bytes(raw)
    contact = Image.new('RGBA', (26 * len(frames), 30), '#303440')
    for i, frame in enumerate(frames):
        contact.alpha_composite(frame, (i * 26, 0))
    contact.resize((260 * len(frames), 300), Image.Resampling.NEAREST).save(output / 'frames.png')
    return dict(source=str(source_path), source_sha256=sha(raw), source_frames=len(frames),
                source_duration_ms=durations, unique_poses=len(unique), native_pixels=[26, 30],
                lossless_grid=True, display_scale=3, stable_single_pose=False,
                native_loop_frames=period, atlas_fx=fx, atlas_fy=fy,
                lowest_foot_y=-128-fy+bottom, frame_references=counts, sequences=sequences)
