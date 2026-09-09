import React from 'react';
import { AdminSessionContext, useAdminSessionState } from '../hooks/useAdminSession';

/** One admin session for both surfaces; see hooks/useAdminSession.js. */
export default function AdminSessionProvider({ children }) {
  const admin = useAdminSessionState();
  return <AdminSessionContext.Provider value={admin}>{children}</AdminSessionContext.Provider>;
}
