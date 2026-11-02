"""Keep optional warmups independent and report their failures visibly."""
import json
import logging


def warm_read(name, load):
    try:
        value = load()
        if hasattr(value, "status") and hasattr(value, "body"):
            body = json.loads(value.body)
            preview = body.get("preview", {})
            if value.status >= 400:
                raise ValueError(body.get("error") or f"HTTP {value.status}")
            if preview.get("ok") is False:
                raise ValueError("；".join(preview.get("blockers", [])) or "模式预览失败")
        return value
    except (ValueError, OSError, KeyError, TypeError, RuntimeError) as exc:
        logging.getLogger(__name__).warning("预热缓存失败 [%s]（请求时会重试）：%s: %s",
                                          name, type(exc).__name__, exc)
        return None
