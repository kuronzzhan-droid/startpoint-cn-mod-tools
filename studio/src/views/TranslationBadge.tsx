import { TranslationSource } from "../abilityGlossary";
import "../glossary.css";

export function TranslationBadge({ value }: { value?: TranslationSource }) {
  const info = value ?? { source: "直译", uncertain: true, reason: "工具解析，语义待人工核实", evidence: [] };
  return <span class={"tag translation-source" + (info.uncertain ? " translation-uncertain" : "")}
    title={[info.reason, ...info.evidence].join("\n")}>{info.source}{info.uncertain ? " · 待核实" : ""}</span>;
}
