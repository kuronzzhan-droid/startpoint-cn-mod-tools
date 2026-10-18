import { render } from "preact";
import { useEffect, useState } from "preact/hooks";
import { api, Meta } from "./api";
import { href, useRoute } from "./router";
import { CharacterList } from "./views/CharacterList";
import { CharacterDetailView } from "./views/CharacterDetail";
import { BossPlaceholder } from "./views/BossPlaceholder";
import { PatchManager } from "./views/PatchManager";
import { ScratchDetail, ScratchList } from "./views/ScratchView";
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
        <span title={meta ? `技术细节：kulo active 补丁链之后再叠加 ${meta.source.extraZips.length} 个补丁 ZIP`
          + (meta.source.chain ? `（按补丁链清单 ${meta.source.chain.manifest} 找到 ${meta.source.chain.resolved} 个）` : "") : ""}>
          当前内容：<strong>测试服</strong>
          {meta ? <> · 资源版本 {meta.source.version}</> : null}
        </span>
        <span class="pill draftable" title="只写草稿（work/studio-drafts）和本机交付目录（work/studio-deliveries）；不改测试服、不发布、不写游戏数据">只写草稿</span>
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
          <a role="tab" class={route.shop === "scratch" ? "active" : ""} href={href({ work: "content", shop: "scratch" })}>
            草稿角色
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
          ) : route.shop === "scratch" ? (
            route.id ? <ScratchDetail id={route.id} tab={route.tab} sub={route.sub} /> : <ScratchList />
          ) : route.id ? (
            <CharacterDetailView id={route.id} tab={route.tab} sub={route.sub} />
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
