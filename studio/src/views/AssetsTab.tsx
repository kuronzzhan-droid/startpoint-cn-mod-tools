import { useEffect, useState } from "preact/hooks";
import { api, AssetGroup, AssetItem, CharacterAssets } from "../api";
import { Notice } from "./common";

function size(bytes?: number): string {
  if (bytes == null) return "";
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / 1024 / 1024).toFixed(2) + " MB";
}

const EXPECTED_LABEL: Record<string, string> = {
  required: "模板必备", optional: "模板可选", referenced: "被引用",
};

export function AssetsTab({ characterId }: { characterId: string }) {
  const [data, setData] = useState<CharacterAssets | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [onlyMissing, setOnlyMissing] = useState(false);
  // Groups start folded (a character has ~200 files); groups with missing files start open.
  const [open, setOpen] = useState<Set<string>>(new Set());

  useEffect(() => {
    setData(null);
    api.assets(characterId).then((d) => {
      setData(d);
      setOpen(new Set(d.groups.filter((g) => g.missing).map((g) => g.id)));
    }, (e: Error) => setError(e.message));
  }, [characterId]);

  if (error) return <Notice kind="error">资源清单读取失败：{error}</Notice>;
  if (!data) return <div class="loading">正在探测这个角色的全部资源……</div>;
  const missing = data.groups.reduce((n, g) => n + g.missing, 0);

  return (
    <div class="assets">
      <p class="hint">{data.note}</p>
      <div class="asset-summary">
        <span>共 <strong>{data.total}</strong> 项</span>
        <span class={missing ? "error-text" : ""}>缺失 {missing} 项</span>
        <label class="check">
          <input type="checkbox" checked={onlyMissing} onChange={(e) => setOnlyMissing((e.target as HTMLInputElement).checked)} />
          只看缺失
        </label>
        <button class="small-btn" onClick={() => setOpen(new Set(data.groups.map((g) => g.id)))}>全部展开</button>
        <button class="small-btn" onClick={() => setOpen(new Set())}>全部收起</button>
      </div>
      {data.groups.map((group) => (
        <AssetGroupView group={group} onlyMissing={onlyMissing} data={data} open={open.has(group.id) || onlyMissing}
          onToggle={() => { const next = new Set(open); if (next.has(group.id)) next.delete(group.id); else next.add(group.id); setOpen(next); }} />
      ))}
    </div>
  );
}

function AssetGroupView({ group, onlyMissing, data, open, onToggle }: {
  group: AssetGroup; onlyMissing: boolean; data: CharacterAssets; open: boolean; onToggle: () => void;
}) {
  const items = onlyMissing ? group.items.filter((i) => !i.layer) : group.items;
  if (!open) {
    return (
      <section class="asset-group folded" id={`asset-${group.id}`}>
        <h3><button class="group-toggle" onClick={onToggle} aria-expanded="false">▸ {group.label}</button>
          <span class="count">{group.present}</span>{group.missing ? <span class="count bad">缺 {group.missing}</span> : null}</h3>
      </section>
    );
  }
  return (
    <section class="asset-group" id={`asset-${group.id}`}>
      <h3>
        <button class="group-toggle" onClick={onToggle} aria-expanded="true">▾ {group.label}</button>
        <span class="count">{group.present}</span>
        {group.missing ? <span class="count bad">缺 {group.missing}</span> : null}
      </h3>
      {group.id === "cutin" ? (
        <p class="muted small">
          真机战斗读取安卓根的 ATF（.atf.deflate），不读 PNG；只换 PNG 不会生效。
          {data.cutins.map((c) => (
            <span class="cutin-pair">
              {" "}形态 {c.form}：PNG {c.png ? "有" : "无"} · ATF {c.atf ? "有" : "无"}
              {c.png && c.atf && c.pngLayer !== c.atfLayer ? "（两者来自不同层，注意是否配对）" : ""}
            </span>
          ))}
        </p>
      ) : null}
      {group.id === "voice" && data.speech.length ? <SpeechTable data={data} /> : null}
      {items.length === 0 ? <p class="muted small">{onlyMissing ? "本组没有缺失项。" : "本组没有找到资源。"}</p> : (
        <div class={group.id === "voice" || group.id === "effect" || group.id === "other" ? "asset-list" : "asset-grid"}>
          {items.map((item) => <AssetCard item={item} compact={group.id === "voice" || group.id === "effect" || group.id === "other"} />)}
        </div>
      )}
    </section>
  );
}

function AssetCard({ item, compact }: { item: AssetItem; compact: boolean }) {
  const name = item.path.split("/").slice(-2).join("/");
  const meta = (
    <div class="asset-meta">
      <div class="mono small asset-path" title={item.path}>{compact ? item.path : name}</div>
      <div class="small">
        <span class={"status " + (item.layer ? "ok" : "bad")}>{item.status}</span>
        {item.expected ? <span class="tag">{EXPECTED_LABEL[item.expected]}</span> : null}
        {item.width ? <span class="muted"> {item.width}×{item.height}</span> : null}
        {item.size != null ? <span class="muted"> · {size(item.size)}</span> : null}
      </div>
      {item.layer ? (
        <div class="small muted">
          {(item.roots ?? []).map((r) => <div>{r.root}根 · {r.layerLabel}</div>)}
          {item.official ? <div>{item.official}</div> : null}
        </div>
      ) : null}
      {item.text ? <div class="small asset-line">「{item.text}」</div> : null}
      {item.notes.length ? <div class="small muted">{item.notes.join("；")}</div> : null}
    </div>
  );
  if (compact) {
    return (
      <div class={"asset-row" + (item.layer ? "" : " missing")}>
        {meta}
        {item.media === "audio" && item.layer ? <audio controls preload="none" src={api.assetUrl(item.path)} /> : null}
        {item.media === "image" && item.layer ? <img class="asset-thumb small-thumb" loading="lazy" src={api.assetUrl(item.path)} alt="" /> : null}
      </div>
    );
  }
  return (
    <div class={"asset-card" + (item.layer ? "" : " missing")}>
      <div class="asset-preview">
        {item.media === "image" && item.layer ? (
          <a href={api.assetUrl(item.path)} target="_blank" rel="noreferrer">
            <img class="asset-thumb" loading="lazy" src={api.assetUrl(item.path)} alt={name} />
          </a>
        ) : <span class="muted small">{item.layer ? "数据文件，无预览" : "缺失"}</span>}
      </div>
      {meta}
    </div>
  );
}

function SpeechTable({ data }: { data: CharacterAssets }) {
  return (
    <details class="speech" open>
      <summary>character_speech 台词 {data.speech.length} 行</summary>
      <table>
        <thead><tr><th>#</th><th>类型</th><th>可见</th><th>台词</th><th>语音</th></tr></thead>
        <tbody>
          {data.speech.map((s) => (
            <tr>
              <td class="mono">{s.row}</td>
              <td class="nowrap">{s.kind}</td>
              <td class="nowrap small">{s.constraint}{s.evoLevel ? ` · 进化${s.evoLevel}` : ""}</td>
              <td class="speech-text">{s.text}</td>
              <td>
                {s.path ? (s.present ? <audio controls preload="none" src={api.assetUrl(s.path)} /> : <span class="error-text small">引用但缺失：{s.voice}</span>)
                  : <span class="muted small">无声（(None)）</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  );
}
