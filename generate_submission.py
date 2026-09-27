"""
magicpin AI Challenge — Generate submission.jsonl
Evaluates the 30 canonical test pairs and produces submission.jsonl.
"""

import json
from pathlib import Path
from bot import compose

DATASET_DIR = Path(__file__).parent / "dataset"
EXPANDED_DIR = DATASET_DIR / "expanded"
TEST_PAIRS_FILE = EXPANDED_DIR / "test_pairs.json"
SUBMISSION_FILE = Path(__file__).parent / "submission.jsonl"


def load_dataset():
    categories = {}
    merchants = {}
    customers = {}
    triggers = {}

    # Load categories
    for cat_file in (DATASET_DIR / "categories").glob("*.json"):
        data = json.load(open(cat_file, "r", encoding="utf-8"))
        categories[data.get("slug", cat_file.stem)] = data

    # Load merchants
    if (EXPANDED_DIR / "merchants").exists():
        for f in (EXPANDED_DIR / "merchants").glob("*.json"):
            m = json.load(open(f, "r", encoding="utf-8"))
            merchants[m["merchant_id"]] = m
    else:
        seed = json.load(open(DATASET_DIR / "merchants_seed.json", "r", encoding="utf-8"))
        for m in seed.get("merchants", []):
            merchants[m["merchant_id"]] = m

    # Load customers
    if (EXPANDED_DIR / "customers").exists():
        for f in (EXPANDED_DIR / "customers").glob("*.json"):
            c = json.load(open(f, "r", encoding="utf-8"))
            customers[c["customer_id"]] = c
    else:
        seed = json.load(open(DATASET_DIR / "customers_seed.json", "r", encoding="utf-8"))
        for c in seed.get("customers", []):
            customers[c["customer_id"]] = c

    # Load triggers
    if (EXPANDED_DIR / "triggers").exists():
        for f in (EXPANDED_DIR / "triggers").glob("*.json"):
            t = json.load(open(f, "r", encoding="utf-8"))
            triggers[t["id"]] = t
    else:
        seed = json.load(open(DATASET_DIR / "triggers_seed.json", "r", encoding="utf-8"))
        for t in seed.get("triggers", []):
            triggers[t["id"]] = t

    return categories, merchants, customers, triggers


def main():
    import time
    import sys
    sys.stdout.reconfigure(encoding='utf-8')

    categories, merchants, customers, triggers = load_dataset()

    test_pairs_data = json.load(open(TEST_PAIRS_FILE, "r", encoding="utf-8"))
    pairs = test_pairs_data.get("pairs", [])

    print(f"Generating submission for {len(pairs)} test pairs with Gemini 3.8 Flash...")
    
    with open(SUBMISSION_FILE, "w", encoding="utf-8") as f:
        for idx, p in enumerate(pairs, 1):
            test_id = p["test_id"]
            tid = p["trigger_id"]
            mid = p["merchant_id"]
            cid = p.get("customer_id")

            trigger = triggers.get(tid, {})
            merchant = merchants.get(mid, {})
            customer = customers.get(cid) if cid else None
            cat_slug = merchant.get("category_slug", "dentists")
            category = categories.get(cat_slug, {})

            print(f"[{idx}/{len(pairs)}] Generating {test_id} (merchant: {mid}, trigger: {tid})...")
            result = compose(category, merchant, trigger, customer)

            record = {
                "test_id": test_id,
                "body": result["body"],
                "cta": result["cta"],
                "send_as": result["send_as"],
                "suppression_key": result["suppression_key"],
                "rationale": result["rationale"]
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            f.flush()

            # Pacing for free-tier rate limits (15 RPM)
            if idx < len(pairs):
                time.sleep(3.0)

    print(f"\n[DONE] Successfully generated {len(pairs)} test pairs in: {SUBMISSION_FILE}")


if __name__ == "__main__":
    main()
