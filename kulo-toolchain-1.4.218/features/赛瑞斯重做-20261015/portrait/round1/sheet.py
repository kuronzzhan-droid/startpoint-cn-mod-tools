from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
GEN = HERE / "gen"
IDS = [f"S0-{i}" for i in range(1, 7)] + [f"S1-{i}" for i in range(1, 7)]
CW, CH, LAB = 600, 800, 110
COLS = 6
font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 84)
rows = (len(IDS) + COLS - 1) // COLS
sheet = Image.new("RGB", (CW * COLS, (CH + LAB) * rows), "white")
d = ImageDraw.Draw(sheet)
for n, i in enumerate(IDS):
    r, c = divmod(n, COLS)
    x, y = c * CW, r * (CH + LAB)
    f = GEN / f"seiris_{i[1]}_{i[-1]}.png"
    d.rectangle([x, y, x + CW - 1, y + LAB - 1], fill=(20, 40, 90) if i[1] == "0" else (0, 110, 140))
    d.text((x + CW // 2, y + LAB // 2), i, fill="white", font=font, anchor="mm")
    if f.exists():
        im = Image.open(f).convert("RGBA")
        bg = Image.new("RGB", im.size, "white"); bg.paste(im, mask=im.split()[3])
        bg.thumbnail((CW - 10, CH - 10))
        sheet.paste(bg, (x + (CW - bg.width) // 2, y + LAB + (CH - bg.height) // 2))
    else:
        d.text((x + CW // 2, y + LAB + CH // 2), "missing", fill="red", font=font, anchor="mm")
    d.rectangle([x, y, x + CW - 1, y + CH + LAB - 1], outline=(180, 180, 180), width=3)
out = HERE / "立绘候选-round1.jpg"
q = 88
while True:
    sheet.save(out, quality=q)
    if out.stat().st_size <= 3 * 1024 * 1024 or q < 50:
        break
    q -= 6
print(out, sheet.size, out.stat().st_size, q)
