import { useEffect, useState } from "preact/hooks";
import { AbilityGroup, AbilityRow, api, CharacterDetail, ColumnLabel } from "../api";
import { href } from "../router";
import { Avatar, ElementBadge, Notice, OriginBadge, Rarity, StatusStrip } from "./common";
import { AssetsTab } from "./AssetsTab";
import { ChangesPanel, useDraft } from "./Changes";
import { PixelImport } from "./PixelImport";
import { PixelPlayer } from "./PixelPlayer";
import { PixelWorkshop } from "./PixelWorkshop";
import { PortraitEditor } from "./PortraitEditor";
import { VoiceTab } from "./VoiceTab";
import { useDeliveries } from "./Delivery";
import { AbilityProvider, KeyEditor, PendingBar, useAbilityWorkspace, useWorkspace } from "./AbilityEditor";
import { AttachControl, SkillTiers, slotOf } from "./KeyTools";
import { TextTab } from "./TextTab";

const TABS: { id: string; label: string }[] = [
  { id: "board1", label: "一板" },
  { id: "board2", label: "二板" },
  { id: "board3", label: "三板（觉醒）" },
  { id: "skill", label: "技能" },
  { id: "text", label: "文案" },
  { id: "pixel", label: "像素小人" },
  { id: "assets", label: "全套资源" },
  { id: "portrait", label: "换立绘" },
  { id: "pixel-import", label: "换像素" },
  { id: "workshop", label: "像素工坊" },
  { id: "voice", label: "换语音" },
  { id: "changes", label: "本次修改" },
];

export function CharacterDetailView({ id, tab }: { id: string; tab?: string }) {
  const [detail, setDetail] = useState<CharacterDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const active = TABS.some((t) => t.id === tab) ? tab! : "board1";
  const draft = useDraft(id);
  const workspace = useAbilityWorkspace(id);
  const built = useDeliveries(id);

  useEffect(() => {
    setDetail(null);
    setError(null);
    api.character(id).then(setDetail, (e: Error) => setError(e.message));
  }, [id]);

  if (error) return <section class="page"><BackLink /><Notice kind="error">读取角色失败：{error}</Notice></section>;
  if (!detail) return <section class="page"><BackLink /><div class="loading">正在读取角色 {id}……</div></section>;

  const awakeCount = detail.boards.find((b) => b.id === "board3")?.slots.length ?? 0;

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
          <OriginBadge origin={detail.origin} />
          <span class="char-id" title={"代码名 " + detail.code}>ID {detail.id} · {detail.code}</span>
        </div>
      </header>
      <StatusStrip draft={draft.view?.status ?? null} checks={draft.view?.changeset?.changes.flatMap((c) => c.checks) ?? []}
        build={(built.list ?? []).find((d) => draft.view?.changeset && d.draftRevision === draft.view.changeset.revision
          && draft.view.status.state === "saved") ?? null} />
      <nav class="tabs" role="tablist" aria-label="角色内容">
        {TABS.map((t) => (
          <a role="tab" aria-selected={active === t.id} class={active === t.id ? "active" : ""}
            href={href({ work: "content", shop: "characters", id, tab: t.id })}>
            {t.label}
            {t.id === "board3" ? <span class="count">{awakeCount}</span> : null}
            {t.id === "changes" && draft.view?.status.changes ? (
              <span class={"count " + (draft.view.status.state === "saved" ? "" : "dirty")}>{draft.view.status.changes}</span>
            ) : null}
          </a>
        ))}
      </nav>
      {active.startsWith("board") ? (
        <BoardTab detail={detail} boardId={active} />
      ) : active === "skill" ? (
        <SkillTab detail={detail} />
      ) : active === "text" ? (
        <TextTab characterId={detail.id} />
      ) : active === "assets" ? (
        <AssetsTab characterId={detail.id} />
      ) : active === "portrait" ? (
        <PortraitEditor characterId={detail.id} />
      ) : active === "pixel-import" ? (
        <PixelImport characterId={detail.id} />
      ) : active === "workshop" ? (
        <PixelWorkshop characterId={detail.id} />
      ) : active === "voice" ? (
        <VoiceTab characterId={detail.id} />
      ) : active === "changes" ? (
        <ChangesPanel characterId={detail.id} />
      ) : (
        <PixelPlayer characterId={detail.id} />
      )}
      <PendingBar />
    </section>
    </AbilityProvider>
  );
}

function BackLink() {
  return <a class="back" href={href({ work: "content", shop: "characters" })}>← 查找其他角色</a>;
}

function BoardTab({ detail, boardId }: { detail: CharacterDetail; boardId: string }) {
  const board = detail.boards.find((b) => b.id === boardId)!;
  return (
    <div class="board">
      <p class="hint">
        {detail.boardRule}
        <br />
        {detail.describeNote}
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
        <span class="tag">{awake ? "觉醒行" : hasOverride ? "有覆盖文案" : "数据行自动解析"}</span>
        <span class="spacer" />
        {awake ? null : <AttachControl table={table} slot={slot} title={title} />}
      </header>
      {hasOverride && !awake ? (
        <div class="override">
          <span class="label">玩家文案（覆盖，desc_override；在「文案」页编辑）</span>
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
                <strong>{p.kind}</strong> <code>{p.program}</code> · 节点 {p.commandCount}
                {p.warning ? <span class="error-text"> {p.warning}</span> : null}
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </article>
  );
}

function SkillTab({ detail }: { detail: CharacterDetail }) {
  const ws = useWorkspace();
  if (!detail.skills.length) return <Notice>没有找到技能数据（action_skill）。</Notice>;
  const skillKey = ws?.state?.entries.find((e) => e.table === "action_skill")?.key;
  return (
    <div class="board">
      <p class="hint">技能文本取自 action_skill 表（玩家可见文案）；程序摘要来自技能 DSL，仅列出节点名称，L2 时间线预览尚未接入。
        <br />编辑：c0 技能名 / c1 文案走 wf text 面板规则，并同步两份服务端镜像（生成时写入交付 server/）；改名或文案时每一档都会带旧值断言。
        档位插入/删除见下方「技能档位」；完整文案规则与服务端生效文本对照见「文案」页。</p>
      <SkillTiers />
      {detail.switch ? (
        <Notice>技能切换：{detail.switch.label}（键 {detail.switch.key}）</Notice>
      ) : null}
      {detail.skills.map((s) => (
        <article class="ability">
          <header>
            <h3>{s.name || "（无名称）"}</h3>
            <span class="tag">{s.label}</span>
            <span class="muted key">{s.gaugeLabel}：{s.gauge ?? "—"}</span>
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
              <summary>原始字段（{s.raw.length} 列，只读：{s.kind === "main" ? "正在读取词条键" : "切换形态技能不在 action_skill 编辑范围"}）</summary>
              <table><tbody>{s.raw.map((v, i) => <tr><td class="mono">c{i}</td><td class="mono">{v === "" ? "（空）" : v}</td></tr>)}</tbody></table>
            </details>
          )}
        </article>
      ))}
    </div>
  );
}
