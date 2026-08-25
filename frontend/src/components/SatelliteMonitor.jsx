import React, { useState, useEffect } from 'react';

const API = '/api';

export default function SatelliteMonitor() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API}/satellite/change-detection?district=Chamoli`).then(r => r.json()).then(d => { setData(d); setLoading(false); }).catch(() => setLoading(false));
  }, []);

  if (loading) return <div style={{ padding: 40, textAlign: 'center', color: '#94A3B8' }}>Loading satellite data...</div>;

  return (
    <div style={{ maxWidth: 900 }}>
      <h2 style={{ fontSize: 22, fontWeight: 800, marginBottom: 4 }}>Satellite Change Detection</h2>
      <p style={{ fontSize: 13, color: '#94A3B8', marginBottom: 24 }}>Sentinel-2 before/after imagery analysis for Chamoli district.</p>

      <div className="card" style={{ marginBottom: 20, padding: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
          <div style={{ width: 40, height: 40, borderRadius: 10, background: data?.is_live_satellite ? '#EFF6FF' : '#FEF3C7', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={data?.is_live_satellite ? '#2563EB' : '#D97706'} strokeWidth="2"><path d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
          </div>
          <div>
            <div style={{ fontSize: 15, fontWeight: 700, color: '#111827' }}>{data?.source || 'Sentinel-2'}</div>
            <div style={{ fontSize: 12, color: '#94A3B8' }}>{data?.district} District | {data?.changes_detected} zones analyzed</div>
          </div>
          <span className={`badge ${data?.is_live_satellite ? 'badge-safe' : 'badge-warn'}`} style={{ marginLeft: 'auto' }}>
            {data?.is_live_satellite ? 'LIVE SATELLITE' : 'HAZARD ZONES'}
          </span>
        </div>

        {data?.note && (
          <div style={{ padding: '10px 14px', background: data?.is_live_satellite ? '#F0FDF4' : '#FFFBEB', borderRadius: 8, fontSize: 12, color: data?.is_live_satellite ? '#16A34A' : '#92400E', marginBottom: 16 }}>
            {data.note}
          </div>
        )}

        {/* Changes Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 12 }}>
          {data?.changes?.map((c, i) => (
            <div key={i} style={{ padding: 14, background: '#F9FAFB', borderRadius: 10, border: '1px solid #E5E7EB' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                <span style={{ fontSize: 13, fontWeight: 700, color: '#111827' }}>{c.product || c.zone_id || `Zone ${i+1}`}</span>
                {c.severity !== undefined && (
                  <span className={`badge ${c.severity > 0.7 ? 'badge-danger' : c.severity > 0.4 ? 'badge-warn' : 'badge-safe'}`}>
                    {(c.severity * 100).toFixed(0)}%
                  </span>
                )}
              </div>
              {c.date && <div style={{ fontSize: 11, color: '#94A3B8', marginBottom: 4 }}>Date: {c.date}</div>}
              {c.cloud_cover !== undefined && <div style={{ fontSize: 11, color: '#94A3B8', marginBottom: 4 }}>Cloud: {c.cloud_cover}%</div>}
              {c.type && <div style={{ fontSize: 11, color: '#6B7280', marginBottom: 4 }}>Type: {c.type}</div>}
              {c.analysis && <div style={{ fontSize: 11, color: '#374151', lineHeight: 1.4 }}>{c.analysis}</div>}
            </div>
          ))}
        </div>

        {(!data?.changes || data.changes.length === 0) && (
          <div style={{ padding: 40, textAlign: 'center', color: '#94A3B8' }}>No satellite data available at this time.</div>
        )}
      </div>

      {/* NDWI/NDSI Explanation */}
      <div className="card" style={{ padding: 20 }}>
        <div className="card-header">How Change Detection Works</div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <div style={{ padding: 14, background: '#EFF6FF', borderRadius: 10, border: '1px solid #DBEAFE' }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: '#1D4ED8', marginBottom: 4 }}>NDWI — Water Detection</div>
            <div style={{ fontSize: 12, color: '#4B5563', lineHeight: 1.5 }}>Normalised Difference Water Index compares green and near-infrared bands. Rising NDWI = expanding water bodies, flood risk.</div>
          </div>
          <div style={{ padding: 14, background: '#FEF3C7', borderRadius: 10, border: '1px solid #FDE68A' }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: '#92400E', marginBottom: 4 }}>NDSI — Snow/Landslide Detection</div>
            <div style={{ fontSize: 12, color: '#4B5563', lineHeight: 1.5 }}>Normalised Difference Snow Index detects snow and bare soil. Changes indicate landslide risk or glacial lake outburst potential.</div>
          </div>
        </div>
      </div>
    </div>
  );
}
