"""Read-only prerequisites introduced by separately published table revisions."""
from __future__ import annotations

import wf_midautumn_kitlib as KL


def validate_base_strings(ctx, expected: dict[str, str]) -> None:
    """Fail before writing if either live or candidate differs from the base.

    An unchanged pre-existing key is a dependency, not permission to adopt it.
    PackTransaction still rejects any subsequent unclaimed payload change.
    """
    for scope, values in (("live", ctx.live_flat(KL.CAS)),
                          ("candidate", ctx.pkg_flat(KL.CAS))):
        for key, text in expected.items():
            raw = values.get(key)
            if raw is None or ctx.csv_split(raw) != [[text]]:
                raise KL.KitError(f"{scope} base string dependency differs or is missing: {key}")
