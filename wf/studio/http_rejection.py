"""Bounded cleanup of rejected request bodies before closing HTTP/1.0 sockets."""
import time

MAX_DISCARD = 64 * 1024
DISCARD_SECONDS = 0.25


def discard_rejected_body(handler):
    """Never parse or dispatch rejected content; avoid TCP resets for small bodies.

    Missing/invalid framing, chunked data and large uploads are not drained.
    Both bytes and total wall time are bounded, even for a trickling sender.
    """
    if handler.headers.get("Transfer-Encoding") is not None:
        return
    try:
        remaining = int(handler.headers.get("Content-Length", "0"))
    except (ValueError, TypeError):
        return
    if not 0 < remaining <= MAX_DISCARD:
        return
    connection = handler.connection
    previous = connection.gettimeout()
    deadline = time.monotonic() + DISCARD_SECONDS
    try:
        while remaining:
            timeout = deadline - time.monotonic()
            if timeout <= 0:
                break
            connection.settimeout(timeout)
            chunk = handler.rfile.read1(remaining)
            if not chunk:
                break
            remaining -= len(chunk)
    except OSError:
        pass  # Rejection is still returned; never turn cleanup into authorization.
    finally:
        try:
            connection.settimeout(previous)
        except OSError:
            pass
