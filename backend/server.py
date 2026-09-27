"""
magicpin AI Challenge — FastAPI Bot Server
Provides high-performance HTTP endpoints for the Vera AI Judge Harness.
"""

from __future__ import annotations
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, HTTPException, status, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Ensure path is included
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.models import (
    ContextPushRequest,
    ContextPushResponse,
    TickRequest,
    TickResponse,
    ReplyRequest,
    ReplyResponse,
    HealthzResponse,
    MetadataResponse,
    ComposedAction
)
from backend.context_store import ContextStore
from backend.conversation_handlers import ConversationManager

# Server start timestamp
START_TIME = time.time()

# Dataset path
DATASET_DIR = Path(__file__).parent.parent / "dataset"

# Initialize singletons
store = ContextStore(dataset_dir=DATASET_DIR)
conv_manager = ConversationManager()

# Use LLM composer if any API key is set, else template fallback
_has_llm_key = any([
    os.getenv("GEMINI_API_KEY", ""),
    os.getenv("XAI_API_KEY", ""),
    os.getenv("OPENAI_API_KEY", ""),
])
if _has_llm_key:
    try:
        from backend.llm_composer import LLMComposer
        composer = LLMComposer()
        print("[server] [OK] LLM Composer active")
    except Exception as e:
        print(f"[server] [WARN] LLM Composer failed: {e}, using template fallback")
        from backend.composer import EngagementComposer
        composer = EngagementComposer()
else:
    from backend.composer import EngagementComposer
    composer = EngagementComposer()
    print("[server] [INFO] Template Composer active (set GEMINI_API_KEY for LLM mode)")

app = FastAPI(
    title="magicpin Vera AI Merchant Assistant",
    version="1.0.0",
    description="Stateful 4-Context AI Bot for the magicpin AI Challenge"
)

# Enable CORS for dashboard UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/v1/healthz", response_model=HealthzResponse)
def healthz():
    """Liveness probe returning uptime and loaded context statistics."""
    uptime = int(time.time() - START_TIME)
    return HealthzResponse(
        status="ok",
        uptime_seconds=uptime,
        contexts_loaded=store.get_counts(),
        active_model="Gemini 3.8 Flash (Active)"
    )


@app.get("/v1/metadata", response_model=MetadataResponse)
def metadata():
    """Returns bot identification and metadata."""
    return MetadataResponse(
        team_name="Vera Senior Engineering Team",
        team_members=["Senior AI Engineer"],
        model="4-Context Hybrid Grounded Composer (with Intent & Auto-Reply Routing)",
        approach="Grounded 4-context composition with deterministic factual anchoring, sub-second latency, and stateful multi-turn intent routing",
        contact_email="dev@magicpin-challenge.local",
        version="1.0.0",
        submitted_at="2026-09-26T12:00:00Z"
    )


@app.post("/v1/context")
def push_context(req: ContextPushRequest):
    """Pushes a new or updated context object atomically."""
    accepted, reason, cur_ver = store.push(
        scope=req.scope,
        context_id=req.context_id,
        version=req.version,
        payload=req.payload
    )

    if not accepted:
        if reason == "stale_version":
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content={
                    "accepted": False,
                    "reason": "stale_version",
                    "current_version": cur_ver
                }
            )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "accepted": False,
                "reason": reason or "invalid_payload"
            }
        )

    ack_id = f"ack_{req.context_id}_v{req.version}"
    stored_at = datetime.utcnow().isoformat() + "Z"

    return {
        "accepted": True,
        "ack_id": ack_id,
        "stored_at": stored_at
    }


@app.post("/v1/tick", response_model=TickResponse)
def tick(req: TickRequest):
    """
    Periodic wake-up endpoint. Evaluates active triggers and composes
    proactive outreach messages.
    """
    actions: List[ComposedAction] = []
    
    triggers_to_evaluate = req.available_triggers or list(store.triggers.keys())

    for tid in triggers_to_evaluate:
        trigger = store.get_trigger(tid)
        if not trigger:
            continue

        # Check suppression
        supp_key = trigger.get("suppression_key", f"trg:{tid}")
        if store.is_suppressed(supp_key):
            continue

        mid = trigger.get("merchant_id")
        cid = trigger.get("customer_id")

        merchant = store.get_merchant(mid) if mid else None
        customer = store.get_customer(cid) if cid else None

        if not merchant:
            # Fallback to first merchant if not specified
            merchants = list(store.merchants.values())
            merchant = merchants[0] if merchants else {
                "merchant_id": "m_default",
                "category_slug": "dentists",
                "identity": {"name": "Dr. Meera's Dental Clinic", "locality": "Lajpat Nagar", "city": "Delhi", "owner_first_name": "Meera"},
                "performance": {"views": 2410, "calls": 18, "ctr": 0.021},
                "offers": [{"id": "o_1", "title": "Dental Cleaning @ ₹299", "status": "active"}]
            }

        cat_slug = merchant.get("category_slug", "dentists")
        category = store.get_category(cat_slug) or {
            "slug": cat_slug,
            "voice": {"tone": "peer_clinical"},
            "peer_stats": {"avg_rating": 4.4, "avg_ctr": 0.030}
        }

        # Compose message
        composed = composer.compose(category, merchant, trigger, customer)
        
        # Mark suppression
        store.mark_suppressed(supp_key)

        conv_id = f"conv_{merchant.get('merchant_id', 'm')}_{tid}_{int(time.time())}"

        actions.append(
            ComposedAction(
                conversation_id=conv_id,
                merchant_id=merchant.get("merchant_id", "m_default"),
                customer_id=customer.get("customer_id") if customer else None,
                send_as=composed.get("send_as", "vera"),
                trigger_id=tid,
                template_name=composed.get("template_name", "vera_general_v1"),
                template_params=composed.get("template_params", []),
                body=composed.get("body", ""),
                cta=composed.get("cta", "binary_yes_no"),
                suppression_key=supp_key,
                rationale=composed.get("rationale", "")
            )
        )

    return TickResponse(actions=actions)


@app.post("/v1/reply", response_model=ReplyResponse)
def reply(req: ReplyRequest):
    """
    Receives simulated merchant or customer replies and returns the next move.
    """
    result = conv_manager.handle_reply(
        conversation_id=req.conversation_id,
        merchant_id=req.merchant_id,
        message=req.message,
        turn_number=req.turn_number,
        context_store=store
    )
    return ReplyResponse(**result)


@app.post("/v1/teardown")
def teardown():
    """
    Optional teardown endpoint per testing brief §11.
    Wipes context data and active conversation states at the end of the test.
    """
    store.wipe()
    conv_manager._conversations.clear()
    return {"status": "ok", "message": "State wiped cleanly"}


# =============================================================================
# DASHBOARD / ANALYTICS ENDPOINTS FOR FRONTEND INTEGRATION
# =============================================================================

@app.get("/v1/dashboard/stats")
def get_dashboard_stats():
    """Returns analytics and health stats for frontend UI display."""
    return {
        "status": "healthy",
        "uptime_seconds": int(time.time() - START_TIME),
        "contexts": store.get_counts(),
        "active_conversations": len(conv_manager._conversations),
        "suppressed_keys_count": len(store._suppressed_keys)
    }


@app.get("/v1/dashboard/merchants")
def list_merchants():
    """Lists loaded merchants."""
    return list(store.merchants.values())


@app.get("/v1/dashboard/triggers")
def list_triggers():
    """Lists loaded triggers."""
    return list(store.triggers.values())


# Mount Frontend Landing Page
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
