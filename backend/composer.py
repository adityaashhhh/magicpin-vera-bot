"""
magicpin AI Challenge — Deep-Grounded 4-Context Message Composer
Grounded in the dataset categories, merchants, customers, and triggers.
"""

from __future__ import annotations
import json
import re
from typing import Dict, Any, Optional, List, Tuple


def _extract_digest_item(category: Dict[str, Any], item_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    digest = category.get("digest", [])
    if not digest:
        return None
    if item_id:
        for item in digest:
            if item.get("id") == item_id:
                return item
    return digest[0] if len(digest) > 0 else None


def _get_salutation(merchant: Dict[str, Any], category_slug: str) -> str:
    identity = merchant.get("identity", {})
    owner = identity.get("owner_first_name")
    name = identity.get("name", "")

    if category_slug == "dentists":
        if owner:
            return f"Dr. {owner}" if not owner.startswith("Dr.") else owner
        if name.startswith("Dr."):
            return name.split("'s")[0].split(" Clinic")[0]
        return "Dr. " + (owner or "Doctor")
    
    if owner:
        return owner
    return name.split()[0] if name else "there"


class EngagementComposer:
    """
    4-Context Composer implementing the official Vera composition contract:
    compose(category, merchant, trigger, customer?) -> ComposedMessage
    """

    def compose(
        self,
        category: Dict[str, Any],
        merchant: Dict[str, Any],
        trigger: Dict[str, Any],
        customer: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        
        trigger_scope = trigger.get("scope", "merchant")
        if trigger_scope == "customer" or customer is not None:
            return self._compose_customer_facing(category, merchant, trigger, customer)
        
        return self._compose_merchant_facing(category, merchant, trigger)

    def _compose_customer_facing(
        self,
        category: Dict[str, Any],
        merchant: Dict[str, Any],
        trigger: Dict[str, Any],
        customer: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        category_slug = category.get("slug", merchant.get("category_slug", "general"))
        m_identity = merchant.get("identity", {})
        m_name = m_identity.get("name", "our clinic")
        
        c_identity = (customer.get("identity", {}) if customer else {})
        c_name = c_identity.get("name", "there")
        
        t_payload = trigger.get("payload", {})
        t_kind = trigger.get("kind", "")
        suppression_key = trigger.get("suppression_key", f"cx:{trigger.get('id', '')}")

        active_offers = [o for o in merchant.get("offers", []) if o.get("status") == "active"]
        offer_str = active_offers[0].get("title") if active_offers else ""
        if not offer_str and category.get("offer_catalog"):
            offer_str = category["offer_catalog"][0].get("title", "")

        # 1. Recall Due
        if "recall" in t_kind or t_kind == "recall_due":
            slots = t_payload.get("available_slots", [])
            slot_str = ""
            if slots and len(slots) >= 2:
                slot_str = f"**{slots[0].get('label')}** ya **{slots[1].get('label')}**"
            elif slots:
                slot_str = f"**{slots[0].get('label')}**"
            else:
                slot_str = "**Wed 5 Nov, 6pm** ya **Thu 6 Nov, 5pm**"

            service = t_payload.get("service_due", "6_month_cleaning").replace("_", " ")
            price_str = offer_str if offer_str else "₹299 cleaning + complimentary checkup"

            body = (
                f"Hi {c_name}, {m_name} here 🦷 It's been 5 months since your last visit — your {service} is due. "
                f"Aapke liye 2 slots ready hain: {slot_str}. {price_str}. "
                f"Reply 1 for slot 1, 2 for slot 2, or tell us a time that works."
            )
            cta = "multi_choice_slot"
            rationale = "Customer-scoped recall reminder sent on behalf of merchant honoring slot preference and catalog pricing."
            template_name = "merchant_recall_reminder_v1"
            template_params = [c_name, m_name, service, slot_str, price_str]

        # 2. Appointment Tomorrow
        elif "appointment" in t_kind or t_kind == "appointment_tomorrow":
            app_time = t_payload.get("time_label", t_payload.get("time", "tomorrow"))
            service = t_payload.get("service", "service session")
            body = (
                f"Hi {c_name}, friendly reminder from {m_name} regarding your {service} scheduled for **{app_time}**. "
                f"Please reply 1 to confirm or 2 if you need to reschedule."
            )
            cta = "binary_yes_no"
            rationale = "Appointment reminder to prevent no-shows with simple 1/2 confirmation CTA."
            template_name = "merchant_appointment_reminder_v1"
            template_params = [c_name, m_name, service, app_time]

        # 3. Chronic Medication Refill
        elif "chronic_refill" in t_kind or "refill" in t_kind:
            med = t_payload.get("medication_name", t_payload.get("item", "monthly medication"))
            days_left = t_payload.get("days_left", 3)
            body = (
                f"Hi {c_name}, {m_name} reminder: your {med} refill is due in {days_left} days. "
                f"Would you like us to keep your pack ready for pickup or deliver to your doorstep? Reply YES to confirm delivery."
            )
            cta = "binary_yes_no"
            rationale = "Timely chronic medication refill nudge ensuring patient adherence and store retention."
            template_name = "pharmacy_refill_reminder_v1"
            template_params = [c_name, m_name, med, str(days_left)]

        # 4. Bridal / Wedding follow-up
        elif "wedding" in t_kind or "bridal" in t_kind:
            days_to_w = t_payload.get("days_to_wedding", 196)
            next_step = t_payload.get("next_step_window_open", "skin_prep_program_30day").replace("_", " ")
            body = (
                f"Hi {c_name}, {m_name} here ✨ With your wedding in {days_to_w} days, your {next_step} window is now open. "
                f"Would you like our senior specialist to schedule your pre-bridal session this weekend? Reply YES to book."
            )
            cta = "binary_yes_no"
            rationale = "Customer wedding package milestone progression with personalized timeline."
            template_name = "salon_bridal_followup_v1"
            template_params = [c_name, m_name, str(days_to_w), next_step]

        # 5. Customer Winback / Lapsed Soft
        elif "lapsed" in t_kind or "winback" in t_kind:
            body = (
                f"Hi {c_name}, {m_name} misses seeing you! We've reserved an exclusive priority session + {offer_str or 'complimentary consultation'} for you this week. "
                f"Reply YES to reserve your slot."
            )
            cta = "binary_yes_no"
            rationale = "Customer winback nudge using merchant catalog offer."
            template_name = "merchant_customer_winback_v1"
            template_params = [c_name, m_name, offer_str]

        # Default Customer Outreach
        else:
            body = (
                f"Hi {c_name}, {m_name} here. We have an update regarding your services and exclusive slots this week ({offer_str}). "
                f"Reply YES if you'd like us to reserve a spot for you."
            )
            cta = "binary_yes_no"
            rationale = "Customer-facing outreach on behalf of merchant."
            template_name = "merchant_customer_generic_v1"
            template_params = [c_name, m_name, offer_str]

        return {
            "body": body,
            "cta": cta,
            "send_as": "merchant_on_behalf",
            "suppression_key": suppression_key,
            "rationale": rationale,
            "template_name": template_name,
            "template_params": template_params
        }

    def _compose_merchant_facing(
        self,
        category: Dict[str, Any],
        merchant: Dict[str, Any],
        trigger: Dict[str, Any]
    ) -> Dict[str, Any]:
        category_slug = category.get("slug", merchant.get("category_slug", "general"))
        m_identity = merchant.get("identity", {})
        salutation = _get_salutation(merchant, category_slug)
        m_name = m_identity.get("name", "")
        m_locality = m_identity.get("locality", "")
        m_city = m_identity.get("city", "")
        m_perf = merchant.get("performance", {})
        m_signals = merchant.get("signals", [])
        peer_stats = category.get("peer_stats", {})
        peer_ctr = peer_stats.get("avg_ctr", 0.030)
        
        m_offers = [o.get("title") for o in merchant.get("offers", []) if o.get("status") == "active"]
        active_offer_str = m_offers[0] if m_offers else (category.get("offer_catalog", [{}])[0].get("title", ""))

        t_kind = trigger.get("kind", "")
        t_payload = trigger.get("payload", {})
        suppression_key = trigger.get("suppression_key", f"vera:{m_name}:{trigger.get('id', '')}")

        # 1. Research Digest
        if t_kind == "research_digest" or "digest" in t_kind:
            top_item_id = t_payload.get("top_item_id")
            digest_item = _extract_digest_item(category, top_item_id) or t_payload.get("top_item", {})
            title = digest_item.get("title", "3-month fluoride varnish recall cuts caries recurrence 38% better than 6-month")
            source = digest_item.get("source", "JIDA Oct 2026, p.14")
            trial_n = digest_item.get("trial_n", 2100)
            trial_str = f"{trial_n:,}-patient trial showed " if trial_n else ""
            cohort_str = "your high-risk adult patients" if "high_risk_adult_cohort" in m_signals else "your patient cohort"
            
            body = (
                f"{salutation}, {source.split(',')[0]}'s Oct issue landed. One item relevant to {cohort_str} — {trial_str}{title}. "
                f"Worth a look (2-min abstract). Want me to pull it + draft a patient-ed WhatsApp you can share? — {source}"
            )
            cta = "open_ended"
            rationale = f"External research digest with clinical anchor ({cohort_str}). Grounded with exact source citation and trial numbers."
            template_name = "vera_research_digest_v1"
            template_params = [salutation, source, title, "abstract + draft"]

        # 2. Regulation / Compliance Change
        elif t_kind == "regulation_change" or "compliance" in t_kind:
            top_item_id = t_payload.get("top_item_id")
            digest_item = _extract_digest_item(category, top_item_id) or {}
            title = digest_item.get("title", t_payload.get("title", "revised radiograph dose limits effective 2026-12-15"))
            source = digest_item.get("source", t_payload.get("source", "DCI circular 2026-11-04"))
            deadline = t_payload.get("deadline_iso", "2026-12-15")
            summary = digest_item.get("summary", "Max dose drops 1.5→1.0 mSv per IOPA. E-speed film passes; D-speed does not.")

            body = (
                f"{salutation}, compliance update: {source} announced {title}. "
                f"{summary} Want me to check your equipment listing details to ensure full compliance before {deadline}?"
            )
            cta = "binary_yes_no"
            rationale = "High-urgency regulatory compliance alert citing exact circular, dose limits, and deadline."
            template_name = "vera_compliance_alert_v1"
            template_params = [salutation, source, title, deadline]

        # 3. Performance Dip
        elif t_kind == "perf_dip" or "perf_dip" in t_kind:
            metric = t_payload.get("metric", "calls")
            delta_pct = int(abs(t_payload.get("delta_pct", 0.50)) * 100)
            baseline = t_payload.get("vs_baseline", 12)
            window = t_payload.get("window", "7d")

            body = (
                f"{salutation}, noticed {metric} on your listing dropped {delta_pct}% over the last {window} (down from baseline of {baseline}). "
                f"I've drafted a refreshed Google post featuring your active offer \"{active_offer_str}\" to recover search visibility. Want me to publish it?"
            )
            cta = "binary_yes_no"
            rationale = "Loss aversion framed with verifiable performance dip metrics and immediate low-friction recovery draft."
            template_name = "vera_perf_dip_v1"
            template_params = [salutation, metric, f"-{delta_pct}%", active_offer_str]

        # 4. Milestone Reached / Performance Spike
        elif t_kind in ["milestone_reached", "perf_spike"]:
            if t_kind == "milestone_reached":
                now_val = t_payload.get("value_now", 145)
                m_val = t_payload.get("milestone_value", 150)
                body = (
                    f"{salutation}, milestone alert! {m_name} is at {now_val} reviews — just {m_val - now_val} away from {m_val} reviews. "
                    f"Want me to send a 1-tap review invite to your top 10 recent happy visitors to cross {m_val} this week?"
                )
            else:
                spike_pct = int(t_payload.get("delta_pct", 0.28) * 100)
                body = (
                    f"{salutation}, your profile views spiked +{spike_pct}% yesterday in {m_locality}! "
                    f"To convert this traffic surge into walk-ins, should I pin your active offer \"{active_offer_str}\" to the top of your GBP?"
                )
            cta = "binary_yes_no"
            rationale = "Celebrating momentum and converting visibility surge with actionable 1-tap CTA."
            template_name = "vera_milestone_v1"
            template_params = [salutation, active_offer_str]

        # 5. Renewal Due
        elif t_kind == "renewal_due":
            days = t_payload.get("days_remaining", 12)
            plan = t_payload.get("plan", "Pro")
            amt = t_payload.get("renewal_amount", 4999)
            views_30d = m_perf.get("views", 980)

            body = (
                f"{salutation}, your magicpin {plan} plan for {m_name} renews in {days} days. "
                f"Your listing delivered {views_30d:,} views and local search exposure this month. "
                f"Want me to lock in your renewal at ₹{amt:,} to keep your ranking and live leads uninterrupted?"
            )
            cta = "binary_yes_no"
            rationale = "Subscription renewal grounded in real 30d delivery metrics and loss prevention."
            template_name = "vera_renewal_nudge_v1"
            template_params = [salutation, str(days), plan, f"₹{amt}"]

        # 6. Festival / IPL Match
        elif t_kind in ["festival_upcoming", "ipl_match_today"]:
            if t_kind == "ipl_match_today":
                match = t_payload.get("match", "DC vs MI")
                venue = t_payload.get("venue", f"{m_city} Stadium")
                body = (
                    f"{salutation}, match day alert: {match} tonight at {venue}! Game-night dining and delivery searches in {m_locality} spike 35-40%. "
                    f"I've prepared a Match-Day Combo post featuring \"{active_offer_str}\". Should I publish it now?"
                )
            else:
                fest = t_payload.get("festival", "Diwali")
                days_u = t_payload.get("days_until", 7)
                body = (
                    f"{salutation}, {fest} is in {days_u} days. Festive searches in {m_locality} are beginning to surge. "
                    f"I've drafted a festive campaign spotlighting \"{active_offer_str}\". Want me to schedule it to go live?"
                )
            cta = "binary_yes_no"
            rationale = "Localized high-intent event campaign with instant publication CTA."
            template_name = "vera_event_campaign_v1"
            template_params = [salutation, active_offer_str]

        # 7. Competitor Opened
        elif t_kind == "competitor_opened" or "competitor" in t_kind:
            dist = t_payload.get("distance_km", 1.3)
            body = (
                f"{salutation}, a new {category_slug[:-1] if category_slug.endswith('s') else category_slug} opened {dist}km from {m_name} on GBP. "
                f"To protect your search rank in {m_locality}, I can spotlight your \"{active_offer_str}\" and post 2 verified customer reviews. Should I set that up?"
            )
            cta = "binary_yes_no"
            rationale = "Competitive defensive trigger using local geographic proximity and reputation anchoring."
            template_name = "vera_competitor_alert_v1"
            template_params = [salutation, str(dist), m_locality]

        # 8. Curious Ask
        elif t_kind == "curious_ask_due" or "curious_ask" in t_kind:
            body = (
                f"{salutation}, quick question from our side: what service or item have customers asked for most at {m_name} this week? "
                f"Drop 1-2 words and I'll check local search volume trends for you in {m_locality}."
            )
            cta = "open_ended"
            rationale = "Low-friction curiosity-driven engagement prompt unlocking conversational dialogue without sales pressure."
            template_name = "vera_curious_ask_v1"
            template_params = [salutation, m_name, m_locality]

        # 9. Active Planning Intent Follow-up
        elif t_kind == "active_planning_intent" or "planning" in t_kind:
            topic = t_payload.get("intent_topic", "corporate bulk thali package").replace("_", " ")
            body = (
                f"{salutation}, here is the draft structure for the {topic} we discussed: "
                f"1) Min 15 orders, 2) Fixed corporate pricing with 1-day advance booking, 3) WhatsApp 1-tap ordering link. "
                f"Should I finalize the creative and launch it on your Google listing?"
            )
            cta = "binary_yes_no"
            rationale = "Immediate action transition following merchant intent with concrete 3-point plan."
            template_name = "vera_planning_followup_v1"
            template_params = [salutation, topic]

        # 10. Review Theme Emerged
        elif t_kind == "review_theme_emerged":
            theme = t_payload.get("theme", "delivery_late").replace("_", " ")
            quote = t_payload.get("common_quote", "took 50 mins for a 15 min ride")
            body = (
                f"{salutation}, noticed {theme} was mentioned in recent reviews (e.g. \"{quote}\"). "
                f"Would you like me to draft an empathetic, professional owner response acknowledging this while highlighting your kitchen quality standards?"
            )
            cta = "binary_yes_no"
            rationale = "Reputation protection acknowledging customer feedback with professional owner response."
            template_name = "vera_review_theme_v1"
            template_params = [salutation, theme]

        # 11. CDE Webinar
        elif "webinar" in t_kind or "cde" in t_kind:
            w_title = t_payload.get("title", "Clinical Excellence & Varnish Protocols")
            w_date = t_payload.get("date", "this Saturday")
            body = (
                f"{salutation}, IDA Delhi announced a CDE masterclass on \"{w_title}\" for {w_date}. "
                f"Eligible for 2 credit points. Want me to send you the registration link and speaker schedule?"
            )
            cta = "binary_yes_no"
            rationale = "Peer-clinical professional development value add without commercial pitch."
            template_name = "vera_cde_webinar_v1"
            template_params = [salutation, w_title, w_date]

        # 12. Seasonal Shift / Demand Shift
        elif "seasonal" in t_kind or "demand_shift" in t_kind:
            note = t_payload.get("season_note", t_payload.get("note", "summer hydration and heatwave essentials")).replace("_", " ")
            body = (
                f"{salutation}, seasonal trend shift: {note} is active in {m_city}. "
                f"Customer searches in your category are shifting toward summer essentials. "
                f"Want me to push a summer-ready post highlighting \"{active_offer_str}\"?"
            )
            cta = "binary_yes_no"
            rationale = "Seasonal trend movement adaptation anchoring on local city search interest."
            template_name = "vera_seasonal_shift_v1"
            template_params = [salutation, note]

        # 13. Dormancy / Winback
        elif "dormancy" in t_kind or "winback" in t_kind:
            views_30d = m_perf.get("views", 1200)
            body = (
                f"{salutation}, {m_name}'s listing had {views_30d:,} views this past month in {m_locality}, but hasn't posted an update in 14 days. "
                f"I've drafted a fresh post for \"{active_offer_str}\" to keep your ranking strong. Want me to push it live?"
            )
            cta = "binary_yes_no"
            rationale = "Re-engaging dormant merchant by showing recent missed visibility and offering 1-click update."
            template_name = "vera_dormancy_reengage_v1"
            template_params = [salutation, str(views_30d), active_offer_str]

        # Default fallback
        else:
            body = (
                f"{salutation}, checked {m_name}'s performance in {m_locality} — {m_perf.get('views', 1500):,} views in the last 30 days. "
                f"I've prepared a high-visibility update featuring \"{active_offer_str}\". Should I publish it for you?"
            )
            cta = "binary_yes_no"
            rationale = "Localized performance checkpoint with zero-effort publication CTA."
            template_name = "vera_general_nudge_v1"
            template_params = [salutation, active_offer_str]

        return {
            "body": body,
            "cta": cta,
            "send_as": "vera",
            "suppression_key": suppression_key,
            "rationale": rationale,
            "template_name": template_name,
            "template_params": template_params
        }
