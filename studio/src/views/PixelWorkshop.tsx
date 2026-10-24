import { useEffect, useMemo, useState } from "preact/hooks";
import {
  api, CharacterSummary, ColorPair, drafts, PaletteColor, PaletteGroup, RemapResult, WorkshopAction,
  WorkshopAnalysis, WorkshopCell, WorkshopFamily, workshop,
} from "../api";
import { ChecksList } from "./Changes";
import { Notice } from "./common";
import { InfoTip } from "./Delivery";
import { ActionStage, canvasFromRaw, contentCrop, hexToInt, luma, recolorRaw, useClock, useFamilies } from "./workshopKit";
import { DrawingBoard, ProceduralActions } from "./PixelWorkshopTools";

export type WorkshopSub = "breakdown" | "remap" | "generate" | "board";
export const WORKSHOP_SUBS: { id: WorkshopSub; label: string; hint: string }[] = [
  { id: "breakdown", label: "拆解", hint: "逐动作看每张图、复用和调色板" },
  { id: "remap", label: "母本换色", hint: "拿一个官方小人当母本，按颜色表整套换色" },
  { id: "generate", label: "程序化动作", hint: "从正面/背面底图自动合成走路、胜利、幽灵等动作" },
  { id: "board", label: "画板", hint: "逐帧手改一个动作" },
];
const GROUPS: PaletteGroup[] = ["body", "outline", "fx", "template"];
const ACTION_LABEL: Record<string, string> = {
  neutral: "待机", walk_front: "向前移动", walk_back: "向后移动", skill_ready: "技能准备", kachidoki: "胜利",
  into_coffin: "倒下入棺", ghost_raise: "幽灵升起", ghost_neutral: "幽灵待机", revive: "复活",
  special_land: "特殊登场", special_pose: "特殊姿势",
};
const KIND_LABEL: Record<string, string> = { loop: "循环", once: "单次", pass: "过渡", stop: "停住" };
const TINY = 10;

/** Plain-language legend for the pixel pages (technical names stay in tooltips). */
export function PixelLegend() {
  return (
    <details class="ws-legend">
      <summary>看图说明</summary>
      <dl>
        <dt>一张图</dt><dd>图集里的一个画面。时间轴上它接着上一张播放，一直显示到它的「结束帧号」。</dd>
        <dt>停留 N 帧</dt><dd>这张图显示多久；60 帧 = 1 秒。</dd>
        <dt>下沉</dt><dd>脚底比定位点低多少像素：正数往下沉，负数离地。（技术名 dy）</dd>
        <dt>R12</dt><dd>图集里的第 12 块区域；同一块被几个动作共用时才标出来。</dd>
        <dt>循环 / 单次 / 过渡 / 停住</dt><dd>动作的播放方式（loop / once / pass / stop）。</dd>
        <dt>战斗大图集</dt><dd>战斗时三名队员的小人拼进同一张 4096×4096 大图，每人占（宽+2）×（高+2）。（技术名 layer0）</dd>
        <dt>通用区间</dt><dd>官方角色都一样的动作帧号范围；不一样的会标出来。</dd>
        <dt>定位点</dt><dd>角色在战场上的站位原点，红色十字。</dd>
      </dl>
    </details>
  );
}
const GROUP_LABEL: Record<PaletteGroup, string> = { body: "本体", outline: "描边", fx: "特效", template: "入棺/幽灵模板" };

function storageGet<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch { return fallback; }
}
function storageSet(key: string, value: unknown) {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* private mode */ }
}

/** Palette grouping, editable, remembered per character in this browser. */
export function useGroups(cid: string, palette: PaletteColor[] | undefined) {
  const key = "wf-workshop-groups-" + cid;
  const [overrides, setOverrides] = useState<Record<string, PaletteGroup>>(() => storageGet(key, {}));
  useEffect(() => setOverrides(storageGet(key, {})), [cid]);
  const groups = useMemo(() => {
    const out: Record<string, PaletteGroup> = {};
    for (const p of palette ?? []) out[p.hex] = overrides[p.hex] ?? p.group;
    return out;
  }, [palette, overrides]);
  const set = (hex: string, group: PaletteGroup) => {
    const next = { ...overrides, [hex]: group };
    setOverrides(next);
    storageSet(key, next);
  };
  const reset = () => { setOverrides({}); storageSet(key, {}); };
  return { groups, set, reset, edited: Object.keys(overrides).length };
}

/** One workshop page (拆解 / 母本换色 / 程序化动作 / 画板); the 像素 group shows the sub navigation. */
export function PixelWorkshop({ characterId, sub }: { characterId: string; sub: WorkshopSub }) {
  const [state, setState] = useState<"view" | "draft">("view");
  const [analysis, setAnalysis] = useState<WorkshopAnalysis | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    setError(null);
    workshop.analyze(characterId, state).then(setAnalysis, (e: Error) => setError(e.message));
  }, [characterId, state, refresh]);
  const groups = useGroups(characterId, analysis?.palette);
  const bump = () => setRefresh((n) => n + 1);

  return (
    <div class="workshop">
      {sub === "breakdown" ? (
        <div class="ws-subtabs">
          <label class="small">看哪份数据
            <select value={state} onChange={(e) => setState((e.target as HTMLSelectElement).value as "view" | "draft")}>
              <option value="view">改动前（当前视图）</option>
              <option value="draft">草稿里的样子（含像素改动）</option>
            </select>
          </label>
          <span class="spacer" />
          <PixelLegend />
        </div>
      ) : null}
      {error ? <Notice kind="error">像素工坊读取失败：{error}</Notice> : null}
      {!analysis && !error ? <div class="loading">正在拆解像素图集……</div> : null}
      {analysis && sub === "breakdown" ? <Breakdown analysis={analysis} groups={groups} /> : null}
      {analysis && sub === "remap" ? <Remap analysis={analysis} groups={groups} onSaved={bump} /> : null}
      {analysis && sub === "generate" ? <ProceduralActions characterId={characterId} analysis={analysis} refresh={refresh} onSaved={bump} /> : null}
      {analysis && sub === "board" ? <DrawingBoard characterId={characterId} analysis={analysis} groups={groups.groups} refresh={refresh} onSaved={bump} /> : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// 拆解

function Breakdown({ analysis, groups }: { analysis: WorkshopAnalysis; groups: ReturnType<typeof useGroups> }) {
  const [familyName, setFamilyName] = useState(analysis.families[0]?.family ?? "pixelart");
  const [scale, setScale] = useState(4);
  const [picked, setPicked] = useState<{ action: string; key: number } | null>(null);
  const family = analysis.families.find((f) => f.family === familyName);
  if (!analysis.families.length) return <Notice kind="warn">这个角色没有像素族（pixelart / special）。</Notice>;
  if (!family) return null;
  const reuse = new Map(family.regions.map((r) => [r.id, r.keys.length]));
  const cell = picked ? family.actions.find((a) => a.name === picked.action)?.cells.find((c) => c.key === picked.key) : undefined;
  const region = cell ? family.regions[cell.region] : undefined;

  return (
    <div class="ws-breakdown">
      <div class="toolbar">
        {analysis.families.map((f) => (
          <button class={f.family === familyName ? "primary" : ""} onClick={() => { setFamilyName(f.family); setPicked(null); }}>
            {f.family === "pixelart" ? "基础动作 pixelart" : "特殊动作 special"}
          </button>
        ))}
        <span class="muted small">
          <span title={`sprite_sheet ${family.sheet.width}×${family.sheet.height}，填充 ${(family.sheet.fill * 100).toFixed(1)}%`}>图集 {family.sheet.width}×{family.sheet.height}</span> ·
          {family.family === "pixelart" ? <span title="战斗大图集 layer0：(宽+2)×(高+2)"> 战斗大图集占 {family.sheet.layer0Px} 像素 · </span> : " 战斗不加载 · "}
          <span title={`atlas 端点 ${family.keys} 个，区域 ${family.regions.length} 个，frame.scale ${family.frame.scale}，原点 (${family.origin.join(", ")})`}>
            {family.keys} 张图 · 显示倍率 ×{family.frame.scale}</span>
        </span>
        <label class="small">每帧宽<select value={scale} onChange={(e) => setScale(Number((e.target as HTMLSelectElement).value))}>
          {[1, 2, 3, 4, 6].map((v) => <option value={v}>{v}px</option>)}</select></label>
      </div>
      <ChecksList checks={family.checks} empty="没有发现已知坑位。" />
      <div class="ws-timeline" aria-label="动作时间轴">
        {family.actions.map((a) => (
          <ActionRow cid={analysis.characterId} state={analysis.state} family={family} action={a} scale={scale}
            reuse={reuse} picked={picked} onPick={(key) => setPicked({ action: a.name, key })} />
        ))}
      </div>
      <div class="ws-detail-grid">
        <section class="ws-panel">
          <h4>选中的图</h4>
          {cell && region ? (
            <div class="ws-cell-detail">
              <img class="ws-big" src={workshop.cellUrl(analysis.characterId, family.family, cell.key, analysis.state)} alt="" />
              <table class="compare-table"><tbody>
                <tr><th>动作</th><td>{ACTION_LABEL[picked!.action] ?? picked!.action} · 从动作第 {cell.start} 帧起，停留 {cell.frames} 帧</td></tr>
                <tr><th>可见尺寸</th><td>{cell.w}×{cell.h}（{cell.alphaPx} 个可见像素）</td></tr>
                <tr><th>下沉 / 横向偏移</th><td>{cell.dy} / {cell.dx} <span class="muted small">（dy / dx）</span></td></tr>
                <tr><th>共用</th><td>{region.keys.length > 1 ? `和 ${region.actions.join("、")} 共用同一块图` : "只此一处"}</td></tr>
                <tr><th>技术细节</th><td class="small mono">端点 {cell.key} · fx {cell.fx} / fy {cell.fy} · 包围盒 {cell.bbox ? cell.bbox.join(", ") : "空"} ·
                  R{region.id} @ ({region.x}, {region.y}) {region.w}×{region.h}{region.rotated ? " 旋转 90°" : ""}</td></tr>
              </tbody></table>
            </div>
          ) : <p class="muted small">点时间轴上的任意一张图看明细。</p>}
        </section>
        <section class="ws-panel">
          <h4>图集复用与浪费</h4>
          <p class="small">复用区域 {family.regions.filter((r) => r.keys.length > 1).length} 个；
            逐像素重复（打包器未去重）{family.duplicateRegions.length} 组；无动作引用的区域 {family.unusedRegions.length} 个
            {family.unusedKeys.length ? `（端点 ${family.unusedKeys.slice(0, 12).join(", ")}${family.unusedKeys.length > 12 ? "…" : ""}）` : ""}。</p>
          <div class="ws-region-list">
            {family.regions.filter((r) => r.keys.length > 1 || family.unusedRegions.includes(r.id)).slice(0, 40).map((r) => (
              <span class={"ws-region" + (family.unusedRegions.includes(r.id) ? " unused" : "")} title={`端点 ${r.keys.join(", ")}`}>
                <img src={workshop.cellUrl(analysis.characterId, family.family, r.keys[0], analysis.state)} alt="" />
                R{r.id}×{r.keys.length}
              </span>
            ))}
          </div>
          <p class="muted small">{analysis.notes[0]}<br />{analysis.notes[1]}</p>
        </section>
      </div>
      <PalettePanel analysis={analysis} groups={groups} />
    </div>
  );
}

function ActionRow({ cid, state, family, action, scale, reuse, picked, onPick }: {
  cid: string; state: "view" | "draft"; family: WorkshopFamily; action: WorkshopAction; scale: number;
  reuse: Map<number, number>; picked: { action: string; key: number } | null; onPick: (key: number) => void;
}) {
  return (
    <div class="ws-row">
      <div class="ws-row-head">
        <strong>{ACTION_LABEL[action.name] ?? action.name}</strong>
        <span class="mono small muted">{action.name}</span>
        <span class="small" title={`时间轴帧 ${action.begin}–${action.end}`}>{action.totalFrames} 帧 · {KIND_LABEL[action.kind] ?? action.kind}</span>
        <span class={"small " + (action.universal ? "muted" : "warn-text")}>{action.universal ? "通用区间" : "非通用区间"}</span>
        <span class="small muted">{action.cells.length} 张图</span>
        {action.overflow ? <span class="small warn-text" title="区间超出图集最后一个端点，多出的帧取不到图">越界 {action.overflow} 帧</span> : null}
      </div>
      <div class="ws-strip">
        {action.cells.map((c: WorkshopCell) => {
          const shared = (reuse.get(c.region) ?? 1) > 1;
          const on = picked?.action === action.name && picked.key === c.key;
          return (
            <button class={"ws-cell" + (on ? " on" : "") + (shared ? " shared" : "")} style={{ width: Math.max(30, c.frames * scale) + "px" }}
              title={`结束帧号 ${c.key} · 停留 ${c.frames} 帧 · 下沉 ${c.dy}（dy；fy ${c.fy}）· ${c.w}×${c.h} · 区域 R${c.region}`}
              onClick={() => onPick(c.key)}>
              <img src={workshop.cellUrl(cid, family.family, c.key, state)} alt="" />
              <span class="mono">{c.key}</span>
              <span class="mono">{c.frames}f</span>
              <span class={"mono" + (c.dy ? " warn-text" : "")} title="下沉（dy）">↓{c.dy > 0 ? "+" : ""}{c.dy}</span>
              {shared ? <span class="mono ws-reg">R{c.region}</span> : null}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function PalettePanel({ analysis, groups }: { analysis: WorkshopAnalysis; groups: ReturnType<typeof useGroups> }) {
  const [showTiny, setShowTiny] = useState(false);
  const tiny = analysis.palette.filter((p) => p.count < TINY);
  return (
    <section class="ws-panel">
      <h4>调色板（{analysis.palette.length} 色）</h4>
      <p class="muted small">{analysis.notes[2]} {groups.edited ? <button class="link" onClick={groups.reset}>恢复启发分组（已改 {groups.edited} 色）</button> : null}</p>
      {tiny.length ? (
        <label class="check small"><input type="checkbox" checked={showTiny} onChange={(e) => setShowTiny((e.target as HTMLInputElement).checked)} />
          显示 {tiny.length} 个零星色（不到 {TINY} 个像素，多是描边/半透明过渡色）</label>
      ) : null}
      <div class="ws-palette-groups">
        {GROUPS.map((g) => {
          const colors = analysis.palette.filter((p) => groups.groups[p.hex] === g && (showTiny || p.count >= TINY));
          return (
            <div class="ws-pgroup">
              <h5>{GROUP_LABEL[g]} <span class="muted small">{colors.length}</span></h5>
              {colors.map((p) => (
                <div class="ws-swatch-row" title={`出现于 ${p.actions.join("、")}`}>
                  <span class="ws-swatch" style={{ background: p.hex }} />
                  <span class="mono small">{p.hex}</span>
                  <span class="small muted">{p.count}px</span>
                  {p.opaque === 0 ? <span class="tag" title="这个颜色只出现在半透明像素上">仅半透明</span> : null}
                  <select class="small" value={groups.groups[p.hex]} aria-label={"分组 " + p.hex}
                    onChange={(e) => groups.set(p.hex, (e.target as HTMLSelectElement).value as PaletteGroup)}>
                    {GROUPS.map((o) => <option value={o}>{GROUP_LABEL[o]}</option>)}
                  </select>
                </div>
              ))}
            </div>
          );
        })}
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// 母本映射

function suggest(base: PaletteColor[], baseGroups: Record<string, PaletteGroup>, target: PaletteColor[],
  targetGroups: Record<string, PaletteGroup>): Record<string, string> {
  const out: Record<string, string> = {};
  for (const g of ["body", "fx"] as PaletteGroup[]) {
    const from = base.filter((p) => baseGroups[p.hex] === g).sort((a, b) => a.luma - b.luma);
    const to = target.filter((p) => targetGroups[p.hex] === g).sort((a, b) => a.luma - b.luma);
    if (!from.length || !to.length) continue;
    from.forEach((p, i) => {
      out[p.hex] = to[Math.min(to.length - 1, Math.round((i * (to.length - 1)) / Math.max(1, from.length - 1)))].hex;
    });
  }
  return out;
}

function Remap({ analysis, groups, onSaved }: { analysis: WorkshopAnalysis; groups: ReturnType<typeof useGroups>; onSaved: () => void }) {
  const cid = analysis.characterId;
  const [query, setQuery] = useState("");
  const [roster, setRoster] = useState<CharacterSummary[]>([]);
  const [baseId, setBaseId] = useState<string | null>(() => storageGet<string | null>("wf-workshop-base-" + cid, null));
  const [base, setBase] = useState<WorkshopAnalysis | null>(null);
  const [mapping, setMapping] = useState<Record<string, string>>(() => storageGet("wf-workshop-map-" + cid, {}));
  const [lock, setLock] = useState(true);
  const [actionName, setActionName] = useState("skill_ready");
  const [allActions, setAllActions] = useState(false);
  const [playing, setPlaying] = useState(true);
  const [tick] = useClock(playing);
  const [result, setResult] = useState<RemapResult | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<{ kind: "info" | "error"; text: string } | null>(null);
  const baseGroups = useGroups(baseId ?? "none", base?.palette);
  const fam = useFamilies(baseId, "view", 0, true);

  useEffect(() => { api.characters().then((r) => setRoster(r.characters)); }, []);
  useEffect(() => {
    if (!baseId) return;
    storageSet("wf-workshop-base-" + cid, baseId);
    setBase(null);
    workshop.analyze(baseId).then(setBase, (e: Error) => setMessage({ kind: "error", text: e.message }));
  }, [baseId]);
  useEffect(() => storageSet("wf-workshop-map-" + cid, mapping), [mapping]);

  const map = useMemo(() => {
    const m = new Map<number, number>();
    for (const [from, to] of Object.entries(mapping)) if (to && to !== from) m.set(hexToInt(from), hexToInt(to));
    return m;
  }, [mapping]);
  // Recolour the backend-decoded RGBA; canvases are display-only (never read back).
  const remapped = useMemo(() => {
    const out: Record<string, HTMLCanvasElement> = {};
    for (const [name, raw] of Object.entries(fam.raws)) out[name] = canvasFromRaw(recolorRaw(raw, map));
    return out;
  }, [fam.raws, map]);
  const crops = useMemo(() => {
    const out: Record<string, ReturnType<typeof contentCrop>> = {};
    for (const f of fam.meta?.families ?? []) if (!f.error) out[f.family] = contentCrop(f, fam.raws[f.family]);
    return out;
  }, [fam.meta, fam.raws]);

  const hits = query.trim()
    ? roster.filter((c) => (c.id + c.name + (c.title ?? "") + c.code).toLowerCase().includes(query.trim().toLowerCase())).slice(0, 12)
    : [];
  const baseHexes = new Set((base?.palette ?? []).map((p) => p.hex));
  const pairs: ColorPair[] = Object.entries(mapping).filter(([f, t]) => t && t !== f && baseHexes.has(f))
    .map(([from, to]) => ({ from, to, group: baseGroups.groups[from] })).sort((a, b) => a.from.localeCompare(b.from));
  const request = (dryRun: boolean) => ({ base: baseId!, mapping: pairs.map(({ from, to }) => ({ from, to })), dryRun,
    groups: baseGroups.groups });
  const run = async (dryRun: boolean) => {
    setBusy(dryRun ? "check" : "save"); setMessage(null);
    try {
      const r = await workshop.remap(cid, request(dryRun));
      setResult(r);
      if (!dryRun) { setMessage({ kind: "info", text: `已写入草稿：${r.changes?.map((c) => c.title).join("；")}（${r.status?.label}）` }); onSaved(); }
    } catch (e) { setMessage({ kind: "error", text: (e as Error).message }); }
    finally { setBusy(null); }
  };
  const options = (fromHex: string) => {
    const g = baseGroups.groups[fromHex];
    return analysis.palette.filter((p) => !lock || groups.groups[p.hex] === g);
  };
  const actions = fam.meta?.families.flatMap((f) => (f.error ? [] : f.actions.map((a) => ({ f, a })))) ?? [];
  const shown = allActions ? actions : actions.filter((x) => x.a.name === actionName);

  return (
    <div class="ws-remap">
      <p class="hint">母本换色：挑一个官方小人当母本，照着颜色表把它整套小人一个颜色一个颜色地换掉，动作、帧数、站位全部照搬；
        表里没有的颜色保持原样。同一张表永远得到同样的结果，生成时会按母本重算再核对一遍。
        <InfoTip text="技术细节：精确 RGB→RGB 逐像素改色，alpha 不变；timeline 逐字节照搬，atlas 条目名与 frame.name 改成本角色前缀；生成时按母本+映射表重算并比对。" /></p>
      <div class="toolbar">
        <label>母本
          <input type="search" placeholder="名字 / ID / 代码名" value={query} onInput={(e) => setQuery((e.target as HTMLInputElement).value)} />
        </label>
        {baseId ? <span class="small">当前母本 <strong>{roster.find((c) => c.id === baseId)?.name ?? baseId}</strong> <span class="mono muted">{baseId} · {base?.code}</span></span> : <span class="muted small">先选母本</span>}
      </div>
      {hits.length ? (
        <div class="ws-hits">
          {hits.map((c) => (
            <button onClick={() => { setBaseId(c.id); setQuery(""); setResult(null); }}>
              <img src={api.avatarUrl(c.id)} alt="" width={28} height={28} loading="lazy" />
              <span>{c.name}</span><span class="mono small muted">{c.id} · {c.code}</span>
            </button>
          ))}
        </div>
      ) : null}
      {message ? <Notice kind={message.kind === "error" ? "error" : "info"}>{message.text}</Notice> : null}
      {baseId && base ? (
        <>
          <div class="ws-map-head">
            <label class="check small"><input type="checkbox" checked={lock} onChange={(e) => setLock((e.target as HTMLInputElement).checked)} />分组锁定（本体只映射到本体色、特效只映射到特效色）</label>
            <button onClick={() => setMapping({ ...mapping, ...suggest(base.palette, baseGroups.groups, analysis.palette, groups.groups) })}>自动建议（同组按明度排名）</button>
            <button onClick={() => setMapping({})}>清空</button>
            <span class="small muted">已映射 {pairs.length} 色 / 母本 {base.palette.length} 色</span>
          </div>
          <div class="ws-map-grid">
            <table class="compare-table ws-map-table" aria-label="颜色映射表">
              <thead><tr><th>母本色</th><th>分组</th><th>像素</th><th></th><th>映射到</th></tr></thead>
              <tbody>
                {GROUPS.flatMap((g) => base.palette.filter((p) => baseGroups.groups[p.hex] === g).map((p) => {
                  const to = mapping[p.hex] ?? "";
                  const opts = options(p.hex);
                  const custom = to && !opts.some((o) => o.hex === to);
                  return (
                    <tr class={to && to !== p.hex ? "hl" : ""}>
                      <td><span class="ws-swatch" style={{ background: p.hex }} /> <span class="mono">{p.hex}</span></td>
                      <td><select class="small" value={baseGroups.groups[p.hex]} onChange={(e) => baseGroups.set(p.hex, (e.target as HTMLSelectElement).value as PaletteGroup)}>
                        {GROUPS.map((o) => <option value={o}>{GROUP_LABEL[o]}</option>)}</select></td>
                      <td class="small muted">{p.count}</td>
                      <td>→</td>
                      <td class="ws-map-to">
                        <span class="ws-swatch" style={{ background: to || p.hex }} />
                        <select class="small mono" value={custom ? "custom" : to} aria-label={"映射 " + p.hex}
                          onChange={(e) => {
                            const v = (e.target as HTMLSelectElement).value;
                            setMapping({ ...mapping, [p.hex]: v === "custom" ? (to || p.hex) : v });
                          }}>
                          <option value="">保持原色</option>
                          {opts.map((o) => <option value={o.hex}>{o.hex} · {GROUP_LABEL[groups.groups[o.hex]]} · 明度 {Math.round(luma(o.hex))}</option>)}
                          <option value="custom">自定义…</option>
                        </select>
                        {custom || mapping[p.hex] === p.hex ? (
                          <input type="color" value={to || p.hex} onInput={(e) => setMapping({ ...mapping, [p.hex]: (e.target as HTMLInputElement).value })} />
                        ) : null}
                      </td>
                    </tr>
                  );
                }))}
              </tbody>
            </table>
            <div class="ws-palettes">
              <h5>本角色调色板（映射目标）</h5>
              {GROUPS.map((g) => (
                <div class="ws-chiprow"><span class="small muted">{GROUP_LABEL[g]}</span>
                  {analysis.palette.filter((p) => groups.groups[p.hex] === g).map((p) => <span class="ws-swatch" title={p.hex} style={{ background: p.hex }} />)}
                </div>
              ))}
              <h5>母本调色板</h5>
              {GROUPS.map((g) => (
                <div class="ws-chiprow"><span class="small muted">{GROUP_LABEL[g]}</span>
                  {base.palette.filter((p) => baseGroups.groups[p.hex] === g).map((p) => <span class="ws-swatch" title={p.hex} style={{ background: p.hex }} />)}
                </div>
              ))}
            </div>
          </div>
          <div class="toolbar">
            <label>动作
              <select value={actionName} onChange={(e) => setActionName((e.target as HTMLSelectElement).value)}>
                {actions.map(({ f, a }) => <option value={a.name}>{f.family} · {a.name} · {a.totalFrames} 帧</option>)}
              </select>
            </label>
            <label class="check small"><input type="checkbox" checked={allActions} onChange={(e) => setAllActions((e.target as HTMLInputElement).checked)} />全部动作一起播</label>
            <button onClick={() => setPlaying(!playing)}>{playing ? "暂停" : "播放"}</button>
          </div>
          {fam.error ? <Notice kind="error">{fam.error}</Notice> : null}
          <div class="ws-compare-grid">
            {shown.map(({ f, a }) => (
              <div class="ws-pair">
                <div class="small"><strong>{a.name}</strong> <span class="muted">{f.family}</span></div>
                <div class="ws-pair-stages">
                  <ActionStage family={f} sheet={fam.sheets[f.family]} action={a} tick={tick} zoom={allActions ? 2 : 4} label="母本" crop={crops[f.family]} />
                  <ActionStage family={f} sheet={remapped[f.family]} action={a} tick={tick} zoom={allActions ? 2 : 4} label="映射后" crop={crops[f.family]} />
                </div>
              </div>
            ))}
          </div>
          <div class="save-row">
            <button onClick={() => run(true)} disabled={busy !== null || !drafts.hasToken()}>{busy === "check" ? "检查中……" : "检查（不写草稿）"}</button>
            <button class="primary" onClick={() => run(false)} disabled={busy !== null || !drafts.hasToken()}>
              {busy === "save" ? "保存中……" : "保存到草稿（替换这个角色的整套小人）"}</button>
          </div>
          {result ? (
            <section class="pixel-check">
              <h4>{result.dryRun ? "检查结果" : "已写入"}</h4>
              {result.families.map((f) => (
                <div>
                  <p class="small"><strong>{f.family === "pixelart" ? "基础动作" : "特殊动作"}</strong>：改了 {f.changedPixels} 个像素，颜色表用上 {f.mappingUsed}/{f.mappingSize} 色，图集 {f.sheet.join("×")}
                    <InfoTip text={`atlas 改名 ${f.renamedEntries} 条（${f.family}）`} /></p>
                  <ChecksList checks={f.checks} empty="没有提示。" />
                </div>
              ))}
            </section>
          ) : null}
        </>
      ) : baseId ? <div class="loading">正在拆解母本……</div> : null}
    </div>
  );
}
