// 行为：GeneralBoss 的 routine / marker 出招槽与 StandardBoss 的 esdl 状态机（只读视图）；
// 开放同首领换招、招式伤害倍率、StandardBoss 状态间隔与试炼阈值；GeneralBoss 间隔/试炼与跨首领借招待 M6.1。
// 每个出招都有「预览」：优先用后端 /api/boss/<quest>/timeline-summary，没有就按出招的 DSL 路径调 /api/studio/timeline。
import { useEffect, useMemo, useRef, useState } from "preact/hooks";
import { BehaviorDoc, BehaviorEnemy, BehaviorRequest, BehaviorState, BossDoc, GeneralTrial } from "../../bossApi";
import { Timeline, timelineApi } from "../../timelineApi";
import { Notice } from "../common";
import { InfoTip } from "../Delivery";
import { TimelinePlayer } from "../TimelinePreview";
import { PreviewState } from "./BossParams";
import { OpActions, PendingFix, useBossOp, useSection } from "./bossOps";

const H1 = "M6.1 修复中：GeneralBoss 改间隔 / 试炼会让自身 watch 失效（审查 H1），修好前不开放";
const H2 = "M6.1 修复中：借用其它首领的招式时，动作里的命名站位引用还没有门禁（审查 H2），修好前不开放";
const GENERAL_TERMINATION: Record<string, string> = { "1": "动画结束", "2": "定时", "3": "条件", "6": "试炼 / 计数" };
const TRIAL_KIND: Record<string, string> = { "0": "直击次数", "1": "技能次数", "2": "强化弹射次数", "3": "技能连锁" };
const PAGE = 40;

const short = (path: string) => path.split("/").pop()?.replace(/^boss_[^$]*\$/, "") ?? path;

type Edit =
  | { kind: "swap"; enemy: BehaviorEnemy; slot: number }
  | { kind: "damage"; enemy: BehaviorEnemy; slot: number }
  | { kind: "interval"; enemy: BehaviorEnemy; state: BehaviorState }
  | { kind: "trial"; enemy: BehaviorEnemy; state: BehaviorState }
  | null;

interface MoveRef { path: string; label: string; enemy: string; slot?: number }

function terminationText(enemy: BehaviorEnemy, s: BehaviorState): string {
  const t = s.termination as any;
  if (Array.isArray(t)) {
    if (t[0] === "TimeElapsed" && Array.isArray(t[1])) return t[1][0] === "Frame" ? `定时 ${t[1][1]} 帧` : t[1][0] === "Loop" ? `动画循环 ${t[1][1]} 次` : JSON.stringify(t);
    return String(t[0] ?? "—");
  }
  if (enemy.kind === "general" && t) return `${GENERAL_TERMINATION[t.kind] ?? "类型 " + t.kind}${t.kind === "2" ? ` ${t.value} 帧` : t.value ? ` · ${t.value}` : ""}`;
  return "—";
}

function trialText(s: BehaviorState): string {
  const t = s.trial as any;
  if (!t) return "";
  if (Array.isArray(t)) {
    if (t[0] === "HitCountCheck") return `${t[1]?.content?.[0] ?? "计数"} ${t[1]?.content?.[1] ?? "?"} 次`;
    if (t[0] === "DamageCheck") return `伤害 ${t[1]?.percentage ?? "?"}%`;
    return String(t[0]);
  }
  const g = t as GeneralTrial;
  return `${TRIAL_KIND[g.kind] ?? "类型 " + g.kind} ${g.threshold}`;
}

/** What the backend lets us edit on this state, and why not otherwise. */
function editable(enemy: BehaviorEnemy, s: BehaviorState): { interval: "ok" | "pending" | "no"; trial: "ok" | "pending" | "no"; frames?: number; threshold?: number } {
  if (enemy.kind === "general") {
    const t = s.termination as { kind: string; value: string };
    const trial = s.trial as GeneralTrial | null;
    return {
      interval: t?.kind === "2" ? "pending" : "no",
      trial: trial && ["0", "1", "2", "3"].includes(trial.kind) ? "pending" : "no",
    };
  }
  const t = s.termination as any[];
  const trial = s.trial as any[] | null;
  const frames = Array.isArray(t) && t[0] === "TimeElapsed" && t[1]?.[0] === "Frame" ? Number(t[1][1]) : undefined;
  let threshold: number | undefined;
  let trialOk: "ok" | "no" = "no";
  if (Array.isArray(trial) && trial[0] === "HitCountCheck" && ["DirectAttack", "Skill", "PowerFlip", "SkillChain"].includes(trial[1]?.content?.[0])
    && typeof trial[1]?.content?.[1] === "number") { trialOk = "ok"; threshold = trial[1].content[1]; }
  if (Array.isArray(trial) && trial[0] === "DamageCheck") { trialOk = "ok"; threshold = trial[1]?.percentage; }
  return { interval: frames !== undefined ? "ok" : "no", trial: trialOk, frames, threshold };
}

export function BossBehavior({ doc, questId, rev, onPreview, onWritten }: {
  doc: BossDoc; questId: string; rev: string; onPreview: (s: PreviewState) => void; onWritten: () => void;
}) {
  const behavior = useSection<BehaviorDoc>(questId, "behavior", rev);
  const [enemyIndex, setEnemyIndex] = useState(0);
  const [edit, setEdit] = useState<Edit>(null);
  const [move, setMove] = useState<MoveRef | null>(null);
  useEffect(() => { setEdit(null); }, [rev]);
  if (doc.routing.kind === "BothBoss") return <Notice kind="warn">五重入口（BothBoss）只读：行为在隐藏关里。</Notice>;
  if (behavior.error) return <Notice kind="error">读取行为失败：{behavior.error}</Notice>;
  if (!behavior.data) return <div class="loading">正在解码 boss 行为（esdl / routine）……</div>;
  const enemies = behavior.data.enemies;
  if (!enemies.length) return <Notice>这一关没有可读的 boss 行为。</Notice>;
  const enemy = enemies[Math.min(enemyIndex, enemies.length - 1)];
  return (
    <div class="boss-read boss-behavior">
      <section class="boss-block">
        <header>
          <h3>首领</h3>
          <InfoTip text="GeneralBoss：general_boss 行 + routine 状态表 + marker 动画触发槽；StandardBoss：esdl 状态机。时间轴以每个状态进入为 0 帧、60 帧/秒；条件退出、循环保留为表达式，不模拟战斗。" />
        </header>
        <div class="segmented" role="group" aria-label="首领">
          {enemies.map((e, i) => (
            <button type="button" class={i === enemyIndex ? "on" : ""} aria-pressed={i === enemyIndex} onClick={() => { setEnemyIndex(i); setEdit(null); }}>
              {e.enemyCode} <span class="small muted">第 {Number(e.wave) + 1} 波 · Lv{e.level}</span>
            </button>
          ))}
        </div>
        <dl class="kv">
          <dt>类型</dt><dd>{enemy.kind === "general" ? "GeneralBoss（表驱动 routine）" : enemy.kind === "standard" ? "StandardBoss（esdl 状态机）" : enemy.kind}
            {enemy.limitation ? <span class="warn-text small"> {enemy.limitation}</span> : null}</dd>
          {enemy.kind === "general" ? <><dt>routine</dt><dd class="mono small">{enemy.routine} · 初始状态 {enemy.initial_state}</dd></> : null}
          {enemy.logical ? <><dt>esdl</dt><dd class="mono small">{enemy.logical.replace(/\.esdl\.amf3\.deflate$/, "")}</dd></> : null}
          <dt>marker</dt><dd class="mono small">{enemy.marker ?? "—"}{enemy.marker_missing ? <span class="error-text"> 缺失</span> : null}</dd>
          <dt>状态数</dt><dd>{enemy.states.length}</dd>
          {enemy.preload ? <><dt>预载</dt><dd class="small">{enemy.preload.dsl.length} 个动作程序 · {enemy.preload.effects.length} 个特效
            {enemy.preload.missing.length ? <span class="error-text"> · 缺 {enemy.preload.missing.length}</span> : null}</dd></> : null}
        </dl>
      </section>

      {enemy.kind === "general" ? (
        <SlotTable enemy={enemy} edit={edit} setEdit={setEdit} onPreviewMove={setMove} questId={questId}
          onPreview={onPreview} onWritten={onWritten} />
      ) : (
        <section class="boss-block">
          <header><h3>出招槽</h3></header>
          <p class="small muted">StandardBoss 的招式写在各状态的动作里（见下方状态表的「动作」列），没有 marker 槽，所以不能换招或改招式伤害倍率。</p>
        </section>
      )}

      {move ? <MovePlayer key={move.path} quest={questId} move={move} onClose={() => setMove(null)} /> : null}
      <StateTable enemy={enemy} edit={edit} setEdit={setEdit} onPreviewMove={setMove} questId={questId}
        onPreview={onPreview} onWritten={onWritten} />

    </div>
  );
}

// ------------------------------------------------------------------------------------- slots

function SlotTable({ enemy, edit, setEdit, onPreviewMove, questId, onPreview, onWritten }: {
  enemy: BehaviorEnemy; edit: Edit; setEdit: (e: Edit) => void; onPreviewMove: (m: MoveRef) => void;
  questId: string; onPreview: (s: PreviewState) => void; onWritten: () => void;
}) {
  // Which states fire each slot (marker actions inside the state's sequence).
  const usedBy = useMemo(() => {
    const map = new Map<number, string[]>();
    for (const s of enemy.states) for (const a of s.actions) if (a.slot !== undefined) map.set(a.slot, [...(map.get(a.slot) ?? []), s.name ?? s.id]);
    return map;
  }, [enemy]);
  return (
    <section class="boss-block">
      <header>
        <h3>出招槽（{enemy.slots.length}）</h3>
        <InfoTip text="general_boss c111–c160：marker 动画到触发帧时执行槽里的 ActionDsl。换招 = 把目标槽改用同一首领另一个槽的程序；伤害倍率 = 槽里 CreateNormalAttack 当前倍率再乘一个数。" />
        <span class="spacer" />
        <PendingFix why={H2}><button type="button" disabled>从其它首领借招</button></PendingFix>
      </header>
      <div class="table-scroll">
        <table class="boss-table">
          <thead><tr><th>槽</th><th>程序</th><th>触发它的状态</th><th /></tr></thead>
          <tbody>
            {enemy.slots.map((s) => {
              const states = usedBy.get(s.slot) ?? [];
              const on = edit && (edit.kind === "swap" || edit.kind === "damage") && edit.slot === s.slot;
              return (
                <>
                  <tr class={on ? "on" : ""}>
                    <td class="mono">{s.slot}</td>
                    <td class="mono small" title={s.program}>{short(s.program)}</td>
                    <td class="small">{states.length ? states.slice(0, 4).join("、") + (states.length > 4 ? ` 等 ${states.length} 个` : "") : <span class="muted">没有 marker 触发</span>}</td>
                    <td class="nowrap">
                      <button type="button" class="link" onClick={() => onPreviewMove({ path: s.program, label: `槽 ${s.slot} · ${short(s.program)}`, enemy: enemy.enemyCode, slot: s.slot })}>预览</button>
                      {" "}<button type="button" class="link" onClick={() => setEdit({ kind: "swap", enemy, slot: s.slot })}>换招</button>
                      {" "}<button type="button" class="link" onClick={() => setEdit({ kind: "damage", enemy, slot: s.slot })}>伤害倍率</button>
                    </td>
                  </tr>
                  {on ? (
                    <tr class="edit-row"><td colSpan={4}>
                      {edit!.kind === "swap" ? (
                        <SwapEditor enemy={enemy} slot={s.slot} questId={questId} onPreview={onPreview} onWritten={onWritten} onClose={() => setEdit(null)} />
                      ) : (
                        <DamageEditor enemy={enemy} slot={s.slot} questId={questId} onPreview={onPreview} onWritten={onWritten} onClose={() => setEdit(null)} />
                      )}
                    </td></tr>
                  ) : null}
                </>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function SwapEditor({ enemy, slot, questId, onPreview, onWritten, onClose }: {
  enemy: BehaviorEnemy; slot: number; questId: string; onPreview: (s: PreviewState) => void; onWritten: () => void; onClose: () => void;
}) {
  const others = enemy.slots.filter((s) => s.slot !== slot);
  const [source, setSource] = useState<number | "">("");
  const request: BehaviorRequest | null = source === "" ? null
    : { operation: "behavior_replace", enemyCode: enemy.enemyCode, slot, sourceEnemyCode: enemy.enemyCode, sourceSlot: source };
  const op = useBossOp(questId, request, [], onPreview, onWritten);
  return (
    <div class="param-block pending-block">
      <h4>槽 {slot} 换成同一首领的另一招 <button type="button" class="link close-x" onClick={onClose} aria-label="关闭">×</button></h4>
      <label class="param-field"><span>改用哪个槽的程序</span>
        <select value={source} onChange={(e) => { const v = (e.target as HTMLSelectElement).value; setSource(v ? Number(v) : ""); }}>
          <option value="">（选一个槽）</option>
          {others.map((s) => <option value={s.slot}>槽 {s.slot} · {short(s.program)}</option>)}
        </select>
      </label>
      <p class="small muted">目标槽和来源槽都必须已有 marker 触发；有伤害共享 / 联动随从等固定身份链接的首领会被拒绝，并说明引用链。</p>
      <OpActions op={op} problems={[]} onReset={onClose} idle="选一个来源槽" />
    </div>
  );
}

function DamageEditor({ enemy, slot, questId, onPreview, onWritten, onClose }: {
  enemy: BehaviorEnemy; slot: number; questId: string; onPreview: (s: PreviewState) => void; onWritten: () => void; onClose: () => void;
}) {
  const [value, setValue] = useState("1.2");
  const n = Number(value);
  const problems = !Number.isFinite(n) || n <= 0 || n > 1000 ? ["倍率要是 0–1000 之间的正数"] : n === 1 ? ["×1 不会有变化"] : [];
  const request: BehaviorRequest | null = { operation: "behavior_parameters", enemyCode: enemy.enemyCode, slot, damageMultiplier: n };
  const op = useBossOp(questId, problems.length ? null : request, problems, onPreview, onWritten);
  return (
    <div class="param-block pending-block">
      <h4>槽 {slot} 的伤害倍率 <button type="button" class="link close-x" onClick={onClose} aria-label="关闭">×</button></h4>
      <label class="param-field"><span>乘以</span><input type="number" min={0} step={0.05} value={value} onInput={(e) => setValue((e.target as HTMLInputElement).value)} /></label>
      <Notice kind="warn">这是乘数，不是绝对值：作用在这个槽动作里每个 CreateNormalAttack 的当前倍率上；再写一次会继续相乘。</Notice>
      <OpActions op={op} problems={problems} onReset={onClose} />
    </div>
  );
}

// ------------------------------------------------------------------------------------- states

function StateTable({ enemy, edit, setEdit, onPreviewMove, questId, onPreview, onWritten }: {
  enemy: BehaviorEnemy; edit: Edit; setEdit: (e: Edit) => void; onPreviewMove: (m: MoveRef) => void;
  questId: string; onPreview: (s: PreviewState) => void; onWritten: () => void;
}) {
  const [filter, setFilter] = useState("");
  const [only, setOnly] = useState<"all" | "actions" | "trial" | "timed">("all");
  const [page, setPage] = useState(0);
  useEffect(() => { setPage(0); }, [filter, only, enemy.enemyCode]);
  const rows = enemy.states.filter((s) => {
    const q = filter.trim().toLowerCase();
    if (q && !(`${s.id} ${s.animation} ${s.marker_sequence} ${s.dsl.join(" ")}`.toLowerCase().includes(q))) return false;
    if (only === "actions") return s.dsl.length > 0;
    if (only === "trial") return !!s.trial;
    if (only === "timed") return s.duration_frames !== null;
    return true;
  });
  const shown = rows.slice(page * PAGE, page * PAGE + PAGE);
  const general = enemy.kind === "general";
  return (
    <section class="boss-block">
      <header>
        <h3>状态（{enemy.states.length}）</h3>
        <InfoTip text={general ? "general_boss_state：c46/c47 终止条件、c22–c26 试炼、c31 下一状态、c50 站位。" : "esdl forms[].states：terminationCondition、trial、next/back；form = 形态（例如单人 / 协力或阶段）。"} />
      </header>
      <div class="filters">
        <input placeholder="按状态名、动画或程序搜索" value={filter} onInput={(e) => setFilter((e.target as HTMLInputElement).value)} />
        <div class="segmented" role="group" aria-label="筛选">
          {([["all", "全部"], ["actions", "有出招"], ["timed", "定时"], ["trial", "试炼"]] as const).map(([id, label]) => (
            <button type="button" class={only === id ? "on" : ""} aria-pressed={only === id} onClick={() => setOnly(id)}>{label}</button>
          ))}
        </div>
        <span class="small muted">{rows.length} 个</span>
      </div>
      <div class="table-scroll">
        <table class="boss-table state-table">
          <thead><tr><th>状态</th><th>动画</th><th>时长 / 终止</th><th>试炼</th><th>下一状态</th><th>出招</th><th>标记</th><th /></tr></thead>
          <tbody>
            {shown.map((s) => {
              const can = editable(enemy, s);
              const on = edit && (edit.kind === "interval" || edit.kind === "trial") && edit.state.id === s.id;
              return (
                <>
                  <tr class={on ? "on" : ""}>
                    <td class="mono small">{s.form !== undefined ? <span class="muted">形态 {s.form} · </span> : null}{s.id}</td>
                    <td class="small">{s.animation}{s.marker_interval ? <span class="muted"> · 帧 {s.marker_interval.begin}–{s.marker_interval.end}</span> : null}</td>
                    <td class="small">{terminationText(enemy, s)}{s.duration_frames === null ? <span class="muted"> · 时长未知</span> : null}</td>
                    <td class="small">{trialText(s) || <span class="muted">—</span>}</td>
                    <td class="small mono">{typeof s.next === "string" ? s.next : <span title={JSON.stringify(s.next)}>表达式</span>}</td>
                    <td class="small">
                      {s.actions.length ? s.actions.map((a) => a.dsl.map((d) => (
                        <button type="button" class="link" title={d} onClick={() => onPreviewMove({ path: d, label: `${s.id} · ${short(d)}`, enemy: enemy.enemyCode, slot: a.slot })}>
                          {a.slot !== undefined ? `槽 ${a.slot}` : short(d)}{a.trigger_frame !== undefined ? `@${a.trigger_frame}` : ""} ▶
                        </button>
                      ))) : <span class="muted">—</span>}
                    </td>
                    <td class="small">
                      {s.invincible_by_phase_change ? <span class="tag">转阶段无敌</span> : null}
                      {s.immunity_links.length ? <span class="tag" title="CreateCondition 免伤 / 耐性引用">免伤 {s.immunity_links.length}</span> : null}
                      {s.position ? <span class="tag mono">站位 {s.position}</span> : null}
                      {s.missing.length ? <span class="tag error-text" title={s.missing.join("\n")}>缺 {s.missing.length}</span> : null}
                    </td>
                    <td class="nowrap">
                      {can.interval === "ok" ? <button type="button" class="link" onClick={() => setEdit({ kind: "interval", enemy, state: s })}>改间隔</button>
                        : can.interval === "pending" ? <PendingFix why={H1}><button type="button" class="link" disabled>改间隔</button></PendingFix> : null}
                      {" "}
                      {can.trial === "ok" ? <button type="button" class="link" onClick={() => setEdit({ kind: "trial", enemy, state: s })}>改试炼</button>
                        : can.trial === "pending" ? <PendingFix why={H1}><button type="button" class="link" disabled>改试炼</button></PendingFix> : null}
                    </td>
                  </tr>
                  {on ? (
                    <tr class="edit-row"><td colSpan={8}>
                      <StateEditor edit={edit as Extract<Edit, { kind: "interval" | "trial" }>} can={can} questId={questId}
                        onPreview={onPreview} onWritten={onWritten} onClose={() => setEdit(null)} />
                    </td></tr>
                  ) : null}
                </>
              );
            })}
          </tbody>
        </table>
      </div>
      {rows.length > PAGE ? (
        <div class="save-row">
          <button type="button" disabled={page === 0} onClick={() => setPage(page - 1)}>上一页</button>
          <span class="small muted">第 {page + 1} / {Math.ceil(rows.length / PAGE)} 页</span>
          <button type="button" disabled={(page + 1) * PAGE >= rows.length} onClick={() => setPage(page + 1)}>下一页</button>
        </div>
      ) : null}
    </section>
  );
}

function StateEditor({ edit, can, questId, onPreview, onWritten, onClose }: {
  edit: Extract<Edit, { kind: "interval" | "trial" }>; can: ReturnType<typeof editable>; questId: string;
  onPreview: (s: PreviewState) => void; onWritten: () => void; onClose: () => void;
}) {
  const isInterval = edit.kind === "interval";
  const original = isInterval ? can.frames : can.threshold;
  const [value, setValue] = useState(String(original ?? ""));
  const trial = edit.state.trial as any[] | null;
  const damage = Array.isArray(trial) && trial[0] === "DamageCheck";
  const chain = Array.isArray(trial) && trial[1]?.content?.[0] === "SkillChain";
  const n = Number(value);
  const problems: string[] = [];
  if (!Number.isInteger(n) || n < 1) problems.push(isInterval ? "帧数要是正整数（客户端按整数读取）" : "阈值要是正整数");
  else if (isInterval && n > 36000) problems.push("帧数最多 36000（10 分钟）");
  else if (damage && n > 100) problems.push("伤害百分比不超过 100");
  else if (chain && (n < 4 || n > 9)) problems.push("技能连锁阈值只能 4–9");
  else if (n === original) problems.push("和原值一样");
  const request: BehaviorRequest | null = {
    operation: "behavior_parameters", enemyCode: edit.enemy.enemyCode, state: edit.state.id,
    ...(edit.state.form !== undefined ? { form: edit.state.form } : {}),
    ...(isInterval ? { intervalFrames: n } : { trialThreshold: n }),
  };
  const op = useBossOp(questId, problems.length ? null : request, problems, onPreview, onWritten);
  return (
    <div class="param-block pending-block">
      <h4>{isInterval ? "改状态间隔" : "改试炼阈值"} · <span class="mono">{edit.state.id}</span>
        <button type="button" class="link close-x" onClick={onClose} aria-label="关闭">×</button></h4>
      <label class="param-field"><span>{isInterval ? "帧数（60 帧 = 1 秒）" : damage ? "伤害百分比" : "次数"}</span>
        <input type="number" min={1} step={1} value={value} onInput={(e) => setValue((e.target as HTMLInputElement).value)} />
        <span class="small muted">原 {original}{isInterval && Number.isFinite(n) ? ` · ${(n / 60).toFixed(2)} 秒` : ""}</span>
      </label>
      <p class="small muted">{isInterval ? "只改原生 TimeElapsed / Frame 定时终止；条件退出和循环不受影响。" : damage ? "DamageCheck 百分比（当前接口只收整数）。" : "HitCountCheck 常量次数；表达式型阈值不能改。"}
        改动写进这一关专属的 esdl 副本，原敌人资源不变。</p>
      <OpActions op={op} problems={problems} onReset={onClose} />
    </div>
  );
}

// ------------------------------------------------------------------------------------- player

const summaryOnce: Map<string, ReturnType<typeof timelineApi.bossMoves>> = new Map();

/** 「预览」: backend esdl timeline summary when present, else the move's DSL through /api/studio/timeline. */
function MovePlayer({ quest, move, onClose }: { quest: string; move: MoveRef; onClose: () => void }) {
  const box = useRef<HTMLElement>(null);
  useEffect(() => { box.current?.scrollIntoView({ block: "start", behavior: "smooth" }); }, []);
  const [timeline, setTimeline] = useState<Timeline | null>(null);
  const [source, setSource] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    setTimeline(null); setError(null);
    if (!summaryOnce.has(quest)) summaryOnce.set(quest, timelineApi.bossMoves(quest));
    summaryOnce.get(quest)!.then(async (summary) => {
      const hit = summary.available ? summary.moves.find((m: any) => m.name === move.path || m.program === move.path || m.path === move.path
        || (move.slot !== undefined && (m.slot === move.slot && (!m.enemyCode || m.enemyCode === move.enemy)))) : undefined;
      if (hit) { if (live) { setTimeline(hit.timeline); setSource("后端 esdl 时间轴摘要（timeline-summary）"); } return; }
      const t = await timelineApi.timeline(move.path, "subprogram");
      if (live) { setTimeline(t); setSource(summary.available ? "timeline-summary 里没有这一招，改用 DSL 路径直接解析" : "按出招 DSL 路径直接解析（/api/studio/timeline）"); }
    }).catch((e: Error) => { if (live) setError(e.message); });
    return () => { live = false; };
  }, [quest, move.path]);
  return (
    <section class="boss-block move-player" aria-label="出招预览" ref={box}>
      <header><h3>出招预览 · {move.label}</h3><span class="small muted">{source}</span><span class="spacer" />
        <button type="button" class="link close-x" onClick={onClose} aria-label="关闭">×</button></header>
      {error ? <Notice kind="error">解析失败：{error}</Notice> : !timeline ? <div class="loading">正在解析出招……</div> : (
        <>
          <p class="small muted">敌方出招：画面里的「伤害归属」标签对敌人不适用；主体「协力伙伴 / 自身」指 boss 的目标与自身。读的是当前基线视图里的程序，不含本草稿的换招。</p>
          <TimelinePlayer key={move.path} timeline={timeline} title={move.label} boss />
        </>
      )}
    </section>
  );
}
