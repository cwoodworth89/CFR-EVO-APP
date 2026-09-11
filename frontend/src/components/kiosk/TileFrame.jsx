import React from 'react';

/**
 * The frame both view tiles share (artboard 3A): the tile's name, a small status and EXPAND,
 * over a picture that fills the whole card.
 *
 * The header was a solid bar above the picture until 2026-09-10, when the operator asked what
 * could be done about "the black headers inside the pip cards". It is now a gradient over the
 * top of the picture, so the tile is all picture and the name still reads on a bright
 * orthophoto. Only EXPAND takes clicks; the rest of the strip passes them to the map beneath.
 * The controls themselves still live in the expanded view (docs/ux_notes.md section 4, "the
 * tile is the picture"), which is what #74 asked for.
 *
 * The name sits at the RIGHT beside EXPAND, not at the left: Google puts its own "Open in
 * Maps" control at the top left of a Street View, and the two landed on top of each other.
 */
export default function TileFrame({ label, meta = null, onExpand = null, expandTitle = 'Open the expanded view', children }) {
  return (
    <div className="relative w-full h-full rounded-xl overflow-hidden border border-slate-800 bg-slate-950 shadow-xl">
      {/* The picture is the tile, so the header floats over it rather than taking a black bar
          off its height (operator, 2026-09-10). The gradient is what keeps the name legible
          over a bright orthophoto; the strip itself lets clicks through to the map beneath,
          and only the button takes them back. */}
      <div className="absolute inset-x-0 top-0 z-[1000] pointer-events-none flex items-center justify-end gap-2.5 px-3 lg:px-4 py-2 lg:py-2.5 bg-gradient-to-b from-slate-950/85 via-slate-950/55 to-transparent">
        <div className="flex items-center gap-2.5 min-w-0">
          <span className="font-mono font-bold text-[11px] lg:text-xs tracking-[0.12em] uppercase text-slate-200 whitespace-nowrap drop-shadow-[0_1px_2px_rgba(2,6,23,0.9)]">{label}</span>
          {meta}
        </div>
        {onExpand && (
          <button
            type="button"
            onClick={onExpand}
            title={expandTitle}
            className="pointer-events-auto bg-slate-950/85 backdrop-blur border border-slate-700 hover:border-slate-500 text-slate-300 hover:text-white rounded-md px-3 py-1.5 touch:py-2.5 font-mono font-bold text-[11px] tracking-[0.1em] uppercase cursor-pointer transition flex-shrink-0"
          >
            Expand
          </button>
        )}
      </div>
      <div className="w-full h-full relative">
        {children}
      </div>
    </div>
  );
}
