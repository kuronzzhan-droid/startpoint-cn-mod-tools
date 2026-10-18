"""Reject known missing native enemy bands before edited levels reach delivery."""
from __future__ import annotations

from .catalog import result
from .boss_references import missing_combat_references


def enemy_level_check(document):
    dangling = missing_combat_references(document)
    if dangling:
        return result("boss.enemy-level", "问题", "战斗资源引用不闭合，无法读取活动敌人档位",
                      blocking=True, issues=dangling)
    enemies = document.get("enemies")
    terrain = document.get("terrain") or {}
    if enemies is None or terrain.get("missing") or "waves" not in terrain:
        return result("boss.enemy-level", "未执行", "缺少敌人原始行或活动地形波次，未验证原生等级档")
    active = {str(wave.get("name")) for wave in terrain["waves"]}
    issues, pending, checked = [], [], set()
    for enemy in enemies:
        if str(enemy.get("wave", "0")) not in active:
            continue
        identity = (enemy.get("table"), enemy.get("code"), enemy.get("level"))
        if identity in checked:
            continue
        checked.add(identity)
        if enemy.get("missing") is True:
            issues.append({"table": enemy.get("table"), "code": enemy.get("code"),
                           "level": enemy.get("level"), "wave": enemy.get("wave"),
                           "source": enemy.get("source")})
        elif enemy.get("missing") is not False:
            pending.append({"code": enemy.get("code"), "native_kind": enemy.get("native_kind"),
                            "reason": enemy.get("limitation", "此敌人的等级行未确认")})
    state = "问题" if issues else "待验证" if pending else "满足" if checked else "未执行"
    return result("boss.enemy-level", state, "活动波次敌人须具有客户端按原生键顺序选出的 >=任务等级档（U_3be147）",
                  blocking=bool(issues), checked_enemies=len(checked), issues=issues, limitations=pending)
