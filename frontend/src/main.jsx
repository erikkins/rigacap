import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App.jsx'
import './index.css'

// Matches the errors thrown when a deploy replaces hashed JS chunks under an
// already-open tab (the lazy import 404s). These are transient — a reload fetches
// the fresh index.html + chunks — so we auto-recover instead of showing an error.
const CHUNK_ERROR_RE = /Loading chunk|dynamically imported module|Importing a module script failed|Failed to fetch dynamically/i;
const isChunkError = (error) =>
  error?.name === 'ChunkLoadError' || CHUNK_ERROR_RE.test(error?.message || '');

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error, info) {
    console.error('ErrorBoundary caught:', error, info);
    // Stale-chunk-during-deploy: reload once to pick up the new build. The
    // timestamp guard prevents a reload loop if it's NOT actually a deploy
    // (still chunk-errors within 12s → fall through to the branded fallback),
    // while still allowing recovery from a later deploy.
    if (isChunkError(error)) {
      try {
        const last = Number(sessionStorage.getItem('rc_chunk_reload_ts')) || 0;
        if (Date.now() - last > 12000) {
          sessionStorage.setItem('rc_chunk_reload_ts', String(Date.now()));
          window.location.reload();
        }
      } catch (_) {
        window.location.reload();
      }
    }
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '100vh', background: '#F5F1E8', color: '#141210', fontFamily: "'IBM Plex Sans', system-ui, sans-serif", padding: '2rem', textAlign: 'center' }}>
          <div style={{ fontFamily: "'Fraunces', Georgia, serif", fontSize: '1.75rem', fontWeight: 600, letterSpacing: '-0.01em', marginBottom: '0.9rem' }}>RigaCap</div>
          <p style={{ fontSize: '1.05rem', color: '#3a342c', marginBottom: '0.4rem', maxWidth: '30rem' }}>Something interrupted this page.</p>
          <p style={{ fontSize: '0.95rem', color: '#8a8073', marginBottom: '1.75rem', maxWidth: '30rem', lineHeight: 1.55 }}>This usually clears with a quick reload &mdash; often it's just a fresh version of the site coming online.</p>
          <button
            onClick={() => window.location.reload()}
            style={{ padding: '0.8rem 2.2rem', background: '#7A2430', color: '#F5F1E8', border: 'none', borderRadius: '2px', fontWeight: 600, cursor: 'pointer', fontSize: '1rem', fontFamily: "'IBM Plex Sans', system-ui, sans-serif" }}
          >
            Reload
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

// Vite fires this when a lazy chunk fails to load (typically right after a deploy
// swapped the hashed files under an open tab). Reload once to fetch the new build —
// catches it before it ever reaches the ErrorBoundary fallback above.
window.addEventListener('vite:preloadError', () => {
  try {
    const last = Number(sessionStorage.getItem('rc_chunk_reload_ts')) || 0;
    if (Date.now() - last > 12000) {
      sessionStorage.setItem('rc_chunk_reload_ts', String(Date.now()));
      window.location.reload();
    }
  } catch (_) {
    window.location.reload();
  }
});

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ErrorBoundary>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </ErrorBoundary>
  </React.StrictMode>,
)
