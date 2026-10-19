// 商店与武器：分类商品表（改价格 / 库存；新增待 M6.1）、关联武器（数值 / 词条 / 到 120 的强化链）、
// 克隆武器向导（名称、数值倍率、词条、已有图标引用；ID 由后端分配并显示）、改强化材料。
// 每次一个操作：实时预检 → 写入草稿；三处同步、C8004 与 kind 落位的结果并排显示。
import { ComponentChildren } from "preact";
import { useEffect, useMemo, useRef, useState } from "preact/hooks";
import { ability, TemplateOption } from "../../api";
import {
  boss, BossDoc, MaterialCost, ShopDoc, ShopProduct, ShopWeaponRequest, WeaponAbilityChange, WeaponDoc, WeaponIcons,
} from "../../bossApi";
import { Notice } from "../common";
import { InfoTip } from "../Delivery";
import { PreviewState } from "./BossParams";
import { Src } from "./BossRead";
import { cellOf, codeHits, OpActions, PendingFix, useBossOp, useSection } from "./bossOps";
import { present } from "./bossModel";

type Editing =
  | { kind: "product"; category: string; product: ShopProduct }
  | { kind: "delete"; category: string; product: ShopProduct }
  | { kind: "clone"; source: string }
  | { kind: "materials"; weapon: WeaponDoc }
  | null;

/** Mode column (precondition1 − 1) that decides which content block a soul/enhancement row uses. */
const MODE_COLUMN: Record<string, number> = { ability_soul: 2, equipment_enhancement_ability: 5 };
const TABLE_LABEL: Record<string, string> = { ability_soul: "魂珠词条", equipment_enhancement_ability: "强化词条" };
const BLOCK_LABEL: Record<string, string> = { instant_content: "瞬时", during_content: "持续" };
const USER_COST: Record<string, string> = { "1": "星导石（免费）", "2": "羁绊证" };
const TEXT_BAD = /[,\n\r"]|::/;

function itemNames(shops: ShopDoc[]): Map<string, string> {
  const names = new Map<string, string>();
  for (const shop of shops) for (const p of shop.products) {
    for (const c of p.fields.currencies) if (c.item) names.set(c.itemId, cellOf(c.item.row, 2));
    for (const r of p.fields.rewards) if (r.kind === "0" && p.fields.rewards.length === 1) names.set(r.id, p.fields.name);
  }
  return names;
}

function costText(costs: { itemId: string; amount: string | number }[], names: Map<string, string>): string {
  return costs.length ? costs.map((c) => `${names.get(c.itemId) ?? c.itemId} ×${c.amount}`).join(" + ") : "—";
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

function useKindNames(): Record<string, Map<string, TemplateOption>> {
  const [names, setNames] = useState<Record<string, Map<string, TemplateOption>>>({});
  useEffect(() => {
    for (const block of ["instant_content", "during_content"]) {
      ability.templates("ability", block).then((t) => setNames((n) => ({ ...n, [block]: new Map(t.options.map((o) => [o.kind, o])) })), () => undefined);
    }
  }, []);
  return names;
}

export function BossShopWeapons({ doc, questId, rev, onPreview, onWritten }: {
  doc: BossDoc; questId: string; rev: string; onPreview: (s: PreviewState) => void; onWritten: () => void;
}) {
  const shops = useSection<ShopDoc[]>(questId, "shops", rev);
  const weapons = useSection<WeaponDoc[]>(questId, "weapons", rev);
  const [editing, setEditing] = useState<Editing>(null);
  const [lastChecks, setLastChecks] = useState<PreviewState["checks"]>(null);
  const kinds = useKindNames();
  useEffect(() => { setEditing(null); }, [rev]);
  const names = useMemo(() => {
    const map = itemNames(shops.data ?? []);
    for (const w of weapons.data ?? []) if (w.equipment) map.set(w.id, cellOf(w.equipment.row, 1));
    return map;
  }, [shops.data, weapons.data]);
  const relay = (s: PreviewState) => { if (s.checks) setLastChecks(s.checks); onPreview(s); };

  if (doc.routing.kind === "BothBoss") return <Notice kind="warn">五重入口（BothBoss）只读：商店挂在领主节点上，请打开隐藏关或领主节点所在副本。</Notice>;
  if (shops.error) return <Notice kind="error">读取商店失败：{shops.error}</Notice>;
  if (!shops.data) return <div class="loading">正在读取商店与武器……</div>;
  const sync = lastChecks?.find((c) => c.rule === "boss.shop-sync");
  const c8004 = codeHits(lastChecks, /C8004/);
  const kindHits = codeHits(lastChecks, /kind/i).filter((m) => !/C8004/.test(m));

  return (
    <div class="boss-read boss-shopweapons">
      <section class="boss-block sync-strip">
        <header><h3>同步与落位检查</h3><InfoTip text="三处同步 = 客户端商品行 · 服务端 category_map · 服务端分类内商品，逐键对照；C8004 = 币种/奖励图标不在已加载图集；kind 落位 = 词条 kind 写在客户端实际读取的列（魂珠 c44/c106，强化 c47/c109）。结果来自最近一次预检。" /></header>
        <ul class="sync-list small">
          <li class={sync ? (sync.status === "满足" ? "state-ok" : sync.status === "问题" ? "error-text" : "warn-text") : "muted"}>
            三处同步：{sync ? `${sync.status} · ${sync.message}` : "未执行（改动预检时核对；生成时再核对一次）"}
          </li>
          <li class={c8004.length ? "error-text" : lastChecks ? "state-ok" : "muted"}>
            图标图集（C8004）：{c8004.length ? c8004.join("；") : lastChecks ? "最近一次预检没有命中" : "未执行"}
          </li>
          <li class={kindHits.length ? "error-text" : lastChecks ? "state-ok" : "muted"}>
            词条 kind 落位：{kindHits.length ? kindHits.join("；") : lastChecks ? "最近一次预检没有命中" : "未执行（克隆武器改词条时核对）"}
          </li>
        </ul>
      </section>

      <section class="boss-block">
        <header><h3>兑换商店（{shops.data.length}）</h3>
          <span class="spacer" />
          <PendingFix why="M6.1 修复中：新增商品会沿用来源商品的上架时间（审查 M1），修好前不开放">
            <button type="button" disabled>新增商品</button>
          </PendingFix>
        </header>
        {!shops.data.length ? <p class="muted small">这一关没有关联的兑换商店。</p> : shops.data.map((shop) => (
          <article class="boss-shop">
            <header>
              <h4>分类 {shop.id}{shop.category ? ` · ${cellOf(shop.category.row, 0)}` : ""}</h4>
              <Src c={shop.category?.source} />
              {!shop.category ? <span class="error-text small">缺少分类同号行（C8601）</span> : null}
              <span class="small muted">服务端：{shop.server_sync}</span>
            </header>
            <div class="table-scroll">
              <table class="boss-table">
                <thead><tr><th>商品</th><th>价格</th><th>库存 / 限购</th><th>开放</th><th>奖励</th><th /></tr></thead>
                <tbody>
                  {shop.products.map((p) => {
                    const f = p.fields;
                    const on = editing && "product" in editing && editing.product.id === p.id;
                    return (
                      <tr class={on ? "on" : ""}>
                        <td>{f.name}<div class="small muted mono">{p.id}</div></td>
                        <td class="small">{costText(f.price, names)}</td>
                        <td class="small">{f.stock === "-1" ? "不限" : f.stock}
                          {[["每月", f.limit.monthly], ["每日", f.limit.daily], ["周期", f.limit.frequency]].filter(([, v]) => present(v)).map(([k, v]) => <span class="muted"> · {k} {v}</span>)}</td>
                        <td class="small">{present(f.availableFrom) ? f.availableFrom.slice(0, 10) : "—"}{present(f.availableUntil) ? ` 至 ${f.availableUntil.slice(0, 10)}` : ""}</td>
                        <td class="small">{f.rewards.map((r) => `${r.kind === "4" ? "装备" : "道具"} ${names.get(r.id) ?? r.id} ×${r.amount}`).join("、")}</td>
                        <td class="nowrap">
                          <button type="button" class="link" onClick={() => setEditing({ kind: "product", category: shop.id, product: p })}>改价格 / 库存</button>
                          {" "}<button type="button" class="link" onClick={() => setEditing({ kind: "delete", category: shop.id, product: p })}>下架</button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            {editing && (editing.kind === "product" || editing.kind === "delete") && editing.category === shop.id ? (
              <ProductEditor key={editing.kind + editing.product.id} editing={editing} questId={questId} names={names}
                onPreview={relay} onWritten={onWritten} onClose={() => setEditing(null)} />
            ) : null}
          </article>
        ))}
      </section>

      <section class="boss-block">
        <header><h3>武器（{weapons.data?.length ?? "…"}）</h3>
          <InfoTip text="关联商店里的装备奖励，以及本草稿克隆、尚未上架的新武器。克隆不自动上架。" /></header>
        {weapons.error ? <Notice kind="error">{weapons.error}</Notice> : !weapons.data ? <p class="small muted">正在读取武器……</p>
          : !weapons.data.length ? <p class="small muted">这一关的商店里没有武器。</p> : (
            <div class="weapon-list">
              {weapons.data.map((w) => (
                <WeaponCard weapon={w} names={names} kinds={kinds}
                  editingMaterials={editing?.kind === "materials" && editing.weapon.id === w.id}
                  onClone={() => setEditing({ kind: "clone", source: w.id })}
                  onMaterials={() => setEditing({ kind: "materials", weapon: w })}>
                  {editing?.kind === "materials" && editing.weapon.id === w.id ? (
                    <MaterialsEditor weapon={w} questId={questId} names={names} onPreview={relay} onWritten={onWritten}
                      onClose={() => setEditing(null)} />
                  ) : null}
                </WeaponCard>
              ))}
            </div>
          )}
      </section>

      {editing?.kind === "clone" && weapons.data ? (
        <CloneWizard key={editing.source} weapons={weapons.data} source={editing.source} questId={questId} kinds={kinds}
          onPreview={relay} onWritten={onWritten} onClose={() => setEditing(null)} />
      ) : null}
    </div>
  );
}

// ------------------------------------------------------------------------------------ product

function ProductEditor({ editing, questId, names, onPreview, onWritten, onClose }: {
  editing: { kind: "product" | "delete"; category: string; product: ShopProduct }; questId: string; names: Map<string, string>;
  onPreview: (s: PreviewState) => void; onWritten: () => void; onClose: () => void;
}) {
  const p = editing.product;
  const [price, setPrice] = useState(p.fields.price.map((c) => ({ itemId: c.itemId, amount: String(c.amount) })));
  const [stock, setStock] = useState(p.fields.stock);
  const problems: string[] = [];
  let request: ShopWeaponRequest | null = null;
  if (editing.kind === "delete") {
    request = { operation: "shop_delete", shop: { category: editing.category, productId: p.id } };
  } else {
    const changedPrice = price.some((c, i) => c.amount !== String(p.fields.price[i]?.amount));
    const changedStock = stock.trim() !== p.fields.stock;
    const costs: MaterialCost[] = price.map((c) => ({ itemId: c.itemId, amount: Number(c.amount) }));
    if (costs.some((c) => !Number.isInteger(c.amount) || c.amount < 1)) problems.push("价格要是正整数");
    const s = Number(stock);
    if (!Number.isInteger(s) || s < -1) problems.push("库存要是整数（-1 = 不限）");
    if (changedPrice || changedStock) {
      request = { operation: "shop_edit", shop: {
        category: editing.category, productId: p.id, ...(changedPrice ? { price: costs } : {}), ...(changedStock ? { stock: s } : {}) } };
    }
  }
  const op = useBossOp(questId, request, problems, onPreview, onWritten);
  return (
    <div class="param-block pending-block">
      <h4>{editing.kind === "delete" ? "下架" : "修改"} {p.fields.name} <span class="mono small muted">{p.id}</span>
        <button type="button" class="link close-x" onClick={onClose} aria-label="关闭">×</button></h4>
      {editing.kind === "delete" ? (
        <p class="small">同时删除客户端商品行、服务端 category_map 和分类内商品。只进草稿；撤销整份草稿即可恢复。</p>
      ) : (
        <div class="param-fields compact">
          {price.map((c, i) => (
            <label class="param-field"><span>价格 · {names.get(c.itemId) ?? c.itemId}</span>
              <input type="number" min={1} step={1} value={c.amount}
                onInput={(e) => setPrice(price.map((x, j) => j === i ? { ...x, amount: (e.target as HTMLInputElement).value } : x))} />
              <span class="small muted">原 {p.fields.price[i]?.amount}</span>
            </label>
          ))}
          <label class="param-field"><span>库存（总可兑换次数）</span>
            <input type="number" min={-1} step={1} value={stock} onInput={(e) => setStock((e.target as HTMLInputElement).value)} />
            <span class="small muted">原 {p.fields.stock}；-1 = 不限。每月 / 每日周期限购列不在这里改</span>
          </label>
        </div>
      )}
      <OpActions op={op} problems={problems} writeLabel={editing.kind === "delete" ? "写入下架" : "写入草稿"}
        onReset={() => { setPrice(p.fields.price.map((c) => ({ itemId: c.itemId, amount: String(c.amount) }))); setStock(p.fields.stock); onClose(); }} />
    </div>
  );
}

// ------------------------------------------------------------------------------------- weapon

function WeaponIcon({ path, size = 44 }: { path: string; size?: number }) {
  const [bad, setBad] = useState(false);
  if (!present(path) || bad) return <span class="weapon-icon empty" style={{ width: size + "px", height: size + "px" }} title={path || "无图标"}>?</span>;
  return <img class="weapon-icon" src={boss.iconUrl(path)} width={size} height={size} alt="" title={path} onError={() => setBad(true)} />;
}

function KindName({ kind, block, kinds }: { kind: string; block: string; kinds: Record<string, Map<string, TemplateOption>> }) {
  const o = kinds[block]?.get(kind);
  return <span title={o?.en}>{o?.cn || o?.en || "kind"} <span class="mono small muted">{kind}</span></span>;
}

function WeaponCard({ weapon, names, kinds, editingMaterials, onClone, onMaterials, children }: {
  weapon: WeaponDoc; names: Map<string, string>; kinds: Record<string, Map<string, TemplateOption>>; editingMaterials: boolean;
  onClone: () => void; onMaterials: () => void; children?: ComponentChildren;
}) {
  const e = weapon.equipment?.row;
  const lines = abilityLines(weapon);
  const statusText = weapon.status.map((s) => `Lv${s.level} HP ${cellOf(s.row, 0)} / 攻 ${cellOf(s.row, 1)}`).join(" · ");
  const enhanced = weapon.enhancement_status.filter((s) => cellOf(s.row, 0) !== "0" || cellOf(s.row, 1) !== "0")
    .map((s) => `Lv${s.level} +HP ${cellOf(s.row, 0)} / +攻 ${cellOf(s.row, 1)}`).join(" · ");
  const draftOnly = !weapon.product;
  return (
    <article class="weapon-card">
      <header>
        <WeaponIcon path={cellOf(e, 6)} />
        <div class="weapon-title">
          <strong>{cellOf(e, 1) || "（装备表缺行）"}</strong>
          <span class="mono small muted">{weapon.id}{weapon.product ? ` · 商品 ${weapon.product}` : ""}</span>
          {draftOnly ? <span class="tag pend">本草稿克隆，未上架</span> : null}
        </div>
        <span class="spacer" />
        <Src c={weapon.equipment?.source} />
        <button type="button" onClick={onClone}>以它为母本克隆</button>
        <button type="button" disabled={!weapon.enhancement_chain.length || editingMaterials} onClick={onMaterials}>改强化材料</button>
      </header>
      <dl class="kv">
        <dt>基础数值</dt><dd>{statusText || "—"}</dd>
        <dt>强化加成</dt><dd>{enhanced || "—"}</dd>
        <dt>词条</dt>
        <dd>
          <ul class="ability-lines">
            {lines.map((l) => (
              <li>{TABLE_LABEL[l.table]} 第 {l.row + 1} 行 · {BLOCK_LABEL[l.block]} · <KindName kind={l.kind} block={l.block} kinds={kinds} />
                {present(l.power1) ? <span class="small muted"> · 强度 {l.power1} → {l.firstMax}</span> : null}</li>
            ))}
          </ul>
        </dd>
        <dt>强化到 120</dt>
        <dd>
          {weapon.reaches_120 ? <span class="state-ok">可到 120</span> : <span class="warn-text">强化链到不了 120</span>}
          <span class="small">累计 {costText(weapon.materials_to_120, names)}
            {weapon.user_costs_to_120.length ? " + " + weapon.user_costs_to_120.map((u) => `${USER_COST[u.type] ?? "类型 " + u.type} ×${u.amount}`).join(" + ") : ""}</span>
        </dd>
      </dl>
      {weapon.enhancement_chain.length ? (
        <details class="tech" open={editingMaterials}>
          <summary>强化链（{weapon.enhancement_chain.length} 阶）</summary>
          <div class="table-scroll">
            <table class="boss-table">
              <thead><tr><th>阶</th><th>等级区间</th><th>购买次数</th><th>每次材料</th><th>用户货币</th><th>需觉醒</th></tr></thead>
              <tbody>
                {weapon.enhancement_chain.map((s) => (
                  <tr><td class="mono small">{s.stage} <span class="muted">{s.id}</span></td>
                    <td>{s.startLevel} → {s.maxLevel}</td><td>{s.purchaseCountTo120}</td>
                    <td class="small">{costText(s.costs, names)}</td>
                    <td class="small">{s.userCost ? `${USER_COST[s.userCost.type] ?? s.userCost.type} ×${s.userCost.amount}` : "—"}</td>
                    <td>{s.requireAwakeningLevel}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
          <p class="small muted">{weapon.material_semantics}</p>
        </details>
      ) : <p class="small muted">没有强化链。</p>}
      <details class="tech"><summary>技术细节</summary>
        <p class="small mono">kind 列：魂珠 c{weapon.kind_columns?.ability_soul?.instant_content}/c{weapon.kind_columns?.ability_soul?.during_content} ·
          强化 c{weapon.kind_columns?.equipment_enhancement_ability?.instant_content}/c{weapon.kind_columns?.equipment_enhancement_ability?.during_content}</p>
        <p class="small muted">{weapon.kind_evidence}</p>
      </details>
      {children}
    </article>
  );
}

function MaterialsEditor({ weapon, questId, names, onPreview, onWritten, onClose }: {
  weapon: WeaponDoc; questId: string; names: Map<string, string>;
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
  const op = useBossOp(questId, request, problems, onPreview, onWritten);
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
                    <label class="cost-input"><span class="small">{names.get(c.itemId) ?? c.itemId}</span>
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

function CloneWizard({ weapons, source, questId, kinds, onPreview, onWritten, onClose }: {
  weapons: WeaponDoc[]; source: string; questId: string; kinds: Record<string, Map<string, TemplateOption>>;
  onPreview: (s: PreviewState) => void; onWritten: () => void; onClose: () => void;
}) {
  const [step, setStep] = useState(0);
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
  } } : null;
  const op = useBossOp(questId, request, problems, onPreview, onWritten);
  const allocatedWeapon = op.fresh ? op.preview?.changes?.find((c) => c.table === "master/item/equipment.orderedmap" && c.old === null)?.path[0] : undefined;
  const allocatedStages = op.fresh ? (op.preview?.changes ?? []).filter((c) => c.table.endsWith("equipment_enhancement_shop.orderedmap") && c.old === null).map((c) => c.path[0]) : [];
  const iconList = (icons?.equipment ?? []).filter((i) => !iconFilter.trim() || (i.icon + i.name + i.id).toLowerCase().includes(iconFilter.trim().toLowerCase())).slice(0, 48);
  const enhList = (icons?.enhanced ?? []).filter((i) => !iconFilter.trim() || (i.icon + i.name + i.id).toLowerCase().includes(iconFilter.trim().toLowerCase())).slice(0, 24);

  return (
    <section class="boss-block clone-wizard" aria-label="克隆武器向导" ref={box}>
      <header><h3>克隆武器</h3><span class="small muted">克隆装备、魂珠、状态、强化词条和 6 阶强化链；新 ID 由后端分配，不自动上架</span>
        <span class="spacer" /><button type="button" class="link close-x" onClick={onClose} aria-label="关闭">×</button></header>
      <ol class="wizard-steps">
        {STEPS.map((s, i) => <li class={i === step ? "on" : i < step ? "done" : ""}><button type="button" class="link" onClick={() => setStep(i)}>{i + 1}. {s}</button></li>)}
      </ol>
      {step === 0 ? (
        <div class="param-fields">
          <label class="param-field wide"><span>母本武器</span>
            <select value={donor?.id} onChange={(e) => setSrc((e.target as HTMLSelectElement).value)}>
              {weapons.map((w) => <option value={w.id}>{cellOf(w.equipment?.row, 1)} · {w.id}</option>)}
            </select>
            <span class="small muted">只能从这一关关联的武器（或本草稿已克隆的）中选；诅咒 / PARADOX 武器的觉醒限制不会被克隆（审查 M2）。</span>
          </label>
        </div>
      ) : step === 1 ? (
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
      ) : step === 2 ? (
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
      ) : step === 3 ? (
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
          </dl>
          <p class="small muted">ID 同时避开客户端表、服务端记录和其它草稿；写入后保存在草稿请求里，之后重放用同一组 ID。上架需另做「新增商品」（待 M6.1）。</p>
        </div>
      )}
      <div class="save-row">
        <button type="button" disabled={step === 0} onClick={() => setStep(step - 1)}>上一步</button>
        <button type="button" disabled={step === STEPS.length - 1} onClick={() => setStep(step + 1)}>下一步</button>
      </div>
      <OpActions op={op} problems={problems} onReset={onClose} idle="选好母本后自动预检" />
    </section>
  );
}
