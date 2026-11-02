import { get, post, RuleResult } from "./api";

export interface BatchChange { table: string; key: string; row?: number; beforeDescription: string; afterDescription: string }
export interface Manual { table: string; key: string; row?: number; reason: string }
export interface VariantTarget { to: string; zone?: string; element?: number; code?: string }
export interface BatchRow {
  id: number; status: string; reason: string; characterId?: string; source?: string[];
  changes?: BatchChange[]; checks: RuleResult[]; target?: VariantTarget;
  result?: { characterId: string; buildable: boolean; variant: { changes: BatchChange[]; manual: Manual[] } };
}
export interface BatchPreview { review: string; rows: BatchRow[]; runtime: string }
export interface BatchWritten { written: { characterId: string }[] }
export type Mapping = Record<string, string>;
export interface BalanceBody { text: string; mapping: Mapping }
export interface VariantBody { from: string; rule: string; targets: VariantTarget[] }
export interface LinkedId { id: string; available: boolean; reasons: string[]; serverChecked: boolean }
const root = "/api/studio/characters";
export const batch = {
  idCheck: (from: string, id: string) => get<LinkedId>(`${root}/variants/ids/check?from=${encodeURIComponent(from)}&id=${encodeURIComponent(id)}`),
  idNext: (from: string, near?: string) => get<LinkedId>(`${root}/variants/ids/next?from=${encodeURIComponent(from)}${near ? `&near=${encodeURIComponent(near)}` : ""}`),
  mapping: () => get<{ mapping: Mapping }>(`${root}/balance/mapping`),
  remember: (mapping: Mapping) => post(`${root}/balance/mapping`, { mapping }),
  parse: (text: string) => post<{ headers: string[]; rows: string[][] }>(`${root}/balance/parse`, { text }, { readonly: true }),
  balance: (body: BalanceBody) => post<BatchPreview>(`${root}/balance/preview`, body, { readonly: true }),
  variants: (body: VariantBody) => post<BatchPreview>(`${root}/variants/preview`, body, { readonly: true }),
  apply: (kind: "balance" | "variants", body: BalanceBody | VariantBody, review: string, selected: number[]) =>
    post<BatchWritten>(`${root}/${kind}/apply`, { ...body, review, selected }),
};
