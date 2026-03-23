"""
backend/engines/graph_engine.py
══════════════════════════════════════════════════════════════════
Phase 6 — Privilege Graph Engine

WHAT THIS FILE DOES (beginner-friendly):
─────────────────────────────────────────
Imagine a company has:
  - Users  (Bob, Alice, Charlie)
  - Roles  (developer, hr, admin, viewer, analyst, manager)
  - Resources  (dashboard, reports, hr_portal, financial_data, admin_panel)

Each resource has a SENSITIVITY level (1=public → 5=top secret).
Each role has a CLEARANCE level (1=lowest → 5=highest).

The Privilege Graph answers 3 security questions per login:

  1. PERMISSION CHECK — Is this user allowed to access this resource
     at all based on their role?
     → "Bob is a developer (clearance=3). admin_panel needs clearance 5.
        Bob should NOT be accessing admin_panel."

  2. PRIVILEGE GAP — How large is the gap between what the user
     normally accesses vs what they are trying to access now?
     → "Bob always accesses 'reports' (sensitivity=2).
        Today he's trying to access 'financial_data' (sensitivity=4).
        Gap = 2. Suspicious."

  3. LATERAL MOVEMENT — Is the user jumping between resources they
     have never combined before? Attackers often escalate privileges
     gradually, accessing more and more sensitive resources.
     → "Bob has never accessed hr_portal before. Now he's trying to
        access financial_data immediately after. Lateral movement detected."

OUTPUT:
  GraphRiskResult containing:
    risk_score       : 0–25  (fed into the final risk formula as 10%)
    permission_ok    : bool  (is this user even allowed here?)
    privilege_gap    : int   (sensitivity - clearance, clipped to 0)
    is_lateral_move  : bool  (jumping to new resource after another new one)
    explanation      : human-readable reason
══════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional
import networkx as nx


# ══════════════════════════════════════════════════════════════════
# CONSTANTS — resource and role definitions
# These match exactly what is in your Firestore privilege_graph
# collection (seeded by firebase_schema_init.py in Phase 1)
# ══════════════════════════════════════════════════════════════════

# Sensitivity level of each resource (1=public, 5=top secret)
RESOURCE_SENSITIVITY: dict[str, int] = {
    "dashboard":      1,
    "reports":        2,
    "hr_portal":      3,
    "user_management":3,
    "audit_logs":     3,
    "financial_data": 4,
    "api_keys":       4,
    "ml_models":      4,
    "admin_panel":    5,
    "database_backup":5,
}

# Clearance level of each role (1=lowest, 5=highest)
ROLE_CLEARANCE: dict[str, int] = {
    "viewer":    1,
    "analyst":   2,
    "developer": 3,
    "hr":        3,
    "manager":   4,
    "admin":     5,
}

# Which resources each role is explicitly allowed to access
ROLE_PERMISSIONS: dict[str, list[str]] = {
    "viewer":    ["dashboard"],
    "analyst":   ["dashboard", "reports"],
    "developer": ["dashboard", "reports", "api_keys", "ml_models"],
    "hr":        ["dashboard", "reports", "hr_portal", "user_management"],
    "manager":   ["dashboard", "reports", "hr_portal", "financial_data",
                  "user_management", "audit_logs", "api_keys", "ml_models"],
    "admin":     ["dashboard", "reports", "hr_portal", "financial_data",
                  "admin_panel", "api_keys", "user_management", "audit_logs",
                  "ml_models", "database_backup"],
}

# Risk points added for each violation type
RISK_POINTS = {
    "no_permission":      20,   # accessing something completely off-limits
    "privilege_gap_per":   5,   # per sensitivity level above clearance
    "lateral_movement":   10,   # jumping to a new resource type
    "new_resource":        5,   # accessing a resource never used before
    "sensitivity_jump":    8,   # jumping 2+ sensitivity levels in one session
}

MAX_GRAPH_RISK = 25   # graph contributes max 25 points (10% weight in final score)


# ══════════════════════════════════════════════════════════════════
# DATA CLASSES
# ══════════════════════════════════════════════════════════════════

@dataclass
class GraphRiskResult:
    """
    Returned by GraphEngine.evaluate() for every login.
    The risk_score (0–25) feeds into the Phase 7 risk formula.
    """
    user_id:          str
    resource:         str
    role:             str

    risk_score:       float   # 0–25, fed into risk engine (10% weight)
    permission_ok:    bool    # is user allowed to access this resource?
    privilege_gap:    int     # sensitivity - clearance (0 if within rights)
    is_lateral_move:  bool    # jumping across resource categories
    is_new_resource:  bool    # user never accessed this resource before
    sensitivity_jump: int     # how many sensitivity levels jumped in session
    explanation:      str     # human-readable reason for the score

    def to_dict(self) -> dict:
        return {
            "user_id":         self.user_id,
            "resource":        self.resource,
            "role":            self.role,
            "risk_score":      round(self.risk_score, 2),
            "permission_ok":   self.permission_ok,
            "privilege_gap":   self.privilege_gap,
            "is_lateral_move": self.is_lateral_move,
            "is_new_resource": self.is_new_resource,
            "sensitivity_jump":self.sensitivity_jump,
            "explanation":     self.explanation,
        }


# ══════════════════════════════════════════════════════════════════
# GRAPH ENGINE
# ══════════════════════════════════════════════════════════════════

class GraphEngine:
    """
    Builds a NetworkX directed graph:

        User ──[has_role]──► Role ──[can_access]──► Resource

    Then uses graph traversal to:
      1. Check if user→role→resource path exists (permission check)
      2. Measure the gap between user's clearance and resource sensitivity
      3. Detect lateral movement through resource access patterns

    BEGINNER NOTE: NetworkX is like a map of nodes connected by arrows.
    Each node is a user, role, or resource. Each arrow is a relationship.
    We can then ask: "Is there a path from User A to Resource X?"
    """

    def __init__(self):
        self.graph = self._build_graph()

    # ──────────────────────────────────────────────────────────────
    # GRAPH CONSTRUCTION
    # ──────────────────────────────────────────────────────────────

    def _build_graph(self) -> nx.DiGraph:
        """
        Build the privilege graph with all roles and resources.

        Graph structure:
          - Node types: "user", "role", "resource"
          - Edge types: "has_role" (user→role), "can_access" (role→resource)
          - Each node has attributes (clearance_level, sensitivity_level, etc.)

        This is built once at startup and reused for every login check.
        """
        G = nx.DiGraph()

        # ── Add role nodes ─────────────────────────────────────
        for role, clearance in ROLE_CLEARANCE.items():
            G.add_node(
                f"role:{role}",
                node_type       = "role",
                name            = role,
                clearance_level = clearance,
            )

        # ── Add resource nodes ─────────────────────────────────
        for resource, sensitivity in RESOURCE_SENSITIVITY.items():
            G.add_node(
                f"resource:{resource}",
                node_type         = "resource",
                name              = resource,
                sensitivity_level = sensitivity,
            )

        # ── Add role → resource edges (permissions) ────────────
        for role, resources in ROLE_PERMISSIONS.items():
            for resource in resources:
                G.add_edge(
                    f"role:{role}",
                    f"resource:{resource}",
                    edge_type = "can_access",
                )

        return G

    def add_user(self, user_id: str, role: str) -> None:
        """
        Add a user node to the graph and connect it to their role.
        Called when a new user is encountered.
        """
        role_node = f"role:{role}"
        user_node = f"user:{user_id}"

        if user_node not in self.graph:
            self.graph.add_node(
                user_node,
                node_type = "user",
                name      = user_id,
                role      = role,
            )

        if role_node in self.graph:
            self.graph.add_edge(
                user_node,
                role_node,
                edge_type = "has_role",
            )

    # ──────────────────────────────────────────────────────────────
    # CORE EVALUATION
    # ──────────────────────────────────────────────────────────────

    def evaluate(
        self,
        user_id:           str,
        role:              str,
        resource:          str,
        clearance_level:   int,
        resource_history:  list[str] = None,
    ) -> GraphRiskResult:
        """
        Evaluate the privilege risk of a login attempt.

        Args:
            user_id:          The user's ID string
            role:             The user's assigned role (e.g. "developer")
            resource:         The resource being accessed (e.g. "financial_data")
            clearance_level:  The user's numeric clearance (1–5)
            resource_history: List of resources accessed in the current session
                              (empty list if this is the first access)

        Returns:
            GraphRiskResult with risk_score and full explanation

        Example:
            result = engine.evaluate(
                user_id         = "u_dev_001",
                role            = "developer",
                resource        = "admin_panel",
                clearance_level = 3,
                resource_history= ["dashboard", "reports"],
            )
            # → risk_score = 25 (developer cannot access admin_panel)
            # → permission_ok = False
            # → privilege_gap = 2  (sensitivity=5, clearance=3)
        """
        if resource_history is None:
            resource_history = []

        resource_sensitivity = RESOURCE_SENSITIVITY.get(resource, 2)
        role_clearance       = ROLE_CLEARANCE.get(role, 1)

        # ── 1. Permission check ────────────────────────────────
        permission_ok = self._check_permission(role, resource)

        # ── 2. Privilege gap ───────────────────────────────────
        # How many sensitivity levels ABOVE the user's clearance
        # is this resource?
        # Positive gap = trying to punch above their weight
        privilege_gap = max(0, resource_sensitivity - role_clearance)

        # ── 3. New resource check ──────────────────────────────
        is_new_resource = resource not in resource_history

        # ── 4. Lateral movement detection ─────────────────────
        is_lateral_move  = False
        sensitivity_jump = 0

        if resource_history:
            last_resource    = resource_history[-1]
            last_sensitivity = RESOURCE_SENSITIVITY.get(last_resource, 2)
            sensitivity_jump = resource_sensitivity - last_sensitivity

            # Lateral move = jumping to a completely different resource
            # category AND increasing sensitivity by 2+ levels
            is_lateral_move = (
                sensitivity_jump >= 2 and
                is_new_resource and
                not permission_ok
            )

        # ── 5. Calculate risk score ────────────────────────────
        risk = 0.0

        if not permission_ok:
            risk += RISK_POINTS["no_permission"]

        # Only penalise privilege gap when permission is explicitly denied.
        # Some roles (e.g. developer→api_keys) have explicit permission
        # even though sensitivity > clearance, so do NOT penalise them.
        if privilege_gap > 0 and not permission_ok:
            risk += privilege_gap * RISK_POINTS["privilege_gap_per"]

        if is_lateral_move:
            risk += RISK_POINTS["lateral_movement"]
        elif is_new_resource and not permission_ok:
            risk += RISK_POINTS["new_resource"]

        # Only flag sensitivity jump if user does NOT have permission
        # (permitted users may legitimately jump sensitivity levels)
        if sensitivity_jump >= 2 and not permission_ok:
            risk += RISK_POINTS["sensitivity_jump"]

        risk = float(min(risk, MAX_GRAPH_RISK))

        # ── 6. Build explanation ───────────────────────────────
        explanation = self._build_explanation(
            role, resource, resource_sensitivity, role_clearance,
            permission_ok, privilege_gap, is_lateral_move,
            is_new_resource, sensitivity_jump, risk,
        )

        return GraphRiskResult(
            user_id          = user_id,
            resource         = resource,
            role             = role,
            risk_score       = risk,
            permission_ok    = permission_ok,
            privilege_gap    = privilege_gap,
            is_lateral_move  = is_lateral_move,
            is_new_resource  = is_new_resource,
            sensitivity_jump = sensitivity_jump,
            explanation      = explanation,
        )

    # ──────────────────────────────────────────────────────────────
    # GRAPH QUERIES
    # ──────────────────────────────────────────────────────────────

    def _check_permission(self, role: str, resource: str) -> bool:
        """
        Check if a role has permission to access a resource.
        Uses NetworkX path detection: role → resource edge exists?

        This is the graph traversal part — we ask:
          "Is there an edge from role:developer to resource:admin_panel?"
        """
        role_node     = f"role:{role}"
        resource_node = f"resource:{resource}"

        if role_node not in self.graph or resource_node not in self.graph:
            # Unknown role or resource — treat as no permission
            return False

        return self.graph.has_edge(role_node, resource_node)

    def get_all_accessible_resources(self, role: str) -> list[str]:
        """
        Return all resources a role can access.
        Uses NetworkX successors (nodes reachable from this node).
        """
        role_node = f"role:{role}"
        if role_node not in self.graph:
            return []

        return [
            self.graph.nodes[n]["name"]
            for n in self.graph.successors(role_node)
            if self.graph.nodes[n].get("node_type") == "resource"
        ]

    def get_shortest_privilege_path(
        self, role: str, resource: str
    ) -> Optional[list[str]]:
        """
        Find the shortest path from a role to a resource through the graph.
        Returns None if no path exists (no permission even indirectly).

        This detects privilege escalation chains:
          developer → (via manager permissions) → financial_data
        """
        role_node     = f"role:{role}"
        resource_node = f"resource:{resource}"

        if role_node not in self.graph or resource_node not in self.graph:
            return None

        try:
            path = nx.shortest_path(self.graph, role_node, resource_node)
            return [self.graph.nodes[n].get("name", n) for n in path]
        except nx.NetworkXNoPath:
            return None

    def get_graph_stats(self) -> dict:
        """Return statistics about the privilege graph."""
        return {
            "total_nodes": self.graph.number_of_nodes(),
            "total_edges": self.graph.number_of_edges(),
            "roles":       len(ROLE_CLEARANCE),
            "resources":   len(RESOURCE_SENSITIVITY),
        }

    # ──────────────────────────────────────────────────────────────
    # EXPLANATION BUILDER
    # ──────────────────────────────────────────────────────────────

    def _build_explanation(
        self,
        role: str, resource: str,
        resource_sensitivity: int, role_clearance: int,
        permission_ok: bool, privilege_gap: int,
        is_lateral_move: bool, is_new_resource: bool,
        sensitivity_jump: int, risk: float,
    ) -> str:
        """Build a human-readable explanation for the dashboard."""

        if risk == 0:
            return (
                f"{role} accessing {resource} "
                f"(sensitivity={resource_sensitivity}, clearance={role_clearance}) — normal"
            )

        parts = []

        if not permission_ok:
            parts.append(
                f"{role} role has no permission for {resource} "
                f"(needs clearance {resource_sensitivity}, has {role_clearance})"
            )

        if privilege_gap > 0 and permission_ok:
            parts.append(
                f"accessing resource {privilege_gap} level(s) above clearance"
            )

        if is_lateral_move:
            parts.append(
                f"lateral movement detected — jumping to {resource} "
                f"(sensitivity jumped +{sensitivity_jump})"
            )
        elif is_new_resource and not permission_ok:
            parts.append(f"resource {resource!r} never accessed before")

        return "; ".join(parts) if parts else f"elevated risk accessing {resource}"


# ══════════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTION
# Used by the FastAPI backend (Phase 10)
# ══════════════════════════════════════════════════════════════════

# Singleton instance — built once at import, reused for every request
_engine_instance: Optional[GraphEngine] = None

def get_graph_engine() -> GraphEngine:
    """Return the singleton GraphEngine instance."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = GraphEngine()
    return _engine_instance
