import pytest


def test_server_exists():
    from firefly_mcp.server import mcp
    assert mcp.name == "firefly"
