import React, { useState, useCallback, useRef, useEffect } from 'react';

const API = '/api';

export default function AIAssistant({ data }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const endRef = useRef(null);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  const buildContext = useCallback(() => {
    const cap = data?.capacity_summary || {};
    const result = data?.latest_result;
    const zones = data?.hazard_zones || [];
    const conf = data?.hazard_confidences || {};
    const alerts = {};
    Object.values(conf).forEach(c => { alerts[c.alert_level] = (alerts[c.alert_level]||0)+1; });

    const shelterInfo = [];
    if (result?.assignments) {
      result.assignments.slice(0, 15).forEach(a => {
        shelterInfo.push(`${a.habitation_id} → ${a.shelter_id}: ${a.people_assigned} people, ${a.distance_km}km`);
      });
    }

    // Build zone details
    const zoneDetails = zones.map(z => `${z.type} zone: severity ${(z.severity*100).toFixed(0)}%`).join('; ');

    return `You are LocaTS AI — a helpful disaster management assistant for Chamoli district, Uttarakhand, India.

You are friendly, conversational, and helpful. You CAN discuss:
- Anything related to this disaster management system and Chamoli district
- Hazard zones, flood risks, landslide risks, seismic activity
- Evacuation plans, shelter capacity, relocation assignments
- Rainfall data, weather conditions
- System features and how they work
- General disaster preparedness advice for mountain regions

Only refuse if the question is completely unrelated to disaster management or this system (e.g., "write me a poem", "what's the stock price").

DISTRICT DATA:
- Chamoli, Uttarakhand — Seismic Zone IV, elevation 1300-3300m
- Population: ${cap.total_population?.toLocaleString()||'N/A'}
- Active Shelters: ${cap.active_shelters||0} with ${(cap.total_beds_available||0).toLocaleString()} beds
- Hazard Zones: ${zones.length} active (${zoneDetails || 'none currently mapped'})
- Alert Distribution: ${Object.entries(alerts).map(([k,v])=>`${k}: ${v}`).join(', ')||'none computed yet'}

${result?`LATEST EVACUATION PLAN:
- Status: ${result.is_feasible ? 'FEASIBLE — all people can be sheltered' : 'INFEASIBLE — more people than beds available'}
- People Relocated: ${result.total_people_relocated?.toLocaleString()||0}
- People Unmet: ${result.total_people_unmet?.toLocaleString()||0} (need additional shelter capacity)
- Method: ${result.used_fallback_heuristic ? 'Greedy heuristic' : 'OR-Tools optimal solver'}
- Assignments (${result.assignments?.length || 0} total):
${shelterInfo.join('\n') || 'No assignments yet'}
${result.total_people_unmet > 0 ? `\nNote: ${result.total_people_unmet.toLocaleString()} people couldn't be assigned. Officials should activate nearby district shelters or deploy temporary tent cities.` : ''}` : 'No optimization run yet. Go to Dashboard → Run Optimization to generate an evacuation plan.'}

SYSTEM FEATURES:
- Hazard Fusion: Combines static maps + live sensors + crowd reports (Bayesian scoring)
- OR-Tools Optimizer: Solves who goes to which shelter optimally
- Rolling-horizon: Re-plans when roads/shelters change
- Social Vulnerability: Prioritizes elderly, disabled, children
- IVR Helpline: Hindi/English phone menu (1800-XXX-XXXX)
- Family Search: Track separated family across shelters
- What-If Simulator: Test rainfall increase, road blocks, shelter closures
- Historical Backtesting: Tests against 2021 Chamoli flash flood

Be conversational and helpful. If someone asks about flood zones, tell them exactly which zones exist, their severity, and what actions to take. If they ask "where", describe the locations relative to known landmarks in Chamoli (Gopeshwar, Joshimath, Badrinath, etc).`;
  }, [data]);

  // Only block truly off-topic queries
  const BLOCKED_PATTERNS = ['write me a poem', 'tell me a joke', 'what is the stock price', 'bitcoin price', 'recipe for'];

  const send = useCallback(async (text) => {
    if (!text.trim()) return;

    const lowerText = text.toLowerCase().trim();
    const blocked = BLOCKED_PATTERNS.some(kw => lowerText.includes(kw));
    if (blocked) {
      setMessages(p => [...p, { role: 'user', text }, { role: 'assistant', text: "I'm focused on disaster management for Chamoli district. Ask me about hazard zones, evacuation plans, shelter capacity, or system features!" }]);
      return;
    }

    setMessages(p => [...p, { role: 'user', text }]);
    setInput(''); setLoading(true);
    try {
      const chatMessages = [
        ...messages.slice(-10).map(m => ({ role: m.role === 'user' ? 'user' : 'assistant', content: m.text })),
        { role: 'user', content: text },
      ];

      const res = await fetch(`${API}/ai/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: chatMessages,
          system_prompt: buildContext(),
        }),
      });

      const j = await res.json();
      if (j.error) {
        setMessages(p => [...p, { role: 'assistant', text: `Error: ${j.error}` }]);
      } else {
        setMessages(p => [...p, { role: 'assistant', text: j.content || 'No response.' }]);
      }
    } catch (e) {
      setMessages(p => [...p, { role: 'assistant', text: `Error: ${e.message}` }]);
    } finally {
      setLoading(false);
    }
  }, [messages, buildContext]);

  const downloadReport = useCallback(async () => {
    try {
      const res = await fetch(`${API}/report/relocation-pdf`);
      if (!res.ok) {
        const err = await res.json();
        alert(err.detail || 'Run optimization first');
        return;
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a'); a.href = url;
      a.download = `locats_relocation_order.pdf`; a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      alert('Error: ' + e.message);
    }
  }, []);

  return (
    <div className="chat-panel">
      <div style={{ padding: '20px 20px 0', borderBottom: '1px solid #E2E8F0' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
          <div style={{ width: 36, height: 36, borderRadius: 10, background: 'linear-gradient(135deg, #16A34A, #14B8A6)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2"><path d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"/></svg>
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 15, fontWeight: 700 }}>Disaster Management Assistant</div>
            <div style={{ fontSize: 11, color: '#94A3B8' }}>Powered by LocaTS data + Groq AI</div>
          </div>
          <button className="btn btn-secondary btn-sm" onClick={downloadReport} style={{ fontSize: 11, padding: '4px 10px' }}>
            Download Report
          </button>
        </div>
      </div>
      <div className="chat-messages">
        {messages.length === 0 && (
          <div style={{ textAlign: 'center', padding: '50px 20px', color: '#94A3B8' }}>
            <div style={{ fontSize: 15, fontWeight: 600, color: '#475569', marginBottom: 8 }}>Ask about Chamoli district</div>
            <div style={{ fontSize: 13, marginBottom: 24, maxWidth: 380, margin: '0 auto 24px' }}>I can help with evacuation plans, hazard zones, shelter capacity, and disaster preparedness.</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxWidth: 360, margin: '0 auto' }}>
              {['Is there a flood risk today?','Which villages need evacuation?','How many shelters are available?','What should I do in an emergency?'].map((s, i) => (
                <button key={i} className="btn btn-secondary btn-sm" style={{ justifyContent: 'flex-start' }} onClick={() => send(s)}>{s}</button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`chat-msg ${m.role}`}>
            <div className={`chat-avatar ${m.role === 'user' ? 'human' : 'ai'}`}>{m.role === 'user' ? 'U' : 'AI'}</div>
            <div className="chat-bubble" style={{ whiteSpace: 'pre-wrap' }}>{m.text}</div>
          </div>
        ))}
        {loading && <div className="chat-msg assistant"><div className="chat-avatar ai">AI</div><div className="chat-bubble" style={{ color: '#94A3B8' }}>Thinking...</div></div>}
        <div ref={endRef} />
      </div>
      <div className="chat-input-area">
        <input className="chat-input" value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(input); } }} placeholder="Ask about flood zones, evacuation, shelters..." disabled={loading} />
        <button className="btn btn-primary btn-sm" onClick={() => send(input)} disabled={loading || !input.trim()}>Send</button>
      </div>
    </div>
  );
}
