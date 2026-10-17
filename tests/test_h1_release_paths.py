"""B lineage: configured release roots and Windows Modify-only access."""
from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

import wf_character_pack as pack
import wf_mod_tool as core
import wf_release as release


def test_release_resolves_store_server_and_cdn_from_shared_configuration(monkeypatch, tmp_path):
    server = tmp_path / "server"
    store = tmp_path / "data" / "upload"
    cdn = tmp_path / "cdn"
    for path in (server, store, cdn):
        path.mkdir(parents=True)
    # An explicit environment override can select a store while the legacy
    # profile has no store field. Release must use the shared resolver.
    profile = SimpleNamespace(id="cn", store=None)
    monkeypatch.setattr(core, "resolve_profile", lambda profile_id: profile)
    monkeypatch.setattr(core, "resolve_active_store", lambda **kwargs: store)
    monkeypatch.setattr(core, "resolve_server_dir", lambda profile_id: server)
    monkeypatch.setattr(core, "resolve_cdn_root", lambda profile_id: cdn)
    root, live, active = release._repo_paths("cn")
    assert root == server
    assert live.common == store
    assert live.server == server / "assets"
    assert active == cdn
    assert live.protected == (cdn,)


def test_release_refuses_unconfigured_server_instead_of_parent_fallback(monkeypatch, tmp_path):
    monkeypatch.setattr(core, "resolve_profile", lambda profile_id: SimpleNamespace(id="cn", store=tmp_path))

    def missing(profile_id):
        raise core.ServerDirNotConfiguredError("server is not configured")

    monkeypatch.setattr(core, "resolve_server_dir", missing)
    with pytest.raises(core.ServerDirNotConfiguredError, match="not configured"):
        release._repo_paths("cn")


@pytest.mark.skipif(os.name != "nt", reason="Windows owned-directory access contract")
def test_owned_child_directory_does_not_require_full_control():
    api = pack._WIN_OWNED_API
    contract = api.relative_open_contract("owned_directory_create")
    assert not contract.access & api.FILE_DELETE_CHILD
    for required in (api.FILE_LIST_DIRECTORY, api.FILE_ADD_FILE,
                     api.FILE_ADD_SUBDIRECTORY, api.DELETE, api.SYNCHRONIZE):
        assert contract.access & required


def test_rogue_write_requires_server_before_reading_or_writing_tables(monkeypatch):
    import wf_rogue_build as rb

    monkeypatch.setattr("sys.argv", ["wf_rogue_build.py", "--write"])

    def missing():
        raise core.ServerDirNotConfiguredError("server is not configured")

    def unexpected_table_access(*args, **kwargs):
        raise AssertionError("server must be resolved before table access")

    monkeypatch.setattr(core, "resolve_server_dir", missing)
    monkeypatch.setattr(rb.q, "load_table", unexpected_table_access)
    with pytest.raises(core.ServerDirNotConfiguredError, match="not configured"):
        rb.main()
