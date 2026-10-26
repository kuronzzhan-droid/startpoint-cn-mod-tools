// 技能模板：搜索官方技能作母本 → 看各档伤害节点（路径、原系数、元素、归属）与特效族 → 新 action_skill 键、
// 全局倍率或逐节点系数、属性改写、伤害归属、特效换色、开头召唤 → 预检（改动摘要 + 五态检查）→ 写入草稿。
// 接口：docs/studio/skill-templates.md。母本只读官方基线；预检不写文件、不预留键；写入只进本角色草稿。
import { useEffect, useMemo, useRef, useState } from "preact/hooks";
import { ability, api, CharacterDetail, DraftChange, drafts, RuleResult } from "../api";
import {
  ATTRIBUTION_LABEL, Coefficient, COEFFICIENT_KIND_LABEL, DamageNode, elementName, SKILL_ELEMENTS, SkillTemplateDetail,
  SkillTemplateList, SkillTemplateRequest, SkillTemplateResult, skillTemplates, SummonBlock,
} from "../skillTemplateApi";
import { ElementBadge, Notice } from "./common";
import { InfoTip } from "./Delivery";
import { RuleList } from "./rules";
import "./boss/boss.css";
import "./skillpf.css";

const NEW_KEY = /^[A-Za-z0-9_][A-Za-z0-9_-]{0,127}$/;
const HEX = /^#[0-9A-Fa-f]{6}$/;
const BOUND = /^(min|max|alv[2-6]?_(min|max))$/;
const MAX_DURATION = 2147483647;

type RecolorMode = "none" | "hue" | "pairs";
interface Pair { from: string; to: string }
interface SummonForm { on: boolean; multiballId: string; maxCount: string; selfOnly: boolean; durationFrames: string; effectPrefix: string }
const EMPTY_SUMMON: SummonForm = { on: false, multiballId: "", maxCount: "1", selfOnly: true, durationFrames: "", effectPrefix: "" };

/** A node takes a single number only when it has one term with exactly min/max and no vlv (backend rule). */
function simpleNode(node: DamageNode): boolean {
  if (node.coefficient.length !== 1) return false;
  const term = node.coefficient[0];
  return Object.keys(term).filter((k) => BOUND.test(k)).length === 2 && "min" in term && "max" in term && !term.vlv;
}

function termText(term: Coefficient): string {
  const min = term.min, max = term.max;
  const base = min === max ? String(min) : `${min}–${max}`;
  const extra = Object.keys(term).filter((k) => k !== "min" && k !== "max");
  return extra.length ? `${base} (+${extra.join(",")})` : base;
}
const coefText = (c: Coefficient[]) => c.map(termText).join(" ; ");

function nodeElement(node: DamageNode): string {
  if (node.constructor !== "CreateNormalAttack") return "无独立元素参数";
  if (node.elementInherited) return "继承（255）";
  return elementName(node.element) ?? (node.elementCode === null ? "—" : `码 ${node.elementCode}`);
}

/** Pasted summon-workshop output: the skillTemplate block, a whole POST/GET item containing it, or a plain summon object. */
function parseSummonPaste(text: string): { form?: Partial<SummonForm>; notes: string[]; error?: string } {
  let value: any;
  try { value = JSON.parse(text); } catch (e) { return { notes: [], error: "不是有效 JSON：" + (e as Error).message }; }
  if (Array.isArray(value?.items) && value.items.length) value = value.items[0];
  const outer = value?.skillTemplate ?? value;
  const block = outer?.summon ?? outer;
  if (!block || typeof block !== "object") return { notes: [], error: "没有找到参数对象" };
  const notes: string[] = [];
  const id = block.multiballId ?? (Array.isArray(block.parameters) ? block.parameters[1] : undefined);
  if (id === undefined || id === null || !/^[1-9][0-9]{0,9}$/.test(String(id))) return { notes, error: "参数块里没有合法的 multiballId" };
  const form: Partial<SummonForm> = { on: true, multiballId: String(id) };
  const life = block.lifetimeFrames ?? block.durationFrames;
  if (typeof life === "number") {
    if (Number.isInteger(life) && life >= 1 && life <= MAX_DURATION) { form.durationFrames = String(life); notes.push(`寿命 ${life} 帧已填入。`); }
    else return { notes, error: "参数块寿命必须是 1–2147483647 的整数帧" };
  }
  if (typeof block.maxCount === "number") form.maxCount = String(block.maxCount);
  if (typeof block.selfOnly === "boolean") form.selfOnly = block.selfOnly;
  if (typeof block.effectPrefix === "string") form.effectPrefix = block.effectPrefix;
  if (block.command && block.command !== "CreateSummonsMultiball") notes.push(`参数块命令是 ${block.command}，不是 CreateSummonsMultiball。`);
  if (Array.isArray(block.callbackSubjectIds)) notes.push("回调主体 ID 与 node 不会直接使用：技能模板按自己的规则生成召唤节点。");
  notes.push("球 ID 可来自当前视图或同一角色草稿的召唤工坊；生成时会联合编译。");
  return { form, notes };
}

export function SkillTemplate({ characterId }: { characterId: string }) {
  const [character, setCharacter] = useState<CharacterDetail | null>(null);
  const [existing, setExisting] = useState<DraftChange | null>(null);
  const [sourceKey, setSourceKey] = useState("");
  const [detail, setDetail] = useState<SkillTemplateDetail | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [newKey, setNewKey] = useState("");
  const [scale, setScale] = useState("1");
  const [overrides, setOverrides] = useState<Record<string, Record<string, string>>>({});
  const [element, setElement] = useState("");
  const [attribution, setAttribution] = useState("");
  const [recolorMode, setRecolorMode] = useState<RecolorMode>("none");
  const [hue, setHue] = useState("0");
  const [pairs, setPairs] = useState<Pair[]>([{ from: "#ffffff", to: "#ffffff" }]);
  const [summon, setSummon] = useState<SummonForm>(EMPTY_SUMMON);
  const [preview, setPreview] = useState<{ key: string; result: SkillTemplateResult } | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState<SkillTemplateResult | null>(null);

  useEffect(() => { api.character(characterId).then(setCharacter, () => setCharacter(null)); }, [characterId]);
  const loadExisting = () => drafts.get(characterId).then(
    (d) => setExisting(d.changeset?.changes.find((c) => c.kind === "skill_template") ?? null), () => setExisting(null));
  useEffect(() => { loadExisting(); }, [characterId]);

  useEffect(() => {
    if (!sourceKey) { setDetail(null); return; }
    let live = true;
    setDetail(null); setDetailError(null);
    skillTemplates.detail(sourceKey).then((d) => { if (live) setDetail(d); }, (e: Error) => { if (live) setDetailError(e.message); });
    return () => { live = false; };
  }, [sourceKey]);

  const pickSource = (key: string) => { setSourceKey(key); setOverrides({}); setSaved(null); };

  /** Pre-fill from the draft's skill_template change (resubmitting replaces it). */
  const loadFromExisting = () => {
    const request = (existing?.params as any)?.request as SkillTemplateRequest | undefined;
    if (!request) return;
    if (request.source?.key) pickSource(request.source.key);
    setNewKey(request.newKey ?? "");
    setScale(request.scale === undefined ? "1" : String(request.scale));
    setOverrides(Object.fromEntries(Object.entries(request.nodeCoefficients ?? {}).map(([level, nodes]) =>
      [level, Object.fromEntries(Object.entries(nodes).map(([path, v]) => [path, typeof v === "number" ? String(v) : JSON.stringify(v)]))])));
    setElement(request.element === undefined ? "" : String(request.element));
    setAttribution(request.attribution === undefined ? "" : String(request.attribution));
    const recolor = request.recolor as any;
    if (recolor?.pairs) { setRecolorMode("pairs"); setPairs(recolor.pairs); }
    else if (recolor && typeof recolor.hueShift === "number") { setRecolorMode("hue"); setHue(String(recolor.hueShift)); }
    else setRecolorMode("none");
    const s = request.summon;
    setSummon(s ? { on: true, multiballId: s.multiballId, maxCount: String(s.maxCount ?? 1), selfOnly: s.selfOnly ?? true,
      durationFrames: s.durationFrames ? String(s.durationFrames) : "", effectPrefix: s.effectPrefix ?? "" } : EMPTY_SUMMON);
  };

  // ---- request + client-side problems
  const problems: string[] = [];
  const request: SkillTemplateRequest = { source: { key: sourceKey }, newKey };
  if (!sourceKey) problems.push("先选母本技能");
  else if (detail && !detail.cloneable) problems.push("母本有档位没通过 DSL 静态检查，不能克隆");
  if (!NEW_KEY.test(newKey)) problems.push("新技能键只用字母、数字、_、-（首字符不能是 -），最长 128");
  const scaleValue = Number(scale);
  if (scale.trim() === "" || !Number.isFinite(scaleValue) || scaleValue < 0) problems.push("全局倍率要是非负数");
  else if (scaleValue !== 1) request.scale = scaleValue;
  const nodeCoefficients: Record<string, Record<string, number | Coefficient[]>> = {};
  for (const tier of detail?.tiers ?? []) {
    for (const node of tier.damageNodes) {
      const raw = overrides[tier.level]?.[node.path];
      if (raw === undefined || raw.trim() === "") continue;
      let value: number | Coefficient[];
      if (simpleNode(node)) {
        value = Number(raw);
        if (!Number.isFinite(value) || value < 0) { problems.push(`档位 ${tier.level} ${node.path}：系数要是非负数`); continue; }
      } else {
        try { value = JSON.parse(raw); } catch { problems.push(`档位 ${tier.level} ${node.path}：系数数组不是有效 JSON`); continue; }
        if (!Array.isArray(value) || value.length !== node.coefficient.length) {
          problems.push(`档位 ${tier.level} ${node.path}：要写 ${node.coefficient.length} 项 SLvValue 数组（不能增删项）`); continue;
        }
        if (JSON.stringify(value) === JSON.stringify(node.coefficient)) continue;
      }
      (nodeCoefficients[tier.level] ??= {})[node.path] = value;
    }
  }
  const overrideCount = Object.values(nodeCoefficients).reduce((n, m) => n + Object.keys(m).length, 0);
  if (overrideCount) request.nodeCoefficients = nodeCoefficients;
  if (element !== "") request.element = Number(element);
  if (attribution !== "") request.attribution = Number(attribution) as 1 | 3;
  if (recolorMode === "hue") {
    const h = Number(hue);
    if (hue.trim() === "" || !Number.isFinite(h) || h < -360 || h > 360) problems.push("色相旋转范围 -360..360");
    else request.recolor = { hueShift: h };
  } else if (recolorMode === "pairs") {
    const froms = new Set<string>();
    for (const [i, p] of pairs.entries()) {
      if (!HEX.test(p.from) || !HEX.test(p.to)) problems.push(`颜色对 ${i + 1}：要写 #RRGGBB`);
      else if (froms.has(p.from.toLowerCase())) problems.push(`颜色对 ${i + 1}：原色 ${p.from} 重复`);
      froms.add(p.from.toLowerCase());
    }
    if (!pairs.length) problems.push("颜色对不能为空");
    request.recolor = { pairs: pairs.map((p) => ({ from: p.from, to: p.to })) };
  }
  if (summon.on) {
    const block: SummonBlock = { multiballId: summon.multiballId };
    if (!/^[1-9][0-9]{0,9}$/.test(summon.multiballId) || Number(summon.multiballId) > 2147483647) problems.push("召唤球 ID 要是正整数（≤ 2147483647）");
    const max = Number(summon.maxCount);
    if (!Number.isInteger(max) || max < 1 || max > 99) problems.push("召唤上限要是 1–99 的整数");
    else block.maxCount = max;
    block.selfOnly = summon.selfOnly;
    if (summon.selfOnly && max > 1) problems.push("「仅计自身」目前只支持上限 1；更大的上限请取消「仅计自身」用队伍计数");
    if (summon.durationFrames.trim()) {
      const d = Number(summon.durationFrames);
      if (!Number.isInteger(d) || d < 1 || d > MAX_DURATION) problems.push("召唤寿命要是 1–2147483647 的整数帧");
      else block.durationFrames = d;
    }
    if (summon.effectPrefix.trim()) {
      if (!/^battle\/effect\/[A-Za-z0-9_/-]+$/.test(summon.effectPrefix.trim())) problems.push("召唤特效前缀必须在 battle/effect/ 下");
      else block.effectPrefix = summon.effectPrefix.trim();
    }
    request.summon = block;
  }

  // ---- automatic dry run whenever the request changes and passes client checks
  const key = JSON.stringify(request);
  const fresh = preview?.key === key ? preview.result : null;
  useEffect(() => {
    if (problems.length || !detail || fresh) return;
    let live = true;
    setPreviewing(true);
    const timer = window.setTimeout(() => {
      skillTemplates.preview(characterId, request).then((r) => { if (live) setPreview({ key, result: r }); })
        .finally(() => { if (live) setPreviewing(false); });
    }, 400);
    return () => { live = false; window.clearTimeout(timer); };
  }, [key, problems.length, !!detail]);

  const save = async () => {
    if (problems.length || !fresh?.ok) return;
    setBusy(true);
    try {
      const r = await skillTemplates.save(characterId, request);
      setSaved(r);
      if (r.ok) loadExisting();
    } finally { setBusy(false); }
  };

  const hasNormal = detail?.tiers.some((t) => t.damageNodes.some((n) => n.constructor === "CreateNormalAttack")) ?? false;
  const existingKey = (existing?.params as any)?.request?.newKey as string | undefined;

  return (
    <section class="page skillpf-page skill-template-page">
      <div class="page-head">
        <div>
          <h1>技能模板{character ? <span class="muted"> · {character.name} <span class="mono small">{characterId}</span></span> : null}</h1>
          <p class="muted">以官方技能为母本克隆一个新 action_skill：改伤害系数、属性、伤害归属，复制并换色特效族，可在开头插入召唤。母本只读官方基线；写入只进本角色草稿，之后照常保存、生成。</p>
        </div>
      </div>
      {existing ? (
        <Notice kind="info">本角色草稿已有技能模板改动（新键 <span class="mono">{existingKey ?? "?"}</span>）。每个角色只保留一项，再次写入会替换它；可以沿用同一个新键反复调参。
          {" "}<button type="button" class="link" onClick={loadFromExisting}>载入现有参数</button></Notice>
      ) : null}
      <div class="skillpf-layout">
        <TemplatePicker selected={sourceKey} onPick={pickSource} />
        <div class="skillpf-main">
          {!sourceKey ? <Notice>从左侧搜索并选一个官方技能作母本。</Notice>
            : detailError ? <Notice kind="error">母本详情读取失败：{detailError}</Notice>
            : !detail ? <div class="loading">正在读取母本……</div>
            : (
              <>
                <TemplateDetailView detail={detail} overrides={overrides} setOverrides={setOverrides} />
                <section class="boss-block">
                  <h3>新技能参数</h3>
                  <div class="param-fields">
                    <NewKeyField cid={characterId} value={newKey} onChange={setNewKey} ownKey={existingKey} />
                    <label class={"param-field" + (scale.trim() !== "1" ? " changed" : "")}><span>全局伤害倍率 ×</span>
                      <input type="number" min="0" step="0.05" value={scale} onInput={(e) => setScale((e.target as HTMLInputElement).value)} />
                      <span class="small muted">只作用于没有逐节点覆盖的伤害系数；不改帧数、判定形状</span></label>
                    <label class={"param-field" + (element !== "" ? " changed" : "")}><span>属性改写</span>
                      <select value={element} disabled={!hasNormal} onChange={(e) => setElement((e.target as HTMLSelectElement).value)}>
                        <option value="">沿用母本</option>
                        {SKILL_ELEMENTS.map((name, i) => <option value={String(i)}>{name}</option>)}
                      </select>
                      <span class="small muted">{hasNormal ? "只改有独立元素参数的 CreateNormalAttack；不改角色表属性、能力条件和文案" : "母本没有带独立元素参数的伤害节点"}</span></label>
                    <label class={"param-field" + (attribution !== "" ? " changed" : "")}><span>伤害归属</span>
                      <select value={attribution} onChange={(e) => setAttribution((e.target as HTMLSelectElement).value)}>
                        <option value="">沿用母本</option>
                        <option value="1">技能伤害（1）</option>
                        <option value="3">强化弹射伤害（3）</option>
                      </select>
                      <span class="small muted">写伤害 params[9]；归属不是独立倍率</span></label>
                  </div>
                  <RecolorEditor mode={recolorMode} setMode={setRecolorMode} hue={hue} setHue={setHue} pairs={pairs} setPairs={setPairs} />
                  <SummonEditor value={summon} onChange={setSummon} />
                </section>
                <section class="boss-block">
                  <h3>预检与写入 <InfoTip text="POST …/skill-template?preview=true：同一套检查，不建草稿文件、不预留键。写入时后端重新读取来源并检查占用。" /></h3>
                  {problems.length ? <ul class="inline-problems">{problems.map((p) => <li>{p}</li>)}</ul>
                    : previewing && !fresh ? <p class="small muted">预检中……</p>
                    : fresh ? <ResultView result={fresh} title={fresh.ok ? "预检结果" : "预检被拒绝"} />
                    : <p class="small muted">等待预检……</p>}
                  {saved && !saved.ok ? <ResultView result={saved} title="写入被拒绝" /> : null}
                  {saved?.ok ? (
                    <Notice kind={saved.buildable ? "info" : "warn"}>已写入草稿：新技能 <strong class="mono">{saved.newKey}</strong>（{saved.status?.label ?? "未保存"}）。
                      {saved.buildable ? "到「本次修改」保存后可以生成。" : "检查里还有阻断项，生成会被拦下。"} 真机：未执行。</Notice>
                  ) : null}
                  <div class="save-row">
                    <button type="button" class="primary" disabled={busy || problems.length > 0 || !fresh?.ok || !drafts.hasToken()} onClick={save}
                      title={!drafts.hasToken() ? "没有编辑令牌，只读" : !fresh ? "等预检跑完" : !fresh.ok ? "预检被拒绝，不能写入" : ""}>
                      {busy ? "写入中……" : existing ? "写入草稿（替换现有技能模板）" : "写入草稿"}</button>
                    <span class="small muted">{problems.length ? problems[0] : !fresh ? "预检后可写入" : fresh.ok ? (fresh.buildable ? "预检没有阻断项" : "预检有阻断项，写入后仍不能生成") : "预检被拒绝"}</span>
                  </div>
                </section>
              </>
            )}
        </div>
      </div>
    </section>
  );
}

// ------------------------------------------------------------------------------ picker

function TemplatePicker({ selected, onPick }: { selected: string; onPick: (key: string) => void }) {
  const [query, setQuery] = useState("");
  const [list, setList] = useState<SkillTemplateList | null>(null);
  const [error, setError] = useState<string | null>(null);
  const seq = useRef(0);
  useEffect(() => {
    const mine = ++seq.current;
    const timer = window.setTimeout(() => {
      skillTemplates.list(query).then((r) => { if (mine === seq.current) { setList(r); setError(null); } },
        (e: Error) => { if (mine === seq.current) setError(e.message); });
    }, 300);
    return () => window.clearTimeout(timer);
  }, [query]);
  const shown = useMemo(() => (list?.templates ?? []).slice(0, 200), [list]);
  return (
    <nav class="skillpf-side" aria-label="官方技能母本">
      <input class="search small-search" type="search" value={query} placeholder="搜索技能键、技能名、角色名或 ID"
        onInput={(e) => setQuery((e.target as HTMLInputElement).value)} />
      {error ? <Notice kind="error">母本列表读取失败：{error}（官方基线不可用时不会改用其他来源）</Notice> : null}
      {!list && !error ? <p class="small muted">正在读取官方技能……</p> : null}
      {list ? <p class="small muted">官方母本 {list.count} 个{list.count > shown.length ? `，显示前 ${shown.length} 个` : ""}
        {list.unavailable.length ? <span> · 另有 {list.unavailable.length} 个无法克隆</span> : null}</p> : null}
      <ul>
        {shown.map((t) => (
          <li><button type="button" class={"source-option" + (t.key === selected ? " on" : "")} onClick={() => onPick(t.key)}>
            <span class="sp-line"><strong>{t.names[0] ?? t.key}</strong> <span class="mono small muted">{t.key}</span></span>
            <span class="sp-line small muted">
              {t.characters.slice(0, 3).map((c) => <span>{elementName(c.element) ? <ElementBadge element={elementName(c.element)!} /> : null} {c.name}</span>)}
              {t.characters.length > 3 ? <span>等 {t.characters.length} 人</span> : t.characters.length ? null : <span>无角色使用</span>}
            </span>
            <span class="sp-line small muted">伤害节点 {t.damageNodeCount} · 特效族 {t.effectFamilies.length} · 档位 {t.tiers.join("/")}</span>
          </button></li>
        ))}
      </ul>
      {list?.unavailable.length ? (
        <details class="tech"><summary>无法克隆的母本（{list.unavailable.length}）</summary>
          <ul class="small">{list.unavailable.map((u) => <li><span class="mono">{u.key}</span>：{u.reason}</li>)}</ul></details>
      ) : null}
    </nav>
  );
}

// ------------------------------------------------------------------------------ detail

function TemplateDetailView({ detail, overrides, setOverrides }: {
  detail: SkillTemplateDetail;
  overrides: Record<string, Record<string, string>>;
  setOverrides: (fn: (o: Record<string, Record<string, string>>) => Record<string, Record<string, string>>) => void;
}) {
  const set = (level: string, path: string, value: string) =>
    setOverrides((o) => ({ ...o, [level]: { ...(o[level] ?? {}), [path]: value } }));
  return (
    <section class="boss-block">
      <h3>母本 <span class="mono">{detail.key}</span>
        <span class="tag" title="来源：官方归档，不是当前改版视图">官方基线</span>
        {detail.cloneable ? null : <span class="tag pend">有档位不可克隆</span>}
        {detail.contextElement !== null ? <span class="small muted">特效按 {elementName(detail.contextElement)} 属性解析</span> : <span class="small muted">母本角色属性不唯一，特效按元素选择的部分未固定</span>}
      </h3>
      <p class="small muted">使用角色：{detail.characters.length ? detail.characters.map((c) => `${c.name}（${c.id}）`).join("、") : "无"}</p>
      {detail.tiers.map((tier) => (
        <div class="sp-tier">
          <h4>档位 {tier.level} · {tier.name} <span class="mono small muted">{tier.program}</span>
            {tier.cloneable ? null : <span class="error-text small"> 不可克隆</span>}</h4>
          {tier.checks.length ? (
            <ul class="small">{tier.checks.map((c) => <li class={c.level === "error" ? "error-text" : c.level === "warn" ? "warn-text" : "muted"}>{c.message} <span class="mono muted">{c.code}</span></li>)}</ul>
          ) : null}
          {tier.damageNodes.length ? (
            <div class="table-scroll">
              <table class="boss-table">
                <thead><tr><th>路径</th><th>构造 / 含义</th><th>原系数</th><th>元素</th><th>归属</th><th>新系数（留空 = 按全局倍率）</th></tr></thead>
                <tbody>{tier.damageNodes.map((node) => {
                  const raw = overrides[tier.level]?.[node.path] ?? "";
                  const simple = simpleNode(node);
                  return (
                    <tr>
                      <td class="mono small">{node.path}</td>
                      <td class="small">{node.constructor.replace(/^Create/, "")}<br /><span class="muted">{COEFFICIENT_KIND_LABEL[node.coefficientKind] ?? node.coefficientKind}</span></td>
                      <td class="sp-coef" title={JSON.stringify(node.coefficient)}>{coefText(node.coefficient)}</td>
                      <td class="small">{nodeElement(node)}</td>
                      <td class="small">{ATTRIBUTION_LABEL[node.attribution] ?? node.attribution}</td>
                      <td>{simple ? (
                        <input class={"sp-node-input" + (raw.trim() ? " changed" : "")} type="number" min="0" step="any" value={raw}
                          placeholder={String(node.coefficient[0].max)} onInput={(e) => set(tier.level, node.path, (e.target as HTMLInputElement).value)} />
                      ) : (
                        <span>
                          <textarea class={"sp-json" + (raw.trim() && raw.trim() !== JSON.stringify(node.coefficient) ? " changed" : "")} value={raw}
                            placeholder={JSON.stringify(node.coefficient)} onInput={(e) => set(tier.level, node.path, (e.target as HTMLTextAreaElement).value)} />
                          <span class="small muted">多项 / alv / vlv 系数：写同长度的 SLvValue 数组，只改原本存在的上下界。
                            {raw ? null : <button type="button" class="link" onClick={() => set(tier.level, node.path, JSON.stringify(node.coefficient))}>填入原值</button>}</span>
                        </span>
                      )}</td>
                    </tr>
                  );
                })}</tbody>
              </table>
            </div>
          ) : <p class="small muted">这一档没有可编辑伤害节点。</p>}
        </div>
      ))}
      <h4>引用的特效（{detail.effects.length}）<InfoTip text="特效族总会完整复制到目标角色 code 目录下（不选换色也复制）。只有当前视图素材与官方母本一致时才给预览；没有预览不代表素材缺失。" /></h4>
      {detail.effects.length ? (
        <ul class="sp-effects">{detail.effects.map((e) => (
          <li>{e.previewUrl ? <img src={e.previewUrl} alt={e.path} loading="lazy" />
            : <span class="sp-noprev" title={(e.previewIssues ?? []).join("；")}>不可预览{e.previewIssues?.length ? "（" + e.previewIssues[0] + "）" : "（当前视图素材与官方不一致或渲染不可用）"}</span>}
            <span class="mono">{e.path}</span></li>
        ))}</ul>
      ) : <p class="small muted">母本没有引用特效族。</p>}
    </section>
  );
}

// ------------------------------------------------------------------------------ fields

function NewKeyField({ cid, value, onChange, ownKey }: { cid: string; value: string; onChange: (v: string) => void; ownKey?: string }) {
  const [state, setState] = useState<{ key: string; exact: string | null; error?: string } | null>(null);
  useEffect(() => {
    if (!NEW_KEY.test(value)) { setState(null); return; }
    let live = true;
    const timer = window.setTimeout(() => {
      ability.keys("action_skill", value, cid).then((r) => { if (live) setState({ key: value, exact: r.exact ?? null }); },
        (e: Error) => { if (live) setState({ key: value, exact: null, error: e.message }); });
    }, 300);
    return () => { live = false; window.clearTimeout(timer); };
  }, [value, cid]);
  const fresh = state?.key === value ? state : null;
  return (
    <label class="param-field"><span>新 action_skill 键</span>
      <input class="mono" value={value} placeholder="例如 my_skill_v1" onInput={(e) => onChange((e.target as HTMLInputElement).value.trim())} />
      <span class="small">
        {!value ? <span class="muted">必填；输入后查当前视图已有键</span>
          : !NEW_KEY.test(value) ? <span class="error-text">格式不对：字母、数字、_、-</span>
          : !fresh ? <span class="muted">查询占用……</span>
          : fresh.error ? <span class="error-text">查询失败：{fresh.error}</span>
          : fresh.exact && value === ownKey ? <span class="muted">本角色技能模板正在用这个键（可沿用）</span>
          : fresh.exact ? <span class="error-text">当前视图已有键 {fresh.exact}，后端会拒绝</span>
          : <span class="state-ok">当前视图没有这个键</span>}
        {fresh && !fresh.error && !fresh.exact ? <span class="muted">；其他草稿的预留在预检时检查</span> : null}
      </span>
    </label>
  );
}

function RecolorEditor({ mode, setMode, hue, setHue, pairs, setPairs }: {
  mode: RecolorMode; setMode: (m: RecolorMode) => void; hue: string; setHue: (v: string) => void;
  pairs: Pair[]; setPairs: (p: Pair[]) => void;
}) {
  const update = (i: number, patch: Partial<Pair>) => setPairs(pairs.map((p, j) => (j === i ? { ...p, ...patch } : p)));
  return (
    <fieldset class="param-field wide">
      <legend>特效换色 <InfoTip text="引用到的特效族总会复制为本角色的私有族；不换色就保留原颜色。换色后的图在预检摘要里只给变动像素数，编辑台目前没有换色后的预览图。" /></legend>
      <span>
        <label class="check"><input type="radio" checked={mode === "none"} onChange={() => setMode("none")} />保留原色（仍复制为私有族）</label>{" "}
        <label class="check"><input type="radio" checked={mode === "hue"} onChange={() => setMode("hue")} />色相旋转</label>{" "}
        <label class="check"><input type="radio" checked={mode === "pairs"} onChange={() => setMode("pairs")} />指定颜色对</label>
      </span>
      {mode === "hue" ? (
        <span class="sp-pair">
          <input type="range" min="-360" max="360" step="1" value={hue} onInput={(e) => setHue((e.target as HTMLInputElement).value)} />
          <input class="sp-node-input" type="number" min="-360" max="360" value={hue} onInput={(e) => setHue((e.target as HTMLInputElement).value)} /> 度
        </span>
      ) : null}
      {mode === "pairs" ? (
        <div class="sp-pairs">
          {pairs.map((p, i) => (
            <div class="sp-pair">
              <input type="color" value={HEX.test(p.from) ? p.from : "#000000"} onInput={(e) => update(i, { from: (e.target as HTMLInputElement).value })} />
              <input type="text" class="mono sp-node-input" value={p.from} onInput={(e) => update(i, { from: (e.target as HTMLInputElement).value.trim() })} />
              →
              <input type="color" value={HEX.test(p.to) ? p.to : "#000000"} onInput={(e) => update(i, { to: (e.target as HTMLInputElement).value })} />
              <input type="text" class="mono sp-node-input" value={p.to} onInput={(e) => update(i, { to: (e.target as HTMLInputElement).value.trim() })} />
              <button type="button" class="ghost small-btn" disabled={pairs.length <= 1} onClick={() => setPairs(pairs.filter((_, j) => j !== i))}>删除</button>
            </div>
          ))}
          <span><button type="button" class="small-btn" onClick={() => setPairs([...pairs, { from: "#000000", to: "#000000" }])}>加一对</button></span>
        </div>
      ) : null}
    </fieldset>
  );
}

function SummonEditor({ value, onChange }: { value: SummonForm; onChange: (v: SummonForm) => void }) {
  const [paste, setPaste] = useState("");
  const [pasteNotes, setPasteNotes] = useState<{ notes: string[]; error?: string } | null>(null);
  const set = (patch: Partial<SummonForm>) => onChange({ ...value, ...patch });
  const apply = () => {
    const r = parseSummonPaste(paste);
    setPasteNotes(r);
    if (r.form) onChange({ ...value, ...r.form });
  };
  return (
    <fieldset class="param-field wide">
      <legend><label class="check"><input type="checkbox" checked={value.on} onChange={(e) => set({ on: (e.target as HTMLInputElement).checked })} />技能开头召唤协力球</label></legend>
      {value.on ? (
        <>
          <div class="param-fields">
            <label class="param-field"><span>协力球 ID</span>
              <input class="mono" value={value.multiballId} placeholder="已在当前视图 multiball 表里的 ID" onInput={(e) => set({ multiballId: (e.target as HTMLInputElement).value.trim() })} /></label>
            <label class="param-field"><span>召唤上限</span>
              <input type="number" min="1" max="99" value={value.maxCount} onInput={(e) => set({ maxCount: (e.target as HTMLInputElement).value })} />
              <span class="small muted">没到上限时本次加一个；到上限不替换、不刷新寿命</span></label>
            <label class="param-field"><span>计数方式</span>
              <label class="check"><input type="checkbox" checked={value.selfOnly} onChange={(e) => set({ selfOnly: (e.target as HTMLInputElement).checked })} />仅计自身召唤数</label>
              <span class="small muted">仅计自身只支持上限 1；更大上限用队伍计数</span></label>
            <label class="param-field"><span>寿命（帧）</span>
              <input type="number" min="1" max={MAX_DURATION} value={value.durationFrames} placeholder="默认 2147483647（常驻）" onInput={(e) => set({ durationFrames: (e.target as HTMLInputElement).value })} /></label>
            <label class="param-field"><span>召唤特效前缀</span>
              <input class="mono" value={value.effectPrefix} placeholder="留空用官方召唤特效族" onInput={(e) => set({ effectPrefix: (e.target as HTMLInputElement).value })} /></label>
          </div>
          <details class="tech">
            <summary>粘贴召唤工坊的参数块</summary>
            <p class="small muted">召唤工坊预检 / 草稿列表里的 <span class="mono">skillTemplate</span> 对象（或含它的整个响应）。只取球 ID 和寿命；不会直接插入它的 node。</p>
            <textarea class="sp-json" value={paste} onInput={(e) => setPaste((e.target as HTMLTextAreaElement).value)} placeholder='{"command":"CreateSummonsMultiball","multiballId":"1990001",…}' />
            <div class="save-row"><button type="button" class="small-btn" disabled={!paste.trim()} onClick={apply}>解析并填入</button></div>
            {pasteNotes?.error ? <p class="small error-text">{pasteNotes.error}</p> : null}
            {pasteNotes?.notes.length ? <ul class="small">{pasteNotes.notes.map((n) => <li>{n}</li>)}</ul> : null}
          </details>
        </>
      ) : <span class="small muted">不召唤。召唤节点插在技能开头，召唤所需特效同样复制到本角色目录。</span>}
    </fieldset>
  );
}

// ------------------------------------------------------------------------------ result

function ResultView({ result, title }: { result: SkillTemplateResult; title: string }) {
  const summary = result.summary;
  return (
    <div class="sp-result">
      {!result.ok ? <Notice kind="error"><strong>{title}</strong>{result.error ? `：${result.error}` : ""}</Notice> : (
        <p class={"small " + (result.buildable ? "state-ok" : "warn-text")}>
          {result.buildable ? "预检没有阻断项（静态检查；交付时还会重新检查）。" : "预检有阻断项：可以看下方检查，写入后生成会被拦下。"}
          <span class="muted"> 真机：{result.runtime}</span></p>
      )}
      <RuleList checks={result.checks as RuleResult[]} title="检查" />
      {summary ? (
        <>
          <dl class="kv">
            <dt>母本 → 新键</dt><dd class="mono">{summary.sourceKey} → {summary.newKey}</dd>
            <dt>伤害节点</dt><dd>{summary.damageNodeCount}</dd>
            {result.reservations ? <><dt>拟登记键</dt><dd class="mono">{Object.entries(result.reservations).map(([t, ks]) => `${t}: ${ks.join("、")}`).join("；")}{result.preview ? <span class="small muted">（预检不登记）</span> : null}</dd></> : null}
          </dl>
          <div class="sp-levels">
            {summary.levels.map((level) => (
              <div class="sp-level">
                <h4>档位 {level.level} <span class="mono small muted">{level.logical}</span></h4>
                <p class="small">倍率 ×{level.summary.scale} · 逐节点覆盖 {level.summary.nodeOverrideCount} ·
                  属性 {level.summary.element === null ? "沿用" : elementName(level.summary.element)}{level.summary.elementCode !== null ? `（码 ${level.summary.elementCode}）` : ""} ·
                  归属 {level.summary.attribution === null ? "沿用" : ATTRIBUTION_LABEL[level.summary.attribution] ?? level.summary.attribution}
                  {level.summary.summon ? ` · 召唤 ${level.summary.summon.multiballId}（上限 ${level.summary.summon.maxCount ?? 1}${level.summary.summon.countMode ? "，" + level.summary.summon.countMode : ""}）` : ""}</p>
                <p class={"small " + (level.summary.timingAndGeometryPreserved ? "muted" : "warn-text")}>{level.summary.timingAndGeometryPreserved ? "时序与判定形状保留" : "时序或判定形状有变化"}</p>
                <table class="boss-table">
                  <thead><tr><th>路径（新树）</th><th>系数</th><th>元素</th><th>归属</th></tr></thead>
                  <tbody>{level.damageNodes.map((n) => (
                    <tr><td class="mono small">{n.path}</td><td class="sp-coef">{coefText(n.coefficient)}</td><td class="small">{nodeElement(n)}</td>
                      <td class="small">{ATTRIBUTION_LABEL[n.attribution] ?? n.attribution}</td></tr>
                  ))}</tbody>
                </table>
              </div>
            ))}
          </div>
          {summary.effectFamilies.length ? (
            <>
              <h4>特效族复制（{summary.effectFamilies.length}）</h4>
              <div class="table-scroll">
                <table class="boss-table">
                  <thead><tr><th>母本族</th><th>目标族</th><th>变动像素</th><th>资源</th><th>依赖完整</th></tr></thead>
                  <tbody>{summary.effectFamilies.map((f) => (
                    <tr><td class="mono small">{f.source}</td><td class="mono small">{f.target}</td><td class="small">{f.changedPixels ?? "—"}</td>
                      <td class="small">{f.resources.length}</td>
                      <td class={"small " + (f.completeDependencies ? "state-ok" : "warn-text")}>{f.completeDependencies ? "是" : "否"}</td></tr>
                  ))}</tbody>
                </table>
              </div>
            </>
          ) : null}
          {summary.files?.length ? (
            <details class="tech"><summary>候选交付文件（{summary.files.length}）{result.preview ? " · 仅内存生成，尚未落盘" : ""}</summary>
              <ul class="small mono">{summary.files.map((f) => <li>{f.root}/{f.logical} · {f.size} B · {f.sha256.slice(0, 12)}</li>)}</ul></details>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
