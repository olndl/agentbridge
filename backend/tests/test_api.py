import os
import tempfile

db_file = tempfile.NamedTemporaryFile(delete=False)
os.environ["AGENTBRIDGE_DB"] = db_file.name

from fastapi.testclient import TestClient  # noqa: E402

from app.main import create_app  # noqa: E402

client = TestClient(create_app())


def test_health() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_webhook_processes_github_issue() -> None:
    payload = {
        "issue": {
            "id": 123,
            "title": "Connect Salesforce sandbox",
            "html_url": "https://github.com/acme/platform/issues/1",
            "labels": {"0": {"name": "high"}},
        },
        "repository": {"full_name": "acme/platform"},
    }

    response = client.post(
        "/webhooks/github",
        headers={"X-Idempotency-Key": "issue-123-opened"},
        json=payload,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "delivered"

    run = client.get(f"/runs/{body['run_id']}").json()
    assert run["mapped_payload"]["title"] == "Connect Salesforce sandbox"
    assert run["mapped_payload"]["customer"] == "acme/platform"


def test_idempotency_reuses_existing_run() -> None:
    payload = {
        "event": {
            "ts": "1729.01",
            "text": "Customer cannot sync invoices",
            "priority": "urgent",
            "permalink": "https://slack.example/messages/1729",
        },
        "team": {"domain": "acme"},
    }

    first = client.post(
        "/webhooks/slack",
        headers={"X-Idempotency-Key": "slack-1729"},
        json=payload,
    ).json()
    second = client.post(
        "/webhooks/slack",
        headers={"X-Idempotency-Key": "slack-1729"},
        json=payload,
    ).json()

    assert first["run_id"] == second["run_id"]
    assert second["message"].startswith("Duplicate webhook")


def test_mapping_suggestion() -> None:
    response = client.post(
        "/mapping/suggest",
        json={
            "sample_payload": {
                "issue": {"title": "Broken import", "html_url": "https://example.com"}
            },
            "target_schema": {"title": "string", "url": "string"},
        },
    )

    assert response.status_code == 200
    assert response.json()["mapping"]["title"] == "issue.title"
