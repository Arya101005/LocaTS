"""
Optimization Layer - CORE INNOVATION.

Formulates relocation as a capacitated min-cost flow / assignment problem:
  - Source nodes: habitation clusters (supply = buffered population)
  - Sink nodes: shelters (demand = available bed capacity)
  - Edges: road paths with cost = distance x urgency_weight
  - Constraints: shelter capacity, road throughput, accessibility

Key differentiator: ROLLING-HORIZON RE-OPTIMIZATION
  When a road segment or shelter capacity changes, re-solve within a bounded
  time budget. No full manual restart needed.

Edge case handling:
  - 5.1: Infeasible optimization -> relaxed equitable allocation
  - 5.2: Disconnected graph -> flag non-road evacuation needs
  - 5.5: Race conditions -> atomic capacity bookkeeping via locks
  - 5.7: Accessibility infeasibility -> flag as capacity gap
  - 5.11: Solver time-budget -> greedy heuristic fallback
  - 5.13: Cross-district -> flag inter-district coordination
"""

from __future__ import annotations

import time
import threading
import uuid
from datetime import datetime
from typing import Optional

from ortools.graph.python import min_cost_flow as mcf

from backend.app.models.domain import (
    AlertLevel,
    CapacityGraph,
    DecisionExplanation,
    EvacuationMode,
    ExplanationFactor,
    HabitationCluster,
    OptimizationResult,
    RelocationAssignment,
    ResourceForecast,
    RoadSegment,
    Shelter,
    ShelterComparison,
)


class OptimizationEngine:
    """
    Capacitated relocation optimizer with rolling-horizon support.

    Uses Google OR-Tools MinCostFlow for the primary solver, with:
      - Time-budget enforcement (edge 5.11)
      - Greedy heuristic fallback
      - Infeasibility detection and relaxed allocation (edge 5.1)
      - Atomic capacity bookkeeping (edge 5.5)
    """

    DEFAULT_TIME_BUDGET_SECONDS = 30.0
    POPULATION_UNIT = 10  # Finer granularity for better optimization

    def __init__(
        self,
        time_budget_seconds: float = DEFAULT_TIME_BUDGET_SECONDS,
        population_unit: int = POPULATION_UNIT,
        enable_explanations: bool = True,
        social_vulnerability_weight: float = 0.15,
    ):
        self.time_budget_seconds = time_budget_seconds
        self.population_unit = population_unit
        self.enable_explanations = enable_explanations
        self.social_vulnerability_weight = social_vulnerability_weight
        self._capacity_lock = threading.RLock()
        self._last_result: Optional[OptimizationResult] = None
        self._shortfall_cooldown: dict[str, dict] = {}  # hysteresis for shortfall feedback

    def solve(
        self,
        graph_data: CapacityGraph,
        shortest_paths: dict[tuple[str, str], dict],
        urgency_weights: Optional[dict[str, float]] = None,
        current_hazard_confidences: Optional[dict[str, float]] = None,
    ) -> OptimizationResult:
        """Main entry point. Returns OptimizationResult with edge-case annotations."""
        start_time = time.time()
        run_id = str(uuid.uuid4())[:8]

        if urgency_weights is None:
            urgency_weights = {}
        if current_hazard_confidences is None:
            current_hazard_confidences = {}

        disconnected = self._find_disconnected_habitations(graph_data, shortest_paths)
        solvable_habs = [h for h in graph_data.habitations if h.id not in disconnected]
        active_shelters = [s for s in graph_data.shelters if s.is_active]

        if not active_shelters:
            return self._empty_result(run_id, graph_data, disconnected, time.time() - start_time)

        total_demand = sum(h.population_estimate for h in solvable_habs)
        total_capacity = sum(s.beds_available for s in active_shelters)

        # Shortfall feedback with hysteresis (Edge Case 4 from EDGE_CASES.md)
        # Reduce effective capacity for shelters predicted to fill within 4 hours
        # Only restore capacity when predicted exhaustion > 8 hours (asymmetric bounds)
        now_ts = time.time()
        for s in active_shelters:
            available = s.bed_capacity - s.beds_occupied
            if available <= 0:
                continue
            # Predict hours to full (assume 10% arrival rate per hour during active evacuation)
            arrival_rate = max(1, available * 0.1)
            hours_to_full = available / arrival_rate
            shelter_key = s.id
            last_adjustment = self._shortfall_cooldown.get(shelter_key, {}).get('ts', 0)
            last_action = self._shortfall_cooldown.get(shelter_key, {}).get('action', None)
            cooldown_active = (now_ts - last_adjustment) < 900  # 15 min cooldown

            if cooldown_active:
                continue  # Skip — still in cooldown

            if hours_to_full < 4 and last_action != 'reduced':
                # Reduce capacity by 20% as safety margin
                reduction = int(available * 0.2)
                if reduction > 0:
                    s.beds_occupied += reduction
                    self._shortfall_cooldown[shelter_key] = {'ts': now_ts, 'action': 'reduced'}
            elif hours_to_full > 8 and last_action == 'reduced':
                # Restore previously reduced capacity
                reduction = int(s.bed_capacity * 0.2 * 0.5)  # Restore half of the 20%
                if reduction > 0 and s.beds_occupied >= reduction:
                    s.beds_occupied -= reduction
                    self._shortfall_cooldown[shelter_key] = {'ts': now_ts, 'action': 'restored'}
        solver_time_start = time.time()
        solver_timed_out = False
        used_fallback = False

        try:
            if time.time() + self.time_budget_seconds > time.time():
                assignments, used_fallback = self._solve_mincostflow(
                    solvable_habs, active_shelters, shortest_paths,
                    urgency_weights, current_hazard_confidences,
                    deadline=time.time() + self.time_budget_seconds,
                )
            else:
                raise TimeoutError("No time budget remaining")
        except Exception:
            assignments = self._greedy_fallback(
                solvable_habs, active_shelters, shortest_paths, urgency_weights
            )
            used_fallback = True
            solver_timed_out = True

        solver_time = time.time() - solver_time_start

        if not assignments:
            assignments = self._greedy_fallback(
                solvable_habs, active_shelters, shortest_paths, urgency_weights
            )
            used_fallback = True

        # Post-solver: assign remainder people lost to integer division in MCF
        if not used_fallback and assignments:
            remaining_capacity = {s.id: s.beds_available for s in active_shelters}
            for a in assignments:
                remaining_capacity[a.shelter_id] = remaining_capacity.get(a.shelter_id, 0) - a.people_assigned
            for hab in solvable_habs:
                assigned_to_hab = sum(a.people_assigned for a in assignments if a.habitation_id == hab.id)
                remainder = hab.population_estimate - assigned_to_hab
                if remainder > 0:
                    # Try to add remainder to best existing assignment
                    existing = [a for a in assignments if a.habitation_id == hab.id]
                    if existing:
                        # Sort shelters by distance, find one with capacity
                        candidates = []
                        for shelter in active_shelters:
                            key = (hab.id, shelter.id)
                            p = shortest_paths.get(key, {})
                            if p.get('feasible', False) and remaining_capacity.get(shelter.id, 0) >= remainder:
                                candidates.append((shelter, p, remainder))
                            elif p.get('feasible', False) and remaining_capacity.get(shelter.id, 0) > 0:
                                partial = remaining_capacity.get(shelter.id, 0)
                                candidates.append((shelter, p, partial))
                        candidates.sort(key=lambda x: x[1].get('distance_km', float('inf')))
                        leftover = remainder
                        for shelter, p, take in candidates:
                            if leftover <= 0:
                                break
                            take = min(take, leftover)
                            assignments.append(RelocationAssignment(
                                habitation_id=hab.id, shelter_id=shelter.id,
                                people_assigned=take,
                                distance_km=round(p.get('distance_km', 0), 2),
                                travel_time_minutes=round(p.get('travel_time_minutes', 0), 1),
                                cost=round(p.get('distance_km', 0) * take, 2),
                                is_fallback=False,
                                is_inter_district=bool(
                                    hab.district and shelter.district and hab.district != shelter.district
                                ),
                            ))
                            remaining_capacity[shelter.id] -= take
                            leftover -= take

        total_relocated = sum(a.people_assigned for a in assignments)
        total_unmet = total_demand - total_relocated
        unmet_habs = self._find_unmet_habitations(solvable_habs, assignments)
        accessibility_gaps = self._find_accessibility_gaps(graph_data, assignments, shortest_paths)
        inter_district = self._find_inter_district_assignments(graph_data, assignments)

        unmet_capacity = {}
        for shelter in active_shelters:
            assigned_to = sum(a.people_assigned for a in assignments if a.shelter_id == shelter.id)
            remaining = shelter.beds_available - assigned_to
            if remaining < 0:
                unmet_capacity[shelter.id] = abs(remaining)

        total_cost = sum(a.cost for a in assignments)
        elapsed = time.time() - start_time

        # Generate explanations for assignments (Tier 1)
        if self.enable_explanations:
            assignments = self._add_assignment_explanations(
                assignments, graph_data, shortest_paths, urgency_weights, current_hazard_confidences
            )

        # Generate resource forecasts (Tier 2)
        resource_forecasts = self._forecast_resources(graph_data, assignments)

        result = OptimizationResult(
            run_id=run_id,
            timestamp=datetime.utcnow(),
            assignments=assignments,
            total_cost=round(total_cost, 2),
            total_people_relocated=total_relocated,
            total_people_unmet=max(0, total_unmet),
            unmet_habitations=unmet_habs,
            disconnected_habitations=disconnected,
            accessibility_gap_habitations=accessibility_gaps,
            inter_district_assignments=inter_district,
            used_fallback_heuristic=used_fallback,
            solver_time_seconds=round(solver_time, 3),
            is_feasible=(total_unmet <= max(1, total_demand * 0.01) and not solver_timed_out),
            unsatisfied_shelter_capacity=unmet_capacity,
            resource_forecasts=resource_forecasts,
        )

        self._last_result = result
        return result

    def re_optimize(
        self,
        graph_data: CapacityGraph,
        shortest_paths: dict[tuple[str, str], dict],
        urgency_weights: Optional[dict[str, float]] = None,
        current_hazard_confidences: Optional[dict[str, float]] = None,
    ) -> OptimizationResult:
        """Rolling-horizon re-optimization with atomic capacity bookkeeping (edge 5.5)."""
        with self._capacity_lock:
            if self._last_result:
                for shelter in graph_data.shelters:
                    shelter.beds_occupied = 0

            return self.solve(
                graph_data, shortest_paths, urgency_weights, current_hazard_confidences
            )

    # -----------------------------------------------------------------------
    # OR-Tools Min-Cost Flow solver
    # -----------------------------------------------------------------------

    def _solve_mincostflow(
        self,
        habitations: list[HabitationCluster],
        shelters: list[Shelter],
        shortest_paths: dict[tuple[str, str], dict],
        urgency_weights: dict[str, float],
        hazard_confidences: dict[str, float],
        deadline: float,
    ) -> tuple[list[RelocationAssignment], bool]:
        """
        Transportation problem formulation using OR-Tools SimpleMinCostFlow.

        OR-Tools MCF requires total supply == total demand (balanced).
        We add a dummy sink node to absorb excess demand/supply at zero cost.
        """
        if time.time() > deadline:
            raise TimeoutError("Solver time budget exceeded")

        total_supply = sum(max(1, h.population_estimate // self.population_unit) for h in habitations)
        total_demand = sum(max(1, s.beds_available // self.population_unit) for s in shelters)

        smf = mcf.SimpleMinCostFlow()

        n_hab = len(habitations)
        n_shelter = len(shelters)
        # Dummy node index for balancing
        dummy_node = n_hab + n_shelter

        # Set supply/demand for habitation nodes (positive = supply)
        for i, hab in enumerate(habitations):
            supply = max(1, hab.population_estimate // self.population_unit)
            smf.set_node_supply(i, supply)

        # Set supply/demand for shelter nodes (negative = demand)
        for j, shelter in enumerate(shelters):
            node_id = n_hab + j
            demand = max(1, shelter.beds_available // self.population_unit)
            smf.set_node_supply(node_id, -demand)

        # Balance: add dummy node to absorb the difference
        # When supply > demand: dummy is demand node (absorbs excess supply)
        # When supply < demand: dummy is supply node (fills unmet demand)
        balance = total_supply - total_demand
        smf.set_node_supply(dummy_node, -balance)  # negative = demand when supply > demand

        # Add arcs from each habitation to each shelter
        for i, hab in enumerate(habitations):
            for j, shelter in enumerate(shelters):
                key = (hab.id, shelter.id)
                path_info = shortest_paths.get(key, {})
                if not path_info.get("feasible", False):
                    continue

                dist = path_info.get("distance_km", float("inf"))
                if dist == float("inf") or dist <= 0:
                    continue

                urgency = urgency_weights.get(hab.id, 1.0)
                confidence = hazard_confidences.get(hab.id, 0.5)

                # Integer cost for OR-Tools (scale by 100)
                cost = max(1, int(dist * urgency * 100 * (1.0 + confidence)))

                hab_supply = max(1, hab.population_estimate // self.population_unit)
                shelter_demand = max(1, shelter.beds_available // self.population_unit)
                arc_capacity = hab_supply + shelter_demand  # Allow full flow

                smf.add_arc_with_capacity_and_unit_cost(i, n_hab + j, arc_capacity, cost)

                if time.time() > deadline:
                    raise TimeoutError("Solver time budget exceeded during model building")

        # Add arcs connecting to dummy node
        dummy_cost = 100000  # Very high cost to discourage unassignment
        if balance > 0:
            # Supply > Demand: dummy absorbs excess supply from habitations
            for i, hab in enumerate(habitations):
                hab_supply = max(1, hab.population_estimate // self.population_unit)
                smf.add_arc_with_capacity_and_unit_cost(i, dummy_node, hab_supply, dummy_cost)
        elif balance < 0:
            # Demand > Supply: dummy fills unmet demand at shelters
            for j, shelter in enumerate(shelters):
                shelter_demand = max(1, shelter.beds_available // self.population_unit)
                smf.add_arc_with_capacity_and_unit_cost(dummy_node, n_hab + j, shelter_demand, dummy_cost)

        # Solve
        status = smf.solve()

        if status not in (mcf.SimpleMinCostFlow.OPTIMAL, mcf.SimpleMinCostFlow.FEASIBLE):
            return [], True

        # Extract assignments (skip dummy arcs)
        assignments = []
        for arc_idx in range(smf.num_arcs()):
            flow = smf.flow(arc_idx)
            if flow <= 0:
                continue

            from_node = smf.tail(arc_idx)
            to_node = smf.head(arc_idx)

            # Skip dummy node arcs
            if from_node == dummy_node or to_node == dummy_node:
                continue
            # Only care about habitation -> shelter arcs
            if from_node >= n_hab or to_node < n_hab:
                continue

            hab_idx = from_node
            shelter_idx = to_node - n_hab

            hab = habitations[hab_idx]
            shelter = shelters[shelter_idx]
            people = flow * self.population_unit

            key = (hab.id, shelter.id)
            path_info = shortest_paths.get(key, {})
            dist = path_info.get("distance_km", 0)

            urgency = urgency_weights.get(hab.id, 1.0)
            confidence = hazard_confidences.get(hab.id, 0.5)
            cost = dist * urgency * (1.0 + confidence) * people

            assignments.append(RelocationAssignment(
                habitation_id=hab.id,
                shelter_id=shelter.id,
                people_assigned=people,
                distance_km=round(dist, 2),
                travel_time_minutes=round(path_info.get("travel_time_minutes", dist * 2), 1),
                cost=round(cost, 2),
                is_fallback=False,
                is_inter_district=bool(
                    hab.district and shelter.district and hab.district != shelter.district
                ),
            ))

        return assignments, False

    # -----------------------------------------------------------------------
    # Greedy fallback heuristic (edge 5.11)
    # -----------------------------------------------------------------------

    def _greedy_fallback(
        self,
        habitations: list[HabitationCluster],
        shelters: list[Shelter],
        shortest_paths: dict[tuple[str, str], dict],
        urgency_weights: dict[str, float],
    ) -> list[RelocationAssignment]:
        """
        Fast greedy nearest-feasible-shelter assignment.
        Labeled as heuristic-fallback in output (edge 5.11).
        """
        assignments = []
        remaining_capacity = {s.id: s.beds_available for s in shelters}

        sorted_habs = sorted(
            habitations,
            key=lambda h: urgency_weights.get(h.id, 1.0) * h.population_estimate,
            reverse=True,
        )

        for hab in sorted_habs:
            candidates = []
            for shelter in shelters:
                if remaining_capacity.get(shelter.id, 0) <= 0:
                    continue
                key = (hab.id, shelter.id)
                path_info = shortest_paths.get(key, {})
                if not path_info.get("feasible", False):
                    continue
                candidates.append((shelter, path_info))

            if not candidates:
                continue

            candidates.sort(key=lambda x: x[1].get("distance_km", float("inf")))

            people_remaining = hab.population_estimate
            for shelter, path_info in candidates:
                if people_remaining <= 0:
                    break
                beds = remaining_capacity[shelter.id]
                if beds <= 0:
                    continue

                assign_count = min(people_remaining, beds)
                dist = path_info.get("distance_km", 0)
                urgency = urgency_weights.get(hab.id, 1.0)
                confidence = 0.5
                cost = dist * urgency * (1.0 + confidence) * assign_count

                assignments.append(RelocationAssignment(
                    habitation_id=hab.id,
                    shelter_id=shelter.id,
                    people_assigned=assign_count,
                    distance_km=round(dist, 2),
                    travel_time_minutes=round(
                        path_info.get("travel_time_minutes", dist * 2), 1
                    ),
                    cost=round(cost, 2),
                    is_fallback=True,
                    is_inter_district=bool(
                        hab.district and shelter.district
                        and hab.district != shelter.district
                    ),
                ))

                remaining_capacity[shelter.id] -= assign_count
                people_remaining -= assign_count

        return assignments

    # -----------------------------------------------------------------------
    # Tier 1: Explainable decision layer
    # -----------------------------------------------------------------------

    def _add_assignment_explanations(
        self,
        assignments: list[RelocationAssignment],
        graph_data: CapacityGraph,
        shortest_paths: dict,
        urgency_weights: dict,
        hazard_confidences: dict,
    ) -> list[RelocationAssignment]:
        """Add WHY explanations to each assignment."""
        enriched = []
        for a in assignments:
            hab = graph_data.get_habitation_by_id(a.habitation_id)
            shelter = graph_data.get_shelter_by_id(a.shelter_id)
            if not hab or not shelter:
                enriched.append(a)
                continue

            # Build comparison of all candidate shelters
            comparisons = self._compare_shelters(
                hab, graph_data.shelters, shortest_paths, urgency_weights, a.shelter_id
            )

            # Build explanation factors
            factors = []
            urgency = urgency_weights.get(hab.id, 1.0)
            confidence = hazard_confidences.get(hab.id, 0.5)
            vi = hab.social_vulnerability.vulnerability_index if hab.social_vulnerability else 0.0

            factors.append(ExplanationFactor(
                factor="distance",
                weight=1.0 / (1.0 + a.distance_km),
                value=a.distance_km,
                description=f"Distance to shelter: {a.distance_km:.1f}km",
            ))

            factors.append(ExplanationFactor(
                factor="urgency",
                weight=urgency,
                value=urgency,
                description=f"Urgency weight: {urgency:.2f} (based on hazard confidence {confidence:.2f})",
            ))

            factors.append(ExplanationFactor(
                factor="capacity",
                weight=shelter.beds_available / max(1, shelter.bed_capacity),
                value=shelter.beds_available,
                description=f"Shelter beds available: {shelter.beds_available}/{shelter.bed_capacity}",
            ))

            if hab.social_vulnerability:
                factors.append(ExplanationFactor(
                    factor="social_vulnerability",
                    weight=vi,
                    value=vi,
                    description=(
                        f"Social vulnerability index: {vi:.2f} ({hab.social_vulnerability.evacuation_difficulty}). "
                        f"Elderly: {hab.social_vulnerability.elderly_fraction:.0%}, "
                        f"Disability: {hab.social_vulnerability.disability_fraction:.0%}, "
                        f"Children: {hab.social_vulnerability.child_fraction:.0%}"
                    ),
                ))

            if not shelter.is_accessible:
                factors.append(ExplanationFactor(
                    factor="accessibility",
                    weight=0.0,
                    value=0.0,
                    description="WARNING: Assigned shelter is NOT accessible. Mobility-impaired evacuees need special transport.",
                ))

            # Build summary
            why_chosen = self._explain_why_chosen(a, hab, shelter, comparisons)

            explanation = DecisionExplanation(
                decision_type="shelter_assignment",
                factors=factors,
                summary=why_chosen,
                confidence_breakdown={
                    "distance_km": a.distance_km,
                    "urgency_weight": urgency,
                    "hazard_confidence": confidence,
                    "shelter_beds_available": shelter.beds_available,
                    "social_vulnerability": vi,
                },
            )

            enriched.append(a.model_copy(update={
                "explanation": explanation,
                "shelter_comparison": comparisons,
            }))

        return enriched

    def _compare_shelters(
        self,
        hab: HabitationCluster,
        shelters: list[Shelter],
        shortest_paths: dict,
        urgency_weights: dict,
        chosen_shelter_id: str,
    ) -> list[ShelterComparison]:
        """Compare all candidate shelters for a habitation."""
        comparisons = []
        urgency = urgency_weights.get(hab.id, 1.0)
        confidence = 0.5

        for shelter in shelters:
            key = (hab.id, shelter.id)
            path_info = shortest_paths.get(key, {})
            feasible = path_info.get("feasible", False)
            dist = path_info.get("distance_km", float("inf")) if feasible else float("inf")
            accessible = path_info.get("is_accessible", False)

            if feasible:
                cost = dist * urgency * (1.0 + confidence)
            else:
                cost = float("inf")

            # Determine rejection reason
            rejection = ""
            if not feasible:
                rejection = "No route available (road blocked or disconnected)"
            elif not shelter.is_active:
                rejection = "Shelter in hazard zone (multi-hazard overlap)"
            elif shelter.beds_available <= 0:
                rejection = "Capacity full"
            elif not accessible and hab.has_accessible_population:
                rejection = "Not accessible (mobility-impaired residents need alternative)"
            elif shelter.id != chosen_shelter_id:
                rejection = "Higher cost/risk score than chosen shelter"

            comparisons.append(ShelterComparison(
                shelter_id=shelter.id,
                shelter_name=shelter.name,
                distance_km=round(dist, 1) if dist != float("inf") else -1,
                beds_available=shelter.beds_available,
                is_accessible=shelter.is_accessible,
                score=round(cost, 1) if cost != float("inf") else -1,
                was_chosen=(shelter.id == chosen_shelter_id),
                rejection_reason=rejection if shelter.id != chosen_shelter_id else "Chosen",
            ))

        # Sort by score
        comparisons.sort(key=lambda c: c.score if c.score >= 0 else float("inf"))
        return comparisons

    def _explain_why_chosen(
        self,
        assignment: RelocationAssignment,
        hab: HabitationCluster,
        shelter: Shelter,
        comparisons: list[ShelterComparison],
    ) -> str:
        """Build a one-sentence explanation of why this shelter was chosen."""
        vi_info = ""
        if hab.social_vulnerability:
            vi = hab.social_vulnerability.vulnerability_index
            vi_info = f" Social vulnerability: {vi:.2f} ({hab.social_vulnerability.evacuation_difficulty})."

        rejected = [c for c in comparisons if not c.was_chosen and c.rejection_reason]
        better_options = [c for c in rejected if c.score >= 0 and c.score < assignment.cost]

        if assignment.is_inter_district:
            return (
                f"Assigned to {shelter.name} ({shelter.district}) because local capacity is insufficient. "
                f"Distance: {assignment.distance_km:.1f}km. "
                f"Cross-district coordination required."
            )

        if better_options:
            reasons = "; ".join(f"{c.shelter_name}: {c.rejection_reason}" for c in better_options[:2])
            return (
                f"Assigned to {shelter.name} at {assignment.distance_km:.1f}km. "
                f"Closer alternatives rejected: {reasons}.{vi_info}"
            )

        return (
            f"Assigned to nearest feasible shelter {shelter.name} at {assignment.distance_km:.1f}km. "
            f"Beds available: {shelter.beds_available}. "
            f"Accessible: {shelter.is_accessible}.{vi_info}"
        )

    # -----------------------------------------------------------------------
    # Tier 2: Resource shortfall forecasting
    # -----------------------------------------------------------------------

    def _forecast_resources(
        self,
        graph_data: CapacityGraph,
        assignments: list[RelocationAssignment],
    ) -> list[ResourceForecast]:
        """
        Forecast when each shelter will run out of resources.
        Simple inflow-rate extrapolation.
        """
        # Aggregate inflow per shelter
        shelter_inflows: dict[str, float] = {}
        for a in assignments:
            # People arriving per hour (travel_time / people gives arrival rate)
            if a.travel_time_minutes > 0:
                inflow = a.people_assigned / max(1, a.travel_time_minutes / 60.0)
            else:
                inflow = a.people_assigned  # instant arrival
            shelter_inflows[a.shelter_id] = shelter_inflows.get(a.shelter_id, 0) + inflow

        forecasts = []
        for shelter in graph_data.shelters:
            if not shelter.is_active:
                continue

            inflow = shelter_inflows.get(shelter.id, 0)
            current = shelter.beds_occupied
            capacity = shelter.bed_capacity
            water = shelter.water_capacity_liters_per_day
            healthcare = shelter.healthcare_beds_per_hour

            # Hours until each resource runs out
            remaining_beds = max(0, capacity - current)
            hours_bed = remaining_beds / max(1, inflow) if inflow > 0 else None

            # Water: assume 15 liters per person per day
            water_per_hour_per_person = 15.0 / 24.0
            water_capacity_per_hour = water / 24.0
            total_inflow_rate = inflow  # people per hour
            if total_inflow_rate > 0:
                hours_water = water_capacity_per_hour / (total_inflow_rate * water_per_hour_per_person)
            else:
                hours_water = None

            # Healthcare: 1 person per 50 needs medical attention per hour
            medical_needs_per_hour = total_inflow_rate * 0.02
            hours_healthcare = healthcare / max(0.01, medical_needs_per_hour) if medical_needs_per_hour > 0 else None

            # Warning level
            min_hours = min(
                h for h in [hours_bed, hours_water, hours_healthcare] if h is not None
            ) if any(h is not None for h in [hours_bed, hours_water, hours_healthcare]) else 999

            if min_hours < 2:
                warning = "critical"
            elif min_hours < 6:
                warning = "warning"
            elif min_hours < 12:
                warning = "watch"
            else:
                warning = "ok"

            forecasts.append(ResourceForecast(
                shelter_id=shelter.id,
                current_occupancy=current,
                bed_capacity=capacity,
                water_capacity_lpd=water,
                healthcare_beds_per_hour=healthcare,
                estimated_inflow_per_hour=round(inflow, 1),
                hours_until_water_shortage=round(hours_water, 1) if hours_water else None,
                hours_until_bed_shortage=round(hours_bed, 1) if hours_bed else None,
                hours_until_healthcare_shortage=round(hours_healthcare, 1) if hours_healthcare else None,
                warning_level=warning,
            ))

        return forecasts

    # -----------------------------------------------------------------------
    # Edge case detection helpers
    # -----------------------------------------------------------------------

    def _find_disconnected_habitations(
        self,
        graph_data: CapacityGraph,
        shortest_paths: dict[tuple[str, str], dict],
    ) -> list[str]:
        """Edge 5.2: Habitations with no path to any active shelter."""
        disconnected = []
        active_shelter_ids = {s.id for s in graph_data.shelters if s.is_active}

        for hab in graph_data.habitations:
            has_path = False
            for sid in active_shelter_ids:
                key = (hab.id, sid)
                if key in shortest_paths and shortest_paths[key].get("feasible", False):
                    has_path = True
                    break
            if not has_path and active_shelter_ids:
                disconnected.append(hab.id)

        return disconnected

    def _find_unmet_habitations(
        self,
        habitations: list[HabitationCluster],
        assignments: list[RelocationAssignment],
    ) -> list[str]:
        """Edge 5.1: Habitations where assigned people < population."""
        assigned_map: dict[str, int] = {}
        for a in assignments:
            assigned_map[a.habitation_id] = (
                assigned_map.get(a.habitation_id, 0) + a.people_assigned
            )

        return [
            hab.id for hab in habitations
            if assigned_map.get(hab.id, 0) < hab.population_estimate
        ]

    def _find_accessibility_gaps(
        self,
        graph_data: CapacityGraph,
        assignments: list[RelocationAssignment],
        shortest_paths: dict[tuple[str, str], dict],
    ) -> list[str]:
        """Edge 5.7: No accessible shelter within safe travel distance."""
        gaps = []
        for hab in graph_data.habitations:
            if not hab.has_accessible_population:
                continue

            has_accessible = False
            for shelter in graph_data.shelters:
                if not shelter.is_active or not shelter.is_accessible:
                    continue
                key = (hab.id, shelter.id)
                path_info = shortest_paths.get(key, {})
                if path_info.get("feasible", False) and path_info.get("is_accessible", False):
                    has_accessible = True
                    break

            if not has_accessible:
                gaps.append(hab.id)

        return gaps

    def _find_inter_district_assignments(
        self,
        graph_data: CapacityGraph,
        assignments: list[RelocationAssignment],
    ) -> list[str]:
        """Edge 5.13: Flag assignments that cross district boundaries."""
        inter = []
        for a in assignments:
            hab = graph_data.get_habitation_by_id(a.habitation_id)
            shelter = graph_data.get_shelter_by_id(a.shelter_id)
            if hab and shelter and hab.district and shelter.district:
                if hab.district != shelter.district:
                    inter.append(a.habitation_id)
        return list(set(inter))

    def _empty_result(
        self,
        run_id: str,
        graph_data: CapacityGraph,
        disconnected: list[str],
        elapsed: float,
    ) -> OptimizationResult:
        return OptimizationResult(
            run_id=run_id,
            timestamp=datetime.utcnow(),
            assignments=[],
            total_cost=0,
            total_people_relocated=0,
            total_people_unmet=sum(h.population_estimate for h in graph_data.habitations),
            unmet_habitations=[h.id for h in graph_data.habitations],
            disconnected_habitations=disconnected,
            used_fallback_heuristic=True,
            solver_time_seconds=round(elapsed, 3),
            is_feasible=False,
        )
