from infrai_knowledge import RankedPassage
from payment_kb_service import PaymentEventRequest, PaymentKnowledgeBot


class FixedRetriever:
    def retrieve(self, question, passages, shortlist_size, top_k):
        assert "hold funds" in question
        return [
            RankedPassage(passages[0], 0.98),
            RankedPassage(passages[3], 0.81),
        ]


def test_high_value_chargeback_requires_review_and_keeps_citations():
    event = PaymentEventRequest(
        event_id="evt_chargeback_1042",
        event_type="chargeback.opened",
        amount_minor=2_500_000,
        currency="USD",
        question="Which runbook rule applies before we hold funds for this chargeback?",
    )

    decision = PaymentKnowledgeBot(FixedRetriever()).answer(event)

    assert decision.action.status == "review_required"
    assert decision.action.name == "hold_and_escalate"
    assert decision.citations[0].score == 0.98
    assert "USD 10,000.00" in decision.answer
    assert decision.audit_notice.event_id == "evt_chargeback_1042"
    assert decision.audit_notice.evidence == [item.text for item in decision.citations]
