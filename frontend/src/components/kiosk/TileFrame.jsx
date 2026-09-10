import React from 'react';

/**
 * The frame both view tiles share (artboard 3A): a one-line header bar carrying the tile's
 * name, a small status, and EXPAND, with the picture filling the rest. Nothing floats over
 * the picture; the controls live in the expanded view (docs/ux_notes.md section 4, "the tile
 * is the picture"). Replaces the floating header pill and the separate Expand button that
 * the operator called busy (#74).
 */
export default function TileFrame({ label, meta = null, onExpand = null, expandTitle = 'Open the expanded view', children }) {
  return (
    <div className="relative w-full h-full rounded-xl overflow-hidden border border-slate-800 bg-slate-950 shadow-xl flex flex-col">
      <div className="flex-shrink-0 flex items-center justify-between gap-3 px-3 lg:px-4 py-2 lg:py-2.5 border-b border-slate-800/80 bg-slate-950">
        <div className="flex items-center gap-2.5 min-w-0">
          <span className="font-mono font-bold text-[11px] lg:text-xs tracking-[0.12em] uppercase text-slate-300 whitespace-nowrap">{label}</span>
          {meta}
        </div>
        {onExpand && (
          <button
            type="button"
            onClick={onExpand}
            title={expandTitle}
            className="bg-slate-950 border border-slate-700 hover:border-slate-500 text-slate-300 hover:text-white rounded-md px-3 py-1.5 touch:py-2.5 font-mono font-bold text-[11px] tracking-[0.1em] uppercase cursor-pointer transition flex-shrink-0"
          >
            Expand
          </button>
        )}
      </div>
      <div className="flex-1 min-h-0 relative">
        {children}
      </div>
    </div>
  );
}
