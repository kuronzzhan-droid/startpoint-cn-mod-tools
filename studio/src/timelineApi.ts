// L2 编排级 preview: typed wrappers over /api/studio/timeline, /api/studio/effect and the per-character program list.
import { get } from "./api";

export type LaneId = "effect" | "hit" | "action" | "sound" | "wait" | "state" | "other";

export interface Subject {
  ref: string; // ball | self | field_center | field_lt | enemy | ally | leader | mate | hitarea:<id> | marker:<id> | unknown
  label: string;
  id?: number;
  selector?: number;
}

export interface Coord { kind: "AB" | "CD" | "EF" | "GH"; toward?: Subject; note?: string }

export interface Motion { t: number; angle: number; speed: number; coord: string | null }

export interface Shape {
  type: "circle" | "rect" | "sector" | "donut" | "arc" | "unknown";
  r?: number; w?: number; h?: number; angle?: number; label: string; approx?: boolean;
}

export interface Formation {
  type: string; label?: string; angles?: number[]; offsets?: { x?: number; y?: number }[]; approx?: boolean;
}

export interface Attribution { value: number; label: string; auto: boolean; note: string; source?: string }

export interface TimelineEvent {
  id: number;
  lane: LaneId;
  kind: string;
  t: number;
  dur: number;
  label: string;
  detail?: string;
  node: string;
  arms: number[];
  scope: string[];
  trigger: string | null;
  subject?: Subject | null;
  subjectY?: Subject;
  // effects
  path?: string | null;
  how?: string;
  layer?: number;
  layerLabel?: string;
  lifetime?: { kind: string | null; label: string };
  life?: number | null;
  lifeEstimated?: boolean;
  coord?: Coord;
  offset?: { x: number; y: number };
  rot?: number;
  tracking?: { pos: boolean; dir: boolean };
  scale?: number | null;
  scaleSource?: string;
  asset?: boolean;
  missing?: string;
  runs?: [number, number, number, number][];
  endLength?: number;
  endNote?: string;
  hiddenAt?: number;
  // hit areas
  name?: string;
  shape?: Shape;
  align?: { h: string; v: string };
  formation?: Formation;
  hits?: { kind: string | null; label?: string; times: number[]; expected?: number; cap?: string; note: string };
  attribution?: Attribution;
  attacks?: number[];
  motions?: Motion[];
  sampleHit?: number;
  erasedAt?: number;
  // attacks
  multiplier?: string;
  element?: string;
  area?: number | null;
  extra?: Record<string, unknown>;
  // other
  subprogram?: number;
  effect?: number;
  interval?: number;
  count?: number;
}

export interface Arm { id: number; label: string; condition: string; node: string; empty: boolean }

export interface Timeline {
  program: string;
  kind: string;
  fps: number;
  duration: number;
  header: Record<string, unknown>;
  attribution: Attribution;
  lanes: { id: LaneId; label: string }[];
  events: TimelineEvent[];
  arms: Arm[];
  unknown: { node: string; name: string; reason: string; kind?: string }[];
  unmodeled: { name: string; label: string; count: number }[];
  issues: { level: string; node: string; text: string }[];
  subprograms: { path: string; spawnedBy: number; t: number; node: string; note: string; error?: string; timeline?: Timeline }[];
  notSimulated: string[];
  truncated: boolean;
  notes: string[];
}

export interface ProgramEntry {
  id: string;
  group: string;
  label: string;
  path: string;
  kind: "skill" | "pf" | "ability_skill" | "subprogram";
  exists: boolean;
  note: string;
  name?: string;
  forLevels?: string[];
  mainOnly?: boolean;
}

export interface EffectCell { w: number; h: number; fx: number; fy: number; x: number; y: number }

export interface EffectBake {
  path: string;
  ok: boolean;
  issues: string[];
  sequences?: { name: string; kind: string; begin: number; end: number }[];
  defaultScale?: number;
  frameCount?: number;
  frames?: number[][][];
  cells?: (EffectCell | null)[];
  bounds?: [number, number, number, number] | null;
  note?: string;
}

const memo = new Map<string, Promise<unknown>>();
function once<T>(url: string): Promise<T> {
  if (!memo.has(url)) {
    const p = get<T>(url);
    p.catch(() => memo.delete(url));
    memo.set(url, p);
  }
  return memo.get(url) as Promise<T>;
}

export const timelineApi = {
  programs: (cid: string) => once<{ characterId: string; programs: ProgramEntry[]; note: string }>(`/api/characters/${cid}/programs`),
  timeline: (path: string, kind: string, cid?: string) =>
    once<Timeline>(`/api/studio/timeline?path=${encodeURIComponent(path)}&kind=${kind}${cid ? "&cid=" + cid : ""}`),
  effect: (path: string) => once<EffectBake>(`/api/studio/effect?path=${encodeURIComponent(path)}`),
  effectPngUrl: (path: string) => `/api/studio/effect.png?path=${encodeURIComponent(path)}`,
  /** BOSS moves from the esdl timeline summary (M6 backend). 404 → not available yet. */
  bossMoves: async (quest: string): Promise<{ available: true; moves: { name: string; label?: string; timeline: Timeline }[]; note?: string } | { available: false; reason: string }> => {
    const response = await fetch(`/api/boss/${encodeURIComponent(quest)}/timeline-summary`);
    const body = await response.json().catch(() => ({}));
    if (response.status === 405 || (response.status === 404 && (!body.error || body.error === "未知接口"))) {
      return { available: false, reason: "后端还没有 BOSS 出招时间轴接口（/api/boss/<关卡>/timeline-summary，M6 的 esdl 时间轴摘要）。" };
    }
    if (!response.ok) return { available: false, reason: body.error || `HTTP ${response.status}` };
    return { available: true, moves: body.moves ?? [], note: body.note };
  },
};
