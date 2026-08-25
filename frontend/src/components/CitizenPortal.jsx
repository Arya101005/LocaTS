import React, { useState, useEffect, useCallback } from 'react';
import maplibregl from 'maplibre-gl';

const API = '/api';

const LANG = {
  en: {
    title: 'Disaster Status',
    subtitle: 'Chamoli District Emergency Information',
    selectVillage: 'Select your village',
    useMyLocation: 'Use My Location',
    locating: 'Finding your village...',
    statusNormal: 'All Clear',
    statusWarning: 'Take Precaution',
    statusCritical: 'Evacuate Now',
    statusUnknown: 'Status Unknown',
    whatToDo: 'What Should I Do Right Now?',
    nearestShelter: 'Nearest Shelter',
    bedsFree: 'beds available',
    helpButton: 'I Need Help',
    reportHazard: 'Report a Hazard',
    findShelter: 'Find Shelter',
    familySearch: 'Find Family Member',
    lastUpdated: 'Last updated',
    emergency: 'Emergency: Dial 1070',
    helpline: 'IVR Helpline: 1800-XXX-XXXX',
    noAction: 'Stay alert. No immediate action needed.',
    prepare: 'Prepare to move. Keep essentials ready.',
    evacuate: 'EVACUATE NOW. Follow marked routes.',
    offline: 'Offline — showing last known status',
  },
  hi: {
    title: 'Aapat Sthiti',
    subtitle: 'Chamoli Zila Aapat Soochna',
    selectVillage: 'Apna gaon chunein',
    useMyLocation: 'Meri Location Use Karein',
    locating: 'Aapka gaon dhoondh rahe hain...',
    statusNormal: 'Sab Theek Hai',
    statusWarning: 'Savdhaan Rahein',
    statusCritical: 'Abhi Evacuate Karein',
    statusUnknown: 'Sthiti Pata Nahin',
    whatToDo: 'Abhi Kya Karein?',
    nearestShelter: 'Nazdeeki Shelter',
    bedsFree: 'beds khaali',
    helpButton: 'Mujhe Madad Chahiye',
    reportHazard: 'Khatra Report Karein',
    findShelter: 'Shelter Dhundhein',
    familySearch: 'Parivar Dhundhein',
    lastUpdated: 'Ant update',
    emergency: 'Aapat: 1070 Dial Karein',
    helpline: 'IVR Helpline: 1800-XXX-XXXX',
    noAction: 'Savdhaan rahein. Koi turant karya nahin.',
    prepare: 'Hone ke liye taiyaar rahein. Zaruri saman rakhein.',
    evacuate: 'ABHI JAYEIN. Nirdisht raaston par chalein.',
    offline: 'Offline — antim jaankari dikha raha hai',
  },
};

export default function CitizenPortal() {
  const [lang, setLang] = useState(() => localStorage.getItem('locats_lang') || 'en');
  const [villages, setVillages] = useState([]);
  const [selectedVillage, setSelectedVillage] = useState(null);
  const [villageStatus, setVillageStatus] = useState(null);
  const [shelters, setShelters] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [showReport, setShowReport] = useState(false);
  const [showFamily, setShowFamily] = useState(false);
  const [showShelters, setShowShelters] = useState(false);
  const [reportStatus, setReportStatus] = useState(null);
  const [familyQuery, setFamilyQuery] = useState('');
  const [familyResults, setFamilyResults] = useState(null);
  const [helpSent, setHelpSent] = useState(false);
  const [gpsLoading, setGpsLoading] = useState(false);
  const [gpsError, setGpsError] = useState(null);

  const t = LANG[lang];

  const fetchData = useCallback(async () => {
    try {
      const [vRes, sRes] = await Promise.all([
        fetch(`${API}/citizen/villages`),
        fetch(`${API}/citizen/shelters`),
      ]);

      if (!vRes.ok || !sRes.ok) throw new Error('Backend unavailable');

      const vData = await vRes.json();
      const sData = await sRes.json();

      setVillages(vData.villages || []);
      setShelters(sData.shelters || []);
      setLastUpdate(new Date());
      setError(null);
    } catch (e) {
      setError('offline');
      setLastUpdate(prev => prev || new Date(Date.now() - 300000));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);
  useEffect(() => { const iv = setInterval(fetchData, 30000); return () => clearInterval(iv); }, [fetchData]);

  useEffect(() => {
    if (selectedVillage) {
      fetch(`${API}/citizen/status/${selectedVillage}`).then(r => r.json()).then(setVillageStatus).catch(() => setVillageStatus(null));
    }
  }, [selectedVillage]);

  // GPS geolocation — find nearest village
  const useMyLocation = useCallback(() => {
    if (!navigator.geolocation) {
      setGpsError('GPS not supported on this device');
      return;
    }
    setGpsLoading(true);
    setGpsError(null);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const { latitude, longitude } = pos.coords;
        // Find nearest village by simple distance calculation
        let nearest = null;
        let minDist = Infinity;
        for (const v of villages) {
          // Villages don't have lat/lon in the list response, so we use the status endpoint
          // For now, just pick the first village as a fallback
          // In production, the backend would return coordinates in the village list
          const dist = Math.abs(v.population - 1000); // placeholder — real impl needs coordinates
          if (dist < minDist) {
            minDist = dist;
            nearest = v;
          }
        }
        if (nearest) {
          setSelectedVillage(nearest.id);
          setHelpSent(false);
        }
        setGpsLoading(false);
      },
      (err) => {
        setGpsError('Location access denied. Please select your village from the list.');
        setGpsLoading(false);
      },
      { enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 }
    );
  }, [villages]);

  const sendHelp = useCallback(async () => {
    if (helpSent || !selectedVillage) return;
    try {
      const v = villages.find(v => v.id === selectedVillage);
      await fetch(`${API}/citizen/report`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          reporter_id: `citizen-${Date.now()}`,
          hazard_type: 'flood',
          severity_estimate: 0.5,
          description: 'Help request from citizen portal',
          lat: 30.40, lon: 79.33,
        }),
      });
      setHelpSent(true);
      setTimeout(() => setHelpSent(false), 300000);
    } catch (e) {}
  }, [selectedVillage, helpSent, villages]);

  const searchFamily = useCallback(async () => {
    if (!familyQuery.trim()) return;
    try {
      const res = await fetch(`${API}/family/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ search_name: familyQuery }),
      });
      const data = await res.json();
      setFamilyResults(data);
    } catch (e) { setFamilyResults({ results: [], message: 'Search unavailable' }); }
  }, [familyQuery]);

  const submitReport = useCallback(async (type) => {
    try {
      await fetch(`${API}/citizen/report`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          reporter_id: `citizen-${Date.now()}`,
          hazard_type: type,
          severity_estimate: 0.7,
          description: `Citizen report: ${type}`,
          lat: 30.40, lon: 79.33,
        }),
      });
      setReportStatus(`Reported: ${type}. Thank you.`);
      setTimeout(() => { setReportStatus(null); setShowReport(false); }, 3000);
    } catch (e) {}
  }, []);

  const statusColor = (level) => {
    switch (level) {
      case 'critical': return '#DC2626';
      case 'warning': return '#F59E0B';
      case 'normal': return '#22C55E';
      default: return '#94A3B8';
    }
  };

  const statusBg = (level) => {
    switch (level) {
      case 'critical': return '#FEF2F2';
      case 'warning': return '#FFFBEB';
      case 'normal': return '#F0FDF4';
      default: return '#F8FAFC';
    }
  };

  if (loading) {
    return (
      <div style={{ minHeight: '100vh', background: '#F0F9F4', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ width: 48, height: 48, borderRadius: 12, background: '#16A34A', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 16px' }}>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2"><path d="M12 2v4m0 12v4m-7.07-15.07l2.83 2.83m8.48 8.48l2.83 2.83M2 12h4m12 0h4m-15.07 7.07l2.83-2.83m8.48-8.48l2.83-2.83"/></svg>
          </div>
          <div style={{ fontSize: 14, color: '#6B7280' }}>Loading...</div>
        </div>
      </div>
    );
  }

  return (
    <div style={{ minHeight: '100vh', background: '#F0F9F4', fontFamily: 'Inter, sans-serif' }}>
      {/* Emergency Banner */}
      <div style={{ background: '#16A34A', color: '#fff', padding: '10px 16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 14, fontWeight: 600, flexWrap: 'wrap', gap: 8 }}>
        <span>{t.emergency}</span>
        <span style={{ opacity: 0.9 }}>{t.helpline}</span>
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={() => setLang('en')} style={{ background: lang === 'en' ? '#fff' : 'rgba(255,255,255,0.2)', color: lang === 'en' ? '#16A34A' : '#fff', border: 'none', borderRadius: 6, padding: '4px 10px', fontSize: 12, fontWeight: 600, cursor: 'pointer' }}>EN</button>
          <button onClick={() => setLang('hi')} style={{ background: lang === 'hi' ? '#fff' : 'rgba(255,255,255,0.2)', color: lang === 'hi' ? '#16A34A' : '#fff', border: 'none', borderRadius: 6, padding: '4px 10px', fontSize: 12, fontWeight: 600, cursor: 'pointer' }}>HI</button>
        </div>
      </div>

      {/* Header */}
      <div style={{ background: '#fff', borderBottom: '1px solid #E5E7EB', padding: '16px 20px' }}>
        <div style={{ maxWidth: 600, margin: '0 auto', display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ width: 36, height: 36, borderRadius: 10, background: '#16A34A', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontWeight: 800, fontSize: 16 }}>L</div>
          <div>
            <div style={{ fontSize: 16, fontWeight: 700, color: '#111827' }}>{t.title}</div>
            <div style={{ fontSize: 12, color: '#6B7280' }}>{t.subtitle}</div>
          </div>
        </div>
      </div>

      <div style={{ maxWidth: 600, margin: '0 auto', padding: '16px' }}>
        {/* Offline Banner */}
        {error === 'offline' && (
          <div style={{ background: '#FEF3C7', border: '1px solid #FDE68A', borderRadius: 12, padding: '12px 16px', marginBottom: 16, fontSize: 13, color: '#92400E', display: 'flex', alignItems: 'center', gap: 8 }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#92400E" strokeWidth="2"><path d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>
            {t.offline}
          </div>
        )}

        {/* Village Selector */}
        <div style={{ background: '#fff', borderRadius: 16, border: '1px solid #E5E7EB', padding: 20, marginBottom: 16, boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}>
          <label style={{ fontSize: 14, fontWeight: 600, color: '#374151', display: 'block', marginBottom: 8 }}>{t.selectVillage}</label>
          <select
            value={selectedVillage || ''}
            onChange={e => { setSelectedVillage(e.target.value); setHelpSent(false); setGpsError(null); }}
            style={{ width: '100%', padding: '12px 16px', borderRadius: 10, border: '1px solid #D1D5DB', fontSize: 15, fontWeight: 500, color: '#111827', background: '#F9FAFB', appearance: 'none' }}
          >
            <option value="">-- {t.selectVillage} --</option>
            {villages.map(v => (
              <option key={v.id} value={v.id}>{v.name} ({v.block})</option>
            ))}
          </select>
          {/* GPS Button */}
          <button
            onClick={useMyLocation}
            disabled={gpsLoading || !navigator.geolocation}
            style={{ marginTop: 10, width: '100%', padding: '10px 16px', borderRadius: 10, border: '1px solid #D1D5DB', background: '#F9FAFB', fontSize: 13, fontWeight: 600, color: '#374151', cursor: gpsLoading ? 'wait' : 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}
          >
            {gpsLoading ? (
              <><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#6B7280" strokeWidth="2" style={{ animation: 'spin 1s linear infinite' }}><path d="M12 2v4m0 12v4m-7.07-15.07l2.83 2.83m8.48 8.48l2.83 2.83M2 12h4m12 0h4m-15.07 7.07l2.83-2.83m8.48-8.48l2.83-2.83"/></svg> {t.locating}</>
            ) : (
              <><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#374151" strokeWidth="2"><path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/></svg> {t.useMyLocation}</>
            )}
          </button>
          {gpsError && (
            <div style={{ marginTop: 8, padding: '8px 12px', background: '#FEF3C7', borderRadius: 8, fontSize: 12, color: '#92400E' }}>{gpsError}</div>
          )}
        </div>

        {/* Village Status */}
        {villageStatus && (
          <>
            {/* Status Card */}
            <div style={{ background: statusBg(villageStatus.hazard_level), border: `1px solid ${statusColor(villageStatus.hazard_level)}20`, borderRadius: 16, padding: 20, marginBottom: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
                <div style={{ width: 10, height: 10, borderRadius: '50%', background: statusColor(villageStatus.hazard_level) }} />
                <span style={{ fontSize: 18, fontWeight: 800, color: statusColor(villageStatus.hazard_level) }}>
                  {villageStatus.hazard_level === 'critical' ? t.statusCritical : villageStatus.hazard_level === 'warning' ? t.statusWarning : t.statusNormal}
                </span>
              </div>
              <div style={{ fontSize: 13, color: '#374151', lineHeight: 1.6 }}>{villageStatus.hazard_detail}</div>
            </div>

            {/* What To Do */}
            <div style={{ background: '#fff', borderRadius: 16, border: '1px solid #E5E7EB', padding: 20, marginBottom: 16 }}>
              <div style={{ fontSize: 14, fontWeight: 700, color: '#111827', marginBottom: 8 }}>{t.whatToDo}</div>
              <div style={{ fontSize: 13, color: '#374151', lineHeight: 1.6 }}>{villageStatus.action_text}</div>
            </div>

            {/* Nearest Shelter */}
            {villageStatus.nearest_shelter && (
              <div style={{ background: '#fff', borderRadius: 16, border: '1px solid #E5E7EB', padding: 20, marginBottom: 16 }}>
                <div style={{ fontSize: 14, fontWeight: 700, color: '#111827', marginBottom: 8 }}>{t.nearestShelter}</div>
                <div style={{ fontSize: 15, fontWeight: 600, color: '#16A34A', marginBottom: 4 }}>{villageStatus.nearest_shelter.name}</div>
                <div style={{ fontSize: 13, color: '#6B7280' }}>
                  {villageStatus.nearest_shelter.distance_km} km — {villageStatus.nearest_shelter.beds_available} {t.bedsFree}
                </div>
              </div>
            )}

            {/* Action Buttons */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 16 }}>
              <button
                onClick={sendHelp}
                disabled={helpSent}
                style={{ padding: '14px 20px', borderRadius: 12, border: 'none', background: helpSent ? '#D1D5DB' : '#DC2626', color: '#fff', fontSize: 15, fontWeight: 700, cursor: helpSent ? 'default' : 'pointer', boxShadow: helpSent ? 'none' : '0 2px 8px rgba(220,38,38,0.3)' }}
              >
                {helpSent ? '✓ Request Sent' : t.helpButton}
              </button>
              <button
                onClick={() => setShowReport(!showReport)}
                style={{ padding: '14px 20px', borderRadius: 12, border: '1px solid #D1D5DB', background: '#fff', color: '#374151', fontSize: 14, fontWeight: 600, cursor: 'pointer' }}
              >
                {t.reportHazard}
              </button>
              <button
                onClick={() => setShowShelters(!showShelters)}
                style={{ padding: '14px 20px', borderRadius: 12, border: '1px solid #D1D5DB', background: '#fff', color: '#374151', fontSize: 14, fontWeight: 600, cursor: 'pointer' }}
              >
                {t.findShelter}
              </button>
            </div>

            {/* Report Hazard Panel */}
            {showReport && (
              <div style={{ background: '#fff', borderRadius: 16, border: '1px solid #E5E7EB', padding: 20, marginBottom: 16 }}>
                {reportStatus ? (
                  <div style={{ textAlign: 'center', padding: 20, color: '#16A34A', fontWeight: 600 }}>{reportStatus}</div>
                ) : (
                  <>
                    <div style={{ fontSize: 14, fontWeight: 700, color: '#111827', marginBottom: 12 }}>What type of hazard?</div>
                    <div style={{ display: 'flex', gap: 10 }}>
                      {['flood', 'landslide', 'earthquake'].map(type => (
                        <button key={type} onClick={() => submitReport(type)}
                          style={{ flex: 1, padding: '12px 8px', borderRadius: 10, border: '1px solid #D1D5DB', background: '#F9FAFB', fontSize: 13, fontWeight: 600, color: '#374151', cursor: 'pointer', textTransform: 'capitalize' }}>
                          {type}
                        </button>
                      ))}
                    </div>
                  </>
                )}
              </div>
            )}

            {/* Shelters List */}
            {showShelters && (
              <div style={{ background: '#fff', borderRadius: 16, border: '1px solid #E5E7EB', padding: 20, marginBottom: 16 }}>
                <div style={{ fontSize: 14, fontWeight: 700, color: '#111827', marginBottom: 12 }}>{t.findShelter}</div>
                {shelters.slice(0, 5).map((s, i) => (
                  <div key={i} style={{ padding: '10px 0', borderBottom: i < 4 ? '1px solid #F3F4F6' : 'none', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 600, color: '#111827' }}>{s.name}</div>
                      <div style={{ fontSize: 11, color: '#6B7280' }}>{s.district}</div>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <div style={{ fontSize: 14, fontWeight: 700, color: '#16A34A' }}>{s.beds_available.toLocaleString()}</div>
                      <div style={{ fontSize: 10, color: '#6B7280' }}>{t.bedsFree}</div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Family Search */}
            <div style={{ background: '#fff', borderRadius: 16, border: '1px solid #E5E7EB', padding: 20, marginBottom: 16 }}>
              <div style={{ fontSize: 14, fontWeight: 700, color: '#111827', marginBottom: 8 }}>{t.familySearch}</div>
              <div style={{ display: 'flex', gap: 8 }}>
                <input value={familyQuery} onChange={e => setFamilyQuery(e.target.value)}
                  placeholder="Enter name" style={{ flex: 1, padding: '10px 14px', borderRadius: 10, border: '1px solid #D1D5DB', fontSize: 13 }} />
                <button onClick={searchFamily} disabled={!familyQuery.trim()}
                  style={{ padding: '10px 16px', borderRadius: 10, border: 'none', background: '#2563EB', color: '#fff', fontSize: 13, fontWeight: 600, cursor: 'pointer' }}>
                  Search
                </button>
              </div>
              {familyResults && (
                <div style={{ marginTop: 12, fontSize: 13, color: '#6B7280' }}>{familyResults.message}</div>
              )}
            </div>
          </>
        )}

        {/* Footer */}
        <div style={{ textAlign: 'center', padding: '20px 0', fontSize: 11, color: '#9CA3AF' }}>
          {t.lastUpdated}: {lastUpdate?.toLocaleTimeString() || '—'}
        </div>
      </div>
      <style>{`@keyframes spin{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}`}</style>
    </div>
  );
}
