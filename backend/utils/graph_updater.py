"""
backend/utils/graph_updater.py
══════════════════════════════════════════════════════════════════
Phase 6 — Graph Firebase Manager

WHAT THIS FILE DOES:
─────────────────────
Syncs the privilege graph with Firestore so:
  1. User roles are loaded from the users collection
  2. Resource access history is tracked per user per session
  3. Role/resource changes in Firestore update the graph automatically

This is the bridge between GraphEngine and Firebase — exactly like
how DNAUpdater bridges DNAEngine and Firebase.

USAGE in FastAPI (Phase 10):
────────────────────────────
    from utils.graph_updater import GraphUpdater
    from engines.graph_engine import GraphEngine

    graph_engine  = GraphEngine()
    graph_updater = GraphUpdater()

    # Get user's role from Firestore
    role, clearance = graph_updater.get_user_role(user_id)

    # Get what the user accessed this session
    session_history = graph_updater.get_session_history(user_id, session_id)

    # Evaluate
    result = graph_engine.evaluate(
        user_id, role, resource, clearance, session_history
    )

    # Log this access
    graph_updater.log_resource_access(user_id, session_id, resource)
══════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from typing import Optional

# Graceful Firebase import
try:
    from firebase_admin import firestore
    try:
        _db = firestore.client()
        FIREBASE_AVAILABLE = True
    except Exception:
        _db = None
        FIREBASE_AVAILABLE = False
except ImportError:
    _db = None
    FIREBASE_AVAILABLE = False

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engines.graph_engine import GraphEngine, ROLE_CLEARANCE, RESOURCE_SENSITIVITY


class GraphUpdater:
    """
    Manages Firestore reads/writes for the privilege graph.
    Works in both Firebase mode (production) and local mode (testing).
    """

    def __init__(self, db=None, engine: GraphEngine = None):
        self.db      = db or _db
        self.engine  = engine or GraphEngine()
        # In-memory caches so we don't hit Firestore on every request
        self._role_cache:    dict[str, tuple[str, int]] = {}   # user_id → (role, clearance)
        self._session_cache: dict[str, list[str]]       = {}   # session_id → [resources]

    # ──────────────────────────────────────────────────────────────
    # USER ROLE LOOKUP
    # ──────────────────────────────────────────────────────────────

    def get_user_role(self, user_id: str) -> tuple[str, int]:
        """
        Get a user's role and clearance level from Firestore.

        Returns:
            (role_name, clearance_level)  e.g. ("developer", 3)
            Falls back to ("viewer", 1) if user not found.

        Example:
            role, clearance = updater.get_user_role("u_dev_001")
            # → ("developer", 3)
        """
        # Check cache first
        if user_id in self._role_cache:
            return self._role_cache[user_id]

        if not self.db:
            return ("viewer", 1)

        try:
            doc  = self.db.collection("users").document(user_id).get()
            if doc.exists:
                data      = doc.to_dict()
                role      = data.get("role", "viewer")
                clearance = int(data.get("clearance_level",
                                         ROLE_CLEARANCE.get(role, 1)))
                self._role_cache[user_id] = (role, clearance)
                return (role, clearance)
        except Exception as e:
            print(f"[GraphUpdater] Warning: could not get role for {user_id}: {e}")

        return ("viewer", 1)

    # ──────────────────────────────────────────────────────────────
    # SESSION RESOURCE HISTORY
    # ──────────────────────────────────────────────────────────────

    def get_session_history(self, user_id: str, session_id: str) -> list[str]:
        """
        Get the list of resources already accessed in this session.
        Used for lateral movement detection.

        Returns:
            List of resource names accessed so far, e.g. ["dashboard", "reports"]
        """
        cache_key = f"{session_id}:{user_id}"
        if cache_key in self._session_cache:
            return list(self._session_cache[cache_key])

        if not self.db:
            return []

        try:
            doc = self.db.collection("sessions").document(session_id).get()
            if doc.exists:
                data    = doc.to_dict()
                history = data.get("resources_accessed", [])
                self._session_cache[cache_key] = history
                return list(history)
        except Exception as e:
            print(f"[GraphUpdater] Warning: could not get session {session_id}: {e}")

        return []

    def log_resource_access(
        self,
        user_id:    str,
        session_id: str,
        resource:   str,
    ) -> bool:
        """
        Log that a user accessed a resource during this session.
        Called AFTER a successful (ALLOW) login decision.

        This builds up the session resource history used for
        lateral movement detection on subsequent requests.
        """
        cache_key = f"{session_id}:{user_id}"

        # Update local cache
        if cache_key not in self._session_cache:
            self._session_cache[cache_key] = []
        if resource not in self._session_cache[cache_key]:
            self._session_cache[cache_key].append(resource)

        if not self.db:
            return True

        try:
            self.db.collection("sessions").document(session_id).set(
                {
                    "user_id":            user_id,
                    "resources_accessed": self._session_cache[cache_key],
                    "last_resource":      resource,
                    "last_access_ts":     datetime.now(timezone.utc).isoformat(),
                },
                merge=True,
            )
            return True
        except Exception as e:
            print(f"[GraphUpdater] Error logging access for {session_id}: {e}")
            return False

    # ──────────────────────────────────────────────────────────────
    # FULL EVALUATE SHORTCUT
    # ──────────────────────────────────────────────────────────────

    def evaluate_access(
        self,
        user_id:    str,
        session_id: str,
        resource:   str,
    ):
        """
        One-call helper that:
          1. Loads the user's role from Firestore
          2. Loads session resource history
          3. Runs the graph evaluation
          4. Returns the GraphRiskResult

        This is the single method called from FastAPI in Phase 10.

        Example:
            result = graph_updater.evaluate_access(
                user_id    = "u_dev_001",
                session_id = "sess_abc123",
                resource   = "financial_data",
            )
            print(result.risk_score)      # → 15.0
            print(result.permission_ok)   # → False
            print(result.explanation)     # → "developer role has no permission..."
        """
        role, clearance  = self.get_user_role(user_id)
        session_history  = self.get_session_history(user_id, session_id)

        result = self.engine.evaluate(
            user_id          = user_id,
            role             = role,
            resource         = resource,
            clearance_level  = clearance,
            resource_history = session_history,
        )

        return result

    # ──────────────────────────────────────────────────────────────
    # CACHE MANAGEMENT
    # ──────────────────────────────────────────────────────────────

    def clear_session_cache(self, session_id: str = None) -> None:
        """Clear session cache when session ends."""
        if session_id:
            keys = [k for k in self._session_cache if k.startswith(session_id)]
            for k in keys:
                del self._session_cache[k]
        else:
            self._session_cache.clear()

    def clear_role_cache(self, user_id: str = None) -> None:
        """Clear role cache (e.g. after a user's role changes)."""
        if user_id:
            self._role_cache.pop(user_id, None)
        else:
            self._role_cache.clear()

    def get_cache_stats(self) -> dict:
        return {
            "cached_roles":    len(self._role_cache),
            "cached_sessions": len(self._session_cache),
        }
