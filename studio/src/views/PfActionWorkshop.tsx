// 强化弹射动作工坊：列出可作母本的 PF 动作（CDN / APK 内置）→ 看三档详情 → 新键（实时查重）、属性、
// 统一或逐档缩放、可选特效族映射 → 预检（依赖、表规划、五态检查）→ 写入草稿；下方列出本角色草稿里已有的 PF 键，
// 供召唤工坊的 wfx_ball_pf_action_<球> 引用。接口：docs/studio/pf-actions.md。
import { useEffect, useMemo, useRef, useState } from "preact/hooks";
import { api, CharacterDetail, drafts, onDraftChange, RuleResult } from "../api";
import { useClientProfile } from "../clientProfile";
import {
  PF_EFFECT_TARGET, PF_ELEMENTS, PF_KEY, pfActions, PfCloneRequest, PfCloneResult, PfDetail, PfDraftKey, PfElement, PfLevelDetail, PfList,
} from "../pfApi";
import { ElementBadge, Notice } from "./common";
import { InfoTip } from "./Delivery";
import { RuleList } from "./rules";
import "./boss/boss.css";
import "./skillpf.css";

const SOURCE_LABEL: Record<string, string> = { cdn: "CDN", bundled: "APK 内置" };
const nominal = (v: number | null) => (v === null ? "不可静态求和" : `×${Math.round(v * 1000) / 1000}`);

function termsText(terms: { min?: number; max?: number }[]): string {
  return terms.map((t) => (t.min === t.max ? String(t.max) : `${t.min}–${t.max}`)).join(" + ");
}

export function PfActionWorkshop({ characterId }: { characterId: string }) {
  const profile = useClientProfile();
  const clientProfile = profile.selected;
  const [character, setCharacter] = useState<CharacterDetail | null>(null);
  const [source, setSource] = useState("");
  const [detail, setDetail] = useState<PfDetail | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [newKey, setNewKey] = useState("");
  const [element, setElement] = useState<PfElement | "">("");
  const [perLevel, setPerLevel] = useState(false);
  const [scale, setScale] = useState(["1", "1", "1"]);
  const [effects, setEffects] = useState<Record<string, string>>({});
  const [preview, setPreview] = useState<{ key: string; result: PfCloneResult } | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [written, setWritten] = useState<PfCloneResult | null>(null);
  const [draftKeys, setDraftKeys] = useState<PfDraftKey[] | null>(null);
  const [draftKeysError, setDraftKeysError] = useState<string | null>(null);

  useEffect(() => { api.character(characterId).then(setCharacter, () => setCharacter(null)); }, [characterId]);
  useEffect(() => {
    const load = () => pfActions.draftKeys(characterId).then((r) => { setDraftKeys(r.items); setDraftKeysError(null); },
      (e: Error) => setDraftKeysError(e.message));
    load();
    return onDraftChange((cid) => { if (cid === characterId) load(); });
  }, [characterId]);

  useEffect(() => {
    if (!source) { setDetail(null); return; }
    let live = true;
    setDetail(null); setDetailError(null);
    pfActions.detail(source, clientProfile).then((d) => { if (live) setDetail(d); }, (e: Error) => { if (live) setDetailError(e.message); });
    return () => { live = false; };
  }, [source, clientProfile]);

  const families = useMemo(() => [...new Set((detail?.levels ?? []).flatMap((l) => l.effectFamilies))].sort(), [detail]);
  const keyCheck = useKeyCheck(newKey, clientProfile);

  // ---- request + client-side problems
  const problems: string[] = [];
  if (!source) problems.push("先选母本 PF 动作");
  else if (detail && !detail.selectable) problems.push("母本不可选");
  if (!PF_KEY.test(newKey)) problems.push("新键只用小写字母开头的 a–z、0–9、_，最长 80");
  else if (newKey === source) problems.push("新键不能和母本键相同");
  else if (keyCheck?.key === newKey && keyCheck.hit) problems.push(`新键 ${newKey} 已在${SOURCE_LABEL[keyCheck.hit.source] ?? keyCheck.hit.source}里`);
  else if (draftKeys?.some((d) => d.key === newKey)) problems.push(`本角色草稿已有 PF 键 ${newKey}（要改请先撤销那一项）`);
  if (!element) problems.push("选一个属性");
  const scales = (perLevel ? scale : [scale[0]]).map(Number);
  if (scales.some((s, i) => !(perLevel ? scale[i] : scale[0]).trim() || !Number.isFinite(s) || s <= 0)) problems.push("缩放系数要是正数");
  const effectMap: Record<string, string> = {};
  for (const family of families) {
    const target = (effects[family] ?? "").trim();
    if (!target) continue;
    if (!PF_EFFECT_TARGET.test(target)) problems.push(`特效映射 ${family}：目标要在 battle/effect/skill_unique/ 下`);
    else effectMap[family] = target;
  }
  const request: PfCloneRequest = {
    key: newKey, source, element: (element || "火") as PfElement,
    scale: perLevel ? (scales as [number, number, number]) : scales[0],
    ...(Object.keys(effectMap).length ? { effects: effectMap } : {}),
  };
  const key = JSON.stringify([request, clientProfile]);
  const fresh = preview?.key === key ? preview.result : null;
  useEffect(() => {
    if (problems.length || !detail || fresh) return;
    let live = true;
    setPreviewing(true);
    const timer = window.setTimeout(() => {
      pfActions.preview(characterId, request, clientProfile).then((r) => { if (live) setPreview({ key, result: r }); })
        .finally(() => { if (live) setPreviewing(false); });
    }, 400);
    return () => { live = false; window.clearTimeout(timer); };
  }, [key, problems.length, !!detail]);

  const write = async () => {
    if (problems.length || !fresh?.ok) return;
    setBusy(true);
    try {
      const r = await pfActions.clone(characterId, request, clientProfile);
      setWritten(r);
      if (r.ok) setPreview(null);
    } finally { setBusy(false); }
  };

  return (
    <section class="page skillpf-page pf-workshop-page">
      <div class="page-head">
        <div>
          <h1>强化弹射动作工坊{character ? <span class="muted"> · {character.name} <span class="mono small">{characterId}</span></span> : null}</h1>
          <p class="muted">把一个 PF 动作的三档克隆为新键：换属性、缩放倍率、可替换特效族引用。每次写入新增一项；已有键不能覆盖，要改先撤销再重做。
            目标客户端：<strong>{profile.label(clientProfile)}</strong>（页面顶部切换）。</p>
        </div>
      </div>
      <div class="skillpf-layout">
        <PfPicker selected={source} onPick={(k) => { setSource(k); setEffects({}); setWritten(null); }} profile={clientProfile} />
        <div class="skillpf-main">
          {!source ? <Notice>从左侧选一个 PF 动作作母本。</Notice>
            : detailError ? <Notice kind="error">母本详情读取失败：{detailError}</Notice>
            : !detail ? <div class="loading">正在读取三档详情……</div>
            : (
              <>
                <PfDetailView detail={detail} />
                <section class="boss-block">
                  <h3>新 PF 动作</h3>
                  <div class="param-fields">
                    <label class="param-field"><span>新键</span>
                      <input class="mono" value={newKey} placeholder="例如 workshop_dark_pf" onInput={(e) => setNewKey((e.target as HTMLInputElement).value.trim())} />
                      <KeyStatus value={newKey} source={source} check={keyCheck} draftKeys={draftKeys} /></label>
                    <label class={"param-field" + (element ? " changed" : "")}><span>属性</span>
                      <select value={element} onChange={(e) => setElement((e.target as HTMLSelectElement).value as PfElement | "")}>
                        <option value="">请选择</option>
                        {PF_ELEMENTS.map((name) => <option value={name}>{name}</option>)}
                      </select>
                      <span class="small muted">{element ? <>写成 DSL 显式元素码 {PF_ELEMENTS.indexOf(element) + 1} <ElementBadge element={element} /></> : "命中项改成这个属性"}</span></label>
                  </div>
                  <fieldset class="param-field wide">
                    <legend>倍率缩放 <InfoTip text="在每个命中项系数上逐项相乘，保留各档分段与相对比例；时间、循环、结束通知与 Lv3 判定标记不变。" /></legend>
                    <span>
                      <label class="check"><input type="radio" checked={!perLevel} onChange={() => setPerLevel(false)} />三档统一</label>{" "}
                      <label class="check"><input type="radio" checked={perLevel} onChange={() => setPerLevel(true)} />逐档</label>
                    </span>
                    <div class="sp-scale-row">
                      {(perLevel ? [0, 1, 2] : [0]).map((i) => (
                        <label class="param-field"><span>{perLevel ? `Lv${i + 1} ×` : "×"}</span>
                          <input type="number" min="0" step="0.05" value={scale[i]}
                            onInput={(e) => setScale(scale.map((s, j) => (j === i ? (e.target as HTMLInputElement).value : s)))} />
                          <span class="small muted">{detail.levels[i] ? `名义 ${nominal(detail.levels[i].nominalMultiplier)}` : ""}
                            {detail.levels[i]?.nominalMultiplier != null && Number(scale[i]) > 0 && perLevel ? ` → ×${Math.round(detail.levels[i].nominalMultiplier! * Number(scale[i]) * 1000) / 1000}` : ""}</span></label>
                      ))}
                    </div>
                  </fieldset>
                  <fieldset class="param-field wide">
                    <legend>特效族映射（可选）<InfoTip text="只换引用，不生成素材、不覆盖共享特效；目标族必须已存在于 battle/effect/skill_unique/ 下并有可用资源。留空 = 沿用母本特效。" /></legend>
                    {families.length ? (
                      <div class="sp-effect-map">
                        {families.map((f) => (
                          <>
                            <span class="mono small">{f}</span><span>→</span>
                            <input class="mono" value={effects[f] ?? ""} placeholder="留空沿用"
                              onInput={(e) => setEffects({ ...effects, [f]: (e.target as HTMLInputElement).value })} />
                          </>
                        ))}
                      </div>
                    ) : <span class="small muted">母本没有可映射的特效族。</span>}
                  </fieldset>
                </section>
                <section class="boss-block">
                  <h3>预检与写入 <InfoTip text="POST …/pf-action?preview=true：同一套检查，不写草稿、不预留键。写入时后端重新核对占用，预检后被别的草稿占用也会被拒绝。" /></h3>
                  {problems.length ? <ul class="inline-problems">{problems.map((p) => <li>{p}</li>)}</ul>
                    : previewing && !fresh ? <p class="small muted">预检中……</p>
                    : fresh ? <PfResultView result={fresh} title={fresh.ok ? "预检结果" : "预检被拒绝"} />
                    : <p class="small muted">等待预检……</p>}
                  {written && !written.ok ? <PfResultView result={written} title="写入被拒绝" /> : null}
                  {written?.ok ? (
                    <Notice kind={written.buildable ? "info" : "warn"}>已写入草稿：新 PF 键 <strong class="mono">{written.key}</strong>（{written.status?.label ?? "未保存"}）。
                      到「本次修改」保存后照常生成；设备战斗与特效验证：{written.runtime}。</Notice>
                  ) : null}
                  <div class="save-row">
                    <button type="button" class="primary" disabled={busy || problems.length > 0 || !fresh?.ok || !drafts.hasToken()} onClick={write}
                      title={!drafts.hasToken() ? "没有编辑令牌，只读" : !fresh ? "等预检跑完" : !fresh.ok ? "预检被拒绝，不能写入" : ""}>
                      {busy ? "写入中……" : "写入草稿（新增一项）"}</button>
                    <span class="small muted">{problems.length ? problems[0] : !fresh ? "预检后可写入" : fresh.ok ? (fresh.buildable ? "预检没有阻断项" : "预检有阻断项，写入后仍不能生成") : "预检被拒绝"}</span>
                  </div>
                </section>
              </>
            )}
          <DraftKeys cid={characterId} items={draftKeys} error={draftKeysError} />
        </div>
      </div>
    </section>
  );
}

// ------------------------------------------------------------------------------ list

function PfPicker({ selected, onPick, profile }: { selected: string; onPick: (key: string) => void; profile: string | null }) {
  const [query, setQuery] = useState("");
  const [list, setList] = useState<PfList | null>(null);
  const [error, setError] = useState<string | null>(null);
  const seq = useRef(0);
  useEffect(() => {
    const mine = ++seq.current;
    const timer = window.setTimeout(() => {
      pfActions.list(query, profile).then((r) => { if (mine === seq.current) { setList(r); setError(null); } },
        (e: Error) => { if (mine === seq.current) setError(e.message); });
    }, 250);
    return () => window.clearTimeout(timer);
  }, [query, profile]);
  return (
    <nav class="skillpf-side" aria-label="PF 母本">
      <input class="search small-search" type="search" value={query} placeholder="按键名搜索，如 special"
        onInput={(e) => setQuery((e.target as HTMLInputElement).value)} />
      {error ? <Notice kind="error">母本列表读取失败：{error}</Notice> : null}
      {list && !list.bundledAvailable ? (
        <Notice kind="warn">没有可读的目标 APK：只列出当前视图 CDN 里的 PF 动作；knight / fighter / ranged / supporter 等标准动作可能只在 APK 内置表里。
          内置表查重<strong>未执行</strong>。请在本机 client_apks 配置里为所选目标客户端指定 APK。</Notice>
      ) : null}
      {list?.warnings.length ? <ul class="small warn-text">{list.warnings.map((w) => <li>{w}</li>)}</ul> : null}
      {!list && !error ? <p class="small muted">正在读取 PF 动作……</p> : null}
      <ul>
        {(list?.items ?? []).map((item) => (
          <li><button type="button" class={"source-option" + (item.key === selected ? " on" : "")} disabled={!item.selectable}
            title={item.error ?? ""} onClick={() => onPick(item.key)}>
            <span class="sp-line"><strong class="mono">{item.key}</strong>
              <span class="tag">{SOURCE_LABEL[item.source] ?? item.source}</span>
              {item.type !== item.key ? <span class="small muted">{item.type === "custom" ? "自定义" : item.type}</span> : null}</span>
            {item.selectable ? (
              <span class="sp-line small muted">{item.levels.map((l) => `Lv${l.level} ${nominal(l.nominalMultiplier)}`).join(" · ")}</span>
            ) : <span class="sp-line small error-text">不可选：{item.error ?? "解析失败"}</span>}
          </button></li>
        ))}
      </ul>
      {list && !list.items.length ? <p class="small muted">没有匹配的 PF 动作。</p> : null}
      <p class="small muted">名义倍率是静态系数摘要，不是实战总伤害；实际命中数受分段、碰撞和战斗条件影响。</p>
    </nav>
  );
}

// ------------------------------------------------------------------------------ detail

function LevelTable({ levels }: { levels: PfLevelDetail[] }) {
  return (
    <div class="sp-levels">
      {levels.map((level) => (
        <div class="sp-level">
          <h4>Lv{level.level} <span class="small muted">名义 {nominal(level.nominalMultiplier)}</span></h4>
          <p class="mono small muted">{level.path}</p>
          <p class="small">命中项 {level.hitCount} · 判定区 {level.hitAreaCount}
            <InfoTip text="命中项 = CreateNormalAttack 节点数，判定区 = CreateHitArea 节点数；都不是实战累计命中次数。" /></p>
          {level.nominalNote ? <p class="small muted">{level.nominalNote}</p> : null}
          <table class="boss-table">
            <thead><tr><th>#</th><th>元素码</th><th>系数</th></tr></thead>
            <tbody>{level.coefficients.map((c) => (
              <tr><td class="small">{c.index}</td><td class="small">{c.elementCode === 255 ? "255 继承" : c.elementCode ?? "—"}</td>
                <td class="sp-coef" title={JSON.stringify(c.terms)}>{termsText(c.terms)}</td></tr>
            ))}</tbody>
          </table>
          {level.effectFamilies.length ? <p class="small">特效族：<span class="mono">{level.effectFamilies.join("、")}</span></p> : null}
          {level.markers.length ? (
            <details class="tech"><summary>判定标记（{level.markers.length}）</summary>
              <pre class="small mono">{JSON.stringify(level.markers)}</pre></details>
          ) : null}
        </div>
      ))}
    </div>
  );
}

function PfDetailView({ detail }: { detail: PfDetail }) {
  return (
    <section class="boss-block">
      <h3>母本 <span class="mono">{detail.key}</span> <span class="tag">{SOURCE_LABEL[detail.source] ?? detail.source}</span>
        <span class="small muted">{detail.type === "custom" ? "自定义类型" : `类型 ${detail.type}`}</span></h3>
      {detail.warnings.length ? <ul class="small warn-text">{detail.warnings.map((w) => <li>{w}</li>)}</ul> : null}
      <LevelTable levels={detail.levels} />
    </section>
  );
}

// ------------------------------------------------------------------------------ key check

interface KeyCheckState { key: string; hit: { source: string } | null; bundledAvailable: boolean; error?: string }

/** Exact-match lookup in the template list (view CDN + target APK bundled); draft reservations are checked by the backend. */
function useKeyCheck(value: string, profile: string | null): KeyCheckState | null {
  const [state, setState] = useState<KeyCheckState | null>(null);
  useEffect(() => {
    if (!PF_KEY.test(value)) { setState(null); return; }
    let live = true;
    const timer = window.setTimeout(() => {
      pfActions.list(value, profile).then((r) => {
        const hit = r.items.find((i) => i.key === value);
        if (live) setState({ key: value, hit: hit ? { source: hit.source } : null, bundledAvailable: r.bundledAvailable });
      }, (e: Error) => { if (live) setState({ key: value, hit: null, bundledAvailable: false, error: e.message }); });
    }, 300);
    return () => { live = false; window.clearTimeout(timer); };
  }, [value, profile]);
  return state;
}

function KeyStatus({ value, source, check, draftKeys }: { value: string; source: string; check: KeyCheckState | null; draftKeys: PfDraftKey[] | null }) {
  const fresh = check?.key === value ? check : null;
  return (
    <span class="small">
      {!value ? <span class="muted">必填；输入后查视图与 APK 内置键</span>
        : !PF_KEY.test(value) ? <span class="error-text">格式：小写字母开头，只用 a–z、0–9、_</span>
        : value === source ? <span class="error-text">不能和母本键相同</span>
        : !fresh ? <span class="muted">查询占用……</span>
        : fresh.error ? <span class="error-text">查询失败：{fresh.error}</span>
        : fresh.hit ? <span class="error-text">已占用：{SOURCE_LABEL[fresh.hit.source] ?? fresh.hit.source} 里已有这个键，后端会拒绝（不覆盖、不自动改名）</span>
        : draftKeys?.some((d) => d.key === value) ? <span class="error-text">本角色草稿已有这个 PF 键</span>
        : <>
            <span class="state-ok">当前视图没有{fresh.bundledAvailable ? "，APK 内置表也没有" : ""}</span>
            {fresh.bundledAvailable ? null : <span class="warn-text">；APK 内置表未查（没有可读 APK）</span>}
            <span class="muted">；其他草稿的预留在预检时检查</span>
          </>}
    </span>
  );
}

// ------------------------------------------------------------------------------ result

function PfResultView({ result, title }: { result: PfCloneResult; title: string }) {
  return (
    <div class="sp-result">
      {!result.ok ? <Notice kind="error"><strong>{title}</strong>{result.error ? `：${result.error}` : ""}</Notice> : (
        <p class={"small " + (result.buildable ? "state-ok" : "warn-text")}>
          {result.buildable ? "预检没有阻断项（本地静态检查；交付时还会跑 bundle-check / key-diff）。" : "预检有阻断项：见下方检查，写入后生成会被拦下。"}
          <span class="muted"> 设备实测：{result.runtime}</span></p>
      )}
      <RuleList checks={result.checks as RuleResult[]} title="检查" />
      {result.warnings?.length ? <ul class="small warn-text">{result.warnings.map((w) => <li>{w}</li>)}</ul> : null}
      {result.ok ? (
        <>
          <dl class="kv">
            <dt>母本 → 新键</dt><dd class="mono">{result.source}（{SOURCE_LABEL[result.sourceKind ?? ""] ?? result.sourceKind}）→ {result.key}</dd>
            <dt>属性</dt><dd>{result.element ? <ElementBadge element={result.element} /> : null} 显式元素码 {result.elementCode}</dd>
            <dt>缩放</dt><dd>{(result.scale ?? []).map((s, i) => `Lv${i + 1} ×${s}`).join(" · ")}</dd>
          </dl>
          {result.levels?.length ? <LevelTable levels={result.levels} /> : null}
          {result.tables?.length ? (
            <>
              <h4>共享表写入规划</h4>
              <ul class="small">{result.tables.map((t) => <li><span class="mono">{t.logical}</span> 新增 <span class="mono">{t.addedKeys.join("、")}</span></li>)}</ul>
            </>
          ) : null}
          {result.dependencies?.length ? (
            <>
              <h4>预载依赖（{result.dependencies.length}）<InfoTip text="需要随调用场景预载的输入清单；不能据此推断目标客户端已加载这些资源。缺少必需资源时后端直接拒绝，不会列出假装可用的缺失项。" /></h4>
              <div class="table-scroll">
                <table class="boss-table">
                  <thead><tr><th>类型</th><th>路径</th><th>必需</th><th>状态</th></tr></thead>
                  <tbody>{result.dependencies.map((d) => (
                    <tr><td class="small">{d.kind}</td><td class="mono small">{d.root}/{d.logical}</td><td class="small">{d.required ? "是" : "可选"}</td>
                      <td class="small" title={d.sha256 ?? ""}>{d.status === "existing" ? "已读到" : d.status === "compiled_reference" ? "本次生成的私有引用" : d.status}</td></tr>
                  ))}</tbody>
                </table>
              </div>
              <p class="small muted">隐式命中特效、flatomo 嵌套 MovieClip 和运行时动态资源不在清单里，仍需冷缓存设备验收。</p>
            </>
          ) : null}
          {result.files?.length ? (
            <details class="tech"><summary>产物规划（{result.files.length}）{result.preview ? " · 预检未落盘" : ""}</summary>
              <ul class="small mono">{result.files.map((f) => <li>{f.root}/{f.logical} · {f.size} B · {f.sha256.slice(0, 12)}</li>)}</ul></details>
          ) : null}
        </>
      ) : null}
    </div>
  );
}

// ------------------------------------------------------------------------------ draft keys

function DraftKeys({ cid, items, error }: { cid: string; items: PfDraftKey[] | null; error: string | null }) {
  const [busy, setBusy] = useState<string | null>(null);
  const [revertError, setRevertError] = useState<string | null>(null);
  const [copied, setCopied] = useState<string | null>(null);
  const revert = async (item: PfDraftKey) => {
    if (!window.confirm(`撤销 PF 键 ${item.key} 这一项改动？召唤工坊里引用它的地方需要另行修改。`)) return;
    setBusy(item.changeId); setRevertError(null);
    try { await drafts.revert(cid, item.changeId); }
    catch (e) { setRevertError((e as Error).message); }
    finally { setBusy(null); }
  };
  const copy = (text: string) => {
    navigator.clipboard?.writeText(text).then(() => { setCopied(text); window.setTimeout(() => setCopied(null), 1500); }, () => setCopied(null));
  };
  return (
    <section class="boss-block">
      <h3>本角色草稿里的 PF 键 {items ? <span class="count">{items.length}</span> : null}
        <InfoTip text="GET /api/drafts/<cid>/pf-actions：只读本角色草稿。召唤工坊的 wfx_ball_pf_action_<球> 填「引用值」；使用时必须一起编译本角色草稿里的 PF 改动。" /></h3>
      {error ? <Notice kind="error">读取失败：{error}</Notice> : null}
      {!items && !error ? <p class="small muted">读取中……</p> : null}
      {items && !items.length ? <p class="small muted">还没有 PF 改动。</p> : null}
      {items?.length ? (
        <table class="boss-table sp-keys">
          <thead><tr><th>引用值</th><th>母本</th><th>属性</th><th>状态</th><th /></tr></thead>
          <tbody>{items.map((item) => (
            <tr>
              <td class="mono">{item.reference} <button type="button" class="link small" onClick={() => copy(item.reference)}>{copied === item.reference ? "已复制" : "复制"}</button></td>
              <td class="mono small">{item.source}</td>
              <td>{(PF_ELEMENTS as readonly string[]).includes(item.element) ? <ElementBadge element={item.element} /> : item.element}</td>
              <td class="small" title="只说明有本地制作记录；不是已投递，也没有设备验证">仅草稿</td>
              <td><button type="button" class="ghost small-btn" disabled={busy !== null || !drafts.hasToken()} onClick={() => revert(item)}>
                {busy === item.changeId ? "撤销中……" : "撤销"}</button></td>
            </tr>
          ))}</tbody>
        </table>
      ) : null}
      {revertError ? <p class="small error-text">撤销失败：{revertError}</p> : null}
    </section>
  );
}
