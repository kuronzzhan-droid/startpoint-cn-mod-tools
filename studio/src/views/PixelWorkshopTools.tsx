import { useEffect, useMemo, useRef, useState } from "preact/hooks";
import {
  ActionFrames, base64ToBytes, BaseImageSpec, bytesToBase64, DraftCheck, drafts, GENERATE_ACTIONS, GeneratedFrame,
  PaletteColor, PaletteGroup, PixelAction, WorkshopAnalysis, workshop,
} from "../api";
import { ChecksList } from "./Changes";
import { Notice } from "./common";
import { InfoTip } from "./Delivery";
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
      <p class="hint">按官方小人的做法，从正面 / 背面 / 躺倒三张底图自动合成动作，不调用任何外部服务：
        走路 = 上下轻晃 1 像素、裙摆左右摆；胜利 = 起跳 → 最高点带火花 → 落地（客户端第 19 帧取举手画面，会落在最高点）；
        幽灵 = 变成白蓝色、悬浮；入棺 = 渐隐后躺倒；复活 = 幽灵落下 → 闪白 → 恢复。底图默认用草稿里的样子（换过色就是换色后的颜色）。
        <InfoTip text="技术细节：每帧 256×256 帧框、定位原点 (128,128)，fy = −(128 − h + dy)；端点按官方比例缩放，胜利动作保证 begin+18 落在最高点那张。" /></p>
      <div class="ws-bases">
        {(["front", "back", "liedown"] as Slot[]).map((slot) => (
          <div class={"ws-base" + (active === slot ? " on" : "")} onClick={() => setActive(slot)}>
            <strong class="small">{SLOT_LABEL[slot]}</strong>
            {bases[slot] ? <img src={bases[slot]!.url} alt="" /> : <span class="muted small">{slot === "liedown" ? "未选：用正面转 90°" : "未选"}</span>}
            <span class="small muted">{bases[slot] && "cell" in bases[slot]!.spec ? "现有画面" : bases[slot] ? "上传" : ""}</span>
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
          <span class="small muted">点下面的现有画面，设为「{SLOT_LABEL[active]}」底图：</span>
          <div class="ws-cellpick-list">
            {uniqueCells.map((key) => (
              <button title={"图集端点 " + key} onClick={() => setBases({ ...bases, [active]: {
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
                <span class="small mono" title={`停留 ${f.duration} 帧 · 下沉 dy ${f.dy} · fy ${-(f.bbox[1])}`}>{f.duration} 帧 · ↓{f.dy > 0 ? "+" : ""}{f.dy}</span>
                <span class="small muted ws-note">{f.note}</span>
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
//
// Frame pixels are the backend's raw RGBA (GET …/pixel-workshop/action/<family>/<action>):
// canvases only display them (putImageData, never getImageData/toDataURL), and saving sends the
// raw bytes back (pixelFrame.rgba). Untouched pixels — including semi-transparent shadow and
// ghost pixels — therefore stay byte-identical; a save without edits compiles to the same frames.

type Tool = "pencil" | "eraser" | "fill" | "picker";
const TOOL_LABEL: Record<Tool, string> = { pencil: "铅笔", eraser: "橡皮", fill: "填充", picker: "吸管" };
type BoardFrame = { id: number; data: Uint8ClampedArray; duration: number };
type Box = { x: number; y: number; w: number; h: number };

let frameSerial = 0;

function expandFrame(frame: ActionFrames["frames"][number], width: number, height: number): Uint8ClampedArray {
  const out = new Uint8ClampedArray(width * height * 4);
  if (!frame.box || !frame.rgba) return out;
  const [x0, y0, x1, y1] = frame.box;
  const src = base64ToBytes(frame.rgba);
  const w = x1 - x0;
  for (let y = y0; y < y1; y++) out.set(src.subarray((y - y0) * w * 4, (y - y0 + 1) * w * 4), (y * width + x0) * 4);
  return out;
}

/** Display-only canvas (putImageData; the board never reads pixels back from a canvas). */
function toCanvas(data: Uint8ClampedArray, width: number, height: number): HTMLCanvasElement {
  const canvas = document.createElement("canvas");
  canvas.width = width; canvas.height = height;
  canvas.getContext("2d")!.putImageData(new ImageData(new Uint8ClampedArray(data), width, height), 0, 0);
  return canvas;
}

export function DrawingBoard({ characterId, analysis, groups, refresh, onSaved }: {
  characterId: string; analysis: WorkshopAnalysis; groups: Record<string, PaletteGroup>; refresh: number; onSaved: () => void;
}) {
  const fam = useFamilies(characterId, "draft", refresh);
  const [familyName, setFamilyName] = useState("pixelart");
  const [actionName, setActionName] = useState("neutral");
  const [source, setSource] = useState<ActionFrames | null>(null);
  const [frames, setFrames] = useState<BoardFrame[]>([]);
  const [index, setIndex] = useState(0);
  const [tool, setTool] = useState<Tool>("pencil");
  const [color, setColor] = useState<string>(analysis.palette[0]?.hex ?? "#000000");
  const [custom, setCustom] = useState<string[]>([]);
  const [onion, setOnion] = useState(true);
  const [full, setFull] = useState(false);
  const [version, setVersion] = useState(0);
  // Undo records name the frame by id, so copying/deleting frames cannot redirect them to another frame.
  const [undo, setUndo] = useState<{ id: number; data: Uint8ClampedArray }[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<{ kind: "info" | "error"; text: string } | null>(null);
  const [checks, setChecks] = useState<DraftCheck[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const ref = useRef<HTMLCanvasElement>(null);
  const drawing = useRef(false);

  const family = familyOf(fam.meta, familyName);
  const action: PixelAction | undefined = family?.actions.find((a) => a.name === actionName);
  const W = source?.frameBox[0] ?? BOX, H = source?.frameBox[1] ?? BOX;
  const origin = source?.origin ?? [W / 2, H / 2];

  const [actionBox, setActionBox] = useState<Box>({ x: 0, y: 0, w: BOX, h: BOX });
  useEffect(() => {
    if (!family || !action) { setFrames([]); setSource(null); return; }
    let alive = true;
    setLoadError(null);
    workshop.actionFrames(characterId, familyName, actionName, fam.source).then((data) => {
      if (!alive) return;
      const [w, h] = data.frameBox;
      const loaded = data.frames.map((f) => ({ id: ++frameSerial, data: expandFrame(f, w, h), duration: f.duration }));
      // View = this action's visible union (+ origin), padded; fixed while drawing.
      let x0 = data.origin[0], y0 = data.origin[1], x1 = x0, y1 = y0;
      for (const f of data.frames) {
        if (!f.box) continue;
        x0 = Math.min(x0, f.box[0]); y0 = Math.min(y0, f.box[1]); x1 = Math.max(x1, f.box[2] - 1); y1 = Math.max(y1, f.box[3] - 1);
      }
      const pad = 10, minSide = 40;
      const bw = Math.max(x1 - x0 + 1 + pad * 2, minSide), bh = Math.max(y1 - y0 + 1 + pad * 2, minSide);
      const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
      const x = Math.max(0, Math.min(w - bw, Math.round(cx - bw / 2))), y = Math.max(0, Math.min(h - bh, Math.round(cy - bh / 2)));
      setActionBox({ x, y, w: Math.min(w, bw), h: Math.min(h, bh) });
      setSource(data);
      setFrames(loaded);
      setIndex(0); setUndo([]); setChecks(null);
    }, (e: Error) => { if (alive) setLoadError(e.message); });
    return () => { alive = false; };
  }, [family, action, fam.source, characterId]);

  const view = full || !source ? { x: 0, y: 0, w: W, h: H } : actionBox;
  const zoom = Math.max(2, Math.min(16, Math.floor(Math.min(560 / view.w, 460 / view.h))));
  const [draftPalette, setDraftPalette] = useState<PaletteColor[] | null>(null);
  useEffect(() => {
    workshop.analyze(characterId, "draft").then((a) => setDraftPalette(a.palette), () => setDraftPalette(null));
  }, [characterId, refresh]);
  const palette = useMemo(() => [...(draftPalette ?? analysis.palette).map((p) => p.hex), ...custom], [draftPalette, analysis.palette, custom]);
  const counts = useMemo(() => Object.fromEntries((draftPalette ?? analysis.palette).map((p) => [p.hex, p.count])), [draftPalette, analysis.palette]);

  useEffect(() => {
    const canvas = ref.current;
    const current = frames[index];
    if (!canvas || !current) return;
    canvas.width = view.w * zoom; canvas.height = view.h * zoom;
    const ctx = canvas.getContext("2d")!;
    ctx.imageSmoothingEnabled = false;
    paintChecker(ctx, canvas.width, canvas.height, zoom * 2);
    const draw = (data: Uint8ClampedArray, alpha: number) => {
      ctx.globalAlpha = alpha;
      ctx.drawImage(toCanvas(data, W, H), view.x, view.y, view.w, view.h, 0, 0, canvas.width, canvas.height);
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
    return x >= 0 && y >= 0 && x < W && y < H ? [x, y] : null;
  };
  const pushUndo = () => {
    const current = frames[index];
    if (current) setUndo((u) => [...u.slice(-49), { id: current.id, data: new Uint8ClampedArray(current.data) }]);
  };
  const apply = (e: PointerEvent, first: boolean) => {
    const p = pointAt(e);
    const current = frames[index];
    if (!p || !current) return;
    const d = current.data;
    const at = (p[1] * W + p[0]) * 4;
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
      const seen = new Uint8Array(W * H);
      while (stack.length) {
        const [x, y] = stack.pop()!;
        if (x < 0 || y < 0 || x >= W || y >= H || seen[y * W + x]) continue;
        seen[y * W + x] = 1;
        const i = (y * W + x) * 4;
        if ([d[i], d[i + 1], d[i + 2], d[i + 3]].join(",") !== target) continue;
        write(i);
        stack.push([x + 1, y], [x - 1, y], [x, y + 1], [x, y - 1]);
      }
    } else write(at);
    setVersion((v) => v + 1);
  };
  const nudge = (dy: number) => {
    pushUndo();
    const src = frames[index].data;
    const out = new Uint8ClampedArray(src.length);
    for (let y = 0; y < H; y++) {
      const ty = y + dy;
      if (ty < 0 || ty >= H) continue;
      out.set(src.subarray(y * W * 4, (y + 1) * W * 4), ty * W * 4);
    }
    const next = [...frames];
    next[index] = { ...frames[index], data: out };
    setFrames(next);
  };
  const undoLast = () => {
    const stack = [...undo];
    while (stack.length) {
      const last = stack.pop()!;
      const at = frames.findIndex((f) => f.id === last.id);
      if (at < 0) continue; // that frame was deleted
      const next = [...frames];
      next[at] = { ...next[at], data: last.data };
      setFrames(next); setUndo(stack); setIndex(at);
      return;
    }
    setUndo([]);
  };
  const total = frames.reduce((n, f) => n + f.duration, 0);
  const request = () => ({
    family: familyName, action: actionName, origin: { mode: "board", from: fam.source },
    frames: frames.map((f) => ({ rgba: bytesToBase64(new Uint8Array(f.data.buffer, f.data.byteOffset, f.data.byteLength)),
      width: W, height: H, duration: f.duration, anchor: origin })),
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
  const setDuration = (value: string) => {
    const v = Math.max(1, Math.min(600, Math.round(Number(value) || 1)));
    const next = [...frames]; next[index] = { ...next[index], duration: v }; setFrames(next);
  };

  if (fam.error) return <Notice kind="error">{fam.error}</Notice>;
  if (!fam.meta) return <div class="loading">正在读取像素帧……</div>;

  return (
    <div class="ws-board">
      <div class="toolbar">
        <label>像素族
          <select value={familyName} onChange={(e) => setFamilyName((e.target as HTMLSelectElement).value)}>
            {fam.meta.families.filter((f) => !f.error).map((f) => <option value={f.family}>{f.label}</option>)}
          </select>
        </label>
        <label>动作
          <select value={actionName} onChange={(e) => setActionName((e.target as HTMLSelectElement).value)}>
            {family?.actions.map((a) => <option value={a.name}>{a.label} · {a.totalFrames} 帧</option>)}
          </select>
        </label>
        <span class="small muted" title={`帧框 ${W}×${H} · 定位原点 (${origin.join(", ")})`}>{fam.source === "draft" ? "草稿里的帧" : "当前帧"} · 共 {total} 帧
          {action && total !== action.totalFrames ? <span class="warn-text">（原 {action.totalFrames}；只有末尾动作能改总长）</span> : null}</span>
      </div>
      {message ? <Notice kind={message.kind === "error" ? "error" : "info"}>{message.text}</Notice> : null}
      {loadError ? <Notice kind="error">读取动作帧失败：{loadError}</Notice> : null}
      <div class="ws-board-main">
        <div>
          <div class="toolbar ws-tools">
            {(Object.keys(TOOL_LABEL) as Tool[]).map((t) => <button class={tool === t ? "primary" : ""} onClick={() => setTool(t)}>{TOOL_LABEL[t]}</button>)}
            <button onClick={undoLast} disabled={!undo.length}>撤销</button>
            <label class="check small"><input type="checkbox" checked={onion} onChange={(e) => setOnion((e.target as HTMLInputElement).checked)} />洋葱皮</label>
            <label class="check small"><input type="checkbox" checked={full} onChange={(e) => setFull((e.target as HTMLInputElement).checked)} />整帧</label>
          </div>
          <canvas ref={ref} class="pixel-canvas ws-board-canvas" aria-label="画板"
            onPointerDown={(e) => { drawing.current = true; (e.target as HTMLCanvasElement).setPointerCapture(e.pointerId); apply(e as unknown as PointerEvent, true); }}
            onPointerMove={(e) => { if (drawing.current && tool !== "fill" && tool !== "picker") apply(e as unknown as PointerEvent, false); }}
            onPointerUp={() => { drawing.current = false; }} />
        </div>
        <aside class="ws-board-side">
          <h5>调色板 <span class="muted small">（本角色现有颜色；新增颜色会单独列出）</span></h5>
          <BoardPalette palette={palette} groups={groups} custom={custom} color={color} counts={counts}
            onPick={(hex) => { setColor(hex); if (tool === "eraser" || tool === "picker") setTool("pencil"); }} />
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
            <button onClick={() => nudge(-1)} title="整帧上移 1 像素（离地）">上移 1px</button>
            <button onClick={() => nudge(1)} title="整帧下移 1 像素（下沉）">下移 1px</button>
          </div>
          <label class="small">停留<input type="number" min={1} max={600} step={1} value={frames[index]?.duration ?? 1}
            onInput={(e) => setDuration((e.target as HTMLInputElement).value)} />帧</label>
          <div class="save-row">
            <button onClick={() => {
              const next = [...frames];
              next.splice(index + 1, 0, { id: ++frameSerial, data: new Uint8ClampedArray(frames[index].data), duration: frames[index].duration });
              setFrames(next); setIndex(index + 1);
            }}>复制本帧</button>
            <button onClick={() => { if (frames.length < 2) return; const next = frames.filter((_, i) => i !== index); setFrames(next); setIndex(Math.max(0, index - 1)); }} disabled={frames.length < 2}>删除本帧</button>
          </div>
        </aside>
      </div>
      <div class="filmstrip ws-board-strip">
        {frames.map((f, i) => (
          <button class={"film" + (i === index ? " on" : "")} onClick={() => setIndex(i)}>
            <BoardThumb data={f.data} size={[W, H]} view={view} version={version} />
            <span class="small mono">#{i + 1} · {f.duration}f</span>
          </button>
        ))}
      </div>
      <div class="save-row">
        <button onClick={() => save(true)} disabled={busy !== null || !frames.length || !drafts.hasToken()}>{busy === "check" ? "检查中……" : "检查（不写草稿）"}</button>
        <button class="primary" onClick={() => save(false)} disabled={busy !== null || !frames.length || !drafts.hasToken()}>{busy === "save" ? "保存中……" : `保存到草稿（${action?.label ?? actionName}）`}</button>
      </div>
      {checks ? <ChecksList checks={checks} empty="没有提示。" /> : null}
    </div>
  );
}

/** Palette grouped like the breakdown page (本体 / 描边 / 特效 / 入棺幽灵 / 新增); colours used by fewer
 *  than 10 pixels (edge / semi-transparent blends) are folded away until asked for. */
function BoardPalette({ palette, groups, custom, color, counts, onPick }: {
  palette: string[]; groups: Record<string, PaletteGroup>; custom: string[]; color: string; counts: Record<string, number>;
  onPick: (hex: string) => void;
}) {
  const [showTiny, setShowTiny] = useState(false);
  const order: [PaletteGroup | "custom", string][] = [["body", "本体"], ["outline", "描边"], ["fx", "特效"], ["template", "入棺/幽灵"], ["custom", "新增"]];
  const of = (hex: string): PaletteGroup | "custom" => (custom.includes(hex) ? "custom" : groups[hex] ?? "fx");
  const tiny = (hex: string) => !custom.includes(hex) && (counts[hex] ?? 0) < 10 && hex !== color;
  const hidden = palette.filter(tiny).length;
  return (
    <div class="ws-board-palette-groups">
      {hidden ? (
        <label class="check small"><input type="checkbox" checked={showTiny} onChange={(e) => setShowTiny((e.target as HTMLInputElement).checked)} />
          显示 {hidden} 个零星色（不到 10 个像素）</label>
      ) : null}
      {order.map(([g, label]) => {
        const colors = palette.filter((hex) => of(hex) === g && (showTiny || !tiny(hex)));
        if (!colors.length) return null;
        return (
          <div class="ws-board-pgroup">
            <span class="small muted">{label}</span>
            <div class="ws-board-palette">
              {colors.map((hex) => (
                <button class={"ws-swatch big" + (hex === color ? " on" : "")} style={{ background: hex }} title={hex} onClick={() => onPick(hex)} />
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function BoardThumb({ data, size, view, version }: { data: Uint8ClampedArray; size: [number, number]; view: Box; version: number }) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const z = Math.max(1, Math.floor(56 / Math.max(view.w, view.h)));
    canvas.width = view.w * z; canvas.height = view.h * z;
    const ctx = canvas.getContext("2d")!;
    ctx.imageSmoothingEnabled = false;
    paintChecker(ctx, canvas.width, canvas.height, 4);
    ctx.drawImage(toCanvas(data, size[0], size[1]), view.x, view.y, view.w, view.h, 0, 0, canvas.width, canvas.height);
  }, [data, view, version]);
  return <canvas ref={ref} class="pixel-canvas" />;
}
