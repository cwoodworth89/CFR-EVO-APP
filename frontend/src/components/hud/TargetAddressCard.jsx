import React from 'react';

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
export default function TargetAddressCard({ targetAddress, nearestHydrants = [], onClose }) {
  if (!targetAddress) return null;
  const nearest = nearestHydrants[0];

  return (
      <div className="flex-1 min-h-0 bg-slate-900/90 border border-slate-800 rounded-2xl p-4 flex flex-col justify-between shadow-xl backdrop-blur relative overflow-hidden">
        <div>
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
          
          {nearest && (
            <div className="mt-3 pt-2.5 border-t border-slate-800/80 flex flex-col gap-1.5">
              <span className="text-[9.5px] text-sky-400 font-extrabold uppercase tracking-wider font-mono flex items-center gap-1">
                💧 Nearest Hydrant
              </span>
              <div className="flex justify-between text-xs bg-slate-950/80 px-3 py-1.5 rounded-lg border border-slate-800/80 font-mono">
                <span className="text-slate-400">ID / Distance</span>
                <span className="text-white font-black">{nearest.gisId} ({nearest.distance}m)</span>
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
