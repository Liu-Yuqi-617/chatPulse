from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health() -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "ChatPulse API"


def test_simulation_populates_dashboard() -> None:
    response = client.post("/api/dev/simulate", json={"scenario": "mixed"})

    assert response.status_code == 200
    state = response.json()
    assert len(state["messages"]) == 5
    assert len(state["topics"]) == 2
    assert len(state["questions"]) == 2


def test_question_can_be_pinned_and_spotlight_cleared() -> None:
    client.post("/api/dev/simulate", json={"scenario": "questions"})

    pinned = client.post("/api/questions/question-schedule/pinned")
    assert pinned.status_code == 200
    assert pinned.json()["spotlight"]["question_id"] == "question-schedule"

    cleared = client.delete("/api/spotlight")
    assert cleared.status_code == 200
    assert cleared.json()["spotlight"]["question_id"] is None

