// Pending ability edits: an ordered list of asserted operations plus merged
// skill-text edits. The backend replays the same request (AbilityEditor), so
// everything here is only a local projection for display.
import { AbilityEntry, AbilityOp, AbilityRequest, AbilityTable, AttachOp, TextPair } from "../api";

export interface TextEdit {
  key: string;
  column: "c0" | "c1";
  level: string;
  old: string;
  new: string;
}

/** Panel text edited through wf text: desc_override / custom_ability_string (client-only surfaces). */
export interface CustomEdit {
  section: "desc_override" | "custom_ability_string";
  key: string;
  old: string;
  new: string;
}

export interface Pending {
  ops: AbilityOp[];
  text: TextEdit[];
  custom: CustomEdit[];
  attach: AttachOp[];
  /** character_text c10 (wf text also syncs character c18 and both server mirrors). */
  leaderName: TextPair | null;
  sharedOk: Record<string, boolean>; // `${table}/${key}`
  /** All owners known for keys touched by custom/attach edits (sharedId → owners). */
  owners: Record<string, string[]>;
  /** Skill-tier insert/delete references reviewed by the user. */
  tierConfirmed: boolean;
  /** Second confirmation when the result leaves unawakened players without a tier they can reach. */
  tierRisk: boolean;
}

export const EMPTY_PENDING: Pending = {
  ops: [], text: [], custom: [], attach: [], leaderName: null, sharedOk: {}, owners: {}, tierConfirmed: false, tierRisk: false,
};

export function isTierOp(op: AbilityOp): boolean {
  return op.table === "action_skill" && (op.op === "insert_row" || op.op === "delete_row" || op.op === "move_row");
}

export function tierOps(p: Pending): AbilityOp[] {
  return p.ops.filter(isTierOp);
}

export function attachFor(p: Pending, table: AbilityTable, slot: number): AttachOp | undefined {
  return p.attach.find((a) => a.table === table && a.slot === slot);
}

export function setCustom(p: Pending, section: CustomEdit["section"], key: string, original: string, value: string,
  owners: string[]): Pending {
  const custom = p.custom.filter((c) => !(c.section === section && c.key === key));
  if (value !== original) custom.push({ section, key, old: original, new: value });
  return { ...p, custom, owners: { ...p.owners, [sharedId(section, key)]: owners } };
}

export function entryId(table: string, key: string, level?: string | null): string {
  return `${table}/${key}${level ? "#" + level : ""}`;
}

export function sharedId(table: string, key: string): string {
  return `${table}/${key}`;
}

export function isAwake(row: string[]): boolean {
  const kind = (row[3] ?? "").trim();
  const level = (row[4] ?? "").trim();
  return kind === "2" || (kind === "1" && /^\d+$/.test(level) && Number(level) >= 1);
}

export function colIndex(column: string): number {
  return Number(column.replace(/^c/, ""));
}

function sameTarget(op: AbilityOp, table: string, key: string, level?: string | null) {
  return op.table === table && op.key === key && (op.level ?? null) === (level ?? null);
}

/** Apply pending structural/cell ops to the draft-state rows (mirrors the backend semantics). */
export function workingRows(entry: AbilityEntry, pending: Pending): string[][] {
  let rows = entry.rows.map((r) => [...r]);
  for (const op of pending.ops) {
    if (isTierOp(op) || !sameTarget(op, entry.table, entry.key, entry.level)) continue;
    if (op.op === "set_cells") {
      const row = rows[op.row];
      if (row) for (const c of op.cells) row[colIndex(c.column)] = c.new ?? "";
    } else if (op.op === "insert_row") {
      const row: string[] = [];
      for (const c of op.cells) row[colIndex(c.column)] = c.new ?? "";
      rows.splice(op.row, 0, row);
    } else if (op.op === "delete_row") {
      rows.splice(op.row, 1);
    } else if (op.op === "move_row" && op.to_row !== undefined) {
      const [moved] = rows.splice(op.row, 1);
      rows.splice(op.to_row, 0, moved);
    }
  }
  if (entry.table === "action_skill") {
    for (const t of pending.text) {
      if (t.key === entry.key && t.level === entry.level && rows[0]) rows[0][colIndex(t.column)] = t.new;
    }
  }
  return rows;
}

/** Skill tier insert/delete/move pending on this key: tier cells are locked until written or undone. */
export function tierLocked(p: Pending, table: string, key: string): boolean {
  return table === "action_skill" && tierOps(p).some((o) => o.key === key);
}

export function setCell(p: Pending, entry: AbilityEntry, rows: string[][], row: number, column: number, value: string): Pending {
  const current = rows[row]?.[column] ?? "";
  if (current === value) return p;
  // Cell edits after a pending tier insert/delete would be replayed against the shifted tiers.
  if (tierLocked(p, entry.table, entry.key)) return p;
  if (entry.table === "action_skill" && column < 2) {
    const name = (column === 0 ? "c0" : "c1") as "c0" | "c1";
    const original = entry.rows[0]?.[column] ?? "";
    const text = p.text.filter((t) => !(t.key === entry.key && t.level === entry.level && t.column === name));
    if (value !== original) text.push({ key: entry.key, column: name, level: entry.level ?? "1", old: original, new: value });
    return { ...p, text };
  }
  const ops = [...p.ops];
  const last = ops[ops.length - 1];
  const name = "c" + column;
  if (last && last.op === "set_cells" && sameTarget(last, entry.table, entry.key, entry.level) && last.row === row) {
    const cells = last.cells.filter((c) => c.column !== name);
    const prior = last.cells.find((c) => c.column === name);
    const old = prior ? prior.old : current;
    if (old !== value) cells.push({ column: name, old, new: value });
    if (cells.length) ops[ops.length - 1] = { ...last, cells };
    else ops.pop();
    return { ...p, ops };
  }
  ops.push({ op: "set_cells", table: entry.table, key: entry.key, ...(entry.level ? { level: entry.level } : {}),
    row, row_count: rows.length, column_space: "native", cells: [{ column: name, old: current, new: value }] });
  return { ...p, ops };
}

export function insertRow(p: Pending, entry: AbilityEntry, rows: string[][], at: number, values: string[]): Pending {
  return { ...p, ops: [...p.ops, { op: "insert_row", table: entry.table, key: entry.key, row: at, row_count: rows.length,
    column_space: "native", cells: values.map((v, i) => ({ column: "c" + i, old: null, new: v })) }] };
}

export function deleteRow(p: Pending, entry: AbilityEntry, rows: string[][], at: number): Pending {
  return { ...p, ops: [...p.ops, { op: "delete_row", table: entry.table, key: entry.key, row: at, row_count: rows.length,
    column_space: "native", cells: rows[at].map((v, i) => ({ column: "c" + i, old: v, new: null })) }] };
}

export function moveRow(p: Pending, entry: AbilityEntry, rows: string[][], from: number, to: number): Pending {
  return { ...p, ops: [...p.ops, { op: "move_row", table: entry.table, key: entry.key, row: from, to_row: to,
    row_count: rows.length, column_space: "native", cells: rows[from].map((v, i) => ({ column: "c" + i, old: v, new: v })) }] };
}

/** Build the abilityRequest: numeric/structural ops in order, then skill text with every tier asserted. */
export function buildRequest(p: Pending, entries: AbilityEntry[]): AbilityRequest {
  const shared = (table: string, key: string) => p.sharedOk[sharedId(table, key)] === true;
  const operations: AbilityRequest["operations"] = p.ops.map((op) => (shared(op.table, op.key) ? { ...op, shared_ok: true } : op));
  for (const a of p.attach) operations.push(shared(a.table, a.key) ? { ...a, shared_ok: true } : a);
  const textKeys = [...new Set(p.text.map((t) => t.key))];
  for (const key of textKeys) {
    const tiers = entries.filter((e) => e.table === "action_skill" && e.key === key);
    const columns = [...new Set(p.text.filter((t) => t.key === key).map((t) => t.column))];
    for (const tier of tiers) {
      const cells = columns.map((column) => {
        const edit = p.text.find((t) => t.key === key && t.level === tier.level && t.column === column);
        const old = tier.rows[0]?.[colIndex(column)] ?? "";
        return { column, old, new: edit ? edit.new : old };
      });
      operations.push({ op: "set_cells", table: "action_skill", key, level: tier.level ?? "1", row: 0, row_count: 1,
        column_space: "native", cells, ...(shared("action_skill", key) ? { shared_ok: true } : {}) });
    }
  }
  const request: AbilityRequest = { operations };
  const text: NonNullable<AbilityRequest["text"]> = {};
  for (const c of p.custom) (text[c.section] ??= {})[c.key] = { old: c.old, new: c.new };
  if (p.leaderName) text.character_text = { "10": p.leaderName };
  if (Object.keys(text).length) request.text = text;
  // wf text takes one request-level shared_ok for panel strings; the UI requires each shared key confirmed.
  if (p.custom.some((c) => (p.owners[sharedId(c.section, c.key)] ?? []).length > 1 && shared(c.section, c.key))) {
    request.shared_ok = true;
  }
  return request;
}

export function pendingCount(p: Pending): number {
  return p.ops.length + p.text.length + p.custom.length + p.attach.length + (p.leaderName ? 1 : 0);
}

export function touches(p: Pending, table: string, key: string): boolean {
  return p.ops.some((o) => o.table === table && o.key === key) || (table === "action_skill" && p.text.some((t) => t.key === key));
}

/** Skill c0/c1 per tier (wf text); original is the draft-state value of that tier. */
export function setSkillText(p: Pending, key: string, level: string, column: "c0" | "c1", original: string, value: string): Pending {
  const text = p.text.filter((t) => !(t.key === key && t.level === level && t.column === column));
  if (value !== original) text.push({ key, column, level, old: original, new: value });
  return { ...p, text };
}

/** Replace any pending attach on the same slot; null clears it. */
export function setAttach(p: Pending, table: AbilityTable, slot: number, op: AttachOp | null, owners: string[] = []): Pending {
  const attach = p.attach.filter((a) => !(a.table === table && a.slot === slot));
  if (op) attach.push(op);
  const next = { ...p, attach };
  if (op) next.owners = { ...p.owners, [sharedId(table, op.key)]: owners };
  return next;
}
