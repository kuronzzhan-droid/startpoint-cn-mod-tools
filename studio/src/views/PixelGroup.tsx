// 像素 group: one sub navigation for preview, single-action replacement, the workshop pages and
// whole-family import — the same structure on real characters and on scratch characters.
import { useState } from "preact/hooks";
import { drafts, ImportResult, scratchApi } from "../api";
import { href, Route } from "../router";
import { Notice } from "./common";
import { InfoTip } from "./Delivery";
import { PixelImport } from "./PixelImport";
import { PixelPlayer } from "./PixelPlayer";
import { SkillPreview } from "./TimelinePreview";
import { PixelWorkshop, WORKSHOP_SUBS, WorkshopSub } from "./PixelWorkshop";
import { readAsDataUrl } from "./workshopKit";

export type PixelSub = "preview" | "replace" | WorkshopSub | "import" | "timeline";

const SUBS: { id: PixelSub; label: string; hint: string }[] = [
  { id: "preview", label: "预览", hint: "播放每个动作" },
  { id: "replace", label: "单动作替换", hint: "上传逐帧 PNG 或精灵图，替换一个动作" },
  ...WORKSHOP_SUBS,
  { id: "import", label: "整族导入", hint: "导入离线做好的整套小人文件（可带颜色表）" },
  { id: "timeline", label: "强化弹射预览", hint: "强化弹射 / 技能的编排时间轴（L2），与「技能 › 动作预览」同一个播放器" },
];

export function pixelSubs(scratch: boolean) {
  // A scratch character's「当前视图」is its base family: preview and single-action replace live in the workshop pages.
  return scratch ? SUBS.filter((s) => s.id !== "preview" && s.id !== "replace" && s.id !== "timeline") : SUBS;
}

export function PixelGroup({ characterId, sub, scratch, link }: {
  characterId: string; sub?: string; scratch?: boolean; link: (sub: PixelSub) => Route;
}) {
  const subs = pixelSubs(!!scratch);
  const active = (subs.find((s) => s.id === sub) ?? subs[0]).id;
  return (
    <div class="group-page">
      <nav class="subnav" aria-label="像素">
        {subs.map((s) => (
          <a class={active === s.id ? "on" : ""} href={href(link(s.id))} title={s.hint} aria-current={active === s.id ? "page" : undefined}>{s.label}</a>
        ))}
      </nav>
      {active === "preview" ? <PixelPlayer characterId={characterId} />
        : active === "replace" ? <PixelImport characterId={characterId} />
        : active === "import" ? <FamilyImport cid={characterId} />
        : active === "timeline" ? <SkillPreview characterId={characterId} prefer="pf" />
        : <PixelWorkshop characterId={characterId} sub={active as WorkshopSub} key={characterId + active} />}
    </div>
  );
}

/** 整族导入: sprite_sheet / atlas / frame / timeline (pixelart or special) from a folder or zip, optional colour table. */
export function FamilyImport({ cid, onDone }: { cid: string; onDone?: () => void }) {
  const [files, setFiles] = useState<Record<string, string>>({});
  const [zip, setZip] = useState<{ name: string; data: string } | null>(null);
  const [remap, setRemap] = useState<{ name: string; value: unknown } | null>(null);
  const [name, setName] = useState("");
  const [result, setResult] = useState<ImportResult | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<{ kind: "info" | "error"; text: string } | null>(null);
  const b64 = async (f: File) => (await readAsDataUrl(f)).replace(/^data:[^,]*,/, "");
  const pickFolder = async (list: FileList | null) => {
    if (!list) return;
    const out: Record<string, string> = {};
    for (const f of Array.from(list)) {
      if (/\.(png|deflate|json)$/.test(f.name)) out[(f as File & { webkitRelativePath?: string }).webkitRelativePath || f.name] = await b64(f);
    }
    setFiles(out); setZip(null); setResult(null);
    if (!name) setName(Object.keys(out)[0]?.split("/")[0] ?? "");
  };
  const run = async (dryRun: boolean) => {
    setBusy(dryRun ? "check" : "import"); setMessage(null);
    try {
      const body = { ...(zip ? { zip: zip.data } : { files }), ...(remap ? { remap: remap.value } : {}), name: name || zip?.name || "导入", dryRun };
      const r = await scratchApi.importSet(cid, body);
      setResult(r);
      if (!dryRun) { setMessage({ kind: "info", text: `已导入：${r.changes?.map((c) => c.title).join("；")}（${r.status?.label}）` }); onDone?.(); }
    } catch (e) { setMessage({ kind: "error", text: (e as Error).message }); }
    finally { setBusy(null); }
  };
  const ready = zip !== null || Object.keys(files).length > 0;
  const folderProps = { webkitdirectory: "", directory: "" } as Record<string, string>;
  return (
    <div class="ws-import">
      <p class="hint">导入离线做好的整套小人（基础动作或特殊动作的四个文件），按文件名识别，自动改成这个角色的名字前缀，整族替换。
        可以附一张颜色表（母本 + 颜色对照）：逐张对照「母本换色」的结果，一样的算换色，不一样的标成手绘。
        <InfoTip text={'文件：sprite_sheet.png + sprite_sheet.atlas.amf3.deflate + pixelart.frame.amf3.deflate + pixelart.timeline.amf3.deflate（special_* 同构）；颜色表 JSON：{"base": 母本代码, "mapping": {"#src": "#dst"}} 或 [{from,to}]，包里文件名含 remap/mapping/palette 的 JSON 会自动识别。'} /></p>
      <div class="toolbar">
        <label class="upload-btn">选文件夹<input type="file" multiple {...folderProps} onChange={(e) => pickFolder((e.target as HTMLInputElement).files)} /></label>
        <label class="upload-btn">或 zip<input type="file" accept=".zip" onChange={async (e) => {
          const f = (e.target as HTMLInputElement).files?.[0];
          if (f) { setZip({ name: f.name.replace(/\.zip$/, ""), data: await b64(f) }); setFiles({}); setResult(null); if (!name) setName(f.name.replace(/\.zip$/, "")); }
        }} /></label>
        <label class="upload-btn">颜色表 JSON（可选）<input type="file" accept=".json" onChange={async (e) => {
          const f = (e.target as HTMLInputElement).files?.[0];
          if (!f) return;
          try { setRemap({ name: f.name, value: JSON.parse(await f.text()) }); }
          catch (err) { setMessage({ kind: "error", text: "颜色表不是合法 JSON：" + (err as Error).message }); }
        }} /></label>
        <label>来源名称<input value={name} maxLength={80} onInput={(e) => setName((e.target as HTMLInputElement).value)} /></label>
      </div>
      <p class="small muted">{zip ? `zip：${zip.name}` : Object.keys(files).length ? `文件夹：${Object.keys(files).length} 个文件` : "还没选"}{remap ? ` · 颜色表 ${remap.name}` : ""}</p>
      {message ? <Notice kind={message.kind === "error" ? "error" : "info"}>{message.text}</Notice> : null}
      <div class="save-row">
        <button onClick={() => run(true)} disabled={!ready || busy !== null || !drafts.hasToken()}>{busy === "check" ? "检查中……" : "检查（不写草稿）"}</button>
        <button class="primary" onClick={() => run(false)} disabled={!ready || busy !== null || !drafts.hasToken()}>{busy === "import" ? "导入中……" : "导入到草稿（整族替换）"}</button>
      </div>
      {result ? (
        <section class="pixel-check">
          <h4>{result.dryRun ? "检查结果" : "已导入"}{result.remap ? ` · 颜色表 ${result.remap.colors} 色，母本 ${result.remap.base ?? "（未写）"}` : ""}</h4>
          {result.families.map((f) => (
            <div>
              <p class="small"><strong>{f.family === "pixelart" ? "基础动作" : "特殊动作"}</strong>：{f.endpoints} 张图 · 图集 {f.sheet.join("×")} · 动作 {f.actions.join("、")}
                <InfoTip text={`原名字前缀 ${f.sourceCode}`} /></p>
              {f.provenance?.comparable ? (
                <p class="small">与「母本 + 颜色表」一致 {f.provenance.matchingEndpoints}/{f.provenance.endpoints} 张
                  {Object.keys(f.provenance.differingByAction ?? {}).length ? "；手绘/改动：" + Object.entries(f.provenance.differingByAction!).map(([a, n]) => `${a} ${n}`).join("，") : ""}</p>
              ) : null}
              <ul class="checks">{f.checks.map((c) => <li class={"check-" + c.level}><span>{c.message}</span></li>)}</ul>
            </div>
          ))}
        </section>
      ) : null}
    </div>
  );
}
