"""作者确认的840后深渊规格；仅修改990001，不重建竞速或其他池。"""
from copy import deepcopy
from fractions import Fraction

from wf_content_gacha import BIG_BOSS_ZERO, MINIBOSSES, probability, update_entries

FEATURED = (149990, 119989, 149989, 169989, 149988)
LEGACY_22 = (129952, 169980, 169994, 169995, 179981, 119996, 119997,
             129997, 129999, 139997, 139998, 139999, 149996, 149997,
             149998, 149999, 169998, 169999, 179999, 149995, 169996, 169997)
EXCHANGEABLE = frozenset((129992, 139995, 129952))
ANCHOR = 169997


def revise_abyss(gacha):
    """纯函数：5新置顶、15小Boss紧随巴萨拉卡，概率与展示同源。"""
    source = gacha["990001"]
    if source["rankRates"] != {"normal": [150, 350, 500], "multiGuarantee": [150, 850]}:
        raise ValueError("unreviewed Abyss rank-rate baseline")
    entries = source["pool"]["1"]
    ids = [int(e["id"]) for e in entries]
    required = set(FEATURED) | set(LEGACY_22) | EXCHANGEABLE | MINIBOSSES
    if len(ids) != len(set(ids)) or not required <= set(ids):
        raise ValueError("missing/duplicate reviewed Abyss character")
    if [cid for cid in ids if cid in LEGACY_22] != list(LEGACY_22):
        raise ValueError("legacy water-witch-to-Vaseraga order changed")
    result = deepcopy(gacha)
    abyss = result["990001"]
    fixed = {cid: 1000 for cid in set(LEGACY_22) | EXCHANGEABLE}
    fixed.update({cid: 2000 for cid in MINIBOSSES})
    fixed.update({cid: 2500 for cid in FEATURED})
    fixed.update({cid: 0 for cid in set(ids) & BIG_BOSS_ZERO})
    update_entries(abyss, fixed, 150000, exchangeable=EXCHANGEABLE)
    by_id = {int(e["id"]): e for e in abyss["pool"]["1"]}
    for cid in FEATURED:
        by_id[cid]["isRateUp"] = True
        by_id[cid]["isExchangeable"] = False
    for cid in MINIBOSSES:
        by_id[cid]["isRateUp"] = True
        by_id[cid]["isExchangeable"] = False
    order = list(FEATURED)
    for cid in ids:
        if cid not in FEATURED and cid not in MINIBOSSES:
            order.append(cid)
        if cid == ANCHOR:
            order.extend(sorted(MINIBOSSES))
    abyss["pool"]["1"] = [by_id[cid] for cid in order]
    if len(order) != len(ids) or len(set(order)) != len(ids):
        raise AssertionError("Abyss ordering lost or duplicated an entry")
    for cid, weight in fixed.items():
        if probability(abyss, cid) != Fraction(weight, 1000000):
            raise AssertionError(f"incorrect actual Abyss probability: {cid}")
    if any(result[pid] != value for pid, value in gacha.items() if pid != "990001"):
        raise AssertionError("Abyss revision changed another pool")
    return result


def metadata():
    return dict(featured_order=list(FEATURED), featured_percent="0.25",
                featured_rate_up=True, featured_exchangeable=False, legacy_22=list(LEGACY_22),
                legacy_percent="0.1", big_boss_zero_overrides_legacy=True,
                explicitly_exchangeable=sorted(EXCHANGEABLE),
                miniboss_after=ANCHOR, miniboss_percent="0.2",
                miniboss_rate_up=True, miniboss_exchangeable=False,
                fixed_five_star_weight=65500, remaining_five_star_weight=84500,
                racing_untouched=True)


def highlight_featured(gacha):
    """既有深渊窄修：仅置顶五人的红底/UP 标记，不重算概率或排序。"""
    source = gacha['990001']
    entries = source['pool']['1']
    if [int(e['id']) for e in entries[:5]] != list(FEATURED):
        raise ValueError('featured order is not the reviewed installed baseline')
    if any(probability(source, cid) != Fraction(1, 400) for cid in FEATURED):
        raise ValueError('featured probability is not 0.25 percent')
    if any(e.get('isExchangeable') for e in entries[:5]):
        raise ValueError('featured entry unexpectedly exchangeable')
    result = deepcopy(gacha)
    for entry in result['990001']['pool']['1'][:5]:
        entry['isRateUp'] = True
    return result
