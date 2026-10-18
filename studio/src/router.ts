import { useEffect, useState } from "preact/hooks";

export type Route =
  | { work: "content"; shop: "characters"; id?: string; tab?: string }
  | { work: "content"; shop: "boss" }
  | { work: "content"; shop: "scratch"; id?: string; tab?: string }
  | { work: "patches"; archive?: string };

export function parse(hash: string): Route {
  const parts = hash.replace(/^#\/?/, "").split("/").filter(Boolean).map(decodeURIComponent);
  // Short deep link: #/character/139985[/tab]
  if (parts[0] === "character" && parts[1])
    return { work: "content", shop: "characters", id: parts[1], tab: parts[2] };
  if (parts[0] === "patches") return { work: "patches", archive: parts[1] };
  if (parts[0] === "scratch") return { work: "content", shop: "scratch", id: parts[1], tab: parts[2] };
  if (parts[0] === "content" && parts[1] === "boss") return { work: "content", shop: "boss" };
  if (parts[0] === "content" && parts[1] === "characters" && parts[2])
    return { work: "content", shop: "characters", id: parts[2], tab: parts[3] };
  return { work: "content", shop: "characters" };
}

export function href(route: Route): string {
  if (route.work === "patches") return "#/patches" + (route.archive ? "/" + encodeURIComponent(route.archive) : "");
  if (route.shop === "boss") return "#/content/boss";
  if (route.shop === "scratch") return "#/scratch" + (route.id ? "/" + route.id + (route.tab ? "/" + route.tab : "") : "");
  if (route.id) return `#/content/characters/${route.id}` + (route.tab ? "/" + route.tab : "");
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
