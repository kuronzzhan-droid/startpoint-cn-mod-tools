import { lazyView } from "../../lazyView";
import "./boss.css";

const BossDetail = lazyView(() => import("./BossDetail"), "BossDetail");
const BossOverview = lazyView(() => import("./BossOverview"), "BossOverview");
const BossWizard = lazyView(() => import("./BossWizard"), "BossWizard");
const ModeWorkshop = lazyView(() => import("./ModeWorkshop"), "ModeWorkshop");

/** BOSS工坊：总览 → 副本详情（遭遇 / 奖励与商店 / 调整参数 + 本次修改抽屉）→ 新建共同决战向导。 */
export function BossWorkshop({ quest, tab, sub, wizard, source }: { quest?: string; tab?: string; sub?: string; wizard?: boolean; source?: string }) {
  if (quest === "five-structure" || quest === "rogue") return <ModeWorkshop key={quest} mode={quest === "rogue" ? "rogue" : "five"} />;
  if (wizard) return <BossWizard source={source} />;
  if (quest) return <BossDetail key={quest} quest={quest} tab={tab} sub={sub} />;
  return <BossOverview />;
}
