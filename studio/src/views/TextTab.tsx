import { useEffect, useRef, useState } from "preact/hooks";
import { ability, onDraftChange, OverrideSlot, TextField, TextPanel, TextRuleRecord } from "../api";
import { Notice } from "./common";
import { editedLocations, useWorkspace } from "./AbilityEditor";
import { setCustom, setSkillText, sharedId, tierOps } from "./abilityModel";
import { InfoTip } from "./Delivery";
import { lookupCaps, useCaps } from "../clientProfile";
import { CapChip } from "./ClientProfile";

// 文案：技能名/描述（每档）、覆盖文案（按槽）、技能强化等关联文本、队长名。
// Reads GET /api/characters/<cid>/text (draft state, both server mirrors). Edits join the
// shared pending request; the write still goes through wf text and AbilityEditor.apply.

const STATE_CLASS: Record<string, string> = { 问题: "rs-bad", 待验证: "rs-warn", 未执行: "rs-none", 满足: "rs-ok", 不适用: "rs-na" };
const MAIN_LABEL: Record<string, string> = { all: "主位限定", some: "部分主位限定", none: "" };
export const MAIN_ICON = " <icon id='main'>  ";

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
  if (!panel || !ws) return <div class="loading">正在读取文案……</div>;

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
  const unattached = overrides.filter((f) => f.slot === "未挂接");

  return (
    <div class="board text-tab">
      <p class="hint">
        改动通过统一的文案检查写入：技能名和描述同时改客户端与两份服务器文本，覆盖文案和技能强化文本只在客户端。
        「待验证」= 规则只认得列举出的写法，没命中不等于合格，需要人工看。
        <InfoTip text={`技术细节：wf text；action_skill c0/c1、character_text 镜像列（c4–c10）、server/ 下 character_text.json 与 character_text_rank_p5b.json；desc_override / custom_ability_string 是客户端专属表。检查依据「${panel.standard.name}」v${panel.standard.version}。`} />
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
      <p class="small muted">{panel.standard.note}</p>

      <article class="ability">
        <header>
          <h3>技能名与描述</h3>
          <span class="muted key" title="技能键（action_skill）">键 {panel.skillKey}</span>
          {skillShared ? <span class="pill bad">与 {panel.skillOwners.length - 1} 个角色共用</span> : null}
        </header>
        {skillLocked ? <Notice kind="warn">{skillLocked}</Notice> : null}
        {skillShared ? <SharedConfirm id={sharedId("action_skill", panel.skillKey)} owners={panel.skillOwners} /> : null}
        <p class="small muted">各档写法须一致（数值可以不同）；技能描述只写技能本身，不重复队长技/能力里的强化效果。改任何一档都会核对全部档位的原文。</p>
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
          <h3>能力 / 队长技覆盖文案</h3>
          <span class="tag">{overrides.length} 条</span>
          <InfoTip text="desc_override_<槽里行的 c0>：客户端按这个键找覆盖文案，找到就整槽替换面板描述。" />
        </header>
        <p class="small muted">覆盖文案替换面板对数据行的自动描述：只写满级数值（面板只显示一个值）；一行一条效果，句末不加句号；
          队长槽不写「自身为队长时」；主位限定的槽每一行都要以主位图标开头。</p>
        {panel.slots.map((slot) => <SlotOverride panel={panel} slot={slot} view={view} />)}
        {unattached.length ? (
          <section class="slot-override">
            <h4>未挂接 <span class="small muted">（没有哪个槽的行对应这个键，面板不会显示）</span></h4>
            {unattached.map((f) => <CustomEditor field={view(f.location) ?? f} original={f.value} owners={f.owners} label="未挂接" />)}
          </section>
        ) : null}
      </article>

      <article class="ability">
        <header>
          <h3>技能强化效果与其它关联文本</h3>
          <span class="tag">{custom.length} 条</span>
          <InfoTip text="custom_ability_string；change_skill_* 是技能强化效果文本" />
        </header>
        <p class="small muted">技能强化效果写成「强化『技能名』：定性说明」，不写数字。这里检查恒真条件、「…之核」命名和与技能描述的重复。</p>
        {custom.length ? custom.map((f) => (
          <CustomEditor field={view(f.location) ?? f} original={f.value} owners={f.owners} label={f.enhancement ? "技能强化效果" : "关联文本"} />
        )) : <Notice>没有关联文本。</Notice>}
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

/** One slot: its override (exact key desc_override_<row c0>), or a button to create one. */
function SlotOverride({ panel, slot, view }: { panel: TextPanel; slot: OverrideSlot; view: (location: string) => TextField | undefined }) {
  const ws = useWorkspace()!;
  const existing = slot.existing.map((key) => panel.fields.find((f) => f.key === key && f.surface === "desc_override"))
    .filter(Boolean) as TextField[];
  const creating = ws.pending.custom.filter((c) => c.section === "desc_override" && c.old === null && slot.overrideKeys.includes(c.key));
  const newKey = slot.overrideKeys[0];
  const head = (
    <h4>
      {slot.label} <span class="mono small muted" title="词条键">{slot.key}</span>
      {MAIN_LABEL[slot.main] ? <span class="tag main-tag" title="能力 c1≠true：只在主位生效，面板每行带主位图标">{MAIN_LABEL[slot.main]}</span> : null}
    </h4>
  );
  if (existing.length || creating.length) {
    return (
      <section class="slot-override">
        {head}
        {existing.map((f) => <CustomEditor field={view(f.location) ?? f} original={f.value} owners={f.owners} label="" slot={slot} />)}
        {creating.map((c) => (
          <CustomEditor field={view(`desc_override.${c.key}`) ?? placeholderField(c.key, slot)} original={null}
            owners={slot.owners} label="新建" slot={slot} />
        ))}
      </section>
    );
  }
  return (
    <section class="slot-override empty">
      {head}
      <p class="small muted">没有覆盖文案：面板显示数据行自动描述。</p>
      {newKey ? (
        <button class="small-btn" onClick={() => ws.update((p) => setCustom(p, "desc_override", newKey, null,
          slot.main === "all" ? panel.mainIcon : "", slot.owners))} title={`新键 ${newKey}`}>
          新建覆盖文案
        </button>
      ) : <span class="small muted">这个槽的行没有名字列（c0），不能挂覆盖文案。</span>}
    </section>
  );
}

function placeholderField(key: string, slot: OverrideSlot): TextField {
  return { surface: "desc_override", location: `desc_override.${key}`, key, value: "", original: null, base: null,
    owners: slot.owners, enhancement: false, slot: slot.label, findings: [], rules: [], house: [], problems: 0,
    standardChecked: 0, main: slot.main, created: true };
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
      <p>这段文本同时属于 <span class="mono">{owners.join("、")}</span>，修改会同步到每一个角色。</p>
      <label class="check">
        <input type="checkbox" checked={!!ws.pending.sharedOk[id]}
          onChange={(e) => ws.update((p) => ({ ...p, sharedOk: { ...p.sharedOk, [id]: (e.target as HTMLInputElement).checked } }))} />
        确认一起修改（共享键）
      </label>
    </div>
  );
}

function CustomEditor({ field, original, owners, label, slot }: {
  field: TextField; original: string | null; owners: string[]; label: string; slot?: OverrideSlot;
}) {
  const ws = useWorkspace()!;
  const section = field.surface as "desc_override" | "custom_ability_string";
  const pending = ws.pending.custom.find((c) => c.section === section && c.key === field.key);
  const shared = owners.length > 1;
  const creating = original === null;
  const value = pending?.new ?? original ?? "";
  const missingIcon = slot?.main === "all" && value.split("\n").some((line) => line.trim() && line.trim() !== "<icon id='main'>" && !line.startsWith(MAIN_ICON));
  const addIcons = () => value.split("\n")
    .map((line) => (line.trim() && !line.startsWith(MAIN_ICON) ? MAIN_ICON + line.replace(/^\s*(<icon id='main'>)?\s*/, "") : line)).join("\n");
  return (
    <div class="custom-text">
      <div class="key-meta">
        <span class="mono small" title="文本键">{field.key}</span>
        {label ? <span class={"tag" + (creating ? " pendingpill" : "")}>{label}</span> : null}
        {shared ? <span class="pill bad" title={"持有者：" + owners.join("、")}>{owners.length} 个角色共用</span> : null}
        <TextCapChip section={section} keyName={field.key} />
        {creating ? (
          <button class="ghost small-btn" onClick={() => ws.update((p) => ({ ...p, custom: p.custom.filter((c) => !(c.section === section && c.key === field.key)) }))}>
            取消新建</button>
        ) : null}
      </div>
      {shared ? <SharedConfirm id={sharedId(section, field.key)} owners={owners} /> : null}
      <TextFieldEditor field={field} label="" multiline value={value} original={original ?? ""}
        edited={editedLocations(ws.pending).has(field.location)}
        onChange={(next) => ws.update((p) => setCustom(p, section, field.key, original, next, owners))} />
      {missingIcon ? (
        <p class="small warn-text">主位限定槽：有的行缺主位图标。
          <button class="link" onClick={() => ws.update((p) => setCustom(p, section, field.key, original, addIcons(), owners))}>给每行补上</button></p>
      ) : null}
      {section === "desc_override" && value.trim() ? <PanelPreview text={value} /> : null}
    </div>
  );
}

/** How the client draws the override: one line per row, <icon id='main'> as the Ⓜ badge. */
export function PanelPreview({ text }: { text: string }) {
  return (
    <div class="panel-preview" aria-label="面板预览">
      <span class="small muted">面板预览</span>
      {text.split("\n").map((line) => {
        const parts = line.split("<icon id='main'>");
        return (
          <div class="panel-line">
            {parts.map((part, i) => (
              <>{i > 0 ? <span class="main-badge" title="主位图标">M</span> : null}{part.replace(/^ +/, (s) => " ".repeat(s.length))}</>
            ))}
          </div>
        );
      })}
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
    class: "text-input" + (changedFromDraft ? " changed" : "") + (field.problems && edited ? " problem" : ""),
    value: local, disabled, "aria-label": `${label || field.key} ${field.location}`,
    onInput: (e: Event) => onInput((e.target as HTMLInputElement).value),
    onBlur: () => commit(local), onKeyDown: onKey,
  };
  return (
    <div class="text-field">
      {label ? <span class="field-label">{label}</span> : null}
      {multiline ? <textarea rows={Math.min(8, Math.max(2, local.split("\n").length + 1, Math.ceil(local.length / 64) + 1))} {...props} /> : <input {...props} />}
      {changedFromDraft && original ? <p class="small muted was">草稿当前：{original}</p> : null}
      {differsFromBase ? <p class="small muted was" title="当前视图里、这份草稿之前的文本">改动前：{field.base || "（空）"}</p> : null}
      <FieldRules field={field} edited={edited} />
    </div>
  );
}

function FieldRules({ field, edited }: { field: TextField; edited: boolean }) {
  const houseRules = new Set(field.house.flatMap((h) => h.findings.map((f) => f.rule)));
  const others = field.findings.filter((f) => (f.state === "问题" || f.state === "待验证") && !houseRules.has(f.rule));
  const flagged = field.house.filter((h) => h.state !== "满足");
  return (
    <div class={"field-rules" + (edited ? " edited" : "")}>
      <div class="house-row">
        {field.problems ? <span class="rs rs-bad">问题 {field.problems}</span> : <span class="rs rs-ok">未发现问题</span>}
        {flagged.map((h) => (
          <span class={"house-chip " + (STATE_CLASS[h.state] ?? "")} title={h.requirement}>{h.state} · {h.title}</span>
        ))}
      </div>
      {flagged.length ? <FindingList findings={flagged.flatMap((h) => h.findings)} /> : null}
      {others.length ? <FindingList findings={others} /> : null}
      {field.rules.length ? (
        <details class="std-rules">
          <summary>命中面板规范 {field.rules.length} 条</summary>
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
      <span class="mono small muted">{rule.source}</span>
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
          {f.source ? <InfoTip text={`${f.rule} · ${f.source}`} /> : null}
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
        服务器上实际生效的文本 {mismatches.length ? <span class="rs rs-bad">与客户端不一致 {mismatches.length}</span> : <span class="rs rs-ok">与客户端一致</span>}
        <InfoTip text={`生效来源 ${source}${s.rankOverridesBase ? "（p5b 整行覆盖 base）" : s.inBase ? "（仅 base）" : "（两份镜像都没有此角色）"}。${s.rule}`} />
      </summary>
      <table class="compare-table">
        <thead><tr><th>内容</th><th>客户端</th><th>服务器生效</th><th /></tr></thead>
        <tbody>
          {s.columns.map((c) => (
            <tr class={c.match ? "" : "mismatch"}>
              <td class="small" title={`character_text c${c.column}`}>{c.label}</td>
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
        <InfoTip text="写入 character_text c10，同时同步 character c18 与两份服务器文本" />
        {mismatch ? <span class="rs rs-bad">两处不一致</span> : <span class="rs rs-ok">一致</span>}
      </header>
      <p class="small muted">换了队长技之后通常要改这里。</p>
      <div class="text-field">
        <input class={"text-input" + (local !== current ? " changed" : "")} value={local} aria-label="队长名"
          onInput={(e) => setLocal((e.target as HTMLInputElement).value)} onBlur={() => commit(local)}
          onKeyDown={(e) => {
            if (e.key === "Enter") { e.preventDefault(); commit(local); }
            if (e.key === "Escape") { e.stopPropagation(); setLocal(value); }
          }} />
        {mismatch ? <p class="small warn-text">另一处（角色表）当前为「{panel.leaderName.character}」。</p> : null}
      </div>
    </article>
  );
}

/** 「v34 即可」 / 「需要 v35e」 for a client-only text key (desc_override or a wfx_* configuration string). */
function TextCapChip({ section, keyName }: { section: "desc_override" | "custom_ability_string"; keyName: string }) {
  const override = section === "desc_override";
  const req = useCaps(`text:${section}:${override ? "" : keyName}`,
    () => lookupCaps(override ? { selector: "text.desc_override" } : { customKey: keyName }));
  return <CapChip req={req} what={override ? "覆盖文案（desc_override）需要的客户端能力：" : `配置文本 ${keyName} 需要的客户端能力：`} />;
}
