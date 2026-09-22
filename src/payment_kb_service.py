from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from infrai_knowledge import InfraiError, InfraiKnowledgeClient, RankedPassage


PAYMENT_RUNBOOK = (
    "Chargebacks at or above USD 10,000.00 require risk review before funds are held or released.",
    "Refund requests below the high-value review threshold may be approved automatically when the payment identity matches.",
    "A duplicate card authorization should be voided only after the processor reference is confirmed.",
    "Operators must record the cited runbook passage and event identifier with every payment action.",
    "Account-takeover signals require manual review regardless of the payment amount.",
)


class PaymentEventRequest(BaseModel):
    event_id: str = Field(min_length=1)
    event_type: Literal["chargeback.opened", "refund.requested", "authorization.duplicated"]
    amount_minor: int = Field(ge=0)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    question: str = Field(min_length=3)


class Citation(BaseModel):
    text: str
    score: float


class RiskAction(BaseModel):
    name: str
    status: Literal["auto_allowed", "review_required"]
    reason: str


class AuditNotice(BaseModel):
    notice_id: str
    event_id: str
    message: str
    evidence: list[str]


class KnowledgeDecision(BaseModel):
    event_id: str
    answer: str
    citations: list[Citation]
    action: RiskAction
    audit_notice: AuditNotice


@dataclass
class PaymentKnowledgeBot:
    retriever: InfraiKnowledgeClient

    def answer(self, event: PaymentEventRequest) -> KnowledgeDecision:
        ranked = self.retriever.retrieve(event.question, PAYMENT_RUNBOOK, shortlist_size=4, top_k=2)
        action = self._decide_action(event)
        citations = [Citation(text=item.text, score=item.score) for item in ranked]
        return KnowledgeDecision(
            event_id=event.event_id,
            answer=ranked[0].text,
            citations=citations,
            action=action,
            audit_notice=AuditNotice(
                notice_id=f"notice_{event.event_id}",
                event_id=event.event_id,
                message=f"{action.name}: {action.reason}",
                evidence=[citation.text for citation in citations],
            ),
        )

    @staticmethod
    def _decide_action(event: PaymentEventRequest) -> RiskAction:
        if event.event_type == "chargeback.opened" and event.currency == "USD" and event.amount_minor >= 1_000_000:
            return RiskAction(
                name="hold_and_escalate",
                status="review_required",
                reason="This high-value chargeback requires risk review.",
            )
        return RiskAction(
            name="prepare_operator_response",
            status="auto_allowed",
            reason="The event does not cross the high-value chargeback review threshold.",
        )


app = FastAPI(title="Payment operations knowledge bot")


def get_bot() -> PaymentKnowledgeBot:
    return PaymentKnowledgeBot(InfraiKnowledgeClient())


@app.post("/payment-knowledge/decisions", response_model=KnowledgeDecision)
def decide_payment_action(
    event: PaymentEventRequest,
    bot: PaymentKnowledgeBot = Depends(get_bot),
) -> KnowledgeDecision:
    try:
        return bot.answer(event)
    except InfraiError as exc:
        status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(status_code=status, detail={"code": exc.code, "message": str(exc)}) from exc
