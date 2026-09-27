# Vera 2.0 — magicpin AI Challenge Submission

## Approach

Vera 2.0 is an **LLM-powered 4-context composition engine** that generates hyper-personalized WhatsApp messages for merchants across 5 verticals (dentists, salons, restaurants, gyms, pharmacies).

### Architecture

```
Trigger Event → Context Fusion (4 layers) → LLM Composer (Grok) → Post-Validation → WhatsApp Output
                                                    ↕
                                          Stateful Conversation Manager
                                          (auto-reply · intent · hostile · curveball)
```

### Key Design Decisions

1. **LLM-first composition** — Uses Grok (xAI) via OpenAI-compatible API with a meticulously crafted system prompt encoding the full 5-dimension rubric (specificity, category fit, merchant fit, trigger relevance, engagement compulsion). Temperature=0 for deterministic outputs.

2. **4-Context structured prompting** — All four contexts (Category, Merchant, Trigger, Customer) are serialized into a structured prompt with explicit field labels. The LLM sees exact peer_stats, active offers with prices, digest items with sources, and performance metrics — ensuring every message is grounded in verifiable data.

3. **Hinglish code-mixing** — System prompt instructs the LLM to produce Hindi-English mix when the merchant's `language_pref` indicates `hi` or `hi-en`. Production Vera conversations show Hinglish is natural for Indian merchant audiences.

4. **Multi-lever compulsion** — Each message uses 2+ engagement levers (specificity + effort externalization, loss aversion + social proof, curiosity + reciprocity). The system prompt explicitly encodes all 8 compulsion families from the brief.

5. **Post-LLM validation** — Output is validated for: valid CTA type, correct `send_as` field, taboo word filtering, and JSON schema compliance. Falls back to deterministic template composer if LLM fails.

6. **Stateful multi-turn handling** — Auto-reply detection (regex + repeat count), intent transition (immediate action mode), hostile opt-out (graceful Hinglish exit), and out-of-scope deflection. LLM generates contextual replies using conversation history.

7. **Template fallback** — If LLM is unavailable (no API key, timeout, rate limit), the system gracefully degrades to a rule-based template composer covering all 13+ trigger kinds.

### Tradeoffs

- **LLM latency vs quality**: Chose grok-3-mini for speed (<5s per call) while maintaining high composition quality. Can swap to grok-4 for max quality at ~15s latency.
- **Determinism**: Temperature=0 + response caching ensures identical outputs for identical inputs, as required.
- **No external data**: All facts in messages come exclusively from the provided contexts. Zero hallucination by design — the LLM is constrained to only reference data present in the structured prompt.

### What additional context would help most

1. **Real merchant reply patterns** — A corpus of actual merchant WhatsApp responses (beyond the 4 anonymized examples) would improve auto-reply detection accuracy and multi-turn flow.
2. **Conversion data** — Which message types/CTAs actually drove merchant action (click-through, reply, campaign launch) would let us optimize compulsion lever selection.
3. **Time-of-day preferences** — When merchants are most responsive per category would improve send-time optimization.

## Files

| File | Purpose |
|------|---------|
| `bot.py` | Canonical `compose()` entry point |
| `submission.jsonl` | 30 test pair outputs |
| `backend/llm_composer.py` | LLM-powered 4-context composer (Grok/xAI) |
| `backend/composer.py` | Deterministic template fallback composer |
| `backend/conversation_handlers.py` | Multi-turn state machine with LLM replies |
| `backend/context_store.py` | Thread-safe versioned context store |
| `backend/server.py` | FastAPI server (5 judge endpoints) |
| `backend/models.py` | Pydantic schemas |

## Running

```bash
export XAI_API_KEY=your_key_here
uvicorn backend.server:app --host 0.0.0.0 --port 8080
```
