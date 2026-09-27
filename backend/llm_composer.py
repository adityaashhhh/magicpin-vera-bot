"""
magicpin AI Challenge — LLM-Powered 4-Context Message Composer
Uses Grok (xAI) via OpenAI-compatible API for intelligent composition.

Scores optimized across all 5 judge dimensions:
  1. Specificity (verifiable facts, numbers, dates)
  2. Category Fit (voice, vocabulary, taboos)
  3. Merchant Fit (personalized to THIS merchant's data)
  4. Trigger Relevance (why NOW, what triggered this)
  5. Engagement Compulsion (curiosity, loss aversion, social proof)
"""

from __future__ import annotations
import os
import re
import json
import time
import hashlib
from typing import Dict, Any, Optional

from openai import OpenAI

# ---------------------------------------------------------------------------
# Configuration — Auto-detect LLM provider
# Priority: GEMINI_API_KEY > XAI_API_KEY > OPENAI_API_KEY
# ---------------------------------------------------------------------------
def _detect_provider():
    """Auto-detect which LLM provider to use based on environment variables."""
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    xai_key = os.getenv("XAI_API_KEY", "")
    openai_key = os.getenv("OPENAI_API_KEY", "")
    
    if gemini_key:
        return {
            "api_key": gemini_key,
            "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
            "model": os.getenv("LLM_MODEL", "gemini-3.8-flash"),
            "provider": "gemini"
        }
    elif xai_key:
        return {
            "api_key": xai_key,
            "base_url": "https://api.x.ai/v1",
            "model": os.getenv("LLM_MODEL", "grok-3-mini"),
            "provider": "xai"
        }
    elif openai_key:
        return {
            "api_key": openai_key,
            "base_url": "https://api.openai.com/v1",
            "model": os.getenv("LLM_MODEL", "gpt-4o-mini"),
            "provider": "openai"
        }
    else:
        return None

TEMPERATURE = 0  # deterministic per challenge requirement
MAX_TOKENS = 1500
TIMEOUT = 25  # seconds — must complete under 30s per challenge rules


# ---------------------------------------------------------------------------
# System Prompt — encodes the entire challenge rubric into the LLM
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are Vera 2.0, magicpin's autonomous merchant intelligence engine.
You compose WhatsApp messages for Indian local merchants (dentists, salons, restaurants, gyms, pharmacies).

## YOUR TASK
Given 4 structured contexts (Category, Merchant, Trigger, optionally Customer), compose ONE WhatsApp message.

## OUTPUT FORMAT (strict JSON)
```json
{
  "body": "the WhatsApp message body",
  "cta": "binary_yes_no | open_ended | multi_choice_slot | none",
  "send_as": "vera | merchant_on_behalf",
  "suppression_key": "string for dedup",
  "rationale": "1-2 sentence explanation of why this message, what compulsion lever it uses"
}
```

## RULES YOU MUST FOLLOW

### Voice & Tone
- For merchant-facing (send_as=vera): peer/colleague tone. You are a helpful business partner, NOT a salesperson.
- For customer-facing (send_as=merchant_on_behalf): warm, professional, as if the merchant's clinic/shop is messaging.
- Match the category voice: dentists=clinical peer, salons=warm practical, restaurants=operator, gyms=coaching energy, pharmacies=trust precision.
- NEVER use promotional language ("AMAZING DEAL!", "Don't miss out!", "Limited time!") for clinical categories.

### Hindi-English Code-Mix
- If the merchant's language_pref includes "hi" or "hi-en", USE Hinglish naturally.
- Example: "Dr. Meera, JIDA ka Oct issue aaya hai. Ek item relevant hai aapke high-risk adult patients ke liye..."
- If language_pref is "en" or unspecified, use English.

### Specificity (this is THE most important dimension)
- ALWAYS anchor on a concrete, verifiable fact from the contexts: a number, date, percentage, price, source citation, patient count, review count.
- NEVER write generic messages like "improve your sales" or "10% off". Always use exact service+price from the merchant's catalog or category's offer_catalog.
- Example good: "Haircut @ ₹99" or "Dental Cleaning @ ₹299" or "2,100-patient trial showed..."
- Example bad: "a special discount" or "great offers"

### Trigger Relevance
- The message MUST explicitly reference WHY you're messaging NOW — the trigger event.
- For research_digest: cite the exact source, trial numbers, patient segment.
- For perf_dip: cite the exact metric, percentage drop, time window.
- For recall_due: cite the customer's last visit date, service due.
- For festival/IPL: cite the specific event, expected search surge.

### Compulsion Levers (use 2+ per message)
1. Specificity/verifiability — concrete numbers
2. Loss aversion — "you're missing X" / "before this window closes"
3. Social proof — "3 dentists in your locality did Y this month" (use peer_stats from CategoryContext)
4. Effort externalization — "I've already drafted X — just say go"
5. Curiosity — "want to see who?" / "want the full list?"
6. Reciprocity — "I noticed Y, thought you'd want to know"
7. Asking the merchant — "what's your most-asked service this week?"

### Anti-Patterns (NEVER do these)
- Generic offers when service+price is available in the catalog
- Multiple CTAs in one message
- Buried CTA — the action request MUST be in the last 1-2 sentences
- Long preambles ("I hope you're doing well...")
- Re-introducing yourself after first message
- Fabricating data not in the contexts (no fake research, no fake competitors)
- Same message verbatim as previously sent

### CTA Rules
- send_as=vera (merchant-facing): Use binary_yes_no for action triggers, open_ended for information/curiosity triggers
- send_as=merchant_on_behalf (customer-facing): Use multi_choice_slot for booking, binary_yes_no for confirmations
- CTA should be the LAST sentence

### Suppression Key
- Format: "{trigger_kind}:{merchant_category}:{time_period}" for merchant-facing
- Format: "cx:{trigger_kind}:{merchant_id}:{customer_id}" for customer-facing

### Message Length
- Keep it concise: 2-4 sentences for merchant-facing, 3-5 for customer-facing
- No walls of text — this is WhatsApp, not email
"""


# ---------------------------------------------------------------------------
# Composer Class
# ---------------------------------------------------------------------------
class LLMComposer:
    """LLM-powered 4-context composer using Gemini/Grok/OpenAI via OpenAI-compatible API."""

    def __init__(self):
        self._client = None
        self._provider = None
        self._cache: Dict[str, Dict[str, Any]] = {}  # determinism cache

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            self._provider = _detect_provider()
            if not self._provider:
                raise RuntimeError(
                    "No LLM API key found. Set one of: "
                    "GEMINI_API_KEY, XAI_API_KEY, or OPENAI_API_KEY"
                )
            self._client = OpenAI(
                api_key=self._provider["api_key"],
                base_url=self._provider["base_url"]
            )
            print(f"[LLM] [OK] Connected to {self._provider['provider']} ({self._provider['model']})")
        return self._client

    @property
    def model(self) -> str:
        if self._provider is None:
            _ = self.client  # triggers detection
        return self._provider["model"]

    def _cache_key(self, category: dict, merchant: dict, trigger: dict, customer: Optional[dict]) -> str:
        """Deterministic hash of inputs for caching."""
        raw = json.dumps({
            "cat": category.get("slug", ""),
            "mx": merchant.get("id", merchant.get("identity", {}).get("id", "")),
            "trg": trigger.get("id", ""),
            "cx": (customer or {}).get("customer_id", "")
        }, sort_keys=True)
        return hashlib.md5(raw.encode()).hexdigest()

    def _build_user_prompt(self, category: dict, merchant: dict, trigger: dict, customer: Optional[dict]) -> str:
        """Build a structured user prompt from the 4 contexts."""

        # Extract key fields to keep prompt focused
        cat_slug = category.get("slug", "general")
        voice = category.get("voice", {})
        peer_stats = category.get("peer_stats", {})
        offer_catalog = category.get("offer_catalog", [])
        digest = category.get("digest", [])
        taboos = category.get("taboos", [])

        m_identity = merchant.get("identity", {})
        m_perf = merchant.get("performance", {})
        m_offers = merchant.get("offers", [])
        m_signals = merchant.get("signals", [])
        m_history = merchant.get("conversation_history", [])
        m_reviews = merchant.get("review_themes", [])

        t_kind = trigger.get("kind", "")
        t_scope = trigger.get("scope", "merchant")
        t_payload = trigger.get("payload", {})
        t_urgency = trigger.get("urgency", 1)
        t_suppression = trigger.get("suppression_key", "")

        # Determine send_as
        is_customer_facing = t_scope == "customer" or customer is not None
        send_as = "merchant_on_behalf" if is_customer_facing else "vera"

        # Language preference
        lang_pref = m_identity.get("language_pref", "en")
        if customer:
            lang_pref = customer.get("identity", {}).get("language_pref", lang_pref)

        prompt_parts = []
        prompt_parts.append(f"## COMPOSE A MESSAGE\nsend_as: {send_as}")
        prompt_parts.append(f"language_preference: {lang_pref}")

        # Category Context
        prompt_parts.append(f"\n## CATEGORY CONTEXT\nslug: {cat_slug}")
        if voice:
            prompt_parts.append(f"voice_tone: {voice.get('tone', 'professional')}")
            if voice.get("vocab_allowed"):
                prompt_parts.append(f"vocab_allowed: {', '.join(voice['vocab_allowed'][:10])}")
        if taboos:
            prompt_parts.append(f"TABOO WORDS (never use): {', '.join(taboos)}")
        if peer_stats:
            prompt_parts.append(f"peer_stats: avg_ctr={peer_stats.get('avg_ctr', 'N/A')}, avg_views={peer_stats.get('avg_views_30d', 'N/A')}")
        if offer_catalog:
            catalog_str = "; ".join([f"{o.get('title', '')} @ ₹{o.get('price', '')}" for o in offer_catalog[:5] if o.get('title')])
            prompt_parts.append(f"category_offer_catalog: [{catalog_str}]")
        if digest:
            for d in digest[:2]:
                prompt_parts.append(f"digest_item: title=\"{d.get('title', '')}\", source=\"{d.get('source', '')}\", summary=\"{d.get('summary', '')}\"")

        # Merchant Context
        prompt_parts.append(f"\n## MERCHANT CONTEXT")
        prompt_parts.append(f"id: {m_identity.get('id', merchant.get('id', ''))}")
        prompt_parts.append(f"name: {m_identity.get('name', '')}")
        prompt_parts.append(f"owner: {m_identity.get('owner_first_name', '')}")
        prompt_parts.append(f"locality: {m_identity.get('locality', '')}, city: {m_identity.get('city', '')}")
        if m_perf:
            prompt_parts.append(f"performance: views={m_perf.get('views', 'N/A')}, calls={m_perf.get('calls', 'N/A')}, ctr={m_perf.get('ctr', 'N/A')}, rating={m_perf.get('rating', 'N/A')}, reviews={m_perf.get('review_count', 'N/A')}")
        if m_offers:
            active = [o for o in m_offers if o.get("status") == "active"]
            if active:
                offers_str = "; ".join([o.get("title", "") for o in active[:3]])
                prompt_parts.append(f"active_offers: [{offers_str}]")
        if m_signals:
            prompt_parts.append(f"signals: {', '.join(m_signals[:5])}")
        if m_reviews:
            themes_str = "; ".join([f"{r.get('theme', '')}: {r.get('sentiment', '')} ({r.get('count', '')} mentions)" for r in m_reviews[:3]])
            prompt_parts.append(f"review_themes: [{themes_str}]")
        if m_history:
            last = m_history[-1] if m_history else {}
            prompt_parts.append(f"last_vera_touch: {last.get('date', 'unknown')} — outcome: {last.get('outcome', 'unknown')}")

        # Trigger Context
        prompt_parts.append(f"\n## TRIGGER CONTEXT")
        prompt_parts.append(f"kind: {t_kind}")
        prompt_parts.append(f"scope: {t_scope}")
        prompt_parts.append(f"urgency: {t_urgency}")
        prompt_parts.append(f"suppression_key_hint: {t_suppression}")
        if t_payload:
            prompt_parts.append(f"payload: {json.dumps(t_payload, ensure_ascii=False, default=str)}")

        # Customer Context (if present)
        if customer:
            c_id = customer.get("identity", {})
            c_rel = customer.get("relationship", {})
            c_state = customer.get("state", "unknown")
            c_prefs = customer.get("preferences", {})
            prompt_parts.append(f"\n## CUSTOMER CONTEXT")
            prompt_parts.append(f"name: {c_id.get('name', '')}")
            prompt_parts.append(f"language_pref: {c_id.get('language_pref', 'en')}")
            prompt_parts.append(f"state: {c_state}")
            prompt_parts.append(f"last_visit: {c_rel.get('last_visit', 'unknown')}")
            prompt_parts.append(f"visits_total: {c_rel.get('visits_total', 0)}")
            prompt_parts.append(f"services: {', '.join(c_rel.get('services_received', []))}")
            if c_prefs:
                prompt_parts.append(f"preferred_time: {c_prefs.get('preferred_time', 'any')}")

        prompt_parts.append("\n## INSTRUCTION")
        prompt_parts.append("Compose the message now. Return ONLY the JSON object, no markdown fencing, no explanation.")

        return "\n".join(prompt_parts)

    def _validate_output(self, result: dict, category: dict, trigger: dict, customer: Optional[dict]) -> dict:
        """Post-LLM validation: ensure output meets challenge constraints."""

        # Ensure required keys exist
        for key in ["body", "cta", "send_as", "suppression_key", "rationale"]:
            if key not in result:
                if key == "body":
                    result["body"] = "Error: composition failed."
                elif key == "cta":
                    result["cta"] = "binary_yes_no"
                elif key == "send_as":
                    is_cx = trigger.get("scope") == "customer" or customer is not None
                    result["send_as"] = "merchant_on_behalf" if is_cx else "vera"
                elif key == "suppression_key":
                    result["suppression_key"] = trigger.get("suppression_key", "unknown")
                elif key == "rationale":
                    result["rationale"] = "Composed via Vera 2.0 engine."

        # Validate CTA values
        valid_ctas = {"binary_yes_no", "open_ended", "multi_choice_slot", "none"}
        if result["cta"] not in valid_ctas:
            result["cta"] = "binary_yes_no"

        # Validate send_as
        if result["send_as"] not in {"vera", "merchant_on_behalf"}:
            is_cx = trigger.get("scope") == "customer" or customer is not None
            result["send_as"] = "merchant_on_behalf" if is_cx else "vera"

        # Check for taboo words
        taboos = category.get("taboos", [])
        body_lower = result["body"].lower()
        for taboo in taboos:
            if taboo.lower() in body_lower:
                result["body"] = result["body"].replace(taboo, "[REMOVED]")
                result["rationale"] += f" [Warning: taboo word '{taboo}' was filtered.]"

        return result

    def compose(
        self,
        category: Dict[str, Any],
        merchant: Dict[str, Any],
        trigger: Dict[str, Any],
        customer: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Main composition entry point.
        Calls Grok LLM with full 4-context prompt, validates output.
        """

        # Check cache for determinism
        cache_key = self._cache_key(category, merchant, trigger, customer)
        if cache_key in self._cache:
            return self._cache[cache_key]

        user_prompt = self._build_user_prompt(category, merchant, trigger, customer)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                temperature=TEMPERATURE,
                max_tokens=MAX_TOKENS,
                timeout=TIMEOUT,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ]
            )

            raw_content = response.choices[0].message.content or ""
            content = raw_content.strip()

            # Robust JSON extraction: look for code fences or { ... }
            if "```json" in content:
                content = content.split("```json", 1)[1].split("```", 1)[0].strip()
            elif "```" in content:
                content = content.split("```", 1)[1].split("```", 1)[0].strip()
            else:
                match = re.search(r'(\{[\s\S]*\})', content)
                if match:
                    content = match.group(1).strip()

            result = json.loads(content)
            result = self._validate_output(result, category, trigger, customer)

            # Add template fields for the server
            result["template_name"] = f"vera_{trigger.get('kind', 'general')}_v1"
            result["template_params"] = [
                merchant.get("identity", {}).get("owner_first_name", ""),
                trigger.get("kind", ""),
            ]

            # Cache for determinism
            self._cache[cache_key] = result
            return result

        except json.JSONDecodeError as e:
            # LLM returned non-JSON — fall back
            return self._fallback(category, merchant, trigger, customer, f"JSON parse error: {e}")
        except Exception as e:
            return self._fallback(category, merchant, trigger, customer, str(e))

    def _fallback(
        self,
        category: Dict[str, Any],
        merchant: Dict[str, Any],
        trigger: Dict[str, Any],
        customer: Optional[Dict[str, Any]],
        error: str
    ) -> Dict[str, Any]:
        """Fallback to template-based composition if LLM fails."""
        from backend.composer import EngagementComposer
        fallback = EngagementComposer()
        result = fallback.compose(category, merchant, trigger, customer)
        # Log cleanly without contaminating the output rationale
        print(f"[LLM] [INFO] Used deterministic fallback: {str(error)[:60]}")
        return result
