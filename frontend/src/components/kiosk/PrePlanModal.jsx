import React from 'react';

export default function PrePlanModal({ isOpen, onClose, pdfUrl, address, gisId }) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/90 backdrop-blur-md flex items-center justify-center p-4 sm:p-6 animate-fadeIn">
      <div className="bg-slate-900 border border-slate-700/80 rounded-2xl shadow-2xl w-full max-w-5xl h-[88vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="bg-slate-950 px-6 py-4 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-sky-950/80 border border-sky-500/40 flex items-center justify-center text-xl shadow-lg">
              📄
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-sky-400 bg-sky-950/60 border border-sky-900/60 px-2 py-0.5 rounded">
                  PRE-INCIDENT CONSTRUCTION PLAN
                </span>
                {gisId && <span className="text-[10px] font-mono text-slate-400">ID: {gisId}</span>}
              </div>
              <h2 className="text-lg font-bold text-white leading-snug mt-0.5">
                {address || 'Coquitlam High-Rise / Commercial Pre-Plan'}
              </h2>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {pdfUrl && (
              <a
                href={pdfUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs font-mono font-semibold text-sky-400 hover:text-sky-300 bg-slate-800 hover:bg-slate-700 px-3 py-1.5 rounded-lg border border-slate-700 transition-all flex items-center gap-1.5"
              >
                ↗ Open External
              </a>
            )}
            <button
              onClick={onClose}
              className="text-slate-400 hover:text-white bg-slate-800/80 hover:bg-rose-950/80 border border-slate-700 hover:border-rose-700/50 w-9 h-9 rounded-xl flex items-center justify-center text-lg font-bold transition-all"
              title="Close Pre-Plan View"
            >
              ✕
            </button>
          </div>
        </div>

        {/* Body: Embedded PDF or Placeholder Notice */}
        <div className="flex-1 bg-slate-950 relative overflow-hidden flex items-center justify-center">
          {pdfUrl ? (
            <iframe
              src={pdfUrl}
              title="Pre-Incident Construction Plan PDF"
              className="w-full h-full border-0"
            />
          ) : (
            <div className="max-w-md text-center p-6 bg-slate-900/60 border border-slate-800 rounded-2xl shadow-xl">
              <div className="w-16 h-16 rounded-2xl bg-amber-950/40 border border-amber-500/30 flex items-center justify-center text-3xl mx-auto mb-4">
                📋
              </div>
              <h3 className="text-base font-bold text-white">Pre-Incident Plan File Pending</h3>
              <p className="text-xs text-slate-400 mt-2 leading-relaxed font-sans">
                Coquitlam Fire Rescue pre-incident construction plans for this commercial / high-rise structure will display automatically in this viewport once linked to Parcel ID <span className="font-mono text-amber-300 font-bold">{gisId || 'N/A'}</span>.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
