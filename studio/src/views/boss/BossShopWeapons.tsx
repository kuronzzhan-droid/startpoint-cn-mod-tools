// 商店与武器：分类商品表（新增 / 改价格 / 库存 / 下架）、关联武器（数值 / 词条 / 到 120 的强化链）、
// 克隆武器向导（名称、数值倍率、词条、已有图标引用；ID 由后端分配并显示）、改强化材料。
// 每次一个操作：实时预检 → 写入草稿；三处同步、C8004 与 kind 落位的结果并排显示。
// 武器卡片之外的武器编辑件（克隆向导 / 改强化材料 / 图标）与武器工坊共用，在 ../weapons/weaponEditors。
import { ComponentChildren } from "preact";
import { useEffect, useMemo, useState } from "preact/hooks";
import { TemplateOption } from "../../api";
import { BossDoc, MaterialCost, ShopDoc, ShopProduct, ShopWeaponRequest, WeaponDoc } from "../../bossApi";
import { Notice } from "../common";
import { InfoTip } from "../Delivery";
import {
  abilityLines, BLOCK_LABEL, CloneWizard, costText, KindName, MaterialsEditor, TABLE_LABEL, useKindNames, USER_COST, WeaponIcon,
} from "../weapons/weaponEditors";
import { PreviewState } from "./BossParams";
import { Src } from "./BossRead";
import { cellOf, codeHits, OpActions, useBossOp, useSection } from "./bossOps";
import { present } from "./bossModel";

type Editing =
  | { kind: "product"; category: string; product: ShopProduct }
  | { kind: "delete"; category: string; product: ShopProduct }
  | { kind: "add"; category: string }
  | { kind: "clone"; source: string }
  | { kind: "materials"; weapon: WeaponDoc }
  | null;

function itemNames(shops: ShopDoc[]): Map<string, string> {
  const names = new Map<string, string>();
  for (const shop of shops) for (const p of shop.products) {
    for (const c of p.fields.currencies) if (c.item) names.set(c.itemId, cellOf(c.item.row, 2));
    for (const r of p.fields.rewards) if (r.kind === "0" && p.fields.rewards.length === 1) names.set(r.id, p.fields.name);
  }
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
          <InfoTip text="新增 = 从这个分类的已有商品克隆一行（productId 由后端分配），默认 2000-01-01 起上架、不结束；不继承来源的过期窗口。" />
        </header>
        {!shops.data.length ? <p class="muted small">这一关没有关联的兑换商店。</p> : shops.data.map((shop) => (
          <article class="boss-shop">
            <header>
              <h4>分类 {shop.id}{shop.category ? ` · ${cellOf(shop.category.row, 0)}` : ""}</h4>
              <Src c={shop.category?.source} />
              {!shop.category ? <span class="error-text small">缺少分类同号行（C8601）</span> : null}
              <span class="small muted">服务端：{shop.server_sync}</span>
              <span class="spacer" />
              <button type="button" disabled={!shop.products.length || !shop.category}
                title={!shop.category ? "缺少分类同号行，不能新增" : !shop.products.length ? "分类里没有可克隆的商品" : ""}
                onClick={() => setEditing({ kind: "add", category: shop.id })}>新增商品</button>
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
            {editing?.kind === "add" && editing.category === shop.id ? (
              <AddProductEditor shop={shop} questId={questId} names={names} onPreview={relay} onWritten={onWritten} onClose={() => setEditing(null)} />
            ) : null}
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
                    <MaterialsEditor weapon={w} target={questId} names={names} onPreview={relay} onWritten={onWritten}
                      onClose={() => setEditing(null)} />
                  ) : null}
                </WeaponCard>
              ))}
            </div>
          )}
      </section>

      {editing?.kind === "clone" && weapons.data ? (
        <CloneWizard key={editing.source} weapons={weapons.data} source={editing.source} target={questId} kinds={kinds}
          onPreview={relay} onWritten={onWritten} onClose={() => setEditing(null)} />
      ) : null}
    </div>
  );
}

// ------------------------------------------------------------------------------------ product

/** Server clock is pinned (wf-custom-server-time-trap); a source window ending before it is already expired in game. */
const SERVER_NOW = "2025-08-05";
const DATE = /^\d{4}-\d{2}-\d{2}( \d{2}:\d{2}:\d{2})?$/;

function AddProductEditor({ shop, questId, names, onPreview, onWritten, onClose }: {
  shop: ShopDoc; questId: string; names: Map<string, string>;
  onPreview: (s: PreviewState) => void; onWritten: () => void; onClose: () => void;
}) {
  const [source, setSource] = useState(shop.products[0]?.id ?? "");
  const [from, setFrom] = useState("2000-01-01");
  const [until, setUntil] = useState("");
  const src = shop.products.find((p) => p.id === source);
  const problems: string[] = [];
  if (!src) problems.push("选一个来源商品");
  if (!DATE.test(from.trim())) problems.push("上架时间格式 YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS");
  if (until.trim() && !DATE.test(until.trim())) problems.push("下架时间格式 YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS（留空 = 不结束）");
  if (DATE.test(from.trim()) && DATE.test(until.trim()) && until.trim() < from.trim()) problems.push("下架时间不能早于上架时间");
  if (DATE.test(from.trim()) && from.trim().slice(0, 10) > SERVER_NOW) problems.push(`服务端时间固定在 ${SERVER_NOW}，上架时间晚于它会一直不开放`);
  const srcUntil = src && present(src.fields.availableUntil) ? src.fields.availableUntil : "";
  const expired = !!srcUntil && srcUntil.slice(0, 10) < SERVER_NOW;
  const request: ShopWeaponRequest | null = src ? { operation: "shop_add", shop: {
    category: shop.id, sourceProduct: src.id, availableFrom: from.trim(), availableUntil: until.trim() ? until.trim() : null } } : null;
  const op = useBossOp(questId, problems.length ? null : request, problems, onPreview, onWritten);
  return (
    <div class="param-block pending-block">
      <h4>新增商品 · 分类 {shop.id} <button type="button" class="link close-x" onClick={onClose} aria-label="关闭">×</button></h4>
      <div class="param-fields compact">
        <label class="param-field"><span>克隆来源</span>
          <select value={source} onChange={(e) => setSource((e.target as HTMLSelectElement).value)}>
            {shop.products.map((p) => <option value={p.id}>{p.fields.name} · {p.id}</option>)}
          </select>
          {src ? <span class="small muted">价格 {costText(src.fields.price, names)} · 来源窗口 {present(src.fields.availableFrom) ? src.fields.availableFrom.slice(0, 10) : "—"}
            {srcUntil ? ` 至 ${srcUntil.slice(0, 10)}` : " 起不结束"}</span> : null}
        </label>
        <label class="param-field"><span>上架时间</span>
          <input class="mono" value={from} onInput={(e) => setFrom((e.target as HTMLInputElement).value)} />
          <span class="small muted">默认 2000-01-01（服务端时间钉在 {SERVER_NOW}）</span>
        </label>
        <label class="param-field"><span>下架时间</span>
          <input class="mono" placeholder="留空 = 不结束" value={until} onInput={(e) => setUntil((e.target as HTMLInputElement).value)} />
        </label>
      </div>
      {expired ? <Notice kind="warn">来源商品已于 {srcUntil} 下架（服务端时间 {SERVER_NOW}）。新商品用上面的窗口，不继承来源的过期时间；这只是提示，不阻断。</Notice> : null}
      <p class="small muted">新 productId 由后端分配，同时写客户端商品行、服务端 category_map 和分类内商品；之后可用「改价格 / 库存」继续改。</p>
      <OpActions op={op} problems={problems} onReset={onClose} idle="选一个来源商品" />
    </div>
  );
}

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
