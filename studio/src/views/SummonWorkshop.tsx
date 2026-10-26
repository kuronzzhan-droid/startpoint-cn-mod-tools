// 召唤角色工坊：在宿主角色草稿里，从角色（★4 母本）或现有 multiball 克隆一个召唤协力球。
// 母本 → ID / 外观 / 属性 / PF → 面板曲线 → 主动技能 → 援护与寿命 → p13 扩展 → 预检（计划写入的行与检查）→ 写入草稿。
// 只产出 multiball / multiball_level / 曲线 / custom_ability_string 行；技能 DSL 不改，召唤动作参数块交给技能编辑器。
// 接口见 docs/studio/summon.md「前端对接」。
import { useEffect, useMemo, useRef, useState } from "preact/hooks";
import { drafts, onDraftChange } from "../api";
import {
  isSummonFailure, SummonApplied, SummonDetail, SummonFailure, SummonItem, SummonList, SummonPanelSpec, SummonPreview,
  SummonRequest, SummonRow, summons, SummonSkillTemplate, SummonTemplate, SummonTemplateKind, summonElement, summonPfType,
  SUMMON_ELEMENTS, SUMMON_PF_TYPES,
} from "../summonApi";
import { ElementBadge, Notice } from "./common";
import { InfoTip } from "./Delivery";
import { IdField } from "./IdTools";
import { RuleChips, RuleList, ruleCounts } from "./rules";
import "./boss/boss.css";
import "./summon.css";

const INT_MAX = 2147483647;
const CODE = /^[a-z0-9_]+$/;
const POSITIVE_INT = /^[1-9][0-9]*$/;
const KIND_LABEL: Record<SummonTemplateKind, string> = { character: "角色", multiball: "协力球" };

type PanelMode = "source" | "scaled" | "manual";
type LifeMode = "permanent" | "frames" | "seconds";
interface ManualRow { level: string; hp: string; attack: string }

/** Every form field as typed text; turned into a request (plus problems) by buildRequest. */
interface Form {
  template: { kind: SummonTemplateKind; id: string } | null;
  id: string;
  imagePrefix: string;
  element: string; // "" = 继承
  pfType: string; // "" = 继承
  panelMode: PanelMode;
  hpScale: string;
  attackScale: string;
  manual: ManualRow[];
  skillMode: "inherit" | "specified";
  skillKey: string;
  skillLevel: string;
  assist: "" | "true" | "false";
  lifeMode: LifeMode;
  frames: string;
  seconds: string;
  flipEnabled: boolean;
  flipInterval: string;
  pfAction: string;
}

const EMPTY_FORM: Form = {
  template: null, id: "", imagePrefix: "", element: "", pfType: "", panelMode: "source", hpScale: "1", attackScale: "1",
  manual: [{ level: "1", hp: "", attack: "" }], skillMode: "inherit", skillKey: "", skillLevel: "", assist: "",
  lifeMode: "permanent", frames: "", seconds: "", flipEnabled: false, flipInterval: "", pfAction: "",
};

/** A finite number from a text field, or null. */
function num(text: string): number | null {
  if (!text.trim()) return null;
  const value = Number(text);
  return Number.isFinite(value) ? value : null;
}
const isInt = (text: string) => /^-?[0-9]+$/.test(text.trim());

function buildRequest(form: Form): { request: SummonRequest | null; problems: string[] } {
  const problems: string[] = [];
  if (!form.template) return { request: null, problems: ["先选母本"] };
  const request: SummonRequest = { template: form.template };
  const id = form.id.trim();
  if (id) {
    if (!POSITIVE_INT.test(id) || Number(id) > INT_MAX) problems.push("新 multiball ID 要是 1–2147483647 的正整数");
    else request.id = id;
  }
  const prefix = form.imagePrefix.trim();
  if (prefix) {
    if (!CODE.test(prefix)) problems.push("外观前缀只用小写字母、数字和下划线");
    else request.image_prefix = prefix;
  }
  if (form.element !== "") request.element = Number(form.element);
  if (form.pfType !== "") request.pf_type = Number(form.pfType);

  if (form.panelMode === "scaled") {
    const hp = num(form.hpScale), atk = num(form.attackScale);
    const panel: SummonPanelSpec = { mode: "scaled" };
    if (form.hpScale.trim()) { if (hp === null || hp < 1e-15 || hp > INT_MAX) problems.push("HP 倍率须为 1e-15–2147483647 的有限数"); else panel.hp_scale = hp; }
    if (form.attackScale.trim()) { if (atk === null || atk < 1e-15 || atk > INT_MAX) problems.push("攻击倍率须为 1e-15–2147483647 的有限数"); else panel.attack_scale = atk; }
    request.panel = panel;
  } else if (form.panelMode === "manual") {
    const levels: { level: number; hp: number; attack: number }[] = [];
    const seen = new Set<number>();
    form.manual.forEach((row, i) => {
      const level = Number(row.level), hp = num(row.hp), atk = num(row.attack);
      if (!isInt(row.level) || level < 1 || level > INT_MAX) problems.push(`手填第 ${i + 1} 行：等级须为 1–2147483647 整数`);
      else if (seen.has(level)) problems.push(`手填第 ${i + 1} 行：等级 ${level} 重复`);
      if (hp === null || hp < 1) problems.push(`手填第 ${i + 1} 行：HP 须为至少 1 的有限数`);
      if (atk === null || atk < 0) problems.push(`手填第 ${i + 1} 行：攻击须为非负有限数`);
      seen.add(level);
      if (hp !== null && atk !== null) levels.push({ level, hp, attack: atk });
    });
    if (!form.manual.length) problems.push("手填面板至少要一个等级断点");
    request.panel = { mode: "manual", levels };
  }

  const level = form.skillLevel.trim();
  if (level && !POSITIVE_INT.test(level)) problems.push("技能进化档须为正整数");
  if (form.skillMode === "specified") {
    if (!form.skillKey.trim()) problems.push("指定技能时要填 action_skill 键");
    request.skill = { mode: "specified", key: form.skillKey.trim(), ...(level ? { level } : {}) };
  } else if (level) request.skill = { mode: "inherit", level };

  if (form.assist) request.assist = form.assist === "true";

  if (form.lifeMode === "frames") {
    const frames = Number(form.frames);
    if (!isInt(form.frames) || frames < 1 || frames > INT_MAX) problems.push("寿命帧数须为 1–2147483647 整数");
    else request.lifetime = { frames };
  } else if (form.lifeMode === "seconds") {
    const seconds = num(form.seconds);
    if (seconds === null || seconds <= 0 || Math.ceil(seconds * 60) > INT_MAX) problems.push("寿命秒数须为正数，换算成 60fps 帧后不超过 2147483647");
    else request.lifetime = { seconds };
  }

  const extensions: NonNullable<SummonRequest["extensions"]> = {};
  if (form.flipEnabled) {
    const flip: { enabled: boolean; min_interval_frames?: number } = { enabled: true };
    if (form.flipInterval.trim()) {
      const value = Number(form.flipInterval);
      if (!isInt(form.flipInterval) || value < 0 || value > INT_MAX) problems.push("弹板 PF 最小间隔须为 0–2147483647 整数帧");
      else flip.min_interval_frames = value;
    }
    extensions.flip_pf = flip;
  }
  if (form.pfAction.trim()) extensions.ball_pf_action = form.pfAction.trim();
  if (Object.keys(extensions).length) request.extensions = extensions;
  return { request, problems };
}

/** Saved spec → form (「载入编辑」). */
function formOf(spec: SummonRequest & { id: string }): Form {
  const panel = spec.panel ?? { mode: "source" };
  const life = spec.lifetime;
  const ext = spec.extensions ?? {};
  return {
    ...EMPTY_FORM,
    template: spec.template, id: spec.id, imagePrefix: spec.image_prefix ?? "",
    element: spec.element === undefined ? "" : String(spec.element), pfType: spec.pf_type === undefined ? "" : String(spec.pf_type),
    panelMode: panel.mode,
    hpScale: panel.mode === "scaled" ? String(panel.hp_scale ?? 1) : "1",
    attackScale: panel.mode === "scaled" ? String(panel.attack_scale ?? 1) : "1",
    manual: panel.mode === "manual" ? panel.levels.map((p) => ({ level: String(p.level), hp: String(p.hp), attack: String(p.attack) })) : EMPTY_FORM.manual,
    skillMode: spec.skill?.mode ?? "inherit",
    skillKey: spec.skill?.mode === "specified" ? spec.skill.key : "",
    skillLevel: spec.skill?.level ?? "",
    assist: spec.assist === undefined ? "" : spec.assist ? "true" : "false",
    lifeMode: !life ? "permanent" : "frames" in life ? "frames" : "seconds",
    frames: life && "frames" in life ? String(life.frames) : "",
    seconds: life && "seconds" in life ? String(life.seconds) : "",
    flipEnabled: !!ext.flip_pf?.enabled,
    flipInterval: ext.flip_pf?.min_interval_frames === undefined ? "" : String(ext.flip_pf.min_interval_frames),
    pfAction: ext.ball_pf_action ?? "",
  };
}

// ------------------------------------------------------------------------------------- page

export function SummonWorkshop({ characterId }: { characterId: string }) {
  const [list, setList] = useState<SummonList | null>(null);
  const [listError, setListError] = useState<string | null>(null);
  const [form, setForm] = useState<Form>(EMPTY_FORM);
  const [editing, setEditing] = useState<string | null>(null);
  const formRef = useRef<HTMLElement>(null);

  useEffect(() => {
    const load = () => summons.list(characterId).then((r) => { setList(r); setListError(null); }, (e: Error) => setListError(e.message));
    load();
    return onDraftChange((key) => { if (key === characterId) load(); });
  }, [characterId]);

  const edit = (item: SummonItem) => {
    setForm(formOf(item.spec));
    setEditing(item.multiballId);
    formRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <section class="summon-workshop">
      <div class="page-head">
        <div>
          <h2>召唤角色工坊</h2>
          <p class="muted small">在本角色（<span class="mono">{characterId}</span>）的草稿里克隆召唤协力球：只写 multiball、面板曲线和可选 p13 扩展键；
            技能 DSL 不改，把下方给出的召唤动作参数块插进技能后才会真正召唤。</p>
        </div>
      </div>
      <SummonDraftList characterId={characterId} list={list} error={listError} editing={editing} onEdit={edit} />
      <section ref={formRef}>
        <SummonForm characterId={characterId} form={form} setForm={setForm} editing={editing}
          existing={list?.items.map((i) => i.multiballId) ?? []}
          onReset={() => { setForm(EMPTY_FORM); setEditing(null); }} />
      </section>
    </section>
  );
}

// ------------------------------------------------------------------------------------- draft list

function SummonDraftList({ characterId, list, error, editing, onEdit }: {
  characterId: string; list: SummonList | null; error: string | null; editing: string | null; onEdit: (item: SummonItem) => void;
}) {
  const [open, setOpen] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [revertError, setRevertError] = useState<string | null>(null);
  const revert = async (item: SummonItem) => {
    if (!confirm(`撤销召唤角色 ${item.multiballId}？会删除这项草稿改动并释放它的 ID 预留。`)) return;
    setBusy(item.changeId); setRevertError(null);
    try { await summons.revert(characterId, item.changeId); }
    catch (e) { setRevertError((e as Error).message); }
    finally { setBusy(null); }
  };
  return (
    <section class="boss-block summon-list">
      <header><h3>草稿里的召唤角色 {list ? <span class="count">{list.items.length}</span> : null}</h3>
        <InfoTip text="GET /api/drafts/<cid>/summon：本角色草稿中的 summon_clone 改动。读取时会按当前视图重新编译校验，母本输入变化会报错。" />
        {list ? <span class="small muted">{list.status.label} · 视图 {list.version}</span> : null}</header>
      {error ? <Notice kind="error">读取召唤角色失败：{error}</Notice>
        : !list ? <p class="small muted">正在读取……</p>
        : !list.items.length ? <p class="small muted">这个草稿里还没有召唤角色。</p> : (
          <div class="table-scroll">
            <table class="boss-table">
              <thead><tr><th>multiball</th><th>母本</th><th>技能</th><th>面板</th><th>寿命</th><th>检查</th><th></th></tr></thead>
              <tbody>{list.items.map((item) => (
                <>
                  <tr class={editing === item.multiballId ? "summon-editing" : ""}>
                    <td class="mono">{item.multiballId}</td>
                    <td class="small">{KIND_LABEL[item.spec.template.kind]} <span class="mono">{item.spec.template.id}</span></td>
                    <td class="small">{item.skill.name || "—"} <span class="mono muted">{item.skill.key ?? "继承路径"}</span></td>
                    <td class="small"><PanelText panel={item.panel} /></td>
                    <td class="small">{lifeText(item.skillTemplate.lifetimeFrames)}</td>
                    <td><RuleChips counts={ruleCounts(item.checks)} /></td>
                    <td class="summon-actions">
                      <button type="button" class="small-btn" onClick={() => setOpen(open === item.changeId ? null : item.changeId)}>{open === item.changeId ? "收起" : "详情"}</button>
                      <button type="button" class="small-btn" onClick={() => onEdit(item)}>载入编辑</button>
                      <button type="button" class="small-btn" disabled={busy !== null || !drafts.hasToken()} onClick={() => revert(item)}>
                        {busy === item.changeId ? "撤销中……" : "撤销"}</button>
                    </td>
                  </tr>
                  {open === item.changeId ? <tr><td colSpan={7}><SummonDetailView detail={item} /></td></tr> : null}
                </>
              ))}</tbody>
            </table>
          </div>
        )}
      {revertError ? <Notice kind="error">撤销失败：{revertError}</Notice> : null}
      {list?.items.length ? <p class="small muted">保存草稿、生成和导出走角色页的「本次修改」；运行结果：{list.runtime}。</p> : null}
    </section>
  );
}

function lifeText(frames: number) {
  if (frames >= INT_MAX) return "常驻";
  return `${frames} 帧（≈${(frames / 60).toFixed(frames % 60 ? 2 : 0)} 秒）`;
}

function PanelText({ panel }: { panel: SummonDetail["panel"] }) {
  return (
    <span title={`${panel.count} 个等级断点 · 取整：${panel.rounding} · 上下文等级 ${panel.contextLevel}；越界：${panel.outsideDomain}`}>
      Lv{panel.first.level} {panel.first.hp}/{panel.first.attack} → Lv{panel.last.level} {panel.last.hp}/{panel.last.attack}
    </span>
  );
}

// ------------------------------------------------------------------------------------- form

function SummonForm({ characterId, form, setForm, editing, existing, onReset }: {
  characterId: string; form: Form; setForm: (f: Form) => void; editing: string | null; existing: string[]; onReset: () => void;
}) {
  const set = <K extends keyof Form>(key: K, value: Form[K]) => setForm({ ...form, [key]: value });
  const [template, setTemplate] = useState<SummonTemplate | null>(null);
  const [idFree, setIdFree] = useState<boolean | null>(null);
  const [preview, setPreview] = useState<{ key: string; result: SummonPreview | SummonFailure } | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [written, setWritten] = useState<SummonApplied | SummonFailure | null>(null);

  const { request, problems: inputProblems } = useMemo(() => buildRequest(form), [form]);
  const problems = [...inputProblems];
  const ownId = !!form.id.trim() && existing.includes(form.id.trim());
  if (form.id.trim() && idFree === false && !ownId) problems.push(`multiball ID ${form.id.trim()} 已被占用`);
  const key = JSON.stringify(request);
  const fresh = preview?.key === key ? preview.result : null;

  // Template info card for a template set from a saved spec (「载入编辑」).
  useEffect(() => {
    if (!form.template) { setTemplate(null); return; }
    if (template && template.kind === form.template.kind && template.id === form.template.id) return;
    const want = form.template;
    summons.templates(want.id).then((r) => setTemplate(r.items.find((t) => t.kind === want.kind && t.id === want.id) ?? null), () => setTemplate(null));
  }, [form.template?.kind, form.template?.id]);

  const runPreview = async () => {
    if (!request || problems.length) return;
    const mine = key;
    setPreviewing(true); setWritten(null);
    try {
      const result = await summons.preview(characterId, request);
      setPreview({ key: mine, result });
    } catch (e) {
      setPreview({ key: mine, result: { ok: false, error: (e as Error).message, characterId, runtime: "未执行", checks: [{ rule: "summon.inputs", status: "问题", blocking: true, message: (e as Error).message }] } });
    } finally { setPreviewing(false); }
  };
  const write = async () => {
    if (!request || problems.length || !fresh || isSummonFailure(fresh)) return;
    // A blank ID was allocated by the preview; save that ID so the written rows are the ones previewed
    // (the backend still re-checks occupancy on write).
    const body: SummonRequest = request.id ? request : { ...request, id: fresh.multiballId };
    setBusy(true);
    try {
      const result = await summons.apply(characterId, body);
      setWritten(result);
      if (!isSummonFailure(result)) setForm({ ...form, id: result.multiballId });
    } catch (e) {
      setWritten({ ok: false, error: (e as Error).message, characterId, runtime: "未执行", checks: [] });
    } finally { setBusy(false); }
  };

  const tplElement = template ? summonElement(template.element) : null;
  return (
    <section class="boss-block summon-form">
      <header>
        <h3>{editing ? <>修改召唤角色 <span class="mono">{editing}</span></> : "新召唤角色"}</h3>
        <span class="spacer" />
        <button type="button" class="ghost small-btn" onClick={() => { onReset(); setPreview(null); setWritten(null); setTemplate(null); }}>清空表单</button>
      </header>

      <fieldset class="param-block">
        <legend>1. 母本</legend>
        <TemplatePicker selected={form.template} onPick={(t) => {
          setTemplate(t);
          setForm({ ...form, template: { kind: t.kind, id: t.id }, skillKey: form.skillKey || (t.skill.key ?? "") });
        }} />
        {form.template ? (
          <p class="summon-picked small">已选：<span class="tag">{KIND_LABEL[form.template.kind]}</span>
            {template ? <> <strong>{template.name}</strong> <span class="mono">{template.id}</span> <ElementBadge element={summonElement(template.element)} />
              {" "}PF {summonPfType(template.pfType)} · 外观 <span class="mono">{template.imagePrefix}</span> · 技能 {template.skill.name}
              <span class="mono muted"> {template.skill.key ?? template.skill.path}{template.skill.level ? ` / 档 ${template.skill.level}` : ""}</span>
              {!template.panelAvailable ? <span class="warn-text"> · 母本没有面板曲线，只能手填</span> : null}</>
              : <span class="mono"> {form.template.id}</span>}
          </p>
        ) : null}
        {form.template?.kind === "character" ? <p class="small muted">召唤角色一般取 ★4 角色作母本；列表不按星级过滤，是否可生成以预检为准。</p> : null}
      </fieldset>

      <fieldset class="param-block">
        <legend>2. ID、外观、属性与 PF</legend>
        <div class="param-fields">
          <IdField kind="multiball" label="新 multiball ID（留空自动分配）" value={form.id} onChange={(v) => set("id", v)}
            placeholder="例如 1990001" onAvailability={setIdFree} />
          <label class="param-field"><span>外观前缀 image_prefix</span>
            <input class="mono" value={form.imagePrefix} placeholder={template?.imagePrefix ?? "留空沿用母本"}
              onInput={(e) => set("imagePrefix", (e.target as HTMLInputElement).value.trim())} />
            <span class="small muted">写入 multiball c1；只引用已有外观，不复制素材</span></label>
          <label class="param-field"><span>属性</span>
            <select value={form.element} onChange={(e) => set("element", (e.target as HTMLSelectElement).value)}>
              <option value="">继承母本{tplElement ? `（${tplElement}）` : ""}</option>
              {SUMMON_ELEMENTS.map((e, i) => <option value={String(i)}>{e}</option>)}
            </select>
            <span class="small muted">只改召唤球属性；沿用技能的 DSL 元素不改写</span></label>
          <label class="param-field"><span>PF 类型</span>
            <select value={form.pfType} onChange={(e) => set("pfType", (e.target as HTMLSelectElement).value)}>
              <option value="">继承母本{template ? `（${summonPfType(template.pfType)}）` : ""}</option>
              {SUMMON_PF_TYPES.map((p, i) => <option value={String(i)}>{p}</option>)}
            </select></label>
        </div>
        {ownId ? <p class="small warn-text">这个 ID 是本草稿已有的召唤角色：写入会替换它。</p> : null}
        {!form.id.trim() ? <p class="small muted">留空时预检会查询一个空闲 ID；查询不预留，写入时按预检显示的 ID 再检查一次占用。</p> : null}
      </fieldset>

      <fieldset class="param-block">
        <legend>3. 面板曲线</legend>
        <div class="summon-radios">
          <label class="check"><input type="radio" checked={form.panelMode === "source"} onChange={() => set("panelMode", "source")} />沿用母本曲线</label>
          <label class="check"><input type="radio" checked={form.panelMode === "scaled"} onChange={() => set("panelMode", "scaled")} />母本曲线 × 倍率</label>
          <label class="check"><input type="radio" checked={form.panelMode === "manual"} onChange={() => set("panelMode", "manual")} />手填等级断点</label>
          <InfoTip text="只表达基础曲线，不含玛纳板、觉醒、编队加成。最终面板按客户端口径取整，以预检返回的面板摘要为准。" />
        </div>
        {form.panelMode === "scaled" ? (
          <div class="param-fields">
            <label class="param-field"><span>HP 倍率</span><input value={form.hpScale} onInput={(e) => set("hpScale", (e.target as HTMLInputElement).value)} /></label>
            <label class="param-field"><span>攻击倍率</span><input value={form.attackScale} onInput={(e) => set("attackScale", (e.target as HTMLInputElement).value)} /></label>
          </div>
        ) : form.panelMode === "manual" ? (
          <ManualLevels rows={form.manual} onChange={(rows) => set("manual", rows)} />
        ) : null}
      </fieldset>

      <fieldset class="param-block">
        <legend>4. 主动技能</legend>
        <div class="summon-radios">
          <label class="check"><input type="radio" checked={form.skillMode === "inherit"} onChange={() => set("skillMode", "inherit")} />继承母本技能</label>
          <label class="check"><input type="radio" checked={form.skillMode === "specified"} onChange={() => set("skillMode", "specified")} />指定 action_skill 键</label>
        </div>
        <div class="param-fields">
          {form.skillMode === "specified" ? (
            <label class="param-field"><span>action_skill 键</span>
              <input class="mono" value={form.skillKey} placeholder={template?.skill.key ?? ""} onInput={(e) => set("skillKey", (e.target as HTMLInputElement).value.trim())} /></label>
          ) : null}
          <label class="param-field"><span>进化档 level（可选）</span>
            <input class="mono" value={form.skillLevel} placeholder="留空取最高数值档" onInput={(e) => set("skillLevel", (e.target as HTMLInputElement).value.trim())} />
            <span class="small muted">{form.template?.kind === "multiball" && form.skillMode === "inherit"
              ? "球母本留空保留原 c9–c19；填了档位要能唯一反查技能键" : "决定 c9 技能路径与 c11 weight（原生充能参数，不是秒数）"}</span></label>
        </div>
      </fieldset>

      <fieldset class="param-block">
        <legend>5. 援护与寿命</legend>
        <div class="param-fields">
          <label class="param-field"><span>援护布局 c8</span>
            <select value={form.assist} onChange={(e) => set("assist", (e.target as HTMLSelectElement).value as Form["assist"])}>
              <option value="">默认（角色母本 = 是，球母本 = 继承）</option>
              <option value="true">是</option>
              <option value="false">否</option>
            </select></label>
          <label class="param-field"><span>寿命</span>
            <select value={form.lifeMode} onChange={(e) => set("lifeMode", (e.target as HTMLSelectElement).value as LifeMode)}>
              <option value="permanent">常驻（默认 2147483647 帧）</option>
              <option value="frames">按帧</option>
              <option value="seconds">按秒（60fps 向上取整）</option>
            </select></label>
          {form.lifeMode === "frames" ? (
            <label class="param-field"><span>帧数</span><input value={form.frames} placeholder="例如 1800" onInput={(e) => set("frames", (e.target as HTMLInputElement).value.trim())} /></label>
          ) : form.lifeMode === "seconds" ? (
            <label class="param-field"><span>秒数</span><input value={form.seconds} placeholder="例如 30" onInput={(e) => set("seconds", (e.target as HTMLInputElement).value.trim())} />
              {num(form.seconds) !== null && num(form.seconds)! > 0 ? <span class="small muted">= {Math.ceil(num(form.seconds)! * 60)} 帧</span> : null}</label>
          ) : null}
        </div>
        <p class="small muted">multiball 表没有寿命列：寿命只进召唤动作参数块，技能 DSL 接入后才生效。</p>
      </fieldset>

      <fieldset class="param-block">
        <legend>6. p13 扩展（可选）</legend>
        <div class="param-fields">
          <label class="param-field"><span>弹板 PF</span>
            <label class="check"><input type="checkbox" checked={form.flipEnabled} onChange={(e) => set("flipEnabled", (e.target as HTMLInputElement).checked)} />
              启用（写 wfx_summon_flip_pf_&lt;id&gt;）</label></label>
          {form.flipEnabled ? (
            <label class="param-field"><span>最小间隔帧（可选）</span>
              <input value={form.flipInterval} placeholder="留空 = 不限" onInput={(e) => set("flipInterval", (e.target as HTMLInputElement).value.trim())} /></label>
          ) : null}
          <label class="param-field"><span>球 PF 动作键（可选）</span>
            <input class="mono" value={form.pfAction} placeholder="power_flip_action 键" onInput={(e) => set("pfAction", (e.target as HTMLInputElement).value.trim())} />
            <span class="small muted">只引用已有三档动作，不克隆动作与资源</span></label>
        </div>
        <p class="small muted">需要客户端 p13 能力（client.summon.flip_pf@1 / client.ball.pf_action@1）；是否支持在交付时按目标 APK 检查。</p>
      </fieldset>

      <fieldset class="param-block">
        <legend>7. 预检与写入 <InfoTip text="POST /api/drafts/<cid>/summon?preview=true：与写入相同的校验与编译，不写草稿、不预留 ID。改了任何参数都要重新预检。" /></legend>
        {problems.length ? <ul class="inline-problems">{problems.map((p) => <li>{p}</li>)}</ul> : null}
        <div class="save-row">
          <button type="button" disabled={!request || problems.length > 0 || previewing} onClick={runPreview}>{previewing ? "预检中……" : fresh ? "重新预检" : "预检"}</button>
          <button type="button" class="primary" disabled={busy || problems.length > 0 || !fresh || isSummonFailure(fresh) || !drafts.hasToken()} onClick={write}
            title={!fresh ? "先按当前参数预检" : isSummonFailure(fresh) ? "预检被拒绝，不能写入" : !drafts.hasToken() ? "页面缺少编辑令牌" : ""}>
            {busy ? "写入中……" : editing || ownId ? "写入草稿（替换）" : "写入草稿"}</button>
          <span class="small muted">{problems.length ? problems[0] : previewing ? "预检中……" : !fresh ? (preview ? "参数已改，需要重新预检" : "预检后可写入")
            : isSummonFailure(fresh) ? "预检被拒绝" : "预检未被拒绝，可以写入（运行与 APK 检查仍未执行）"}</span>
        </div>
        {written ? (isSummonFailure(written)
          ? <Notice kind="error"><strong>写入被拒绝</strong>：{written.error}{written.checks.length ? <RuleList checks={written.checks} /> : null}</Notice>
          : <Notice>已写入草稿：召唤角色 <strong class="mono">{written.multiballId}</strong>（{written.status.label}）。保存、生成在角色页「本次修改」。</Notice>) : null}
        {fresh ? (isSummonFailure(fresh)
          ? <Notice kind="error"><strong>预检被拒绝</strong>：{fresh.error}<RuleList checks={fresh.checks} /></Notice>
          : <SummonPreviewView preview={fresh} />) : null}
      </fieldset>
    </section>
  );
}

function ManualLevels({ rows, onChange }: { rows: ManualRow[]; onChange: (rows: ManualRow[]) => void }) {
  const update = (i: number, field: keyof ManualRow, value: string) => onChange(rows.map((r, j) => (j === i ? { ...r, [field]: value } : r)));
  return (
    <div class="summon-manual">
      <table class="boss-table">
        <thead><tr><th>等级</th><th>HP</th><th>攻击</th><th></th></tr></thead>
        <tbody>{rows.map((r, i) => (
          <tr>
            <td><input class="mono" value={r.level} onInput={(e) => update(i, "level", (e.target as HTMLInputElement).value.trim())} /></td>
            <td><input class="mono" value={r.hp} onInput={(e) => update(i, "hp", (e.target as HTMLInputElement).value.trim())} /></td>
            <td><input class="mono" value={r.attack} onInput={(e) => update(i, "attack", (e.target as HTMLInputElement).value.trim())} /></td>
            <td><button type="button" class="small-btn" disabled={rows.length <= 1} onClick={() => onChange(rows.filter((_, j) => j !== i))}>删除</button></td>
          </tr>
        ))}</tbody>
      </table>
      <button type="button" class="small-btn" onClick={() => onChange([...rows, { level: "", hp: "", attack: "" }])}>加一行</button>
      <span class="small muted"> 断点之间按原生口径插值，最终面板向下取整；调用等级须落在断点定义域内。</span>
    </div>
  );
}

// ------------------------------------------------------------------------------------- template search

function TemplatePicker({ selected, onPick }: { selected: Form["template"]; onPick: (t: SummonTemplate) => void }) {
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState<"" | SummonTemplateKind>("");
  const [result, setResult] = useState<{ items: SummonTemplate[]; total: number } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const seq = useRef(0);
  useEffect(() => {
    const mine = ++seq.current;
    const timer = window.setTimeout(() => {
      summons.templates(query).then(
        (r) => { if (mine === seq.current) { setResult({ items: r.items, total: r.total }); setError(null); } },
        (e: Error) => { if (mine === seq.current) setError(e.message); });
    }, 250);
    return () => window.clearTimeout(timer);
  }, [query]);
  const items = (result?.items ?? []).filter((t) => !kind || t.kind === kind);
  const shown = items.slice(0, 80);
  return (
    <div class="summon-picker">
      <div class="summon-picker-bar">
        <input class="search small-search" type="search" value={query} placeholder="搜索母本：名称、ID、外观代码、技能"
          onInput={(e) => setQuery((e.target as HTMLInputElement).value)} />
        <select aria-label="母本种类" value={kind} onChange={(e) => setKind((e.target as HTMLSelectElement).value as "" | SummonTemplateKind)}>
          <option value="">角色与协力球</option>
          <option value="character">只看角色</option>
          <option value="multiball">只看协力球</option>
        </select>
        {result ? <span class="small muted">{items.length} 个{items.length > shown.length ? `，显示前 ${shown.length} 个` : ""}</span> : null}
      </div>
      {error ? <Notice kind="error">母本列表读取失败：{error}</Notice>
        : !result ? <p class="small muted">正在读取母本……</p>
        : !shown.length ? <p class="small muted">没有匹配的母本。</p> : (
          <ul class="clone-donors summon-templates">
            {shown.map((t) => (
              <li><button type="button" class={"source-option" + (selected?.kind === t.kind && selected.id === t.id ? " on" : "")} onClick={() => onPick(t)}>
                <ElementBadge element={summonElement(t.element)} />
                <span>{t.name} <span class="small muted"><span class="tag">{KIND_LABEL[t.kind]}</span> <span class="mono">{t.id}</span> · {summonPfType(t.pfType)} · {t.skill.name}
                  {!t.panelAvailable ? <span class="warn-text"> · 无面板曲线</span> : null}</span></span>
              </button></li>
            ))}
          </ul>
        )}
    </div>
  );
}

// ------------------------------------------------------------------------------------- preview / detail

function SummonPreviewView({ preview }: { preview: SummonPreview }) {
  const a = preview.allocation;
  return (
    <div class="summon-preview">
      <dl class="kv alloc">
        <dt>新 multiball ID</dt>
        <dd><span class="mono">{preview.multiballId}</span>
          <span class={"small " + (a.available ? "state-ok" : "error-text")}>{a.available ? "当前空闲" : "已占用"}</span>
          {!a.serverChecked ? <span class="small warn-text">服务端镜像未核对（编辑台启动时没有 --server-dir）</span> : null}
          <span class="small muted">查询不预留 · 视图 {a.viewVersion}</span></dd>
      </dl>
      <SummonDetailView detail={preview} />
    </div>
  );
}

function SummonDetailView({ detail }: { detail: SummonDetail }) {
  const preserved = Object.entries(detail.preservedColumns);
  return (
    <div class="summon-detail">
      <dl class="kv">
        <dt>主动技能</dt><dd>{detail.skill.name || "—"} <span class="mono small">{detail.skill.key ?? "（直接继承球路径）"}{detail.skill.level ? ` / 档 ${detail.skill.level}` : ""}</span>
          <span class="mono small muted">{detail.skill.path}</span></dd>
        <dt>面板</dt><dd><PanelText panel={detail.panel} /><span class="small muted">{detail.panel.count} 个等级 · 取整 {detail.panel.rounding} · 上下文等级 {detail.panel.contextLevel}</span></dd>
        <dt>客户端能力</dt><dd>{detail.requires.length ? detail.requires.map((r) => <span class="tag mono">{r}</span>) : <span class="muted small">无</span>}</dd>
        <dt>预留</dt><dd class="mono small">{Object.entries(detail.reservations).filter(([, v]) => v.length).map(([k, v]) => `${k}: ${v.join("、")}`).join("；") || "—"}</dd>
        <dt>实测</dt><dd class="state-none">{detail.runtime}</dd>
      </dl>
      <RuleList checks={detail.checks} title="检查" />
      <h4>计划写入的行（{detail.rows.length}）</h4>
      <div class="table-scroll">
        <table class="boss-table">
          <thead><tr><th>表</th><th>键</th><th>内容</th></tr></thead>
          <tbody>{detail.rows.map((row) => <tr><td class="mono small">{row.logical}</td><td class="mono small">{row.key}</td><td><RowContent row={row} /></td></tr>)}</tbody>
        </table>
      </div>
      {preserved.length ? (
        <details class="tech"><summary>保留母本原值的列（{preserved.length}）</summary>
          <p class="small muted">这些列照抄母本，编辑台不推断它们的行为。</p>
          <dl class="kv summon-cols">{preserved.map(([col, value]) => <><dt class="mono">{col}</dt><dd class="mono small">{value === "" ? "（空）" : value}</dd></>)}</dl>
        </details>
      ) : null}
      <SkillTemplateBlock template={detail.skillTemplate} />
    </div>
  );
}

function RowContent({ row }: { row: SummonRow }) {
  if (row.rows) {
    return (
      <div class="summon-cells">
        {row.rows.map((cells) => <div>{cells.map((cell, i) => <span class="summon-cell" title={`c${i}`}><i>c{i}</i>{cell === "" ? "∅" : cell}</span>)}</div>)}
      </div>
    );
  }
  const levels = Object.entries(row.levels ?? {});
  if (!levels.length) return <span class="muted small">—</span>;
  const [first, last] = [levels[0], levels[levels.length - 1]];
  return (
    <details class="tech"><summary class="small">{levels.length} 个等级：Lv{first[0]} = {first[1]} … Lv{last[0]} = {last[1]}</summary>
      <div class="summon-levels mono small">{levels.slice(0, 300).map(([lv, v]) => <span>Lv{lv}={v}</span>)}
        {levels.length > 300 ? <span class="muted">……另 {levels.length - 300} 个</span> : null}</div>
    </details>
  );
}

function SkillTemplateBlock({ template }: { template: SummonSkillTemplate }) {
  const [copied, setCopied] = useState<string | null>(null);
  const node = JSON.stringify(template.node);
  const copy = (label: string, text: string) => {
    navigator.clipboard?.writeText(text).then(() => setCopied(label), () => setCopied(null));
  };
  return (
    <div class="param-block summon-handoff">
      <h4>在技能里召唤这个 ID <InfoTip text="skillTemplate：给技能编辑器用的召唤动作。inserted=false 表示技能 DSL 还没改；插入后仍要编译、预载并上设备验证。" /></h4>
      <dl class="kv">
        <dt>命令</dt><dd class="mono">{template.command}</dd>
        <dt>multiball</dt><dd class="mono">{template.multiballId}</dd>
        <dt>寿命</dt><dd>{lifeText(template.lifetimeFrames)} <span class="mono small muted">{template.lifetimeFrames}</span></dd>
        <dt>回调主体</dt><dd class="mono">{template.callbackSubjectIds.join("、")} <span class="small muted">示例 ID，接入已有技能时要换成未占用且互异的主体 ID</span></dd>
        <dt>已插入 DSL</dt><dd class={template.inserted ? "state-ok" : "warn-text"}>{template.inserted ? "是" : "否（只生成了表行）"}</dd>
      </dl>
      <pre class="summon-code mono small">{node}</pre>
      <div class="save-row">
        <button type="button" class="small-btn" onClick={() => copy("node", node)}>复制 node（插入 Block）</button>
        <button type="button" class="small-btn" onClick={() => copy("params", JSON.stringify(template.parameters))}>复制参数数组</button>
        {copied ? <span class="small state-ok">已复制{copied === "node" ? " node" : "参数数组"}</span> : null}
      </div>
      {template.instructions?.length ? <ul class="small">{template.instructions.map((t) => <li>{t}</li>)}</ul> : null}
    </div>
  );
}
