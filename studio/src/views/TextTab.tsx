import { useEffect, useRef, useState } from "preact/hooks";
import { ability, onDraftChange, TextField, TextPanel, TextRuleRecord } from "../api";
import { Notice } from "./common";
import { editedLocations, useWorkspace } from "./AbilityEditor";
import { setCustom, setSkillText, sharedId, tierOps } from "./abilityModel";

// 文案：desc_override / custom_ability_string / 技能 c0·c1（每档）/ 队长名。
// Reads GET /api/characters/<cid>/text (draft state, both server mirrors). Edits
// join the shared pending request (abilityRequest.text / asserted skill ops), so
// the write still goes through wf text and AbilityEditor.apply.

const STATE_CLASS: Record<string, string> = { 问题: "rs-bad", 待验证: "rs-warn", 未执行: "rs-none", 满足: "rs-ok", 不适用: "rs-na" };

export function TextTab({ characterId }: { characterId: string }) {
  const ws = useWorkspace();
  const [panel, setPanel] = useState<TextPanel | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = () => ability.text(characterId).then((p) => { setPanel(p); setError(null); }, (e: Error) => setError(e.message));
  useEffect(() => {
    setPanel(null);
    load();
    return onDraftChange((changed) => { if (changed === characterId) load(); });
  }, [characterId]);

  if (error) {
    return <Notice kind="error">读取文案失败：{error}{/server_dir|服务端镜像/.test(error) ? "（启动编辑台时需加 --server-dir 指向服务端镜像根）" : ""}</Notice>;
  }
  if (!panel || !ws) return <div class="loading">正在读取文案与两份服务端镜像……（约 3 秒）</div>;

  const live = ws.lint;
  const view = (location: string): TextField | undefined =>
    live?.fields.find((f) => f.location === location) ?? panel.fields.find((f) => f.location === location);
  const skill = panel.fields.filter((f) => f.surface === "action_skill");
  const overrides = panel.fields.filter((f) => f.surface === "desc_override");
  const custom = panel.fields.filter((f) => f.surface === "custom_ability_string");
  const tiers = [...new Set(skill.map((f) => f.tier!))].sort();
  const p = ws.pending;
  const skillLocked = tierOps(p).length > 0 || p.attach.some((a) => a.table === "action_skill")
    ? "技能档位或技能键有未写入的修改；技能文本请在写入后另起一次修改。" : null;
  const skillShared = panel.skillOwners.length > 1;
  const houseTotals = summarize(panel.fields.map((f) => view(f.location) ?? f));

  return (
    <div class="board text-tab">
      <p class="hint">
        写入走 wf text：技能 c0/c1 同时改 action_skill、客户端 character_text 镜像列与两份服务端镜像（character_text.json /
        character_text_rank_p5b.json，仅生成交付时写入 server/）；desc_override、custom_ability_string 是客户端专属表面。
        检查依据「{panel.standard.name}」规则 v{panel.standard.version}；「待验证」= 规则只覆盖列举写法，须人工核对，不算通过。
        <br />快捷键：Ctrl+Enter 确认当前文本框，Esc 还原，Ctrl+S 写入草稿。
      </p>
      <div class="house-summary" aria-label="作者规则汇总">
        {panel.houseRules.map((h) => (
          <span class={"house-chip " + (STATE_CLASS[houseTotals[h.id] ?? "满足"] ?? "")} title={h.requirement}>
            {houseTotals[h.id] ?? "满足"} · {h.title}
          </span>
        ))}
        {ws.linting ? <span class="small muted">文案检查中……</span> : null}
      </div>

      <article class="ability">
        <header>
          <h3>技能文本（每档 c0 名称 / c1 描述）</h3>
          <span class="muted key">键 {panel.skillKey}</span>
          {skillShared ? <span class="pill bad">共享 · {panel.skillOwners.join("、")}</span> : null}
        </header>
        {skillLocked ? <Notice kind="warn">{skillLocked}</Notice> : null}
        {skillShared ? <SharedConfirm id={sharedId("action_skill", panel.skillKey)} owners={panel.skillOwners} /> : null}
        <p class="small muted">各档写法须一致（数值差异可以）；技能描述只写本体，不重复队长技/能力里的强化效果。改任一档都会对全部档位带旧值断言。</p>
        <div class="tier-grid">
          {tiers.map((tier) => (
            <section class="tier-text">
              <h4>档 {tier}</h4>
              {(["c0", "c1"] as const).map((column) => {
                const field = view(`action_skill.${tier}.${column}`)!;
                const original = panel.fields.find((f) => f.location === field.location)!.value;
                const pendingValue = p.text.find((t) => t.key === panel.skillKey && t.level === tier && t.column === column)?.new;
                return (
                  <TextFieldEditor field={field} label={column === "c0" ? "技能名" : "技能描述"} multiline={column === "c1"}
                    value={pendingValue ?? original} original={original} disabled={!!skillLocked}
                    edited={editedLocations(p).has(field.location)}
                    onChange={(value) => ws.update((q) => setSkillText(q, panel.skillKey, tier, column, original, value))} />
                );
              })}
            </section>
          ))}
        </div>
        <ServerCompare panel={live ?? panel} />
      </article>

      <article class="ability">
        <header>
          <h3>能力 / 队长技覆盖文案（desc_override）</h3>
          <span class="tag">{overrides.length} 条</span>
        </header>
        <p class="small muted">覆盖文案替换游戏面板对数据行的自动描述，只写满级数值；一行一条，句末不加句号；队长槽不写「自身为队长时」。</p>
        {overrides.length ? overrides.map((f) => (
          <CustomEditor field={view(f.location) ?? f} original={f.value} owners={f.owners} label={f.slot ?? ""} />
        )) : <Notice>这个角色没有覆盖文案键；面板显示数据行自动描述。新建覆盖键不在本页范围。</Notice>}
      </article>

      <article class="ability">
        <header>
          <h3>技能强化效果与其它关联文本（custom_ability_string）</h3>
          <span class="tag">{custom.length} 条</span>
        </header>
        <p class="small muted">change_skill_* 是技能强化效果文本（强化『技能名』：定性说明，不写数字）。面板规范第 1–8 节只约束 desc_override，这里检查恒真条件、「…之核」命名以及与技能描述的重复。</p>
        {custom.length ? custom.map((f) => (
          <CustomEditor field={view(f.location) ?? f} original={f.value} owners={f.owners} label={f.enhancement ? "技能强化效果" : "关联文本"} />
        )) : <Notice>没有关联的 custom_ability_string 键。</Notice>}
      </article>

      <LeaderName panel={panel} />

      {(live ?? panel).general.length ? (
        <article class="ability">
          <header><h3>其它检查</h3></header>
          <FindingList findings={(live ?? panel).general} />
        </article>
      ) : null}
    </div>
  );
}

function summarize(fields: TextField[]): Record<string, string> {
  const order = ["满足", "待验证", "问题"];
  const out: Record<string, string> = {};
  for (const f of fields) for (const h of f.house) {
    if (order.indexOf(h.state) > order.indexOf(out[h.id] ?? "满足")) out[h.id] = h.state;
  }
  return out;
}

function SharedConfirm({ id, owners }: { id: string; owners: string[] }) {
  const ws = useWorkspace()!;
  return (
    <div class="shared-confirm">
      <p>这个键同时属于 <span class="mono">{owners.join("、")}</span>，修改会同步到每个持有者。</p>
      <label class="check">
        <input type="checkbox" checked={!!ws.pending.sharedOk[id]}
          onChange={(e) => ws.update((p) => ({ ...p, sharedOk: { ...p.sharedOk, [id]: (e.target as HTMLInputElement).checked } }))} />
        确认修改共享键（shared_ok）
      </label>
    </div>
  );
}

function CustomEditor({ field, original, owners, label }: { field: TextField; original: string; owners: string[]; label: string }) {
  const ws = useWorkspace()!;
  const section = field.surface as "desc_override" | "custom_ability_string";
  const pendingValue = ws.pending.custom.find((c) => c.section === section && c.key === field.key)?.new;
  const shared = owners.length > 1;
  return (
    <div class="custom-text">
      <div class="key-meta">
        <span class="mono small">{field.key}</span>
        {label ? <span class="tag">{label}</span> : null}
        {shared ? <span class="pill bad" title={"持有者：" + owners.join("、")}>共享 · {owners.length} 个角色</span> : null}
      </div>
      {shared ? <SharedConfirm id={sharedId(section, field.key)} owners={owners} /> : null}
      <TextFieldEditor field={field} label="" multiline value={pendingValue ?? original} original={original}
        edited={editedLocations(ws.pending).has(field.location)}
        onChange={(value) => ws.update((p) => setCustom(p, section, field.key, original, value, owners))} />
    </div>
  );
}

function TextFieldEditor({ field, label, value, original, multiline, disabled, edited, onChange }: {
  field: TextField; label: string; value: string; original: string; multiline?: boolean; disabled?: boolean;
  edited: boolean; onChange: (value: string) => void;
}) {
  const [local, setLocal] = useState(value);
  const timer = useRef<number | undefined>(undefined);
  useEffect(() => setLocal(value), [value]);
  const commit = (next: string) => { window.clearTimeout(timer.current); if (next !== value) onChange(next); };
  const onInput = (next: string) => {
    setLocal(next);
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => commit(next), 500);
  };
  const onKey = (e: KeyboardEvent) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey || !multiline)) { e.preventDefault(); commit(local); }
    if (e.key === "Escape") { e.stopPropagation(); window.clearTimeout(timer.current); setLocal(value); }
  };
  const changedFromDraft = local !== original;
  const differsFromBase = field.base !== null && field.base !== undefined && field.base !== original;
  const props = {
    class: "text-input" + (changedFromDraft ? " changed" : "") + (field.house.some((h) => h.state === "问题") && edited ? " problem" : ""),
    value: local, disabled, "aria-label": `${label || field.key} ${field.location}`,
    onInput: (e: Event) => onInput((e.target as HTMLInputElement).value),
    onBlur: () => commit(local), onKeyDown: onKey,
  };
  return (
    <div class="text-field">
      {label ? <span class="field-label"><span class="mono">{field.field}</span> {label}</span> : null}
      {multiline ? <textarea rows={Math.min(8, Math.max(2, local.split("\n").length + 1, Math.ceil(local.length / 64) + 1))} {...props} /> : <input {...props} />}
      {changedFromDraft ? <p class="small muted was">草稿当前：{original || "（空）"}</p> : null}
      {differsFromBase ? <p class="small muted was">官方/原版：{field.base || "（空）"}</p> : null}
      <FieldRules field={field} edited={edited} />
    </div>
  );
}

function FieldRules({ field, edited }: { field: TextField; edited: boolean }) {
  const problems = field.findings.filter((f) => f.state === "问题");
  const reviews = field.findings.filter((f) => f.state === "待验证");
  const counts: Record<string, number> = {};
  for (const r of field.rules) counts[r.state] = (counts[r.state] ?? 0) + 1;
  return (
    <div class={"field-rules" + (edited ? " edited" : "")}>
      <div class="house-row">
        {field.house.map((h) => (
          <span class={"house-chip " + (STATE_CLASS[h.state] ?? "")} title={h.requirement}>{h.state} · {h.title}</span>
        ))}
      </div>
      {problems.length || reviews.length ? <FindingList findings={[...problems, ...reviews]} /> : null}
      {field.rules.length ? (
        <details class="std-rules">
          <summary>
            面板规范 {field.rules.length} 条：
            {["问题", "待验证", "满足"].filter((s) => counts[s]).map((s) => <span class={"rs " + STATE_CLASS[s]}>{s} {counts[s]}</span>)}
          </summary>
          <ul>{sortRules(field.rules).map((r) => <RuleLine rule={r} />)}</ul>
        </details>
      ) : null}
    </div>
  );
}

function sortRules(rules: TextRuleRecord[]): TextRuleRecord[] {
  const order = ["问题", "待验证", "满足"];
  return [...rules].sort((a, b) => order.indexOf(a.state) - order.indexOf(b.state));
}

function RuleLine({ rule }: { rule: TextRuleRecord }) {
  return (
    <li class={STATE_CLASS[rule.state] ?? ""}>
      <span class="rs-state">{rule.state}</span>
      <span class="rs-msg">{rule.requirement}</span>
      <span class="mono small muted">{rule.rule} · {rule.source}{rule.state === "待验证" ? " · " + rule.boundary : ""}</span>
    </li>
  );
}

function FindingList({ findings }: { findings: TextField["findings"] }) {
  return (
    <ul class="finding-list">
      {findings.map((f) => (
        <li class={STATE_CLASS[f.state] ?? ""}>
          <span class="rs-state">{f.state}</span>{" "}
          <strong>{f.message}</strong>
          {f.evidence?.matches?.length ? <span class="small"> —「{f.evidence.matches.join("」「")}」</span> : null}
          {f.evidence?.key ? <span class="small mono"> 关联 {f.evidence.key}</span> : null}
          <span class="mono small muted"> {f.rule}{f.source ? " · " + f.source : ""}</span>
        </li>
      ))}
    </ul>
  );
}

function ServerCompare({ panel }: { panel: TextPanel }) {
  const s = panel.server;
  const mismatches = s.columns.filter((c) => !c.match);
  const source = s.effectiveSource.split("/").pop();
  return (
    <details class="server-compare" open={mismatches.length > 0}>
      <summary>
        服务端生效文本对照：生效来源 <span class="mono">{source}</span>
        {s.rankOverridesBase ? "（p5b 整行覆盖 base）" : s.inBase ? "（仅 base）" : "（两份镜像都没有此角色）"}{" "}
        {mismatches.length ? <span class="rs rs-bad">不一致 {mismatches.length}</span> : <span class="rs rs-ok">一致</span>}
      </summary>
      <p class="small muted">{s.rule}。客户端列取 character_text 镜像列（c4–c10）。</p>
      <table class="compare-table">
        <thead><tr><th>列</th><th>客户端</th><th>服务端生效</th><th /></tr></thead>
        <tbody>
          {s.columns.map((c) => (
            <tr class={c.match ? "" : "mismatch"}>
              <td class="mono small">c{c.column} {c.label}</td>
              <td>{c.client ?? <em class="muted">（无）</em>}</td>
              <td>{c.server ?? <em class="muted">（无）</em>}</td>
              <td>{c.match ? <span class="rs rs-ok">一致</span> : <span class="rs rs-bad">不一致</span>}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  );
}

function LeaderName({ panel }: { panel: TextPanel }) {
  const ws = useWorkspace()!;
  const current = panel.leaderName.characterText ?? "";
  const value = ws.pending.leaderName?.new ?? current;
  const [local, setLocal] = useState(value);
  useEffect(() => setLocal(value), [value]);
  const commit = (next: string) => ws.update((p) => ({ ...p, leaderName: next === current ? null : { old: current, new: next } }));
  const mismatch = panel.leaderName.character !== panel.leaderName.characterText;
  return (
    <article class="ability">
      <header>
        <h3>队长名</h3>
        <span class="muted key">character_text c10 ↔ character c18</span>
        {mismatch ? <span class="rs rs-bad">两处不一致</span> : <span class="rs rs-ok">一致</span>}
      </header>
      <p class="small muted">wf text 改 c10 时同步 character c18 与两份服务端镜像。换队长技键后通常要改这里。</p>
      <div class="text-field">
        <input class={"text-input" + (local !== current ? " changed" : "")} value={local} aria-label="队长名 character_text c10"
          onInput={(e) => setLocal((e.target as HTMLInputElement).value)} onBlur={() => commit(local)}
          onKeyDown={(e) => {
            if (e.key === "Enter") { e.preventDefault(); commit(local); }
            if (e.key === "Escape") { e.stopPropagation(); setLocal(value); }
          }} />
        {mismatch ? <p class="small warn-text">character c18 当前为「{panel.leaderName.character}」。</p> : null}
      </div>
    </article>
  );
}
