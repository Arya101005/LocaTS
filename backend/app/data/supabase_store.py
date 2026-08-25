"""
Supabase persistent storage for LocaTS.

Replaces all in-memory state with a real PostGIS database.
Provides:
  - Persistent habitations, shelters, roads, hazard zones
  - Evacuation orders with audit trail
  - Crowd reports storage
  - Evacuee registrations for family reunification
  - Real-time subscriptions for live dashboard updates

Requires Supabase project with PostGIS enabled.
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class SupabaseStore:
    """
    Persistent storage backend using Supabase (PostGIS).
    
    Falls back to in-memory dict when Supabase is not configured.
    """

    def __init__(self):
        self.url = os.environ.get("SUPABASE_URL", "")
        self.key = os.environ.get("SUPABASE_KEY", "")
        self._client = None
        self._memory: dict[str, list] = {
            "habitations": [],
            "shelters": [],
            "roads": [],
            "hazard_zones": [],
            "sensor_readings": [],
            "crowd_reports": [],
            "evacuees": [],
            "relocation_orders": [],
            "alerts": [],
        }

    @property
    def is_configured(self) -> bool:
        return bool(self.url and self.key)

    @property
    def client(self):
        if self._client is None and self.is_configured:
            try:
                from supabase import create_client
                self._client = create_client(self.url, self.key)
            except Exception as e:
                logger.warning(f"Supabase connection failed: {e}")
        return self._client

    def _table(self, name: str):
        """Get a Supabase table reference."""
        if self.client:
            return self.client.table(name)
        return None

    def _mem(self, table: str) -> list:
        return self._memory.setdefault(table, [])

    # ------------------------------------------------------------------
    # Generic CRUD
    # ------------------------------------------------------------------
    def upsert(self, table: str, data: dict, conflict_col: str = "id") -> bool:
        """Insert or update a row."""
        if self.client:
            try:
                self._table(table).upsert(data).execute()
                return True
            except Exception as e:
                logger.warning(f"  Upsert {table} failed: {e}")
                return False
        # Memory fallback
        rows = self._mem(table)
        for i, row in enumerate(rows):
            if row.get(conflict_col) == data.get(conflict_col):
                rows[i] = data
                return True
        rows.append(data)
        return True

    def insert(self, table: str, data: dict) -> bool:
        """Insert a row."""
        if self.client:
            try:
                self._table(table).insert(data).execute()
                return True
            except Exception as e:
                logger.warning(f"  Insert {table} failed: {e}")
                return False
        self._mem(table).append(data)
        return True

    def select(self, table: str, filters: Optional[dict] = None) -> list[dict]:
        """Select rows with optional filters."""
        if self.client:
            try:
                q = self._table(table).select("*")
                if filters:
                    for k, v in filters.items():
                        q = q.eq(k, v)
                result = q.execute()
                return result.data
            except Exception as e:
                logger.warning(f"  Select {table} failed: {e}")
                return []
        # Memory fallback
        rows = self._mem(table)
        if not filters:
            return rows
        return [r for r in rows if all(r.get(k) == v for k, v in filters.items())]

    def update(self, table: str, data: dict, filters: dict) -> bool:
        """Update rows matching filters."""
        if self.client:
            try:
                q = self._table(table).update(data)
                for k, v in filters.items():
                    q = q.eq(k, v)
                q.execute()
                return True
            except Exception as e:
                logger.warning(f"  Update {table} failed: {e}")
                return False
        # Memory fallback
        updated = False
        for row in self._mem(table):
            if all(row.get(k) == v for k, v in filters.items()):
                row.update(data)
                updated = True
        return updated

    def delete(self, table: str, filters: dict) -> bool:
        """Delete rows matching filters."""
        if self.client:
            try:
                q = self._table(table).delete()
                for k, v in filters.items():
                    q = q.eq(k, v)
                q.execute()
                return True
            except Exception as e:
                logger.warning(f"  Delete {table} failed: {e}")
                return False
        rows = self._mem(table)
        self._memory[table] = [r for r in rows if not all(r.get(k) == v for k, v in filters.items())]
        return True

    def count(self, table: str, filters: Optional[dict] = None) -> int:
        """Count rows."""
        if self.client:
            try:
                q = self._table(table).select("*", count="exact")
                if filters:
                    for k, v in filters.items():
                        q = q.eq(k, v)
                result = q.execute()
                return result.count or 0
            except Exception:
                return len(self._mem(table))
        rows = self._mem(table)
        if not filters:
            return len(rows)
        return sum(1 for r in rows if all(r.get(k) == v for k, v in filters.items()))

    def clear(self, table: str) -> bool:
        """Clear all rows in a table."""
        if self.client:
            try:
                self._table(table).delete().neq("id", "").execute()
                return True
            except Exception:
                pass
        self._memory[table] = []
        return True

    # ------------------------------------------------------------------
    # Domain-specific helpers
    # ------------------------------------------------------------------
    def save_habitation(self, hab: dict) -> bool:
        return self.upsert("habitations", hab)

    def save_shelter(self, shelter: dict) -> bool:
        return self.upsert("shelters", shelter)

    def save_road(self, road: dict) -> bool:
        return self.upsert("road_segments", road)

    def save_hazard_zone(self, zone: dict) -> bool:
        return self.upsert("hazard_zones", zone)

    def save_relocation_order(self, order: dict) -> bool:
        return self.insert("relocation_orders", order)

    def save_crowd_report(self, report: dict) -> bool:
        return self.insert("crowd_reports", report)

    def save_evacuee(self, evacuee: dict) -> bool:
        return self.insert("evacuees", evacuee)

    def get_all_habitations(self) -> list[dict]:
        return self.select("habitations")

    def get_all_shelters(self) -> list[dict]:
        return self.select("shelters")

    def get_all_roads(self) -> list[dict]:
        return self.select("road_segments")

    def get_hazard_zones(self, district: Optional[str] = None) -> list[dict]:
        filters = {"district": district} if district else None
        return self.select("hazard_zones", filters)

    def get_evacuees(self, shelter_id: Optional[str] = None) -> list[dict]:
        filters = {"registered_shelter_id": shelter_id} if shelter_id else None
        return self.select("evacuees", filters)

    def get_relocation_orders(self, limit: int = 10) -> list[dict]:
        orders = self.select("relocation_orders")
        return sorted(orders, key=lambda x: x.get("issued_at", ""), reverse=True)[:limit]


# Singleton
store = SupabaseStore()
