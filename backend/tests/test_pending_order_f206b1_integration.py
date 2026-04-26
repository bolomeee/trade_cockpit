"""F206-b1 §D: integration tests for /api/cockpit/pending-orders (4 endpoints)."""
from __future__ import annotations

from datetime import date, timedelta


_BASE_URL = "/api/cockpit/pending-orders"

_VALID_PAYLOAD = {
    "ticker": "NVDA",
    "setupType": "BREAKOUT",
    "entryPrice": 180.0,
    "stopPrice": 173.0,
    "shares": 40,
}


def _post(client, **overrides) -> dict:
    payload = {**_VALID_PAYLOAD, **overrides}
    resp = client.post(_BASE_URL, json=payload)
    return resp


# ---------------------------------------------------------------------------
# D1: GET defaults to active — returns only ACTIVE orders
# ---------------------------------------------------------------------------

def test_get_default_returns_active_only(client):
    _post(client)  # creates ACTIVE order
    resp = client.get(_BASE_URL)
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body["data"], list)
    assert all(item["status"] == "ACTIVE" for item in body["data"])


# ---------------------------------------------------------------------------
# D2: GET ?status=all includes non-ACTIVE rows
# ---------------------------------------------------------------------------

def test_get_status_all_includes_triggered(client):
    create_resp = _post(client)
    order_id = create_resp.json()["data"]["id"]

    # Trigger the order
    client.patch(f"{_BASE_URL}/{order_id}", json={"status": "TRIGGERED"})

    # Create another ACTIVE order
    _post(client, ticker="AAPL")

    resp = client.get(f"{_BASE_URL}?status=all")
    assert resp.status_code == 200
    statuses = {item["status"] for item in resp.json()["data"]}
    assert "TRIGGERED" in statuses
    assert "ACTIVE" in statuses


# ---------------------------------------------------------------------------
# D3: GET ?status=EXPIRED (uppercase) — filtered correctly
# ---------------------------------------------------------------------------

def test_get_status_expired_uppercase(client):
    create_resp = _post(client)
    order_id = create_resp.json()["data"]["id"]
    client.patch(f"{_BASE_URL}/{order_id}", json={"status": "EXPIRED"})

    _post(client, ticker="MSFT")  # stays ACTIVE

    resp = client.get(f"{_BASE_URL}?status=EXPIRED")
    assert resp.status_code == 200
    items = resp.json()["data"]
    assert len(items) == 1
    assert items[0]["status"] == "EXPIRED"


# ---------------------------------------------------------------------------
# D4: POST 201 — response contains computed fields
# ---------------------------------------------------------------------------

def test_post_201_contains_computed_fields(client):
    resp = _post(client)
    assert resp.status_code == 201
    body = resp.json()
    item = body["data"]
    assert item["ticker"] == "NVDA"
    assert item["status"] == "ACTIVE"
    assert "id" in item
    assert "lastClose" in item       # may be None in test env
    assert "distanceToTriggerPct" in item
    assert "riskPct" in item
    # riskPct = (180-173)*40/100000*100 = 0.28 (default account_size=100000)
    assert item["riskPct"] == 0.28


# ---------------------------------------------------------------------------
# D5: POST 422 — entry <= stop
# ---------------------------------------------------------------------------

def test_post_422_entry_le_stop(client):
    resp = _post(client, entryPrice=170.0, stopPrice=173.0)
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# D6: POST 422 — expirationDate < today
# ---------------------------------------------------------------------------

def test_post_422_expiration_date_in_past(client):
    past = str(date.today() - timedelta(days=1))
    resp = _post(client, expirationDate=past)
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# D7: POST 422 — invalid setupType
# ---------------------------------------------------------------------------

def test_post_422_invalid_setup_type(client):
    resp = _post(client, setupType="INVALID_TYPE")
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# D8: PATCH 200 — move stopPrice; riskPct updates accordingly
# ---------------------------------------------------------------------------

def test_patch_stop_price_updates_risk_pct(client):
    create_resp = _post(client)
    order_id = create_resp.json()["data"]["id"]

    patch_resp = client.patch(f"{_BASE_URL}/{order_id}", json={"stopPrice": 175.0})
    assert patch_resp.status_code == 200
    item = patch_resp.json()["data"]
    assert item["stopPrice"] == 175.0
    # riskPct = (180-175)*40/100000*100 = 0.20
    assert item["riskPct"] == 0.2


# ---------------------------------------------------------------------------
# D9: PATCH 422 — state machine violation (TRIGGERED → ACTIVE)
# ---------------------------------------------------------------------------

def test_patch_422_state_machine_triggered_to_active(client):
    create_resp = _post(client)
    order_id = create_resp.json()["data"]["id"]

    client.patch(f"{_BASE_URL}/{order_id}", json={"status": "TRIGGERED"})

    patch_resp = client.patch(f"{_BASE_URL}/{order_id}", json={"status": "ACTIVE"})
    assert patch_resp.status_code == 422


# ---------------------------------------------------------------------------
# D10: PATCH 404 — non-existent id
# ---------------------------------------------------------------------------

def test_patch_404_nonexistent(client):
    resp = client.patch(f"{_BASE_URL}/99999", json={"stopPrice": 100.0})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# D11: DELETE 200 — deletes order; subsequent GET 404
# ---------------------------------------------------------------------------

def test_delete_200(client):
    create_resp = _post(client)
    order_id = create_resp.json()["data"]["id"]

    del_resp = client.delete(f"{_BASE_URL}/{order_id}")
    assert del_resp.status_code == 200
    body = del_resp.json()
    assert body["data"]["id"] == order_id
    assert body["data"]["deleted"] is True

    # Confirm it's gone via PATCH (should 404)
    get_resp = client.patch(f"{_BASE_URL}/{order_id}", json={"stopPrice": 100.0})
    assert get_resp.status_code == 404


# ---------------------------------------------------------------------------
# D12: DELETE 404 — non-existent id
# ---------------------------------------------------------------------------

def test_delete_404_nonexistent(client):
    resp = client.delete(f"{_BASE_URL}/99999")
    assert resp.status_code == 404
