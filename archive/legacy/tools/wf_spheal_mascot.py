"""海豹球五星吉祥物：候选包入口，所有写入仅限 flow workspace。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from wf_seasonal7_common import S7Pack
from wf_seasonal7_specs import SeasonalSpec, occupancy_problems

SPEC = SeasonalSpec(
    key="spheal", cid=129990, code="spheal_mascot", pkg_id="spheal-mascot-20260919",
    workspace="work/character_packs/spheal-mascot-20260919",
    template_id=321009, template_code="cute_fafnir", template_element=1,
    element=1, element_token="Blue", rarity=5, pf_type=3, stance="Supporter",
    identity=129990, template_identity=321009, theme="海豹球·吉祥物",
    texts={
        "name": "海豹球", "furigana": "タマザラシ", "title": "滚滚的潮汐伙伴",
        "profile": "圆滚滚的海豹球，喜欢在浅水中拍着小鳍玩耍。比起战斗，更擅长用开心的笑容为伙伴打气。吃饱后滚到大家身边，就是它最喜欢的冒险。",
        "skill1": "扑通！水花时间", "skill2": "扑通！水花时间＋",
        "desc1": "恢复全体参战者少量生命值，并暂时提升火属性耐性。",
        "desc2": "恢复全体参战者少量生命值，并暂时提升火属性耐性。",
        "leader": "今天也要一起玩！", "cv": "—",
    },
    backdrop_colors=((105, 190, 235), (37, 93, 146)),
    requires_client_base="1.4.927",
)


class SphealPack(S7Pack):
    def template_raw(self, logical):
        rows = super().template_raw(logical)
        # 法夫来自剧情，没有抽卡声音行。采用原生水五星的属性抽卡音效。
        if logical == "master/character/character_gacha_sound.orderedmap" and "321009" not in rows:
            rows = dict(rows)
            rows["321009"] = rows["121001"]
        return rows


def context():
    return SphealPack(SPEC)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step", choices=("check", "scaffold", "kit", "media", "manifest"))
    args = parser.parse_args()
    pack = context()
    if args.step == "check":
        result = occupancy_problems([SPEC], repo_root=pack.root, store=pack.store)
    elif args.step == "scaffold":
        from wf_seasonal7_tables import build as tables
        from wf_seasonal7_assets import build as assets
        result = {"tables": tables(pack), "assets": assets(pack)}
    elif args.step == "kit":
        from wf_spheal_mascot_kit import build
        result = build(pack)
    elif args.step == "media":
        from wf_spheal_mascot_media import build
        result = build(pack)
    else:
        from wf_seasonal7_manifest import build
        result = build(pack)
    pack.write_evidence(f"spheal-{args.step}.json", result)
    print(json.dumps({"step": args.step, "evidence": str(pack.evidence),
                      "result": result if args.step == "check" else "written"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
