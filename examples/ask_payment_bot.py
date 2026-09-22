import json
import urllib.request


event = {
    "event_id": "evt_chargeback_1042",
    "event_type": "chargeback.opened",
    "amount_minor": 2_500_000,
    "currency": "USD",
    "question": "Which runbook rule applies before we hold funds for this chargeback?",
}

request = urllib.request.Request(
    "http://127.0.0.1:8000/payment-knowledge/decisions",
    data=json.dumps(event).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(request) as response:
    print(json.dumps(json.load(response), indent=2))
