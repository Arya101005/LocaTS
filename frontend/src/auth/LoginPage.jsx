import React, { useState } from 'react';
import { useAuth } from './AuthContext';

export default function LoginPage() {
  const { login, signup } = useAuth();
  const [mode, setMode] = useState('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(''); setSuccess(''); setLoading(true);
    try {
      if (mode === 'login') {
        await login(email, password);
      } else {
        const res = await signup(email, password, name);
        setSuccess(res.message || 'Account created. Check your email for confirmation.');
        setMode('login');
      }
    } catch (err) { setError(err.message); }
    finally { setLoading(false); }
  };

  return (
    <div style={{ minHeight: '100vh', background: '#F6FAFD', display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: "'Inter', sans-serif" }}>
      <div style={{ width: '100%', maxWidth: 420, padding: '0 20px' }}>
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: 36 }}>
          <div style={{ width: 56, height: 56, borderRadius: 14, background: 'linear-gradient(135deg, #2563EB, #14B8A6)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 16px', fontWeight: 800, fontSize: 24, color: '#fff', boxShadow: '0 4px 12px rgba(37,99,235,0.3)' }}>L</div>
          <h1 style={{ fontSize: 26, fontWeight: 800, color: '#172B4D', marginBottom: 4, letterSpacing: '-0.5px' }}>LocaTS</h1>
          <p style={{ fontSize: 13, color: '#94A3B8', fontWeight: 500 }}>Intelligent Disaster Relocation Planning</p>
        </div>

        {/* Card */}
        <div style={{ background: '#fff', borderRadius: 16, border: '1px solid #E2E8F0', padding: 32, boxShadow: '0 1px 3px rgba(0,0,0,0.06)' }}>
          {/* Tabs */}
          <div style={{ display: 'flex', gap: 4, background: '#F6FAFD', borderRadius: 10, padding: 4, marginBottom: 24, border: '1px solid #E2E8F0' }}>
            <button onClick={() => { setMode('login'); setError(''); setSuccess(''); }}
              style={{ flex: 1, padding: '9px 0', border: 'none', borderRadius: 8, fontFamily: "'Inter', sans-serif", fontSize: 13, fontWeight: 600, cursor: 'pointer', background: mode === 'login' ? '#fff' : 'transparent', color: mode === 'login' ? '#2563EB' : '#94A3B8', boxShadow: mode === 'login' ? '0 1px 2px rgba(0,0,0,0.06)' : 'none', transition: 'all 0.15s' }}>Sign In</button>
            <button onClick={() => { setMode('signup'); setError(''); setSuccess(''); }}
              style={{ flex: 1, padding: '9px 0', border: 'none', borderRadius: 8, fontFamily: "'Inter', sans-serif", fontSize: 13, fontWeight: 600, cursor: 'pointer', background: mode === 'signup' ? '#fff' : 'transparent', color: mode === 'signup' ? '#2563EB' : '#94A3B8', boxShadow: mode === 'signup' ? '0 1px 2px rgba(0,0,0,0.06)' : 'none', transition: 'all 0.15s' }}>Create Account</button>
          </div>

          {error && <div style={{ padding: '10px 14px', background: '#FEF2F2', border: '1px solid rgba(239,68,68,0.15)', borderRadius: 8, fontSize: 13, color: '#EF4444', marginBottom: 16 }}>{error}</div>}
          {success && <div style={{ padding: '10px 14px', background: '#F0FDF4', border: '1px solid rgba(34,197,94,0.15)', borderRadius: 8, fontSize: 13, color: '#16A34A', marginBottom: 16 }}>{success}</div>}

          <form onSubmit={handleSubmit}>
            {mode === 'signup' && (
              <div style={{ marginBottom: 14 }}>
                <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#475569', marginBottom: 6 }}>Full Name</label>
                <input type="text" value={name} onChange={e => setName(e.target.value)} placeholder="Enter your full name" required
                  style={{ width: '100%', padding: '10px 14px', background: '#F6FAFD', border: '1px solid #E2E8F0', borderRadius: 10, color: '#172B4D', fontFamily: "'Inter', sans-serif", fontSize: 13 }} />
              </div>
            )}
            <div style={{ marginBottom: 14 }}>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#475569', marginBottom: 6 }}>Email</label>
              <input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="operator@locats.gov.in" required
                style={{ width: '100%', padding: '10px 14px', background: '#F6FAFD', border: '1px solid #E2E8F0', borderRadius: 10, color: '#172B4D', fontFamily: "'Inter', sans-serif", fontSize: 13 }} />
            </div>
            <div style={{ marginBottom: 20 }}>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#475569', marginBottom: 6 }}>Password</label>
              <input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="Minimum 6 characters" required minLength={6}
                style={{ width: '100%', padding: '10px 14px', background: '#F6FAFD', border: '1px solid #E2E8F0', borderRadius: 10, color: '#172B4D', fontFamily: "'Inter', sans-serif", fontSize: 13 }} />
            </div>
            <button type="submit" disabled={loading} style={{ width: '100%', padding: '11px 0', background: '#2563EB', color: '#fff', border: 'none', borderRadius: 10, fontFamily: "'Inter', sans-serif", fontSize: 14, fontWeight: 600, cursor: loading ? 'wait' : 'pointer', boxShadow: '0 1px 3px rgba(37,99,235,0.3)', opacity: loading ? 0.7 : 1 }}>
              {loading ? 'Please wait...' : mode === 'login' ? 'Sign In' : 'Create Account'}
            </button>
          </form>

          {mode === 'login' && (
            <div style={{ marginTop: 20, textAlign: 'center', fontSize: 12, color: '#94A3B8' }}>
              Demo credentials: <span style={{ fontFamily: 'monospace', color: '#475569' }}>admin@locats.gov.in / admin123</span>
            </div>
          )}
        </div>

        {/* Footer */}
        <div style={{ textAlign: 'center', marginTop: 24, fontSize: 11, color: '#94A3B8' }}>
          SIH26191 — Ministry of Home Affairs, Disaster Management
        </div>
      </div>
    </div>
  );
}
