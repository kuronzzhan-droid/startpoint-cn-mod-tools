/** Share only reads that are currently running. The server owns content-keyed caches. */
type Read = {
  controller: AbortController;
  promise: Promise<unknown>;
  consumers: number;
  started: number;
  settled: boolean;
};

const pending = new Map<string, Read>();
const running = new Set<Read>();
const listeners = new Set<() => void>();
const changed = () => listeners.forEach((listener) => listener());

export class HttpError extends Error {
  constructor(message: string, readonly status: number) { super(message); }
}

export function readActivity(): { count: number; started: number } {
  return { count: running.size, started: Math.min(...[...running].map((read) => read.started)) };
}

export function onReadActivity(listener: () => void): () => void {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}

/** A post-write read must not join a request started against the previous draft. */
export function invalidateReads(): void { pending.clear(); }

export function get<T>(url: string, signal?: AbortSignal): Promise<T> {
  if (signal?.aborted) return Promise.reject(new DOMException("读取已取消", "AbortError"));
  let read = pending.get(url);
  if (!read) {
    const controller = new AbortController();
    read = { controller, consumers: 0, started: Date.now(), settled: false, promise: Promise.resolve() };
    const current = read;
    current.promise = fetch(url, { signal: controller.signal, cache: "no-store" }).then(async (response) => {
      const body = await response.json().catch((error: unknown) => {
        if (controller.signal.aborted) throw error;
        return { error: `HTTP ${response.status}` };
      });
      if (!response.ok) throw new HttpError(body.error || `HTTP ${response.status}`, response.status);
      return body;
    }).finally(() => {
      current.settled = true;
      if (pending.get(url) === current) pending.delete(url);
      running.delete(current);
      changed();
    });
    pending.set(url, current);
    running.add(current);
    changed();
  }
  const current = read;
  current.consumers++;
  return new Promise<T>((resolve, reject) => {
    let finished = false;
    const release = () => {
      if (finished) return false;
      finished = true;
      signal?.removeEventListener("abort", abort);
      current.consumers--;
      return true;
    };
    const abort = () => {
      if (!release()) return;
      reject(new DOMException("读取已取消", "AbortError"));
      if (!current.consumers && !current.settled) {
        if (pending.get(url) === current) pending.delete(url);
        current.controller.abort();
      }
    };
    signal?.addEventListener("abort", abort, { once: true });
    current.promise.then(
      (body) => {
        if (finished) return;
        try {
          // Each subscriber owns its result; only the last one can take the original.
          const value = current.consumers > 1 ? structuredClone(body) : body;
          release();
          resolve(value as T);
        } catch (error) { release(); reject(error); }
      },
      (error: unknown) => { if (release()) reject(error); },
    );
  });
}
