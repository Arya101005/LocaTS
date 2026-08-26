import React, { useState } from 'react';
import { useAuth } from './AuthContext';

const API = '/api';

export default function LoginPage() {
  const { login, signup } = useAuth();
  const [mode, setMode] = useState('login'); // login | signup | forgot | reset
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState('');
  // Forgot password state
  const [resetToken, setResetToken] = useState('');
  const [resetCode, setResetCode] = useState('');
  const [debugCode, setDebugCode] = useState('');
  const [newPass, setNewPass] = useState('');
  const [confirmPass, setConfirmPass] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(''); setSuccess(''); setLoading(true);
    try {
      if (mode === 'login') {
        await login(email, password);
      } else if (mode === 'signup') {
        const res = await signup(email, password, name);
        setSuccess(res.message || 'Account created. Please sign in.');
        setMode('login');
      }
    } catch (err) { setError(err.message); }
    finally { setLoading(false); }
  };

  const handleForgot = async (e) => {
    e.preventDefault();
    setError(''); setSuccess(''); setLoading(true);
    try {
      const res = await fetch(`${API}/auth/forgot-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to send reset code.');
      setResetToken(data._debug_token || '');
      setDebugCode(data._debug_code || '');
      setSuccess('Reset code sent! Check your email (or see code below in demo).');
      setMode('reset');
    } catch (err) { setError(err.message); }
    finally { setLoading(false); }
  };

  const handleReset = async (e) => {
    e.preventDefault();
    setError(''); setSuccess(''); setLoading(true);
    try {
      if (newPass !== confirmPass) throw new Error('Passwords do not match.');
      if (newPass.length < 6) throw new Error('Password must be at least 6 characters.');
      const res = await fetch(`${API}/auth/reset-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: resetToken, code: resetCode, new_password: newPass }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to reset password.');
      setSuccess('Password reset successful! You can now sign in.');
      setMode('login');
      setPassword('');
    } catch (err) { setError(err.message); }
    finally { setLoading(false); }
  };

  const inputStyle = { width: '100%', padding: '10px 14px', background: '#F6FAFD', border: '1px solid #E2E8F0', borderRadius: 10, color: '#172B4D', fontFamily: "'Inter', sans-serif", fontSize: 13 };
  const labelStyle = { display: 'block', fontSize: 12, fontWeight: 600, color: '#475569', marginBottom: 6 };

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
          {/* Tabs (only for login/signup) */}
          {(mode === 'login' || mode === 'signup') && (
            <div style={{ display: 'flex', gap: 4, background: '#F6FAFD', borderRadius: 10, padding: 4, marginBottom: 24, border: '1px solid #E2E8F0' }}>
              <button onClick={() => { setMode('login'); setError(''); setSuccess(''); }}
                style={{ flex: 1, padding: '9px 0', border: 'none', borderRadius: 8, fontFamily: "'Inter', sans-serif", fontSize: 13, fontWeight: 600, cursor: 'pointer', background: mode === 'login' ? '#fff' : 'transparent', color: mode === 'login' ? '#2563EB' : '#94A3B8', boxShadow: mode === 'login' ? '0 1px 2px rgba(0,0,0,0.06)' : 'none', transition: 'all 0.15s' }}>Sign In</button>
              <button onClick={() => { setMode('signup'); setError(''); setSuccess(''); }}
                style={{ flex: 1, padding: '9px 0', border: 'none', borderRadius: 8, fontFamily: "'Inter', sans-serif", fontSize: 13, fontWeight: 600, cursor: 'pointer', background: mode === 'signup' ? '#fff' : 'transparent', color: mode === 'signup' ? '#2563EB' : '#94A3B8', boxShadow: mode === 'signup' ? '0 1px 2px rgba(0,0,0,0.06)' : 'none', transition: 'all 0.15s' }}>Create Account</button>
            </div>
          )}

          {/* Header for forgot/reset modes */}
          {mode === 'forgot' && (
            <div style={{ marginBottom: 20 }}>
              <button onClick={() => { setMode('login'); setError(''); setSuccess(''); }} style={{ background: 'none', border: 'none', color: '#94A3B8', fontSize: 12, cursor: 'pointer', padding: 0, marginBottom: 12, fontFamily: "'Inter', sans-serif" }}>&larr; Back to Sign In</button>
              <h2 style={{ fontSize: 18, fontWeight: 700, color: '#111827', marginBottom: 4 }}>Forgot Password?</h2>
              <p style={{ fontSize: 13, color: '#6B7280' }}>Enter your email and we'll send you a reset code.</p>
            </div>
          )}

          {mode === 'reset' && (
            <div style={{ marginBottom: 20 }}>
              <button onClick={() => { setMode('forgot'); setError(''); setSuccess(''); }} style={{ background: 'none', border: 'none', color: '#94A3B8', fontSize: 12, cursor: 'pointer', padding: 0, marginBottom: 12, fontFamily: "'Inter', sans-serif" }}>&larr; Back</button>
              <h2 style={{ fontSize: 18, fontWeight: 700, color: '#111827', marginBottom: 4 }}>Reset Password</h2>
              <p style={{ fontSize: 13, color: '#6B7280' }}>Enter the code from your email and your new password.</p>
            </div>
          )}

          {error && <div style={{ padding: '10px 14px', background: '#FEF2F2', border: '1px solid rgba(239,68,68,0.15)', borderRadius: 8, fontSize: 13, color: '#EF4444', marginBottom: 16 }}>{error}</div>}
          {success && <div style={{ padding: '10px 14px', background: '#F0FDF4', border: '1px solid rgba(34,197,94,0.15)', borderRadius: 8, fontSize: 13, color: '#16A34A', marginBottom: 16 }}>{success}</div>}

          {/* Demo code display */}
          {mode === 'reset' && debugCode && (
            <div style={{ padding: '10px 14px', background: '#EFF6FF', border: '1px solid #BFDBFE', borderRadius: 8, fontSize: 12, color: '#1E40AF', marginBottom: 16, fontFamily: 'monospace' }}>
              <strong>Demo Reset Code:</strong> {debugCode}
            </div>
          )}

          {/* Login/Signup form */}
          {(mode === 'login' || mode === 'signup') && (
            <form onSubmit={handleSubmit}>
              {mode === 'signup' && (
                <div style={{ marginBottom: 14 }}>
                  <label style={labelStyle}>Full Name</label>
                  <input type="text" value={name} onChange={e => setName(e.target.value)} placeholder="Enter your full name" required style={inputStyle} />
                </div>
              )}
              <div style={{ marginBottom: 14 }}>
                <label style={labelStyle}>Email</label>
                <input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="you@example.com" required style={inputStyle} />
              </div>
              <div style={{ marginBottom: 20 }}>
                <label style={labelStyle}>Password</label>
                <input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="Minimum 6 characters" required minLength={6} style={inputStyle} />
              </div>
              <button type="submit" disabled={loading} style={{ width: '100%', padding: '11px 0', background: '#2563EB', color: '#fff', border: 'none', borderRadius: 10, fontFamily: "'Inter', sans-serif", fontSize: 14, fontWeight: 600, cursor: loading ? 'wait' : 'pointer', boxShadow: '0 1px 3px rgba(37,99,235,0.3)', opacity: loading ? 0.7 : 1 }}>
                {loading ? 'Please wait...' : mode === 'login' ? 'Sign In' : 'Create Account'}
              </button>
            </form>
          )}

          {/* Forgot password form */}
          {mode === 'forgot' && (
            <form onSubmit={handleForgot}>
              <div style={{ marginBottom: 20 }}>
                <label style={labelStyle}>Email Address</label>
                <input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="you@example.com" required style={inputStyle} />
              </div>
              <button type="submit" disabled={loading} style={{ width: '100%', padding: '11px 0', background: '#2563EB', color: '#fff', border: 'none', borderRadius: 10, fontFamily: "'Inter', sans-serif", fontSize: 14, fontWeight: 600, cursor: loading ? 'wait' : 'pointer', opacity: loading ? 0.7 : 1 }}>
                {loading ? 'Sending...' : 'Send Reset Code'}
              </button>
            </form>
          )}

          {/* Reset password form */}
          {mode === 'reset' && (
            <form onSubmit={handleReset}>
              <div style={{ marginBottom: 14 }}>
                <label style={labelStyle}>Reset Code</label>
                <input type="text" value={resetCode} onChange={e => setResetCode(e.target.value)} placeholder="6-digit code" required maxLength={6}
                  style={{ ...inputStyle, fontFamily: 'monospace', letterSpacing: 4, textAlign: 'center', fontSize: 18 }} />
              </div>
              <div style={{ marginBottom: 14 }}>
                <label style={labelStyle}>New Password</label>
                <input type="password" value={newPass} onChange={e => setNewPass(e.target.value)} placeholder="Minimum 6 characters" required minLength={6} style={inputStyle} />
              </div>
              <div style={{ marginBottom: 20 }}>
                <label style={labelStyle}>Confirm New Password</label>
                <input type="password" value={confirmPass} onChange={e => setConfirmPass(e.target.value)} placeholder="Re-enter new password" required minLength={6} style={inputStyle} />
              </div>
              <button type="submit" disabled={loading} style={{ width: '100%', padding: '11px 0', background: '#16A34A', color: '#fff', border: 'none', borderRadius: 10, fontFamily: "'Inter', sans-serif", fontSize: 14, fontWeight: 600, cursor: loading ? 'wait' : 'pointer', opacity: loading ? 0.7 : 1 }}>
                {loading ? 'Resetting...' : 'Reset Password'}
              </button>
            </form>
          )}

          {/* Forgot password link (only on login) */}
          {mode === 'login' && (
            <div style={{ marginTop: 16, textAlign: 'center' }}>
              <button onClick={() => { setMode('forgot'); setError(''); setSuccess(''); setDebugCode(''); }}
                style={{ background: 'none', border: 'none', color: '#2563EB', fontSize: 12, cursor: 'pointer', fontWeight: 600, fontFamily: "'Inter', sans-serif" }}>
                Forgot password?
              </button>
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
