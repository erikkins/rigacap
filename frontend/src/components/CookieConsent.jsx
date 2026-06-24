import React, { useState, useEffect } from 'react';

const CONSENT_KEY = 'rigacap_cookie_consent';

// Consent Mode v2: gtag is loaded in index.html with consent default-DENIED, so
// analytics already fires in cookieless/modeled mode. This banner only flips the
// consent SIGNAL — it no longer controls whether tracking loads. Accept → grant
// (full cookie-based tracking); Decline → stays denied (cookieless modeling
// continues, GDPR-compliant). Either way we can now see paid traffic + funnel drop-off.
function updateConsent(granted) {
  if (typeof window.gtag !== 'function') return;
  const v = granted ? 'granted' : 'denied';
  window.gtag('consent', 'update', {
    ad_storage: v,
    ad_user_data: v,
    ad_personalization: v,
    analytics_storage: v,
  });
}

export default function CookieConsent() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const consent = localStorage.getItem(CONSENT_KEY);
    if (consent === 'accepted') {
      updateConsent(true);   // re-affirm (index.html already granted on first load)
    } else if (!consent) {
      setVisible(true);
    }
  }, []);

  const accept = () => {
    localStorage.setItem(CONSENT_KEY, 'accepted');
    updateConsent(true);
    setVisible(false);
  };

  const decline = () => {
    localStorage.setItem(CONSENT_KEY, 'declined');
    updateConsent(false);
    setVisible(false);
  };

  if (!visible) return null;

  return (
    <div className="fixed bottom-0 inset-x-0 z-50 bg-ink/95 backdrop-blur-sm border-t border-rule-dark px-4 py-4">
      <div className="max-w-4xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-3">
        <p className="text-sm text-paper/80 text-center sm:text-left font-body">
          We use cookies for analytics to improve your experience.{' '}
          <a href="/privacy" className="text-claret-light underline underline-offset-2 decoration-1 hover:text-paper">
            Privacy Policy
          </a>
        </p>
        <div className="flex gap-2 shrink-0">
          <button
            onClick={decline}
            className="px-4 py-1.5 text-sm text-paper/60 hover:text-paper border border-paper/20 hover:border-paper/40 transition-colors font-body"
          >
            Decline
          </button>
          <button
            onClick={accept}
            className="px-4 py-1.5 text-sm text-ink bg-paper hover:bg-paper-deep font-medium transition-colors font-body"
          >
            Accept
          </button>
        </div>
      </div>
    </div>
  );
}
