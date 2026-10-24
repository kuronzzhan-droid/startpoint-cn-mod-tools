"""Small, conservative reader for the decompiler's enum/switch dialect.

This is not an AS3 interpreter. Unknown switch selectors are skipped; ordinary
if branches may contribute alternative keys. No client code is executed.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

from scripts.ability_as3_bindings import record_binding


# Entry points, not every method that happens to take this enum as context.
DESCRIBERS = {
    "ConditionTargetKind": {"stringfyConditionTarget", "stringfyCondtionTargetDuring"},
    "ConditionChangeContent": {"stringfyConditionChangeContent", "stringfyConditionCharacterContent", "stringfyConditionBattleContent"},
    "CommonAbilityContent": {"stringfyCommonContent"},
    "CommonAbilityCharacterContent": {"stringfyCommonCharacterContent"},
    "CommonAbilityBattleContent": {"stringfyCommonBattleContent"},
    "AbilityTargetKind": {"stringfyAbilityTarget"},
    "DuringAbilityTriggerPullerKind": {"stringfyDuringTriggerPuller", "stringfyDuringTriggerPullerSumOf"},
    "InstantAbilityTriggerPullerKind": {"stringfyInstantTriggerPuller"},
    "InstantAbilityInstantBattleContent": {"stringfyInstantBattleContent"},
    "InstantAbilityInstantCharacterContent": {"stringfyInstantCharacterContent"},
    "InstantAbilityMultiplyTrigger": set(),
    "Option": set(),
}


@dataclass(frozen=True)
class EnumValue:
    type: str
    index: int
    args: tuple = ()


def split_args(text):
    parts, start, depth = [], 0, 0
    for match in re.finditer(r'"(?:\\.|[^"\\])*"|[()[\],]', text):
        char = match[0]
        if char in ("(", "["):
            depth += 1
        elif char in (")", "]"):
            depth -= 1
        elif char == "," and depth == 0:
            parts.append(text[start:match.start()].strip())
            start = match.end()
    return parts + [text[start:].strip()] if text.strip() else []


def matching(text, start, left="(", right=")"):
    depth = 0
    for match in re.finditer(r'"(?:\\.|[^"\\])*"|[(){}]', text[start:]):
        if match[0] == left:
            depth += 1
        elif match[0] == right:
            depth -= 1
            if not depth:
                return start + match.start()
    raise ValueError("Unbalanced AS3 block")


def prune_ternaries(text, reader, env):
    """Resolve literal-key alternatives guarded by a known boolean."""
    pattern = r'(\w+) \? ("[^"\n]*") : ("[^"\n]*"|\()'
    for match in reversed(list(re.finditer(pattern, text))):
        flag = reader.evaluate(match[1], env)
        if flag is None:
            continue
        end = matching(text, match.start(3)) + 1 if match[3] == "(" else match.end()
        chosen = match[2] if flag else text[match.start(3):end]
        text = text[:match.start()] + chosen + text[end:]
    return text


class Reader:
    def __init__(self, root):
        self.root = root
        self.enums, self.functions, self.sources = {}, [], {}
        paths = sorted((root / "pinball/common/data/ability").rglob("*.as"))
        paths += sorted((root / "pinball/common/data/character/condition").glob("*.as"))
        element_tools = root / "pinball/common/data/general/ElementKindTools.as"
        if element_tools.is_file():
            paths.append(element_tools)
        for path in paths:
            src = path.read_text(encoding="utf-8-sig")
            rel = path.relative_to(root).as_posix()
            self.sources[rel] = src
            for name, index in re.findall(r'new ' + re.escape(path.stem) + r'\("(\w+)",(\d+),', src):
                self.enums[path.stem, name] = int(index)
            for match in re.finditer(r'^      (?:override )?public (?:static )?function (\w+)\(([^\n]*)\)[^\n]*\n      \{(.*?)\n      \}', src, re.M | re.S):
                name, params, body = match.groups()
                self.functions.append({"class": path.stem, "name": name, "params": params,
                                       "body": body, "path": rel,
                                       "line": src.count("\n", 0, match.start(3)) + 1})

    def evaluate(self, expr, env):
        expr = expr.strip()
        if expr in env:
            return env[expr]
        if re.fullmatch(r"-?\d+", expr):
            return int(expr)
        if expr in ("true", "false"):
            return expr == "true"
        compare = re.fullmatch(r"(.+?) (==|!=|>=|<=|>|<) (.+)", expr)
        if compare:
            left, right = self.evaluate(compare[1], env), self.evaluate(compare[3], env)
            if left is not None and right is not None:
                return {"==": lambda: left == right, "!=": lambda: left != right,
                        ">=": lambda: left >= right, "<=": lambda: left <= right,
                        ">": lambda: left > right, "<": lambda: left < right}[compare[2]]()
        if expr.startswith("!"):
            value = self.evaluate(expr[1:], env)
            return not value if value is not None else None
        if expr.startswith("OrCharacterGroup_Impl_.resolveOptional("):
            return EnumValue("Option", -1)
        if expr == "Option.None":
            return EnumValue("Option", 1)
        if expr.startswith("Option.Some("):
            return EnumValue("Option", 0, (self.evaluate(expr[12:-1], env),))
        cast = re.fullmatch(r"(?:int|Number|Boolean)\((.*)\)", expr)
        if cast:
            return self.evaluate(cast[1], env)
        prop = re.fullmatch(r"(\w+)((?:\.params\[\d+\])*)(\.index)?", expr)
        if prop:
            value = env.get(prop[1])
            for index in re.findall(r"\[(\d+)\]", prop[2]):
                value = value.args[int(index)] if isinstance(value, EnumValue) and int(index) < len(value.args) else None
            return value.index if prop[3] and isinstance(value, EnumValue) else value if not prop[3] else None
        ctor = re.fullmatch(r"(\w+)\.(\w+)(?:\((.*)\))?", expr)
        if ctor and (ctor[1], ctor[2]) in self.enums:
            args = tuple(self.evaluate(a, env) for a in split_args(ctor[3] or ""))
            return EnumValue(ctor[1], self.enums[ctor[1], ctor[2]], args)
        return None

    def select(self, body, line, env):
        """Yield reachable lines, retaining line numbers and simple local bindings."""
        lines = body.splitlines()
        i = 0
        while i < len(lines):
            text = lines[i]
            condition = re.match(r"(\s*)if\((.*)\)\s*$", text)
            if condition and self.evaluate(condition[2], env) is not None:
                indent = condition[1]
                start, end = i + 2, i + 2
                while end < len(lines) and lines[end] != indent + "}":
                    end += 1
                stop = end + 1
                chosen = self.evaluate(condition[2], env)
                if stop < len(lines) and lines[stop] == indent + "else":
                    other_end = stop + 2
                    while other_end < len(lines) and lines[other_end] != indent + "}":
                        other_end += 1
                    if not chosen:
                        start, end = stop + 2, other_end
                    stop = other_end + 1
                    chosen = True
                if chosen:
                    yield from self.select("\n".join(lines[start:end]), line + start, env)
                    if any(s.startswith(indent + "   return ") for s in lines[start:end]):
                        return
                i = stop
                continue
            switch = re.match(r"(\s*)switch\((.*)\)\s*$", text)
            if switch:
                indent, selector = switch.groups()
                end = i + 2
                while end < len(lines) and lines[end] != indent + "}":
                    end += 1
                value = self.evaluate(selector, env)
                labels = [(j, m[1]) for j in range(i + 2, end)
                          if (m := re.fullmatch(indent + r"   (case -?\d+|default):", lines[j]))]
                chosen = next((n for n, (_, s) in enumerate(labels) if s == f"case {value}"), None)
                if value == -1:
                    # An optional role filter may be present or absent. Both
                    # branches are legitimate alternatives for this master value.
                    for n, (j, _) in enumerate(labels):
                        stop = labels[n + 1][0] if n + 1 < len(labels) else end
                        yield from self.select("\n".join(lines[j + 1:stop]), line + j + 1, dict(env))
                    i = end + 1
                    continue
                if chosen is None and value is not None:
                    chosen = next((n for n, (_, s) in enumerate(labels) if s == "default"), None)
                if chosen is not None:
                    # Adjacent empty case labels share the following body.
                    start = labels[chosen][0] + 1
                    n = chosen + 1
                    while n < len(labels) and not any(s.strip() for s in lines[start:labels[n][0]]):
                        start = labels[n][0] + 1
                        n += 1
                    stop = labels[n][0] if n < len(labels) else end
                    yield from self.select("\n".join(lines[start:stop]), line + start, env)
                i = end + 1
                continue
            assign = re.search(r"(?:var )?(\w+)(?::[\w*]+)? = (.*);$", text.strip())
            if assign:
                env[assign[1]] = self.evaluate(assign[2], env)
            yield line + i, text, dict(env)
            i += 1

    def constructors(self, body, line, env=None):
        env = dict(env or {})
        # The master arm is already selected. Branches on optional data inside
        # it may legitimately resolve to multiple runtime constructors.
        for offset, text in enumerate(body.splitlines()):
            number, local = line + offset, env
            assign = re.search(r"(?:var )?(\w+)(?::[\w*]+)? = (.*);$", text.strip())
            if assign:
                env[assign[1]] = self.evaluate(assign[2], env)
            for match in re.finditer(r"\b(\w+)\.(\w+)", text):
                if (match[1], match[2]) not in self.enums:
                    continue
                end = match.end()
                if text[end:end + 1] == "(":
                    end = matching(text, end) + 1
                value = self.evaluate(text[match.start():end], local)
                if value is not None:
                    yield value, number

    def keys_for(self, value):
        """Follow typed description switches and their stringfy helper calls."""
        return self.trace_for(value)["keys"]

    def trace_for(self, value):
        found = {}
        recipes = {}
        for fn in self.functions:
            if "/description/" not in fn["path"] or not fn["name"].startswith("stringfy"):
                continue
            if value.type in DESCRIBERS and fn["name"] not in DESCRIBERS[value.type]:
                continue
            params = re.findall(r"(\w+):([\w*]+)", fn["params"])
            bindings = [p for p, t in params if t == value.type]
            # Opening uses a member rather than a typed function parameter.
            if value.type == "OpeningAbilityKind" and fn["name"] == "stringfyOpening":
                bindings = ["opening"]
            if value.type == "InstantAbilityPrecontent" and fn["name"] == "stringfyInstantAbilityPrecontentPrefix":
                bindings = ["precontent"]
            for param in bindings:
                self._keys(fn, {param: value}, found, set(), (), recipes)
        return {"keys": found, "bindings": recipes}

    def _keys(self, fn, env, found, visiting, chain, recipes=None):
        identity = fn["class"], fn["name"], repr(env)
        if identity in visiting or len(visiting) > 8:
            return
        visiting = visiting | {identity}
        lines = list(self.select(fn["body"], fn["line"], dict(env)))
        active_key = None
        for index, (number, text, local) in enumerate(lines):
            evidence = f'{fn["path"]}:{number}'
            text = prune_ternaries(text, self, local)
            for key in re.findall(r'"(ability_description_[\w]+)"', text):
                found.setdefault(key, [*chain, evidence])
                auxiliary = (key.startswith("ability_description_target_")
                             or "separated_term_" in key
                             or key in {"ability_description_condition_content_initial_accumulation",
                                        "ability_description_condition_content_number"})
                if active_key is None or not auxiliary:
                    active_key = key
            for call in re.finditer(r"(?:(\w+)\.)?(stringfy\w+)\(", text):
                args = text[call.end():matching(text, call.end() - 1)]
                values = [self.evaluate(a, local) for a in split_args(args)]
                candidates = [f for f in self.functions if f["name"] == call[2]
                              and (not call[1] or f["class"] == call[1]) and "/description/" in f["path"]]
                for target in candidates:
                    names = re.findall(r"(\w+):[\w*]+", target["params"])
                    child_keys = {}
                    self._keys(target, dict(zip(names, values)), child_keys, visiting, (*chain, evidence), recipes)
                    for key, provenance in child_keys.items():
                        found.setdefault(key, provenance)
                    record_binding(recipes, active_key, lines, index, call[2], values,
                                   child_keys, chain, fn["path"])

    def master_branches(self, enum):
        """Resolve enum master indices, including the large if-chain resolvers."""
        for fn in self.functions:
            if "/description/" in fn["path"] or not (fn["name"].startswith("resolve") or fn["name"].startswith("create")):
                continue
            typed = re.search(r"(\w+)(?::|:\* = null as )" + re.escape(enum) + r"\b", fn["params"] + "\n" + fn["body"])
            if not typed:
                continue
            var = typed[1]
            body = fn["body"]
            # Resolve the huge content methods' independent if(index == N) arms.
            alias = re.search(r"(\w+):int = " + var + r"\.index;", body)
            arms = list(re.finditer(r"if\(" + (alias[1] if alias else "__absent") + r" == (\d+)\)\s*\{", body))
            if arms:
                for arm in arms:
                    start = arm.end()
                    end = matching(body, start - 1, "{", "}")
                    yield arm[1], fn["path"], body[start:end], fn["line"] + body.count("\n", 0, start)
            else:
                switch = re.search(r"(?m)^(\s*)switch\(" + var + r"\.index\)\s*\n", body)
                if not switch:
                    continue
                indent = switch[1].split("\n")[-1]
                end = body.find("\n" + indent + "}", switch.end())
                chunk = body[switch.end():end]
                cases = list(re.finditer(r"(?m)^" + indent + r"   case (\d+):", chunk))
                for i, case in enumerate(cases):
                    start = switch.end() + case.end()
                    stop = switch.end() + cases[i + 1].start() if i + 1 < len(cases) else end
                    yield case[1], fn["path"], body[start:stop], fn["line"] + body.count("\n", 0, start)
