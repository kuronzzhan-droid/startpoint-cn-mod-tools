import { useEffect, useState } from "preact/hooks";
import { onReadActivity, readActivity } from "../requests";
import "../loading.css";

export function Loading({ label = "正在读取页面……" }: { label?: string }) {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    const started = Date.now();
    const timer = window.setInterval(() => setSeconds(Math.floor((Date.now() - started) / 1000)), 1000);
    return () => window.clearInterval(timer);
  }, []);
  return <div class="read-loading" role="status" aria-live="polite" aria-busy="true">
    <p>{label}{seconds >= 2 ? <span class="muted"> · 已等待 {seconds} 秒</span> : null}</p>
    <div class="read-skeleton" aria-hidden="true"><span /><span /><span /></div>
  </div>;
}

/** Visible even when an already loaded page is waiting for a background refresh. */
export function ReadActivity() {
  const [state, setState] = useState(readActivity);
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    setState(readActivity());
    return onReadActivity(() => setState(readActivity()));
  }, []);
  useEffect(() => {
    if (!state.count) return;
    const timer = window.setInterval(() => setNow(Date.now()), 500);
    return () => window.clearInterval(timer);
  }, [state.count > 0]);
  const seconds = Math.max(0, Math.floor((now - state.started) / 1000));
  return state.count && seconds >= 1 ? <span class="read-activity" role="status" aria-live="polite">
    正在读取 {state.count} 项 · {seconds} 秒
  </span> : null;
}
