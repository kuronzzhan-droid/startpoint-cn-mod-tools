"""Read encounter-scoped multiplayer inputs without changing draft input locks."""
from __future__ import annotations

from wf.boss import schema as s
from wf.boss.behavior_identity import GENERAL_FUNNEL, STANDARD_FUNNEL, WATCH
from wf.boss.behavior_model import Programs, STATES
from wf.boss.esdl import decode_esdl

from .boss_common import CandidateView
from .boss_preload import programs, tier, walk

ACTION_SUFFIX = ".action.dsl.amf3.deflate"
ESDL_SUFFIX = ".esdl.amf3.deflate"
FUNNEL_STATES = "master/battle/boss/funnel/general_funnel_state.orderedmap"
ZAKO_STATES = "master/battle/zako/general_zako_state.orderedmap"
MULTIBALL = "master/battle/multiball/multiball.orderedmap"
# ActionDslAnalyzer.as:171-197,364-366 enumerates these external action paths.
ACTION_REFERENCES = {"CreateBombMultiball": 6, "CreateTornado": 7, "CreateTargetAttack": 5}


class _ReadOnlyView:
    def __init__(self, view):
        from wf.boss.edit_state import BossEditState
        self.source = getattr(view, "view", view)
        self.edit = self.source if isinstance(self.source, BossEditState) else None

    def raw(self, logical):
        if self.edit is not None:
            if logical in self.edit.client:
                return self.edit.client[logical]
            return CandidateView(self.edit.base).raw(logical)
        return CandidateView(self.source).raw(logical)


def _programs(value):
    # action_base_path is a prefix, not an action. In real ESDL it ends in '$'.
    # StandardEnemySource.as:6494-6503 treats an empty filePath as no action.
    for path in programs(value):
        path = path.removesuffix(ACTION_SUFFIX)
        if path and not path.endswith(("$", "/")):
            yield path


def _decoded_rows(node):
    if isinstance(node, str):
        return s.parse_rows(node)
    if isinstance(node, dict):
        return {key: _decoded_rows(value) for key, value in node.items()}
    raise ValueError("expected ordered-map CSV leaf")


def _rows(tree):
    for node in walk(tree):
        if isinstance(node, list) and node and all(isinstance(value, str) for value in node):
            yield node


class _Inputs:
    def __init__(self, view):
        self.view = _ReadOnlyView(view)
        self.graph = Programs(self.view)
        self.trees, self.tables, self.diagnostics = {}, {}, []
        self.queue, self.seen, self.funnels = [], set(), set()

    def issue(self, logical, error):
        self.diagnostics.append(f"{logical}: {error}")

    def table(self, logical):
        if logical not in self.tables:
            import wf_mod_tool as maps
            import wf_quest_lib as codec
            try:
                raw = self.view.raw(logical)
                if raw is None:
                    raise FileNotFoundError("missing table")
                index = maps.read_orderedmap_raw_rows_from_bytes(raw, logical)
                self.tables[logical] = codec.parse_node(raw) if index.keys else {}
            except Exception as exc:  # Advisory failures are retained per input.
                self.issue(logical, f"{type(exc).__name__}: {exc}")
                self.tables[logical] = {}
        return self.tables[logical]

    def subtree(self, logical, path, *, required=False):
        node = s.get_leaf(self.table(logical), path)
        if node is None:
            if required:
                self.issue(logical + "#/" + "/".join(path), "missing table subtree")
            return None
        decoded = _decoded_rows(node)
        target = self.trees.setdefault(logical, {})
        for key in path[:-1]:
            target = target.setdefault(key, {})
        target[path[-1]] = decoded
        return decoded

    def roots(self, node, level):
        for value in walk(node):
            if isinstance(value, str):
                self.queue.extend((program, level) for program in _programs(value))

    def standard(self, value, level):
        if not s.present(value):
            self.issue("EnemyDsl", "missing ESDL path")
            return
        logical = value if value.endswith(ESDL_SUFFIX) else value + ESDL_SUFFIX
        if logical not in self.trees:
            try:
                raw = self.view.raw(logical)
                if raw is None:
                    raise FileNotFoundError("missing ESDL")
                self.trees[logical] = decode_esdl(raw)["tree"]
            except Exception as exc:
                self.issue(logical, f"{type(exc).__name__}: {exc}")
                return
        tree = self.trees[logical]
        base = tree.get("action_base_path") or ""
        for node in walk(tree):
            # WatchContent.ExecuteAction: StandardEnemySource.as:5253-5268.
            if isinstance(node, list) and len(node) == 4 and node[0] == "ExecuteAction":
                for value in node[1]:
                    if isinstance(value, str) and value:
                        self.roots(base + value, level)
            if not isinstance(node, dict):
                continue
            value = node.get("filePath")
            if isinstance(value, str) and value:
                # Same concatenation as StandardEnemySource.as:6501-6503.
                self.roots(base + value, level)
            # Type.TBoss initialization actions use the same prefix (as:690-697).
            for value in node.get("pre_action_path") or []:
                if isinstance(value, str) and value:
                    self.roots(base + value, level)

    def general(self, enemy):
        self.native(enemy.get("row", []), str(enemy.get("code", "")),
                    enemy.get("level", 1), STATES, 42, "1")

    def native(self, row, code, level, states, routine_column, watch_kind=None):
        routine = s.cell(row, routine_column)
        # Generated *Values parsers: GeneralBossValues.as:1150-1220,2151;
        # GeneralFunnelValues.as:1072-1090,2021; GeneralZakoValues.as:376-565.
        columns = {STATES: (109, *range(111, 161)),
                   FUNNEL_STATES: range(89, 139), ZAKO_STATES: range(30, 40)}[states]
        for column in columns:
            self.roots(s.cell(row, column), level)
        if s.present(routine):
            self.subtree(states, [routine], required=True)
            if watch_kind is not None:
                watches = self.subtree(WATCH, [watch_kind, code, routine])
                for watch in _rows(watches):
                    # GeneralEnemyWatchValues.as:398-418: kind 5 is ExecuteAction.
                    if s.cell(watch, 14) == "5":
                        self.roots(s.cell(watch, 18), level)
        else:
            self.issue(states, f"{code}: missing routine in source c{routine_column}")

    def spawn(self, node, level):
        if not isinstance(node, list) or len(node) < 2:
            return
        if node[0] == "SpawnAlterEgo":
            kind, code = node[0], node[1]
        elif node[0] == "CreateSummonsMultiball" and len(node) > 2:
            kind, code = node[0], node[2]
        elif node[0] == "SpawnFunnel" and isinstance(node[1], list) and len(node[1]) > 1:
            kind, code = node[1][:2]
        else:
            return
        key = kind, str(code), str(level)
        if key in self.funnels:
            return
        self.funnels.add(key)
        # ActionEvaluator.as:3921-3931 selects these three table-backed sources.
        # ActionDslAssetResolver.as:694-695 resolves SpawnAlterEgo as GeneralBoss.
        logical = {"Funnel": GENERAL_FUNNEL, "StandardFunnel": STANDARD_FUNNEL,
                   "Zako": s.GENERAL_ZAKO, "SpawnAlterEgo": s.GENERAL_BOSS,
                   "CreateSummonsMultiball": MULTIBALL}.get(kind)
        if logical is None:
            self.issue(f"SpawnFunnel/{kind}/{code}", "unmapped summon kind")
            return
        row = tier(self.table(logical).get(str(code)), level)
        if not row:
            self.issue(f"{logical}#/{code}", f"missing summon row/tier for level {level}")
        elif kind == "CreateSummonsMultiball":
            # AssetResolver.as:620-625,1063-1071; MultiballValues.as:155-186.
            self.roots(s.cell(row, 9), level)
            support = [str(column) for column in range(20, 24) if s.present(s.cell(row, column))]
            if support:
                self.issue(f"{logical}#/{code}", "support ability dependencies not expanded (c"
                           + ",c".join(support) + "; ActionDslAssetResolver.as:1080-1157)")
        elif kind == "StandardFunnel":
            self.standard(s.cell(row, 0), level)
        elif kind == "Funnel":
            # GeneralFunnelValues.as:829-830; FunnelSource.as:84-86.
            self.native(row, str(code), level, FUNNEL_STATES, 37, "2")
        elif kind == "SpawnAlterEgo":
            self.native(row, str(code), level, STATES, 42, "1")
        else:
            # GeneralZakoValues.as:207-208; ZakoSource.as:53-55,66-75.
            self.native(row, str(code), level, ZAKO_STATES, 17)

    def actions(self):
        while self.queue:
            program, level = self.queue.pop()
            key = program, str(level)
            if key in self.seen:
                continue
            self.seen.add(key)
            if len(self.graph.trees) >= 800 and program not in self.graph.trees:
                self.issue("action closure", "exceeds 800 programs")
                break
            logical = program + ACTION_SUFFIX
            try:
                tree = self.graph.load(program)
                if tree is None:
                    self.issue(logical, "missing action DSL")
                    continue
                self.trees[logical] = tree
                for node in walk(tree):
                    if not (isinstance(node, list) and len(node) == 2 and node[0] == "Command"
                            and isinstance(node[1], list) and node[1]):
                        continue
                    command = node[1]
                    index = ACTION_REFERENCES.get(command[0])
                    if index is not None and len(command) > index:
                        self.roots(command[index], level)
                    self.spawn(command, level)
            except Exception as exc:
                self.issue(logical, f"{type(exc).__name__}: {exc}")


def collect_inputs(document, view):
    """Return decoded logical-file inputs and non-blocking incomplete reasons.

    State/watch CSV leaves become arrays of rows, retaining original map keys
    and zero-based columns. All slots and initialization/watch programs are
    scanned even when no marker fires them; native specials remain explicit.
    """
    inputs = _Inputs(view)
    seen = set()
    for enemy in document.get("enemies", []):
        if enemy.get("kind") not in {"boss", "zako"}:
            continue
        key = (enemy.get("table"), enemy.get("code"), str(enemy.get("level", 1)),
               tuple(enemy.get("row", [])))
        if key in seen:
            continue
        seen.add(key)
        try:
            if enemy.get("table") == s.GENERAL_BOSS:
                inputs.general(enemy)
            elif enemy.get("table") == s.STANDARD_BOSS:
                inputs.standard(s.cell(enemy.get("row", []), 1), enemy.get("level", 1))
            elif enemy.get("table") == s.GENERAL_ZAKO:
                inputs.native(enemy.get("row", []), str(enemy.get("code", "")),
                              enemy.get("level", 1), ZAKO_STATES, 17)
            else:
                inputs.issue(str(enemy.get("code")), "native-special boss has no generic DSL mapping")
        except Exception as exc:
            inputs.issue(str(enemy.get("code")), f"{type(exc).__name__}: {exc}")
    inputs.actions()
    return inputs.trees, sorted(set(inputs.diagnostics))
