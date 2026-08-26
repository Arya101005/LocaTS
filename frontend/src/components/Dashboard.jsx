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
  const [selectedHab, setSelectedHab] = useState(null);
  const [habDetails, setHabDetails] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [socialVuln, setSocialVuln] = useState(null);
  const [scenarioResult, setScenarioResult] = useState(null);
  const [scenarioLoading, setScenarioLoading] = useState(false);

  const cap = data?.capacity_summary || {};
  const result = data?.latest_result;

  // Compute overview metrics from data
  const totalHabitations = cap.active_shelters ? (cap.total_population ? Math.round(cap.total_population / 6000) : 24) : 24;
  const hazardZones = data?.hazard_zones?.length || 0;
  const confidences = data?.hazard_confidences || {};
  const atRiskCount = Object.values(confidences).filter(c => c.alert_level === 'evacuate' || c.alert_level === 'relocate').length;
  const advisoryCount = Object.values(confidences).filter(c => c.alert_level === 'advisory').length;
  const peopleAtRisk = result ? (result.total_people_unmet || 0) + (result.total_people_relocated || 0) : 0;
  const redZoneCount = atRiskCount;
  const safeSites = cap.active_shelters || 0;
  const peopleToRelocate = result?.total_people_relocated || 0;

  // Build alerts from hazard data
  useEffect(() => {
    if (!dataReady) return;
    const newAlerts = [];
    Object.entries(confidences).forEach(([key, conf]) => {
      if (conf.alert_level === 'evacuate' || conf.alert_level === 'relocate') {
        const habId = key.split(':')[0];
        newAlerts.push({
          id: key,
          type: 'critical',
          message: `${getHabName(habId)} requires immediate action`,
          detail: `${conf.hazard_type || 'hazard'} risk — ${conf.alert_level}`,
          time: 'now',
        });
      }
    });
    if (rainfallData?.max_rainfall_mm > 10) {
      newAlerts.push({
        id: 'rainfall',
        type: 'warning',
        message: `Heavy rainfall detected: ${rainfallData.max_rainfall_mm}mm`,
        detail: rainfallData.source || 'Open-Meteo',
        time: 'now',
      });
    }
    setAlerts(newAlerts.slice(0, 8));
  }, [dataReady, confidences, rainfallData]);

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

  // Auto-detect loaded data — fetch once, then cache
  useEffect(() => {
    let mounted = true;
    const loadData = async () => {
      // Try cached data first
      try {
        const dashRes = await fetch(`${API}/dashboard`);
        const dashData = await dashRes.json();
        const shelters = dashData.capacity_summary?.active_shelters || 0;
        if (shelters > 0 || dashData.hazard_zones?.length > 0 || dashData.latest_result != null) {
          if (mounted) {
            setDataReady(true);
            setLoadingMsg(`${dashData.hazard_zones?.length || 0} hazard zones | ${shelters} shelters`);
          }
          try {
            const nr = await fetch(`${API}/capacity/names`);
            if (nr.ok && mounted) {
              const nd = await nr.json();
              setNameMap(nd.names || {});
            }
          } catch(e) {}
          return;
        }
      } catch(e) {}
      // Poll if not loaded yet (max 30s)
      let attempts = 0;
      const interval = setInterval(async () => {
        attempts++;
        try {
          const dashRes = await fetch(`${API}/dashboard`);
          const dashData = await dashRes.json();
          const shelters = dashData.capacity_summary?.active_shelters || 0;
          if (shelters > 0 || dashData.hazard_zones?.length > 0) {
            if (mounted) {
              setDataReady(true);
              setLoadingMsg(`${dashData.hazard_zones?.length || 0} hazard zones | ${shelters} shelters`);
            }
            try {
              const nr = await fetch(`${API}/capacity/names`);
              if (nr.ok && mounted) {
                const nd = await nr.json();
                setNameMap(nd.names || {});
              }
            } catch(e) {}
            clearInterval(interval);
            return;
          }
          if (attempts >= 15) {
            if (mounted) setLoadingMsg('Data load timeout.');
            clearInterval(interval);
          }
        } catch (e) {
          if (mounted) setLoadingMsg('Connecting...');
        }
      }, 2000);
    };
    loadData();
    return () => { mounted = false; };
  }, []);

  // Fetch social vulnerability data
  useEffect(() => {
    fetch(`${API}/social-vulnerability`).then(r => r.json()).then(setSocialVuln).catch(() => {});
  }, [dataReady]);

  const getHabName = useCallback((id) => nameMap[id] || id, [nameMap]);
  const getShelterName = useCallback((id) => nameMap[id] || id, [nameMap]);

  // Add map layers
  const addLayers = useCallback(async (hasResult) => {
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

    // Evacuation routes (only if optimization has been run)
    if (hasResult) {
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
        }
      }
    } catch (e) {}
    } // end if (hasResult)

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
      map.on('mouseleave', lid, () => { map.getCanvas().style.cursor = ''; popup.remove(); });
    };

    addPop('l-habitations', p => {
      const id = p.id || '';
      const confKeys = Object.keys(confidences).filter(k => k.startsWith(id + ':'));
      const worstLevel = confKeys.reduce((w, k) => {
        const l = confidences[k]?.alert_level;
        if (l === 'evacuate' || l === 'relocate') return 'critical';
        if (l === 'advisory' && w !== 'critical') return 'warning';
        return w;
      }, 'normal');
      const levelColors = { critical: '#EF4444', warning: '#F59E0B', normal: '#22C55E' };
      const levelLabels = { critical: 'RED ZONE', warning: 'ADVISORY', normal: 'SAFE' };
      return `<div style="background:#fff;padding:14px;border-radius:12px;border:1px solid #D1D9DB;box-shadow:0 4px 12px rgba(0,0,0,0.08);min-width:200px">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
          <div style="font-weight:700;color:#16A34A;font-size:14px">${p.name||'Unknown'}</div>
          <span style="padding:2px 8px;border-radius:10px;font-size:9px;font-weight:700;background:${levelColors[worstLevel]}20;color:${levelColors[worstLevel]}">${levelLabels[worstLevel]}</span>
        </div>
        <div style="color:#3D5A3D;font-size:12px;line-height:1.6">
          Population: <b style="color:#1A2E1A">${(p.population||0).toLocaleString()}</b><br/>
          District: ${p.district || 'Chamoli'}
        </div>
        <div style="margin-top:6px;font-size:10px;color:#94A3B8">Click for full risk details →</div>
      </div>`;
    });
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
  }, [dataReady, mapLoaded, confidences]);

  useEffect(() => { addLayers(data?.latest_result != null); }, [addLayers, data]);

  // Fetch nearby capacity
  useEffect(() => {
    if (result && result.total_people_unmet > 100) {
      fetch(`${API}/nearby-capacity`).then(r => r.json()).then(setNearbyData).catch(() => {});
    } else {
      setNearbyData(null);
    }
  }, [result]);

  // Fetch shortfall forecast (only when graph is loaded)
  useEffect(() => {
    if (dataReady) {
      fetch(`${API}/resources/shortfall-forecast`).then(r => {
        if (r.ok) return r.json();
        throw new Error();
      }).then(setShortfallData).catch(() => setShortfallData(null));
    }
  }, [dataReady]);

  // Fetch rainfall
  useEffect(() => {
    fetch(`${API}/rainfall/realtime`).then(r => r.json()).then(setRainfallData).catch(() => {});
    const iv = setInterval(() => {
      fetch(`${API}/rainfall/realtime`).then(r => r.json()).then(setRainfallData).catch(() => {});
    }, 60000);
    return () => clearInterval(iv);
  }, []);

  // Fetch explainability for selected habitation
  const fetchHabDetails = useCallback(async (habId) => {
    setSelectedHab(habId);
    try {
      const res = await fetch(`${API}/explain/${habId}`);
      if (res.ok) setHabDetails(await res.json());
    } catch(e) {}
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
    setScenarioLoading(true);
    try {
      const res = await fetch(`${API}/whatif`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          rainfall_multiplier: rainfallMult,
          block_road_ids: roadBlockId ? [roadBlockId] : [],
          disable_shelter_ids: shelterDisableId ? [shelterDisableId] : []
        })
      });
      if (res.ok) {
        const data = await res.json();
        setScenarioResult(data);
      }
    } catch(e) { console.error('What-if failed:', e); }
    finally { setScenarioLoading(false); }
  }, [rainfallMult, roadBlockId, shelterDisableId]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* === OVERVIEW SUMMARY BAR === */}
      <div style={{ background: '#fff', borderBottom: '1px solid var(--border)', padding: '14px 24px', display: 'flex', gap: 16, alignItems: 'center', flexShrink: 0 }}>          {[
            { icon: 'H', label: 'Total Habitants', value: totalHabitations.toLocaleString(), color: '#172B4D' },
            { icon: '!', label: 'At Risk', value: `${atRiskCount} (${atRiskCount > 0 ? ((atRiskCount / Math.max(totalHabitations, 1)) * 100).toFixed(1) : '0'}%)`, color: '#DC2626' },
            { icon: 'P', label: 'People at Risk', value: peopleAtRisk.toLocaleString(), color: '#EA580C' },
            { icon: 'R', label: 'Red Zone Habitations', value: redZoneCount.toLocaleString(), color: '#DC2626' },
            { icon: 'S', label: 'Safe Sites', value: safeSites.toLocaleString(), color: '#16A34A' },
            { icon: 'E', label: 'People to Relocate', value: peopleToRelocate.toLocaleString(), color: '#2563EB' },
          ].map((s, i) => (
            <div key={i} className="animate-fade-in-up" style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 10, padding: '8px 12px', background: `${s.color}08`, borderRadius: 10, border: `1px solid ${s.color}15`, transition: 'transform 0.2s, box-shadow 0.2s' }} onMouseEnter={e => { e.currentTarget.style.transform = 'translateY(-2px)'; e.currentTarget.style.boxShadow = `0 4px 12px ${s.color}15`; }} onMouseLeave={e => { e.currentTarget.style.transform = ''; e.currentTarget.style.boxShadow = ''; }}>
              <div style={{ width: 32, height: 32, borderRadius: 8, background: `${s.color}12`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, fontWeight: 800, color: s.color }}>{s.icon}</div>
            <div>
              <div style={{ fontSize: 18, fontWeight: 800, color: s.color, fontFamily: 'var(--mono)', letterSpacing: -0.5 }}>{s.value}</div>
              <div style={{ fontSize: 10, color: '#94A3B8', fontWeight: 500 }}>{s.label}</div>
            </div>
          </div>
        ))}
      </div>

      {/* === MAIN 3-COLUMN LAYOUT === */}
      <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr 380px', flex: 1, overflow: 'hidden' }}>

        {/* LEFT PANEL */}
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
                  <span className="status-dot" />
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
            <div className="stagger-children" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
              {[
                { l: 'Hazard Zones', v: data?.hazard_zones?.length || 5, c: '#DC2626', bg: '#FEF2F2' },
                { l: 'Shelters', v: cap.active_shelters || 18, c: '#16A34A', bg: '#F0FDF4' },
                { l: 'Villages', v: totalHabitations, c: '#16A34A', bg: '#F0FDF4' },
                { l: 'Roads', v: 'Live', c: '#0D9488', bg: '#F0FDFA' }
              ].map((s, i) => (
                <div key={i} className="animate-fade-in-up" style={{ background: s.bg, border: '1px solid #E8F0E8', borderRadius: 10, padding: '14px 12px', textAlign: 'center', transition: 'transform 0.2s' }} onMouseEnter={e => { e.currentTarget.style.transform = 'scale(1.03)'; }} onMouseLeave={e => { e.currentTarget.style.transform = ''; }}>
                  <div className="stat-value" style={{ fontSize: 26, color: s.c }}>{s.v}</div>
                  <div className="stat-label">{s.l}</div>
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
                const count = Object.values(confidences).filter(c => c.alert_level === level).length;
                const colors = { normal: '#16A34A', advisory: '#F59E0B', evacuate: '#F97316', relocate: '#DC2626' };
                const total = Object.keys(confidences).length || 1;
                return (
                  <div key={level} style={{ marginBottom: 6 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, marginBottom: 3 }}>
                      <span style={{ width: 8, height: 8, borderRadius: '50%', background: colors[level], flexShrink: 0 }} />
                      <span style={{ flex: 1, color: '#3D5A3D', fontWeight: 500 }}>{level}</span>
                      <span style={{ fontWeight: 700, fontFamily: 'var(--mono)', fontSize: 12 }}>{count}</span>
                    </div>
                    <div style={{ height: 4, background: '#F3F4F6', borderRadius: 2, overflow: 'hidden' }}>
                      <div style={{ width: `${(count / total) * 100}%`, height: '100%', background: colors[level], borderRadius: 2, transition: 'width 0.5s ease' }} />
                    </div>
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
              <button className="btn btn-secondary btn-block" onClick={runWhatIf} disabled={scenarioLoading}>
                {scenarioLoading ? 'Running...' : 'Run Scenario'}
              </button>
              {scenarioResult && (
                <button className="btn btn-block" onClick={() => setScenarioResult(null)} style={{ marginTop: 6, fontSize: 11, padding: '6px 0', background: '#F1F5F9', color: '#64748B', border: '1px solid #E2E8F0', borderRadius: 8, cursor: 'pointer' }}>
                  Clear Scenario
                </button>
              )}
            </div>
          </div>

          {/* Live Rainfall */}
          {rainfallData && (
            <div>
              <div className="card-header">Live Rainfall</div>
              <div className="card" style={{ padding: 14 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                  <div style={{ width: 32, height: 32, borderRadius: 8, background: rainfallData.is_live ? '#EFF6FF' : '#FEF3C7', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={rainfallData.is_live ? '#2563EB' : '#D97706'} strokeWidth="2"><path d="M20 16.58A5 5 0 0018 7h-1.26A8 8 0 104 15.25"/></svg>
                  </div>
                  <div>
                    <div style={{ fontSize: 20, fontWeight: 800, color: '#172B4D', fontFamily: 'var(--mono)' }}>{rainfallData.max_rainfall_mm}mm</div>
                    <div style={{ fontSize: 11, color: '#94A3B8' }}>{rainfallData.source}</div>
                  </div>
                </div>
                {rainfallData.readings && (
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(80px, 1fr))', gap: 4 }}>
                    {rainfallData.readings.slice(0, 7).map((r, i) => (
                      <div key={i} style={{ textAlign: 'center', padding: '4px 2px', background: r.rainfall_mm > 5 ? '#FEF2F2' : '#F0FDF4', borderRadius: 6 }}>
                        <div style={{ fontSize: 11, fontWeight: 700, color: r.rainfall_mm > 5 ? '#DC2626' : '#16A34A' }}>{r.rainfall_mm}mm</div>
                        <div style={{ fontSize: 8, color: '#94A3B8' }}>{r.name}</div>
                      </div>
                    ))}
                  </div>
                )}
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

        {/* CENTER: MAP */}
        <div className="dashboard-center" style={{ position: 'relative' }}>
          <div ref={mapRef} className="map-container" />
          <div className="map-overlay">
            <div style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 1.2, color: '#7A9A7A', marginBottom: 6 }}>Legend</div>
            {[
              { color: '#16A34A', label: 'Villages' },
              { color: '#22C55E', label: 'Shelters' },
              { color: '#DC2626', label: 'Hazard Zones', opacity: 0.4 },
              { color: '#9CA3AF', label: 'Roads', line: true },
              { color: '#DC2626', label: 'Urgent Routes', line: true },
              { color: '#F59E0B', label: 'Medium Routes', line: true },
              { color: '#22C55E', label: 'Normal Routes', line: true },
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

        {/* RIGHT PANEL */}
        <div className="dashboard-right">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <div className="card-header" style={{ margin: 0 }}>Relocation Plan</div>
            {result && (
              <button className="btn btn-primary btn-sm" onClick={async () => {
                try {
                  const res = await fetch(`${API}/report/relocation-pdf`);
                  if (!res.ok) return;
                  const blob = await res.blob();
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement('a'); a.href = url; a.download = 'locats_relocation_order.pdf'; a.click();
                  URL.revokeObjectURL(url);
                } catch(e) {}
              }} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>
                PDF
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
              {/* Result stats */}
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

              {/* Feasibility explanation */}
              {result.is_feasible ? (
                <div className="card" style={{ padding: 14, borderColor: 'rgba(34,197,94,0.2)', background: '#F0FDF4', marginBottom: 12 }}>
                  <div style={{ fontSize: 13, fontWeight: 700, color: '#16A34A', marginBottom: 4 }}>✅ Evacuation Plan Ready</div>
                  <div style={{ fontSize: 11, color: '#14532D', lineHeight: 1.6 }}>
                    All {result.total_people_relocated.toLocaleString()} people assigned.
                    {result.inter_district_assignments?.length > 0 && ` ${result.inter_district_assignments.length} inter-district.`}
                  </div>
                </div>
              ) : (
                <div className="card" style={{ padding: 14, borderColor: 'rgba(220,38,38,0.2)', background: '#FEF2F2', marginBottom: 12 }}>                   <div style={{ fontSize: 13, fontWeight: 700, color: '#DC2626', marginBottom: 4 }}>Capacity Shortfall</div>
                  <div style={{ fontSize: 11, color: '#7F1D1D', lineHeight: 1.6 }}>
                    {result.total_people_unmet.toLocaleString()} people unassigned. Activate nearby district shelters.
                  </div>
                </div>
              )}

              {/* Priority Classification */}
              <div style={{ marginBottom: 14 }}>
                <div className="card-header">Priority Classification</div>
                <div className="card" style={{ padding: 12 }}>
                  {[
                    { level: 'Level 1 (Immediate)', color: '#DC2626', bg: '#FEF2F2', pct: result.assignments ? Math.round((result.assignments.filter(a => a.people_assigned > 500).length / Math.max(result.assignments.length, 1)) * 100) : 0 },
                    { level: 'Level 2 (Short-Term)', color: '#F59E0B', bg: '#FFFBEB', pct: result.assignments ? Math.round((result.assignments.filter(a => a.people_assigned <= 500 && a.people_assigned > 100).length / Math.max(result.assignments.length, 1)) * 100) : 0 },
                    { level: 'Level 3 (Medium-Term)', color: '#16A34A', bg: '#F0FDF4', pct: result.assignments ? Math.round((result.assignments.filter(a => a.people_assigned <= 100).length / Math.max(result.assignments.length, 1)) * 100) : 0 },
                  ].map((p, i) => (
                    <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '5px 0', fontSize: 12 }}>
                      <span style={{ width: 8, height: 8, borderRadius: '50%', background: p.color, flexShrink: 0 }} />
                      <span style={{ flex: 1, color: '#3D5A3D', fontWeight: 500 }}>{p.level}</span>
                      <span style={{ fontWeight: 700, fontFamily: 'var(--mono)', fontSize: 11, color: p.color }}>{p.pct}%</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Assignments */}
              <div className="card-header" style={{ marginTop: 4 }}>Assignments ({result.assignments?.length || 0})</div>
              <div style={{ maxHeight: 'calc(100vh - 520px)', overflowY: 'auto' }}>
                {result.assignments?.slice(0, 40).map((a, i) => (
                  <div key={i} className="assignment-card" style={{ cursor: 'pointer' }} onClick={() => fetchHabDetails(a.habitation_id)}>
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
                {(result.assignments?.length || 0) > 40 && (
                  <div style={{ textAlign: 'center', padding: 8, fontSize: 12, color: '#7A9A7A' }}>
                    +{result.assignments.length - 40} more
                  </div>
                )}
              </div>

              {/* Disconnected habitations */}
              {result.disconnected_habitations?.length > 0 && (
                <div className="card" style={{ borderColor: 'rgba(220,38,38,0.2)', background: '#FEF2F2', marginTop: 12 }}>                   <div style={{ fontSize: 12, fontWeight: 700, color: '#DC2626', marginBottom: 6 }}>Boat/Air Evacuation Required</div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                    {result.disconnected_habitations.map(id => (
                      <span key={id} className="badge badge-danger">{getHabName(id)}</span>
                    ))}
                  </div>
                </div>
              )}

              {/* Nearby District Overflow */}
              {nearbyData && nearbyData.nearby_shelters?.length > 0 && (
                <div className="card" style={{ marginTop: 12, borderColor: 'rgba(139,92,246,0.2)', background: '#F5F3FF' }}>                   <div style={{ fontSize: 12, fontWeight: 700, color: '#8B5CF6', marginBottom: 8 }}>Nearby District Capacity</div>
                  <div style={{ fontSize: 11, color: '#6D28D9', marginBottom: 8, lineHeight: 1.5 }}>{nearbyData.recommendation}</div>
                  <button className="btn btn-primary btn-block" onClick={runExpanded} disabled={loadingExpanded} style={{ fontSize: 12 }}>
                    {loadingExpanded ? 'Expanding...' : 'Expand to Nearby Districts'}
                  </button>
                </div>
              )}
            </>
          )}

          {/* === WHAT-IF SCENARIO RESULT === */}
          {scenarioLoading && (
            <div className="card" style={{ marginTop: 14, padding: 16, borderColor: 'rgba(37,99,235,0.2)', background: '#EFF6FF' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#2563EB" strokeWidth="2" style={{ animation: 'spin 2s linear infinite' }}><path d="M12 2v4m0 12v4m-7.07-15.07l2.83 2.83m8.48 8.48l2.83 2.83M2 12h4m12 0h4m-15.07 7.07l2.83-2.83m8.48-8.48l2.83-2.83"/></svg>
                <span style={{ fontSize: 13, fontWeight: 600, color: '#2563EB' }}>Running scenario simulation...</span>
              </div>
            </div>
          )}
          {scenarioResult && !scenarioLoading && (
            <div className="card" style={{ marginTop: 14, padding: 16, borderColor: 'rgba(37,99,235,0.2)', background: '#EFF6FF' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                <div style={{ fontSize: 13, fontWeight: 700, color: '#2563EB', display: 'flex', alignItems: 'center', gap: 6 }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#2563EB" strokeWidth="2"><path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/></svg>
                  What-If Scenario Result
                </div>
                <button onClick={() => setScenarioResult(null)} style={{ background: 'none', border: 'none', color: '#94A3B8', cursor: 'pointer', fontSize: 12, fontWeight: 600 }}>✕ Dismiss</button>
              </div>

              {/* Scenario parameters */}
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 10 }}>
                {scenarioResult.scenario?.rainfall_multiplier !== 1.0 && (
                  <span style={{ padding: '2px 8px', borderRadius: 6, fontSize: 10, fontWeight: 700, background: '#DBEAFE', color: '#1D4ED8' }}>
                    🌧 Rainfall: {scenarioResult.scenario.rainfall_multiplier}x
                  </span>
                )}
                {scenarioResult.scenario?.block_road_ids?.length > 0 && (
                  <span style={{ padding: '2px 8px', borderRadius: 6, fontSize: 10, fontWeight: 700, background: '#FEF3C7', color: '#92400E' }}>
                    🚧 Roads blocked: {scenarioResult.scenario.block_road_ids.join(', ')}
                  </span>
                )}
                {scenarioResult.scenario?.disable_shelter_ids?.length > 0 && (
                  <span style={{ padding: '2px 8px', borderRadius: 6, fontSize: 10, fontWeight: 700, background: '#FEE2E2', color: '#991B1B' }}>
                    🏚 Shelters disabled: {scenarioResult.scenario.disable_shelter_ids.join(', ')}
                  </span>
                )}
                {scenarioResult.scenario?.population_multiplier !== 1.0 && (
                  <span style={{ padding: '2px 8px', borderRadius: 6, fontSize: 10, fontWeight: 700, background: '#F3E8FF', color: '#7C3AED' }}>
                    👥 Population: {scenarioResult.scenario.population_multiplier}x
                  </span>
                )}
              </div>

              {/* Scenario stats vs current */}
              {scenarioResult.result && (
                <>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 6, marginBottom: 10 }}>
                    {[
                      { l: 'Relocated', v: (scenarioResult.result.total_people_relocated || 0).toLocaleString(), c: '#22C55E' },
                      { l: 'Unmet', v: (scenarioResult.result.total_people_unmet || 0).toLocaleString(), c: (scenarioResult.result.total_people_unmet || 0) > 0 ? '#DC2626' : '#22C55E' },
                      { l: 'Feasible', v: scenarioResult.result.is_feasible ? 'Yes' : 'No', c: scenarioResult.result.is_feasible ? '#22C55E' : '#DC2626' },
                    ].map((s, i) => (
                      <div key={i} style={{ textAlign: 'center', padding: '8px 4px', background: '#fff', borderRadius: 8, border: '1px solid #BFDBFE' }}>
                        <div style={{ fontSize: 16, fontWeight: 800, color: s.c, fontFamily: 'var(--mono)' }}>{s.v}</div>
                        <div style={{ fontSize: 9, color: '#6B7280', textTransform: 'uppercase', letterSpacing: 0.5 }}>{s.l}</div>
                      </div>
                    ))}
                  </div>

                  {/* Comparison with current plan */}
                  {result && (
                    <div style={{ padding: 10, background: '#fff', borderRadius: 8, border: '1px solid #BFDBFE', marginBottom: 8 }}>
                      <div style={{ fontSize: 11, fontWeight: 700, color: '#1E40AF', marginBottom: 6 }}>📊 vs Current Plan</div>
                      {(() => {
                        const currReloc = result.total_people_relocated || 0;
                        const scenReloc = scenarioResult.result.total_people_relocated || 0;
                        const currUnmet = result.total_people_unmet || 0;
                        const scenUnmet = scenarioResult.result.total_people_unmet || 0;
                        const relocDiff = scenReloc - currReloc;
                        const unmetDiff = scenUnmet - currUnmet;
                        return (
                          <div style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 11 }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                              <span style={{ color: '#6B7280' }}>Relocated</span>
                              <span style={{ fontWeight: 700, color: relocDiff >= 0 ? '#16A34A' : '#DC2626' }}>{relocDiff >= 0 ? '+' : ''}{relocDiff.toLocaleString()}</span>
                            </div>
                            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                              <span style={{ color: '#6B7280' }}>Unmet need</span>
                              <span style={{ fontWeight: 700, color: unmetDiff <= 0 ? '#16A34A' : '#DC2626' }}>{unmetDiff >= 0 ? '+' : ''}{unmetDiff.toLocaleString()}</span>
                            </div>
                          </div>
                        );
                      })()}
                    </div>
                  )}

                  {/* Scenario assignments preview */}
                  {scenarioResult.result.assignments?.length > 0 && (
                    <div style={{ maxHeight: 140, overflowY: 'auto' }}>
                      <div style={{ fontSize: 11, fontWeight: 700, color: '#1E40AF', marginBottom: 4 }}>Scenario Assignments ({scenarioResult.result.assignments.length})</div>
                      {scenarioResult.result.assignments.slice(0, 5).map((a, i) => (
                        <div key={i} style={{ padding: '5px 8px', background: '#fff', borderRadius: 6, border: '1px solid #BFDBFE', marginBottom: 4, fontSize: 11 }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <span style={{ fontWeight: 600, color: '#374151' }}>{getHabName(a.habitation_id)} → {getShelterName(a.shelter_id)}</span>
                            <span style={{ fontFamily: 'var(--mono)', color: '#2563EB', fontWeight: 700 }}>{a.people_assigned.toLocaleString()}</span>
                          </div>
                        </div>
                      ))}
                      {scenarioResult.result.assignments.length > 5 && (
                        <div style={{ textAlign: 'center', fontSize: 10, color: '#6B7280', padding: 4 }}>+{scenarioResult.result.assignments.length - 5} more</div>
                      )}
                    </div>
                  )}
                </>
              )}

              {/* Affected habitations */}
              {scenarioResult.affected_habitations?.length > 0 && (
                <div style={{ marginTop: 8, padding: 8, background: '#fff', borderRadius: 8, border: '1px solid #BFDBFE' }}>
                  <div style={{ fontSize: 10, fontWeight: 600, color: '#6B7280', marginBottom: 4 }}>Affected: {scenarioResult.affected_habitations.length} habitations</div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                    {scenarioResult.affected_habitations.slice(0, 8).map(h => (
                      <span key={h.id} style={{ padding: '1px 6px', borderRadius: 4, fontSize: 9, background: '#EFF6FF', color: '#1D4ED8', fontWeight: 500 }}>{h.name}</span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* === ALERTS & NOTIFICATIONS === */}
          {alerts.length > 0 && (
            <div style={{ marginTop: 14 }}>
              <div className="card-header" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#DC2626', animation: 'pulse 2s infinite' }} />
                Alerts & Notifications
              </div>
              <div className="card" style={{ padding: 0 }}>
                {alerts.map((a, i) => (
                  <div key={a.id || i} style={{ padding: '10px 14px', borderBottom: i < alerts.length - 1 ? '1px solid #F3F4F6' : 'none', display: 'flex', gap: 10, alignItems: 'flex-start' }}>
                    <span style={{ width: 7, height: 7, borderRadius: '50%', background: a.type === 'critical' ? '#DC2626' : '#F59E0B', marginTop: 5, flexShrink: 0 }} />
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 12, fontWeight: 600, color: '#1F2937' }}>{a.message}</div>
                      <div style={{ fontSize: 10, color: '#94A3B8', marginTop: 2 }}>{a.detail}</div>
                    </div>
                    <div style={{ fontSize: 9, color: '#D1D5DB', flexShrink: 0 }}>{a.time}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
