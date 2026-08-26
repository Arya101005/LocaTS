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

  // Try to restore user from localStorage for instant render (no network call)
  const cachedUser = localStorage.getItem('locats_user_email');
  const cachedRole = localStorage.getItem('locats_role');

  const fetchProfile = useCallback(async (accessToken) => {
    try {
      const headers = { 'Authorization': `Bearer ${accessToken}` };
      const res = await fetch(`${API}/auth/me`, { headers });
      if (!res.ok) {
        localStorage.removeItem('locats_token');
        setToken(null);
        setUser(null);
        setProfile(null);
        return false;
      }
      const meData = await res.json();
      setUser(meData.user);
      setProfile({ role: cachedRole || meData.user?.role || 'citizen', email: meData.user?.email || '', full_name: '' });
      return true;
    } catch {
      setUser(null);
      setProfile(null);
      return false;
    }
  }, [cachedRole]);

  useEffect(() => {
    const isLandingPage = window.location.pathname === '/';
    if (token && !isLandingPage) {
      // If we have cached user info, use it instantly — verify token in background
      if (cachedUser && cachedRole) {
        setUser({ email: cachedUser });
        setProfile({ role: cachedRole, email: cachedUser, full_name: '' });
        setLoading(false);
        // Verify token in background (don't block UI)
        fetchProfile(token).catch(() => {});
      } else {
        fetchProfile(token).finally(() => setLoading(false));
      }
    } else {
      setLoading(false);
    }
  }, []);

  const login = useCallback(async (email, password) => {
    const res = await fetch(`${API}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || data.error || 'Login failed. Please try again.');
    if (!data.access_token) throw new Error('No token received from server');
    localStorage.setItem('locats_token', data.access_token);
    localStorage.setItem('locats_user_email', data.user?.email || email);
    setToken(data.access_token);
    // Store role immediately — no need to wait for profile fetch
    if (data.role) {
      localStorage.setItem('locats_role', data.role);
      setStoredRole(data.role);
      setUser({ email: data.user?.email || email, id: data.user?.id });
      setProfile({ role: data.role, email: data.user?.email || email, full_name: '' });
    }
    return data;
  }, []);

  const signup = useCallback(async (email, password, name) => {
    // Clear any stale tokens from previous sessions before signup
    localStorage.removeItem('locats_token');
    localStorage.removeItem('locats_role');
    localStorage.removeItem('locats_user_email');
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
    if (!res.ok) throw new Error(data.detail || data.error || 'Signup failed. Please try again.');
    // Signup returns success — user must sign in explicitly
    return data;
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem('locats_token');
    localStorage.removeItem('locats_role');
    localStorage.removeItem('locats_user_email');
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

  const role = profile?.role || storedRole || 'citizen';
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
