// 像素 › 场地比例: the character (and an optional effect image) on a real quest stage, in runtime
// pixels (terrain ×6 = the client's 1080×1920 BOUNDS; pixel frames ×frame.scale). Exports a
// full-size positioning reference image.
import { useEffect, useRef, useState } from "preact/hooks";
import { craft, StageInfo } from "../craftApi";
import { Notice } from "./common";
import { InfoTip } from "./Delivery";
import "./craft.css";
import { cellAt, loadImage, readAsDataUrl, useClock, useFamilies } from "./workshopKit";

type Point = { x: number; y: number };
type Overlay = { img: HTMLImageElement; name: string; scale: number; at: Point };

const VIEW_HEIGHT = 640;
const GRID = 120;

function draw(ctx: CanvasRenderingContext2D, stage: StageInfo, k: number, paint: {
  sprite?: { image: CanvasImageSource; sx: number; sy: number; w: number; h: number; ax: number; ay: number; scale: number; at: Point };
  overlay?: Overlay | null; grid: boolean; labels: boolean;
}) {
  const b = stage.bounds;
  const W = b.width * k, H = b.height * k;
  ctx.imageSmoothingEnabled = false;
  ctx.fillStyle = "#1d222b";
  ctx.fillRect(0, 0, W, H);
  const X = (x: number) => (x - b.x) * k, Y = (y: number) => (y - b.y) * k;
  if (paint.grid) {
    ctx.strokeStyle = "rgba(255,255,255,0.08)";
    ctx.lineWidth = 1;
    for (let x = 0; x <= b.width; x += GRID) { ctx.beginPath(); ctx.moveTo(x * k + 0.5, 0); ctx.lineTo(x * k + 0.5, H); ctx.stroke(); }
    for (let y = 0; y <= b.height; y += GRID) { ctx.beginPath(); ctx.moveTo(0, y * k + 0.5); ctx.lineTo(W, y * k + 0.5); ctx.stroke(); }
    if (paint.labels) {
      ctx.fillStyle = "rgba(255,255,255,0.45)";
      ctx.font = `${Math.max(10, 22 * k)}px sans-serif`;
      for (let y = GRID; y < b.height; y += GRID) ctx.fillText(String(y), 4, y * k - 4);
      for (let x = GRID; x < b.width; x += GRID) ctx.fillText(String(x), x * k + 4, 24 * k + 10);
    }
  }
  for (const o of stage.objects) {
    ctx.strokeStyle = o.type.startsWith("WALL") ? "rgba(173,181,189,0.85)" : "rgba(173,181,189,0.4)";
    ctx.lineWidth = o.type.startsWith("WALL") ? 3 : 1.5;
    if (o.polygon.length > 1) {
      ctx.beginPath();
      o.polygon.forEach(([px, py], i) => (i ? ctx.lineTo(X(px), Y(py)) : ctx.moveTo(X(px), Y(py))));
      ctx.closePath();
      ctx.stroke();
    } else if (o.width && o.height) ctx.strokeRect(X(o.x), Y(o.y), o.width * k, o.height * k);
  }
  ctx.strokeStyle = "#8ce99a";
  ctx.lineWidth = 2;
  ctx.strokeRect(1, 1, W - 2, H - 2);
  ctx.font = `${Math.max(10, 20 * k)}px sans-serif`;
  for (const c of stage.coffins) {
    ctx.strokeStyle = "#74c0fc";
    ctx.beginPath(); ctx.arc(X(c.x), Y(c.y), Math.max(3, 18 * k), 0, Math.PI * 2); ctx.stroke();
    if (paint.labels) { ctx.fillStyle = "#74c0fc"; ctx.fillText(`${c.party + 1}-${c.member + 1}`, X(c.x) + 22 * k, Y(c.y) + 6 * k); }
  }
  for (const p of stage.positions) {
    if (!p.name) continue;
    ctx.fillStyle = "#ffd43b";
    ctx.fillRect(X(p.x) - 3, Y(p.y) - 3, 6, 6);
    if (paint.labels) ctx.fillText(p.name, X(p.x) + 6, Y(p.y) - 6);
  }
  const s = paint.sprite;
  if (s) {
    ctx.drawImage(s.image, s.sx, s.sy, s.w, s.h, X(s.at.x - s.ax * s.scale), Y(s.at.y - s.ay * s.scale), s.w * s.scale * k, s.h * s.scale * k);
    ctx.strokeStyle = "rgba(230,60,90,0.9)";
    ctx.beginPath(); ctx.moveTo(X(s.at.x) - 8, Y(s.at.y) + 0.5); ctx.lineTo(X(s.at.x) + 8, Y(s.at.y) + 0.5); ctx.stroke();
  }
  const o = paint.overlay;
  if (o) {
    const w = o.img.naturalWidth * o.scale, h = o.img.naturalHeight * o.scale;
    ctx.globalAlpha = 0.85;
    ctx.drawImage(o.img, X(o.at.x - w / 2), Y(o.at.y - h / 2), w * k, h * k);
    ctx.globalAlpha = 1;
    ctx.strokeStyle = "rgba(255,212,59,0.8)";
    ctx.setLineDash([4, 3]);
    ctx.strokeRect(X(o.at.x - w / 2), Y(o.at.y - h / 2), w * k, h * k);
    ctx.setLineDash([]);
  }
}

export function StageScale({ characterId }: { characterId: string }) {
  const [quest, setQuest] = useState("1002001");
  const [terrain, setTerrain] = useState("");
  const [stage, setStage] = useState<StageInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { meta, sheets } = useFamilies(characterId, "draft");
  const [familyName, setFamilyName] = useState("pixelart");
  const [actionName, setActionName] = useState("neutral");
  const [playing, setPlaying] = useState(true);
  const [tick] = useClock(playing);
  const [at, setAt] = useState<Point | null>(null);
  const [overlay, setOverlay] = useState<Overlay | null>(null);
  const [labels, setLabels] = useState(true);
  const drag = useRef<"sprite" | "overlay" | null>(null);
  const canvas = useRef<HTMLCanvasElement>(null);

  const load = () => {
    setError(null);
    craft.stage(quest, terrain).then((s) => {
      setStage(s);
      const first = s.coffins[0];
      setAt(first ? { x: first.x, y: first.y } : { x: s.bounds.x + s.bounds.width / 2, y: s.bounds.y + s.bounds.height * 0.75 });
    }, (e: Error) => setError(e.message));
  };
  useEffect(load, []);

  const family = meta?.families.find((f) => f.family === familyName && !f.error);
  const action = family?.actions.find((a) => a.name === actionName) ?? family?.actions[0];
  const k = stage ? VIEW_HEIGHT / stage.bounds.height : 1;
  const sprite = () => {
    const image = family ? sheets[family.family] : undefined;
    if (!family || !action || !image || !at) return undefined;
    const cell = cellAt(action, tick);
    return { image, sx: (cell % family.columns) * family.cellWidth, sy: Math.floor(cell / family.columns) * family.cellHeight,
      w: family.cellWidth, h: family.cellHeight, ax: family.anchor.x, ay: family.anchor.y, scale: family.scale || 6, at };
  };

  useEffect(() => {
    const el = canvas.current;
    if (!el || !stage) return;
    el.width = Math.round(stage.bounds.width * k);
    el.height = Math.round(stage.bounds.height * k);
    draw(el.getContext("2d")!, stage, k, { sprite: sprite(), overlay, grid: true, labels });
  });

  const exportPng = () => {
    if (!stage) return;
    const el = document.createElement("canvas");
    el.width = stage.bounds.width;
    el.height = stage.bounds.height;
    draw(el.getContext("2d")!, stage, 1, { sprite: sprite(), overlay, grid: true, labels: true });
    el.toBlob((blob) => {
      if (!blob) return;
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `定位参考-${characterId}-${stage.quest?.id ?? "terrain"}-${actionName}.png`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    }, "image/png");
  };

  const toStage = (e: PointerEvent): Point => {
    const rect = (e.target as HTMLCanvasElement).getBoundingClientRect();
    return { x: stage!.bounds.x + (e.clientX - rect.left) / k, y: stage!.bounds.y + (e.clientY - rect.top) / k };
  };
  const down = (e: PointerEvent) => {
    if (!stage) return;
    const p = toStage(e);
    const near = (q: Point | null | undefined) => q && Math.hypot(q.x - p.x, q.y - p.y) < 120;
    drag.current = overlay && near(overlay.at) && !(at && near(at) && Math.hypot(at.x - p.x, at.y - p.y) < Math.hypot(overlay.at.x - p.x, overlay.at.y - p.y))
      ? "overlay" : "sprite";
    (e.target as HTMLCanvasElement).setPointerCapture(e.pointerId);
    move(e);
  };
  const move = (e: PointerEvent) => {
    if (!drag.current || !stage) return;
    const p = toStage(e);
    if (drag.current === "overlay") setOverlay((o) => (o ? { ...o, at: p } : o));
    else setAt(p);
  };

  const sp = sprite();
  const height = sp && family ? Math.round(sp.h * sp.scale) : 0;
  return (
    <div class="ws-import">
      <p class="hint">按真实关卡边界看角色和特效有多大：战场是客户端的 1080×1920（地形 ×6），像素小人按 frame.scale 放大，
        同一张图上直接比。拖动小人或特效换位置，导出的定位参考图是 1080×1920 原尺寸，带 120px 网格和复活位编号。
        <InfoTip text={"关卡默认主线 1-2-1（1002001）。也可以直接填地形路径，例如 battle/terrain/...。\n复活位圆圈 = 队-成员；黄点 = 命名站位；灰线 = 墙和其它对象。"} /></p>
      <div class="toolbar">
        <label>关卡 ID<input class="mono" value={quest} onInput={(e) => setQuest((e.target as HTMLInputElement).value)} /></label>
        <label>或地形路径<input class="mono" placeholder="battle/terrain/..." value={terrain} onInput={(e) => setTerrain((e.target as HTMLInputElement).value)} /></label>
        <button onClick={load}>读取场地</button>
      </div>
      {error ? <Notice kind="error">{error}</Notice> : null}
      {stage ? (
        <p class="small muted">{stage.quest ? `${stage.quest.category} ${stage.quest.name}（${stage.quest.id}）· ` : ""}地形 <span class="mono">{stage.terrain}</span> · 波次层 {stage.wave}（共 {stage.waves} 层）
          · 边界 {stage.bounds.width}×{stage.bounds.height}</p>
      ) : null}
      <div class="toolbar">
        <label>像素族<select value={familyName} onChange={(e) => setFamilyName((e.target as HTMLSelectElement).value)}>
          {(meta?.families ?? []).filter((f) => !f.error).map((f) => <option value={f.family}>{f.label}</option>)}
        </select></label>
        <label>动作<select value={action?.name} onChange={(e) => setActionName((e.target as HTMLSelectElement).value)}>
          {(family?.actions ?? []).map((a) => <option value={a.name}>{a.label}（{a.name}）</option>)}
        </select></label>
        <button onClick={() => setPlaying((p) => !p)}>{playing ? "暂停" : "播放"}</button>
        <label class="upload-btn">叠一张特效图<input type="file" accept="image/png" onChange={async (e) => {
          const f = (e.target as HTMLInputElement).files?.[0];
          if (!f || !stage) return;
          const img = await loadImage(await readAsDataUrl(f));
          setOverlay({ img, name: f.name, scale: overlay?.scale ?? 1, at: at ?? { x: stage.bounds.width / 2, y: stage.bounds.height / 2 } });
        }} /></label>
        {overlay ? (
          <>
            <label>特效放大<input type="number" min={0.1} max={12} step={0.1} value={overlay.scale}
              onInput={(e) => setOverlay({ ...overlay, scale: Number((e.target as HTMLInputElement).value) || 1 })} /></label>
            <button onClick={() => setOverlay(null)}>去掉特效</button>
          </>
        ) : null}
        <label><input type="checkbox" checked={labels} onChange={(e) => setLabels((e.target as HTMLInputElement).checked)} />标注</label>
        <button class="primary" onClick={exportPng} disabled={!stage}>导出定位参考图</button>
      </div>
      {stage ? (
        <div class="stage-scale">
          <canvas ref={canvas} style={{ cursor: "crosshair", touchAction: "none" }}
            onPointerDown={down} onPointerMove={move} onPointerUp={() => { drag.current = null; }} />
          <ul class="small">
            {sp && at ? <li>小人帧框 {Math.round(sp.w * sp.scale)}×{height}（运行时像素，×{sp.scale}）· 占战场高 {(height / stage.bounds.height * 100).toFixed(1)}%
              · 脚底 ({Math.round(at.x)}, {Math.round(at.y)})</li> : <li class="muted">正在读取像素……</li>}
            {overlay ? <li>特效 {overlay.name}：{Math.round(overlay.img.naturalWidth * overlay.scale)}×{Math.round(overlay.img.naturalHeight * overlay.scale)}
              · 中心 ({Math.round(overlay.at.x)}, {Math.round(overlay.at.y)}) · 占战场宽 {(overlay.img.naturalWidth * overlay.scale / stage.bounds.width * 100).toFixed(1)}%</li> : null}
            <li class="muted">{stage.note}</li>
          </ul>
        </div>
      ) : null}
    </div>
  );
}
