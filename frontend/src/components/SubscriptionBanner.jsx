import React, { useState } from 'react';
import { Clock, X, CreditCard } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { formatDate } from '../utils/formatDate';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export default function SubscriptionBanner() {
  const { user, hasValidSubscription, trialDaysRemaining, fetchWithAuth } = useAuth();
  const [dismissed, setDismissed] = useState(false);
  const [loading, setLoading] = useState(false);

  if (!user) return null;

  // NOTE: These handlers MUST be declared before the early returns below.
  // The `!user.subscription` branch (and others) reference handleUpgrade in
  // their onClick — if the handler is defined further down, that branch returns
  // before the `const` initializes, and clicking throws a TDZ ReferenceError
  // (button silently does nothing). This was breaking the primary "Start Free
  // Trial" CTA for every newly-registered, unpaid user.
  const handleUpgrade = async (plan = null) => {
    setLoading(true);
    try {
      const selectedPlan = plan || localStorage.getItem('rigacap_selected_plan') || 'monthly';
      const response = await fetchWithAuth(`${API_URL}/api/billing/create-checkout`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plan: selectedPlan }),
      });
      if (response.ok) {
        const data = await response.json();
        window.location.href = data.checkout_url;
      } else {
        const error = await response.json().catch(() => ({}));
        alert(error.detail || 'Failed to create checkout session');
      }
    } catch (err) {
      console.error('Checkout error:', err);
      alert('Failed to start checkout. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleManageSubscription = async () => {
    setLoading(true);
    try {
      const response = await fetchWithAuth(`${API_URL}/api/billing/portal`, { method: 'POST' });
      if (response.ok) {
        const data = await response.json();
        window.location.href = data.portal_url;
      } else {
        const error = await response.json().catch(() => ({}));
        alert(error.detail || 'Failed to open billing portal');
      }
    } catch (err) {
      console.error('Portal error:', err);
      alert('Failed to open billing portal. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  if (!user.subscription) {
    return (
      <div className="border border-rule-dark rounded p-5 mb-6 bg-paper-card">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <CreditCard className="text-claret flex-shrink-0" size={20} />
            <div>
              <p className="font-medium text-ink">
                Complete your signup to start your free trial
              </p>
              <p className="text-sm text-ink-mute mt-1">
                7-day free trial, then $129/month or $1,099/year
              </p>
            </div>
          </div>
          <button
            onClick={() => handleUpgrade('monthly')}
            disabled={loading}
            className="px-5 py-2.5 bg-ink text-paper font-medium rounded-[2px] hover:bg-claret transition-colors disabled:opacity-50"
          >
            {loading ? 'Loading...' : 'Start Free Trial'}
          </button>
        </div>
      </div>
    );
  }

  const subStatus = user.subscription?.status;
  const isActive = subStatus === 'active';
  const isPastDue = subStatus === 'past_due';
  const isTrialExpired = subStatus === 'trial' && trialDaysRemaining === 0;
  const isTrialExpiring = subStatus === 'trial' && trialDaysRemaining <= 3 && trialDaysRemaining > 0;

  const cancelEndDate = user.subscription?.current_period_end ? new Date(user.subscription.current_period_end) : null;
  const daysUntilCancel = cancelEndDate ? Math.ceil((cancelEndDate - new Date()) / (1000 * 60 * 60 * 24)) : null;
  const isCanceling = isActive && user.subscription?.cancel_at_period_end && daysUntilCancel !== null && daysUntilCancel <= 30;

  if (dismissed || (isActive && !isCanceling)) return null;
  if (!isTrialExpired && !isTrialExpiring && !isPastDue && !isCanceling) return null;

  const getMessage = () => {
    if (isCanceling) {
      const endDate = user.subscription?.current_period_end;
      const formatted = endDate ? formatDate(endDate, { includeYear: true }) : 'soon';
      return `Your subscription is set to cancel on ${formatted}.`;
    }
    if (isPastDue) return 'Your payment failed. Please update your payment method to continue.';
    if (isTrialExpired) return 'Your free trial has ended. Subscribe to continue using RigaCap.';
    if (trialDaysRemaining === 1) return 'Your free trial ends tomorrow.';
    return `Your free trial ends in ${trialDaysRemaining} days.`;
  };

  const isUrgent = isTrialExpired || isPastDue;

  if (isPastDue) {
    return (
      <div className="border border-negative/30 rounded p-5 mb-6 bg-negative/5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <CreditCard className="text-negative flex-shrink-0" size={20} />
            <p className="font-medium text-ink">{getMessage()}</p>
          </div>
          <button
            onClick={handleManageSubscription}
            disabled={loading}
            className="px-5 py-2.5 bg-negative text-paper font-medium rounded-[2px] hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center gap-2"
          >
            <CreditCard size={16} />
            {loading ? 'Loading...' : 'Update Payment'}
          </button>
        </div>
      </div>
    );
  }

  if (isCanceling) {
    return (
      <div className="border border-rule-dark rounded p-5 mb-6 bg-paper-deep">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Clock className="text-ink-mute flex-shrink-0" size={20} />
            <p className="font-medium text-ink">{getMessage()}</p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleManageSubscription}
              disabled={loading}
              className="px-5 py-2.5 bg-ink text-paper font-medium rounded-[2px] hover:bg-claret transition-colors disabled:opacity-50"
            >
              {loading ? 'Loading...' : 'Resubscribe'}
            </button>
            <button onClick={() => setDismissed(true)} className="p-2 text-ink-light hover:text-ink">
              <X size={18} />
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`border rounded p-5 mb-6 ${isUrgent ? 'border-claret/30 bg-claret/5' : 'border-rule-dark bg-paper-card'}`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Clock className={`flex-shrink-0 ${isUrgent ? 'text-claret' : 'text-ink-mute'}`} size={20} />
          <div>
            <p className="font-medium text-ink">{getMessage()}</p>
            <p className="text-sm text-ink-mute mt-1">
              $129/month or $1,099/year (three months free)
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => handleUpgrade('monthly')}
            disabled={loading}
            className="px-4 py-2.5 border border-rule-dark text-ink font-medium rounded-[2px] hover:border-ink transition-colors disabled:opacity-50"
          >
            Monthly
          </button>
          <button
            onClick={() => handleUpgrade('annual')}
            disabled={loading}
            className="px-4 py-2.5 bg-ink text-paper font-medium rounded-[2px] hover:bg-claret transition-colors disabled:opacity-50"
          >
            {loading ? 'Loading...' : 'Annual (Save $449)'}
          </button>
          {!isTrialExpired && (
            <button onClick={() => setDismissed(true)} className="p-2 text-ink-light hover:text-ink">
              <X size={18} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
