"""A caller may add codecs but cannot replace the built-in table inspectors."""

from pathlib import Path

import pytest

import wf_character_pack as pack


def transaction(tmp_path: Path, registry):
    return pack.PackTransaction(
        tmp_path / "package", {},
        live_roots=pack.LiveRoots(
            tmp_path / "common", tmp_path / "medium",
            tmp_path / "android", tmp_path / "server"),
        release_base_provider=None,
        codec_registry=registry,
    )


@pytest.mark.parametrize("codec_id", sorted(pack.DEFAULT_CODECS))
def test_builtin_table_codecs_cannot_be_replaced(tmp_path, codec_id):
    class PermissiveCodec:
        def inspect(self, raw, claim, semantic_claims):
            return pack.TableImage(())

    with pytest.raises(pack.PackPreflightError, match="cannot override built-in"):
        transaction(tmp_path, {codec_id: PermissiveCodec()})


def test_custom_table_codecs_remain_supported(tmp_path):
    codec = object()
    tx = transaction(tmp_path, {"author_custom": codec})
    assert tx.codecs["author_custom"] is codec
    assert all(tx.codecs[key] is value for key, value in pack.DEFAULT_CODECS.items())
