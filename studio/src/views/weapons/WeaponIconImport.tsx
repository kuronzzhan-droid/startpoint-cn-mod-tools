// 图标导入：武器本体 20×20、魂珠 / 材料 40×40（写进 item_icon 图集空位并派生 20×20）。
// 先在浏览器里核对尺寸并放大预览，再走 ?preview=true 预检，通过后写入武器草稿。
import { useEffect, useState } from "preact/hooks";
import { fileToBase64 } from "../../api";
import { WeaponDetail, WeaponIconPreview, WeaponIconRequest, weaponIcons } from "../../weaponApi";
import { BossRuleList } from "../boss/BossChecks";
import { Notice } from "../common";
import { InfoTip } from "../Delivery";

const SIZE: Record<WeaponIconRequest["kind"], number> = { weapon: 20, soul: 40, material: 40 };
const KIND_LABEL: Record<WeaponIconRequest["kind"], string> = { weapon: "武器本体（20×20）", soul: "魂珠（40×40）", material: "材料（40×40）" };

/** Item ids this weapon's enhancement stages and awakening use, with names when the detail carries them. */
function materialOptions(detail: WeaponDetail): { id: string; name: string }[] {
  const seen = new Map<string, string>();
  for (const s of detail.enhancement_chain) for (const c of s.costs) if (!seen.has(c.itemId)) seen.set(c.itemId, c.name ?? "");
  if (detail.awakening?.materialId && !seen.has(detail.awakening.materialId)) seen.set(detail.awakening.materialId, "专用觉醒材料");
  return [...seen].map(([id, name]) => ({ id, name }));
}

export function WeaponIconImport({ detail, onClose }: { detail: WeaponDetail; onClose: () => void }) {
  const [kind, setKind] = useState<WeaponIconRequest["kind"]>("weapon");
  const [itemId, setItemId] = useState("");
  const [png, setPng] = useState<string | null>(null);
  const [url, setUrl] = useState<string | null>(null);
  const [size, setSize] = useState<[number, number] | null>(null);
  const [preview, setPreview] = useState<WeaponIconPreview | null>(null);
  const [busy, setBusy] = useState<"check" | "write" | null>(null);
  const [message, setMessage] = useState<{ kind: "info" | "error"; text: string } | null>(null);
  const materials = materialOptions(detail);
  useEffect(() => () => { if (url) URL.revokeObjectURL(url); }, [url]);
  useEffect(() => { setPreview(null); setMessage(null); }, [kind, itemId, png]);

  const pick = async (file: File | undefined) => {
    if (!file) return;
    const next = URL.createObjectURL(file);
    setUrl(next);
    setPng(await fileToBase64(file));
    const img = new Image();
    img.onload = () => setSize([img.naturalWidth, img.naturalHeight]);
    img.onerror = () => setSize(null);
    img.src = next;
  };
  const want = SIZE[kind];
  const problems: string[] = [];
  if (!png) problems.push("选一张 PNG");
  else if (size && (size[0] !== want || size[1] !== want)) problems.push(`尺寸是 ${size[0]}×${size[1]}，${KIND_LABEL[kind]}要 ${want}×${want}`);
  if (kind === "material" && !/^[1-9][0-9]*$/.test(itemId)) problems.push("选或填材料 item ID");
  if (png && png.length > 2000000) problems.push("PNG 太大（base64 上限 2,000,000 字符）");
  const body = (): WeaponIconRequest => ({ kind, png: png!, ...(kind === "material" ? { item_id: itemId } : {}) });

  const check = async () => {
    setBusy("check");
    try { setPreview(await weaponIcons.preview(detail.id, body())); } finally { setBusy(null); }
  };
  const write = async () => {
    setBusy("write"); setMessage(null);
    try {
      const r = await weaponIcons.apply(detail.id, body());
      setMessage({ kind: "info", text: `已写入草稿（${r.status.label}）：${(r.icons ?? []).map((i) => i.logical).join("、") || "图标"}` });
    } catch (e) { setMessage({ kind: "error", text: (e as Error).message }); }
    finally { setBusy(null); }
  };

  return (
    <section class="boss-block icon-import">
      <header><h3>导入图标</h3>
        <InfoTip text="武器本体写独立 PNG 并改 equipment c6；魂珠 / 材料 40×40 写进 item_icon 图集空位（不扩画布、不动旧条目），同时派生 20×20，改 item c4 / c3。材料是共享 item，会影响所有使用它的地方。" />
        <span class="spacer" /><button type="button" class="link close-x" onClick={onClose} aria-label="关闭">×</button></header>
      <div class="param-fields compact">
        <label class="param-field"><span>图标类型</span>
          <select value={kind} onChange={(e) => setKind((e.target as HTMLSelectElement).value as WeaponIconRequest["kind"])}>
            {(Object.keys(SIZE) as WeaponIconRequest["kind"][]).map((k) => <option value={k}>{KIND_LABEL[k]}</option>)}
          </select>
          {kind === "soul" ? <span class="small muted">自动用本体 c10 指向的魂珠 {detail.soulId}</span> : null}</label>
        {kind === "material" ? (
          <label class="param-field"><span>材料 item ID</span>
            <input class="mono" list="weapon-icon-materials" value={itemId} onInput={(e) => setItemId((e.target as HTMLInputElement).value.trim())} />
            <datalist id="weapon-icon-materials">{materials.map((m) => <option value={m.id}>{m.name}</option>)}</datalist>
            <span class="small warn-text">共享 item：这份草稿里该材料的图标对所有使用者生效</span></label>
        ) : null}
        <label class="param-field"><span>PNG 文件</span>
          <input type="file" accept="image/png" onChange={(e) => pick((e.target as HTMLInputElement).files?.[0])} /></label>
      </div>
      {url ? (
        <div class="icon-preview">
          <img src={url} width={want * 4} height={want * 4} alt="" class="pixelated" />
          <img src={url} width={want} height={want} alt="" />
          <span class="small muted">{size ? `${size[0]}×${size[1]}` : "读取尺寸……"} · 放大 4 倍 / 原尺寸</span>
        </div>
      ) : null}
      {problems.length ? <ul class="inline-problems">{problems.map((p) => <li>{p}</li>)}</ul> : null}
      {preview ? (
        <div>
          <p class={"small " + (preview.ok ? "state-ok" : "error-text")}>{preview.ok ? "预检通过，可以写入" : "预检有阻断项"}</p>
          {preview.icons?.length ? (
            <ul class="small mono">{preview.icons.map((i) => (
              <li>{i.kind} · {i.logical}{i.itemId ? ` · item ${i.itemId}` : ""}{i.thumbnail ? ` · 20×20 ${i.thumbnail}` : ""}
                {i.preservedEntries !== undefined ? ` · 保留旧条目 ${i.preservedEntries}` : ""}</li>
            ))}</ul>
          ) : null}
          <BossRuleList checks={preview.checks} compact />
        </div>
      ) : null}
      {message ? <Notice kind={message.kind}>{message.text}</Notice> : null}
      <div class="save-row">
        <button type="button" disabled={problems.length > 0 || busy !== null} onClick={check}>{busy === "check" ? "预检中……" : "预检"}</button>
        <button type="button" class="primary" disabled={problems.length > 0 || busy !== null || !preview?.ok} onClick={write}
          title={!preview?.ok ? "先预检通过" : ""}>{busy === "write" ? "写入中……" : "写入草稿"}</button>
      </div>
    </section>
  );
}
