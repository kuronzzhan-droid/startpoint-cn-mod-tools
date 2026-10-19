import { useEffect, useState } from "preact/hooks";
import { api, BindResult, CharacterSummary, DraftCheck, DraftStatus, drafts, ScratchInfo, scratchApi } from "../api";
import { href, Route } from "../router";
import { ChangesPanel, useDraft } from "./Changes";
import { Drawer, ElementBadge, Notice, StatusStrip } from "./common";
import { InfoTip, useDeliveries } from "./Delivery";
import { deviceCell } from "./DeviceResult";
import { PixelGroup, PixelSub } from "./PixelGroup";

const ELEMENTS = ["火", "水", "雷", "风", "光", "暗"];

function useRoster() {
  const [roster, setRoster] = useState<CharacterSummary[]>([]);
  useEffect(() => { api.characters().then((r) => setRoster(r.characters)); }, []);
  return roster;
}

/** One picker: type a name / ID / code and pick from the hits (or keep a typed code name). */
function CharacterPicker({ roster, value, onChange, placeholder }: {
  roster: CharacterSummary[]; value: CharacterSummary | string | null; onChange: (v: CharacterSummary | string | null) => void;
  placeholder: string;
}) {
  const [query, setQuery] = useState("");
  const q = query.trim().toLowerCase();
  const hits = q ? roster.filter((c) => (c.id + c.name + (c.title ?? "") + c.code).toLowerCase().includes(q)).slice(0, 10) : [];
  if (value && typeof value !== "string") {
    return (
      <span class="picked">
        <img src={api.avatarUrl(value.id)} alt="" width={22} height={22} loading="lazy" />
        <strong>{value.name}</strong><span class="mono small muted">{value.id} · {value.code}</span>
        <button class="ghost small-btn" onClick={() => onChange(null)} aria-label="重新选择">换一个</button>
      </span>
    );
  }
  return (
    <span class="ws-search">
      <input type="search" placeholder={placeholder} value={query}
        onInput={(e) => { const v = (e.target as HTMLInputElement).value; setQuery(v); onChange(v.trim() || null); }} />
      {hits.length ? (
        <div class="ws-hits">
          {hits.map((c) => (
            <button onClick={() => { onChange(c); setQuery(""); }}>
              <img src={api.avatarUrl(c.id)} alt="" width={24} height={24} loading="lazy" />
              <span>{c.name}</span><span class="mono small muted">{c.id} · {c.code}</span>
            </button>
          ))}
        </div>
      ) : null}
    </span>
  );
}

const nameProblem = (name: string) => {
  const v = name.trim();
  if (!v) return "先填名字";
  if (v.length < 2 || /^[\d\W_]+$/u.test(v)) return "名字至少两个字，且不能只有数字或符号";
  return null;
};

export function ScratchList() {
  const [items, setItems] = useState<ScratchInfo[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({ name: "", element: "水", slug: "" });
  const [base, setBase] = useState<CharacterSummary | string | null>(null);
  const [busy, setBusy] = useState(false);
  const roster = useRoster();
  useEffect(() => { scratchApi.list().then((r) => setItems(r.scratch), (e: Error) => setError(e.message)); }, []);
  const baseRef = base === null ? "" : typeof base === "string" ? base : base.code;
  const problem = nameProblem(form.name);
  const create = async () => {
    setBusy(true); setError(null);
    try {
      const info = await scratchApi.create({ name: form.name.trim(), element: form.element, base: baseRef,
        ...(form.slug.trim() ? { slug: form.slug.trim() } : {}) });
      location.hash = href({ work: "content", shop: "scratch", id: info.characterId });
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  };
  return (
    <section class="page">
      <h2>草稿角色</h2>
      <p class="hint">还没有游戏 ID 的新角色，只做像素小人：选一个现有角色当母本（动作、帧数、站位都照它来），在「像素」里换色、生成动作、手改，
        或导入离线做好的整套小人。定好 ID 后「绑定到角色」，改动才会进那个角色的草稿、才能生成。
        <InfoTip text="技术细节：目录 work/studio-drafts/scratch-<slug>/，占位代码 scratch_<slug>，不写任何表行；母本提供帧区间、锚点和 frame.scale。" /></p>
      <div class="ws-panel ws-new">
        <h4>新建草稿角色</h4>
        <div class="toolbar">
          <label>名字<input value={form.name} maxLength={40} placeholder="例如 水杰拉德" onInput={(e) => setForm({ ...form, name: (e.target as HTMLInputElement).value })} /></label>
          <label>属性<select value={form.element} onChange={(e) => setForm({ ...form, element: (e.target as HTMLSelectElement).value })}>
            {ELEMENTS.map((el) => <option value={el}>{el}</option>)}</select></label>
          <label>母本 <CharacterPicker roster={roster} value={base} onChange={setBase} placeholder="名字 / ID / 代码名" /></label>
          <details class="inline-details"><summary class="small">目录名（可选）</summary>
            <input class="mono" value={form.slug} placeholder="如 gerald-water" onInput={(e) => setForm({ ...form, slug: (e.target as HTMLInputElement).value })} />
          </details>
          <button class="primary" onClick={create} disabled={busy || !!problem || !baseRef || !drafts.hasToken()}
            title={problem ?? (!baseRef ? "先选母本" : "")}>{busy ? "新建中……" : "新建"}</button>
        </div>
        {form.name && problem ? <p class="small warn-text">{problem}</p> : null}
      </div>
      {error ? <Notice kind="error">{error}</Notice> : null}
      {!items ? <div class="loading">正在读取草稿角色……</div> : items.length === 0 ? <p class="muted">还没有草稿角色。</p> : (
        <div class="ws-scratch-list">
          {items.map((s) => (
            <a class="ws-scratch-card" href={href({ work: "content", shop: "scratch", id: s.characterId })}>
              <strong><ElementBadge element={s.scratch.element} /> {s.scratch.name}</strong>
              <span class="small muted">母本 {s.scratch.base.name ?? s.scratch.base.code}</span>
              <span class="small">{s.status.label}</span>
              <span class={"small " + (s.scratch.boundTo ? "" : "warn-text")}>{s.scratch.boundTo ? `已绑定到 ${s.scratch.boundTo.characterId}` : "还没绑定角色 ID，不能生成"}</span>
            </a>
          ))}
        </div>
      )}
    </section>
  );
}

const GROUPS = [
  { id: "pixel", label: "像素" },
  { id: "bind", label: "绑定到角色" },
];

export function ScratchDetail({ id, tab, sub }: { id: string; tab?: string; sub?: string }) {
  const [info, setInfo] = useState<ScratchInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const draft = useDraft(id);
  // Old deep links: workshop / import / changes.
  const drawer = tab === "changes";
  const group = tab === "bind" ? "bind" : "pixel";
  const pixelSub = tab === "import" ? "import" : sub;
  const [refresh, setRefresh] = useState(0);
  const link = (g: string, s?: string): Route => ({ work: "content", shop: "scratch", id, tab: g, sub: s });
  useEffect(() => { scratchApi.get(id).then(setInfo, (e: Error) => setError(e.message)); }, [id, refresh, draft.view?.changeset?.revision]);
  if (error) return <section class="page"><a class="back" href="#/scratch">← 草稿角色</a><Notice kind="error">{error}</Notice></section>;
  if (!info) return <section class="page"><div class="loading">正在读取草稿角色……</div></section>;
  const bound = info.scratch.boundTo;
  const status = draft.view?.status;
  const remove = async () => {
    if (!confirm(`删除草稿角色「${info.scratch.name}」？它的整个草稿目录会被删除，无法恢复${bound ? `（已绑定到 ${bound.characterId} 的改动保留在那个角色里）` : ""}。`)) return;
    try { await scratchApi.remove(id); location.hash = "#/scratch"; } catch (e) { setError((e as Error).message); }
  };
  return (
    <section class="page detail">
      <a class="back" href="#/scratch">← 草稿角色</a>
      <header class="char-header">
        <div class="char-header-main">
          <h1><ElementBadge element={info.scratch.element} />{info.scratch.name}
            <button class="ghost small-btn" onClick={() => setEditing(!editing)}>改名</button></h1>
          <div class="muted">草稿角色 · 母本 {info.scratch.base.name ?? info.scratch.base.code}
            {info.scratch.base.characterId ? <> （<a href={href({ work: "content", shop: "characters", id: info.scratch.base.characterId })}>{info.scratch.base.characterId}</a>）</> : null}
            <InfoTip text={`技术细节：${info.characterId} · 占位代码 ${info.code} · 母本代码 ${info.scratch.base.code}`} /></div>
          {editing ? <RenameForm info={info} onDone={() => { setEditing(false); setRefresh((n) => n + 1); }} /> : null}
        </div>
        <div class="char-header-side">
          <div class="header-actions">
            <a class={"header-btn" + (status?.state === "dirty" ? " dirty" : status?.changes ? " saved" : "")} href={href(link("changes"))}>
              本次修改 <span class="count">{status?.changes ?? 0}</span>{status?.state === "dirty" ? <span class="dot" title="未保存" /> : null}
            </a>
            <button class="header-btn danger" onClick={remove} disabled={!drafts.hasToken()}>删除</button>
          </div>
          <span class={"origin " + (bound ? "origin-new" : "origin-unknown")}>{bound ? `已绑定 ${bound.characterId}` : "还没有角色 ID"}</span>
        </div>
      </header>
      {bound ? <BoundStatusStrip cid={bound.characterId} draft={draft.view?.status ?? null}
        checks={draft.view?.changeset?.changes.flatMap((c) => c.checks) ?? []} />
        : <StatusStrip draft={draft.view?.status ?? null} checks={draft.view?.changeset?.changes.flatMap((c) => c.checks) ?? []}
          deviceNote="没有游戏 ID，不能生成" />}
      {bound ? <Notice>已绑定到 <a href={href({ work: "content", shop: "characters", id: bound.characterId, tab: "changes" })}>{bound.characterId}（{bound.code}）</a>：
        在那个角色的「本次修改」里保存、生成。这里之后的改动不会自动同步过去。</Notice>
        : <Notice kind="warn">还没有游戏 ID：可以编辑、保存，但不能生成；先「绑定到角色」。</Notice>}
      <nav class="tabs" role="tablist" aria-label="草稿角色">
        {GROUPS.map((g) => (
          <a role="tab" aria-selected={group === g.id} class={group === g.id ? "active" : ""} href={href(link(g.id))}>{g.label}</a>
        ))}
      </nav>
      {group === "pixel"
        ? <PixelGroup characterId={id} sub={pixelSub} scratch link={(s: PixelSub) => link("pixel", s)} key={refresh} />
        : <BindPanel info={info} onDone={() => setRefresh((n) => n + 1)} />}
      {drawer ? (
        <Drawer title={<>本次修改 <span class="small muted">{status?.label}</span></>} onClose={() => { location.hash = href(link(group, pixelSub)); }}>
          <ChangesPanel characterId={id} scratch />
        </Drawer>
      ) : null}
    </section>
  );
}

/** A bound scratch character is generated and tested as its target character: show that one's 实测. */
function BoundStatusStrip({ cid, draft, checks }: { cid: string; draft: DraftStatus | null; checks: DraftCheck[] }) {
  const built = useDeliveries(cid);
  const target = useDraft(cid);
  return <StatusStrip draft={draft} checks={checks} device={deviceCell(built.list, target.view?.changeset?.revision)}
    deviceNote={`按绑定角色 ${cid}`}
    deviceLink={(name) => href({ work: "content", shop: "characters", id: cid, tab: "changes", sub: name })} />;
}

function RenameForm({ info, onDone }: { info: ScratchInfo; onDone: () => void }) {
  const [name, setName] = useState(info.scratch.name);
  const [element, setElement] = useState(info.scratch.element);
  const [error, setError] = useState<string | null>(null);
  const problem = nameProblem(name);
  const save = async () => {
    try {
      await scratchApi.rename(info.characterId, { ...(name.trim() !== info.scratch.name ? { name: name.trim() } : {}),
        ...(element !== info.scratch.element ? { element } : {}) });
      onDone();
    } catch (e) { setError((e as Error).message); }
  };
  return (
    <div class="toolbar rename-form">
      <label>名字<input value={name} maxLength={40} onInput={(e) => setName((e.target as HTMLInputElement).value)} /></label>
      <label>属性<select value={element} onChange={(e) => setElement((e.target as HTMLSelectElement).value)}>
        {ELEMENTS.map((el) => <option value={el}>{el}</option>)}</select></label>
      <button class="primary" onClick={save} disabled={!!problem || (name.trim() === info.scratch.name && element === info.scratch.element)}>保存</button>
      <button class="ghost" onClick={onDone}>取消</button>
      {problem ? <span class="small warn-text">{problem}</span> : null}
      {error ? <span class="small error-text">{error}</span> : null}
    </div>
  );
}

function BindPanel({ info, onDone }: { info: ScratchInfo; onDone: () => void }) {
  const roster = useRoster();
  const [target, setTarget] = useState<CharacterSummary | string | null>(null);
  const [preview, setPreview] = useState<BindResult | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<{ kind: "info" | "error"; text: string } | null>(null);
  const bound = info.scratch.boundTo;
  const cid = target === null ? "" : typeof target === "string" ? target : target.id;
  const run = async (dryRun: boolean) => {
    setBusy(dryRun ? "check" : "bind"); setMessage(null);
    try {
      const r = await scratchApi.bind(info.characterId, { characterId: cid, dryRun });
      setPreview(r);
      if (!dryRun) { setMessage({ kind: "info", text: `已绑定到 ${r.characterId}（${r.code}），写入 ${r.created?.length ?? 0} 项改动。` }); onDone(); }
    } catch (e) { setMessage({ kind: "error", text: (e as Error).message }); }
    finally { setBusy(null); }
  };
  if (bound) return (
    <Notice>已于 {bound.at.replace("T", " ").slice(0, 16)} 绑定到 <a href={href({ work: "content", shop: "characters", id: bound.characterId, tab: "changes" })}>{bound.characterId}（{bound.code}）</a>，
      写入了 {bound.changes.length} 项改动。草稿角色本身不能生成。</Notice>
  );
  return (
    <div class="ws-bind">
      <p class="hint">选一个已经在游戏里的角色 ID：全部像素改动改成那个角色的名字，写进它的草稿（同一族、同一动作的旧改动会被替换），
        然后在那个角色的「本次修改」里保存、生成。只改了单个动作的族，会自动把母本整套小人一起带过去。
        <InfoTip text={`技术细节：atlas / frame 名前缀 character/${info.code}/ 改成目标代码；母本换色类改动按母本 + 颜色表重算核对；整个绑定一次写入，失败全部回滚。`} /></p>
      <div class="toolbar">
        <label>角色 <CharacterPicker roster={roster} value={target} onChange={(v) => { setTarget(v); setPreview(null); }} placeholder="名字 / ID" /></label>
        <button onClick={() => run(true)} disabled={!/^\d+$/.test(cid) || busy !== null || !drafts.hasToken()}>{busy === "check" ? "核对中……" : "预览绑定"}</button>
        <button class="primary" onClick={() => run(false)} disabled={!preview || !preview.dryRun || busy !== null}>{busy === "bind" ? "绑定中……" : "确认绑定"}</button>
      </div>
      {message ? <Notice kind={message.kind === "error" ? "error" : "info"}>{message.text}</Notice> : null}
      {preview ? (
        <section class="pixel-check">
          <h4>{preview.dryRun ? "将要绑定" : "已绑定"}：{preview.name}（{preview.characterId}）</h4>
          <ul>{preview.changes.map((c) => <li class="small">{c.auto ? <span class="tag">自动补</span> : null} {c.title}</li>)}</ul>
          {preview.notes?.length ? <ul class="checks">{preview.notes.map((n) => <li class="check-info"><span>{n}</span></li>)}</ul> : null}
          {!preview.dryRun ? <a href={href({ work: "content", shop: "characters", id: preview.characterId, tab: "changes" })}>去 {preview.characterId} 的「本次修改」→</a> : null}
        </section>
      ) : null}
    </div>
  );
}
