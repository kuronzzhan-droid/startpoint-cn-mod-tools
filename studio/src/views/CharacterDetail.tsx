import { useEffect, useState } from "preact/hooks";
import { AbilityGroup, AbilityRow, api, CharacterDetail, ColumnLabel } from "../api";
import { href } from "../router";
import { Avatar, ElementBadge, Notice, OriginBadge, Rarity, StatusStrip } from "./common";
import { AssetsTab } from "./AssetsTab";
import { PixelPlayer } from "./PixelPlayer";

const TABS: { id: string; label: string }[] = [
  { id: "board1", label: "一板" },
  { id: "board2", label: "二板" },
  { id: "board3", label: "三板（觉醒）" },
  { id: "skill", label: "技能" },
  { id: "pixel", label: "像素小人" },
  { id: "assets", label: "全套资源" },
];

export function CharacterDetailView({ id, tab }: { id: string; tab?: string }) {
  const [detail, setDetail] = useState<CharacterDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const active = TABS.some((t) => t.id === tab) ? tab! : "board1";

  useEffect(() => {
    setDetail(null);
    setError(null);
    api.character(id).then(setDetail, (e: Error) => setError(e.message));
  }, [id]);

  if (error) return <section class="page"><BackLink /><Notice kind="error">读取角色失败：{error}</Notice></section>;
  if (!detail) return <section class="page"><BackLink /><div class="loading">正在读取角色 {id}……</div></section>;

  const awakeCount = detail.boards.find((b) => b.id === "board3")?.slots.length ?? 0;

  return (
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
      <StatusStrip />
      <nav class="tabs" role="tablist" aria-label="角色内容">
        {TABS.map((t) => (
          <a role="tab" aria-selected={active === t.id} class={active === t.id ? "active" : ""}
            href={href({ work: "content", shop: "characters", id, tab: t.id })}>
            {t.label}
            {t.id === "board3" ? <span class="count">{awakeCount}</span> : null}
          </a>
        ))}
      </nav>
      {active.startsWith("board") ? (
        <BoardTab detail={detail} boardId={active} />
      ) : active === "skill" ? (
        <SkillTab detail={detail} />
      ) : active === "assets" ? (
        <AssetsTab characterId={detail.id} />
      ) : (
        <PixelPlayer characterId={detail.id} />
      )}
    </section>
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
        <AbilityCard title="队长技" group={detail.leader} rows={detail.leader.rows} columns={detail.columns.leader_ability} />
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
            group={group}
            rows={(group[board.rowsKey] as AbilityRow[]) ?? group.rows}
            columns={detail.columns.ability}
            awake={boardId === "board3"}
          />
        ))
      )}
    </div>
  );
}

function AbilityCard({ title, group, rows, columns, awake }: {
  title: string; group: AbilityGroup; rows: AbilityRow[]; columns: ColumnLabel[]; awake?: boolean;
}) {
  const hasOverride = group.descriptionSource === "游戏面板覆盖文案";
  const empty = !group.key || group.key === "(None)";
  return (
    <article class="ability">
      <header>
        <h3>{title}</h3>
        <span class="muted key" title="词条键">{empty ? "未配置" : "键 " + group.key}</span>
        <span class="tag">{awake ? "觉醒行" : hasOverride ? "有覆盖文案" : "数据行自动解析"}</span>
      </header>
      {hasOverride && !awake ? (
        <div class="override">
          <span class="label">玩家文案（覆盖）</span>
          <p>{group.description}</p>
        </div>
      ) : null}
      {empty ? <p class="muted">{group.description}</p> : null}
      <ol class="effect-rows">
        {rows.map((row) => (
          <li>
            <div class="effect-text">
              <span class="row-no">行 {row.index}</span>
              {row.awake ? <span class="tag awake">{row.awake.kind} Lv{row.awake.level}</span> : null}
              <span>{row.description || <em class="muted">（无法解析为中文描述）</em>}</span>
            </div>
            <RawFields values={row.values} columns={columns} />
          </li>
        ))}
      </ol>
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

function RawFields({ values, columns }: { values: string[]; columns: ColumnLabel[] }) {
  const [showEmpty, setShowEmpty] = useState(false);
  const filled = values.map((v, i) => ({ v, i })).filter(({ v }) => showEmpty || (v !== "" && v !== "(None)"));
  return (
    <details class="raw">
      <summary>原始字段（{values.length} 列，只读）</summary>
      <label class="check">
        <input type="checkbox" checked={showEmpty} onChange={(e) => setShowEmpty((e.target as HTMLInputElement).checked)} />
        显示空列
      </label>
      <table>
        <thead>
          <tr><th>列</th><th>区块</th><th>字段</th><th>值</th></tr>
        </thead>
        <tbody>
          {filled.map(({ v, i }) => (
            <tr class={v === "" || v === "(None)" ? "empty" : ""}>
              <td class="mono">c{i}</td>
              <td>{columns[i]?.block ?? ""}</td>
              <td title={columns[i]?.note ?? ""}>{columns[i]?.field ?? ""}</td>
              <td class="mono">{v === "" ? "（空）" : v}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  );
}

function SkillTab({ detail }: { detail: CharacterDetail }) {
  if (!detail.skills.length) return <Notice>没有找到技能数据（action_skill）。</Notice>;
  return (
    <div class="board">
      <p class="hint">技能文本取自 action_skill 表（玩家可见文案）；程序摘要来自技能 DSL，仅列出节点名称，L2 时间线预览尚未接入。</p>
      {detail.switch ? (
        <Notice>技能切换：{detail.switch.label}（键 {detail.switch.key}）</Notice>
      ) : null}
      {detail.skills.map((s) => (
        <article class="ability">
          <header>
            <h3>{s.name || "（无名称）"}</h3>
            <span class="tag">{s.label}</span>
            <span class="muted key">{s.gaugeLabel}：{s.gauge ?? "—"}</span>
          </header>
          <p class="skill-text">{s.description || <em class="muted">（无文案）</em>}</p>
          <details class="programs">
            <summary>技能程序 · 节点 {s.commandCount}</summary>
            <p class="mono small">{s.program}</p>
            {s.warning ? <p class="error-text">{s.warning}</p> : null}
            <ul class="commands">{s.commands.map((c) => <li class="mono small">{c}</li>)}</ul>
          </details>
          <details class="raw">
            <summary>原始字段（{s.raw.length} 列，只读）</summary>
            <table><tbody>{s.raw.map((v, i) => <tr><td class="mono">c{i}</td><td class="mono">{v === "" ? "（空）" : v}</td></tr>)}</tbody></table>
          </details>
        </article>
      ))}
    </div>
  );
}
