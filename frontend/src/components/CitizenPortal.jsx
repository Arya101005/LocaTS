import React, { useState, useEffect, useCallback } from 'react';
import maplibregl from 'maplibre-gl';

const API = '/api';

const LANG = {
  en: {
    title: 'Disaster Status',
    subtitle: 'Chamoli District Emergency Information',
    selectVillage: 'Select your village',
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
            onChange={e => { setSelectedVillage(e.target.value); setHelpSent(false); }}
            style={{ width: '100%', padding: '12px 16px', borderRadius: 10, border: '1px solid #D1D5DB', fontSize: 15, fontWeight: 500, color: '#111827', background: '#F9FAFB', appearance: 'none' }}
          >
            <option value="">-- {t.selectVillage} --</option>
            {villages.map(v => (
              <option key={v.id} value={v.id}>{v.name} ({v.block})</option>
            ))}
          </select>
        </div>

        {/* Village Status */}
        {villageStatus && (
          <>
            {/* Status Card */}
            <div style={{ background: statusBg(villageStatus.hazard_level), border: `2px solid ${statusColor(villageStatus.hazard_level)}20`, borderRadius: 16, padding: 24, marginBottom: 16, textAlign: 'center' }}>
              <div style={{ width: 56, height: 56, borderRadius: '50%', background: statusColor(villageStatus.hazard_level), display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 12px' }}>
                {villageStatus.hazard_level === 'critical' && <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.5"><path d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>}
                {villageStatus.hazard_level === 'warning' && <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.5"><path d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/><path d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/></svg>}
                {villageStatus.hazard_level === 'normal' && <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.5"><path d="M5 13l4 4L19 7"/></svg>}
              </div>
              <div style={{ fontSize: 22, fontWeight: 800, color: statusColor(villageStatus.hazard_level), marginBottom: 4 }}>
                {villageStatus.hazard_level === 'critical' ? t.statusCritical : villageStatus.hazard_level === 'warning' ? t.statusWarning : t.statusNormal}
              </div>
              <div style={{ fontSize: 14, color: '#4B5563', fontWeight: 500 }}>{villageStatus.village_name}</div>
              <div style={{ fontSize: 12, color: '#6B7280', marginTop: 4 }}>{villageStatus.hazard_detail}</div>
            </div>

            {/* Action Card */}
            <div style={{ background: '#fff', borderRadius: 16, border: '1px solid #E5E7EB', padding: 20, marginBottom: 16, boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}>
              <div style={{ fontSize: 16, fontWeight: 700, color: '#111827', marginBottom: 10 }}>{t.whatToDo}</div>
              <div style={{ fontSize: 15, lineHeight: 1.6, color: '#374151' }}>{villageStatus.action_text}</div>
              {villageStatus.nearest_shelter && (
                <div style={{ marginTop: 12, padding: '12px 16px', background: '#F0FDF4', borderRadius: 10, border: '1px solid #BBF7D0' }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: '#16A34A', marginBottom: 4 }}>{t.nearestShelter}</div>
                  <div style={{ fontSize: 14, fontWeight: 600, color: '#111827' }}>{villageStatus.nearest_shelter.name}</div>
                  <div style={{ fontSize: 13, color: '#6B7280' }}>
                    {villageStatus.nearest_shelter.distance_km}km | {villageStatus.nearest_shelter.beds_available.toLocaleString()} {t.bedsFree}
                    {villageStatus.nearest_shelter.district !== 'Chamoli' && ` (${villageStatus.nearest_shelter.district})`}
                  </div>
                </div>
              )}
            </div>

            {/* Help Button */}
            <div style={{ marginBottom: 16 }}>
              <button
                onClick={sendHelp}
                disabled={helpSent}
                style={{
                  width: '100%', padding: '16px 24px', borderRadius: 14, border: 'none', fontSize: 18, fontWeight: 700, cursor: helpSent ? 'default' : 'pointer',
                  background: helpSent ? '#D1D5DB' : villageStatus.hazard_level === 'critical' ? '#DC2626' : '#F59E0B',
                  color: '#fff', boxShadow: helpSent ? 'none' : '0 4px 12px rgba(0,0,0,0.15)',
                }}
              >
                {helpSent ? 'Help Requested - Help is on the way' : t.helpButton}
              </button>
            </div>
          </>
        )}

        {/* Action Buttons */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 }}>
          <button onClick={() => { setShowShelters(!showShelters); setShowReport(false); setShowFamily(false); }} style={{ padding: '14px 16px', background: '#fff', border: '1px solid #E5E7EB', borderRadius: 12, fontSize: 14, fontWeight: 600, color: '#374151', cursor: 'pointer', textAlign: 'center' }}>
            {t.findShelter}
          </button>
          <button onClick={() => { setShowReport(!showReport); setShowShelters(false); setShowFamily(false); }} style={{ padding: '14px 16px', background: '#fff', border: '1px solid #E5E7EB', borderRadius: 12, fontSize: 14, fontWeight: 600, color: '#374151', cursor: 'pointer', textAlign: 'center' }}>
            {t.reportHazard}
          </button>
        </div>
        <button onClick={() => { setShowFamily(!showFamily); setShowShelters(false); setShowReport(false); }} style={{ width: '100%', padding: '14px 16px', background: '#fff', border: '1px solid #E5E7EB', borderRadius: 12, fontSize: 14, fontWeight: 600, color: '#374151', cursor: 'pointer', marginBottom: 16 }}>
          {t.familySearch}
        </button>

        {/* Shelter List */}
        {showShelters && (
          <div style={{ background: '#fff', borderRadius: 16, border: '1px solid #E5E7EB', padding: 20, marginBottom: 16 }}>
            <div style={{ fontSize: 16, fontWeight: 700, marginBottom: 12 }}>{t.findShelter}</div>
            {shelters.slice(0, 10).map(s => (
              <div key={s.id} style={{ padding: '12px 0', borderBottom: '1px solid #F3F4F6', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <div style={{ fontSize: 14, fontWeight: 600, color: '#111827' }}>{s.name}</div>
                  <div style={{ fontSize: 12, color: '#6B7280' }}>{s.district} | {s.type}</div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontSize: 14, fontWeight: 700, color: s.status === 'open' ? '#16A34A' : s.status === 'limited' ? '#F59E0B' : '#DC2626' }}>
                    {s.beds_available.toLocaleString()}
                  </div>
                  <div style={{ fontSize: 11, color: '#9CA3AF' }}>{t.bedsFree}</div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Report Hazard */}
        {showReport && (
          <div style={{ background: '#fff', borderRadius: 16, border: '1px solid #E5E7EB', padding: 20, marginBottom: 16 }}>
            <div style={{ fontSize: 16, fontWeight: 700, marginBottom: 12 }}>{t.reportHazard}</div>
            {reportStatus ? (
              <div style={{ padding: 16, background: '#F0FDF4', borderRadius: 10, fontSize: 14, color: '#16A34A', fontWeight: 600, textAlign: 'center' }}>{reportStatus}</div>
            ) : (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                {['flood', 'landslide', 'earthquake', 'fire'].map(type => (
                  <button key={type} onClick={() => submitReport(type)} style={{ padding: '14px', background: '#F9FAFB', border: '1px solid #E5E7EB', borderRadius: 10, fontSize: 14, fontWeight: 600, textTransform: 'capitalize', cursor: 'pointer', color: '#374151' }}>
                    {type}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Family Search */}
        {showFamily && (
          <div style={{ background: '#fff', borderRadius: 16, border: '1px solid #E5E7EB', padding: 20, marginBottom: 16 }}>
            <div style={{ fontSize: 16, fontWeight: 700, marginBottom: 12 }}>{t.familySearch}</div>
            <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
              <input value={familyQuery} onChange={e => setFamilyQuery(e.target.value)} placeholder="Enter name..." style={{ flex: 1, padding: '10px 14px', borderRadius: 10, border: '1px solid #D1D5DB', fontSize: 14 }} onKeyDown={e => { if (e.key === 'Enter') searchFamily(); }} />
              <button onClick={searchFamily} style={{ padding: '10px 18px', background: '#16A34A', color: '#fff', border: 'none', borderRadius: 10, fontSize: 14, fontWeight: 600, cursor: 'pointer' }}>Search</button>
            </div>
            {familyResults && (
              <div style={{ fontSize: 13, color: '#374151' }}>{familyResults.message}</div>
            )}
          </div>
        )}

        {/* Last Updated */}
        <div style={{ textAlign: 'center', padding: '16px 0', fontSize: 12, color: '#9CA3AF' }}>
          {t.lastUpdated}: {lastUpdate ? lastUpdate.toLocaleTimeString() : '--'}
        </div>
      </div>
    </div>
  );
}
