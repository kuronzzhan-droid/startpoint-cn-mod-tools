"""Remove real-powerflip lifecycle operations from kind-629 ability actions."""
from __future__ import annotations

import copy

PF_COMMANDS = frozenset({"SetPowerFilpSuppress", "NotifyPowerflipEnd", "RemoveEvent"})


def _body(node, tag):
    if (isinstance(node, list) and len(node) == 2 and node[0] == tag
            and isinstance(node[1], list) and node[1] and isinstance(node[1][0], str)):
        return node[1]
    return None


def _only_notify(node):
    """A nonempty callback consisting solely of the PF-end notification.

    An empty Wait left by the historical 222 fix is harmless and is accepted.
    Do not remove timed effects or normal attack notifications.
    """
    body = _body(node, "Command")
    if body:
        return body[0] == "NotifyPowerflipEnd"
    if isinstance(node, list) and len(node) == 2 and node[0] == "Block":
        return isinstance(node[1], list) and bool(node[1]) and all(_only_notify(child) for child in node[1])
    return False


def _forbidden(node):
    body = _body(node, "Command")
    if body and body[0] in PF_COMMANDS:
        return body[0]
    event = _body(node, "Event")
    if event and event[0] == "Wait" and len(event) == 4 and _only_notify(event[3]):
        return "Wait(NotifyPowerflipEnd only)"
    return None


def forbidden_629(tree):
    """Return precise node locations; strings and real PF trees are not edited."""
    findings = []

    def walk(node, location):
        label = _forbidden(node)
        if label:
            findings.append({"path": location, "command": label})
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
