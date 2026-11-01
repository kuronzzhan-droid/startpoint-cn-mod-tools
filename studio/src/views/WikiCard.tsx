import { useEffect, useState } from "preact/hooks";
import { get, onDraftChange } from "../api";
import { TranslationSource } from "../abilityGlossary";
import { TranslationBadge } from "./TranslationBadge";
import { Notice } from "./common";

interface CardGroup { name: string; description: string; translation?: TranslationSource }
interface Card {
  id: string; name: string; title: string; profile: string; element: string; rarity: number;
  type: string; role: string; portraits: { url: string; label: string }[];
  leader: CardGroup; abilities: CardGroup[];
  skills: { label: string; name: string; description: string; translation?: TranslationSource; gauge: number | null }[];
  stats: { levels: { level: number; hp: number; atk: number }[]; note: string };
  warnings: string[];
}
interface Preview { card: Card; draftRevision: number | null; sourceVersion: string; note: string; readOnly: true }

export function WikiCard({ cid }: { cid: string }) {
  const [data, setData] = useState<Preview | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    let request = 0;
    const load = () => {
      const n = ++request;
      setData(null); setError(null);
      get<Preview>(`/api/drafts/${cid}/wiki-card`).then((v) => { if (active && n === request) setData(v); },
        (e: Error) => { if (active && n === request) setError(e.message); });
    };
    load();
    const off = onDraftChange((changed) => { if (changed === cid) load(); });
    return () => { active = false; off(); };
  }, [cid]);
  if (error) return <Notice kind="error">Wiki 卡片预览失败：{error}</Notice>;
  if (!data) return <p class="loading">正在读取草稿 Wiki 卡片……</p>;
  const c = data.card;
  return <div class="board wiki-card-preview">
    <p class="hint">{data.note} 来源 {data.sourceVersion} · 草稿修订 {data.draftRevision ?? "无"}</p>
    <article class="ability"><header><h2>{c.name}</h2><span class="tag">{c.element} · ★{c.rarity || "未定"}</span><span>{c.type} {c.role}</span></header>
      <p>{c.title}</p><p class="speech-text">{c.profile}</p>
      <div class="change-thumbs">{c.portraits.map((p) => <figure><img src={p.url} alt={p.label} loading="lazy" /><figcaption>{p.label}</figcaption></figure>)}</div>
    </article>
    {[c.leader, ...c.abilities].map((g) => <article class="ability"><header><h3>{g.name || "队长技"}</h3>{g.translation && <TranslationBadge value={g.translation} />}</header><p class="speech-text">{g.description}</p></article>)}
    {c.skills.map((s) => <article class="ability"><header><h3>{s.name}</h3><span>{s.label} · 能量 {s.gauge ?? "未知"}</span></header>{s.translation && <TranslationBadge value={s.translation} />}<p class="speech-text">{s.description}</p></article>)}
    <article class="ability"><h3>基础数值</h3><p class="small muted">{c.stats.note}</p>
      <table><thead><tr><th>等级</th><th>HP</th><th>ATK</th></tr></thead><tbody>{c.stats.levels.map((s) => <tr><td>{s.level}</td><td>{s.hp}</td><td>{s.atk}</td></tr>)}</tbody></table>
    </article>
    {c.warnings.length ? <Notice kind="warn"><ul>{c.warnings.map((w) => <li>{w}</li>)}</ul></Notice> : null}
  </div>;
}
