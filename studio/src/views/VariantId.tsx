import { useEffect, useState } from "preact/hooks";
import { batch, LinkedId } from "../batchApi";

export function VariantId({ from, value, duplicate, onChange }: {
  from: string; value: string; duplicate: boolean; onChange: (value: string) => void;
}) {
  const [result, setResult] = useState<LinkedId | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let live = true;
    setResult(null); setError("");
    if (!value || duplicate) return;
    const timer = window.setTimeout(() => {
      batch.idCheck(from, value).then(r => { if (live) setResult(r); },
        e => { if (live) setError((e as Error).message); });
    }, 300);
    return () => { live = false; window.clearTimeout(timer); };
  }, [from, value, duplicate]);
  const fresh = result?.id === value ? result : null;
  return <label class="param-field"><span>新角色 ID</span>
    <input value={value} onInput={e => onChange(e.currentTarget.value.trim())} />
    {duplicate ? <span class="error-text">批内 ID 重复</span>
      : error ? <span class="error-text">{error}</span>
      : fresh ? <span class={fresh.available ? "state-ok" : "error-text"}>
        {fresh.available ? `联动键空闲${fresh.serverChecked ? "" : "（未查服务端镜像）"}` : fresh.reasons.join("；")}</span>
      : <span class="muted">{value ? "查询角色、玛纳段、能力、技能与草稿占用……" : "填写目标 ID"}</span>}
  </label>;
}
