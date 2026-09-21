from fastapi.testclient import TestClient

import UI.dashboard as dashboard


def test_dashboard_state_update_rejects_missing_token():
    client = TestClient(dashboard.app)
    response = client.put("/api/state", json={"regime": "TREND"})
    assert response.status_code == 403


def test_dashboard_state_update_accepts_valid_token():
    client = TestClient(dashboard.app)
    response = client.put(
        "/api/state",
        json={"regime": "TREND"},
        headers={"X-GTS-Token": dashboard.TOKEN},
    )
    assert response.status_code == 200
    state = client.get("/api/state").json()
    assert state["regime"] == "TREND"
