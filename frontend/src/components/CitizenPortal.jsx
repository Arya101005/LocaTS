import React, { useState, useEffect, useCallback } from 'react';

const API = '/api';

const LANG = {
  en: {
    title: 'LocaTS',
    subtitle: 'Chamoli District Emergency',
    selectVillage: 'Select your village',
    useMyLocation: 'Use My Location',
    locating: 'Finding your village...',
    statusNormal: 'All Clear',
    statusWarning: 'Take Precaution',
    statusCritical: 'Evacuate Now',
    whatToDo: 'What Should I Do Right Now?',
    nearestShelter: 'Nearest Shelter',
    bedsFree: 'beds free',
    helpButton: 'I Need Help',
    reportHazard: 'Report a Hazard',
    findShelter: 'Find Shelter',
    familySearch: 'Find Family',
    emergency: 'Emergency: Dial 1070',
    helpline: 'IVR: 1800-XXX-XXXX',
    noAction: 'Stay alert. No immediate action needed.',
    prepare: 'Prepare to move. Keep essentials ready.',
    evacuate: 'EVACUATE NOW. Follow marked routes.',
    offline: 'Offline — showing last known status',
    home: 'Home',
    shelters: 'Shelters',
    report: 'Report',
    family: 'Family',
    signOut: 'Sign Out',
  },
  hi: {
    title: 'LocaTS',
    subtitle: 'Chamoli Zila Aapat',
    selectVillage: 'Apna gaon chunein',
    useMyLocation: 'Meri Location Use Karein',
    locating: 'Aapka gaon dhoondh rahe hain...',
    statusNormal: 'Sab Theek Hai',
    statusWarning: 'Savdhaan Rahein',
    statusCritical: 'Abhi Evacuate Karein',
    whatToDo: 'Abhi Kya Karein?',
    nearestShelter: 'Nazdeeki Shelter',
    bedsFree: 'beds khaali',
    helpButton: 'Mujhe Madad Chahiye',
    reportHazard: 'Khatra Report Karein',
    findShelter: 'Shelter Dhundhein',
    familySearch: 'Parivar Dhundhein',
    emergency: 'Aapat: 1070 Dial Karein',
    helpline: 'IVR: 1800-XXX-XXXX',
    noAction: 'Savdhaan rahein. Koi turant karya nahin.',
    prepare: 'Hone ke liye taiyaar rahein.',
    evacuate: 'ABHI JAYEIN. Nirdisht raaston par chalein.',
    offline: 'Offline — antim jaankari dikha raha hai',
    home: 'Ghar',
    shelters: 'Shelter',
    report: 'Report',
    family: 'Parivar',
    signOut: 'Sign Out',
  },
};

function ChangePasswordForm({ token, onDone }) {
  const [current, setCurrent] = useState('');
  const [newPass, setNewPass] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(''); setSuccess('');
    if (newPass !== confirm) { setError('Passwords do not match.'); return; }
    if (newPass.length < 6) { setError('Min 6 characters.'); return; }
    setLoading(true);
    try {
      const res = await fetch(`${API}/auth/change-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ current_password: current, new_password: newPass }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed.');
      setSuccess('Password changed!');
      setTimeout(() => onDone(), 1500);
    } catch (err) { setError(err.message); }
    finally { setLoading(false); }
  };

  return (
    <form onSubmit={handleSubmit}>
      {error && <div style={{ padding: '6px 10px', background: '#FEF2F2', borderRadius: 6, fontSize: 11, color: '#DC2626', marginBottom: 10 }}>{error}</div>}
      {success && <div style={{ padding: '6px 10px', background: '#F0FDF4', borderRadius: 6, fontSize: 11, color: '#16A34A', marginBottom: 10 }}>{success}</div>}
      <input type="password" value={current} onChange={e => setCurrent(e.target.value)} placeholder="Current password" required
        style={{ width: '100%', padding: '9px 12px', border: '1px solid #E2E8F0', borderRadius: 8, fontSize: 13, marginBottom: 8 }} />
      <input type="password" value={newPass} onChange={e => setNewPass(e.target.value)} placeholder="New password" required minLength={6}
        style={{ width: '100%', padding: '9px 12px', border: '1px solid #E2E8F0', borderRadius: 8, fontSize: 13, marginBottom: 8 }} />
      <input type="password" value={confirm} onChange={e => setConfirm(e.target.value)} placeholder="Confirm new password" required minLength={6}
        style={{ width: '100%', padding: '9px 12px', border: '1px solid #E2E8F0', borderRadius: 8, fontSize: 13, marginBottom: 12 }} />
      <div style={{ display: 'flex', gap: 8 }}>
        <button type="button" onClick={onDone} style={{ flex: 1, padding: '9px 0', border: '1px solid #E2E8F0', borderRadius: 8, background: '#fff', fontSize: 12, fontWeight: 600, cursor: 'pointer' }}>Cancel</button>
        <button type="submit" disabled={loading} style={{ flex: 1, padding: '9px 0', border: 'none', borderRadius: 8, background: '#16A34A', color: '#fff', fontSize: 12, fontWeight: 600, cursor: loading ? 'wait' : 'pointer', opacity: loading ? 0.7 : 1 }}>{loading ? 'Saving...' : 'Save'}</button>
      </div>
    </form>
  );
}

export default function CitizenPortal({ user, profile, onLogout }) {
  const [lang, setLang] = useState(() => localStorage.getItem('locats_lang') || 'en');
  const [villages, setVillages] = useState([]);
  const [selectedVillage, setSelectedVillage] = useState(null);
  const [villageStatus, setVillageStatus] = useState(null);
  const [shelters, setShelters] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('home');
  const [showReport, setShowReport] = useState(false);
  const [reportStatus, setReportStatus] = useState(null);
  const [familyQuery, setFamilyQuery] = useState('');
  const [familyResults, setFamilyResults] = useState(null);
  const [helpSent, setHelpSent] = useState(false);
  const [helpConfirm, setHelpConfirm] = useState(false);
  const [helpSending, setHelpSending] = useState(false);
  const [gpsLoading, setGpsLoading] = useState(false);
  const [gpsError, setGpsError] = useState(null);
  const [showChangePass, setShowChangePass] = useState(false);

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
      setError(null);
    } catch (e) {
      setError('offline');
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

  const useMyLocation = useCallback(() => {
    if (!navigator.geolocation) { setGpsError('GPS not supported'); return; }
    setGpsLoading(true); setGpsError(null);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const { latitude: lat, longitude: lon } = pos.coords;
        // Haversine distance to find nearest village
        const R = 6371;
        let nearest = null, minDist = Infinity;
        for (const v of villages) {
          const dLat = (v.lat - lat) * Math.PI / 180;
          const dLon = (v.lon - lon) * Math.PI / 180;
          const a = Math.sin(dLat/2)**2 + Math.cos(lat*Math.PI/180) * Math.cos(v.lat*Math.PI/180) * Math.sin(dLon/2)**2;
          const d = R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
          if (d < minDist) { minDist = d; nearest = v; }
        }
        if (nearest) { setSelectedVillage(nearest.id); setHelpSent(false); }
        setGpsLoading(false);
      },
      () => { setGpsError('Location access denied. Select from list.'); setGpsLoading(false); },
      { enableHighAccuracy: false, timeout: 10000 }
    );
  }, [villages]);

  const sendHelp = useCallback(async () => {
    if (helpSent || !selectedVillage || helpSending) return;
    setHelpSending(true);
    try {
      const village = villages.find(v => v.id === selectedVillage);
      await fetch(`${API}/citizen/report`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          reporter_id: `citizen-${Date.now()}`,
          hazard_type: 'flood',
          severity_estimate: 0.5,
          description: `SOS help request from ${village?.name || 'unknown village'}`,
          lat: 30.40, lon: 79.33,
        }),
      });
      setHelpSent(true);
      setHelpConfirm(false);
      setTimeout(() => setHelpSent(false), 300000);
    } catch (e) {}
    finally { setHelpSending(false); }
  }, [selectedVillage, helpSent, helpSending, villages]);

  const submitReport = useCallback(async (type) => {
    try {
      await fetch(`${API}/citizen/report`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reporter_id: `citizen-${Date.now()}`, hazard_type: type, severity_estimate: 0.7, description: `Citizen report: ${type}`, lat: 30.40, lon: 79.33 }),
      });
      setReportStatus(`Reported: ${type}. Thank you.`);
      setTimeout(() => { setReportStatus(null); setShowReport(false); }, 3000);
    } catch (e) {}
  }, []);

  const [familyAge, setFamilyAge] = useState('');
  const [familyVillage, setFamilyVillage] = useState('');

  const searchFamily = useCallback(async () => {
    if (!familyQuery.trim()) return;
    try {
      const res = await fetch(`${API}/family/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          search_name: familyQuery,
          age_range: familyAge || undefined,
          home_habitation_id: familyVillage || undefined,
        }),
      });
      setFamilyResults(await res.json());
    } catch (e) { setFamilyResults({ results: [], message: 'Search unavailable' }); }
  }, [familyQuery, familyAge, familyVillage]);

  const statusColor = (level) => ({ critical: '#DC2626', warning: '#F59E0B', normal: '#22C55E' }[level] || '#94A3B8');
  const statusBg = (level) => ({ critical: '#FEF2F2', warning: '#FFFBEB', normal: '#F0FDF4' }[level] || '#F8FAFC');
  const statusLabel = (level) => ({ critical: t.statusCritical, warning: t.statusWarning, normal: t.statusNormal }[level] || 'Unknown');

  if (loading) {
    return (
      <div style={{ minHeight: '100vh', background: '#F0F9F4', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ textAlign: 'center' }}>
          <div className="animate-glow" style={{ width: 48, height: 48, borderRadius: 12, background: 'linear-gradient(135deg, #16A34A, #0D9488)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 16px' }}>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2"><path d="M12 2v4m0 12v4m-7.07-15.07l2.83 2.83m8.48 8.48l2.83 2.83M2 12h4m12 0h4m-15.07 7.07l2.83-2.83m8.48-8.48l2.83-2.83"/></svg>
          </div>
          <div style={{ fontSize: 14, color: '#6B7280', fontWeight: 500 }}>Loading Chamoli data...</div>
        </div>
      </div>
    );
  }

  return (
    <div style={{ minHeight: '100vh', background: '#F0F9F4', fontFamily: 'Inter, sans-serif', display: 'flex', flexDirection: 'column' }}>
      {/* Emergency Banner */}
      <div style={{ background: 'linear-gradient(135deg, #16A34A, #0D9488)', color: '#fff', padding: '10px 16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 13, fontWeight: 600, flexShrink: 0 }}>
        <span>{t.emergency}</span>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <span style={{ opacity: 0.9, fontSize: 11 }}>{t.helpline}</span>
          <button onClick={() => setLang(lang === 'en' ? 'hi' : 'en')} style={{ background: 'rgba(255,255,255,0.2)', color: '#fff', border: 'none', borderRadius: 6, padding: '3px 8px', fontSize: 11, fontWeight: 700, cursor: 'pointer' }}>{lang === 'en' ? 'HI' : 'EN'}</button>
        </div>
      </div>

      {/* Header */}
      <div style={{ background: '#fff', borderBottom: '1px solid #E5E7EB', padding: '12px 16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 32, height: 32, borderRadius: 8, background: 'linear-gradient(135deg, #16A34A, #0D9488)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontWeight: 800, fontSize: 14 }}>L</div>
          <div>
            <div style={{ fontSize: 15, fontWeight: 700, color: '#111827' }}>{t.title}</div>
            <div style={{ fontSize: 10, color: '#94A3B8' }}>{t.subtitle}</div>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 11, color: '#6B7280' }}>{profile?.full_name || user?.email}</span>
          {token && <button onClick={() => setShowChangePass(true)} style={{ background: 'none', border: 'none', color: '#94A3B8', fontSize: 11, cursor: 'pointer', fontWeight: 500 }}>Change Password</button>}
          <button onClick={() => { onLogout?.(); window.location.href = '/'; }} style={{ background: 'none', border: 'none', color: '#94A3B8', fontSize: 11, cursor: 'pointer', fontWeight: 500 }}>{t.signOut}</button>
        </div>
      </div>

      {/* Main Content */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px', paddingBottom: 80, maxWidth: 600, margin: '0 auto', width: '100%' }}>
        {error === 'offline' && (
          <div style={{ background: '#FEF3C7', border: '1px solid #FDE68A', borderRadius: 10, padding: '10px 14px', marginBottom: 14, fontSize: 12, color: '#92400E', display: 'flex', alignItems: 'center', gap: 6 }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#92400E" strokeWidth="2"><path d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>
            {t.offline}
          </div>
        )}

        {/* === HOME TAB === */}
        {activeTab === 'home' && (
          <>
            {/* Village Selector */}
            <div style={{ background: '#fff', borderRadius: 14, border: '1px solid #E5E7EB', padding: 16, marginBottom: 14, boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}>
              <label style={{ fontSize: 13, fontWeight: 600, color: '#374151', display: 'block', marginBottom: 6 }}>{t.selectVillage}</label>
              <select value={selectedVillage || ''} onChange={e => { setSelectedVillage(e.target.value); setHelpSent(false); setGpsError(null); }}
                style={{ width: '100%', padding: '11px 14px', borderRadius: 10, border: '1px solid #D1D5DB', fontSize: 14, fontWeight: 500, color: '#111827', background: '#F9FAFB', appearance: 'none' }}>
                <option value="">-- {t.selectVillage} --</option>
                {villages.map(v => <option key={v.id} value={v.id}>{v.name} ({v.block})</option>)}
              </select>
              <button onClick={useMyLocation} disabled={gpsLoading || !navigator.geolocation}
                style={{ marginTop: 8, width: '100%', padding: '9px 14px', borderRadius: 10, border: '1px solid #D1D5DB', background: '#F9FAFB', fontSize: 12, fontWeight: 600, color: '#374151', cursor: gpsLoading ? 'wait' : 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#374151" strokeWidth="2"><path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/></svg>
                {gpsLoading ? t.locating : t.useMyLocation}
              </button>
              {gpsError && <div style={{ marginTop: 6, padding: '6px 10px', background: '#FEF3C7', borderRadius: 6, fontSize: 11, color: '#92400E' }}>{gpsError}</div>}
            </div>

            {/* Status Card */}
            {villageStatus && (
              <>
                <div style={{ background: statusBg(villageStatus.hazard_level), border: `1px solid ${statusColor(villageStatus.hazard_level)}20`, borderRadius: 14, padding: 16, marginBottom: 14 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                    <div style={{ width: 10, height: 10, borderRadius: '50%', background: statusColor(villageStatus.hazard_level), boxShadow: villageStatus.hazard_level === 'critical' ? `0 0 8px ${statusColor(villageStatus.hazard_level)}` : 'none' }} />
                    <span style={{ fontSize: 17, fontWeight: 800, color: statusColor(villageStatus.hazard_level) }}>{statusLabel(villageStatus.hazard_level)}</span>
                  </div>
                  <div style={{ fontSize: 13, color: '#374151', lineHeight: 1.5 }}>{villageStatus.hazard_detail}</div>
                </div>

                {/* Action Card */}
                <div style={{ background: '#fff', borderRadius: 14, border: '1px solid #E5E7EB', padding: 16, marginBottom: 14 }}>
                  <div style={{ fontSize: 13, fontWeight: 700, color: '#111827', marginBottom: 6 }}>{t.whatToDo}</div>
                  <div style={{ fontSize: 13, color: '#374151', lineHeight: 1.5 }}>{villageStatus.action_text}</div>
                </div>

                {/* Nearest Shelter */}
                {villageStatus.nearest_shelter && (
                  <div style={{ background: '#fff', borderRadius: 14, border: '1px solid #E5E7EB', padding: 16, marginBottom: 14, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <div style={{ fontSize: 12, color: '#6B7280', marginBottom: 2 }}>{t.nearestShelter}</div>
                      <div style={{ fontSize: 14, fontWeight: 700, color: '#16A34A' }}>{villageStatus.nearest_shelter.name}</div>
                      <div style={{ fontSize: 11, color: '#94A3B8' }}>{villageStatus.nearest_shelter.distance_km} km away</div>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <div style={{ fontSize: 20, fontWeight: 800, color: '#16A34A' }}>{villageStatus.nearest_shelter.beds_available}</div>
                      <div style={{ fontSize: 10, color: '#94A3B8' }}>{t.bedsFree}</div>
                    </div>
                  </div>
                )}

                {/* Quick Action Buttons */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 14 }}>
                  <button onClick={() => { if (!helpSent) setHelpConfirm(true); }} disabled={helpSent}
                    style={{ padding: '14px 12px', borderRadius: 12, border: 'none', background: helpSent ? '#D1D5DB' : 'linear-gradient(135deg, #DC2626, #B91C1C)', color: '#fff', fontSize: 13, fontWeight: 700, cursor: helpSent ? 'default' : 'pointer', boxShadow: helpSent ? 'none' : '0 2px 8px rgba(220,38,38,0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
                    {helpSent ? 'SOS Sent - Help On Way' : t.helpButton}
                  </button>
                  <button onClick={() => { setActiveTab('report'); setShowReport(true); }}
                    style={{ padding: '14px 12px', borderRadius: 12, border: '1px solid #D1D5DB', background: '#fff', color: '#374151', fontSize: 13, fontWeight: 700, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#F59E0B" strokeWidth="2"><path d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>
                    {t.reportHazard}
                  </button>
                </div>
              </>
            )}

            {/* No village selected */}
            {!villageStatus && !loading && (
              <div style={{ textAlign: 'center', padding: '40px 20px', color: '#94A3B8' }}>
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#D1D5DB" strokeWidth="1.5" style={{ margin: '0 auto 12px' }}><path d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"/></svg>
                <div style={{ fontSize: 14, fontWeight: 600, color: '#475569', marginBottom: 4 }}>Select your village</div>
                <div style={{ fontSize: 12 }}>Choose your village above to see hazard status and shelter info</div>
              </div>
            )}
          </>
        )}

        {/* === SHELTERS TAB === */}
        {activeTab === 'shelters' && (
          <div>
            <h2 style={{ fontSize: 18, fontWeight: 800, color: '#111827', marginBottom: 4 }}>{t.findShelter}</h2>
            <p style={{ fontSize: 12, color: '#94A3B8', marginBottom: 14 }}>All active shelters in Chamoli district</p>
            {shelters.map((s, i) => (
              <div key={i} style={{ background: '#fff', borderRadius: 12, border: '1px solid #E5E7EB', padding: 14, marginBottom: 10, display: 'flex', justifyContent: 'space-between', alignItems: 'center', transition: 'transform 0.2s' }} onMouseEnter={e => e.currentTarget.style.transform = 'translateY(-1px)'} onMouseLeave={e => e.currentTarget.style.transform = ''}>
                <div>
                  <div style={{ fontSize: 14, fontWeight: 600, color: '#111827' }}>{s.name}</div>
                  <div style={{ fontSize: 11, color: '#6B7280' }}>{s.district} | {s.type}</div>
                  <div style={{ display: 'flex', gap: 4, marginTop: 4 }}>
                    {s.is_accessible && <span style={{ fontSize: 9, padding: '2px 6px', background: '#EFF6FF', color: '#2563EB', borderRadius: 4, fontWeight: 600 }}>Accessible</span>}
                    <span style={{ fontSize: 9, padding: '2px 6px', background: s.status === 'open' ? '#F0FDF4' : '#FEF3C7', color: s.status === 'open' ? '#16A34A' : '#D97706', borderRadius: 4, fontWeight: 600 }}>{s.status}</span>
                  </div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontSize: 20, fontWeight: 800, color: s.beds_available > 100 ? '#16A34A' : s.beds_available > 0 ? '#F59E0B' : '#DC2626' }}>{s.beds_available.toLocaleString()}</div>
                  <div style={{ fontSize: 10, color: '#94A3B8' }}>{t.bedsFree}</div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* === REPORT TAB === */}
        {activeTab === 'report' && (
          <div>
            <h2 style={{ fontSize: 18, fontWeight: 800, color: '#111827', marginBottom: 4 }}>{t.reportHazard}</h2>
            <p style={{ fontSize: 12, color: '#94A3B8', marginBottom: 14 }}>Your report helps protect your community</p>
            {reportStatus ? (
              <div style={{ background: '#F0FDF4', border: '1px solid #BBF7D0', borderRadius: 12, padding: 20, textAlign: 'center', color: '#16A34A', fontWeight: 600, fontSize: 14 }}>{reportStatus}</div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {[{ type: 'flood', label: 'Flood / Water Rising', color: '#2563EB', bg: '#EFF6FF' }, { type: 'landslide', label: 'Landslide / Rock Fall', color: '#D97706', bg: '#FFFBEB' }, { type: 'earthquake', label: 'Earthquake / Tremor', color: '#DC2626', bg: '#FEF2F2' }].map(r => (
                  <button key={r.type} onClick={() => submitReport(r.type)}
                    style={{ padding: '16px', borderRadius: 12, border: `1px solid ${r.color}20`, background: r.bg, fontSize: 14, fontWeight: 700, color: r.color, cursor: 'pointer', textAlign: 'left', display: 'flex', alignItems: 'center', gap: 12, transition: 'transform 0.15s' }} onMouseEnter={e => e.currentTarget.style.transform = 'scale(1.01)'} onMouseLeave={e => e.currentTarget.style.transform = ''}>
                    <div style={{ width: 36, height: 36, borderRadius: 10, background: `${r.color}15`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                      {r.type === 'flood' && <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={r.color} strokeWidth="2"><path d="M20 16.58A5 5 0 0018 7h-1.26A8 8 0 104 15.25"/></svg>}
                      {r.type === 'landslide' && <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={r.color} strokeWidth="2"><path d="M3 20h18M5 20l4-12 4 8 3-4 3 8"/></svg>}
                      {r.type === 'earthquake' && <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={r.color} strokeWidth="2"><path d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>}
                    </div>
                    {r.label}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {/* === FAMILY TAB === */}
        {activeTab === 'family' && (
          <div>
            <h2 style={{ fontSize: 18, fontWeight: 800, color: '#111827', marginBottom: 4 }}>{t.familySearch}</h2>
            <p style={{ fontSize: 12, color: '#94A3B8', marginBottom: 14 }}>Find family members across shelters</p>
            <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
              <input value={familyQuery} onChange={e => setFamilyQuery(e.target.value)} onKeyDown={e => e.key === 'Enter' && searchFamily()}
                placeholder="Enter person's name" style={{ flex: 1, padding: '11px 14px', borderRadius: 10, border: '1px solid #D1D5DB', fontSize: 13, background: '#fff' }} />
              <button onClick={searchFamily} disabled={!familyQuery.trim()}
                style={{ padding: '11px 18px', borderRadius: 10, border: 'none', background: '#2563EB', color: '#fff', fontSize: 13, fontWeight: 600, cursor: 'pointer' }}>Search</button>
            </div>
            <div style={{ display: 'flex', gap: 8, marginBottom: 14 }}>
              <select value={familyAge} onChange={e => setFamilyAge(e.target.value)}
                style={{ flex: 1, padding: '9px 12px', borderRadius: 10, border: '1px solid #D1D5DB', fontSize: 12, background: '#fff', color: '#6B7280' }}>
                <option value="">Any age group</option>
                <option value="child">Child (0-12)</option>
                <option value="teen">Teen (13-17)</option>
                <option value="adult">Adult (18-59)</option>
                <option value="senior">Senior (60+)</option>
              </select>
              <select value={familyVillage} onChange={e => setFamilyVillage(e.target.value)}
                style={{ flex: 1, padding: '9px 12px', borderRadius: 10, border: '1px solid #D1D5DB', fontSize: 12, background: '#fff', color: '#6B7280' }}>
                <option value="">Any village</option>
                {villages.map(v => <option key={v.id} value={v.id}>{v.name}</option>)}
              </select>
            </div>
            {familyResults && (
              <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #E5E7EB', padding: 14 }}>
                <div style={{ fontSize: 13, color: '#6B7280', marginBottom: 8 }}>{familyResults.message}</div>
                {familyResults.results?.map((r, i) => (
                  <div key={i} style={{ padding: '10px 0', borderBottom: '1px solid #F3F4F6', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 600, color: '#111827' }}>{r.shelter_name || r.shelter_id}</div>
                      <div style={{ fontSize: 11, color: '#94A3B8' }}>{r.registered_at?.split('T')[0]}</div>
                    </div>
                    <span style={{ padding: '3px 10px', borderRadius: 20, fontSize: 11, fontWeight: 700, background: r.status === 'safe' ? '#F0FDF4' : '#FEF3C7', color: r.status === 'safe' ? '#16A34A' : '#D97706' }}>{r.status}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Change Password Modal */}
      {showChangePass && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 200, padding: 20 }} onClick={() => setShowChangePass(false)}>
          <div style={{ background: '#fff', borderRadius: 16, padding: 24, maxWidth: 340, width: '100%' }} onClick={e => e.stopPropagation()}>
            <h3 style={{ fontSize: 16, fontWeight: 700, marginBottom: 14 }}>Change Password</h3>
            <ChangePasswordForm token={token} onDone={() => setShowChangePass(false)} />
          </div>
        </div>
      )}

      {/* SOS Confirmation Dialog */}
      {helpConfirm && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 200, padding: 20 }}>
          <div style={{ background: '#fff', borderRadius: 16, padding: 24, maxWidth: 340, width: '100%', boxShadow: '0 20px 60px rgba(0,0,0,0.3)' }}>
            <div style={{ textAlign: 'center', marginBottom: 16 }}>
              <div style={{ width: 48, height: 48, borderRadius: '50%', background: '#FEF2F2', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 12px' }}>
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#DC2626" strokeWidth="2"><path d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>
              </div>
              <div style={{ fontSize: 17, fontWeight: 800, color: '#111827', marginBottom: 4 }}>Send SOS Help Request?</div>
              <div style={{ fontSize: 12, color: '#6B7280', lineHeight: 1.5 }}>
                Emergency services and nearby shelters will be notified immediately.
              </div>
            </div>
            {villageStatus?.nearest_shelter && (
              <div style={{ background: '#F0FDF4', border: '1px solid #BBF7D0', borderRadius: 10, padding: 12, marginBottom: 16 }}>
                <div style={{ fontSize: 11, color: '#16A34A', fontWeight: 600, marginBottom: 4 }}>Nearest shelter to go to:</div>
                <div style={{ fontSize: 14, fontWeight: 700, color: '#166534' }}>{villageStatus.nearest_shelter.name}</div>
                <div style={{ fontSize: 11, color: '#6B7280' }}>{villageStatus.nearest_shelter.distance_km} km away | {villageStatus.nearest_shelter.beds_available} beds free</div>
              </div>
            )}
            <div style={{ background: '#FFFBEB', border: '1px solid #FDE68A', borderRadius: 10, padding: 12, marginBottom: 16 }}>
              <div style={{ fontSize: 11, color: '#92400E', lineHeight: 1.5 }}>
                While waiting, stay away from water bodies and follow marked evacuation routes. Dial 1070 for emergency.
              </div>
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={() => setHelpConfirm(false)}
                style={{ flex: 1, padding: '11px 0', borderRadius: 10, border: '1px solid #D1D5DB', background: '#fff', color: '#374151', fontSize: 13, fontWeight: 600, cursor: 'pointer' }}>Cancel</button>
              <button onClick={sendHelp} disabled={helpSending}
                style={{ flex: 1, padding: '11px 0', borderRadius: 10, border: 'none', background: 'linear-gradient(135deg, #DC2626, #B91C1C)', color: '#fff', fontSize: 13, fontWeight: 700, cursor: helpSending ? 'wait' : 'pointer', boxShadow: '0 2px 8px rgba(220,38,38,0.3)' }}>
                {helpSending ? 'Sending...' : 'Send SOS'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Bottom Navigation */}
      <div style={{ position: 'fixed', bottom: 0, left: 0, right: 0, background: '#fff', borderTop: '1px solid #E5E7EB', display: 'flex', justifyContent: 'space-around', padding: '8px 0', paddingBottom: 'max(8px, env(safe-area-inset-bottom))', zIndex: 100 }}>
        {[
          { id: 'home', label: t.home, icon: <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"/></svg> },
          { id: 'shelters', label: t.shelters, icon: <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"/></svg> },
          { id: 'report', label: t.report, icon: <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg> },
          { id: 'family', label: t.family, icon: <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"/></svg> },
        ].map(tab => (
          <button key={tab.id} onClick={() => setActiveTab(tab.id)}
            style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2, background: 'none', border: 'none', color: activeTab === tab.id ? '#16A34A' : '#94A3B8', cursor: 'pointer', padding: '4px 12px', fontSize: 10, fontWeight: activeTab === tab.id ? 700 : 500, transition: 'color 0.15s' }}>
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>
    </div>
  );
}
