import React from 'react';
import { CARD_STATE, HYDRANT_CLASS_COLOUR, HYDRANT_UNRATED_COLOUR, HYDRANT_PRIVATE_RING } from '../../utils/hydrantCard';

/**
 * The hydrant card on the dispatch map, bottom left (artboard 3A of the operator's Claude
 * Design canvas). One hydrant, numbered as its badge is on the map and in the same NFPA 291
 * class colour, its class, its distance in feet, and how the operator's rule chose it. A tap
 * zooms to the parcel and the picks (SNAP TO CALL). The model is utils/hydrantCard.js.
 *
 * Sized down 2026-09-10 on the operator's word ("way too big"): about two thirds of the
 * canvas's card.
 *
 * Every state is its own words: awaiting a location, inventory loading, lookup failed (red,
 * never dressed as "no hydrant"), nothing within the 1,000 ft supply lay (amber), the pick.
 */

const LABEL = 'font-mono font-bold text-[10px] tracking-[0.16em] uppercase text-slate-400';

function Badge({ n, colour, isPrivate }) {
  return (
    <span
      className="inline-flex items-center justify-center w-5 h-5 lg:w-6 lg:h-6 rounded-full font-mono font-black text-[11px] lg:text-xs text-slate-900 border-2 flex-shrink-0"
      style={{ backgroundColor: colour, borderColor: isPrivate ? HYDRANT_PRIVATE_RING : '#0f172a' }}
    >
      {n}
    </span>
  );
}

export default function HydrantCard({ model, onSnap = null, compact = false, cardRef = null }) {
  if (!model) return null;
  const base = `absolute bottom-3 left-3 z-[1000] rounded-xl shadow-xl text-left ${compact ? 'right-3' : 'min-w-[15rem] max-w-[21rem]'}`;

  if (model.state === CARD_STATE.AWAITING || model.state === CARD_STATE.LOADING || model.state === CARD_STATE.FAILED) {
    const failed = model.state === CARD_STATE.FAILED;
    return (
      <div ref={cardRef} className={`${base} bg-slate-950/90 border ${failed ? 'border-red-900/70' : 'border-slate-800'} px-3.5 py-2.5 flex items-center gap-2.5`}>
        <span className={LABEL}>Hydrant</span>
        <span className={`font-mono text-xs ${failed ? 'text-red-400 font-bold' : 'text-slate-400 italic'}`}>{model.note}</span>
      </div>
    );
  }

  if (model.state === CARD_STATE.NONE) {
    return (
      <div ref={cardRef} className={`${base} bg-amber-950/95 border border-amber-700 px-4 py-3 lg:py-3.5 flex items-center gap-3`}>
        <span className="w-2.5 h-2.5 rounded-full bg-amber-500 flex-shrink-0" />
        <span className="font-mono font-extrabold text-amber-400 text-sm lg:text-base leading-tight">NO HYDRANT WITHIN 1,000 FT</span>
      </div>
    );
  }

  return (
    <button
      ref={cardRef}
      type="button"
      onClick={onSnap || undefined}
      className={`${base} bg-slate-950/95 border ${model.warn ? 'border-amber-700' : 'border-sky-800'} px-3 py-2.5 lg:px-3.5 lg:py-3 flex flex-col gap-1.5 lg:gap-2 ${onSnap ? 'cursor-pointer' : 'cursor-default'}`}
    >
      <span className="flex items-center gap-2.5 w-full">
        {model.warn ? (
          <span className="bg-amber-500 text-slate-950 rounded px-1.5 py-0.5 font-mono font-extrabold text-[10px] tracking-[0.12em] uppercase">{model.title}</span>
        ) : (
          <span className={LABEL}>{model.title}</span>
        )}
        {onSnap && <span className="ml-auto font-mono font-bold text-[10px] tracking-[0.1em] uppercase text-sky-300">Tap to zoom</span>}
      </span>

      {model.rows.map((r, i) => {
        const classColour = HYDRANT_CLASS_COLOUR[String(r.flowClass || '').toUpperCase()] || HYDRANT_UNRATED_COLOUR;
        const idColour = r.isPrivate ? '#fbbf24' : classColour;
        return (
          <span key={`${r.id}-${i}`} className={`flex items-center gap-2 lg:gap-2.5 w-full ${i > 0 ? 'pt-1.5 lg:pt-2 border-t border-slate-800' : ''}`}>
            <Badge n={r.n} colour={classColour} isPrivate={r.isPrivate} />
            <span className="font-mono font-extrabold text-base lg:text-lg leading-none" style={{ color: idColour }}>{r.id}</span>
            <span className={`rounded px-1.5 py-0.5 font-mono font-extrabold text-[10px] border ${
              r.isPrivate ? 'border-amber-700 bg-amber-950 text-amber-400' : 'border-sky-700 bg-sky-950 text-sky-300'
            }`}>
              {r.isPrivate ? 'PRIVATE · ' : ''}{r.flowClass ? String(r.flowClass).toUpperCase() : 'UNRATED'}
            </span>
            <span className="ml-auto font-mono font-extrabold text-white text-base lg:text-lg leading-none tabular-nums whitespace-nowrap">
              {r.feet != null ? `${r.feet.toLocaleString()} ft` : '-- ft'}
            </span>
          </span>
        );
      })}

      {model.note && (
        <span className="block font-sans font-medium text-[11px] lg:text-xs text-slate-300 leading-snug">{model.note}</span>
      )}
    </button>
  );
}
