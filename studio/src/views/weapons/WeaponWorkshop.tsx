// 武器工坊：不挂副本的全局武器列表（搜索 / 属性 / 稀有度）→ 详情（数值曲线、魂珠与词条、强化阶段、觉醒素材、
// 商店与卡池引用）→ 克隆为新武器（含魂珠可装备属性与魂珠说明）/ 改强化材料。每个武器一份独立草稿
// （work/studio-drafts/weapons/<id>/），「本次修改」抽屉里保存、生成、导出，接口见 docs/studio/weapons.md。
import { useEffect, useMemo, useRef, useState } from "preact/hooks";
import { DraftChange, onDraftChange, RuleResult } from "../../api";
import type { AnyBossRequest, BossRecord } from "../../bossApi";
import { href, Route } from "../../router";
import {
  asWeaponDoc, WEAPON_ANY, WEAPON_ELEMENTS, weaponDeliveries, WeaponDetail, WeaponDraftSummary, weaponElement, weaponKey,
  WeaponList, weapons, weaponSubject,
} from "../../weaponApi";
import { ChangesPanel, ChecksList, useDraftOf } from "../Changes";
import { Drawer, ElementBadge, Notice, Rarity, StatusStrip } from "../common";
import { InfoTip, useDeliveries } from "../Delivery";
import { deviceCell, sameDraft } from "../DeviceResult";
import { ChecksPanel } from "../boss/BossChecks";
import { describeRequest } from "../boss/BossDetail";
import { PreviewState } from "../boss/BossParams";
import { cellOf, OpTarget } from "../boss/bossOps";
import { present } from "../boss/bossModel";
import {
  abilityLines, BLOCK_LABEL, CloneWizard, KindName, MaterialList, MaterialsEditor, soulElementsText, TABLE_LABEL, useKindNames,
  USER_COST, WeaponIcon,
} from "./weaponEditors";
import "../boss/boss.css";
import "./weapons.css";

function remembered(key: string, fallback: string): string {
  try { return sessionStorage.getItem(key) ?? fallback; } catch { return fallback; }
}
function remember(key: string, value: string) {
  try { sessionStorage.setItem(key, value); } catch { /* storage unavailable */ }
}

const link = (id?: string, tab?: string, sub?: string): string => href({ work: "content", shop: "weapons", id, tab, sub } as Route);

/** Weapon drafts (GET /drafts), refreshed on every weapon draft write. */
function useWeaponDrafts(): WeaponDraftSummary[] | null {
  const [drafts, setDrafts] = useState<WeaponDraftSummary[] | null>(null);
  useEffect(() => {
    const load = () => weapons.drafts().then((r) => setDrafts(r.drafts), () => setDrafts([]));
    load();
    return onDraftChange((key) => { if (key === WEAPON_ANY) load(); });
  }, []);
  return drafts;
}

/** Previews / writes of the weapon routes; the written message links to that weapon's 「本次修改」. */
function weaponTarget(id: string): OpTarget {
  return {
    id, preview: (_target: string, request: AnyBossRequest) => weapons.preview(request),
    apply: async (request) => {
      const result = await weapons.apply(request);
      return {
        label: result.status.label, link: link(result.weaponId, "changes"),
        linkText: request.operation === "weapon_clone" ? `打开新武器 ${result.weaponId} 的「本次修改」→` : undefined,
      };
    },
  };
}

export function WeaponWorkshop({ id, tab, sub }: { id?: string; tab?: string; sub?: string }) {
  const drafts = useWeaponDrafts();
  return (
    <section class="page weapon-page">
      <div class="page-head">
        <div>
          <h1>武器工坊</h1>
          <p class="muted">不需要副本：查全部武器，克隆新武器、改强化材料。改动只进本地武器草稿，生成后才是测试补丁；上架另到 BOSS工坊「商店与武器」。</p>
        </div>
      </div>
      <div class="weapon-layout">
        <WeaponListPane selected={id} drafts={drafts} />
        {id ? <WeaponDetailPane key={id} id={id} tab={tab} sub={sub} />
          : <div class="boss-main"><Notice>从左侧选一把武器查看详情；以它为母本可以「克隆为新武器」。</Notice></div>}
      </div>
    </section>
  );
}

// ------------------------------------------------------------------------------------- list

function WeaponListPane({ selected, drafts }: { selected?: string; drafts: WeaponDraftSummary[] | null }) {
  const [query, setQuery] = useState(() => remembered("weapon.q", ""));
  const [element, setElement] = useState(() => remembered("weapon.element", ""));
  const [rarity, setRarity] = useState(() => remembered("weapon.rarity", ""));
  const [list, setList] = useState<WeaponList | null>(null);
  const [error, setError] = useState<string | null>(null);
  const seq = useRef(0);
  useEffect(() => remember("weapon.q", query), [query]);
  useEffect(() => remember("weapon.element", element), [element]);
  useEffect(() => remember("weapon.rarity", rarity), [rarity]);
  // Filtering is server side (q / element / rarity); typing is debounced, stale answers dropped.
  useEffect(() => {
    const mine = ++seq.current;
    const timer = window.setTimeout(() => {
      weapons.list({ q: query, element, rarity }).then(
        (r) => { if (mine === seq.current) { setList(r); setError(null); } },
        (e: Error) => { if (mine === seq.current) setError(e.message); });
    }, 250);
    return () => window.clearTimeout(timer);
  }, [query, element, rarity]);
  const draftIds = useMemo(() => new Set((drafts ?? []).map((d) => d.characterId)), [drafts]);

  return (
    <nav class="weapon-side" aria-label="武器列表">
      <input class="search small-search" type="search" value={query} placeholder="搜索名称、ID、内部代码"
        onInput={(e) => setQuery((e.target as HTMLInputElement).value)}
        onKeyDown={(e) => { if (e.key === "Enter" && list?.items[0]) location.hash = link(list.items[0].id); }} />
      <div class="weapon-filters">
        <select aria-label="属性" value={element} onChange={(e) => setElement((e.target as HTMLSelectElement).value)}
          title="服务端 equipment_element 装备分类；不是魂珠可装备属性限制">
          <option value="">全部属性</option>
          {WEAPON_ELEMENTS.map((e, i) => <option value={String(i)}>{e}</option>)}
          <option value="-1">无属性</option>
        </select>
        <select aria-label="稀有度" value={rarity} onChange={(e) => setRarity((e.target as HTMLSelectElement).value)}>
          <option value="">全部稀有度</option>
          {[5, 4, 3, 2, 1].map((r) => <option value={String(r)}>{"★".repeat(r)}</option>)}
        </select>
      </div>
      {drafts?.length ? (
        <div class="weapon-drafts">
          <h4>武器草稿 <span class="count">{drafts.length}</span>
            <InfoTip text="GET /api/studio/weapons/drafts：每个武器一份草稿（克隆的新武器、或改过材料的已有武器），点开后在「本次修改」里保存与生成。" /></h4>
          <ul>
            {drafts.map((d) => (
              <li><a class={selected === d.characterId ? "on" : ""} href={link(d.characterId, "changes")}>
                <span class="weapon-draft-name">{d.name || "（无名）"} <span class="mono small muted">{d.characterId}</span></span>
                <span class="small muted">{d.isNew ? <span class="tag pend" title="草稿含克隆操作">新建</span> : <span class="tag" title="改已有武器">改</span>}
                  {" "}{d.changes} 项 · {d.savedAt ? "已保存" : "未保存"}</span>
              </a></li>
            ))}
          </ul>
        </div>
      ) : null}
      {error ? <Notice kind="error">武器列表读取失败：{error}</Notice> : null}
      {!list && !error ? <div class="loading">正在读取武器……</div> : null}
      {list ? (
        <>
          <p class="small muted">共 {list.total} 把{list.count < list.total ? `，显示前 ${list.count} 把（再缩小搜索）` : ""}</p>
          <ul class="weapon-rows">
            {list.items.map((w) => {
              const el = weaponElement(w.element);
              return (
                <li>
                  <a class={"weapon-row" + (selected === w.id ? " on" : "")} aria-current={selected === w.id ? "page" : undefined}
                    href={link(w.id)} title={`${w.name} · ${w.id}`}>
                    <WeaponIcon path={w.icon} size={36} />
                    <span class="weapon-row-main">
                      <span class="weapon-row-name">{w.name || "（无名）"}<Rarity value={w.rarity} /></span>
                      <span class="small muted">
                        <span class="mono">{w.id}</span>
                        {w.hasEnhancement ? <span class="tag" title="有强化本体">强化</span> : null}
                        {w.hasAwakening ? <span class="tag awake" title="原生最大觉醒等级 > 1">觉醒</span> : null}
                      </span>
                    </span>
                    <span class="weapon-row-side">
                      {el ? <ElementBadge element={el} /> : <span class="small muted" title="缺本机服务端 equipment_element 输入">—</span>}
                      <span class={"origin " + (w.isMod ? "origin-new" : w.isMod === false ? "origin-official" : "origin-unknown")}
                        title="按官方装备基线判断是否新增键；改动官方武器仍算官方">{w.isMod ? "MOD" : w.isMod === false ? "官方" : "未知"}</span>
                      {draftIds.has(w.id) ? <span class="dot" title="有草稿" /> : null}
                    </span>
                  </a>
                </li>
              );
            })}
          </ul>
          {list.notes.map((n) => <p class="small muted">{n}</p>)}
        </>
      ) : null}
    </nav>
  );
}

// ----------------------------------------------------------------------------------- detail

type Editing = "clone" | "materials" | null;
const IDLE: PreviewState = { state: "idle", checks: null, ok: false };

function WeaponDetailPane({ id, tab, sub }: { id: string; tab?: string; sub?: string }) {
  const [detail, setDetail] = useState<WeaponDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<Editing>(null);
  const [preview, setPreview] = useState<PreviewState>(IDLE);
  const kinds = useKindNames();
  const load = () => weapons.detail(id).then((d) => { setDetail(d); setError(null); }, (e: Error) => setError(e.message));
  useEffect(() => { load(); return onDraftChange((key) => { if (key === weaponKey(id)) load(); }); }, [id]);
  const subject = useMemo(() => weaponSubject(id), [id]);
  const draft = useDraftOf(subject);
  const built = useDeliveries(id, weaponDeliveries);
  const target = useMemo(() => weaponTarget(id), [id]);
  const cloneTarget = useMemo(() => weaponTarget("clone"), []);
  const doc = useMemo(() => (detail ? asWeaponDoc(detail) : null), [detail]);
  const names = useMemo(() => itemNames(detail), [detail]);
  const close = () => { setEditing(null); setPreview(IDLE); };

  if (error) return <div class="boss-main"><Notice kind="error">读取武器 {id} 失败：{error}</Notice></div>;
  if (!detail || !doc) return <div class="boss-main"><div class="loading">正在读取武器 {id}……</div></div>;

  const status = draft.view?.status ?? detail.draft_status ?? detail.status;
  const changes = draft.view?.changeset?.changes ?? [];
  const el = weaponElement(detail.element);
  const checks: RuleResult[] | null = editing ? preview.checks : detail.checks.length ? detail.checks : null;

  return (
    <>
      <div class="boss-main">
        <header class="char-header weapon-header">
          <WeaponIcon path={detail.icon} size={56} />
          <div class="char-header-main">
            <h1>{detail.name || "（无名）"}<Rarity value={detail.rarity} /></h1>
            <div class="muted">
              {el ? <span class="el-inline"><ElementBadge element={el} /> {el === "无" ? "无属性" : el + "属性"}</span> : "属性未知（缺本机服务端输入）"}
              {" · "}<span class={"origin " + (detail.isMod ? "origin-new" : detail.isMod === false ? "origin-official" : "origin-unknown")}>
                {detail.isMod ? "MOD 新增" : detail.isMod === false ? "官方已有" : "来源未知"}</span>
              {detail.hasEnhancement ? <span class="tag">可强化</span> : null}
              {detail.hasAwakening ? <span class="tag awake">可觉醒</span> : null}
            </div>
          </div>
          <div class="char-header-side">
            <div class="header-actions">
              <a class={"header-btn" + (status.state === "dirty" ? " dirty" : status.changes ? " saved" : "")}
                href={link(id, "changes")} title={status.label}>
                本次修改 <span class="count">{status.changes ?? 0}</span>{status.state === "dirty" ? <span class="dot" title="未保存" /> : null}
              </a>
              <button type="button" class="header-btn" disabled={editing === "clone"} onClick={() => { setEditing("clone"); setPreview(IDLE); }}>克隆为新武器</button>
              <button type="button" class="header-btn" disabled={!detail.enhancement_chain.length || editing === "materials"}
                title={!detail.enhancement_chain.length ? "没有强化商品阶段" : ""}
                onClick={() => { setEditing("materials"); setPreview(IDLE); }}>改强化材料</button>
            </div>
            <span class="char-id mono" title={`魂珠 item ${detail.soulId}`}>{id}</span>
          </div>
        </header>
        <StatusStrip draft={status} checks={changes.flatMap((c) => c.checks)}
          build={(built.list ?? []).find((d) => sameDraft(d, draft.view?.changeset) && draft.view?.status.state === "saved") ?? null}
          device={deviceCell(built.list, draft.view?.changeset?.revision)}
          deviceLink={(name) => link(id, "changes", name)} />
        {detail.changeset ? <Notice>这里显示的是重放了本武器草稿后的候选状态（{(detail.draft_status ?? detail.status).label}）。</Notice> : null}

        {editing === "clone" ? (
          <CloneWizard key={id} weapons={[doc]} source={id} target={cloneTarget} kinds={kinds} soul
            donorNote="母本 = 当前打开的武器；要换母本，在左侧列表里打开另一把。觉醒限制和稀有度覆盖按母本一并复制。"
            onPreview={setPreview} onWritten={() => undefined} onClose={close} />
        ) : null}
        {editing === "materials" ? (
          <MaterialsEditor key={id + (detail.changeset?.revision ?? "")} weapon={doc} target={target} names={names}
            onPreview={setPreview} onWritten={() => load()} onClose={close} />
        ) : null}

        <CurvesBlock detail={detail} />
        <SoulBlock detail={detail} kinds={kinds} />
        <EnhancementBlock detail={detail} />
        <AwakeningBlock detail={detail} />
        <ReferencesBlock detail={detail} />
        {detail.note ? <p class="small muted">{detail.note}</p> : null}
      </div>
      <ChecksPanel title={editing ? "预检" : "草稿检查"} checks={checks}
        state={editing ? (preview.state === "running" ? "running" : undefined) : undefined}
        note={editing
          ? preview.state === "invalid" ? "输入有问题，先改正：" + (preview.note ?? "") : "未执行：还没有改动。改动后会自动预检。"
          : detail.changeset ? "这份草稿没有检查结果。" : "未执行：这把武器还没有草稿。"} />
      {tab === "changes" ? (
        <Drawer title={<>本次修改 · 武器 {id} <span class="small muted">{status.label}</span></>} onClose={() => { location.hash = link(id); }}>
          <ChangesPanel characterId={id} subject={subject} openDelivery={sub ?? null}
            renderChange={(change, actions) => <WeaponChangeItem change={change} {...actions} />}
            emptyText="还没有改动。在详情页「克隆为新武器」或「改强化材料」，预检通过后写入草稿。"
            techNote={<p class="small">武器草稿在 <span class="mono">work/studio-drafts/weapons/{id}/</span>，一份可重放的操作序列（
              <span class="mono">params.requests</span>，每次操作 revision 递增，重放会复核输入哈希）；生成写
              <span class="mono"> work/studio-deliveries/weapons/</span>，变更集 ID <span class="mono">studio-weapon-{id}-&lt;版本&gt;</span>。</p>} />
        </Drawer>
      ) : null}
    </>
  );
}

/** Item names the detail can prove (awakening material rows; item c2 = name) plus the weapon itself. */
function itemNames(detail: WeaponDetail | null): Map<string, string> {
  const names = new Map<string, string>();
  if (!detail) return names;
  const add = (r: BossRecord | null | undefined) => { if (r?.path?.[0] && present(cellOf(r.row, 2))) names.set(r.path[0], cellOf(r.row, 2)); };
  add(detail.awakening?.material);
  detail.awakening?.standardMaterials?.forEach(add);
  names.set(detail.id, detail.name);
  return names;
}

function pointText(p: { level: number | null; hp: number | null; attack: number | null } | null, plus = false): string {
  if (!p) return "—";
  return `Lv${p.level ?? "?"} ${plus ? "+" : ""}HP ${p.hp ?? "?"} / ${plus ? "+" : ""}攻 ${p.attack ?? "?"}`;
}

function CurvesBlock({ detail }: { detail: WeaponDetail }) {
  const { base, enhancement } = detail.curves;
  return (
    <section class="boss-block">
      <header><h3>数值曲线</h3><InfoTip text="基础曲线 = equipment_status（base_status）；强化曲线 = 强化后加成（enhancement_status）。首尾按等级排序。" /></header>
      <dl class="kv">
        <dt>基础（{base.count} 点）</dt><dd>{pointText(base.first)} → {pointText(base.last)}</dd>
        <dt>强化（{enhancement.count} 点）</dt><dd>{enhancement.count ? `${pointText(enhancement.first, true)} → ${pointText(enhancement.last, true)}` : "没有强化曲线"}</dd>
      </dl>
      {detail.base_status.length ? (
        <details class="tech"><summary>完整基础曲线（{detail.base_status.length} 行）</summary>
          <div class="table-scroll">
            <table class="boss-table"><thead><tr><th>等级</th><th>HP</th><th>攻击</th></tr></thead>
              <tbody>{detail.base_status.map((s) => <tr><td>{s.level}</td><td>{cellOf(s.row, 0)}</td><td>{cellOf(s.row, 1)}</td></tr>)}</tbody>
            </table>
          </div>
        </details>
      ) : null}
    </section>
  );
}

function SoulBlock({ detail, kinds }: { detail: WeaponDetail; kinds: ReturnType<typeof useKindNames> }) {
  const item = detail.soul_item;
  const lines = abilityLines(asWeaponDoc(detail));
  return (
    <section class="boss-block">
      <header><h3>魂珠与词条</h3><InfoTip text="魂珠 item 由本体 c10 关联，ID 不一定与武器相同。词条按每行生效的块（瞬时 / 持续）读 kind 与强度。" /></header>
      {item ? (
        <dl class="kv">
          <dt>魂珠</dt><dd>{cellOf(item.row, 2) || "—"} <span class="mono small muted">{item.path?.[0] ?? detail.soulId}</span></dd>
          <dt>可装备属性</dt><dd>{soulElementsText(cellOf(item.row, 12))} <span class="mono small muted">c12 = {cellOf(item.row, 12) || "（空）"}</span></dd>
          <dt>魂珠说明</dt><dd>{cellOf(item.row, 5) || "—"}</dd>
        </dl>
      ) : <Notice kind="warn">找不到关联的魂珠 item（本体 c10 = {detail.soulId || "空"}）。</Notice>}
      {!detail.ability_soul ? <p class="small warn-text">没有能力魂记录。</p> : null}
      {lines.length ? (
        <div class="table-scroll">
          <table class="boss-table">
            <thead><tr><th>词条</th><th>块</th><th>kind</th><th>强度（初始 → 满级）</th></tr></thead>
            <tbody>
              {lines.map((l) => (
                <tr><td>{TABLE_LABEL[l.table]} 第 {l.row + 1} 行</td><td>{BLOCK_LABEL[l.block]}</td>
                  <td><KindName kind={l.kind} block={l.block} kinds={kinds} /></td>
                  <td>{present(l.power1) ? `${l.power1} → ${l.firstMax}` : "—"}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <p class="small muted">没有可读的魂珠 / 强化词条行。</p>}
    </section>
  );
}

function EnhancementBlock({ detail }: { detail: WeaponDetail }) {
  const chain = detail.enhancement_chain;
  return (
    <section class="boss-block">
      <header><h3>强化阶段（{chain.length}）</h3>
        {chain.length ? (detail.reaches_120 ? <span class="state-ok small">可到 120</span> : <span class="warn-text small">强化链到不了 120</span>) : null}</header>
      {!chain.length ? <p class="small muted">没有强化商品阶段。</p> : (
        <>
          <div class="table-scroll">
            <table class="boss-table">
              <thead><tr><th>阶</th><th>商品</th><th>等级区间</th><th>购买次数</th><th>每次材料</th><th>普通货币</th><th>需觉醒</th></tr></thead>
              <tbody>
                {chain.map((s) => (
                  <tr><td class="mono small">{s.stage}</td><td class="mono small">{s.id}</td>
                    <td>{s.startLevel} → {s.maxLevel}</td><td>{s.purchaseCountTo120}</td>
                    <td class="small"><MaterialList costs={s.costs} /></td>
                    <td class="small">{s.userCost ? `${USER_COST[s.userCost.type] ?? "类型 " + s.userCost.type} ×${s.userCost.amount}` : "—"}</td>
                    <td>{s.requireAwakeningLevel}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
          <p class="small">到 120 累计：<MaterialList costs={detail.materials_to_120} />
            {detail.user_costs_to_120.length ? " + " + detail.user_costs_to_120.map((u) => `${USER_COST[u.type] ?? "类型 " + u.type} ×${u.amount}`).join(" + ") : ""}</p>
          <p class="small muted">{detail.material_semantics}</p>
        </>
      )}
    </section>
  );
}

function AwakeningBlock({ detail }: { detail: WeaponDetail }) {
  const a = detail.awakening;
  if (!a) return null;
  const standard = (a.standardMaterials ?? []).filter((r): r is BossRecord => !!r);
  return (
    <section class="boss-block">
      <header><h3>觉醒素材</h3><span class="small muted">最大觉醒等级 {a.maxLevel ?? "—"}</span></header>
      {!a.serverInputAvailable ? <Notice kind="warn">缺少本机服务端觉醒输入：专用材料限制和稀有度覆盖未知（不等于没有）。</Notice> : null}
      <dl class="kv">
        <dt>专用觉醒材料</dt>
        <dd>{a.materialId ? <>{cellOf(a.material?.row, 2) || "（item 表缺行）"} <span class="mono small muted">{a.materialId}</span></> : a.serverInputAvailable ? "无（用通用材料）" : "未知"}</dd>
        <dt>客户端材料文案</dt><dd>{a.clientMaterial ? <span class="mono small">{a.clientMaterial.path?.join("/")}</span> : "—"}</dd>
        <dt>稀有度覆盖</dt><dd class="mono small">{a.rarityOverride === null || a.rarityOverride === undefined ? "—" : JSON.stringify(a.rarityOverride)}</dd>
        <dt>通用觉醒材料</dt>
        <dd>{standard.length ? standard.map((r) => <span>{cellOf(r.row, 2) || r.path?.[0]} <span class="mono small muted">{r.path?.[0]}</span></span>) : "—"}</dd>
      </dl>
      {a.note ? <p class="small muted">{a.note}</p> : null}
    </section>
  );
}

const SHOP_KIND: Record<string, string> = {
  boss_coin: "领主币商店", event_item: "活动道具商店", enhancement: "强化商店", general: "通用商店（含羁绊兑换）",
  star_grain: "星粒商店", treasure: "宝物商店",
};

function ReferencesBlock({ detail }: { detail: WeaponDetail }) {
  const { shops, gacha } = detail.references;
  const missing = Object.entries(detail.referenceCoverage?.serverShops ?? {}).filter(([, ok]) => !ok).map(([k]) => k);
  const group = (r: (typeof shops)[number]) => r.categoryId ? `分类 ${r.categoryId}` : r.eventId ? `活动 ${r.eventType ?? ""}/${r.eventId}` : "";
  return (
    <section class="boss-block">
      <header><h3>引用（商店 {shops.length} · 卡池 {gacha.length}）</h3>
        <InfoTip text="客户端与服务端各自返回证据：同一商品的客户端行、服务端镜像会各算一条，条数不等于去重后的商品数。卡池权重 0 仍是引用，不等于开放获取。" /></header>
      {missing.length ? <p class="small warn-text">以下服务端商店缺输入，没有扫描（不代表没有引用）：<span class="mono">{missing.join("、")}</span></p> : null}
      {detail.referenceCoverage && !detail.referenceCoverage.serverGachaAvailable ? <p class="small warn-text">缺服务端 gacha.json，服务端卡池没有扫描。</p> : null}
      {shops.length ? (
        <div class="table-scroll">
          <table class="boss-table">
            <thead><tr><th>来源</th><th>商店</th><th>商品</th><th>归属</th><th>表 / 文件</th></tr></thead>
            <tbody>
              {shops.map((r) => (
                <tr><td>{r.scope === "client" ? "客户端" : "服务端"}</td><td>{SHOP_KIND[r.kind] ?? r.kind}</td>
                  <td class="mono small">{r.productId}</td><td class="small">{group(r)}</td>
                  <td class="mono small">{r.scope === "server" ? String(r.source ?? "") : r.table ?? ""}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <p class="small muted">已扫描的商店里没有引用这把武器（或它的魂珠）。</p>}
      {gacha.length ? (
        <div class="table-scroll">
          <table class="boss-table">
            <thead><tr><th>来源</th><th>卡池</th><th>ID</th><th>权重 / 分组</th></tr></thead>
            <tbody>
              {gacha.map((g) => (
                <tr><td>{g.scope === "client" ? "客户端" : "服务端"}</td><td>{g.name ?? "—"}</td><td class="mono small">{g.id}{g.oddsId ? ` · ${g.oddsId}` : ""}</td>
                  <td class="small">{g.scope === "client" ? <>权重 {g.weight}{g.weight === "0" ? <span class="warn-text">（0：不会抽到）</span> : null}</> : `分组 ${g.group ?? "—"}`}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <p class="small muted">装备卡池里没有这把武器。</p>}
    </section>
  );
}

function WeaponChangeItem({ change, busy, onRevert }: { change: DraftChange; busy: boolean; onRevert: () => void }) {
  const requests: AnyBossRequest[] = change.params.requests ?? [];
  const warns = change.checks.filter((c) => c.level !== "info");
  const soul = (r: AnyBossRequest) => {
    if (r.operation !== "weapon_clone") return "";
    const e = r.weapon.soul_elements;
    return (e === undefined ? "，魂珠属性沿用母本" : `，魂珠属性 ${e === "all" ? "全属性" : e === "auto" ? "自动" : e.map((x) => WEAPON_ELEMENTS[x]).join("、")}`)
      + (r.weapon.soulDescription ? "，改魂珠说明" : "");
  };
  return (
    <li class="change">
      <header>
        <span class="tag">武器</span>
        <h3>{change.title} · {change.target.weapon}</h3>
        <span class="muted small mono">{change.id} · {change.createdAt.replace("T", " ").slice(0, 19)}</span>
        <span class="spacer" />
        {warns.length ? <span class="pill warnpill">{warns.length} 注意</span> : null}
        <button onClick={onRevert} disabled={busy}>{busy ? "撤销中……" : "撤销整份"}</button>
      </header>
      <ol class="ability-ops small">
        {requests.map((r) => <li>{describeRequest(r)}{soul(r)}</li>)}
      </ol>
      <ChecksList checks={warns} />
    </li>
  );
}
