"""
Sample data for demo: Chamoli district, Uttarakhand.
Real district prone to both flash floods (2021 Chamoli disaster) and landslides.

Data is based on real geography but population/capacity numbers are illustrative
estimates for the demo, NOT real census data. Attributed as such in README.
"""

from backend.app.models.domain import (
    CapacityGraph,
    HabitationCluster,
    RoadSegment,
    RoadStatus,
    Shelter,
    SocialVulnerability,
)


def build_chamoli_sample() -> CapacityGraph:
    """Build sample capacity graph for Chamoli district, Uttarakhand."""

    habitations = [
        HabitationCluster(
            id="hab-001", name="Raini Village",
            location={"lat": 30.47, "lon": 79.55}, population_estimate=1200,
            district="Chamoli", block="Chamoli", elevation_m=2400,
            social_vulnerability=SocialVulnerability(
                elderly_fraction=0.15, disability_fraction=0.08,
                single_income_fraction=0.35, non_native_language_fraction=0.02,
                child_fraction=0.22,
            ),
        ),
        HabitationCluster(
            id="hab-002", name="Tapovan Settlement",
            location={"lat": 30.49, "lon": 79.58}, population_estimate=800,
            district="Chamoli", block="Chamoli", elevation_m=2600,
            social_vulnerability=SocialVulnerability(
                elderly_fraction=0.20, disability_fraction=0.12,
                single_income_fraction=0.40, non_native_language_fraction=0.05,
                child_fraction=0.18,
            ),
        ),
        HabitationCluster(
            id="hab-003", name="Ghat Village",
            location={"lat": 30.38, "lon": 79.62}, population_estimate=2000,
            district="Chamoli", block="Ghat", elevation_m=1800,
            social_vulnerability=SocialVulnerability(
                elderly_fraction=0.12, disability_fraction=0.06,
                single_income_fraction=0.25, non_native_language_fraction=0.03,
                child_fraction=0.28,
            ),
        ),
        HabitationCluster(
            id="hab-004", name="Joshimath Town",
            location={"lat": 30.56, "lon": 79.57}, population_estimate=3500,
            district="Chamoli", block="Joshimath", elevation_m=1889,
            social_vulnerability=SocialVulnerability(
                elderly_fraction=0.08, disability_fraction=0.05,
                single_income_fraction=0.20, non_native_language_fraction=0.01,
                child_fraction=0.25,
            ),
        ),
        HabitationCluster(
            id="hab-005", name="Badrinath Puri",
            location={"lat": 30.74, "lon": 79.49}, population_estimate=1500,
            district="Chamoli", block="Badrinath", elevation_m=3300,
            social_vulnerability=SocialVulnerability(
                elderly_fraction=0.18, disability_fraction=0.10,
                single_income_fraction=0.30, non_native_language_fraction=0.08,
                child_fraction=0.15,
            ),
        ),
        HabitationCluster(
            id="hab-006", name="Karnaprayag Town",
            location={"lat": 30.27, "lon": 79.32}, population_estimate=2500,
            district="Chamoli", block="Karnaprayag", elevation_m=1450,
            social_vulnerability=SocialVulnerability(
                elderly_fraction=0.10, disability_fraction=0.04,
                single_income_fraction=0.18, non_native_language_fraction=0.01,
                child_fraction=0.26,
            ),
        ),
        HabitationCluster(
            id="hab-007", name="Nandprayag Settlement",
            location={"lat": 30.33, "lon": 79.32}, population_estimate=1200,
            district="Chamoli", block="Nandprayag", elevation_m=1300,
            social_vulnerability=SocialVulnerability(
                elderly_fraction=0.22, disability_fraction=0.15,
                single_income_fraction=0.45, non_native_language_fraction=0.10,
                child_fraction=0.20,
            ),
        ),
        HabitationCluster(
            id="hab-008", name="Gopeshwar Town",
            location={"lat": 30.40, "lon": 79.33}, population_estimate=3000,
            district="Chamoli", block="Chamoli", elevation_m=1500,
            social_vulnerability=SocialVulnerability(
                elderly_fraction=0.09, disability_fraction=0.04,
                single_income_fraction=0.15, non_native_language_fraction=0.01,
                child_fraction=0.24,
            ),
        ),
    ]
    # Total population: 15,700; with 15% buffer = ~18,065

    shelters = [
        Shelter(
            id="shelter-001", name="Govt Inter College, Gopeshwar",
            location={"lat": 30.41, "lon": 79.34}, bed_capacity=3500,
            healthcare_beds_per_hour=20, water_capacity_liters_per_day=80000,
            is_accessible=True, shelter_type="school", district="Chamoli",
        ),
        Shelter(
            id="shelter-002", name="Community Hall, Karnaprayag",
            location={"lat": 30.28, "lon": 79.33}, bed_capacity=3000,
            healthcare_beds_per_hour=10, water_capacity_liters_per_day=60000,
            is_accessible=True, shelter_type="community_hall", district="Chamoli",
        ),
        Shelter(
            id="shelter-003", name="ITBP Camp, Joshimath",
            location={"lat": 30.55, "lon": 79.58}, bed_capacity=3500,
            healthcare_beds_per_hour=30, water_capacity_liters_per_day=80000,
            is_accessible=True, shelter_type="govt_building", district="Chamoli",
        ),
        Shelter(
            id="shelter-004", name="Tent Colony, Srinagar (Pauri)",
            location={"lat": 30.22, "lon": 79.18}, bed_capacity=4500,
            healthcare_beds_per_hour=15, water_capacity_liters_per_day=100000,
            is_accessible=False, shelter_type="tent", district="Pauri Garhwal",
        ),
        Shelter(
            id="shelter-005", name="District Hospital, Srinagar",
            location={"lat": 30.23, "lon": 79.19}, bed_capacity=4000,
            healthcare_beds_per_hour=40, water_capacity_liters_per_day=90000,
            is_accessible=True, shelter_type="govt_building", district="Pauri Garhwal",
        ),
    ]
    # Total beds: 18,500 (just enough for buffered demand of ~18,065)

    road_segments = [
        # Main arterial roads
        RoadSegment(
            id="road-001", from_node="hab-001", to_node="hab-004",
            distance_km=15.0, travel_time_minutes=45,
            capacity_vehicles_per_hour=60, people_throughput_per_hour=500,
            status=RoadStatus.OPEN, damage_factor=1.0,
        ),
        RoadSegment(
            id="road-002", from_node="hab-004", to_node="hab-005",
            distance_km=25.0, travel_time_minutes=75,
            capacity_vehicles_per_hour=40, people_throughput_per_hour=300,
            status=RoadStatus.OPEN, damage_factor=1.0,
        ),
        RoadSegment(
            id="road-003", from_node="hab-003", to_node="hab-001",
            distance_km=12.0, travel_time_minutes=35,
            capacity_vehicles_per_hour=50, people_throughput_per_hour=400,
            status=RoadStatus.OPEN, damage_factor=1.0,
        ),
        RoadSegment(
            id="road-004", from_node="hab-004", to_node="shelter-003",
            distance_km=2.0, travel_time_minutes=10,
            capacity_vehicles_per_hour=100, people_throughput_per_hour=1000,
            status=RoadStatus.OPEN, damage_factor=1.0,
        ),
        RoadSegment(
            id="road-005", from_node="hab-004", to_node="hab-008",
            distance_km=30.0, travel_time_minutes=90,
            capacity_vehicles_per_hour=50, people_throughput_per_hour=400,
            status=RoadStatus.OPEN, damage_factor=1.0,
        ),
        RoadSegment(
            id="road-006", from_node="hab-008", to_node="shelter-001",
            distance_km=3.0, travel_time_minutes=10,
            capacity_vehicles_per_hour=80, people_throughput_per_hour=800,
            status=RoadStatus.OPEN, damage_factor=1.0,
        ),
        RoadSegment(
            id="road-007", from_node="hab-006", to_node="hab-007",
            distance_km=8.0, travel_time_minutes=20,
            capacity_vehicles_per_hour=60, people_throughput_per_hour=500,
            status=RoadStatus.OPEN, damage_factor=1.0,
        ),
        RoadSegment(
            id="road-008", from_node="hab-006", to_node="shelter-002",
            distance_km=2.0, travel_time_minutes=8,
            capacity_vehicles_per_hour=80, people_throughput_per_hour=800,
            status=RoadStatus.OPEN, damage_factor=1.0,
        ),
        RoadSegment(
            id="road-009", from_node="hab-007", to_node="shelter-002",
            distance_km=5.0, travel_time_minutes=15,
            capacity_vehicles_per_hour=60, people_throughput_per_hour=500,
            status=RoadStatus.OPEN, damage_factor=1.0,
        ),
        # Cross-district routes (longer distances)
        RoadSegment(
            id="road-010", from_node="hab-008", to_node="shelter-004",
            distance_km=80.0, travel_time_minutes=240,
            capacity_vehicles_per_hour=30, people_throughput_per_hour=200,
            status=RoadStatus.OPEN, damage_factor=1.0,
        ),
        RoadSegment(
            id="road-011", from_node="hab-006", to_node="shelter-005",
            distance_km=60.0, travel_time_minutes=180,
            capacity_vehicles_per_hour=30, people_throughput_per_hour=200,
            status=RoadStatus.OPEN, damage_factor=1.0,
        ),
        # Connection from hab-002
        RoadSegment(
            id="road-012", from_node="hab-002", to_node="hab-004",
            distance_km=18.0, travel_time_minutes=55,
            capacity_vehicles_per_hour=30, people_throughput_per_hour=200,
            status=RoadStatus.OPEN, damage_factor=1.0,
        ),
        # Additional connectivity
        RoadSegment(
            id="road-013", from_node="hab-008", to_node="shelter-002",
            distance_km=25.0, travel_time_minutes=75,
            capacity_vehicles_per_hour=40, people_throughput_per_hour=300,
            status=RoadStatus.OPEN, damage_factor=1.0,
        ),
        RoadSegment(
            id="road-014", from_node="hab-005", to_node="shelter-003",
            distance_km=25.0, travel_time_minutes=75,
            capacity_vehicles_per_hour=40, people_throughput_per_hour=300,
            status=RoadStatus.OPEN, damage_factor=1.0,
        ),
        RoadSegment(
            id="road-015", from_node="hab-001", to_node="shelter-003",
            distance_km=17.0, travel_time_minutes=50,
            capacity_vehicles_per_hour=40, people_throughput_per_hour=300,
            status=RoadStatus.OPEN, damage_factor=1.0,
        ),
    ]

    return CapacityGraph(
        habitations=habitations,
        shelters=shelters,
        road_segments=road_segments,
    )


def get_sample_hazard_zones() -> list[dict]:
    """Sample static hazard zones for Chamoli district."""
    return [
        {
            "id": "zone-flood-001",
            "hazard_type": "flood",
            "severity": 0.85,
            "zone_type": "red",
            "center_lat": 30.47,
            "center_lon": 79.55,
            "radius_km": 20.0,
        },
        {
            "id": "zone-flood-002",
            "hazard_type": "flood",
            "severity": 0.60,
            "zone_type": "orange",
            "center_lat": 30.38,
            "center_lon": 79.62,
            "radius_km": 15.0,
        },
        {
            "id": "zone-landslide-001",
            "hazard_type": "landslide",
            "severity": 0.70,
            "zone_type": "red",
            "center_lat": 30.56,
            "center_lon": 79.57,
            "radius_km": 10.0,
        },
        {
            "id": "zone-landslide-002",
            "hazard_type": "landslide",
            "severity": 0.50,
            "zone_type": "orange",
            "center_lat": 30.74,
            "center_lon": 79.49,
            "radius_km": 12.0,
        },
    ]


def get_sample_sensor_readings() -> list[dict]:
    """Sample IMD rainfall readings (simulated heavy monsoon event)."""
    return [
        {"source": "imd_rainfall", "lat": 30.47, "lon": 79.55, "value": 85.0},
        {"source": "imd_rainfall", "lat": 30.49, "lon": 79.58, "value": 72.0},
        {"source": "imd_rainfall", "lat": 30.38, "lon": 79.62, "value": 60.0},
        {"source": "imd_rainfall", "lat": 30.56, "lon": 79.57, "value": 45.0},
        {"source": "imd_rainfall", "lat": 30.74, "lon": 79.49, "value": 55.0},
        {"source": "imd_rainfall", "lat": 30.27, "lon": 79.32, "value": 20.0},
        {"source": "imd_rainfall", "lat": 30.40, "lon": 79.33, "value": 30.0},
    ]
