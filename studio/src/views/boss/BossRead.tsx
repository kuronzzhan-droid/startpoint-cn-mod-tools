import { ComponentChildren } from "preact";
import { BossCitation, BossDoc, BossEnemy, BossRecord } from "../../bossApi";
import { href } from "../../router";
import { ElementBadge, Notice } from "../common";
import { InfoTip } from "../Delivery";
import { citationTip, ENEMY_ELEMENTS, layerClass, layerLabel, present, questElement, shortName } from "./bossModel";

/** Small provenance pill; the full record is in the tooltip (技术细节). */
export function Src({ c }: { c: BossCitation | null | undefined }) {
  if (!c) return null;
  return <span class={"src-pill " + layerClass(c.layer)} title={citationTip(c)} tabIndex={0}>{layerLabel(c.layer)}</span>;
}

function Kv({ items }: { items: [ComponentChildren, ComponentChildren, string?][] }) {
  return (
    <dl class="kv">
      {items.map(([label, value, tip]) => (
        <>
          <dt title={tip}>{label}</dt>
          <dd>{value === "" || value === null || value === undefined ? <span class="muted">—</span> : value}</dd>
        </>
      ))}
    </dl>
  );
}

function Section({ title, src, tip, children }: { title: string; src?: BossCitation | null; tip?: string; children: ComponentChildren }) {
  return (
    <section class="boss-block">
      <header><h3>{title}</h3>{tip ? <InfoTip text={tip} /> : null}<span class="spacer" /><Src c={src} /></header>
      {children}
    </section>
  );
}

const cell = (row: string[] | undefined, i: number) => (row && row[i] !== undefined ? row[i] : "");
const val = (v: string) => (present(v) ? v : "");

export function ElementName({ value }: { value: string | null | undefined }) {
  const name = questElement(value);
  return name ? <span class="el-inline"><ElementBadge element={name} />{name}</span> : <span class="muted">{present(value ?? "") ? value : "不限定"}</span>;
}

/** 入口 / 关卡数值 / 场地与波次 / 敌人 —— the read model of one encounter. */
export function BossEncounter({ doc }: { doc: BossDoc }) {
  const { quest } = doc;
  const f = quest.fields;
  const scoped = doc.content_scope?.combat_content === false;
  return (
    <div class="boss-read">
      {scoped ? (
        <Notice kind="warn">下面的场地和敌人是<strong>入口自身</strong>的配置，不是实际战斗内容（{doc.content_scope?.label}）。实际战斗见上方「路由指向的隐藏关」。</Notice>
      ) : null}
      <Section title="入口" src={doc.entrance.stage_node?.source ?? doc.entrance.event?.source ?? doc.entrance.folder?.source}
        tip="玩家从哪里进这一关：领主战节点、共同决战活动及其目录、练习目录">
        <Entrance doc={doc} />
      </Section>
      <Section title="关卡数值" src={quest.source}
        tip={"quest 行原值。列号随副本类型不同（领主战 c106 等级、共同决战/练习 c107）。" + (quest.field_sources_semantics ? "\n" + quest.field_sources_semantics.note : "")}>
        <Kv items={[
          ["等级", f.level ? "Lv" + f.level : ""],
          ["难度 rank", val(f.rank)],
          ["副本属性", <ElementName value={f.recommended_element} />, "推荐属性字段；敌人属性为「继承」时 boss 用它作自身属性"],
          ["出战限定", <ElementName value={f.restriction} />],
          ["HP 倍率", <Multipliers values={[f.hp_zako, f.hp_funnel, f.hp_boss]} />],
          ["攻击倍率", <Multipliers values={[f.attack_zako, f.attack_funnel, f.attack_boss]} />],
          ["BGM 组", <span class="mono">{val(f.bgm)}</span>],
          ["体力", val(f.stamina)],
          ["时间限制（原值）", val(f.time_limit)],
          ["开放时间", <OpenTime start={f.start_time} end={f.end_time} />],
          ["前置条件", <Prerequisites values={f.need_quest ?? []} />],
          ["推荐属性隐藏", f.hide_recommended_element === "true" ? "是" : "否"],
        ]} />
      </Section>
      <Section title="场地与波次" src={doc.field_data.source ?? null}
        tip="field_data 指向场景（field）、地形和 zone；波次数等于地形的 objectgroup 层数，不按 zone 行数推断">
        <Kv items={[
          ["场景", doc.field.missing ? <span class="error-text">缺失：{doc.field.id}</span>
            : <span><span class="mono">{doc.field.id}</span> <span class="small muted">{cell(doc.field.row, 0)}</span></span>],
          ["地形", doc.terrain.missing ? <span class="error-text">缺失：{doc.terrain.logical}</span>
            : <span class="mono small">{doc.terrain.logical.replace(/\.amf3\.deflate$/, "")}</span>],
          ["zone", doc.zone.missing ? <span class="error-text">缺失：{doc.zone.id}</span> : <span class="mono">{doc.zone.id}</span>],
          ["field_data", <span class="mono">{doc.field_data.id}</span>],
        ]} />
        {doc.terrain.waves.length ? (
          <table class="boss-table">
            <thead><tr><th>波次</th><th>复活位</th><th>命名站位</th></tr></thead>
            <tbody>
              {doc.terrain.waves.map((w, i) => (
                <tr>
                  <td>第 {i + 1} 波 <span class="small muted mono">层 {w.name}</span></td>
                  <td class={w.coffin_count >= 9 ? "" : "warn-text"}>{w.coffin_count}{w.coffin_count >= 9 ? "" : "（协力需 9）"}</td>
                  <td class="mono small">{w.position_names.length ? w.position_names.join("、") : <span class="muted">无</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : null}
      </Section>
      <Section title={`敌人（${doc.enemies.length}）`} src={doc.zone.rows[0]?.source}
        tip="zone 槽位里的 boss 与杂兵；等级档 = 客户端按原生键顺序选出的第一个 ≥ 任务等级的档位">
        <EnemyTable enemies={doc.enemies} />
      </Section>
    </div>
  );
}

function Multipliers({ values }: { values: string[] }) {
  const same = values.every((v) => v === values[0]);
  if (same) return <span>×{values[0]}</span>;
  return <span>杂兵 ×{values[0]} · 浮游 ×{values[1]} · boss ×{values[2]}</span>;
}

function OpenTime({ start, end }: { start: string; end: string }) {
  return <span>{present(start) ? start : "—"} 起{present(end) ? `，至 ${end}` : "，不结束"}</span>;
}

function Prerequisites({ values }: { values: string[] }) {
  const set = values.filter(present);
  if (!set.length) return <span class="muted">无</span>;
  return <span class="mono small" title="quest c7–c16 原值（未逐列解释）">{values.map((v) => (present(v) ? v : "·")).join(" ")}</span>;
}

function Entrance({ doc }: { doc: BossDoc }) {
  const { entrance, quest } = doc;
  if (quest.kind === "boss_battle") {
    const node = entrance.stage_node;
    if (!node) return <p class="error-text">没有找到领主战节点 {quest.path.slice(0, 2).join("/")}。</p>;
    return (
      <Kv items={[
        ["页面", `${cell(node.row, 0)}`],
        ["节点标题", cell(node.row, 1)],
        ["节点", <span class="mono">{node.path.join("/")}</span>],
        ["兑换商店", present(cell(node.row, 6)) ? <span class="mono">分类 {cell(node.row, 6)}</span> : ""],
        ["币种", <span class="mono">{node.row.slice(7, 11).filter(present).join("、")}</span>],
      ]} />
    );
  }
  if (quest.kind === "hard_multi") {
    const event = entrance.event;
    const links = entrance.event_folder_events;
    return (
      <Kv items={[
        ["活动", event ? cell(event.row, 2) : <span class="error-text">缺少活动行 {quest.path[0]}</span>],
        ["活动 ID", <span class="mono">{quest.path[0]}</span>],
        ["活动目录", links.length ? links.map((l) => (
          <span class="mono">目录 {l.path[0]} / 节点 {l.path[1]}（类型 {cell(l.row, 0)}）</span>
        )) : <span class="warn-text">没有挂进任何活动目录</span>],
        ["活动时间", event ? <OpenTime start={cell(event.row, 23)} end={cell(event.row, 24)} /> : ""],
      ]} />
    );
  }
  const folder = entrance.folder;
  return (
    <Kv items={[
      ["练习目录", folder ? `${cell(folder.row, 0)}` : <span class="error-text">缺少练习目录</span>],
      ["目录键", <span class="mono">{cell(quest.row, 0)}</span>],
      ["练习关 ID", <span class="mono" title="练习表 c0 是目录；身份取表键">{quest.id}</span>],
    ]} />
  );
}

function enemyName(e: BossEnemy): string {
  if (e.name) return e.name;
  if (e.table?.endsWith("general_boss.orderedmap") && present(cell(e.row, 3))) return cell(e.row, 3);
  return e.code;
}

const MODE_TEXT: Record<string, string> = { single: "单人", multi: "协力", both: "通用" };

function EnemyTable({ enemies }: { enemies: BossEnemy[] }) {
  if (!enemies.length) return <p class="muted small">zone 里没有敌人槽位。</p>;
  return (
    <div class="table-scroll">
      <table class="boss-table">
        <thead><tr><th>波次</th><th>槽</th><th>类型</th><th>名称</th><th>等级档</th><th>属性</th><th>站位</th><th>来源</th></tr></thead>
        <tbody>
          {enemies.map((e) => {
            const general = e.table?.endsWith("general_boss.orderedmap");
            const elementIndex = general && /^\d+$/.test(e.element ?? "") ? Number(e.element) : -1;
            return (
              <tr class={e.missing ? "missing" : ""}>
                <td>{Number(e.wave) + 1}</td>
                <td class="nowrap">{MODE_TEXT[e.mode] ?? e.mode} {e.slot}</td>
                <td>{e.kind === "boss" ? "boss" : "杂兵"}</td>
                <td><span>{enemyName(e)}</span> <span class="mono small muted">{e.code}</span></td>
                <td class="nowrap" title="客户端按原生键顺序取第一个 ≥ 任务等级的档位">
                  {e.missing === null ? <span class="warn-text">未核对</span> : e.missing ? <span class="error-text">无可选档</span>
                    : e.path && e.path.length > 1 ? `档 ${e.path[1]}` : "单档"}
                </td>
                <td>{elementIndex >= 0 ? (ENEMY_ELEMENTS[elementIndex] ?? e.element) : <span class="muted">—</span>}</td>
                <td class="mono small">{e.position_name ?? "—"}</td>
                <td><Src c={e.source} />{e.limitation ? <span class="warn-text small"> {e.limitation}</span> : null}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/** 奖励（score / rare）与商店、武器。 */
export function BossRewards({ doc }: { doc: BossDoc }) {
  const { rewards } = doc;
  return (
    <div class="boss-read">
      <Section title="通关奖励" src={rewards.score_reward[0]?.source}
        tip="score_reward 组（quest 的奖励列）及其引用的 rare_score_reward 组；列含义未逐列核对，按原值显示">
        {!present(rewards.key) ? <p class="muted small">这一关没有奖励组。</p> : rewards.missing ? (
          <p class="error-text">奖励组 {rewards.key} 在客户端表里不存在。</p>
        ) : (
          <>
            <p class="small">奖励组 <span class="mono">{rewards.key}</span> · 涉及物品 {rewards.item_ids.map((i) => <span class="tag mono">{i}</span>)}</p>
            <RowTable title="score_reward" records={rewards.score_reward} />
            {rewards.rare_score_reward.length ? <RowTable title="rare_score_reward（稀有）" records={rewards.rare_score_reward} /> : null}
          </>
        )}
      </Section>
      <Section title={`商店与武器（${doc.shops.length}）`} tip="按领主节点的商店分类、奖励币种关联；服务端同步在「生成」时由规则检查，读模型本身不读服务端">
        {!doc.shops.length ? <p class="muted small">没有关联的兑换商店。</p> : doc.shops.map((shop) => (
          <article class="boss-shop">
            <header>
              <h4>分类 {shop.id}{shop.category ? ` · ${cell(shop.category.row, 0)}` : ""}</h4>
              <Src c={shop.category?.source} />
              {shop.association.kind === "field_family_inference" ? (
                <span class="tag" title={shop.association.note}>按场景命名推断的关联</span>
              ) : null}
              {!shop.category ? <span class="error-text small">缺少 boss_coin_shop_category 同号行</span> : null}
            </header>
            <ul class="boss-products">
              {shop.products.map((p) => (
                <li>
                  <span>{cell(p.row, 6) || p.path.join("/")}</span>
                  <span class="small muted mono"> {p.path.join("/")}</span>
                  {present(cell(p.row, 17)) ? <span class="small muted"> · 消耗 {cell(p.row, 18)} × <span class="mono">{cell(p.row, 17)}</span></span> : null}
                </li>
              ))}
            </ul>
            {shop.weapons.length ? (
              <p class="small">武器：{shop.weapons.map((w) => (
                <span class="tag" title={w.equipment ? cell(w.equipment.row, 7) : "装备表缺行"}>
                  {w.equipment ? cell(w.equipment.row, 1) : <span class="error-text">缺装备行</span>} <span class="mono">{w.id}</span>
                </span>
              ))}</p>
            ) : null}
            <p class="small muted">服务端：{shop.server_sync}</p>
          </article>
        ))}
      </Section>
    </div>
  );
}

function RowTable({ title, records }: { title: string; records: BossRecord[] }) {
  const width = Math.max(...records.map((r) => r.row.length), 0);
  return (
    <details class="tech" open={records.length <= 6}>
      <summary>{title} · {records.length} 行</summary>
      <div class="table-scroll">
        <table class="boss-table mono small">
          <thead><tr><th>键</th>{Array.from({ length: width }, (_, i) => <th>c{i}</th>)}<th>来源</th></tr></thead>
          <tbody>
            {records.map((r) => (
              <tr><td>{r.path.join("/")}</td>{Array.from({ length: width }, (_, i) => <td>{cell(r.row, i)}</td>)}<td><Src c={r.source} /></td></tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

/** 五重入口：路由到的隐藏关。 */
export function HiddenQuests({ doc }: { doc: BossDoc }) {
  const hidden = doc.routing.hidden_quests ?? [];
  return (
    <section class="boss-block">
      <header><h3>路由指向的隐藏关（{hidden.length}）</h3><InfoTip text={doc.routing.meaning ?? "BothBoss 路由"} /></header>
      <p class="small muted">{doc.routing.meaning}。入口按两轮选择把玩家送进这些隐藏关；要改难度，打开对应的隐藏关。</p>
      <div class="table-scroll">
        <table class="boss-table">
          <thead><tr><th>隐藏关</th><th>quest</th><th>场景数据</th><th>路由引用</th></tr></thead>
          <tbody>
            {hidden.map((h) => (
              <tr>
                <td>{h.selector ? <a href={href({ work: "content", shop: "boss", quest: h.selector })}>{shortName(h.name ?? h.id).replace(/^五重决战·?/, "")}</a>
                  : <span class="error-text">缺失</span>}</td>
                <td class="mono small">{h.id}</td>
                <td class="mono small">{h.field_data ?? "—"}</td>
                <td class="small">{h.map_refs.length} 条</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
