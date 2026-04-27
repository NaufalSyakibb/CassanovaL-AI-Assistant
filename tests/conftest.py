"""
Pytest configuration: prevent server.py's sys.stdout replacement from
breaking pytest's capture mechanism (server.py line: sys.stdout = io.TextIOWrapper(...)).
"""
import sys
import io
import unittest.mock as mock


def pytest_configure(config):
    """
    Patch io.TextIOWrapper so that when server.py does:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    it becomes a no-op — returning the original sys.stdout unchanged.
    """
    _real_TextIOWrapper = io.TextIOWrapper

    def _safe_TextIOWrapper(buffer, *args, **kwargs):
        # If the buffer is sys.stdout.buffer (pytest's captured stdout),
        # return the current sys.stdout rather than wrapping it.
        if buffer is getattr(sys.stdout, "buffer", None):
            return sys.stdout
        return _real_TextIOWrapper(buffer, *args, **kwargs)

    config._stdout_patch = mock.patch("io.TextIOWrapper", side_effect=_safe_TextIOWrapper)
    config._stdout_patch.start()


def pytest_unconfigure(config):
    patch = getattr(config, "_stdout_patch", None)
    if patch is not None:
        patch.stop()
