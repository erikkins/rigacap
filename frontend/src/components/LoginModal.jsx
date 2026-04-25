import React, { useState, useEffect, useRef } from 'react';
import { X, Mail, Lock, User, Eye, EyeOff, Chrome, Apple, Shield } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';

const TURNSTILE_SITE_KEY = import.meta.env.VITE_TURNSTILE_SITE_KEY;
const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID;

export default function LoginModal({ isOpen = true, onClose, onSuccess, initialMode = 'login', selectedPlan = 'monthly' }) {
  const { login, register, loginWithGoogle, loginWithApple, verify2FA, cancel2FA, twoFactorRequired, error, clearError } = useAuth();
  const [mode, setMode] = useState(initialMode);
  const [twoFactorCode, setTwoFactorCode] = useState('');
  const [trustDevice, setTrustDevice] = useState(false);
  const [useBackupCode, setUseBackupCode] = useState(false);
  const [twoFactorLoading, setTwoFactorLoading] = useState(false);
  const [twoFactorError, setTwoFactorError] = useState('');
  const twoFactorInputRef = useRef(null);

  // Store selected plan in localStorage for use during checkout
  useEffect(() => {
    if (selectedPlan) {
      localStorage.setItem('rigacap_selected_plan', selectedPlan);
    }
  }, [selectedPlan]);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [localError, setLocalError] = useState('');
  const [turnstileToken, setTurnstileToken] = useState('');
  const turnstileRef = useRef(null);

  // Reset form when modal opens/closes
  useEffect(() => {
    if (isOpen) {
      setEmail('');
      setPassword('');
      setName('');
      setLocalError('');
      clearError();
      setTurnstileToken('');
      setMode(initialMode); // Reset mode based on visitor type
    }
  }, [isOpen, clearError, initialMode]);

  // Load Turnstile widget
  useEffect(() => {
    if (!isOpen || !TURNSTILE_SITE_KEY || mode !== 'register') return;

    const loadTurnstile = () => {
      if (window.turnstile && turnstileRef.current) {
        window.turnstile.render(turnstileRef.current, {
          sitekey: TURNSTILE_SITE_KEY,
          callback: (token) => setTurnstileToken(token),
          'error-callback': () => setTurnstileToken(''),
        });
      }
    };

    // Wait for turnstile to load
    if (window.turnstile) {
      loadTurnstile();
    } else {
      const checkInterval = setInterval(() => {
        if (window.turnstile) {
          loadTurnstile();
          clearInterval(checkInterval);
        }
      }, 100);
      return () => clearInterval(checkInterval);
    }
  }, [isOpen, mode]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setLocalError('');

    try {
      if (mode === 'register') {
        if (!turnstileToken && TURNSTILE_SITE_KEY) {
          setLocalError('Please complete the verification');
          setLoading(false);
          return;
        }
        const result = await register(email, password, name, turnstileToken || 'dev-bypass');
        if (result.success) {
          if (!result.redirecting) {
            onSuccess ? onSuccess() : onClose();
          }
        } else {
          setLocalError(result.error);
        }
      } else {
        const result = await login(email, password);
        if (result.success) {
          if (result.requires_2fa) {
            return;
          }
          if (onSuccess) {
            onSuccess();
          } else if (onClose) {
            onClose();
          }
        } else {
          setLocalError(result.error || 'Login failed');
        }
      }
    } catch (err) {
      setLocalError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleLogin = async () => {
    if (!GOOGLE_CLIENT_ID) {
      setLocalError('Google Sign-In is not configured.');
      return;
    }

    try {
      const google = window.google;
      if (!google?.accounts?.id) {
        setLocalError('Google Sign-In SDK not loaded. Please refresh and try again.');
        return;
      }

      google.accounts.id.initialize({
        client_id: GOOGLE_CLIENT_ID,
        callback: async (response) => {
          if (response.credential) {
            setLoading(true);
            const result = await loginWithGoogle(response.credential);
            setLoading(false);
            if (result.success) {
              if (result.requires_2fa) return;
              if (!result.redirecting) {
                onSuccess ? onSuccess() : onClose();
              }
            } else {
              setLocalError(result.error || 'Google login failed');
            }
          }
        },
      });

      google.accounts.id.prompt((notification) => {
        if (notification.isNotDisplayed() || notification.isSkippedMoment()) {
          google.accounts.id.renderButton(
            document.getElementById('google-signin-button'),
            { theme: 'outline', size: 'large', width: '100%' }
          );
        }
      });
    } catch (err) {
      console.error('Google login error:', err);
      setLocalError('Google Sign-In failed. Please try again.');
    }
  };

  const handleAppleLogin = async () => {
    const APPLE_CLIENT_ID = import.meta.env.VITE_APPLE_CLIENT_ID;
    if (!APPLE_CLIENT_ID) {
      setLocalError('Apple Sign-In is not configured.');
      return;
    }

    try {
      if (!window.AppleID) {
        setLocalError('Apple Sign-In SDK not loaded. Please refresh and try again.');
        return;
      }

      window.AppleID.auth.init({
        clientId: APPLE_CLIENT_ID,
        scope: 'name email',
        redirectURI: `${window.location.origin}/auth/apple/callback`,
        usePopup: true,
      });

      const response = await window.AppleID.auth.signIn();
      const idToken = response.authorization.id_token;
      const userData = response.user || null;

      setLoading(true);
      const result = await loginWithApple(idToken, userData);
      setLoading(false);

      if (result.success) {
        if (result.requires_2fa) return;
        if (!result.redirecting) {
          onSuccess ? onSuccess() : onClose();
        }
      } else {
        setLocalError(result.error || 'Apple login failed');
      }
    } catch (err) {
      setLoading(false);
      if (err.error === 'popup_closed_by_user') return;
      console.error('Apple login error:', err);
      setLocalError('Apple Sign-In failed. Please try again.');
    }
  };

  const handle2FASubmit = async (e) => {
    e.preventDefault();
    setTwoFactorLoading(true);
    setTwoFactorError('');
    try {
      const result = await verify2FA(twoFactorCode, trustDevice, useBackupCode);
      if (result.success) {
        setTwoFactorCode('');
        setTrustDevice(false);
        setUseBackupCode(false);
        onSuccess ? onSuccess() : onClose();
      } else {
        setTwoFactorError(result.error || 'Invalid code');
      }
    } catch (err) {
      setTwoFactorError(err.message);
    } finally {
      setTwoFactorLoading(false);
    }
  };

  useEffect(() => {
    if (twoFactorRequired && twoFactorInputRef.current) {
      twoFactorInputRef.current.focus();
    }
  }, [twoFactorRequired, useBackupCode]);

  if (!isOpen) return null;

  // 2FA verification step
  if (twoFactorRequired) {
    return (
      <div className="fixed inset-0 bg-ink/60 flex items-center justify-center z-50 p-4">
        <div className="bg-paper rounded max-w-md w-full overflow-hidden border border-rule">
          <div className="px-6 py-5 border-b border-rule flex justify-between items-center">
            <h2 className="font-display text-lg text-ink flex items-center gap-2" style={{ fontVariationSettings: '"opsz" 48' }}>
              <Shield size={18} className="text-claret" /> Verification
            </h2>
            <button
              onClick={() => { cancel2FA(); setTwoFactorCode(''); setTwoFactorError(''); setUseBackupCode(false); }}
              className="text-ink-light hover:text-ink transition-colors"
            >
              <X size={22} />
            </button>
          </div>
          <div className="p-6">
            <p className="text-sm text-ink-mute mb-4">
              {useBackupCode
                ? 'Enter one of your 8-character backup codes.'
                : 'Enter the 6-digit code from your authenticator app.'}
            </p>

            {(twoFactorError || error) && (
              <div className="mb-4 p-3 bg-negative/10 border border-negative/30 text-negative text-sm">
                {twoFactorError || error}
              </div>
            )}

            <form onSubmit={handle2FASubmit} className="space-y-4">
              <div>
                <input
                  ref={twoFactorInputRef}
                  type="text"
                  value={twoFactorCode}
                  onChange={(e) => setTwoFactorCode(e.target.value)}
                  placeholder={useBackupCode ? 'ABCD1234' : '000000'}
                  maxLength={useBackupCode ? 8 : 6}
                  autoComplete="one-time-code"
                  inputMode={useBackupCode ? 'text' : 'numeric'}
                  className="w-full px-4 py-3 border border-rule-dark text-center text-2xl font-mono tracking-widest bg-paper-card focus:outline-none focus:border-ink"
                />
              </div>

              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={trustDevice}
                  onChange={(e) => setTrustDevice(e.target.checked)}
                  className="w-4 h-4 accent-claret"
                />
                <span className="text-sm text-ink-mute">Trust this device for 30 days</span>
              </label>

              <button
                type="submit"
                disabled={twoFactorLoading || (!useBackupCode && twoFactorCode.length !== 6) || (useBackupCode && twoFactorCode.length < 8)}
                className="w-full py-3 bg-ink text-paper font-medium hover:bg-claret transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {twoFactorLoading ? 'Verifying...' : 'Verify'}
              </button>
            </form>

            <div className="mt-4 flex justify-between text-sm">
              <button
                onClick={() => { setUseBackupCode(!useBackupCode); setTwoFactorCode(''); setTwoFactorError(''); }}
                className="text-claret hover:underline"
              >
                {useBackupCode ? 'Use authenticator app' : 'Use a backup code'}
              </button>
              <button
                onClick={() => { cancel2FA(); setTwoFactorCode(''); setTwoFactorError(''); setUseBackupCode(false); }}
                className="text-ink-mute hover:text-ink"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 bg-ink/60 flex items-center justify-center z-50 p-4">
      <div className="bg-paper rounded max-w-md w-full overflow-hidden border border-rule">
        {/* Header */}
        <div className="px-6 py-5 border-b border-rule flex justify-between items-center">
          <h2 className="font-display text-xl text-ink" style={{ fontVariationSettings: '"opsz" 48' }}>
            {mode === 'login' ? 'Welcome Back' : 'Start Your Free Trial'}
          </h2>
          <button
            onClick={onClose}
            className="text-ink-light hover:text-ink transition-colors"
          >
            <X size={22} />
          </button>
        </div>

        {/* Content */}
        <div className="p-6">
          {/* OAuth buttons */}
          <div className="space-y-3 mb-6">
            <div id="google-signin-button" className="w-full">
              <button
                onClick={handleGoogleLogin}
                className="w-full flex items-center justify-center gap-3 px-4 py-3 border border-rule hover:bg-paper-deep transition-colors rounded"
              >
                <Chrome size={20} className="text-ink-light" />
                <span className="font-medium text-ink-mute">Continue with Google</span>
              </button>
            </div>
            <button
              onClick={handleAppleLogin}
              className="w-full flex items-center justify-center gap-3 px-4 py-3 border border-ink text-ink hover:bg-paper-deep transition-colors rounded"
            >
              <Apple size={20} />
              <span className="font-medium">Continue with Apple</span>
            </button>
          </div>

          {/* Divider */}
          <div className="relative mb-6">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-rule"></div>
            </div>
            <div className="relative flex justify-center text-sm">
              <span className="px-3 bg-paper text-ink-light">or continue with email</span>
            </div>
          </div>

          {/* Error message */}
          {(localError || error) && (
            <div className="mb-4 p-3 bg-negative/10 border border-negative/30 text-negative text-sm">
              {localError || error}
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            {mode === 'register' && (
              <div>
                <label className="block text-sm font-medium text-ink-mute mb-1">Full Name</label>
                <div className="relative">
                  <User size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-light" />
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="John Doe"
                    className="w-full pl-10 pr-4 py-3 border border-rule-dark bg-paper-card focus:outline-none focus:border-ink"
                  />
                </div>
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-ink-mute mb-1">Email</label>
              <div className="relative">
                <Mail size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-light" />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  required
                  className="w-full pl-10 pr-4 py-3 border border-rule-dark bg-paper-card focus:outline-none focus:border-ink"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-ink-mute mb-1">Password</label>
              <div className="relative">
                <Lock size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-light" />
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                  minLength={8}
                  className="w-full pl-10 pr-12 py-3 border border-rule-dark bg-paper-card focus:outline-none focus:border-ink"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-ink-light hover:text-ink"
                >
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
              {mode === 'register' && (
                <p className="text-xs text-ink-light mt-1">Must be at least 8 characters</p>
              )}
              {mode === 'login' && (
                <div className="text-right mt-1">
                  <button
                    type="button"
                    onClick={() => {
                      onClose();
                      window.location.href = '/forgot-password';
                    }}
                    className="text-xs text-claret hover:underline"
                  >
                    Forgot password?
                  </button>
                </div>
              )}
            </div>

            {/* Turnstile widget for registration */}
            {mode === 'register' && TURNSTILE_SITE_KEY && (
              <div className="flex justify-center">
                <div ref={turnstileRef}></div>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 bg-ink text-paper font-medium hover:bg-claret transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  {mode === 'login' ? 'Signing in...' : 'Setting up trial...'}
                </span>
              ) : (
                mode === 'login' ? 'Sign In' : 'Start 7-Day Free Trial'
              )}
            </button>
          </form>

          {/* Toggle mode */}
          <div className="mt-6 text-center text-sm text-ink-mute">
            {mode === 'login' ? (
              <>
                Don't have an account?{' '}
                <button
                  onClick={() => setMode('register')}
                  className="text-claret hover:underline font-medium"
                >
                  Start free trial
                </button>
              </>
            ) : (
              <>
                Already have an account?{' '}
                <button
                  onClick={() => setMode('login')}
                  className="text-claret hover:underline font-medium"
                >
                  Sign in
                </button>
              </>
            )}
          </div>

          {/* Trial info */}
          {mode === 'register' && (
            <div className="mt-4 py-2.5 border-t border-b border-rule text-center">
              <p className="text-sm text-positive font-medium">
                7-day free trial &middot; Credit card required
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
