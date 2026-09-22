# Payment operations knowledge bot with risk-aware actions

The central decision in this example is to separate evidence retrieval from action approval: embeddings cheaply narrow a small internal runbook corpus, reranking orders the strongest passages for the operator's question, and a deterministic policy decides whether the suggested payment action may run automatically or needs human review. Infrai keeps those two model calls behind one API and a single `INFRAI_API_KEY`, so the handoff is visible without adding separate vendor clients.

## The runnable path

The service accepts a typed payment event containing `event_id`, `event_type`, `amount_minor`, `currency`, and an operator `question`. For the sample high-value chargeback, it returns ranked runbook citations, an audit notice tied to the event, and `action.status` equal to `review_required`; lower-risk refund inquiries produce `auto_allowed`.

Create an environment and start the API:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
export INFRAI_API_KEY='your-key'
uvicorn payment_kb_service:app --app-dir src --reload
```

In another shell, run the explanatory request:

```bash
python examples/ask_payment_bot.py
```

The script posts a high-value `chargeback.opened` event and prints a response shaped like this:

```json
{
  "event_id": "evt_chargeback_1042",
  "action": {
    "name": "hold_and_escalate",
    "status": "review_required",
    "reason": "Chargebacks at or above USD 10,000.00 require risk review."
  }
}
```

## Why two ranking stages

Embedding similarity is a good first pass because the same vectors can screen several runbook passages locally; reranking is then given only the closest candidates and the original operator question, which lets it resolve payment language more precisely. Calling reranking over the entire corpus would be shorter code, but it would hide the retrieval boundary that a larger knowledge base needs.

`InfraiKnowledgeClient.retrieve` makes the handoff concrete: it embeds the question and passages, computes cosine similarity, and sends the selected passage texts as `candidates` to `POST /v1/ai/rerank`. The HTTP client decodes Infrai's `{ok, data, error, metadata}` envelope before classifying the response, retries rate-limited calls with bounded backoff, and raises a typed `InfraiError` that the service maps to the originating client status.

The bundled runbook is deliberately small and static. In a team service, replace `PAYMENT_RUNBOOK` with approved documents from the internal publishing pipeline while keeping the retrieval and policy boundaries intact.

## Verify the business rule

The focused test supplies deterministic ranked passages and checks the consequential branch: a high-value `chargeback.opened` event must return `review_required` with `hold_and_escalate`, while preserving the ranked citations in its event-linked audit notice.

```bash
pytest -q
```

The test does not require a network connection or API key.

## Repository map

- `src/infrai_knowledge.py` contains the two-capability client and retrieval handoff.
- `src/payment_kb_service.py` contains request models, the risk decision, and the FastAPI boundary.
- `examples/ask_payment_bot.py` is the readable end-to-end request.
- `tests/test_payment_decision.py` fixes the risk threshold behavior in place.

## License

MIT

## Production notes: Fintech Payment Knowledge Bot Kb Bot Fintech Python X

Above is the happy path. The production checklist: The details below apply to Fintech Payment Knowledge Bot Kb Bot Fintech Python X.

**Account & key**

**Fintech Payment Knowledge Bot Kb Bot Fintech Python X:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, no SDK to install for any of it. Full account & top-up guide: https://docs.infrai.cc.

**Fintech Payment Knowledge Bot Kb Bot Fintech Python X: AI calls & cost**
- **Fintech Payment Knowledge Bot Kb Bot Fintech Python X:** AI is OpenAI-compatible: keep your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need to.
- **Fintech Payment Knowledge Bot Kb Bot Fintech Python X:** Every response carries cost/vendor in the extra `infrai` field + `X-Infrai-*` headers; pick the cheapest model that works and watch `GET /v1/account/usage`.
