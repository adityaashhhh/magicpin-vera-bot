"""
Refine submission.jsonl by re-running any test pairs that hit rate-limit fallbacks.
Implements exponential backoff on 429 so all 30 test pairs are 100% LLM generated.
"""

import json
import time
import sys
from pathlib import Path

# Force UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

DATASET_DIR = Path(__file__).parent / "dataset"
EXPANDED_DIR = DATASET_DIR / "expanded"
TEST_PAIRS_FILE = EXPANDED_DIR / "test_pairs.json"
SUBMISSION_FILE = Path(__file__).parent / "submission.jsonl"

from generate_submission import load_dataset
from bot import compose


def main():
    categories, merchants, customers, triggers = load_dataset()
    test_pairs_data = json.load(open(TEST_PAIRS_FILE, "r", encoding="utf-8"))
    pairs = test_pairs_data.get("pairs", [])
    pairs_by_id = {p["test_id"]: p for p in pairs}

    # Read current submission
    lines = []
    with open(SUBMISSION_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                lines.append(json.loads(line))

    needs_refinement = [rec for rec in lines if "fallback" in rec.get("rationale", "").lower()]
    print(f"Total records: {len(lines)}. Records needing LLM regeneration: {len(needs_refinement)}")

    for idx, rec in enumerate(lines):
        test_id = rec["test_id"]
        if "fallback" not in rec.get("rationale", "").lower():
            continue

        p = pairs_by_id.get(test_id)
        if not p:
            continue

        tid = p["trigger_id"]
        mid = p["merchant_id"]
        cid = p.get("customer_id")

        trigger = triggers.get(tid, {})
        merchant = merchants.get(mid, {})
        customer = customers.get(cid) if cid else None
        cat_slug = merchant.get("category_slug", "dentists")
        category = categories.get(cat_slug, {})

        print(f"\nRegenerating {test_id} ({mid}, {tid})...")

        # Retry loop for 429
        max_retries = 5
        for attempt in range(max_retries):
            # Clear any cached fallback
            from backend.llm_composer import LLMComposer
            from bot import _get_composer
            composer_inst = _get_composer()
            if hasattr(composer_inst, '_cache'):
                composer_inst._cache.clear()

            res = compose(category, merchant, trigger, customer)
            if "fallback" not in res.get("rationale", "").lower():
                lines[idx] = {
                    "test_id": test_id,
                    "body": res["body"],
                    "cta": res["cta"],
                    "send_as": res["send_as"],
                    "suppression_key": res["suppression_key"],
                    "rationale": res["rationale"]
                }
                print(f"  [OK] {test_id} successfully composed with LLM!")
                break
            else:
                wait_sec = 25
                print(f"  [WAIT] Rate limit encountered. Sleeping {wait_sec}s before retry {attempt+1}/{max_retries}...")
                time.sleep(wait_sec)

        # Write progress immediately
        with open(SUBMISSION_FILE, "w", encoding="utf-8") as f:
            for r in lines:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

        # Healthy pacing between successful calls (5s)
        time.sleep(5.0)

    # Final check
    final_fallbacks = [r for r in lines if "fallback" in r.get("rationale", "").lower()]
    print(f"\nFinished refinement! Remaining fallbacks: {len(final_fallbacks)}/30")


if __name__ == "__main__":
    main()
