// L2「编排级」preview: one ActionDsl program laid out on a 60 fps timeline over a 1080×1920 battlefield.
// Visual subset only — hits, target selection and branch conditions are annotated, not simulated.
// TimelinePlayer only needs a Timeline (the same event schema can come from an esdl summary for BOSS moves).
import { useEffect, useMemo, useRef, useState } from "preact/hooks";
import { api, PixelAction, PixelFamily, PixelMeta } from "../api";
import { EffectBake, LaneId, ProgramEntry, Timeline, TimelineEvent, timelineApi } from "../timelineApi";
import { Notice } from "./common";
import {
  attributionColor, effectFrame, FIELD_CENTER, isActive, pivot, Placement, Point, rotate, Scene, STAGE,
} from "./timelineGeometry";
import "./timeline.css";

const SPEEDS = [0.25, 0.5, 1, 2];
const LANE_COLOR: Record<LaneId, string> = {
  effect: "#9775fa", hit: "#ff922b", action: "#20c997", sound: "#fab005", wait: "#868e96", state: "#4dabf7", other: "#adb5bd",
};
const BLEND: Record<number, GlobalCompositeOperation> = { 1: "lighter", 2: "multiply", 3: "overlay", 4: "screen" };

interface LoadedEffect { meta: EffectBake; image: HTMLImageElement | null }

function loadImage(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error("贴图加载失败"));
    image.src = url;
  });
}

/** Program picker (技能 / 强化弹射 / 能力技 629) + player, for one character. */
export function SkillPreview({ characterId, prefer }: { characterId: string; prefer?: "pf" | "skill" }) {
  const [programs, setPrograms] = useState<ProgramEntry[] | null>(null);
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [timeline, setTimeline] = useState<Timeline | null>(null);
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    setPrograms(null); setSelected(null); setTimeline(null); setError(null);
    timelineApi.programs(characterId).then((r) => {
      setPrograms(r.programs); setNote(r.note);
      const usable = r.programs.filter((p) => p.exists);
      const first = (prefer ? usable.find((p) => p.kind === prefer) : null) ?? usable[0];
      if (first) setSelected(first.id);
    }, (e: Error) => setError(e.message));
  }, [characterId, prefer]);
  const program = programs?.find((p) => p.id === selected);
  useEffect(() => {
    if (!program || !program.exists) { setTimeline(null); return; }
    setLoading(true);
    timelineApi.timeline(program.path, program.kind, characterId)
      .then((t) => { setTimeline(t); setError(null); }, (e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [program?.id]);

  if (error && !programs) return <Notice kind="error">读取程序列表失败：{error}</Notice>;
  if (!programs) return <div class="loading">正在列出技能与强化弹射程序……</div>;
  if (!programs.length) return <Notice>这个角色没有可预览的技能/强化弹射程序。</Notice>;
  const groups = Array.from(new Set(programs.map((p) => p.group)));
  return (
    <div class="tl-page">
      <div class="tl-picker">
        {groups.map((g) => (
          <div class="tl-picker-group">
            <h4>{g}</h4>
            {programs.filter((p) => p.group === g).map((p) => (
              <button class={"tl-program" + (p.id === selected ? " on" : "") + (p.exists ? "" : " absent")}
                disabled={!p.exists} title={p.path + (p.note ? "\n" + p.note : "")} onClick={() => setSelected(p.id)}>
                <span>{p.label}</span>
                {p.note ? <span class="small muted">{p.note}</span> : null}
              </button>
            ))}
          </div>
        ))}
        <p class="small muted">{note}</p>
      </div>
      <div class="tl-main">
        {error ? <Notice kind="error">{error}</Notice> : null}
        {loading && !timeline ? <div class="loading">正在解析程序……</div> : null}
        {timeline && program ? (
          <TimelinePlayer key={program.id} timeline={timeline} characterId={characterId}
            title={`${program.group} · ${program.label}`} mainOnly={program.mainOnly} />
        ) : null}
      </div>
    </div>
  );
}

/** BOSS moves: reuses the player once the backend serves an esdl-derived event list. */
export function BossMovesPreview({ quest }: { quest: string }) {
  const [state, setState] = useState<Awaited<ReturnType<typeof timelineApi.bossMoves>> | null>(null);
  const [index, setIndex] = useState(0);
  useEffect(() => { setState(null); timelineApi.bossMoves(quest).then(setState, (e: Error) => setState({ available: false, reason: e.message })); }, [quest]);
  if (!state) return <div class="loading">正在读取出招时间轴……</div>;
  if (!state.available) {
    return (
      <div class="tl-placeholder">
        <Notice kind="warn">出招预览尚未接通：{state.reason}</Notice>
        <p class="small muted">接通后这里沿用角色技能预览的同一个播放器：每个出招一条时间轴（特效 / 判定 / 动作 / 声音 / 等待），
          事件格式与 <span class="mono">/api/studio/timeline</span> 相同（<span class="mono">{"{ moves: [{ name, timeline }] }"}</span>）。</p>
      </div>
    );
  }
  if (!state.moves.length) return <Notice>这一关没有可预览的出招。</Notice>;
  const move = state.moves[Math.min(index, state.moves.length - 1)];
  return (
    <div class="tl-page">
      <div class="tl-picker">
        <div class="tl-picker-group">
          <h4>出招</h4>
          {state.moves.map((m, i) => (
            <button class={"tl-program" + (i === index ? " on" : "")} onClick={() => setIndex(i)}>{m.label ?? m.name}</button>
          ))}
        </div>
        {state.note ? <p class="small muted">{state.note}</p> : null}
      </div>
      <div class="tl-main"><TimelinePlayer key={move.name} timeline={move.timeline} title={move.label ?? move.name} boss /></div>
    </div>
  );
}

function usePixelBody(characterId?: string) {
  const [meta, setMeta] = useState<PixelMeta | null>(null);
  const [sheets, setSheets] = useState<Record<string, HTMLImageElement>>({});
  useEffect(() => {
    if (!characterId) return;
    api.pixels(characterId).then(async (data) => {
      setMeta(data);
      const loaded: Record<string, HTMLImageElement> = {};
      for (const f of data.families) if (!f.error) loaded[f.family] = await loadImage(api.pixelSheetUrl(characterId, f.family));
      setSheets(loaded);
    }, () => setMeta(null));
  }, [characterId]);
  return { meta, sheets };
}

function cellAt(action: PixelAction, tick: number): number {
  const local = Math.floor(tick) % Math.max(1, action.totalFrames);
  for (const c of action.cells) if (local >= c.start && local < c.start + c.frames) return c.cell;
  return action.cells[action.cells.length - 1]?.cell ?? 0;
}

export function TimelinePlayer({ timeline: root, characterId, title, mainOnly, boss }: {
  timeline: Timeline; characterId?: string; title: string; mainOnly?: boolean; boss?: boolean;
}) {
  const [stack, setStack] = useState<{ timeline: Timeline; title: string }[]>([]);
  const timeline = stack.length ? stack[stack.length - 1].timeline : root;
  const heading = stack.length ? stack[stack.length - 1].title : title;
  const [tick, setTick] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [loop, setLoop] = useState(true);
  const [lanes, setLanes] = useState<Set<LaneId>>(new Set(["effect", "hit", "action", "sound", "wait", "state", "other"]));
  const [hiddenArms, setHiddenArms] = useState<Set<number>>(new Set());
  const [labels, setLabels] = useState(true);
  const [scene, setScene] = useState<Scene>({ ball: { x: 540, y: 1380 }, enemy: { x: 540, y: 620 }, ballDir: 0 });
  const [selected, setSelected] = useState<number | null>(null);
  const [effects, setEffects] = useState<Record<string, LoadedEffect>>({});
  const [action, setAction] = useState<{ family: string; name: string }>({ family: "pixelart", name: "neutral" });
  const body = usePixelBody(boss ? undefined : characterId);
  const canvas = useRef<HTMLCanvasElement>(null);
  const drag = useRef<"ball" | "enemy" | null>(null);
  const duration = Math.max(1, timeline.duration);

  useEffect(() => { setTick(0); setPlaying(false); setSelected(null); setHiddenArms(new Set()); }, [timeline]);

  // Load every effect the program shows (baked parts + repacked cells).
  useEffect(() => {
    const paths = Array.from(new Set(timeline.events.filter((e) => e.kind === "effect" && e.asset && e.path).map((e) => e.path!)));
    for (const path of paths) {
      if (effects[path]) continue;
      timelineApi.effect(path).then(async (meta) => {
        const image = meta.ok ? await loadImage(timelineApi.effectPngUrl(path)).catch(() => null) : null;
        setEffects((current) => ({ ...current, [path]: { meta, image } }));
      }, (e: Error) => setEffects((current) => ({ ...current, [path]: { meta: { path, ok: false, issues: [e.message] }, image: null } })));
    }
  }, [timeline]);

  // Clock.
  useEffect(() => {
    if (!playing) return;
    let last = performance.now();
    let handle = 0;
    const step = (now: number) => {
      const delta = ((now - last) / 1000) * timeline.fps * speed;
      last = now;
      setTick((current) => {
        let next = current + delta;
        if (next >= duration) {
          if (loop) next %= duration;
          else { next = duration - 1; setPlaying(false); }
        }
        return next;
      });
      handle = requestAnimationFrame(step);
    };
    handle = requestAnimationFrame(step);
    return () => cancelAnimationFrame(handle);
  }, [playing, speed, loop, duration, timeline]);

  const visible = (e: TimelineEvent) => lanes.has(e.lane) && !e.arms.some((a) => hiddenArms.has(a));
  const frame = Math.floor(tick);

  // Draw the battlefield.
  useEffect(() => {
    const el = canvas.current;
    if (!el) return;
    const view = 0.375;
    const ratio = window.devicePixelRatio || 1;
    const cw = Math.round(STAGE.w * view), ch = Math.round(STAGE.h * view);
    if (el.width !== cw * ratio) { el.width = cw * ratio; el.height = ch * ratio; el.style.width = cw + "px"; el.style.height = ch + "px"; }
    const ctx = el.getContext("2d")!;
    const k = view * ratio;
    const stage = () => ctx.setTransform(k, 0, 0, k, 0, 0);
    stage();
    ctx.globalAlpha = 1;
    ctx.globalCompositeOperation = "source-over";
    ctx.fillStyle = "#151a24";
    ctx.fillRect(0, 0, STAGE.w, STAGE.h);
    ctx.strokeStyle = "rgba(255,255,255,0.06)";
    ctx.lineWidth = 2;
    for (let x = 0; x <= STAGE.w; x += 120) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, STAGE.h); ctx.stroke(); }
    for (let y = 0; y <= STAGE.h; y += 120) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(STAGE.w, y); ctx.stroke(); }

    const place = new Placement(timeline, scene);
    const events = timeline.events.filter(visible);
    const font = (size: number) => { ctx.font = `${size}px "Microsoft YaHei UI", sans-serif`; };
    const label = (text: string, x: number, y: number, color = "#e9ecef") => {
      if (!labels) return;
      stage(); font(26); ctx.globalAlpha = 1; ctx.globalCompositeOperation = "source-over";
      const w = ctx.measureText(text).width;
      ctx.fillStyle = "rgba(0,0,0,0.55)"; ctx.fillRect(x - 4, y - 24, w + 8, 32);
      ctx.fillStyle = color; ctx.fillText(text, x, y);
    };

    // Field points and subjects.
    const cross = (p: Point, color: string) => {
      stage(); ctx.strokeStyle = color; ctx.lineWidth = 3;
      ctx.beginPath(); ctx.moveTo(p.x - 30, p.y); ctx.lineTo(p.x + 30, p.y); ctx.moveTo(p.x, p.y - 30); ctx.lineTo(p.x, p.y + 30); ctx.stroke();
    };
    cross(FIELD_CENTER, "rgba(255,255,255,0.35)");
    label("场地中心 -1", FIELD_CENTER.x + 34, FIELD_CENTER.y - 10, "#adb5bd");
    label("场地左上 -2", 8, 34, "#adb5bd");
    stage();
    ctx.fillStyle = "rgba(255,107,107,0.18)"; ctx.strokeStyle = "#ff6b6b"; ctx.lineWidth = 4;
    ctx.beginPath(); ctx.arc(scene.enemy.x, scene.enemy.y, 150, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
    label("敌人（示意，可拖动）", scene.enemy.x - 120, scene.enemy.y - 165, "#ffa8a8");

    const drawEffect = (e: TimelineEvent) => {
      if (!isActive(e, tick)) return;
      const local = tick - e.t;
      const p = place.place(e, frame);
      const loaded = e.path ? effects[e.path] : undefined;
      const scale = e.scale ?? loaded?.meta.defaultScale ?? 1;
      const f = effectFrame(e, Math.floor(local));
      if (loaded?.meta.ok && loaded.image && f !== null && loaded.meta.frames) {
        const commands = loaded.meta.frames[f - 1] ?? [];
        for (const [cell, a, b, c, d, tx, ty, alpha, blend] of commands) {
          const info = loaded.meta.cells?.[cell];
          if (!info) continue;
          stage();
          ctx.translate(p.x, p.y); ctx.rotate(p.r); ctx.scale(scale, scale);
          ctx.transform(a, b, c, d, tx, ty);
          ctx.globalAlpha = Math.max(0, Math.min(1, alpha));
          ctx.globalCompositeOperation = BLEND[blend] ?? "source-over";
          ctx.drawImage(loaded.image, info.x, info.y, info.w, info.h, -info.fx, -info.fy, info.w, info.h);
        }
        ctx.globalAlpha = 1; ctx.globalCompositeOperation = "source-over";
      } else {
        stage(); ctx.translate(p.x, p.y); ctx.rotate(p.r);
        ctx.setLineDash([12, 8]); ctx.strokeStyle = "#b197fc"; ctx.lineWidth = 3;
        ctx.strokeRect(-80, -80, 160, 160); ctx.setLineDash([]);
        label(`特效（未渲染）${e.label}`, p.x - 80, p.y - 90, "#d0bfff");
        return;
      }
      if (selected === e.id) label(`特效 ${e.label}`, p.x + 10, p.y - 10, "#d0bfff");
    };

    const drawPixel = () => {
      const meta = body.meta;
      const fam: PixelFamily | undefined = meta?.families.find((f) => f.family === action.family && !f.error)
        ?? meta?.families.find((f) => !f.error);
      const act = fam?.actions.find((a) => a.name === action.name) ?? fam?.actions[0];
      const image = fam ? body.sheets[fam.family] : undefined;
      const hidden = timeline.events.some((e) => e.kind === "HideCharacter" && visible(e) && isActive(e, tick));
      stage();
      ctx.fillStyle = "rgba(77,171,247,0.25)"; ctx.strokeStyle = "#4dabf7"; ctx.lineWidth = 3;
      ctx.beginPath(); ctx.arc(scene.ball.x, scene.ball.y, 45, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
      const [dx, dy] = rotate(0, -110, scene.ballDir);
      ctx.beginPath(); ctx.moveTo(scene.ball.x, scene.ball.y); ctx.lineTo(scene.ball.x + dx, scene.ball.y + dy); ctx.stroke();
      if (fam && act && image && !hidden) {
        const cell = cellAt(act, tick);
        const sx = (cell % fam.columns) * fam.cellWidth, sy = Math.floor(cell / fam.columns) * fam.cellHeight;
        const s = Number(fam.scale) || 1;
        stage(); ctx.imageSmoothingEnabled = false;
        ctx.drawImage(image, sx, sy, fam.cellWidth, fam.cellHeight, scene.ball.x - fam.anchor.x * s, scene.ball.y - fam.anchor.y * s,
          fam.cellWidth * s, fam.cellHeight * s);
        ctx.imageSmoothingEnabled = true;
      }
      label(hidden ? "自身 -17 / 球 -18（隐藏中）" : "自身 -17 / 球 -18（可拖动）", scene.ball.x + 50, scene.ball.y + 70, "#a5d8ff");
    };

    const drawHit = (e: TimelineEvent) => {
      if (e.kind === "marker") {
        if (!isActive(e, tick) && !(e.life == null && tick >= e.t)) return;
        const p = place.place(e, frame);
        stage(); ctx.translate(p.x, p.y); ctx.rotate(Math.PI / 4);
        ctx.strokeStyle = "#ffe066"; ctx.lineWidth = 3; ctx.strokeRect(-14, -14, 28, 28);
        label(`参考点 #${e.id}`, p.x + 18, p.y - 14, "#ffe066");
        return;
      }
      if (e.kind !== "hitarea" || !isActive(e, tick) || !e.shape) return;
      const p = place.place(e, frame);
      const color = attributionColor(e.attribution?.label);
      const local = tick - e.t;
      const flash = (e.hits?.times ?? []).some((h) => local >= h && local < h + 3);
      const copies: { off: [number, number]; rot: number }[] = e.formation?.angles?.length
        ? e.formation.angles.map((a) => ({ off: [0, 0] as [number, number], rot: a }))
        : e.formation?.offsets?.length ? e.formation.offsets.map((o) => ({ off: [o.x ?? 0, o.y ?? 0] as [number, number], rot: 0 }))
        : [{ off: [0, 0], rot: 0 }];
      const [px, py] = pivot(e);
      for (const copy of copies) {
        stage(); ctx.translate(p.x, p.y); ctx.rotate(p.r);
        ctx.translate(copy.off[0], copy.off[1]); ctx.rotate(copy.rot); ctx.translate(px, py);
        ctx.fillStyle = color; ctx.strokeStyle = color; ctx.lineWidth = selected === e.id ? 8 : 4;
        ctx.globalAlpha = flash ? 0.42 : 0.2;
        ctx.beginPath();
        const s = e.shape;
        if (s.type === "rect") ctx.rect(-(s.w ?? 0) / 2, -(s.h ?? 0) / 2, s.w ?? 0, s.h ?? 0);
        else if (s.type === "sector") { ctx.moveTo(0, 0); ctx.arc(0, 0, s.r ?? 0, -Math.PI / 2 - (s.angle ?? 0) / 2, -Math.PI / 2 + (s.angle ?? 0) / 2); ctx.closePath(); }
        else ctx.arc(0, 0, Math.max(4, s.type === "circle" ? s.r ?? 0 : (s.r ?? 1) * 10), 0, Math.PI * 2);
        ctx.fill(); ctx.globalAlpha = 0.9; ctx.stroke(); ctx.globalAlpha = 1;
      }
      const tag = `#${e.id} ${e.shape.label} · ${e.attribution?.label ?? ""}${e.hits?.expected ? ` · ${e.hits.expected}次` : ""}`;
      label(tag, Math.max(4, Math.min(STAGE.w - 420, p.x - 140)), Math.max(30, Math.min(STAGE.h - 10, p.y + 8)), color);
    };

    const layered = events.filter((e) => e.kind === "effect");
    layered.filter((e) => (e.layer ?? 2) <= 1).forEach(drawEffect);
    drawPixel();
    layered.filter((e) => (e.layer ?? 2) > 1).forEach(drawEffect);
    events.filter((e) => e.kind === "hitarea" || e.kind === "marker").forEach(drawHit);
    // Attacks flash on their target for a few frames.
    for (const e of events) {
      if (e.kind !== "attack" || tick < e.t || tick >= e.t + 8) continue;
      const p = place.subject(e.subject, frame);
      label(`${e.label} · ${e.attribution?.label ?? ""}`, p.x - 90, p.y + 40, attributionColor(e.attribution?.label));
    }
    stage();
  });

  // Dragging the ball / enemy markers.
  const toStage = (event: PointerEvent): Point => {
    const rect = canvas.current!.getBoundingClientRect();
    return { x: ((event.clientX - rect.left) / rect.width) * STAGE.w, y: ((event.clientY - rect.top) / rect.height) * STAGE.h };
  };
  const onDown = (event: PointerEvent) => {
    const p = toStage(event);
    if (Math.hypot(p.x - scene.ball.x, p.y - scene.ball.y) < 120) drag.current = "ball";
    else if (Math.hypot(p.x - scene.enemy.x, p.y - scene.enemy.y) < 170) drag.current = "enemy";
    if (drag.current) (event.target as HTMLElement).setPointerCapture(event.pointerId);
  };
  const onMove = (event: PointerEvent) => {
    if (!drag.current) return;
    const p = toStage(event);
    setScene((s) => ({ ...s, [drag.current!]: { x: Math.round(p.x), y: Math.round(p.y) } }));
  };
  const onUp = () => { drag.current = null; };

  const shown = timeline.events.filter(visible);
  const now = shown.filter((e) => isActive(e, tick)).slice(0, 40);
  const picked = selected != null ? timeline.events.find((e) => e.id === selected) : undefined;
  const actions = (body.meta?.families ?? []).flatMap((f) => (f.error ? [] : f.actions.map((a) => ({ f, a }))));

  return (
    <div class="tl-player">
      <div class="tl-head">
        {stack.length ? <button onClick={() => setStack(stack.slice(0, -1))}>← 返回上一层</button> : null}
        <strong>{heading}</strong>
        <span class="mono small muted">{timeline.program}</span>
        <span class="tag" title={timeline.attribution.note}>伤害归属：{timeline.attribution.label}{timeline.attribution.auto ? "（自动）" : ""}</span>
        <span class="tag">{duration} 帧 · {(duration / timeline.fps).toFixed(2)} 秒</span>
        {mainOnly ? <span class="tag">仅队长位生效</span> : null}
      </div>
      <Notice kind="warn">未模拟：{timeline.notSimulated.join(" / ")}。两条分支都画出来（可在右侧关掉某条分支）；命中块只在示意时刻展开一次；
        目标选取只画 1 个代表；球静止（可拖动），方向用右侧「球方向」。</Notice>
      <div class="tl-body">
        <div class="tl-stage">
          <canvas ref={canvas} class="tl-canvas" data-frame={frame} onPointerDown={onDown} onPointerMove={onMove}
            onPointerUp={onUp} onPointerLeave={onUp} />
        </div>
        <aside class="tl-side">
          <section>
            <h4>轨道</h4>
            {timeline.lanes.map((lane) => (
              <label class="check tl-lane-toggle">
                <input type="checkbox" checked={lanes.has(lane.id)} onChange={() => {
                  const next = new Set(lanes); next.has(lane.id) ? next.delete(lane.id) : next.add(lane.id); setLanes(next);
                }} />
                <span class="tl-swatch" style={{ background: LANE_COLOR[lane.id] }} />{lane.label}
                <span class="small muted">{timeline.events.filter((e) => e.lane === lane.id).length}</span>
              </label>
            ))}
            <label class="check"><input type="checkbox" checked={labels} onChange={() => setLabels(!labels)} />画面标签</label>
          </section>
          {timeline.arms.length ? (
            <section>
              <h4>分支（条件未模拟）</h4>
              {timeline.arms.map((arm) => (
                <label class="check tl-arm" title={arm.node}>
                  <input type="checkbox" checked={!hiddenArms.has(arm.id)} onChange={() => {
                    const next = new Set(hiddenArms); next.has(arm.id) ? next.delete(arm.id) : next.add(arm.id); setHiddenArms(next);
                  }} />
                  {arm.label}{arm.empty ? <span class="small muted">（空）</span> : null}
                </label>
              ))}
            </section>
          ) : null}
          <section>
            <h4>场景</h4>
            <label class="tl-range">球方向 {Math.round((scene.ballDir * 180) / Math.PI)}°
              <input type="range" min={-180} max={180} value={Math.round((scene.ballDir * 180) / Math.PI)}
                onInput={(e) => setScene({ ...scene, ballDir: (Number((e.target as HTMLInputElement).value) * Math.PI) / 180 })} />
            </label>
            {actions.length ? (
              <label>小人动作
                <select value={action.family + "/" + action.name} onChange={(e) => {
                  const [family, name] = (e.target as HTMLSelectElement).value.split("/");
                  setAction({ family, name });
                }}>
                  {actions.map(({ f, a }) => <option value={f.family + "/" + a.name}>{a.label}（{a.name}）</option>)}
                </select>
              </label>
            ) : null}
            <p class="small muted">技能/强化弹射期间小人播哪个动作由客户端代码决定，DSL 不控制；这里按所选动作循环播放。</p>
            <button onClick={() => setScene({ ball: { x: 540, y: 1380 }, enemy: { x: 540, y: 620 }, ballDir: 0 })}>复位</button>
          </section>
          <Diagnostics timeline={timeline} onOpen={(i) => {
            const sub = timeline.subprograms[i];
            if (sub?.timeline) setStack([...stack, { timeline: sub.timeline, title: "子程序 · " + sub.path.split("/").pop() }]);
          }} />
        </aside>
      </div>
      <div class="transport">
        <button onClick={() => { setPlaying(false); setTick(Math.max(0, frame - 10)); }} title="后退 10 帧">−10</button>
        <button onClick={() => { setPlaying(false); setTick(Math.max(0, frame - 1)); }} title="上一帧">⏮</button>
        <button class="primary" onClick={() => { if (!playing && frame >= duration - 1) setTick(0); setPlaying(!playing); }}>{playing ? "暂停" : "播放"}</button>
        <button onClick={() => { setPlaying(false); setTick(Math.min(duration - 1, frame + 1)); }} title="下一帧">⏭</button>
        <button onClick={() => { setPlaying(false); setTick(Math.min(duration - 1, frame + 10)); }} title="前进 10 帧">+10</button>
        <input type="range" min={0} max={duration - 1} value={frame} aria-label="时间轴"
          onInput={(e) => { setPlaying(false); setTick(Number((e.target as HTMLInputElement).value)); }} />
        <span class="mono small">帧 {frame}/{duration - 1} · {(frame / timeline.fps).toFixed(2)} 秒</span>
        <label>速度 <select value={speed} onChange={(e) => setSpeed(Number((e.target as HTMLSelectElement).value))}>
          {SPEEDS.map((s) => <option value={s}>{s}×</option>)}</select></label>
        <label class="check"><input type="checkbox" checked={loop} onChange={() => setLoop(!loop)} />循环</label>
      </div>
      <Lanes timeline={timeline} visible={visible} filterKey={[...lanes].join() + "|" + [...hiddenArms].join()} tick={tick} selected={selected}
        onSeek={(t) => { setPlaying(false); setTick(Math.max(0, Math.min(duration - 1, t))); }}
        onSelect={(id) => setSelected(id)} />
      <div class="tl-bottom">
        <section>
          <h4>当前帧（{frame}）</h4>
          {now.length ? (
            <ul class="tl-now">
              {now.map((e) => (
                <li class={selected === e.id ? "on" : ""} onClick={() => setSelected(e.id)}>
                  <span class="tl-swatch" style={{ background: LANE_COLOR[e.lane] }} />
                  <span class="mono small">{e.t}{e.dur ? `–${e.t + e.dur}` : ""}</span> {e.label}
                  {e.trigger ? <span class="tag">{e.trigger}</span> : null}
                  {e.arms.length ? <span class="tag">分支</span> : null}
                </li>
              ))}
            </ul>
          ) : <p class="small muted">这一帧没有事件。</p>}
        </section>
        <section>
          <h4>选中事件</h4>
          {picked ? <EventDetail e={picked} timeline={timeline} /> : <p class="small muted">点轨道上的条或左侧列表查看参数。</p>}
        </section>
      </div>
      <ul class="small muted tl-notes">{timeline.notes.map((n) => <li>{n}</li>)}</ul>
    </div>
  );
}

function Diagnostics({ timeline, onOpen }: { timeline: Timeline; onOpen: (index: number) => void }) {
  return (
    <section>
      <h4>检查</h4>
      {timeline.issues.length ? (
        <ul class="tl-issues">{timeline.issues.map((i) => <li class={i.level === "问题" ? "error-text" : "warn-text"} title={i.node}>{i.level}：{i.text}</li>)}</ul>
      ) : <p class="small muted">作用域/坐标系/形状检查无问题。</p>}
      <p class="small"><strong>未知节点 {timeline.unknown.length}</strong>{timeline.unknown.length ? "" : "（全部构造名都在签名表里）"}</p>
      {timeline.unknown.length ? <ul class="tl-issues">{timeline.unknown.map((u) => <li class="error-text" title={u.node}>{u.name}：{u.reason}</li>)}</ul> : null}
      {timeline.unmodeled.length ? (
        <p class="small">没有画面模型的命令：{timeline.unmodeled.map((u) => `${u.label}×${u.count}`).join("、")}（标在「其它」轨道）</p>
      ) : null}
      {timeline.subprograms.length ? (
        <div class="small">子程序：
          <ul class="tl-issues">{timeline.subprograms.map((s, i) => (
            <li>{s.path.split("/").pop()} {s.timeline ? <button class="link" onClick={() => onOpen(i)}>打开</button> : <span class="warn-text">{s.error}</span>}
              <span class="muted">（{s.note}）</span></li>
          ))}</ul>
        </div>
      ) : null}
      {timeline.truncated ? <p class="warn-text small">事件或时长超过预览上限，后面的部分被截断。</p> : null}
    </section>
  );
}

function EventDetail({ e, timeline }: { e: TimelineEvent; timeline: Timeline }) {
  const rows: [string, string][] = [["节点", e.node], ["时刻", `第 ${e.t} 帧${e.dur ? `，持续 ${e.dur} 帧` : ""}`]];
  if (e.subject) rows.push(["主体", e.subject.label]);
  if (e.coord) rows.push(["坐标系", e.coord.kind + (e.coord.toward ? ` → ${e.coord.toward.label}` : "") + (e.coord.note ? `（${e.coord.note}）` : "")]);
  if (e.offset && (e.offset.x || e.offset.y)) rows.push(["偏移", `(${e.offset.x}, ${e.offset.y})`]);
  if (e.rot) rows.push(["旋转", `${((e.rot * 180) / Math.PI).toFixed(1)}°`]);
  if (e.path) rows.push(["特效", e.path + (e.how && e.how !== "直接指定" ? `（${e.how}）` : "")]);
  if (e.missing) rows.push(["资源", e.missing]);
  if (e.lifetime) rows.push(["寿命", e.lifetime.label + (e.lifeEstimated ? "（估计）" : "")]);
  if (e.endNote) rows.push(["收尾", e.endNote + (e.endLength ? `（end ${e.endLength} 帧）` : "") + (e.hiddenAt != null ? `；第 ${e.hiddenAt} 帧被 HideEffect 终止` : "")]);
  if (e.scale != null) rows.push(["缩放", `${e.scale}（${e.scaleSource}）`]);
  if (e.layerLabel) rows.push(["图层", e.layerLabel]);
  if (e.tracking) rows.push(["跟随", `位置 ${e.tracking.pos ? "是" : "否（创建帧快照）"} / 方向 ${e.tracking.dir ? "是" : "否"}`]);
  if (e.shape) rows.push(["形状", e.shape.label + (e.align ? `，对齐 ${e.align.h}/${e.align.v}` : "")]);
  if (e.formation) rows.push(["阵型", e.formation.label ?? e.formation.type]);
  if (e.hits) rows.push(["命中", `${e.hits.label ?? ""}；${e.hits.note}`]);
  if (e.sampleHit != null) rows.push(["命中块", `示意展开于第 ${e.sampleHit} 帧`]);
  if (e.attribution) rows.push(["伤害归属", `${e.attribution.label}${e.attribution.source ? `（${e.attribution.source}）` : ""}：${e.attribution.note}`]);
  if (e.attacks?.length) rows.push(["攻击", e.attacks.map((id) => timeline.events[id]?.label).join("、")]);
  if (e.multiplier) rows.push(["倍率", `${e.multiplier}（SLv1→满级），属性 ${e.element}`]);
  if (e.extra) rows.push(["其它参数", Object.entries(e.extra).map(([k, v]) => `${k} ${v}`).join("，")]);
  if (e.scope.length) rows.push(["作用域", e.scope.join(" › ")]);
  if (e.trigger) rows.push(["触发", e.trigger]);
  if (e.arms.length) rows.push(["分支", e.arms.map((a) => timeline.arms[a]?.label).join(" › ")]);
  if (e.detail) rows.push(["说明", e.detail]);
  return (
    <table class="tl-detail"><tbody>{rows.map(([k, v]) => <tr><th>{k}</th><td>{v}</td></tr>)}</tbody></table>
  );
}

function Lanes({ timeline, visible, filterKey, tick, selected, onSeek, onSelect }: {
  timeline: Timeline; visible: (e: TimelineEvent) => boolean; filterKey: string; tick: number; selected: number | null;
  onSeek: (t: number) => void; onSelect: (id: number) => void;
}) {
  const duration = Math.max(1, timeline.duration);
  const rows = useMemo(() => {
    const result: { lane: LaneId; label: string; rows: TimelineEvent[][] }[] = [];
    for (const lane of timeline.lanes) {
      const items = timeline.events.filter((e) => e.lane === lane.id && visible(e)).sort((a, b) => a.t - b.t);
      if (!items.length) continue;
      const stacked: TimelineEvent[][] = [];
      const ends: number[] = [];
      for (const e of items) {
        const end = e.t + Math.max(e.dur, duration / 120);
        let row = ends.findIndex((x) => x <= e.t);
        if (row < 0 && ends.length < 8) { row = ends.length; ends.push(0); stacked.push([]); }
        if (row < 0) row = ends.indexOf(Math.min(...ends));
        ends[row] = Math.max(ends[row], end);
        stacked[row].push(e);
      }
      result.push({ lane: lane.id, label: lane.label, rows: stacked });
    }
    return result;
  }, [timeline, filterKey]);
  const seek = (event: MouseEvent) => {
    const rect = (event.currentTarget as HTMLElement).getBoundingClientRect();
    onSeek(Math.round(((event.clientX - rect.left) / rect.width) * duration));
  };
  const ticks = [];
  const step = duration > 600 ? 120 : duration > 240 ? 60 : duration > 60 ? 15 : 5;
  for (let t = 0; t <= duration; t += step) ticks.push(t);
  return (
    <div class="tl-lanes">
      <div class="tl-lane tl-ruler">
        <span class="tl-lane-name">帧</span>
        <div class="tl-track" onClick={seek}>
          {ticks.map((t) => <span class="tl-tick" style={{ left: (t / duration) * 100 + "%" }}>{t}</span>)}
          <span class="tl-playhead" style={{ left: (tick / duration) * 100 + "%" }} />
        </div>
      </div>
      {rows.map((lane) => (
        <div class="tl-lane">
          <span class="tl-lane-name" style={{ borderColor: LANE_COLOR[lane.lane] }}>{lane.label}</span>
          <div class="tl-track" style={{ height: lane.rows.length * 16 + 4 + "px" }} onClick={seek}>
            {lane.rows.map((row, r) => row.map((e) => (
              <span class={"tl-bar" + (selected === e.id ? " on" : "") + (e.dur ? "" : " instant") + (e.arms.length ? " armed" : "") + (e.trigger ? " triggered" : "")}
                title={`${e.label}\n第 ${e.t} 帧${e.dur ? ` · ${e.dur} 帧` : ""}${e.trigger ? "\n" + e.trigger : ""}${e.detail ? "\n" + e.detail : ""}`}
                style={{ left: (e.t / duration) * 100 + "%", width: e.dur ? Math.max(0.3, (e.dur / duration) * 100) + "%" : undefined,
                  top: r * 16 + 2 + "px", background: e.kind === "hitarea" ? attributionColor(e.attribution?.label) : LANE_COLOR[e.lane] }}
                onClick={(ev) => { ev.stopPropagation(); onSelect(e.id); onSeek(e.t); }}>
                {e.dur && e.dur / duration > 0.06 ? e.label : ""}
              </span>
            )))}
            <span class="tl-playhead" style={{ left: (tick / duration) * 100 + "%" }} />
          </div>
        </div>
      ))}
    </div>
  );
}
