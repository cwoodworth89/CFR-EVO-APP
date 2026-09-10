import React from 'react';
import { CARD_STATE, HYDRANT_CLASS_COLOUR, HYDRANT_UNRATED_COLOUR, HYDRANT_PRIVATE_RING } from '../../utils/hydrantCard';

/**
 * The hydrant, as the third card of the dispatch header.
 *
 * Artboard 3A put this over the bottom-left of the route map. On 1132 Dufferin St it covered
 * the destination and the operator called it too big; moved into the header 2026-09-10 on
 * their word ("moving it to the units card. Or possibly to the timer card next to it"). It
 * has the card the elapsed clock vacated rather than a place inside the units card, so it
 * sits in the same spot on a one-unit medical call and a seven-unit structure fire: the
 * units card grows downward and would have pushed it about the screen.
 *
 * One hydrant, numbered as its badge is on the map and in the same NFPA 291 class colour,
 * its class, its distance in feet, and how the operator's rule chose it. A second row only
 * where the rule yields a decision. The model is utils/hydrantCard.js; every state is its
 * own words: awaiting a location, inventory loading, lookup failed (red, never dressed as
 * "no hydrant"), nothing within the 1,000 ft supply lay (amber), the pick.
 */

const LABEL = 'font-mono font-bold text-[10px] tracking-[0.16em] uppercase text-slate-400';
const SHELL = 'bg-slate-900 border rounded-xl min-w-0 px-3 py-2.5 lg:px-4 lg:py-3 flex flex-col justify-center gap-1.5 lg:gap-2 text-left';

function Badge({ n, colour, isPrivate }) {
  return (
    <span
      className="inline-flex items-center justify-center w-5 h-5 rounded-full font-mono font-black text-[11px] text-slate-900 border-2 flex-shrink-0"
      style={{ backgroundColor: colour, borderColor: isPrivate ? HYDRANT_PRIVATE_RING : '#0f172a' }}
    >
      {n}
    </span>
  );
}

export default function HydrantCard({ model, onTap = null, className = '' }) {
  if (!model) return null;

  if (model.state === CARD_STATE.AWAITING || model.state === CARD_STATE.LOADING || model.state === CARD_STATE.FAILED) {
    const failed = model.state === CARD_STATE.FAILED;
    return (
      <section className={`${SHELL} ${failed ? 'border-red-900/70' : 'border-slate-800'} ${className}`}>
        <span className={LABEL}>Hydrant</span>
        <span className={`font-mono text-xs ${failed ? 'text-red-400 font-bold' : 'text-slate-400 italic'}`}>{model.note}</span>
      </section>
    );
  }

  if (model.state === CARD_STATE.NONE) {
    return (
      <section className={`${SHELL} bg-amber-950/60 border-amber-700 ${className}`}>
        <span className={LABEL}>Hydrant</span>
        <span className="font-mono font-extrabold text-amber-400 text-sm lg:text-[clamp(0.85rem,1.8vh,1.15rem)] leading-tight">
          NO HYDRANT WITHIN 1,000 FT
        </span>
      </section>
    );
  }

  const Shell = onTap ? 'button' : 'section';
  const shellProps = onTap ? { type: 'button', onClick: onTap } : {};

  return (
    <Shell
      {...shellProps}
      className={`${SHELL} ${model.warn ? 'border-amber-700' : 'border-slate-800'} ${onTap ? 'cursor-pointer hover:border-slate-600 transition' : ''} ${className}`}
    >
      <span className="flex items-center gap-2 w-full">
        {model.warn ? (
          <span className="bg-amber-500 text-slate-950 rounded px-1.5 py-0.5 font-mono font-extrabold text-[10px] tracking-[0.12em] uppercase">{model.title}</span>
        ) : (
          <span className={LABEL}>{model.title}</span>
        )}
        {onTap && <span className="ml-auto font-mono font-bold text-[10px] tracking-[0.1em] uppercase text-sky-300">Tap to zoom</span>}
      </span>

      {model.rows.map((r, i) => {
        const classColour = HYDRANT_CLASS_COLOUR[String(r.flowClass || '').toUpperCase()] || HYDRANT_UNRATED_COLOUR;
        const idColour = r.isPrivate ? '#fbbf24' : classColour;
        return (
          <span key={`${r.id}-${i}`} className={`flex items-center gap-2 w-full ${i > 0 ? 'pt-1.5 border-t border-slate-800' : ''}`}>
            <Badge n={r.n} colour={classColour} isPrivate={r.isPrivate} />
            <span className="font-mono font-extrabold text-sm lg:text-[clamp(0.9rem,1.9vh,1.25rem)] leading-none" style={{ color: idColour }}>{r.id}</span>
            <span className={`rounded px-1.5 py-0.5 font-mono font-extrabold text-[10px] border whitespace-nowrap ${
              r.isPrivate ? 'border-amber-700 bg-amber-950 text-amber-400' : 'border-sky-700 bg-sky-950 text-sky-300'
            }`}>
              {r.isPrivate ? 'PRIV · ' : ''}{r.flowClass ? String(r.flowClass).toUpperCase() : 'UNRATED'}
            </span>
            <span className="ml-auto font-mono font-extrabold text-white text-sm lg:text-[clamp(0.9rem,1.9vh,1.25rem)] leading-none tabular-nums whitespace-nowrap">
              {r.feet != null ? `${r.feet.toLocaleString()} ft` : '-- ft'}
            </span>
          </span>
        );
      })}

      {model.note && (
        <span className="block font-sans font-medium text-[11px] lg:text-xs text-slate-300 leading-snug">{model.note}</span>
      )}
    </Shell>
  );
}
