import React, { useState, useEffect, useRef } from 'react';
import { X, Mail, Lock, User, Eye, EyeOff, Chrome, Apple, Shield } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { logPublicEvent } from '../lib/publicEvent';

const TURNSTILE_SITE_KEY = import.meta.env.VITE_TURNSTILE_SITE_KEY;
const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID;
// Sentinel sent ONLY when the Turnstile challenge couldn't load (in-app webview). The backend
// recognizes it, skips Turnstile, and falls back to rate-limit + email verification. Must match
// TURNSTILE_FAILSAFE_TOKEN in backend/app/api/auth.py.
const TURNSTILE_FAILSAFE_TOKEN = 'inapp-webview-unavailable';

// In-app browsers (LinkedIn, Instagram, Facebook, etc.) BLOCK Google/Apple OAuth by policy — the
// redirect returns but the credential never reaches us, stranding the user on a login loop (first-
// user report: LinkedIn → phone). Detect it so we can guide them to a real browser instead.
const isInAppBrowser = () => {
  if (typeof navigator === 'undefined') return false;
  const ua = navigator.userAgent || '';
  return /(LinkedInApp|FBAN|FBAV|FB_IAB|Instagram|Twitter|Line\/|MicroMessenger|WhatsApp|Snapchat|TikTok|musical_ly|Pinterest|\bGSA\b)/i.test(ua)
      || (/Android/.test(ua) && /; wv\)/.test(ua));   // generic Android WebView
};

// iOS gives no programmatic way out of an in-app webview; Android does (intent:// → default browser,
// where Google/Apple OAuth works). So the escape UX is platform-split.
const isIOS = () => {
  if (typeof navigator === 'undefined') return false;
  const ua = navigator.userAgent || '';
  return /iPhone|iPad|iPod/i.test(ua)
      || (/Macintosh/.test(ua) && typeof document !== 'undefined' && 'ontouchend' in document);
};
// Escape the in-app webview into the default browser. Landing URL carries ?signin=1 so the login
// modal auto-reopens there (see the ?signin handler on the landing/door pages).
const androidBrowserIntent = (url) =>
  `intent://${url.replace(/^https?:\/\//, '')}#Intent;scheme=https;action=android.intent.action.VIEW;end`;

export default function LoginModal({ isOpen = true, onClose, onSuccess, initialMode = 'login', selectedPlan = 'monthly' }) {
  const { login, register, loginWithGoogle, loginWithApple, verify2FA, cancel2FA, twoFactorRequired, error, clearError } = useAuth();
  const [mode, setMode] = useState(initialMode);
  const [twoFactorCode, setTwoFactorCode] = useState('');
  const [trustDevice, setTrustDevice] = useState(false);
  const [useBackupCode, setUseBackupCode] = useState(false);
  const [twoFactorLoading, setTwoFactorLoading] = useState(false);
  const [twoFactorError, setTwoFactorError] = useState('');
  const twoFactorInputRef = useRef(null);

  // Free-first (project_free_first_spec §7): registration creates a FREE account and lands in the
  // free view — it must NEVER seed a checkout plan or auto-route to Stripe (the App auto-checkout
  // effect consumes rigacap_selected_plan). The card is asked for ONLY at explicit upgrade.
  const [regStep, setRegStep] = useState(1);  // register is two-step: 1 = email, 2 = password
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [localError, setLocalError] = useState('');
  const [turnstileToken, setTurnstileToken] = useState('');
  const [turnstileUnavailable, setTurnstileUnavailable] = useState(false);  // widget couldn't load (webview)
  const turnstileRef = useRef(null);
  // Soft-conversion: capture cold visitors who aren't ready for a trial into the
  // free newsletter instead of letting them leave (Erik Jun 23 — "never let them
  // leak if they've come to visit").
  const [newsletterBusy, setNewsletterBusy] = useState(false);
  const [newsletterDone, setNewsletterDone] = useState(false);
  const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';
  const subscribeToNewsletter = async () => {
    const e = email.trim();
    if (!e || !e.includes('@')) { setLocalError('Enter your email above to follow the newsletter.'); return; }
    setNewsletterBusy(true); setLocalError('');
    try {
      const res = await fetch(`${API_BASE}/api/public/subscribe-newsletter`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: e, turnstile_token: turnstileToken || 'dev-bypass', report_type: 'market_measured', source: 'signup_modal_soft' }),
      });
      if (res.ok) setNewsletterDone(true);
      else setLocalError('Could not subscribe — please try again.');
    } catch { setLocalError('Could not subscribe — please try again.'); }
    finally { setNewsletterBusy(false); }
  };

  const [inAppBrowser] = useState(() => isInAppBrowser());
  const [iosDevice] = useState(() => isIOS());
  const [linkCopied, setLinkCopied] = useState(false);
  const [gisReady, setGisReady] = useState(false);

  // Reopen THIS page (door context preserved) in the real browser with ?signin=1 so the modal
  // auto-reopens there and OAuth works. Only used when we're stuck inside an in-app browser.
  const escapeUrl = (() => {
    try { const u = new URL(window.location.href); u.searchParams.set('signin', '1'); return u.toString(); }
    catch { return 'https://rigacap.com/?signin=1'; }
  })();
  const copyEscapeLink = async () => {
    logPublicEvent('oauth_inapp_escape_copy');
    try { await navigator.clipboard.writeText(escapeUrl); setLinkCopied(true); setTimeout(() => setLinkCopied(false), 3000); }
    catch { /* clipboard blocked — user can long-press the address bar to copy */ }
  };

  // Reset form when modal opens/closes
  useEffect(() => {
    if (isOpen) {
      logPublicEvent('signup_modal_open');   // auth-funnel base: modal opened from ANY entry point
      setEmail('');
      setPassword('');
      setName('');
      setLocalError('');
      clearError();
      setTurnstileToken('');
      setMode(initialMode); // Reset mode based on visitor type
      setRegStep(1);        // always start registration at the email step
    }
  }, [isOpen, clearError, initialMode]);

  // Advance the two-step register flow: validate the email, capture it into the newsletter NOW
  // (before the password) so an abandoned signup is still a lead (fire-and-forget), then step to
  // the password. (project_free_first_spec §6/§7)
  const handleContinue = (e) => {
    e.preventDefault();
    const em = email.trim();
    if (!em || !em.includes('@')) { setLocalError('Enter a valid email to continue.'); return; }
    setLocalError('');
    try {
      fetch(`${API_BASE}/api/public/subscribe-newsletter`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: em, turnstile_token: turnstileToken || 'dev-bypass', report_type: 'market_measured', source: 'signup_step1' }),
      }).catch(() => {});
    } catch { /* never block advancing on a beacon failure */ }
    setRegStep(2);
  };

  // Load Turnstile widget (register step 2, where the password + create button live)
  useEffect(() => {
    if (!isOpen || !TURNSTILE_SITE_KEY || mode !== 'register' || regStep !== 2) return;
    setTurnstileUnavailable(false);

    const loadTurnstile = () => {
      if (window.turnstile && turnstileRef.current) {
        window.turnstile.render(turnstileRef.current, {
          sitekey: TURNSTILE_SITE_KEY,
          callback: (token) => { setTurnstileToken(token); setTurnstileUnavailable(false); },
          // The challenge iframe often can't load inside in-app webviews — flag it so submit shows
          // a real path forward instead of a dead-end "complete the verification".
          'error-callback': () => { setTurnstileToken(''); setTurnstileUnavailable(true); },
          'timeout-callback': () => { setTurnstileToken(''); setTurnstileUnavailable(true); },
          'expired-callback': () => setTurnstileToken(''),
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
      // If the Cloudflare script never arrives (webview blocked it), stop pretending it will.
      const giveUp = setTimeout(() => {
        clearInterval(checkInterval);
        if (!window.turnstile) setTurnstileUnavailable(true);
      }, 7000);
      return () => { clearInterval(checkInterval); clearTimeout(giveUp); };
    }
  }, [isOpen, mode, regStep]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setLocalError('');

    try {
      if (mode === 'register') {
        logPublicEvent('signup_submit');   // funnel: register attempt made — logged BEFORE the
                                           // Turnstile gate so hard-blocks are visible, not silent.
        if (!turnstileToken && TURNSTILE_SITE_KEY && !turnstileUnavailable) {
          // Widget is present but the user hasn't solved it yet — soft-block and wait.
          logPublicEvent('signup_turnstile_incomplete');
          setLocalError('Please complete the verification');
          setLoading(false);
          return;
        }
        // Fail-safe: when the challenge genuinely couldn't load (in-app webview), proceed with a
        // sentinel. The backend skips Turnstile for it but STILL enforces rate-limit (3/min/IP) +
        // mandatory email verification, so a bot gains only an inert, unverified row.
        const tsToken = turnstileToken || (turnstileUnavailable ? TURNSTILE_FAILSAFE_TOKEN : 'dev-bypass');
        if (!turnstileToken && turnstileUnavailable) logPublicEvent('signup_turnstile_failsafe');
        const result = await register(email, password, name, tsToken);
        if (result.success) {
          logPublicEvent('signup_success'); // funnel: account created
          if (!result.redirecting) {
            onSuccess ? onSuccess() : onClose();
          }
        } else {
          logPublicEvent('signup_register_fail');   // credential/backend rejection (dupe email, etc.)
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
    logPublicEvent('oauth_google_click');   // client-side visibility into OAuth attempts
    if (!GOOGLE_CLIENT_ID) {
      logPublicEvent('oauth_google_error');
      setLocalError('Google Sign-In is not configured.');
      return;
    }

    try {
      const google = window.google;
      if (!google?.accounts?.id) {
        logPublicEvent('oauth_google_error');
        setLocalError('Google Sign-In SDK not loaded. Please refresh and try again.');
        return;
      }

      google.accounts.id.initialize({
        client_id: GOOGLE_CLIENT_ID,
        callback: async (response) => {
          if (response.credential) {
            setLoading(true);
            if (mode === 'register') logPublicEvent('signup_submit');
            const result = await loginWithGoogle(response.credential);
            setLoading(false);
            if (result.success) {
              if (mode === 'register') logPublicEvent('signup_success');
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
      logPublicEvent('oauth_google_error');
      console.error('Google login error:', err);
      setLocalError('Google Sign-In failed. Please try again.');
    }
  };

  // Shared credential handler for both the rendered GIS button and the click fallback.
  const handleGoogleCredential = async (credential) => {
    if (!credential) return;
    logPublicEvent('oauth_google_credential');   // account picked, Google returned to us
    setLoading(true);
    if (mode === 'register') logPublicEvent('signup_submit');
    const result = await loginWithGoogle(credential);
    setLoading(false);
    if (result.success) {
      logPublicEvent('oauth_google_success');
      if (mode === 'register') logPublicEvent('signup_success');
      if (result.requires_2fa) return;
      if (!result.redirecting) { onSuccess ? onSuccess() : onClose(); }
    } else {
      logPublicEvent('oauth_google_backend_fail');   // credential OK but our /auth/google rejected it
      setLocalError(result.error || 'Google login failed');
    }
  };

  // Register the Google callback + render the official GIS button ON MOUNT (not on click), so the
  // credential is always captured — including after a mobile redirect — instead of stranding the
  // user on the login screen in a loop. Skipped in in-app browsers (OAuth is blocked there anyway).
  useEffect(() => {
    if (!isOpen || inAppBrowser || !GOOGLE_CLIENT_ID) return;
    if (!(mode === 'login' || regStep === 1)) return;
    let cancelled = false;
    const init = () => {
      const google = window.google;
      if (!google?.accounts?.id) return false;
      try {
        google.accounts.id.initialize({
          client_id: GOOGLE_CLIENT_ID,
          callback: (resp) => handleGoogleCredential(resp?.credential),
          ux_mode: 'popup',
        });
        const el = document.getElementById('google-signin-button');
        if (el) {
          el.innerHTML = '';
          google.accounts.id.renderButton(el, {
            theme: 'outline', size: 'large', width: '300',
            text: mode === 'register' ? 'signup_with' : 'continue_with',
          });
          if (!gisReady) logPublicEvent('oauth_google_rendered');   // SDK loaded + button shown
          setGisReady(true);
        }
      } catch (e) {
        console.error('GIS init/render failed:', e);
        return false;
      }
      return true;
    };
    if (init()) return;
    // GIS script loads async — poll briefly until window.google is ready.
    let done = false;
    const iv = setInterval(() => {
      if (cancelled || done) { clearInterval(iv); return; }
      if (init()) { done = true; clearInterval(iv); }
    }, 200);
    const to = setTimeout(() => {
      if (!done && !cancelled) { clearInterval(iv); logPublicEvent('oauth_google_sdk_timeout'); }
    }, 6000);
    return () => { cancelled = true; clearInterval(iv); clearTimeout(to); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, inAppBrowser, mode, regStep]);

  // Visibility into the in-app-browser wall — how many arrive in a webview where OAuth can't work.
  useEffect(() => {
    if (isOpen && inAppBrowser) logPublicEvent('oauth_inapp_blocked');
  }, [isOpen, inAppBrowser]);

  const handleAppleLogin = async () => {
    logPublicEvent('oauth_apple_click');   // client-side visibility into OAuth attempts
    const APPLE_CLIENT_ID = import.meta.env.VITE_APPLE_CLIENT_ID;
    if (!APPLE_CLIENT_ID) {
      logPublicEvent('oauth_apple_error');
      setLocalError('Apple Sign-In is not configured.');
      return;
    }

    try {
      if (!window.AppleID) {
        logPublicEvent('oauth_apple_error');
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
      if (mode === 'register') logPublicEvent('signup_submit');
      const result = await loginWithApple(idToken, userData);
      setLoading(false);

      if (result.success) {
        logPublicEvent('oauth_apple_success');
        if (mode === 'register') logPublicEvent('signup_success');
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
      logPublicEvent('oauth_apple_error');
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
                className="w-full py-3 bg-claret text-paper font-medium hover:bg-ink transition-colors disabled:opacity-50 disabled:cursor-not-allowed rounded"
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
    <div className="fixed inset-0 bg-ink/60 flex items-center justify-center z-[60] p-4 overflow-y-auto">
      <div className="bg-paper rounded max-w-md w-full max-h-[90vh] overflow-y-auto border border-rule my-auto">
        {/* Header */}
        <div className="px-6 py-5 border-b border-rule flex justify-between items-center">
          <h2 className="font-display text-xl text-ink" style={{ fontVariationSettings: '"opsz" 48' }}>
            {mode === 'login' ? 'Welcome Back' : (regStep === 1 ? 'Create your free account' : 'Choose a password')}
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
          {(mode === 'login' || regStep === 1) && (
          <>
          {inAppBrowser ? (
            <div className="mb-6">
              <p className="text-sm text-ink-mute leading-relaxed mb-3">
                <strong className="text-ink font-medium">Create your account with email</strong> — quickest way in, right below. Takes about 20 seconds.
              </p>
              {iosDevice ? (
                <details className="rounded border border-rule bg-paper-deep text-[0.82rem] text-ink-mute"
                  onToggle={(e) => { if (e.currentTarget.open) logPublicEvent('oauth_inapp_escape_open'); }}>
                  <summary className="cursor-pointer px-3 py-2.5 text-ink font-medium list-none">Prefer Google or Apple? &rarr;</summary>
                  <div className="px-3 pb-3 leading-relaxed">
                    They can&rsquo;t run inside in-app browsers. Open this page in Safari &mdash; tap the
                    {' '}<strong className="text-ink">&middot;&middot;&middot;</strong> or <strong className="text-ink">&#x2934;</strong> menu, choose
                    {' '}<strong className="text-ink">Open in Safari</strong>, then sign in with Google or Apple there.
                    <button type="button" onClick={copyEscapeLink}
                      className="mt-3 w-full py-2 rounded border border-claret/50 text-claret text-[0.8rem] font-medium hover:bg-claret/[0.06] transition-colors">
                      {linkCopied ? 'Copied — paste in Safari' : 'Copy link for Safari'}
                    </button>
                  </div>
                </details>
              ) : (
                <a href={androidBrowserIntent(escapeUrl)}
                  onClick={() => logPublicEvent('oauth_inapp_escape_click')}
                  className="block w-full text-center py-2.5 rounded border border-claret/50 text-claret text-[0.82rem] font-medium hover:bg-claret/[0.06] transition-colors">
                  Prefer Google or Apple? Open in Chrome &rarr;
                </a>
              )}
            </div>
          ) : (
          <>
          {/* OAuth buttons */}
          <div className="space-y-3 mb-6">
            {/* GIS renders its official button into this (React-empty) div on mount. */}
            <div id="google-signin-button" className="w-full flex justify-center min-h-[44px]" />
            {!gisReady && (
              <button
                onClick={handleGoogleLogin}
                className="w-full flex items-center justify-center gap-3 px-4 py-3 border border-rule hover:bg-paper-deep transition-colors rounded"
              >
                <Chrome size={20} className="text-ink-light" />
                <span className="font-medium text-ink-mute">Continue with Google</span>
              </button>
            )}
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
          </>
          )}
          </>
          )}

          {/* Error message */}
          {(localError || error) && (
            <div className="mb-4 p-3 bg-negative/10 border border-negative/30 text-negative text-sm">
              {localError || error}
            </div>
          )}

          {/* Form */}
          <form onSubmit={mode === 'register' && regStep === 1 ? handleContinue : handleSubmit} className="space-y-4">
            {mode === 'register' && regStep === 1 && (
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

            {(mode === 'login' || regStep === 1) && (
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
            )}

            {mode === 'register' && regStep === 2 && (
              <div className="text-sm text-ink-mute">
                Signing up as <span className="text-ink font-medium">{email}</span>
                <button type="button" onClick={() => { setRegStep(1); setLocalError(''); }} className="text-claret hover:underline ml-2">change</button>
              </div>
            )}

            {(mode === 'login' || (mode === 'register' && regStep === 2)) && (
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
                  minLength={mode === 'register' ? 8 : undefined}
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
            )}

            {/* Turnstile widget for registration */}
            {mode === 'register' && regStep === 2 && TURNSTILE_SITE_KEY && (
              <div className="flex justify-center">
                <div ref={turnstileRef}></div>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 bg-claret text-paper font-medium hover:bg-ink transition-colors disabled:opacity-50 disabled:cursor-not-allowed rounded"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  {mode === 'login' ? 'Signing in…' : 'Creating your account…'}
                </span>
              ) : (
                mode === 'login' ? 'Sign In' : (regStep === 1 ? 'Continue' : 'Create free account')
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
                  Create a free account
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

          {/* Free-account assurance — no card at signup (project_free_first_spec §7) */}
          {mode === 'register' && (
            <div className="mt-4 py-2.5 border-t border-b border-rule text-center">
              <p className="text-sm text-positive font-medium">
                Free account &middot; No credit card
              </p>
              <p className="text-xs text-ink-mute mt-0.5">
                Upgrade anytime — 30-day money-back guarantee.
              </p>
            </div>
          )}

          {/* Soft conversion — don't let cold visitors leak. Offer the free
              newsletter as a no-commitment alternative (step 1 only). */}
          {mode === 'register' && regStep === 1 && (
            <div className="mt-4 text-center">
              {newsletterDone ? (
                <p className="text-sm text-positive font-medium">You're on the list — watch your inbox for the weekly read.</p>
              ) : (
                <p className="text-sm text-gray-500">
                  Not ready to commit?{' '}
                  <button
                    type="button"
                    onClick={subscribeToNewsletter}
                    disabled={newsletterBusy}
                    className="text-claret font-medium underline underline-offset-2 hover:text-ink disabled:opacity-50"
                  >
                    {newsletterBusy ? 'Subscribing…' : 'Follow the free newsletter'}
                  </button>{' '}
                  and let us earn it.
                </p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
