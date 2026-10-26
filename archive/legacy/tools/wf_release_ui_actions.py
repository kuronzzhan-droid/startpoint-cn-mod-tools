"""Strict preparation-only actions exposed by the standalone release UI."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Final, Mapping

from wf_preview_2d_core import PreviewBundle, load_preview
from wf_release_v1.legacy_character import adopt_legacy_character
from wf_release_v1.character_edit import (
    checkout_character_workspace,
    seal_edited_character_workspace,
)
from wf_release_v1.legacy_import import import_legacy_share
from wf_release_v1.legacy_share import inspect_legacy_share
from wf_release_v1.overlay_builder import build_character_overlay
from wf_release_v1.planning import capture_target_requirements
from wf_release_v1.platform import WindowsPlatformAdapter
from wf_release_v1.target import ManagedTarget
from wf_release_v1.target_capability import inspect_target_capability
from wf_release_v1.target_planning import plan_target_install


class UIActionError(ValueError):
    """The local browser sent an unsupported or ambiguous action request."""


@dataclass(frozen=True)
class ActionResult:
    wire: dict[str, object]
    preview: PreviewBundle | None = None


@dataclass(frozen=True)
class _Action:
    required: frozenset[str]
    optional: frozenset[str]
    handler: Callable[[Mapping[str, object]], ActionResult]


def _strict(
    value: object,
    required: frozenset[str],
    optional: frozenset[str] = frozenset(),
) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        raise UIActionError("操作参数必须是 JSON object")
    keys = frozenset(value)
    if not required.issubset(keys) or not keys.issubset(required | optional):
        raise UIActionError("操作参数字段与契约不一致")
    return value


def _text(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or any(ord(character) <= 0x1F or ord(character) == 0x7F for character in value)
    ):
        raise UIActionError(f"{label} 必须是非空文本")
    return value


def _path(value: object, label: str) -> Path:
    path = Path(_text(value, label))
    if not path.is_absolute():
        raise UIActionError(f"{label} 必须是显式绝对路径")
    return path


def _inspect(value: Mapping[str, object]) -> ActionResult:
    return ActionResult(inspect_legacy_share(_path(value["share"], "share")).to_wire())


def _import(value: Mapping[str, object]) -> ActionResult:
    mapping_value = value.get("mapping")
    mapping = None if mapping_value is None else _path(mapping_value, "mapping")
    receipt = import_legacy_share(
        _path(value["share"], "share"),
        _path(value["output"], "output"),
        mapping=mapping,
    )
    return ActionResult(receipt.to_wire())


def _adopt(value: Mapping[str, object]) -> ActionResult:
    receipt = adopt_legacy_character(
        _path(value["imported"], "imported"),
        _path(value["config"], "config"),
        _path(value["output"], "output"),
    )
    return ActionResult(receipt.to_wire())


def _checkout_character(value: Mapping[str, object]) -> ActionResult:
    receipt = checkout_character_workspace(
        _path(value["workspace"], "workspace"),
        _path(value["output"], "output"),
        _text(value["packageVersion"], "packageVersion"),
    )
    return ActionResult(receipt.to_wire())


def _seal_character(value: Mapping[str, object]) -> ActionResult:
    receipt = seal_edited_character_workspace(_path(value["workspace"], "workspace"))
    return ActionResult(receipt.to_wire())


def _preview(value: Mapping[str, object]) -> ActionResult:
    variant = _text(value.get("variant", "auto"), "variant")
    if variant not in ("auto", "normal", "special"):
        raise UIActionError("variant 只能是 auto、normal 或 special")
    bundle = load_preview(_path(value["source"], "source"), variant=variant)
    sequences = bundle.manifest["sequences"]
    return ActionResult(
        {
            "frameCount": sum(len(sequence["frames"]) for sequence in sequences),
            "mode": bundle.manifest["mode"],
            "previewAvailable": True,
            "readOnly": True,
            "sequenceCount": len(sequences),
            "sourceLogicalRoot": bundle.manifest.get("sourceLogicalRoot"),
            "writesLive": False,
        },
        bundle,
    )


def _overlay(value: Mapping[str, object]) -> ActionResult:
    receipt = build_character_overlay(
        _path(value["workspace"], "workspace"),
        _text(value["fromVersion"], "fromVersion"),
        _text(value["targetVersion"], "targetVersion"),
        _path(value["output"], "output"),
    )
    return ActionResult(receipt.to_wire())


def _capture(value: Mapping[str, object]) -> ActionResult:
    target = ManagedTarget.load(_path(value["target"], "target"))
    receipt = capture_target_requirements(
        target,
        _path(value["workspace"], "workspace"),
        _path(value["output"], "output"),
    )
    return ActionResult(receipt.to_wire())


def _plan(value: Mapping[str, object]) -> ActionResult:
    target = ManagedTarget.load(_path(value["target"], "target"))
    result = plan_target_install(
        _path(value["release"], "release"),
        target,
        lambda: _platform(target),
    )
    return ActionResult(result.to_wire())


def _inspect_target(value: Mapping[str, object]) -> ActionResult:
    target = ManagedTarget.load(_path(value["target"], "target"))
    return ActionResult(
        inspect_target_capability(target, lambda: _platform(target)).to_wire()
    )


def _platform(target: ManagedTarget) -> WindowsPlatformAdapter:
    launch = target.launch_spec()
    return WindowsPlatformAdapter(target.state_root, launch.executable)


ACTIONS: Final[dict[str, _Action]] = {
    "inspect-share": _Action(frozenset({"share"}), frozenset(), _inspect),
    "import-share": _Action(
        frozenset({"share", "output"}), frozenset({"mapping"}), _import
    ),
    "adopt-character": _Action(
        frozenset({"imported", "config", "output"}), frozenset(), _adopt
    ),
    "checkout-character": _Action(
        frozenset({"workspace", "output", "packageVersion"}),
        frozenset(),
        _checkout_character,
    ),
    "seal-character": _Action(
        frozenset({"workspace"}), frozenset(), _seal_character
    ),
    "preview": _Action(frozenset({"source"}), frozenset({"variant"}), _preview),
    "build-overlay": _Action(
        frozenset({"workspace", "fromVersion", "targetVersion", "output"}),
        frozenset(),
        _overlay,
    ),
    "capture-requirements": _Action(
        frozenset({"target", "workspace", "output"}), frozenset(), _capture
    ),
    "inspect-target": _Action(
        frozenset({"target"}), frozenset(), _inspect_target
    ),
    "plan-install": _Action(
        frozenset({"target", "release"}), frozenset(), _plan
    ),
}


def run_action(name: str, value: object) -> ActionResult:
    action = ACTIONS.get(name)
    if action is None:
        raise UIActionError("未知或被禁止的操作")
    request = _strict(value, action.required, action.optional)
    return action.handler(request)


__all__ = ["ACTIONS", "ActionResult", "UIActionError", "run_action"]
