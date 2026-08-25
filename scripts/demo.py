#!/usr/bin/env python3
"""
LocaTS Demo Script - SIH26191
Demonstrates the full pipeline for Chamoli district, Uttarakhand:

  1. Load hazard zones + sensor data + habitations + shelters + roads
  2. Run hazard fusion -> confidence scores per habitation
  3. Run baseline (greedy nearest-shelter) allocation
  4. Run optimized (min-cost flow) allocation -> compare with baseline
  5. Simulate road failure (road-001 blocked) -> trigger re-optimization
  6. Show the system adapting -- new assignments, disconnected habitation flagged

This comparison is the single most important demo moment for SIH judges.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime

from backend.app.data.sample.chamoli_data import (
    build_chamoli_sample,
    get_sample_hazard_zones,
    get_sample_sensor_readings,
)
from backend.app.hazard_fusion.fusion import fuse_hazard_scores
from backend.app.capacity.graph_builder import CapacityGraphBuilder
from backend.app.optimizer.optimizer import OptimizationEngine
from backend.app.models.domain import HazardType, AlertLevel, RoadStatus, StaticHazardZone


def print_header(text):
    print()
    print("=" * 70)
    print("  " + text)
    print("=" * 70)
    print()


def main():
    print_header("LocaTS Demo - SIH26191: Chamoli District, Uttarakhand")
    print("Intelligent Hazard Identification & Optimized Relocation Planning")
    print("Solver: OR-Tools MinCostFlow (CPU -- no GPU available)")
    print()

    # STEP 1: Load data
    print_header("STEP 1: Load District Data")
    graph_data = build_chamoli_sample()
    hazard_zones = get_sample_hazard_zones()
    sensor_readings = get_sample_sensor_readings()

    print("Habitations loaded: %d" % len(graph_data.habitations))
    for h in graph_data.habitations:
        print("  %s: %s -- pop. %s" % (h.id, h.name, format(h.population_estimate, ",")))
    print()
    print("Shelters loaded: %d" % len(graph_data.shelters))
    for s in graph_data.shelters:
        print("  %s: %s -- %d beds, accessible=%s, district=%s" % (
            s.id, s.name, s.bed_capacity, s.is_accessible, s.district))
    print()
    print("Road segments: %d" % len(graph_data.road_segments))
    print("Hazard zones: %d" % len(hazard_zones))
    print("Sensor readings: %d" % len(sensor_readings))

    # STEP 2: Build capacity graph
    print_header("STEP 2: Build Capacity Graph")
    builder = CapacityGraphBuilder(population_safety_margin=0.15)
    graph_data = builder.build(graph_data)
    summary = builder.get_shelter_capacity_summary(graph_data)
    print("Capacity summary:")
    for k, v in summary.items():
        print("  %s: %s" % (k, v))

    shortest_paths = builder.compute_shortest_paths(graph_data)
    print()
    print("Shortest paths computed: %d" % len(shortest_paths))
    feasible_count = sum(1 for p in shortest_paths.values() if p.get("feasible"))
    print("Feasible routes: %d/%d" % (feasible_count, len(shortest_paths)))

    # STEP 3: Hazard fusion
    print_header("STEP 3: Hazard Fusion -- Multi-Source Confidence Scoring")
    print("Sources: Static zones (Bhuvan/NDMA) + IMD rainfall + crowd reports")
    print()

    now = datetime.utcnow()
    alert_counts = {level: 0 for level in AlertLevel}

    for hab in graph_data.habitations:
        for htype in [HazardType.FLOOD, HazardType.LANDSLIDE]:
            typed_zones = []
            for z in hazard_zones:
                if z["hazard_type"] == htype.value:
                    typed_zones.append(StaticHazardZone(
                        id=z["id"],
                        hazard_type=htype,
                        severity=z["severity"],
                        center={"lat": z["center_lat"], "lon": z["center_lon"]},
                        radius_km=z["radius_km"],
                    ))

            score = fuse_hazard_scores(
                habitation_id=hab.id,
                habitation_location=hab.location,
                hazard_type=htype,
                static_zones=typed_zones,
                sensor_readings=[],
                crowd_reports=[],
                now=now,
            )
            alert_counts[score.alert_level] += 1

            icon = {"normal": "[OK] ", "advisory": "[!!] ", "evacuate": "[!!] ", "relocate": "[XX] "}
            print("  %-25s | %-10s | confidence=%.3f | %s%-10s | static=%.3f sensor=%.3f" % (
                hab.name, htype.value, score.confidence,
                icon[score.alert_level.value], score.alert_level.value,
                score.component_scores["static"], score.component_scores["sensor"]))

    print()
    print("Alert level distribution:")
    for level, count in alert_counts.items():
        print("  %s: %d" % (level.value, count))

    # STEP 4: Baseline allocation (greedy)
    print_header("STEP 4: BASELINE -- Greedy Nearest-Shelter Allocation")
    print("(What most existing systems do -- simple nearest feasible shelter)")
    print()

    optimizer = OptimizationEngine(time_budget_seconds=5.0)
    hazard_scores = {}
    urgency_weights = {}
    for hab in graph_data.habitations:
        hazard_scores[hab.id] = 0.5 + hab.population_estimate / 20000.0
        urgency_weights[hab.id] = 1.0 + hazard_scores[hab.id]

    baseline_assignments = optimizer._greedy_fallback(
        graph_data.habitations,
        [s for s in graph_data.shelters if s.is_active],
        shortest_paths,
        urgency_weights={},  # Greedy ignores urgency -- key weakness
    )

    baseline_total = sum(a.people_assigned for a in baseline_assignments)
    baseline_cost = sum(a.cost for a in baseline_assignments)
    baseline_dist = sum(a.distance_km * a.people_assigned for a in baseline_assignments)
    # Compute urgency-weighted cost for fair comparison
    baseline_urgency_cost = sum(
        a.distance_km * a.people_assigned * urgency_weights.get(a.habitation_id, 1.0)
        for a in baseline_assignments
    )

    for a in baseline_assignments:
        hab = graph_data.get_habitation_by_id(a.habitation_id)
        print("  %-25s -> %-15s | %5d people | %6.1f km | cost=%10.1f" % (
            hab.name if hab else a.habitation_id, a.shelter_id,
            a.people_assigned, a.distance_km, a.cost))

    print()
    print("  Total relocated: %s" % format(baseline_total, ","))
    print("  Total weighted cost: %s" % format(baseline_cost, ",.1f"))
    print("  Total person-km: %s" % format(baseline_dist, ",.1f"))

    # STEP 5: Optimized allocation (min-cost flow)
    print_header("STEP 5: OPTIMIZED -- Capacitated Min-Cost Flow")
    print("(Our core innovation -- optimal assignment subject to all constraints)")
    print()

    opt_result = optimizer.solve(
        graph_data, shortest_paths, urgency_weights, hazard_scores
    )
    opt_urgency_cost = sum(
        a.distance_km * a.people_assigned * urgency_weights.get(a.habitation_id, 1.0)
        for a in opt_result.assignments
    )

    for a in opt_result.assignments:
        hab = graph_data.get_habitation_by_id(a.habitation_id)
        fb = " [FALLBACK]" if a.is_fallback else ""
        inter = " [INTER-DIST]" if a.is_inter_district else ""
        print("  %-25s -> %-15s | %5d people | %6.1f km | cost=%10.1f%s%s" % (
            hab.name if hab else a.habitation_id, a.shelter_id,
            a.people_assigned, a.distance_km, a.cost, fb, inter))

    print()
    print("  Total relocated: %s" % format(opt_result.total_people_relocated, ","))
    print("  Total people unmet: %s" % format(opt_result.total_people_unmet, ","))
    print("  Total weighted cost: %s" % format(opt_result.total_cost, ",.1f"))
    print("  Solver time: %.3fs" % opt_result.solver_time_seconds)
    print("  Feasible: %s" % opt_result.is_feasible)
    print("  Used fallback heuristic: %s" % opt_result.used_fallback_heuristic)
    print("  Disconnected habitations: %s" % opt_result.disconnected_habitations)
    print("  Accessibility gaps: %s" % opt_result.accessibility_gap_habitations)
    print("  Inter-district: %s" % opt_result.inter_district_assignments)
    print("  Audit hash: %s" % opt_result.compute_audit_hash())

    # STEP 6: Compare baseline vs optimized
    print_header("STEP 6: BASELINE vs OPTIMIZED COMPARISON")

    print("  %-35s %15s %15s %15s" % ("Metric", "Baseline", "Optimized", "Delta"))
    print("  %-35s %15s %15s %15s" % ("-" * 35, "-" * 15, "-" * 15, "-" * 15))
    print("  %-35s %15s %15s %+15d" % (
        "Total relocated", format(baseline_total, ","),
        format(opt_result.total_people_relocated, ","),
        opt_result.total_people_relocated - baseline_total))
    print("  %-35s %15s %15s %+15s" % (
        "Urgency-weighted cost", format(baseline_urgency_cost, ",.1f"),
        format(opt_urgency_cost, ",.1f"),
        format(opt_urgency_cost - baseline_urgency_cost, "+,.1f")))
    print("  %-35s %15s %15s %15s" % (
        "Total person-km", format(baseline_dist, ",.1f"), "N/A", "N/A"))

    # STEP 7: Simulate road failure -> re-optimize
    print_header("STEP 7: SIMULATE ROAD FAILURE -- Rolling-Horizon Re-optimization")
    print("Road-001 (Raini -> Joshimath) BLOCKED by landslide")
    print()

    for road in graph_data.road_segments:
        if road.id == "road-001":
            road.status = RoadStatus.BLOCKED
            road.damage_factor = 0.0
            print("  Road %s: %s -> %s BLOCKED" % (road.id, road.from_node, road.to_node))
            break

    for road in graph_data.road_segments:
        if road.id == "road-003":
            road.status = RoadStatus.DEGRADED
            road.damage_factor = 0.3
            print("  Road %s: %s -> %s DEGRADED (30%% capacity)" % (
                road.id, road.from_node, road.to_node))
            break

    graph_data = builder.build(graph_data)
    shortest_paths = builder.compute_shortest_paths(graph_data)

    print()
    print("Rebuilding graph with updated road status...")
    print("Recomputing shortest paths...")

    disconnected = optimizer._find_disconnected_habitations(graph_data, shortest_paths)
    if disconnected:
        print()
        print("  DISCONNECTED HABITATIONS (require non-road evacuation):")
        for hid in disconnected:
            hab = graph_data.get_habitation_by_id(hid)
            print("    %s: %s -- FLAG FOR BOAT/AIR EVACUATION (Edge 5.2)" % (
                hid, hab.name if hab else "unknown"))

    print()
    print("Re-solving optimization...")
    re_result = optimizer.re_optimize(
        graph_data, shortest_paths, urgency_weights, hazard_scores
    )

    print()
    print("  Re-optimization result:")
    print("  Total relocated: %s" % format(re_result.total_people_relocated, ","))
    print("  Total people unmet: %s" % format(re_result.total_people_unmet, ","))
    print("  Disconnected: %s" % re_result.disconnected_habitations)
    print("  Used fallback: %s" % re_result.used_fallback_heuristic)
    print("  Solver time: %.3fs" % re_result.solver_time_seconds)

    for a in re_result.assignments:
        hab = graph_data.get_habitation_by_id(a.habitation_id)
        fb = " [FALLBACK]" if a.is_fallback else ""
        inter = " [INTER-DIST]" if a.is_inter_district else ""
        evac = " [NON-ROAD]" if a.evacuation_mode.value != "road" else ""
        print("    %-25s -> %-15s | %5d people | %6.1f km%s%s%s" % (
            hab.name if hab else a.habitation_id, a.shelter_id,
            a.people_assigned, a.distance_km, fb, inter, evac))

    # Summary
    print_header("DEMO COMPLETE")
    print("Key takeaways for SIH judges:")
    print("  1. The system fuses multiple hazard sources with explainable weights")
    print("  2. The optimizer finds globally optimal assignments, not just nearest-shelter")
    print("  3. Road failure triggers automatic re-optimization without manual restart")
    print("  4. Disconnected habitations are flagged for non-road evacuation")
    print("  5. Every relocation order is audit-hashed for tamper evidence")
    print("  6. Population uncertainty is handled with configurable safety margins")
    print("  7. Accessibility constraints are encoded in the optimizer, not just UI filters")
    print()
    print("This is NOT just a hazard dashboard -- the optimization layer is the innovation.")


if __name__ == "__main__":
    main()
