import { ComponentChildren, createContext } from "preact";
import { useContext } from "preact/hooks";
import { CommandResult, CorridorStatus, ELEMENTS, Finding, Json, Registry } from "../../corridorApi";

export interface CorridorCtx {
  status: CorridorStatus | null;
  registry: Registry | null;
  revision: number;
  /** Bumped after every successful write; pages reload their data on change. */
  tick: number;
  busy: boolean;
  run: (commands: Record<string, Json>[], message?: string) => Promise<CommandResult | null>;
  refresh: () => Promise<void>;
  setError: (message: string | null) => void;
}
export const Ctx = createContext<CorridorCtx>(null as unknown as CorridorCtx);
export const useCorridor = () => useContext(Ctx);

export function Tag({ kind = "", children, title }: { kind?: string; children: ComponentChildren; title?: string }) {
  return <span class={"cor-tag " + kind} title={title}>{children}</span>;
}

export function FindingList({ findings, limit = 200, onPick }: { findings: Finding[]; limit?: number; onPick?: (f: Finding) => void }) {
  if (!findings.length) return <div class="muted small">没有问题。</div>;
  const sorted = [...findings].sort((a, b) => (a.severity === b.severity ? 0 : a.severity === "block" ? -1 : 1));
  return (
    <div class="cor-findings">
      {sorted.slice(0, limit).map((f, i) => (
        <div key={i} class={"cor-finding " + f.severity}>
          <span class="code">{f.code}</span>
          <span>
            {onPick && f.entity_id ? <a href="javascript:void 0" onClick={() => onPick(f)}>{f.message}</a> : f.message}
            {f.suggested_fix ? <span class="muted"> — {f.suggested_fix}</span> : null}
            <span class="muted small mono"> {f.pointer}</span>
          </span>
        </div>
      ))}
      {sorted.length > limit ? <div class="muted small">还有 {sorted.length - limit} 条…</div> : null}
    </div>
  );
}

export function Num({ value, onChange, step, min, max, title }: {
  value: number | null | undefined; onChange: (v: number) => void; step?: number; min?: number; max?: number; title?: string;
}) {
  return (
    <input class="num" type="number" value={value ?? ""} step={step ?? "any"} min={min} max={max} title={title}
      onChange={(e) => {
        const raw = (e.currentTarget as HTMLInputElement).value;
        if (raw.trim() === "") return;
        const v = Number(raw);
        if (Number.isFinite(v)) onChange(v);
      }} />
  );
}

export function ElementSelect({ value, onChange, extra = [] }: {
  value: Json; onChange: (v: Json) => void; extra?: [string, string][];
}) {
  return (
    <select value={String(value ?? "")} onChange={(e) => {
      const v = (e.currentTarget as HTMLSelectElement).value;
      onChange(/^\d$/.test(v) ? Number(v) : v);
    }}>
      {extra.map(([k, label]) => <option key={k} value={k}>{label}</option>)}
      {ELEMENTS.map(([k, label]) => <option key={k} value={k}>{label}</option>)}
    </select>
  );
}

type Effect = Record<string, Json>;

/** Relic effect list: type from the registry (legacy types stay selectable when already present). */
export function RelicEffectsEditor({ effects, registry, onChange }: {
  effects: Effect[]; registry: Registry; onChange: (next: Effect[]) => void;
}) {
  const kinds = registry.relic_kinds;
  const set = (i: number, patch: Effect) => onChange(effects.map((e, j) => (j === i ? { ...e, ...patch } : e)));
  return (
    <div>
      {effects.map((e, i) => {
        const type = String(e.type);
        const spec = kinds[type];
        const legacy = !spec;
        const nested = type === "ignore_first_death_per_battle";
        return (
          <div key={i} class="cor-effect">
            <select value={type} onChange={(ev) => {
              const t = (ev.currentTarget as HTMLSelectElement).value;
              const k = kinds[t];
              const next: Effect = { type: t, value: k?.value === "number" ? 10 : 1 };
              if (k?.extra?.element) next.element = 1;
              if (k?.extra?.combo_threshold) next.combo_threshold = 50;
              onChange(effects.map((x, j) => (j === i ? next : x)));
            }}>
              {legacy ? <option value={type}>{type}（旧口径，保留）</option> : null}
              {Object.entries(kinds).map(([k, v]) => <option key={k} value={k}>{v.label}{v.combat ? "（战斗·客户端）" : ""}</option>)}
            </select>
            {nested ? (
              <span class="small">
                免扣次数 <Num value={(e.value as Record<string, number>)?.free_deaths} onChange={(v) => set(i, { value: { ...(e.value as object), free_deaths: v } })} />
                {" "}代价：休息回复 <Num value={(e.value as Record<string, number>)?.penalty_value} onChange={(v) => set(i, { value: { ...(e.value as object), penalty_value: v } })} />
              </span>
            ) : (
              <span class="small">
                数值 <Num value={e.value as number} min={spec?.min} max={spec?.max} onChange={(v) => set(i, { value: v })} />
                {spec?.unit ? <span class="muted"> {spec.unit}</span> : legacy ? <span class="muted"> （旧口径：按服务端换算）</span> : null}
              </span>
            )}
            {spec?.extra?.element ? <span class="small">属性 <ElementSelect value={e.element} onChange={(v) => set(i, { element: v })} /></span> : null}
            {spec?.extra?.combo_threshold ? (
              <span class="small">每 <Num value={e.combo_threshold as number} min={1} onChange={(v) => set(i, { combo_threshold: v })} /> 连击</span>
            ) : null}
            {spec?.combat ? <Tag kind="warn" title="服务端只透传（runtime=client_pending），是否生效取决于客户端">客户端效果</Tag> : null}
            <button class="ghost" disabled={effects.length <= 1} onClick={() => onChange(effects.filter((_, j) => j !== i))}>删除</button>
          </div>
        );
      })}
      {effects.length < 8 ? (
        <button onClick={() => onChange([...effects, { type: "gold_on_pickup", value: 50 }])}>＋ 效果</button>
      ) : null}
    </div>
  );
}

/** Event option effects (closed list of server-supported types and parameter shapes). */
export function EventEffectsEditor({ effects, registry, onChange }: {
  effects: Effect[]; registry: Registry; onChange: (next: Effect[]) => void;
}) {
  const kinds = registry.event_kinds;
  const set = (i: number, patch: Effect) => onChange(effects.map((e, j) => (j === i ? { ...e, ...patch } : e)));
  const defaults: Record<string, Effect> = {
    gamble: { value: { win_chance: 0.5, win_multiplier: 2, lose_multiplier: 0.5 } },
    relic: { value: { rarity: "random" } }, swap: {}, tier_element: { value: { tier: "T2", element: "random" } },
    true: { value: true }, int: { value: 10 },
  };
  return (
    <div>
      {effects.map((e, i) => {
        const type = String(e.type);
        const spec = kinds[type];
        const v = (e.value ?? {}) as Record<string, Json>;
        return (
          <div key={i} class="cor-effect">
            <select value={type} onChange={(ev) => {
              const t = (ev.currentTarget as HTMLSelectElement).value;
              const shape = kinds[t]?.value;
              onChange(effects.map((x, j) => (j === i ? { type: t, ...(shape ? defaults[shape] ?? {} : {}) } : x)));
            }}>
              {Object.entries(kinds).map(([k, s]) => <option key={k} value={k}>{s.label}</option>)}
            </select>
            {spec?.value === "int" ? <Num value={e.value as number} min={spec.min} max={spec.max} onChange={(n) => set(i, { value: Math.round(n) })} /> : null}
            {spec?.value === "gamble" ? (
              <span class="small">
                胜率 <Num value={v.win_chance as number} min={0} max={1} step={0.05} onChange={(n) => set(i, { value: { ...v, win_chance: n } })} />
                {" "}赢倍数 <Num value={v.win_multiplier as number} min={1} max={10} onChange={(n) => set(i, { value: { ...v, win_multiplier: n } })} />
                {" "}输后剩余比例 <Num value={v.lose_multiplier as number} min={0} max={1} step={0.05} onChange={(n) => set(i, { value: { ...v, lose_multiplier: n } })} />
              </span>
            ) : null}
            {spec?.value === "relic" ? (
              <select value={String(v.rarity ?? "random")} onChange={(ev) => set(i, { value: { ...v, rarity: (ev.currentTarget as HTMLSelectElement).value } })}>
                <option value="random">随机稀有度</option>
                {Object.entries(registry.rarities).map(([k, label]) => <option key={k} value={k}>{label}</option>)}
              </select>
            ) : null}
            {spec?.value === "tier_element" ? (
              <span class="small">
                档位 <select value={String(v.tier ?? "T2")} onChange={(ev) => set(i, { value: { ...v, tier: (ev.currentTarget as HTMLSelectElement).value } })}>
                  {["T1", "T2", "T3", "T4"].map((t) => <option key={t} value={t}>{t}</option>)}
                </select>
                {" "}属性 <ElementSelect value={v.element ?? "random"} onChange={(x) => set(i, { value: { ...v, element: x } })}
                  extra={[["random", "随机"], ["preferred", "偏好（开局属性）"], ["choose", "玩家自选"]]} />
              </span>
            ) : null}
            <button class="ghost" disabled={effects.length <= 1} onClick={() => onChange(effects.filter((_, j) => j !== i))}>删除</button>
          </div>
        );
      })}
      {effects.length < 8 ? <button onClick={() => onChange([...effects, { type: "gain_gold", value: 10 }])}>＋ 效果</button> : null}
    </div>
  );
}

export function RequiresEditor({ value, registry, onChange }: {
  value: Record<string, number> | null | undefined; registry: Registry; onChange: (v: Record<string, number>) => void;
}) {
  const current = value ?? {};
  return (
    <div class="cor-toolbar small">
      {Object.entries(registry.requires).map(([k, label]) => (
        <span key={k}>
          {label} <Num value={current[k] ?? null} min={0} onChange={(n) => onChange({ ...current, [k]: Math.max(0, Math.round(n)) })} />
          {k in current ? <button class="ghost" onClick={() => { const next = { ...current }; delete next[k]; onChange(next); }}>×</button> : null}
        </span>
      ))}
    </div>
  );
}

export function Modal({ children, onClose }: { children: ComponentChildren; onClose: () => void }) {
  return (
    <div class="cor-modal" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div role="dialog" aria-modal="true">{children}</div>
    </div>
  );
}

export function useConfirm() {
  return (text: string) => window.confirm(text);
}
