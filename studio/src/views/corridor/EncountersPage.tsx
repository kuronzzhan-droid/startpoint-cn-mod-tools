import { useEffect, useState } from "preact/hooks";
import { corridor, ELEMENTS, EncounterPage, Json } from "../../corridorApi";
import { Notice } from "../common";
import { Num, Tag, useCorridor } from "./widgets";

const EL = Object.fromEntries(ELEMENTS);

export function EncountersPage() {
  const { run, tick, setError } = useCorridor();
  const [data, setData] = useState<EncounterPage | null>(null);
  const [bossRounds, setBossRounds] = useState("");
  useEffect(() => {
    corridor.encounters().then((d) => { setData(d); setBossRounds((d.boss_rounds ?? []).join(",")); }, (e: Error) => setError(e.message));
  }, [tick]);
  if (!data) return <div class="loading">读取遭遇…</div>;
  const byQuest = Object.fromEntries(data.host.map((e) => [e.quest_id, e]));
  const label = (q: string | null) => (q ? `${byQuest[q]?.label ?? ""}（${q.slice(-3)}）` : "—");
  const ranked = [...data.host].sort((a, b) => (a.rank ?? 999) - (b.rank ?? 999) || a.round - b.round);
  const toggle = (round: number, exclude: boolean) => {
    const next = exclude ? [...data.excluded_rounds, round] : data.excluded_rounds.filter((r) => r !== round);
    run([{ op: "rules.set", path: "/encounters/exclude_rounds", value: [...new Set(next)].sort((a, b) => a - b) }],
      `${exclude ? "排除" : "恢复"}第 ${round} 轮`);
  };
  const be = (data.boss_elements ?? {}) as Record<string, Json>;
  return (
    <div class="cor">
      <Notice>每幕首领 = 本幕排名段里威胁最高的遭遇；第 1 幕跳过对开局属性伤害倍率 ≤ 阈值的遭遇（v3f）。
        排除轮次是全局的；幕级白名单需要服务端能力（候选）。改排名段或排除后，下面的首领矩阵会实时重算。</Notice>
      {data.problems.length ? <Notice kind="error">{data.problems.map((p, i) => <div key={i}>{p.message}</div>)}</Notice> : null}
      <div class="cor-grid">
        {data.acts.map((a, i) => (
          <div key={a.act} class="cor-card">
            <h3>第 {a.act} 幕 <Tag kind={a.size >= 4 ? "ok" : "bad"}>{a.size} 个遭遇</Tag></h3>
            <div class="cor-toolbar small">
              排名段 <Num value={a.ranks[0]} min={1} max={28} onChange={(v) => run([{ op: "rules.set", path: `/map/acts/${i}/encounter_ranks`, value: [Math.round(v), a.ranks[1]] }], `第${a.act}幕排名段`)} />
              – <Num value={a.ranks[1]} min={1} max={28} onChange={(v) => run([{ op: "rules.set", path: `/map/acts/${i}/encounter_ranks`, value: [a.ranks[0], Math.round(v)] }], `第${a.act}幕排名段`)} />
            </div>
            <table class="cor-table cor-matrix small">
              <thead><tr><th>开局属性</th><th>本幕首领</th></tr></thead>
              <tbody>
                {ELEMENTS.map(([k, l]) => (
                  <tr key={k}><td>{l}</td><td>{a.boss_by_element[k] ? label(a.boss_by_element[k]) : <Tag kind="bad">无首领</Tag>}
                    {a.boss_by_element[k] && a.boss_by_element[k] !== a.boss ? <Tag kind="info" title="段尾对该属性无效，改选下一个">跳过段尾</Tag> : null}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}
        <div class="cor-card">
          <h3>首领规则</h3>
          <div class="cor-form">
            <label>首领轮次</label>
            <span class="cor-toolbar"><input type="text" value={bossRounds} onInput={(e) => setBossRounds((e.currentTarget as HTMLInputElement).value)} />
              <button onClick={() => run([{ op: "rules.set", path: "/encounters/boss_rounds",
                value: bossRounds.split(/[,，\s]+/).filter(Boolean).map(Number) }], "首领轮次")}>保存</button></span>
            <label>无效阈值</label><Num value={be.threshold as number} min={0} max={0.99} step={0.01}
              onChange={(v) => run([{ op: "rules.set", path: "/v3f/boss_elements/threshold", value: v }], "首领属性阈值")} />
            <label>第 1 幕跳过无效首领</label><input type="checkbox" checked={!!be.exclude_act1}
              onChange={(e) => run([{ op: "rules.set", path: "/v3f/boss_elements/exclude_act1", value: (e.currentTarget as HTMLInputElement).checked }], "第1幕首领规则")} />
            <label>有效属性加权的幕</label>
            <span>{[1, 2, 3].map((a) => (
              <label key={a} class="small"><input type="checkbox" checked={((be.boost_acts as number[]) ?? []).includes(a)} onChange={(e) => {
                const cur = (be.boost_acts as number[]) ?? [];
                const next = (e.currentTarget as HTMLInputElement).checked ? [...cur, a] : cur.filter((x) => x !== a);
                run([{ op: "rules.set", path: "/v3f/boss_elements/boost_acts", value: [...new Set(next)].sort() }], "加权幕");
              }} /> {a} </label>))}</span>
            <label>有效属性概率下限</label><Num value={be.effective_share as number} min={0} max={1} step={0.05}
              onChange={(v) => run([{ op: "rules.set", path: "/v3f/boss_elements/effective_share", value: v }], "有效属性下限")} />
          </div>
        </div>
      </div>
      <div class="table-wrap">
        <table class="cor-table">
          <thead><tr><th>排名</th><th>轮</th><th>quest</th><th>敌人</th><th>提示</th><th>威胁</th><th>属性伤害（≠1）</th><th>所在幕</th><th>参与</th><th>备注</th></tr></thead>
          <tbody>
            {ranked.map((e) => {
              const dmg = Object.entries(e.element_damage).filter(([, r]) => r !== 1);
              const bossOf = data.acts.filter((a) => a.boss === e.quest_id).map((a) => a.act);
              return (
                <tr key={e.quest_id} class={e.excluded ? "dim" : ""}>
                  <td>{e.rank ?? "—"}</td><td>{e.round}</td><td class="mono small">{e.quest_id}</td>
                  <td title={e.mechanic_text}>{e.label}{bossOf.length ? <Tag kind="info">第{bossOf.join("/")}幕首领</Tag> : null}</td>
                  <td>{e.kind_hint}</td><td>{Math.round(e.threat * 100) / 100}</td>
                  <td class="small">{dmg.map(([k, r]) => <Tag key={k} kind={r <= data.threshold ? "bad" : "warn"}>{EL[k]}×{r}</Tag>)}</td>
                  <td>{e.acts.join("、") || "—"}</td>
                  <td><label class="small"><input type="checkbox" checked={!e.excluded} onChange={(ev) => toggle(e.round, !(ev.currentTarget as HTMLInputElement).checked)} />
                    {e.excluded ? " 已排除" : " 参与"}</label></td>
                  <td><a href="javascript:void 0" title={String(e.policy.notes ?? "")} onClick={() => {
                    const notes = window.prompt(`遭遇 ${e.quest_id} 备注`, String(e.policy.notes ?? ""));
                    if (notes !== null) run([{ op: "encounter.policy", quest_ids: [e.quest_id], notes: notes || null }], "遭遇备注");
                  }}>{e.policy.notes ? "✎" : "＋"}</a></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
