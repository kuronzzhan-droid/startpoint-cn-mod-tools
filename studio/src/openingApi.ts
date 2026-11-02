import { get, RuleResult } from "./api";

export type OpeningServer = "local" | "test175";
export interface OpeningChecklist {
  schema: string; server: OpeningServer; createdAt: string; readOnly: true; runtime: string;
  status: "ready" | "blocked" | "pending"; ok: boolean;
  targets: { id: OpeningServer; label: string; configured: boolean }[];
  source: { version: string; baseVersion: string | null; view: string | null; edgeCount: number };
  target: { version: string | null; manifestSha256: string | null; configured: boolean };
  missingEdges: { from: string; to: string; localTestOnly: boolean;
    archives: { name: string; sha256: string | null; size: number | null }[] }[];
  checks: RuleResult[];
  clientCapabilities: { profile: string; available: boolean; status: "matched" | "mismatch" | "unknown";
    providesCount: number; requires: string[]; missing: string[]; unknownEdges: string[]; checks: RuleResult[] };
  manualSteps: string[]; rollback: string; entryLinks: { id: string; label: string; href: string }[]; note: string;
}

export const opening = {
  read: (server: OpeningServer, clientProfile?: string | null) => get<OpeningChecklist>(
    `/api/studio/opening?server=${server}` + (clientProfile ? `&clientProfile=${encodeURIComponent(clientProfile)}` : "")),
};
