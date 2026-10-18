import { useEffect, useMemo, useState } from "preact/hooks";
import { DraftChange, onDraftChange } from "../../api";
import {
  boss, bossDeliveries, BossDoc, BossDraftSummary, bossKey, BossList, BossRead, BossRequest, BossParameters,
  bossSubject, BossTemplates,
} from "../../bossApi";
import { href, Route } from "../../router";
import { ChangesPanel, ChecksList, useDraftOf } from "../Changes";
import { Drawer, ElementBadge, Notice, StatusStrip } from "../common";
import { InfoTip, useDeliveries } from "../Delivery";
import { ChecksPanel } from "./BossChecks";
import { BossParams, PreviewState } from "./BossParams";
import { BossEncounter, BossRewards, HiddenQuests, Src } from "./BossRead";
import {
  fiveTier, MODE_LABEL, QUEST_ELEMENTS, questElement, shortName, useBossDrafts, useBossList,
} from "./bossModel";

const TABS = [
  { id: "encounter", label: "遭遇" },
  { id: "rewards", label: "奖励与商店" },
  { id: "params", label: "调整参数" },
];

const IDLE: PreviewState = { state: "idle", checks: null, ok: false };

export function BossDetail({ quest, tab }: { quest: string; tab?: string }) {
  const [read, setRead] = useState<BossRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { list } = useBossList();
  const drafts = useBossDrafts();
  const [preview, setPreview] = useState<PreviewState>(IDLE);
  const [templates, setTemplates] = useState<BossTemplates | null>(null);
  const drawer = tab === "changes";
  const [lastTab, setLastTab] = useState("encounter");
  const active = drawer ? lastTab : TABS.some((t) => t.id === tab) ? tab! : "encounter";
  useEffect(() => { if (!drawer) setLastTab(active); }, [active, drawer]);
  useEffect(() => { boss.templates().then(setTemplates, () => setTemplates(null)); }, []);

  const load = () => boss.read(quest).then((r) => { setRead(r); setError(null); }, (e: Error) => setError(e.message));
  useEffect(() => { setRead(null); setError(null); setPreview(IDLE); load(); }, [quest]);
  const questId = read?.questId ?? quest;
  useEffect(() => onDraftChange((key) => { if (key === bossKey(questId)) load(); }), [questId]);
  const subject = useMemo(() => bossSubject(questId), [questId]);
  const draft = useDraftOf(subject);
  const built = useDeliveries(questId, bossDeliveries);
  const link = (t?: string): Route => ({ work: "content", shop: "boss", quest, tab: t });

  if (error) return <section class="page"><BackLink /><Notice kind="error">读取副本失败：{error}</Notice></section>;
  if (!read) return <section class="page"><BackLink /><div class="loading">正在读取副本 {quest}……</div></section>;

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
  const checks = active === "params" ? preview.checks : read.checks.length ? read.checks : null;

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
        build={(built.list ?? []).find((d) => draft.view?.changeset && d.draftRevision === draft.view.changeset.revision
          && draft.view.status.state === "saved") ?? null} />
      <nav class="tabs" role="tablist" aria-label="副本内容">
        {TABS.map((t) => (
          <a role="tab" aria-selected={active === t.id} class={active === t.id ? "active" : ""} href={href(link(t.id))}>
            {t.label}{t.id === "params" && doc.routing.kind === "BothBoss" ? <span class="count">只读</span> : null}
          </a>
        ))}
      </nav>
      <div class="boss-layout">
        <SiblingNav doc={doc} list={list} drafts={drafts} tab={active} />
        <div class="boss-main">
          {doc.routing.kind === "BothBoss" && active !== "params" ? (
            <Notice kind="warn">这是五重决战的<strong>入口</strong>（BothBoss 路由），只读：它按两轮选择把玩家送进隐藏关，自己不是战斗内容，也不能作新建共同决战的模板。</Notice>
          ) : null}
          {doc.routing.kind === "BothBoss" && active === "encounter" ? <HiddenQuests doc={doc} /> : null}
          {active === "encounter" ? <BossEncounter doc={doc} /> : active === "rewards" ? <BossRewards doc={doc} /> : null}
          {/* Kept mounted so unwritten edits survive a look at 遭遇 / 奖励. */}
          <div class="boss-params-host" hidden={active !== "params"}>
            <BossParams doc={doc} questId={read.questId} list={list} drafts={drafts} onPreview={setPreview}
              onWritten={(written) => { if (written === read.questId) load(); }} />
          </div>
        </div>
        <ChecksPanel
          title={active === "params" ? "预检" : "草稿检查"}
          checks={checks}
          state={active === "params" ? (preview.state === "running" ? "running" : undefined) : undefined}
          note={active === "params"
            ? doc.routing.kind === "BothBoss" ? "入口只读，不做预检。" : preview.state === "invalid" ? "输入有问题，先改正：" + (preview.note ?? "") : "未执行：还没有改动。改了数值会自动预检。"
            : changes.length ? "这份草稿没有检查结果。" : "未执行：这一关还没有草稿。到「调整参数」改动后会自动预检。"}>
          {active !== "params" && read.checks.length ? <p class="small muted">按当前视图重放草稿得到的结果。</p> : null}
        </ChecksPanel>
      </div>
      {drawer ? (
        <Drawer title={<>本次修改 <span class="small muted">{status?.label}</span></>} onClose={closeDrawer}>
          <ChangesPanel characterId={questId} subject={subject}
            renderChange={(change, actions) => <BossChangeItem change={change} {...actions} />}
            emptyText="还没有改动。到「调整参数」改等级、倍率、属性、BGM 或场景，预检通过后写入草稿。"
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
  if (p.hpMultiplier !== undefined) out.push(`HP ×${p.hpMultiplier}`);
  if (p.attackMultiplier !== undefined) out.push(`攻击 ×${p.attackMultiplier}`);
  if (p.recommendedElement !== undefined) out.push(`副本属性 ${QUEST_ELEMENTS[p.recommendedElement] ?? p.recommendedElement}`);
  if (p.restrictedElement !== undefined) out.push(p.restrictedElement === null ? "出战不限定" : `出战限定 ${QUEST_ELEMENTS[p.restrictedElement]}`);
  if (p.bgm !== undefined) out.push(`BGM ${p.bgm}`);
  if (p.scene !== undefined) out.push(`场景 ${p.scene}`);
  return out;
}

export function describeRequest(r: BossRequest): string {
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
  const requests: BossRequest[] = change.params.requests ?? [];
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
          <li>{describeRequest(r)}{r.acknowledgePreload ? <span class="tag warn-text" title="显式接受未证明的预载风险（C8016），只豁免「待验证」"> 已确认预载风险</span> : null}</li>
        ))}
      </ol>
      <ChecksList checks={warns} />
      {infos ? <p class="small muted">另有 {infos} 条规则满足或不适用。<InfoTip text="写入时的规则快照；生成时按当前视图重放再检查一次。" /></p> : null}
    </li>
  );
}
