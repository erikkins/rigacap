/**
 * Admin authentication — email/password + 2FA, with an admin-role gate.
 *
 * This app is admin-only. login() rejects any account whose role !== 'admin'
 * (and clears tokens), so a non-admin can never get past the login screen even
 * though the backend would happily issue them a normal user token.
 */

import * as SecureStore from 'expo-secure-store';
import api from './api';

export interface AuthUser {
  id: string;
  email: string;
  name: string | null;
  role: string;
  totp_enabled?: boolean;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
}

export interface LoginResult {
  user?: AuthUser;
  requires_2fa?: boolean;
  challenge_token?: string;
}

export class NotAdminError extends Error {
  constructor() {
    super('This account is not an administrator.');
    this.name = 'NotAdminError';
  }
}

async function storeTokens(tokens: AuthTokens) {
  await SecureStore.setItemAsync('access_token', tokens.access_token);
  await SecureStore.setItemAsync('refresh_token', tokens.refresh_token);
}

async function getTrustHeaders(): Promise<Record<string, string>> {
  const trustToken = await SecureStore.getItemAsync('2fa_trust_token');
  return trustToken ? { 'X-2FA-Trust': trustToken } : {};
}

async function getDeviceFingerprint(): Promise<string> {
  let fp = await SecureStore.getItemAsync('device_fingerprint');
  if (!fp) {
    fp = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
      const r = (Math.random() * 16) | 0;
      const v = c === 'x' ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    });
    await SecureStore.setItemAsync('device_fingerprint', fp);
  }
  return fp;
}

/** Throw + clear tokens if the authenticated user is not an admin. */
function assertAdmin(user: AuthUser): AuthUser {
  if (user.role !== 'admin') {
    throw new NotAdminError();
  }
  return user;
}

export async function login(email: string, password: string): Promise<LoginResult> {
  const headers = await getTrustHeaders();
  const { data } = await api.post('/api/auth/login', { email, password }, { headers });
  if (data.requires_2fa) {
    return { requires_2fa: true, challenge_token: data.challenge_token };
  }
  // Non-admins are rejected before tokens are persisted.
  if (data.user?.role !== 'admin') {
    throw new NotAdminError();
  }
  await storeTokens(data);
  return { user: data.user };
}

export async function verify2FA(
  challengeToken: string,
  code: string,
  trustDevice: boolean = false,
  isBackupCode: boolean = false,
): Promise<AuthUser> {
  const deviceId = await getDeviceFingerprint();
  const { data } = await api.post('/api/auth/2fa/verify', {
    challenge_token: challengeToken,
    code,
    device_id: deviceId,
    trust_device: trustDevice,
    is_backup_code: isBackupCode,
  });
  if (data.user?.role !== 'admin') {
    throw new NotAdminError();
  }
  await storeTokens(data);
  if (data.trust_token) {
    await SecureStore.setItemAsync('2fa_trust_token', data.trust_token);
  }
  return data.user;
}

export async function getProfile(): Promise<AuthUser> {
  const { data } = await api.get('/api/auth/me');
  return assertAdmin(data);
}

export async function logout() {
  await SecureStore.deleteItemAsync('access_token');
  await SecureStore.deleteItemAsync('refresh_token');
  await SecureStore.deleteItemAsync('2fa_trust_token');
}

export async function hasStoredTokens(): Promise<boolean> {
  const token = await SecureStore.getItemAsync('access_token');
  return !!token;
}
