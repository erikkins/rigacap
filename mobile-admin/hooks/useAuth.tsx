/**
 * Auth context for the admin app — email/password + 2FA, admin-gated.
 */

import React, { createContext, useContext, useEffect, useState } from 'react';
import {
  AuthUser,
  getProfile,
  hasStoredTokens,
  login as authLogin,
  logout as authLogout,
  verify2FA as authVerify2FA,
} from '@/services/auth';
import { registerForPushNotifications } from '@/services/notifications';

interface AuthContextType {
  user: AuthUser | null;
  isLoading: boolean;
  twoFactorRequired: boolean;
  login: (email: string, password: string) => Promise<void>;
  verify2FA: (code: string, trustDevice: boolean, isBackupCode: boolean) => Promise<void>;
  cancel2FA: () => void;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [twoFactorRequired, setTwoFactorRequired] = useState(false);
  const [challengeToken, setChallengeToken] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        if (await hasStoredTokens()) {
          const profile = await getProfile(); // throws if not admin
          setUser(profile);
          registerForPushNotifications().catch(() => {});
        }
      } catch {
        // expired / invalid / not-admin — stay logged out and clear tokens
        await authLogout().catch(() => {});
      } finally {
        setIsLoading(false);
      }
    })();
  }, []);

  const login = async (email: string, password: string) => {
    const result = await authLogin(email, password);
    if (result.requires_2fa && result.challenge_token) {
      setChallengeToken(result.challenge_token);
      setTwoFactorRequired(true);
      return;
    }
    if (result.user) {
      setUser(result.user);
      registerForPushNotifications().catch(() => {});
    }
  };

  const verify2FA = async (code: string, trustDevice: boolean, isBackupCode: boolean) => {
    if (!challengeToken) throw new Error('No 2FA challenge active');
    const u = await authVerify2FA(challengeToken, code, trustDevice, isBackupCode);
    setUser(u);
    setTwoFactorRequired(false);
    setChallengeToken(null);
    registerForPushNotifications().catch(() => {});
  };

  const cancel2FA = () => {
    setTwoFactorRequired(false);
    setChallengeToken(null);
  };

  const logout = async () => {
    await authLogout();
    setUser(null);
    setTwoFactorRequired(false);
    setChallengeToken(null);
  };

  return (
    <AuthContext.Provider
      value={{ user, isLoading, twoFactorRequired, login, verify2FA, cancel2FA, logout }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
