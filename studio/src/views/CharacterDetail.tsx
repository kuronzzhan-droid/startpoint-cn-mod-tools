import { useEffect, useState } from "preact/hooks";
import { AbilityGroup, AbilityRow, api, CharacterDetail, ColumnLabel } from "../api";
import { href, Route } from "../router";
import { Avatar, Drawer, ElementBadge, Notice, OriginBadge, Rarity, StatusStrip } from "./common";
import { AssetsTab } from "./AssetsTab";
import { ChangesPanel, useDraft } from "./Changes";
import { PixelGroup, PixelSub } from "./PixelGroup";
import { PortraitEditor } from "./PortraitEditor";
import { VoiceTab } from "./VoiceTab";
import { InfoTip, useDeliveries } from "./Delivery";
import { AbilityProvider, KeyEditor, PendingBar, useAbilityWorkspace, useWorkspace } from "./AbilityEditor";
import { pendingCount } from "./abilityModel";
import { AttachControl, SkillTiers, slotOf } from "./KeyTools";
import { TextTab } from "./TextTab";
import { CharacterProfileBadge, ProgramCapChip } from "./ClientProfile";
import { SkillPreview } from "./TimelinePreview";

// Seven groups (C1): 能力（一板/二板/三板）｜技能｜文案｜立绘｜像素（预览/单动作替换/工坊/整族导入）｜语音;
// 本次修改 and 资源 open as header drawers.
const GROUPS: { id: string; label: string; ability?: boolean }[] = [
  { id: "ability", label: "能力", ability: true },
  { id: "skill", label: "技能", ability: true },
  { id: "text", label: "文案", ability: true },
  { id: "portrait", label: "立绘" },
  { id: "pixel", label: "像素" },
  { id: "voice", label: "语音" },
];
const BOARDS = [{ id: "board1", label: "一板" }, { id: "board2", label: "二板" }, { id: "board3", label: "三板（觉醒）" }];
// Old deep links keep working.
const LEGACY: Record<string, [string, string?]> = {
  board1: ["ability", "board1"], board2: ["ability", "board2"], board3: ["ability", "board3"],
  "pixel-import": ["pixel", "replace"], workshop: ["pixel", "breakdown"],
};

export function CharacterDetailView({ id, tab, sub }: { id: string; tab?: string; sub?: string }) {
  const [detail, setDetail] = useState<CharacterDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const drawer = tab === "changes" || tab === "assets" ? tab : null;
  const [lastGroup, setLastGroup] = useState<[string, string?]>(["ability"]);
  const [group, groupSub] = drawer ? lastGroup
    : GROUPS.some((g) => g.id === tab) ? [tab!, sub] : LEGACY[tab ?? ""] ?? ["ability"];
  useEffect(() => { if (!drawer) setLastGroup([group, groupSub]); }, [group, groupSub, drawer]);
  const draft = useDraft(id);
  const workspace = useAbilityWorkspace(id, GROUPS.find((g) => g.id === group)?.ability ?? false);
  const built = useDeliveries(id);
  const link = (g: string, s?: string): Route => ({ work: "content", shop: "characters", id, tab: g, sub: s });

  useEffect(() => {
    setDetail(null);
    setError(null);
    api.character(id).then(setDetail, (e: Error) => setError(e.message));
  }, [id]);

  if (error) return <section class="page"><BackLink /><Notice kind="error">读取角色失败：{error}</Notice></section>;
  if (!detail) return <section class="page"><BackLink /><div class="loading">正在读取角色 {id}……</div></section>;

  const awakeCount = detail.boards.find((b) => b.id === "board3")?.slots.length ?? 0;
  const status = draft.view?.status;
  const unwritten = pendingCount(workspace.pending);
  const isAbilityGroup = GROUPS.find((g) => g.id === group)?.ability ?? false;
  const closeDrawer = () => { location.hash = href(link(group, groupSub)); };

  return (
    <AbilityProvider value={workspace}>
    <section class="page detail">
      <BackLink />
      <header class="char-header">
        <Avatar id={detail.id} element={detail.element} size={64} />
        <div class="char-header-main">
          <h1>
            <ElementBadge element={detail.element} />
            {detail.name}
            <Rarity value={detail.rarity} />
          </h1>
          <div class="muted">
            {detail.title || "（无称号）"} · {detail.type} · {detail.role}
            {detail.races.length ? " · " + detail.races.join("、") : ""}
          </div>
        </div>
        <div class="char-header-side">
          <div class="header-actions">
            <a class={"header-btn" + (status?.state === "dirty" ? " dirty" : status?.changes ? " saved" : "")}
              href={href(link("changes"))} title={status?.label ?? "无草稿改动"}>
              本次修改 <span class="count">{status?.changes ?? 0}</span>{status?.state === "dirty" ? <span class="dot" title="未保存" /> : null}
            </a>
            <a class="header-btn" href={href(link("assets"))} title="这个角色的全部资源文件（立绘、小人、语音、特效……）">资源</a>
          </div>
          <span class="char-meta"><CharacterProfileBadge cid={detail.id} /> <OriginBadge origin={detail.origin} /> <span class="char-id" title={"代码名 " + detail.code}>ID {detail.id}</span></span>
        </div>
      </header>
      <StatusStrip draft={draft.view?.status ?? null} checks={draft.view?.changeset?.changes.flatMap((c) => c.checks) ?? []}
        build={(built.list ?? []).find((d) => draft.view?.changeset && d.draftRevision === draft.view.changeset.revision
          && draft.view.status.state === "saved") ?? null} />
      <nav class="tabs" role="tablist" aria-label="角色内容">
        {GROUPS.map((g) => (
          <a role="tab" aria-selected={group === g.id} class={group === g.id ? "active" : ""} href={href(link(g.id))}>
            {g.label}
            {g.ability && unwritten && !isAbilityGroup && g.id === "ability" ? <span class="count dirty" title="词条有未写入的修改">{unwritten}</span> : null}
          </a>
        ))}
      </nav>
      {!isAbilityGroup && unwritten ? (
        <p class="small warn-text">词条/文案有 {unwritten} 项未写入：回到 <a href={href(link("ability"))}>能力</a>、技能或文案页写入或放弃。</p>
      ) : null}
      {group === "ability" ? (
        <AbilityGroupPage detail={detail} sub={groupSub} awakeCount={awakeCount} link={(s) => link("ability", s)} />
      ) : group === "skill" ? (
        <SkillGroupPage detail={detail} sub={groupSub} link={(s) => link("skill", s)}
          onText={() => { location.hash = href(link("text")); }} />
      ) : group === "text" ? (
        <TextTab characterId={detail.id} />
      ) : group === "portrait" ? (
        <PortraitEditor characterId={detail.id} />
      ) : group === "pixel" ? (
        <PixelGroup characterId={detail.id} sub={groupSub} link={(s: PixelSub) => link("pixel", s)} />
      ) : (
        <VoiceTab characterId={detail.id} />
      )}
      {isAbilityGroup ? <PendingBar /> : null}
      {drawer === "changes" ? (
        <Drawer title={<>本次修改 <span class="small muted">{status?.label}</span></>} onClose={closeDrawer}>
          <ChangesPanel characterId={detail.id} />
        </Drawer>
      ) : drawer === "assets" ? (
        <Drawer title="全部资源" wide onClose={closeDrawer}>
          <AssetsTab characterId={detail.id} />
        </Drawer>
      ) : null}
    </section>
    </AbilityProvider>
  );
}

function BackLink() {
  return <a class="back" href={href({ work: "content", shop: "characters" })}>← 查找其他角色</a>;
}

function AbilityGroupPage({ detail, sub, awakeCount, link }: {
  detail: CharacterDetail; sub?: string; awakeCount: number; link: (sub: string) => Route;
}) {
  const active = BOARDS.some((b) => b.id === sub) ? sub! : "board1";
  return (
    <div class="group-page">
      <nav class="subnav" aria-label="能力">
        {BOARDS.map((b) => {
          const empty = b.id === "board3" && awakeCount === 0;
          return (
            <a class={(active === b.id ? "on" : "") + (empty ? " empty" : "")} href={href(link(b.id))}
              title={empty ? "这个角色没有觉醒替换/追加的能力行" : undefined} aria-disabled={empty || undefined}>
              {b.label}{b.id === "board3" ? <span class="count">{awakeCount}</span> : null}
            </a>
          );
        })}
      </nav>
      <BoardTab detail={detail} boardId={active} />
    </div>
  );
}

function BoardTab({ detail, boardId }: { detail: CharacterDetail; boardId: string }) {
  const board = detail.boards.find((b) => b.id === boardId)!;
  return (
    <div class="board">
      <p class="hint">
        {detail.boardRule}
        <InfoTip text={detail.describeNote} />
      </p>
      {boardId === "board1" ? (
        <AbilityCard title="队长技" table="leader_ability" group={detail.leader} rows={detail.leader.rows}
          columns={detail.columns.leader_ability} filter="all" />
      ) : null}
      {board.slots.length === 0 ? (
        <Notice>
          {boardId === "board3"
            ? "这个角色没有觉醒替换/追加的能力数据行，三板（觉醒）不开放。"
            : "这一板没有能力数据。"}
        </Notice>
      ) : (
        board.slots.map((group) => (
          <AbilityCard
            title={group.name}
            table="ability"
            group={group}
            rows={group.rows}
            columns={detail.columns.ability}
            awake={boardId === "board3"}
            filter={boardId === "board3" ? "awake" : "base"}
          />
        ))
      )}
    </div>
  );
}

function AbilityCard({ title, table, group, rows, columns, awake, filter }: {
  title: string; table: "ability" | "leader_ability"; group: AbilityGroup; rows: AbilityRow[]; columns: ColumnLabel[];
  awake?: boolean; filter: "base" | "awake" | "all";
}) {
  const hasOverride = group.descriptionSource === "游戏面板覆盖文案";
  const empty = !group.key || group.key === "(None)";
  const ws = useWorkspace();
  const slot = slotOf(table, group.key, ws?.state?.slots, group.slot);
  return (
    <article class="ability">
      <header>
        <h3>{title}</h3>
        <span class="muted key" title="词条键">{empty ? "未配置" : "键 " + group.key}</span>
        <span class="tag">{awake ? "觉醒行" : hasOverride ? "面板用覆盖文案" : "面板自动描述"}</span>
        <span class="spacer" />
        {awake ? null : <AttachControl table={table} slot={slot} title={title} />}
      </header>
      {hasOverride && !awake ? (
        <div class="override">
          <span class="label">玩家看到的文字（覆盖文案，在「文案」页编辑）</span>
          <p>{group.description}</p>
        </div>
      ) : null}
      {empty ? <p class="muted">{group.description}</p> : (
        <KeyEditor table={table} keyName={group.key} title={title} columns={columns}
          baseRows={rows.map((r) => r.values)} filter={filter} />
      )}
      {group.relatedPrograms.length ? (
        <details class="programs">
          <summary>关联程序 {group.relatedPrograms.length} 个</summary>
          <ul>
            {group.relatedPrograms.map((p) => (
              <li>
                <strong>{p.kind}</strong> <code>{p.program}</code> · 节点 {p.commandCount} <ProgramCapChip path={p.program} />
                {p.warning ? <span class="error-text"> {p.warning}</span> : null}
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </article>
  );
}

const SKILL_SUBS = [
  { id: "data", label: "技能数据", hint: "能量、程序、档位等字段" },
  { id: "preview", label: "动作预览", hint: "技能 / 强化弹射 / 629 能力技的编排时间轴（L2）" },
];

function SkillGroupPage({ detail, sub, link, onText }: {
  detail: CharacterDetail; sub?: string; link: (sub: string) => Route; onText: () => void;
}) {
  const active = SKILL_SUBS.some((s) => s.id === sub) ? sub! : "data";
  return (
    <div class="group-page">
      <nav class="subnav" aria-label="技能">
        {SKILL_SUBS.map((s) => (
          <a class={active === s.id ? "on" : ""} href={href(link(s.id))} title={s.hint} aria-current={active === s.id ? "page" : undefined}>{s.label}</a>
        ))}
      </nav>
      {active === "preview" ? <SkillPreview characterId={detail.id} /> : <SkillTab detail={detail} onText={onText} />}
    </div>
  );
}

function SkillTab({ detail, onText }: { detail: CharacterDetail; onText: () => void }) {
  const ws = useWorkspace();
  if (!detail.skills.length) return <Notice>没有找到技能数据。</Notice>;
  const skillKey = ws?.state?.entries.find((e) => e.table === "action_skill")?.key;
  return (
    <div class="board">
      <p class="hint">技能名和描述在「文案」页改（会同时改服务器上的文本）；这里改技能能量、程序等数值字段，以及档位的插入、删除和顺序。
        <InfoTip text="技术细节：action_skill 表；c0/c1 走 wf text 并同步两份服务端镜像；技能程序摘要来自技能 DSL（只列节点名称）。" />
        {" "}<button class="link" onClick={onText}>去文案页 →</button></p>
      <SkillTiers onText={onText} />
      {detail.switch ? (
        <Notice>技能切换：{detail.switch.label}（键 {detail.switch.key}）</Notice>
      ) : null}
      {detail.skills.map((s) => (
        <article class="ability">
          <header>
            <h3>{s.name || "（无名称）"}</h3>
            <span class="tag">{s.label}</span>
            <span class="muted key">{s.gaugeLabel}：{s.gauge ?? "—"}</span>
            <ProgramCapChip path={s.program} />
            <span class="spacer" />
            {s.kind === "main" && s.level === "1" ? <AttachControl table="action_skill" slot={0} title="技能" /> : null}
          </header>
          <p class="skill-text">{s.description || <em class="muted">（无文案）</em>}</p>
          <details class="programs">
            <summary>技能程序 · 节点 {s.commandCount}</summary>
            <p class="mono small">{s.program}</p>
            {s.warning ? <p class="error-text">{s.warning}</p> : null}
            <ul class="commands">{s.commands.map((c) => <li class="mono small">{c}</li>)}</ul>
          </details>
          {s.kind === "main" && skillKey ? (
            <KeyEditor table="action_skill" keyName={skillKey} level={s.level} title={s.label} columns={[]}
              baseRows={[s.raw]} filter="all" />
          ) : (
            <details class="raw">
              <summary>原始字段（{s.raw.length} 列，只读：{s.kind === "main" ? "正在读取" : "切换形态的技能不在这里编辑"}）</summary>
              <table><tbody>{s.raw.map((v, i) => <tr><td class="mono">c{i}</td><td class="mono">{v === "" ? "（空）" : v}</td></tr>)}</tbody></table>
            </details>
          )}
        </article>
      ))}
    </div>
  );
}
