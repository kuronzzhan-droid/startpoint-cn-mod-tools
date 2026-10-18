// Shared helpers for 像素工坊: sheet loading, a 60 fps clock, a small stage that
// draws one action of a family (optionally from a recoloured sheet), recolouring.
import { useEffect, useRef, useState } from "preact/hooks";
import { api, PixelAction, PixelFamily, PixelMeta, workshop } from "../api";

export type Drawable = HTMLImageElement | HTMLCanvasElement;

export function loadImage(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error("图片加载失败：" + url));
    image.src = url;
  });
}

export function readAsDataUrl(file: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error ?? new Error("读取失败"));
    reader.readAsDataURL(file);
  });
}

export function hexToInt(hex: string): number {
  return parseInt(hex.replace("#", ""), 16);
}

export function intToHex(value: number): string {
  return "#" + value.toString(16).padStart(6, "0");
}

export function luma(hex: string): number {
  const v = hexToInt(hex);
  return 0.299 * ((v >> 16) & 255) + 0.587 * ((v >> 8) & 255) + 0.114 * (v & 255);
}

/** Pixel meta + loaded grid sheets, for the view or for the draft (falls back to the view). */
export function useFamilies(cid: string | null, state: "view" | "draft", refresh = 0) {
  const [meta, setMeta] = useState<(PixelMeta & { draftRevision?: number }) | null>(null);
  const [sheets, setSheets] = useState<Record<string, HTMLImageElement>>({});
  const [source, setSource] = useState<"view" | "draft">("view");
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (!cid) return;
    let alive = true;
    setError(null);
    (async () => {
      let data: PixelMeta & { draftRevision?: number };
      let from: "view" | "draft" = "view";
      if (state === "draft") {
        try {
          data = await workshop.draftPixels(cid);
          from = "draft";
        } catch {
          data = await api.pixels(cid);
        }
      } else data = await api.pixels(cid);
      const loaded: Record<string, HTMLImageElement> = {};
      for (const f of data.families) {
        if (f.error) continue;
        loaded[f.family] = await loadImage(from === "draft"
          ? workshop.draftSheetUrl(cid, f.family, data.draftRevision ?? 0) : api.pixelSheetUrl(cid, f.family));
      }
      if (!alive) return;
      setMeta(data);
      setSheets(loaded);
      setSource(from);
    })().catch((e: Error) => alive && setError(e.message));
    return () => { alive = false; };
  }, [cid, state, refresh]);
  return { meta, sheets, source, error };
}

/** Shared 60 fps timeline clock (ticks = timeline frames). */
export function useClock(playing: boolean, speed = 1): [number, (t: number) => void] {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    if (!playing) return;
    let last = performance.now();
    let handle = 0;
    const step = (now: number) => {
      setTick((t) => t + ((now - last) / 1000) * 60 * speed);
      last = now;
      handle = requestAnimationFrame(step);
    };
    handle = requestAnimationFrame(step);
    return () => cancelAnimationFrame(handle);
  }, [playing, speed]);
  return [tick, setTick];
}

export function cellAt(action: PixelAction, tick: number): number {
  const t = Math.floor(tick) % Math.max(1, action.totalFrames);
  for (const c of action.cells) if (t >= c.start && t < c.start + c.frames) return c.cell;
  return action.cells[action.cells.length - 1].cell;
}

export function paintChecker(ctx: CanvasRenderingContext2D, w: number, h: number, size = 8) {
  for (let y = 0; y < h; y += size)
    for (let x = 0; x < w; x += size) {
      ctx.fillStyle = ((x / size + y / size) & 1) === 0 ? "#e9ecf1" : "#f7f8fa";
      ctx.fillRect(x, y, size, size);
    }
}

/** One action of a family, anchored; `sheet` may be a recoloured canvas of the same grid. */
export function ActionStage({ family, sheet, action, tick, zoom = 3, label, crop }: {
  family: PixelFamily; sheet: Drawable | undefined; action: PixelAction | undefined; tick: number; zoom?: number;
  label?: string; crop?: { x: number; y: number; w: number; h: number };
}) {
  const ref = useRef<HTMLCanvasElement>(null);
  const view = crop ?? { x: 0, y: 0, w: family.cellWidth, h: family.cellHeight };
  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const w = view.w * zoom, h = view.h * zoom;
    if (canvas.width !== w) canvas.width = w;
    if (canvas.height !== h) canvas.height = h;
    const ctx = canvas.getContext("2d")!;
    ctx.imageSmoothingEnabled = false;
    paintChecker(ctx, w, h, 4 * zoom);
    if (!sheet || !action) return;
    const cell = cellAt(action, tick);
    const sx = (cell % family.columns) * family.cellWidth + view.x;
    const sy = Math.floor(cell / family.columns) * family.cellHeight + view.y;
    ctx.drawImage(sheet, sx, sy, view.w, view.h, 0, 0, w, h);
    ctx.strokeStyle = "rgba(230,60,90,0.8)";
    ctx.beginPath();
    const ax = (family.anchor.x - view.x) * zoom, ay = (family.anchor.y - view.y) * zoom;
    ctx.moveTo(ax - 6, ay + 0.5); ctx.lineTo(ax + 6, ay + 0.5);
    ctx.moveTo(ax + 0.5, ay - 6); ctx.lineTo(ax + 0.5, ay + 6);
    ctx.stroke();
  }, [family, sheet, action, Math.floor(tick), zoom, view.x, view.y, view.w, view.h]);
  return (
    <figure class="ws-stage">
      <canvas ref={ref} class="pixel-canvas" data-action={action?.name} />
      {label ? <figcaption class="small">{label}</figcaption> : null}
    </figure>
  );
}

/** Visible content box shared by all cells of a family (for tighter previews). */
export function contentCrop(family: PixelFamily, sheet: Drawable | undefined, pad = 3) {
  if (!sheet) return undefined;
  const canvas = document.createElement("canvas");
  canvas.width = sheet.width;
  canvas.height = sheet.height;
  const ctx = canvas.getContext("2d")!;
  ctx.drawImage(sheet, 0, 0);
  const data = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
  let x0 = family.cellWidth, y0 = family.cellHeight, x1 = 0, y1 = 0;
  for (let i = 0; i < family.cellCount; i++) {
    const ox = (i % family.columns) * family.cellWidth, oy = Math.floor(i / family.columns) * family.cellHeight;
    for (let y = 0; y < family.cellHeight; y++)
      for (let x = 0; x < family.cellWidth; x++)
        if (data[((oy + y) * canvas.width + ox + x) * 4 + 3]) {
          if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y;
        }
  }
  if (x1 < x0) return undefined;
  x0 = Math.max(0, x0 - pad); y0 = Math.max(0, y0 - pad);
  x1 = Math.min(family.cellWidth - 1, x1 + pad); y1 = Math.min(family.cellHeight - 1, y1 + pad);
  return { x: x0, y: y0, w: x1 - x0 + 1, h: y1 - y0 + 1 };
}

/** Exact RGB→RGB recolour (alpha untouched), mirroring the backend remap. */
export function recolor(sheet: Drawable, mapping: Map<number, number>): HTMLCanvasElement {
  const canvas = document.createElement("canvas");
  canvas.width = sheet.width;
  canvas.height = sheet.height;
  const ctx = canvas.getContext("2d")!;
  ctx.drawImage(sheet, 0, 0);
  if (!mapping.size) return canvas;
  const image = ctx.getImageData(0, 0, canvas.width, canvas.height);
  const d = image.data;
  for (let i = 0; i < d.length; i += 4) {
    if (!d[i + 3]) continue;
    const to = mapping.get((d[i] << 16) | (d[i + 1] << 8) | d[i + 2]);
    if (to === undefined) continue;
    d[i] = (to >> 16) & 255; d[i + 1] = (to >> 8) & 255; d[i + 2] = to & 255;
  }
  ctx.putImageData(image, 0, 0);
  return canvas;
}

export function familyOf(meta: PixelMeta | null, name: string): PixelFamily | undefined {
  return meta?.families.find((f) => f.family === name && !f.error);
}
