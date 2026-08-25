"""
Satellite Change-Detection Framework for LocaTS.

Detects new/expanding hazard zones by comparing before/after satellite imagery.
Uses Sentinel-2 data via Copernicus Open Access Hub.

In demo mode: generates synthetic before/after comparisons.
In production: connects to Sentinel Hub or Google Earth Engine.

Source: Copernicus Sentinel-2 (10m resolution, free for research)
"""

from __future__ import annotations

import logging
import math
import os
import random
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# Sentinel-2 band indices for hazard detection
# NDWI (Normalized Difference Water Index) = (Green - NIR) / (Green + NIR)
# High NDWI = water/flood
# NDSI (Normalized Difference Snow Index) = (Green - SWIR) / (Green + SWIR)
# Used for landslide debris detection

# Demo mode: generate synthetic data for Chamoli district
CHAMOLI_DEMO_ZONES = [
    {"name": "Rishiganga River Corridor", "lat": 30.47, "lon": 79.55, "type": "flood", "baseline_ndwi": 0.2, "current_ndwi": 0.7},
    {"name": "Joshimath Slope North", "lat": 30.56, "lon": 79.57, "type": "landslide", "baseline_ndsi": 0.1, "current_ndsi": 0.6},
    {"name": "Tapovan Area", "lat": 30.49, "lon": 79.58, "type": "flood", "baseline_ndwi": 0.15, "current_ndwi": 0.55},
    {"name": "Badrinath Road Section", "lat": 30.74, "lon": 79.49, "type": "landslide", "baseline_ndsi": 0.05, "current_ndsi": 0.45},
]


class SatelliteChangeDetector:
    """
    Detects hazard zone changes from satellite imagery.
    
    In demo mode: returns synthetic before/after analysis.
    In production: fetches real Sentinel-2 imagery and computes NDWI/NDSI.
    """

    def __init__(self, use_demo: bool = True):
        self.use_demo = use_demo
        self.sentinel_hub_key = os.environ.get("SENTINEL_HUB_API_KEY", "")

    def detect_changes(
        self,
        district: str = "Chamoli",
        before_date: Optional[str] = None,
        after_date: Optional[str] = None,
    ) -> list[dict]:
        """
        Detect changes between two dates.
        
        Returns list of detected change zones with:
          - location, type (flood/landslide), severity, confidence
          - before/after index values (NDWI/NDSI)
          - pixel change percentage
        """
        if self.use_demo or not self.sentinel_hub_key:
            return self._demo_detection(district)

        return self._sentinel_detection(district, before_date, after_date)

    def _demo_detection(self, district: str) -> list[dict]:
        """Generate synthetic but realistic change detection results."""
        results = []
        for zone in CHAMOLI_DEMO_ZONES:
            # Simulate detection confidence based on index change
            if zone["type"] == "flood":
                change = zone["current_ndwi"] - zone["baseline_ndwi"]
                confidence = min(1.0, change * 1.5)
                severity = min(1.0, zone["current_ndwi"])
            else:
                change = zone["current_ndsi"] - zone["baseline_ndsi"]
                confidence = min(1.0, change * 1.8)
                severity = min(1.0, zone["current_ndsi"])

            results.append({
                "id": f"sat-change-{len(results)+1:04d}",
                "district": district,
                "name": zone["name"],
                "center_lat": zone["lat"],
                "center_lon": zone["lon"],
                "hazard_type": zone["type"],
                "severity": round(severity, 3),
                "confidence": round(confidence, 3),
                "change_magnitude": round(change, 3),
                "detection_method": "NDWI" if zone["type"] == "flood" else "NDSI",
                "before_index": zone.get("baseline_ndwi", zone.get("baseline_ndsi", 0)),
                "after_index": zone.get("current_ndwi", zone.get("current_ndsi", 0)),
                "pixel_change_pct": round(random.uniform(15, 60), 1),
                "source": "Sentinel-2 (demo mode)",
                "timestamp": datetime.utcnow().isoformat(),
                "recommendation": self._get_recommendation(zone["type"], severity),
            })

        logger.info(f"  Satellite change detection: {len(results)} zones detected (demo)")
        return results

    def _sentinel_detection(
        self, district: str, before_date: Optional[str], after_date: Optional[str]
    ) -> list[dict]:
        """
        Real Sentinel-2 change detection.
        
        In production, this would:
        1. Fetch Sentinel-2 L2A tiles from Copernicus
        2. Compute NDWI = (B3 - B8) / (B3 + B8) for flood
        3. Compute NDSI = (B3 - B11) / (B3 + B11) for landslide
        4. Threshold the difference to detect new hazard zones
        5. Return detected zones
        
        Requires: SENTINEL_HUB_API_KEY in environment.
        """
        # Placeholder for real Sentinel Hub integration
        logger.warning("  Sentinel Hub not configured. Using demo mode.")
        return self._demo_detection(district)

    def _get_recommendation(self, hazard_type: str, severity: float) -> str:
        if hazard_type == "flood":
            if severity > 0.7:
                return "IMMEDIATE: New flood zone detected. Issue evacuation order."
            elif severity > 0.4:
                return "WARNING: Potential flooding. Issue advisory and monitor."
            else:
                return "WATCH: Minor water level increase. Monitor conditions."
        else:
            if severity > 0.7:
                return "CRITICAL: Landslide debris detected. Block road and evacuate."
            elif severity > 0.4:
                return "WARNING: Slope instability detected. Issue advisory."
            else:
                return "WATCH: Minor ground movement. Monitor with ground sensors."

    def get_before_after_imagery_urls(
        self, lat: float, lon: float, before_date: str, after_date: str
    ) -> dict:
        """
        Get Sentinel-2 imagery URLs for visual comparison.
        
        Returns thumbnail URLs for before/after images.
        In production, these would be real Sentinel-2 RGB composites.
        """
        return {
            "before": f"https://Sentinel Hub-browse URL (before {before_date})",
            "after": f"https://Sentinel Hub-browse URL (after {after_date})",
            "ndwi_before": f"NDWI visualization before {before_date}",
            "ndwi_after": f"NDWI visualization after {after_date}",
            "note": "Configure SENTINEL_HUB_API_KEY for real imagery",
        }


# Singleton
satellite_detector = SatelliteChangeDetector(use_demo=True)
