"""
Core domain models for LocaTS.

These define the shared data structures across all four layers:
Hazard Fusion, Carrying Capacity, Optimization, and Delivery.
"""

from __future__ import annotations

import hashlib
import time
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class HazardType(str, Enum):
    FLOOD = "flood"
    LANDSLIDE = "landslide"
    SEISMIC = "seismic"
    CYCLONE = "cyclone"


class AlertLevel(str, Enum):
    NORMAL = "normal"
    ADVISORY = "advisory"
    EVACUATE = "evacuate"
    RELOCATE = "relocate"


class RoadStatus(str, Enum):
    OPEN = "open"
    DEGRADED = "degraded"
    BLOCKED = "blocked"


class EvacuationMode(str, Enum):
    ROAD = "road"
    BOAT = "boat"
    AIR = "air"


# ---------------------------------------------------------------------------
# Geo primitives
# ---------------------------------------------------------------------------

class Coordinates(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)


# ---------------------------------------------------------------------------
# Explainability models (Tier 1: Explainable Decision Layer)
# ---------------------------------------------------------------------------

class ExplanationFactor(BaseModel):
    """A single factor that contributed to a decision."""
    factor: str  # e.g. "satellite_flood_zone", "rainfall_intensity", "crowd_corroboration"
    weight: float  # 0.0 to 1.0 — how much this factor contributed
    value: float  # the raw value of this factor
    description: str = ""  # human-readable explanation


class DecisionExplanation(BaseModel):
    """Full explanation for why a decision was made."""
    decision_type: str  # "hazard_alert" or "shelter_assignment"
    factors: list[ExplanationFactor] = Field(default_factory=list)
    summary: str = ""  # one-sentence human-readable summary
    confidence_breakdown: dict = Field(default_factory=dict)


class ShelterComparison(BaseModel):
    """Why shelter A was chosen over shelter B."""
    shelter_id: str
    shelter_name: str
    distance_km: float
    beds_available: int
    is_accessible: bool
    score: float  # lower is better (cost * urgency)
    was_chosen: bool
    rejection_reason: str = ""  # e.g. "no route", "capacity full", "inaccessible"


# ---------------------------------------------------------------------------
# Hazard layer models
# ---------------------------------------------------------------------------

class StaticHazardZone(BaseModel):
    """A polygon or point from satellite/NDMA zonation data."""
    id: str
    hazard_type: HazardType
    severity: float = Field(..., ge=0.0, le=1.0, description="0=safe, 1=extreme")
    zone_type: str = "red"  # red / orange / yellow
    geom_wkt: Optional[str] = None  # WKT polygon for GIS interop
    center: Coordinates
    radius_km: float = Field(default=5.0, ge=0)


class CrowdReport(BaseModel):
    """A single community-submitted report from the PWA."""
    id: str
    reporter_id: str
    hazard_type: HazardType
    severity_estimate: float = Field(ge=0, le=1)
    description: str = ""
    location: Coordinates
    photo_hash: Optional[str] = None  # SHA-256 of photo, not the photo itself (PII)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    verified: bool = False
    corroboration_count: int = 0  # how many independent reports agree


class LiveSensorReading(BaseModel):
    """IMD rainfall, seismic feed, or other real-time telemetry."""
    source: str  # "imd_rainfall", "seismic", etc.
    location: Coordinates
    value: float  # mm rainfall, Richter scale, etc.
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    is_stale: bool = False
    staleness_minutes: float = 0.0


class HazardConfidence(BaseModel):
    """Per-habitation fused hazard confidence score."""
    habitation_id: str
    hazard_type: HazardType
    confidence: float = Field(ge=0.0, le=1.0)
    alert_level: AlertLevel
    component_scores: dict = Field(default_factory=dict, description="Breakdown: static, sensor, crowd weights")
    explanation: Optional[DecisionExplanation] = None  # Tier 1: explainability
    is_stale: bool = False
    staleness_minutes: float = 0.0
    last_updated: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Habitation cluster models
# ---------------------------------------------------------------------------

class SocialVulnerability(BaseModel):
    """Tier 2: Social vulnerability index per habitation cluster."""
    elderly_fraction: float = Field(default=0.10, ge=0, le=1, description="% elderly (65+)")
    disability_fraction: float = Field(default=0.05, ge=0, le=1, description="% with disabilities")
    single_income_fraction: float = Field(default=0.20, ge=0, le=1, description="% single-income households")
    non_native_language_fraction: float = Field(default=0.05, ge=0, le=1, description="% non-dominant language speakers")
    child_fraction: float = Field(default=0.25, ge=0, le=1, description="% children under 12")

    @property
    def vulnerability_index(self) -> float:
        """Composite vulnerability score (0-1). Higher = more vulnerable."""
        return min(1.0, (
            self.elderly_fraction * 0.25 +
            self.disability_fraction * 0.30 +
            self.single_income_fraction * 0.15 +
            self.non_native_language_fraction * 0.15 +
            self.child_fraction * 0.15
        ))

    @property
    def evacuation_difficulty(self) -> str:
        """Label for evacuation difficulty based on vulnerability."""
        vi = self.vulnerability_index
        if vi >= 0.4:
            return "high"
        elif vi >= 0.25:
            return "moderate"
        else:
            return "low"


class HabitationCluster(BaseModel):
    """A group of nearby habitations treated as one evacuation unit."""
    id: str
    name: str
    location: Coordinates
    population_estimate: int = Field(ge=0)
    population_confidence: float = Field(default=0.8, ge=0, le=1)
    has_accessible_population: bool = True
    accessible_population_fraction: float = Field(default=0.12, ge=0, le=1)
    elevation_m: Optional[float] = None
    district: str = ""
    block: str = ""
    social_vulnerability: Optional[SocialVulnerability] = None  # Tier 2


# ---------------------------------------------------------------------------
# Carrying capacity models
# ---------------------------------------------------------------------------

class Shelter(BaseModel):
    id: str
    name: str
    location: Coordinates
    bed_capacity: int = Field(ge=0)
    beds_occupied: int = Field(default=0, ge=0)
    healthcare_beds_per_hour: float = Field(default=0, ge=0)
    water_capacity_liters_per_day: float = Field(default=0, ge=0)
    is_accessible: bool = True  # NDMA disability-inclusive
    shelter_type: str = "school"  # school, community_hall, govt_building, tent
    district: str = ""
    hazard_zone_ids: list[str] = Field(default_factory=list)  # multi-hazard check
    is_active: bool = True  # False if shelter is itself in a hazard zone

    @property
    def beds_available(self) -> int:
        return max(0, self.bed_capacity - self.beds_occupied)

    @property
    def water_per_person_liters(self) -> float:
        return self.water_capacity_liters_per_day


class ResourceForecast(BaseModel):
    """Tier 2: Resource shortfall forecasting at a shelter."""
    shelter_id: str
    current_occupancy: int
    bed_capacity: int
    water_capacity_lpd: float
    healthcare_beds_per_hour: float
    estimated_inflow_per_hour: float = 0
    hours_until_water_shortage: Optional[float] = None
    hours_until_bed_shortage: Optional[float] = None
    hours_until_healthcare_shortage: Optional[float] = None
    warning_level: str = "ok"  # ok, watch, warning, critical


class RoadSegment(BaseModel):
    id: str
    from_node: str  # habitation or shelter id
    to_node: str
    distance_km: float = Field(ge=0)
    travel_time_minutes: float = Field(ge=0)
    capacity_vehicles_per_hour: float = Field(ge=0)
    people_throughput_per_hour: float = Field(ge=0)
    status: RoadStatus = RoadStatus.OPEN
    damage_factor: float = Field(default=1.0, ge=0, le=1, description="1=fully functional, 0=destroyed")

    @property
    def effective_throughput(self) -> float:
        return self.people_throughput_per_hour * self.damage_factor

    @property
    def is_usable(self) -> bool:
        return self.status != RoadStatus.BLOCKED and self.damage_factor > 0.01


class CapacityGraph(BaseModel):
    """The full graph of habitations, shelters, and road segments."""
    habitations: list[HabitationCluster] = Field(default_factory=list)
    shelters: list[Shelter] = Field(default_factory=list)
    road_segments: list[RoadSegment] = Field(default_factory=list)

    def get_shelter_by_id(self, shelter_id: str) -> Optional[Shelter]:
        for s in self.shelters:
            if s.id == shelter_id:
                return s
        return None

    def get_habitation_by_id(self, hab_id: str) -> Optional[HabitationCluster]:
        for h in self.habitations:
            if h.id == hab_id:
                return h
        return None

    def blocked_shelter_ids(self) -> set[str]:
        """Shelters that are themselves in a hazard zone (multi-hazard overlap, edge 5.12)."""
        return {s.id for s in self.shelters if not s.is_active}


# ---------------------------------------------------------------------------
# Optimization result models
# ---------------------------------------------------------------------------

class RelocationAssignment(BaseModel):
    """One habitation cluster assigned to one shelter with a routing path."""
    habitation_id: str
    shelter_id: str
    people_assigned: int = Field(ge=0)
    distance_km: float = Field(ge=0)
    travel_time_minutes: float = Field(ge=0)
    cost: float = Field(ge=0, description="distance * urgency_weight")
    is_fallback: bool = False  # True if greedy heuristic was used (edge 5.11)
    is_inter_district: bool = False  # True if crossing district boundary (edge 5.13)
    evacuation_mode: EvacuationMode = EvacuationMode.ROAD
    requires_special_transport: bool = False  # edge 5.7
    explanation: Optional[DecisionExplanation] = None  # Tier 1: why this assignment
    shelter_comparison: list[ShelterComparison] = Field(default_factory=list)  # Tier 1: why not other shelters


class OptimizationResult(BaseModel):
    """Complete output of one optimization run."""
    run_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    assignments: list[RelocationAssignment] = Field(default_factory=list)
    total_cost: float = 0
    total_people_relocated: int = 0
    total_people_unmet: int = 0  # edge 5.1
    unmet_habitations: list[str] = Field(default_factory=list)
    disconnected_habitations: list[str] = Field(default_factory=list)  # edge 5.2
    accessibility_gap_habitations: list[str] = Field(default_factory=list)  # edge 5.7
    inter_district_assignments: list[str] = Field(default_factory=list)  # edge 5.13
    used_fallback_heuristic: bool = False  # edge 5.11
    solver_time_seconds: float = 0
    is_feasible: bool = True
    unsatisfied_shelter_capacity: dict[str, int] = Field(default_factory=dict)
    resource_forecasts: list[ResourceForecast] = Field(default_factory=list)  # Tier 2

    def compute_audit_hash(self) -> str:
        """Lightweight tamper-evident hash of the relocation order."""
        payload = f"{self.run_id}:{self.timestamp.isoformat()}:{self.total_cost}:{self.total_people_relocated}"
        return hashlib.sha256(payload.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Alert models
# ---------------------------------------------------------------------------

class Alert(BaseModel):
    id: str
    habitation_id: str
    alert_level: AlertLevel
    hazard_type: HazardType
    confidence: float
    message: str = ""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    acknowledged: bool = False


# ---------------------------------------------------------------------------
# PWA crowd report sync models (edge 5.9)
# ---------------------------------------------------------------------------

class OfflineReport(BaseModel):
    """Report submitted offline; sync uses last-write-wins conflict resolution."""
    client_id: str  # device id
    report: CrowdReport
    client_timestamp: float = Field(default_factory=time.time)
    sync_status: str = "pending"  # pending, synced, conflict


class RelocationOrder(BaseModel):
    """Official relocation order with audit trail."""
    order_id: str
    result: OptimizationResult
    issued_at: datetime = Field(default_factory=datetime.utcnow)
    issued_by: str = "system"
    audit_hash: str = ""
    hash_chain_previous: str = ""  # hash of previous order for chain integrity

    def compute_hash(self) -> str:
        payload = f"{self.order_id}:{self.issued_at.isoformat()}:{self.result.run_id}"
        return hashlib.sha256(payload.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Historical backtesting models (Tier 1)
# ---------------------------------------------------------------------------

class HistoricalEvent(BaseModel):
    """A historical disaster event for backtesting."""
    event_id: str
    name: str
    district: str
    state: str
    hazard_type: HazardType
    date: str  # ISO date string
    description: str
    affected_habitations: list[str] = Field(default_factory=list)
    actual_casualties: int = 0
    actual_displaced: int = 0


class BacktestResult(BaseModel):
    """Result of running the system against a historical event."""
    event_id: str
    system_flagged_habitations: list[str] = Field(default_factory=list)
    actual_affected_habitations: list[str] = Field(default_factory=list)
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    early_warning_hours: float = 0  # how many hours earlier the system would have flagged
    hypothetical_displacement_reduction: float = 0  # % reduction in avg displacement distance
    hypothetical_people_better_served: int = 0
    explanation: str = ""


# ---------------------------------------------------------------------------
# Family Reunification Tracking (Item 6)
# ---------------------------------------------------------------------------

class EvacueeRegistration(BaseModel):
    """An anonymized evacuee registered at a shelter during intake."""
    evacuee_id: str = Field(default="", description="Unique anonymized ID (QR code)")
    family_group_id: Optional[str] = None  # links family members
    name_hash: str = Field(default="", description="SHA-256 of name for privacy")
    age_range: str = ""  # "child", "adult", "elderly"
    needs_medical: bool = False
    needs_accessibility: bool = False
    home_habitation_id: str = ""  # where they came from
    home_lat: Optional[float] = None
    home_lon: Optional[float] = None
    registered_shelter_id: str = ""
    registered_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = "safe"  # safe, missing, hospitalized, deceased
    notes: str = ""


class FamilySearch(BaseModel):
    """Search query to find a family member across shelters."""
    search_name: str = Field(..., description="Name to search (hashed server-side)")
    home_habitation_id: Optional[str] = None
    age_range: Optional[str] = None


class FamilySearchResult(BaseModel):
    """Result of a family member search."""
    evacuee_id: str
    shelter_id: str
    shelter_name: str = ""
    status: str
    registered_at: datetime
    name_hash: str  # so searcher can confirm match
    is_match: bool = False  # server-verified match
    message: str = ""


class EvacueeStatusUpdate(BaseModel):
    """Update evacuee status (safe, missing, hospitalized)."""
    evacuee_id: str
    new_status: str
    notes: str = ""


class IVRSession(BaseModel):
    """A simulated IVR phone session for demo."""
    session_id: str
    caller_id: str = ""
    language: str = "en"  # en, hi, ta, te, etc.
    current_step: str = "greeting"
    responses: list[dict] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
