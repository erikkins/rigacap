import { useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Cookieless, first-party pageview beacon. Fires on every route change regardless
// of cookie consent (no cookie, no persistent ID, no PII) — this is the low-volume
// visibility GA4 can't give us, since consent-denied visits are invisible there.
// Fire-and-forget; never throws.
export default function PageViewBeacon() {
  const location = useLocation();
  const last = useRef(null);

  useEffect(() => {
    const key = location.pathname + location.search;
    if (last.current === key) return; // dedupe strict-mode double-mount / identical fires
    last.current = key;
    try {
      const p = new URLSearchParams(location.search);
      fetch(`${API_BASE}/api/public/hit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        keepalive: true,
        body: JSON.stringify({
          path: location.pathname,
          ref: document.referrer || null,
          utm_source: p.get('utm_source'),
          utm_medium: p.get('utm_medium'),
          utm_campaign: p.get('utm_campaign'),
          gclid: p.get('gclid'),
        }),
      }).catch(() => {});
    } catch (_) {
      /* never break the app over analytics */
    }
  }, [location.pathname, location.search]);

  return null;
}
