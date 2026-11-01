import { useEffect, useState } from "preact/hooks";
import { DraftView } from "../../api";
import { Json } from "../../modeApi";
import { href } from "../../router";
import { ScenePreview as Preview, SceneRead, SceneSpec, sceneDeliveries, scenes } from "../../sceneApi";
import { Notice } from "../common";
import { DeliveryPanel } from "../Delivery";
import { useWorkshopAction } from "../workshopKit";
import { ScenePath, SceneSpecFields } from "./SceneSpecFields";
import { ScenePreview } from "./ScenePreview";
import { SceneCloneForm, SceneCreationSummary } from "./SceneCloneForm";
import "./modes.css";
import "./scene.css";

const ID = "hell-pumpkin";
const SLOT_RE = /^(?:hell-pumpkin|scene-[3-9][0-9]{5})$/;
const format = (value: unknown) => JSON.stringify(value, null, 2);

export function slotForSpec(spec: SceneSpec | null | undefined, fallback = ID): string {
  if (!spec || typeof spec !== "object") return fallback;
  const specId = typeof spec.id === "string" ? spec.id : "";
  if (SLOT_RE.test(specId)) return specId;
  const eventId = spec.event && typeof spec.event === "object" && typeof spec.event.id === "string" ? spec.event.id : "";
  if (spec.creation && /^[3-9][0-9]{5}$/.test(eventId) && eventId !== "300097") return `scene-${eventId}`;
  return fallback;
}

export function BossSceneWorkshop({ tab = "edit" }: { tab?: string }) {
  const [read, setRead] = useState<SceneRead | null>(null);
  const [text, setText] = useState("");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [invalidFields, setInvalidFields] = useState<Record<string, string>>({});
  const [delivery, setDelivery] = useState<"generate" | "export">("generate");
  const action = useWorkshopAction();
  const applyRead = (data: SceneRead) => {
    setRead(data);
    setText(data.payload ? format(data.payload) : "");
    setPreview(data.preview ?? data.draft?.preview ?? null);
    setInvalidFields({});
  };
  useEffect(() => {
    let alive = true;
    (async () => {
      const initial = await scenes.read(ID);
      const data = !initial.draft && initial.migratedSlot ? await scenes.read(initial.migratedSlot) : initial;
      if (alive) applyRead(data);
    })().catch(e => alive && setError((e as Error).message));
    return () => { alive = false; };
  }, []);

  const parsed = parseSceneText(text);
  const payload = parsed.payload;
  const activeSlot = slotForSpec(payload, read?.slot ?? ID);
  const draftMatchesSlot = !!read?.draft && (!read.draft.characterId || read.draft.characterId === activeSlot);
  const activeDraft = draftMatchesSlot ? read!.draft : null;
  const slotSummary = Array.isArray(read?.drafts) ? read!.drafts.find(item => item.slot === activeSlot) : undefined;
  const activeRevision = activeDraft?.revision ?? slotSummary?.revision ?? 0;
  const valid = !!payload && !Object.keys(invalidFields).length;
  const saved = valid && !!activeDraft && JSON.stringify(payload) === JSON.stringify(activeDraft.payload)
    && activeDraft.baseView === read?.version;
  const allowed = saved && !!preview?.canGenerate;
  const view: DraftView = { characterId: activeSlot, changeset: activeDraft,
    status: { state: saved ? "saved" : "dirty", label: saved ? "已保存" : "尚未保存", changes: 1 }, actions: [] };
  const changeText = (value: string) => { setText(value); setPreview(null); setInvalidFields({}); };
  const openSlot = (slot: string) => action.run(async () => applyRead(await scenes.read(slot)));
  const changeSetting = (path: ScenePath, value: Json | undefined, issue: string | null) => {
    setPreview(null);
    const key = JSON.stringify(path);
    setInvalidFields(current => {
      const next = { ...current };
      if (issue) next[key] = issue; else delete next[key];
      return next;
    });
    if (issue || value === undefined || !payload) return;
    const next = structuredClone(payload);
    let parent: any = next;
    for (const part of path.slice(0, -1)) parent = parent[part];
    parent[path.at(-1)!] = value;
    setText(format(next));
  };
  const submit = (save: boolean) => action.run(async () => {
    if (!payload || !valid) throw new Error("请修正规格 JSON 和输入错误后再预览。");
    const result = save ? await scenes.save(payload, activeRevision, activeSlot) : await scenes.preview(payload, activeSlot);
    setPreview(result);
    if (result.draft && read) {
      setRead({
        ...read,
        slot: activeSlot,
        payload: result.draft.payload,
        draft: result.draft,
        drafts: result.drafts ?? read.drafts,
      });
    }
    if (save) await sceneDeliveries.finished(activeSlot);
  });
  const clone = (name: string) => action.run(async () => {
    if (!payload || !valid || payload.creation) throw new Error("请先载入有效的已有活动母本规格。");
    const result = await scenes.clone(payload, name);
    const nextSlot = result.slot ?? slotForSpec(result.payload);
    if (read) {
      setRead({
        ...read,
        slot: nextSlot,
        payload: result.payload,
        draft: result.draft ?? null,
        drafts: result.drafts ?? read.drafts,
        preview: result.preview,
      });
    }
    changeText(format(result.payload));
    setPreview(result.preview);
  });
  const savedSlots = Array.isArray(read?.drafts) ? read!.drafts : [];
  const motherSummary = savedSlots.find(item => item.slot === ID);
  const cloneSummaries = savedSlots.filter(item => item.slot !== ID);
  const route = (next: string) => href({ work: "content", shop: "boss", quest: "scene-spec", tab: next });
  return <section class="page mode-workshop scene-workshop">
    <a class="back" href={href({ work: "content", shop: "boss" })}>← BOSS 工坊</a>
    <div class="page-head"><div><h1>场景 BOSS · 规格工坊</h1>
      <p class="muted">{typeof payload?.name === "string" ? payload.name : read?.payload?.name ?? "地狱南瓜"} · 槽位 {activeSlot} · 当前视图 {read?.version ?? "读取中"}</p></div>
      <a class="header-btn" href={href({ work: "content", shop: "boss", wizard: true })}>新建共同决战 · 简单模式</a>
    </div>
    <nav class="segmented" aria-label="场景规格工作区">
      <a class={tab !== "delivery" ? "on" : ""} href={route("edit")}>规格与门禁</a>
      <a class={tab === "delivery" ? "on" : ""} href={route("delivery")}>本地交付</a>
    </nav>
    {error || action.error ? <Notice kind="error">{error || action.error}</Notice> : null}
    {read?.migratedSlot ? <Notice kind="info">已将旧版单槽克隆草稿自动迁移到独立槽位 {read.migratedSlot}，母本与克隆草稿不再互相覆盖。</Notice> : null}
    {!read && !error ? <p class="loading">正在读取场景规格和当前链资源……</p> : null}
    {read ? <>
      <div class="version-row scene-slots" aria-label="场景草稿槽位">
        <span class="small muted">草稿槽位：</span>
        <button class={activeSlot === ID ? "primary" : ""} disabled={action.busy} onClick={() => openSlot(ID)}>
          母本 · 地狱南瓜{motherSummary ? `（修订 ${motherSummary.revision}）` : ""}</button>
        {cloneSummaries.map(item => <button key={item.slot} class={activeSlot === item.slot ? "primary" : ""}
          disabled={action.busy} onClick={() => openSlot(item.slot)}>
          {item.eventId} · {item.name}（修订 {item.revision}）</button>)}
      </div>
      <div hidden={tab === "delivery"}>
        <p class="small muted">活动行、五档、阶段、换场地、换 BGM、召唤物、机关、试炼、商店和掉落一并编译。
          预览不保存；母本（hell-pumpkin）与每个克隆活动（scene-&lt;event&gt;）各自独立分槽保存。</p>
        <p class="small muted">规格来源版本：{typeof payload?.sourceVersion === "string" ? payload.sourceVersion : read.payload?.sourceVersion ?? "尚未加载"}
          {payload?.provenance?.note ? ` · ${payload.provenance.note}` : ""}</p>
        <fieldset disabled={action.busy} class="mode-editor">
          <div class="version-row scene-import">
            <label>导入规格 JSON <input type="file" accept=".json,application/json" onChange={e => {
              const file = e.currentTarget.files?.[0];
              if (file) action.run(async () => changeText(await file.text()));
              e.currentTarget.value = "";
            }} /></label>
            <a href={scenes.schemaUrl} target="_blank" rel="noreferrer">查看规格 schema</a>
            <button disabled={!read.payload} onClick={() => changeText(format(read.payload))}>
              {activeDraft ? "恢复当前槽已保存规格" : "恢复当前链规格"}</button>
            {activeDraft || payload?.creation ? <button disabled={!read.spec} onClick={() => changeText(format(read.spec))}>载入当前链母本</button> : null}
          </div>
          {payload?.creation ? <SceneCreationSummary spec={payload} /> : <SceneCloneForm disabled={!valid} onClone={clone} />}
          {payload && hasSceneFields(payload) ? <SceneSpecFields spec={payload} change={changeSetting} /> : null}
          <details open={!payload || !hasSceneFields(payload)}><summary>高级 JSON：完整规格、资源与编译绑定</summary>
            <label>完整规格 <textarea class="scene-spec-editor mono" aria-label="场景 BOSS 完整规格 JSON" spellcheck={false}
              value={text} onInput={e => changeText(e.currentTarget.value)} /></label>
          </details>
          {parsed.error ? <Notice kind="error">{parsed.error}</Notice> : null}
          {Object.keys(invalidFields).length ? <Notice kind="error">有 {Object.keys(invalidFields).length} 个输入无效，预览和生成已停用。</Notice> : null}
          <div class="version-row">
            <button disabled={!valid} onClick={() => submit(false)}>只读编译与校验</button>
            <button class="primary" disabled={!valid || !preview?.ok} onClick={() => submit(true)}>保存独立草稿</button>
            <span class="small muted">{saved ? `已保存（${activeSlot} · 修订 ${activeDraft?.revision}）` : `尚有未保存内容（目标槽 ${activeSlot}）`}</span>
          </div>
        </fieldset>
        {action.busy ? <p class="loading">正在编译规格并核验资源……</p> : null}
        {preview ? <ScenePreview result={preview} /> : <p class="muted">修改规格后请重新预览。旧检查结果不会用于新内容。</p>}
      </div>
      {tab === "delivery" ? <>
        {!allowed ? <Notice kind="warn">{preview?.blockers?.join("；") || "请先通过规格门禁并保存当前草稿，才可生成交付。"}</Notice> : null}
        <fieldset disabled={action.busy || (delivery === "generate" && !allowed)} class="mode-editor">
          <DeliveryPanel characterId={activeSlot} view={view} mode={delivery} onMode={setDelivery}
            api={sceneDeliveries} allowServerApply={false} />
        </fieldset>
        {!allowed && delivery === "generate" ? <button onClick={() => setDelivery("export")}>查看已有交付</button> : null}
      </> : null}
    </> : null}
  </section>;
}

export function parseSceneText(text: string): { payload: SceneSpec | null; error: string | null } {
  if (!text.trim()) return { payload: null, error: "请输入规格 JSON。" };
  try {
    const payload = JSON.parse(text);
    if (!payload || typeof payload !== "object" || Array.isArray(payload)) throw new Error("规格必须是 JSON 对象");
    return { payload: payload as SceneSpec, error: null };
  } catch (e) { return { payload: null, error: `规格 JSON 无效：${(e as Error).message}` }; }
}

function hasSceneFields(spec: SceneSpec): boolean {
  const settings = (value: unknown): boolean => Array.isArray(value) && value.every(setting => setting
    && typeof setting === "object" && "value" in setting && typeof setting.id === "string"
    && typeof setting.kind === "string" && Array.isArray(setting.bindings));
  const group = (value: unknown): boolean => !!value && typeof value === "object"
    && "id" in value && typeof value.id === "string" && "settings" in value && settings(value.settings)
    && (!("name" in value) || typeof value.name === "string") && (!("quest" in value) || typeof value.quest === "string");
  return group(spec.event) && [spec.tiers, spec.phases, spec.shops, spec.drops].every(value => Array.isArray(value) && value.every(group))
    && [spec.summons, spec.mechanisms, spec.trials].every(settings);
}
