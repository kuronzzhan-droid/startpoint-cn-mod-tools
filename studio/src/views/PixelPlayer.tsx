import { useEffect, useMemo, useRef, useState } from "preact/hooks";
import { api, PixelAction, PixelFamily, PixelMeta } from "../api";
import { Notice } from "./common";

type Background = "checker" | "dark" | "light";
const SPEEDS = [0.25, 0.5, 1, 2];
const ZOOMS = [1, 2, 3, 4, 6, 8];

function cellIndexAt(action: PixelAction, tick: number): number {
  const t = Math.floor(tick);
  for (let i = 0; i < action.cells.length; i++) {
    const c = action.cells[i];
    if (t >= c.start && t < c.start + c.frames) return i;
  }
  return action.cells.length - 1;
}

function loadImage(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error("图集加载失败：" + url));
    image.src = url;
  });
}

export function PixelPlayer({ characterId }: { characterId: string }) {
  const [meta, setMeta] = useState<PixelMeta | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [images, setImages] = useState<Record<string, HTMLImageElement>>({});
  const [selection, setSelection] = useState<{ family: string; action: string }>({ family: "pixelart", action: "neutral" });
  const [playing, setPlaying] = useState(true);
  const [tick, setTick] = useState(0);
  const [speed, setSpeed] = useState(1);
  const [loopOverride, setLoopOverride] = useState<boolean | null>(null);
  const [onion, setOnion] = useState(false);
  const [zoom, setZoom] = useState(4);
  const [showAnchor, setShowAnchor] = useState(true);
  const [background, setBackground] = useState<Background>("checker");
  const canvas = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    setMeta(null);
    setError(null);
    api.pixels(characterId).then(async (data) => {
      setMeta(data);
      const loaded: Record<string, HTMLImageElement> = {};
      for (const family of data.families) {
        if (family.error) continue;
        loaded[family.family] = await loadImage(api.pixelSheetUrl(characterId, family.family));
      }
      setImages(loaded);
      const first = data.families.find((f) => !f.error && f.actions.length);
      if (first) setSelection({ family: first.family, action: first.actions[0].name });
    }).catch((e: Error) => setError(e.message));
  }, [characterId]);

  const family: PixelFamily | undefined = meta?.families.find((f) => f.family === selection.family);
  const action: PixelAction | undefined = family?.actions.find((a) => a.name === selection.action);
  const loop = loopOverride ?? action?.kind === "loop";

  // Playback clock: 60 timeline frames per second times the speed factor.
  useEffect(() => {
    if (!playing || !action || !family) return;
    let last = performance.now();
    let handle = 0;
    const step = (now: number) => {
      const delta = ((now - last) / 1000) * family.fps * speed;
      last = now;
      setTick((current) => {
        let next = current + delta;
        if (next >= action.totalFrames) {
          if (loop) next %= action.totalFrames;
          else {
            next = action.totalFrames - 1;
            setPlaying(false);
          }
        }
        return next;
      });
      handle = requestAnimationFrame(step);
    };
    handle = requestAnimationFrame(step);
    return () => cancelAnimationFrame(handle);
  }, [playing, action, family, speed, loop]);

  const cellIdx = action ? cellIndexAt(action, tick) : 0;

  // Draw.
  useEffect(() => {
    const el = canvas.current;
    const image = family ? images[family.family] : undefined;
    if (!el || !family || !action || !image) return;
    const pad = 8;
    const w = family.cellWidth * zoom + pad * 2;
    const h = family.cellHeight * zoom + pad * 2;
    if (el.width !== w || el.height !== h) {
      el.width = w;
      el.height = h;
    }
    const ctx = el.getContext("2d")!;
    ctx.imageSmoothingEnabled = false;
    // Background.
    if (background === "checker") {
      const size = 8;
      for (let y = 0; y < h; y += size)
        for (let x = 0; x < w; x += size) {
          ctx.fillStyle = ((x / size + y / size) & 1) === 0 ? "#e9ecf1" : "#f7f8fa";
          ctx.fillRect(x, y, size, size);
        }
    } else {
      ctx.fillStyle = background === "dark" ? "#1d222b" : "#ffffff";
      ctx.fillRect(0, 0, w, h);
    }
    const drawCell = (cell: number, alpha: number) => {
      const sx = (cell % family.columns) * family.cellWidth;
      const sy = Math.floor(cell / family.columns) * family.cellHeight;
      ctx.globalAlpha = alpha;
      ctx.drawImage(image, sx, sy, family.cellWidth, family.cellHeight, pad, pad,
        family.cellWidth * zoom, family.cellHeight * zoom);
      ctx.globalAlpha = 1;
    };
    if (onion) {
      const prev = action.cells[cellIdx - 1] ?? (loop ? action.cells[action.cells.length - 1] : undefined);
      const next = action.cells[cellIdx + 1] ?? (loop ? action.cells[0] : undefined);
      if (prev && action.cells.length > 1) drawCell(prev.cell, 0.3);
      if (next && action.cells.length > 2) drawCell(next.cell, 0.15);
    }
    drawCell(action.cells[cellIdx].cell, 1);
    if (showAnchor) {
      const ax = pad + family.anchor.x * zoom;
      const ay = pad + family.anchor.y * zoom;
      ctx.strokeStyle = "rgba(230, 60, 90, 0.9)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(ax - 10, ay + 0.5);
      ctx.lineTo(ax + 10, ay + 0.5);
      ctx.moveTo(ax + 0.5, ay - 10);
      ctx.lineTo(ax + 0.5, ay + 10);
      ctx.stroke();
    }
  }, [family, action, images, cellIdx, zoom, onion, showAnchor, background, loop]);

  const actions = useMemo(
    () => (meta?.families ?? []).flatMap((f) => (f.error ? [] : f.actions.map((a) => ({ f, a })))),
    [meta],
  );

  if (error) return <Notice kind="error">像素资源读取失败：{error}</Notice>;
  if (!meta) return <div class="loading">正在解码像素图集……</div>;
  if (!actions.length) return <Notice kind="warn">这个角色没有可预览的像素动作。</Notice>;

  const select = (f: PixelFamily, a: PixelAction) => {
    setSelection({ family: f.family, action: a.name });
    setTick(0);
    setLoopOverride(null);
    setPlaying(true);
  };
  const stepCell = (direction: number) => {
    if (!action) return;
    setPlaying(false);
    const count = action.cells.length;
    const next = (cellIdx + direction + count) % count;
    setTick(action.cells[next].start);
  };
  const current = action?.cells[cellIdx];

  return (
    <div class="pixel">
      <p class="hint">{meta.note}</p>
      <div class="pixel-layout">
        <aside class="pixel-actions">
          {meta.families.map((f) => (
            <div class="family">
              <h4>{f.label}</h4>
              {f.error ? <p class="error-text small">{f.error}</p> : null}
              {f.actions.map((a) => (
                <button class={"action-btn" + (selection.family === f.family && selection.action === a.name ? " on" : "")}
                  onClick={() => select(f, a)}>
                  <span>{a.label}</span>
                  <span class="muted small mono">{a.name}</span>
                  <span class="muted small">{a.totalFrames} 帧 · {a.kindLabel}</span>
                </button>
              ))}
            </div>
          ))}
          <details class="slots">
            <summary>18 个官方动作槽</summary>
            <ul>
              {meta.slots.map((s) => (
                <li class={s.present ? "present" : "absent"}>
                  {s.present ? "●" : "○"} {s.label} <span class="mono small muted">{s.name}</span>
                </li>
              ))}
            </ul>
            <p class="muted small">受击、攻击、死亡等 7 个槽只出现在由 boss 改造的角色上。</p>
          </details>
        </aside>
        <div class="pixel-stage">
          <div class="stage-head">
            <strong>{action?.label}</strong>
            <span class="mono muted">{action?.name}</span>
            <span class="muted">{family?.label} · 原生显示倍率 ×{family?.scale}</span>
          </div>
          <div class="canvas-wrap">
            <canvas ref={canvas} class="pixel-canvas" data-tick={Math.floor(tick)} data-cell={current?.cell} />
          </div>
          <div class="transport">
            <button onClick={() => stepCell(-1)} title="上一帧">⏮</button>
            <button class="primary" onClick={() => {
              if (!playing && action && tick >= action.totalFrames - 1) setTick(0);
              setPlaying(!playing);
            }}>{playing ? "暂停" : "播放"}</button>
            <button onClick={() => stepCell(1)} title="下一帧">⏭</button>
            <input type="range" min={0} max={Math.max(0, (action?.totalFrames ?? 1) - 1)} step={1}
              value={Math.floor(tick)} aria-label="时间轴"
              onInput={(e) => { setPlaying(false); setTick(Number((e.target as HTMLInputElement).value)); }} />
            <span class="mono small">
              {Math.floor(tick) + 1}/{action?.totalFrames} 帧 · 图 {cellIdx + 1}/{action?.cells.length}
              {current ? ` · 停留 ${current.frames} 帧` : ""}
            </span>
          </div>
          <div class="options">
            <label>速度
              <select value={speed} onChange={(e) => setSpeed(Number((e.target as HTMLSelectElement).value))}>
                {SPEEDS.map((s) => <option value={s}>{s}×</option>)}
              </select>
            </label>
            <label>缩放
              <select value={zoom} onChange={(e) => setZoom(Number((e.target as HTMLSelectElement).value))}>
                {ZOOMS.map((z) => <option value={z}>{z}×</option>)}
              </select>
            </label>
            <label class="check"><input type="checkbox" checked={loop}
              onChange={(e) => setLoopOverride((e.target as HTMLInputElement).checked)} />循环</label>
            <label class="check"><input type="checkbox" checked={onion}
              onChange={(e) => setOnion((e.target as HTMLInputElement).checked)} />洋葱皮</label>
            <label class="check"><input type="checkbox" checked={showAnchor}
              onChange={(e) => setShowAnchor((e.target as HTMLInputElement).checked)} />显示锚点</label>
            <label>背景
              <select value={background} onChange={(e) => setBackground((e.target as HTMLSelectElement).value as Background)}>
                <option value="checker">棋盘格</option>
                <option value="dark">深色</option>
                <option value="light">白色</option>
              </select>
            </label>
          </div>
          {action && family && images[family.family] ? (
            <div class="filmstrip" aria-label="帧条">
              {action.cells.map((c, i) => (
                <button class={"film" + (i === cellIdx ? " on" : "")} title={`图 ${i + 1} · 停留 ${c.frames} 帧`}
                  onClick={() => { setPlaying(false); setTick(c.start); }}>
                  <span class="film-img" style={{
                    width: family.cellWidth + "px", height: family.cellHeight + "px",
                    backgroundImage: `url(${api.pixelSheetUrl(characterId, family.family)})`,
                    backgroundPosition: `-${(c.cell % family.columns) * family.cellWidth}px -${Math.floor(c.cell / family.columns) * family.cellHeight}px`,
                  }} />
                  <span class="small mono">{c.frames}</span>
                </button>
              ))}
            </div>
          ) : null}
          <p class="muted small">
            锚点 = 角色在战场上的定位原点：帧框左上角相对原点偏移 frame.x/y，所以原点在帧框内的 (−x, −y)。
            单元格 {family?.cellWidth}×{family?.cellHeight}，锚点 ({family?.anchor.x}, {family?.anchor.y})。
          </p>
        </div>
      </div>
    </div>
  );
}
