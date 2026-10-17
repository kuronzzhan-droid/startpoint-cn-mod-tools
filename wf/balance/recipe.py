"""Strict, data-only YAML recipes; duplicate mapping keys are rejected."""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import yaml

from wf.paths import REPOSITORY


class RecipeLoader(yaml.SafeLoader):
    pass


def _mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise ValueError(f"duplicate YAML key: {key}")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


RecipeLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def validate_recipe(value: dict) -> dict:
    schema = json.loads((REPOSITORY / "schemas/balance-recipe.schema.json").read_text("utf-8"))
    errors = sorted(jsonschema.Draft202012Validator(schema).iter_errors(value),
                    key=lambda error: "/".join(map(str, error.absolute_path)))
    if errors:
        details = [f"{'/'.join(map(str, error.absolute_path))}: {error.message}" for error in errors]
        raise ValueError("invalid balance recipe:\n" + "\n".join(details))
    if tuple(map(int, value["to_version"].split("."))) <= tuple(map(int, value["from_version"].split("."))):
        raise ValueError("balance version must advance; rollback requires a new forward edge")
    return value


def load_recipe(path: str | Path) -> dict:
    with Path(path).open(encoding="utf-8-sig") as source:
        return validate_recipe(yaml.load(source, Loader=RecipeLoader))
