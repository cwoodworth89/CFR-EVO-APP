import React from 'react';
import { formatTimestampPT, getCallTones } from './reviewFormat';

export default function ReviewTable({
  filteredCalls = [],
  selectedCall,
  onSelectCall,
  searchQuery,
  setSearchQuery,
  statusFilter,
  setStatusFilter,
  toneFilter,
  setToneFilter,
  unitFilter,
  setUnitFilter,
  loading = false,
  dbStatus = 'connected',
  dbError = null,
  onRetryFetch,
  onReviewCall,
  onDeleteCall,
}) {
  return (
    <div className="flex-grow flex flex-col bg-slate-900 border border-slate-800 rounded-2xl p-4 overflow-hidden">
      {/* Search and Header */}
      <div className="flex justify-between items-center gap-4 mb-4 flex-shrink-0">
        <h2 className="text-sm font-extrabold uppercase tracking-wider text-slate-300">
          Captured Dispatches ({filteredCalls.length})
        </h2>
        <input
          type="text"
          placeholder="Search by ID, Address, Incident..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="bg-slate-950 border border-slate-800 hover:border-slate-700 focus:border-sky-500 text-white rounded-lg px-3 py-1.5 text-xs focus:outline-none placeholder-slate-600 w-72 transition-all font-mono"
        />
      </div>

      {/* Status & Metadata Filter Bar */}
      <div className="flex flex-wrap items-center justify-between gap-2 mb-3 bg-slate-950/60 p-2 border border-slate-850 rounded-xl flex-shrink-0">
        <div className="flex items-center gap-1">
          {[
            { id: 'all', label: 'All Dispatches' },
            { id: 'needs_review', label: '⏳ Needs HITL Review' },
            { id: 'low_confidence', label: '⚠️ Low Confidence' },
            { id: 'fine_tuned', label: '✅ Verified' }
          ].map(tab => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setStatusFilter(tab.id)}
              className={`px-2.5 py-1 rounded-lg text-[10px] font-extrabold uppercase font-mono transition-all cursor-pointer ${
                statusFilter === tab.id
                  ? 'bg-sky-500 text-slate-950 shadow-md font-black'
                  : 'bg-slate-900 text-slate-400 hover:text-white hover:bg-slate-850'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2 text-[10px] font-mono">
          <select
            value={toneFilter}
            onChange={(e) => setToneFilter(e.target.value)}
            className="bg-slate-900 border border-slate-800 text-slate-300 rounded-lg px-2 py-1 focus:outline-none cursor-pointer"
          >
            <option value="all">All Tones</option>
            <option value="engine">Engine</option>
            <option value="rescue">Rescue</option>
            <option value="chief">Chief</option>
          </select>

          <select
            value={unitFilter}
            onChange={(e) => setUnitFilter(e.target.value)}
            className="bg-slate-900 border border-slate-800 text-slate-300 rounded-lg px-2 py-1 focus:outline-none cursor-pointer"
          >
            <option value="all">All Units</option>
            <option value="engine">Engine Units</option>
            <option value="rescue">Rescue Units</option>
            <option value="chief">Chief Units</option>
          </select>
        </div>
      </div>

      {/* Table Container */}
      <div className="flex-grow overflow-auto pr-1">
        {loading ? (
          <div className="flex flex-col items-center justify-center py-20 text-slate-500 gap-2">
            <span className="flex h-4 w-4 relative">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-sky-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-4 w-4 bg-sky-500"></span>
            </span>
            <span className="text-[10px] font-bold font-mono tracking-widest uppercase mt-2">Fetching dispatch logs...</span>
          </div>
        ) : dbStatus === 'disconnected' ? (
          <div className="flex flex-col items-center justify-center py-16 px-4 bg-rose-950/20 border border-rose-900/30 rounded-2xl text-center">
            <span className="text-3xl mb-2">⚠️</span>
            <h3 className="font-extrabold text-rose-400 uppercase text-xs tracking-wider">Database Connection Failed</h3>
            <p className="text-xs text-slate-400 mt-2 max-w-md font-mono leading-relaxed">
              Could not load dispatches from Local Database API. Ensure your local FastAPI Gateway is running on port 8000 and PostgreSQL container is healthy.
            </p>

            {dbError && (
              <div className="mt-4 p-3 bg-slate-950/80 border border-slate-850 text-[10px] text-rose-400 font-mono rounded-lg max-w-lg overflow-x-auto text-left select-text">
                Error Details: {dbError}
              </div>
            )}
            {onRetryFetch && (
              <button
                type="button"
                onClick={onRetryFetch}
                className="mt-5 bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 border border-rose-500/35 px-4 py-2 rounded-lg text-xs font-bold transition-all cursor-pointer shadow-md"
              >
                Retry Connection
              </button>
            )}
          </div>
        ) : filteredCalls.length === 0 ? (
          <div className="text-center py-20 text-slate-500 text-xs italic">
            No dispatches found matching current filters.
          </div>
        ) : (
          <div className="min-w-[800px]">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-800 text-[10px] text-slate-400 font-extrabold uppercase tracking-wider font-mono sticky top-0 z-10">
                  <th className="py-2.5 px-3 w-[18%] bg-slate-900">Date / Dispatch ID</th>
                  <th className="py-2.5 px-3 w-[10%] text-center bg-slate-900">Tones</th>
                  <th className="py-2.5 px-3 w-[11%] text-center bg-slate-900">Conf &gt;90%</th>
                  <th className="py-2.5 px-3 w-[11%] text-center bg-slate-900">HITL Reviewed</th>
                  <th className="py-2.5 px-3 w-[11%] text-center bg-slate-900">Training Status</th>
                  <th className="py-2.5 px-3 w-[28%] bg-slate-900">System Prefills</th>
                  <th className="py-2.5 px-3 text-right w-[11%] bg-slate-900">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredCalls.map((call) => {
                  const isSelected = selectedCall?.id === call.id || (selectedCall?.dispatch_id && selectedCall.dispatch_id === call.dispatch_id);
                  const rowTones = getCallTones(call);
                  return (
                    <tr
                      key={call.id || call.dispatch_id}
                      onClick={() => onSelectCall && onSelectCall(call)}
                      className={`border-b border-slate-850 hover:bg-slate-800/40 transition-all cursor-pointer text-xs ${
                        isSelected ? 'bg-slate-800/70 border-sky-500/40 shadow-sm' : ''
                      }`}
                    >
                      <td className="py-3 px-3 font-mono">
                        <div className="text-slate-200 font-bold">{formatTimestampPT(call.timestamp)}</div>
                        <div className="text-[9.5px] text-sky-400 font-medium mt-0.5">
                          ID: {call.dispatch_id}
                        </div>
                      </td>
                      <td className="py-3 px-3 text-center" onClick={(e) => e.stopPropagation()}>
                        <div className="flex gap-1 justify-center items-center font-mono text-[9px] font-extrabold">
                          <span
                            className={`w-5 h-5 rounded-full border flex items-center justify-center transition-all ${
                              rowTones.includes('chief')
                                ? 'bg-sky-500/20 border-sky-500/50 text-sky-400 shadow-[0_0_8px_rgba(14,165,233,0.3)] font-black'
                                : 'bg-slate-900/60 border-slate-850 text-slate-600'
                            }`}
                            title={rowTones.includes('chief') ? 'Chief Tone Captured' : 'Chief Tone Not Captured'}
                          >
                            C
                          </span>
                          <span
                            className={`w-5 h-5 rounded-full border flex items-center justify-center transition-all ${
                              rowTones.includes('engine')
                                ? 'bg-amber-500/20 border-amber-500/50 text-amber-400 shadow-[0_0_8px_rgba(245,158,11,0.3)] font-black'
                                : 'bg-slate-900/60 border-slate-850 text-slate-600'
                            }`}
                            title={rowTones.includes('engine') ? 'Engine Tone Captured' : 'Engine Tone Not Captured'}
                          >
                            E
                          </span>
                          <span
                            className={`w-5 h-5 rounded-full border flex items-center justify-center transition-all ${
                              rowTones.includes('rescue')
                                ? 'bg-rose-500/20 border-rose-500/50 text-rose-400 shadow-[0_0_8px_rgba(244,63,94,0.3)] font-black'
                                : 'bg-slate-900/60 border-slate-850 text-slate-600'
                            }`}
                            title={rowTones.includes('rescue') ? 'Rescue Tone Captured' : 'Rescue Tone Not Captured'}
                          >
                            R
                          </span>
                        </div>
                      </td>
                      <td className="py-3 px-3 text-center">
                        {call.confidence_score !== undefined && call.confidence_score !== null ? (
                          <span className={`text-[11px] font-mono font-bold ${call.confidence_score >= 90 ? 'text-emerald-400' : 'text-rose-400'}`}>
                            {call.confidence_score >= 90 ? '🟢 Yes' : '🔴 No'} ({Math.round(call.confidence_score)}%)
                          </span>
                        ) : (
                          <span className="text-slate-500 font-mono text-[10px]">N/A</span>
                        )}
                      </td>
                      <td className="py-3 px-3 text-center">
                        {call.feedback_submitted ? (
                          <span className="text-[11px] text-emerald-400 font-extrabold uppercase tracking-wider bg-emerald-500/10 border border-emerald-500/20 px-1.5 py-0.5 rounded font-mono">
                            🟢 YES
                          </span>
                        ) : (
                          <span className="text-[11px] text-slate-500 font-extrabold uppercase tracking-wider bg-slate-800/50 border border-slate-750 px-1.5 py-0.5 rounded font-mono">
                            🔴 NO
                          </span>
                        )}
                      </td>
                      <td className="py-3 px-3 text-center">
                        {!call.feedback_submitted ? (
                          <span className="text-slate-500 font-mono text-[10.5px]">—</span>
                        ) : call.model_updated ? (
                          <span className="text-[11px] text-emerald-400 font-extrabold uppercase tracking-wider bg-emerald-500/10 border border-emerald-500/20 px-1.5 py-0.5 rounded font-mono">
                            🟢 Fine-Tuned
                          </span>
                        ) : (
                          <span className="text-[11px] text-amber-400 font-extrabold uppercase tracking-wider bg-amber-500/10 border border-amber-500/20 px-1.5 py-0.5 rounded animate-pulse font-mono" title="Queued for next model retuning run">
                            🟡 QUEUED
                          </span>
                        )}
                      </td>
                      <td className="py-3 px-3 max-w-[15rem] truncate text-slate-300">
                        <div className="font-extrabold text-white text-[11px] truncate">
                          {call.feedback_submitted && call.verified_incident ? (
                            <span className="text-emerald-400 font-bold" title="Verified Ground Truth">
                              {call.verified_incident}
                            </span>
                          ) : (
                            call.incident_type
                          )}
                        </div>
                        <div className="text-[10px] truncate mt-0.5 flex items-center gap-0.5">
                          {call.target?.map_coords_accurate === true ? (
                            <span className="text-emerald-400 font-extrabold" title="Map Coordinates Verified Accurate">📍✔️ </span>
                          ) : call.target?.map_coords_accurate === false ? (
                            <span className="text-rose-400 font-extrabold" title="Map Coordinates Flagged Inaccurate">📍⚠️ </span>
                          ) : (
                            <span className="text-slate-500" title="Map Coordinates Unverified">📍 </span>
                          )}
                          {call.feedback_submitted && call.verified_address ? (
                            <span className="text-emerald-400 font-bold" title="Verified Ground Truth">
                              {call.verified_address}
                            </span>
                          ) : (
                            call.target?.address || call.address || 'Unknown Address'
                          )}
                        </div>
                        <div className="text-[9px] text-slate-500 font-mono mt-0.5">
                          Units: {call.feedback_submitted && call.verified_units && call.verified_units.length > 0 ? (
                            <span className="text-emerald-400 font-bold" title="Verified Ground Truth">
                              {call.verified_units.join(', ')}
                            </span>
                          ) : (
                            call.responding_units?.join(', ') || 'None'
                          )}
                        </div>
                      </td>
                      <td className="py-3 px-3 text-right" onClick={(e) => e.stopPropagation()}>
                        <div className="flex gap-1.5 justify-end items-center">
                          {typeof onReviewCall === 'function' && (
                            <button
                              type="button"
                              onClick={() => onReviewCall(call)}
                              className="bg-amber-600 hover:bg-amber-500 text-white font-extrabold px-3 py-1 rounded-lg text-[10px] border border-amber-500/40 transition-all flex items-center gap-1 cursor-pointer shadow"
                              title="Replay this dispatch in Kiosk Mode as it was received"
                            >
                              ▶️ REVIEW
                            </button>
                          )}

                          {typeof onDeleteCall === 'function' && (
                            <button
                              type="button"
                              onClick={() => onDeleteCall(call.id, call.dispatch_id)}
                              className="bg-rose-950/30 hover:bg-rose-900/20 text-rose-400 hover:text-rose-300 font-bold px-2.5 py-1 rounded text-[10px] border border-rose-900/20 transition-all cursor-pointer flex items-center justify-center"
                              title="Delete dispatch entry"
                            >
                              🗑️
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
