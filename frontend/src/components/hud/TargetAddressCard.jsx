import React, { useState } from 'react';

/**
 * Address summary for the workstation inspection stack: the searched target, its building
 * name if it matched a known one, and the nearest hydrant.
 *
 * Extracted from MapBoard.jsx — the last panel still rendered inline there.
 *
 * Flow rating is shown only when the hydrant has one. An unrated hydrant carries a null
 * flowClass and the row is omitted rather than showing a class it does not have
 * (CLAUDE.md §6.1 — this is the same defect that had 853 unrated hydrants presented as
 * NFPA 291 class AA).
 */
const SET_BY_KEY = 'cfr_entrance_set_by';

/**
 * Arrival point controls (punch-list #49). The truck stops at the marker; when the computed
 * frontage is wrong for a site -- a gate off the lane, a trailer park, a highrise with the
 * lobby round the back -- the operator clicks where it should be and says why. Saved with a
 * name and a time; the kiosk shows the note on the next call there.
 */
function ArrivalPointSection({ parcel, placing, draft, onStart, onCancel, onSave }) {
  const [note, setNote] = useState('');
  const [setBy, setSetBy] = useState(() => {
    try { return localStorage.getItem(SET_BY_KEY) || ''; } catch { return ''; }
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  if (!parcel) {
    return (
      <div className="mt-3 pt-2.5 border-t border-slate-800/80 text-[10px] font-mono text-slate-500">
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
    <div className="mt-3 pt-2.5 border-t border-slate-800/80 flex flex-col gap-1.5">
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

      {!placing ? (
        <div className="flex gap-1.5">
          <button onClick={onStart} className="flex-1 text-[10px] font-bold font-mono px-2 py-1.5 rounded-lg bg-amber-500 hover:bg-amber-400 text-slate-950 border border-amber-300 cursor-pointer">
            {hasEntrance ? 'Move arrival point' : 'Set arrival point'}
          </button>
          {hasEntrance && (
            <button onClick={() => { onStart(); }} title="Clear: the computed frontage is used again" className="text-[10px] font-bold font-mono px-2 py-1.5 rounded-lg bg-slate-800 hover:bg-red-900 text-slate-300 border border-slate-700 cursor-pointer">
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
            className="text-[10px] font-mono bg-slate-950 border border-slate-700 rounded px-2 py-1 text-white placeholder:text-slate-600" />
          <input value={setBy} onChange={e => setSetBy(e.target.value)} placeholder="Your name or initials" maxLength={60}
            className="text-[10px] font-mono bg-slate-950 border border-slate-700 rounded px-2 py-1 text-white placeholder:text-slate-600" />
          {error && <div className="text-[10px] font-mono text-red-400">{error}</div>}
          <div className="flex gap-1.5">
            <button disabled={busy || !draft} onClick={() => submit(false)} className="flex-1 text-[10px] font-bold font-mono px-2 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-800 disabled:text-slate-500 text-white border border-emerald-400 cursor-pointer">
              {busy ? 'Saving…' : 'Save arrival point'}
            </button>
            {hasEntrance && (
              <button disabled={busy} onClick={() => submit(true)} className="text-[10px] font-bold font-mono px-2 py-1.5 rounded-lg bg-red-800 hover:bg-red-700 text-white border border-red-600 cursor-pointer">
                Clear it
              </button>
            )}
            <button disabled={busy} onClick={onCancel} className="text-[10px] font-bold font-mono px-2 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 cursor-pointer">
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function TargetAddressCard({ targetAddress, nearestHydrants = [], hydrantTier = null, parcel = null,
                                            placingEntrance = false, entranceDraft = null,
                                            onStartPlacing, onCancelPlacing, onSaveEntrance, onClose }) {
  if (!targetAddress) return null;
  const nearest = nearestHydrants[0];

  return (
      <div className="flex-1 min-h-0 bg-slate-900/90 border border-slate-800 rounded-2xl p-4 flex flex-col justify-between shadow-xl backdrop-blur relative overflow-hidden">
        <div className="min-h-0 overflow-y-auto pr-1">
          <div className="flex justify-between items-center gap-2 pb-2.5 border-b border-slate-800">
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] text-slate-400 font-mono font-bold uppercase tracking-wider">SEARCH TARGET</span>
              <span className="text-emerald-400 text-[9px] font-black tracking-wider bg-emerald-950/80 border border-emerald-800/80 px-2 py-0.5 rounded">ACTIVE ROUTE</span>
            </div>
            <button 
              onClick={onClose}
              className="text-slate-400 hover:text-white text-xs font-bold w-6 h-6 flex items-center justify-center rounded-full hover:bg-slate-800 transition cursor-pointer"
              title="Close Inspection Panel"
            >
              ✕
            </button>
          </div>

          {targetAddress.buildingName && (
            <div className="flex items-center gap-1.5 mt-2.5 bg-amber-950/70 border border-amber-700/80 px-2.5 py-1 rounded-lg text-amber-300 font-extrabold text-xs">
              <span>🏢</span>
              <span>{targetAddress.buildingName}</span>
            </div>
          )}
          <h3 className="font-black text-lg text-sky-400 mt-2 leading-tight uppercase font-sans tracking-tight">
            {targetAddress.address}
          </h3>
          <p className="text-[11px] text-slate-400 font-mono mt-0.5 font-semibold">Coquitlam, BC</p>
          {targetAddress.note && (
            <p className="text-[10px] text-sky-300 font-sans italic mt-1 font-semibold bg-slate-950/60 p-1.5 rounded border border-slate-800">
              ℹ️ {targetAddress.note}
            </p>
          )}
          
          <ArrivalPointSection
            parcel={parcel}
            placing={placingEntrance}
            draft={entranceDraft}
            onStart={onStartPlacing}
            onCancel={onCancelPlacing}
            onSave={onSaveEntrance}
          />

          {hydrantTier === 'none' && (
            <div className="text-[10px] font-mono font-black text-amber-300">⚠️ NO HYDRANT WITHIN 1,000 FT</div>
          )}
          {nearest && (
            <div className="mt-3 pt-2.5 border-t border-slate-800/80 flex flex-col gap-1.5">
              <span className="text-[9.5px] text-sky-400 font-extrabold uppercase tracking-wider font-mono flex items-center gap-1">
                💧 Nearest Hydrant
              </span>
              <div className="flex justify-between text-xs bg-slate-950/80 px-3 py-1.5 rounded-lg border border-slate-800/80 font-mono">
                <span className="text-slate-400">ID / Distance</span>
                <span className="text-white font-black">{nearest.gisId} ({nearest.distance} m{nearest.how === 'doorstep' ? ', within a 50 ft roll' : nearest.how === 'approach' ? ' before arrival, on route' : nearest.how === 'supply' ? ', supply lay' : ''})</span>
              </div>
              {nearest.flowClass && (
                <div className="flex justify-between text-xs bg-slate-950/80 px-3 py-1.5 rounded-lg border border-slate-800/80 font-mono">
                  <span className="text-slate-400">Flow Rating</span>
                  <span className="text-sky-400 font-black">{nearest.flowClass}</span>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
  );
}
