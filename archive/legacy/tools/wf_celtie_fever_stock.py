"""星风快门共享库存；队长授予2层，能力3授予1层，各自消费。"""
CODE = "wind_spgirl_campus"
STOCK_UID = 14998901
GAIN_UID = 14998902
STOCK_NAME = "星风快门"
GAIN_NAME = "星风心得"
STOCK_STRING_ID = CODE + "_flip_stock"
GAIN_STRING_ID = STOCK_STRING_ID + "_gain"
ABILITY_STOCK_STRING_ID = STOCK_STRING_ID + "_ability"
_ACTION_PREFIX = "battle/action/skill/action/ability_skill/" + CODE + "$"
STOCK_ACTION_PATH = _ACTION_PREFIX + STOCK_STRING_ID
ABILITY_STOCK_ACTION_PATH = _ACTION_PREFIX + ABILITY_STOCK_STRING_ID
STOCK_ICON = "battle/common/unique_condition/" + STOCK_STRING_ID
GAIN_ICON = "battle/common/unique_condition/" + GAIN_STRING_ID
LEADER_SPEND_UID = 14998903
ABILITY_SPEND_UID = 14998904
LEADER_SPEND_STRING_ID = STOCK_STRING_ID + "_spent"
ABILITY_SPEND_STRING_ID = ABILITY_STOCK_STRING_ID + "_spent"
LEADER_SPEND_ACTION_PATH = _ACTION_PREFIX + LEADER_SPEND_STRING_ID
ABILITY_SPEND_ACTION_PATH = _ACTION_PREFIX + ABILITY_SPEND_STRING_ID
SPEND_MARKERS = (
    (LEADER_SPEND_UID, LEADER_SPEND_STRING_ID, LEADER_SPEND_ACTION_PATH),
    (ABILITY_SPEND_UID, ABILITY_SPEND_STRING_ID, ABILITY_SPEND_ACTION_PATH),
)


def stock_action_tree(layers=2):
    """原生 ACUnique 同时记录可用库存和历史获得层数，无额外施技事件。"""
    if layers not in (1, 2):
        raise ValueError("Starwind Shutter grant must be one or two layers")
    one = [{"min": 1, "max": 1}]
    count = [{"min": layers, "max": layers}]
    contents = [["ACUnique", uid, one] for uid in (STOCK_UID, GAIN_UID)]
    grant = ["Command", ["CreateCondition", -17, contents, one,
                         ["GenericConditionHitEffect"], False, False, "", None,
                         False, 3, count, True]]
    return ["ActionDsl", 1, ["None"], False, False, False, False, False, False,
            False, 0, ["Block", [grant]]]


def spend_action_tree(marker_uid):
    """仅由消费成功的 I629 调用；同帧标记后删除，能力2按来源各计一次。

    原生 impact 阶段先处理赋予(index8)、再处理删除(index9)。不能改用
    ConsumeUniqueCondition(index13)，后者优先处理，会在标记生成前执行。
    """
    if marker_uid not in (LEADER_SPEND_UID, ABILITY_SPEND_UID):
        raise ValueError("unknown Starwind Shutter consumption source")
    one = [{"min": 1, "max": 1}]
    combo = ["Command", ["AddCombo", [{"min": 7, "max": 7}]]]
    mark = ["Command", ["CreateCondition", -17,
            [["ACUnique", marker_uid, one]], one, ["None"], False, False,
            "", None, False, 3, one, True]]
    clear = ["Command", ["DeleteCondition", -17, ["DCUnique", marker_uid],
                         1, 2, "", ["Default"]]]
    return ["ActionDsl", 1, ["None"], False, False, False, False, False, False,
            False, 0, ["Block", [combo, mark, clear]]]


def spend_unique_rows():
    """有效图标作安全依赖；标记在同次 impact 阶段内创建并删除。"""
    return {str(uid): [[sid, "快门消费结算", STOCK_ICON, "1", "1",
            "(None)", "(None)", "(None)", "(None)", "false", "true",
            "0", "0", "true", "(None)"]]
            for uid, sid, _ in SPEND_MARKERS}
