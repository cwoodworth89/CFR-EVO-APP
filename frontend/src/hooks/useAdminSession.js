import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { apiClient } from '../apiClient';

/**
 * The admin unlock, one state for the whole app.
 *
 * Operator, 2026-09-08: the arrival point and the Street View saves are operator rulings
 * on a shared screen, not crew controls, and the review screen is admin-only. So there is
 * one padlock in the workstation header (hud/AdminLock.jsx); unlocking it with the admin
 * password reveals every admin control, and the unlock lasts 30 days unless LOCK is
 * pressed. An auto-lock is a production feature, not built.
 *
 * The state is the API's answer about the stored token (apiClient.auth.getSession), never
 * a guess: `checked` is false until the first answer, so nothing bounces or reveals itself
 * on a stale assumption, and an unreachable API reads as locked.
 */
export const AdminSessionContext = createContext(null);

const LOCKED = { checked: false, unlocked: false, user: null };

/** The provider's state. Components read it through useAdminSession(). */
export function useAdminSessionState() {
  const [state, setState] = useState(LOCKED);

  const refresh = useCallback(() => apiClient.auth.getSession().then(({ data }) => {
    setState({ checked: true, unlocked: !!data.session, user: data.session?.user ?? null });
  }), []);

  useEffect(() => {
    refresh();
    // A token change here (setToken fires cfr-auth-change) or in another tab (storage);
    // a token kept through an outage is re-checked when the network is back.
    const onStorage = (e) => { if (e.key === 'cfr_auth_token') refresh(); };
    window.addEventListener('storage', onStorage);
    window.addEventListener('cfr-auth-change', refresh);
    window.addEventListener('online', refresh);
    return () => {
      window.removeEventListener('storage', onStorage);
      window.removeEventListener('cfr-auth-change', refresh);
      window.removeEventListener('online', refresh);
    };
  }, [refresh]);

  const unlock = useCallback(async (password) => {
    const { data, error } = await apiClient.auth.signInWithPassword({ username: 'cfradmin', password });
    if (error) throw error;
    setState({ checked: true, unlocked: true, user: data.session.user });
  }, []);

  const lock = useCallback(async () => {
    await apiClient.auth.signOut();
    setState({ checked: true, unlocked: false, user: null });
  }, []);

  return { ...state, unlock, lock, refresh };
}

// Outside a provider (a panel rendered alone, a test): locked, and honest about it.
const NO_PROVIDER = {
  ...LOCKED,
  checked: true,
  unlock: async () => { throw new Error('No AdminSessionProvider above this component'); },
  lock: async () => {},
  refresh: async () => {},
};

/** { checked, unlocked, user, unlock(password), lock(), refresh() } */
export function useAdminSession() {
  return useContext(AdminSessionContext) ?? NO_PROVIDER;
}
