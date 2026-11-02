import { useEffect, useState } from "preact/hooks";

// #/content/characters/<id>/<tab>[/<sub>]   (tab = group: ability / skill / text / portrait / pixel / voice;
//                                             tab = changes / assets opens the header drawer)
// #/scratch/<id>/<tab>[/<sub>]
// #/content/boss                         BOSS工坊总览
// #/content/boss/q/<selector>[/<tab>[/<sub>]]  副本详情（tab = encounter / rewards / params；changes 打开抽屉，sub = 交付名）
// #/content/boss/new[/<source selector>] 新建共同决战向导
// #/content/characters/new[/<母本 id>]  从母本克隆新角色向导
// #/content/weapons[/<id>[/changes[/<sub>]]]  武器工坊（列表 + 详情；changes 打开本次修改抽屉，sub = 交付名）
export type Route =
  | { work: "content"; shop: "characters"; id?: string; tab?: string; sub?: string; clone?: boolean; source?: string; balance?: boolean }
  | { work: "content"; shop: "boss"; quest?: string; tab?: string; sub?: string; wizard?: boolean; source?: string }
  | { work: "content"; shop: "scratch"; id?: string; tab?: string; sub?: string }
  | { work: "content"; shop: "weapons"; id?: string; tab?: string; sub?: string }
  | { work: "patches"; archive?: string }
  | { work: "opening" };

export function parse(hash: string): Route {
  const parts = hash.replace(/^#\/?/, "").split("/").filter(Boolean).map(decodeURIComponent);
  // Short deep link: #/character/139985[/tab[/sub]]
  if (parts[0] === "character" && parts[1])
    return { work: "content", shop: "characters", id: parts[1], tab: parts[2], sub: parts[3] };
  if (parts[0] === "patches") return { work: "patches", archive: parts[1] };
  if (parts[0] === "opening") return { work: "opening" };
  if (parts[0] === "scratch") return { work: "content", shop: "scratch", id: parts[1], tab: parts[2], sub: parts[3] };
  if (parts[0] === "content" && parts[1] === "boss") {
    if (parts[2] === "new") return { work: "content", shop: "boss", wizard: true, source: parts[3] };
    if (parts[2] === "q" && parts[3]) return { work: "content", shop: "boss", quest: parts[3], tab: parts[4], sub: parts[5] };
    return { work: "content", shop: "boss" };
  }
  if (parts[0] === "content" && parts[1] === "weapons")
    return { work: "content", shop: "weapons", id: parts[2], tab: parts[3], sub: parts[4] };
  if (parts[0] === "content" && parts[1] === "characters" && parts[2] === "new")
    return { work: "content", shop: "characters", clone: true, source: parts[3] };
  if (parts[0] === "content" && parts[1] === "characters" && parts[2] === "balance-import")
    return { work: "content", shop: "characters", balance: true };
  if (parts[0] === "content" && parts[1] === "characters" && parts[2])
    return { work: "content", shop: "characters", id: parts[2], tab: parts[3], sub: parts[4] };
  return { work: "content", shop: "characters" };
}

export function href(route: Route): string {
  if (route.work === "patches") return "#/patches" + (route.archive ? "/" + encodeURIComponent(route.archive) : "");
  if (route.work === "opening") return "#/opening";
  if (route.shop === "boss") {
    if (route.wizard) return "#/content/boss/new" + (route.source ? "/" + encodeURIComponent(route.source) : "");
    if (route.quest) return "#/content/boss/q/" + encodeURIComponent(route.quest) + (route.tab ? "/" + route.tab
      + (route.sub ? "/" + encodeURIComponent(route.sub) : "") : "");
    return "#/content/boss";
  }
  const tail = (r: { tab?: string; sub?: string }) => (r.tab ? "/" + r.tab + (r.sub ? "/" + r.sub : "") : "");
  if (route.shop === "scratch") return "#/scratch" + (route.id ? "/" + route.id + tail(route) : "");
  if (route.shop === "weapons") return "#/content/weapons" + (route.id ? "/" + encodeURIComponent(route.id) + tail(route) : "");
  if (route.clone) return "#/content/characters/new" + (route.source ? "/" + encodeURIComponent(route.source) : "");
  if (route.balance) return "#/content/characters/balance-import";
  if (route.id) return `#/content/characters/${route.id}` + tail(route);
  return "#/content/characters";
}

export function useRoute(): Route {
  const [route, setRoute] = useState(() => parse(location.hash));
  useEffect(() => {
    const update = () => setRoute(parse(location.hash));
    window.addEventListener("hashchange", update);
    return () => window.removeEventListener("hashchange", update);
  }, []);
  return route;
}
