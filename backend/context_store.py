"""
magicpin AI Challenge — Stateful Context Store
Handles atomic versioning, idempotency, and retrieval for the 4-context framework.
"""

import threading
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, List
from pathlib import Path
import json


class ContextStore:
    def __init__(self, dataset_dir: Optional[Path] = None):
        self._lock = threading.RLock()
        self.categories: Dict[str, Dict[str, Any]] = {}
        self.merchants: Dict[str, Dict[str, Any]] = {}
        self.customers: Dict[str, Dict[str, Any]] = {}
        self.triggers: Dict[str, Dict[str, Any]] = {}

        # Versions tracking: { (scope, context_id): version_int }
        self._versions: Dict[Tuple[str, str], int] = {}
        # Suppression registry: { suppression_key: timestamp_or_status }
        self._suppressed_keys: Dict[str, datetime] = {}

        if dataset_dir:
            self.preload_from_disk(dataset_dir)

    def preload_from_disk(self, dataset_dir: Path):
        """Preload baseline dataset if available on disk."""
        with self._lock:
            # 1. Categories
            cat_dir = dataset_dir / "categories"
            if cat_dir.exists():
                for f in cat_dir.glob("*.json"):
                    try:
                        data = json.load(open(f, "r", encoding="utf-8"))
                        slug = data.get("slug", f.stem)
                        self.categories[slug] = data
                        self._versions[("category", slug)] = 1
                    except Exception as e:
                        print(f"Error loading category {f}: {e}")

            # 2. Merchants, Customers, Triggers from expanded or seeds
            for filename, container, id_key, scope in [
                ("merchants_seed.json", self.merchants, "merchant_id", "merchant"),
                ("customers_seed.json", self.customers, "customer_id", "customer"),
                ("triggers_seed.json", self.triggers, "id", "trigger"),
            ]:
                seed_file = dataset_dir / filename
                if seed_file.exists():
                    try:
                        data = json.load(open(seed_file, "r", encoding="utf-8"))
                        items = data.get(container_name := filename.split('_')[0], [])
                        for item in items:
                            if id_key in item:
                                cid = item[id_key]
                                container[cid] = item
                                self._versions[(scope, cid)] = 1
                    except Exception as e:
                        print(f"Error loading seed {seed_file}: {e}")

            # Also check expanded folder if available
            exp_dir = dataset_dir / "expanded"
            if exp_dir.exists():
                for sub, container, id_key, scope in [
                    ("merchants", self.merchants, "merchant_id", "merchant"),
                    ("customers", self.customers, "customer_id", "customer"),
                    ("triggers", self.triggers, "id", "trigger"),
                ]:
                    target_dir = exp_dir / sub
                    if target_dir.exists():
                        for f in target_dir.glob("*.json"):
                            try:
                                item = json.load(open(f, "r", encoding="utf-8"))
                                if id_key in item:
                                    cid = item[id_key]
                                    container[cid] = item
                                    self._versions[(scope, cid)] = 1
                            except Exception:
                                pass

    def push(self, scope: str, context_id: str, version: int, payload: Dict[str, Any]) -> Tuple[bool, Optional[str], Optional[int]]:
        """
        Pushes a new or updated context item atomically.
        Returns (accepted: bool, error_reason: Optional[str], current_version: Optional[int]).
        """
        with self._lock:
            key = (scope, context_id)
            current_ver = self._versions.get(key)

            if current_ver is not None:
                if version < current_ver:
                    # Stale version / conflict
                    return False, "stale_version", current_ver
                elif version == current_ver:
                    # Idempotent replay: accept with current version
                    return True, None, current_ver

            # Accept & replace atomically
            if scope == "category":
                self.categories[context_id] = payload
            elif scope == "merchant":
                self.merchants[context_id] = payload
            elif scope == "customer":
                self.customers[context_id] = payload
            elif scope == "trigger":
                self.triggers[context_id] = payload
            else:
                return False, "invalid_scope", None

            self._versions[key] = version
            return True, None, version

    def get_counts(self) -> Dict[str, int]:
        with self._lock:
            return {
                "category": len(self.categories),
                "merchant": len(self.merchants),
                "customer": len(self.customers),
                "trigger": len(self.triggers)
            }

    def get_category(self, slug: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self.categories.get(slug)

    def get_merchant(self, merchant_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self.merchants.get(merchant_id)

    def get_customer(self, customer_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self.customers.get(customer_id)

    def get_trigger(self, trigger_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self.triggers.get(trigger_id)

    def is_suppressed(self, suppression_key: str) -> bool:
        with self._lock:
            return suppression_key in self._suppressed_keys

    def mark_suppressed(self, suppression_key: str):
        with self._lock:
            self._suppressed_keys[suppression_key] = datetime.utcnow()

    def wipe(self):
        """Wipes state as required by POST /v1/teardown at end of evaluation."""
        with self._lock:
            self.categories.clear()
            self.merchants.clear()
            self.customers.clear()
            self.triggers.clear()
            self._versions.clear()
            self._suppressed_keys.clear()
