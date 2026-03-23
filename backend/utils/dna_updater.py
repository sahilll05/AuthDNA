"""
backend/utils/dna_updater.py
══════════════════════════════════════════════════════════════════
Phase 5 — DNA Profile Firebase Manager

WHAT THIS FILE DOES:
─────────────────────
This is the "bridge" between the DNA Engine and Firebase Firestore.

The DNAEngine does all the smart calculations (matching, scoring,
drift detection) but knows nothing about Firebase.

This DNAUpdater handles all the database work:
  • LOAD   — fetch a user's DNA profile from Firestore
  • SAVE   — write a new/updated profile to Firestore
  • BUILD  — build a profile from raw login history in Firestore
  • UPDATE — incrementally update after a safe login
  • BATCH  — rebuild all 500 user profiles at once

USAGE in FastAPI (backend/routers/evaluate.py):
──────────────────────────────────────────────
    from utils.dna_updater import DNAUpdater
    from engines.dna_engine import DNAEngine

    updater = DNAUpdater()
    engine  = DNAEngine()

    # Load stored profile
    stored = updater.load_profile(user_id)

    # Compare against current login
    result = engine.match(user_id, current_login, stored)

    # If login is safe → update DNA
    if result.drift_type != "fast":
        updater.update_after_safe_login(user_id, current_login)
══════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import os
import sys
import json
from datetime import datetime, timezone
from typing import Optional

# ── Graceful import of Firebase (won't crash if not configured) ────
try:
    from firebase_admin import firestore
    # Try to get the Firestore client
    try:
        _db = firestore.client()
        FIREBASE_AVAILABLE = True
    except Exception:
        _db = None
        FIREBASE_AVAILABLE = False
except ImportError:
    _db = None
    FIREBASE_AVAILABLE = False

# Add parent directory to path so we can import from engines/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engines.dna_engine import DNAEngine, DNAProfile, DNAConfig


# ══════════════════════════════════════════════════════════════════
# COLLECTION & FIELD CONSTANTS
# ══════════════════════════════════════════════════════════════════

DNA_COLLECTION   = "dna_profiles"     # Firestore collection name
LOGIN_COLLECTION = "login_logs"       # Where raw login history lives
HISTORY_LIMIT    = 90                 # Use last 90 logins to build profile


# ══════════════════════════════════════════════════════════════════
# DNA UPDATER
# ══════════════════════════════════════════════════════════════════

class DNAUpdater:
    """
    Manages reading and writing DNA profiles to Firestore.

    Works in two modes:
      1. Firebase mode  — reads/writes real Firestore (production)
      2. Local mode     — works with in-memory dicts (testing/dev)
    """

    def __init__(self, db=None, engine: DNAEngine = None):
        """
        Args:
            db:     Firestore client. If None, uses the global Firebase client.
            engine: DNAEngine instance. If None, creates a default one.
        """
        self.db     = db or _db
        self.engine = engine or DNAEngine()
        self._local_cache: dict[str, dict] = {}  # in-memory fallback

    # ──────────────────────────────────────────────────────────────
    # LOAD
    # ──────────────────────────────────────────────────────────────

    def load_profile(self, user_id: str) -> Optional[dict]:
        """
        Load a user's DNA profile from Firestore.

        Returns:
            Profile dict if found, or None if user has no profile yet.

        Example:
            profile = updater.load_profile("u_dev_001")
            if profile is None:
                print("New user — no DNA profile yet")
            else:
                print(f"Profile has {profile['login_count']} logins")
        """
        # ── Check in-memory cache first ────────────────────────
        if user_id in self._local_cache:
            return self._local_cache[user_id]

        # ── Try Firestore ──────────────────────────────────────
        if not self.db:
            return None

        try:
            doc_ref  = self.db.collection(DNA_COLLECTION).document(user_id)
            snapshot = doc_ref.get()
            if snapshot.exists:
                profile = snapshot.to_dict()
                self._local_cache[user_id] = profile   # cache it
                return profile
            return None
        except Exception as e:
            print(f"[DNAUpdater] Warning: could not load profile for {user_id}: {e}")
            return None

    # ──────────────────────────────────────────────────────────────
    # SAVE
    # ──────────────────────────────────────────────────────────────

    def save_profile(self, profile: dict) -> bool:
        """
        Save a DNA profile dict to Firestore.

        Args:
            profile: Dict with user_id and all DNA fields

        Returns:
            True if saved successfully, False on error.
        """
        user_id = profile.get("user_id")
        if not user_id:
            print("[DNAUpdater] Error: profile missing user_id")
            return False

        # Always update local cache
        self._local_cache[user_id] = profile

        if not self.db:
            # Local-only mode (for testing without Firebase)
            return True

        try:
            self.db.collection(DNA_COLLECTION).document(user_id).set(
                profile, merge=True
            )
            return True
        except Exception as e:
            print(f"[DNAUpdater] Error saving profile for {user_id}: {e}")
            return False

    # ──────────────────────────────────────────────────────────────
    # BUILD FROM HISTORY
    # ──────────────────────────────────────────────────────────────

    def build_profile_from_history(
        self,
        user_id: str,
        login_history: list[dict],
    ) -> dict:
        """
        Build a DNA profile from scratch using login history.
        Saves it to Firestore and returns the profile dict.

        Call this:
          - When a new user first accumulates 10+ logins
          - As a monthly refresh to rebuild all profiles

        Args:
            user_id:       The user's ID
            login_history: List of login event dicts

        Returns:
            The built profile dict (also saved to Firestore)
        """
        profile_obj  = self.engine.build_profile(user_id, login_history)
        profile_dict = self._profile_to_dict(profile_obj)
        self.save_profile(profile_dict)
        print(f"[DNAUpdater] Built profile for {user_id} from {len(login_history)} logins")
        return profile_dict

    def build_profile_from_firestore_history(self, user_id: str) -> Optional[dict]:
        """
        Build a DNA profile by fetching login history directly from Firestore.
        Useful for initial setup or monthly refresh.

        Args:
            user_id: The user's ID

        Returns:
            Built profile dict, or None if not enough history
        """
        if not self.db:
            print(f"[DNAUpdater] No Firestore connection — cannot fetch history for {user_id}")
            return None

        try:
            # Fetch the last HISTORY_LIMIT logins for this user
            query = (
                self.db.collection(LOGIN_COLLECTION)
                .where("user_id", "==", user_id)
                .where("is_attack", "==", 0)        # only use SAFE logins
                .order_by("timestamp", direction=firestore.Query.DESCENDING)
                .limit(HISTORY_LIMIT)
            )

            logins = []
            for doc in query.stream():
                d = doc.to_dict()
                logins.append({
                    "hour":              d.get("hour", 12),
                    "country":           d.get("country", ""),
                    "device":            d.get("device", ""),
                    "resource":          d.get("resource", ""),
                    "session_mins":      d.get("session_mins", 30),
                    "daily_login_count": d.get("daily_login_count", 1),
                    "timestamp":         d.get("timestamp"),
                })

            if len(logins) < DNAConfig.MIN_LOGINS_FOR_PROFILE:
                print(f"[DNAUpdater] Not enough history for {user_id}: only {len(logins)} safe logins")
                return None

            return self.build_profile_from_history(user_id, logins)

        except Exception as e:
            print(f"[DNAUpdater] Error building profile for {user_id}: {e}")
            return None

    # ──────────────────────────────────────────────────────────────
    # UPDATE AFTER SAFE LOGIN
    # ──────────────────────────────────────────────────────────────

    def update_after_safe_login(
        self,
        user_id:      str,
        login_data:   dict,
        drift_type:   str = "none",
    ) -> bool:
        """
        Update a user's DNA profile after a VERIFIED safe login.

        Call this ONLY after:
          - Decision was ALLOW (risk score < 30), OR
          - Decision was OTP and the user passed the OTP challenge

        NEVER call this after a BLOCK decision.

        Args:
            user_id:    The user's ID
            login_data: The login event dict
            drift_type: "none" (safe) or "slow" (gradual change, still update)

        Returns:
            True if update succeeded
        """
        if drift_type == "fast":
            # This should never happen — caller should not call this after
            # a fast drift. But just in case, guard against it.
            print(f"[DNAUpdater] WARNING: update_after_safe_login called with "
                  f"drift_type='fast' for {user_id}. Skipping update.")
            return False

        stored = self.load_profile(user_id)
        if stored is None:
            # First time — build a new minimal profile from this one login
            minimal = {
                "user_id":         user_id,
                "avg_login_hour":  float(login_data.get("hour", 12)),
                "std_login_hour":  3.0,
                "primary_country": login_data.get("country", ""),
                "known_countries": [login_data.get("country", "")] if login_data.get("country") else [],
                "primary_device":  login_data.get("device", ""),
                "known_devices":   [login_data.get("device", "")] if login_data.get("device") else [],
                "top_resources":   [login_data.get("resource", "")] if login_data.get("resource") else [],
                "typical_resource_sensitivity": 2.0,
                "avg_session_mins": float(login_data.get("session_mins", 30)),
                "avg_daily_logins": 1.0,
                "login_count":     1,
                "last_login_ts":   login_data.get("timestamp", datetime.now(timezone.utc).isoformat()),
                "last_updated":    datetime.now(timezone.utc).isoformat(),
                "typical_days":    list(range(5)),
                "profile_version": 1,
            }
            return self.save_profile(minimal)

        # ── Incremental update ─────────────────────────────────
        updated = self.engine.update_profile_incremental(
            stored_profile = stored,
            current_login  = login_data,
        )
        # Store the last match score for drift detection on next login
        updated["last_match_score"] = login_data.get("dna_match_score", 1.0)
        return self.save_profile(updated)

    # ──────────────────────────────────────────────────────────────
    # BATCH REBUILD (admin utility)
    # ──────────────────────────────────────────────────────────────

    def rebuild_all_profiles(self, user_ids: list[str] = None) -> dict:
        """
        Rebuild DNA profiles for all users (or a specific list).
        Run this as a scheduled job (e.g., nightly at 2am).

        Args:
            user_ids: List of user IDs to rebuild. If None, rebuilds all users
                      found in the login_logs collection.

        Returns:
            Summary dict: {built: N, skipped: N, errors: N}
        """
        if not self.db:
            return {"built": 0, "skipped": 0, "errors": 0,
                    "note": "No Firestore connection"}

        # If no user IDs provided, find all unique users in login_logs
        if user_ids is None:
            try:
                users_snap = self.db.collection("users").stream()
                user_ids   = [doc.id for doc in users_snap]
            except Exception as e:
                return {"built": 0, "skipped": 0, "errors": 1, "error": str(e)}

        built = skipped = errors = 0

        for uid in user_ids:
            try:
                result = self.build_profile_from_firestore_history(uid)
                if result:
                    built   += 1
                else:
                    skipped += 1
            except Exception as e:
                errors += 1
                print(f"[DNAUpdater] Error rebuilding {uid}: {e}")

        print(f"[DNAUpdater] Rebuild complete: {built} built, "
              f"{skipped} skipped (insufficient history), "
              f"{errors} errors")

        return {"built": built, "skipped": skipped, "errors": errors}

    # ──────────────────────────────────────────────────────────────
    # HELPERS
    # ──────────────────────────────────────────────────────────────

    def _profile_to_dict(self, profile: DNAProfile) -> dict:
        from dataclasses import asdict
        return asdict(profile)

    def get_cache_stats(self) -> dict:
        """Return how many profiles are in the local memory cache."""
        return {"cached_profiles": len(self._local_cache)}

    def clear_cache(self, user_id: str = None) -> None:
        """Clear local cache (all users or a specific user)."""
        if user_id:
            self._local_cache.pop(user_id, None)
        else:
            self._local_cache.clear()
