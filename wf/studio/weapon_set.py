"""Optional weapon-set operations on the existing replayable draft overlay."""
import json

from wf.boss import schema as s
from wf.boss.shop_edit import one, item_reference
from wf.boss.shop_model import ITEM, SOUL
from wf.boss.weapon_rules import AWAKENING, CUSTOM
from wf.rules.catalog import result
from wf.view.base149 import join

DISSOLVE = "assets/equipment_dissolve.json"
AWAKENING_CAPABILITY = "equipment-awakening-material-v1"


def write_row(state, logical, key, row):
    state.set_leaf(logical, [key], join(row), new=key not in state.table(logical))


def material(state, identity):
    from .ids import canonical
    canonical("soul_item", identity)
    one(state, ITEM, identity, 23)
    item_reference(state, identity)
    # A readable client row alone does not make a server inventory currency.
    if int(identity) not in state.server("assets/item_ids.json"):
        raise ValueError(f"material is absent from server item_ids: {identity}")


def restrict_awakening(state, wid, identity):
    material(state, identity)
    equipment = one(state, s.EQUIPMENT, wid, 16)
    document = state.server(AWAKENING)
    if state.raw(CUSTOM) is None:
        raise ValueError("missing custom_ability_string baseline")
    updates = {}
    for name, value in (("materialByEquipment", int(identity)), ("rarityOverrides", int(equipment[11]))):
        if not isinstance(document.get(name, {}), dict):
            raise ValueError(f"invalid awakening section: {name}")
        updates[name] = {**document.get(name, {}), wid: value}
    state.set_server_keys(AWAKENING, updates)
    write_row(state, CUSTOM, "awakening_material_" + wid, [identity])
    return result("weapon.awakening-material", "待验证",
        "材料替代仅接受指定道具；仍允许重复本体突破。需要客户端 equipment-awakening-material-v1 "
        "及服务端 equipment_awakening_material.materialByEquipment 白名单；数据不证明已部署。",
        materialId=identity, clientCapability=AWAKENING_CAPABILITY,
        duplicateEquipmentAllowed=True)


def disable_soul(state, wid):
    equipment = one(state, s.EQUIPMENT, wid, 16)
    soul = equipment[10]
    one(state, ITEM, soul, 23)
    if not state.table(SOUL).get(soul):
        raise ValueError("equipment base ability reference is missing")
    document = state.server(DISSOLVE)
    if (wid in getattr(state, "weapon_donors", {})
            and wid in json.loads(state.server_original[DISSOLVE])):
        raise ValueError("new weapon ID collides with existing equipment_dissolve entry")
    if wid not in document:
        # A cloned weapon keeps the donor's dissolve payout and only changes
        # the native soul switch/reference. Existing weapons need their own row.
        donor = getattr(state, "weapon_donors", {}).get(wid)
        if donor is None or donor not in document:
            raise ValueError("missing complete equipment_dissolve donor entry")
        value = dict(document[donor])
    else:
        value = dict(document[wid])
    value.update(ability_soul_id=int(soul), generate_ability_soul=False)
    equipment[9] = "false"
    write_row(state, s.EQUIPMENT, wid, equipment)
    state.set_server_keys(DISSOLVE, {wid: value})
    return result("weapon.no-soul", "满足", "禁止产出魂珠；内部 item 与 ability_soul 保留，基础能力由武器本体读取。",
                  internalSoulId=soul, generatedSoul=False, abilitySource="equipment_base")


def apply_set(state, spec, reserved):
    from .weapon_set_shops import category, exchange
    from .weapon_set_enhancement import enhance, move_category
    wid = spec["id"]
    one(state, s.EQUIPMENT, wid, 16)
    checks = []
    if spec.get("noSoul", False):
        checks.append(disable_soul(state, wid))
    selected = None
    if "enhancementCategory" in spec:
        selected = category(state, spec["enhancementCategory"], "enhancement", reserved)
    if "enhancement" in spec:
        enhance(state, wid, spec["enhancement"], selected, reserved)
    elif selected is not None:
        move_category(state, wid, selected)
    if "exchange" in spec:
        exchange(state, wid, spec["exchange"], reserved)
    if "awakeningMaterial" in spec:
        checks.append(restrict_awakening(state, wid, spec["awakeningMaterial"]))
    state.weapon_checks = [*getattr(state, "weapon_checks", []), *checks,
        result("weapon.set-rows", "满足", "已在内存中生成所选武器配置及服务端镜像；共享表保留旧键。")]


def preview_rows(state):
    """Expose final rows, not intermediate writes from clone + set replay."""
    from wf.boss.edit_state import leaf
    paths = {(entry["table"], tuple(entry["path"])) for entry in state.changes if not entry.get("resource")}
    clients = [{"table": table, "path": list(path), "value": leaf(state.table(table), path)}
               for table, path in sorted(paths)]
    servers = []
    for target, raw in sorted(state.servers.items()):
        before = json.loads(state.server_original[target] or b"{}")
        after = json.loads(raw)
        if isinstance(after, dict):
            changed = {key: value for key, value in after.items() if before.get(key) != value}
        else:
            changed = [value for value in after if value not in before]
        servers.append({"target": target, "updates": changed})
    return {"client": clients, "server": servers}


def requirements(state):
    from wf.caps.weapon_requirements import weapon_requirements
    return weapon_requirements(state.client, state.servers,
                               read_raw=lambda path: state.original.get(path))
