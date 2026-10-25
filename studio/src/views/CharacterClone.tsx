// 从母本克隆新角色：母本搜索 → 新 ID（实时查占用 / 取下一个空闲）→ 代码名与显示名 → 元素与技能策略 → 确认写入。
// 后端没有预检：写入前列出会改的表（契约清单），写入后显示真实的 37 项资产状态与检查，再进入新角色页。
// 同一个 PromoteForm 也用于草稿角色页的「升级为正式角色」。
import { useEffect, useMemo, useState } from "preact/hooks";
import { api, CharacterSummary, drafts } from "../api";
import { href } from "../router";
import { CharacterCloneResult, CLONE_ELEMENTS, CLONE_TABLES, CloneAsset, studio } from "../studioApi";
import { ChecksList } from "./Changes";
import { Avatar, ElementBadge, Notice, Rarity } from "./common";
import { InfoTip } from "./Delivery";
import { IdField } from "./IdTools";

const CODE = /^[a-z0-9_]+$/;
const STEPS = ["母本", "新 ID 与代码名", "元素与技能", "确认"];
const ASSET_CLASS: Record<string, string> = { reuse: "muted", pending: "warn-text", derived: "state-ok" };

export function CloneAssetList({ assets }: { assets: CloneAsset[] }) {
  const counts = assets.reduce<Record<string, number>>((m, a) => ({ ...m, [a.status]: (m[a.status] ?? 0) + 1 }), {});
  return (
    <div class="clone-assets">
      <p class="small">必需资产 {assets.length} 项：复用母本 {counts.reuse ?? 0} · <span class="warn-text">待替换 {counts.pending ?? 0}</span> · <span class="state-ok">已派生 {counts.derived ?? 0}</span></p>
      <div class="table-scroll">
        <table class="boss-table">
          <thead><tr><th>状态</th><th>资产</th><th>根</th><th>来源</th></tr></thead>
          <tbody>{assets.map((a) => (
            <tr><td class={ASSET_CLASS[a.status] ?? ""}>{a.label}</td><td class="mono small">{a.logical}</td><td class="small">{a.root}</td>
              <td class="mono small">{a.source}</td></tr>
          ))}</tbody>
        </table>
      </div>
    </div>
  );
}

/** Written result: checks, buildable, the 37 assets and where to go next. */
function CloneDone({ result }: { result: CharacterCloneResult }) {
  const files = result.changeset.changes.flatMap((c) => c.files.map((f) => f.logical));
  return (
    <div class="clone-done">
      <Notice kind={result.buildable ? "info" : "warn"}>
        已写入草稿 <strong class="mono">{result.characterId}</strong>（{result.code}，{result.status.label}）。
        {result.buildable ? "检查没有错误；到角色页「本次修改」保存后可以生成。" : "还有错误或资产未齐：可以继续在立绘 / 像素 / 语音里替换，生成会阻断直到补齐。"}
        {" "}<a href={href({ work: "content", shop: "characters", id: result.characterId })}>打开新角色页 →</a>
      </Notice>
      <ChecksList checks={result.checks} empty="克隆检查没有提醒。" />
      <CloneAssetList assets={result.assets} />
      {files.length ? (
        <details class="tech"><summary>草稿里实际写的文件（{files.length}）</summary>
          <ul class="small mono">{files.map((f) => <li>{f}</li>)}</ul></details>
      ) : null}
    </div>
  );
}

export function CharacterCloneWizard({ source }: { source?: string }) {
  const [list, setList] = useState<CharacterSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [step, setStep] = useState(source ? 1 : 0);
  const [from, setFrom] = useState(source ?? "");
  const [query, setQuery] = useState("");
  const [to, setTo] = useState("");
  const [toFree, setToFree] = useState<boolean | null>(null);
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [element, setElement] = useState("");
  const [skill, setSkill] = useState<"copy" | "reuse">("copy");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [result, setResult] = useState<CharacterCloneResult | null>(null);
  useEffect(() => { api.characters().then((d) => setList(d.characters), (e: Error) => setError(e.message)); }, []);
  const donor = list?.find((c) => c.id === from) ?? null;
  const hits = useMemo(() => {
    const terms = query.trim().toLowerCase().split(/\s+/).filter(Boolean);
    return (list ?? []).filter((c) => terms.every((t) => [c.id, c.name, c.title ?? "", c.code].join(" ").toLowerCase().includes(t))).slice(0, 60);
  }, [list, query]);

  const problems: string[] = [];
  if (!from) problems.push("先选母本");
  else if (list && !donor) problems.push(`母本 ${from} 不在当前视图的角色表里`);
  if (!/^[1-9][0-9]*$/.test(to)) problems.push("新 ID 要是正整数");
  else if (toFree === false) problems.push(`新 ID ${to} 已被占用`);
  if (!CODE.test(code)) problems.push("代码名只用小写字母、数字和下划线");
  if (name.length > 80) problems.push("显示名最多 80 字");

  const write = async () => {
    if (problems.length) return;
    setBusy(true); setMessage(null);
    try {
      setResult(await studio.cloneCharacter({
        from, to, code, skill, ...(element !== "" ? { element: Number(element) } : {}), ...(name.trim() ? { name: name.trim() } : {}),
      }));
    } catch (e) { setMessage((e as Error).message); }
    finally { setBusy(false); }
  };

  return (
    <section class="page clone-character">
      <a class="back" href={href({ work: "content", shop: "characters" })}>← 全部角色</a>
      <div class="page-head">
        <div>
          <h1>从母本克隆新角色</h1>
          <p class="muted">新 ID 的标准角色草稿：表行、玛纳板、语音字幕与 37 项资产引用来自母本；机制（技能 DSL、队长技、能力）复用母本，之后在角色页替换立绘、像素和语音。</p>
        </div>
      </div>
      {error ? <Notice kind="error">角色列表读取失败：{error}</Notice> : null}
      {result ? <CloneDone result={result} /> : (
        <section class="boss-block clone-wizard">
          <ol class="wizard-steps">
            {STEPS.map((s, i) => <li class={i === step ? "on" : i < step ? "done" : ""}><button type="button" class="link" onClick={() => setStep(i)}>{i + 1}. {s}</button></li>)}
          </ol>
          {donor ? (
            <p class="clone-donor"><Avatar id={donor.id} element={donor.element} size={32} /> 母本：<strong>{donor.name}</strong>
              <span class="muted"> {donor.title}</span> <span class="mono small">{donor.id}</span> <ElementBadge element={donor.element} /> <Rarity value={donor.rarity} /></p>
          ) : null}
          {step === 0 ? (
            <div>
              <input class="search small-search" type="search" value={query} autoFocus placeholder="搜索母本：名字、称号、ID、代码名"
                onInput={(e) => setQuery((e.target as HTMLInputElement).value)} />
              {!list ? <p class="small muted">正在读取角色……</p> : (
                <ul class="clone-donors">
                  {hits.map((c) => (
                    <li><button type="button" class={"source-option" + (c.id === from ? " on" : "")} onClick={() => { setFrom(c.id); setStep(1); }}>
                      <Avatar id={c.id} element={c.element} size={28} />
                      <span>{c.name} <span class="small muted">{c.title} · <span class="mono">{c.id}</span> · {c.code}</span></span>
                    </button></li>
                  ))}
                </ul>
              )}
            </div>
          ) : step === 1 ? (
            <div class="param-fields">
              <IdField kind="character" label="新角色 ID" value={to} onChange={setTo} placeholder="例如 199000" onAvailability={setToFree} />
              <label class="param-field"><span>代码名（code）</span>
                <input class="mono" value={code} placeholder="new_character" onInput={(e) => setCode((e.target as HTMLInputElement).value.trim())} />
                <span class="small muted">只用 a–z、0–9、_；语音和资源路径会改成这个名字，碰撞由后端写入时检查</span></label>
              <label class="param-field"><span>显示名</span>
                <input value={name} placeholder={donor?.name ?? "留空沿用母本"} onInput={(e) => setName((e.target as HTMLInputElement).value)} /></label>
            </div>
          ) : step === 2 ? (
            <div class="param-fields">
              <label class="param-field"><span>元素</span>
                <select value={element} onChange={(e) => setElement((e.target as HTMLSelectElement).value)}>
                  <option value="">沿用母本{donor ? `（${donor.element}）` : ""}</option>
                  {CLONE_ELEMENTS.map((e, i) => <option value={String(i)}>{e}</option>)}
                </select>
                <span class="small muted">改元素会按 item 表换玛纳材料，但不改复用技能 / 能力里写死的元素效果</span></label>
              <label class="param-field"><span>稀有度</span>
                <span>{donor ? <Rarity value={donor.rarity} /> : "—"} <span class="small muted">沿用母本（克隆接口不改稀有度）</span></span></label>
              <fieldset class="param-field wide">
                <legend>技能</legend>
                <label class="check"><input type="radio" checked={skill === "copy"} onChange={() => setSkill("copy")} />复制为独立 action_skill 键（默认）</label>
                <label class="check"><input type="radio" checked={skill === "reuse"} onChange={() => setSkill("reuse")} />直接复用母本技能键</label>
              </fieldset>
            </div>
          ) : (
            <div>
              <dl class="kv alloc">
                <dt>母本</dt><dd>{donor ? `${donor.name} · ${donor.id}` : from || "—"}</dd>
                <dt>新 ID</dt><dd class="mono">{to || "—"}</dd>
                <dt>代码名</dt><dd class="mono">{code || "—"}</dd>
                <dt>显示名</dt><dd>{name.trim() || "沿用母本"}</dd>
                <dt>元素</dt><dd>{element === "" ? "沿用母本" : CLONE_ELEMENTS[Number(element)]}</dd>
                <dt>技能</dt><dd>{skill === "copy" ? "复制为新键" : "复用母本键"}</dd>
              </dl>
              <h4>会写的表 <InfoTip text="克隆接口没有预检：这是契约里的清单；写入后显示草稿实际写的文件和 37 项资产状态。" /></h4>
              <p class="small mono">{CLONE_TABLES.required.join("、")}{skill === "copy" ? "、action_skill（新键）" : ""}</p>
              <p class="small muted">母本有行时同步：<span class="mono">{CLONE_TABLES.optional.join("、")}</span>。玛纳节点按「新 ID × 2」重编号。</p>
              <p class="small muted">资产 37 项先标「复用母本」或「待替换」；在角色页替换立绘后会派生 30 项，状态改为「已派生」。</p>
            </div>
          )}
          {problems.length && step === STEPS.length - 1 ? <ul class="inline-problems">{problems.map((p) => <li>{p}</li>)}</ul> : null}
          {message ? <Notice kind="error">写入失败：{message}</Notice> : null}
          <div class="save-row">
            <button type="button" disabled={step === 0} onClick={() => setStep(step - 1)}>上一步</button>
            {step < STEPS.length - 1 ? <button type="button" onClick={() => setStep(step + 1)}>下一步</button> : (
              <button type="button" class="primary" disabled={busy || problems.length > 0 || !drafts.hasToken()} onClick={write}>
                {busy ? "写入中……" : "写入草稿"}</button>
            )}
            <span class="small muted">{problems.length ? problems[0] : "可以写入"}</span>
          </div>
        </section>
      )}
    </section>
  );
}

/** 「升级为正式角色」 on a scratch page: new ID + code (default = placeholder without scratch_). */
export function PromoteForm({ sid, code: placeholder, onClose }: { sid: string; code: string; onClose: () => void }) {
  const [to, setTo] = useState("");
  const [free, setFree] = useState<boolean | null>(null);
  const [code, setCode] = useState(placeholder.replace(/^scratch_/, ""));
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [result, setResult] = useState<CharacterCloneResult | null>(null);
  const problems: string[] = [];
  if (!/^[1-9][0-9]*$/.test(to)) problems.push("新 ID 要是正整数");
  else if (free === false) problems.push(`新 ID ${to} 已被占用`);
  if (!CODE.test(code)) problems.push("代码名只用小写字母、数字和下划线");
  const run = async () => {
    setBusy(true); setMessage(null);
    try { setResult(await studio.promoteScratch(sid, { to, code })); } catch (e) { setMessage((e as Error).message); } finally { setBusy(false); }
  };
  if (result) return <div class="param-block"><CloneDone result={result} /></div>;
  return (
    <div class="param-block pending-block">
      <h4>升级为正式角色 <button type="button" class="link close-x" onClick={onClose} aria-label="关闭">×</button></h4>
      <p class="small muted">先从母本克隆新 ID，再把这里的像素改动整套迁过去；原草稿角色保留并记录绑定，不能再升级一次。失败会回滚新角色目录。</p>
      <div class="param-fields">
        <IdField kind="character" label="新角色 ID" value={to} onChange={setTo} onAvailability={setFree} />
        <label class="param-field"><span>代码名</span>
          <input class="mono" value={code} onInput={(e) => setCode((e.target as HTMLInputElement).value.trim())} /></label>
      </div>
      {problems.length ? <ul class="inline-problems">{problems.map((p) => <li>{p}</li>)}</ul> : null}
      {message ? <Notice kind="error">升级失败：{message}</Notice> : null}
      <div class="save-row">
        <button type="button" class="primary" disabled={busy || problems.length > 0 || !drafts.hasToken()} onClick={run}>{busy ? "升级中……" : "升级"}</button>
        <button type="button" class="ghost" onClick={onClose}>取消</button>
      </div>
    </div>
  );
}
