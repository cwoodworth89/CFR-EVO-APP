import React, { useState } from 'react';
import PropertySatellitePanel from './kiosk/PropertySatellitePanel';
import StreetViewPanel from './kiosk/StreetViewPanel';

/**
 * The right-hand spatial inspection stack: three equal cells, the top one selected by
 * mode, the lower two shared.
 *
 * Both surfaces already rendered this. The console showed the target address card above
 * the satellite and street views; the dispatch display showed the cadastral block above
 * the same two. Only the top cell and the container styling ever differed.
 *
 * Step 5 of docs/architecture/unified_map_surface.md — chrome that differs by *kind*
 * stays as separate components (`topCard`), while the shared structure lives here.
 *
 * `call` is the single dispatch shape from utils/dispatchModel, so both surfaces feed
 * their panels identically.
 *
 * `compact` (a phone or an upright tablet, below Tailwind's `lg`): the same cells as tabs,
 * one mounted at a time. Three stacked maps in a 55 % tall sheet were 130 px each; and one Leaflet instance
 * plus a Street View at a time is what a phone can afford. Street View is then the whole
 * sheet, which on that surface also satisfies the Google terms on sharing a screen with a
 * non-Google map (docs/standards, s3.2.3(e)(ii)). The tab bar is a finger's height.
 *
 * `sheet`: the compact stack is floating over the map (the console) rather than in the
 * column (the dispatch display), so it can fold down to its tab bar and give the map back;
 * a landscape phone has 393 px of height for everything.
 */
export default function DetailStack({ call, topCard, className = '', compact = false, sheet = false }) {
  const tabs = [
    topCard ? { id: 'details', label: 'Details' } : null,
    // The tabs carry the tiles' own names (artboard 3A: AERIAL, STREET VIEW), no glyphs.
    { id: 'satellite', label: 'Aerial' },
    { id: 'street', label: 'Street view' },
  ].filter(Boolean);
  const [tab, setTab] = useState(tabs[0].id);
  const [open, setOpen] = useState(true);
  const active = tabs.some((t) => t.id === tab) ? tab : tabs[0].id;
  const showContent = !sheet || open;

  if (!compact) {
    return (
      <div className={`h-full min-h-0 flex flex-col gap-3 overflow-hidden ${className}`}>
        {topCard}

        <div className="flex-1 min-h-0 relative">
          <PropertySatellitePanel activeCall={call} />
        </div>

        <div className="flex-1 min-h-0 relative">
          <StreetViewPanel activeCall={call} />
        </div>
      </div>
    );
  }

  return (
    <div className={`h-full min-h-0 flex flex-col gap-2 overflow-hidden ${className}`}>
      <div className="flex gap-1 flex-shrink-0" role="tablist">
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={active === t.id}
            onClick={() => { setTab(t.id); if (sheet) setOpen(true); }}
            className={`flex-1 min-h-11 rounded-xl text-xs font-black font-mono border transition cursor-pointer ${
              active === t.id && showContent
                ? 'bg-slate-800 text-white border-slate-600 shadow'
                : 'bg-slate-950 text-slate-400 border-slate-800'
            }`}
          >
            {t.label}
          </button>
        ))}
        {sheet && (
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
            aria-label={open ? 'Fold the details down' : 'Open the details'}
            className="min-h-11 min-w-11 rounded-xl text-sm font-black text-slate-300 bg-slate-950 border border-slate-800 cursor-pointer"
          >
            {open ? '▾' : '▴'}
          </button>
        )}
      </div>

      {showContent && (
        <div className={`relative flex flex-col ${sheet ? 'h-[46dvh]' : 'flex-1 min-h-0'}`}>
          {active === 'details' && topCard}
          {active === 'satellite' && <PropertySatellitePanel activeCall={call} />}
          {active === 'street' && <StreetViewPanel activeCall={call} />}
        </div>
      )}
    </div>
  );
}
