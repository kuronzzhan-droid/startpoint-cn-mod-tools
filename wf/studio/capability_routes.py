"""Read-only client profile requirements for the future ability editor UI."""
import re

from wf.caps.profiles import profile_options
from wf.caps.query import query_requirements


def routes():
    return [("GET", re.compile(r"^/api/capabilities/requirements$"), requirements),
            ("GET", re.compile(r"^/api/client-profiles$"), profiles)]


def profiles(query):
    from .server import json_response
    return json_response(profile_options())


def requirements(query):
    from .server import error, json_response
    try:
        return json_response(query_requirements(
            kinds=query.get("kind", []), unique_strings=query.get("unique", []),
            dsl_markers=query.get("dsl", []), selectors=query.get("selector", []),
            custom_keys=query.get("customKey", []), unique_id=(query.get("uniqueId") or [None])[0],
            client_profile=(query.get("clientProfile") or [None])[0]))
    except (ValueError, OSError) as exc:
        return error(400, str(exc))
