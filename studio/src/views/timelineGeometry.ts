// Battlefield placement for the L2 timeline preview. Pure functions: no DOM.
// Conventions follow the client: display rotation 0 = art unrotated / "up"; offsets are rotated by the
// coordinate-system direction (ActionHitAreaGroup: u' = u + x·cos w − y·sin w); velocity for angle w is
// speed·(sin w, −cos w) (ActionHitArea.applyMovement, AB case).
import { Subject, Timeline, TimelineEvent } from "../timelineApi";

export const STAGE = { w: 1080, h: 1920 };
export const FIELD_CENTER = { x: STAGE.w / 2, y: STAGE.h / 2 };

export interface Point { x: number; y: number }
export interface Scene { ball: Point; enemy: Point; ballDir: number }
export interface Placed { x: number; y: number; r: number }

export const rotate = (x: number, y: number, r: number): [number, number] =>
  [x * Math.cos(r) - y * Math.sin(r), x * Math.sin(r) + y * Math.cos(r)];
const up = (r: number): [number, number] => [Math.sin(r), -Math.cos(r)];
const BALLISH = new Set(["ball", "self", "ally", "leader", "mate"]);

export class Placement {
  private byId = new Map<number, TimelineEvent>();
  private cache = new Map<string, Placed>();
  constructor(timeline: Timeline, private scene: Scene) {
    for (const e of timeline.events) this.byId.set(e.id, e);
  }

  subject(subject: Subject | null | undefined, t: number, depth = 0): Placed {
    const ref = subject?.ref ?? "unknown";
    if (BALLISH.has(ref)) return { ...this.scene.ball, r: this.scene.ballDir };
    if (ref === "enemy") return { ...this.scene.enemy, r: 0 };
    if (ref === "field_center") return { ...FIELD_CENTER, r: 0 };
    if (ref === "field_lt") return { x: 0, y: 0, r: 0 };
    const match = /^(hitarea|marker):(\d+)$/.exec(ref);
    if (match && depth < 8) {
      const host = this.byId.get(Number(match[2]));
      if (host) return this.place(host, t, depth + 1);
    }
    return { ...FIELD_CENTER, r: 0 };
  }

  private direction(e: TimelineEvent, base: Placed, t: number, depth: number): number {
    const coord = e.coord;
    if (!coord || coord.kind === "AB") return 0;
    if (coord.kind === "EF") return BALLISH.has(e.subject?.ref ?? "") ? this.scene.ballDir : 0;
    if (coord.kind === "CD") return /^hitarea:/.test(e.subject?.ref ?? "") ? base.r : 0;
    const target = this.subject(coord.toward, t, depth + 1);
    return Math.atan2(target.y - base.y, target.x - base.x) + Math.PI / 2;
  }

  /** Position and rotation of an effect / hit area / marker at frame t. */
  place(e: TimelineEvent, t: number, depth = 0): Placed {
    const key = e.id + ":" + Math.floor(t);
    const hit = this.cache.get(key);
    if (hit) return hit;
    const at = e.tracking?.pos ? t : e.t;
    let base = this.subject(e.subject, at, depth);
    if (e.subjectY) base = { x: base.x, y: this.subject(e.subjectY, at, depth).y, r: 0 };
    const dir = this.direction(e, base, at, depth);
    const [ox, oy] = rotate(e.offset?.x ?? 0, e.offset?.y ?? 0, dir);
    let x = base.x + ox, y = base.y + oy;
    const r = dir + (e.rot ?? 0);
    const motions = (e.motions ?? []).slice().sort((a, b) => a.t - b.t);
    motions.forEach((m, i) => {
      const from = Math.max(m.t, e.t);
      const to = Math.min(t, i + 1 < motions.length ? motions[i + 1].t : t);
      if (to <= from) return;
      const heading = m.coord === "CD" ? r + m.angle : m.coord === "EF" ? this.scene.ballDir + m.angle
        : m.coord === "GH" ? Math.atan2(this.scene.enemy.y - y, this.scene.enemy.x - x) + Math.PI / 2 : m.angle;
      const [vx, vy] = up(heading);
      x += vx * m.speed * (to - from);
      y += vy * m.speed * (to - from);
    });
    const placed = { x, y, r };
    this.cache.set(key, placed);
    return placed;
  }
}

/** Timeline frame (1-based) shown by an effect `local` frames after it spawned, or null when gone. */
export function effectFrame(e: TimelineEvent, local: number): number | null {
  if (local < 0 || local >= e.dur) return null;
  for (const [start, base, length, step] of e.runs ?? []) {
    if (local >= start && local < start + length) return base + (local - start) * step;
  }
  return null;
}

/** Shape centre offset for HAlign/VAlign (ActionHitArea pivotX/pivotY: Left/Top push the centre +size). */
export function pivot(e: TimelineEvent): [number, number] {
  const s = e.shape;
  if (!s) return [0, 0];
  const hx = s.type === "rect" ? (s.w ?? 0) / 2 : s.type === "circle" ? s.r ?? 0 : 0;
  const hy = s.type === "rect" ? (s.h ?? 0) / 2 : s.type === "circle" ? s.r ?? 0 : 0;
  const h = e.align?.h === "Left" ? hx : e.align?.h === "Right" ? -hx : 0;
  const v = e.align?.v === "Top" ? hy : e.align?.v === "Bottom" ? -hy : 0;
  return [h, v];
}

export function isActive(e: TimelineEvent, t: number): boolean {
  return t >= e.t && t < e.t + Math.max(1, e.dur);
}

export const ATTRIBUTION_COLOR: Record<string, string> = {
  技能: "#ff922b", 强化弹射: "#4dabf7", 能力: "#51cf66", 直击: "#ff6b6b",
};
export function attributionColor(label: string | undefined): string {
  const key = Object.keys(ATTRIBUTION_COLOR).find((k) => (label ?? "").startsWith(k));
  return key ? ATTRIBUTION_COLOR[key] : "#adb5bd";
}
