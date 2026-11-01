"""Keep static mode checks separate from runtime and asset uncertainty."""
import copy

from .drafts import DraftError
from .freshness import freshness
from .mode_store import ViewInputs


def delivery_checks(mode, result):
    checks = [{"rule": "studio.mode", "status": "满足", "blocking": False,
               "message": "模式构建器与当前视图静态引用门禁已通过"},
              {"rule": "studio.mode.runtime", "status": "待验证", "blocking": False,
               "message": "设备实测未执行"}]
    if mode == "five":
        checks.append({"rule": "studio.mode.budget", "status": "待验证", "blocking": False,
                       "message": "预算仅为敌方静态 layer0 贴图下界；队伍、召唤与运行时图集未验证"})
    messages = list(result.get("warnings", []))
    messages += ["假定在 APK，未核验：" + name for name in
                 result.get("report", {}).get("element_variants_in_apk", [])]
    for message in messages:
        checks.append({"rule": "studio.mode.warning", "status": "待验证",
                       "blocking": False, "message": message})
    return checks


def saved_preview(source, draft):
    result = copy.deepcopy(draft.get("preview") or {})
    blockers = list(result.get("blockers", []))
    try:
        if draft["baseView"] != source.version:
            raise DraftError("草稿基线已过期，请在当前视图重新预览保存")
        if any(":" not in key for key in draft["inputs"]):
            raise DraftError("旧草稿未记录多 CDN 根输入，请重新预览保存")
        inputs = ViewInputs(source)
        inputs.inputs = draft["inputs"]
        inputs.verify()
        fresh = freshness(source)
        result["freshness"] = fresh
        if fresh.get("error") or fresh["latest"] != source.version:
            raise DraftError("当前视图不是已确认的新鲜链尾")
    except (ValueError, OSError, KeyError, TypeError, RuntimeError) as exc:
        blockers.append(str(exc))
    result["blockers"] = blockers
    result["canGenerate"] = bool(result.get("canGenerate")) and not blockers
    return result
