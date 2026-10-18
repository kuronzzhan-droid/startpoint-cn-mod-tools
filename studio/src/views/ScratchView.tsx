import { useEffect, useState } from "preact/hooks";
import { api, BindResult, CharacterSummary, drafts, ImportResult, ScratchInfo, scratchApi } from "../api";
import { href } from "../router";
import { ChangesPanel } from "./Changes";
import { ElementBadge, Notice, StatusStrip } from "./common";
import { PixelWorkshop } from "./PixelWorkshop";
import { useDraft } from "./Changes";
import { readAsDataUrl } from "./workshopKit";

const ELEMENTS = ["火", "水", "雷", "风", "光", "暗"];

function useRoster() {
  const [roster, setRoster] = useState<CharacterSummary[]>([]);
  useEffect(() => { api.characters().then((r) => setRoster(r.characters)); }, []);
  return roster;
}

function CharacterSearch({ roster, onPick, placeholder }: { roster: CharacterSummary[]; onPick: (c: CharacterSummary) => void; placeholder: string }) {
  const [query, setQuery] = useState("");
  const hits = query.trim()
    ? roster.filter((c) => (c.id + c.name + (c.title ?? "") + c.code).toLowerCase().includes(query.trim().toLowerCase())).slice(0, 10)
    : [];
  return (
    <span class="ws-search">
      <input type="search" placeholder={placeholder} value={query} onInput={(e) => setQuery((e.target as HTMLInputElement).value)} />
      {hits.length ? (
        <div class="ws-hits">
          {hits.map((c) => (
            <button onClick={() => { onPick(c); setQuery(""); }}>
              <img src={api.avatarUrl(c.id)} alt="" width={24} height={24} loading="lazy" />
              <span>{c.name}</span><span class="mono small muted">{c.id} · {c.code}</span>
            </button>
          ))}
        </div>
      ) : null}
    </span>
  );
}

export function ScratchList() {
  const [items, setItems] = useState<ScratchInfo[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({ name: "", element: "水", base: "", slug: "" });
  const [busy, setBusy] = useState(false);
  const roster = useRoster();
  useEffect(() => { scratchApi.list().then((r) => setItems(r.scratch), (e: Error) => setError(e.message)); }, []);
  const create = async () => {
    setBusy(true); setError(null);
    try {
      const info = await scratchApi.create({ name: form.name.trim(), element: form.element, base: form.base.trim(),
        ...(form.slug.trim() ? { slug: form.slug.trim() } : {}) });
      location.hash = href({ work: "content", shop: "scratch", id: info.characterId });
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  };
  return (
    <section class="page">
      <h2>草稿角色</h2>
      <p class="hint">还没有游戏 ID 的角色，只做像素：放在 <span class="mono">work/studio-drafts/scratch-&lt;slug&gt;/</span>，占位代码
        <span class="mono"> scratch_&lt;slug&gt;</span>，不写任何表行。母本提供帧区间、锚点和 frame.scale；像素工坊四页都能用，也能导入离线做好的像素集与映射表。
        定好 ID 后「绑定到角色 ID」，改名前缀进该角色草稿，才能生成交付。</p>
      <div class="ws-panel ws-new">
        <h4>新建草稿角色</h4>
        <div class="toolbar">
          <label>名字<input value={form.name} maxLength={40} placeholder="例如 水杰拉德" onInput={(e) => setForm({ ...form, name: (e.target as HTMLInputElement).value })} /></label>
          <label>属性<select value={form.element} onChange={(e) => setForm({ ...form, element: (e.target as HTMLSelectElement).value })}>
            {ELEMENTS.map((el) => <option value={el}>{el}</option>)}</select></label>
          <label>母本<input class="mono" value={form.base} placeholder="代码名或 ID" onInput={(e) => setForm({ ...form, base: (e.target as HTMLInputElement).value })} /></label>
          <CharacterSearch roster={roster} placeholder="检索母本" onPick={(c) => setForm({ ...form, base: c.code })} />
          <label>目录名<input class="mono" value={form.slug} placeholder="可选，如 gerald-water" onInput={(e) => setForm({ ...form, slug: (e.target as HTMLInputElement).value })} /></label>
          <button class="primary" onClick={create} disabled={busy || !form.name.trim() || !form.base.trim() || !drafts.hasToken()}>{busy ? "新建中……" : "新建"}</button>
        </div>
      </div>
      {error ? <Notice kind="error">{error}</Notice> : null}
      {!items ? <div class="loading">正在读取草稿角色……</div> : items.length === 0 ? <p class="muted">还没有草稿角色。</p> : (
        <div class="ws-scratch-list">
          {items.map((s) => (
            <a class="ws-scratch-card" href={href({ work: "content", shop: "scratch", id: s.characterId })}>
              <strong><ElementBadge element={s.scratch.element} /> {s.scratch.name}</strong>
              <span class="mono small">{s.characterId}</span>
              <span class="small muted">母本 {s.scratch.base.name ?? ""} <span class="mono">{s.scratch.base.code}</span></span>
              <span class="small">{s.status.label}</span>
              <span class={"small " + (s.scratch.boundTo ? "" : "warn-text")}>{s.scratch.boundTo ? `已绑定 ${s.scratch.boundTo.characterId}（${s.scratch.boundTo.code}）` : "未绑定 ID · 不能生成交付"}</span>
            </a>
          ))}
        </div>
      )}
    </section>
  );
}

const TABS = [
  { id: "workshop", label: "像素工坊" },
  { id: "import", label: "导入像素集" },
  { id: "bind", label: "绑定到角色 ID" },
  { id: "changes", label: "本次修改" },
];

export function ScratchDetail({ id, tab }: { id: string; tab?: string }) {
  const [info, setInfo] = useState<ScratchInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const draft = useDraft(id);
  const active = TABS.some((t) => t.id === tab) ? tab! : "workshop";
  const [refresh, setRefresh] = useState(0);
  useEffect(() => { scratchApi.get(id).then(setInfo, (e: Error) => setError(e.message)); }, [id, refresh, draft.view?.changeset?.revision]);
  if (error) return <section class="page"><a class="back" href="#/scratch">← 草稿角色</a><Notice kind="error">{error}</Notice></section>;
  if (!info) return <section class="page"><div class="loading">正在读取草稿角色……</div></section>;
  const bound = info.scratch.boundTo;
  return (
    <section class="page detail">
      <a class="back" href="#/scratch">← 草稿角色</a>
      <header class="char-header">
        <div class="char-header-main">
          <h1><ElementBadge element={info.scratch.element} />{info.scratch.name}</h1>
          <div class="muted">草稿角色 · 母本 {info.scratch.base.name ?? ""} <span class="mono">{info.scratch.base.code}</span>
            {info.scratch.base.characterId ? <> (<a href={href({ work: "content", shop: "characters", id: info.scratch.base.characterId })}>{info.scratch.base.characterId}</a>)</> : null}</div>
        </div>
        <div class="char-header-side">
          <span class={"origin " + (bound ? "origin-new" : "origin-unknown")}>{bound ? `已绑定 ${bound.characterId}` : "未分配 ID"}</span>
          <span class="char-id">{info.characterId} · 占位代码 {info.code}</span>
        </div>
      </header>
      <StatusStrip draft={draft.view?.status ?? null} checks={draft.view?.changeset?.changes.flatMap((c) => c.checks) ?? []} />
      {bound ? <Notice>已绑定到 <a href={href({ work: "content", shop: "characters", id: bound.characterId, tab: "changes" })}>{bound.characterId}（{bound.code}）</a>：
        交付请在该角色「本次修改」里生成。这里之后的改动不会自动同步过去。</Notice>
        : <Notice kind="warn">没有游戏 ID：可以编辑、保存，但「生成」会被拒绝；先绑定到角色 ID。</Notice>}
      <nav class="tabs" role="tablist" aria-label="草稿角色">
        {TABS.map((t) => (
          <a role="tab" aria-selected={active === t.id} class={active === t.id ? "active" : ""}
            href={href({ work: "content", shop: "scratch", id, tab: t.id })}>{t.label}
            {t.id === "changes" && draft.view?.status.changes ? <span class="count">{draft.view.status.changes}</span> : null}</a>
        ))}
      </nav>
      {active === "workshop" ? <PixelWorkshop characterId={id} key={refresh} />
        : active === "import" ? <ImportPanel cid={id} onDone={() => setRefresh((n) => n + 1)} />
        : active === "bind" ? <BindPanel info={info} onDone={() => setRefresh((n) => n + 1)} />
        : <ChangesPanel characterId={id} />}
    </section>
  );
}

function ImportPanel({ cid, onDone }: { cid: string; onDone: () => void }) {
  const [files, setFiles] = useState<Record<string, string>>({});
  const [zip, setZip] = useState<{ name: string; data: string } | null>(null);
  const [remap, setRemap] = useState<{ name: string; value: unknown } | null>(null);
  const [name, setName] = useState("");
  const [result, setResult] = useState<ImportResult | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<{ kind: "info" | "error"; text: string } | null>(null);
  const b64 = async (f: File) => (await readAsDataUrl(f)).replace(/^data:[^,]*,/, "");
  const pickFolder = async (list: FileList | null) => {
    if (!list) return;
    const out: Record<string, string> = {};
    for (const f of Array.from(list)) {
      if (/\.(png|deflate|json)$/.test(f.name)) out[(f as File & { webkitRelativePath?: string }).webkitRelativePath || f.name] = await b64(f);
    }
    setFiles(out); setZip(null); setResult(null);
    if (!name) setName(Object.keys(out)[0]?.split("/")[0] ?? "");
  };
  const run = async (dryRun: boolean) => {
    setBusy(dryRun ? "check" : "import"); setMessage(null);
    try {
      const body = { ...(zip ? { zip: zip.data } : { files }), ...(remap ? { remap: remap.value } : {}), name: name || zip?.name || "导入", dryRun };
      const r = await scratchApi.importSet(cid, body);
      setResult(r);
      if (!dryRun) { setMessage({ kind: "info", text: `已导入：${r.changes?.map((c) => c.title).join("；")}（${r.status?.label}）` }); onDone(); }
    } catch (e) { setMessage({ kind: "error", text: (e as Error).message }); }
    finally { setBusy(null); }
  };
  const ready = zip !== null || Object.keys(files).length > 0;
  const folderProps = { webkitdirectory: "", directory: "" } as Record<string, string>;
  return (
    <div class="ws-import">
      <p class="hint">导入离线做好的像素集：sprite_sheet.png + .atlas + pixelart.frame + .timeline（special_* 同构），按文件名识别，
        atlas/frame 名前缀改成本草稿的代码。可带映射表 JSON（<span class="mono">{"{"}"base": 母本代码, "mapping": {"{"}"#src": "#dst"{"}"}{"}"}</span>
        或 [{"{"}from,to{"}"}]，包里名字含 remap/mapping/palette 的 JSON 会自动识别）：逐端点对照「母本 + 映射表」，一致的是映射、不一致的标为手绘。</p>
      <div class="toolbar">
        <label class="upload-btn">选文件夹<input type="file" multiple {...folderProps} onChange={(e) => pickFolder((e.target as HTMLInputElement).files)} /></label>
        <label class="upload-btn">或 zip<input type="file" accept=".zip" onChange={async (e) => {
          const f = (e.target as HTMLInputElement).files?.[0];
          if (f) { setZip({ name: f.name.replace(/\.zip$/, ""), data: await b64(f) }); setFiles({}); setResult(null); if (!name) setName(f.name.replace(/\.zip$/, "")); }
        }} /></label>
        <label class="upload-btn">映射表 JSON（可选）<input type="file" accept=".json" onChange={async (e) => {
          const f = (e.target as HTMLInputElement).files?.[0];
          if (!f) return;
          try { setRemap({ name: f.name, value: JSON.parse(await f.text()) }); }
          catch (err) { setMessage({ kind: "error", text: "映射表不是合法 JSON：" + (err as Error).message }); }
        }} /></label>
        <label>来源名称<input value={name} maxLength={80} onInput={(e) => setName((e.target as HTMLInputElement).value)} /></label>
      </div>
      <p class="small muted">{zip ? `zip：${zip.name}` : Object.keys(files).length ? `文件夹：${Object.keys(files).length} 个文件` : "还没选"}{remap ? ` · 映射表 ${remap.name}` : ""}</p>
      {message ? <Notice kind={message.kind === "error" ? "error" : "info"}>{message.text}</Notice> : null}
      <div class="save-row">
        <button onClick={() => run(true)} disabled={!ready || busy !== null || !drafts.hasToken()}>{busy === "check" ? "检查中……" : "检查（不写草稿）"}</button>
        <button class="primary" onClick={() => run(false)} disabled={!ready || busy !== null || !drafts.hasToken()}>{busy === "import" ? "导入中……" : "导入到草稿"}</button>
      </div>
      {result ? (
        <section class="pixel-check">
          <h4>{result.dryRun ? "检查结果" : "已导入"}{result.remap ? ` · 映射表 ${result.remap.colors} 色，母本 ${result.remap.base ?? "（未写）"}` : ""}</h4>
          {result.families.map((f) => (
            <div>
              <p class="small"><strong>{f.family}</strong>：原前缀 <span class="mono">{f.sourceCode}</span> · {f.endpoints} 个端点 · 图集 {f.sheet.join("×")} · 动作 {f.actions.join("、")}</p>
              {f.provenance?.comparable ? (
                <p class="small">与母本 + 映射表一致 {f.provenance.matchingEndpoints}/{f.provenance.endpoints} 个端点
                  {Object.keys(f.provenance.differingByAction ?? {}).length ? "；手绘/改动：" + Object.entries(f.provenance.differingByAction!).map(([a, n]) => `${a} ${n}`).join("，") : ""}</p>
              ) : null}
              <ul class="checks">{f.checks.map((c) => <li class={"check-" + c.level}><span>{c.message}</span> <span class="mono muted small">{c.code}</span></li>)}</ul>
            </div>
          ))}
        </section>
      ) : null}
    </div>
  );
}

function BindPanel({ info, onDone }: { info: ScratchInfo; onDone: () => void }) {
  const roster = useRoster();
  const [cid, setCid] = useState("");
  const [preview, setPreview] = useState<BindResult | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<{ kind: "info" | "error"; text: string } | null>(null);
  const bound = info.scratch.boundTo;
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
    <Notice>已于 {bound.at} 绑定到 <a href={href({ work: "content", shop: "characters", id: bound.characterId, tab: "changes" })}>{bound.characterId}（{bound.code}）</a>，
      写入改动 {bound.changes.join("、")}。草稿角色本身不能生成交付。</Notice>
  );
  return (
    <div class="ws-bind">
      <p class="hint">选定真实角色 ID（必须已在当前视图的角色表里）后：全部像素改动的 atlas / frame 名前缀从
        <span class="mono"> character/{info.code}/</span> 改成该角色代码，写进该角色草稿（同族同动作的旧改动会被替换）；母本映射类改动会按母本 + 映射表重算核对。
        绑定后在该角色页「本次修改」里保存、生成交付。</p>
      <div class="toolbar">
        <label>角色 ID<input class="mono" value={cid} onInput={(e) => { setCid((e.target as HTMLInputElement).value.trim()); setPreview(null); }} /></label>
        <CharacterSearch roster={roster} placeholder="检索角色" onPick={(c) => { setCid(c.id); setPreview(null); }} />
        <button onClick={() => run(true)} disabled={!/^\d+$/.test(cid) || busy !== null || !drafts.hasToken()}>{busy === "check" ? "核对中……" : "预览绑定"}</button>
        <button class="primary" onClick={() => run(false)} disabled={!preview || !preview.dryRun || busy !== null}>{busy === "bind" ? "绑定中……" : "确认绑定"}</button>
      </div>
      {message ? <Notice kind={message.kind === "error" ? "error" : "info"}>{message.text}</Notice> : null}
      {preview ? (
        <section class="pixel-check">
          <h4>{preview.dryRun ? "将要绑定" : "已绑定"}：{preview.name}（{preview.characterId} · <span class="mono">{preview.code}</span>）</h4>
          <p class="small mono">{preview.renamed}</p>
          <ul>{preview.changes.map((c) => <li class="small">{c.auto ? <span class="tag">自动补</span> : null} {c.title}</li>)}</ul>
          {preview.notes?.length ? <ul class="checks">{preview.notes.map((n) => <li class="check-info"><span>{n}</span></li>)}</ul> : null}
          {!preview.dryRun ? <a href={href({ work: "content", shop: "characters", id: preview.characterId, tab: "changes" })}>去 {preview.characterId} 的「本次修改」→</a> : null}
        </section>
      ) : null}
    </div>
  );
}
