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
  const [loading, setLoading] = useState(true);

  const fetchProfile = useCallback(async (accessToken) => {
    try {
      const res = await fetch(`${API}/auth/me`, {
        headers: { 'Authorization': `Bearer ${accessToken}` },
      });
      if (!res.ok) {
        // Token invalid — clear it
        localStorage.removeItem('locats_token');
        setToken(null);
        setUser(null);
        setProfile(null);
        return false;
      }
      const data = await res.json();
      setUser(data.user);

      // Fetch full profile with role
      try {
        const pres = await fetch(`${API}/auth/profile`, {
          headers: { 'Authorization': `Bearer ${accessToken}` },
        });
        if (pres.ok) {
          const pdata = await pres.json();
          setProfile(pdata);
        } else {
          // Fallback: determine role from email
          const email = data.user?.email || '';
          setProfile({ role: email.includes('admin') ? 'admin' : 'operator', full_name: email, email });
        }
      } catch {
        const email = data.user?.email || '';
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
    if (token) {
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
    return data;
  }, []);

  const signup = useCallback(async (email, password, name) => {
    const res = await fetch(`${API}/auth/signup`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password, name }),
    });
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    // If auto-confirmed, tokens are returned — log in immediately
    if (data.access_token) {
      localStorage.setItem('locats_token', data.access_token);
      setToken(data.access_token);
    }
    return data;
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem('locats_token');
    setToken(null);
    setUser(null);
    setProfile(null);
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

  const role = profile?.role || (user?.email?.includes('admin') ? 'admin' : 'operator');
  const isAdmin = role === 'admin';
  const isOperator = role === 'operator' || role === 'admin';
  const isViewer = role === 'viewer';

  const ctxValue = React.useMemo(() => ({
    user, profile, token, loading, login, signup, logout, becomeAdmin, isAdmin, isOperator, isViewer, role
  }), [user, profile, token, loading, login, signup, logout, becomeAdmin, isAdmin, isOperator, isViewer, role]);

  return (
    <AuthContext.Provider value={ctxValue}>
      {children}
    </AuthContext.Provider>
  );
}
