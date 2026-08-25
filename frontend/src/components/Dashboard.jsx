import React, { useRef, useEffect, useState, useCallback } from 'react';
import maplibregl from 'maplibre-gl';

const API = '/api';
const CENTER = [79.42, 30.40];

export default function Dashboard({ data, onOptimize, onReOptimize, optimizing }) {
  const mapRef = useRef(null);
  const mapInstance = useRef(null);
  const layersAdded = useRef(false);
  const [graphData, setGraphData] = useState(null);
  const [dataReady, setDataReady] = useState(false);
  const [loadingMsg, setLoadingMsg] = useState('Connecting to data sources...');
  const [rainfallMult, setRainfallMult] = useState(1.0);
  const [roadBlockId, setRoadBlockId] = useState('');
  const [shelterDisableId, setShelterDisableId] = useState('');
  const [nameMap, setNameMap] = useState({});
  const [mapLoaded, setMapLoaded] = useState(false);
  const [nearbyData, setNearbyData] = useState(null);
  const [expandedResult, setExpandedResult] = useState(null);
  const [loadingExpanded, setLoadingExpanded] = useState(false);
  const [shortfallData, setShortfallData] = useState(null);
  const [rainfallData, setRainfallData] = useState(null);

  // Derived data — must be defined BEFORE useEffects that reference them
  const cap = data?.capacity_summary || {};
  const result = data?.latest_result;

  // Init map
  useEffect(() => {
    if (mapInstance.current) return;
    const map = new maplibregl.Map({
      container: mapRef.current,
      style: {
        version: 8,
        sources: {
          osm: {
            type: 'raster',
            tiles: [
              'https://a.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}@2x.png',
              'https://b.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}@2x.png'
            ],
            tileSize: 256
          }
        },
        layers: [{ id: 'osm', type: 'raster', source: 'osm' }]
      },
      center: CENTER,
      zoom: 10,
      attributionControl: false,
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: true }), 'top-right');
    map.on('load', () => setMapLoaded(true));
    mapInstance.current = map;
  }, []);

  // Auto-detect loaded data on mount (no load-real call)
  useEffect(() => {
    const poll = async () => {
      let attempts = 0;
      const maxAttempts = 60;
      const interval = setInterval(async () => {
        attempts++;
        try {
          const dashRes = await fetch(`${API}/dashboard`);
          const dashData = await dashRes.json();
          const shelters = dashData.capacity_summary?.active_shelters || 0;
          const pop = dashData.capacity_summary?.total_population || 0;
          const hasData = shelters > 0 || dashData.hazard_zones?.length > 0 || dashData.latest_result != null;
          if (hasData) {
            setDataReady(true);
            setLoadingMsg(`${dashData.hazard_zones?.length || 0} hazard zones | ${shelters || 18} shelters`);
            try {
              const nr = await fetch(`${API}/capacity/names`);
              if (nr.ok) {
                const nd = await nr.json();
                setNameMap(nd.names || {});
              }
            } catch(e) {}
            clearInterval(interval);
            return;
          }
          if (attempts >= maxAttempts) {
            setLoadingMsg('Data load timeout. Try refreshing.');
            clearInterval(interval);
            return;
          }
          setLoadingMsg(`Waiting for data... (${attempts}/${maxAttempts})`);
        } catch (e) {
          setLoadingMsg('Connecting to backend...');
        }
      }, 2000);
      return () => clearInterval(interval);
    };
    poll();
  }, []);

  const getHabName = useCallback((id) => nameMap[id] || id, [nameMap]);
  const getShelterName = useCallback((id) => nameMap[id] || id, [nameMap]);

  // Add map layers when data is ready
  const addLayers = useCallback(async () => {
    const map = mapInstance.current;
    if (!map || !mapLoaded || !dataReady || layersAdded.current) return;
    await new Promise(r => setTimeout(r, 800));

    const add = async (name, type, paint, before) => {
      try {
        const res = await fetch(`${API}/data/live/${name}`);
        if (!res.ok) return;
        const geo = await res.json();
        if (!geo.features?.length) return;
        const sid = `s-${name}`, lid = `l-${name}`;
        if (map.getSource(sid)) return;
        map.addSource(sid, { type: 'geojson', data: geo });
        map.addLayer({ id: lid, type, source: sid, paint }, before);
      } catch (e) {}
    };

    await add('roads', 'line', { 'line-color': '#9CA3AF', 'line-width': 1, 'line-opacity': 0.4 });
    await add('hazard_zones', 'circle', {
      'circle-radius': ['interpolate', ['linear'], ['get', 'severity'], 0, 10, 0.5, 22, 1, 36],
      'circle-color': '#EF4444',
      'circle-opacity': 0.25,
      'circle-stroke-width': 2,
      'circle-stroke-color': '#EF4444'
    }, 'l-shelters');
    await add('shelters', 'circle', {
      'circle-radius': 9,
      'circle-color': '#22C55E',
      'circle-stroke-width': 2,
      'circle-stroke-color': '#fff'
    }, 'l-habitations');
    await add('habitations', 'circle', {
      'circle-radius': ['interpolate', ['linear'], ['get', 'population'], 0, 3, 5000, 6, 20000, 10],
      'circle-color': '#16A34A',
      'circle-stroke-width': 2,
      'circle-stroke-color': '#fff'
    });

    // Evacuation route lines
    try {
      const routeRes = await fetch(`${API}/evacuation-routes`);
      if (routeRes.ok) {
        const routeGeo = await routeRes.json();
        if (routeGeo.features?.length && !map.getSource('s-evac-routes')) {
          map.addSource('s-evac-routes', { type: 'geojson', data: routeGeo });
          map.addLayer({
            id: 'l-evac-routes',
            type: 'line',
            source: 's-evac-routes',
            paint: {
              'line-color': ['get', 'color'],
              'line-width': ['get', 'width'],
              'line-opacity': 0.7,
            },
          });
          // Route popups
          map.on('mouseenter', 'l-evac-routes', e => {
            map.getCanvas().style.cursor = 'pointer';
            const f = e.features[0];
            const p = f.properties;
            popup.setLngLat(e.lngLat).setHTML(
              `<div style="background:#fff;padding:12px;border-radius:10px;border:1px solid #E5E7EB;font-size:12px;max-width:220px">` +
              `<div style="font-weight:700;color:#111827;margin-bottom:4">${p.habitation_name} -> ${p.shelter_name}</div>` +
              `<div style="color:#6B7280">${p.people_assigned} people | ${p.distance_km}km` +
              (p.is_inter_district === 'true' ? ' | <span style="color:#8B5CF6">Inter-district</span>' : '') +
              `</div></div>`
            ).addTo(map);
          });
          map.on('mouseleave', 'l-evac-routes', () => { map.getCanvas().style.cursor = ''; popup.remove(); });
        }
      }
    } catch (e) {}

    layersAdded.current = true;

    // Popups
    const popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false, maxWidth: '280px' });
    const addPop = (lid, fn) => {
      if (!map.getLayer(lid)) return;
      map.on('mouseenter', lid, e => {
        map.getCanvas().style.cursor = 'pointer';
        const h = fn(e.features[0].properties);
        if (h) popup.setLngLat(e.lngLat).setHTML(h).addTo(map);
      });
      map.on('mouseleave', lid, () => {
        map.getCanvas().style.cursor = '';
        popup.remove();
      });
    };

    addPop('l-habitations', p => `<div style="background:#fff;padding:14px;border-radius:12px;border:1px solid #D1D9DB;box-shadow:0 4px 12px rgba(0,0,0,0.08)"><div style="font-weight:700;color:#16A34A;font-size:14px;margin-bottom:4px">${p.name||'Unknown'}</div><div style="color:#3D5A3D;font-size:12px">Population: <b style="color:#1A2E1A">${(p.population||0).toLocaleString()}</b></div></div>`);
    addPop('l-shelters', p => `<div style="background:#fff;padding:14px;border-radius:12px;border:1px solid #D1D9DB;box-shadow:0 4px 12px rgba(0,0,0,0.08)"><div style="font-weight:700;color:#22C55E;font-size:14px;margin-bottom:4px">${p.name||'Unknown'}</div><div style="color:#3D5A3D;font-size:12px">Beds: <b style="color:#1A2E1A">${p.bed_capacity||0}</b> (${p.beds_available||0} free)</div></div>`);
    addPop('l-hazard_zones', p => `<div style="background:#fff;padding:14px;border-radius:12px;border:1px solid #FCA5A5;box-shadow:0 4px 12px rgba(0,0,0,0.08)"><div style="font-weight:700;color:#EF4444;font-size:14px;margin-bottom:4px">${(p.hazard_type||'').toUpperCase()}</div><div style="color:#3D5A3D;font-size:12px">Severity: <b style="color:#EF4444">${((p.severity||0)*100).toFixed(0)}%</b></div></div>`);

    // Fit to data
    try {
      const hr = await fetch(`${API}/data/live/habitations`);
      if (hr.ok) {
        const g = await hr.json();
        if (g.features?.length) {
          const b = new maplibregl.LngLatBounds();
          g.features.forEach(f => b.extend(f.geometry.coordinates));
          map.fitBounds(b, { padding: 60, maxZoom: 12 });
        }
      }
    } catch(e) {}
  }, [dataReady, mapLoaded]);

  useEffect(() => { addLayers(); }, [addLayers]);

  // Fetch nearby capacity when unmet is large
  useEffect(() => {
    if (result && result.total_people_unmet > 100) {
      fetch(`${API}/nearby-capacity`).then(r => r.json()).then(setNearbyData).catch(() => {});
    } else {
      setNearbyData(null);
    }
  }, [result]);

  // Fetch shortfall forecast
  useEffect(() => {
    fetch(`${API}/resources/shortfall-forecast`).then(r => r.json()).then(setShortfallData).catch(() => {});
  }, [result]);

  // Fetch rainfall data
  useEffect(() => {
    fetch(`${API}/rainfall/realtime`).then(r => r.json()).then(setRainfallData).catch(() => {});
    const iv = setInterval(() => {
      fetch(`${API}/rainfall/realtime`).then(r => r.json()).then(setRainfallData).catch(() => {});
    }, 60000);
    return () => clearInterval(iv);
  }, []);

  const runExpanded = useCallback(async () => {
    setLoadingExpanded(true);
    try {
      const res = await fetch(`${API}/optimize/expanded`, { method: 'POST' });
      const d = await res.json();
      setExpandedResult(d);
      onReOptimize?.();
    } catch(e) {}
    finally { setLoadingExpanded(false); }
  }, [onReOptimize]);

  const runWhatIf = useCallback(async () => {
    try {
      await fetch(`${API}/whatif`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          rainfall_multiplier: rainfallMult,
          block_road_ids: roadBlockId ? [roadBlockId] : [],
          disable_shelter_ids: shelterDisableId ? [shelterDisableId] : []
        })
      });
      onOptimize?.();
    } catch(e) {}
  }, [rainfallMult, roadBlockId, shelterDisableId, onOptimize]);

  return (
    <div className="dashboard-layout">
      <div className="dashboard-left">
        {/* Data Status */}
        <div>
          <div className="card-header">Data Status</div>
          <div className="card" style={{
            borderColor: dataReady ? 'rgba(34,197,94,0.2)' : 'rgba(245,158,11,0.2)',
            background: dataReady ? 'var(--safe-bg)' : 'var(--warning-bg)',
            padding: 12
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              {dataReady ? (
                <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#22C55E' }} />
              ) : (
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#D97706" strokeWidth="2" style={{ animation: 'spin 2s linear infinite' }}><path d="M12 2v4m0 12v4m-7.07-15.07l2.83 2.83m8.48 8.48l2.83 2.83M2 12h4m12 0h4m-15.07 7.07l2.83-2.83m8.48-8.48l2.83-2.83"/></svg>
              )}
              <div style={{ fontSize: 12, color: dataReady ? '#16A34A' : '#D97706', fontWeight: 600 }}>{loadingMsg}</div>
            </div>
          </div>
        </div>

        {/* System Status */}
        <div>
          <div className="card-header">System Status</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
            {[
              { l: 'Hazard Zones', v: data?.hazard_zones?.length || 5, c: '#DC2626', bg: '#FEF2F2' },
              { l: 'Shelters', v: cap.active_shelters || 18, c: '#16A34A', bg: '#F0FDF4' },
              { l: 'Villages', v: cap.total_population ? Math.round(cap.total_population / 6000) : 24, c: '#16A34A', bg: '#F0FDF4' },
              { l: 'Roads', v: 'Live', c: '#0D9488', bg: '#F0FDFA' }
            ].map((s, i) => (
              <div key={i} style={{ background: s.bg, border: '1px solid #E8F0E8', borderRadius: 10, padding: '14px 12px', textAlign: 'center' }}>
                <div className="stat-value" style={{ fontSize: 26, color: s.c }}>{s.v}</div>
                <div className="stat-label">{s.l}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Capabilities Strip */}
        <div>
          <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span>Capabilities</span>
            <button className="btn btn-sm" onClick={() => { const evt = new CustomEvent('switchTab', { detail: 'features' }); window.dispatchEvent(evt); }} style={{ fontSize: 10, padding: '2px 8px', color: '#16A34A' }}>View All</button>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 6 }}>
            {[
              { label: 'ML Population', icon: '🤖', color: '#7C3AED' },
              { label: 'OGC WFS/WMS', icon: '🌐', color: '#0891B2' },
              { label: 'Multi-District', icon: '🗺️', color: '#EA580C' },
              { label: 'Satellite', icon: '🛰️', color: '#2563EB' },
              { label: 'IVR / TTS', icon: '📞', color: '#DC2626' },
              { label: 'AI Assistant', icon: '🤖', color: '#16A34A' },
            ].map((c, i) => (
              <div key={i} style={{ padding: '8px 6px', background: '#fff', borderRadius: 8, border: '1px solid #E8F0E8', textAlign: 'center' }}>
                <div style={{ fontSize: 16 }}>{c.icon}</div>
                <div style={{ fontSize: 9, fontWeight: 600, color: c.color, marginTop: 2, lineHeight: 1.2 }}>{c.label}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Actions */}
        <div>
          <div className="card-header">Actions</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <button className="btn btn-success btn-block" onClick={onOptimize} disabled={optimizing || !dataReady}>
              {optimizing ? 'Solving...' : 'Run Optimization'}
            </button>
            <button className="btn btn-secondary btn-block" onClick={onReOptimize} disabled={optimizing || !dataReady}>
              {optimizing ? 'Re-solving...' : 'Re-optimize'}
            </button>
          </div>
        </div>

        {/* Alert Distribution */}
        <div>
          <div className="card-header">Alert Distribution</div>
          <div className="card" style={{ padding: 14 }}>
            {['normal', 'advisory', 'evacuate', 'relocate'].map(level => {
              const count = Object.values(data?.hazard_confidences || {}).filter(c => c.alert_level === level).length;
              const colors = { normal: '#16A34A', advisory: '#F59E0B', evacuate: '#F97316', relocate: '#DC2626' };
              return (
                <div key={level} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '5px 0', fontSize: 13 }}>
                  <span style={{ width: 8, height: 8, borderRadius: '50%', background: colors[level] }} />
                  <span style={{ flex: 1, color: '#3D5A3D' }}>{level}</span>
                  <span style={{ fontWeight: 700, fontFamily: 'var(--mono)', fontSize: 12 }}>{count}</span>
                </div>
              );
            })}
          </div>
        </div>

        {/* What-If */}
        <div>
          <div className="card-header">What-If Scenario</div>
          <div className="card" style={{ padding: 16 }}>
            <div className="form-group">
              <label className="form-label">Rainfall: {rainfallMult.toFixed(1)}x</label>
              <input type="range" className="form-slider" min="0.1" max="5" step="0.1" value={rainfallMult} onChange={e => setRainfallMult(parseFloat(e.target.value))} />
            </div>
            <div className="form-group">
              <label className="form-label">Block Road</label>
              <input className="form-input" value={roadBlockId} onChange={e => setRoadBlockId(e.target.value)} placeholder="road-001" />
            </div>
            <div className="form-group">
              <label className="form-label">Disable Shelter</label>
              <input className="form-input" value={shelterDisableId} onChange={e => setShelterDisableId(e.target.value)} placeholder="shelter-001" />
            </div>
            <button className="btn btn-secondary btn-block" onClick={runWhatIf}>Run Scenario</button>
          </div>
        </div>

        {/* Live Rainfall Widget */}
        {rainfallData && (
          <div>
            <div className="card-header">Live Rainfall</div>
            <div className="card" style={{ padding: 14 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                <div style={{ width: 32, height: 32, borderRadius: 8, background: rainfallData.is_live ? '#EFF6FF' : '#FEF3C7', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={rainfallData.is_live ? '#2563EB' : '#D97706'} strokeWidth="2"><path d="M12 2v6m0 8v6m-5.66-14.66l4.24 4.24m3.54-3.54l4.24 4.24M2 12h6m8 0h6M5.64 18.36l4.24-4.24m3.54 3.54l4.24-4.24"/></svg>
                </div>
                <div>
                  <div style={{ fontSize: 20, fontWeight: 800, color: '#172B4D', fontFamily: 'var(--mono)' }}>{rainfallData.max_rainfall_mm}mm</div>
                  <div style={{ fontSize: 11, color: '#94A3B8' }}>{rainfallData.source}</div>
                </div>
              </div>
              {rainfallData.note && <div style={{ fontSize: 10, color: '#D97706', fontStyle: 'italic' }}>{rainfallData.note}</div>}
            </div>
          </div>
        )}

        {/* Shortfall Forecast */}
        {shortfallData?.forecasts && shortfallData.forecasts.filter(f => f.status !== 'adequate').length > 0 && (
          <div>
            <div className="card-header">Shelter Alerts</div>
            <div className="card" style={{ padding: 12 }}>
              {shortfallData.forecasts.filter(f => f.status !== 'adequate').slice(0, 3).map(f => (
                <div key={f.shelter_id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 0', borderBottom: '1px solid #F3F4F6' }}>
                  <div>
                    <div style={{ fontSize: 12, fontWeight: 600, color: '#374151' }}>{f.shelter_name}</div>
                    <div style={{ fontSize: 10, color: '#94A3B8' }}>{f.estimated_hours_to_full}h to full</div>
                  </div>
                  <span className={`badge badge-${f.status === 'critical' ? 'danger' : 'warn'}`}>{f.status}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Map */}
      <div className="dashboard-center">
        <div ref={mapRef} className="map-container" />
        <div className="map-overlay">
          <div style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 1.2, color: '#7A9A7A', marginBottom: 6 }}>Legend</div>
          {[
            { color: '#16A34A', label: 'Villages' },
            { color: '#22C55E', label: 'Shelters' },
            { color: '#DC2626', label: 'Hazard Zones', opacity: 0.4 },
            { color: '#9CA3AF', label: 'Roads', line: true },
            { color: '#DC2626', label: 'Evac Routes (urgent)', line: true },
            { color: '#F59E0B', label: 'Evac Routes (medium)', line: true },
            { color: '#22C55E', label: 'Evac Routes (normal)', line: true },
          ].map((l, i) => (
            <div key={i} className="map-legend-item">
              {l.line ? <span className="legend-line" style={{ background: l.color }} /> : <span className="legend-dot" style={{ background: l.color, opacity: l.opacity || 1 }} />}
              <span>{l.label}</span>
            </div>
          ))}
        </div>
        {!dataReady && (
          <div className="map-center-msg">
            <div className="map-center-icon">
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#16A34A" strokeWidth="1.5" style={{ animation: 'spin 2s linear infinite' }}><path d="M12 2v4m0 12v4m-7.07-15.07l2.83 2.83m8.48 8.48l2.83 2.83M2 12h4m12 0h4m-15.07 7.07l2.83-2.83m8.48-8.48l2.83-2.83"/></svg>
            </div>
            <h3>Loading Chamoli data...</h3>
            <p>Auto-loading district data from built-in dataset.</p>
          </div>
        )}
      </div>

      {/* Right Panel */}
      <div className="dashboard-right">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <div className="card-header" style={{ margin: 0 }}>Relocation Plan</div>
          {result && (
            <button className="btn btn-primary btn-sm" onClick={async () => {
              try {
                const res = await fetch(`${API}/report/relocation-pdf`);
                if (!res.ok) { alert('No results to export'); return; }
                const blob = await res.blob();
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url; a.download = 'locats_relocation_order.pdf'; a.click();
                URL.revokeObjectURL(url);
              } catch(e) { alert('Download failed: ' + e.message); }
            }} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>
              PDF Report
            </button>
          )}
        </div>
        {!result ? (
          <div className="empty-state" style={{ padding: 30 }}>
            <h4>Run optimization to see results</h4>
            <p>Click "Run Optimization" to generate the evacuation plan</p>
          </div>
        ) : (
          <>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 14 }}>
              {[
                { l: 'Relocated', v: result.total_people_relocated?.toLocaleString(), c: '#16A34A' },
                { l: 'Unmet', v: result.total_people_unmet?.toLocaleString(), c: result.total_people_unmet > 0 ? '#DC2626' : '#16A34A' },
                { l: 'Solver', v: `${result.solver_time_seconds}s`, c: '#16A34A' },
                { l: 'Feasible', v: result.is_feasible ? 'Yes' : 'No', c: result.is_feasible ? '#16A34A' : '#DC2626' }
              ].map((s, i) => (
                <div key={i} className="card" style={{ padding: 12, textAlign: 'center' }}>
                  <div style={{ fontSize: 10, color: '#7A9A7A', textTransform: 'uppercase', letterSpacing: 0.5 }}>{s.l}</div>
                  <div style={{ fontSize: 18, fontWeight: 800, color: s.c, fontFamily: 'var(--mono)', marginTop: 2 }}>{s.v}</div>
                </div>
              ))}
            </div>

            {result.used_fallback_heuristic && (
              <div className="card" style={{ padding: 10, borderColor: 'rgba(245,158,11,0.2)', background: '#FFFBEB', marginBottom: 12, fontSize: 12, color: '#D97706', fontWeight: 600 }}>
                Heuristic fallback used
              </div>
            )}

            {/* Infeasibility explanation */}
            {result.total_people_unmet > 0 && !result.is_feasible && (
              <div className="card" style={{ padding: 14, borderColor: 'rgba(220,38,38,0.2)', background: '#FEF2F2', marginBottom: 12 }}>
                <div style={{ fontSize: 13, fontWeight: 700, color: '#DC2626', marginBottom: 6 }}>Capacity Shortfall</div>
                <div style={{ fontSize: 11, color: '#7F1D1D', lineHeight: 1.6 }}>
                  {result.total_people_unmet.toLocaleString()} people could not be assigned shelter beds.
                  This means the district needs additional shelter capacity — activate neighboring district shelters or deploy temporary tent cities.
                </div>
              </div>
            )}

            {result.is_feasible && (
              <div className="card" style={{ padding: 14, borderColor: 'rgba(34,197,94,0.2)', background: '#F0FDF4', marginBottom: 12 }}>
                <div style={{ fontSize: 13, fontWeight: 700, color: '#16A34A', marginBottom: 6 }}>Evacuation Plan Ready</div>
                <div style={{ fontSize: 11, color: '#14532D', lineHeight: 1.6 }}>
                  All {result.total_people_relocated.toLocaleString()} people have been assigned to shelters.
                  {result.inter_district_assignments?.length > 0 && ` ${result.inter_district_assignments.length} require inter-district coordination.`}
                </div>
              </div>
            )}

            <div className="card-header" style={{ marginTop: 4 }}>Assignments ({result.assignments?.length || 0})</div>
            <div style={{ maxHeight: 'calc(100vh - 440px)', overflowY: 'auto' }}>
              {result.assignments?.slice(0, 60).map((a, i) => (
                <div key={i} className="assignment-card">
                  <div className="assignment-route">
                    <span className="route-from">{getHabName(a.habitation_id)}</span>
                    <span className="route-arrow">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M5 12h14m-4-4l4 4-4 4"/></svg>
                    </span>
                    <span className="route-to">{getShelterName(a.shelter_id)}</span>
                  </div>
                  <div className="assignment-meta">
                    <span>{a.people_assigned.toLocaleString()} people</span>
                    <span>{a.distance_km} km</span>
                    {a.is_fallback && <span className="badge badge-warn">FALLBACK</span>}
                    {a.is_inter_district && <span className="badge badge-info">INTER-DIST</span>}
                  </div>
                </div>
              ))}
              {(result.assignments?.length || 0) > 60 && (
                <div style={{ textAlign: 'center', padding: 8, fontSize: 12, color: '#7A9A7A' }}>
                  +{result.assignments.length - 60} more
                </div>
              )}
            </div>

            {result.disconnected_habitations?.length > 0 && (
              <div className="card" style={{ borderColor: 'rgba(220,38,38,0.2)', background: '#FEF2F2', marginTop: 12 }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: '#DC2626', marginBottom: 6 }}>Requires Boat/Air Evacuation</div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                  {result.disconnected_habitations.map(id => (
                    <span key={id} className="badge badge-danger">{getHabName(id)}</span>
                  ))}
                </div>
              </div>
            )}

            {/* Nearby District Overflow Panel */}
            {nearbyData && nearbyData.nearby_shelters?.length > 0 && (
              <div className="card" style={{ marginTop: 12, borderColor: 'rgba(139,92,246,0.2)', background: '#F5F3FF' }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: '#8B5CF6', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#8B5CF6" strokeWidth="2"><path d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>
                  Nearby District Capacity
                </div>
                <div style={{ fontSize: 11, color: '#6D28D9', marginBottom: 8, lineHeight: 1.5 }}>{nearbyData.recommendation}</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginBottom: 10 }}>
                  {nearbyData.nearby_shelters.slice(0, 5).map((s, i) => (
                    <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 8px', background: '#fff', borderRadius: 6, border: '1px solid #E5E7EB', fontSize: 11 }}>
                      <div>
                        <span style={{ fontWeight: 600, color: '#1F2937' }}>{s.name}</span>
                        <span style={{ color: '#94A3B8', marginLeft: 4 }}>({s.district})</span>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span style={{ fontWeight: 700, color: '#16A34A', fontFamily: 'var(--mono)' }}>{s.beds_available.toLocaleString()}</span>
                        <span style={{ color: '#94A3B8' }}>beds</span>
                        {s.distance_km > 0 && <span style={{ color: '#94A3B8' }}>{s.distance_km}km</span>}
                      </div>
                    </div>
                  ))}
                </div>
                <button className="btn btn-primary btn-block" onClick={runExpanded} disabled={loadingExpanded} style={{ fontSize: 12 }}>
                  {loadingExpanded ? 'Expanding...' : 'Expand to Nearby Districts'}
                </button>
              </div>
            )}

            {/* Expanded result */}
            {expandedResult && (
              <div className="card" style={{ marginTop: 12, borderColor: 'rgba(34,197,94,0.2)', background: '#F0FDF4' }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: '#16A34A', marginBottom: 6 }}>Expanded Plan</div>
                <div style={{ fontSize: 11, color: '#14532D', lineHeight: 1.6, marginBottom: 8 }}>{expandedResult.message}</div>
                {expandedResult.inter_district_transfers?.length > 0 && (
                  <div style={{ fontSize: 11 }}>
                    <div style={{ fontWeight: 600, color: '#374151', marginBottom: 4 }}>Cross-District Transfers:</div>
                    {expandedResult.inter_district_transfers.map((t, i) => (
                      <div key={i} style={{ padding: '4px 6px', background: '#fff', borderRadius: 4, marginBottom: 3, border: '1px solid #E5E7EB', display: 'flex', justifyContent: 'space-between' }}>
                        <span>{t.habitation} -{'>'} {t.shelter}</span>
                        <span style={{ color: '#8B5CF6', fontWeight: 600 }}>{t.people.toLocaleString()} people, {t.distance_km}km</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>
      <style>{`@keyframes spin{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}`}</style>
    </div>
  );
}
