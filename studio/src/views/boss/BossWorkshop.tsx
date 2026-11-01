import { BossDetail } from "./BossDetail";
import { BossOverview } from "./BossOverview";
import { BossWizard } from "./BossWizard";
import "./boss.css";
import { ModeWorkshop } from "./ModeWorkshop";

/** BOSS工坊：总览 → 副本详情（遭遇 / 奖励与商店 / 调整参数 + 本次修改抽屉）→ 新建共同决战向导。 */
export function BossWorkshop({ quest, tab, sub, wizard, source }: { quest?: string; tab?: string; sub?: string; wizard?: boolean; source?: string }) {
  if (quest === "five-structure" || quest === "rogue") return <ModeWorkshop key={quest} mode={quest === "rogue" ? "rogue" : "five"} />;
  if (wizard) return <BossWizard source={source} />;
  if (quest) return <BossDetail quest={quest} tab={tab} sub={sub} />;
  return <BossOverview />;
}
