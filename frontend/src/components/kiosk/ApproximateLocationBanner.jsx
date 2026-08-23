import React from 'react';

/**
 * Amber warning for a location the geocoder placed only approximately.
 *
 * Shown whenever the resolver set `resolution_note` -- the marker it writes when it
 * substituted a nearby civic address, fell back to a street midpoint, or otherwise
 * could not place the dispatched address exactly. The note explains what was
 * substituted and why; until now it was carried all the way through the payload and
 * never displayed, so an approximate pin looked exactly like an exact one.
 *
 * Deliberately keyed off resolution_note rather than a confidence threshold.
 * Confidence is poorly calibrated in both directions -- measured 2026-08-23 against
 * 202 operator-verified calls, score 100 was wrong on 8% of them while the 81-89 band
 * was flawless -- so a numeric cut would both miss real substitutions and flag good
 * ones. resolution_note is set by the resolver that actually made the substitution, so
 * it states a fact rather than estimating one.
 *
 * This is a warning, not a suppression: the coordinates are usually close and useful
 * (a nearest-civic hit is typically a few doors away). Crews get the location AND the
 * signal that it is approximate, which is what lets them fall back on their own
 * methods rather than trusting a pin that has no business being trusted.
 *
 * Tier 1 (no coordinates at all) is a separate, louder state that pauses routing.
 */
export default function ApproximateLocationBanner({ activeCall, compact = false }) {
  const note = activeCall?.resolution_note;
  if (!note) return null;

  // The street-section case has its own banner explaining the same situation; two
  // amber cards saying different things about one call is worse than one.
  if (activeCall?.location_type === 'street_section') return null;

  const requested = activeCall.requested_address;
  const actual = activeCall.address || activeCall.target?.address;

  return (
    <div
      className="w-full rounded-2xl border border-amber-600/60 bg-amber-950/30 px-4 py-3 shadow-lg backdrop-blur-sm"
      role="status"
    >
      <div className="flex items-start gap-3">
        <span className="text-2xl leading-none mt-0.5" aria-hidden="true">⚠️</span>
        <div className="min-w-0">
          <h4 className="text-sm font-black uppercase tracking-wider text-amber-400 font-mono">
            APPROXIMATE LOCATION — VERIFY ON ARRIVAL
          </h4>
          {requested && actual && requested !== actual && (
            <p className={`font-mono text-slate-300 mt-1 leading-relaxed ${compact ? 'text-[10px]' : 'text-xs'}`}>
              Dispatched <span className="text-amber-300 font-bold">{requested}</span>
              {' '}&middot; routed to <span className="text-amber-300 font-bold">{actual}</span>
            </p>
          )}
          <p className={`font-mono text-slate-400 mt-1 leading-relaxed ${compact ? 'text-[10px]' : 'text-xs'}`}>
            {note}
          </p>
        </div>
      </div>
    </div>
  );
}
