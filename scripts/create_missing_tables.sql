-- Create missing crowd_reports table
CREATE TABLE IF NOT EXISTS crowd_reports (
    id TEXT PRIMARY KEY,
    reporter_id TEXT NOT NULL DEFAULT '',
    hazard_type TEXT NOT NULL DEFAULT '',
    severity_estimate REAL DEFAULT 0.5,
    location_lat REAL DEFAULT 0,
    location_lon REAL DEFAULT 0,
    description TEXT DEFAULT '',
    photo_hash TEXT DEFAULT '',
    status TEXT DEFAULT 'pending',
    data JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable RLS and allow demo access
ALTER TABLE crowd_reports ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow all for demo" ON crowd_reports FOR ALL USING (true);

-- Create index for fast lookups
CREATE INDEX IF NOT EXISTS idx_crowd_hazard ON crowd_reports(hazard_type);
CREATE INDEX IF NOT EXISTS idx_crowd_status ON crowd_reports(status);
