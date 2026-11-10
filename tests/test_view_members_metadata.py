"""Patch archives may carry root bookkeeping files next to CDN members."""
import io
import zipfile

import pytest

from wf.view.members import archive_members, canonical_member

MEMBER = "production/upload/15/" + "0" * 38


def _zip(names):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name in names:
            archive.writestr(name, b"{}")
    return zipfile.ZipFile(io.BytesIO(buffer.getvalue()))


@pytest.mark.parametrize("name", [".empty", ".integrity.json"])
def test_root_metadata_members_are_skipped(name):
    assert canonical_member(name) is None
    assert archive_members(_zip([name, MEMBER])) == {MEMBER: MEMBER}


@pytest.mark.parametrize("name", ["integrity.json", "sub/.integrity.json", "production/upload/.integrity.json"])
def test_other_unknown_members_still_fail_closed(name):
    with pytest.raises(ValueError, match="invalid CDN member"):
        canonical_member(name)
