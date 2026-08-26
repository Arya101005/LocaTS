import { useState, useEffect } from 'react';

export default function MultiDistrict() {
  const [data, setData] = useState(null);
  const [expanded, setExpanded] = useState(null);

  useEffect(() => {
    fetch('/api/multi-district/overview')
      .then(r => r.json())
      .then(setData)
      .catch(() => {});
  }, []);

  if (!data) {
    return <div style={{ padding: 40, textAlign: 'center', color: '#6b7280' }}>Loading multi-district data...</div>;
  }

  const statusColors = {
    active_disaster: '#ef4444',
    standby: '#22c55e',
    monitoring: '#f59e0b',
  };

  const riskColors = { high: '#ef4444', medium: '#f59e0b', low: '#22c55e' };

  return (
    <div style={{ padding: 0, fontFamily: "'Inter', system-ui, sans-serif" }}>
      {/* Header */}
      <div style={{
        background: 'linear-gradient(135deg, #1e40af 0%, #1e3a8a 100%)',
        borderRadius: '18px', padding: '32px', marginBottom: '24px', color: 'white',
      }}>
        <h2 style={{ fontSize: '22px', fontWeight: 800, margin: '0 0 6px' }}>
          Multi-District Coordination
        </h2>
        <p style={{ fontSize: '14px', opacity: 0.85, margin: 0 }}>
          Cross-district shelter sharing, corridor management, and authorization chain
        </p>
      </div>

      {/* District Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '16px', marginBottom: '24px' }}>
        {data.districts.map((d, i) => (
          <div key={d.id} style={{
            background: '#fff', borderRadius: '14px', border: '1px solid #e5e7eb',
            overflow: 'hidden', boxShadow: '0 2px 8px rgba(0,0,0,0.04)',
          }}>
            <div style={{
              padding: '16px 18px', borderBottom: '3px solid',
              borderColor: riskColors[d.risk_level] || '#e5e7eb',
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            }}>
              <div>
                <div style={{ fontWeight: 700, fontSize: '16px', color: '#111827' }}>{d.name}</div>
                <div style={{
                  display: 'inline-block', padding: '2px 10px', borderRadius: '12px',
                  fontSize: '11px', fontWeight: 600, marginTop: 4,
                  background: riskColors[d.risk_level] + '15',
                  color: riskColors[d.risk_level],
                }}>
                  {d.risk_level.toUpperCase()} RISK
                </div>
              </div>
              <div style={{
                padding: '6px 12px', borderRadius: '8px', fontSize: '12px', fontWeight: 600,
                background: statusColors[d.status] + '15',
                color: statusColors[d.status],
              }}>
                {d.status.replace(/_/g, ' ').toUpperCase()}
              </div>
            </div>
            <div style={{ padding: '16px 18px' }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                <InfoItem label="Population" value={`${(d.population / 1000).toFixed(0)}K`} />
                <InfoItem label="Shelters" value={d.shelters} />
                <InfoItem label="Total Beds" value={`${(d.total_beds / 1000).toFixed(0)}K`} />
                <InfoItem label="Hazard Zones" value={d.hazard_zones} />
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Corridors */}
      <div style={{
        background: '#fff', borderRadius: '14px', border: '1px solid #e5e7eb',
        padding: '20px 24px', marginBottom: '24px',
        boxShadow: '0 2px 8px rgba(0,0,0,0.04)',
      }}>
        <h3 style={{ fontSize: '16px', fontWeight: 700, color: '#111827', margin: '0 0 16px' }}>
          Cross-District Corridors
        </h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {data.corridors.map((c, i) => (
            <div key={i} style={{
              padding: '14px 16px', borderRadius: '10px',
              background: c.status === 'open' ? '#f0fdf4' : '#fef2f2',
              border: `1px solid ${c.status === 'open' ? '#bbf7d0' : '#fecaca'}`,
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              flexWrap: 'wrap', gap: '8px',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <span style={{ fontSize: '18px' }}>                   <span style={{ width: 8, height: 8, borderRadius: '50%', background: c.status === 'open' ? '#22C55E' : '#DC2626', display: 'inline-block' }} />
                </span>
                 <div>
                   <div style={{ fontWeight: 600, fontSize: '14px', color: '#111827' }}>
                     {c.from} → {c.to}
                   </div>
                   <div style={{ fontSize: '12px', color: '#6b7280', marginTop: 2 }}>
                     {c.distance_km} km • {c.travel_time_hrs}h travel time
                   </div>
                 </div>
              </div>
              <div style={{ display: 'flex', gap: '12px', fontSize: '12px' }}>
                <span style={{
                  padding: '4px 10px', borderRadius: '6px',
                  background: 'rgba(37,99,235,0.1)', color: '#2563eb', fontWeight: 500,
                }}>
                  {c.capacity_vehicles_hr} vehicles/hr
                </span>
                <span style={{
                  padding: '4px 10px', borderRadius: '6px',
                  background: c.status === 'open' ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.1)',
                  color: c.status === 'open' ? '#16a34a' : '#dc2626', fontWeight: 500,
                }}>
                  {c.status.toUpperCase()}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Coordination Log */}
      <div style={{
        background: '#fff', borderRadius: '14px', border: '1px solid #e5e7eb',
        padding: '20px 24px',
        boxShadow: '0 2px 8px rgba(0,0,0,0.04)',
      }}>
        <h3 style={{ fontSize: '16px', fontWeight: 700, color: '#111827', margin: '0 0 16px' }}>
          Coordination Event Log
        </h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {(data.coordination_log || []).map((e, i) => {
            const severityColors = {
              critical: '#ef4444', warning: '#f59e0b', info: '#2563eb',
            };
            const sc = severityColors[e.severity] || '#6b7280';
            return (
              <div key={i} style={{
                padding: '12px 14px', borderRadius: '8px',
                background: '#f9fafb', borderLeft: `3px solid ${sc}`,
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                flexWrap: 'wrap', gap: '6px',
              }}>
                <div>
                  <div style={{ fontSize: '13px', fontWeight: 500, color: '#111827' }}>{e.event}</div>
                  <div style={{ fontSize: '11px', color: '#9ca3af', marginTop: 2 }}>
                    {new Date(e.time).toLocaleString()}
                  </div>
                </div>
                <span style={{
                  padding: '2px 8px', borderRadius: '6px', fontSize: '10px', fontWeight: 600,
                  background: sc + '15', color: sc, textTransform: 'uppercase',
                }}>
                  {e.severity}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function InfoItem({ label, value }) {
  return (
    <div style={{ padding: '8px 10px', background: '#f9fafb', borderRadius: '8px' }}>
      <div style={{ fontSize: '11px', color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.3px' }}>{label}</div>
      <div style={{ fontSize: '18px', fontWeight: 700, color: '#111827', marginTop: 2 }}>{value}</div>
    </div>
  );
}
