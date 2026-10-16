from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
HERE = Path(__file__).resolve().parent
ITEMS = [("原图", HERE / "refs/seiris_0_3_src.png")] + [(t, HERE / f"gen/seiris_0_3_{t}.png") for t in ("T1", "T2", "T3", "T4")]
CW, CH, LAB = 720, 960, 130
font = ImageFont.truetype("C:/Windows/Fonts/msyhbd.ttc", 96)
sheet = Image.new("RGB", (CW * len(ITEMS), CH + LAB), "white")
d = ImageDraw.Draw(sheet)
for n, (lab, f) in enumerate(ITEMS):
    x = n * CW
    d.rectangle([x, 0, x + CW - 1, LAB - 1], fill=(90, 90, 90) if n == 0 else (20, 40, 90))
    d.text((x + CW // 2, LAB // 2), lab, fill="white", font=font, anchor="mm")
    if f.exists():
        im = Image.open(f).convert("RGBA")
        bg = Image.new("RGB", im.size, "white"); bg.paste(im, mask=im.split()[3])
        bg.thumbnail((CW - 10, CH - 10))
        sheet.paste(bg, (x + (CW - bg.width) // 2, LAB + (CH - bg.height) // 2))
    else:
        d.text((x + CW // 2, LAB + CH // 2), "missing", fill="red", font=font, anchor="mm")
    d.rectangle([x, 0, x + CW - 1, CH + LAB - 1], outline=(180, 180, 180), width=3)
out = HERE / "S0-3尾巴修正-候选.jpg"
q = 90
while True:
    sheet.save(out, quality=q)
    if out.stat().st_size <= 3 * 1024 * 1024 or q < 50: break
    q -= 6
print(out, sheet.size, out.stat().st_size, q)
