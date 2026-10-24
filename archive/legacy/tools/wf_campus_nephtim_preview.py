"""从候选原生帧/时间线渲染可播放像素预览与技能命令摘要。"""
from __future__ import annotations

import base64
import io
import json
import zlib
from PIL import Image
import wf_assets
import wf_dsl
import wf_dsl_sig
import wf_pixelart_vfx
import wf_campus_nephtim_common as C
from wf_campus_nephtim_kit import walk


def build():
    report_dir = C.ROOT / 'work/codex_out/campus-trio-20260911/nephtim'
    report_dir.mkdir(parents=True, exist_ok=True)
    pixel = C.pkg_path('common', f'character/{C.CODE}/pixelart')
    read = lambda name: wf_dsl.parse_dsl(zlib.decompress((pixel / name).read_bytes(), -15))['tree']
    sheet = Image.open(io.BytesIO(wf_assets.png_decode((pixel / 'sprite_sheet.png').read_bytes()))).convert('RGBA')
    atlas = read('sprite_sheet.atlas.amf3.deflate')
    frame = read('pixelart.frame.amf3.deflate')
    timeline = read('pixelart.timeline.amf3.deflate')
    index = wf_pixelart_vfx.frame_index(atlas, frame['name'])
    cards = []
    for sequence in timeline['sequences']:
        if sequence['name'] not in ['neutral', 'walk_front', 'skill_ready', 'kachidoki']:
            continue
        frames = []
        for number in range(sequence['begin'], sequence['end'] + 1):
            entry = wf_pixelart_vfx.entry_for_frame(index, number)
            restored = wf_pixelart_vfx.restore_frame(sheet, entry)
            # 仅为审阅缩放/裁剪展示区域；不会回写任何游戏纹理或动画数据。
            visible = restored.crop((64, 64, 192, 192)).resize((512, 512), Image.Resampling.NEAREST)
            background = Image.new('RGBA', visible.size, '#e9e3da')
            background.alpha_composite(visible)
            frames.append(background.convert('RGB'))
        buffer = io.BytesIO()
        frames[0].save(buffer, format='GIF', save_all=True, append_images=frames[1:],
                       duration=1000 / 60, loop=0, disposal=2)
        raw = buffer.getvalue()
        (report_dir / f"pixel-{sequence['name']}.gif").write_bytes(raw)
        cards.append(f'<figure><img src="data:image/gif;base64,{base64.b64encode(raw).decode()}">'
                     f'<figcaption>{sequence["name"]} · 原生帧 {sequence["begin"]}–{sequence["end"]}</figcaption></figure>')
    summaries = {}
    for level in ['1', '2']:
        tree = json.loads((C.EVIDENCE / f'skill-{level}.json').read_text('utf-8'))
        summaries[level] = [wf_dsl_sig.brief_command(n[1]) for n in walk(tree)
                            if n and n[0] == 'Command']
    (report_dir / 'skill-command-summary.json').write_text(json.dumps(summaries, ensure_ascii=False, indent=2), 'utf-8')
    rows = ''.join('<li>' + value.replace('<', '&lt;') + '</li>' for value in summaries['2'])
    html = f'''<!doctype html><meta charset="utf-8"><title>校园奈芙提姆 · 候选审阅</title>
<style>body{{max-width:1180px;margin:50px auto;background:#f8f3ec;color:#382a37;font:18px/1.7 system-ui}}h1{{font-size:34px}}section{{display:flex;flex-wrap:wrap;gap:16px}}figure{{margin:0;width:260px}}img{{width:260px;image-rendering:pixelated;border-radius:18px}}figcaption{{padding:8px}}li{{margin:12px 0}}</style>
<h1>奈芙提姆 · 午后珍珠星光</h1><p>暗属性直击体系 · 169989 / ruin_girl_campus</p>
<p>以下动画由候选包的原生图集、帧表和时间线还原。技能部分是实际 DSL 的离线命令摘要，游戏战斗表现仍需客户端验证。</p>
<section>{''.join(cards)}</section><h2>觉醒技能命令</h2><ol>{rows}</ol>'''
    target = report_dir / '候选审阅.html'
    target.write_text(html, 'utf-8')
    return str(target)


if __name__ == '__main__':
    print(build())
