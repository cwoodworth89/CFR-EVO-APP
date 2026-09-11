import React, { useState } from 'react';

const SET_BY_KEY = 'cfr_entrance_set_by';

/**
 * Arrival point controls (punch-list #49). The truck stops at the marker; when the computed
 * frontage is wrong for a site -- a gate off the lane, a trailer park, a highrise with the
 * lobby round the back -- the operator clicks where it should be and says why. Saved with a
 * name and a time; the kiosk shows the note on the next call there.
 */
export default function ArrivalPointSection({ parcel, placing, draft, onStart, onCancel, onSave, canEdit, standalone = false }) {
  // `standalone`: its own card on the dispatch display, rather than the foot of the
  // console's target card, so it carries no divider of its own.
  const frame = standalone ? 'flex flex-col gap-1.5' : 'mt-3 pt-2.5 border-t border-slate-800/80 flex flex-col gap-1.5';
  const [note, setNote] = useState('');
  const [setBy, setSetBy] = useState(() => {
    try { return localStorage.getItem(SET_BY_KEY) || ''; } catch { return ''; }
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  if (!parcel) {
    return (
      <div className={`${standalone ? '' : 'mt-3 pt-2.5 border-t border-slate-800/80 '}text-[10px] font-mono text-slate-500`}>
        🚒 Arrival point: no parcel row for this address, nothing to set
      </div>
    );
  }
  const hasEntrance = parcel.entrance_lat != null && parcel.entrance_lng != null;

  const submit = async (clear) => {
    setError(null);
    const who = setBy.trim();
    if (!who) { setError('Your name or initials are required'); return; }
    if (!clear && !draft) { setError('Click the map where the truck stops'); return; }
    setBusy(true);
    try {
      try { localStorage.setItem(SET_BY_KEY, who); } catch { /* fine */ }
      await onSave({ lat: clear ? null : draft.lat, lng: clear ? null : draft.lng, note: note.trim() || (clear ? 'cleared' : ''), setBy: who });
      setNote('');
    } catch (e) {
      setError(e.message || String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className={frame}>
      <span className="text-[9.5px] text-amber-400 font-extrabold uppercase tracking-wider font-mono flex items-center gap-1">
        🚒 Arrival point
      </span>
      {/* The explanation gives way to the form while placing: the card is a third of the
          stack's height and the form's save button was clipped below it (operator,
          2026-09-08). The card also scrolls now, so nothing in it is unreachable. */}
      {hasEntrance ? (
        <div className="text-[10px] font-mono bg-emerald-950/50 border border-emerald-800/60 rounded-lg px-2.5 py-1.5 text-emerald-200">
          <div className="font-black">OPERATOR-SET · {parcel.entrance_set_by}{parcel.entrance_set_at ? ` · ${String(parcel.entrance_set_at).slice(0, 10)}` : ''}</div>
          {parcel.entrance_note && <div className="text-emerald-100/90 italic mt-0.5">"{parcel.entrance_note}"</div>}
        </div>
      ) : !placing && (
        <div className="text-[10px] font-mono text-slate-400 bg-slate-950/80 border border-slate-800/80 rounded-lg px-2.5 py-1.5">
          Computed frontage: the closest point on the addressed road to the parcel. Set one only if the truck should stop somewhere else.
        </div>
      )}

      {/* The controls are an operator ruling, not a crew control: shown only while the
          header padlock is unlocked (operator, 2026-09-08). Locked, the card still says who
          set the point and when. */}
      {canEdit && (!placing ? (
        <div className="flex gap-1.5">
          <button onClick={onStart} className="flex-1 text-[10px] font-bold font-mono px-2 py-1.5 touch:py-2.5 rounded-lg bg-amber-500 hover:bg-amber-400 text-slate-950 border border-amber-300 cursor-pointer">
            {hasEntrance ? 'Move arrival point' : 'Set arrival point'}
          </button>
          {hasEntrance && (
            <button onClick={() => { onStart(); }} title="Clear: the computed frontage is used again" className="text-[10px] font-bold font-mono px-2 py-1.5 touch:py-2.5 rounded-lg bg-slate-800 hover:bg-red-900 text-slate-300 border border-slate-700 cursor-pointer">
              Clear
            </button>
          )}
        </div>
      ) : (
        <div className="flex flex-col gap-1.5 bg-amber-950/40 border border-amber-700/60 rounded-lg p-2">
          <div className="text-[10px] font-mono text-amber-200 font-bold">
            {draft ? `Pin at ${draft.lat.toFixed(5)}, ${draft.lng.toFixed(5)}` : 'Click the map where the truck stops'}
          </div>
          <input value={note} onChange={e => setNote(e.target.value)} placeholder="Why, in your words: gated, keypad at Glen Dr west end" maxLength={200}
            className="text-[10px] touch:text-base font-mono bg-slate-950 border border-slate-700 rounded px-2 py-1 touch:py-2 text-white placeholder:text-slate-600" />
          <input value={setBy} onChange={e => setSetBy(e.target.value)} placeholder="Your name or initials" maxLength={60}
            className="text-[10px] touch:text-base font-mono bg-slate-950 border border-slate-700 rounded px-2 py-1 touch:py-2 text-white placeholder:text-slate-600" />
          {error && <div className="text-[10px] font-mono text-red-400">{error}</div>}
          <div className="flex gap-1.5">
            <button disabled={busy || !draft} onClick={() => submit(false)} className="flex-1 text-[10px] font-bold font-mono px-2 py-1.5 touch:py-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-800 disabled:text-slate-500 text-white border border-emerald-400 cursor-pointer">
              {busy ? 'Saving…' : 'Save arrival point'}
            </button>
            {hasEntrance && (
              <button disabled={busy} onClick={() => submit(true)} className="text-[10px] font-bold font-mono px-2 py-1.5 touch:py-2.5 rounded-lg bg-red-800 hover:bg-red-700 text-white border border-red-600 cursor-pointer">
                Clear it
              </button>
            )}
            <button disabled={busy} onClick={onCancel} className="text-[10px] font-bold font-mono px-2 py-1.5 touch:py-2.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 cursor-pointer">
              Cancel
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
