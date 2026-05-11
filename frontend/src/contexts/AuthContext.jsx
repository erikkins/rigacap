import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const AuthContext = createContext(null);

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [twoFactorRequired, setTwoFactorRequired] = useState(false);
  const [challengeToken, setChallengeToken] = useState(null);

  // Get or create device fingerprint
  const getDeviceFingerprint = useCallback(() => {
    let fp = localStorage.getItem('device_fingerprint');
    if (!fp) {
      fp = crypto.randomUUID();
      localStorage.setItem('device_fingerprint', fp);
    }
    return fp;
  }, []);

  // Get stored tokens
  const getTokens = useCallback(() => {
    const accessToken = localStorage.getItem('accessToken');
    const refreshToken = localStorage.getItem('refreshToken');
    return { accessToken, refreshToken };
  }, []);

  // Store tokens
  const setTokens = useCallback((accessToken, refreshToken) => {
    if (accessToken) {
      localStorage.setItem('accessToken', accessToken);
    }
    if (refreshToken) {
      localStorage.setItem('refreshToken', refreshToken);
    }
  }, []);

  // Clear tokens
  const clearTokens = useCallback(() => {
    localStorage.removeItem('accessToken');
    localStorage.removeItem('refreshToken');
  }, []);

  // Refresh access token
  const refreshAccessToken = useCallback(async () => {
    const { refreshToken } = getTokens();
    if (!refreshToken) {
      return null;
    }

    try {
      const response = await fetch(`${API_URL}/api/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });

      if (!response.ok) {
        throw new Error('Refresh failed');
      }

      const data = await response.json();
      setTokens(data.access_token, data.refresh_token);
      setUser(data.user);
      return data.access_token;
    } catch (err) {
      console.warn('Token refresh failed:', err.message);
      // Don't clear tokens on transient failures — keep stale token
      // and retry on next request. Only clear on explicit logout.
      return null;
    }
  }, [getTokens, setTokens]);

  // Fetch with auth (auto-refresh on 401)
  const fetchWithAuth = useCallback(async (url, options = {}) => {
    const { accessToken } = getTokens();

    const headers = {
      ...options.headers,
      'Authorization': `Bearer ${accessToken}`,
    };

    let response = await fetch(url, { ...options, headers });

    // If 401, try to refresh and retry
    if (response.status === 401) {
      const newToken = await refreshAccessToken();
      if (newToken) {
        headers['Authorization'] = `Bearer ${newToken}`;
        response = await fetch(url, { ...options, headers });
      }
    }

    return response;
  }, [getTokens, refreshAccessToken]);

  // Load user on mount
  useEffect(() => {
    const loadUser = async () => {
      const { accessToken } = getTokens();
      if (!accessToken) {
        setLoading(false);
        return;
      }

      try {
        const response = await fetch(`${API_URL}/api/auth/me`, {
          headers: { 'Authorization': `Bearer ${accessToken}` },
        });

        if (response.ok) {
          const userData = await response.json();
          setUser(userData);
        } else if (response.status === 401) {
          // Try refresh
          const newToken = await refreshAccessToken();
          if (newToken) {
            // Retry /me with new token
            const retry = await fetch(`${API_URL}/api/auth/me`, {
              headers: { 'Authorization': `Bearer ${newToken}` },
            });
            if (retry.ok) {
              setUser(await retry.json());
            }
          }
        }
        // Don't clear tokens on non-401 errors — could be transient
      } catch (err) {
        console.error('Failed to load user:', err);
        // Don't clear tokens on network errors — keep session for retry
      } finally {
        setLoading(false);
      }
    };

    loadUser();
  }, [getTokens, clearTokens, refreshAccessToken]);

  // Helper: redirect users without a subscription to Stripe checkout
  const redirectToCheckoutIfNeeded = async (userData, accessToken) => {
    if (!userData.subscription) {
      const plan = localStorage.getItem('rigacap_selected_plan') || 'monthly';
      try {
        const res = await fetch(`${API_URL}/api/billing/create-checkout`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${accessToken}`,
          },
          body: JSON.stringify({ plan }),
        });
        const data = await res.json();
        if (res.ok && data.checkout_url) {
          // GA4: track begin_checkout conversion
          if (window.gtag) {
            window.gtag('event', 'begin_checkout', { value: plan === 'annual' ? 349 : 39, currency: 'USD' });
          }
          window.location.href = data.checkout_url;
          return true;
        }
      } catch (err) {
        console.error('Checkout redirect failed:', err);
      }
    }
    return false;
  };

  // Register
  const register = async (email, password, name, turnstileToken) => {
    setError(null);
    try {
      const referralCode = localStorage.getItem('rigacap_referral_code');
      const response = await fetch(`${API_URL}/api/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email,
          password,
          name,
          turnstile_token: turnstileToken,
          referral_code: referralCode || undefined,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Registration failed');
      }

      localStorage.removeItem('rigacap_referral_code');
      setTokens(data.access_token, data.refresh_token);
      setUser(data.user);

      // GA4: track sign_up conversion
      if (window.gtag) {
        window.gtag('event', 'sign_up', { method: 'email' });
      }

      // Redirect new users (no subscription) to Stripe checkout
      if (await redirectToCheckoutIfNeeded(data.user, data.access_token)) {
        return { success: true, redirecting: true };
      }

      return { success: true };
    } catch (err) {
      setError(err.message);
      return { success: false, error: err.message };
    }
  };

  // Login
  const login = async (email, password) => {
    setError(null);

    try {
      const trustToken = localStorage.getItem('2fa_trust_token');
      const headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      };
      if (trustToken) {
        headers['X-2FA-Trust'] = trustToken;
      }

      const response = await fetch(`${API_URL}/api/auth/login`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ email, password }),
      });

      let data;
      try {
        data = await response.json();
      } catch (parseErr) {
        throw new Error('Invalid response from server');
      }

      if (!response.ok) {
        throw new Error(data.detail || 'Login failed');
      }

      // Check if 2FA is required
      if (data.requires_2fa) {
        setChallengeToken(data.challenge_token);
        setTwoFactorRequired(true);
        return { success: true, requires_2fa: true };
      }

      setTokens(data.access_token, data.refresh_token);
      setUser(data.user);
      // Log login event AFTER tokens are set — eventLogger reads accessToken
      // from localStorage, so it needs the token in place before calling.
      try {
        const { logEvent } = await import('../lib/eventLogger');
        logEvent('login', { method: 'password', user_id: data.user?.id });
      } catch {}
      return { success: true };
    } catch (err) {
      console.error('Login failed:', err.message);
      setError(err.message);
      return { success: false, error: err.message };
    }
  };

  // Google OAuth
  const loginWithGoogle = async (idToken, turnstileToken = null) => {
    setError(null);
    try {
      const referralCode = localStorage.getItem('rigacap_referral_code');
      const trustToken = localStorage.getItem('2fa_trust_token');
      const headers = { 'Content-Type': 'application/json' };
      if (trustToken) {
        headers['X-2FA-Trust'] = trustToken;
      }

      const response = await fetch(`${API_URL}/api/auth/google`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          id_token: idToken,
          turnstile_token: turnstileToken,
          referral_code: referralCode || undefined,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Google login failed');
      }

      // Check if 2FA is required
      if (data.requires_2fa) {
        setChallengeToken(data.challenge_token);
        setTwoFactorRequired(true);
        return { success: true, requires_2fa: true };
      }

      localStorage.removeItem('rigacap_referral_code');
      setTokens(data.access_token, data.refresh_token);
      setUser(data.user);

      // GA4: track sign_up for new Google users (no subscription = first time)
      if (!data.user.subscription && window.gtag) {
        window.gtag('event', 'sign_up', { method: 'google' });
      }

      // Redirect new users (no subscription) to Stripe checkout
      if (await redirectToCheckoutIfNeeded(data.user, data.access_token)) {
        return { success: true, redirecting: true };
      }

      return { success: true };
    } catch (err) {
      setError(err.message);
      return { success: false, error: err.message };
    }
  };

  // Apple OAuth
  const loginWithApple = async (idToken, userData = null, turnstileToken = null) => {
    setError(null);
    try {
      const referralCode = localStorage.getItem('rigacap_referral_code');
      const trustToken = localStorage.getItem('2fa_trust_token');
      const headers = { 'Content-Type': 'application/json' };
      if (trustToken) {
        headers['X-2FA-Trust'] = trustToken;
      }

      const response = await fetch(`${API_URL}/api/auth/apple`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          id_token: idToken,
          user_data: userData,
          turnstile_token: turnstileToken,
          referral_code: referralCode || undefined,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Apple login failed');
      }

      // Check if 2FA is required
      if (data.requires_2fa) {
        setChallengeToken(data.challenge_token);
        setTwoFactorRequired(true);
        return { success: true, requires_2fa: true };
      }

      localStorage.removeItem('rigacap_referral_code');
      setTokens(data.access_token, data.refresh_token);
      setUser(data.user);

      // GA4: track sign_up for new Apple users (no subscription = first time)
      if (!data.user.subscription && window.gtag) {
        window.gtag('event', 'sign_up', { method: 'apple' });
      }

      // Redirect new users (no subscription) to Stripe checkout
      if (await redirectToCheckoutIfNeeded(data.user, data.access_token)) {
        return { success: true, redirecting: true };
      }

      return { success: true };
    } catch (err) {
      setError(err.message);
      return { success: false, error: err.message };
    }
  };

  // Verify 2FA code after login challenge
  const verify2FA = async (code, trustDevice = false, isBackupCode = false) => {
    setError(null);
    try {
      const deviceId = getDeviceFingerprint();
      const response = await fetch(`${API_URL}/api/auth/2fa/verify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          challenge_token: challengeToken,
          code,
          device_id: deviceId,
          trust_device: trustDevice,
          is_backup_code: isBackupCode,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Verification failed');
      }

      // Store trust token if provided
      if (data.trust_token) {
        localStorage.setItem('2fa_trust_token', data.trust_token);
      }

      setTokens(data.access_token, data.refresh_token);
      setUser(data.user);
      setTwoFactorRequired(false);
      setChallengeToken(null);
      return { success: true };
    } catch (err) {
      setError(err.message);
      return { success: false, error: err.message };
    }
  };

  // Cancel 2FA flow — go back to login
  const cancel2FA = useCallback(() => {
    setTwoFactorRequired(false);
    setChallengeToken(null);
    setError(null);
  }, []);

  // Logout
  const logout = useCallback(async () => {
    try {
      const { accessToken } = getTokens();
      if (accessToken) {
        await fetch(`${API_URL}/api/auth/logout`, {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${accessToken}` },
        });
      }
    } catch (err) {
      console.error('Logout error:', err);
    } finally {
      clearTokens();
      localStorage.removeItem('2fa_trust_token');
      setUser(null);
      setTwoFactorRequired(false);
      setChallengeToken(null);
    }
  }, [getTokens, clearTokens]);

  // Check if user is admin
  const isAdmin = user?.role === 'admin' && user?.email === 'erik@rigacap.com';

  // Refresh user data from API (e.g., after checkout to update subscription status)
  const refreshUser = useCallback(async () => {
    const { accessToken } = getTokens();
    if (!accessToken) return;
    try {
      const response = await fetch(`${API_URL}/api/auth/me`, {
        headers: { 'Authorization': `Bearer ${accessToken}` },
      });
      if (response.ok) {
        const userData = await response.json();
        setUser(userData);
      }
    } catch (err) {
      console.error('Failed to refresh user:', err);
    }
  }, [getTokens]);

  // Check if subscription is valid
  const hasValidSubscription = user?.subscription?.is_valid ?? false;

  // Get trial days remaining
  const trialDaysRemaining = user?.subscription?.days_remaining ?? 0;

  const value = {
    user,
    loading,
    error,
    isAuthenticated: !!user,
    isAdmin,
    hasValidSubscription,
    trialDaysRemaining,
    twoFactorRequired,
    register,
    login,
    loginWithGoogle,
    loginWithApple,
    logout,
    verify2FA,
    cancel2FA,
    fetchWithAuth,
    refreshUser,
    clearError: () => setError(null),
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export default AuthContext;
