"""Remove real-powerflip lifecycle operations from kind-629 ability actions."""
from __future__ import annotations

import copy

PF_COMMANDS = frozenset({"SetPowerFilpSuppress", "NotifyPowerflipEnd", "RemoveEvent"})


def _body(node):
    """Recognize enum bodies, expression wrappers and named JSON nodes.

    Lifecycle detection is deliberately independent of signature validation:
    malformed or alternative wrappers must not hide a dangerous constructor.
    Ordinary strings (including Trace payloads) are never constructors.
    """
    if isinstance(node, list) and node and isinstance(node[0], str):
        if node[0] in {"Command", "Event"} and len(node) >= 2:
            return _body(node[1])
        return node
    if isinstance(node, dict):
        for wrapper in ("Command", "Event"):
            if wrapper in node:
                return _body(node[wrapper])
        for key in ("command", "name", "type"):
            if isinstance(node.get(key), str) and node[key] in PF_COMMANDS | {"Wait"}:
                args = node.get("args", [])
                return [node[key], *(args if isinstance(args, list) else [args])]
    return None


def _only_notify(node):
    """A nonempty callback consisting solely of the PF-end notification.

    An empty Wait left by the historical 222 fix is harmless and is accepted.
    Do not remove timed effects or normal attack notifications.
    """
    body = _body(node)
    if body and body[0] == "NotifyPowerflipEnd":
        return True
    if isinstance(node, list) and len(node) == 2 and node[0] == "Block":
        return isinstance(node[1], list) and bool(node[1]) and all(_only_notify(child) for child in node[1])
    return False


def _forbidden(node):
    body = _body(node)
    if body and body[0] in PF_COMMANDS:
        return body[0]
    if body and body[0] == "Wait" and any(_only_notify(arg) for arg in body[1:]):
        return "Wait(NotifyPowerflipEnd only)"
    return None


def forbidden_629(tree):
    """Return precise node locations; strings and real PF trees are not edited."""
    findings = []

    def walk(node, location):
        label = _forbidden(node)
        if label:
            findings.append({"path": location, "command": label})
            return
        if isinstance(node, list):
            for index, child in enumerate(node):
                walk(child, f"{location}/{index}")
        elif isinstance(node, dict):
            for key, child in node.items():
                walk(child, f"{location}/{key}")

    walk(tree, "$")
    return findings


def sanitize_for_629(tree):
    """Return an independent sanitized tree, preserving unrelated payloads.

    Removed expressions become empty Blocks when used as a positional callback;
    statements in a Block are removed outright. The transform is idempotent.
    """
    def transform(node):
        if _forbidden(node):
            return ["Block", []]
        if isinstance(node, list):
            if len(node) == 2 and node[0] == "Block" and isinstance(node[1], list):
                return ["Block", [transform(child) for child in node[1] if not _forbidden(child)]]
            return [transform(child) for child in node]
        if isinstance(node, dict):
            return {key: transform(child) for key, child in node.items()}
        return copy.deepcopy(node)

    result = transform(tree)
    if forbidden_629(result):
        raise ValueError("kind 629 sanitizer left unsafe lifecycle operations")
    return result
