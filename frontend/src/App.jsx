import React, { useState, useEffect, useCallback, lazy, Suspense, startTransition } from 'react';
import { AuthProvider, useAuth } from './auth/AuthContext';
import { useSSE } from './hooks/useSSE';
import LoginPage from './auth/LoginPage';
import Dashboard from './components/Dashboard';
import IVRDemo from './components/IVRDemo';
import FamilySearch from './components/FamilySearch';
import AIAssistant from './components/AIAssistant';
import FeatureShowcase from './components/FeatureShowcase';
import MultiDistrict from './components/MultiDistrict';
import './App.css';

const CitizenPortal = lazy(() => import('./components/CitizenPortal'));
const AuditVerify = lazy(() => import('./components/AuditVerify'));
const WhatsAppBot = lazy(() => import('./components/WhatsAppBot'));
const SatelliteMonitor = lazy(() => import('./components/SatelliteMonitor'));

const API = '/api';

const NAV_ITEMS = [
  { id: 'dashboard', label: 'Command Overview', icon: 'M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z', roles: ['admin', 'operator', 'viewer', 'citizen'] },
  { id: 'analysis', label: 'Optimization Console', icon: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z', roles: ['admin', 'operator'] },
  { id: 'shelters', label: 'Shelter Management', icon: 'M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4', roles: ['admin', 'operator'] },
  { id: 'reports', label: 'Crowd Reports', icon: 'M11 5.882V19.24a1.76 1.76 0 01-3.417.592l-2.147-6.15M18 13a3 3 0 100-6M5.436 13.683A4.001 4.001 0 017 6h1.832c4.1 0 7.625-1.234 9.168-3v14c-1.543-1.766-5.067-3-9.168-3H7a3.988 3.988 0 01-1.564-.317z', roles: ['admin', 'operator'] },
  { id: 'ivr', label: 'Phone / IVR', icon: 'M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z', roles: ['admin', 'operator'] },
  { id: 'whatsapp', label: 'WhatsApp Bot', icon: 'M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z', roles: ['admin', 'operator'] },
  { id: 'satellite', label: 'Satellite Monitor', icon: 'M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z', roles: ['admin', 'operator'] },
  { id: 'family', label: 'Family Reunification', icon: 'M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z', roles: ['admin', 'operator', 'viewer', 'citizen'] },
  { id: 'ai', label: 'AI Assistant', icon: 'M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z', roles: ['admin', 'operator', 'viewer', 'citizen'] },
  { id: 'audit', label: 'Audit Log', icon: 'M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z', roles: ['admin'] },
  { id: 'users', label: 'User Management', icon: 'M12 4.354a4 4 0 110 7.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z', roles: ['admin'] },
  { id: 'multidistrict', label: 'Multi-District', icon: 'M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z', roles: ['admin', 'operator'], badge: { text: '3', bg: '#7C3AED', color: '#fff' } },
  { id: 'features', label: 'Feature Showcase', icon: 'M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z', roles: ['admin', 'operator', 'viewer', 'citizen'], badge: { text: '32', bg: '#16A34A', color: '#fff' } },
];

function LandingPage() {
  const [mode, setMode] = useState('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState('');
  const [resetToken, setResetToken] = useState('');
  const [resetCode, setResetCode] = useState('');
  const [debugCode, setDebugCode] = useState('');
  const [newPass, setNewPass] = useState('');
  const [confirmPass, setConfirmPass] = useState('');
  const { login, signup } = useAuth();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(''); setSuccess(''); setLoading(true);
    try {
      if (mode === 'login') {
        await login(email, password);
        // React will re-render — AppContent sees user set and routes accordingly
      } else {
        await signup(email, password, name);
        setSuccess('Account created successfully! Welcome to LocaTS.');
      }
    } catch (err) { setError(err.message); }
    finally { setLoading(false); }
  };

  const handleForgot = async (e) => {
    e.preventDefault();
    setError(''); setSuccess(''); setLoading(true);
    try {
      const res = await fetch(`${API}/auth/forgot-password`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed.');
      setResetToken(data._debug_token || '');
      setDebugCode(data._debug_code || '');
      setSuccess('Reset code sent! Check your email.');
      setMode('reset');
    } catch (err) { setError(err.message); }
    finally { setLoading(false); }
  };

  const handleReset = async (e) => {
    e.preventDefault();
    setError(''); setSuccess(''); setLoading(true);
    try {
      if (newPass !== confirmPass) throw new Error('Passwords do not match.');
      if (newPass.length < 6) throw new Error('Min 6 characters.');
      const res = await fetch(`${API}/auth/reset-password`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: resetToken, code: resetCode, new_password: newPass }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed.');
      setSuccess('Password reset! You can now sign in.');
      setMode('login'); setPassword('');
    } catch (err) { setError(err.message); }
    finally { setLoading(false); }
  };

  return (
    <div style={{ minHeight: '100vh', background: 'linear-gradient(180deg, #F0F9F4 0%, #ECFDF5 50%, #F0FDF4 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: 'Inter, sans-serif', position: 'relative', overflow: 'hidden' }}>
      {/* Floating background orbs */}
      <div className="animate-float" style={{ position: 'absolute', top: '10%', left: '8%', width: 180, height: 180, borderRadius: '50%', background: 'radial-gradient(circle, rgba(22,163,74,0.08) 0%, transparent 70%)', pointerEvents: 'none' }} />
      <div className="animate-float" style={{ position: 'absolute', bottom: '15%', right: '10%', width: 240, height: 240, borderRadius: '50%', background: 'radial-gradient(circle, rgba(13,148,136,0.06) 0%, transparent 70%)', pointerEvents: 'none', animationDelay: '1.5s' }} />

      <div style={{ textAlign: 'center', maxWidth: 440, width: '100%', padding: '0 20px', position: 'relative', zIndex: 1 }}>
        {/* Logo */}
        <div style={{ marginBottom: 28 }}>
          <div className="animate-glow" style={{ width: 64, height: 64, borderRadius: 16, background: 'linear-gradient(135deg, #16A34A, #0D9488)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 16px', fontWeight: 800, fontSize: 28, color: '#fff', boxShadow: '0 8px 32px rgba(22,163,74,0.3)' }}>L</div>
          <h1 style={{ fontSize: 28, fontWeight: 800, color: '#111827', marginBottom: 4, letterSpacing: -1 }}>
            <span className="gradient-text">LocaTS</span>
          </h1>
          <p style={{ fontSize: 13, color: '#94A3B8', fontWeight: 500 }}>Intelligent Disaster Relocation Planning</p>
        </div>

        {/* Auth Card */}
        <div className="animate-fade-in-up" style={{ background: '#fff', borderRadius: 16, border: '1px solid #E2E8F0', padding: 32, boxShadow: '0 4px 20px rgba(0,0,0,0.06)' }}>
          {/* Tabs */}
          <div style={{ display: 'flex', gap: 4, background: '#F6FAFD', borderRadius: 10, padding: 4, marginBottom: 24, border: '1px solid #E2E8F0' }}>
            <button onClick={() => { setMode('login'); setError(''); setSuccess(''); }}
              style={{ flex: 1, padding: '9px 0', border: 'none', borderRadius: 8, fontFamily: 'Inter, sans-serif', fontSize: 13, fontWeight: 600, cursor: 'pointer', background: mode === 'login' ? '#fff' : 'transparent', color: mode === 'login' ? '#16A34A' : '#94A3B8', boxShadow: mode === 'login' ? '0 1px 2px rgba(0,0,0,0.06)' : 'none', transition: 'all 0.15s' }}>Sign In</button>
            <button onClick={() => { setMode('signup'); setError(''); setSuccess(''); }}
              style={{ flex: 1, padding: '9px 0', border: 'none', borderRadius: 8, fontFamily: 'Inter, sans-serif', fontSize: 13, fontWeight: 600, cursor: 'pointer', background: mode === 'signup' ? '#fff' : 'transparent', color: mode === 'signup' ? '#16A34A' : '#94A3B8', boxShadow: mode === 'signup' ? '0 1px 2px rgba(0,0,0,0.06)' : 'none', transition: 'all 0.15s' }}>Create Account</button>
          </div>

          {error && <div style={{ padding: '10px 14px', background: '#FEF2F2', border: '1px solid rgba(239,68,68,0.15)', borderRadius: 8, fontSize: 13, color: '#EF4444', marginBottom: 16 }}>{error}</div>}
          {success && <div style={{ padding: '10px 14px', background: '#F0FDF4', border: '1px solid rgba(34,197,94,0.15)', borderRadius: 8, fontSize: 13, color: '#16A34A', marginBottom: 16 }}>{success}</div>}

          <form onSubmit={handleSubmit}>
            {mode === 'signup' && (
              <div style={{ marginBottom: 14 }}>
                <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#475569', marginBottom: 6 }}>Full Name</label>
                <input type="text" value={name} onChange={e => setName(e.target.value)} placeholder="Enter your full name" required
                  style={{ width: '100%', padding: '10px 14px', background: '#F6FAFD', border: '1px solid #E2E8F0', borderRadius: 10, color: '#172B4D', fontFamily: 'Inter, sans-serif', fontSize: 13 }} />
              </div>
            )}
            <div style={{ marginBottom: 14 }}>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#475569', marginBottom: 6 }}>Email</label>
              <input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="you@example.com" required
                style={{ width: '100%', padding: '10px 14px', background: '#F6FAFD', border: '1px solid #E2E8F0', borderRadius: 10, color: '#172B4D', fontFamily: 'Inter, sans-serif', fontSize: 13 }} />
            </div>
            <div style={{ marginBottom: 20 }}>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#475569', marginBottom: 6 }}>Password</label>
              <input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="Minimum 6 characters" required minLength={6}
                style={{ width: '100%', padding: '10px 14px', background: '#F6FAFD', border: '1px solid #E2E8F0', borderRadius: 10, color: '#172B4D', fontFamily: 'Inter, sans-serif', fontSize: 13 }} />
            </div>
            <button type="submit" disabled={loading} style={{ width: '100%', padding: '11px 0', background: 'linear-gradient(135deg, #16A34A, #0D9488)', color: '#fff', border: 'none', borderRadius: 10, fontFamily: 'Inter, sans-serif', fontSize: 14, fontWeight: 600, cursor: loading ? 'wait' : 'pointer', boxShadow: '0 2px 8px rgba(22,163,74,0.3)', opacity: loading ? 0.7 : 1, transition: 'all 0.15s' }}>
              {loading ? 'Please wait...' : mode === 'login' ? 'Sign In' : 'Create Account'}
            </button>
          </form>

          {mode === 'login' && (
            <div style={{ marginTop: 16, textAlign: 'center' }}>
              <button onClick={() => { setMode('forgot'); setError(''); setSuccess(''); setDebugCode(''); }}
                style={{ background: 'none', border: 'none', color: '#2563EB', fontSize: 12, cursor: 'pointer', fontWeight: 600, fontFamily: 'Inter, sans-serif' }}>
                Forgot password?
              </button>
            </div>
          )}
          {mode === 'signup' && (
            <div style={{ marginTop: 16, textAlign: 'center', fontSize: 11, color: '#94A3B8', lineHeight: 1.5 }}>
              New accounts start as citizens. Admin can upgrade your role.
            </div>
          )}

          {/* Forgot Password Form */}
          {mode === 'forgot' && (
            <div style={{ marginTop: 20 }}>
              <button onClick={() => { setMode('login'); setError(''); setSuccess(''); }} style={{ background: 'none', border: 'none', color: '#94A3B8', fontSize: 12, cursor: 'pointer', padding: 0, marginBottom: 16 }}>&larr; Back to Sign In</button>
              <form onSubmit={handleForgot}>
                <div style={{ marginBottom: 16 }}>
                  <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#475569', marginBottom: 6 }}>Email Address</label>
                  <input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="you@example.com" required
                    style={{ width: '100%', padding: '10px 14px', background: '#F6FAFD', border: '1px solid #E2E8F0', borderRadius: 10, fontSize: 13 }} />
                </div>
                <button type="submit" disabled={loading} style={{ width: '100%', padding: '11px 0', background: '#2563EB', color: '#fff', border: 'none', borderRadius: 10, fontSize: 14, fontWeight: 600, cursor: loading ? 'wait' : 'pointer', opacity: loading ? 0.7 : 1 }}>
                  {loading ? 'Sending...' : 'Send Reset Code'}
                </button>
              </form>
            </div>
          )}

          {/* Reset Password Form */}
          {mode === 'reset' && (
            <div style={{ marginTop: 20 }}>
              <button onClick={() => { setMode('forgot'); setError(''); setSuccess(''); }} style={{ background: 'none', border: 'none', color: '#94A3B8', fontSize: 12, cursor: 'pointer', padding: 0, marginBottom: 16 }}>&larr; Back</button>
              {debugCode && (
                <div style={{ padding: '8px 12px', background: '#EFF6FF', border: '1px solid #BFDBFE', borderRadius: 8, fontSize: 12, color: '#1E40AF', marginBottom: 14, fontFamily: 'monospace' }}>
                  <strong>Demo Code:</strong> {debugCode}
                </div>
              )}
              <form onSubmit={handleReset}>
                <div style={{ marginBottom: 12 }}>
                  <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#475569', marginBottom: 6 }}>Reset Code</label>
                  <input type="text" value={resetCode} onChange={e => setResetCode(e.target.value)} placeholder="6-digit code" required maxLength={6}
                    style={{ width: '100%', padding: '10px 14px', background: '#F6FAFD', border: '1px solid #E2E8F0', borderRadius: 10, fontSize: 18, fontFamily: 'monospace', letterSpacing: 4, textAlign: 'center' }} />
                </div>
                <div style={{ marginBottom: 12 }}>
                  <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#475569', marginBottom: 6 }}>New Password</label>
                  <input type="password" value={newPass} onChange={e => setNewPass(e.target.value)} placeholder="Min 6 characters" required minLength={6}
                    style={{ width: '100%', padding: '10px 14px', background: '#F6FAFD', border: '1px solid #E2E8F0', borderRadius: 10, fontSize: 13 }} />
                </div>
                <div style={{ marginBottom: 16 }}>
                  <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#475569', marginBottom: 6 }}>Confirm Password</label>
                  <input type="password" value={confirmPass} onChange={e => setConfirmPass(e.target.value)} placeholder="Re-enter password" required minLength={6}
                    style={{ width: '100%', padding: '10px 14px', background: '#F6FAFD', border: '1px solid #E2E8F0', borderRadius: 10, fontSize: 13 }} />
                </div>
                <button type="submit" disabled={loading} style={{ width: '100%', padding: '11px 0', background: '#16A34A', color: '#fff', border: 'none', borderRadius: 10, fontSize: 14, fontWeight: 600, cursor: loading ? 'wait' : 'pointer', opacity: loading ? 0.7 : 1 }}>
                  {loading ? 'Resetting...' : 'Reset Password'}
                </button>
              </form>
            </div>
          )}
        </div>

        <div style={{ marginTop: 20, fontSize: 11, color: '#9CA3AF' }}>
          SIH26191 — Ministry of Home Affairs, Disaster Management
        </div>
      </div>
    </div>
  );
}

/* ---- Shelter Management Section ---- */
function ShelterManagement({ data }) {
  const shelters = data?.capacity_summary?.shelters || [];
  const [forecasts, setForecasts] = useState(null);

  useEffect(() => {
    fetch(`${API}/resources/shortfall-forecast`).then(r => r.json()).then(setForecasts).catch(() => {});
  }, []);

  return (
    <div style={{ padding: 28, maxWidth: 1000, overflow: 'auto', height: '100%' }}>
      <h2 style={{ fontSize: 22, fontWeight: 800, marginBottom: 4 }}>Shelter Management</h2>
      <p style={{ fontSize: 13, color: '#94A3B8', marginBottom: 24 }}>Capacity, occupancy, and resource shortfall forecasting.</p>

      {forecasts?.forecasts && (
        <div className="card" style={{ marginBottom: 20 }}>
          <div className="card-header">Resource Shortfall Forecast</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 12 }}>
            {forecasts.forecasts.map(f => (
              <div key={f.shelter_id} style={{ padding: 14, background: f.status === 'critical' ? '#FEF2F2' : f.status === 'warning' ? '#FFFBEB' : '#F0FDF4', borderRadius: 10, border: `1px solid ${f.status === 'critical' ? '#FCA5A5' : f.status === 'warning' ? '#FDE68A' : '#BBF7D0'}` }}>
                <div style={{ fontSize: 13, fontWeight: 700, color: '#111827', marginBottom: 4 }}>{f.shelter_name}</div>
                <div style={{ fontSize: 12, color: '#6B7280', marginBottom: 8 }}>{f.district} | {f.beds_occupied.toLocaleString()} / {f.bed_capacity.toLocaleString()} occupied</div>
                <div style={{ display: 'flex', gap: 16, fontSize: 12 }}>
                  <div><span style={{ color: '#94A3B8' }}>Hours to full:</span> <span style={{ fontWeight: 700, color: f.status === 'critical' ? '#DC2626' : f.status === 'warning' ? '#F59E0B' : '#16A34A' }}>{f.estimated_hours_to_full}h</span></div>
                  <div><span style={{ color: '#94A3B8' }}>Water:</span> <span style={{ fontWeight: 700 }}>{f.water_hours_remaining}h</span></div>
                </div>
                <div style={{ marginTop: 6, height: 4, background: '#E5E7EB', borderRadius: 2, overflow: 'hidden' }}>
                  <div style={{ width: `${f.occupancy_pct}%`, height: '100%', background: f.status === 'critical' ? '#DC2626' : f.status === 'warning' ? '#F59E0B' : '#22C55E', borderRadius: 2 }} />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* ---- Crowd Reports Queue ---- */
function CrowdReportsQueue() {
  const [reports, setReports] = useState([]);
  const [confidences, setConfidences] = useState([]);

  useEffect(() => {
    fetch(`${API}/dashboard`).then(r => r.json()).then(d => {
      setReports(d.crowd_reports || []);
      setConfidences(Object.entries(d.hazard_confidences || {}).map(([k, v]) => ({ key: k, ...v })).slice(0, 30));
    }).catch(() => {});
  }, []);

  const hazardIcon = (type) => ({ flood: '🌊', landslide: '🏔️', seismic: '🌍', fire: '🔥' }[type] || '⚠️');
  const severityColor = (sev) => sev >= 0.7 ? '#DC2626' : sev >= 0.4 ? '#F59E0B' : '#22C55E';

  return (
    <div style={{ padding: 28, maxWidth: 900, overflow: 'auto', height: '100%' }}>
      <h2 style={{ fontSize: 22, fontWeight: 800, marginBottom: 4 }}>Crowd Reports Queue</h2>
      <p style={{ fontSize: 13, color: '#94A3B8', marginBottom: 24 }}>Incoming hazard reports from citizens, pending corroboration.</p>

      {/* Actual crowd reports */}
      <div className="card" style={{ marginBottom: 20 }}>
        <div style={{ padding: '12px 16px', background: '#F6FAFD', borderBottom: '1px solid #E2E8F0', fontWeight: 700, fontSize: 13, color: '#374151' }}>
          Citizen Reports ({reports.length})
        </div>
        {reports.length === 0 ? (
          <div style={{ padding: 40, textAlign: 'center', color: '#94A3B8' }}>
            <div style={{ fontSize: 32, marginBottom: 8 }}>📡</div>
            <div>No crowd reports yet.</div>
            <div style={{ fontSize: 12, marginTop: 4 }}>Reports appear here when citizens submit hazard observations.</div>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, padding: 12 }}>
            {reports.slice().reverse().slice(0, 25).map((r, i) => (
              <div key={r.id || i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 14px', background: '#F9FAFB', borderRadius: 8, border: '1px solid #F3F4F6' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{ fontSize: 18 }}>{hazardIcon(r.hazard_type)}</span>
                  <div>
                    <div style={{ fontSize: 12, fontWeight: 600, color: '#374151' }}>
                      {r.hazard_type?.charAt(0).toUpperCase() + r.hazard_type?.slice(1)} Report
                      <span style={{ fontWeight: 400, color: '#94A3B8', marginLeft: 8 }}>#{r.id}</span>
                    </div>
                    <div style={{ fontSize: 11, color: '#94A3B8', marginTop: 2 }}>
                      {r.description || 'No description'}
                      {r.reporter_id && <span style={{ marginLeft: 8 }}>from {r.reporter_id}</span>}
                    </div>
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <div style={{ width: 50, height: 6, background: '#E5E7EB', borderRadius: 3, overflow: 'hidden' }}>
                    <div style={{ width: `${(r.severity_estimate || 0) * 100}%`, height: '100%', background: severityColor(r.severity_estimate || 0), borderRadius: 3 }} />
                  </div>
                  <span style={{ fontSize: 11, fontWeight: 700, color: severityColor(r.severity_estimate || 0) }}>{((r.severity_estimate || 0) * 100).toFixed(0)}%</span>
                  <span style={{ fontSize: 10, color: '#94A3B8' }}>{r.timestamp?.split('T')[0] || ''}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Hazard fusion confidences as context */}
      {confidences.length > 0 && (
        <div className="card">
          <div style={{ padding: '12px 16px', background: '#F6FAFD', borderBottom: '1px solid #E2E8F0', fontWeight: 700, fontSize: 13, color: '#374151' }}>
            Hazard Fusion Scores (auto-generated from reports + sensors)
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, padding: 12 }}>
            {confidences.map((c, i) => (
              <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 14px', background: '#F9FAFB', borderRadius: 8, border: '1px solid #F3F4F6' }}>
                <div>
                  <span style={{ fontSize: 12, fontWeight: 600, color: '#374151' }}>{c.key?.split(':')[0]}</span>
                  <span style={{ fontSize: 11, color: '#94A3B8', marginLeft: 8 }}>{c.key?.split(':')[1]}</span>
                </div>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <span style={{ fontSize: 11, fontWeight: 700, color: '#374151' }}>{(c.confidence * 100).toFixed(0)}%</span>
                  <span className={`badge badge-${c.alert_level === 'normal' ? 'safe' : c.alert_level === 'advisory' ? 'warn' : 'danger'}`}>{c.alert_level}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* ---- Audit Log ---- */
function AuditLog() {
  const [orders, setOrders] = useState([]);
  const [verifyId, setVerifyId] = useState('');
  const [verifyResult, setVerifyResult] = useState(null);

  useEffect(() => { fetch(`${API}/orders`).then(r => r.json()).then(d => setOrders(d.orders || [])).catch(() => {}); }, []);

  const verify = async () => {
    if (!verifyId.trim()) return;
    try {
      const res = await fetch(`${API}/audit/verify/${verifyId}`);
      setVerifyResult(await res.json());
    } catch (e) { setVerifyResult({ verification_result: 'Verification failed.' }); }
  };

  return (
    <div style={{ padding: 28, maxWidth: 800, overflow: 'auto', height: '100%' }}>
      <h2 style={{ fontSize: 22, fontWeight: 800, marginBottom: 4 }}>Audit Log</h2>
      <p style={{ fontSize: 13, color: '#94A3B8', marginBottom: 24 }}>Tamper-evident hash chain for all relocation orders.</p>

      <div className="card" style={{ marginBottom: 20 }}>
        <div className="card-header">Verify Order</div>
        <div style={{ display: 'flex', gap: 8 }}>
          <input value={verifyId} onChange={e => setVerifyId(e.target.value)} placeholder="Paste order ID..." style={{ flex: 1, padding: '10px 14px', borderRadius: 8, border: '1px solid #D1D5DB', fontSize: 13 }} />
          <button className="btn btn-primary btn-sm" onClick={verify}>Verify</button>
        </div>
        {verifyResult && (
          <div style={{ marginTop: 12, padding: 14, background: verifyResult.hash_match ? '#F0FDF4' : '#FEF2F2', borderRadius: 8, fontSize: 13 }}>
            <div style={{ fontWeight: 700, color: verifyResult.hash_match ? '#16A34A' : '#DC2626', marginBottom: 4 }}>{verifyResult.verification_result}</div>
            <div style={{ color: '#4B5563', lineHeight: 1.5 }}>{verifyResult.plain_explanation}</div>
          </div>
        )}
      </div>

      <div className="card">
        <div className="card-header">Issued Orders ({orders.length})</div>
        {orders.map((o, i) => (
          <div key={i} style={{ padding: '10px 14px', background: '#F9FAFB', borderRadius: 8, marginBottom: 6, border: '1px solid #F3F4F6', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <span style={{ fontSize: 13, fontWeight: 600, color: '#111827' }}>{o.order_id}</span>
              <span style={{ fontSize: 11, color: '#94A3B8', marginLeft: 8 }}>{o.issued_at?.split('T')[0]}</span>
            </div>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <span style={{ fontSize: 11, fontFamily: 'monospace', color: '#6B7280' }}>{o.audit_hash?.substring(0, 8)}...</span>
              <span className={`badge ${o.is_feasible ? 'badge-safe' : 'badge-danger'}`}>{o.total_relocated?.toLocaleString()}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ---- Relocation Analysis (Optimization Console) ---- */
function RelocationAnalysis({ data }) {
  const result = data?.latest_result;
  const cap = data?.capacity_summary || {};
  const totalPop = cap.total_population || 0;
  const totalBeds = cap.total_beds_available || 0;
  const ratio = totalPop > 0 ? (totalBeds / totalPop * 100).toFixed(1) : '0';
  const relocated = result?.total_people_relocated || 0;
  const unmet = result?.total_people_unmet || 0;

  return (
    <div style={{ padding: 28, maxWidth: 840, overflow: 'auto', height: '100%' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 28 }}>
        <div><h2 style={{ fontSize: 22, fontWeight: 800, marginBottom: 4 }}>Optimization Console</h2><p style={{ fontSize: 13, color: '#94A3B8' }}>OR-Tools solver, what-if scenarios, and explainability.</p></div>
        {result && (
          <button className="btn btn-primary" onClick={async () => { try { const res = await fetch('/api/report/relocation-pdf'); if (!res.ok) return; const blob = await res.blob(); const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = 'locats_relocation_order.pdf'; a.click(); URL.revokeObjectURL(url); } catch(e) {} }} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>
            PDF Report
          </button>
        )}
      </div>
      {!result ? (
        <div className="empty-state" style={{ borderRadius: 16, border: '1px solid #E2E8F0', padding: 60, background: '#fff' }}><h4>No Optimization Results Yet</h4><p>Go to Command Overview and click "Run Optimization".</p></div>
      ) : (<>
        <div className={`feasibility-panel ${!result.is_feasible ? 'infeasible' : ''}`}>
          <div className="feasibility-header">
            <div>
              <div style={{ fontSize: 16, fontWeight: 700, color: result.is_feasible ? '#16A34A' : '#EF4444' }}>{result.is_feasible ? 'Plan Feasible' : 'Plan Infeasible'}</div>
              <div style={{ fontSize: 12, color: '#94A3B8', marginTop: 2 }}>{result.is_feasible ? 'All habitations can be evacuated.' : 'Shelter capacity insufficient for all evacuees.'}</div>
            </div>
            <div className={`badge ${result.is_feasible ? 'badge-safe' : 'badge-danger'}`}>{result.is_feasible ? 'FEASIBLE' : 'INFEASIBLE'}</div>
          </div>
          <div className="feasibility-bar"><div className="feasibility-bar-fill" style={{ width: `${Math.min(100, (relocated / Math.max(totalPop, 1)) * 100)}%`, background: result.is_feasible ? '#22C55E' : '#EF4444' }} /></div>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 20 }}>
          {[{ l: 'Population', v: totalPop.toLocaleString(), c: '#172B4D' }, { l: 'Relocated', v: relocated.toLocaleString(), c: '#22C55E' }, { l: 'Unmet Need', v: unmet.toLocaleString(), c: unmet > 0 ? '#EF4444' : '#22C55E' }, { l: 'Bed Ratio', v: `${ratio}%`, c: parseFloat(ratio) > 50 ? '#22C55E' : '#EF4444' }].map((m, i) => (
            <div key={i} className="card" style={{ textAlign: 'center', padding: '18px 12px' }}><div className="stat-value" style={{ fontSize: 26, color: m.c }}>{m.v}</div><div className="stat-label">{m.l}</div></div>
          ))}
        </div>
      </>)}
    </div>
  );
}

/* ---- User Management (Admin only) ---- */
function UserManagement({ token }) {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [updatingId, setUpdatingId] = useState(null);
  const [fetchError, setFetchError] = useState(null);
  const [serverNote, setServerNote] = useState(null);

  const fetchUsers = useCallback(async () => {
    setFetchError(null);
    setServerNote(null);
    try {
      const res = await fetch(`${API}/auth/users`, { headers: { 'Authorization': `Bearer ${token}` } });
      if (res.status === 403) { setFetchError('You do not have admin access to view users.'); setUsers([]); return; }
      if (!res.ok) { setFetchError(`Failed to load users (HTTP ${res.status})`); setUsers([]); return; }
      const data = await res.json();
      setUsers(data.users || []);
      if (data.note) setServerNote(data.note);
    } catch (e) { setFetchError('Could not connect to server.'); }
    finally { setLoading(false); }
  }, [token]);

  useEffect(() => { fetchUsers(); }, [fetchUsers]);

  const updateRole = async (userId, newRole) => {
    setUpdatingId(userId);
    try {
      await fetch(`${API}/auth/users/${userId}/role?role=${newRole}`, {
        method: 'PUT',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      fetchUsers();
    } catch (e) {}
    finally { setUpdatingId(null); }
  };

  const roleColors = { admin: '#2563EB', operator: '#16A34A', citizen: '#F59E0B', viewer: '#6B7280' };
  const roleBgs = { admin: '#EFF6FF', operator: '#F0FDF4', citizen: '#FFFBEB', viewer: '#F9FAFB' };

  return (
    <div style={{ padding: 28, maxWidth: 900, overflow: 'auto', height: '100%' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <div>
          <h2 style={{ fontSize: 22, fontWeight: 800, marginBottom: 4 }}>User Management</h2>
          <p style={{ fontSize: 13, color: '#94A3B8' }}>Approve registrations and assign roles to citizens.</p>
        </div>
        <button className="btn btn-secondary btn-sm" onClick={fetchUsers} disabled={loading}>
          {loading ? 'Loading...' : 'Refresh'}
        </button>
      </div>

      {/* Role summary */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 20, marginTop: 16 }}>
        {['admin', 'operator', 'citizen', 'viewer'].map(r => (
          <div key={r} style={{ flex: 1, padding: '12px 14px', background: roleBgs[r], borderRadius: 10, border: `1px solid ${roleColors[r]}20`, textAlign: 'center' }}>
            <div style={{ fontSize: 22, fontWeight: 800, color: roleColors[r] }}>{users.filter(u => u.role === r).length}</div>
            <div style={{ fontSize: 10, fontWeight: 600, color: roleColors[r], textTransform: 'uppercase', letterSpacing: 0.5 }}>{r}s</div>
          </div>
        ))}
      </div>

      {fetchError && (
        <div style={{ padding: '12px 16px', background: '#FEF2F2', border: '1px solid #FECACA', borderRadius: 10, marginBottom: 16, color: '#991B1B', fontSize: 13 }}>
          {fetchError}
        </div>
      )}
      {serverNote && !fetchError && (
        <div style={{ padding: '12px 16px', background: '#FFFBEB', border: '1px solid #FDE68A', borderRadius: 10, marginBottom: 16, color: '#92400E', fontSize: 13, display: 'flex', alignItems: 'center', gap: 8 }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#D97706" strokeWidth="2"><path d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>
          <div>
            <div style={{ fontWeight: 600, marginBottom: 2 }}>{serverNote}</div>
            <div style={{ fontSize: 12, opacity: 0.8 }}>This may require running the SQL setup in your Supabase dashboard.</div>
          </div>
        </div>
      )}
      {loading ? (
        <div style={{ padding: 40, textAlign: 'center', color: '#94A3B8' }}>Loading users...</div>
      ) : (
        <div className="card" style={{ overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead><tr style={{ borderBottom: '1px solid #E2E8F0', background: '#F6FAFD' }}>
              {['Email', 'Name', 'Current Role', 'Assign Role'].map(h => (
                <th key={h} style={{ padding: '12px 16px', textAlign: 'left', fontWeight: 600, color: '#475569', fontSize: 11, textTransform: 'uppercase', letterSpacing: 1 }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {users.map(u => (
                <tr key={u.id} style={{ borderBottom: '1px solid #F1F5F9', background: u.role === 'citizen' ? '#FFFBEB08' : 'transparent' }}>
                  <td style={{ padding: '12px 16px', fontWeight: 500, color: '#1F2937' }}>{u.email}</td>
                  <td style={{ padding: '12px 16px', color: '#475569' }}>{u.full_name || <span style={{ color: '#D1D5DB' }}>—</span>}</td>
                  <td style={{ padding: '12px 16px' }}>
                    <span style={{ padding: '3px 10px', borderRadius: 20, fontSize: 11, fontWeight: 700, background: roleBgs[u.role] || '#F9FAFB', color: roleColors[u.role] || '#6B7280', border: `1px solid ${roleColors[u.role] || '#6B7280'}20` }}>
                      {u.role}
                    </span>
                  </td>
                  <td style={{ padding: '12px 16px' }}>
                    <select
                      className="form-select"
                      value={u.role}
                      onChange={e => updateRole(u.id, e.target.value)}
                      disabled={updatingId === u.id}
                      style={{ padding: '6px 10px', fontSize: 12, borderRadius: 8, border: '1px solid #E2E8F0' }}
                    >
                      <option value="citizen">👤 Citizen</option>
                      <option value="operator">🔧 Operator</option>
                      <option value="admin">👑 Admin</option>
                      <option value="viewer">👁 Viewer</option>
                    </select>
                  </td>
                </tr>
              ))}
              {users.length === 0 && (
                <tr><td colSpan={4} style={{ padding: 40, textAlign: 'center', color: '#94A3B8' }}>
                  <div style={{ fontSize: 14, marginBottom: 4 }}>No registered users yet</div>
                  <div style={{ fontSize: 12 }}>Users will appear here after they create an account.</div>
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function ChangePasswordModal({ token, onClose }) {
  const [current, setCurrent] = useState('');
  const [newPass, setNewPass] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(''); setSuccess('');
    if (newPass !== confirm) { setError('New passwords do not match.'); return; }
    if (newPass.length < 6) { setError('New password must be at least 6 characters.'); return; }
    setLoading(true);
    try {
      const res = await fetch(`${API}/auth/change-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ current_password: current, new_password: newPass }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to change password.');
      setSuccess('Password changed successfully!');
      setCurrent(''); setNewPass(''); setConfirm('');
    } catch (err) { setError(err.message); }
    finally { setLoading(false); }
  };

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }} onClick={onClose}>
      <div style={{ background: '#fff', borderRadius: 16, padding: 28, width: '100%', maxWidth: 380, boxShadow: '0 8px 32px rgba(0,0,0,0.15)' }} onClick={e => e.stopPropagation()}>
        <h3 style={{ fontSize: 18, fontWeight: 700, marginBottom: 16, color: '#111827' }}>Change Password</h3>
        {error && <div style={{ padding: '8px 12px', background: '#FEF2F2', border: '1px solid #FECACA', borderRadius: 8, fontSize: 12, color: '#DC2626', marginBottom: 12 }}>{error}</div>}
        {success && <div style={{ padding: '8px 12px', background: '#F0FDF4', border: '1px solid #BBF7D0', borderRadius: 8, fontSize: 12, color: '#16A34A', marginBottom: 12 }}>{success}</div>}
        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: 12 }}>
            <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#475569', marginBottom: 4 }}>Current Password</label>
            <input type="password" value={current} onChange={e => setCurrent(e.target.value)} required
              style={{ width: '100%', padding: '9px 12px', border: '1px solid #E2E8F0', borderRadius: 8, fontSize: 13 }} />
          </div>
          <div style={{ marginBottom: 12 }}>
            <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#475569', marginBottom: 4 }}>New Password</label>
            <input type="password" value={newPass} onChange={e => setNewPass(e.target.value)} required minLength={6}
              style={{ width: '100%', padding: '9px 12px', border: '1px solid #E2E8F0', borderRadius: 8, fontSize: 13 }} />
          </div>
          <div style={{ marginBottom: 16 }}>
            <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#475569', marginBottom: 4 }}>Confirm New Password</label>
            <input type="password" value={confirm} onChange={e => setConfirm(e.target.value)} required minLength={6}
              style={{ width: '100%', padding: '9px 12px', border: '1px solid #E2E8F0', borderRadius: 8, fontSize: 13 }} />
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button type="button" onClick={onClose} style={{ flex: 1, padding: '9px 0', border: '1px solid #E2E8F0', borderRadius: 8, background: '#fff', fontSize: 13, fontWeight: 600, cursor: 'pointer' }}>Cancel</button>
            <button type="submit" disabled={loading} style={{ flex: 1, padding: '9px 0', border: 'none', borderRadius: 8, background: '#2563EB', color: '#fff', fontSize: 13, fontWeight: 600, cursor: loading ? 'wait' : 'pointer', opacity: loading ? 0.7 : 1 }}>{loading ? 'Saving...' : 'Change Password'}</button>
          </div>
        </form>
      </div>
    </div>
  );
}

function AppContent() {
  const { user, profile, loading, logout, token, role: authRole } = useAuth();
  const [dashboardData, setDashboardData] = useState(null);
  const [error, setError] = useState(null);
  const [optimizing, setOptimizing] = useState(false);
  const [activeTab, setActiveTab] = useState('dashboard');
  const [liveStatus, setLiveStatus] = useState(null);
  const [showChangePass, setShowChangePass] = useState(false);
  const [showUserMenu, setShowUserMenu] = useState(false);

  // Route-based portal selection
  const path = window.location.pathname;
  const isCitizen = path.startsWith('/citizen');
  const isAudit = path.startsWith('/audit');
  const isAdmin = path.startsWith('/admin');

  // fetchDashboard must be defined BEFORE useSSE references it
  const fetchDashboard = useCallback(async () => {
    try { const res = await fetch(`${API}/dashboard`); if (!res.ok) throw new Error(`HTTP ${res.status}`); setDashboardData(await res.json()); setError(null); } catch (err) { setError(err.message); }
  }, []);

  // SSE live updates — only on admin pages, not citizen
  const { connected: sseConnected, lastUpdate: sseLastUpdate, reconnecting } = useSSE(
    isAdmin ? '/api/sse/stream' : null,
    useCallback((data) => {
      setLiveStatus(data);
    }, [])
  );

  const triggerOptimization = useCallback(async () => {
    setOptimizing(true);
    try { await fetch(`${API}/optimize/solve`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ time_budget_seconds: 30.0 }) }); await fetchDashboard(); } catch (err) { setError(err.message); } finally { setOptimizing(false); }
  }, [fetchDashboard]);

  const reOptimize = useCallback(async () => {
    setOptimizing(true);
    try { await fetch(`${API}/optimize/re-solve`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ time_budget_seconds: 30.0 }) }); await fetchDashboard(); } catch (err) { setError(err.message); } finally { setOptimizing(false); }
  }, [fetchDashboard]);

  // Only fetch dashboard data when on admin page and logged in
  useEffect(() => {
    if (user && isAdmin && !loading) fetchDashboard();
  }, [user, isAdmin, loading, fetchDashboard]);

  // Listen for tab-switch events from child components
  useEffect(() => {
    const handler = (e) => { if (e.detail) setActiveTab(e.detail); };
    window.addEventListener('switchTab', handler);
    return () => window.removeEventListener('switchTab', handler);
  }, []);

  // Loading state
  if (loading) return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', background: '#F6FAFD' }}>
      <div style={{ textAlign: 'center' }}>
        <div style={{ width: 52, height: 52, borderRadius: 14, background: 'linear-gradient(135deg, #16A34A, #0D9488)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 16px', fontWeight: 800, fontSize: 22, color: '#fff' }}>L</div>
        <div style={{ fontSize: 14, color: '#94A3B8', fontWeight: 500 }}>Loading...</div>
      </div>
    </div>
  );

  // Not logged in — show landing page with login/signup
  // Also, if logged in user is on landing page, redirect based on role
  if (!user) {
    // If we have a token in localStorage, try to verify it (don't block UI)
    const savedToken = localStorage.getItem('locats_token');
    const savedRole = localStorage.getItem('locats_role');
    if (savedToken && savedRole && !localStorage.getItem('_auth_verifying')) {
      localStorage.setItem('_auth_verifying', '1');
      // Fire-and-forget: verify token, if valid the AuthContext will pick it up
      fetch(`${API}/auth/me`, { headers: { 'Authorization': `Bearer ${savedToken}` } })
        .then(r => r.ok ? r.json() : Promise.reject())
        .then(d => {
          // Token is valid — AuthContext will handle it on next render
          localStorage.removeItem('_auth_verifying');
        })
        .catch(() => {
          localStorage.removeItem('locats_token');
          localStorage.removeItem('locats_role');
          localStorage.removeItem('locats_user_email');
          localStorage.removeItem('_auth_verifying');
        });
    }
    return <LandingPage />;
  }

  // Logged in — determine role and route accordingly
  const role = authRole || profile?.role || 'citizen';

  // Citizens see the citizen portal directly (no redirect, no extra network call)
  if (role === 'citizen') {
    return (
      <div style={{ minHeight: '100vh', background: '#F0F9F4' }}>
        <Suspense fallback={<div style={{ padding: 40, textAlign: 'center', color: '#94A3B8' }}>Loading...</div>}>
          <CitizenPortal user={user} profile={profile} token={token} onLogout={logout} />
        </Suspense>
      </div>
    );
  }

  // Admin/operator portal — auth required
  const filteredNav = NAV_ITEMS.filter(item => item.roles.includes(role));
  const Icon = ({ path, size = 18 }) => <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d={path} /></svg>;

  return (
    <div className="app-layout">
      <header className="app-header">
        <div className="logo">
          <div className="logo-mark">L</div>
          <span className="logo-text">LocaTS</span>
          <span className="logo-sub">SIH26191</span>
        </div>
        <div className="header-right">
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 14px', background: '#EFF6FF', borderRadius: 20, border: '1px solid rgba(37,99,235,0.12)' }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#2563EB" strokeWidth="2"><path d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/></svg>
            <span style={{ fontSize: 12, fontWeight: 600, color: '#172B4D' }}>{user.email}</span>
          </div>
          <span className={`badge badge-${role === 'admin' ? 'info' : role === 'operator' ? 'safe' : 'warn'}`}>{role}</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '5px 12px', borderRadius: 20, background: sseConnected ? '#F0FDF4' : reconnecting ? '#FEF3C7' : '#FEF2F2', border: `1px solid ${sseConnected ? 'rgba(34,197,94,0.2)' : reconnecting ? 'rgba(245,158,11,0.2)' : 'rgba(220,38,38,0.2)'}` }}>
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: sseConnected ? '#22C55E' : reconnecting ? '#F59E0B' : '#DC2626' }} />
            <span style={{ fontSize: 11, fontWeight: 600, color: sseConnected ? '#16A34A' : reconnecting ? '#D97706' : '#DC2626' }}>{sseConnected ? 'Live' : reconnecting ? 'Reconnecting...' : 'Offline'}</span>
          </div>
          <div style={{ position: 'relative' }}>
            <button onClick={() => setShowUserMenu(!showUserMenu)} style={{ fontSize: 12, padding: '6px 14px', border: '1px solid #E2E8F0', borderRadius: 8, background: '#fff', cursor: 'pointer', fontWeight: 600, color: '#374151', display: 'flex', alignItems: 'center', gap: 4 }}>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M19 9l-7 7-7-7"/></svg>
            </button>
            {showUserMenu && (
              <div style={{ position: 'absolute', top: '100%', right: 0, marginTop: 4, background: '#fff', border: '1px solid #E2E8F0', borderRadius: 10, boxShadow: '0 4px 16px rgba(0,0,0,0.1)', minWidth: 160, zIndex: 100, overflow: 'hidden' }}>
                <button onClick={() => { setShowUserMenu(false); setShowChangePass(true); }} style={{ width: '100%', padding: '10px 14px', border: 'none', background: 'none', textAlign: 'left', fontSize: 13, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8, color: '#374151' }} onMouseEnter={e => e.target.style.background = '#F9FAFB'} onMouseLeave={e => e.target.style.background = 'none'}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#6B7280" strokeWidth="2"><path d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z"/></svg>
                  Change Password
                </button>
                <div style={{ height: 1, background: '#F3F4F6' }} />
                <button onClick={() => { setShowUserMenu(false); logout(); }} style={{ width: '100%', padding: '10px 14px', border: 'none', background: 'none', textAlign: 'left', fontSize: 13, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8, color: '#DC2626' }} onMouseEnter={e => e.target.style.background = '#FEF2F2'} onMouseLeave={e => e.target.style.background = 'none'}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#DC2626" strokeWidth="2"><path d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"/></svg>
                  Sign Out
                </button>
              </div>
            )}
          </div>
          {showChangePass && <ChangePasswordModal token={token} onClose={() => setShowChangePass(false)} />}
        </div>
      </header>

      <nav className="app-sidebar">
        <div className="sidebar-section">
          <div className="sidebar-label">Navigation</div>
           {filteredNav.map(item => (
             <div key={item.id} className={`nav-item ${activeTab === item.id ? 'active' : ''}`} onClick={(e) => { e.stopPropagation(); e.preventDefault(); setActiveTab(item.id); }}>
               <Icon path={item.icon} />
               <span>{item.label}</span>
              {item.badge && (
                <span style={{ marginLeft: 'auto', padding: '1px 7px', borderRadius: 10, fontSize: 10, fontWeight: 700, background: item.badge.bg, color: item.badge.color }}>{item.badge.text}</span>
              )}
            </div>
          ))}
        </div>
        <div style={{ marginTop: 'auto', padding: '0 8px' }}>
          <div style={{ padding: 14, background: 'linear-gradient(135deg, #F0F9F4, #ECFDF5)', borderRadius: 12, border: '1px solid #D1FAE5' }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: '#166534', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#16A34A" strokeWidth="2"><path d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"/></svg>
              Chamoli District
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
              {[
                { l: 'Zones', v: dashboardData?.hazard_zones?.length || 5, c: '#DC2626' },
                { l: 'Shelters', v: dashboardData?.capacity_summary?.active_shelters || 26, c: '#16A34A' },
                { l: 'Beds', v: `${Math.round((dashboardData?.capacity_summary?.total_beds_available || 247000) / 1000)}K`, c: '#2563EB' },
                { l: 'Features', v: '32', c: '#7C3AED' },
              ].map((s, i) => (
                <div key={i} style={{ textAlign: 'center', padding: '6px 4px', background: 'rgba(255,255,255,0.7)', borderRadius: 6 }}>
                  <div style={{ fontSize: 14, fontWeight: 800, color: s.c }}>{s.v}</div>
                  <div style={{ fontSize: 9, color: '#6B7280', textTransform: 'uppercase', letterSpacing: '0.3px' }}>{s.l}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </nav>

      <div className="app-main">
        {error && <div className="alert-banner error toast-notification">{error}</div>}
        <Suspense fallback={<div style={{ padding: 40, textAlign: 'center', color: '#94A3B8' }}><div className="skeleton" style={{ width: 200, height: 20, margin: '0 auto 12px' }} /><div className="skeleton" style={{ width: 300, height: 14, margin: '0 auto' }} /></div>}>
        <div key={activeTab} className="page-transition">
        {activeTab === 'dashboard' && <Dashboard data={dashboardData} onOptimize={triggerOptimization} onReOptimize={reOptimize} optimizing={optimizing} />}
        {activeTab === 'analysis' && <RelocationAnalysis data={dashboardData} />}
        {activeTab === 'shelters' && <ShelterManagement data={dashboardData} />}
        {activeTab === 'reports' && <CrowdReportsQueue />}
        {activeTab === 'ivr' && <div style={{ padding: 28, overflow: 'auto', height: '100%' }}><IVRDemo /></div>}
        {activeTab === 'whatsapp' && <div style={{ padding: 28, overflow: 'auto', height: '100%' }}><WhatsAppBot /></div>}
        {activeTab === 'satellite' && <div style={{ padding: 28, overflow: 'auto', height: '100%' }}><SatelliteMonitor /></div>}
        {activeTab === 'family' && <div style={{ padding: 28, overflow: 'auto', height: '100%' }}><FamilySearch /></div>}
        {activeTab === 'ai' && <AIAssistant data={dashboardData} />}
        {activeTab === 'audit' && <AuditLog />}
        {activeTab === 'users' && <UserManagement token={token} />}
        {activeTab === 'multidistrict' && <div style={{ padding: 28, overflow: 'auto', height: '100%' }}><MultiDistrict /></div>}
        {activeTab === 'features' && <div style={{ padding: 28, overflow: 'auto', height: '100%' }}><FeatureShowcase /></div>}
        </div>
        </Suspense>
      </div>
    </div>
  );
}

function CitizenWrapper() {
  const token = localStorage.getItem('locats_token');
  const role = localStorage.getItem('locats_role');
  const cachedEmail = localStorage.getItem('locats_user_email');

  const [user, setUser] = useState(() => {
    if (!token) return null;
    // Instant render from cache
    return { email: cachedEmail || '' };
  });
  const [profile, setProfile] = useState(() => {
    if (!token) return null;
    return { role: role || 'citizen', email: cachedEmail || '' };
  });

  useEffect(() => {
    if (!token) {
      window.location.href = '/';
      return;
    }
    // Verify token in background (don't block UI)
    fetch('/api/auth/me', { headers: { 'Authorization': `Bearer ${token}` } })
      .then(r => r.ok ? r.json() : Promise.reject())
      .then(d => {
        setUser(d.user);
        setProfile({ role: role || 'citizen', email: d.user?.email });
      })
      .catch(() => {
        localStorage.removeItem('locats_token');
        localStorage.removeItem('locats_role');
        localStorage.removeItem('locats_user_email');
        window.location.href = '/';
      });
  }, []);

  if (!user) return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#F0F9F4' }}>
      <div style={{ textAlign: 'center' }}>
        <div style={{ width: 52, height: 52, borderRadius: 14, background: 'linear-gradient(135deg, #16A34A, #0D9488)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 16px', fontWeight: 800, fontSize: 22, color: '#fff' }}>L</div>
        <div style={{ fontSize: 14, color: '#6B7280' }}>Redirecting to login...</div>
      </div>
    </div>
  );

  const handleLogout = () => {
    localStorage.removeItem('locats_token');
    localStorage.removeItem('locats_role');
    localStorage.removeItem('locats_user_email');
    window.location.href = '/';
  };

  return (
    <Suspense fallback={<div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#F0F9F4' }}><div style={{ color: '#6B7280' }}>Loading...</div></div>}>          <CitizenPortal user={user} profile={profile} token={token} onLogout={handleLogout} />
    </Suspense>
  );
}

export default function App() {
  const path = window.location.pathname;
  if (path.startsWith('/citizen')) {
    return <CitizenWrapper />;
  }
  return (
    <AuthProvider>
      {path.startsWith('/audit') ? (
        <Suspense fallback={<div style={{ padding: 40, textAlign: 'center', color: '#94A3B8' }}>Loading...</div>}>
          <AuditVerify />
        </Suspense>
      ) : (
        <AppContent />
      )}
    </AuthProvider>
  );
}
