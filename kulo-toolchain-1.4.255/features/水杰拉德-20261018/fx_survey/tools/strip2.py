import sys, json
from PIL import Image, ImageDraw, ImageFont
import render_sheet as R
rows = {r["path"]: r for r in json.load(open("rows.json", encoding="utf-8"))}
out = sys.argv[1]; title = sys.argv[2]; items = sys.argv[3:]
n = 7; cw = 140
font = ImageFont.truetype(R.FONT, 14); fontb = ImageFont.truetype(R.FONT, 18)
chh = int(cw * 1920 / 1080)
rowh = chh + 30
S = Image.new("RGB", (n * (cw + 2) + 8, 40 + len(items) * rowh + 6), (8, 8, 12))
dr = ImageDraw.Draw(S)
dr.text((8, 8), title, font=fontb, fill=(240, 240, 240))
for i, it in enumerate(items):
    lab, p = it.split("=", 1)
    e = R.E[p]; nf = e["frames"]
    frs = [min(nf - 1, int(round(nf * (k + 0.5) / n))) for k in range(n)]
    y0 = 40 + i * rowh
    for j, f in enumerate(frs):
        S.paste(R.render_screen(p, f, w=cw), (4 + j * (cw + 2), y0))
        dr.text((6 + j * (cw + 2), y0 + 1), f"f{f}", font=font, fill=(170, 170, 170))
    r = rows.get(p, {})
    dr.text((6, y0 + chh + 4), f"{lab}  {r.get('char','')} {r.get('cn','')} ★{r.get('rarity','')}{r.get('elem','')} {r.get('role','')}  |  {p.split('/')[-1]}  {nf}帧", font=font, fill=(120, 180, 255) if r.get('water') else (230, 230, 230))
S.save(out, optimize=True)
print(out, S.size)
