import { useEffect, useMemo, useRef, useState } from "preact/hooks";
import {
  BaseImageSpec, DraftCheck, drafts, GENERATE_ACTIONS, GeneratedFrame, PaletteGroup, PixelAction, PixelFamily,
  WorkshopAnalysis, workshop,
} from "../api";
import { ChecksList } from "./Changes";
import { Notice } from "./common";
import { ActionStage, familyOf, hexToInt, intToHex, loadImage, paintChecker, readAsDataUrl, useClock, useFamilies } from "./workshopKit";

const BOX = 256;
type Slot = "front" | "back" | "liedown";
const SLOT_LABEL: Record<Slot, string> = { front: "正面", back: "背面", liedown: "躺倒" };

// ---------------------------------------------------------------------------
// 程序化动作

export function ProceduralActions({ characterId, refresh, onSaved }: { characterId: string; analysis: WorkshopAnalysis; refresh: number; onSaved: () => void }) {
  const [bases, setBases] = useState<Partial<Record<Slot, { spec: BaseImageSpec; url: string }>>>({});
  const [active, setActive] = useState<Slot>("front");
  const [action, setAction] = useState("walk_front");
  const [total, setTotal] = useState<number | "">("");
  const [frames, setFrames] = useState<(GeneratedFrame & { img: HTMLImageElement })[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<{ kind: "info" | "error"; text: string } | null>(null);
  const [checks, setChecks] = useState<DraftCheck[] | null>(null);
  const [playing, setPlaying] = useState(true);
  const [tick] = useClock(playing);
  const fam = useFamilies(characterId, "draft", refresh);
  const [draftAnalysis, setDraftAnalysis] = useState<WorkshopAnalysis | null>(null);
  useEffect(() => { workshop.analyze(characterId, "draft").then(setDraftAnalysis, () => setDraftAnalysis(null)); }, [characterId, refresh]);
  const pixelart = draftAnalysis?.families.find((f) => f.family === "pixelart");

  useEffect(() => {
    workshop.bases(characterId).then((r) => {
      const next: Partial<Record<Slot, { spec: BaseImageSpec; url: string }>> = {};
      for (const [slot, spec] of Object.entries(r.bases) as [Slot, BaseImageSpec][]) {
        if ("cell" in spec) next[slot] = { spec, url: workshop.cellUrl(characterId, spec.cell.family, spec.cell.key, "draft") };
      }
      // Keep uploaded images across refreshes; cell picks follow the (possibly remapped) draft.
      setBases((prev) => ({ ...next, ...Object.fromEntries(Object.entries(prev).filter(([, v]) => v && "png" in v.spec)) }));
    }, () => undefined);
  }, [characterId, refresh]);

  const family = familyOf(fam.meta, "pixelart");
  const current = family?.actions.find((a) => a.name === action);
  const generate = async (save: boolean) => {
    setBusy(save ? "save" : "gen"); setMessage(null);
    try {
      const body = { action, bases: Object.fromEntries(Object.entries(bases).map(([k, v]) => [k, v!.spec])),
        ...(total ? { totalFrames: Number(total) } : {}), save };
      const result = await workshop.generate(characterId, body);
      const imgs = await Promise.all(result.frames.map((f) => loadImage("data:image/png;base64," + f.png)));
      setFrames(result.frames.map((f, i) => ({ ...f, img: imgs[i] })));
      if (save) {
        setChecks(result.change?.checks ?? []);
        setMessage({ kind: "info", text: `已写入草稿：${result.change?.title}（${result.status?.label}）` });
        onSaved();
      } else setChecks(null);
    } catch (e) { setMessage({ kind: "error", text: (e as Error).message }); }
    finally { setBusy(null); }
  };
  const uniqueCells = pixelart ? pixelart.regions.map((r) => r.keys[0]) : [];
  const sum = frames.reduce((n, f) => n + f.duration, 0);
  const genCrop = useMemo(() => {
    if (!frames.length) return null;
    const boxes = frames.map((f) => f.bbox).filter((b) => b[2] > b[0]);
    const pad = 6;
    const x0 = Math.min(...boxes.map((b) => b[0]), 128) - pad, y0 = Math.min(...boxes.map((b) => b[1])) - pad;
    const x1 = Math.max(...boxes.map((b) => b[2]), 128) + pad, y1 = Math.max(...boxes.map((b) => b[3]), 128) + pad;
    return { x: Math.max(0, x0), y: Math.max(0, y0), w: Math.min(BOX, x1) - Math.max(0, x0), h: Math.min(BOX, y1) - Math.max(0, y0) };
  }, [frames]);
  const genIndex = useMemo(() => {
    let t = Math.floor(tick) % Math.max(1, sum);
    for (let i = 0; i < frames.length; i++) { if (t < frames[i].duration) return i; t -= frames[i].duration; }
    return 0;
  }, [tick, frames, sum]);

  return (
    <div class="ws-generate">
      <p class="hint">按官方配方从三张底图合成动作（零 API）：走路 = 交替下沉 1px + 底行摆 1px；胜利 = 原姿 → 倾斜 12° 起跳 → 最高点 −16° + 金白火花 → 落地 6°；
        幽灵 = 明度三档白/灰蓝 + 底部波尾，悬浮 12px；入棺 = 本体渐隐 → 躺倒；复活 = 幽灵下落 → 交叠 → 全白闪 → 本体。
        帧是 256² 帧框、原点 (128,128)，fy = −(128 − h + dy)。底图默认取草稿态（有母本映射时就是映射后的颜色）。</p>
      <div class="ws-bases">
        {(["front", "back", "liedown"] as Slot[]).map((slot) => (
          <div class={"ws-base" + (active === slot ? " on" : "")} onClick={() => setActive(slot)}>
            <strong class="small">{SLOT_LABEL[slot]}</strong>
            {bases[slot] ? <img src={bases[slot]!.url} alt="" /> : <span class="muted small">{slot === "liedown" ? "未选：用正面转 90°" : "未选"}</span>}
            <span class="mono small muted">{bases[slot] && "cell" in bases[slot]!.spec ? `端点 ${(bases[slot]!.spec as { cell: { key: number } }).cell.key}` : bases[slot] ? "上传" : ""}</span>
            <label class="upload-btn small">上传 PNG
              <input type="file" accept="image/png" onChange={async (e) => {
                const file = (e.target as HTMLInputElement).files?.[0];
                if (!file) return;
                const url = await readAsDataUrl(file);
                setBases({ ...bases, [slot]: { spec: { png: url.replace(/^data:[^,]*,/, "") }, url } });
              }} />
            </label>
          </div>
        ))}
        <div class="ws-cellpick">
          <span class="small muted">点下面的现有帧，设为「{SLOT_LABEL[active]}」底图（pixelart 每个图集区域一张）：</span>
          <div class="ws-cellpick-list">
            {uniqueCells.map((key) => (
              <button title={"端点 " + key} onClick={() => setBases({ ...bases, [active]: {
                spec: { cell: { family: "pixelart", key } }, url: workshop.cellUrl(characterId, "pixelart", key, "draft") } })}>
                <img src={workshop.cellUrl(characterId, "pixelart", key, "draft")} alt="" />
              </button>
            ))}
          </div>
        </div>
      </div>
      <div class="toolbar">
        <label>动作
          <select value={action} onChange={(e) => { setAction((e.target as HTMLSelectElement).value); setFrames([]); }}>
            {GENERATE_ACTIONS.map((a) => <option value={a.id}>{a.label} · {a.id}</option>)}
          </select>
        </label>
        <label>总帧数<input type="number" min={1} placeholder={String(current?.totalFrames ?? "")} value={total}
          onInput={(e) => { const v = (e.target as HTMLInputElement).value; setTotal(v ? Number(v) : ""); }} /></label>
        <button class="primary" onClick={() => generate(false)} disabled={busy !== null || !drafts.hasToken()}>{busy === "gen" ? "生成中……" : "生成预览"}</button>
        <button onClick={() => generate(true)} disabled={busy !== null || !frames.length || !drafts.hasToken()}>{busy === "save" ? "保存中……" : "保存到草稿"}</button>
        <button onClick={() => setPlaying(!playing)}>{playing ? "暂停" : "播放"}</button>
      </div>
      {message ? <Notice kind={message.kind === "error" ? "error" : "info"}>{message.text}</Notice> : null}
      {frames.length && genCrop ? (
        <>
          <div class="compare">
            <figure>
              <figcaption><strong>现在</strong> <span class="muted small">{current ? `${current.totalFrames} 帧 · ${current.cells.length} 张图` : "（没有这个动作）"}{fam.source === "draft" ? " · 草稿态" : ""}</span></figcaption>
              {family && current ? <ActionStage family={family} sheet={fam.sheets.pixelart} action={current} tick={tick} zoom={5}
                crop={{ x: genCrop.x - (family.frameBox?.cropX ?? 0), y: genCrop.y - (family.frameBox?.cropY ?? 0), w: genCrop.w, h: genCrop.h }} /> : null}
            </figure>
            <figure>
              <figcaption><strong>生成</strong> <span class="muted small">{frames.length} 张图 · 共 {sum} 帧{current && sum !== current.totalFrames ? " · 与现有时长不同" : ""}</span></figcaption>
              <FrameStage image={frames[genIndex].img} crop={genCrop} zoom={5} />
            </figure>
          </div>
          <div class="filmstrip">
            {frames.map((f, i) => (
              <div class={"film" + (i === genIndex ? " on" : "")} title={f.note}>
                <FrameStage image={f.img} crop={genCrop} zoom={2} />
                <span class="small mono">{f.duration}f · dy{f.dy > 0 ? "+" : ""}{f.dy}</span>
                <span class="small muted ws-note">{f.note}</span>
                <span class="small mono muted">fy {-(f.bbox[1])}</span>
              </div>
            ))}
          </div>
          {checks ? <ChecksList checks={checks} empty="没有提示。" /> : null}
        </>
      ) : null}
    </div>
  );
}

function FrameStage({ image, crop, zoom }: { image: CanvasImageSource; crop: { x: number; y: number; w: number; h: number }; zoom: number }) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    canvas.width = crop.w * zoom; canvas.height = crop.h * zoom;
    const ctx = canvas.getContext("2d")!;
    ctx.imageSmoothingEnabled = false;
    paintChecker(ctx, canvas.width, canvas.height, 4 * zoom);
    ctx.drawImage(image, crop.x, crop.y, crop.w, crop.h, 0, 0, canvas.width, canvas.height);
    ctx.strokeStyle = "rgba(230,60,90,0.8)";
    const ax = (128 - crop.x) * zoom, ay = (128 - crop.y) * zoom;
    ctx.beginPath(); ctx.moveTo(ax - 6, ay + 0.5); ctx.lineTo(ax + 6, ay + 0.5); ctx.moveTo(ax + 0.5, ay - 6); ctx.lineTo(ax + 0.5, ay + 6); ctx.stroke();
  }, [image, crop.x, crop.y, crop.w, crop.h, zoom]);
  return <canvas ref={ref} class="pixel-canvas" />;
}

// ---------------------------------------------------------------------------
// 画板

type Tool = "pencil" | "eraser" | "fill" | "picker";
const TOOL_LABEL: Record<Tool, string> = { pencil: "铅笔", eraser: "橡皮", fill: "填充", picker: "吸管" };
type BoardFrame = { data: ImageData; duration: number };

function frameFromSheet(family: PixelFamily, sheet: CanvasImageSource, cell: number): ImageData {
  const canvas = document.createElement("canvas");
  canvas.width = BOX; canvas.height = BOX;
  const ctx = canvas.getContext("2d")!;
  const box = family.frameBox ?? { cropX: 0, cropY: 0, width: BOX, height: BOX };
  ctx.drawImage(sheet, (cell % family.columns) * family.cellWidth, Math.floor(cell / family.columns) * family.cellHeight,
    family.cellWidth, family.cellHeight, box.cropX, box.cropY, family.cellWidth, family.cellHeight);
  return ctx.getImageData(0, 0, BOX, BOX);
}

function cloneData(data: ImageData): ImageData {
  return new ImageData(new Uint8ClampedArray(data.data), data.width, data.height);
}

function toCanvas(data: ImageData): HTMLCanvasElement {
  const canvas = document.createElement("canvas");
  canvas.width = data.width; canvas.height = data.height;
  canvas.getContext("2d")!.putImageData(data, 0, 0);
  return canvas;
}

export function DrawingBoard({ characterId, analysis, groups, refresh, onSaved }: {
  characterId: string; analysis: WorkshopAnalysis; groups: Record<string, PaletteGroup>; refresh: number; onSaved: () => void;
}) {
  const fam = useFamilies(characterId, "draft", refresh);
  const [familyName, setFamilyName] = useState("pixelart");
  const [actionName, setActionName] = useState("neutral");
  const [frames, setFrames] = useState<BoardFrame[]>([]);
  const [index, setIndex] = useState(0);
  const [tool, setTool] = useState<Tool>("pencil");
  const [color, setColor] = useState<string>(analysis.palette[0]?.hex ?? "#000000");
  const [custom, setCustom] = useState<string[]>([]);
  const [onion, setOnion] = useState(true);
  const [full, setFull] = useState(false);
  const [version, setVersion] = useState(0);
  const [undo, setUndo] = useState<{ index: number; data: ImageData }[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<{ kind: "info" | "error"; text: string } | null>(null);
  const [checks, setChecks] = useState<DraftCheck[] | null>(null);
  const ref = useRef<HTMLCanvasElement>(null);
  const drawing = useRef(false);

  const family = familyOf(fam.meta, familyName);
  const action: PixelAction | undefined = family?.actions.find((a) => a.name === actionName);
  const sheet = family ? fam.sheets[family.family] : undefined;
  const origin = family ? [(family.frameBox?.cropX ?? 0) + family.anchor.x, (family.frameBox?.cropY ?? 0) + family.anchor.y] : [128, 128];

  const [actionBox, setActionBox] = useState({ x: 0, y: 0, w: BOX, h: BOX });
  useEffect(() => {
    if (!family || !action || !sheet) { setFrames([]); return; }
    const loaded = action.cells.map((c) => ({ data: frameFromSheet(family, sheet, c.cell), duration: c.frames }));
    // View = this action's visible union (+ origin), padded; fixed while drawing.
    let x0 = origin[0], y0 = origin[1], x1 = origin[0], y1 = origin[1];
    for (const f of loaded) {
      const d = f.data.data;
      for (let y = 0; y < BOX; y++) for (let x = 0; x < BOX; x++) if (d[(y * BOX + x) * 4 + 3]) {
        if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y;
      }
    }
    const pad = 10, minSide = 40;
    let w = x1 - x0 + 1 + pad * 2, h = y1 - y0 + 1 + pad * 2;
    const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
    w = Math.max(w, minSide); h = Math.max(h, minSide);
    const x = Math.max(0, Math.min(BOX - w, Math.round(cx - w / 2))), y = Math.max(0, Math.min(BOX - h, Math.round(cy - h / 2)));
    setActionBox({ x, y, w: Math.min(BOX, w), h: Math.min(BOX, h) });
    setFrames(loaded);
    setIndex(0); setUndo([]); setChecks(null);
  }, [family, action, sheet]);

  const view = full || !family ? { x: 0, y: 0, w: BOX, h: BOX } : actionBox;
  const zoom = Math.max(2, Math.min(16, Math.floor(Math.min(560 / view.w, 460 / view.h))));
  const [draftPalette, setDraftPalette] = useState<string[] | null>(null);
  useEffect(() => {
    workshop.analyze(characterId, "draft").then((a) => setDraftPalette(a.palette.map((p) => p.hex)), () => setDraftPalette(null));
  }, [characterId, refresh]);
  const palette = useMemo(() => [...(draftPalette ?? analysis.palette.map((p) => p.hex)), ...custom], [draftPalette, analysis.palette, custom]);

  useEffect(() => {
    const canvas = ref.current;
    const current = frames[index];
    if (!canvas || !current) return;
    canvas.width = view.w * zoom; canvas.height = view.h * zoom;
    const ctx = canvas.getContext("2d")!;
    ctx.imageSmoothingEnabled = false;
    paintChecker(ctx, canvas.width, canvas.height, zoom * 2);
    const draw = (data: ImageData, alpha: number) => {
      ctx.globalAlpha = alpha;
      ctx.drawImage(toCanvas(data), view.x, view.y, view.w, view.h, 0, 0, canvas.width, canvas.height);
      ctx.globalAlpha = 1;
    };
    if (onion && frames.length > 1) {
      draw(frames[(index - 1 + frames.length) % frames.length].data, 0.3);
      if (frames.length > 2) draw(frames[(index + 1) % frames.length].data, 0.15);
    }
    draw(current.data, 1);
    if (zoom >= 6) {
      ctx.strokeStyle = "rgba(120,130,150,0.18)";
      ctx.beginPath();
      for (let x = 0; x <= view.w; x++) { ctx.moveTo(x * zoom + 0.5, 0); ctx.lineTo(x * zoom + 0.5, canvas.height); }
      for (let y = 0; y <= view.h; y++) { ctx.moveTo(0, y * zoom + 0.5); ctx.lineTo(canvas.width, y * zoom + 0.5); }
      ctx.stroke();
    }
    ctx.strokeStyle = "rgba(230,60,90,0.85)";
    const ax = (origin[0] - view.x) * zoom, ay = (origin[1] - view.y) * zoom;
    ctx.beginPath(); ctx.moveTo(ax - 10, ay + 0.5); ctx.lineTo(ax + 10, ay + 0.5); ctx.moveTo(ax + 0.5, ay - 10); ctx.lineTo(ax + 0.5, ay + 10); ctx.stroke();
  }, [frames, index, view, zoom, onion, version]);

  const pointAt = (e: PointerEvent) => {
    const canvas = ref.current!;
    const rect = canvas.getBoundingClientRect();
    const x = view.x + Math.floor(((e.clientX - rect.left) * (canvas.width / rect.width)) / zoom);
    const y = view.y + Math.floor(((e.clientY - rect.top) * (canvas.height / rect.height)) / zoom);
    return x >= 0 && y >= 0 && x < BOX && y < BOX ? [x, y] : null;
  };
  const pushUndo = () => setUndo((u) => [...u.slice(-49), { index, data: cloneData(frames[index].data) }]);
  const apply = (e: PointerEvent, first: boolean) => {
    const p = pointAt(e);
    const current = frames[index];
    if (!p || !current) return;
    const d = current.data.data;
    const at = (p[1] * BOX + p[0]) * 4;
    if (tool === "picker") {
      if (!d[at + 3]) return;
      const hex = intToHex((d[at] << 16) | (d[at + 1] << 8) | d[at + 2]);
      if (!palette.includes(hex)) setCustom([...custom, hex]);
      setColor(hex); setTool("pencil");
      return;
    }
    if (first) pushUndo();
    const rgb = hexToInt(color);
    const write = (i: number) => {
      if (tool === "eraser") { d[i] = d[i + 1] = d[i + 2] = d[i + 3] = 0; return; }
      d[i] = (rgb >> 16) & 255; d[i + 1] = (rgb >> 8) & 255; d[i + 2] = rgb & 255; d[i + 3] = 255;
    };
    if (tool === "fill") {
      if (!first) return;
      const target = [d[at], d[at + 1], d[at + 2], d[at + 3]].join(",");
      const stack = [p];
      const seen = new Uint8Array(BOX * BOX);
      while (stack.length) {
        const [x, y] = stack.pop()!;
        if (x < 0 || y < 0 || x >= BOX || y >= BOX || seen[y * BOX + x]) continue;
        seen[y * BOX + x] = 1;
        const i = (y * BOX + x) * 4;
        if ([d[i], d[i + 1], d[i + 2], d[i + 3]].join(",") !== target) continue;
        write(i);
        stack.push([x + 1, y], [x - 1, y], [x, y + 1], [x, y - 1]);
      }
    } else write(at);
    setVersion((v) => v + 1);
  };
  const nudge = (dy: number) => {
    pushUndo();
    const src = frames[index].data.data;
    const out = new Uint8ClampedArray(src.length);
    for (let y = 0; y < BOX; y++) {
      const ty = y + dy;
      if (ty < 0 || ty >= BOX) continue;
      out.set(src.subarray(y * BOX * 4, (y + 1) * BOX * 4), ty * BOX * 4);
    }
    const next = [...frames];
    next[index] = { ...frames[index], data: new ImageData(out, BOX, BOX) };
    setFrames(next);
  };
  const total = frames.reduce((n, f) => n + f.duration, 0);
  const request = () => ({
    family: familyName, action: actionName, origin: { mode: "board", from: fam.source },
    frames: frames.map((f) => ({ png: toCanvas(f.data).toDataURL("image/png").replace(/^data:[^,]*,/, ""), duration: f.duration, anchor: origin })),
  });
  const save = async (dry: boolean) => {
    setBusy(dry ? "check" : "save"); setMessage(null);
    try {
      if (dry) setChecks((await drafts.checkPixel(characterId, request())).checks);
      else {
        const r = await drafts.savePixel(characterId, request());
        setChecks(r.change?.checks ?? []);
        setMessage({ kind: "info", text: `已写入草稿：${r.change?.title}（${r.status.label}）` });
        onSaved();
      }
    } catch (e) { setMessage({ kind: "error", text: (e as Error).message }); }
    finally { setBusy(null); }
  };

  if (fam.error) return <Notice kind="error">{fam.error}</Notice>;
  if (!fam.meta) return <div class="loading">正在读取像素帧……</div>;

  return (
    <div class="ws-board">
      <div class="toolbar">
        <label>像素族
          <select value={familyName} onChange={(e) => setFamilyName((e.target as HTMLSelectElement).value)}>
            {fam.meta.families.filter((f) => !f.error).map((f) => <option value={f.family}>{f.family}</option>)}
          </select>
        </label>
        <label>动作槽
          <select value={actionName} onChange={(e) => setActionName((e.target as HTMLSelectElement).value)}>
            {family?.actions.map((a) => <option value={a.name}>{a.name} · {a.totalFrames} 帧</option>)}
          </select>
        </label>
        <span class="small muted">{fam.source === "draft" ? "草稿态帧" : "当前视图帧"} · 帧框 256² · 原点 ({origin.join(", ")}) · 总 {total} 帧{action && total !== action.totalFrames ? <span class="warn-text">（原 {action.totalFrames}；只有末尾动作能改总时长）</span> : null}</span>
      </div>
      {message ? <Notice kind={message.kind === "error" ? "error" : "info"}>{message.text}</Notice> : null}
      <div class="ws-board-main">
        <div>
          <div class="toolbar ws-tools">
            {(Object.keys(TOOL_LABEL) as Tool[]).map((t) => <button class={tool === t ? "primary" : ""} onClick={() => setTool(t)}>{TOOL_LABEL[t]}</button>)}
            <button onClick={() => {
              const last = undo[undo.length - 1];
              if (!last) return;
              const next = [...frames]; next[last.index] = { ...next[last.index], data: last.data };
              setFrames(next); setUndo(undo.slice(0, -1)); setIndex(last.index);
            }} disabled={!undo.length}>撤销</button>
            <label class="check small"><input type="checkbox" checked={onion} onChange={(e) => setOnion((e.target as HTMLInputElement).checked)} />洋葱皮</label>
            <label class="check small"><input type="checkbox" checked={full} onChange={(e) => setFull((e.target as HTMLInputElement).checked)} />整帧 256²</label>
          </div>
          <canvas ref={ref} class="pixel-canvas ws-board-canvas" aria-label="画板"
            onPointerDown={(e) => { drawing.current = true; (e.target as HTMLCanvasElement).setPointerCapture(e.pointerId); apply(e as unknown as PointerEvent, true); }}
            onPointerMove={(e) => { if (drawing.current && tool !== "fill" && tool !== "picker") apply(e as unknown as PointerEvent, false); }}
            onPointerUp={() => { drawing.current = false; }} />
        </div>
        <aside class="ws-board-side">
          <h5>调色板（锁定为本角色颜色）</h5>
          <div class="ws-board-palette">
            {palette.map((hex) => (
              <button class={"ws-swatch big" + (hex === color ? " on" : "")} style={{ background: hex }}
                title={`${hex}${groups[hex] ? " · " + groups[hex] : " · 新增"}`} onClick={() => { setColor(hex); if (tool === "eraser" || tool === "picker") setTool("pencil"); }} />
            ))}
          </div>
          <div class="small">当前 <span class="ws-swatch" style={{ background: color }} /> <span class="mono">{color}</span>
            <label class="small"> 添加颜色 <input type="color" onChange={(e) => {
              const v = (e.target as HTMLInputElement).value;
              if (!palette.includes(v)) setCustom([...custom, v]);
              setColor(v);
            }} /></label>
          </div>
          {custom.length ? <p class="small warn-text">新增 {custom.length} 色不在本角色调色板里：{custom.join(" ")}</p> : null}
          <h5>当前帧 {index + 1}/{frames.length}</h5>
          <div class="save-row">
            <button onClick={() => nudge(-1)} title="整帧上移 1px（离地，dy−1）">上移 1px</button>
            <button onClick={() => nudge(1)} title="整帧下移 1px（下沉，dy+1）">下移 1px</button>
          </div>
          <label class="small">停留<input type="number" min={1} max={600} value={frames[index]?.duration ?? 1}
            onInput={(e) => { const v = Math.max(1, Number((e.target as HTMLInputElement).value)); const next = [...frames]; next[index] = { ...next[index], duration: v }; setFrames(next); }} />帧</label>
          <div class="save-row">
            <button onClick={() => { const next = [...frames]; next.splice(index + 1, 0, { data: cloneData(frames[index].data), duration: frames[index].duration }); setFrames(next); setIndex(index + 1); }}>复制本帧</button>
            <button onClick={() => { if (frames.length < 2) return; const next = frames.filter((_, i) => i !== index); setFrames(next); setIndex(Math.max(0, index - 1)); }} disabled={frames.length < 2}>删除本帧</button>
          </div>
        </aside>
      </div>
      <div class="filmstrip ws-board-strip">
        {frames.map((f, i) => (
          <button class={"film" + (i === index ? " on" : "")} onClick={() => setIndex(i)}>
            <BoardThumb data={f.data} view={view} version={version} />
            <span class="small mono">#{i + 1} · {f.duration}f</span>
          </button>
        ))}
      </div>
      <div class="save-row">
        <button onClick={() => save(true)} disabled={busy !== null || !frames.length || !drafts.hasToken()}>{busy === "check" ? "检查中……" : "检查（不写草稿）"}</button>
        <button class="primary" onClick={() => save(false)} disabled={busy !== null || !frames.length || !drafts.hasToken()}>{busy === "save" ? "保存中……" : `保存到草稿（${familyName}/${actionName}）`}</button>
      </div>
      {checks ? <ChecksList checks={checks} empty="没有提示。" /> : null}
    </div>
  );
}

function BoardThumb({ data, view, version }: { data: ImageData; view: { x: number; y: number; w: number; h: number }; version: number }) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const z = Math.max(1, Math.floor(56 / Math.max(view.w, view.h)));
    canvas.width = view.w * z; canvas.height = view.h * z;
    const ctx = canvas.getContext("2d")!;
    ctx.imageSmoothingEnabled = false;
    paintChecker(ctx, canvas.width, canvas.height, 4);
    ctx.drawImage(toCanvas(data), view.x, view.y, view.w, view.h, 0, 0, canvas.width, canvas.height);
  }, [data, view, version]);
  return <canvas ref={ref} class="pixel-canvas" />;
}
