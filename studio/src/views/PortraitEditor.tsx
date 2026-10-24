import { useEffect, useMemo, useRef, useState } from "preact/hooks";
import { api, CropTemplate, DraftChange, drafts, fileToBase64, PortraitInfo } from "../api";
import { ChecksList } from "./Changes";
import { Notice } from "./common";

type SourceKind = "current" | "upload";
type Box = { id: string; label: string; color: string; x: number; y: number; w: number; h: number; ratio: number };
type Drag = { kind: "move" | "resize" | "face"; id: string; x0: number; y0: number; template: CropTemplate };

const COLORS: Record<string, string> = {
  square: "#ff6b6b", thumb_level_up: "#f59f00", battle_member_status: "#40c057",
  battle_control_board: "#15aabf", cutin_skill_chain: "#9775fa", thumb_party_main: "#f06595", skill_cutin: "#fcc419",
};
const SHORT: Record<string, string> = {
  square: "方形头像", thumb_level_up: "升级/合击卡", battle_member_status: "状态圆", battle_control_board: "技能准备条",
  cutin_skill_chain: "连锁六边形", thumb_party_main: "主位卡", skill_cutin: "技能 cutin",
};

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));
const round = (v: number, d = 1) => Math.round(v * 10 ** d) / 10 ** d;
const clone = (t: CropTemplate): CropTemplate => JSON.parse(JSON.stringify(t));

function computeBoxes(t: CropTemplate, info: PortraitInfo): Box[] {
  const boxes: Box[] = info.groups.map((g) => {
    const [sw, sh] = info.slotSizes[g.slots[0]];
    const spec = t.groups[g.name];
    const h = t.squareHeight * spec.factor;
    const w = (h * sw) / sh;
    return { id: g.name, label: SHORT[g.name] ?? g.name, color: COLORS[g.name] ?? "#888",
      x: t.face[0] - spec.anchor[0] * w, y: t.face[1] - spec.anchor[1] * h, w, h, ratio: sw / sh };
  });
  const c = t.cutin;
  const ch = c.height;
  const cw = ch * 2;
  boxes.push({ id: "skill_cutin", label: SHORT.skill_cutin, color: COLORS.skill_cutin,
    x: c.center[0] - c.anchor[0] * cw, y: c.center[1] - c.anchor[1] * ch, w: cw, h: ch, ratio: 2 });
  return boxes;
}

function loadImage(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error("图片加载失败"));
    image.src = url;
  });
}

const rgb = (c: number[]) => `rgb(${c[0]},${c[1]},${c[2]})`;
const hex = (c: number[]) => "#" + c.map((v) => v.toString(16).padStart(2, "0")).join("");
const fromHex = (h: string): [number, number, number] => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16)) as [number, number, number];

export function PortraitEditor({ characterId }: { characterId: string }) {
  const [form, setForm] = useState<"0" | "1">("0");
  const [info, setInfo] = useState<PortraitInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [source, setSource] = useState<SourceKind>("current");
  const [template, setTemplate] = useState<CropTemplate | null>(null);
  const [image, setImage] = useState<HTMLImageElement | null>(null);
  const [masks, setMasks] = useState<Record<string, HTMLImageElement>>({});
  const [maskState, setMaskState] = useState<"loading" | "ready" | "error">("loading");
  const [selected, setSelected] = useState("square");
  const [drag, setDrag] = useState<Drag | null>(null);
  const [atf, setAtf] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [result, setResult] = useState<DraftChange | null>(null);
  const [message, setMessage] = useState<{ kind: "info" | "error"; text: string } | null>(null);
  const [stamp, setStamp] = useState(0);
  const svg = useRef<SVGSVGElement>(null);
  const canvases = useRef<Record<string, HTMLCanvasElement | null>>({});

  // Load slot info and any draft template already saved for this form.
  useEffect(() => {
    setInfo(null); setTemplate(null); setImage(null); setResult(null); setMessage(null); setError(null);
    Promise.all([drafts.portraitInfo(characterId, form), drafts.get(characterId)]).then(([data, view]) => {
      setInfo(data);
      const saved = view.changeset?.changes.find((c) => c.kind === "portrait" && c.target.form === form);
      const kind: SourceKind = saved ? saved.params.source : data.upload ? "upload" : "current";
      setSource(kind);
      const base = kind === "upload" ? data.upload : data.current;
      setTemplate(saved ? clone(saved.params.template) : base ? clone(base.template) : null);
      if (saved) setResult(saved);
    }, (e: Error) => setError(e.message));
  }, [characterId, form]);

  // Masks: first request triggers the official statistics on the backend (cached afterwards).
  useEffect(() => {
    if (!info) return;
    setMaskState("loading");
    Promise.all(info.shapeSlots.map((slot) => loadImage(drafts.maskUrl(slot)).then((img) => [slot, img] as const)))
      .then((pairs) => { setMasks(Object.fromEntries(pairs)); setMaskState("ready"); }, () => setMaskState("error"));
  }, [info?.shapeSlots.join()]);

  const active = info ? (source === "upload" ? info.upload : info.current) : null;
  // character/<code> 目录，用来并排显示游戏里现在的图标。
  const gameDir = info?.current?.path ? info.current.path.split("/").slice(0, 2).join("/") : null;
  const imageUrl = !info || !active ? null
    : source === "upload" ? drafts.fileUrl(characterId, active.file!, String(stamp)) : api.assetUrl(active.path!);
  const offset = source === "current" && active?.trim ? active.trim : [0, 0, 0, 0];
  const fullSize = source === "current" && active?.originalSize ? active.originalSize : active?.size ?? [1, 1];

  useEffect(() => {
    setImage(null);
    if (imageUrl) loadImage(imageUrl).then(setImage, (e: Error) => setError(e.message));
  }, [imageUrl]);

  const boxes = useMemo(() => (template && info ? computeBoxes(template, info) : []), [template, info]);

  // Live previews of every derived crop.
  useEffect(() => {
    if (!info || !template || !image) return;
    const byGroup = Object.fromEntries(boxes.map((b) => [b.id, b]));
    const draw = (slot: string, box: Box, size: [number, number]) => {
      const canvas = canvases.current[slot];
      if (!canvas) return;
      canvas.width = size[0];
      canvas.height = size[1];
      const ctx = canvas.getContext("2d")!;
      ctx.clearRect(0, 0, size[0], size[1]);
      ctx.globalCompositeOperation = "source-over";
      if (template.backdrop && slot !== "skill_cutin") {
        const r = Math.hypot(Math.max(0.5, 0.5) * size[0], Math.max(0.42, 0.58) * size[1]);
        const gradient = ctx.createRadialGradient(size[0] * 0.5, size[1] * 0.42, 0, size[0] * 0.5, size[1] * 0.42, r);
        gradient.addColorStop(0, rgb(template.backdrop.inner));
        gradient.addColorStop(1, rgb(template.backdrop.outer));
        ctx.fillStyle = gradient;
        ctx.fillRect(0, 0, size[0], size[1]);
      }
      ctx.imageSmoothingQuality = "high";
      ctx.drawImage(image, box.x + offset[0], box.y + offset[1], box.w, box.h, 0, 0, size[0], size[1]);
      const mask = masks[slot];
      if (mask && info.shapeSlots.includes(slot)) {
        ctx.globalCompositeOperation = "destination-in";
        ctx.drawImage(mask, 0, 0, size[0], size[1]);
        ctx.globalCompositeOperation = "source-over";
      }
    };
    for (const group of info.groups)
      for (const slot of group.slots) draw(slot, byGroup[group.name], info.slotSizes[slot]);
    draw("skill_cutin", byGroup.skill_cutin, [1024, 512]);
  }, [boxes, image, masks, template?.backdrop, info]);

  if (error) return <Notice kind="error">立绘信息读取失败：{error}</Notice>;
  if (!info) return <div class="loading">正在读取立绘与裁剪模板……</div>;

  const toSvg = (event: PointerEvent) => {
    const el = svg.current!;
    const point = el.createSVGPoint();
    point.x = event.clientX;
    point.y = event.clientY;
    return point.matrixTransform(el.getScreenCTM()!.inverse());
  };
  const begin = (event: PointerEvent, kind: Drag["kind"], id: string) => {
    if (!template) return;
    event.stopPropagation();
    event.preventDefault();
    svg.current?.setPointerCapture(event.pointerId);
    const p = toSvg(event);
    setSelected(id === "face" ? selected : id);
    setDrag({ kind, id, x0: p.x, y0: p.y, template: clone(template) });
  };
  const move = (event: PointerEvent) => {
    if (!drag || !info) return;
    const p = toSvg(event);
    const dx = p.x - drag.x0;
    const dy = p.y - drag.y0;
    const t = clone(drag.template);
    const start = computeBoxes(drag.template, info).find((b) => b.id === drag.id);
    if (drag.kind === "face") {
      t.face = [round(t.face[0] + dx), round(t.face[1] + dy)];
      t.cutin.center = [round(t.cutin.center[0] + dx), round(t.cutin.center[1] + dy)];
    } else if (start && drag.id === "skill_cutin") {
      if (drag.kind === "move") {
        t.cutin.center = [round(t.cutin.center[0] + dx), round(t.cutin.center[1] + dy)];
      } else {
        const h = Math.max(32, Math.max(start.h + dy, (start.w + dx) / 2));
        t.cutin.height = round(h);
        t.cutin.center = [round(start.x + t.cutin.anchor[0] * h * 2), round(start.y + t.cutin.anchor[1] * h)];
      }
    } else if (start) {
      const spec = t.groups[drag.id];
      let { x, y, w, h } = start;
      if (drag.kind === "move") {
        x += dx; y += dy;
      } else {
        h = Math.max(8, Math.max(start.h + dy, (start.w + dx) / start.ratio));
        w = h * start.ratio;
        spec.factor = round(h / t.squareHeight, 3);
      }
      spec.anchor = [round(clamp((t.face[0] - x) / w, 0, 1), 3), round(clamp((t.face[1] - y) / h, 0, 1), 3)];
    }
    setTemplate(t);
  };
  const end = () => setDrag(null);

  const pickSource = (kind: SourceKind) => {
    const base = kind === "upload" ? info.upload : info.current;
    setSource(kind);
    setTemplate(base ? clone(base.template) : null);
    setResult(null);
  };
  const upload = async (file: File | undefined) => {
    if (!file) return;
    setBusy("upload"); setMessage(null);
    try {
      const response = await drafts.uploadPortrait(characterId, form, await fileToBase64(file));
      setInfo(response.info);
      setStamp(Date.now());
      setSource("upload");
      setTemplate(clone(response.info.upload!.template));
      setResult(null);
      setMessage({ kind: "info", text: `已上传 ${file.name}（${response.upload.originalSize?.join("×")}，去掉全透明边后 ${response.upload.size.join("×")}）。默认脸锚只是起点：请拖到两眼中点。` });
    } catch (e) {
      setMessage({ kind: "error", text: (e as Error).message });
    } finally {
      setBusy(null);
    }
  };
  const save = async () => {
    if (!template) return;
    setBusy("save"); setMessage(null);
    try {
      const response = await drafts.savePortrait(characterId, { form, source, template, atf });
      setResult(response.change!);
      setMessage({ kind: "info", text: `已写入草稿：${response.change!.files.length} 个文件（${response.status.label}）。` });
    } catch (e) {
      setMessage({ kind: "error", text: (e as Error).message });
    } finally {
      setBusy(null);
    }
  };
  const reset = () => {
    const base = source === "upload" ? info.upload : info.current;
    if (base) setTemplate(clone(base.template));
  };

  const sel = boxes.find((b) => b.id === selected);
  const handle = active ? Math.max(10, active.size[0] / 70) : 10;

  return (
    <div class="portrait">
      <div class="toolbar">
        <div class="segmented" role="group" aria-label="立绘槽">
          {(["0", "1"] as const).map((f) => (
            <button class={form === f ? "on" : ""} onClick={() => setForm(f)}>{f === "0" ? "立绘 _0（基础）" : "立绘 _1（觉醒）"}</button>
          ))}
        </div>
        <div class="segmented" role="group" aria-label="立绘来源">
          <button class={source === "current" ? "on" : ""} disabled={!info.current} onClick={() => pickSource("current")}>当前立绘重新裁剪</button>
          <button class={source === "upload" ? "on" : ""} disabled={!info.upload} onClick={() => pickSource("upload")}>上传的新立绘</button>
        </div>
        <label class="upload-btn">
          {busy === "upload" ? "上传中……" : "上传新立绘 PNG"}
          <input type="file" accept="image/png" onChange={(e) => upload((e.target as HTMLInputElement).files?.[0])} />
        </label>
      </div>
      <div class="notice warn small-notice">
        <strong>注意：</strong>
        <ul>
          <li>技能 cutin 真机只读安卓根 ATF（ETC1）不读 PNG。保存时{atf ? "会用 wf_atf 按原 ATF 的 mip 数重编（与 GUI replace_asset 同一编码器），但这份草稿没上过真机" : "不重编 ATF——换了 PNG 战斗画面也不会变"}。</li>
          <li>立绘切换界面需要 illustration_setting_sprite_sheet：保存时只重画本槽格子（fit 整图，近似；官方是海报构图重裁）。</li>
          <li>三张定位表（character_image / trimmed_image / full_shot_image_attribute）只记目标行，生成时由 wf deliver 写，草稿不写表。</li>
        </ul>
      </div>
      {message ? <Notice kind={message.kind === "error" ? "error" : "info"}>{message.text}</Notice> : null}
      {!active || !template ? (
        <Notice kind="warn">{source === "upload" ? "还没有上传新立绘。" : "当前视图里没有这个立绘。"}</Notice>
      ) : (
        <div class="crop-layout">
          <div class="crop-stage">
            <svg ref={svg} class="crop-svg" viewBox={`0 0 ${active.size[0]} ${active.size[1]}`}
              onPointerMove={move as any} onPointerUp={end} onPointerCancel={end} data-dragging={drag ? drag.kind : ""}>
              {imageUrl ? <image href={imageUrl} x={-offset[0]} y={-offset[1]} width={fullSize[0]} height={fullSize[1]} /> : null}
              {[...boxes.filter((b) => b.id !== selected), ...boxes.filter((b) => b.id === selected)].map((b) => {
                const on = b.id === selected;
                return (
                  <g class={"crop-box" + (on ? " on" : "")} data-box={b.id}>
                    <rect x={b.x} y={b.y} width={b.w} height={b.h} fill={on ? "rgba(255,255,255,0.08)" : "none"}
                      stroke={b.color} stroke-width={on ? 3 : 1.6} vector-effect="non-scaling-stroke"
                      pointer-events={on ? "all" : "none"} style={{ cursor: "move" }}
                      onPointerDown={on ? (e) => begin(e as any, "move", b.id) : undefined} />
                    {on ? null : (
                      <rect class="hit" x={b.x} y={b.y} width={b.w} height={b.h} fill="none" stroke="transparent"
                        stroke-width={handle * 1.4} pointer-events="stroke" style={{ cursor: "pointer" }}
                        onPointerDown={(e) => begin(e as any, "move", b.id)} />
                    )}
                    <text x={b.x + handle * 0.5} y={b.y + handle * 1.6} fill={b.color} font-size={handle * 1.5} class="box-label">{b.label}</text>
                    <rect class="handle" x={b.x + b.w - handle} y={b.y + b.h - handle} width={handle * 2} height={handle * 2} fill={b.color}
                      style={{ cursor: "nwse-resize" }} onPointerDown={(e) => begin(e as any, "resize", b.id)} />
                  </g>
                );
              })}
              <g class="face-anchor" style={{ cursor: "grab" }} onPointerDown={(e) => begin(e as any, "face", "face")}>
                <circle cx={template.face[0]} cy={template.face[1]} r={handle * 2.2} fill="rgba(255,255,255,0.15)" stroke="#fff" stroke-width={3} vector-effect="non-scaling-stroke" />
                <line x1={template.face[0] - handle * 4} y1={template.face[1]} x2={template.face[0] + handle * 4} y2={template.face[1]} stroke="#ff2d55" stroke-width={2} vector-effect="non-scaling-stroke" />
                <line x1={template.face[0]} y1={template.face[1] - handle * 4} x2={template.face[0]} y2={template.face[1] + handle * 4} stroke="#ff2d55" stroke-width={2} vector-effect="non-scaling-stroke" />
              </g>
            </svg>
            <p class="muted small">
              拖红色十字 = 脸锚（两眼连线中点），所有框跟着走；点框边或下方预览选中一组，在选中框内拖动 = 改这一组相对脸锚的位置；拖右下角方块 = 缩放（锁宽高比）。
              立绘 {active.size[0]}×{active.size[1]}{source === "current" && active.trim ? `（视图原图 ${fullSize[0]}×${fullSize[1]}）` : ""}。
            </p>
          </div>
          <aside class="crop-side">
            <h4>模板参数</h4>
            <div class="param-grid">
              <label>脸锚 x<input type="number" value={template.face[0]} step={1}
                onInput={(e) => { const v = Number((e.target as HTMLInputElement).value); const t = clone(template); t.cutin.center[0] += v - t.face[0]; t.face[0] = v; setTemplate(t); }} /></label>
              <label>脸锚 y<input type="number" value={template.face[1]} step={1}
                onInput={(e) => { const v = Number((e.target as HTMLInputElement).value); const t = clone(template); t.cutin.center[1] += v - t.face[1]; t.face[1] = v; setTemplate(t); }} /></label>
              <label title="方形头像框高；其它组 = 它 × factor">基准框高<input type="number" value={template.squareHeight} step={1} min={10}
                onInput={(e) => { const t = clone(template); t.squareHeight = Math.max(10, Number((e.target as HTMLInputElement).value)); setTemplate(t); }} /></label>
            </div>
            {sel ? (
              <div class="selected-box" style={{ borderColor: sel.color }}>
                <strong style={{ color: sel.color }}>{sel.label}</strong>
                {sel.id === "skill_cutin" ? (
                  <span class="small muted"> 框高 {round(template.cutin.height)} · 锚 ({template.cutin.anchor.join(", ")})</span>
                ) : (
                  <span class="small muted"> factor {template.groups[sel.id].factor} · 脸在框内 ({template.groups[sel.id].anchor.join(", ")})</span>
                )}
                <div class="small muted">{info.groups.find((g) => g.name === sel.id)?.label ?? "skill_cutin（1024×512，内容贴左、右侧渐隐）"}</div>
              </div>
            ) : null}
            <h4>图标底色 {active?.backdropSource ? <span class="small muted">（默认{active.backdropSource}）</span> : null}</h4>
            <div class="param-grid">
              <label class="check"><input type="checkbox" checked={template.backdrop === null}
                onChange={(e) => { const t = clone(template); t.backdrop = (e.target as HTMLInputElement).checked ? null : (active?.suggestedBackdrop ?? { inner: [110, 110, 130], outer: [40, 40, 55] }); setTemplate(t); }} />透明底</label>
              {template.backdrop ? (
                <>
                  <label>内<input type="color" value={hex(template.backdrop.inner)}
                    onInput={(e) => { const t = clone(template); t.backdrop!.inner = fromHex((e.target as HTMLInputElement).value); setTemplate(t); }} /></label>
                  <label>外<input type="color" value={hex(template.backdrop.outer)}
                    onInput={(e) => { const t = clone(template); t.backdrop!.outer = fromHex((e.target as HTMLInputElement).value); setTemplate(t); }} /></label>
                </>
              ) : null}
            </div>
            <label class="check"><input type="checkbox" checked={atf} onChange={(e) => setAtf((e.target as HTMLInputElement).checked)} />保存时重编 skill_cutin ATF</label>
            <div class="save-row">
              <button onClick={reset}>恢复默认框</button>
              <button class="primary" onClick={save} disabled={busy !== null}>{busy === "save" ? "派生中（约 10 秒）……" : "保存到草稿"}</button>
            </div>
            {maskState === "loading" ? <p class="small muted">形状蒙版统计中（首次约 10 秒，之后有缓存）……</p> : null}
            {maskState === "error" ? <p class="small error-text">形状蒙版读取失败，预览不套蒙版。</p> : null}
          </aside>
        </div>
      )}
      {active && template ? (
        <section class="previews">
          <h3>派生裁剪实时预览 <span class="muted small">（浏览器近似绘制；保存后下方显示后端用生产派生代码生成的结果）</span></h3>
          <div class="preview-grid">
            {info.groups.flatMap((g) => g.slots.map((slot) => (
              <figure class={"preview" + (g.name === selected ? " on" : "")} onClick={() => setSelected(g.name)}
                style={{ borderColor: COLORS[g.name] }}>
                <canvas ref={(el) => { canvases.current[slot] = el; }} data-slot={slot}
                  style={{ width: Math.min(info.slotSizes[slot][0], 140) + "px" }} />
                {gameDir ? (
                  <img class="game-icon" src={api.assetUrl(`${gameDir}/ui/${slot}_${form}.png`)} alt="" loading="lazy"
                    title="游戏里现在的图标" style={{ width: Math.min(info.slotSizes[slot][0], 140) / 2 + "px" }}
                    onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }} />
                ) : null}
                <figcaption>
                  <span class="mono small">{slot}</span>
                  <span class="small muted">{info.slotSizes[slot].join("×")} · {info.shapeLabels[slot] ?? "满框"} · {info.slotUse[slot]}</span>
                </figcaption>
              </figure>
            )))}
            <figure class={"preview wide" + (selected === "skill_cutin" ? " on" : "")} onClick={() => setSelected("skill_cutin")}
              style={{ borderColor: COLORS.skill_cutin }}>
              <canvas ref={(el) => { canvases.current.skill_cutin = el; }} data-slot="skill_cutin" style={{ width: "300px" }} />
              <figcaption><span class="mono small">skill_cutin</span><span class="small muted">1024×512 · 透明抠图 · {info.slotUse.skill_cutin}</span></figcaption>
            </figure>
          </div>
        </section>
      ) : null}
      {result ? (
        <section class="previews">
          <h3>草稿里的结果 <span class="muted small">{result.id} · {result.createdAt.replace("T", " ").slice(0, 19)}</span></h3>
          <ChecksList checks={result.checks} empty="没有检查提示。" />
          <div class="change-thumbs">
            {result.files.filter((f) => f.draft.endsWith(".png")).map((f) => (
              <figure title={f.note}>
                <img src={drafts.fileUrl(characterId, f.draft, f.sha256.slice(0, 8))} alt="" />
                <figcaption class="small mono">{f.logical.split("/").pop()}{f.approximate ? " ≈" : ""}</figcaption>
              </figure>
            ))}
          </div>
          {result.files.some((f) => f.encoding === "atf-deflate") ? (
            <p class="small muted">已生成 {result.files.filter((f) => f.encoding === "atf-deflate").map((f) => f.logical.split("/").pop()).join("、")}（安卓根）。</p>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}
