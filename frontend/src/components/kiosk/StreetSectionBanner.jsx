import React from 'react';

/**
 * Amber standby card for a dispatch that resolved to a STREET SECTION rather than a
 * point.
 *
 * Locution sometimes announces "<street> and <street>" -- the same street in both the
 * address and the "near" cross-street slot -- when the CAD record carries no cross
 * street. That is not an intersection, and the road does not cross itself. The geocoder
 * answers with the stretch of that street inside the announced map grid, and this card
 * says so plainly: the crew is being sent to a length of road, not to a located
 * incident.
 *
 * Styled as a sibling of the CLAUDE.md section 5 Tier 1 / Tier 2 cards, but visually
 * distinct from both, because this is a third state -- neither resolved nor unresolved.
 */
export default function StreetSectionBanner({ activeCall, compact = false }) {
  if (activeCall?.location_type !== 'street_section') return null;

  const metres = activeCall.length_m;
  const grid = activeCall.grid || activeCall.map_grid;
  const street = (activeCall.street || activeCall.address || '').toString();

  return (
    <div
      className="w-full rounded-2xl border border-amber-600/60 bg-amber-950/30 px-4 py-3 shadow-lg backdrop-blur-sm"
      role="status"
    >
      <div className="flex items-start gap-3">
        <span className="text-2xl leading-none mt-0.5" aria-hidden="true">🛣️</span>
        <div className="min-w-0">
          <h4 className="text-sm font-black uppercase tracking-wider text-amber-400 font-mono">
            STREET SECTION ONLY — NO CROSS STREET GIVEN
          </h4>
          <p className={`font-mono text-slate-300 mt-1 leading-relaxed ${compact ? 'text-[10px]' : 'text-xs'}`}>
            {metres != null && grid ? (
              <>
                Highlighting <span className="text-amber-300 font-bold">{metres} m</span> of{' '}
                <span className="text-amber-300 font-bold">{street}</span> inside map grid{' '}
                <span className="text-amber-300 font-bold">{grid}</span>.
              </>
            ) : (
              <>Highlighting a section of {street}.</>
            )}
          </p>
          <p className={`font-mono text-amber-200/80 mt-1 leading-relaxed ${compact ? 'text-[10px]' : 'text-xs'}`}>
            Not a located incident — apparatus routed to the nearer end of the section.
          </p>
        </div>
      </div>
    </div>
  );
}
