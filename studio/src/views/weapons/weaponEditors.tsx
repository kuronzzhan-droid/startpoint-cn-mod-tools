// Weapon editing pieces shared by BOSS工坊「商店与武器」and 武器工坊: icon, kind names, soul / enhancement
// ability lines, 改强化材料 and the 克隆武器 wizard. Both editors take an OpTarget — a plain quest id writes
// that quest's boss draft; 武器工坊 passes its own (POST /api/studio/weapons/…, own 「本次修改」).
import { useEffect, useRef, useState } from "preact/hooks";
import { ability, TemplateOption } from "../../api";
import { boss, ShopWeaponRequest, WeaponAbilityChange, WeaponDoc, WeaponIcons } from "../../bossApi";
import { Notice } from "../common";
import { InfoTip } from "../Delivery";
import { PreviewState } from "../boss/BossParams";
import { cellOf, OpActions, OpTarget, useBossOp } from "../boss/bossOps";
import { present } from "../boss/bossModel";

/** Mode column (precondition1 − 1) that decides which content block a soul/enhancement row uses. */
const MODE_COLUMN: Record<string, number> = { ability_soul: 2, equipment_enhancement_ability: 5 };
export const TABLE_LABEL: Record<string, string> = { ability_soul: "魂珠词条", equipment_enhancement_ability: "强化词条" };
export const BLOCK_LABEL: Record<string, string> = { instant_content: "瞬时", during_content: "持续" };
export const USER_COST: Record<string, string> = { "1": "星导石（免费）", "2": "羁绊证" };
const TEXT_BAD = /[,\n\r"]|::/;

export function costText(costs: { itemId: string; amount: string | number; name?: string | null }[], names: Map<string, string>): string {
  return costs.length ? costs.map((c) => `${c.name ?? names.get(c.itemId) ?? c.itemId} ×${c.amount}`).join(" + ") : "—";
}

/** Materials with their item icon and name (武器工坊 detail fills both); falls back to the bare item ID. */
export function MaterialList({ costs }: { costs: { itemId: string; amount: string | number; name?: string | null; icon?: string | null }[] }) {
  if (!costs.length) return <span>—</span>;
  return (
    <span class="material-list">
      {costs.map((c) => (
        <span class="material" title={`item ${c.itemId}${c.icon ? "\n" + c.icon : ""}`}>
          {c.icon ? <WeaponIcon path={c.icon} size={20} /> : null}
          {c.name ?? <span class="mono">{c.itemId}</span>} ×{c.amount}
        </span>
      ))}
    </span>
  );
}

export interface AbilityLine {
  table: "ability_soul" | "equipment_enhancement_ability"; row: number; block: "instant_content" | "during_content";
  kind: string; power1: string; firstMax: string;
}

/** Active block of each soul / enhancement ability row, with its kind and strength (kind column +4/+5). */
export function abilityLines(weapon: WeaponDoc): AbilityLine[] {
  const out: AbilityLine[] = [];
  for (const table of ["ability_soul", "equipment_enhancement_ability"] as const) {
    const record = weapon[table];
    if (!record) continue;
    record.rows.forEach((row, index) => {
      const block = cellOf(row, MODE_COLUMN[table]) === "1" ? "during_content" : "instant_content";
      const at = weapon.kind_columns?.[table]?.[block];
      if (at === undefined) return;
      out.push({ table, row: index, block, kind: cellOf(row, at), power1: cellOf(row, at + 4), firstMax: cellOf(row, at + 5) });
    });
  }
  return out;
}

export function useKindNames(): Record<string, Map<string, TemplateOption>> {
  const [names, setNames] = useState<Record<string, Map<string, TemplateOption>>>({});
  useEffect(() => {
    for (const block of ["instant_content", "during_content"]) {
      ability.templates("ability", block).then((t) => setNames((n) => ({ ...n, [block]: new Map(t.options.map((o) => [o.kind, o])) })), () => undefined);
    }
  }, []);
  return names;
}

export function WeaponIcon({ path, size = 44 }: { path: string; size?: number }) {
  const [bad, setBad] = useState(false);
  if (!present(path) || bad) return <span class="weapon-icon empty" style={{ width: size + "px", height: size + "px" }} title={path || "无图标"}>?</span>;
  return <img class="weapon-icon" src={boss.iconUrl(path)} width={size} height={size} alt="" title={path} onError={() => setBad(true)} />;
}

export function KindName({ kind, block, kinds }: { kind: string; block: string; kinds: Record<string, Map<string, TemplateOption>> }) {
  const o = kinds[block]?.get(kind);
  return <span title={o?.en}>{o?.cn || o?.en || "kind"} <span class="mono small muted">{kind}</span></span>;
}

export function MaterialsEditor({ weapon, target, names, onPreview, onWritten, onClose }: {
  weapon: WeaponDoc; target: string | OpTarget; names: Map<string, string>;
  onPreview: (s: PreviewState) => void; onWritten: () => void; onClose: () => void;
}) {
  const initial = () => weapon.enhancement_chain.map((s) => ({
    productId: s.id, costs: s.costs.map((c) => ({ itemId: c.itemId, amount: String(c.amount) })),
    userCost: s.userCost ? String(s.userCost.amount) : "", userType: s.userCost?.type ?? "",
  }));
  const [stages, setStages] = useState(initial);
  const problems: string[] = [];
  const changed = stages.filter((s, i) => {
    const o = weapon.enhancement_chain[i];
    return s.costs.some((c, j) => c.amount !== String(o.costs[j]?.amount)) || s.userCost !== (o.userCost ? String(o.userCost.amount) : "");
  });
  for (const s of changed) {
    if (s.costs.some((c) => !Number.isInteger(Number(c.amount)) || Number(c.amount) < 1)) problems.push(`第 ${s.productId} 阶：材料数量要是正整数`);
    if (s.userCost !== "" && (!Number.isInteger(Number(s.userCost)) || Number(s.userCost) < 1)) problems.push(`第 ${s.productId} 阶：羁绊证数量要是正整数，或留空表示不收`);
  }
  const request: ShopWeaponRequest | null = changed.length ? {
    operation: "weapon_materials", weapon: { id: weapon.id, stages: changed.map((s) => {
      const o = weapon.enhancement_chain.find((x) => x.id === s.productId)!;
      const userChanged = s.userCost !== (o.userCost ? String(o.userCost.amount) : "");
      return {
        productId: s.productId, costs: s.costs.map((c) => ({ itemId: c.itemId, amount: Number(c.amount) })),
        ...(userChanged ? { userCost: s.userCost === "" ? null : { type: 2, amount: Number(s.userCost) } } : {}),
      };
    }) },
  } : null;
  const op = useBossOp(target, request, problems, onPreview, onWritten);
  return (
    <div class="param-block pending-block">
      <h4>改强化材料 · {cellOf(weapon.equipment?.row, 1)}<button type="button" class="link close-x" onClick={onClose} aria-label="关闭">×</button></h4>
      <div class="table-scroll">
        <table class="boss-table tier-edit">
          <thead><tr><th>阶</th><th>等级</th><th>每次材料</th><th>羁绊证 / 次 <InfoTip text="userCost type 2 = 羁绊证；留空 = 不收。不开放付费星导石（type 0）。" /></th></tr></thead>
          <tbody>
            {stages.map((s, i) => {
              const o = weapon.enhancement_chain[i];
              return (
                <tr>
                  <td class="mono small">{o.stage}</td><td class="small">{o.startLevel} → {o.maxLevel}（{o.purchaseCountTo120} 次）</td>
                  <td>{s.costs.map((c, j) => (
                    <label class="cost-input"><span class="small">{o.costs[j]?.name ?? names.get(c.itemId) ?? c.itemId}</span>
                      <input type="number" min={1} step={1} value={c.amount} class={c.amount !== String(o.costs[j]?.amount) ? "changed" : ""}
                        onInput={(e) => setStages(stages.map((x, k) => k === i ? { ...x, costs: x.costs.map((y, m) => m === j ? { ...y, amount: (e.target as HTMLInputElement).value } : y) } : x))} />
                    </label>
                  ))}</td>
                  <td>{s.userType && s.userType !== "2" ? <span class="small muted">{USER_COST[s.userType] ?? s.userType}（不在这里改）</span> : (
                    <input type="number" min={1} step={1} value={s.userCost} placeholder="不收"
                      onInput={(e) => setStages(stages.map((x, k) => k === i ? { ...x, userCost: (e.target as HTMLInputElement).value } : x))} />
                  )}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p class="small muted">客户端强化商品行与服务端 equipment_enhancement_shop.json 同步修改；只发送改过的阶。</p>
      <OpActions op={op} problems={problems} onReset={() => { setStages(initial()); onClose(); }} />
    </div>
  );
}

// -------------------------------------------------------------------------------- clone wizard

const STEPS = ["母本", "名称与数值", "词条", "图标", "确认"];
const SOUL_STEPS = ["母本", "名称与数值", "词条", "魂珠", "图标", "确认"];
/** 火水雷风光暗 = soul_elements 0..5. */
export const SOUL_ELEMENTS = ["火", "水", "雷", "风", "光", "暗"];
type SoulMode = "inherit" | "all" | "auto" | "pick";
const SOUL_MODE: Record<SoulMode, string> = {
  inherit: "沿用母本", all: "全属性可装备", auto: "自动（按武器属性推断）", pick: "指定属性",
};

/** item[12] of a soul item as text: "0,3,2,1,4,5" = all, "30" = auto, else element list. */
export function soulElementsText(value: string): string {
  if (!present(value)) return "（空）";
  if (value === "30") return "自动（30）";
  const parts = value.split(",").map((v) => v.trim());
  if (parts.length === 6 && new Set(parts).size === 6 && parts.every((p) => /^[0-5]$/.test(p))) return "全属性";
  return parts.map((p) => SOUL_ELEMENTS[Number(p)] ?? p).join("、");
}

/** `soul` adds the 魂珠 step (soul_elements + soulDescription, 武器工坊 only); `donorNote` replaces the BOSS donor hint. */
export function CloneWizard({ weapons, source, target, kinds, soul, donorNote, onPreview, onWritten, onClose }: {
  weapons: WeaponDoc[]; source: string; target: string | OpTarget; kinds: Record<string, Map<string, TemplateOption>>;
  soul?: boolean; donorNote?: string;
  onPreview: (s: PreviewState) => void; onWritten: () => void; onClose: () => void;
}) {
  const steps = soul ? SOUL_STEPS : STEPS;
  const [step, setStep] = useState(0);
  const stepName = steps[step];
  const [src, setSrc] = useState(source);
  const donor = weapons.find((w) => w.id === src) ?? weapons[0];
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [hp, setHp] = useState("1");
  const [atk, setAtk] = useState("1");
  const [edits, setEdits] = useState<Record<string, { kind: string; power1: string; firstMax: string }>>({});
  const [icon, setIcon] = useState("");
  const [enhancedIcon, setEnhancedIcon] = useState("");
  const [icons, setIcons] = useState<WeaponIcons | null>(null);
  const [iconFilter, setIconFilter] = useState("");
  const [soulMode, setSoulMode] = useState<SoulMode>("inherit");
  const [soulPick, setSoulPick] = useState<number[]>([]);
  const [soulDescription, setSoulDescription] = useState("");
  useEffect(() => { boss.weaponIcons().then(setIcons, () => setIcons(null)); }, []);
  const box = useRef<HTMLElement>(null);
  useEffect(() => { box.current?.scrollIntoView({ block: "start", behavior: "smooth" }); }, []);
  useEffect(() => { setEdits({}); setIcon(""); setEnhancedIcon(""); }, [src]);
  const lines = donor ? abilityLines(donor) : [];
  const keyOf = (l: AbilityLine) => `${l.table}:${l.row}`;

  const problems: string[] = [];
  for (const [label, value] of [["名称", name], ["说明", description]] as const) {
    if (value && TEXT_BAD.test(value)) problems.push(`${label}不能含半角逗号、换行、双引号或「::」`);
  }
  if (name.length > 80) problems.push("名称最多 80 字");
  if (description.length > 57) problems.push("说明最多 57 字");
  if (soul) {
    if (soulDescription && TEXT_BAD.test(soulDescription)) problems.push("魂珠说明不能含半角逗号、换行、双引号或「::」");
    if (soulDescription.length > 1000) problems.push("魂珠说明最多 1000 字");
    if (soulMode === "pick" && !soulPick.length) problems.push("指定属性至少选一个");
  }
  for (const [label, v] of [["HP 倍率", hp], ["攻击倍率", atk]] as const) {
    const n = Number(v);
    if (!Number.isFinite(n) || n <= 0 || n > 1000) problems.push(`${label}要是 0–1000 之间的正数`);
  }
  const abilities: WeaponAbilityChange[] = [];
  for (const l of lines) {
    const e = edits[keyOf(l)];
    if (!e) continue;
    const change: WeaponAbilityChange = { table: l.table, row: l.row, block: l.block };
    if (e.kind !== l.kind) {
      if (!/^\d+$/.test(e.kind)) problems.push(`${TABLE_LABEL[l.table]}第 ${l.row + 1} 行：kind 要是数字`);
      else change.kind = Number(e.kind);
    }
    if (e.power1 !== l.power1 || e.firstMax !== l.firstMax) {
      const a = Number(e.power1), b = Number(e.firstMax);
      if (!Number.isInteger(a) || !Number.isInteger(b)) problems.push(`${TABLE_LABEL[l.table]}第 ${l.row + 1} 行：强度要是整数`);
      else change.strength = [a, b];
    }
    if (change.kind !== undefined || change.strength) abilities.push(change);
  }
  const request: ShopWeaponRequest | null = donor ? { operation: "weapon_clone", weapon: {
    sourceWeapon: donor.id,
    ...(name.trim() ? { name: name.trim() } : {}), ...(description.trim() ? { description: description.trim() } : {}),
    ...(Number(hp) !== 1 ? { hpMultiplier: Number(hp) } : {}), ...(Number(atk) !== 1 ? { attackMultiplier: Number(atk) } : {}),
    ...(abilities.length ? { abilities } : {}), ...(icon ? { icon } : {}), ...(enhancedIcon ? { enhancedIcon } : {}),
    ...(soul && soulDescription.trim() ? { soulDescription: soulDescription.trim() } : {}),
    ...(soul && soulMode !== "inherit" ? { soul_elements: soulMode === "pick" ? [...soulPick].sort((a, b) => a - b) : soulMode } : {}),
  } } : null;
  const donorSoul = cellOf(donor?.soul_item?.row, 12);
  const soulText = soulMode === "inherit" ? `沿用母本：${soulElementsText(donorSoul)}`
    : soulMode === "pick" ? soulPick.length ? [...soulPick].sort((a, b) => a - b).map((e) => SOUL_ELEMENTS[e]).join("、") : "（未选）" : SOUL_MODE[soulMode];
  const op = useBossOp(target, request, problems, onPreview, onWritten);
  // Non-satisfied rule results (e.g. weapon.soul-elements-inherited) shown inside the wizard, not only in the side column.
  const warnings = (op.fresh ? op.checks ?? [] : []).filter((c) => c.status !== "满足" && c.status !== "不适用");
  const allocatedWeapon = op.fresh ? op.preview?.changes?.find((c) => c.table === "master/item/equipment.orderedmap" && c.old === null)?.path[0] : undefined;
  const allocatedStages = op.fresh ? (op.preview?.changes ?? []).filter((c) => c.table.endsWith("equipment_enhancement_shop.orderedmap") && c.old === null).map((c) => c.path[0]) : [];
  const iconList = (icons?.equipment ?? []).filter((i) => !iconFilter.trim() || (i.icon + i.name + i.id).toLowerCase().includes(iconFilter.trim().toLowerCase())).slice(0, 48);
  const enhList = (icons?.enhanced ?? []).filter((i) => !iconFilter.trim() || (i.icon + i.name + i.id).toLowerCase().includes(iconFilter.trim().toLowerCase())).slice(0, 24);

  return (
    <section class="boss-block clone-wizard" aria-label="克隆武器向导" ref={box}>
      <header><h3>克隆武器</h3><span class="small muted">克隆装备、魂珠、状态、强化词条和 6 阶强化链；新 ID 由后端分配，不自动上架</span>
        <span class="spacer" /><button type="button" class="link close-x" onClick={onClose} aria-label="关闭">×</button></header>
      <ol class="wizard-steps">
        {steps.map((s, i) => <li class={i === step ? "on" : i < step ? "done" : ""}><button type="button" class="link" onClick={() => setStep(i)}>{i + 1}. {s}</button></li>)}
      </ol>
      {stepName === "母本" ? (
        <div class="param-fields">
          <label class="param-field wide"><span>母本武器</span>
            <select value={donor?.id} onChange={(e) => setSrc((e.target as HTMLSelectElement).value)}>
              {weapons.map((w) => <option value={w.id}>{cellOf(w.equipment?.row, 1)} · {w.id}</option>)}
            </select>
            <span class="small muted">{donorNote ?? "只能从这一关关联的武器（或本草稿已克隆的）中选；诅咒 / PARADOX 武器的觉醒限制不会被克隆（审查 M2）。"}</span>
          </label>
        </div>
      ) : stepName === "名称与数值" ? (
        <div class="param-fields">
          <label class="param-field"><span>名称</span><input value={name} placeholder={cellOf(donor?.equipment?.row, 1)} onInput={(e) => setName((e.target as HTMLInputElement).value)} />
            <span class="small muted">留空沿用母本；魂珠名自动加「魂珠」，强化名加「·改」</span></label>
          <label class="param-field wide"><span>说明（≤57 字）</span><input value={description} placeholder={cellOf(donor?.equipment?.row, 7)} onInput={(e) => setDescription((e.target as HTMLInputElement).value)} /></label>
          <label class="param-field"><span>HP 倍率</span><input type="number" min={0} step={0.05} value={hp} onInput={(e) => setHp((e.target as HTMLInputElement).value)} />
            <span class="small muted">按母本每级数值相乘取整</span></label>
          <label class="param-field"><span>攻击倍率</span><input type="number" min={0} step={0.05} value={atk} onInput={(e) => setAtk((e.target as HTMLInputElement).value)} /></label>
          {donor ? <p class="small muted wide">母本：{donor.status.map((s) => `Lv${s.level} HP ${cellOf(s.row, 0)} / 攻 ${cellOf(s.row, 1)}`).join(" · ")}
            {Number(hp) !== 1 || Number(atk) !== 1 ? ` → 新：${donor.status.map((s) => `Lv${s.level} HP ${Math.round(Number(cellOf(s.row, 0)) * Number(hp))} / 攻 ${Math.round(Number(cellOf(s.row, 1)) * Number(atk))}`).join(" · ")}` : ""}</p> : null}
        </div>
      ) : stepName === "词条" ? (
        <div>
          <p class="small muted">只改语义字段（kind 与强度），不开放原始列号；kind 用角色词条编辑器同一份清单。kind 必须是该块客户端支持的分支，列位由后端按 M2.4 证据核对。</p>
          <div class="table-scroll">
            <table class="boss-table">
              <thead><tr><th>词条</th><th>块</th><th>kind</th><th>强度（初始 → 满级）</th></tr></thead>
              <tbody>
                {lines.map((l) => {
                  const e = edits[keyOf(l)] ?? { kind: l.kind, power1: l.power1, firstMax: l.firstMax };
                  const set = (patch: Partial<typeof e>) => setEdits({ ...edits, [keyOf(l)]: { ...e, ...patch } });
                  const options = [...(kinds[l.block]?.values() ?? [])].filter((o) => o.selectable || o.kind === l.kind);
                  return (
                    <tr class={edits[keyOf(l)] ? "on" : ""}>
                      <td>{TABLE_LABEL[l.table]} 第 {l.row + 1} 行</td>
                      <td>{BLOCK_LABEL[l.block]}</td>
                      <td>
                        <select value={e.kind} aria-label="kind" onChange={(ev) => set({ kind: (ev.target as HTMLSelectElement).value })}>
                          {!options.some((o) => o.kind === e.kind) ? <option value={e.kind}>kind {e.kind}</option> : null}
                          {options.map((o) => <option value={o.kind}>{o.kind} · {o.cn || o.en}</option>)}
                        </select>
                        {e.kind !== l.kind ? <span class="small muted"> 原 <KindName kind={l.kind} block={l.block} kinds={kinds} /></span> : null}
                      </td>
                      <td class="nowrap">
                        <input type="number" step={1} value={e.power1} aria-label="初始强度" class="short" onInput={(ev) => set({ power1: (ev.target as HTMLInputElement).value })} />
                        {" → "}
                        <input type="number" step={1} value={e.firstMax} aria-label="满级强度" class="short" onInput={(ev) => set({ firstMax: (ev.target as HTMLInputElement).value })} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {!lines.length ? <p class="small muted">母本没有可改的词条行。</p> : null}
        </div>
      ) : stepName === "魂珠" ? (
        <div class="param-fields">
          <fieldset class="param-field wide soul-elements">
            <legend>魂珠可装备属性（item c12）</legend>
            <div class="segmented" role="radiogroup" aria-label="魂珠可装备属性">
              {(Object.keys(SOUL_MODE) as SoulMode[]).map((m) => (
                <button type="button" role="radio" aria-checked={soulMode === m} class={soulMode === m ? "on" : ""}
                  onClick={() => setSoulMode(m)}>{SOUL_MODE[m]}</button>
              ))}
            </div>
            {soulMode === "pick" ? (
              <div class="soul-pick">
                {SOUL_ELEMENTS.map((e, i) => (
                  <label class="check"><input type="checkbox" checked={soulPick.includes(i)}
                    onChange={(ev) => setSoulPick((ev.target as HTMLInputElement).checked ? [...soulPick, i] : soulPick.filter((x) => x !== i))} />{e}</label>
                ))}
              </div>
            ) : null}
            <span class="small muted">母本魂珠：{soulElementsText(donorSoul)} <span class="mono">{donorSoul}</span>。
              「沿用母本」不改 c12，后端会给出继承提醒；全属性写 0,3,2,1,4,5，自动写 30。</span>
          </fieldset>
          {soulMode === "inherit" ? (
            <Notice kind="warn">魂珠会沿用母本的可装备属性限制（{soulElementsText(donorSoul)}）。母本若是单属性魂珠，新武器的魂珠也只能给这些属性的角色装备；确认这符合设计，或在上面改。</Notice>
          ) : null}
          <label class="param-field wide"><span>魂珠说明（item c5）</span>
            <textarea rows={3} value={soulDescription} placeholder={cellOf(donor?.soul_item?.row, 5)}
              onInput={(e) => setSoulDescription((e.target as HTMLTextAreaElement).value)} />
            <span class="small muted">留空沿用母本魂珠说明；最多 1000 字，不能含半角逗号、换行、双引号或「::」</span>
          </label>
        </div>
      ) : stepName === "图标" ? (
        <div>
          <input placeholder="按名字、ID 或路径搜索已有图标" value={iconFilter} onInput={(e) => setIconFilter((e.target as HTMLInputElement).value)} />
          <p class="small muted">{icons?.note ?? "正在读取图标清单……"}。选本体图标会一并复用对应魂珠的图标组合。</p>
          <h5>本体图标（装备表 c6）{icon ? <> · 已选 <span class="mono">{icon}</span> <button type="button" class="link" onClick={() => setIcon("")}>清除</button></> : " · 未选则沿用母本"}</h5>
          <div class="icon-grid">
            {iconList.map((i) => (
              <button type="button" class={"icon-pick" + (icon === i.icon ? " on" : "")} title={`${i.name} · ${i.id}\n${i.icon}`} onClick={() => setIcon(i.icon)}>
                <WeaponIcon path={i.icon} size={40} /><span class="small">{i.name}</span>
              </button>
            ))}
          </div>
          <h5>强化后图标（强化表 c4）{enhancedIcon ? <> · 已选 <span class="mono">{enhancedIcon}</span> <button type="button" class="link" onClick={() => setEnhancedIcon("")}>清除</button></> : " · 未选则沿用母本"}</h5>
          <div class="icon-grid">
            {enhList.map((i) => (
              <button type="button" class={"icon-pick" + (enhancedIcon === i.icon ? " on" : "")} title={`${i.name} · ${i.id}\n${i.icon}`} onClick={() => setEnhancedIcon(i.icon)}>
                <WeaponIcon path={i.icon} size={40} /><span class="small">{i.name}</span>
              </button>
            ))}
          </div>
        </div>
      ) : (
        <div>
          <dl class="kv alloc">
            <dt>母本</dt><dd>{cellOf(donor?.equipment?.row, 1)} <span class="mono small">{donor?.id}</span></dd>
            <dt>新武器 ID</dt><dd class="mono">{allocatedWeapon ?? (op.fresh ? "—" : "预检后显示")}</dd>
            <dt>强化商品 ID</dt><dd class="mono small">{allocatedStages.length ? allocatedStages.join("、") : op.fresh ? "—" : "预检后显示"}</dd>
            <dt>名称</dt><dd>{name || "沿用母本"}</dd>
            <dt>数值</dt><dd>HP ×{hp} · 攻击 ×{atk}</dd>
            <dt>词条改动</dt><dd>{abilities.length ? abilities.map((a) => `${TABLE_LABEL[a.table]}第 ${a.row + 1} 行${a.kind !== undefined ? ` kind→${a.kind}` : ""}${a.strength ? ` 强度→${a.strength.join("/")}` : ""}`).join("；") : "无"}</dd>
            <dt>图标</dt><dd class="mono small">{icon || "沿用母本"}{enhancedIcon ? " · 强化 " + enhancedIcon : ""}</dd>
            {soul ? <><dt>魂珠属性</dt><dd>{soulText}</dd><dt>魂珠说明</dt><dd>{soulDescription.trim() || "沿用母本"}</dd></> : null}
          </dl>
          <p class="small muted">ID 同时避开客户端表、服务端记录和其它草稿；写入后保存在草稿请求里，之后重放用同一组 ID。上架需另做「新增商品」（在对应分类里克隆一行装备奖励商品，再把奖励改成新武器 ID）。</p>
        </div>
      )}
      <div class="save-row">
        <button type="button" disabled={step === 0} onClick={() => setStep(step - 1)}>上一步</button>
        <button type="button" disabled={step === steps.length - 1} onClick={() => setStep(step + 1)}>下一步</button>
      </div>
      {soul && warnings.length ? (
        <Notice kind={warnings.some((c) => c.blocking || c.status === "问题") ? "error" : "warn"}>
          <strong>预检提醒（{warnings.length}）</strong>
          <ul class="small">{warnings.map((c) => <li>{c.status}{c.blocking ? " · 阻断" : ""}：{c.message}</li>)}</ul>
        </Notice>
      ) : null}
      <OpActions op={op} problems={problems} onReset={onClose} idle="选好母本后自动预检" />
    </section>
  );
}
