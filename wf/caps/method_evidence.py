"""Accept intentional method replacements only for their recorded client SWF."""


def accepted_hashes(method, swf_sha256=None):
    value = selected_method_hash(method, swf_sha256)
    return frozenset({value}) if value else frozenset()


def selected_method_hash(method, swf_sha256=None):
    variants = [v["sha256"] for v in method.get("accepted_variants", [])
                if swf_sha256 and v["swf_sha256"] == swf_sha256]
    if len(set(variants)) > 1:
        raise ValueError("conflicting method variants for the same SWF")
    return variants[0] if variants else method.get("sha256")
