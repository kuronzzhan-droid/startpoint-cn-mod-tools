import { useEffect, useState } from "preact/hooks";
import { corridor, LocaleRow } from "../../corridorApi";
import { Notice } from "../common";
import { Tag, useCorridor } from "./widgets";

function Row({ row }: { row: LocaleRow }) {
  const { run } = useCorridor();
  const [zh, setZh] = useState(row.zh ?? "");
  const [en, setEn] = useState(row.en ?? "");
  useEffect(() => { setZh(row.zh ?? ""); setEn(row.en ?? ""); }, [row.zh, row.en]);
  const dirty = zh !== (row.zh ?? "") || en !== (row.en ?? "");
  const owner = row.owner ? `#/corridor/${row.owner[0] === "relic" ? "relics" : "events"}/${row.owner[1]}` : null;
  return (
    <tr>
      <td class="mono small">{row.key}{owner ? <div><a href={owner}>{row.owner![1]}</a></div> : <Tag kind="warn">无引用</Tag>}</td>
      <td><textarea rows={2} style="width:100%" value={zh} onInput={(e) => setZh((e.currentTarget as HTMLTextAreaElement).value)} /></td>
      <td><textarea rows={2} style="width:100%" value={en} placeholder="待补" onInput={(e) => setEn((e.currentTarget as HTMLTextAreaElement).value)} /></td>
      <td>{row.missing.map((m) => <Tag key={m} kind="bad">{m} 缺</Tag>)}
        <button disabled={!dirty} onClick={() => run([{ op: "locale.set", key: row.key,
          ...(zh !== (row.zh ?? "") ? { zh } : {}), ...(en !== (row.en ?? "") ? { en } : {}) }], `文本 ${row.key}`)}>保存</button></td>
    </tr>
  );
}

export function LocalesPage() {
  const { tick, setError } = useCorridor();
  const [q, setQ] = useState("");
  const [missing, setMissing] = useState(false);
  const [data, setData] = useState<{ count: number; items: LocaleRow[]; totals: Record<string, number> } | null>(null);
  useEffect(() => {
    corridor.locales(new URLSearchParams({ q, missing: missing ? "1" : "" }).toString()).then(setData, (e: Error) => setError(e.message));
  }, [q, missing, tick]);
  return (
    <div class="cor">
      <Notice>locales_v3.json 是展示文本的真值：保存中文时同步回填遗物/事件里的旧中文字段。注意这份文本编进客户端（AbyssI18nContentV3），
        服务端只下发 key——改文案要重编客户端后才在游戏里可见；新增遗物/事件缺英文会阻断发布。</Notice>
      <div class="cor-toolbar">
        <input type="search" placeholder="搜 key / 中文 / 英文" value={q} onInput={(e) => setQ((e.currentTarget as HTMLInputElement).value)} />
        <label class="small"><input type="checkbox" checked={missing} onChange={(e) => setMissing((e.currentTarget as HTMLInputElement).checked)} /> 只看缺失</label>
        {data ? <span class="muted small">中 {data.totals.zh} · 英 {data.totals.en} · 缺失 {data.totals.missing} · 显示 {data.count}</span> : null}
      </div>
      {data ? (
        <div class="table-wrap">
          <table class="cor-table">
            <thead><tr><th style="width:24%">key</th><th>中文</th><th>English</th><th style="width:90px"></th></tr></thead>
            <tbody>{data.items.map((row) => <Row key={row.key} row={row} />)}</tbody>
          </table>
        </div>
      ) : <div class="loading">读取文本…</div>}
    </div>
  );
}
