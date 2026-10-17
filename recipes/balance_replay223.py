"""Fixed 223 byte-compatibility verification; never emits deliverable artifacts."""
from __future__ import annotations

import hashlib
import json

from wf.balance.engine import _apply_operations
from wf.balance.inputs import open_inputs
from wf.balance.recipe import load_recipe
from wf.paths import REPOSITORY

PINNED = {
    "recipes/balance/balance1017-223.yml": "c2b1e11d694ed0a676d6f5982aa4872541b2b6cbbbc694797718c0166d707057",
    "recipes/balance1017/base-lock.json": "39468a5114d45f3a671911ec78037b70836eb7f51a0d6949dbf206decf39ca81",
    "recipes/balance1017/input-zips.json": "1a3052df4110d6d5d1914400e0f4d1482a8e0f0562655070915713a36c16dc2c",
}
GOLDEN = {
    "production/upload/07/0c6e214359ccf27b1cb8078d3fc51aecfe0149": "2712bf39e5dcd3bccdc65cd470761aff5c82ff0e40b51139354fbb90c924aa7d",
    "production/upload/1e/664c1cc8d80f4f9a69aae2c49ae8c01d1c4001": "6d9448945f57093d1a52a0f8cfe459e70e93b00829d7f12a207c29c81a0bfb5f",
    "production/upload/ff/84353774cb95e8d7dc90c679f96a5bca7f42e5": "6967615bb73fa7bdbc8714810a04e26a3f20808c860b626d60164e35a8f97553",
}


def replay():
    for name, expected in PINNED.items():
        data = (REPOSITORY / name).read_bytes().replace(b"\r\n", b"\n")
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError(f"fixed 223 replay input changed: {name}")
    path = REPOSITORY / "recipes/balance/balance1017-223.yml"
    recipe = load_recipe(path)
    view, verify = open_inputs(recipe, path)
    result = _apply_operations(recipe, view)
    verification = verify()
    hashes = {name: hashlib.sha256(data).hexdigest() for name, data in result.files.items()}
    if hashes != GOLDEN:
        raise ValueError("fixed 223 replay member bytes differ from the original delivery")
    return {"schema": "wf-historical-223-verification/1", "status": "满足",
            "scope": "历史字节兼容性验证；不生成变更集或可交付包，不代表当前门禁通过",
            "member_count": len(hashes), "member_sha256": hashes,
            "view_verification": verification}


if __name__ == "__main__":
    print(json.dumps(replay(), ensure_ascii=False, indent=2))
