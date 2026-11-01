export interface TranslationSource {
  source: "官方原文" | "ui_string 拼接" | "直译" | "人工";
  uncertain: boolean;
  reason: string;
  evidence: string[];
}

/** Read-only vocabulary. Numeric edits still use the existing onCell path. */
export interface GlossaryEntry {
  translation: TranslationSource;
  value: string;
  en: string;
  cn: string;
  official: string | null;
  officialTemplate: string | null;
  officialKey: string | null;
  officialArguments: Record<string, { text: string; sources: { key?: string; text?: string; evidence?: string[]; enumToken?: string }[] }>;
  mappingStatus: "as3" | "guess" | "none";
  evidence: string[];
  uses: number;
}

export interface FieldRule {
  enum?: string;
  multiple?: boolean;
  format?: string;
  kindColumn?: number;
  group?: string;
  endpoints?: number[];
}

export interface AbilityGlossary {
  groups: Record<string, { label: string; values: GlossaryEntry[] }>;
  fields: Record<string, Record<string, FieldRule>>;
  strengthCountKinds: Record<string, string[]>;
  formats: Record<string, { divisor: number; unit: string; fps?: number; countDivisor?: number; note?: string }>;
  note: string;
}

export function matches(entry: GlossaryEntry, query: string): boolean {
  const text = `${entry.value} ${entry.official ?? ""} ${entry.cn} ${entry.en}`.toLowerCase();
  return query.toLowerCase().trim().split(/\s+/).every((term) => text.includes(term));
}

export function enumEntries(glossary: AbilityGlossary, rule: FieldRule, value: string) {
  const values = rule.multiple ? value.split(/[,/]/).map((v) => v.trim()).filter(Boolean) : [value.trim()];
  return values.map((v) => ({ value: v, entry: glossary.groups[rule.enum!]?.values.find((e) => e.value === v) }));
}

function number(value: number): string { return String(Number(value.toPrecision(8))); }

export function numericMeaning(glossary: AbilityGlossary, rule: FieldRule, value: string, row: string[]): string | null {
  if (!/^-?\d+$/.test(value.trim()) || Number(value) === 0 || !rule.format) return null;
  const raw = Number(value);
  if (!Number.isFinite(raw)) return null;
  const format = glossary.formats[rule.format];
  if (!format) return null;
  if (rule.format === "threshold" && raw >= format.countDivisor! && raw % format.countDivisor! === 0) {
    return `${number(raw / format.countDivisor!)}（次 / 层 / 个，依类型）`;
  }
  if (rule.format === "strength") {
    const kind = row[rule.kindColumn!];
    if (!glossary.groups[rule.group!]?.values.some((e) => e.value === kind)) return null;
    if (glossary.strengthCountKinds[rule.group!]?.includes(kind)
      && rule.endpoints?.every((i) => (Number(row[i]) || 0) % format.countDivisor! === 0)) {
      return `${number(raw / format.countDivisor!)}（计数 / 层级）`;
    }
  }
  const converted = raw / format.divisor;
  return `${number(converted)}${format.unit === "%" ? "" : " "}${format.unit}`
    + (format.fps ? `（${number(converted / format.fps)} 秒）` : "");
}
