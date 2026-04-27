import sys
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    # server.py replaces sys.stdout at import time; restore after import
    # so pytest's capture mechanism is not broken.
    _orig_stdout = sys.stdout
    from server import app
    sys.stdout = _orig_stdout
    return TestClient(app)


def test_stock_analyze_missing_ticker(client):
    resp = client.get("/api/stock/analyze")
    assert resp.status_code == 422  # FastAPI: missing required query param


def test_stock_analyze_invalid_ticker_too_long(client):
    resp = client.get("/api/stock/analyze?ticker=" + "X" * 21)
    assert resp.status_code == 400
