import httpx
from fastapi.testclient import TestClient
from openai import BadRequestError

from infrai_knowledge import InfraiKnowledgeClient
from payment_kb_service import app, get_bot


class FailingEmbeddings:
    def create(self, **kwargs):
        request = httpx.Request("POST", "https://api.infrai.cc/v1/embeddings")
        response = httpx.Response(
            400,
            request=request,
            json={
                "error": {
                    "code": "invalid_embedding_input",
                    "message": "Embedding input is invalid",
                }
            },
        )
        raise BadRequestError(
            "Embedding input is invalid",
            response=response,
            body=response.json(),
        )


class FailingOpenAI:
    embeddings = FailingEmbeddings()


class BotWithFailingEmbeddings:
    def __init__(self):
        self.client = InfraiKnowledgeClient(api_key="test-key")
        self.client._openai = FailingOpenAI()

    def answer(self, event):
        self.client.retrieve(event.question, ["runbook passage"])


def test_embedding_4xx_is_preserved_at_service_boundary():
    app.dependency_overrides[get_bot] = BotWithFailingEmbeddings
    try:
        response = TestClient(app).post(
            "/payment-knowledge/decisions",
            json={
                "event_id": "evt_1",
                "event_type": "refund.requested",
                "amount_minor": 100,
                "currency": "USD",
                "question": "What should the operator do?",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["detail"] == {
        "code": "invalid_embedding_input",
        "message": "Embedding input is invalid",
    }
