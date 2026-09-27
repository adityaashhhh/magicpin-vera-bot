"""
magicpin AI Challenge — Domain Models & Pydantic Schemas
Strictly adhering to challenge-brief.md and challenge-testing-brief.md
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional, Literal, Union
from pydantic import BaseModel, Field
from datetime import datetime


# =============================================================================
# CONTEXT MODELS
# =============================================================================

class CategoryVoice(BaseModel):
    tone: str = "peer_clinical"
    vocab_allowed: List[str] = Field(default_factory=list)
    vocab_taboo: List[str] = Field(default_factory=list)


class PeerStats(BaseModel):
    avg_rating: Optional[float] = 4.4
    avg_reviews: Optional[int] = 50
    avg_ctr: Optional[float] = 0.030
    scope: Optional[str] = None


class DigestItem(BaseModel):
    id: str
    kind: str  # research, compliance, cde, trend, peer_practice
    title: str
    source: str
    trial_n: Optional[int] = None
    patient_segment: Optional[str] = None
    summary: Optional[str] = ""
    deadline_iso: Optional[str] = None


class OfferTemplate(BaseModel):
    id: Optional[str] = None
    title: str
    value: Optional[Union[str, int]] = None
    audience: Optional[str] = "new_user"
    type: Optional[str] = "service_at_price"


class CategoryContext(BaseModel):
    slug: str  # dentists, salons, restaurants, gyms, pharmacies
    voice: CategoryVoice = Field(default_factory=CategoryVoice)
    offer_catalog: List[OfferTemplate] = Field(default_factory=list)
    peer_stats: PeerStats = Field(default_factory=PeerStats)
    digest: List[DigestItem] = Field(default_factory=list)
    patient_content_library: List[Dict[str, Any]] = Field(default_factory=list)
    seasonal_beats: List[Dict[str, Any]] = Field(default_factory=list)
    trend_signals: List[Dict[str, Any]] = Field(default_factory=list)


class Identity(BaseModel):
    name: str
    city: str
    locality: str
    place_id: Optional[str] = None
    verified: bool = False
    languages: List[str] = Field(default_factory=lambda: ["en", "hi"])
    owner_first_name: Optional[str] = None
    established_year: Optional[int] = None


class PerformanceDelta(BaseModel):
    views_pct: Optional[float] = 0.0
    calls_pct: Optional[float] = 0.0
    ctr_pct: Optional[float] = 0.0


class PerformanceSnapshot(BaseModel):
    window_days: int = 30
    views: int = 0
    calls: int = 0
    directions: int = 0
    ctr: float = 0.025
    leads: Optional[int] = 0
    delta_7d: Optional[Union[PerformanceDelta, Dict[str, float]]] = None


class MerchantOffer(BaseModel):
    id: Optional[str] = None
    title: str
    status: str = "active"
    started: Optional[str] = None
    ended: Optional[str] = None


class CustomerAggregate(BaseModel):
    total_unique_ytd: int = 0
    lapsed_180d_plus: Optional[int] = 0
    lapsed_90d_plus: Optional[int] = 0
    retention_6mo_pct: Optional[float] = 0.35
    retention_3mo_pct: Optional[float] = 0.50
    high_risk_adult_count: Optional[int] = 0


class MerchantContext(BaseModel):
    merchant_id: str
    category_slug: str
    identity: Identity
    subscription: Dict[str, Any] = Field(default_factory=dict)
    performance: PerformanceSnapshot = Field(default_factory=PerformanceSnapshot)
    offers: List[MerchantOffer] = Field(default_factory=list)
    conversation_history: List[Dict[str, Any]] = Field(default_factory=list)
    customer_aggregate: CustomerAggregate = Field(default_factory=CustomerAggregate)
    signals: List[str] = Field(default_factory=list)
    review_themes: List[Dict[str, Any]] = Field(default_factory=list)


class CustomerIdentity(BaseModel):
    name: str
    phone_redacted: Optional[str] = None
    language_pref: str = "hi-en mix"


class Relationship(BaseModel):
    first_visit: Optional[str] = None
    last_visit: Optional[str] = None
    visits_total: int = 1
    services_received: List[str] = Field(default_factory=list)


class CustomerContext(BaseModel):
    customer_id: str
    merchant_id: str
    identity: CustomerIdentity
    relationship: Relationship = Field(default_factory=Relationship)
    state: str = "active"  # new, active, lapsed_soft, lapsed_hard, churned
    preferences: Dict[str, Any] = Field(default_factory=dict)
    consent: Dict[str, Any] = Field(default_factory=dict)


class TriggerContext(BaseModel):
    id: str
    scope: Literal["merchant", "customer"]
    kind: str
    source: Literal["external", "internal"]
    merchant_id: Optional[str] = None
    customer_id: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)
    urgency: int = 2
    suppression_key: str
    expires_at: Optional[str] = None


# =============================================================================
# API REQUEST & RESPONSE MODELS
# =============================================================================

class ContextPushRequest(BaseModel):
    scope: Literal["category", "merchant", "customer", "trigger"]
    context_id: str
    version: int
    payload: Dict[str, Any]
    delivered_at: Optional[str] = None


class ContextPushResponse(BaseModel):
    accepted: bool
    ack_id: Optional[str] = None
    stored_at: Optional[str] = None
    reason: Optional[str] = None
    current_version: Optional[int] = None
    details: Optional[str] = None


class TickRequest(BaseModel):
    now: str
    available_triggers: List[str] = Field(default_factory=list)


class ComposedAction(BaseModel):
    conversation_id: str
    merchant_id: str
    customer_id: Optional[str] = None
    send_as: Literal["vera", "merchant_on_behalf"] = "vera"
    trigger_id: str
    template_name: str
    template_params: List[str] = Field(default_factory=list)
    body: str
    cta: str
    suppression_key: str
    rationale: str


class TickResponse(BaseModel):
    actions: List[ComposedAction] = Field(default_factory=list)


class ReplyRequest(BaseModel):
    conversation_id: str
    merchant_id: str
    customer_id: Optional[str] = None
    from_role: Literal["merchant", "customer"] = "merchant"
    message: str
    received_at: Optional[str] = None
    turn_number: int = 2


class ReplyResponse(BaseModel):
    action: Literal["send", "wait", "end"]
    body: Optional[str] = None
    cta: Optional[str] = None
    wait_seconds: Optional[int] = None
    rationale: str


class HealthzResponse(BaseModel):
    status: str = "ok"
    uptime_seconds: int
    contexts_loaded: Dict[str, int]
    active_model: Optional[str] = "gemini-3.8-flash"


class MetadataResponse(BaseModel):
    team_name: str
    team_members: List[str]
    model: str
    approach: str
    contact_email: str
    version: str
    submitted_at: str
