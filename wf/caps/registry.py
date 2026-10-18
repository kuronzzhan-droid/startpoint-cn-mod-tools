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
    observed = set()
    for method in provider["methods"]:
        key = method["patch"], method["abc"], method["label"]
        if key in observed:
            raise ValueError(f"{document['id']}: duplicate method evidence")
        observed.add(key)
        standalone = not provider["patches"] and method["patch"] is None
        if not standalone and method["patch"] not in provider["patches"]:
            raise ValueError(f"{document['id']}: method refers to an undeclared patch")
        if standalone and (not provider.get("swf_sha256") or not method["sha256"]
                           or not method["abc"] or not method["label"]):
            raise ValueError(f"{document['id']}: standalone methods require a pinned SWF and complete method evidence")
        if method["sha256"] is None and method["status"] != "待补":
            raise ValueError(f"{document['id']}: null method hash must be marked 待补")
        variants = method.get("accepted_variants", [])
        if len({v["swf_sha256"] for v in variants}) != len(variants):
            raise ValueError(f"{document['id']}: duplicate method variant SWF")
        if variants and method["sha256"] is None:
            raise ValueError(f"{document['id']}: pending method cannot have accepted variants")
    missing = set(provider["patches"]) - {method["patch"] for method in provider["methods"]}
    if missing:
        raise ValueError(f"{document['id']}: patches lack method evidence or explicit null: {sorted(missing)}")
    if provider["patches"] and not provider["methods"]:
        raise ValueError(f"{document['id']}: patch evidence must include a method or explicit null")
    if document["layer"] == "B" and (provider["patches"] or provider["methods"]):
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
