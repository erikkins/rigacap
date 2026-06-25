/**
 * Admin app configuration.
 */

export const API_URL = 'https://api.rigacap.com';

// The admin app is email/password only — no social sign-in. Access is gated
// on user.role === 'admin' after login (see services/auth.ts + hooks/useAuth).
