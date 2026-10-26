"""Verify the complete active-chain and store fallback lock for balance replay."""
import hashlib


def verify_balance_view(view, lock):
    """Fail before packaging if an active ZIP or locked base member has drifted.

    An empty store_members mapping is intentional: the frozen recipe currently
    reads only overlay members. Any new store fallback is rejected by the view.
    """
    if lock.get("format") != 1 or view.tip != lock["tip"]:
        raise ValueError("balance base lock format or tip does not match the view")
    active = [archive for archive in view.zips if archive.parent.resolve() == view.active.resolve()]
    expected = lock["active_zips"]
    # Re-enumerate the directory too, so additions/removals during a build fail.
    from .base149 import HistoricalView
    current = HistoricalView(store=view.store, active=view.active, tip=view.tip)
    names = [archive.name for archive in active]
    if names != [item["name"] for item in expected] or names != [p.name for p in current.zips]:
        raise ValueError("balance active ZIP list drifted")
    for archive, item in zip(active, expected):
        if hashlib.sha256(archive.read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError(f"balance active ZIP digest drift: {archive.name}")
    if view.store_member_sha256 != lock["store_members"]:
        raise ValueError("balance store131 member lock does not match the view")
    for name in lock["store_members"]:
        view.read_store_member(name)
    return {"tip": view.tip, "active_zip_count": len(active),
            "store_member_count": len(lock["store_members"]),
            "read_members": dict(sorted(view.read_members.items()))}
