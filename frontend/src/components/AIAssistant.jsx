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

    const shelterNames = [];
    if (result?.assignments) {
      result.assignments.slice(0, 20).forEach(a => {
        shelterNames.push(`${a.shelter_id}: ${a.people_assigned} people assigned, ${a.distance_km}km`);
      });
    }

    return `You are LocaTS AI Assistant — a disaster management assistant for Chamoli district, Uttarakhand, India.

STRICT RULES — YOU MUST FOLLOW THESE:
1. ONLY answer questions about: LocaTS system, disaster management, Chamoli district hazards, evacuation planning, shelter capacity, relocation plans, hazard zones, rainfall data, family reunification, IVR helpline, and this dashboard's data.
2. NEVER answer questions about: politics, prime minister, celebrities, sports, general knowledge, coding, math, history, geography outside Chamoli, or any topic unrelated to disaster management.
3. If asked something outside your scope, respond: "I can only assist with disaster management information for Chamoli district. Please ask about hazard zones, evacuation plans, shelter capacity, or system features."
4. Use ONLY the data provided below. Do not make up numbers or facts.
5. Be concise. Focus on actionable insights for disaster response officials.

DISTRICT: Chamoli, Uttarakhand (Seismic Zone IV, elevation 1300-3300m)
POPULATION: ${cap.total_population?.toLocaleString()||'N/A'} (Census 2011 + buffer)
SHELTERS: ${cap.active_shelters||0} active with ${(cap.total_beds_available||0).toLocaleString()} total beds
HAZARD ZONES: ${zones.length} active (${Object.entries(zones.reduce((a,z)=>{a[z.type]=(a[z.type]||0)+1;return a},{})).map(([k,v])=>`${k}:${v}`).join(', ')||'none'})
ALERTS: ${Object.entries(alerts).map(([k,v])=>`${k}:${v}`).join(', ')||'none computed'}
DATA SOURCES: OpenStreetMap (ODbL), NDMA/Bhuvan hazard maps, IMD rainfall, Census 2011

${result?`LATEST OPTIMIZATION RESULTS:
- Total relocated: ${result.total_people_relocated?.toLocaleString()||0}
- People unmet (need more shelter): ${result.total_people_unmet?.toLocaleString()||0}
- Plan feasible: ${result.is_feasible ? 'Yes — all people assigned to shelters' : 'No — shelter capacity insufficient for all evacuees'}
- Solver method: ${result.used_fallback_heuristic ? 'Greedy heuristic (fast)' : 'OR-Tools optimal solver'}
- Solver time: ${result.solver_time_seconds||0}s
- Top assignments: ${shelterNames.join(' | ')}

WHAT INFEASIBLE MEANS: When the plan shows "infeasible", it means more people need evacuation than current shelter beds can hold. The system still assigns as many people as possible — the "unmet" count tells officials how many additional shelter places are needed.` : 'No optimization has been run yet. Go to Dashboard and click Run Optimization.'}

SYSTEM CAPABILITIES:
- Hazard Fusion: Combines static zones + live sensors + crowd reports using Bayesian scoring
- OR-Tools Optimization: Solves capacitated transportation problem (who goes where)
- Rolling-horizon Re-planning: Updates plan when roads/shelters change
- Social Vulnerability: Prioritizes elderly, disabled, children
- IVR Phone Helpline: Hindi/English voice menu for basic phone users
- Family Reunification: Track separated family members across shelters
- Historical Backtesting: Tests against 2021 Chamoli flash flood`;
  }, [data]);

  const GUARDRAIL_KEYWORDS = ['prime minister', 'president', 'modi', 'rahul gandhi', 'bollywood', 'cricket', 'stock market', 'bitcoin', 'recipe', 'movie', 'song', 'politics', 'election', 'who is the', 'what is the capital of', 'write a code', 'python', 'javascript'];

  const send = useCallback(async (text) => {
    if (!text.trim()) return;

    // Client-side guardrail check
    const lowerText = text.toLowerCase();
    const blocked = GUARDRAIL_KEYWORDS.some(kw => lowerText.includes(kw));
    if (blocked) {
      setMessages(p => [...p, { role: 'user', text }, { role: 'assistant', text: 'I can only assist with disaster management information for Chamoli district. Please ask about hazard zones, evacuation plans, shelter capacity, or system features.' }]);
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
      const a = document.createElement('a');
      a.href = url;
      a.download = `locats_relocation_order.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      alert('Error downloading report: ' + e.message);
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
            <div style={{ fontSize: 11, color: '#94A3B8' }}>Answers only from LocaTS data and disaster knowledge</div>
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
            <div style={{ fontSize: 13, marginBottom: 24, maxWidth: 380, margin: '0 auto 24px' }}>I can explain evacuation plans, hazard scores, shelter capacity, and system features.</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxWidth: 360, margin: '0 auto' }}>
              {['What is the current evacuation status?','Why is the plan infeasible?','How does hazard fusion work?','Which villages are at highest risk?'].map((s, i) => (
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
        <input className="chat-input" value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(input); } }} placeholder="Ask about evacuation, hazards, shelters..." disabled={loading} />
        <button className="btn btn-primary btn-sm" onClick={() => send(input)} disabled={loading || !input.trim()}>Send</button>
      </div>
    </div>
  );
}
