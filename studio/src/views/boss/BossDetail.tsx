import { useEffect, useMemo, useRef, useState } from "preact/hooks";
import { ComponentChildren } from "preact";
import { DraftChange, onDraftChange } from "../../api";
import {
  AnyBossRequest, boss, bossDeliveries, BossDoc, BossDraftSummary, bossKey, BossList, BossOptions, BossRead, BossRequest, BossParameters,
  bossSubject, BossTemplates,
} from "../../bossApi";
import { href, Route } from "../../router";
import { ChangesPanel, ChecksList, useDraftOf } from "../Changes";
import { Drawer, ElementBadge, Notice, StatusStrip } from "../common";
import { Loading } from "../Loading";
import { InfoTip, useDeliveries } from "../Delivery";
import { deviceCell, sameDraft } from "../DeviceResult";
import { ChecksPanel } from "./BossChecks";
import { BossParams, PreviewState } from "./BossParams";
import { BossEncounter, BossRewards, HiddenQuests, Src } from "./BossRead";
import { BossBehavior } from "./BossBehavior";
import { revisionKey } from "./bossOps";
import { BossShopWeapons } from "./BossShopWeapons";
import { BossTerrain } from "./BossTerrain";
import {
  fiveTier, MODE_LABEL, QUEST_ELEMENTS, questElement, shortName, useBossDrafts, useBossList,
} from "./bossModel";

const TABS = [
  { id: "encounter", label: "遭遇" },
  { id: "terrain", label: "地形" },
  { id: "rewards", label: "奖励" },
  { id: "shop", label: "商店与武器" },
  { id: "behavior", label: "行为" },
  { id: "params", label: "调整参数" },
];
/** Tabs that edit (right column = live preview of that tab's current operation). */
const EDIT_TABS = new Set(["terrain", "shop", "behavior", "params"]);
/** Old links (出招预览) land on 行为, where every move has its own 「预览」. */
const TAB_ALIAS: Record<string, string> = { moves: "behavior" };

const IDLE: PreviewState = { state: "idle", checks: null, ok: false };

export function BossDetail({ quest, tab, sub }: { quest: string; tab?: string; sub?: string }) {
  const [read, setRead] = useState<BossRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { list } = useBossList();
  const drafts = useBossDrafts();
  const [previews, setPreviews] = useState<Record<string, PreviewState>>({});
  const [templates, setTemplates] = useState<BossTemplates | null>(null);
  const [options, setOptions] = useState<BossOptions | null>(null);
  const drawer = tab === "changes";
  const [lastTab, setLastTab] = useState("encounter");
  const wanted = tab && TAB_ALIAS[tab] ? TAB_ALIAS[tab] : tab;
  const active = drawer ? lastTab : TABS.some((t) => t.id === wanted) ? wanted! : "encounter";
  // Edit tabs stay mounted once opened so an unwritten edit survives a look at another tab.
  const [visited, setVisited] = useState<Set<string>>(new Set());
  useEffect(() => { if (!drawer) setLastTab(active); setVisited((v) => (v.has(active) ? v : new Set([...v, active]))); }, [active, drawer]);
  useEffect(() => { boss.templates().then(setTemplates, () => setTemplates(null)); }, []);
  useEffect(() => { boss.options().then(setOptions, () => setOptions(null)); }, []);
  const previewFor = (id: string) => (state: PreviewState) => setPreviews((p) => ({ ...p, [id]: state }));

  const request = useRef(0);
  const controller = useRef<AbortController>();
  const load = () => {
    const sequence = ++request.current;
    controller.current?.abort();
    controller.current = new AbortController();
    return boss.read(quest, controller.current.signal).then(
      (r) => { if (sequence === request.current) { setRead(r); setError(null); } },
      (e: Error) => { if (sequence === request.current) setError(e.message); },
    );
  };
  useEffect(() => {
    setRead(null); setError(null); setPreviews({}); setVisited(new Set()); load();
    return () => { request.current++; controller.current?.abort(); };
  }, [quest]);
  const questId = read?.questId ?? quest;
  useEffect(() => onDraftChange((key) => { if (key === bossKey(questId)) load(); }), [questId]);
  const subject = useMemo(() => bossSubject(questId), [questId]);
  const draft = useDraftOf(subject);
  const built = useDeliveries(questId, bossDeliveries);
  const link = (t?: string): Route => ({ work: "content", shop: "boss", quest, tab: t });

  if (error) return <section class="page"><BackLink /><Notice kind="error">读取副本失败：{error}</Notice></section>;
  if (!read) return <section class="page"><BackLink /><Loading label={`正在读取副本 ${quest}……`} /></section>;

  const doc = read.boss;
  const q = doc.quest;
  const element = questElement(q.fields.recommended_element);
  const item = list?.items.find((i) => i.selector === q.selector);
  const mode = item?.mode ?? (q.kind === "hard_multi" ? "shared" : q.kind === "practice" ? "practice" : "lord");
  const isNew = !item;
  const status = draft.view?.status;
  const templateOk = templates?.sources.some((s) => s.selector === q.selector);
  const closeDrawer = () => { location.hash = href(link(active)); };
  const leaf = q.path[q.path.length - 1];
  const tiered = q.kind === "boss_battle" && fiveTier((list?.items ?? []).filter((i) => i.kind === q.kind && i.group === q.group));
  const changes = draft.view?.changeset?.changes ?? [];
  const editing = EDIT_TABS.has(active);
  const preview = previews[active] ?? IDLE;
  const checks = editing ? preview.checks : read.checks.length ? read.checks : null;
  const rev = revisionKey(read.changeset);
  const written = () => load();
  const host = (id: string, body: () => ComponentChildren) => (visited.has(id) || active === id
    ? <div class="boss-tab-host" hidden={active !== id}>{body()}</div> : null);

  return (
    <section class="page detail boss-detail-page">
      <BackLink />
      <header class="char-header boss-header">
        <ElementBadge element={element ?? "—"} />
        <div class="char-header-main">
          <h1>{shortName(q.name)}</h1>
          <div class="muted">
            {isNew ? "新建共同决战（本地草稿）" : MODE_LABEL[mode]} · {q.kind === "boss_battle" ? (tiered ? `第 ${leaf} 档` : `难度 ${leaf}`) : q.kind === "hard_multi" ? `活动 ${q.path[0]}` : `练习关 ${q.id}`}
            {" "}· Lv{q.fields.level}{element ? ` · ${element}属性` : ""}
            {doc.routing.kind === "BothBoss" ? " · 入口只读" : ""}
          </div>
        </div>
        <div class="char-header-side">
          <div class="header-actions">
            <a class={"header-btn" + (status?.state === "dirty" ? " dirty" : status?.changes ? " saved" : "")}
              href={href(link("changes"))} title={status?.label ?? "无草稿改动"}>
              本次修改 <span class="count">{status?.changes ?? 0}</span>{status?.state === "dirty" ? <span class="dot" title="未保存" /> : null}
            </a>
            {templateOk ? (
              <a class="header-btn" href={href({ work: "content", shop: "boss", wizard: true, source: q.selector })}
                title="以这一关的场景、敌人和 BGM 为模板新建一个共同决战">用它新建共同决战</a>
            ) : null}
          </div>
          <span class="char-meta">
            <Src c={q.source} />
            <span class="char-id" title={`quest ID ${q.id}；选择器 ${q.selector}`}>{q.selector}</span>
          </span>
        </div>
      </header>
      <StatusStrip draft={status ?? null} checks={changes.flatMap((c) => c.checks)}
        build={(built.list ?? []).find((d) => sameDraft(d, draft.view?.changeset) && draft.view?.status.state === "saved") ?? null}
        device={deviceCell(built.list, draft.view?.changeset?.revision)}
        deviceLink={(name) => href({ work: "content", shop: "boss", quest, tab: "changes", sub: name })} />
      <nav class="tabs" role="tablist" aria-label="副本内容">
        {TABS.map((t) => (
          <a role="tab" aria-selected={active === t.id} class={active === t.id ? "active" : ""} href={href(link(t.id))}>
            {t.label}{EDIT_TABS.has(t.id) && doc.routing.kind === "BothBoss" ? <span class="count">只读</span> : null}
          </a>
        ))}
      </nav>
      {mode === "five" ? <a class="header-btn" href={href({ work: "content", shop: "boss", quest: "five-structure" })}>结构 · 五重轮次与词缀</a> : null}
      <div class="boss-layout">
        <SiblingNav doc={doc} list={list} drafts={drafts} tab={active} />
        <div class="boss-main">
          {doc.routing.kind === "BothBoss" && !editing ? (
            <Notice kind="warn">这是五重决战的<strong>入口</strong>（BothBoss 路由），只读：它按两轮选择把玩家送进隐藏关，自己不是战斗内容，也不能作新建共同决战的模板。</Notice>
          ) : null}
          {doc.routing.kind === "BothBoss" && active === "encounter" ? <HiddenQuests doc={doc} /> : null}
          {active === "encounter" ? <BossEncounter doc={doc} /> : active === "rewards" ? <BossRewards doc={doc} /> : null}
          {host("terrain", () => <BossTerrain doc={doc} questId={read.questId} rev={rev} list={list} options={options}
            onPreview={previewFor("terrain")} onWritten={written} />)}
          {host("shop", () => <BossShopWeapons doc={doc} questId={read.questId} rev={rev} onPreview={previewFor("shop")} onWritten={written} />)}
          {host("behavior", () => <BossBehavior doc={doc} questId={read.questId} rev={rev} onPreview={previewFor("behavior")} onWritten={written} />)}
          {/* Kept mounted so unwritten edits survive a look at 遭遇 / 奖励. */}
          <div class="boss-params-host" hidden={active !== "params"}>
            <BossParams doc={doc} questId={read.questId} list={list} drafts={drafts} onPreview={previewFor("params")}
              onWritten={(w) => { if (w === read.questId) load(); }} />
          </div>
        </div>
        <ChecksPanel
          title={editing ? "预检" : "草稿检查"}
          checks={checks}
          state={editing ? (preview.state === "running" ? "running" : undefined) : undefined}
          note={editing
            ? doc.routing.kind === "BothBoss" ? "入口只读，不做预检。" : preview.state === "invalid" ? "输入有问题，先改正：" + (preview.note ?? "") : "未执行：还没有改动。改动后会自动预检。"
            : changes.length ? "这份草稿没有检查结果。" : "未执行：这一关还没有草稿。到地形、商店与武器、行为或调整参数改动后会自动预检。"}>
          {!editing && read.checks.length ? <p class="small muted">按当前视图重放草稿得到的结果。</p> : null}
        </ChecksPanel>
      </div>
      {drawer ? (
        <Drawer title={<>本次修改 <span class="small muted">{status?.label}</span></>} onClose={closeDrawer}>
          <ChangesPanel characterId={questId} subject={subject} openDelivery={sub ?? null}
            renderChange={(change, actions) => <BossChangeItem change={change} {...actions} />}
            emptyText="还没有改动。到「地形」「商店与武器」「行为」或「调整参数」改动，预检通过后写入草稿。"
            techNote={<p class="small">副本草稿在 <span class="mono">work/studio-drafts/boss/</span>，每个副本一份可重放的操作序列（
              <span class="mono">params.requests</span>）；生成写 <span class="mono">work/studio-deliveries/boss/</span>。
              agent 可用 <span class="mono">python -m wf.studio.draft … boss {questId}</span> 走同一套操作。</p>} />
        </Drawer>
      ) : null}
    </section>
  );
}

function BackLink() {
  return <a class="back" href={href({ work: "content", shop: "boss" })}>← 全部副本</a>;
}

function SiblingNav({ doc, list, drafts, tab }: {
  doc: BossDoc; list: BossList | null; drafts: BossDraftSummary[] | null; tab: string;
}) {
  const q = doc.quest;
  const items = (list?.items ?? []).filter((i) => i.kind === q.kind && i.group === q.group);
  const draftIds = new Set((drafts ?? []).map((d) => d.characterId));
  const five = fiveTier(items);
  const linkTo = (selector: string) => href({ work: "content", shop: "boss", quest: selector, tab: tab === "encounter" ? undefined : tab });
  const title = q.kind === "boss_battle" ? (five ? "五档" : q.path[1] === "99" ? "五重决战" : "同节点难度")
    : q.kind === "hard_multi" ? "共同决战" : "同目录练习关";
  const entries = items.length ? items : [{ selector: q.selector, id: q.id, name: q.name, level: String(q.fields.level), path: q.path, recommendedElement: q.fields.recommended_element, hidden: false, bothBoss: false } as any];
  return (
    <nav class="boss-side" aria-label="同组副本">
      <h4>{title} <span class="count">{entries.length}</span></h4>
      <ul>
        {entries.map((i) => {
          const leaf = i.path[i.path.length - 1];
          const label = q.kind === "boss_battle"
            ? (q.path[1] === "99" ? shortName(i.name).replace(/^五重决战·?/, "") || "入口" : five ? `第 ${leaf} 档` : `难度 ${leaf}`)
            : q.kind === "hard_multi" ? `活动 ${i.path[0]}` : shortName(i.name);
          const el = questElement(i.recommendedElement);
          const on = i.selector === q.selector;
          return (
            <li>
              <a class={on ? "on" : ""} aria-current={on ? "page" : undefined} href={linkTo(i.selector)} title={`${i.name} · ${i.selector}`}>
                <span class="side-label">{i.bothBoss ? "入口（只读）" : label}</span>
                <span class="small muted">Lv{i.level}{el ? " · " + el : ""}</span>
                {draftIds.has(i.selector) || draftIds.has(i.id) ? <span class="dot" title="有草稿" /> : null}
              </a>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

function paramText(p: BossParameters): string[] {
  const out: string[] = [];
  if (p.level !== undefined) out.push(`等级 ${p.level}`);
  if (p.hpScale !== undefined) out.push(`HP 当前系数乘以 ${p.hpScale}`);
  if (p.attackScale !== undefined) out.push(`攻击当前系数乘以 ${p.attackScale}`);
  if (p.hpValue !== undefined) out.push(`HP 系数设为 ${p.hpValue}`);
  if (p.attackValue !== undefined) out.push(`攻击系数设为 ${p.attackValue}`);
  if (p.hpMultiplier !== undefined) out.push(`HP 系数设为 ${p.hpMultiplier}（旧字段已弃用）`);
  if (p.attackMultiplier !== undefined) out.push(`攻击系数设为 ${p.attackMultiplier}（旧字段已弃用）`);
  if (p.recommendedElement !== undefined) out.push(`副本属性 ${QUEST_ELEMENTS[p.recommendedElement] ?? p.recommendedElement}`);
  if (p.restrictedElement !== undefined) out.push(p.restrictedElement === null ? "出战不限定" : `出战限定 ${QUEST_ELEMENTS[p.restrictedElement]}`);
  if (p.bgm !== undefined) out.push(`BGM ${p.bgm}`);
  if (p.scene !== undefined) out.push(`场景 ${p.scene}`);
  return out;
}

export function describeRequest(request: AnyBossRequest): string {
  const x = request as any;
  switch (request.operation) {
    case "terrain_replace": return `换地形 → ${x.terrain}`;
    case "terrain_position": return `${x.action === "add" ? "新增" : x.action === "delete" ? "删除" : "移动"}站位 ${x.name}（第 ${Number(x.layer) + 1} 波${x.x !== undefined ? `，左上角 ${x.x}, ${x.y}` : ""}）`;
    case "terrain_add_layer": return `追加一波 ← ${x.sourceQuest} 层 ${x.sourceLayer}${x.transitionSourceQuest ? `（出口来自 ${x.transitionSourceQuest}）` : ""}`;
    case "shop_add": return `新增商品 ← ${x.shop.sourceProduct}（分类 ${x.shop.category}${x.shop.productId ? `，ID ${x.shop.productId}` : ""}）`;
    case "shop_edit": return `改商品 ${x.shop.productId}：${[x.shop.price ? "价格 " + x.shop.price.map((c: any) => `${c.itemId}×${c.amount}`).join("+") : "", x.shop.stock !== undefined ? `库存 ${x.shop.stock}` : "", x.shop.name ? `名称 ${x.shop.name}` : ""].filter(Boolean).join("，")}`;
    case "shop_delete": return `下架商品 ${x.shop.productId}（分类 ${x.shop.category}）`;
    case "weapon_clone": return `克隆武器 ${x.weapon.sourceWeapon} → ${x.weapon.id ?? "（待分配）"}${x.weapon.name ? `「${x.weapon.name}」` : ""}`
      + `${x.weapon.hpMultiplier ? ` HP×${x.weapon.hpMultiplier}` : ""}${x.weapon.attackMultiplier ? ` 攻×${x.weapon.attackMultiplier}` : ""}`
      + `${x.weapon.abilities?.length ? ` 词条改 ${x.weapon.abilities.length} 处` : ""}${x.weapon.enhancementProducts?.length ? `，强化商品 ${x.weapon.enhancementProducts.join("/")}` : ""}`;
    case "weapon_materials": return `改强化材料 ${x.weapon.id}：${x.weapon.stages.map((s: any) => `${s.productId} ${s.costs.map((c: any) => `${c.itemId}×${c.amount}`).join("+")}${s.userCost ? ` 羁绊证×${s.userCost.amount}` : s.userCost === null ? " 不收羁绊证" : ""}`).join("；")}`;
    case "behavior_replace": return `${x.enemyCode} 槽 ${x.slot} 换成 ${x.sourceEnemyCode === x.enemyCode ? "" : x.sourceEnemyCode + " 的"}槽 ${x.sourceSlot}`;
    case "behavior_parameters": return `${x.enemyCode} ${x.damageMultiplier !== undefined ? `槽 ${x.slot} 伤害 ×${x.damageMultiplier}` : ""}`
      + `${x.intervalFrames !== undefined ? `状态 ${x.state}${x.form !== undefined ? `（形态 ${x.form}）` : ""} 间隔 ${x.intervalFrames} 帧` : ""}`
      + `${x.trialThreshold !== undefined ? `状态 ${x.state}${x.form !== undefined ? `（形态 ${x.form}）` : ""} 试炼阈值 ${x.trialThreshold}` : ""}`;
    default: return describeLegacy(request as BossRequest);
  }
}

function describeLegacy(r: BossRequest): string {
  if (r.operation === "create_shared") {
    const ids = (r as BossRequest & { ids?: { event: string; node: string } }).ids;
    return `新建共同决战「${r.name ?? "沿用来源名"}」← 模板来源 ${r.sourceQuest ?? "hard_multi:1006/1"}`
      + (ids ? `（活动 ${ids.event}，目录节点 ${ids.node}）` : "")
      + (r.parameters ? "：" + paramText(r.parameters).join("，") : "");
  }
  const parts: string[] = [];
  if (r.parameters) parts.push(paramText(r.parameters).join("，"));
  if (r.tiers) parts.push(r.tiers.map((t, i) => {
    const text = paramText(t);
    return text.length ? `第 ${i + 1} 档 ${text.join("、")}` : "";
  }).filter(Boolean).join("；"));
  return (r.tiers ? "五档：" : "改参数：") + (parts.filter(Boolean).join("；") || "（无）");
}

function BossChangeItem({ change, busy, onRevert }: { change: DraftChange; busy: boolean; onRevert: () => void }) {
  const requests: AnyBossRequest[] = change.params.requests ?? [];
  const warns = change.checks.filter((c) => c.level !== "info");
  const infos = change.checks.length - warns.length;
  return (
    <li class="change">
      <header>
        <span class="tag">副本</span>
        <h3>{change.title} · {change.target.quest}</h3>
        <span class="muted small mono">{change.id} · {change.createdAt.replace("T", " ").slice(0, 19)}</span>
        <span class="spacer" />
        {warns.length ? <span class="pill warnpill">{warns.length} 注意</span> : null}
        <button onClick={onRevert} disabled={busy}>{busy ? "撤销中……" : "撤销整份"}</button>
      </header>
      <ol class="ability-ops small">
        {requests.map((r) => (
          <li>{describeRequest(r)}{(r as BossRequest).acknowledgePreload ? <span class="tag warn-text" title="显式接受未证明的预载风险（C8016），只豁免「待验证」"> 已确认预载风险</span> : null}</li>
        ))}
      </ol>
      <ChecksList checks={warns} />
      {infos ? <p class="small muted">另有 {infos} 条规则满足或不适用。<InfoTip text="写入时的规则快照；生成时按当前视图重放再检查一次。" /></p> : null}
    </li>
  );
}
