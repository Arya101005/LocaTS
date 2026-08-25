"""
Hazard Fusion Layer.

Combines three signal sources into a single per-habitation hazard confidence score:
  1. Static satellite zonation (Bhuvan/NDMA) — highest baseline trust
  2. Live sensor feeds (IMD rainfall, seismic) — time-decaying trust
  3. Crowd reports — corroboration-gated trust

Tier 1: Every score includes a DecisionExplanation with factor-level detail.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta

from backend.app.models.domain import (
    AlertLevel,
    Coordinates,
    CrowdReport,
    DecisionExplanation,
    ExplanationFactor,
    HazardConfidence,
    HazardType,
    LiveSensorReading,
    StaticHazardZone,
)


# ---------------------------------------------------------------------------
# Trust weight configuration
# ---------------------------------------------------------------------------

STATIC_WEIGHT = 0.40
SENSOR_WEIGHT = 0.35
CROWD_WEIGHT = 0.25
CROWD_CORROBORATION_THRESHOLD = 3
STALENESS_HALF_LIFE_MINUTES = 120.0
STALE_TRUST_FLOOR = 0.05
OUTLIER_SIGMA = 2.0


def _compute_staleness_factor(timestamp: datetime, now: datetime | None = None) -> float:
    now = now or datetime.utcnow()
    age_minutes = max(0, (now - timestamp).total_seconds() / 60.0)
    factor = math.exp(-0.693 * age_minutes / STALENESS_HALF_LIFE_MINUTES)
    return max(STALE_TRUST_FLOOR, factor)


def _haversine_distance_km(a: Coordinates, b: Coordinates) -> float:
    R = 6371.0
    lat1, lat2 = math.radians(a.lat), math.radians(b.lat)
    dlat = lat2 - lat1
    dlon = math.radians(b.lon - a.lon)
    x = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(x), math.sqrt(1 - x))


def _filter_crowd_reports(
    reports: list[CrowdReport],
    now: datetime | None = None,
) -> tuple[float | None, int, list[str]]:
    now = now or datetime.utcnow()

    if not reports:
        return None, 0, []

    valid_reports = []
    for r in reports:
        age_min = max(0, (now - r.timestamp).total_seconds() / 60.0)
        if age_min > 24 * 60:
            continue
        decay = math.exp(-0.693 * age_min / STALENESS_HALF_LIFE_MINUTES)
        valid_reports.append((r, decay))

    if len(valid_reports) < CROWD_CORROBORATION_THRESHOLD:
        return None, len(valid_reports), []

    severities = sorted([s * r.severity_estimate for r, s in valid_reports])
    median_sev = severities[len(severities) // 2]
    std_sev = max(0.01, (max(severities) - min(severities)) / 2.0)

    filtered = []
    kept_ids = []
    for r, decay in valid_reports:
        weighted_sev = decay * r.severity_estimate
        if abs(weighted_sev - median_sev) <= OUTLIER_SIGMA * std_sev:
            filtered.append((r, decay))
            kept_ids.append(r.id)

    if not filtered:
        return None, 0, []

    total_weight = sum(d for _, d in filtered)
    weighted_severity = sum(d * r.severity_estimate for r, d in filtered) / total_weight

    return weighted_severity, len(filtered), kept_ids


def fuse_hazard_scores(
    habitation_id: str,
    habitation_location: Coordinates,
    hazard_type: HazardType,
    static_zones: list[StaticHazardZone],
    sensor_readings: list[LiveSensorReading],
    crowd_reports: list[CrowdReport],
    now: datetime | None = None,
) -> HazardConfidence:
    """
    Fuse static, sensor, and crowd signals into a single confidence score
    with a full human-readable explanation.
    """
    now = now or datetime.utcnow()
    factors = []

    # ---- 1. Static hazard score ----
    static_score = 0.0
    closest_zone = None
    closest_dist = float("inf")
    for zone in static_zones:
        dist = _haversine_distance_km(habitation_location, zone.center)
        if dist <= zone.radius_km:
            proximity_factor = 1.0 - (dist / zone.radius_km) * 0.3
            score = zone.severity * proximity_factor
            if score > static_score:
                static_score = score
                closest_zone = zone
                closest_dist = dist

    if closest_zone:
        factors.append(ExplanationFactor(
            factor="satellite_hazard_zone",
            weight=STATIC_WEIGHT,
            value=static_score,
            description=(
                f"Located {closest_dist:.1f}km from center of {closest_zone.hazard_type.value} "
                f"zone '{closest_zone.id}' (severity {closest_zone.severity:.2f}, "
                f"zone type: {closest_zone.zone_type}). "
                f"Proximity factor: {1.0 - (closest_dist / closest_zone.radius_km) * 0.3:.2f}."
            ),
        ))
    else:
        factors.append(ExplanationFactor(
            factor="satellite_hazard_zone",
            weight=STATIC_WEIGHT,
            value=0.0,
            description=f"No {hazard_type.value} hazard zone overlaps this habitation.",
        ))

    # ---- 2. Live sensor score ----
    sensor_score = 0.0
    is_stale = False
    staleness_minutes = 0.0
    best_reading = None
    for reading in sensor_readings:
        dist = _haversine_distance_km(habitation_location, reading.location)
        if dist <= 10.0:
            staleness = _compute_staleness_factor(reading.timestamp, now)
            if reading.source == "imd_rainfall":
                normalized = min(1.0, reading.value / 100.0)
            elif reading.source == "seismic":
                normalized = min(1.0, max(0.0, (reading.value - 3.0) / 4.0))
            else:
                normalized = min(1.0, reading.value)

            effective = normalized * staleness
            if effective > sensor_score:
                sensor_score = effective
                best_reading = reading
                staleness_minutes = (now - reading.timestamp).total_seconds() / 60.0
                is_stale = staleness_minutes > STALENESS_HALF_LIFE_MINUTES

        if best_reading:
            norm_val = best_reading.value
            if best_reading.source == "imd_rainfall":
                norm_desc = f"{norm_val:.0f}mm/hr rainfall (normalized: {min(1.0, norm_val/100.0):.2f})"
            elif best_reading.source == "seismic":
                norm_desc = f"M{norm_val:.1f} seismic (normalized: {min(1.0, max(0.0, (norm_val-3.0)/4.0)):.2f})"
            else:
                norm_desc = f"sensor value: {norm_val:.2f}"
            sensor_dist = _haversine_distance_km(habitation_location, best_reading.location)

            factors.append(ExplanationFactor(
                factor="live_sensor_reading",
                weight=SENSOR_WEIGHT,
                value=sensor_score,
                description=(
                    f"Nearest {best_reading.source} reading: {norm_desc}, "
                    f"distance: {sensor_dist:.1f}km, "
                    f"staleness: {staleness_minutes:.0f} min "
                    f"(trust factor: {staleness:.2f})"
                    f"{' [STALE]' if is_stale else ''}."
                ),
            ))
    else:
        factors.append(ExplanationFactor(
            factor="live_sensor_reading",
            weight=SENSOR_WEIGHT,
            value=0.0,
            description=f"No live {hazard_type.value} sensor readings within 10km radius.",
        ))

    # ---- 3. Crowd report score ----
    crowd_severity, corroboration_count, kept_ids = _filter_crowd_reports(crowd_reports, now)

    if crowd_severity is None or corroboration_count < CROWD_CORROBORATION_THRESHOLD:
        effective_crowd_weight = 0.0
        crowd_score = 0.0
        factors.append(ExplanationFactor(
            factor="crowd_reports",
            weight=0.0,
            value=crowd_severity or 0.0,
            description=(
                f"Crowd reports: {corroboration_count} received, "
                f"{CROWD_CORROBORATION_THRESHOLD} required for corroboration. "
                f"Crowd signal not applied (insufficient independent confirmation)."
            ),
        ))
    else:
        effective_crowd_weight = CROWD_WEIGHT
        crowd_score = crowd_severity
        factors.append(ExplanationFactor(
            factor="crowd_reports",
            weight=CROWD_WEIGHT,
            value=crowd_severity,
            description=(
                f"Crowd reports: {corroboration_count} corroborated reports, "
                f"avg severity: {crowd_severity:.2f}. "
                f"Crowd signal applied at {CROWD_WEIGHT:.0%} weight."
            ),
        ))

    # ---- 4. Weighted fusion ----
    remaining_weight = STATIC_WEIGHT + SENSOR_WEIGHT + (CROWD_WEIGHT - effective_crowd_weight)
    if remaining_weight > 0:
        w_static = STATIC_WEIGHT + (CROWD_WEIGHT - effective_crowd_weight) * (STATIC_WEIGHT / (STATIC_WEIGHT + SENSOR_WEIGHT))
        w_sensor = SENSOR_WEIGHT + (CROWD_WEIGHT - effective_crowd_weight) * (SENSOR_WEIGHT / (STATIC_WEIGHT + SENSOR_WEIGHT))
    else:
        w_static = STATIC_WEIGHT
        w_sensor = SENSOR_WEIGHT

    final_score = w_static * static_score + w_sensor * sensor_score + effective_crowd_weight * crowd_score
    final_score = max(0.0, min(1.0, final_score))

    # ---- 5. Alert level ----
    alert_level = _determine_alert_level(final_score, sensor_score, static_score, is_stale)

    # ---- 6. Build explanation ----
    summary = _build_hazard_explanation(
        habitation_id, hazard_type, alert_level, final_score,
        static_score, sensor_score, crowd_score,
        closest_zone, best_reading, corroboration_count,
    )

    explanation = DecisionExplanation(
        decision_type="hazard_alert",
        factors=factors,
        summary=summary,
        confidence_breakdown={
            "static_component": round(static_score, 4),
            "sensor_component": round(sensor_score, 4),
            "crowd_component": round(crowd_score, 4),
            "weights": {"static": round(w_static, 4), "sensor": round(w_sensor, 4), "crowd": round(effective_crowd_weight, 4)},
            "final_score": round(final_score, 4),
            "crowd_corroboration_count": corroboration_count,
        },
    )

    return HazardConfidence(
        habitation_id=habitation_id,
        hazard_type=hazard_type,
        confidence=round(final_score, 4),
        alert_level=alert_level,
        component_scores={
            "static": round(static_score, 4),
            "sensor": round(sensor_score, 4),
            "crowd": round(crowd_score, 4),
            "weights_used": {
                "static": round(w_static, 4),
                "sensor": round(w_sensor, 4),
                "crowd": round(effective_crowd_weight, 4),
            },
            "crowd_corroboration_count": corroboration_count,
        },
        explanation=explanation,
        is_stale=is_stale,
        staleness_minutes=round(staleness_minutes, 1),
        last_updated=now,
    )


def _build_hazard_explanation(
    hab_id: str,
    htype: HazardType,
    alert_level: AlertLevel,
    final_score: float,
    static_score: float,
    sensor_score: float,
    crowd_score: float,
    closest_zone,
    best_reading,
    corroboration_count,
) -> str:
    """Build a one-sentence human-readable summary of why this alert was issued."""
    if alert_level == AlertLevel.RELOCATE:
        return (
            f"RELOCATE: {hab_id} has {htype.value} confidence {final_score:.2f} "
            f"(satellite zone: {static_score:.2f}, sensor: {sensor_score:.2f}, "
            f"crowd: {crowd_score:.2f}). Immediate relocation recommended."
        )
    elif alert_level == AlertLevel.EVACUATE:
        return (
            f"EVACUATE: {hab_id} has {htype.value} confidence {final_score:.2f} "
            f"(satellite zone: {static_score:.2f}, sensor: {sensor_score:.2f}, "
            f"crowd: {crowd_score:.2f}). Evacuation preparation advised."
        )
    elif alert_level == AlertLevel.ADVISORY:
        return (
            f"ADVISORY: {hab_id} has {htype.value} confidence {final_score:.2f} "
            f"(satellite zone: {static_score:.2f}, sensor: {sensor_score:.2f}). "
            f"Monitor conditions; prepare for possible evacuation."
        )
    else:
        return (
            f"NORMAL: {hab_id} has {htype.value} confidence {final_score:.2f}. "
            f"No immediate action required."
        )


def _determine_alert_level(
    final_score: float,
    sensor_score: float,
    static_score: float,
    is_stale: bool,
) -> AlertLevel:
    predictive_uplift = 0.0
    if sensor_score > 0.6 and static_score > 0.3:
        predictive_uplift = 0.10
    if is_stale:
        predictive_uplift = min(predictive_uplift, 0.0)

    effective = final_score + predictive_uplift

    if effective >= 0.80:
        return AlertLevel.RELOCATE
    elif effective >= 0.55:
        return AlertLevel.EVACUATE
    elif effective >= 0.30:
        return AlertLevel.ADVISORY
    else:
        return AlertLevel.NORMAL
