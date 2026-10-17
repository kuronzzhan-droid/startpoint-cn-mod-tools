# -*- coding: utf-8 -*-
"""收方视角的公开链体检:只看仓内提交物,CI 上干净检出即可跑。

作者本地的 `.cdn/` 全库 gitignored,里面那几百条自发布边从不进公开仓。收方能拿到的
只有 ①他自己的官方 CN dump(到 manifest 的 cdn_version)+ ②clone 到的
`assets/asset-patch/active`。所以链断在收方那侧,作者本地永远看不出来 ——
2026-08-02 就真的发生过:公开链从 1.4.90 起、官方 dump 只到 1.4.54,中间一条边都没有,
收方服务端算出的可达版本停在 1.4.54,给客户端返回 0 个 diff 组(=「你已是最新」),
四个自制角色/塔/武器一样都下发不了。

边的解析规则与服务端 src/lib/cn-asset-graph.ts 的 ARCHIVE_RE 保持一致。
"""
from __future__ import annotations

import json
import re
import unittest
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PATCH_ROOT = REPO_ROOT / "assets" / "asset-patch"
ACTIVE = PATCH_ROOT / "active"
MANIFEST = PATCH_ROOT / "manifest.json"

# 与 cn-asset-graph.ts:66 的 ARCHIVE_RE 同构
ARCHIVE_RE = re.compile(
    r"^pinball-(\d+\.\d+\.\d+)-(\d+\.\d+\.\d+)-([1-9]\d*)-(.+)\.zip$"
)


def _ver(text: str) -> tuple[int, ...]:
    return tuple(int(part) for part in text.split("."))


def _edges() -> dict[str, set[str]]:
    graph: dict[str, set[str]] = defaultdict(set)
    for path in ACTIVE.glob("*.zip"):
        match = ARCHIVE_RE.match(path.name)
        if match is not None:
            graph[match.group(1)].add(match.group(2))
    return graph


def _reachable(start: str, graph: dict[str, set[str]]) -> set[str]:
    seen = {start}
    stack = [start]
    while stack:
        for nxt in graph.get(stack.pop(), ()):
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return seen


@unittest.skipUnless(ACTIVE.is_dir(), "assets/asset-patch/active 不在(平铺工具仓布局)")
class PublicChainReachabilityTest(unittest.TestCase):
    def test_official_dump_tail_reaches_the_newest_published_version(self):
        """收方从官方 dump 的链尾出发,必须能走到公开链的最高版本。"""
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        start = manifest["cdn_version"]
        graph = _edges()
        self.assertTrue(graph, "assets/asset-patch/active 里没有可解析的边")

        newest = max(
            (v for tos in graph.values() for v in tos),
            key=_ver,
        )
        reached = _reachable(start, graph)
        self.assertIn(
            newest,
            reached,
            f"公开链断了:收方从 {start} 出发只能走到 "
            f"{max(reached, key=_ver)},到不了 {newest}。"
            f"补法:python mod-tools/wf_pack_consolidate.py build "
            f"--from-ver {max(reached, key=_ver)} --to-ver <下一段起点> "
            f"--tag bridge --max-zip-mib 5,产物放进 active/ 并在 manifest 加条目。",
        )

    def test_every_active_zip_is_declared_in_the_manifest_chain(self):
        """磁盘上的包与 manifest 的 chain 必须互相覆盖,不留孤儿也不缺文件。"""
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        declared = {
            name
            for patch in manifest["patches"]
            for name in patch.get("chain", ())
        }
        on_disk = {path.name for path in ACTIVE.glob("*.zip")}
        self.assertFalse(
            declared - on_disk, f"manifest 声明了但磁盘上没有: {sorted(declared - on_disk)}"
        )
        self.assertFalse(
            on_disk - declared, f"磁盘上有但 manifest 没声明: {sorted(on_disk - declared)}"
        )

    def test_edge_sequence_numbers_are_unique_per_edge(self):
        """同一条边的 seq 必须唯一。

        active/ 是扁平单目录,而 .cdn 里同一条边的 common/medium/android 三个包**允许同名**
        (各自的 seq 都从 1 起)。照搬过来会同名相撞、只存下一个 —— 2026-08-02 就因此
        丢了 45 个文件(43 medium_upload + 2 android_upload,多是立绘/cut-in 大图)。
        所以放进 active/ 的包一律要全局唯一 seq 重编号。
        """
        seen: dict[tuple[str, str], set[str]] = defaultdict(set)
        for path in ACTIVE.glob("*.zip"):
            match = ARCHIVE_RE.match(path.name)
            if match is None:
                continue
            edge = (match.group(1), match.group(2))
            seq = match.group(3)
            self.assertNotIn(
                seq,
                seen[edge],
                f"边 {edge[0]}->{edge[1]} 的 seq {seq} 重复(扁平目录同名冲突,须重编号)",
            )
            seen[edge].add(seq)


if __name__ == "__main__":
    unittest.main()
