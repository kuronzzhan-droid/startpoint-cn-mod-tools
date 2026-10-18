import { render } from "preact";
import { useEffect, useState } from "preact/hooks";
import { api, Meta } from "./api";
import { href, useRoute } from "./router";
import { CharacterList } from "./views/CharacterList";
import { CharacterDetailView } from "./views/CharacterDetail";
import { BossPlaceholder } from "./views/BossPlaceholder";
import { PatchManager } from "./views/PatchManager";
import { LookupPanel } from "./views/LookupPanel";
import "./styles.css";
import "./m4.css";
import "./workshop.css";

function App() {
  const route = useRoute();
  const [meta, setMeta] = useState<Meta | null>(null);
  const [metaError, setMetaError] = useState<string | null>(null);
  const [lookupOpen, setLookupOpen] = useState(false);

  useEffect(() => {
    api.meta().then(setMeta, (e: Error) => setMetaError(e.message));
  }, []);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setLookupOpen(false);
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setLookupOpen((open) => !open);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div class={"app" + (lookupOpen ? " with-lookup" : "")}>
      <header class="topbar">
        <a class="brand" href="#/content/characters">编辑台</a>
        <nav class="works" aria-label="一级工作">
          <a class={route.work === "content" ? "active" : ""} href="#/content/characters">编辑内容</a>
          <a class={route.work === "patches" ? "active" : ""} href="#/patches">补丁管理</a>
        </nav>
        <div class="topbar-right">
          <button class={"lookup-toggle" + (lookupOpen ? " on" : "")} onClick={() => setLookupOpen(!lookupOpen)}
            title="随时可用的词条速查（Ctrl+K）">
            词条速查
          </button>
        </div>
      </header>
      <div class="context-bar">
        <span>
          当前内容：<strong>测试服链视图</strong>
          {meta ? <> · 资源版本 {meta.source.version}</> : null}
        </span>
        <span class="pill draftable" title="只写草稿 work/studio-drafts 与本地交付 work/studio-deliveries；不应用、不发布，不写游戏表">草稿可写</span>
        {meta && meta.source.extraZips.length > 0 ? (
          <span class="muted" title={meta.source.chain ? "清单：" + meta.source.chain.manifest : ""}>
            active 之后叠加 {meta.source.extraZips.length} 个 ZIP
            {meta.source.chain ? `（按补丁链清单找到 ${meta.source.chain.resolved} 个）` : ""}
          </span>
        ) : null}
        {meta?.source.chain?.missing.length ? (
          <span class="error-text">补丁链缺 {meta.source.chain.missing.length} 个 ZIP，视图不完整</span>
        ) : null}
        {metaError ? <span class="error-text">后端不可用：{metaError}</span> : null}
      </div>
      {route.work === "content" ? (
        <div class="workshop-tabs" role="tablist" aria-label="工坊">
          <a role="tab" class={route.shop === "characters" ? "active" : ""} href={href({ work: "content", shop: "characters" })}>
            角色工坊
          </a>
          <a role="tab" class={route.shop === "boss" ? "active" : ""} href={href({ work: "content", shop: "boss" })}>
            BOSS工坊
          </a>
        </div>
      ) : null}
      <div class="layout">
        <main class="main">
          {route.work === "patches" ? (
            <PatchManager archive={route.archive} />
          ) : route.shop === "boss" ? (
            <BossPlaceholder />
          ) : route.id ? (
            <CharacterDetailView id={route.id} tab={route.tab} />
          ) : (
            <CharacterList />
          )}
        </main>
        {lookupOpen ? <LookupPanel onClose={() => setLookupOpen(false)} context={route.work === "content" && route.shop === "characters" ? route.id : undefined} /> : null}
      </div>
    </div>
  );
}

render(<App />, document.getElementById("app")!);
