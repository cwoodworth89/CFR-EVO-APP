import React, { useState } from 'react';

/**
 * The padlock at the right end of the header (operator, 2026-09-08: "somewhere discreet").
 *
 * Locked it is a dim glyph a crew has no reason to touch. Unlocked it reads ADMIN in amber
 * so nobody leaves a shared screen open without noticing, and one click locks it. The
 * password is the admin password (ADMIN_PASSWORD on the kiosk); the username is fixed.
 * The unlock lasts 30 days unless locked here or logged out from the review screen.
 */
export function AdminLock({ admin }) {
  const [open, setOpen] = useState(false);
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const close = () => { setOpen(false); setPassword(''); setError(null); };

  const submit = async (e) => {
    e.preventDefault();
    if (!password) return;
    setBusy(true);
    setError(null);
    try {
      await admin.unlock(password);
      close();
    } catch (err) {
      setError(err?.message || String(err));
    } finally {
      setBusy(false);
    }
  };

  const onClick = () => {
    if (admin.unlocked) admin.lock();
    else setOpen(true);
  };

  return (
    <>
      <button
        type="button"
        onClick={onClick}
        title={admin.unlocked ? 'Admin controls are unlocked. Click to lock.' : 'Unlock admin controls'}
        className={admin.unlocked
          ? 'px-2 py-1.5 text-[10px] font-black font-mono rounded-lg border border-amber-500/40 bg-amber-500/15 text-amber-300 hover:bg-amber-500/30 cursor-pointer flex items-center gap-1 select-none'
          : 'px-1.5 py-1.5 text-sm text-slate-700 hover:text-slate-300 cursor-pointer select-none'}
      >
        {admin.unlocked ? <><span>🔓</span><span>ADMIN</span></> : '🔒'}
      </button>

      {open && (
        <div className="fixed inset-0 bg-slate-950/90 backdrop-blur-sm z-[2000] flex items-center justify-center p-6 font-sans" onClick={close}>
          <form
            onSubmit={submit}
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-xs bg-slate-900 border border-amber-500/30 rounded-2xl p-5 shadow-2xl flex flex-col gap-3 text-left"
          >
            <div className="text-xs font-black text-amber-300 uppercase tracking-wider font-mono">🔒 Admin unlock</div>
            <p className="text-[10px] text-slate-400 font-mono leading-relaxed">
              Reveals the review screen, the arrival point and the Street View saves. Stays unlocked for 30 days unless locked.
            </p>
            <input
              type="password"
              autoFocus
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={busy}
              placeholder="Admin password"
              className="w-full bg-slate-950 border border-slate-800 focus:border-amber-500 text-xs text-white rounded-xl px-3 py-2.5 focus:outline-none placeholder-slate-600 font-mono"
            />
            {error && <div className="text-[10px] font-mono text-rose-400">{error}</div>}
            <div className="flex gap-2">
              <button type="submit" disabled={busy || !password}
                className="flex-1 text-xs font-bold font-mono px-3 py-2 rounded-xl bg-amber-500 hover:bg-amber-400 disabled:bg-slate-800 disabled:text-slate-500 text-slate-950 border border-amber-300 cursor-pointer">
                {busy ? 'Checking…' : 'UNLOCK'}
              </button>
              <button type="button" onClick={close} disabled={busy}
                className="text-xs font-bold font-mono px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 cursor-pointer">
                CANCEL
              </button>
            </div>
          </form>
        </div>
      )}
    </>
  );
}
