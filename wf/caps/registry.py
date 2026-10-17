"""Data-only capability registry with explicit provenance and unresolved hashes."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import jsonschema
import yaml

from wf.balance.recipe import RecipeLoader
from wf.paths import REPOSITORY


@lru_cache(maxsize=1)
def _validator():
    schema = json.loads((REPOSITORY / "schemas/capability.schema.json").read_text("utf-8"))
    return jsonschema.Draft202012Validator(schema)


def validate_capability(document: dict) -> dict:
    errors = list(_validator().iter_errors(document))
    if errors:
        raise ValueError("invalid capability: " + "; ".join(error.message for error in errors))
    provider = document["provided_by"]
    for method in provider["methods"]:
        if method["patch"] not in provider["patches"]:
            raise ValueError(f"{document['id']}: method refers to an undeclared patch")
        if method["sha256"] is None and method["status"] != "待补":
            raise ValueError(f"{document['id']}: null method hash must be marked 待补")
    if provider["patches"] and not provider["methods"]:
        raise ValueError(f"{document['id']}: patch evidence must include a method or explicit null")
    if document["layer"] == "B" and provider["patches"]:
        raise ValueError(f"{document['id']}: an official B-layer system cannot require an APK patch")
    return document


def load_registry(directory: str | Path | None = None) -> dict[str, dict]:
    root = Path(directory) if directory is not None else Path(__file__).parent
    documents = {}
    for path in sorted(root.glob("*.yml")):
        try:
            document = validate_capability(yaml.load(path.read_text("utf-8-sig"), Loader=RecipeLoader))
        except yaml.YAMLError as error:
            raise ValueError(f"invalid capability YAML {path.name}: {error}") from error
        capability_id = document["id"]
        if capability_id in documents:
            raise ValueError(f"duplicate capability ID: {capability_id}")
        if path.stem != capability_id:
            raise ValueError(f"capability filename does not match ID: {path.name}")
        documents[capability_id] = document
    if not documents:
        raise ValueError(f"empty capability registry: {root}")
    return documents


def required_patches(capability_id: str, registry: dict | None = None) -> list[int]:
    """Archive patch numbers needed together for this stable capability ID."""
    return list((registry if registry is not None else load_registry())[capability_id]["provided_by"]["patches"])
