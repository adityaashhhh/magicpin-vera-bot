"""
magicpin AI Challenge — Candidate Bot Module (bot.py)
Implements the canonical compose(...) entry point for evaluation.

Uses LLM-powered composition (Grok via xAI) with template fallback.
"""

import os
from typing import Optional, Dict, Any

# Try LLM composer first, fall back to template composer
_COMPOSER = None

def _get_composer():
    global _COMPOSER
    if _COMPOSER is not None:
        return _COMPOSER
    
    has_llm_key = any([
        os.getenv("GEMINI_API_KEY", ""),
        os.getenv("XAI_API_KEY", ""),
        os.getenv("OPENAI_API_KEY", ""),
    ])
    if has_llm_key:
        try:
            from backend.llm_composer import LLMComposer
            _COMPOSER = LLMComposer()
            print("[bot.py] [OK] LLM Composer active")
            return _COMPOSER
        except Exception as e:
            print(f"[bot.py] [WARN] LLM Composer failed to init: {e}")
    
    # Fallback to template composer
    from backend.composer import EngagementComposer
    _COMPOSER = EngagementComposer()
    print("[bot.py] [INFO] Using template composer (set GEMINI_API_KEY/XAI_API_KEY for LLM mode)")
    return _COMPOSER


def compose(category: dict, merchant: dict, trigger: dict, customer: Optional[dict] = None) -> dict:
    """
    Official Challenge Entrypoint.
    
    Inputs:
        category: dict - CategoryContext (voice, offer_catalog, peer_stats, digest, etc.)
        merchant: dict - MerchantContext (identity, performance, offers, history, signals)
        trigger: dict  - TriggerContext (kind, source, payload, urgency, suppression_key)
        customer: Optional[dict] - CustomerContext (identity, relationship, state, preferences)

    Returns:
        dict with keys:
            - body: str (WhatsApp message body)
            - cta: str ("binary_yes_no", "open_ended", "multi_choice_slot", "none")
            - send_as: str ("vera" or "merchant_on_behalf")
            - suppression_key: str
            - rationale: str
    """
    composer = _get_composer()
    return composer.compose(
        category=category,
        merchant=merchant,
        trigger=trigger,
        customer=customer
    )
