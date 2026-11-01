import { useEffect, useState } from "preact/hooks";
import { batch, BatchPreview, BatchWritten, Mapping } from "../batchApi";
import { drafts } from "../api";
import { Notice } from "./common";
import { BatchDone, BatchReview } from "./BatchReview";
import { pruneMapping } from "../batchReviewState";

const FIELDS = [["character", "角色（ID / 精确名字 / 代码名）"], ["entry", "词条（能力1–6 / 队长技 / 键）"],
  ["before", "修改前"], ["after", "修改后"], ["row", "词条内行号（可选，从1起）"], ["column", "原始列号（可选，从0起）"]];

export function BalanceImport() {
  const [text, setText] = useState("");
  const [headers, setHeaders] = useState<string[]>([]);
  const [mapping, setMapping] = useState<Mapping>({});
  const [preview, setPreview] = useState<BatchPreview | null>(null);
  const [selected, setSelected] = useState<number[]>([]);
  const [done, setDone] = useState<BatchWritten | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [remembered, setRemembered] = useState(false);
  const [mappingReady, setMappingReady] = useState(false);
  useEffect(() => { let live = true; batch.mapping().then(r => { if (live) setMapping(r.mapping); },
    (e: Error) => { if (live) setError(e.message); }).finally(() => { if (live) setMappingReady(true); }); return () => { live = false; }; }, []);
  const reset = () => { setPreview(null); setSelected([]); setDone(null); setError(""); };
  const changeText = (value: string) => { setText(value); setHeaders([]); reset(); };
  const run = async (action: "parse" | "preview" | "apply") => {
    setBusy(true); setError("");
    try {
      if (action === "parse") {
        const r = await batch.parse(text); setHeaders(r.headers); setPreview(null); setSelected([]);
        setMapping(current => pruneMapping(current, r.headers)); setRemembered(false);
      } else if (action === "preview") {
        setPreview(null); setSelected([]); setDone(null);
        setPreview(await batch.balance({ text, mapping }));
        await batch.remember(mapping); setRemembered(true);
      } else if (preview && selected.length) {
        setDone(await batch.apply("balance", { text, mapping }, preview.review, selected));
        setPreview(null); setSelected([]);
      }
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  };
  return <section class="page">
    <a class="back" href="#/content/characters">← 角色工坊</a><h1>平衡表导入</h1>
    <p>粘贴从文档复制的 TSV，或导入本地 CSV / TSV。每行对应一个角色的一条改动，列名由你映射。</p>
    <Notice>填写完整的修改前、修改后机器中文描述，可自动转换唯一数值变化。也可填写原始列号及精确原始数值；不猜百分比单位。合并单元格、宽表多条能力或新增/删除说明请先整理成逐行改动，不会自动向下填充角色。</Notice>
    <fieldset disabled={busy || !mappingReady}>
      <label>本地表格文件 <input type="file" accept=".csv,.tsv,.txt" onChange={async e => {
        const file = e.currentTarget.files?.[0]; if (!file) return;
        try { changeText(await file.text()); } catch (error) { setError((error as Error).message); }
      }} /></label>
      <textarea class="batch-input" rows={10} value={text} placeholder="在此粘贴带表头的表格文本" onInput={e => changeText(e.currentTarget.value)} />
      <button type="button" disabled={!text.trim()} onClick={() => run("parse")}>解析表头与行</button>
      {!!headers.length && <div class="param-fields">{FIELDS.map(([key, label]) => <label class="param-field" key={key}>
        <span>{label}</span><select value={headers.includes(mapping[key]) ? mapping[key] : ""} onChange={e => {
          setMapping({ ...mapping, [key]: e.currentTarget.value }); setRemembered(false); reset();
        }}><option value="">请选择列</option>{headers.map(h => <option key={h} value={h}>{h}</option>)}</select>
      </label>)}</div>}
      {!!headers.length && <button type="button" onClick={() => run("preview")}>预览改动并记住映射</button>}
      {remembered && <p class="small muted">上次映射已保存在本地 work/ 中。</p>}
      {preview && <BatchReview value={preview} selected={selected} onSelect={setSelected} />}
      {preview && <button class="primary" type="button" disabled={!selected.length || !drafts.hasToken()} onClick={() => run("apply")}>将勾选的 {selected.length} 行写入草稿</button>}
    </fieldset>
    {busy && <p>处理中……</p>}{error && <Notice kind="error">{error}</Notice>}<BatchDone result={done} />
  </section>;
}
