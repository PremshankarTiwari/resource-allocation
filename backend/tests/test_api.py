from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    assert client.get("/api/health").json() == {"status": "ok"}


def test_algorithms_listed():
    keys = {a["key"] for a in client.get("/api/algorithms").json()}
    assert keys == {"greedy", "hungarian", "regret"}


def test_scenario_is_deterministic_for_a_seed():
    a = client.get("/api/scenario", params={"seed": 5, "technicians": 6, "jobs": 20}).json()
    b = client.get("/api/scenario", params={"seed": 5, "technicians": 6, "jobs": 20}).json()
    assert a == b
    assert len(a["technicians"]) == 6 and len(a["jobs"]) == 20


def test_solve_returns_every_requested_algorithm():
    scenario = client.get("/api/scenario", params={"seed": 1, "technicians": 6, "jobs": 20}).json()
    res = client.post("/api/solve", json={"scenario": scenario, "algorithms": ["greedy", "hungarian", "regret"]})
    assert res.status_code == 200
    solutions = res.json()["solutions"]
    assert set(solutions) == {"greedy", "hungarian", "regret"}
    for sol in solutions.values():
        assert sol["metrics"]["jobs_total"] == 20


def test_unknown_algorithm_is_rejected():
    scenario = client.get("/api/scenario", params={"seed": 1, "technicians": 2, "jobs": 3}).json()
    res = client.post("/api/solve", json={"scenario": scenario, "algorithms": ["magic"]})
    assert res.status_code == 422
    assert "magic" in res.json()["detail"]


def test_duplicate_ids_are_rejected():
    scenario = client.get("/api/scenario", params={"seed": 1, "technicians": 2, "jobs": 3}).json()
    scenario["jobs"][1]["id"] = scenario["jobs"][0]["id"]
    res = client.post("/api/solve", json={"scenario": scenario})
    assert res.status_code == 422


def test_invalid_time_window_is_rejected():
    scenario = client.get("/api/scenario", params={"seed": 1, "technicians": 2, "jobs": 3}).json()
    scenario["jobs"][0]["window_start"], scenario["jobs"][0]["window_end"] = 900, 600
    res = client.post("/api/solve", json={"scenario": scenario})
    assert res.status_code == 422
