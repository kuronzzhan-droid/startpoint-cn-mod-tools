import { ComponentChildren } from "preact";
import { useEffect, useState } from "preact/hooks";
import { corridor, ELEMENTS, Json, PoolItem, PoolPage } from "../../corridorApi";
import { Notice } from "../common";
import { Num, Tag, useCorridor } from "./widgets";

const CHAR_TIERS: Record<string, string> = { "1": "普通", "2": "稀有", "3": "传说", "4": "强化传说" };
const WEAPON_TIERS: Record<string, string> = { "1": "普通", "2": "稀有", "3": "史诗", "4": "传说" };

interface Filters { q: string; element: string; tier: string; status: string; page: number }

function query(f: Filters, size = 100) {
  const p = new URLSearchParams({ q: f.q, element: f.element, tier: f.tier, status: f.status, page: String(f.page), size: String(size) });
  return p.toString();
}

function FilterBar({ f, set, tiers, statuses, total, size }: {
  f: Filters; set: (f: Filters) => void; tiers: Record<string, string>; statuses: [string, string][]; total: number; size: number;
}) {
  const pages = Math.max(1, Math.ceil(total / size));
  return (
    <div class="cor-toolbar">
      <input type="search" placeholder="搜 ID / 名称 / code" value={f.q}
        onInput={(e) => set({ ...f, q: (e.currentTarget as HTMLInputElement).value, page: 1 })} />
      <select value={f.element} onChange={(e) => set({ ...f, element: (e.currentTarget as HTMLSelectElement).value, page: 1 })}>
        <option value="">全部属性</option>
        {ELEMENTS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
      </select>
      <select value={f.tier} onChange={(e) => set({ ...f, tier: (e.currentTarget as HTMLSelectElement).value, page: 1 })}>
        <option value="">全部档位</option>
        {Object.entries(tiers).map(([k, l]) => <option key={k} value={k}>T{k} {l}</option>)}
      </select>
      <select value={f.status} onChange={(e) => set({ ...f, status: (e.currentTarget as HTMLSelectElement).value, page: 1 })}>
        <option value="">全部状态</option>
        {statuses.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
      </select>
      <span class="muted small">共 {total} 条</span>
      <button disabled={f.page <= 1} onClick={() => set({ ...f, page: f.page - 1 })}>上一页</button>
      <span class="small">{f.page}/{pages}</span>
      <button disabled={f.page >= pages} onClick={() => set({ ...f, page: f.page + 1 })}>下一页</button>
    </div>
  );
}

function usePool(kind: "characters" | "weapons" | "souls", filters: Filters, size = 100) {
  const { tick, setError } = useCorridor();
  const [data, setData] = useState<PoolPage | null>(null);
  useEffect(() => {
    const load = kind === "characters" ? corridor.characters : kind === "weapons" ? corridor.weapons : corridor.souls;
    load(query(filters, size)).then(setData, (e: Error) => setError(e.message));
  }, [kind, filters.q, filters.element, filters.tier, filters.status, filters.page, tick]);
  return data;
}

function Selectable({ items, selected, setSelected, header, row }: {
  items: PoolItem[]; selected: Set<string>; setSelected: (s: Set<string>) => void;
  header: ComponentChildren; row: (item: PoolItem) => ComponentChildren;
}) {
  const all = items.length > 0 && items.every((i) => selected.has(i.id));
  return (
    <div class="table-wrap" style="max-height:66vh">
      <table class="cor-table">
        <thead>
          <tr>
            <th><input type="checkbox" checked={all} onChange={() => {
              const next = new Set(selected);
              items.forEach((i) => (all ? next.delete(i.id) : next.add(i.id)));
              setSelected(next);
            }} /></th>
            {header}
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id} class={(item.in_pool ? "" : "dim ") + (selected.has(item.id) ? "sel" : "")}>
              <td><input type="checkbox" checked={selected.has(item.id)} onChange={() => {
                const next = new Set(selected);
                if (next.has(item.id)) next.delete(item.id); else next.add(item.id);
                setSelected(next);
              }} /></td>
              {row(item)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function policyTags(p: Record<string, Json>) {
  const keys = Object.keys(p).filter((k) => k !== "notes");
  return (
    <>
      {keys.length ? <Tag kind="warn" title={"编辑层策略（服务端未接入，发布前被 B-014 阻断）：" + keys.join("、")}>候选策略</Tag> : null}
      {p.notes ? <Tag title={String(p.notes)}>备注</Tag> : null}
    </>
  );
}

// ---------------------------------------------------------------- characters
export function CharactersPage() {
  const { run, status } = useCorridor();
  const [f, setF] = useState<Filters>({ q: "", element: "", tier: "", status: "", page: 1 });
  const data = usePool("characters", f);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [reason, setReason] = useState("");
  const [detail, setDetail] = useState<string | null>(null);
  const ids = [...selected];
  const batch = (patch: Record<string, Json>, label: string) =>
    ids.length && run([{ op: "character.set", ids, ...patch }], `${label}（${ids.length} 名）`);
  const bp = data?.boss_playable;
  const rev = status?.workspace?.revision;
  return (
    <div class="cor">
      <div class="cor-grid">
        <div class="cor-card">
          <h3>回廊角色池</h3>
          {data ? (
            <div class="small">
              入池 <b>{String(data.summary.in_pool)}</b> / 主数据 {String(data.summary.total)} ·
              boss 转可玩 {String(data.summary.boss_playable)} · 覆盖 {String(data.summary.overrides)}
              <div>{Object.entries((data.summary.by_tier ?? {}) as Record<string, number>).map(([t, n]) => (
                <Tag key={t}>T{t} {CHAR_TIERS[t]} {n}</Tag>))}</div>
            </div>
          ) : null}
          <p class="muted small">档位覆盖与「移出池」写入服务端 v3f 叠加层 rogue_pool_v3f.json（当前已生效能力）。
            主数据排除的角色只能做候选标记；「可进开局包」= 档位≤传说且非 boss 转可玩。</p>
        </div>
        <div class="cor-card">
          <h3>boss 转可玩（整组）</h3>
          {bp ? (
            <div class="cor-toolbar small">
              <label><input type="checkbox" checked={bp.enabled} onChange={(e) => run([{ op: "rules.set", path: "/v3f/boss_playable/enabled",
                value: (e.currentTarget as HTMLInputElement).checked }], "boss 转可玩开关")} /> 进池</label>
              最早出现幕
              <select value={String(bp.min_act)} onChange={(e) => run([{ op: "rules.set", path: "/v3f/boss_playable/min_act",
                value: Number((e.currentTarget as HTMLSelectElement).value) }], "boss 转可玩最早幕")}>
                {[1, 2, 3].map((a) => <option key={a} value={a}>第 {a} 幕</option>)}
              </select>
              <span class="muted">开局包永远不出现</span>
            </div>
          ) : null}
        </div>
      </div>
      <FilterBar f={f} set={setF} tiers={CHAR_TIERS} total={data?.total ?? 0} size={100}
        statuses={[["in_pool", "入池"], ["excluded", "未入池"], ["boss_playable", "boss 转可玩"], ["override", "有覆盖"],
          ["starter", "可进开局包"], ["policy", "有候选策略"]]} />
      {ids.length ? (
        <div class="cor-card cor-toolbar">
          <b>已选 {ids.length} 名</b>
          <input type="text" placeholder="理由（写进叠加层 reason）" value={reason} onInput={(e) => setReason((e.currentTarget as HTMLInputElement).value)} />
          档位
          {["1", "2", "3", "4"].map((t) => (
            <button key={t} onClick={() => batch({ tier: Number(t), ...(reason ? { reason } : {}) }, `档位→T${t}`)}>T{t}</button>
          ))}
          <button onClick={() => batch({ tier: "source" }, "恢复主数据档位")}>恢复源档</button>
          <button onClick={() => batch({ enabled: false, ...(reason ? { reason } : {}) }, "移出回廊池")}>移出池</button>
          <button onClick={() => batch({ enabled: true }, "放回回廊池")}>放回池</button>
          <span title="单独设置需要服务端能力（候选，发布被阻断）">开局包
            <button onClick={() => batch({ starter_eligible: false }, "候选：禁止开局包")}>禁止</button>
            <button onClick={() => batch({ starter_eligible: null }, "清除开局包候选")}>清除</button></span>
          <span title="单独设置需要服务端能力（候选，发布被阻断）">最早幕
            {[1, 2, 3].map((a) => <button key={a} onClick={() => batch({ min_act: a }, `候选：最早第${a}幕`)}>{a}</button>)}
            <button onClick={() => batch({ min_act: null }, "清除最早幕候选")}>清除</button></span>
          <button class="ghost" onClick={() => setSelected(new Set())}>取消选择</button>
        </div>
      ) : null}
      {data ? (
        <Selectable items={data.items} selected={selected} setSelected={setSelected}
          header={<><th>ID</th><th>名称</th><th>属性</th><th>源档 → 生效</th><th>入池</th><th>开局包</th><th>最早幕</th><th>商店价</th><th>说明</th></>}
          row={(c) => (
            <>
              <td class="mono"><a href="javascript:void 0" onClick={() => setDetail(c.id)}>{c.id}</a></td>
              <td>{c.name}{c.boss_playable ? <Tag kind="info">boss 转可玩</Tag> : null}</td>
              <td>{c.element_name}</td>
              <td>T{c.source_tier ?? "?"}{c.effective_tier && c.effective_tier !== c.source_tier ? <b> → T{c.effective_tier}</b> : null}</td>
              <td>{c.in_pool ? <Tag kind="ok">入池</Tag> : <Tag kind="bad">未入池</Tag>}</td>
              <td>{c.starter_eligible ? "可" : c.starter_derived ? <Tag kind="warn">候选禁止</Tag> : "—"}</td>
              <td>{c.in_pool ? (c.min_act !== c.min_act_derived ? <Tag kind="warn">候选 {String(c.min_act)}</Tag> : c.min_act) : "—"}</td>
              <td>{c.shop_price ?? "—"}</td>
              <td class="small">{c.override_reason ? <span title={c.override_reason}>覆盖：{c.override_reason.slice(0, 24)}</span> : null}
                {!c.in_pool && c.excluded_reason ? <span class="muted">{c.excluded_reason.slice(0, 40)}</span> : null} {policyTags(c.policy)}</td>
            </>
          )} />
      ) : <div class="loading">读取角色池…</div>}
      {detail ? <CharacterDetail id={detail} revision={rev} onClose={() => setDetail(null)} /> : null}
    </div>
  );
}

function CharacterDetail({ id, onClose }: { id: string; revision?: number; onClose: () => void }) {
  const { run, tick } = useCorridor();
  const [data, setData] = useState<{ item: PoolItem; master: Record<string, Json> } | null>(null);
  const [notes, setNotes] = useState("");
  useEffect(() => {
    corridor.character(id).then((d) => { setData(d); setNotes(String(d.item.policy.notes ?? "")); });
  }, [id, tick]);
  if (!data) return null;
  const c = data.item;
  const sp = data.master.starter_profile as Record<string, Json> | null;
  return (
    <div class="cor-card">
      <h3>{c.name}（{c.id}）<button class="ghost" onClick={onClose}>关闭</button></h3>
      <dl class="cor-kv">
        <dt>code / 属性</dt><dd class="mono">{c.code} · {c.element_name}</dd>
        <dt>主数据档位</dt><dd>T{c.source_tier} {String(data.master.tier_reason ?? "")}</dd>
        <dt>生效档位</dt><dd>{c.effective_tier ? `T${c.effective_tier}` : "—"} {c.override_reason ?? ""}</dd>
        <dt>准入检查</dt><dd>{c.pool_check_ok ? "通过" : (c.pool_check_reasons ?? []).join("；")}</dd>
        <dt>首次入池</dt><dd>{c.first_seen ?? "—"}</dd>
        <dt>开局流派评分</dt><dd>{sp ? JSON.stringify(sp.scores ?? {}) + " · " + String(sp.role ?? "") : "—"}</dd>
      </dl>
      <div class="cor-toolbar">
        <input type="text" style="flex:1" placeholder="备注（候选说明，不影响发布）" value={notes}
          onInput={(e) => setNotes((e.currentTarget as HTMLInputElement).value)} />
        <button onClick={() => run([{ op: "character.set", ids: [c.id], notes }], "角色备注")}>保存备注</button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- weapons
export function WeaponsPage() {
  const { run } = useCorridor();
  const [f, setF] = useState<Filters>({ q: "", element: "", tier: "", status: "", page: 1 });
  const data = usePool("weapons", f);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const ids = [...selected];
  const batch = (patch: Record<string, Json>, label: string) => ids.length && run([{ op: "weapon.set", ids, ...patch }], `${label}（${ids.length} 把）`);
  return (
    <div class="cor">
      <Notice kind="warn">当前试验服不读武器覆盖（v3f 叠加层只作用于角色）：这里的入池/档位/最早幕/提取开关只作为候选策略保存，
        非默认值在发布前被 B-014 阻断。属性待定（通用）武器不能当六属性武器入池。</Notice>
      {data ? <div class="small">入池 {String(data.summary.in_pool)} · 属性待定 {String(data.summary.pending)} · 排除 {String(data.summary.excluded)}</div> : null}
      <FilterBar f={f} set={setF} tiers={WEAPON_TIERS} total={data?.total ?? 0} size={100}
        statuses={[["in_pool", "入池"], ["excluded", "未入池"], ["starter", "开局可用"], ["policy", "有候选策略"]]} />
      {ids.length ? (
        <div class="cor-card cor-toolbar">
          <b>已选 {ids.length} 把</b>
          <button onClick={() => batch({ enabled: false }, "候选：移出池")}>移出池</button>
          <button onClick={() => batch({ enabled: null, tier_override: null, min_act: null, soul_extractable: null, starter_eligible: null }, "清除候选策略")}>清除策略</button>
          最早幕 {[1, 2, 3].map((a) => <button key={a} onClick={() => batch({ min_act: a }, `候选：最早第${a}幕`)}>{a}</button>)}
          <button onClick={() => batch({ soul_extractable: false }, "候选：禁止提取魂珠")}>禁提取</button>
          <button class="ghost" onClick={() => setSelected(new Set())}>取消选择</button>
        </div>
      ) : null}
      {data ? (
        <Selectable items={data.items} selected={selected} setSelected={setSelected}
          header={<><th>ID</th><th>名称</th><th>属性</th><th>档位</th><th>等级</th><th>突破</th><th>特殊强化</th><th>魂珠</th><th>状态</th><th>价</th></>}
          row={(w) => (
            <>
              <td class="mono">{w.id}</td><td>{w.name}</td><td>{w.element_name}</td>
              <td>T{w.source_tier} {w.tier_name}</td><td>{w.level_min}–{w.level_max}</td><td>{w.awakening_max}</td><td>{w.enhancement_cap}</td>
              <td>{w.soul_id ? (w.soul_excluded_reason ? <Tag kind="warn" title={w.soul_excluded_reason}>不可提取</Tag> : "可提取") : "—"}</td>
              <td>{w.in_pool ? <Tag kind="ok">入池</Tag> : <Tag kind="bad" title={w.excluded_reason ?? ""}>{w.group === "pending_element" ? "属性待定" : "排除"}</Tag>}
                {policyTags(w.policy)}</td>
              <td>{w.shop_price ?? "—"}</td>
            </>
          )} />
      ) : <div class="loading">读取武器…</div>}
    </div>
  );
}

// ---------------------------------------------------------------- souls
export function SoulsPage() {
  const { run } = useCorridor();
  const [f, setF] = useState<Filters>({ q: "", element: "", tier: "", status: "", page: 1 });
  const data = usePool("souls", f);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const r = (data?.rules ?? {}) as Record<string, number>;
  const ids = [...selected];
  const set = (path: string, value: number, label: string) => run([{ op: "rules.set", path, value }], label);
  return (
    <div class="cor">
      <div class="cor-card">
        <h3>魂珠规则（生效）</h3>
        <div class="cor-fields">
          <div class="cor-field"><span class="label">商店魂珠货架数</span><Num value={r.shop_souls} min={0} max={12} onChange={(v) => set("/shop/souls", Math.round(v), "魂珠货架数")} /></div>
          <div class="cor-field"><span class="label">魂珠价</span><Num value={r.soul_price} min={0} onChange={(v) => set("/shop/soul_price", Math.round(v), "魂珠价")} /></div>
          <div class="cor-field"><span class="label">提取魂珠价</span><Num value={r.extract_soul_price} min={0} onChange={(v) => set("/shop/extract_soul_price", Math.round(v), "提取魂珠价")} /></div>
          <div class="cor-field"><span class="label">精英额外魂珠概率</span><Num value={r.elite_soul_chance} min={0} max={1} step={0.05} onChange={(v) => set("/rewards/elite_soul_chance", v, "精英魂珠概率")} /></div>
          <div class="cor-field"><span class="label">每幕保底自选宝箱</span><span>{String(r.guaranteed_chests_per_act)}（第 5/8 层固定宝箱，服务端固定）</span></div>
        </div>
      </div>
      <Notice kind="warn">魂珠目录来自锁定的 rules_v3_metadata.json；单颗魂珠的禁用/最早幕只作为候选策略保存（服务端未接入，发布被 B-014 阻断）。</Notice>
      <FilterBar f={f} set={setF} tiers={{}} total={data?.total ?? 0} size={100} statuses={[["in_pool", "目录内"], ["excluded", "不可提取"], ["policy", "有候选策略"]]} />
      {ids.length ? (
        <div class="cor-card cor-toolbar">
          <b>已选 {ids.length} 颗</b>
          <button onClick={() => run([{ op: "soul.set", ids, enabled: false }], "候选：禁用魂珠")}>候选禁用</button>
          <button onClick={() => run([{ op: "soul.set", ids, enabled: null, min_act: null }], "清除魂珠策略")}>清除策略</button>
        </div>
      ) : null}
      {data ? (
        <Selectable items={data.items} selected={selected} setSelected={setSelected}
          header={<><th>魂珠 ID</th><th>名称</th><th>属性</th><th>来源武器</th><th>状态</th></>}
          row={(s) => (
            <>
              <td class="mono">{s.id}</td><td>{s.name ?? "—"}</td><td>{s.element_name}</td>
              <td class="mono small">{(s.source_equipment_ids ?? []).join(", ")}</td>
              <td>{s.in_pool ? <Tag kind="ok">目录内</Tag> : <Tag kind="bad" title={s.excluded_reason ?? ""}>不可提取</Tag>} {policyTags(s.policy)}</td>
            </>
          )} />
      ) : <div class="loading">读取魂珠…</div>}
    </div>
  );
}
