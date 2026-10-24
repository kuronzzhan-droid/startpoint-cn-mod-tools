// 地形：逐层画出 1080×1920 的战场（边界 / 9 个复活位 / 命名站位 / boss 初始位置），
// 拖动或新增命名站位、换成已有地形、复制已有战斗层追加一波。每次只提交一个操作，先实时预检再写入草稿。
import { useEffect, useMemo, useRef, useState } from "preact/hooks";
import {
  boss, BossDoc, BossList, BossOptions, BehaviorDoc, Rect, TerrainDoc, TerrainLayer, TerrainRequest,
} from "../../bossApi";
import { Notice } from "../common";
import { InfoTip } from "../Delivery";
import { PreviewState } from "./BossParams";
import { Src } from "./BossRead";
import { cellOf, csvRow, OpActions, useBossOp, useSection } from "./bossOps";
import { questElement, shortName } from "./bossModel";

/** Terrain pixels → runtime: ×6 (the client draws the BOUNDS rectangle as the 1080×1920 field). */
const K = 6;
const STAGE = { w: 1080, h: 1920 };
const VIEW = 0.3;
const PAIR = 0.26;
const NAME = /^[A-Za-z0-9_-]{1,80}$/;

type Mode = "positions" | "replace" | "wave";

interface Pending { action: "add" | "update" | "delete"; name: string; x: string; y: string; width: string; height: string }

function boundsOf(layer: TerrainLayer | undefined): Rect | null {
  return layer?.bounds?.[0] ?? null;
}

function inside(b: Rect, r: Rect): boolean {
  return r.x >= b.x && r.y >= b.y && r.x + r.width <= b.x + b.width && r.y + r.height <= b.y + b.height;
}

const num = (v: string) => (v.trim() === "" ? NaN : Number(v));

/** Names a GeneralBoss routine state or StandardBoss esdl points at (the whole wave shares them). */
function bossPositions(doc: BossDoc, behavior: BehaviorDoc | null, wave: string): { name: string; label: string }[] {
  const out = new Map<string, string>();
  for (const e of doc.enemies) {
    if (e.kind !== "boss" || e.wave !== wave) continue;
    if (e.position_name) out.set(e.position_name, `boss ${e.code}`);
  }
  for (const e of behavior?.enemies ?? []) {
    if (e.wave !== wave) continue;
    const initial = e.decoded?.initialPosition;
    if (Array.isArray(initial) && initial[0] === "Absolute" && typeof initial[1] === "string" && !out.has(initial[1])) {
      out.set(initial[1], `boss ${e.enemyCode}`);
    }
  }
  return [...out].map(([name, label]) => ({ name, label }));
}

function referencedNames(behavior: BehaviorDoc | null, wave: string): Set<string> {
  const names = new Set<string>();
  for (const e of behavior?.enemies ?? []) {
    if (e.wave !== wave) continue;
    for (const s of e.states) if (s.position) names.add(s.position);
  }
  return names;
}

export function BossTerrain({ doc, questId, rev, list, options, onPreview, onWritten }: {
  doc: BossDoc; questId: string; rev: string; list: BossList | null; options: BossOptions | null;
  onPreview: (s: PreviewState) => void; onWritten: () => void;
}) {
  const terrain = useSection<TerrainDoc>(questId, "terrain", rev);
  const behavior = useSection<BehaviorDoc>(questId, "behavior", rev);
  const [mode, setMode] = useState<Mode>("positions");
  const [layerIndex, setLayerIndex] = useState(0);
  const data = terrain.data;
  const layers = data?.waves ?? [];
  const layer = layers[Math.min(layerIndex, Math.max(0, layers.length - 1))];

  if (doc.routing.kind === "BothBoss") return <Notice kind="warn">五重入口（BothBoss）只读：地形属于隐藏关，请打开左侧对应的隐藏关。</Notice>;
  if (terrain.error) return <Notice kind="error">读取地形失败：{terrain.error}</Notice>;
  if (!data) return <div class="loading">正在解码地形……</div>;
  if (data.missing) return <Notice kind="error">这一关的地形 {data.logical} 在当前视图里不存在，不能编辑。</Notice>;

  return (
    <div class="boss-terrain">
      <section class="boss-block">
        <header>
          <h3>地形</h3>
          <span class="mono small muted">{data.logical.replace(/\.amf3\.deflate$/, "")}</span>
          <InfoTip text={"坐标两套：表里存 Tiled 左上角（地形像素），客户端用中心点 ×6（运行时像素，1080×1920 对应边界框）。\n" +
            (data.coordinate_semantics ? Object.values(data.coordinate_semantics).join("\n") : "")} />
          <span class="spacer" /><Src c={data.source} />
        </header>
        <div class="segmented" role="group" aria-label="地形操作">
          {([["positions", "站位"], ["replace", "换地形"], ["wave", "追加一波"]] as [Mode, string][]).map(([id, label]) => (
            <button type="button" class={mode === id ? "on" : ""} aria-pressed={mode === id} onClick={() => setMode(id)}>{label}</button>
          ))}
        </div>
        {layers.length > 1 || mode !== "wave" ? (
          <div class="segmented layer-pick" role="group" aria-label="波次">
            {layers.map((w, i) => (
              <button type="button" class={i === layerIndex ? "on" : ""} aria-pressed={i === layerIndex} onClick={() => setLayerIndex(i)}>
                第 {i + 1} 波 <span class="small muted mono">层 {w.name}</span>
              </button>
            ))}
          </div>
        ) : null}
        {data.bindings ? (
          <details class="tech">
            <summary>技术细节：绑定</summary>
            <p class="small mono">field_data {data.bindings.field_data} · field {data.bindings.field} · zone {data.bindings.zone}</p>
            <ul class="small mono">{data.bindings.waves.map((w) => <li>层 {w.layer} → zone {w.zone_paths.map((p) => p.join("/")).join("、") || "（无）"}</li>)}</ul>
          </details>
        ) : null}
      </section>
      {mode === "positions" && layer ? (
        <PositionsEditor key={rev + layer.name} doc={doc} questId={questId} layer={layer} behavior={behavior.data}
          onPreview={onPreview} onWritten={onWritten} />
      ) : mode === "replace" && layer ? (
        <ReplaceEditor doc={doc} questId={questId} current={data} layerIndex={layerIndex} options={options}
          behavior={behavior.data} onPreview={onPreview} onWritten={onWritten} />
      ) : mode === "wave" ? (
        <WaveEditor doc={doc} questId={questId} current={data} list={list} onPreview={onPreview} onWritten={onWritten} />
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------------- canvas

interface Marker { name: string; rect: Rect; tone: "pos" | "pending" | "ghost"; note?: string }

/** One terrain layer on a 1080×1920 stage (the BOUNDS box); drag a named position when `onDrag` is set. */
export function TerrainCanvas({ layer, markers, bosses, referenced, selected, onSelect, onDrag, caption, view = VIEW }: {
  layer: TerrainLayer; markers?: Marker[]; bosses?: { name: string; label: string }[]; referenced?: Set<string>;
  selected?: string | null; onSelect?: (name: string) => void; onDrag?: (name: string, x: number, y: number) => void;
  caption?: string; view?: number;
}) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const drag = useRef<{ name: string; dx: number; dy: number } | null>(null);
  const b = boundsOf(layer) ?? { x: 0, y: 0, width: STAGE.w / K, height: STAGE.h / K };
  const positions: Marker[] = markers ?? layer.custom_positions.map((p) => ({ name: p.name, rect: p.rect, tone: "pos" as const }));
  const toStage = (x: number, y: number) => ({ x: (x - b.x) * K, y: (y - b.y) * K });
  const offscreen = layer.objects.filter((o) => typeof o.x === "number" && typeof o.y === "number"
    && ((o.x as number) < b.x || (o.y as number) < b.y || (o.x as number) > b.x + b.width || (o.y as number) > b.y + b.height)).length;

  useEffect(() => {
    const el = canvas.current;
    if (!el) return;
    const ratio = window.devicePixelRatio || 1;
    const cw = Math.round(STAGE.w * view), ch = Math.round(STAGE.h * view);
    if (el.width !== cw * ratio) { el.width = cw * ratio; el.height = ch * ratio; el.style.width = cw + "px"; el.style.height = ch + "px"; }
    const ctx = el.getContext("2d")!;
    const k = view * ratio;
    const stage = () => ctx.setTransform(k, 0, 0, k, 0, 0);
    stage();
    ctx.fillStyle = "#151a24"; ctx.fillRect(0, 0, STAGE.w, STAGE.h);
    ctx.strokeStyle = "rgba(255,255,255,0.06)"; ctx.lineWidth = 2;
    for (let x = 0; x <= STAGE.w; x += 120) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, STAGE.h); ctx.stroke(); }
    for (let y = 0; y <= STAGE.h; y += 120) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(STAGE.w, y); ctx.stroke(); }
    const font = (size: number) => { ctx.font = `${size}px "Microsoft YaHei UI", sans-serif`; };
    const label = (text: string, x: number, y: number, color: string) => {
      font(30);
      const w = ctx.measureText(text).width;
      const lx = Math.max(4, Math.min(STAGE.w - w - 12, x)), ly = Math.max(34, Math.min(STAGE.h - 8, y));
      ctx.fillStyle = "rgba(0,0,0,0.6)"; ctx.fillRect(lx - 4, ly - 28, w + 8, 36);
      ctx.fillStyle = color; ctx.fillText(text, lx, ly);
    };
    // Bounds = the whole stage; draw its frame.
    ctx.strokeStyle = "#51cf66"; ctx.lineWidth = 6; ctx.strokeRect(3, 3, STAGE.w - 6, STAGE.h - 6);
    label("边界 BOUNDS", 12, 44, "#8ce99a");
    // Other objects (walls, gates, spawns, items) in grey.
    for (const o of layer.objects) {
      const type = String(o.type ?? "");
      if (["BOUNDS", "COFFIN", "CUSTOM_POSITION"].includes(type) || typeof o.x !== "number" || typeof o.y !== "number") continue;
      const p = toStage(o.x as number, o.y as number);
      const line = (o.polyline ?? o.polygon) as { x: number; y: number }[] | undefined;
      ctx.strokeStyle = type.startsWith("WALL") ? "rgba(173,181,189,0.85)" : type === "GATE" || type === "TRANSIT" ? "#ffd43b" : "rgba(173,181,189,0.45)";
      ctx.lineWidth = type.startsWith("WALL") ? 6 : 3;
      if (Array.isArray(line) && line.length) {
        ctx.beginPath();
        line.forEach((pt, i) => (i ? ctx.lineTo(p.x + pt.x * K, p.y + pt.y * K) : ctx.moveTo(p.x + pt.x * K, p.y + pt.y * K)));
        if (o.polygon) ctx.closePath();
        ctx.stroke();
      } else if ((o.width as number) > 0) {
        ctx.setLineDash([10, 8]); ctx.strokeRect(p.x, p.y, (o.width as number) * K, (o.height as number) * K); ctx.setLineDash([]);
        if (type === "GATE" || type === "TRANSIT") label(type === "GATE" ? "出口 GATE" : "转场 TRANSIT", p.x, p.y - 6, "#ffe066");
      }
    }
    // 9 respawn points (party / member).
    layer.coffins.forEach((c) => {
      const p = toStage(c.rect.x + c.rect.width / 2, c.rect.y + c.rect.height / 2);
      ctx.fillStyle = "rgba(77,171,247,0.35)"; ctx.strokeStyle = "#4dabf7"; ctx.lineWidth = 3;
      ctx.beginPath(); ctx.arc(p.x, p.y, 34, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
      font(26); ctx.fillStyle = "#e7f5ff"; ctx.fillText(`${c.party + 1}-${c.member + 1}`, p.x - 20, p.y + 9);
    });
    // Named positions; boss initial positions get a red ring.
    const bossBy = new Map((bosses ?? []).map((x) => [x.name, x.label]));
    for (const m of positions) {
      const c = toStage(m.rect.x + m.rect.width / 2, m.rect.y + m.rect.height / 2);
      const color = m.tone === "pending" ? "#ff922b" : m.tone === "ghost" ? "rgba(255,212,59,0.6)" : "#ffd43b";
      const out = !inside(b, m.rect);
      ctx.save(); ctx.translate(c.x, c.y); ctx.rotate(Math.PI / 4);
      ctx.fillStyle = out ? "rgba(255,107,107,0.5)" : "rgba(255,212,59,0.25)";
      ctx.strokeStyle = out ? "#ff6b6b" : color; ctx.lineWidth = m.name === selected ? 8 : 4;
      const s = Math.max(28, m.rect.width * K * 0.55);
      ctx.fillRect(-s / 2, -s / 2, s, s); ctx.strokeRect(-s / 2, -s / 2, s, s);
      ctx.restore();
      if (bossBy.has(m.name)) {
        ctx.strokeStyle = "#ff6b6b"; ctx.lineWidth = 5;
        ctx.beginPath(); ctx.arc(c.x, c.y, 120, 0, Math.PI * 2); ctx.stroke();
        label(bossBy.get(m.name)!, c.x - 100, c.y + 160, "#ffa8a8");
      }
      const ref = referenced?.has(m.name) ? " · 行为引用" : "";
      label(`${m.name}${m.note ? " " + m.note : ""}${ref}`, c.x + 30, c.y - 24, out ? "#ff8787" : color);
    }
    stage();
  });

  const hit = (event: PointerEvent): { x: number; y: number } => {
    const rect = canvas.current!.getBoundingClientRect();
    return { x: ((event.clientX - rect.left) / rect.width) * STAGE.w, y: ((event.clientY - rect.top) / rect.height) * STAGE.h };
  };
  const onDown = (event: PointerEvent) => {
    const p = hit(event);
    let best: { name: string; d: number; m: Marker } | null = null;
    for (const m of positions) {
      if (m.tone === "ghost") continue;
      const c = toStage(m.rect.x + m.rect.width / 2, m.rect.y + m.rect.height / 2);
      const d = Math.hypot(p.x - c.x, p.y - c.y);
      if (d < 80 && (!best || d < best.d)) best = { name: m.name, d, m };
    }
    if (!best) return;
    onSelect?.(best.name);
    if (!onDrag) return;
    const c = toStage(best.m.rect.x, best.m.rect.y);
    drag.current = { name: best.name, dx: p.x - c.x, dy: p.y - c.y };
    (event.target as HTMLElement).setPointerCapture(event.pointerId);
  };
  const onMove = (event: PointerEvent) => {
    if (!drag.current || !onDrag) return;
    const p = hit(event);
    onDrag(drag.current.name, Math.round(b.x + (p.x - drag.current.dx) / K), Math.round(b.y + (p.y - drag.current.dy) / K));
  };
  const onUp = () => { drag.current = null; };
  return (
    <figure class="terrain-stage" style={{ maxWidth: Math.round(STAGE.w * view) + "px" }}>
      <canvas ref={canvas} class={"terrain-canvas" + (onDrag ? " draggable" : "")} onPointerDown={onDown} onPointerMove={onMove}
        onPointerUp={onUp} onPointerLeave={onUp} aria-label={caption ?? "地形画布"} />
      <figcaption class="small muted">
        {caption ? <>{caption} · </> : null}边界 {b.width}×{b.height}（运行时 {b.width * K}×{b.height * K}）· 复活位 {layer.coffin_count}
        {offscreen ? ` · 另有 ${offscreen} 个对象在边界外（未画）` : ""}
      </figcaption>
    </figure>
  );
}

function Legend() {
  return (
    <ul class="terrain-legend small">
      <li><span class="sw sw-bounds" />边界</li><li><span class="sw sw-coffin" />复活位（队-成员）</li>
      <li><span class="sw sw-pos" />命名站位</li><li><span class="sw sw-boss" />boss 初始位置</li>
      <li><span class="sw sw-pending" />待写入</li><li><span class="sw sw-wall" />墙 / 其它对象</li>
    </ul>
  );
}

// ---------------------------------------------------------------------------------- positions

function PositionsEditor({ doc, questId, layer, behavior, onPreview, onWritten }: {
  doc: BossDoc; questId: string; layer: TerrainLayer; behavior: BehaviorDoc | null;
  onPreview: (s: PreviewState) => void; onWritten: () => void;
}) {
  const b = boundsOf(layer);
  const [selected, setSelected] = useState<string | null>(layer.custom_positions[0]?.name ?? null);
  const [pending, setPending] = useState<Pending | null>(null);
  const [newName, setNewName] = useState("");
  const bosses = useMemo(() => bossPositions(doc, behavior, layer.name), [doc, behavior, layer.name]);
  const referenced = useMemo(() => referencedNames(behavior, layer.name), [behavior, layer.name]);
  const byName = new Map(layer.custom_positions.map((p) => [p.name, p]));

  const startUpdate = (name: string, x?: number, y?: number) => {
    const p = byName.get(name);
    if (!p && pending?.action !== "add") return;
    const base = pending && pending.name === name && pending.action !== "delete" ? pending
      : { action: "update" as const, name, x: String(p!.rect.x), y: String(p!.rect.y), width: String(p!.rect.width), height: String(p!.rect.height) };
    setPending({ ...base, ...(x !== undefined ? { x: String(x) } : {}), ...(y !== undefined ? { y: String(y) } : {}) });
  };

  const rect = pending ? { x: num(pending.x), y: num(pending.y), width: num(pending.width), height: num(pending.height) } : null;
  const problems: string[] = [];
  if (pending && rect && pending.action !== "delete") {
    if (!NAME.test(pending.name)) problems.push("名字只能用字母、数字、下划线或连字符（1–80 个字符）");
    if (pending.action === "add" && byName.has(pending.name)) problems.push(`这一层已有站位「${pending.name}」`);
    if (!Number.isFinite(rect.x) || !Number.isFinite(rect.y)) problems.push("坐标 x / y 必须填写");
    if (!(rect.width >= 0) || !(rect.height >= 0)) problems.push("宽高要是不小于 0 的数");
    if (b && Number.isFinite(rect.x) && Number.isFinite(rect.y) && !inside(b, rect)) {
      problems.push(`站位要整个落在本层边界内（x ${b.x}–${b.x + b.width - (rect.width || 0)}，y ${b.y}–${b.y + b.height - (rect.height || 0)}）`);
    }
    if (pending.action === "update") {
      const p = byName.get(pending.name);
      if (p && p.rect.x === rect.x && p.rect.y === rect.y && p.rect.width === rect.width && p.rect.height === rect.height) problems.push("坐标和原来一样");
    }
  }
  const request: TerrainRequest | null = pending?.action === "delete"
    ? { operation: "terrain_position", layer: layer.name, action: "delete", name: pending.name }
    : pending && rect ? {
    operation: "terrain_position", layer: layer.name, action: pending.action, name: pending.name,
    x: rect.x, y: rect.y,
    ...(Number.isFinite(rect.width) ? { width: rect.width } : {}), ...(Number.isFinite(rect.height) ? { height: rect.height } : {}),
  } : null;
  const op = useBossOp(questId, request, problems, onPreview, onWritten);

  const markers: Marker[] = layer.custom_positions.map((p) => (
    pending && pending.action === "delete" && pending.name === p.name
      ? { name: p.name, rect: p.rect, tone: "pending" as const, note: "（删除）" }
      : pending && pending.action === "update" && pending.name === p.name && rect && Number.isFinite(rect.x) && Number.isFinite(rect.y)
      ? { name: p.name, rect: rect as Rect, tone: "pending" as const, note: "（移动中）" }
      : { name: p.name, rect: p.rect, tone: "pos" as const }));
  if (pending?.action === "add" && rect && Number.isFinite(rect.x) && Number.isFinite(rect.y)) {
    markers.push({ name: pending.name || "新站位", rect: rect as Rect, tone: "pending", note: "（新增）" });
  }
  const set = (key: keyof Pending) => (e: Event) => pending && setPending({ ...pending, [key]: (e.target as HTMLInputElement).value });
  const sel = selected ? byName.get(selected) : undefined;

  return (
    <div class="terrain-edit">
      <div class="terrain-grid">
        <div>
          <TerrainCanvas layer={layer} markers={markers} bosses={bosses} referenced={referenced} selected={pending?.name ?? selected}
            onSelect={(name) => { setSelected(name); }} caption={`第 ${Number(layer.name) + 1} 波 · 拖动站位即可移动`}
            onDrag={(name, x, y) => {
              if (pending?.action === "add" && name === (pending.name || "新站位")) setPending({ ...pending, x: String(x), y: String(y) });
              else startUpdate(name, x, y);
            }} />
          <Legend />
        </div>
        <div class="terrain-side">
          <section class="param-block">
            <h4>命名站位（{layer.custom_positions.length}）</h4>
            <div class="table-scroll">
              <table class="boss-table">
                <thead><tr><th>名字（点一行开始移动）</th><th>坐标</th><th /></tr></thead>
                <tbody>
                  {layer.custom_positions.map((p) => (
                    <tr class={"clickable" + (p.name === selected ? " on" : "")} onClick={() => { setSelected(p.name); startUpdate(p.name); }}>
                      <td class="mono">{p.name}{bosses.some((x) => x.name === p.name) ? <span class="tag">boss</span> : null}
                        {referenced.has(p.name) ? <span class="tag" title="GeneralBoss 状态 c50 指向这里">行为引用</span> : null}</td>
                      <td class="mono small" title={`左上角（地形像素）${p.rect.x}, ${p.rect.y}，${p.rect.width}×${p.rect.height}
中心（运行时）${Math.round(p.runtime_point.x)}, ${Math.round(p.runtime_point.y)}`}>
                        <span class="nowrap">{p.rect.x}, {p.rect.y}</span><div class="muted nowrap">运行时 {Math.round(p.runtime_point.x)}, {Math.round(p.runtime_point.y)}</div></td>
                      <td class="nowrap"><button type="button" class="link danger" onClick={(e) => {
                        e.stopPropagation(); setSelected(p.name);
                        setPending({ action: "delete", name: p.name, x: String(p.rect.x), y: String(p.rect.y), width: String(p.rect.width), height: String(p.rect.height) });
                      }}>删除</button></td>

                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {!layer.custom_positions.length ? <p class="small muted">这一层没有命名站位。</p> : null}
            <p class="small muted">删除站位前后端会核对 routine / esdl / watch / Funnel 动作里的 CustomPosition 引用；有引用或引用证据不完整（「待验证」）都会拒绝。</p>
            <div class="row-inline">
              <input class="mono" placeholder="新站位名，如 p_extra" value={newName} aria-label="新站位名"
                onInput={(e) => setNewName((e.target as HTMLInputElement).value)} />
              <button type="button" disabled={!newName.trim() || !b} onClick={() => {
                const w = 16, h = 16;
                setPending({ action: "add", name: newName.trim(), width: String(w), height: String(h),
                  x: String(Math.round(b!.x + b!.width / 2 - w / 2)), y: String(Math.round(b!.y + b!.height / 2 - h / 2)) });
              }}>新增站位</button>
            </div>
            <p class="small muted">新增的站位先放在边界中心，可拖到目标处或直接填坐标。</p>
          </section>
          {pending?.action === "delete" ? (
            <section class="param-block pending-block">
              <h4>删除站位 <span class="mono">{pending.name}</span></h4>
              {referenced.has(pending.name) || bosses.some((x) => x.name === pending.name) ? (
                <Notice kind="warn">这个站位是 boss 初始位置或被状态 c50 引用，预检会拒绝删除。</Notice>
              ) : <p class="small muted">预检会再扫一遍动作闭包里的 CustomPosition；任何引用或证据缺失都会拒绝。</p>}
              <OpActions op={op} problems={problems} writeLabel="写入删除" onReset={() => setPending(null)} />
            </section>
          ) : pending ? (
            <section class="param-block pending-block">
              <h4>{pending.action === "add" ? "新增站位" : "移动站位"} <span class="mono">{pending.name || "（未命名）"}</span></h4>
              <div class="param-fields compact">
                {pending.action === "add" ? (
                  <label class="param-field"><span>名字</span><input class="mono" value={pending.name} onInput={set("name")} /></label>
                ) : null}
                <label class="param-field"><span>x（左上角）</span><input type="number" step={1} value={pending.x} onInput={set("x")} /></label>
                <label class="param-field"><span>y（左上角）</span><input type="number" step={1} value={pending.y} onInput={set("y")} /></label>
                <label class="param-field"><span>宽</span><input type="number" min={0} step={1} value={pending.width} onInput={set("width")} /></label>
                <label class="param-field"><span>高</span><input type="number" min={0} step={1} value={pending.height} onInput={set("height")} /></label>
              </div>
              {rect && Number.isFinite(rect.x) && Number.isFinite(rect.y) ? (
                <p class="small muted">运行时中心：{Math.round(K * (rect.x + (rect.width || 0) / 2))}, {Math.round(K * (rect.y + (rect.height || 0) / 2))}
                  {sel && pending.action === "update" ? `（原 ${Math.round(sel.runtime_point.x)}, ${Math.round(sel.runtime_point.y)}）` : ""}</p>
              ) : null}
              <InlineChecks items={[
                ["坐标已填写", !!rect && Number.isFinite(rect.x) && Number.isFinite(rect.y)],
                ["整个落在本层边界内", !!rect && !!b && Number.isFinite(rect.x) && inside(b, rect)],
                ["名字合法且不重名", NAME.test(pending.name) && (pending.action !== "add" || !byName.has(pending.name))],
              ]} />
              {referenced.has(pending.name) || bosses.some((x) => x.name === pending.name) ? (
                <Notice kind="warn">这个站位是 boss 初始位置或被行为引用：移动会改变 boss 出现或移动到的地方。</Notice>
              ) : null}
              <OpActions op={op} problems={problems} onReset={() => setPending(null)} />
            </section>
          ) : <p class="small muted">点表格里的一行或在画布上拖动一个站位开始编辑；每次写入一个站位的改动。</p>}
        </div>
      </div>
    </div>
  );
}

function InlineChecks({ items }: { items: [string, boolean][] }) {
  return (
    <ul class="inline-checks small">
      {items.map(([text, good]) => <li class={good ? "state-ok" : "error-text"}>{good ? "✓" : "✗"} {text}</li>)}
    </ul>
  );
}

// ---------------------------------------------------------------------------------- replace

function ReplaceEditor({ doc, questId, current, layerIndex, options, behavior, onPreview, onWritten }: {
  doc: BossDoc; questId: string; current: TerrainDoc; layerIndex: number; options: BossOptions | null;
  behavior: BehaviorDoc | null; onPreview: (s: PreviewState) => void; onWritten: () => void;
}) {
  const [filter, setFilter] = useState("");
  const [path, setPath] = useState<string | null>(null);
  const [candidate, setCandidate] = useState<TerrainDoc | null>(null);
  const [error, setError] = useState<string | null>(null);
  const currentPath = current.logical.replace(/\.amf3\.deflate$/, "");
  useEffect(() => {
    setCandidate(null); setError(null);
    if (path) boss.terrainPreview(path).then(setCandidate, (e: Error) => setError(e.message));
  }, [path]);
  const choices = useMemo(() => {
    const q = filter.trim().toLowerCase();
    return (options?.terrains ?? []).filter((t) => t.path !== currentPath
      && (!q || t.path.toLowerCase().includes(q) || t.fieldData.some((f) => f.toLowerCase().includes(q)))).slice(0, 60);
  }, [options, filter, currentPath]);
  const names = (d: TerrainDoc) => d.waves.map((w) => w.name).sort().join(",");
  const sameLayers = !!candidate && names(candidate) === names(current);
  const problems: string[] = [];
  if (candidate && !sameLayers) problems.push(`新地形有 ${candidate.wave_count} 层（${candidate.waves.map((w) => w.name).join("、")}），当前 ${current.wave_count} 层：层要一致；要多一波请用「追加一波」`);
  const request: TerrainRequest | null = path && candidate ? { operation: "terrain_replace", terrain: path } : null;
  const op = useBossOp(questId, request, problems, onPreview, onWritten);
  const layer = current.waves[layerIndex];
  const target = candidate?.waves.find((w) => w.name === layer?.name);
  // Positions follow the BOUNDS origin offset (they keep their meaning in this encounter).
  const moved = (rect: Rect): Rect => {
    const a = boundsOf(layer), c = boundsOf(target);
    return a && c ? { ...rect, x: rect.x - a.x + c.x, y: rect.y - a.y + c.y } : rect;
  };
  const kept: Marker[] = target ? [
    ...target.custom_positions.filter((p) => !layer?.custom_positions.some((o) => o.name === p.name))
      .map((p) => ({ name: p.name, rect: p.rect, tone: "ghost" as const, note: "（新图原有）" })),
    ...(layer?.custom_positions ?? []).map((p) => ({ name: p.name, rect: moved(p.rect), tone: "pending" as const, note: "（保留）" })),
  ] : [];
  const out = kept.filter((m) => m.tone === "pending" && target && !inside(boundsOf(target)!, m.rect));
  return (
    <div class="terrain-edit">
      <div class="terrain-grid stacked">
        <div class="terrain-pair">
          {layer ? <TerrainCanvas layer={layer} bosses={bossPositions(doc, behavior, layer.name)} caption="当前" view={PAIR} /> : null}
          {target ? <TerrainCanvas layer={target} markers={kept} caption="换后（预览）" view={PAIR} /> : (
            <div class="terrain-empty small muted">{error ? <span class="error-text">{error}</span> : path ? "正在解码候选地形……" : "从右侧选一个已有地形"}</div>
          )}
        </div>
        <div class="terrain-side">
          <section class="param-block">
            <h4>选一个已有地形</h4>
            <input class="mono" placeholder="按路径或 field_data 搜索" value={filter} onInput={(e) => setFilter((e.target as HTMLInputElement).value)} />
            <ul class="pick-list">
              {choices.map((t) => (
                <li><button type="button" class={"source-option" + (t.path === path ? " on" : "")} onClick={() => setPath(t.path)} title={t.path}>
                  <span class="side-label mono small">{t.path.replace(/^battle\/terrain\//, "")}</span>
                  <span class="small muted">{t.fieldData.join("、")}{t.uses > t.fieldData.length ? ` 等 ${t.uses} 处` : ""}</span>
                </button></li>
              ))}
            </ul>
            {!options ? <p class="small muted">正在读取地形清单……</p> : !choices.length ? <p class="small muted">没有匹配的地形。</p> : null}
          </section>
          {candidate ? (
            <section class="param-block pending-block">
              <h4>换成 <span class="mono small">{path}</span></h4>
              <InlineChecks items={[
                [`层数和层名一致（${current.wave_count} 层）`, sameLayers],
                ["每层 9 个复活位", candidate.waves.every((w) => w.coffin_count >= 9)],
                ["保留的站位都在新边界内", sameLayers && !out.length],
              ]} />
              <p class="small muted">原来的命名站位按边界原点平移保留（不会因为新图也有 p1 就改用新图的 p1）。{out.length ? `越界：${out.map((m) => m.name).join("、")}。` : ""}</p>
              <OpActions op={op} problems={problems} onReset={() => setPath(null)} />
            </section>
          ) : null}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------------- add wave

function WaveEditor({ doc, questId, current, list, onPreview, onWritten }: {
  doc: BossDoc; questId: string; current: TerrainDoc; list: BossList | null;
  onPreview: (s: PreviewState) => void; onWritten: () => void;
}) {
  const element = doc.quest.fields.recommended_element;
  const sources = useMemo(() => (list?.items ?? []).filter((i) => !i.bothBoss && i.recommendedElement === element), [list, element]);
  const [source, setSource] = useState(doc.quest.selector);
  const [sourceLayer, setSourceLayer] = useState("0");
  const [transition, setTransition] = useState("");
  const [filter, setFilter] = useState("");
  const [sourceTerrain, setSourceTerrain] = useState<TerrainDoc | null>(null);
  const [transitionInfo, setTransitionInfo] = useState<{ exits: boolean; c7: string; c8: string } | null>(null);
  useEffect(() => {
    setSourceTerrain(null);
    boss.section<TerrainDoc>(source, "terrain").then((r) => {
      setSourceTerrain(r.data);
      if (!r.data.waves.some((w) => w.name === sourceLayer)) setSourceLayer(r.data.waves[0]?.name ?? "0");
    }, () => setSourceTerrain(null));
  }, [source]);
  const donor = transition || source;
  useEffect(() => {
    setTransitionInfo(null);
    Promise.all([boss.read(donor), boss.section<TerrainDoc>(donor, "terrain")]).then(([read, terrain]) => setTransitionInfo({
      exits: terrain.data.waves.some((w) => w.objects.some((o) => o.type === "GATE") && w.objects.some((o) => o.type === "TRANSIT")),
      c7: cellOf(read.boss.field.row, 7), c8: cellOf(read.boss.field.row, 8),
    }), () => setTransitionInfo(null));
  }, [donor]);
  const last = current.waves[current.waves.length - 1];
  const needsExit = !!last && !(last.objects.some((o) => o.type === "GATE") && last.objects.some((o) => o.type === "TRANSIT"));
  const present = (v: string) => !!v && v !== "(None)";
  const fieldRow = doc.field.row ?? [];
  const needsField = !present(cellOf(fieldRow, 7)) || !present(cellOf(fieldRow, 8));
  const problems: string[] = [];
  if (sourceTerrain && !sourceTerrain.waves.some((w) => w.name === sourceLayer)) problems.push("来源没有这一层");
  const request: TerrainRequest | null = sourceTerrain ? {
    operation: "terrain_add_layer", sourceQuest: source, sourceLayer, ...(transition ? { transitionSourceQuest: transition } : {}),
  } : null;
  const op = useBossOp(questId, request, problems, onPreview, onWritten);
  const fieldChange = op.fresh ? op.preview?.changes?.find((c) => c.table === "master/battle/field.orderedmap") : undefined;
  const newField = typeof fieldChange?.new === "string" ? csvRow(fieldChange.new) : null;
  const shown = sources.filter((s) => !filter.trim() || (s.name + s.selector).toLowerCase().includes(filter.trim().toLowerCase())).slice(0, 80);
  const incoming = sourceTerrain?.waves.find((w) => w.name === sourceLayer);
  return (
    <div class="terrain-edit">
      <div class="terrain-grid stacked">
        <div class="terrain-pair">
          {last ? <TerrainCanvas layer={last} caption={`当前最后一波（第 ${current.waves.length} 波）`} view={PAIR} /> : null}
          {incoming ? <TerrainCanvas layer={incoming} caption={`新第 ${current.waves.length + 1} 波（来自 ${shortName(sources.find((s) => s.selector === source)?.name ?? source)} 层 ${sourceLayer}）`} view={PAIR} />
            : <div class="terrain-empty small muted">正在读取来源地形……</div>}
        </div>
        <div class="terrain-side">
          <section class="param-block">
            <h4>复制哪一层（来源推荐属性须同为{questElement(element) ?? element}）</h4>
            <input placeholder="搜索来源副本" value={filter} onInput={(e) => setFilter((e.target as HTMLInputElement).value)} />
            <select value={source} aria-label="来源副本" size={6} onChange={(e) => setSource((e.target as HTMLSelectElement).value)}>
              {shown.map((s) => <option value={s.selector}>{shortName(s.name)} · {s.selector}</option>)}
            </select>
            <label class="param-field"><span>来源层</span>
              <select value={sourceLayer} onChange={(e) => setSourceLayer((e.target as HTMLSelectElement).value)}>
                {(sourceTerrain?.waves ?? []).map((w, i) => <option value={w.name}>第 {i + 1} 波（层 {w.name}）· 站位 {w.position_names.join("、") || "无"}</option>)}
              </select>
            </label>
            <label class="param-field"><span>转场出口来源（可选）</span>
              <select value={transition} onChange={(e) => setTransition((e.target as HTMLSelectElement).value)}>
                <option value="">与来源副本相同</option>
                {(list?.items ?? []).filter((i) => !i.bothBoss).map((s) => <option value={s.selector}>{shortName(s.name)} · {s.selector}</option>)}
              </select>
            </label>
            <p class="small muted">只借用出口（GATE / TRANSIT）和场景 c7/c8 转场动画，不带它的敌人。</p>
          </section>
          <section class="param-block pending-block">
            <h4>追加后自动补的内容</h4>
            <table class="boss-table">
              <thead><tr><th /><th>现在</th><th>追加后</th></tr></thead>
              <tbody>
                <tr><th>场景 c7（出口）</th><td class="mono small"><Tail v={cellOf(fieldRow, 7)} /></td>
                  <td class="mono small">{newField ? <Tail v={cellOf(newField, 7)} /> : needsField ? `将取自 ${donor}：${transitionInfo?.c7 || "…"}` : "保持"}</td></tr>
                <tr><th>场景 c8（转场）</th><td class="mono small"><Tail v={cellOf(fieldRow, 8)} /></td>
                  <td class="mono small">{newField ? <Tail v={cellOf(newField, 8)} /> : needsField ? `将取自 ${donor}：${transitionInfo?.c8 || "…"}` : "保持"}</td></tr>
                <tr><th>上一波出口</th><td>{needsExit ? "无" : "已有"}</td><td>{needsExit ? `从 ${donor} 复制 GATE / TRANSIT` : "保持"}</td></tr>
              </tbody>
            </table>
            <InlineChecks items={[
              ["来源推荐属性与本关一致", sources.some((s) => s.selector === source)],
              ["转场来源有出口对象", !needsExit || !!transitionInfo?.exits],
              ["转场来源场景有 c7 / c8", !needsField || (!!transitionInfo && present(transitionInfo.c7) && present(transitionInfo.c8))],
              ["来源层有 9 个复活位", (incoming?.coffin_count ?? 0) >= 9],
            ]} />
            {newField ? <p class="small state-ok">上表「追加后」取自预检结果（不是推测）。</p> : null}
            <OpActions op={op} problems={problems} onReset={() => { setSource(doc.quest.selector); setTransition(""); }} />
          </section>
        </div>
      </div>
    </div>
  );
}

/** Long logical path → its last segment (full path in the tooltip). */
function Tail({ v }: { v: string }) {
  if (!v) return <>—</>;
  return <span title={v}>{v.split("/").pop()}</span>;
}
