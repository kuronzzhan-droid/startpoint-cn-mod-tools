import type { ComponentType } from "preact";
import { lazy, Suspense } from "preact/compat";
import { Loading } from "./views/Loading";

/** Each route owns its loading boundary, so navigation and the current editor stay usable. */
export function lazyView<M, K extends keyof M>(load: () => Promise<M>, name: K) {
  type Props = M[K] extends ComponentType<infer P> ? P & object : never;
  const View = lazy(() => load().then((module) => ({ default: module[name] as ComponentType<Props> })));
  return (props: Props) => <Suspense fallback={<Loading label="正在加载页面组件……" />}><View {...props} /></Suspense>;
}
