-- LocaTS Database Schema
-- Paste this into Supabase Dashboard > SQL Editor > Run

-- Habitations table
CREATE TABLE IF NOT EXISTS habitations (
    id TEXT PRIMARY KEY,
    district TEXT NOT NULL DEFAULT '',
    name TEXT NOT NULL DEFAULT '',
    lat REAL DEFAULT 0,
    lon REAL DEFAULT 0,
    population_estimate INTEGER DEFAULT 0,
    data JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Shelters table
CREATE TABLE IF NOT EXISTS shelters (
    id TEXT PRIMARY KEY,
    district TEXT NOT NULL DEFAULT '',
    name TEXT NOT NULL DEFAULT '',
    lat REAL DEFAULT 0,
    lon REAL DEFAULT 0,
    bed_capacity INTEGER DEFAULT 0,
    data JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Road segments table
CREATE TABLE IF NOT EXISTS road_segments (
    id TEXT PRIMARY KEY,
    district TEXT NOT NULL DEFAULT '',
    from_node TEXT DEFAULT '',
    to_node TEXT DEFAULT '',
    distance_km REAL DEFAULT 0,
    data JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Hazard zones table
CREATE TABLE IF NOT EXISTS hazard_zones (
    id TEXT PRIMARY KEY,
    district TEXT NOT NULL DEFAULT '',
    hazard_type TEXT NOT NULL DEFAULT '',
    severity REAL DEFAULT 0,
    data JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Evacuees table (family reunification)
CREATE TABLE IF NOT EXISTS evacuees (
    id SERIAL PRIMARY KEY,
    evacuee_id TEXT DEFAULT '',
    name_hash TEXT DEFAULT '',
    shelter_id TEXT DEFAULT '',
    status TEXT DEFAULT 'safe',
    data JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Relocation orders (audit trail)
CREATE TABLE IF NOT EXISTS relocation_orders (
    id SERIAL PRIMARY KEY,
    order_id TEXT DEFAULT '',
    district TEXT DEFAULT '',
    audit_hash TEXT DEFAULT '',
    data JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable RLS but allow all for demo (change in production)
ALTER TABLE habitations ENABLE ROW LEVEL SECURITY;
ALTER TABLE shelters ENABLE ROW LEVEL SECURITY;
ALTER TABLE road_segments ENABLE ROW LEVEL SECURITY;
ALTER TABLE hazard_zones ENABLE ROW LEVEL SECURITY;
ALTER TABLE evacuees ENABLE ROW LEVEL SECURITY;
ALTER TABLE relocation_orders ENABLE ROW LEVEL SECURITY;

-- Allow anon access for demo
CREATE POLICY "Allow all for demo" ON habitations FOR ALL USING (true);
CREATE POLICY "Allow all for demo" ON shelters FOR ALL USING (true);
CREATE POLICY "Allow all for demo" ON road_segments FOR ALL USING (true);
CREATE POLICY "Allow all for demo" ON hazard_zones FOR ALL USING (true);
CREATE POLICY "Allow all for demo" ON evacuees FOR ALL USING (true);
CREATE POLICY "Allow all for demo" ON relocation_orders FOR ALL USING (true);

-- Also allow storage bucket access
INSERT INTO storage.buckets (id, name, public) VALUES ('locats-data', 'locats-data', true)
ON CONFLICT (id) DO NOTHING;

CREATE POLICY "Allow all for demo" ON storage.objects FOR ALL USING (bucket_id = 'locats-data');
