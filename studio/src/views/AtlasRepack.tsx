// 像素 › 图集重排: MaxRects repack of the current view's sprite_sheet, proved equivalent frame by
// frame before it can be written into the draft as a whole-family replacement.
import { useEffect, useState } from "preact/hooks";
import { api, drafts } from "../api";
import { craft, RepackReport } from "../craftApi";
import { Notice } from "./common";
import { InfoTip } from "./Delivery";
import "./craft.css";

export function AtlasRepack({ characterId }: { characterId: string }) {
  const [family, setFamily] = useState<"pixelart" | "special">("pixelart");
  const [report, setReport] = useState<RepackReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    setReport(null); setError(null); setBusy("load");
    craft.repack(characterId, family).then(setReport, (e: Error) => setError(e.message)).finally(() => setBusy(null));
  }, [characterId, family]);

  const apply = async () => {
    setBusy("apply"); setMessage(null); setError(null);
    try {
      const r = await craft.applyRepack(characterId, family);
      setMessage(`已写入草稿：${r.change.title}（${r.status.label}）`);
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(null); }
  };

  return (
    <div class="ws-import">
      <p class="hint">把当前视图的 sprite_sheet 用 MaxRects 重新装箱：只搬整块区域（不裁边、不旋转、不重采样），每块前留 2px 间隙，
        在几十个候选宽度 × 两种排序里取面积最小的。重排后先证明和原图集等价，才允许写进草稿。
        <InfoTip text={"等价校验：① atlas 记录除 x/y 外逐条相同；② 按记录顺序取出的像素块哈希相同；③ 每个端点按游戏方式（旋转、fx/fy、未裁剪帧框）从新旧两张图各还原一遍，逐字节比对。frame / timeline 原样不动。\n写入草稿 = 一条整族替换，生成时和「整族导入」走同一条路径。"} /></p>
      <div class="toolbar">
        <label>像素族<select value={family} onChange={(e) => setFamily((e.target as HTMLSelectElement).value as "pixelart" | "special")}>
          <option value="pixelart">基础动作（战斗加载）</option><option value="special">特殊动作（战斗不加载）</option>
        </select></label>
      </div>
      {busy === "load" ? <div class="loading">正在重排并做等价校验……</div> : null}
      {error ? <Notice kind="error">{error}</Notice> : null}
      {message ? <Notice kind="info">{message}</Notice> : null}
      {report ? (
        <section class="pixel-check">
          <table class="data">
            <thead><tr><th></th><th>尺寸</th><th>面积</th><th>战斗 layer0 占用</th></tr></thead>
            <tbody>
              <tr><td>原图集</td><td class="mono">{report.source.width}×{report.source.height}</td><td>{report.source.area.toLocaleString()}</td>
                <td>{report.loadedInBattle ? report.source.share + "%" : "不加载"}</td></tr>
              <tr><td>重排后</td><td class="mono">{report.output.width}×{report.output.height}</td><td>{report.output.area.toLocaleString()}</td>
                <td>{report.loadedInBattle ? report.output.share + "%" : "不加载"}</td></tr>
            </tbody>
          </table>
          <p class="small">{report.regions} 块区域 / {report.records} 条记录 · 填充率 {report.fill}% · 面积{report.saving >= 0 ? "省" : "多"} {Math.abs(report.saving)}%
            · 宽度 {report.targetWidth}、按{report.sortMode === "height" ? "高度" : "面积"}排序</p>
          <p class="small">等价校验通过：{report.equivalence.framesCompared} 个端点逐字节相同 · 签名 <span class="mono">{report.equivalence.signature.slice(0, 16)}…</span></p>
          {!report.worthIt ? <Notice kind="info">重排后不比原图集小：原图集已经够紧，不用写入。</Notice> : null}
          <div class="repack-compare">
            <figure><img class="pixelated checker" src={api.assetUrl(`character/${report.code}/pixelart/${family === "pixelart" ? "sprite_sheet" : "special_sprite_sheet"}.png`)} alt="原图集" />
              <figcaption class="small muted">当前视图的 sprite_sheet</figcaption></figure>
            <figure><img class="pixelated checker" src={craft.repackPngUrl(characterId, family)} alt="重排后" /><figcaption class="small muted">重排后的 sprite_sheet</figcaption></figure>
          </div>
          <div class="save-row">
            <a class="button" href={craft.repackPngUrl(characterId, family)} download={`${report.code}-${family}-repacked.png`}>下载重排后的 PNG</a>
            <button class="primary" onClick={apply} disabled={!report.worthIt || busy !== null || !drafts.hasToken()}>
              {busy === "apply" ? "写入中……" : "写入草稿（整族替换）"}</button>
          </div>
        </section>
      ) : null}
    </div>
  );
}
