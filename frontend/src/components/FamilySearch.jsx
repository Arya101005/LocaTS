import React, { useState, useCallback } from 'react';

const API = '/api';

export default function FamilySearch() {
  const [name, setName] = useState('');
  const [habitation, setHabitation] = useState('');
  const [results, setResults] = useState(null);
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [tab, setTab] = useState('search');
  const [regForm, setRegForm] = useState({ name: '', shelter_id: '', age_range: 'adult', home_habitation_id: '', needs_medical: false, needs_accessibility: false });
  const [regResult, setRegResult] = useState(null);

  const search = useCallback(async () => {
    if (!name) return; setLoading(true); setMessage('');
    try { const r = await fetch(`${API}/family/search`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ search_name: name, home_habitation_id: habitation || undefined }) }); const d = await r.json(); setResults(d.results||[]); setMessage(d.message); }
    catch (e) { setMessage(`Error: ${e.message}`); }
    finally { setLoading(false); }
  }, [name, habitation]);

  const register = useCallback(async () => {
    if (!regForm.name || !regForm.shelter_id) return; setLoading(true);
    try { const r = await fetch(`${API}/family/register`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name_hash: regForm.name, registered_shelter_id: regForm.shelter_id, age_range: regForm.age_range, home_habitation_id: regForm.home_habitation_id, needs_medical: regForm.needs_medical, needs_accessibility: regForm.needs_accessibility, status: 'safe' }) }); const d = await r.json(); setRegResult(d); setRegForm({ name:'', shelter_id:'', age_range:'adult', home_habitation_id:'', needs_medical:false, needs_accessibility:false }); }
    catch (e) { setRegResult({ error: e.message }); }
    finally { setLoading(false); }
  }, [regForm]);

  return (
    <div style={{ maxWidth: 600, margin: '0 auto' }}>
      <div style={{ marginBottom: 28 }}>
        <h2 style={{ fontSize: 22, fontWeight: 800, marginBottom: 4 }}>Family Reunification</h2>
        <p style={{ fontSize: 13, color: 'var(--text-muted)' }}>Register evacuees at shelters or search for separated family members.</p>
      </div>
      <div className="tab-bar">
        <button className={`tab-btn ${tab==='search'?'active':''}`} onClick={() => setTab('search')}>Search</button>
        <button className={`tab-btn ${tab==='register'?'active':''}`} onClick={() => setTab('register')}>Register</button>
      </div>
      {tab === 'search' ? (
        <div>
          <div className="form-group"><label className="form-label">Full Name</label><input className="form-input" value={name} onChange={e => setName(e.target.value)} placeholder="Enter the person's full name" /></div>
          <div className="form-group"><label className="form-label">Home Village (optional)</label><input className="form-input" value={habitation} onChange={e => setHabitation(e.target.value)} placeholder="e.g. Raini Village" /></div>
          <button className="btn btn-primary" onClick={search} disabled={loading||!name}>{loading ? 'Searching...' : 'Search All Shelters'}</button>
          {message && <div className="card" style={{ marginTop: 14, padding: 12, fontSize: 13, color: 'var(--text-secondary)' }}>{message}</div>}
          {results && results.length > 0 && (
            <div style={{ marginTop: 16, display: 'flex', flexDirection: 'column', gap: 8 }}>
              {results.map((r,i) => (
                <div key={i} className="assignment-card">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                    <span style={{ fontFamily: 'var(--mono)', fontSize: 12, fontWeight: 600, color: 'var(--purple)' }}>{r.evacuee_id}</span>
                    <span className={`badge badge-${r.status==='safe'?'safe':r.status==='missing'?'warn':'danger'}`}>{r.status}</span>
                  </div>
                  <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{r.shelter_name || r.shelter_id}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      ) : (
        <div>
          <div className="form-group"><label className="form-label">Person's Name</label><input className="form-input" value={regForm.name} onChange={e => setRegForm({...regForm, name: e.target.value})} placeholder="Full name" /></div>
          <div className="form-group"><label className="form-label">Shelter ID</label><input className="form-input" value={regForm.shelter_id} onChange={e => setRegForm({...regForm, shelter_id: e.target.value})} placeholder="e.g. shelter-health-0001" /></div>
          <div className="form-group"><label className="form-label">Age Group</label>
            <select className="form-select" value={regForm.age_range} onChange={e => setRegForm({...regForm, age_range: e.target.value})}>
              <option value="child">Child (under 12)</option><option value="adult">Adult</option><option value="elderly">Elderly (65+)</option>
            </select>
          </div>
          <div className="form-group"><label className="form-label">Home Village</label><input className="form-input" value={regForm.home_habitation_id} onChange={e => setRegForm({...regForm, home_habitation_id: e.target.value})} placeholder="Village name" /></div>
          <label className="form-checkbox"><input type="checkbox" checked={regForm.needs_medical} onChange={e => setRegForm({...regForm, needs_medical: e.target.checked})} /> Needs medical attention</label>
          <label className="form-checkbox" style={{ marginTop: 8 }}><input type="checkbox" checked={regForm.needs_accessibility} onChange={e => setRegForm({...regForm, needs_accessibility: e.target.checked})} /> Needs accessibility support</label>
          <div style={{ marginTop: 16 }}><button className="btn btn-primary" onClick={register} disabled={loading||!regForm.name||!regForm.shelter_id}>{loading ? 'Registering...' : 'Register Evacuee'}</button></div>
          {regResult && (
            <div className="card" style={{ marginTop: 16, padding: 14, borderColor: regResult.error?'rgba(239,68,68,0.2)':'rgba(34,197,94,0.2)', background: regResult.error?'var(--critical-bg)':'var(--safe-bg)' }}>
              {regResult.error ? <span style={{ color: 'var(--critical)', fontSize: 13 }}>{regResult.error}</span> : <>
                <div style={{ fontSize: 13, color: '#16A34A', marginBottom: 6 }}>{regResult.message}</div>
                <div style={{ fontFamily: 'var(--mono)', fontSize: 14, fontWeight: 700 }}>{regResult.evacuee_id}</div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>Show this ID at any shelter to locate this person.</div>
              </>}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
