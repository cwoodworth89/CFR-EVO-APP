import React from 'react';
import { CARD_STATE, HYDRANT_CLASS_COLOUR, HYDRANT_UNRATED_COLOUR, HYDRANT_PRIVATE_RING } from '../../utils/hydrantCard';

/**
 * The hydrant, as the third card of the dispatch header, with the call's documents along
 * its foot.
 *
 * Artboard 3A put this over the bottom-left of the route map. On 1132 Dufferin St it covered
 * the destination and the operator called it too big; moved into the header 2026-09-10 on
 * their word ("moving it to the units card. Or possibly to the timer card next to it"). It
 * has the card the elapsed clock vacated rather than a place inside the units card, so it
 * sits in the same spot on a one-unit medical call and a seven-unit structure fire: the
 * units card grows downward and would have pushed it about the screen.
 *
 * The hydrant reads from the top, the documents sit at the bottom, and the space between
 * them is empty on a short card (operator, 2026-09-10: "move the hydrant card to the top
 * align" and a documents slot "bottom aligned on the card").
 *
 * One hydrant, numbered as its badge is on the map and in the same NFPA 291 class colour,
 * its class, its distance in feet, and how the operator's rule chose it. A second row only
 * where the rule yields a decision. The model is utils/hydrantCard.js; every state is its
 * own words: awaiting a location, inventory loading, lookup failed (red, never dressed as
 * "no hydrant"), nothing within the 1,000 ft supply lay (amber), the pick.
 */

const LABEL = 'font-mono font-bold text-[10px] tracking-[0.16em] uppercase text-slate-400';

/** The hydrant half: whichever state the model is in. */
function HydrantBody({ model }) {
  if (model.state === CARD_STATE.AWAITING || model.state === CARD_STATE.LOADING || model.state === CARD_STATE.FAILED) {
    const failed = model.state === CARD_STATE.FAILED;
    return (
      <>
        <span className={LABEL}>Hydrant</span>
        <span className={`font-mono text-xs ${failed ? 'text-red-400 font-bold' : 'text-slate-400 italic'}`}>{model.note}</span>
      </>
    );
  }

  if (model.state === CARD_STATE.NONE) {
    return (
      <>
        <span className={LABEL}>Hydrant</span>
        <span className="font-mono font-extrabold text-amber-400 text-sm lg:text-[clamp(0.85rem,1.8vh,1.15rem)] leading-tight">
          NO HYDRANT WITHIN 1,000 FT
        </span>
      </>
    );
  }

  return (
    <>
      <span className="flex items-center gap-2 w-full">
        {model.warn ? (
          <span className="bg-amber-500 text-slate-950 rounded px-1.5 py-0.5 font-mono font-extrabold text-[10px] tracking-[0.12em] uppercase">{model.title}</span>
        ) : (
          <span className={LABEL}>{model.title}</span>
        )}
      </span>

      {model.rows.map((r, i) => {
        const classColour = HYDRANT_CLASS_COLOUR[String(r.flowClass || '').toUpperCase()] || HYDRANT_UNRATED_COLOUR;
        const idColour = r.isPrivate ? '#fbbf24' : classColour;
        return (
          <span key={`${r.id}-${i}`} className={`flex items-center gap-2 w-full ${i > 0 ? 'pt-1.5 border-t border-slate-800' : ''}`}>
            <span
              className="inline-flex items-center justify-center w-5 h-5 rounded-full font-mono font-black text-[11px] text-slate-900 border-2 flex-shrink-0"
              style={{ backgroundColor: classColour, borderColor: r.isPrivate ? HYDRANT_PRIVATE_RING : '#0f172a' }}
            >
              {r.n}
            </span>
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
    </>
  );
}

/**
 * @param {object}   props.model         the hydrant card model, or null before the map has reported one
 * @param {function} props.onTap         TAP TO ZOOM: asks the route map to snap to the call
 * @param {string}   props.prePlanUrl    the dispatch's pre-incident plan, if the record carries one
 * @param {function} props.onOpenPrePlan opens it
 */
export default function HydrantCard({ model = null, onTap = null, prePlanUrl = null, onOpenPrePlan = null, className = '' }) {
  // Null only in the frame before the route map reports: the project's own mark for a value
  // that is not there yet, never a state invented to fill the gap (CLAUDE.md s6.1).
  const m = model || { state: CARD_STATE.AWAITING, note: '--', rows: [] };
  const tappable = Boolean(onTap) && m.state === CARD_STATE.PICKS;

  return (
    <section className={`bg-slate-900 border rounded-xl min-w-0 px-3 py-2.5 lg:px-4 lg:py-3 flex flex-col text-left ${
      m.state === CARD_STATE.NONE ? 'bg-amber-950/60 border-amber-700'
        : m.state === CARD_STATE.FAILED ? 'border-red-900/70'
        : m.warn ? 'border-amber-700' : 'border-slate-800'
    } ${className}`}>
      {/* The hydrant, read from the top. */}
      <div className="flex flex-col gap-1.5 lg:gap-2 min-w-0">
        <HydrantBody model={m} />
        {tappable && (
          <button
            type="button"
            onClick={onTap}
            className="self-start font-mono font-bold text-[10px] tracking-[0.1em] uppercase text-sky-300 hover:text-sky-200 cursor-pointer transition"
          >
            Tap to zoom
          </button>
        )}
      </div>

      {/* Documents, along the foot. Operator, 2026-09-10: a place "for bringing up a stored
          pre-incident plan document, or other special documents". The pre-incident plan is
          the one that exists and opens in PrePlanModal; "other special documents" is not a
          feature yet, so this slot states what the record has and, when it has nothing, says
          so plainly rather than showing a control that would open nothing (CLAUDE.md s6.1).
          Post-freeze: what the other document kinds are, and where they are stored. */}
      <div className="mt-auto pt-2.5 border-t border-slate-800/80">
        {prePlanUrl && onOpenPrePlan ? (
          <button
            type="button"
            onClick={onOpenPrePlan}
            className="w-full flex items-center gap-2 rounded-md border border-sky-700 bg-sky-950/60 hover:bg-sky-900/60 px-2.5 py-2 touch:py-2.5 cursor-pointer transition"
          >
            <span className="w-1.5 h-1.5 rounded-full bg-sky-400 flex-shrink-0" />
            <span className="font-mono font-bold text-[11px] tracking-[0.08em] uppercase text-sky-300">Pre-incident plan</span>
          </button>
        ) : (
          <span className="block font-mono text-[10px] tracking-[0.08em] uppercase text-slate-500">
            No stored documents
          </span>
        )}
      </div>
    </section>
  );
}
