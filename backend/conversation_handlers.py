"""
magicpin AI Challenge — Stateful Multi-Turn Conversation Handler
Handles Auto-reply detection, Intent transitions, Hostility/Opt-out, and Curveballs.

Enhanced with LLM-powered contextual replies for competition-winning quality.
"""

from __future__ import annotations
import os
import re
import json
from typing import Dict, Any, Optional, Tuple, List


# Patterns for auto-reply detection
AUTO_REPLY_PATTERNS = [
    r"thank you for contacting",
    r"our team will respond shortly",
    r"we are currently away",
    r"automated assistant",
    r"auto-generated",
    r"hamari team tak pahuncha",
    r"shukriya.*automated",
    r"replying to messages during business hours",
    r"we have received your message",
    r"thanks for reaching out",
    r"aapki jaankari.*team tak",
    r"main ek automated",
]

# Patterns for hostile / opt-out
HOSTILE_PATTERNS = [
    r"stop messaging",
    r"spam",
    r"not interested",
    r"unsubscribe",
    r"don't message",
    r"dont message",
    r"block",
    r"useless",
    r"harass",
    r"leave me alone",
    r"remove my number",
    r"band karo",
    r"mat bhejo",
    r"pareshan",
]

# Patterns for action commitment / intent
INTENT_PATTERNS = [
    r"lets do it",
    r"let's do it",
    r"whats next",
    r"what's next",
    r"i want to join",
    r"yes please",
    r"send the abstract",
    r"draft the",
    r"go ahead",
    r"proceed",
    r"sure[,.]?\s*send",
    r"yes send",
    r"yes do it",
    r"ok lets do",
    r"schedule it",
    r"publish it",
    r"haan bhejo",
    r"kar do",
    r"chalo",
    r"theek hai",
]

REPLY_SYSTEM_PROMPT = """You are Vera 2.0, magicpin's AI merchant assistant, in an active WhatsApp conversation.
You MUST reply in context of the conversation history. Rules:

1. NEVER re-introduce yourself
2. If merchant said YES/agreed → switch to ACTION MODE immediately, deliver value (draft, link, schedule)
3. If merchant asked a question → answer it using ONLY facts from the merchant/category context, never fabricate
4. Keep replies SHORT (1-3 sentences max, this is WhatsApp)
5. Always end with a SINGLE clear next step
6. Match language (if they wrote Hinglish, reply in Hinglish)
7. For out-of-scope questions (GST, tax, hiring) → politely decline and redirect to your domain
8. NEVER say "I'm just an AI" or "I can't help with that"

OUTPUT FORMAT (strict JSON):
{"action":"send","body":"your reply","cta":"binary_yes_no|open_ended|none","rationale":"why this reply"}
"""


class ConversationManager:
    """Manages active conversation states and multi-turn replies."""

    def __init__(self):
        self._conversations: Dict[str, Dict[str, Any]] = {}
        self._llm_client = None

    def _get_llm(self):
        """Lazy-init LLM client for reply generation."""
        if self._llm_client is not None:
            return self._llm_client
        
        # Try providers in order: Gemini > xAI > OpenAI
        providers = [
            ("GEMINI_API_KEY", "https://generativelanguage.googleapis.com/v1beta/openai/", "gemini-3.8-flash"),
            ("XAI_API_KEY", "https://api.x.ai/v1", "grok-3-mini"),
            ("OPENAI_API_KEY", "https://api.openai.com/v1", "gpt-4o-mini"),
        ]
        for env_var, base_url, model in providers:
            api_key = os.getenv(env_var, "")
            if api_key:
                try:
                    from openai import OpenAI
                    self._llm_client = OpenAI(api_key=api_key, base_url=base_url)
                    self._llm_model = model
                    return self._llm_client
                except Exception:
                    pass
        return None

    def get_or_create_state(self, conversation_id: str, merchant_id: str) -> Dict[str, Any]:
        if conversation_id not in self._conversations:
            self._conversations[conversation_id] = {
                "conversation_id": conversation_id,
                "merchant_id": merchant_id,
                "turn_count": 0,
                "history": [],
                "auto_reply_count": 0,
                "status": "active"
            }
        return self._conversations[conversation_id]

    def handle_reply(
        self,
        conversation_id: str,
        merchant_id: str,
        message: str,
        turn_number: int,
        context_store: Any
    ) -> Dict[str, Any]:
        
        state = self.get_or_create_state(conversation_id, merchant_id)
        state["turn_count"] = turn_number
        state["history"].append({"from": "merchant", "message": message, "turn": turn_number})
        
        msg_lower = message.lower().strip()

        # 1. Check Hostile / Opt-out
        if any(re.search(pat, msg_lower) for pat in HOSTILE_PATTERNS):
            state["status"] = "ended"
            body = (
                "Samajh gayi, bilkul koi baat nahi. Maine aapke listing ke notifications "
                "pause kar diye hain. Agar future mein zaroorat ho toh magicpin app pe "
                "Vera se connect kar sakte hain. Best wishes! 🙂"
            )
            return {
                "action": "end",
                "body": body,
                "cta": "none",
                "rationale": "Merchant opted out. Graceful exit with Hinglish empathy, paused notifications, left door open."
            }

        # 2. Check Auto-Reply
        is_auto_reply = any(re.search(pat, msg_lower) for pat in AUTO_REPLY_PATTERNS)
        if is_auto_reply:
            state["auto_reply_count"] += 1
            if state["auto_reply_count"] >= 2:
                # Try once more with a different approach, then stop
                if state["auto_reply_count"] >= 3:
                    state["status"] = "ended"
                    return {
                        "action": "end",
                        "rationale": "3× auto-reply detected. Stopping to avoid spam. Will retry via different channel/time."
                    }
                return {
                    "action": "send",
                    "body": "Samajh gayi — yeh auto-reply lag raha hai. Kya aap khud dekhna chahengi ki Google pe exactly kya missing hai? 2-min ka kaam hai. Chalega?",
                    "cta": "binary_yes_no",
                    "rationale": "Detected auto-reply on 2nd occurrence. Trying one more time with direct question to break through to human."
                }
            return {
                "action": "wait",
                "wait_seconds": 14400,
                "rationale": "Detected merchant WhatsApp Business canned auto-reply. Backing off 4 hours to wait for human owner."
            }

        # 3. Check Intent Commitment — SWITCH TO ACTION MODE IMMEDIATELY
        is_intent = any(re.search(pat, msg_lower) for pat in INTENT_PATTERNS)
        if is_intent or msg_lower in ["yes", "ok", "haan", "ha", "sure", "1", "y"]:
            # Try LLM for contextual action reply
            llm_result = self._llm_action_reply(state, message, merchant_id, context_store)
            if llm_result:
                state["history"].append({"from": "vera", "message": llm_result["body"], "turn": turn_number})
                return llm_result

            # Template fallback for action mode
            merchant = context_store.get_merchant(merchant_id) or {}
            cat_slug = merchant.get("category_slug", "general")
            m_name = merchant.get("identity", {}).get("name", "your listing")
            offers = [o for o in merchant.get("offers", []) if o.get("status") == "active"]
            offer_str = offers[0].get("title", "") if offers else ""

            if cat_slug == "dentists":
                body = (
                    f"Done! Research abstract bhej rahi hoon (PDF). Saath mein patient WhatsApp draft bhi ready hai:\n\n"
                    f"\"Naye clinical data ke mutabik 3-month fluoride recall se cavity recurrence 38% kam hoti hai. "
                    f"Abhi book karein — {offer_str or '₹299 consultation'}.\"\n\n"
                    f"Kal subah 10 AM ka Google post schedule karun? Reply YES to confirm."
                )
            elif cat_slug == "restaurants":
                body = (
                    f"Done! Campaign draft ready hai {m_name} ke liye:\n\n"
                    f"\"{offer_str}\" — targeting {merchant.get('identity', {}).get('locality', 'your area')} ke 2km radius mein.\n\n"
                    f"Abhi publish karun ya kal lunch time pe schedule karun? Reply 1 for now, 2 for tomorrow."
                )
            else:
                body = (
                    f"Done! Aapka campaign draft ready hai:\n\n"
                    f"\"{offer_str or 'Your active offer'}\" — Google listing pe live hoga + nearby users ko push notification jayega.\n\n"
                    f"Publish karun? Reply YES to go live."
                )

            result = {
                "action": "send",
                "body": body,
                "cta": "binary_yes_no",
                "rationale": "Merchant signaled positive intent. Immediately switched to ACTION mode delivering tangible draft with binary confirmation."
            }
            state["history"].append({"from": "vera", "message": body, "turn": turn_number})
            return result

        # 4. Out-of-Scope / Curveball
        if any(w in msg_lower for w in ["gst", "tax", "accounting", "ca ", "billing software", "hiring", "salary", "rent"]):
            body = (
                "GST aur accounting ke liye aapke CA se baat karna best rahega — yeh mere scope se bahar hai. "
                "Wapas aapke marketing pe aata hoon — aapka active offer post publish karna hai? Reply YES."
            )
            result = {
                "action": "send",
                "body": body,
                "cta": "binary_yes_no",
                "rationale": "Politely declined out-of-scope inquiry and redirected to core listing growth action."
            }
            state["history"].append({"from": "vera", "message": body, "turn": turn_number})
            return result

        # 5. LLM-powered contextual reply for general conversation
        llm_result = self._llm_contextual_reply(state, message, merchant_id, context_store)
        if llm_result:
            state["history"].append({"from": "vera", "message": llm_result["body"], "turn": turn_number})
            return llm_result

        # 6. Template fallback for general conversational reply
        body = (
            "Noted! Main aapke profile ke liye ek fresh promotional post draft kar sakti hoon. "
            "Ya agar aap kuch specific share karna chahein toh bataiye — local search trends bhi check karungi. "
            "Reply 1 to publish, ya batayein kya chahiye."
        )
        result = {
            "action": "send",
            "body": body,
            "cta": "open_ended",
            "rationale": "Acknowledged merchant input and guided toward actionable next step."
        }
        state["history"].append({"from": "vera", "message": body, "turn": turn_number})
        return result

    def _llm_action_reply(self, state: dict, message: str, merchant_id: str, context_store) -> Optional[dict]:
        """Use LLM to generate an action-mode reply when merchant says YES."""
        client = self._get_llm()
        if not client:
            return None
        
        merchant = context_store.get_merchant(merchant_id) or {}
        cat_slug = merchant.get("category_slug", "general")
        category = context_store.get_category(cat_slug) or {}

        history_str = "\n".join([
            f"{'VERA' if h['from'] == 'vera' else 'MERCHANT'}: {h['message']}"
            for h in state["history"][-6:]
        ])

        prompt = f"""CONVERSATION HISTORY:
{history_str}

MERCHANT CONTEXT:
name: {merchant.get('identity', {}).get('name', '')}
category: {cat_slug}
locality: {merchant.get('identity', {}).get('locality', '')}
active_offers: {json.dumps([o.get('title','') for o in merchant.get('offers',[]) if o.get('status')=='active'], ensure_ascii=False)}
language_pref: {merchant.get('identity', {}).get('language_pref', 'hi-en')}

The merchant just said YES / agreed. Switch to ACTION MODE immediately.
- Deliver something tangible (draft, link, schedule, confirmation)
- Be specific about what you're doing
- End with ONE confirmation step
- Keep it SHORT (2-3 sentences)
- Use Hinglish if appropriate

Return ONLY JSON: {{"action":"send","body":"...","cta":"binary_yes_no","rationale":"..."}}"""

        try:
            resp = client.chat.completions.create(
                model=getattr(self, '_llm_model', 'gemini-3.8-flash'),
                temperature=0,
                max_tokens=1000,
                timeout=20,
                messages=[
                    {"role": "system", "content": REPLY_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ]
            )
            raw = resp.choices[0].message.content or ""
            content = raw.strip()
            if "```json" in content:
                content = content.split("```json", 1)[1].split("```", 1)[0].strip()
            elif "```" in content:
                content = content.split("```", 1)[1].split("```", 1)[0].strip()
            else:
                m = re.search(r'(\{[\s\S]*\})', content)
                if m:
                    content = m.group(1).strip()
            return json.loads(content)
        except Exception:
            return None

    def _llm_contextual_reply(self, state: dict, message: str, merchant_id: str, context_store) -> Optional[dict]:
        """Use LLM for general contextual multi-turn replies."""
        client = self._get_llm()
        if not client:
            return None
        
        merchant = context_store.get_merchant(merchant_id) or {}
        cat_slug = merchant.get("category_slug", "general")

        history_str = "\n".join([
            f"{'VERA' if h['from'] == 'vera' else 'MERCHANT'}: {h['message']}"
            for h in state["history"][-6:]
        ])

        prompt = f"""CONVERSATION HISTORY:
{history_str}

MERCHANT: {merchant.get('identity', {}).get('name', '')} ({cat_slug})
LOCALITY: {merchant.get('identity', {}).get('locality', '')}
ACTIVE OFFERS: {json.dumps([o.get('title','') for o in merchant.get('offers',[]) if o.get('status')=='active'], ensure_ascii=False)}
PERFORMANCE: views={merchant.get('performance',{}).get('views','N/A')}, rating={merchant.get('performance',{}).get('rating','N/A')}

Respond naturally in context. Don't re-introduce yourself. Keep it short. Guide toward actionable outcome.
Use Hinglish if the merchant is writing in Hindi/Hinglish.

Return ONLY JSON: {{"action":"send","body":"...","cta":"binary_yes_no|open_ended|none","rationale":"..."}}"""

        try:
            resp = client.chat.completions.create(
                model=getattr(self, '_llm_model', 'gemini-3.8-flash'),
                temperature=0,
                max_tokens=1000,
                timeout=20,
                messages=[
                    {"role": "system", "content": REPLY_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ]
            )
            raw = resp.choices[0].message.content or ""
            content = raw.strip()
            if "```json" in content:
                content = content.split("```json", 1)[1].split("```", 1)[0].strip()
            elif "```" in content:
                content = content.split("```", 1)[1].split("```", 1)[0].strip()
            else:
                m = re.search(r'(\{[\s\S]*\})', content)
                if m:
                    content = m.group(1).strip()
            return json.loads(content)
        except Exception:
            return None
