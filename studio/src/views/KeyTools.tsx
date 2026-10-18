import { useEffect, useMemo, useRef, useState } from "preact/hooks";
import { ability, AbilityEntry, AbilityTable, AttachOp, KeySearchResult, RuleResult } from "../api";
import { Notice } from "./common";
import { useWorkspace } from "./AbilityEditor";
import { attachFor, Pending, setAttach, sharedId, tierOps, workingRows } from "./abilityModel";

// ---------------------------------------------------------------------------
// attach_key: 换键（挂现有键 / 复制为新键）on ability 1–6, leader (slot 0), skill (slot 0)

const TABLE_LABEL: Record<AbilityTable, string> = { ability: "能力", leader_ability: "队长技", action_skill: "技能" };

export function slotOf(table: AbilityTable, key: string, slots?: { ability: string[] }, hint?: number): number {
  if (table !== "ability") return 0;
  if (hint && hint >= 1 && hint <= 6) return hint;
  const index = slots?.ability.indexOf(key) ?? -1;
  return index >= 0 ? index + 1 : 0;
}

/** Card-header control: shows a pending attach for this slot, or opens the dialog. */
export function AttachControl({ table, slot, title }: { table: AbilityTable; slot: number; title: string }) {
  const ws = useWorkspace();
  const [open, setOpen] = useState(false);
  if (!ws?.state?.slots || (table === "ability" && !slot)) return null;
  const slots = ws.state.slots;
  const current = table === "ability" ? slots.ability[slot - 1] : table === "leader_ability" ? slots.leader_ability : slots.action_skill;
  const pending = attachFor(ws.pending, table, slot);
  const blocked = table === "action_skill" && (ws.pending.text.length > 0 || tierOps(ws.pending).length > 0);
  return (
    <span class="attach-control">
      {pending ? (
        <>
          <span class="pill pendingpill" title="未写入">换键 → <span class="mono">{pending.key}</span>{pending.rows || pending.levels ? "（新键）" : ""}</span>
          <button class="ghost small-btn" onClick={() => ws.update((p) => setAttach(p, table, slot, null))}>撤销换键</button>
        </>
      ) : (
        <button class="small-btn" disabled={blocked} onClick={() => setOpen(true)}
          title={blocked ? "技能文本或档位有未写入修改；换技能键需单独写入" : `给${title}挂接其它键或复制为新键`}>
          {current && current !== "(None)" ? "换键…" : "挂键…"}
        </button>
      )}
      {open ? <AttachDialog table={table} slot={slot} current={current} title={title} onClose={() => setOpen(false)} /> : null}
    </span>
  );
}

function AttachDialog({ table, slot, current, title, onClose }: {
  table: AbilityTable; slot: number; current: string; title: string; onClose: () => void;
}) {
  const ws = useWorkspace()!;
  const [mode, setMode] = useState<"existing" | "new">("existing");
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<KeySearchResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cursor, setCursor] = useState(0);
  const [confirmShared, setConfirmShared] = useState(false);
  const [newKey, setNewKey] = useState(current && current !== "(None)" ? current + "_m" : "");
  // wf text asserts the old leader name against character_text c10 (not the c18 copy).
  const oldLeaderName = ws.state?.slots?.leaderNameText ?? ws.state?.slots?.leaderName ?? "";
  const [leaderName, setLeaderName] = useState(oldLeaderName);
  // Unwritten edits on the current key: carry them into the copy (default) or write them first.
  const carried = ws.pending.ops.filter((o) => o.table === table && o.key === current);
  const [carry, setCarry] = useState(true);
  const [exists, setExists] = useState<{ key: string; found: boolean } | null>(null);
  const search = useRef<HTMLInputElement>(null);
  const seq = useRef(0);

  useEffect(() => { search.current?.focus(); }, [mode]);
  useEffect(() => {
    if (mode !== "existing") return;
    const id = ++seq.current;
    const timer = setTimeout(() => {
      ability.keys(table, query, ws.cid).then((r) => { if (id === seq.current) { setResult(r); setError(null); setCursor(0); } },
        (e: Error) => { if (id === seq.current) setError(e.message); });
    }, query ? 250 : 0);
    return () => clearTimeout(timer);
  }, [query, mode]);
  useEffect(() => setConfirmShared(false), [cursor, mode]);
  // Duplicate check for a new key: exact lookup of that name, not the last search page.
  useEffect(() => {
    if (mode !== "new" || !/^[A-Za-z0-9_]+$/.test(newKey)) { setExists(null); return; }
    const timer = setTimeout(() => {
      ability.keys(table, newKey, ws.cid).then((r) => setExists({ key: newKey, found: r.exact === newKey }), () => setExists(null));
    }, 200);
    return () => clearTimeout(timer);
  }, [newKey, mode]);

  const items = (result?.results ?? []).filter((r) => r.key !== current);
  const selected = items[cursor];
  const others = selected ? selected.owners.filter((o) => o.id !== ws.cid) : [];
  const currentEntries = ws.state?.entries.filter((e) => e.table === table && e.key === current) ?? [];
  const newExists = mode === "new" && !!newKey && exists?.key === newKey && exists.found;
  const keyPattern = /^[A-Za-z0-9_]+$/;
  const canNew = mode === "new" && keyPattern.test(newKey) && newKey !== current && currentEntries.length > 0
    && exists?.key === newKey && !exists.found && (!carried.length || carry);
  const canExisting = mode === "existing" && !!selected && (!others.length || confirmShared);

  const confirm = () => {
    let op: AttachOp;
    let owners: string[] = [];
    if (mode === "existing") {
      if (!canExisting) return;
      op = { op: "attach_key", table, key: selected.key, slot, old_key: current };
      owners = selected.owners.map((o) => o.id);
    } else {
      if (!canNew) return;
      // Copy the rows as they will be after the unwritten edits, and drop those edits from the old key.
      const source = currentEntries.map((e) => ({ ...e, rows: workingRows(e, ws.pending) }));
      op = { op: "attach_key", table, key: newKey, slot, old_key: current, column_space: "native", ...newRows(table, source) };
    }
    const moving = mode === "new" && carried.length > 0;
    ws.update((p: Pending) => {
      let next = moving ? { ...p, ops: p.ops.filter((o) => !(o.table === table && o.key === current)) } : p;
      next = setAttach(next, table, slot, op, owners);
      if (others.length && mode === "existing") next = { ...next, sharedOk: { ...next.sharedOk, [sharedId(table, op.key)]: true } };
      if (table === "leader_ability") next = { ...next, leaderName: leaderName !== oldLeaderName ? { old: oldLeaderName, new: leaderName } : null };
      return next;
    });
    onClose();
  };

  const onKey = (event: KeyboardEvent) => {
    if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); onClose(); }
    if (mode !== "existing") { if (event.key === "Enter" && (event.target as HTMLElement).tagName === "INPUT") { event.preventDefault(); confirm(); } return; }
    if (event.key === "ArrowDown") { event.preventDefault(); setCursor((c) => Math.min(items.length - 1, c + 1)); }
    if (event.key === "ArrowUp") { event.preventDefault(); setCursor((c) => Math.max(0, c - 1)); }
    if (event.key === "Enter" && (event.target as HTMLElement).tagName !== "BUTTON") { event.preventDefault(); confirm(); }
  };

  return (
    <div class="modal-backdrop" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div class="modal attach-dialog" role="dialog" aria-modal="true" aria-label={`换键：${title}`} onKeyDown={onKey}>
        <header>
          <h3>换键 · {title}</h3>
          <span class="muted small mono">{table} 槽 {slot}：{current || "（空）"}</span>
          <span class="spacer" />
          <button class="ghost" onClick={onClose} aria-label="关闭">Esc</button>
        </header>
        <div class="segmented">
          <button class={mode === "existing" ? "on" : ""} onClick={() => setMode("existing")}>挂现有键</button>
          <button class={mode === "new" ? "on" : ""} onClick={() => setMode("new")} disabled={!currentEntries.length}
            title={currentEntries.length ? "把当前键的全部行复制到新键再挂上（解开共享键的常用做法）" : "当前槽没有键可复制"}>复制为新键</button>
        </div>
        {mode === "existing" ? (
          <>
            <div class="picker-controls">
              <input ref={search} class="search" placeholder={`搜索${TABLE_LABEL[table]}键 / 持有角色名或 ID / 中文描述`} value={query}
                onInput={(e) => setQuery((e.target as HTMLInputElement).value)} />
              <span class="small muted">{result ? `匹配 ${result.total} 个键${result.total > items.length ? `，显示前 ${items.length} 个` : ""}` : "检索中……"}</span>
            </div>
            {error ? <Notice kind="error">{error}</Notice> : null}
            <div class="picker-body">
              <ul class="picker-list key-list" role="listbox" aria-label="键列表">
                {items.map((r, i) => (
                  <li role="option" aria-selected={i === cursor} class={i === cursor ? "on" : ""} onClick={() => setCursor(i)}
                    onDblClick={() => { setCursor(i); }}>
                    <span class="mono"><Highlight text={r.key} terms={result?.terms ?? []} /></span>
                    <span class="kind-name small"><Highlight text={r.owners.length ? r.owners.map((o) => o.name || o.id).join("、") : "无持有者"} terms={result?.terms ?? []} /></span>
                    <span class={"rs " + (r.owners.some((o) => o.id !== ws.cid) ? "rs-warn" : "rs-na")}>
                      {r.levels ? `${r.levels.length} 档` : `${r.rows} 行`}
                    </span>
                  </li>
                ))}
                {result && !items.length ? <li class="muted small">没有匹配的键</li> : null}
              </ul>
              {selected ? (
                <div class="picker-detail">
                  <h4 class="mono">{selected.key}</h4>
                  <p class="small">持有者：{selected.owners.length ? selected.owners.map((o) => `${o.name || "?"}（${o.id}）`).join("、") : "无（未挂在任何角色上）"}</p>
                  <ol class="small">{selected.descriptions.map((d, i) => (
                    <li value={(selected.descriptionRows?.[i] ?? i) + 1} class={selected.matches?.includes(selected.descriptionRows?.[i] ?? i) ? "hit" : ""}>
                      {d ? <Highlight text={d} terms={result?.terms ?? []} /> : "（无法解析）"}</li>
                  ))}</ol>
                  {selected.rows > selected.descriptions.length ? <p class="small muted">另有 {selected.rows - selected.descriptions.length} 行未列出。</p> : null}
                  {others.length ? (
                    <div class="shared-confirm">
                      <p>挂上后该键由 {others.length + 1} 个角色共享；之后改它会影响 {others.map((o) => o.name || o.id).join("、")}。</p>
                      <label class="check"><input type="checkbox" checked={confirmShared}
                        onChange={(e) => setConfirmShared((e.target as HTMLInputElement).checked)} /> 确认挂接共享键（shared_ok）</label>
                    </div>
                  ) : null}
                  {table === "action_skill" && selected.levels && currentEntries.length !== selected.levels.length ? (
                    <p class="warn-text small">档位数 {currentEntries.length} → {selected.levels.length}：玛纳技能进化节点和觉醒档位要按新档数核对。</p>
                  ) : null}
                </div>
              ) : null}
            </div>
          </>
        ) : (
          <div class="picker-detail new-key">
            <label>新键名 <input ref={search} class="wide-input mono" value={newKey}
              onInput={(e) => setNewKey((e.target as HTMLInputElement).value.trim())} /></label>
            <p class="small muted">复制当前键 <span class="mono">{current}</span> 的 {table === "action_skill" ? `${currentEntries.length} 档` : `${currentEntries[0]?.rows.length ?? 0} 行`}，
              每格以「新键不存在」断言写入，然后挂到本槽；原键保留给其它持有者。新键名只用字母、数字、下划线。</p>
            {newKey && !keyPattern.test(newKey) ? <p class="error-text small">键名含不允许的字符。</p> : null}
            {newExists ? <p class="error-text small">已有同名键；请改名或改用「挂现有键」。</p> : null}
            {carried.length ? (
              <div class="shared-confirm">
                <p>当前键 <span class="mono">{current}</span> 上有 {carried.length} 处未写入的修改。</p>
                <label class="check"><input type="checkbox" checked={carry} onChange={(e) => setCarry((e.target as HTMLInputElement).checked)} />
                  把这些修改带到新键（旧键保持原样，不影响其它持有者）</label>
                {!carry ? <p class="small warn-text">不带过去就要先写入或放弃这些修改，再复制为新键。</p> : null}
              </div>
            ) : null}
            <p class="small warn-text">关联的覆盖文案（desc_override_*）按键名/引用查找，新键可能不再带出原来的覆盖文案，写入后到「文案」页核对。</p>
          </div>
        )}
        {table === "leader_ability" ? (
          <div class="leader-sync">
            <p class="warn-text small">换队长技键后要同步队长名：character c18 与 character_text c10（两份服务端镜像随 wf text 同步）。后端会标「待验证」提醒。</p>
            <label>队长名<InfoTipInline text="写入 character_text c10，并同步 character c18 与两份服务端镜像" />
              <input class="wide-input" value={leaderName} onInput={(e) => setLeaderName((e.target as HTMLInputElement).value)} /></label>
          </div>
        ) : null}
        <div class="picker-insert">
          <span class="spacer" />
          <button onClick={onClose}>取消</button>
          <button class="primary" disabled={mode === "existing" ? !canExisting : !canNew || newExists} onClick={confirm}>
            加入未写入 Enter
          </button>
        </div>
        <p class="small muted">只进入「未写入」列表；下方会试算并做旧值断言（old_key = 当前槽值）。</p>
      </div>
    </div>
  );
}

/** Marks every case-insensitive occurrence of the search terms. */
export function Highlight({ text, terms }: { text: string; terms: string[] }) {
  const words = terms.filter(Boolean);
  if (!words.length || !text) return <>{text}</>;
  const lower = text.toLowerCase();
  const marks: boolean[] = new Array(text.length).fill(false);
  for (const w of words) {
    for (let at = lower.indexOf(w); at >= 0; at = lower.indexOf(w, at + 1)) for (let i = at; i < at + w.length; i++) marks[i] = true;
  }
  const parts: preact.ComponentChildren[] = [];
  let start = 0;
  for (let i = 1; i <= text.length; i++) {
    if (i === text.length || marks[i] !== marks[start]) {
      const piece = text.slice(start, i);
      parts.push(marks[start] ? <mark>{piece}</mark> : piece);
      start = i;
    }
  }
  return <>{parts}</>;
}

function newRows(table: AbilityTable, entries: AbilityEntry[]): Pick<AttachOp, "rows" | "levels"> {
  const cells = (row: string[]) => row.map((v, i) => ({ column: "c" + i, old: null, new: v }));
  if (table === "action_skill") {
    const levels: Record<string, ReturnType<typeof cells>[]> = {};
    for (const e of entries) levels[e.level ?? "1"] = e.rows.map(cells);
    return { levels };
  }
  return { rows: entries[0].rows.map(cells) };
}

function InfoTipInline({ text }: { text: string }) {
  return <span class="info-tip" title={text} aria-label={text}>ⓘ</span>;
}

// ---------------------------------------------------------------------------
// Skill tiers: insert (copy a tier) / delete, with the backend's reference report

export function SkillTiers() {
  const ws = useWorkspace();
  if (!ws?.state) return null;
  const tiers = ws.state.entries.filter((e) => e.table === "action_skill").sort((a, b) => Number(a.level) - Number(b.level));
  if (!tiers.length) return null;
  const key = tiers[0].key;
  const pending = tierOps(ws.pending);
  const cellEdits = ws.pending.ops.some((o) => o.table === "action_skill" && o.op === "set_cells");
  const locked = ws.pending.text.length > 0 || ws.pending.attach.some((a) => a.table === "action_skill") || cellEdits
    ? "技能文本、技能格或技能键有未写入修改，档位结构需另起一次写入。" : pending.length ? "一次只改一处档位结构；写入或放弃后再继续。" : null;
  const shared = tiers[0].owners.length > 1;
  const sid = sharedId("action_skill", key);

  const insertAfter = (index: number) => ws.update((p) => ({
    ...p, tierConfirmed: false, tierRisk: false, ops: [...p.ops, {
      op: "insert_row", table: "action_skill", key, level: String(index + 2), row: 0, row_count: tiers.length,
      column_space: "native", cells: tiers[index].rows[0].map((v, i) => ({ column: "c" + i, old: null, new: v })),
    }],
  }));
  const remove = (index: number) => ws.update((p) => ({
    ...p, tierConfirmed: false, tierRisk: false, ops: [...p.ops, {
      op: "delete_row", table: "action_skill", key, level: String(index + 1), row: 0, row_count: tiers.length,
      column_space: "native", cells: tiers[index].rows[0].map((v, i) => ({ column: "c" + i, old: v, new: null })),
    }],
  }));
  const cancel = () => ws.update((p) => ({ ...p, tierConfirmed: false, tierRisk: false, ops: p.ops.filter((o) => !(o.table === "action_skill" && o.op !== "set_cells")) }));

  const projected = tiers.map((t) => ({ label: `档 ${t.level}`, name: t.rows[0]?.[0] ?? "", from: t.level }));
  for (const op of pending) {
    const at = Number(op.level) - 1;
    if (op.op === "insert_row") projected.splice(at, 0, { label: "新档", name: op.cells[0]?.new ?? "", from: null as any });
    if (op.op === "delete_row") projected.splice(at, 1);
  }
  const reference = (ws.check?.checks ?? []).find((c) => c.rule === "ability.skill-tier-references") as TierReference | undefined;
  const missingTiers = Object.entries(reference?.missingUnawakenedTiers ?? {}).filter(([, tiers]) => tiers.length);

  return (
    <article class="ability tier-panel">
      <header>
        <h3>技能档位</h3>
        <span class="muted key">键 {key} · {tiers.length} 档</span>
        {shared ? <span class="pill bad">共享 · {tiers[0].owners.join("、")}</span> : null}
      </header>
      <p class="small muted">档位 = 技能进化阶段（默认 1 档，玛纳「技能进化」节点每个 +1，觉醒另计），与数值 SLv 无关。插入复制所选档的全部 {tiers[0].rows[0]?.length ?? 0} 列；
        插删后服务端镜像的技能名/描述列一起平移。最多 3 档。</p>
      <ol class="tier-list">
        {tiers.map((t, i) => (
          <li>
            <span class="row-no">档 {t.level}</span> <strong>{t.rows[0]?.[0]}</strong>
            <span class="spacer" />
            <button class="small-btn" disabled={!!locked || tiers.length >= 3} onClick={() => insertAfter(i)}
              title={tiers.length >= 3 ? "已达三档上限" : `在档 ${t.level} 之后插入一档（复制档 ${t.level}）`}>在后面插入</button>
            <button class="small-btn danger" disabled={!!locked || tiers.length <= 1} onClick={() => remove(i)}
              title={tiers.length <= 1 ? "不能删掉唯一一档" : `删除档 ${t.level}`}>删除</button>
          </li>
        ))}
      </ol>
      {locked && !pending.length ? <p class="small muted">{locked}</p> : null}
      {pending.length ? (
        <div class="tier-pending">
          <p><strong>未写入：</strong>{pending.map((op) => op.op === "insert_row" ? `在第 ${op.level} 档位置插入（复制前一档）` : `删除档 ${op.level}`).join("；")}
            → 结果 {projected.length} 档：{projected.map((p) => `${p.label}「${p.name}」`).join(" / ")}
            <button class="ghost small-btn" onClick={cancel}>撤销</button></p>
          {shared ? (
            <label class="check"><input type="checkbox" checked={!!ws.pending.sharedOk[sid]}
              onChange={(e) => ws.update((p) => ({ ...p, sharedOk: { ...p.sharedOk, [sid]: (e.target as HTMLInputElement).checked } }))} />
              确认修改共享技能键（shared_ok）</label>
          ) : null}
          {reference ? <TierReferences check={reference} /> : <p class="small muted">{ws.checking ? "正在试算档位引用……" : "试算未返回档位引用（见下方检查问题）。"}</p>}
          {missingTiers.length ? (
            <label class="check confirm-line danger-line">
              <input type="checkbox" checked={ws.pending.tierRisk}
                onChange={(e) => ws.update((p) => ({ ...p, tierRisk: (e.target as HTMLInputElement).checked, tierConfirmed: false }))} />
              我明白：未觉醒的玩家会缺第 {[...new Set(missingTiers.flatMap(([, t]) => t))].join("、")} 档（技能进化到那里时取不到档位）
            </label>
          ) : null}
          <label class="check confirm-line">
            <input type="checkbox" checked={ws.pending.tierConfirmed} disabled={!reference || (missingTiers.length > 0 && !ws.pending.tierRisk)}
              onChange={(e) => ws.update((p) => ({ ...p, tierConfirmed: (e.target as HTMLInputElement).checked }))} />
            我已核对默认档位、玛纳节点与觉醒引用（不读取玩家存档）
          </label>
        </div>
      ) : null}
    </article>
  );
}

interface TierRef {
  kind: string; character: string; source?: string; path?: string[]; nodeId?: string; message: string;
  event?: unknown; nodes?: { path: string[]; nodeId: string }[]; level?: number;
}
interface TierReference extends RuleResult {
  beforeCount: number; afterCount: number; references: TierRef[]; unavailableSources: string[];
  maxUnawakenedTier: Record<string, number>; missingUnawakenedTiers: Record<string, number[]>; coverage: string;
}

const REF_KIND: Record<string, string> = {
  default: "默认档位", mana_skill_evolution: "玛纳·技能进化", mana_skill_level: "玛纳·SLv 强化", awakening: "觉醒",
};

function TierReferences({ check }: { check: TierReference }) {
  const byCharacter = useMemo(() => {
    const out: Record<string, TierRef[]> = {};
    for (const r of check.references) (out[r.character] ??= []).push(r);
    return out;
  }, [check]);
  const missing = Object.entries(check.missingUnawakenedTiers ?? {}).filter(([, tiers]) => tiers.length);
  return (
    <div class="tier-refs">
      <p class="small"><span class="rs rs-warn">{check.status}</span> 档位 {check.beforeCount} → {check.afterCount}；覆盖范围：{check.coverage}</p>
      {missing.length ? (
        <Notice kind="error">
          {missing.map(([cid, tiers]) => `${cid}：未觉醒时最多可进化到 ${check.maxUnawakenedTier[cid]} 档，结果缺第 ${tiers.join("、")} 档`).join("；")}
        </Notice>
      ) : null}
      {check.unavailableSources?.length ? <p class="small warn-text">缺引用表：{check.unavailableSources.join("、")}</p> : null}
      {Object.entries(byCharacter).map(([cid, refs]) => (
        <table class="compare-table">
          <caption class="small">角色 {cid}（最高未觉醒档 {check.maxUnawakenedTier?.[cid] ?? "?"}）</caption>
          <thead><tr><th>引用</th><th>位置</th><th>说明</th></tr></thead>
          <tbody>
            {refs.map((r) => (
              <tr class={r.kind === "mana_skill_evolution" ? "hl" : ""}>
                <td>{REF_KIND[r.kind] ?? r.kind}</td>
                <td class="mono small">{r.path ? `${r.path.join("/")} 节点 ${r.nodeId}` : r.nodes ? r.nodes.map((n) => n.nodeId).join("、") || "—" : r.source ?? ""}</td>
                <td class="small">{r.message}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ))}
    </div>
  );
}
