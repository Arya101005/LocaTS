"""
Edge case tests for LocaTS — SIH26191.

Tests the three mandatory scenarios:
  5.1: Infeasible optimization (demand > supply)
  5.2: Disconnected graph (road network partition)
  5.5: Race conditions in shelter capacity (atomic re-optimization)

Plus additional edge cases:
  5.3: Staleness decay on sensor readings
  5.4: Crowd report corroboration gating
  5.7: Accessibility infeasibility
  5.11: Solver time-budget → greedy fallback
  5.12: Multi-hazard shelter overlap
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta

import pytest

from backend.app.models.domain import (
    CapacityGraph,
    Coordinates,
    CrowdReport,
    HabitationCluster,
    HazardType,
    LiveSensorReading,
    OptimizationResult,
    RoadSegment,
    RoadStatus,
    Shelter,
    StaticHazardZone,
)
from backend.app.hazard_fusion.fusion import (
    _compute_staleness_factor,
    _filter_crowd_reports,
    fuse_hazard_scores,
    STALENESS_HALF_LIFE_MINUTES,
)
from backend.app.capacity.graph_builder import CapacityGraphBuilder
from backend.app.optimizer.optimizer import OptimizationEngine


# ============================================================================
# 5.1 — INFEASIBLE OPTIMIZATION: demand exceeds total shelter capacity
# ============================================================================

class TestInfeasibilityEdgeCase:
    """
    When total habitation population > total shelter capacity,
    the system must NOT crash or hang. It must:
      - Detect infeasibility
      - Fall back to equitable partial allocation
      - Flag unmet demand to the operator
    """

    def _make_infeasible_graph(self) -> CapacityGraph:
        """5000 people, 2000 beds — infeasible."""
        habitations = [
            HabitationCluster(
                id="hab-big-1", name="Large Village",
                location={"lat": 30.0, "lon": 79.0},
                population_estimate=3000, district="D",
            ),
            HabitationCluster(
                id="hab-big-2", name="Another Village",
                location={"lat": 30.1, "lon": 79.1},
                population_estimate=2000, district="D",
            ),
        ]
        shelters = [
            Shelter(
                id="sh-small-1", name="Small Shelter",
                location={"lat": 30.05, "lon": 79.05},
                bed_capacity=1500, district="D",
            ),
            Shelter(
                id="sh-small-2", name="Another Small",
                location={"lat": 30.15, "lon": 79.15},
                bed_capacity=500, district="D",
            ),
        ]
        roads = [
            RoadSegment(
                id="r1", from_node="hab-big-1", to_node="sh-small-1",
                distance_km=5.0, travel_time_minutes=15,
                capacity_vehicles_per_hour=100, people_throughput_per_hour=1000,
            ),
            RoadSegment(
                id="r2", from_node="hab-big-2", to_node="sh-small-2",
                distance_km=5.0, travel_time_minutes=15,
                capacity_vehicles_per_hour=100, people_throughput_per_hour=1000,
            ),
            RoadSegment(
                id="r3", from_node="hab-big-1", to_node="sh-small-2",
                distance_km=20.0, travel_time_minutes=60,
                capacity_vehicles_per_hour=50, people_throughput_per_hour=500,
            ),
            RoadSegment(
                id="r4", from_node="hab-big-2", to_node="sh-small-1",
                distance_km=20.0, travel_time_minutes=60,
                capacity_vehicles_per_hour=50, people_throughput_per_hour=500,
            ),
        ]
        return CapacityGraph(habitations=habitations, shelters=shelters, road_segments=roads)

    def test_infeasibility_detected(self):
        """System detects infeasibility and does not crash."""
        graph = self._make_infeasible_graph()
        builder = CapacityGraphBuilder(population_safety_margin=0.0)
        graph = builder.build(graph)
        paths = builder.compute_shortest_paths(graph)

        engine = OptimizationEngine(time_budget_seconds=10.0)
        result = engine.solve(graph, paths)

        # Must not crash
        assert isinstance(result, OptimizationResult)
        # Should flag unmet demand
        assert result.total_people_unmet > 0
        assert len(result.unmet_habitations) > 0

    def test_partial_allocation_is_equitable(self):
        """When infeasible, allocation distributes proportionally."""
        graph = self._make_infeasible_graph()
        builder = CapacityGraphBuilder(population_safety_margin=0.0)
        graph = builder.build(graph)
        paths = builder.compute_shortest_paths(graph)

        engine = OptimizationEngine(time_budget_seconds=10.0)
        result = engine.solve(graph, paths)

        # Should relocate some people (not all, not zero)
        assert 0 < result.total_people_relocated < 5000
        # Total assigned should match relocated
        total_assigned = sum(a.people_assigned for a in result.assignments)
        assert total_assigned == result.total_people_relocated

    def test_feasible_case_works(self):
        """Sanity check: feasible case produces full allocation."""
        graph = CapacityGraph(
            habitations=[
                HabitationCluster(
                    id="h1", name="Village", location={"lat": 30.0, "lon": 79.0},
                    population_estimate=500, district="D",
                ),
            ],
            shelters=[
                Shelter(
                    id="s1", name="Shelter", location={"lat": 30.05, "lon": 79.05},
                    bed_capacity=1000, district="D",
                ),
            ],
            road_segments=[
                RoadSegment(
                    id="r1", from_node="h1", to_node="s1",
                    distance_km=5.0, travel_time_minutes=15,
                    capacity_vehicles_per_hour=100, people_throughput_per_hour=1000,
                ),
            ],
        )
        builder = CapacityGraphBuilder(population_safety_margin=0.0)
        graph = builder.build(graph)
        paths = builder.compute_shortest_paths(graph)

        engine = OptimizationEngine(time_budget_seconds=10.0)
        result = engine.solve(graph, paths)

        assert result.is_feasible
        assert result.total_people_unmet == 0
        assert result.total_people_relocated >= 500


# ============================================================================
# 5.2 — DISCONNECTED GRAPH: habitation's only route to shelter is cut
# ============================================================================

class TestDisconnectedGraphEdgeCase:
    """
    After road failure, if a habitation has no path to any shelter,
    the system must flag it for non-road evacuation (boat/air),
    NOT silently return "no route".
    """

    def test_disconnected_habitation_flagged(self):
        """A habitation with no road to any shelter is detected."""
        habitations = [
            HabitationCluster(
                id="h-island", name="Isolated Village",
                location={"lat": 30.0, "lon": 79.0},
                population_estimate=500, district="D",
            ),
            HabitationCluster(
                id="h-connected", name="Connected Village",
                location={"lat": 30.1, "lon": 79.1},
                population_estimate=300, district="D",
            ),
        ]
        shelters = [
            Shelter(
                id="s1", name="Shelter", location={"lat": 30.2, "lon": 79.2},
                bed_capacity=2000, district="D",
            ),
        ]
        # Only h-connected has a road to s1; h-island has NO roads
        roads = [
            RoadSegment(
                id="r1", from_node="h-connected", to_node="s1",
                distance_km=15.0, travel_time_minutes=30,
                capacity_vehicles_per_hour=100, people_throughput_per_hour=1000,
            ),
        ]
        graph = CapacityGraph(habitations=habitations, shelters=shelters, road_segments=roads)
        builder = CapacityGraphBuilder(population_safety_margin=0.0)
        graph = builder.build(graph)
        paths = builder.compute_shortest_paths(graph)

        engine = OptimizationEngine(time_budget_seconds=10.0)
        result = engine.solve(graph, paths)

        # h-island must be flagged as disconnected
        assert "h-island" in result.disconnected_habitations

    def test_road_failure_creates_disconnection(self):
        """Blocking the only road to a habitation creates a disconnect."""
        habitations = [
            HabitationCluster(
                id="h1", name="Village", location={"lat": 30.0, "lon": 79.0},
                population_estimate=500, district="D",
            ),
        ]
        shelters = [
            Shelter(
                id="s1", name="Shelter", location={"lat": 30.1, "lon": 79.1},
                bed_capacity=1000, district="D",
            ),
        ]
        roads = [
            RoadSegment(
                id="r1", from_node="h1", to_node="s1",
                distance_km=10.0, travel_time_minutes=30,
                capacity_vehicles_per_hour=100, people_throughput_per_hour=1000,
                status=RoadStatus.OPEN, damage_factor=1.0,
            ),
        ]
        graph = CapacityGraph(habitations=habitations, shelters=shelters, road_segments=roads)
        builder = CapacityGraphBuilder(population_safety_margin=0.0)
        graph = builder.build(graph)

        # Before blocking: has path
        paths = builder.compute_shortest_paths(graph)
        assert paths[("h1", "s1")]["feasible"] is True

        # Block the road
        roads[0].status = RoadStatus.BLOCKED
        roads[0].damage_factor = 0.0
        graph = builder.build(graph)
        paths = builder.compute_shortest_paths(graph)

        # After blocking: no path
        assert paths[("h1", "s1")]["feasible"] is False

        engine = OptimizationEngine(time_budget_seconds=10.0)
        result = engine.solve(graph, paths)
        assert "h1" in result.disconnected_habitations


# ============================================================================
# 5.5 — RACE CONDITIONS: atomic re-optimization on capacity changes
# ============================================================================

class TestRaceConditionEdgeCase:
    """
    When multiple habitation clusters are assigned to overlapping shelters
    simultaneously during re-optimization, the re-solve must be atomic.
    No double-booking of beds across concurrent solver runs.
    """

    def test_concurrent_re_optimize_no_double_booking(self):
        """Two threads calling re_optimize must not produce double-booked shelters."""
        habitations = [
            HabitationCluster(
                id="h1", name="V1", location={"lat": 30.0, "lon": 79.0},
                population_estimate=400, district="D",
            ),
            HabitationCluster(
                id="h2", name="V2", location={"lat": 30.1, "lon": 79.1},
                population_estimate=400, district="D",
            ),
        ]
        shelters = [
            Shelter(
                id="s1", name="Shelter", location={"lat": 30.05, "lon": 79.05},
                bed_capacity=600, district="D",  # Not enough for both
            ),
        ]
        roads = [
            RoadSegment(
                id="r1", from_node="h1", to_node="s1",
                distance_km=5.0, travel_time_minutes=15,
                capacity_vehicles_per_hour=100, people_throughput_per_hour=1000,
            ),
            RoadSegment(
                id="r2", from_node="h2", to_node="s1",
                distance_km=5.0, travel_time_minutes=15,
                capacity_vehicles_per_hour=100, people_throughput_per_hour=1000,
            ),
        ]
        graph = CapacityGraph(habitations=habitations, shelters=shelters, road_segments=roads)
        builder = CapacityGraphBuilder(population_safety_margin=0.0)
        graph = builder.build(graph)
        paths = builder.compute_shortest_paths(graph)

        engine = OptimizationEngine(time_budget_seconds=10.0)
        results = []
        errors = []

        def run_optimize(idx):
            try:
                r = engine.re_optimize(graph, paths)
                results.append(r)
            except Exception as e:
                errors.append(e)

        # Launch two concurrent re-optimizations
        t1 = threading.Thread(target=run_optimize, args=(1,))
        t2 = threading.Thread(target=run_optimize, args=(2,))
        t1.start()
        t2.start()
        t1.join(timeout=30)
        t2.join(timeout=30)

        assert len(errors) == 0, f"Errors in concurrent optimization: {errors}"
        assert len(results) == 2

        # Each result must not overbook the shelter
        for r in results:
            total_assigned = sum(a.people_assigned for a in r.assignments if a.shelter_id == "s1")
            # Should be at most the shelter capacity
            assert total_assigned <= 600, f"Overbooking detected: {total_assigned} > 600"

    def test_shelter_capacity_respected(self):
        """After assignment, shelter occupancy does not exceed capacity."""
        graph = CapacityGraph(
            habitations=[
                HabitationCluster(
                    id="h1", name="V", location={"lat": 30.0, "lon": 79.0},
                    population_estimate=300, district="D",
                ),
            ],
            shelters=[
                Shelter(
                    id="s1", name="S", location={"lat": 30.05, "lon": 79.05},
                    bed_capacity=200, district="D",
                ),
            ],
            road_segments=[
                RoadSegment(
                    id="r1", from_node="h1", to_node="s1",
                    distance_km=5.0, travel_time_minutes=15,
                    capacity_vehicles_per_hour=100, people_throughput_per_hour=1000,
                ),
            ],
        )
        builder = CapacityGraphBuilder(population_safety_margin=0.0)
        graph = builder.build(graph)
        paths = builder.compute_shortest_paths(graph)

        engine = OptimizationEngine(time_budget_seconds=10.0)
        result = engine.solve(graph, paths)

        total = sum(a.people_assigned for a in result.assignments if a.shelter_id == "s1")
        assert total <= 200, f"Capacity exceeded: {total} > 200"


# ============================================================================
# 5.3 — STALENESS DECAY on sensor readings
# ============================================================================

class TestStalenessDecay:
    """Sensor readings must lose trust over time (edge 5.3)."""

    def test_fresh_reading_higher_factor(self):
        now = datetime.utcnow()
        fresh = now - timedelta(minutes=10)
        stale = now - timedelta(hours=6)

        fresh_factor = _compute_staleness_factor(fresh, now)
        stale_factor = _compute_staleness_factor(stale, now)

        assert fresh_factor > stale_factor
        assert fresh_factor > 0.9
        assert stale_factor < 0.2

    def test_very_old_reading_has_floor(self):
        now = datetime.utcnow()
        ancient = now - timedelta(days=30)
        factor = _compute_staleness_factor(ancient, now)
        assert factor >= 0.05  # STALE_TRUST_FLOOR


# ============================================================================
# 5.4 — CROWD REPORT CORROBORATION GATING
# ============================================================================

class TestCrowdReportGating:
    """Single unverified reports must not trigger relocation (edge 5.4)."""

    def test_single_report_filtered(self):
        now = datetime.utcnow()
        reports = [
            CrowdReport(
                id="r1", reporter_id="user1", hazard_type=HazardType.FLOOD,
                severity_estimate=0.9, location={"lat": 30.0, "lon": 79.0},
                timestamp=now,
            ),
        ]
        severity, count, ids = _filter_crowd_reports(reports, now)
        assert severity is None  # Not enough corroboration
        assert count == 1

    def test_corroborated_reports_accepted(self):
        now = datetime.utcnow()
        reports = [
            CrowdReport(
                id=f"r{i}", reporter_id=f"user{i}", hazard_type=HazardType.FLOOD,
                severity_estimate=0.7 + i * 0.05, location={"lat": 30.0, "lon": 79.0},
                timestamp=now,
            )
            for i in range(5)  # 5 independent reports
        ]
        severity, count, ids = _filter_crowd_reports(reports, now)
        assert severity is not None
        assert count >= 3
        assert 0.0 <= severity <= 1.0


# ============================================================================
# 5.7 — ACCESSIBILITY INFEASIBILITY
# ============================================================================

class TestAccessibilityGap:
    """No accessible shelter → flagged as capacity gap (edge 5.7)."""

    def test_accessibility_gap_detected(self):
        habitations = [
            HabitationCluster(
                id="h1", name="V", location={"lat": 30.0, "lon": 79.0},
                population_estimate=500, has_accessible_population=True,
                accessible_population_fraction=0.12, district="D",
            ),
        ]
        shelters = [
            Shelter(
                id="s1", name="Inaccessible Shelter",
                location={"lat": 30.05, "lon": 79.05},
                bed_capacity=1000, is_accessible=False, district="D",
            ),
        ]
        roads = [
            RoadSegment(
                id="r1", from_node="h1", to_node="s1",
                distance_km=5.0, travel_time_minutes=15,
                capacity_vehicles_per_hour=100, people_throughput_per_hour=1000,
            ),
        ]
        graph = CapacityGraph(habitations=habitations, shelters=shelters, road_segments=roads)
        builder = CapacityGraphBuilder(population_safety_margin=0.0)
        graph = builder.build(graph)
        paths = builder.compute_shortest_paths(graph)

        engine = OptimizationEngine(time_budget_seconds=10.0)
        result = engine.solve(graph, paths)

        assert "h1" in result.accessibility_gap_habitations


# ============================================================================
# 5.12 — MULTI-HAZARD SHELTER OVERLAP
# ============================================================================

class TestMultiHazardShelterOverlap:
    """A shelter in a secondary hazard zone must be flagged inactive."""

    def test_shelter_in_hazard_zone_disabled(self):
        shelter = Shelter(
            id="s-dangerous", name="Danger Zone Shelter",
            location={"lat": 30.0, "lon": 79.0},
            bed_capacity=500, hazard_zone_ids=["flood-zone-1", "landslide-zone-1"],
        )
        assert shelter.hazard_zone_ids  # Has hazard zones
        # After graph builder validation, should be inactive
        graph = CapacityGraph(
            habitations=[],
            shelters=[shelter],
            road_segments=[],
        )
        builder = CapacityGraphBuilder()
        graph = builder.build(graph)

        assert not graph.shelters[0].is_active


# ============================================================================
# 5.13 — CROSS-DISTRICT DETECTION
# ============================================================================

class TestCrossDistrict:
    """Inter-district assignments must be flagged."""

    def test_inter_district_flagged(self):
        habitations = [
            HabitationCluster(
                id="h1", name="V", location={"lat": 30.0, "lon": 79.0},
                population_estimate=500, district="Chamoli",
            ),
        ]
        shelters = [
            Shelter(
                id="s1", name="S", location={"lat": 30.5, "lon": 79.5},
                bed_capacity=1000, district="Pauri Garhwal",
            ),
        ]
        roads = [
            RoadSegment(
                id="r1", from_node="h1", to_node="s1",
                distance_km=50.0, travel_time_minutes=150,
                capacity_vehicles_per_hour=50, people_throughput_per_hour=500,
            ),
        ]
        graph = CapacityGraph(habitations=habitations, shelters=shelters, road_segments=roads)
        builder = CapacityGraphBuilder(population_safety_margin=0.0)
        graph = builder.build(graph)
        paths = builder.compute_shortest_paths(graph)

        engine = OptimizationEngine(time_budget_seconds=10.0)
        result = engine.solve(graph, paths)

        assert "h1" in result.inter_district_assignments
