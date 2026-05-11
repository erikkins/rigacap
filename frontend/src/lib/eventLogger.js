// Per-user usage event logger.
//
// Batches client-side events and flushes them to POST /api/events/log
// on a debounce + on page unload (via sendBeacon, which fires reliably
// during unload events when fetch/XHR would be aborted).
//
// Usage:
//   import { logEvent } from './lib/eventLogger';
//   logEvent('signal_click', { symbol: 'NVDA', source: 'dashboard' });
//
// The hook is intentionally NOT a React hook — events fire from arbitrary
// callbacks all over the tree, and we don't want every component to need
// useEventLogger. A module-level singleton is the right primitive.

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const ENDPOINT = `${API_BASE}/api/events/log`;
const FLUSH_INTERVAL_MS = 8000;     // debounce window — flush at most every 8s
const MAX_BATCH = 25;               // flush early if batch grows past this
const SESSION_KEY = 'rigacap_session_id';

// Stable session ID for this tab. Persists across reloads (sessionStorage),
// dies when the tab closes — matches the natural "session" boundary.
const getSessionId = () => {
  try {
    let sid = sessionStorage.getItem(SESSION_KEY);
    if (!sid) {
      sid = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
      sessionStorage.setItem(SESSION_KEY, sid);
    }
    return sid;
  } catch {
    return null; // private mode / disabled storage
  }
};

let queue = [];
let flushTimer = null;

const getAuthHeader = () => {
  try {
    const token = localStorage.getItem('accessToken');
    return token ? { Authorization: `Bearer ${token}` } : {};
  } catch {
    return {};
  }
};

const doFlush = (useBeacon = false) => {
  if (!queue.length) return;
  const batch = queue.splice(0, queue.length);
  const body = JSON.stringify({ events: batch });
  const auth = getAuthHeader();
  // No auth = user not logged in; drop the batch silently
  if (!auth.Authorization) return;

  if (useBeacon && navigator.sendBeacon) {
    // sendBeacon doesn't let us set headers other than Content-Type, so
    // we encode the access token into the body as a fallback. The
    // server side accepts the standard Authorization header from fetch
    // but also reads from body._auth as a beacon-only fallback.
    // Simpler: just use fetch with keepalive, which also survives unload.
    try {
      fetch(ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...auth },
        body,
        keepalive: true,
      });
    } catch {
      // best-effort, swallow
    }
    return;
  }

  // Standard async path
  fetch(ENDPOINT, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...auth },
    body,
  }).catch(() => {
    // never fail the UI on logging errors
  });
};

const scheduleFlush = () => {
  if (flushTimer) return;
  flushTimer = setTimeout(() => {
    flushTimer = null;
    doFlush(false);
  }, FLUSH_INTERVAL_MS);
};

export const logEvent = (eventType, payload = null) => {
  if (!eventType) return;
  try {
    queue.push({
      event_type: eventType,
      payload,
      path: typeof window !== 'undefined' ? window.location.pathname : null,
      session_id: getSessionId(),
      client_ts: new Date().toISOString(),
    });
    if (queue.length >= MAX_BATCH) {
      if (flushTimer) {
        clearTimeout(flushTimer);
        flushTimer = null;
      }
      doFlush(false);
    } else {
      scheduleFlush();
    }
  } catch {
    // never throw from logging
  }
};

// Flush on page unload — best chance the in-flight queue survives the close.
if (typeof window !== 'undefined') {
  window.addEventListener('pagehide', () => doFlush(true));
  window.addEventListener('beforeunload', () => doFlush(true));
  // Also flush when tab becomes hidden — bfcache-aware browsers
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') doFlush(true);
  });
}
