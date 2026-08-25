import React, { useState, useRef, useEffect, useCallback } from 'react';

const API = '/api';

export default function WhatsAppBot() {
  const [messages, setMessages] = useState([
    { from: 'bot', text: 'Welcome to LocaTS Emergency Bot. I can help you report hazards or find shelters.', time: new Date() },
    { from: 'bot', text: 'What would you like to do?\n1. Report a hazard\n2. Find nearest shelter\n3. Check village status\n4. Get evacuation instructions\n\nType a number or tap a button below.', time: new Date() },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [session, setSession] = useState({ step: 'main', data: {} });
  const endRef = useRef(null);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  const addBotMsg = useCallback((text) => {
    setMessages(prev => [...prev, { from: 'bot', text, time: new Date() }]);
  }, []);

  const handleQuickAction = useCallback(async (action) => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/whatsapp/action`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, session }),
      });
      const data = await res.json();
      addBotMsg(data.reply);
      if (data.new_session) setSession(data.new_session);
    } catch (e) {
      addBotMsg('Sorry, service is temporarily unavailable. Please try again.');
    } finally {
      setLoading(false);
    }
  }, [session, addBotMsg]);

  const sendMessage = useCallback(async () => {
    if (!input.trim()) return;
    const userText = input.trim();
    setInput('');
    setMessages(prev => [...prev, { from: 'user', text: userText, time: new Date() }]);
    setLoading(true);

    try {
      const res = await fetch(`${API}/whatsapp/message`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userText, session }),
      });
      const data = await res.json();
      addBotMsg(data.reply);
      if (data.new_session) setSession(data.new_session);
    } catch (e) {
      addBotMsg('Service unavailable. Please try again.');
    } finally {
      setLoading(false);
    }
  }, [input, session, addBotMsg]);

  return (
    <div style={{ maxWidth: 420, margin: '0 auto', height: '100%', display: 'flex', flexDirection: 'column', background: '#E5DDD5', borderRadius: 16, overflow: 'hidden', border: '1px solid #D1D9DB' }}>
      {/* Prototype Badge */}
      <div style={{ background: '#FEF3C7', borderBottom: '1px solid #FDE68A', padding: '8px 18px', fontSize: 12, color: '#92400E', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}>
        <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#F59E0B' }} />
        Prototype — not connected to WhatsApp Business API
      </div>

      {/* Header */}
      <div style={{ background: '#075E54', color: '#fff', padding: '14px 18px', display: 'flex', alignItems: 'center', gap: 12 }}>
        <div style={{ width: 36, height: 36, borderRadius: '50%', background: '#25D366', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 16, fontWeight: 800 }}>W</div>
        <div>
          <div style={{ fontSize: 14, fontWeight: 600 }}>LocaTS Emergency Bot</div>
          <div style={{ fontSize: 11, opacity: 0.8 }}>Chamoli District Disaster Response</div>
        </div>
      </div>

      {/* Messages */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: 8 }}>
        {messages.map((m, i) => (
          <div key={i} style={{ display: 'flex', justifyContent: m.from === 'user' ? 'flex-end' : 'flex-start' }}>
            <div style={{
              maxWidth: '80%', padding: '10px 14px', borderRadius: 12,
              background: m.from === 'user' ? '#DCF8C6' : '#fff',
              border: '1px solid ' + (m.from === 'user' ? '#C5E1A5' : '#E0E0E0'),
              fontSize: 13, lineHeight: 1.5, color: '#303030', whiteSpace: 'pre-wrap',
            }}>
              {m.text}
              <div style={{ fontSize: 10, color: '#999', marginTop: 4, textAlign: 'right' }}>
                {m.time.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </div>
            </div>
          </div>
        ))}
        {loading && (
          <div style={{ display: 'flex', justifyContent: 'flex-start' }}>
            <div style={{ padding: '10px 14px', borderRadius: 12, background: '#fff', border: '1px solid #E0E0E0', fontSize: 13, color: '#999' }}>
              Typing...
            </div>
          </div>
        )}
        <div ref={endRef} />
      </div>

      {/* Quick Actions */}
      <div style={{ padding: '8px 14px', borderTop: '1px solid #D1D9DB', display: 'flex', gap: 6, flexWrap: 'wrap', background: '#F5F5F5' }}>
        {[
          { label: 'Report Flood', action: 'report_flood', color: '#EF4444' },
          { label: 'Report Landslide', action: 'report_landslide', color: '#F59E0B' },
          { label: 'Find Shelter', action: 'find_shelter', color: '#22C55E' },
          { label: 'Village Status', action: 'village_status', color: '#2563EB' },
          { label: 'I Need Help', action: 'need_help', color: '#DC2626' },
        ].map(btn => (
          <button key={btn.action} onClick={() => handleQuickAction(btn.action)} disabled={loading}
            style={{ padding: '6px 12px', borderRadius: 16, border: 'none', background: btn.color, color: '#fff', fontSize: 11, fontWeight: 600, cursor: loading ? 'default' : 'pointer', opacity: loading ? 0.6 : 1 }}>
            {btn.label}
          </button>
        ))}
      </div>

      {/* Input */}
      <div style={{ padding: '10px 14px', borderTop: '1px solid #D1D9DB', display: 'flex', gap: 8, background: '#F0F0F0' }}>
        <input value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') sendMessage(); }}
          placeholder="Type a message..." disabled={loading}
          style={{ flex: 1, padding: '10px 14px', borderRadius: 20, border: '1px solid #D1D9DB', fontSize: 13, outline: 'none' }} />
        <button onClick={sendMessage} disabled={loading || !input.trim()}
          style={{ width: 40, height: 40, borderRadius: '50%', background: '#25D366', border: 'none', color: '#fff', fontSize: 18, cursor: loading ? 'default' : 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/></svg>
        </button>
      </div>
    </div>
  );
}
