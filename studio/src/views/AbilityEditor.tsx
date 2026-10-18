import { createContext } from "preact";
import { useContext, useEffect, useMemo, useRef, useState } from "preact/hooks";
import {
  ability, AbilityCheckResult, AbilityEntry, AbilityPreviewChange, AbilityState, AbilityTable, AbilityTextSections,
  ColumnLabel, drafts, onDraftChange, RowPreview, TemplateOption, TextPanel,
} from "../api";
import { Notice } from "./common";
import { RuleChips, ruleCounts, RuleList } from "./rules";
import {
  buildRequest, deleteRow, EMPTY_PENDING, entryId, insertRow, isAwake, moveRow, Pending, pendingCount, setCell,
  sharedId, tierLocked, tierOps, touches, workingRows,
} from "./abilityModel";

// ---------------------------------------------------------------------------
// Workspace: draft state + pending request, shared by 一板/二板/三板/技能 tabs.

export interface AbilityWorkspace {
  cid: string;
  state: AbilityState | null;
  error: string | null;
  pending: Pending;
  check: AbilityCheckResult | null;
  checking: boolean;
  committing: boolean;
  message: { kind: "info" | "error"; text: string } | null;
  /** Live wf text projection of pending panel-text edits (POST text/lint, never writes). */
  lint: TextPanel | null;
  linting: boolean;
  update: (fn: (p: Pending) => Pending) => void;
  discard: () => void;
  commit: () => Promise<void>;
  entry: (table: AbilityTable, key: string, level?: string | null) => AbilityEntry | undefined;
}

const Ctx = createContext<AbilityWorkspace | null>(null);
export const AbilityProvider = Ctx.Provider;
export function useWorkspace(): AbilityWorkspace | null {
  return useContext(Ctx);
}

export function useAbilityWorkspace(cid: string): AbilityWorkspace {
  const [state, setState] = useState<AbilityState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<Pending>(EMPTY_PENDING);
  const [check, setCheck] = useState<AbilityCheckResult | null>(null);
  const [checking, setChecking] = useState(false);
  const [committing, setCommitting] = useState(false);
  const [message, setMessage] = useState<AbilityWorkspace["message"]>(null);
  const sequence = useRef(0);
  const [lint, setLint] = useState<TextPanel | null>(null);
  const [linting, setLinting] = useState(false);
  const lintSeq = useRef(0);

  const reload = () => ability.state(cid).then((s) => { setState(s); setError(null); }, (e: Error) => setError(e.message));
  useEffect(() => {
    setState(null);
    setPending(EMPTY_PENDING);
    setCheck(null);
    reload();
    return onDraftChange((changed) => { if (changed === cid) reload(); });
  }, [cid]);

  // Live dry-run of the pending request (never writes).
  useEffect(() => {
    if (!state || !pendingCount(pending)) { setCheck(null); return; }
    const id = ++sequence.current;
    setChecking(true);
    const timer = setTimeout(() => {
      ability.check(cid, buildRequest(pending, state.entries)).then(
        (result) => { if (id === sequence.current) { setCheck(result); setChecking(false); } },
        (e: Error) => {
          if (id !== sequence.current) return;
          setCheck({ characterId: cid, changes: [], runtime: "未执行",
            checks: [{ rule: "studio.request", status: "问题", message: e.message, blocking: true }] });
          setChecking(false);
        });
    }, 350);
    return () => clearTimeout(timer);
  }, [pending, state]);

  // Live per-field wf text rules for pending panel text (desc_override / custom / skill c0,c1 / leader name).
  useEffect(() => {
    const sections = lintSections(pending);
    if (!sections) { setLint(null); setLinting(false); return; }
    const id = ++lintSeq.current;
    setLinting(true);
    const timer = setTimeout(() => {
      ability.lint(cid, sections).then(
        (result) => { if (id === lintSeq.current) { setLint(result); setLinting(false); } },
        () => { if (id === lintSeq.current) { setLint(null); setLinting(false); } });
    }, 450);
    return () => clearTimeout(timer);
  }, [pending.custom, pending.text, pending.leaderName]);

  const ws: AbilityWorkspace = {
    cid, state, error, pending, check, checking, committing, message, lint, linting,
    update: (fn) => { setMessage(null); setPending((p) => fn(p)); },
    discard: () => { setPending(EMPTY_PENDING); setMessage({ kind: "info", text: "已放弃未写入的修改。" }); },
    commit: async () => {
      if (!state || !pendingCount(pending)) return;
      setCommitting(true);
      setMessage(null);
      try {
        await ability.apply(cid, buildRequest(pending, state.entries));
        setPending(EMPTY_PENDING);
        setMessage({ kind: "info", text: "已写入草稿（work/studio-drafts）。到「本次修改」保存后即可生成。" });
      } catch (e) {
        setMessage({ kind: "error", text: (e as Error).message });
      } finally {
        setCommitting(false);
      }
    },
    entry: (table, key, level) => state?.entries.find((e) => e.table === table && e.key === key && (e.level ?? null) === (level ?? null)),
  };
  return ws;
}

// ---------------------------------------------------------------------------
// Pending bar (sticky): live check + 写入草稿 / 放弃

export function PendingBar() {
  const ws = useWorkspace();
  const count = ws ? pendingCount(ws.pending) : 0;
  const checks = ws?.check?.checks ?? [];
  const textProblems = ws ? lintProblems(ws) : [];
  const blocking = checks.some((c) => c.blocking || c.status === "问题") || textProblems.length > 0;
  const needShared = ws ? unconfirmedShared(ws) : [];
  const needTierConfirm = !!ws && tierOps(ws.pending).length > 0 && !ws.pending.tierConfirmed;
  const ready = !!ws && count > 0 && !blocking && !needShared.length && !needTierConfirm && !ws.checking
    && !ws.linting && !ws.committing;
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s" && count) {
        event.preventDefault();
        if (ready) ws!.commit();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });
  if (!ws || (!count && !ws.message)) return null;
  return (
    <div class={"pending-bar" + (count ? "" : " idle")} role="region" aria-label="未写入的词条修改">
      {count ? (
        <>
          <div class="pending-head">
            <strong>未写入 {count} 项</strong>
            <span class="small muted">（只在内存试算，写入后进草稿 changeset）</span>
            {ws.checking ? <span class="small muted">检查中……</span> : <RuleChips counts={ruleCounts(checks)} />}
            <span class="spacer" />
            <button onClick={ws.discard} disabled={ws.committing} title="放弃全部未写入修改">放弃</button>
            <button class="primary" onClick={() => ws.commit()} disabled={!ready}
              title={needShared.length ? "共享键需先勾选确认" : needTierConfirm ? "技能档位引用需先勾选确认"
                : blocking ? "检查有「问题」，先修正" : "写入草稿（Ctrl+S）"}>
              {ws.committing ? "写入中……" : "写入草稿 Ctrl+S"}
            </button>
          </div>
          {needShared.length ? <p class="small warn-text">共享键 {needShared.join("、")} 需要在对应卡片上勾选「确认修改共享键」。</p> : null}
          {needTierConfirm ? <p class="small warn-text">技能档位插入/删除：到「技能」页核对默认档位、玛纳节点与觉醒引用后勾选确认。</p> : null}
          {textProblems.length ? (
            <ul class="inline-problems">{textProblems.map((t) => <li>文案问题：{t}</li>)}</ul>
          ) : null}
          {ws.check ? <PendingChanges changes={ws.check.changes} /> : null}
          {ws.check ? (
            <details class="pending-rules" open={blocking}>
              <summary>五态检查（{checks.length} 条）</summary>
              <RuleList checks={checks} />
            </details>
          ) : null}
        </>
      ) : null}
      {ws.message ? <Notice kind={ws.message.kind === "error" ? "error" : "info"}>{ws.message.text}</Notice> : null}
    </div>
  );
}

export function unconfirmedShared(ws: AbilityWorkspace): string[] {
  const p = ws.pending;
  const keys = new Set<string>();
  for (const op of p.ops) keys.add(sharedId(op.table, op.key));
  for (const t of p.text) keys.add(sharedId("action_skill", t.key));
  for (const c of p.custom) keys.add(sharedId(c.section, c.key));
  for (const a of p.attach) keys.add(sharedId(a.table, a.key));
  return [...keys].filter((id) => {
    const [table, key] = id.split("/");
    const owners = p.owners[id] ?? ws.state?.entries.find((e) => e.table === table && e.key === key)?.owners ?? [];
    // Attaching another character's key makes it shared even when this character is not yet an owner.
    const attaching = p.attach.some((a) => sharedId(a.table, a.key) === id);
    const shared = attaching ? owners.some((o) => o !== ws.cid) : owners.length > 1;
    return shared && !p.sharedOk[id];
  });
}

/** Proposed panel text as wf text sections for the lint endpoint; null when nothing textual is pending. */
export function lintSections(p: Pending): AbilityTextSections | null {
  const sections: AbilityTextSections = {};
  for (const c of p.custom) (sections[c.section] ??= {})[c.key] = { old: c.old, new: c.new };
  for (const t of p.text) ((sections.action_skill ??= {})[t.level] ??= {})[t.column] = { old: t.old, new: t.new };
  if (p.leaderName) sections.character_text = { "10": p.leaderName };
  return Object.keys(sections).length ? sections : null;
}

/** Locations edited in this pending set (wf text location naming). */
export function editedLocations(p: Pending): Set<string> {
  const out = new Set<string>();
  for (const c of p.custom) out.add(`${c.section}.${c.key}`);
  for (const t of p.text) out.add(`action_skill.${t.level}.${t.column}`);
  return out;
}

/** 「问题」 on edited fields (wf text findings or editor house rules) block writing. */
function lintProblems(ws: AbilityWorkspace): string[] {
  if (!ws.lint) return [];
  const edited = editedLocations(ws.pending);
  const out: string[] = [];
  for (const field of ws.lint.fields) {
    if (!edited.has(field.location)) continue;
    for (const h of field.house) if (h.state === "问题") out.push(`${field.location}：${h.title}`);
    for (const f of field.findings) {
      if (f.state === "问题" && !field.house.some((h) => h.findings.some((g) => g.rule === f.rule))) {
        out.push(`${field.location}：${f.message}`);
      }
    }
  }
  return out;
}

const OP_LABEL: Record<string, string> = {
  set_cells: "改格", insert_row: "插入行", delete_row: "删除行", move_row: "移动行", attach_key: "换键",
};

function PendingChanges({ changes }: { changes: AbilityPreviewChange[] }) {
  const items = changes.filter((c) => c.op && OP_LABEL[c.op] || c.surface);
  const label = (c: AbilityPreviewChange) => c.table === "action_skill" && c.op && c.op !== "set_cells" && c.op !== "attach_key"
    ? OP_LABEL[c.op].replace("行", "档位") : OP_LABEL[c.op!];
  if (!items.length) return null;
  return (
    <details class="pending-changes">
      <summary>试算明细（含草稿已有操作，共 {items.length} 项）</summary>
      <ol>
        {items.map((c) => c.surface ? (
          <li><span class="tag">文本</span> <span class="mono small">{c.surface}{c.key ? " " + c.key : ""}</span>{" "}
            {c.client_old ?? c.old} → <strong>{c.new}</strong></li>
        ) : c.op === "attach_key" ? (
          <li><span class="tag">换键</span> <span class="mono small">{c.table} 槽{c.slot}：{c.old_key || "（空）"} → {c.key}</span></li>
        ) : (
          <li>
            <span class="tag">{label(c)}</span> <span class="mono small">{c.table}/{c.key}{c.level ? "#" + c.level : ""} 行{(c.row ?? 0) + 1}
              {c.op === "move_row" ? ` → 行${(c.to_row ?? 0) + 1}` : ""}</span>
            {c.beforeDescription !== undefined || c.afterDescription !== undefined ? (
              <div class="before-after small">
                <span class="muted">前：</span>{c.beforeDescription ?? "（无）"}<br />
                <span class="muted">后：</span>{c.afterDescription ?? "（删除）"}
              </div>
            ) : null}
          </li>
        ))}
      </ol>
    </details>
  );
}

// ---------------------------------------------------------------------------
// Key editor: effect cards with add/remove/reorder and field editing

export interface KeyEditorProps {
  table: AbilityTable;
  keyName: string;
  level?: string | null;
  title: string;
  columns: ColumnLabel[];
  /** Rows of the unmodified view (character detail), for 原/改 comparison. */
  baseRows: string[][];
  /** "base" = 一/二板（非觉醒行）, "awake" = 三板, "all" = 不筛选 */
  filter: "base" | "awake" | "all";
  override?: string | null;
  extra?: preact.ComponentChildren;
}

export function KeyEditor(props: KeyEditorProps) {
  const ws = useWorkspace();
  if (!ws) return null;
  if (ws.error) return <Notice kind="error">读取词条草稿态失败：{ws.error}</Notice>;
  const entry = ws.entry(props.table, props.keyName, props.level);
  if (!ws.state) return <div class="loading small">正在读取词条……</div>;
  if (!entry) return <Notice>键 {props.keyName} 不在当前角色的词条里（可能未配置）。</Notice>;
  return <KeyEditorBody {...props} ws={ws} entry={entry} />;
}

function KeyEditorBody(props: KeyEditorProps & { ws: AbilityWorkspace; entry: AbilityEntry }) {
  const { ws, entry, table } = props;
  const rows = workingRows(entry, ws.pending);
  const [picker, setPicker] = useState(false);
  const draftChanged = JSON.stringify(entry.rows) !== JSON.stringify(props.baseRows);
  const sid = sharedId(table, entry.key);
  const shared = entry.owners.length > 1;
  const pendingHere = touches(ws.pending, table, entry.key);
  const blockingHere = (ws.check?.checks ?? []).filter((c) => (c.blocking || c.status === "问题") && c.message.includes(entry.key)
    && !c.message.includes(`${table}/${entry.key}/`));
  const visible = rows.map((row, index) => ({ row, index }))
    .filter(({ row }) => props.filter === "all" || table !== "ability" || (props.filter === "awake") === isAwake(row));
  const hiddenCount = rows.length - visible.length;
  const structural = table !== "action_skill";
  const locked = tierLocked(ws.pending, table, entry.key);
  const update = (fn: (p: Pending) => Pending) => ws.update(fn);

  const move = (from: number, dir: -1 | 1) => {
    const pos = visible.findIndex((v) => v.index === from);
    const target = visible[pos + dir];
    if (!target) return;
    update((p) => moveRow(p, entry, rows, from, target.index));
  };

  return (
    <div class={"key-editor" + (pendingHere ? " has-pending" : "")}>
      <div class="key-meta">
        <span class="small muted">{table === "leader_ability" ? "队长技表 124 列" : table === "ability" ? "能力表 126 列" : `action_skill 档 ${entry.level}`}</span>
        {draftChanged ? <span class="pill warnpill" title="草稿里已有这个键的修改（未生成）">草稿已改</span> : null}
        {pendingHere ? <span class="pill pendingpill">未写入</span> : null}
        {shared ? <span class="pill bad" title={"持有者：" + entry.owners.join("、")}>共享键 · {entry.owners.length} 个角色</span> : null}
      </div>
      {shared ? (
        <div class="shared-confirm">
          <p>
            这个键同时属于 <span class="mono">{entry.owners.join("、")}</span>。
            修改会影响所有持有者{table === "action_skill" ? "（技能文本会同步到每个持有者）" : ""}，后端要求显式确认（shared_ok）。
          </p>
          <label class="check">
            <input type="checkbox" checked={!!ws.pending.sharedOk[sid]}
              onChange={(e) => update((p) => ({ ...p, sharedOk: { ...p.sharedOk, [sid]: (e.target as HTMLInputElement).checked } }))} />
            确认修改共享键（shared_ok）
          </label>
        </div>
      ) : null}
      {blockingHere.length ? (
        <ul class="inline-problems">{blockingHere.map((c) => <li>问题：{c.message}</li>)}</ul>
      ) : null}
      {locked ? (
        <Notice kind="warn">档位插入/删除还没写入：先在「技能档位」写入或撤销，再改档位里的格子（否则改动会落到挪动后的错档）。</Notice>
      ) : null}
      <ol class={"effect-cards" + (locked ? " locked" : "")}>
        {visible.map(({ row, index }, pos) => (
          <EffectCard key={entryId(table, entry.key, entry.level) + ":" + index + ":" + rows.length}
            ws={ws} entry={entry} rows={rows} index={index} row={row} columns={props.columns} locked={locked}
            base={props.baseRows[index]} sameShape={props.baseRows.length === rows.length}
            first={pos === 0} last={pos === visible.length - 1} structural={structural}
            onMove={(dir) => move(index, dir)}
            onDelete={() => update((p) => deleteRow(p, entry, rows, index))}
            onCell={(col, value) => update((p) => setCell(p, entry, rows, index, col, value))} />
        ))}
      </ol>
      {hiddenCount ? (
        <p class="small muted">另有 {hiddenCount} 行{props.filter === "awake" ? "非觉醒行在一/二板" : "觉醒行在三板"}编辑。</p>
      ) : null}
      {structural ? (
        <div class="key-actions">
          <button onClick={() => setPicker(true)} title="从 kind 枚举与先例模板添加一行效果">+ 添加效果</button>
          <span class="small muted">无先例的 kind 标「待验证」，仍可选择。</span>
        </div>
      ) : null}
      {picker ? (
        <TemplatePicker table={table as "ability" | "leader_ability"} rows={rows} awake={props.filter === "awake"}
          onClose={() => setPicker(false)}
          onPick={(values, at) => { update((p) => insertRow(p, entry, rows, at, values)); setPicker(false); }} />
      ) : null}
    </div>
  );
}

function EffectCard({ ws, entry, rows, index, row, columns, base, sameShape, first, last, structural, locked, onMove, onDelete, onCell }: {
  ws: AbilityWorkspace; entry: AbilityEntry; rows: string[][]; index: number; row: string[]; columns: ColumnLabel[];
  base?: string[]; sameShape: boolean; first: boolean; last: boolean; structural: boolean; locked?: boolean;
  onMove: (dir: -1 | 1) => void; onDelete: () => void; onCell: (col: number, value: string) => void;
}) {
  const after = afterDescription(ws, entry, index, row);
  const changedCols = sameShape && base ? row.map((v, i) => (v !== (base[i] ?? "") ? i : -1)).filter((i) => i >= 0) : [];
  const awake = entry.table === "ability" && isAwake(row);
  const label = (i: number) => columnLabel(entry.table, columns, i);
  // Columns named by a blocking finding for this exact row are shown even when empty.
  const problems = (ws.check?.checks ?? []).filter((c) => (c.blocking || c.status === "问题")
    && c.message.includes(`${entry.table}/${entry.key}/${index}:`));
  const problemCols = new Set(problems.flatMap((c) => [...c.message.matchAll(/\bc(\d+)\b/g)].map((m) => Number(m[1]))));
  const filled = row.map((v, i) => ({ v, i }))
    .filter(({ v, i }) => (v !== "" && v !== "(None)") || changedCols.includes(i) || problemCols.has(i));
  const isNew = !sameShape || !base;
  const onKey = (event: KeyboardEvent) => {
    if (!event.altKey || (event.target as HTMLElement).tagName === "INPUT") return;
    if (event.key === "ArrowUp" && !first && structural) { event.preventDefault(); onMove(-1); }
    if (event.key === "ArrowDown" && !last && structural) { event.preventDefault(); onMove(1); }
  };
  return (
    <li class="effect-card" tabIndex={0} onKeyDown={onKey} aria-label={`效果 ${index + 1}`}>
      <header>
        <span class="row-no">{entry.table === "action_skill" ? `档 ${entry.level}` : `效果 ${index + 1}`}</span>
        {awake ? <span class="tag awake">觉醒 c3={row[3]} Lv{row[4]}</span> : null}
        {changedCols.length ? <span class="pill warnpill">{changedCols.length} 格不同于原版</span> : null}
        {isNew && entry.table !== "action_skill" ? <span class="tag">结构已变</span> : null}
        <span class="spacer" />
        {structural ? (
          <span class="card-tools">
            <button class="icon" disabled={first} onClick={() => onMove(-1)} title="上移（Alt+↑）" aria-label="上移">↑</button>
            <button class="icon" disabled={last} onClick={() => onMove(1)} title="下移（Alt+↓）" aria-label="下移">↓</button>
            <button class="icon danger" disabled={rows.length <= 1} onClick={onDelete}
              title={rows.length <= 1 ? "不能删除键的最后一行" : "删除这一行效果"} aria-label="删除">✕</button>
          </span>
        ) : null}
      </header>
      <RowDescription ws={ws} entry={entry} index={index} after={after} draftDiffers={changedCols.length > 0 || isNew} />
      {problems.length ? <ul class="inline-problems">{problems.map((c) => <li>问题：{c.message}</li>)}</ul> : null}
      {entry.table === "ability" && index === 0 ? (
        changedCols.includes(1) || ws.pending.ops.some((o) => o.key === entry.key && o.row === 0 && o.cells.some((c) => c.column === "c1"))
          ? <p class="warn-text small">首行 c1（unisonable）已改：合击资格可能变化，检查会标「待验证」，请审阅。</p> : null
      ) : null}
      <div class="field-grid">
        {filled.map(({ v, i }) => (
          <CellInput label={label(i)} index={i} value={v} problem={problemCols.has(i)} base={sameShape && base ? base[i] ?? "" : undefined}
            text={entry.table === "action_skill" && i < 2} disabled={locked} onCommit={(value) => onCell(i, value)} />
        ))}
      </div>
      <details class="raw-advanced">
        <summary>高级：全部 {row.length} 列（含空列，按区块/字段标注）</summary>
        <table class="raw-table">
          <thead><tr><th>列</th><th>区块</th><th>字段</th><th>值</th></tr></thead>
          <tbody>
            {row.map((v, i) => {
              const l = columns[i];
              return (
                <tr class={(v === "" || v === "(None)" ? "empty " : "") + (changedCols.includes(i) ? "changed" : "")}>
                  <td class="mono">c{i}</td>
                  <td>{entry.table === "action_skill" ? (i < 2 ? "文本" : "") : l?.block ?? ""}</td>
                  <td title={l?.note ?? ""}>{entry.table === "action_skill" ? skillField(i) : l?.field ?? ""}</td>
                  <td><CellInput bare index={i} value={v} base={sameShape && base ? base[i] ?? "" : undefined}
                    text={entry.table === "action_skill" && i < 2} disabled={locked} onCommit={(value) => onCell(i, value)} /></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </details>
    </li>
  );
}

function skillField(i: number): string {
  return i === 0 ? "技能名（玩家可见）" : i === 1 ? "技能文案（玩家可见）" : "";
}

function columnLabel(table: AbilityTable, columns: ColumnLabel[], i: number): string {
  if (table === "action_skill") return skillField(i);
  const l = columns[i];
  if (!l) return `c${i}`;
  return `${l.block}·${l.field}`;
}

function CellInput({ label, index, value, base, text, bare, problem, disabled, onCommit }: {
  label?: string; index: number; value: string; base?: string; text?: boolean; bare?: boolean; problem?: boolean;
  disabled?: boolean; onCommit: (v: string) => void;
}) {
  const [local, setLocal] = useState(value);
  useEffect(() => setLocal(value), [value]);
  const changed = base !== undefined && value !== base;
  const commit = () => { if (local !== value) onCommit(local); };
  const input = (
    <input class={"cell" + (changed ? " changed" : "") + (text ? " text" : "") + (problem ? " problem" : "")} value={local} aria-label={label || `c${index}`}
      disabled={disabled}
      title={changed ? `原版：${base === "" ? "（空）" : base}` : text ? "玩家可见文本：按 wf text 面板规则检查" : `c${index}`}
      onInput={(e) => setLocal((e.target as HTMLInputElement).value)}
      onBlur={commit}
      onKeyDown={(e) => {
        if (e.key === "Enter") { e.preventDefault(); commit(); }
        if (e.key === "Escape") { e.stopPropagation(); setLocal(value); (e.target as HTMLInputElement).blur(); }
      }} />
  );
  if (bare) return input;
  return (
    <label class={"field" + (text ? " wide" : "")}>
      <span class="field-label"><span class="mono">c{index}</span> {label}</span>
      {input}
    </label>
  );
}

function afterDescription(ws: AbilityWorkspace, entry: AbilityEntry, index: number, row: string[]): string | null {
  // Latest dry-run description for this row if the pending request touched it.
  const changes = ws.check?.changes ?? [];
  for (let i = changes.length - 1; i >= 0; i--) {
    const c = changes[i];
    if (c.table === entry.table && c.key === entry.key && (c.level ?? null) === (entry.level ?? null) && c.row === index
        && (c.op === "set_cells" || c.op === "insert_row")) {
      return c.afterDescription ?? null;
    }
  }
  if (entry.table === "action_skill") return `${row[0] ?? ""} · ${row[1] ?? ""}`;
  const same = entry.rows.findIndex((r) => JSON.stringify(r) === JSON.stringify(row));
  return same >= 0 ? entry.descriptions[same] ?? null : null;
}

function RowDescription({ ws, entry, index, after, draftDiffers }: {
  ws: AbilityWorkspace; entry: AbilityEntry; index: number; after: string | null; draftDiffers: boolean;
}) {
  const [preview, setPreview] = useState<RowPreview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const draftRow = entry.rows[index];
  useEffect(() => {
    setPreview(null);
    setError(null);
    if (!draftDiffers || !draftRow || !drafts.hasToken()) return;
    ability.rowPreview(ws.cid, entry.table, entry.key, index, entry.level).then(setPreview, (e: Error) => setError(e.message));
  }, [ws.cid, entry.key, entry.level, index, JSON.stringify(draftRow), draftDiffers]);
  const pending = touches(ws.pending, entry.table, entry.key);
  const rowChanged = JSON.stringify(workingRows(entry, ws.pending)[index]) !== JSON.stringify(draftRow);
  return (
    <div class="row-desc">
      {preview && preview.before.description !== preview.after.description ? (
        <div class="before-after">
          <div><span class="ba-label">原版</span>{preview.before.description ?? "（无此行）"}</div>
          <div><span class="ba-label after">草稿</span>{preview.after.description ?? "（删除）"}</div>
        </div>
      ) : null}
      {pending && rowChanged ? (
        <div class="before-after">
          <div><span class="ba-label">当前</span>{draftRow ? entry.descriptions[index] ?? "（无法解析）" : "（新行）"}</div>
          <div><span class="ba-label pend">试算</span>{after ?? <em class="muted">{ws.checking || !ws.check ? "等待检查结果……" : "检查未通过，无法试算描述（见下方问题）"}</em>}</div>
        </div>
      ) : !preview || preview.before.description === preview.after.description || pending ? (
        <p class="effect-desc">{after ?? <em class="muted">（无法解析为中文描述）</em>}</p>
      ) : null}
      {error ? <p class="small error-text">预览失败：{error}</p> : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Template picker: kind enum + precedent defaults

const BLOCKS: { id: string; label: string }[] = [
  { id: "instant_content", label: "瞬发·效果" },
  { id: "during_content", label: "持续·效果" },
  { id: "instant_trigger", label: "瞬发·触发" },
  { id: "during_trigger", label: "持续·触发" },
  { id: "precondition1", label: "前置条件 1" },
  { id: "precondition2", label: "前置条件 2" },
  { id: "precondition3", label: "前置条件 3" },
];

function TemplatePicker({ table, rows, awake, onClose, onPick }: {
  table: "ability" | "leader_ability"; rows: string[][]; awake: boolean;
  onClose: () => void; onPick: (values: string[], at: number) => void;
}) {
  const [block, setBlock] = useState("instant_content");
  const [query, setQuery] = useState("");
  const [only, setOnly] = useState<"all" | "precedent" | "unverified">("all");
  const [list, setList] = useState<TemplateOption[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cursor, setCursor] = useState(0);
  const [at, setAt] = useState(rows.length);
  const search = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  useEffect(() => {
    setList(null);
    setError(null);
    ability.templates(table, block).then((t) => setList(t.options), (e: Error) => setError(e.message));
  }, [table, block]);
  useEffect(() => { search.current?.focus(); }, []);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (list ?? []).filter((o) => (only === "all" || (only === "precedent") === (o.precedentCount > 0))
      && (!q || o.kind === q || (o.cn ?? "").toLowerCase().includes(q) || (o.en ?? "").toLowerCase().includes(q)));
  }, [list, query, only]);
  useEffect(() => setCursor(0), [query, only, block]);
  useEffect(() => {
    listRef.current?.querySelector(".on")?.scrollIntoView({ block: "nearest" });
  }, [cursor]);
  const selected = filtered[cursor];

  const onKey = (event: KeyboardEvent) => {
    if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); onClose(); }
    if (event.key === "ArrowDown") { event.preventDefault(); setCursor((c) => Math.min(filtered.length - 1, c + 1)); }
    if (event.key === "ArrowUp") { event.preventDefault(); setCursor((c) => Math.max(0, c - 1)); }
    if (event.key === "Enter" && selected) { event.preventDefault(); onPick(selected.defaults, at); }
  };

  return (
    <div class="modal-backdrop" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div class="modal template-picker" role="dialog" aria-modal="true" aria-label="添加效果：选择 kind 模板" onKeyDown={onKey}>
        <header>
          <h3>添加效果 · {table === "leader_ability" ? "队长技" : "能力"}</h3>
          <span class="spacer" />
          <button class="ghost" onClick={onClose} aria-label="关闭">Esc</button>
        </header>
        <div class="picker-controls">
          <label>区块 <select value={block} onChange={(e) => setBlock((e.target as HTMLSelectElement).value)}>
            {BLOCKS.map((b) => <option value={b.id}>{b.label}</option>)}
          </select></label>
          <input ref={search} class="search" placeholder="kind 编号 / 中文 / 英文名" value={query}
            onInput={(e) => setQuery((e.target as HTMLInputElement).value)} />
          <div class="segmented">
            <button class={only === "all" ? "on" : ""} onClick={() => setOnly("all")}>全部</button>
            <button class={only === "precedent" ? "on" : ""} onClick={() => setOnly("precedent")}>有先例</button>
            <button class={only === "unverified" ? "on" : ""} onClick={() => setOnly("unverified")}>待验证</button>
          </div>
        </div>
        {error ? <Notice kind="error">{error}</Notice> : null}
        {!list && !error ? <div class="loading small">正在读取 kind 枚举与先例……</div> : null}
        {list ? (
          <div class="picker-body">
            <ul class="picker-list" ref={listRef} role="listbox" aria-label="kind 列表">
              {filtered.slice(0, 400).map((o, i) => (
                <li role="option" aria-selected={i === cursor} class={i === cursor ? "on" : ""}
                  onClick={() => setCursor(i)} onDblClick={() => onPick(o.defaults, at)}>
                  <span class="mono kind">{o.kind}</span>
                  <span class="kind-name">{o.cn || o.en}</span>
                  <span class={"rs " + (o.precedentCount ? "rs-ok" : "rs-warn")}>{o.precedentCount ? `先例 ${o.precedentCount}` : "待验证"}</span>
                </li>
              ))}
              {filtered.length > 400 ? <li class="muted small">还有 {filtered.length - 400} 项，请输入关键字缩小范围</li> : null}
              {!filtered.length ? <li class="muted small">没有匹配的 kind</li> : null}
            </ul>
            {selected ? (
              <div class="picker-detail">
                <h4>kind {selected.kind} · {selected.cn} <span class="muted mono small">{selected.en}</span></h4>
                {selected.precedentCount ? (
                  <p class="small">默认值取自当前视图先例 <span class="mono">{selected.precedents[0]?.key} 行{(selected.precedents[0]?.row ?? 0) + 1}</span>
                    （共 {selected.precedentCount} 处）；引用的对象（string_id、固有、程序等）需要核对。</p>
                ) : (
                  <Notice kind="warn">没有当前视图先例：仍可选择，参数和运行时效果「待验证」。默认行只填了区块 kind 与必需的默认值。</Notice>
                )}
                {awake ? <p class="small warn-text">三板插入的是普通行；觉醒替换/追加需要自己填 c3/c4。</p> : null}
                <details>
                  <summary>默认行中非空的列（{selected.defaults.filter((v) => v !== "" && v !== "(None)").length}）</summary>
                  <p class="mono small defaults">
                    {selected.defaults.map((v, i) => (v !== "" && v !== "(None)" ? `c${i}=${v}` : null)).filter(Boolean).join("  ")}
                  </p>
                </details>
                <div class="picker-insert">
                  <label>插入到 <select value={String(at)} onChange={(e) => setAt(Number((e.target as HTMLSelectElement).value))}>
                    {rows.map((_, i) => <option value={String(i)}>效果 {i + 1} 之前</option>)}
                    <option value={String(rows.length)}>末尾（效果 {rows.length + 1}）</option>
                  </select></label>
                  <button class="primary" onClick={() => onPick(selected.defaults, at)}>插入为新效果 Enter</button>
                </div>
                <p class="small muted">插入只进入「未写入」列表；下方会立即试算中文描述和五态检查，写入草稿前可继续改字段。</p>
              </div>
            ) : null}
          </div>
        ) : null}
      </div>
    </div>
  );
}
