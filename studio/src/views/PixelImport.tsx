import { useEffect, useMemo, useRef, useState } from "preact/hooks";
import { api, DraftChange, DraftCheck, drafts, PixelAction, PixelBudget, PixelFamily, PixelMeta } from "../api";
import { ChecksList } from "./Changes";
import { Notice } from "./common";

type Frame = { url: string; img: HTMLImageElement; width: number; height: number; duration: number; anchor: [number, number] };

function loadImage(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error("图片加载失败"));
    image.src = url;
  });
}

function readAsDataUrl(file: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error ?? new Error("读取失败"));
    reader.readAsDataURL(file);
  });
}

/** Visible bottom of a frame (alpha > 0), or its height when empty. */
function visibleBottom(img: HTMLImageElement): number {
  const canvas = document.createElement("canvas");
  canvas.width = img.naturalWidth;
  canvas.height = img.naturalHeight;
  const ctx = canvas.getContext("2d")!;
  ctx.drawImage(img, 0, 0);
  const data = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
  for (let y = canvas.height - 1; y >= 0; y--)
    for (let x = 0; x < canvas.width; x++) if (data[(y * canvas.width + x) * 4 + 3] > 0) return y + 1;
  return canvas.height;
}

function spread(total: number, count: number): number[] {
  const base = Math.max(1, Math.floor(total / count));
  const out = Array(count).fill(base);
  let rest = total - base * count;
  for (let i = count - 1; rest > 0 && i >= 0; i--, rest--) out[i] += 1;
  return out;
}

function cellAt(action: PixelAction, tick: number): number {
  const t = Math.floor(tick) % action.totalFrames;
  for (const c of action.cells) if (t >= c.start && t < c.start + c.frames) return c.cell;
  return action.cells[action.cells.length - 1].cell;
}

function frameAt(frames: Frame[], tick: number): number {
  const total = frames.reduce((n, f) => n + f.duration, 0);
  let t = Math.floor(tick) % Math.max(1, total);
  for (let i = 0; i < frames.length; i++) {
    if (t < frames[i].duration) return i;
    t -= frames[i].duration;
  }
  return frames.length - 1;
}

export function PixelImport({ characterId }: { characterId: string }) {
  const [meta, setMeta] = useState<PixelMeta | null>(null);
  const [sheets, setSheets] = useState<Record<string, HTMLImageElement>>({});
  const [error, setError] = useState<string | null>(null);
  const [familyName, setFamilyName] = useState("pixelart");
  const [actionName, setActionName] = useState("skill_ready");
  const [frames, setFrames] = useState<Frame[]>([]);
  const [grid, setGrid] = useState({ columns: 4, rows: 1, count: 0 });
  const [sheetFile, setSheetFile] = useState<HTMLImageElement | null>(null);
  const [selected, setSelected] = useState(0);
  const [tick, setTick] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [zoom, setZoom] = useState(3);
  const [check, setCheck] = useState<{ checks: DraftCheck[]; budget: PixelBudget; originalTotalFrames: number | null; frameBox: [number, number] } | null>(null);
  const [saved, setSaved] = useState<DraftChange | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<{ kind: "info" | "error"; text: string } | null>(null);
  const left = useRef<HTMLCanvasElement>(null);
  const right = useRef<HTMLCanvasElement>(null);
  const editor = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    api.pixels(characterId).then(async (data) => {
      setMeta(data);
      const loaded: Record<string, HTMLImageElement> = {};
      for (const f of data.families) if (!f.error) loaded[f.family] = await loadImage(api.pixelSheetUrl(characterId, f.family));
      setSheets(loaded);
    }, (e: Error) => setError(e.message));
  }, [characterId]);

  const family: PixelFamily | undefined = meta?.families.find((f) => f.family === familyName && !f.error);
  const action: PixelAction | undefined = family?.actions.find((a) => a.name === actionName);

  // Shared clock (60 timeline frames per second).
  useEffect(() => {
    if (!playing) return;
    let last = performance.now();
    let handle = 0;
    const step = (now: number) => {
      setTick((t) => t + ((now - last) / 1000) * 60);
      last = now;
      handle = requestAnimationFrame(step);
    };
    handle = requestAnimationFrame(step);
    return () => cancelAnimationFrame(handle);
  }, [playing]);

  const stage = { w: 96, h: 110 };
  const origin = { x: stage.w / 2, y: stage.h * 0.82 };

  const paintStage = (canvas: HTMLCanvasElement | null, draw: (ctx: CanvasRenderingContext2D) => void) => {
    if (!canvas) return;
    const w = stage.w * zoom;
    const h = stage.h * zoom;
    if (canvas.width !== w) canvas.width = w;
    if (canvas.height !== h) canvas.height = h;
    const ctx = canvas.getContext("2d")!;
    ctx.imageSmoothingEnabled = false;
    for (let y = 0; y < h; y += 8 * zoom)
      for (let x = 0; x < w; x += 8 * zoom) {
        ctx.fillStyle = ((x + y) / (8 * zoom)) % 2 === 0 ? "#e9ecf1" : "#f7f8fa";
        ctx.fillRect(x, y, 8 * zoom, 8 * zoom);
      }
    draw(ctx);
    ctx.strokeStyle = "rgba(230,60,90,0.85)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, origin.y * zoom + 0.5);
    ctx.lineTo(w, origin.y * zoom + 0.5);
    ctx.moveTo(origin.x * zoom + 0.5, origin.y * zoom - 12);
    ctx.lineTo(origin.x * zoom + 0.5, origin.y * zoom + 12);
    ctx.stroke();
  };

  useEffect(() => {
    paintStage(left.current, (ctx) => {
      const image = family && sheets[family.family];
      if (!family || !action || !image) return;
      const cell = cellAt(action, tick);
      const sx = (cell % family.columns) * family.cellWidth;
      const sy = Math.floor(cell / family.columns) * family.cellHeight;
      ctx.drawImage(image, sx, sy, family.cellWidth, family.cellHeight,
        (origin.x - family.anchor.x) * zoom, (origin.y - family.anchor.y) * zoom, family.cellWidth * zoom, family.cellHeight * zoom);
    });
    paintStage(right.current, (ctx) => {
      if (!frames.length) return;
      const f = frames[frameAt(frames, tick)];
      ctx.drawImage(f.img, (origin.x - f.anchor[0]) * zoom, (origin.y - f.anchor[1]) * zoom, f.width * zoom, f.height * zoom);
    });
  }, [tick, family, action, sheets, frames, zoom]);

  // Anchor editor for the selected frame.
  useEffect(() => {
    const canvas = editor.current;
    const f = frames[selected];
    if (!canvas || !f) return;
    const z = Math.max(2, Math.min(6, Math.floor(260 / Math.max(f.width, f.height))));
    canvas.width = f.width * z;
    canvas.height = f.height * z;
    canvas.dataset.zoom = String(z);
    const ctx = canvas.getContext("2d")!;
    ctx.imageSmoothingEnabled = false;
    ctx.fillStyle = "#2a2f3a";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(f.img, 0, 0, canvas.width, canvas.height);
    ctx.strokeStyle = "#ff2d55";
    ctx.beginPath();
    ctx.moveTo(f.anchor[0] * z - 10, f.anchor[1] * z + 0.5);
    ctx.lineTo(f.anchor[0] * z + 10, f.anchor[1] * z + 0.5);
    ctx.moveTo(f.anchor[0] * z + 0.5, f.anchor[1] * z - 10);
    ctx.lineTo(f.anchor[0] * z + 0.5, f.anchor[1] * z + 10);
    ctx.stroke();
  }, [frames, selected]);

  const total = useMemo(() => frames.reduce((n, f) => n + f.duration, 0), [frames]);

  if (error) return <Notice kind="error">像素资源读取失败：{error}</Notice>;
  if (!meta) return <div class="loading">正在解码原像素图集……</div>;

  const adopt = async (images: HTMLImageElement[], urls: string[]) => {
    const durations = spread(action?.totalFrames ?? images.length * 6, images.length);
    const bottoms = images.map(visibleBottom).sort((a, b) => a - b);
    const bottom = bottoms[Math.floor(bottoms.length / 2)];
    setFrames(images.map((img, i) => ({ url: urls[i], img, width: img.naturalWidth, height: img.naturalHeight,
      duration: durations[i], anchor: [Math.floor(img.naturalWidth / 2), bottom] as [number, number] })));
    setSelected(0);
    setTick(0);
    setCheck(null);
    setSaved(null);
  };
  const importFrames = async (files: FileList | null) => {
    if (!files?.length) return;
    const sorted = [...files].sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true }));
    const urls = await Promise.all(sorted.map(readAsDataUrl));
    adopt(await Promise.all(urls.map(loadImage)), urls);
    setMessage({ kind: "info", text: `导入 ${sorted.length} 帧（按文件名排序）。` });
  };
  const splitSheet = async () => {
    if (!sheetFile) return;
    const { columns, rows, count } = grid;
    if (sheetFile.naturalWidth % columns || sheetFile.naturalHeight % rows) {
      setMessage({ kind: "error", text: `精灵图 ${sheetFile.naturalWidth}×${sheetFile.naturalHeight} 不能被 ${columns}×${rows} 整除` });
      return;
    }
    const cw = sheetFile.naturalWidth / columns;
    const ch = sheetFile.naturalHeight / rows;
    const urls: string[] = [];
    for (let r = 0; r < rows; r++)
      for (let c = 0; c < columns; c++) {
        const canvas = document.createElement("canvas");
        canvas.width = cw;
        canvas.height = ch;
        const ctx = canvas.getContext("2d")!;
        ctx.drawImage(sheetFile, c * cw, r * ch, cw, ch, 0, 0, cw, ch);
        const data = ctx.getImageData(0, 0, cw, ch).data;
        let any = false;
        for (let i = 3; i < data.length; i += 4) if (data[i]) { any = true; break; }
        if (count ? urls.length < count : any) urls.push(canvas.toDataURL("image/png"));
      }
    adopt(await Promise.all(urls.map(loadImage)), urls);
    setMessage({ kind: "info", text: `精灵图按 ${columns}×${rows} 切出 ${urls.length} 帧${count ? "" : "（跳过全透明格）"}。` });
  };
  const request = () => ({
    family: familyName, action: actionName,
    frames: frames.map((f) => ({ png: f.url.replace(/^data:[^,]*,/, ""), duration: f.duration, anchor: f.anchor })),
    origin: { mode: sheetFile ? "sheet" : "frames", columns: grid.columns, rows: grid.rows },
  });
  const runCheck = async () => {
    setBusy("check"); setMessage(null);
    try { setCheck(await drafts.checkPixel(characterId, request())); }
    catch (e) { setMessage({ kind: "error", text: (e as Error).message }); }
    finally { setBusy(null); }
  };
  const save = async () => {
    setBusy("save"); setMessage(null);
    try {
      const result = await drafts.savePixel(characterId, request());
      setSaved(result.change!);
      setCheck({ checks: result.change!.checks, budget: result.change!.params.budget,
        originalTotalFrames: result.change!.params.originalTotalFrames, frameBox: [256, 256] });
      setMessage({ kind: "info", text: `已写入草稿：${result.change!.title}（${result.status.label}）。` });
    } catch (e) { setMessage({ kind: "error", text: (e as Error).message }); }
    finally { setBusy(null); }
  };
  const update = (index: number, patch: Partial<Frame>) =>
    setFrames(frames.map((f, i) => (i === index ? { ...f, ...patch } : f)));

  return (
    <div class="pixel-import">
      <p class="hint">
        按动作槽导入新帧：逐帧 PNG 或精灵图网格切分；每帧可设停留帧数（60fps）和锚点（脚底中心）。草稿只存源帧和参数，
        重新装箱 sprite_sheet / 改写 atlas 与时间轴属于「生成」（待接入 wf deliver，M1 分支）。
      </p>
      <div class="toolbar">
        <label>像素族
          <select value={familyName} onChange={(e) => { setFamilyName((e.target as HTMLSelectElement).value); setCheck(null); }}>
            {meta.families.filter((f) => !f.error).map((f) => <option value={f.family}>{f.label}（{f.family}）</option>)}
          </select>
        </label>
        <label>动作槽
          <select value={actionName} onChange={(e) => { setActionName((e.target as HTMLSelectElement).value); setCheck(null); setTick(0); }}>
            {family?.actions.map((a) => <option value={a.name}>{a.label} · {a.name} · {a.totalFrames} 帧</option>)}
          </select>
        </label>
        <label class="upload-btn">逐帧 PNG（多选）
          <input type="file" accept="image/png" multiple onChange={(e) => importFrames((e.target as HTMLInputElement).files)} />
        </label>
        <span class="grid-split">
          <label class="upload-btn">精灵图
            <input type="file" accept="image/png" onChange={async (e) => {
              const file = (e.target as HTMLInputElement).files?.[0];
              if (file) setSheetFile(await loadImage(await readAsDataUrl(file)));
            }} />
          </label>
          {sheetFile ? <span class="small muted">{sheetFile.naturalWidth}×{sheetFile.naturalHeight}</span> : null}
          <label>列<input type="number" min={1} value={grid.columns} onInput={(e) => setGrid({ ...grid, columns: Math.max(1, Number((e.target as HTMLInputElement).value)) })} /></label>
          <label>行<input type="number" min={1} value={grid.rows} onInput={(e) => setGrid({ ...grid, rows: Math.max(1, Number((e.target as HTMLInputElement).value)) })} /></label>
          <label title="0 = 自动跳过全透明格">取前<input type="number" min={0} value={grid.count} onInput={(e) => setGrid({ ...grid, count: Math.max(0, Number((e.target as HTMLInputElement).value)) })} />格</label>
          <button onClick={splitSheet} disabled={!sheetFile}>切分</button>
        </span>
      </div>
      {message ? <Notice kind={message.kind === "error" ? "error" : "info"}>{message.text}</Notice> : null}
      <div class="compare">
        <figure>
          <figcaption><strong>原版</strong> <span class="muted small">{action ? `${action.label} · ${action.totalFrames} 帧 · ${action.cells.length} 张图` : "（原图集没有这个动作）"}</span></figcaption>
          <canvas ref={left} class="pixel-canvas" data-side="original" />
        </figure>
        <figure>
          <figcaption><strong>新帧</strong> <span class="muted small">{frames.length ? `${frames.length} 张图 · 共 ${total} 帧` : "还没有导入"}</span>
            {frames.length && action && total !== action.totalFrames ? <span class="error-text small"> · 与原动作时长不同</span> : null}</figcaption>
          <canvas ref={right} class="pixel-canvas" data-side="new" />
        </figure>
      </div>
      <div class="transport">
        <button class="primary" onClick={() => setPlaying(!playing)}>{playing ? "暂停" : "播放"}</button>
        <button onClick={() => { setPlaying(false); setTick((t) => Math.floor(t) + 1); }}>下一帧</button>
        <span class="mono small">t = {Math.floor(tick) % Math.max(1, action?.totalFrames ?? 1)} / {Math.floor(tick) % Math.max(1, total || 1)}</span>
        <label>缩放
          <select value={zoom} onChange={(e) => setZoom(Number((e.target as HTMLSelectElement).value))}>
            {[2, 3, 4, 5].map((z) => <option value={z}>{z}×</option>)}
          </select>
        </label>
        <span class="small muted">两边按同一时钟播放，红线 = 锚点（战场定位原点）对齐。</span>
      </div>
      {frames.length ? (
        <div class="frame-editor">
          <div class="frame-list">
            {frames.map((f, i) => (
              <div class={"frame-item" + (i === selected ? " on" : "")} onClick={() => setSelected(i)}>
                <img src={f.url} alt="" style={{ width: Math.min(64, f.width * 2) + "px" }} />
                <span class="small mono">#{i + 1} {f.width}×{f.height}</span>
                <label class="small">停留<input type="number" min={1} max={600} value={f.duration}
                  onInput={(e) => update(i, { duration: Math.max(1, Number((e.target as HTMLInputElement).value)) })} />帧</label>
              </div>
            ))}
          </div>
          <div class="anchor-editor">
            <canvas ref={editor} class="pixel-canvas" title="点击设置锚点"
              onClick={(e) => {
                const canvas = e.currentTarget as HTMLCanvasElement;
                const z = Number(canvas.dataset.zoom || 1);
                const rect = canvas.getBoundingClientRect();
                const x = Math.round((e.clientX - rect.left) * (canvas.width / rect.width) / z);
                const y = Math.round((e.clientY - rect.top) * (canvas.height / rect.height) / z);
                update(selected, { anchor: [x, y] });
              }} />
            <div class="small">
              第 {selected + 1} 帧锚点 ({frames[selected]?.anchor.join(", ")})，点击图上任意位置设置。
              <div class="save-row">
                <button onClick={() => setFrames(frames.map((f) => ({ ...f, anchor: [...frames[selected].anchor] as [number, number] })))}>锚点套用到全部帧</button>
                <button onClick={() => { const d = spread(action?.totalFrames ?? total, frames.length); setFrames(frames.map((f, i) => ({ ...f, duration: d[i] }))); }}
                  disabled={!action}>按原时长平均分配</button>
              </div>
            </div>
          </div>
        </div>
      ) : null}
      <div class="save-row">
        <button onClick={runCheck} disabled={!frames.length || busy !== null}>{busy === "check" ? "检查中……" : "检查（不写草稿）"}</button>
        <button class="primary" onClick={save} disabled={!frames.length || busy !== null}>{busy === "save" ? "保存中……" : "保存到草稿"}</button>
      </div>
      {check ? (
        <section class="pixel-check">
          <h4>检查结果</h4>
          <ChecksList checks={check.checks} empty="没有问题提示。" />
          <table class="files">
            <thead><tr><th></th><th>sprite_sheet 尺寸</th><th>战斗 layer0 占用（4096²）</th></tr></thead>
            <tbody>
              <tr><td>当前</td><td>{check.budget.current.width}×{check.budget.current.height}</td><td>{check.budget.current.share}%</td></tr>
              <tr><td>替换后（估算）</td><td>{check.budget.estimate ? `${check.budget.estimate.width}×${check.budget.estimate.height}` : "装不下"}</td>
                <td>{check.budget.estimate ? `${check.budget.estimate.share}%` : "—"}{check.budget.loadedInBattle ? "" : "（special 族战斗不加载）"}</td></tr>
              <tr><td>官方参考</td><td>最大 247×738</td><td>角色中位 {check.budget.officialShareMedian}% · 最大 {check.budget.officialShareMax}%</td></tr>
            </tbody>
          </table>
          <p class="small muted">{check.budget.method}</p>
        </section>
      ) : null}
      {saved ? <p class="small muted">草稿改动 {saved.id}：{saved.params.frames.length} 帧已存为源帧 PNG，见「本次修改」。</p> : null}
    </div>
  );
}
