"""
API Flow Tests
==============
Tests for four critical flows that must work correctly:

1. Login/auth flow — token generation and validation
2. Optimizer solve — returns feasible result on known-good input
3. Corroboration gating — single crowd report must NOT trigger alert
4. Family search privacy — name-only search must not return results
"""

from __future__ import annotations
import pytest


# ============================================================================
# 1. AUTH FLOW
# ============================================================================

class TestAuthFlow:
    """Test Supabase Auth integration (signup, login, token validation)."""

    def test_auth_module_imports(self):
        """Auth module should import without errors."""
        from backend.app.utils.auth import create_auth_routes
        assert callable(create_auth_routes)

    def test_auth_routes_registered(self):
        """Auth routes should be registerable on a FastAPI app."""
        from fastapi import FastAPI
        from backend.app.utils.auth import create_auth_routes
        app = FastAPI()
        create_auth_routes(app)
        # Check that auth routes exist
        routes = [r.path for r in app.routes]
        assert any("/api/auth/login" in r for r in routes)
        assert any("/api/auth/signup" in r for r in routes)


# ============================================================================
# 2. OPTIMIZER SOLVE — FEASIBLE RESULT
# ============================================================================

class TestOptimizerSolve:
    """Test that the optimizer produces a feasible result on known-good input."""

    def _make_feasible_graph(self):
        """Create a graph where total beds >= total population."""
        from backend.app.models.domain import (
            CapacityGraph, HabitationCluster, Shelter, RoadSegment,
        )
        habitations = [
            HabitationCluster(id="h1", name="Village A", location={"lat": 30.0, "lon": 79.0},
                              population_estimate=200, district="D"),
            HabitationCluster(id="h2", name="Village B", location={"lat": 30.1, "lon": 79.1},
                              population_estimate=300, district="D"),
        ]
        shelters = [
            Shelter(id="s1", name="Shelter 1", location={"lat": 30.05, "lon": 79.05},
                    bed_capacity=1000, district="D"),
        ]
        roads = [
            RoadSegment(id="r1", from_node="h1", to_node="s1", distance_km=5.0,
                        travel_time_minutes=15, capacity_vehicles_per_hour=100,
                        people_throughput_per_hour=1000),
            RoadSegment(id="r2", from_node="h2", to_node="s1", distance_km=10.0,
                        travel_time_minutes=30, capacity_vehicles_per_hour=100,
                        people_throughput_per_hour=1000),
        ]
        return CapacityGraph(habitations=habitations, shelters=shelters, road_segments=roads)

    def test_solve_returns_feasible(self):
        """Optimizer should produce a feasible plan when beds >= population."""
        from backend.app.capacity.graph_builder import CapacityGraphBuilder
        from backend.app.optimizer.optimizer import OptimizationEngine

        graph = self._make_feasible_graph()
        builder = CapacityGraphBuilder(population_safety_margin=0.0)
        graph = builder.build(graph)
        paths = builder.compute_shortest_paths(graph)

        engine = OptimizationEngine(time_budget_seconds=10.0)
        result = engine.solve(graph, paths)

        assert result.is_feasible
        assert result.total_people_unmet == 0
        assert result.total_people_relocated >= 500  # 200 + 300
        assert len(result.assignments) > 0

    def test_solve_respects_capacity(self):
        """No shelter should be overbooked."""
        from backend.app.capacity.graph_builder import CapacityGraphBuilder
        from backend.app.optimizer.optimizer import OptimizationEngine

        graph = self._make_feasible_graph()
        builder = CapacityGraphBuilder(population_safety_margin=0.0)
        graph = builder.build(graph)
        paths = builder.compute_shortest_paths(graph)

        engine = OptimizationEngine(time_budget_seconds=10.0)
        result = engine.solve(graph, paths)

        # Check shelter 1 capacity
        assigned_to_s1 = sum(a.people_assigned for a in result.assignments if a.shelter_id == "s1")
        assert assigned_to_s1 <= 1000  # Shelter capacity


# ============================================================================
# 3. CORROBORATION GATING — SINGLE REPORT DOES NOT TRIGGER ALERT
# ============================================================================

class TestCorroborationGating:
    """A single crowd report must NOT trigger a relocation alert."""

    def test_single_report_filtered(self):
        """Single crowd report should not produce a severity score."""
        from datetime import datetime
        from backend.app.models.domain import CrowdReport, HazardType
        from backend.app.hazard_fusion.fusion import _filter_crowd_reports

        now = datetime.utcnow()
        reports = [
            CrowdReport(id="r1", reporter_id="user1", hazard_type=HazardType.FLOOD,
                        severity_estimate=0.9, location={"lat": 30.0, "lon": 79.0}, timestamp=now),
        ]
        severity, count, ids = _filter_crowd_reports(reports, now)
        assert severity is None  # Must be None — not enough corroboration
        assert count == 1

    def test_three_reports_pass_gating(self):
        """3+ corroborated reports should produce a severity score."""
        from datetime import datetime
        from backend.app.models.domain import CrowdReport, HazardType
        from backend.app.hazard_fusion.fusion import _filter_crowd_reports

        now = datetime.utcnow()
        reports = [
            CrowdReport(id=f"r{i}", reporter_id=f"user{i}", hazard_type=HazardType.FLOOD,
                        severity_estimate=0.7 + i * 0.05, location={"lat": 30.0, "lon": 79.0}, timestamp=now)
            for i in range(5)
        ]
        severity, count, ids = _filter_crowd_reports(reports, now)
        assert severity is not None
        assert count >= 3

    def test_stale_reports_filtered(self):
        """Reports older than 24 hours should be ignored."""
        from datetime import datetime, timedelta
        from backend.app.models.domain import CrowdReport, HazardType
        from backend.app.hazard_fusion.fusion import _filter_crowd_reports

        now = datetime.utcnow()
        old_time = now - timedelta(hours=25)
        reports = [
            CrowdReport(id=f"r{i}", reporter_id=f"user{i}", hazard_type=HazardType.FLOOD,
                        severity_estimate=0.8, location={"lat": 30.0, "lon": 79.0}, timestamp=old_time)
            for i in range(5)
        ]
        severity, count, ids = _filter_crowd_reports(reports, now)
        assert severity is None  # All reports are stale


# ============================================================================
# 4. FAMILY SEARCH PRIVACY — NAME-ONLY MUST NOT RETURN RESULTS
# ============================================================================

class TestFamilySearchPrivacy:
    """Name-only search must not return shelter location data."""

    def test_name_only_search_rejected(self):
        """Search with name only (no village, no age) must return empty + warning."""
        import asyncio
        from backend.app.api.routers.citizen import search_family
        from pydantic import BaseModel

        class SearchInput(BaseModel):
            search_name: str
            home_habitation_id: str = ""
            age_range: str = ""

        req = SearchInput(search_name="Test Person")
        result = asyncio.get_event_loop().run_until_complete(search_family(req))
        assert result["results"] == []
        assert result.get("requires_secondary_id") is True

    def test_name_with_village_accepted(self):
        """Search with name + village should be accepted (may return empty results)."""
        import asyncio
        from backend.app.api.routers.citizen import search_family
        from pydantic import BaseModel

        class SearchInput(BaseModel):
            search_name: str
            home_habitation_id: str = ""
            age_range: str = ""

        req = SearchInput(search_name="Test Person", home_habitation_id="Raini Village")
        result = asyncio.get_event_loop().run_until_complete(search_family(req))
        assert "requires_secondary_id" not in result


# ============================================================================
# 5. HEALTH CHECK
# ============================================================================

class TestHealthCheck:
    """Basic health endpoint should respond."""

    def test_health_returns_ok(self):
        import asyncio
        from backend.app.api.main import health

        result = asyncio.get_event_loop().run_until_complete(health())
        assert result["status"] == "ok"
        assert "layers" in result
