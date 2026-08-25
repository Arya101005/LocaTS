import React, { useState, useCallback } from 'react';

const API = '/api';
const optionLabels = { '1':'Report Hazard', '2':'Evacuation Info', '3':'Find Family', 'flood':'Flood', 'landslide':'Landslide', 'earthquake':'Earthquake' };

export default function IVRDemo() {
  const [sessionId, setSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [language, setLanguage] = useState('en');
  const [options, setOptions] = useState({});
  const [done, setDone] = useState(false);
  const [loading, setLoading] = useState(false);

  const start = useCallback(async () => {
    setLoading(true); setMessages([]); setDone(false);
    try {
      const res = await fetch(`${API}/ivr/start?language=${language}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const d = await res.json();
      setSessionId(d.session_id);
      setMessages([{ role: 'system', text: d.text }]);
      setOptions(d.options || {});
    } catch (e) { setMessages([{ role: 'error', text: `Connection failed: ${e.message}` }]); }
    finally { setLoading(false); }
  }, [language]);

  const send = useCallback(async (val) => {
    if (!sessionId || loading) return;
    setLoading(true); setMessages(p => [...p, { role: 'user', text: optionLabels[val]||val }]); setOptions({});
    try {
      const res = await fetch(`${API}/ivr/input?session_id=${sessionId}&user_input=${encodeURIComponent(val)}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const d = await res.json();
      setMessages(p => [...p, { role: 'system', text: d.text }]);
      setOptions(d.options || {}); setDone(d.done || false);
    } catch (e) { setMessages(p => [...p, { role: 'error', text: e.message }]); }
    finally { setLoading(false); }
  }, [sessionId, loading]);

  return (
    <div style={{ maxWidth: 600, margin: '0 auto' }}>
      <div style={{ marginBottom: 28 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
          <h2 style={{ fontSize: 22, fontWeight: 800, margin: 0 }}>Phone Helpline Demo</h2>
          <span style={{ padding: '3px 10px', borderRadius: 12, fontSize: 11, fontWeight: 700, background: '#FEF3C7', color: '#92400E', border: '1px solid #FDE68A' }}>Prototype</span>
        </div>
        <p style={{ fontSize: 13, color: 'var(--text-muted)' }}>Simulates a helpline for people without smartphones. Connects via Twilio in production.</p>
      </div>
      {!sessionId ? (
        <div style={{ maxWidth: 300 }}>
          <div className="form-group">
            <label className="form-label">Language</label>
            <select className="form-select" value={language} onChange={e => setLanguage(e.target.value)}>
              <option value="en">English</option><option value="hi">Hindi</option>
            </select>
          </div>
          <button className="btn btn-primary btn-block" onClick={start} disabled={loading}>Start Call</button>
        </div>
      ) : (
        <div className="ivr-phone-frame">
          <div className="ivr-phone-bar">
            <div className="phone-icon"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2"><path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07 19.5 19.5 0 01-6-6 19.79 19.79 0 01-3.07-8.67A2 2 0 014.11 2h3a2 2 0 012 1.72c.127.96.361 1.903.7 2.81a2 2 0 01-.45 2.11L8.09 9.91a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0122 16.92z"/></svg></div>
            <span>LocaTS Helpline</span>
            <button className="btn btn-sm btn-danger" onClick={() => { setSessionId(null); setMessages([]); setOptions({}); setDone(false); }} style={{ marginLeft: 'auto' }}>End Call</button>
          </div>
          <div className="ivr-messages">
            {messages.map((m,i) => <div key={i} className={`ivr-msg ${m.role==='user'?'user':'system'}`}><div className="ivr-msg-avatar">{m.role==='user'?'U':'AI'}</div><div className="ivr-msg-bubble">{m.text}</div></div>)}
            {loading && <div className="ivr-msg system"><div className="ivr-msg-avatar">AI</div><div className="ivr-msg-bubble" style={{ color: 'var(--text-muted)' }}>Processing...</div></div>}
          </div>
          {!done && Object.keys(options).length > 0 && !loading && (
            <div className="ivr-options">{Object.entries(options).map(([key]) => <button key={key} className="ivr-option-btn" onClick={() => send(key)}>{optionLabels[key]||key}</button>)}</div>
          )}
          {done && <div style={{ padding: 20, textAlign: 'center', borderTop: '1px solid var(--border)' }}><p style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 12 }}>Call ended.</p><button className="btn btn-primary btn-sm" onClick={start}>Call Again</button></div>}
        </div>
      )}
      <div className="card" style={{ marginTop: 28, padding: 18 }}>
        <div className="card-header">How It Works in Production</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: 13, color: 'var(--text-secondary)' }}>
          {['Connected via Twilio to a real phone number (no internet needed)','Voice recognition for Hindi + English speech input','TTS engine reads evacuation instructions in local language','Calls logged and routed to nearest shelter command center'].map((t,i) => (
            <div key={i} style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
              <div style={{ width: 22, height: 22, borderRadius: 6, background: 'var(--primary-bg)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, fontWeight: 800, color: 'var(--primary)', flexShrink: 0 }}>{i+1}</div>
              <span>{t}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
