/**
 * Admin API — typed wrappers over /api/admin/* (and a couple public endpoints).
 *
 * Shapes mirror backend/app/api/admin.py response models. Endpoints that
 * aren't yet strongly typed return `any` and are read defensively in the UI.
 */

import api from './api';

// ── Growth / users ────────────────────────────────────────────────
export interface AdminStats {
  total_users: number;
  active_trials: number;
  paid_subscribers: number;
  expired_trials: number;
  disabled_users: number;
  new_users_today: number;
  new_users_week: number;
  mrr: number;
}

export interface UserSummary {
  id: string;
  email: string;
  name: string | null;
  role: string;
  is_active: boolean;
  created_at: string;
  last_login: string | null;
  subscription_status: string | null;
  trial_days_remaining: number | null;
  is_founding: boolean;
}

export interface UserList {
  users: UserSummary[];
  total: number;
  page: number;
  per_page: number;
}

export async function getStats(): Promise<AdminStats> {
  const { data } = await api.get('/api/admin/stats');
  return data;
}

export async function getUsers(page = 1, perPage = 50): Promise<UserList> {
  const { data } = await api.get('/api/admin/users', {
    params: { page, per_page: perPage },
  });
  return data;
}

// ── Pipeline / service health ─────────────────────────────────────
export interface ServiceStatus {
  overall_status: string;
  services: Record<string, any>;
  metrics: Record<string, any>;
}

export async function getServiceStatus(): Promise<ServiceStatus> {
  const { data } = await api.get('/api/admin/service-status');
  return data;
}

// ── Live model portfolio ──────────────────────────────────────────
export async function getModelPortfolio(): Promise<any> {
  const { data } = await api.get('/api/admin/model-portfolio');
  return data;
}

export async function getCurrentRegime(): Promise<any> {
  const { data } = await api.get('/api/admin/market-regime/current');
  return data;
}

// ── Founding-seat counter (public endpoint) ───────────────────────
export interface FoundingStatus {
  seats_taken?: number;
  seats_total?: number;
  seats_remaining?: number;
  price?: number;
  is_open?: boolean;
  [k: string]: any;
}

export async function getFoundingStatus(): Promise<FoundingStatus> {
  const { data } = await api.get('/api/billing/founding-status');
  return data;
}

// ── Ads summary (milestone 2 — backend endpoint not built yet) ─────
// Returns null if the endpoint doesn't exist yet (404), so the Ads tab can
// render a "not configured" state without crashing.
export interface AdsSummary {
  spend?: number;
  clicks?: number;
  impressions?: number;
  conversions?: number;
  cpc?: number;
  date_range?: string;
  campaigns?: Array<Record<string, any>>;
  [k: string]: any;
}

export async function getAdsSummary(): Promise<AdsSummary | null> {
  try {
    const { data } = await api.get('/api/admin/ads/summary');
    return data;
  } catch (err: any) {
    if (err?.response?.status === 404) return null;
    throw err;
  }
}
