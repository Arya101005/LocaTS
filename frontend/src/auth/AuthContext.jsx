import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';

const API = '/api';
const AuthContext = createContext(null);

// Default context for routes rendered without AuthProvider (e.g. /citizen, /audit)
const AUTH_DEFAULT = { user: null, profile: null, token: null, role: null, loading: false, login: async () => false, logout: () => {} };

export function useAuth() { return useContext(AuthContext) || AUTH_DEFAULT; }

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [profile, setProfile] = useState(null);
  const [token, setToken] = useState(() => localStorage.getItem('locats_token'));
  const [storedRole, setStoredRole] = useState(() => localStorage.getItem('locats_role'));
  const [loading, setLoading] = useState(true);

  const fetchProfile = useCallback(async (accessToken) => {
    try {
      // Fetch /me and /profile in parallel
      const headers = { 'Authorization': `Bearer ${accessToken}` };
      const [meRes, profRes] = await Promise.all([
        fetch(`${API}/auth/me`, { headers }),
        fetch(`${API}/auth/profile`, { headers }),
      ]);
      if (!meRes.ok) {
        // Token invalid — clear it
        localStorage.removeItem('locats_token');
        setToken(null);
        setUser(null);
        setProfile(null);
        return false;
      }
      const meData = await meRes.json();
      setUser(meData.user);

      if (profRes.ok) {
        const pdata = await profRes.json();
        setProfile(pdata);
      } else {
        // Fallback: determine role from email
        const email = meData.user?.email || '';
        setProfile({ role: email.includes('admin') ? 'admin' : 'operator', full_name: email, email });
      }
      return true;
    } catch {
      setUser(null);
      setProfile(null);
      return false;
    }
  }, []);

  useEffect(() => {
    // Skip profile fetch on landing page — show login instantly
    const isLandingPage = window.location.pathname === '/';
    if (token && !isLandingPage) {
      fetchProfile(token).finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, [token, fetchProfile]);

  const login = useCallback(async (email, password) => {
    const res = await fetch(`${API}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    if (!data.access_token) throw new Error('No token received from server');
    localStorage.setItem('locats_token', data.access_token);
    setToken(data.access_token);
    // Store role immediately — no need to wait for profile fetch
    if (data.role) {
      localStorage.setItem('locats_role', data.role);
      setStoredRole(data.role);
      setProfile({ role: data.role, email, full_name: email });
    }
    return data;
  }, []);

  const signup = useCallback(async (email, password, name) => {
    // Clear any stale tokens from previous sessions before signup
    localStorage.removeItem('locats_token');
    localStorage.removeItem('locats_role');
    setToken(null);
    setUser(null);
    setProfile(null);
    setStoredRole(null);
    const res = await fetch(`${API}/auth/signup`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password, name }),
    });
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    // Signup NEVER stores tokens — user must sign in explicitly
    return data;
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem('locats_token');
    localStorage.removeItem('locats_role');
    setToken(null);
    setUser(null);
    setProfile(null);
    setStoredRole(null);
  }, []);

  const becomeAdmin = useCallback(async () => {
    try {
      const res = await fetch(`${API}/auth/make-admin`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
      });
      const data = await res.json();
      // Refresh profile
      if (token) await fetchProfile(token);
      return data;
    } catch (e) { return { error: e.message }; }
  }, [token, fetchProfile]);

  const role = profile?.role || storedRole || (user?.email === 'pranavarya2005@gmail.com' ? 'admin' : 'citizen');
  const isAdmin = role === 'admin';
  const isOperator = role === 'operator' || role === 'admin';
  const isViewer = role === 'viewer';
  const isCitizen = role === 'citizen';

  const ctxValue = React.useMemo(() => ({
    user, profile, token, loading, login, signup, logout, becomeAdmin, isAdmin, isOperator, isViewer, role
  }), [user, profile, token, loading, login, signup, logout, becomeAdmin, isAdmin, isOperator, isViewer, role]);

  return (
    <AuthContext.Provider value={ctxValue}>
      {children}
    </AuthContext.Provider>
  );
}
