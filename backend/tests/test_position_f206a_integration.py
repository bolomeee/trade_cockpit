"""F206-a §D: integration tests for /api/cockpit/positions (4 endpoints)."""
from __future__ import annotations

from datetime import date

import pytest


# ---------------------------------------------------------------------------
# D1: GET empty list returns 200 with empty items
# ---------------------------------------------------------------------------

def test_get_positions_empty(client):
    resp = client.get("/api/cockpit/positions")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["items"] == []


# ---------------------------------------------------------------------------
# D2: POST valid position → 201 + position in response
# ---------------------------------------------------------------------------

def test_post_position_201(client):
    payload = {
        "ticker": "NVDA",
        "entryPrice": 850.0,
        "entryDate": "2026-04-01",
        "shares": 33,
        "stopPrice": 820.0,
        "setupType": "BREAKOUT",
    }
    resp = client.post("/api/cockpit/positions", json=payload)
    assert resp.status_code == 201
    body = resp.json()
    item = body["data"]
    assert item["ticker"] == "NVDA"
    assert item["entryPrice"] == 850.0
    assert item["status"] == "OPEN"
    assert "id" in item


# ---------------------------------------------------------------------------
# D3: POST → GET list shows the new position
# ---------------------------------------------------------------------------

def test_post_then_get_list(client):
    payload = {
        "ticker": "MSFT",
        "entryPrice": 400.0,
        "entryDate": "2026-04-01",
        "shares": 10,
        "stopPrice": 380.0,
    }
    client.post("/api/cockpit/positions", json=payload)

    resp = client.get("/api/cockpit/positions?status=open")
    assert resp.status_code == 200
    tickers = [i["ticker"] for i in resp.json()["data"]["items"]]
    assert "MSFT" in tickers


# ---------------------------------------------------------------------------
# D4: PATCH stop_price → updated value in response
# ---------------------------------------------------------------------------

def test_patch_stop_price(client):
    create_resp = client.post("/api/cockpit/positions", json={
        "ticker": "AAPL",
        "entryPrice": 150.0,
        "entryDate": "2026-04-01",
        "shares": 100,
        "stopPrice": 140.0,
    })
    pos_id = create_resp.json()["data"]["id"]

    patch_resp = client.patch(f"/api/cockpit/positions/{pos_id}", json={"stopPrice": 145.0})
    assert patch_resp.status_code == 200
    assert patch_resp.json()["data"]["stopPrice"] == 145.0


# ---------------------------------------------------------------------------
# D5: DELETE → 200; second GET → 404
# ---------------------------------------------------------------------------

def test_delete_position(client):
    create_resp = client.post("/api/cockpit/positions", json={
        "ticker": "GOOG",
        "entryPrice": 175.0,
        "entryDate": "2026-04-01",
        "shares": 50,
        "stopPrice": 165.0,
    })
    pos_id = create_resp.json()["data"]["id"]

    del_resp = client.delete(f"/api/cockpit/positions/{pos_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["data"]["deleted"] is True

    patch_resp = client.patch(f"/api/cockpit/positions/{pos_id}", json={"stopPrice": 166.0})
    assert patch_resp.status_code == 404


# ---------------------------------------------------------------------------
# D6: PATCH/DELETE on non-existent id → 404
# ---------------------------------------------------------------------------

def test_patch_nonexistent_404(client):
    resp = client.patch("/api/cockpit/positions/9999", json={"stopPrice": 100.0})
    assert resp.status_code == 404


def test_delete_nonexistent_404(client):
    resp = client.delete("/api/cockpit/positions/9999")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# D7: POST entry <= stop → 422
# ---------------------------------------------------------------------------

def test_post_entry_le_stop_422(client):
    resp = client.post("/api/cockpit/positions", json={
        "ticker": "TSLA",
        "entryPrice": 200.0,
        "entryDate": "2026-04-01",
        "shares": 10,
        "stopPrice": 220.0,  # stop > entry
    })
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# D8: PATCH status=CLOSED without closedAt/closePrice → 422
# ---------------------------------------------------------------------------

def test_patch_closed_without_metadata_422(client):
    create_resp = client.post("/api/cockpit/positions", json={
        "ticker": "AMD",
        "entryPrice": 100.0,
        "entryDate": "2026-04-01",
        "shares": 20,
        "stopPrice": 90.0,
    })
    pos_id = create_resp.json()["data"]["id"]

    resp = client.patch(f"/api/cockpit/positions/{pos_id}", json={"status": "CLOSED"})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# D9: POST recommendedShares present in response
# ---------------------------------------------------------------------------

def test_post_response_has_recommended_shares(client, fake_fmp):
    """POST response must include recommendedShares field (may be null if settings unavailable)."""
    resp = client.post("/api/cockpit/positions", json={
        "ticker": "PLTR",
        "entryPrice": 80.0,
        "entryDate": "2026-04-01",
        "shares": 50,
        "stopPrice": 70.0,
    })
    assert resp.status_code == 201
    body = resp.json()["data"]
    # Field must exist (value may be int or null depending on user_settings row)
    assert "recommendedShares" in body
