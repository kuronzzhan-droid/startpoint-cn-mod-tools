// 专属武器全套（weapons.md §10）：不出魂珠 / 强化上限与分段材料 / 强化类目 / 兑换商品 / 突破材料限定。
// 每项默认关闭，关闭的项不进请求体；类目与材料选项全部来自 GET /set-options（当前视图），不写死 ID。
// 先 ?preview=true 预检（展示最终写入行、依赖清单、检查），预检通过且请求未变才能写入草稿。
import { useEffect, useMemo, useState } from "preact/hooks";
import { cellOf } from "../boss/bossOps";
import { PreviewState } from "../boss/BossParams";
import { Notice } from "../common";
import { InfoTip } from "../Delivery";
import { RuleList } from "../rules";
import {
  WeaponDetail, weaponSet, WeaponSetCategory, WeaponSetCategoryOption, WeaponSetCheck, WeaponSetMaterial, WeaponSetOptions,
  WeaponSetRequest, WeaponSetResult,
} from "../../weaponApi";
import { WeaponIcon } from "./weaponEditors";

const CODE = /^[a-z][a-z0-9_]{0,79}$/;
const ID = /^[1-9][0-9]{0,9}$/;
const TEXT_BAD = /[,\n\r"]|::/;
/** Official enhancement categories 1–4 price differently; per_level stages cannot use them (backend rejects). */
const OFFICIAL_ENH = new Set(["1", "2", "3", "4"]);
const isPosInt = (v: string) => /^[1-9][0-9]*$/.test(v.trim()) && Number(v) <= 2147483647;

export const CAPABILITY_LABEL: Record<string, string> = {
  "equipment-awakening-material-v1": "客户端补丁 client-patch/equipment-awakening-material（突破材料替代）",
};
export const FEATURE_LABEL: Record<string, string> = {
  "equipment_awakening_material.materialByEquipment": "服务端突破材料白名单 materialByEquipment",
  "equipment_enhancement_shop.per_level": "服务端强化按级计费 per_level",
  "equipment_dissolve.generate_ability_soul": "服务端熔炼不产魂珠 generate_ability_soul=false",
};

/** Levels only (no material / ID): the cursed-weapon style Lv120 ladder, 12 materials in total. */
const PRESET_120: [number, number][] = [[68, 0], [69, 1], [70, 1], [97, 0], [98, 2], [99, 2], [118, 0], [119, 3], [120, 3]];

interface StageDraft { maxLevel: string; amount: string; awaken: string }
interface CategoryDraft { mode: "existing" | "new"; id: string; source: string; code: string; name: string }
const EMPTY_CAT: CategoryDraft = { mode: "existing", id: "", source: "", code: "", name: "" };

/** One line for the 「本次修改」 list. */
export function describeSet(w: WeaponSetRequest & { id?: string }): string {
  const cat = (c?: WeaponSetCategory) => !c ? "" : c.sourceCategory ? `新建「${c.name ?? c.code}」${c.id ? `（${c.id}）` : ""}` : `复用 ${c.id ?? c.code ?? c.name}`;
  const parts: string[] = [];
  if (w.noSoul) parts.push("不出魂珠");
  if (w.enhancement) parts.push(`强化上限 Lv${w.enhancement.maxLevel}，${w.enhancement.stages.length} 段${w.enhancement.products?.length ? `（商品 ${w.enhancement.products[0]}…）` : ""}`);
  if (w.enhancementCategory) parts.push("强化类目 " + cat(w.enhancementCategory));
  if (w.exchange) parts.push(`兑换商品${w.exchange.productId ? " " + w.exchange.productId : ""}：${w.exchange.itemId}×${w.exchange.amount}，限购 ${w.exchange.stock}，类目 ${cat(w.exchange.category)}`);
  if (w.awakeningMaterial) parts.push(`突破材料限定 ${w.awakeningMaterial}`);
  return "专属武器全套：" + (parts.join("；") || "（空）");
}

function categoryBody(c: CategoryDraft, label: string, problems: string[], forbidOfficial: boolean): WeaponSetCategory | null {
  if (c.mode === "existing") {
    if (!c.id) { problems.push(`${label}：选一个已有类目，或改为新建`); return null; }
    if (forbidOfficial && OFFICIAL_ENH.has(c.id)) problems.push(`${label}：官方类目 1–4 计费语义不同，按级收费的强化阶段不能用`);
    return { id: c.id };
  }
  if (!c.source) problems.push(`${label}：新建要选一个母本类目（复制布局和横幅）`);
  if (!CODE.test(c.code)) problems.push(`${label}：代码以小写字母开头，只用 a–z、0–9、_，最多 80 位`);
  if (!c.name.trim()) problems.push(`${label}：填名称`);
  else if (c.name.length > 80 || TEXT_BAD.test(c.name)) problems.push(`${label}：名称最多 80 字，不能含半角逗号、换行、双引号或「::」`);
  return { sourceCategory: c.source, code: c.code, name: c.name.trim() };
}

function serverText(m: WeaponSetMaterial | undefined): { text: string; cls: string } {
  if (!m) return { text: "", cls: "" };
  if (m.serverAvailable === true) return { text: "服务端 item_ids 有", cls: "state-ok" };
  if (m.serverAvailable === false) return { text: "服务端 item_ids 缺（保存会拒绝）", cls: "error-text" };
  return { text: "服务端未配置，未核对", cls: "state-none" };
}

function MaterialPicker({ label, value, onChange, materials }: {
  label: string; value: string; onChange: (id: string) => void; materials: WeaponSetMaterial[];
}) {
  const [q, setQ] = useState("");
  const chosen = materials.find((m) => m.id === value);
  const hits = useMemo(() => {
    const t = q.trim().toLowerCase();
    if (!t) return [];
    return materials.filter((m) => m.id.includes(t) || m.name.toLowerCase().includes(t)).slice(0, 40);
  }, [q, materials]);
  const s = serverText(chosen);
  return (
    <div class="param-field wide set-material">
      <span>{label}</span>
      <div class="set-material-chosen">
        {value ? (
          <>
            {chosen ? <WeaponIcon path={chosen.icon} size={24} /> : null}
            <span>{chosen?.name || "（当前 item 表没有这一行）"}</span> <span class="mono small muted">{value}</span>
            {s.text ? <span class={"small " + s.cls}>{s.text}</span> : null}
            <button type="button" class="link" onClick={() => onChange("")}>清除</button>
          </>
        ) : <span class="small muted">未选</span>}
      </div>
      <input type="search" value={q} placeholder="按材料名称或 item ID 搜索（当前视图 item 表）"
        onInput={(e) => setQ((e.target as HTMLInputElement).value)} />
      {hits.length ? (
        <div class="set-material-hits">
          {hits.map((m) => (
            <button type="button" class={"icon-pick" + (m.id === value ? " on" : "")} title={`${m.name} · ${m.id}\n${m.icon}`}
              onClick={() => { onChange(m.id); setQ(""); }}>
              <WeaponIcon path={m.icon} size={28} /><span class="small">{m.name || "（无名）"}</span>
              <span class="mono small muted">{m.id}</span>
            </button>
          ))}
        </div>
      ) : q.trim() ? <span class="small muted">没有匹配的材料</span> : null}
    </div>
  );
}

function CategoryPicker({ label, value, onChange, options, kind, forbidOfficial }: {
  label: string; value: CategoryDraft; onChange: (c: CategoryDraft) => void; options: WeaponSetCategoryOption[];
  kind: "enhancement" | "exchange"; forbidOfficial: boolean;
}) {
  const show = (o: WeaponSetCategoryOption) => kind === "enhancement" ? `${o.name || o.code} · ${o.id}（${o.code}）` : `${o.code} · ${o.id}`;
  return (
    <fieldset class="param-field wide soul-elements">
      <legend>{label}</legend>
      <div class="segmented" role="radiogroup" aria-label={label}>
        {(["existing", "new"] as const).map((m) => (
          <button type="button" role="radio" aria-checked={value.mode === m} class={value.mode === m ? "on" : ""}
            onClick={() => onChange({ ...value, mode: m })}>{m === "existing" ? "加入已有类目" : "新建类目"}</button>
        ))}
      </div>
      {value.mode === "existing" ? (
        <label class="param-field"><span>类目</span>
          <select value={value.id} onChange={(e) => onChange({ ...value, id: (e.target as HTMLSelectElement).value })}>
            <option value="">— 选择 —</option>
            {options.map((o) => (
              <option value={o.id} disabled={forbidOfficial && OFFICIAL_ENH.has(o.id)}>
                {show(o)}{forbidOfficial && OFFICIAL_ENH.has(o.id) ? "（官方计费类目，不可用）" : ""}</option>
            ))}
          </select></label>
      ) : (
        <div class="param-fields compact">
          <label class="param-field"><span>母本类目</span>
            <select value={value.source} onChange={(e) => onChange({ ...value, source: (e.target as HTMLSelectElement).value })}>
              <option value="">— 选择 —</option>
              {options.map((o) => <option value={o.id}>{show(o)}</option>)}
            </select></label>
          <label class="param-field"><span>代码（c0）</span>
            <input class="mono" value={value.code} placeholder="exclusive_weapon"
              onInput={(e) => onChange({ ...value, code: (e.target as HTMLInputElement).value.trim() })} /></label>
          <label class="param-field"><span>名称{kind === "exchange" ? "（仅用于查重）" : "（c3）"}</span>
            <input value={value.name} onInput={(e) => onChange({ ...value, name: (e.target as HTMLInputElement).value })} /></label>
        </div>
      )}
      <span class="small muted">
        {kind === "enhancement"
          ? "同代码或同名称的类目已存在时复用并核对身份；新类目复制母本布局和实际横幅，排序追加到最后，不生成新美术。"
          : "兑换类目没有独立文字名称列，列表显示原生代码；展示横幅复用母本。新类目清除母本任务前置。"}
        {" "}ID 由后端分配；被其他未合并草稿预留的同名新类目会被拒绝。</span>
    </fieldset>
  );
}

function valueText(v: unknown): string {
  return typeof v === "string" ? v : JSON.stringify(v, null, 1);
}

function RowsView({ rows }: { rows: NonNullable<WeaponSetResult["rows"]> }) {
  const groups = new Map<string, typeof rows.client>();
  for (const r of rows.client) groups.set(r.table, [...(groups.get(r.table) ?? []), r]);
  return (
    <div class="set-rows">
      <h5>将写入的客户端行（整个草稿序列的最终值，{rows.client.length} 行）</h5>
      {[...groups].map(([table, list]) => (
        <details class="tech"><summary><span class="mono">{table}</span>（{list.length}）</summary>
          <div class="table-scroll">
            <table class="boss-table">
              <thead><tr><th>键</th><th>值</th></tr></thead>
              <tbody>{list.map((r) => (
                <tr><td class="mono small">{r.path.join("/")}</td><td><pre class="mono small set-value">{valueText(r.value)}</pre></td></tr>
              ))}</tbody>
            </table>
          </div>
        </details>
      ))}
      <h5>服务端变更（{rows.server.length} 个目标）</h5>
      {rows.server.map((r) => (
        <details class="tech"><summary><span class="mono">{r.target}</span></summary>
          <pre class="mono small set-value">{valueText(r.updates)}</pre>
        </details>
      ))}
    </div>
  );
}

export function WeaponSetEditor({ detail, revision, onPreview, onWritten, onClose }: {
  detail: WeaponDetail; revision: string; onPreview: (s: PreviewState) => void; onWritten: () => void; onClose: () => void;
}) {
  const [options, setOptions] = useState<WeaponSetOptions | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  useEffect(() => { weaponSet.options().then(setOptions, (e: Error) => setLoadError(e.message)); }, []);

  const [noSoul, setNoSoul] = useState(false);
  const [awakenOn, setAwakenOn] = useState(false);
  const [awakenMat, setAwakenMat] = useState("");
  const [enhOn, setEnhOn] = useState(false);
  const [enhMat, setEnhMat] = useState("");
  const [enhSource, setEnhSource] = useState("");
  const [maxLevel, setMaxLevel] = useState("120");
  const [stages, setStages] = useState<StageDraft[]>([{ maxLevel: "120", amount: "0", awaken: "" }]);
  const [catOn, setCatOn] = useState(false);
  const [cat, setCat] = useState<CategoryDraft>(EMPTY_CAT);
  const [exOn, setExOn] = useState(false);
  const [exCat, setExCat] = useState<CategoryDraft>(EMPTY_CAT);
  const [ex, setEx] = useState({ sourceProduct: "", itemId: "", amount: "1", count: "1", stock: "1", description: "" });

  const maxAwaken = Number(cellOf(detail.equipment?.row, 8) || detail.awakening?.maxLevel || 0);
  const existingStages = detail.enhancement_chain.length;
  const existingCap = Math.max(0, ...detail.enhancement_chain.map((s) => Number(s.maxLevel) || 0));
  const materials = options?.materials ?? [];
  const nameOf = (id: string) => materials.find((m) => m.id === id)?.name || id;
  const sourceProducts = detail.references.shops.filter((r) => r.scope === "client" && r.kind === "boss_coin").map((r) => r.productId);

  // ------------------------------------------------------------ request + local problems
  const problems: string[] = [];
  const body: WeaponSetRequest = {};
  if (noSoul) body.noSoul = true;
  if (awakenOn) {
    if (!awakenMat) problems.push("突破材料限定：选一种材料");
    else body.awakeningMaterial = awakenMat;
  }
  const cap = Number(maxLevel);
  let prev = 0, total = 0;
  const segments = stages.map((s) => {
    const lv = Number(s.maxLevel), amt = s.amount.trim() === "" ? 0 : Number(s.amount);
    const levels = Number.isInteger(lv) ? lv - prev : NaN;
    const ok = Number.isInteger(lv) && lv > prev && Number.isInteger(amt) && amt >= 0;
    const row = { from: prev + 1, to: lv, levels, amt, cost: ok ? amt * levels : NaN };
    if (ok) { total += row.cost; prev = lv; }
    return row;
  });
  if (enhOn) {
    if (!Number.isInteger(cap) || cap < 1 || cap > 200) problems.push("强化上限要是 1–200 的整数");
    if (existingCap && cap < existingCap) problems.push(`强化上限不能低于现有 Lv${existingCap}（不能删旧阶段 / 曲线键）`);
    if (!stages.length || stages.length > 99) problems.push("强化分段要 1–99 段");
    let last = 0;
    stages.forEach((s, i) => {
      const lv = Number(s.maxLevel);
      if (!Number.isInteger(lv) || lv <= last) problems.push(`第 ${i + 1} 段：等级要严格递增的整数`);
      else last = lv;
      if (s.amount.trim() !== "" && !(/^[0-9]+$/.test(s.amount.trim()))) problems.push(`第 ${i + 1} 段：每级价格要是非负整数（0 = 免费）`);
      if (s.awaken.trim() !== "" && (!/^[0-5]$/.test(s.awaken.trim()) || Number(s.awaken) > maxAwaken))
        problems.push(`第 ${i + 1} 段：需要突破等级要是 0–${Math.min(5, maxAwaken)}（不超过本体最大突破）`);
    });
    if (stages.length && Number(stages[stages.length - 1].maxLevel) !== cap) problems.push("最后一段的等级必须等于强化上限");
    if (existingStages && stages.length < existingStages) problems.push(`至少要 ${existingStages} 段：现有强化商品键不能删除`);
    const paid = stages.some((s) => Number(s.amount) > 0);
    if (paid && !enhMat) problems.push("强化材料：有收费段时要选一种材料");
    if (enhSource && !ID.test(enhSource)) problems.push("强化母本要是武器 ID，或留空用当前武器");
    const donorCat = detail.enhancement_chain[0]?.categoryId;
    if (!catOn && !enhSource && donorCat && OFFICIAL_ENH.has(donorCat))
      problems.push(`现有强化阶段在官方类目 ${donorCat}，按级收费不能沿用：同时开启「强化商店类目」选自制类目`);
    body.enhancement = {
      ...(enhSource ? { sourceWeapon: enhSource } : {}), maxLevel: cap,
      stages: stages.map((s) => ({
        maxLevel: Number(s.maxLevel),
        costs: Number(s.amount) > 0 && enhMat ? [{ itemId: enhMat, amount: Number(s.amount) }] : [],
        ...(s.awaken.trim() !== "" ? { requireAwakeningLevel: Number(s.awaken) } : {}),
      })),
    };
  }
  if (catOn) {
    if (!enhOn && !existingStages) problems.push("强化类目：这把武器没有强化阶段，要同时开启「强化上限与分段材料」");
    const c = categoryBody(cat, "强化类目", problems, enhOn);
    if (c) body.enhancementCategory = c;
  }
  if (exOn) {
    const c = categoryBody(exCat, "兑换类目", problems, false);
    if (!ID.test(ex.sourceProduct)) problems.push("兑换商品：填已有 50 列兑换商品母本 ID");
    if (!ex.itemId) problems.push("兑换商品：选价格材料");
    for (const [k, label] of [["amount", "每次所需数量"], ["count", "每次得到数量"], ["stock", "个人限购次数"]] as const)
      if (!isPosInt(ex[k])) problems.push(`兑换商品：${label}要是正整数`);
    if (ex.description && (TEXT_BAD.test(ex.description) || ex.description.length > 1000)) problems.push("兑换商品：说明最多 1000 字，不能含半角逗号、换行、双引号或「::」");
    if (c) body.exchange = {
      category: c, sourceProduct: ex.sourceProduct, itemId: ex.itemId, amount: Number(ex.amount),
      count: Number(ex.count), stock: Number(ex.stock), ...(ex.description.trim() ? { description: ex.description.trim() } : {}),
    };
  }
  const anyOn = noSoul || awakenOn || enhOn || catOn || exOn;
  if (!anyOn) problems.push("至少开启一项");
  const key = JSON.stringify(body) + "@" + revision;

  // ------------------------------------------------------------ preview / write
  const [result, setResult] = useState<{ key: string; data: WeaponSetResult } | null>(null);
  const [written, setWritten] = useState<{ body: string; data: WeaponSetResult } | null>(null);
  const [busy, setBusy] = useState<"check" | "write" | null>(null);
  const fresh = result?.key === key ? result.data : null;
  useEffect(() => {
    if (busy === "check") onPreview({ state: "running", checks: null, ok: false });
    else if (fresh) onPreview({ state: "done", checks: fresh.checks, ok: fresh.ok });
    else if (problems.length && anyOn) onPreview({ state: "invalid", checks: null, ok: false, note: problems.join("；") });
    else onPreview({ state: "idle", checks: null, ok: false });
  }, [key, busy, fresh, problems.length]);

  const check = async () => {
    setBusy("check");
    try { setResult({ key, data: await weaponSet.preview(detail.id, body) }); }
    catch (e) { setResult({ key, data: { ok: false, runtime: "未执行", checks: [{ rule: "weapon.inputs", status: "问题", blocking: true, message: (e as Error).message }] } }); }
    finally { setBusy(null); }
  };
  const write = async () => {
    setBusy("write");
    try {
      const r = await weaponSet.apply(detail.id, body);
      if (r.ok) { setWritten({ body: JSON.stringify(body), data: r }); onWritten(); } else setResult({ key, data: r });
    } catch (e) { setResult({ key, data: { ok: false, runtime: "未执行", checks: [{ rule: "weapon.inputs", status: "问题", blocking: true, message: (e as Error).message }] } }); }
    finally { setBusy(null); }
  };

  const shown = fresh ?? null;
  const costCheck = shown?.checks.find((c) => c.rule === "weapon.enhancement-cost") as WeaponSetCheck | undefined;
  const awakenCheck = shown?.checks.find((c) => c.rule === "weapon.awakening-material") as WeaponSetCheck | undefined;
  const requires = shown?.requires;
  const writtenNow = written?.body === JSON.stringify(body);
  const savedRequest = written?.data.changeset?.changes?.[0]?.params?.requests?.filter((r: { operation: string }) => r.operation === "weapon_set").pop() as
    { weapon: WeaponSetRequest & { id: string } } | undefined;

  if (loadError) return <Notice kind="error">专属武器全套：选择项读取失败（GET /set-options）：{loadError}</Notice>;

  return (
    <section class="boss-block weapon-set" aria-label="专属武器全套">
      <header><h3>专属武器全套</h3>
        <InfoTip text="POST /api/studio/weapons/<id>/set：在本武器草稿里追加一条 weapon_set 请求，与克隆、改材料一起重放。各项默认关闭，关闭的项不写。撤销用「本次修改」里的撤销，不是取消勾选。" />
        <span class="small muted">选项来自当前视图 {options?.version ?? "……"}</span>
        <span class="spacer" /><button type="button" class="link close-x" onClick={onClose} aria-label="关闭">×</button></header>
      {!options ? <div class="loading">正在读取类目和材料……</div> : (
        <>
          {!options.serverInputAvailable ? <Notice kind="warn">没有读到服务端 item_ids：材料是否在服务端存在未核对（不是通过），保存时后端仍会校验。</Notice> : null}

          {/* 1. no soul */}
          <div class="set-option">
            <label class="check"><input type="checkbox" checked={noSoul} onChange={(e) => setNoSoul((e.target as HTMLInputElement).checked)} />
              <strong>不出魂珠</strong></label>
            {noSoul ? (
              <p class="small muted">客户端 equipment c9=false、服务端熔炼 generate_ability_soul=false。魂珠上的基础能力改由武器本体生效；
                内部 item（{detail.soulId}）、c10 与 ability_soul 仍保留（客户端突破 / 熔炼界面要读），不删行，也不收回玩家已有的旧魂珠。
                取消勾选不会撤销已写入的设置，撤销请到「本次修改」。</p>
            ) : null}
          </div>

          {/* 2. enhancement */}
          <div class="set-option">
            <label class="check"><input type="checkbox" checked={enhOn} onChange={(e) => setEnhOn((e.target as HTMLInputElement).checked)} />
              <strong>强化上限与分段材料</strong></label>
            <span class="small muted"> 现有：{existingStages ? `${existingStages} 段，到 Lv${existingCap}` : "没有强化阶段"}</span>
            {enhOn ? (
              <div class="param-fields">
                <label class="param-field"><span>强化上限</span>
                  <input type="number" min={1} max={200} step={1} value={maxLevel} onInput={(e) => setMaxLevel((e.target as HTMLInputElement).value)} /></label>
                <label class="param-field"><span>强化母本（可选）</span>
                  <input class="mono" value={enhSource} placeholder={`留空 = 当前武器 ${detail.id}`} onInput={(e) => setEnhSource((e.target as HTMLInputElement).value.trim())} />
                  <span class="small muted">母本要有强化本体、状态曲线和商店行</span></label>
                <MaterialPicker label="强化材料（所有收费段只用这一种）" value={enhMat} onChange={setEnhMat} materials={materials} />
                <div class="param-field wide">
                  <span>分段（按级收费 per_level：价格 × 本段级数）
                    <button type="button" class="link" onClick={() => { setMaxLevel("120"); setStages(PRESET_120.map(([lv, a]) => ({ maxLevel: String(lv), amount: String(a), awaken: "" }))); }}>
                      套用 Lv120 诅咒武器式分段</button></span>
                  <div class="table-scroll">
                    <table class="boss-table tier-edit">
                      <thead><tr><th>段</th><th>到等级</th><th>本段每级价格 <InfoTip text="0 = 免费区间。每行价格乘以该行覆盖的等级数；不要把长区间整段写成收费。" /></th>
                        <th>覆盖等级</th><th>本段合计</th><th>需要突破 <InfoTip text={`留空 = 本体最大突破等级（${maxAwaken}）`} /></th><th /></tr></thead>
                      <tbody>
                        {stages.map((s, i) => {
                          const g = segments[i];
                          const set = (patch: Partial<StageDraft>) => setStages(stages.map((x, k) => k === i ? { ...x, ...patch } : x));
                          return (
                            <tr>
                              <td class="mono small">{i + 1}</td>
                              <td><input type="number" class="short" min={1} max={200} step={1} value={s.maxLevel} onInput={(e) => set({ maxLevel: (e.target as HTMLInputElement).value })} /></td>
                              <td><input type="number" class="short" min={0} step={1} value={s.amount} onInput={(e) => set({ amount: (e.target as HTMLInputElement).value })} />
                                {Number(s.amount) > 0 ? <span class="small"> {enhMat ? nameOf(enhMat) : "（未选材料）"}/级</span> : <span class="small muted"> 免费</span>}</td>
                              <td class="small">{Number.isFinite(g.levels) && g.levels > 0 ? `Lv${g.from}–${g.to}（${g.levels} 级）` : "—"}</td>
                              <td class="small">{Number.isFinite(g.cost) ? g.cost : "—"}</td>
                              <td><input type="number" class="short" min={0} max={5} step={1} value={s.awaken} placeholder={String(maxAwaken)} onInput={(e) => set({ awaken: (e.target as HTMLInputElement).value })} /></td>
                              <td><button type="button" class="link" disabled={stages.length <= 1} onClick={() => setStages(stages.filter((_, k) => k !== i))}>删</button></td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                  <div class="save-row">
                    <button type="button" disabled={stages.length >= 99} onClick={() => setStages([...stages, { maxLevel: maxLevel, amount: "0", awaken: "" }])}>加一段</button>
                    <span class="small">本地估算合计：{enhMat ? nameOf(enhMat) : "材料"} ×{total}（以预检返回的 materialTotals 为准）</span>
                  </div>
                  <span class="small muted">商品 ID 由后端按「武器 ID×100＋段序号」分配。新增曲线终点复用母本最终 HP/攻击，不生成新的高等级数值；以母本上限为插值终点的强化词条同步到新上限。
                    官方类目 1–4 不能用于按级收费。</span>
                </div>
              </div>
            ) : null}
          </div>

          {/* 3. enhancement category */}
          <div class="set-option">
            <label class="check"><input type="checkbox" checked={catOn} onChange={(e) => setCatOn((e.target as HTMLInputElement).checked)} />
              <strong>强化商店类目</strong></label>
            {catOn ? <CategoryPicker label="强化类目（如「专属武器·觉醒」）" value={cat} onChange={setCat} options={options.categories.enhancement}
              kind="enhancement" forbidOfficial={enhOn} /> : null}
            {catOn && !enhOn ? <p class="small muted">只开类目不开强化：把现有强化阶段移到所选类目（客户端行与服务端 shopCategoryId 同步）。</p> : null}
          </div>

          {/* 4. exchange */}
          <div class="set-option">
            <label class="check"><input type="checkbox" checked={exOn} onChange={(e) => setExOn((e.target as HTMLInputElement).checked)} />
              <strong>兑换商店商品</strong></label>
            {exOn ? (
              <div class="param-fields">
                <CategoryPicker label="兑换类目" value={exCat} onChange={setExCat} options={options.categories.exchange} kind="exchange" forbidOfficial={false} />
                <label class="param-field"><span>商品母本 ID（50 列）</span>
                  <input class="mono" list="weapon-set-source-products" value={ex.sourceProduct}
                    onInput={(e) => setEx({ ...ex, sourceProduct: (e.target as HTMLInputElement).value.trim() })} />
                  <datalist id="weapon-set-source-products">{sourceProducts.map((p) => <option value={p} />)}</datalist>
                  <span class="small muted">只复制，不修改母本；新商品 ID 由后端分配</span></label>
                <MaterialPicker label="价格材料（唯一价格，清除母本其他货币）" value={ex.itemId} onChange={(id) => setEx({ ...ex, itemId: id })} materials={materials} />
                <label class="param-field"><span>每次所需数量</span>
                  <input type="number" min={1} step={1} value={ex.amount} onInput={(e) => setEx({ ...ex, amount: (e.target as HTMLInputElement).value })} /></label>
                <label class="param-field"><span>每次得到武器数</span>
                  <input type="number" min={1} step={1} value={ex.count} onInput={(e) => setEx({ ...ex, count: (e.target as HTMLInputElement).value })} /></label>
                <label class="param-field"><span>每人限购次数（总计）</span>
                  <input type="number" min={1} step={1} value={ex.stock} onInput={(e) => setEx({ ...ex, stock: (e.target as HTMLInputElement).value })} />
                  <span class="small muted">没有日 / 月重置</span></label>
                <label class="param-field wide"><span>商品说明</span>
                  <input value={ex.description} placeholder="专属武器兑换" onInput={(e) => setEx({ ...ex, description: (e.target as HTMLInputElement).value })} /></label>
              </div>
            ) : null}
          </div>

          {/* 5. awakening material */}
          <div class="set-option">
            <label class="check"><input type="checkbox" checked={awakenOn} onChange={(e) => setAwakenOn((e.target as HTMLInputElement).checked)} />
              <strong>突破材料限定</strong></label>
            {awakenOn ? (
              <div class="param-fields">
                <MaterialPicker label="突破替代材料" value={awakenMat} onChange={setAwakenMat} materials={materials} />
                <Notice kind="warn">
                  只约束「用材料代替重复本体」这条路径：<strong>现有服务端仍允许用重复本体突破</strong>，不是从 API 层禁止其他突破方式。
                  需要客户端补丁 <span class="mono">equipment-awakening-material-v1</span>（client-patch/equipment-awakening-material）和服务端白名单
                  <span class="mono"> equipment_awakening_material.materialByEquipment</span>；只写数据或旧客户端忽略配置都不算支持。
                  新版能力目录目前缺方法哈希证据，开启后草稿可保存，但<strong>交付兼容检查会阻断</strong>，直到补齐可信证据。
                </Notice>
              </div>
            ) : null}
          </div>

          {options.notes.length ? <ul class="small muted">{options.notes.map((n) => <li>{n}</li>)}</ul> : null}
        </>
      )}

      {problems.length && anyOn ? <ul class="inline-problems">{problems.map((p) => <li>{p}</li>)}</ul> : null}

      {/* status cells: never let a saved draft stand in for compatibility or device */}
      <div class="status-strip" aria-label="专属武器全套状态">
        <div><span class="label">草稿</span>
          {written && writtenNow ? <span class="value state-ok">已写入草稿{written.data.status ? `（${written.data.status.label}）` : ""}</span>
            : fresh ? <span class={"value " + (fresh.ok ? "" : "error-text")}>{fresh.ok ? "预检完成，未写入" : "预检被拒，未写入"}</span>
            : <span class="value state-none">{result ? "请求已改，需重新预检" : "未预检"}{written ? "（上一次请求已写入）" : ""}</span>}</div>
        <div><span class="label">交付兼容</span>
          {requires?.clientCapabilities.length
            ? <span class="value warn-text" title="生成交付时执行；未解决的客户端能力会阻断">未执行 · 预计阻断（缺 {requires.clientCapabilities.join("、")} 证据）</span>
            : <span class="value state-none" title="在「本次修改」生成交付时执行">未执行</span>}</div>
        <div><span class="label">设备</span><span class="value state-none" title="编辑台不装机">未执行</span></div>
      </div>

      {shown ? (
        <div class="set-preview">
          {shown.error ? <Notice kind="error">{shown.error}</Notice> : null}
          {costCheck?.materialTotals ? (
            <p class="small">强化总消耗（{costCheck.purchaseMode ?? "?"}，到 Lv{costCheck.maxLevel ?? "?"}）：
              {Object.entries(costCheck.materialTotals).map(([id, n]) => `${nameOf(id)} ×${n}`).join(" + ") || "全部免费"}</p>
          ) : null}
          {awakenCheck ? (
            <p class="small warn-text">突破材料 {nameOf(awakenCheck.materialId ?? "")}：需要客户端能力 <span class="mono">{awakenCheck.clientCapability ?? "?"}</span>
              {awakenCheck.duplicateEquipmentAllowed ? "；后端确认仍允许重复本体突破" : ""}。</p>
          ) : null}
          {requires ? (
            <div class="small">
              <strong>依赖清单（requires）</strong>
              <ul>
                {requires.clientCapabilities.map((c) => <li>客户端：<span class="mono">{c}</span> {CAPABILITY_LABEL[c] ?? ""}</li>)}
                {requires.serverFeatures.map((f) => <li>服务端：<span class="mono">{f}</span> {FEATURE_LABEL[f] ?? ""}</li>)}
                {!requires.clientCapabilities.length && !requires.serverFeatures.length ? <li>没有额外依赖</li> : null}
              </ul>
              <span class="muted">这是数据依赖声明，不代表服务端已部署或客户端已打补丁。</span>
            </div>
          ) : null}
          <RuleList checks={shown.checks} title="预检检查" />
          {shown.rows ? <RowsView rows={shown.rows} /> : null}
        </div>
      ) : null}

      {written && savedRequest ? (
        <Notice>已写入：{describeSet(savedRequest.weapon)}。分配的类目 / 商品 ID 已存进草稿请求，重放时复核。生成、导出在「本次修改」。</Notice>
      ) : null}

      <div class="save-row">
        <button type="button" disabled={problems.length > 0 || busy !== null || !options} onClick={check}>{busy === "check" ? "预检中……" : "预检"}</button>
        <button type="button" class="primary" disabled={problems.length > 0 || busy !== null || !fresh?.ok}
          title={!fresh?.ok ? "先预检通过（请求改了要重新预检）" : ""} onClick={write}>{busy === "write" ? "写入中……" : "写入草稿"}</button>
        <span class="small muted">预检不预留 ID；写入时如遇 ID 被占用会被拒绝，需重新预检。</span>
      </div>
    </section>
  );
}
