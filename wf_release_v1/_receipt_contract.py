"""Pure validation and wire helpers for operation receipts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Final

from .errors import ReleaseError


_RELEASE_ID: Final = re.compile(r"sha256:[0-9a-f]{64}")
_OPERATION_ID: Final = re.compile(r"[0-9]{8}T[0-9]{6}\.[0-9]{6}Z-[0-9a-f]{32}")
_ERROR_CODE: Final = re.compile(r"WFREL_[A-Z0-9_]+")
_PHASE_ORDER: Final = (
    "CREATED", "VERIFIED", "BASE_STARTED", "PROBED", "STOPPED", "MATERIALIZED", "SWITCHED",
    "STARTED", "HEALTH_READY", "CAPABILITIES_ACCEPTED", "COMMITTED",
)
_PHASES: Final = frozenset(_PHASE_ORDER)
_OUTCOMES: Final = frozenset({
    "in_progress", "succeeded", "failed", "recovered", "recovery_failed",
})
_RECOVERY_OUTCOMES: Final = frozenset({None, "recovered", "failed"})
_TARGET_PROTOCOLS: Final = frozenset({"capabilities-v1", "legacy"})
_RECEIPT_V1_KEYS: Final = frozenset({
    "schemaVersion", "operationId", "releaseId", "phase", "outcome", "startedAt",
    "updatedAt", "beforeReleaseIds", "candidateReleaseIds", "errorCode",
    "recoveryOutcome",
})
_RECEIPT_V2_KEYS: Final = _RECEIPT_V1_KEYS | {"targetProtocol"}


def invalid_receipt(message: str) -> ReleaseError:
    return ReleaseError("WFREL_RECEIPT_INVALID", message)


def invalid_state(message: str) -> ReleaseError:
    return ReleaseError("WFREL_STATE_INVALID", message)


def validate_release_id(value: object, *, state: bool = False) -> str:
    if not isinstance(value, str) or _RELEASE_ID.fullmatch(value) is None:
        error = invalid_state if state else invalid_receipt
        raise error("release identity is invalid")
    return value


def validate_release_ids(value: object, *, state: bool = False) -> tuple[str, ...]:
    error = invalid_state if state else invalid_receipt
    if not isinstance(value, tuple):
        raise error("release identities must be a tuple")
    parsed = tuple(validate_release_id(item, state=state) for item in value)
    if tuple(sorted(set(parsed))) != parsed:
        raise error("release identities must be unique and canonically ordered")
    return parsed


def _wire_time(value: datetime) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise invalid_receipt("receipt time must be timezone-aware")
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _parse_wire_time(value: object) -> datetime:
    if not isinstance(value, str):
        raise invalid_receipt("receipt time is invalid")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ")
    except ValueError:
        raise invalid_receipt("receipt time is invalid") from None
    if _wire_time(parsed.replace(tzinfo=timezone.utc)) != value:
        raise invalid_receipt("receipt time is not canonical")
    return parsed.replace(tzinfo=timezone.utc)


def new_operation_id(now: datetime, nonce: bytes) -> str:
    """Derive one deterministic, path-safe operation identity."""
    if not isinstance(nonce, bytes) or len(nonce) != 16:
        raise invalid_receipt("operation nonce must contain exactly 16 bytes")
    timestamp = _wire_time(now).replace("-", "").replace(":", "")
    return f"{timestamp}-{nonce.hex()}"


@dataclass(frozen=True)
class OperationReceipt:
    schema_version: int
    operation_id: str
    release_id: str
    phase: str
    outcome: str
    started_at: datetime
    updated_at: datetime
    before_release_ids: tuple[str, ...]
    candidate_release_ids: tuple[str, ...]
    error_code: str | None
    recovery_outcome: str | None
    target_protocol: str = "capabilities-v1"

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version not in (1, 2):
            raise invalid_receipt("receipt schema version is not supported")
        if (
            not isinstance(self.target_protocol, str)
            or self.target_protocol not in _TARGET_PROTOCOLS
            or self.schema_version == 1
            and self.target_protocol != "capabilities-v1"
        ):
            raise invalid_receipt("receipt target protocol is invalid")
        if not isinstance(self.operation_id, str) or _OPERATION_ID.fullmatch(self.operation_id) is None:
            raise invalid_receipt("operation identity is invalid")
        validate_release_id(self.release_id)
        if not isinstance(self.phase, str) or self.phase not in _PHASES:
            raise invalid_receipt("receipt phase is invalid")
        if not isinstance(self.outcome, str) or self.outcome not in _OUTCOMES:
            raise invalid_receipt("receipt outcome is invalid")
        started = _wire_time(self.started_at)
        updated = _wire_time(self.updated_at)
        if updated < started:
            raise invalid_receipt("receipt update precedes its start")
        validate_release_ids(self.before_release_ids)
        validate_release_ids(self.candidate_release_ids)
        if self.error_code is not None and (
            not isinstance(self.error_code, str)
            or _ERROR_CODE.fullmatch(self.error_code) is None
        ):
            raise invalid_receipt("receipt error code is invalid")
        if self.recovery_outcome is not None and not (
            isinstance(self.recovery_outcome, str)
            and self.recovery_outcome in _RECOVERY_OUTCOMES
        ):
            raise invalid_receipt("receipt recovery outcome is invalid")

    def to_wire(self) -> dict[str, object]:
        value: dict[str, object] = {
            "schemaVersion": self.schema_version, "operationId": self.operation_id,
            "releaseId": self.release_id, "phase": self.phase, "outcome": self.outcome,
            "startedAt": _wire_time(self.started_at), "updatedAt": _wire_time(self.updated_at),
            "beforeReleaseIds": list(self.before_release_ids),
            "candidateReleaseIds": list(self.candidate_release_ids), "errorCode": self.error_code,
            "recoveryOutcome": self.recovery_outcome,
        }
        if self.schema_version == 2:
            value["targetProtocol"] = self.target_protocol
        return value


def receipt_from_wire(value: object) -> OperationReceipt:
    if not isinstance(value, dict) or set(value) not in (
        _RECEIPT_V1_KEYS, _RECEIPT_V2_KEYS,
    ):
        raise invalid_receipt("receipt keys do not match the contract")
    version = value.get("schemaVersion")
    if (
        set(value) == _RECEIPT_V1_KEYS and version != 1
        or set(value) == _RECEIPT_V2_KEYS and version != 2
    ):
        raise invalid_receipt("receipt schema does not match its keys")
    before = value["beforeReleaseIds"]
    candidates = value["candidateReleaseIds"]
    if not isinstance(before, list) or not isinstance(candidates, list):
        raise invalid_receipt("receipt release identities are invalid")
    return OperationReceipt(
        schema_version=value["schemaVersion"],  # type: ignore[arg-type]
        operation_id=value["operationId"],  # type: ignore[arg-type]
        release_id=value["releaseId"],  # type: ignore[arg-type]
        phase=value["phase"],  # type: ignore[arg-type]
        outcome=value["outcome"],  # type: ignore[arg-type]
        started_at=_parse_wire_time(value["startedAt"]),
        updated_at=_parse_wire_time(value["updatedAt"]),
        before_release_ids=tuple(before),  # type: ignore[arg-type]
        candidate_release_ids=tuple(candidates),  # type: ignore[arg-type]
        error_code=value["errorCode"],  # type: ignore[arg-type]
        recovery_outcome=value["recoveryOutcome"],  # type: ignore[arg-type]
        target_protocol=value.get("targetProtocol", "capabilities-v1"),  # type: ignore[arg-type]
    )


def validate_receipt_update(old: OperationReceipt, new: OperationReceipt) -> None:
    if (
        old.operation_id != new.operation_id
        or old.release_id != new.release_id
        or old.started_at != new.started_at
        or old.before_release_ids != new.before_release_ids
        or old.candidate_release_ids != new.candidate_release_ids
        or old.target_protocol != new.target_protocol
        or new.updated_at < old.updated_at
        or _PHASE_ORDER.index(new.phase) < _PHASE_ORDER.index(old.phase)
        or (old.outcome != "in_progress" and new.outcome == "in_progress")
        or (old.outcome in {"succeeded", "recovered", "recovery_failed"} and new.outcome != old.outcome)
        or (old.outcome == "failed" and new.outcome not in {"failed", "recovered", "recovery_failed"})
    ):
        raise ReleaseError("WFREL_RECEIPT_CONFLICT", "operation identity was reused")
