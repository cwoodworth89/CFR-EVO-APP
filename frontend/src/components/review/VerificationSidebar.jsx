import React, { useRef, useEffect, useState } from 'react';
import { TALK_GROUPS, toTitleCase } from './verificationConstants';
import { API_BASE_URL } from '../../apiClient';

export default function VerificationSidebar({
  selectedCall,
  audioSignedUrl,
  audioRef,
  verifiedTranscript,
  setVerifiedTranscript,
  verifiedAddress,
  setVerifiedAddress,
  verifiedIncident,
  setVerifiedIncident,
  verifiedUnits,
  setVerifiedUnits,
  verifiedSubaddress,
  setVerifiedSubaddress,
  verifiedTalkgroup,
  setVerifiedTalkgroup,
  verifiedMapGrid,
  setVerifiedMapGrid,
  verifiedTones,
  setVerifiedTones,
  qualityRating,
  setQualityRating,
  reviewNotes,
  setReviewNotes,
  includeInTraining,
  setIncludeInTraining,
  stage1Open,
  setStage1Open,
  stage2Open,
  setStage2Open,
  stage3Open,
  setStage3Open,
  submitting,
  successMsg,
  onSubmitReview,
  onPrefillDefaults,
  onPrefillField,
  onReviewCall,
  formContainerRef: externalFormContainerRef,
}) {
  const localFormContainerRef = useRef(null);
  const formContainerRef = externalFormContainerRef || localFormContainerRef;
  const transcriptTextareaRef = useRef(null);

  const adjustTranscriptHeight = () => {
    if (transcriptTextareaRef.current) {
      const el = transcriptTextareaRef.current;
      el.style.height = 'auto';
      const scrollH = el.scrollHeight;
      const targetH = Math.min(Math.max(scrollH, 140), 320);
      el.style.height = `${targetH}px`;
    }
  };

  useEffect(() => {
    const timer = setTimeout(() => {
      adjustTranscriptHeight();
    }, 50);
    return () => clearTimeout(timer);
  }, [verifiedTranscript, selectedCall]);

  // Call types offered to the reviewer come from public.vocabulary -- the same list the
  // parser matches against. Previously this field was free text, so ground truth drifted
  // from the vocabulary: locale variants ("Smouldering"/"Smoldering") and pluralisations
  // were typed as rival terms, and seven verified values had no vocabulary row at all and
  // so could never be produced by the parser no matter how good the parse (punch-list #33).
  const [callTypes, setCallTypes] = useState([]);
  const [callTypesFailed, setCallTypesFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API_BASE_URL}/api/vocabulary?category=call_type`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data) => {
        if (cancelled) return;
        setCallTypes(Array.isArray(data) ? data : []);
        setCallTypesFailed(false);
      })
      .catch((err) => {
        if (cancelled) return;
        // Do NOT fall back to a hardcoded list. A stale local vocabulary is what this
        // change exists to remove; an empty picker that says so is the honest failure
        // (CLAUDE.md §6.1). The input stays usable as free text either way.
        console.error('Failed to load call_type vocabulary:', err);
        setCallTypes([]);
        setCallTypesFailed(true);
      });
    return () => { cancelled = true; };
  }, []);

  if (!selectedCall) {
    return (
      <div className="w-[28rem] bg-slate-900 border border-slate-800 rounded-2xl p-5 flex flex-col items-center justify-center text-center text-slate-500 flex-shrink-0">
        <span className="text-4xl mb-3">🛡️</span>
        <h3 className="font-bold text-slate-300 text-xs uppercase tracking-wider">Select a Dispatch</h3>
        <p className="text-xs text-slate-400 mt-2 max-w-[240px] leading-relaxed">
          Click any dispatch on the table to review its details, listen to audio, inspect satellite imagery, and input verified ground-truth corrections.
        </p>
      </div>
    );
  }

  const handleToneToggle = (tone) => {
    setVerifiedTones(prev =>
      prev.includes(tone)
        ? prev.filter(t => t !== tone)
        : [...prev, tone]
    );
  };

  const handleInputKeyDown = (e, fieldType) => {
    if ((e.ctrlKey && e.code === 'Space') || (e.altKey && e.key === 'Enter')) {
      e.preventDefault();
      onPrefillField(fieldType);
    }
  };


  return (
    <div className="w-[28rem] bg-slate-900 border border-slate-800 rounded-2xl p-5 flex flex-col overflow-y-auto flex-shrink-0">
      <form onSubmit={onSubmitReview} className="flex-grow flex flex-col gap-4 text-left">
        {/* Header with ID and Confidence */}
        <div className="border-b border-slate-800 pb-3 flex justify-between items-center flex-shrink-0">
          <div>
            <h3 className="font-black text-white text-sm uppercase tracking-wide font-mono">
              Review: {selectedCall.dispatch_id}
            </h3>
            <div className="flex items-center gap-1.5 mt-1">
              <span className="text-[10px] text-slate-400 font-mono">Confidence:</span>
              <span className={`text-[10.5px] font-mono font-bold px-1.5 py-0.5 rounded border ${
                selectedCall.confidence_score >= 80
                  ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20'
                  : selectedCall.confidence_score >= 40
                  ? 'text-amber-400 bg-amber-500/10 border-amber-500/20'
                  : 'text-rose-400 bg-rose-500/10 border-rose-500/20'
              }`}>
                {selectedCall.confidence_score !== undefined && selectedCall.confidence_score !== null
                  ? `${Math.round(selectedCall.confidence_score)}%`
                  : 'N/A'}
              </span>
            </div>
          </div>

          {typeof onReviewCall === 'function' && (
            <button
              type="button"
              onClick={() => onReviewCall(selectedCall)}
              className="bg-amber-600 hover:bg-amber-500 text-white font-extrabold px-3 py-1.5 rounded-lg text-[10px] transition-all flex items-center gap-1 shadow border border-amber-500/40 cursor-pointer"
              title="Replay this dispatch in Kiosk Mode as it was received"
            >
              ▶️ REVIEW
            </button>
          )}
        </div>

        {/* Success Notification */}
        {successMsg && (
          <div className="bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 rounded-xl p-3 text-xs font-semibold animate-in zoom-in duration-150">
            {successMsg}
          </div>
        )}

        {/* Scrollable Form Content */}
        <div ref={formContainerRef} className="flex-grow flex flex-col gap-4 overflow-y-auto pr-1">
          {/* Simple Clean Native Audio Player */}
          {selectedCall.audio_url && (
            <div className="bg-slate-950 border border-slate-800 rounded-xl p-3 flex flex-col gap-2 shadow-inner">
              <div className="flex justify-between items-center text-[10px] font-mono text-slate-400">
                <span className="flex items-center gap-1.5 text-sky-400 font-bold">
                  <span>🎙️</span>
                  <span>DISPATCH AUDIO RECORDING</span>
                </span>
                {selectedCall.audio_duration && (
                  <span className="text-slate-500 font-bold">{selectedCall.audio_duration.toFixed(1)}s</span>
                )}
              </div>
              <audio
                ref={audioRef}
                controls
                src={audioSignedUrl || selectedCall.audio_url}
                className="w-full h-8 rounded accent-sky-500 bg-slate-900"
              />
            </div>
          )}

          {/* 3-Stage Pipeline Flow Timeline */}
          <div className="flex flex-col gap-3 mt-1">
            <span className="text-[10px] text-slate-400 font-extrabold uppercase font-mono tracking-wider">
              Pipeline Execution Flow
            </span>

            <div className="relative border-l border-slate-800 pl-4 ml-2 flex flex-col gap-4">
              {/* Stage 1: Raw STT Output */}
              <div className="relative">
                <span className="absolute -left-[21px] top-1.5 flex h-2 w-2 rounded-full bg-slate-500 border border-slate-900 ring-4 ring-slate-950"></span>
                <div className="flex flex-col gap-1 bg-slate-950 border border-slate-850 rounded-xl p-3 shadow-inner">
                  <div
                    onClick={() => setStage1Open(!stage1Open)}
                    className="flex justify-between items-center cursor-pointer select-none"
                  >
                    <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wide font-mono flex items-center gap-1.5">
                      <span className="text-[8px] transition-transform duration-100">{stage1Open ? '▼' : '▶'}</span>
                      Stage 1: Raw STT Output
                    </span>
                    {(selectedCall.raw_transcript === "[Transcription Failed]" || !selectedCall.raw_transcript) && (
                      <span className="text-[8px] font-black px-1.5 py-0.5 rounded bg-rose-500/20 text-rose-400 border border-rose-500/20 tracking-wider">
                        FAILED
                      </span>
                    )}
                  </div>
                  {stage1Open && (
                    <div className="text-[11px] text-slate-400 font-mono italic mt-2 pt-2 border-t border-slate-850/50 leading-relaxed select-text select-all">
                      {selectedCall.raw_transcript || 'No transcript text captured'}
                    </div>
                  )}
                </div>
              </div>

              {/* Stage 2: Extracted Metadata */}
              <div className="relative">
                <span className="absolute -left-[21px] top-1.5 flex h-2 w-2 rounded-full bg-sky-500 border border-slate-900 ring-4 ring-slate-950"></span>
                <div className="flex flex-col gap-2 bg-sky-950/10 border border-sky-900/20 rounded-xl p-3 shadow-inner">
                  <div
                    onClick={() => setStage2Open(!stage2Open)}
                    className="flex justify-between items-center cursor-pointer select-none"
                  >
                    <span className="text-[10px] text-sky-400 font-bold uppercase tracking-wide font-mono flex items-center gap-1.5">
                      <span className="text-[8px] transition-transform duration-100">{stage2Open ? '▼' : '▶'}</span>
                      Stage 2: Extracted Metadata
                    </span>
                  </div>

                  {stage2Open && (
                    <div className="flex flex-wrap gap-2 pt-2 border-t border-sky-900/20">
                      <div className="flex flex-col gap-0.5">
                        <span className="text-[8px] text-slate-500 font-bold uppercase tracking-wider font-mono">Incident</span>
                        <span className="text-[10px] font-bold text-white bg-slate-950 border border-slate-850 px-2 py-0.5 rounded-lg">
                          {selectedCall.incident_type || 'Unknown'}
                        </span>
                      </div>

                      <div className="flex flex-col gap-0.5">
                        <span className="text-[8px] text-slate-500 font-bold uppercase tracking-wider font-mono">Address</span>
                        <span className="text-[10px] font-bold text-white bg-slate-950 border border-slate-850 px-2 py-0.5 rounded-lg flex items-center gap-1 max-w-[15rem] truncate" title={selectedCall.target?.address || selectedCall.address}>
                          📍 {selectedCall.target?.address || selectedCall.address || 'Unknown'}
                        </span>
                      </div>

                      <div className="flex flex-col gap-0.5">
                        <span className="text-[8px] text-slate-500 font-bold uppercase tracking-wider font-mono">Units</span>
                        <span className="text-[10px] font-mono text-white bg-slate-950 border border-slate-850 px-2 py-0.5 rounded-lg">
                          {selectedCall.responding_units?.join(', ') || 'None'}
                        </span>
                      </div>

                      <div className="flex flex-col gap-0.5">
                        <span className="text-[8px] text-slate-500 font-bold uppercase tracking-wider font-mono">Coordinates</span>
                        <span className="text-[10px] font-mono text-white bg-slate-950 border border-slate-850 px-2 py-0.5 rounded-lg">
                          {selectedCall.target?.lat && selectedCall.target?.lng 
                            ? `${selectedCall.target.lat.toFixed(4)}, ${selectedCall.target.lng.toFixed(4)}`
                            : 'Null'}
                        </span>
                      </div>

                      {selectedCall.target?.subaddress && (
                        <div className="flex flex-col gap-0.5">
                          <span className="text-[8px] text-slate-500 font-bold uppercase tracking-wider font-mono">Subaddress</span>
                          <span className="text-[10px] font-bold text-sky-400 bg-slate-950 border border-slate-850 px-2 py-0.5 rounded-lg">
                            🏢 {toTitleCase(selectedCall.target.subaddress)}
                          </span>
                        </div>
                      )}

                      {selectedCall.target?.intersection && (
                        <div className="flex flex-col gap-0.5">
                          <span className="text-[8px] text-slate-500 font-bold uppercase tracking-wider font-mono">Cross Roads</span>
                          <span className="text-[10px] font-bold text-amber-400 bg-slate-950 border border-slate-850 px-2 py-0.5 rounded-lg">
                            🔀 {selectedCall.target.intersection}
                          </span>
                        </div>
                      )}

                      {/* Calculated Response ETAs */}
                      {selectedCall.routing_metrics && selectedCall.routing_metrics.length > 0 && (
                        <div className="col-span-full flex flex-col gap-1.5 mt-2 bg-slate-950/90 border border-slate-800 p-2.5 rounded-xl">
                          <span className="text-[9px] text-slate-400 font-bold uppercase tracking-wider font-mono flex items-center gap-1.5">
                            <span>⏱️</span>
                            <span>Calculated Emergency Vehicle Response ETAs (Home Hall Origins)</span>
                          </span>
                          <div className="flex flex-wrap gap-2">
                            {selectedCall.routing_metrics.map((m, mIdx) => (
                              <div key={mIdx} className="flex items-center gap-2 bg-slate-900 border border-sky-500/40 px-2.5 py-1 rounded-lg text-[10px] font-mono shadow-sm">
                                <span className="text-white font-bold">{m.unit}</span>
                                <span className="text-slate-400">({m.hall_name || `Hall ${m.origin_hall}`})</span>
                                <span className="text-sky-300 font-bold bg-sky-950 px-1.5 py-0.5 rounded border border-sky-800/60">
                                  ⏱️ ~{m.eta_minutes} min ({m.road_distance_km || m.distance_km} km)
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>

              {/* Stage 3: Standardized Template Reconstruction */}
              <div className="relative">
                <span className="absolute -left-[21px] top-1.5 flex h-2 w-2 rounded-full bg-emerald-500 border border-slate-900 ring-4 ring-slate-950"></span>
                <div className="flex flex-col gap-1 bg-emerald-950/20 border border-emerald-900/30 rounded-xl p-3 shadow-inner">
                  <div
                    onClick={() => setStage3Open(!stage3Open)}
                    className="flex justify-between items-center cursor-pointer select-none"
                  >
                    <span className="text-[10px] text-emerald-400 font-bold uppercase tracking-wide font-mono flex items-center gap-1.5">
                      <span className="text-[8px] transition-transform duration-100">{stage3Open ? '▼' : '▶'}</span>
                      Stage 3: Standardized Template Reconstruction
                    </span>
                    <span className="text-[8px] font-black px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 tracking-wider">
                      HOMOPHONES RESOLVED
                    </span>
                  </div>
                  {stage3Open && (
                    <div className="text-[11px] text-slate-300 font-mono mt-2 pt-2 border-t border-emerald-900/30 leading-relaxed select-text select-all">
                      {selectedCall.sanitized_transcript || selectedCall.raw_transcript || 'No text'}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Verified Ground-Truth Transcript */}
          <div className="flex flex-col gap-1.5 bg-slate-950/60 p-3 border border-slate-850 rounded-xl">
            <div className="flex justify-between items-center">
              <label className="text-[10px] text-sky-400 font-extrabold uppercase font-mono tracking-wider">
                📝 Verified Ground-Truth Transcript
              </label>
              <button
                type="button"
                onClick={onPrefillDefaults}
                className="text-[9px] font-bold text-sky-400 hover:text-sky-300 bg-sky-950/40 border border-sky-900/30 px-2 py-0.5 rounded cursor-pointer transition-all hover:bg-sky-900/30 font-mono"
                title="Prefill transcript, address, incident type, and units using system-extracted data"
              >
                📋 Prefill All Fields
              </button>
            </div>
            <textarea
              ref={transcriptTextareaRef}
              rows={6}
              placeholder={selectedCall.sanitized_transcript || selectedCall.raw_transcript || "Enter confirmed transcript... (Ctrl+Space to prefill)"}
              value={verifiedTranscript}
              onChange={(e) => {
                setVerifiedTranscript(e.target.value);
                adjustTranscriptHeight();
              }}
              onKeyDown={(e) => {
                if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
                  e.preventDefault();
                  onSubmitReview(e);
                  return;
                }
                handleInputKeyDown(e, 'transcript');
              }}
              onDoubleClick={() => onPrefillField('transcript')}
              className="w-full min-h-[140px] max-h-[320px] bg-slate-950 border border-slate-800 hover:border-slate-700 focus:border-sky-500 text-xs text-white rounded-xl p-2.5 focus:outline-none font-mono leading-relaxed overflow-y-auto"
            />
          </div>

          {/* Tone Verification */}
          <div className="flex flex-col gap-1.5">
            <label className="text-[10px] text-slate-400 font-extrabold uppercase font-mono">
              Captured Dispatch Tone
            </label>
            <div className="grid grid-cols-3 gap-2">
              <button
                type="button"
                onClick={() => handleToneToggle('chief')}
                className={`py-2 rounded-xl text-[10px] font-extrabold uppercase font-mono border transition-all cursor-pointer flex items-center justify-center ${
                  verifiedTones.includes('chief')
                    ? 'bg-sky-500/20 border-sky-500/50 text-sky-400 shadow-[0_0_8px_rgba(14,165,233,0.2)] font-black'
                    : 'bg-slate-950 border-slate-800 text-slate-500 hover:border-slate-700'
                }`}
              >
                🔵 Chief
              </button>
              <button
                type="button"
                onClick={() => handleToneToggle('engine')}
                className={`py-2 rounded-xl text-[10px] font-extrabold uppercase font-mono border transition-all cursor-pointer flex items-center justify-center ${
                  verifiedTones.includes('engine')
                    ? 'bg-amber-500/20 border-amber-500/50 text-amber-400 shadow-[0_0_8px_rgba(245,158,11,0.2)] font-black'
                    : 'bg-slate-950 border-slate-800 text-slate-500 hover:border-slate-700'
                }`}
              >
                🟡 Engine
              </button>
              <button
                type="button"
                onClick={() => handleToneToggle('rescue')}
                className={`py-2 rounded-xl text-[10px] font-extrabold uppercase font-mono border transition-all cursor-pointer flex items-center justify-center ${
                  verifiedTones.includes('rescue')
                    ? 'bg-rose-500/20 border-rose-500/50 text-rose-400 shadow-[0_0_8px_rgba(244,63,94,0.2)] font-black'
                    : 'bg-slate-950 border-slate-800 text-slate-500 hover:border-slate-700'
                }`}
              >
                🔴 Rescue
              </button>
            </div>
          </div>

          {/* Responding Units */}
          <div className="flex flex-col gap-1.5">
            <div className="flex justify-between items-center">
              <label className="text-[10px] text-slate-400 font-extrabold uppercase font-mono">
                Verified Units
              </label>
              <span 
                onClick={() => onPrefillField('units')}
                className="text-[8px] text-slate-500 hover:text-sky-400 font-bold truncate max-w-[150px] cursor-pointer transition-colors" 
                title="Click, double-click input, or press Ctrl+Space to import"
              >
                Sys: {selectedCall.responding_units?.join(', ') || 'None'} 📥
              </span>
            </div>
            <input
              type="text"
              value={verifiedUnits}
              onChange={(e) => setVerifiedUnits(e.target.value)}
              onKeyDown={(e) => {
                if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { onSubmitReview(e); return; }
                handleInputKeyDown(e, 'units');
              }}
              onDoubleClick={() => onPrefillField('units')}
              className="w-full bg-slate-950 border border-slate-800 hover:border-slate-700 focus:border-sky-500 text-xs text-white rounded-xl px-3 py-2 focus:outline-none font-mono"
              placeholder={(selectedCall.responding_units || []).join(', ') || "e.g. E1, L1"}
            />
          </div>

          {/* Incident Type */}
          <div className="flex flex-col gap-1.5">
            <div className="flex justify-between items-center">
              <label className="text-[10px] text-slate-400 font-extrabold uppercase font-mono">
                Verified Incident Type
              </label>
              <span 
                onClick={() => onPrefillField('incident')}
                className="text-[8px] text-slate-500 hover:text-sky-400 font-bold cursor-pointer transition-colors" 
                title="Click, double-click input, or press Ctrl+Space to import"
              >
                System: {selectedCall.incident_type || 'Unknown'} 📥
              </span>
            </div>
            <input
              type="text"
              list="cfr-call-types"
              value={verifiedIncident}
              onChange={(e) => setVerifiedIncident(e.target.value)}
              onKeyDown={(e) => {
                if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { onSubmitReview(e); return; }
                handleInputKeyDown(e, 'incident');
              }}
              onDoubleClick={() => onPrefillField('incident')}
              className="w-full bg-slate-950 border border-slate-800 hover:border-slate-700 focus:border-sky-500 text-xs text-white rounded-xl px-3 py-2 focus:outline-none"
              placeholder={selectedCall.incident_type || "e.g. Structure Fire"}
            />
            <datalist id="cfr-call-types">
              {callTypes.map((ct) => (
                <option key={ct} value={ct} />
              ))}
            </datalist>
            {callTypesFailed && (
              <span className="text-[10px] text-amber-400">
                ⚠️ Call-type list unavailable — typed text is not validated
              </span>
            )}
          </div>

          {/* Location Input */}
          <div className="flex flex-col gap-1.5">
            <div className="flex justify-between items-center">
              <label className="text-[10px] text-slate-400 font-extrabold uppercase font-mono">
                Verified Address / Location
              </label>
              <span 
                onClick={() => onPrefillField('address')}
                className="text-[8px] text-slate-500 hover:text-sky-400 font-bold max-w-[180px] truncate cursor-pointer transition-colors" 
                title="Click, double-click input, or press Ctrl+Space to import"
              >
                System: {selectedCall.target?.address || selectedCall.address || 'Unknown'} 📥
              </span>
            </div>
            <input
              type="text"
              value={verifiedAddress}
              onChange={(e) => setVerifiedAddress(e.target.value)}
              onKeyDown={(e) => {
                if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { onSubmitReview(e); return; }
                handleInputKeyDown(e, 'address');
              }}
              onDoubleClick={() => onPrefillField('address')}
              className="w-full bg-slate-950 border border-slate-800 hover:border-slate-700 focus:border-sky-500 text-xs text-white rounded-xl px-3 py-2 focus:outline-none"
              placeholder={selectedCall.target?.address || selectedCall.address || "e.g. 2648 Sandstone Cres"}
            />
          </div>

          {/* Subaddress Input */}
          <div className="flex flex-col gap-1.5">
            <div className="flex justify-between items-center">
              <label className="text-[10px] text-slate-400 font-extrabold uppercase font-mono">
                Verified Subaddress / Unit / Business
              </label>
              <span 
                onClick={() => onPrefillField('subaddress')}
                className="text-[8px] text-slate-500 hover:text-sky-400 font-bold max-w-[180px] truncate cursor-pointer transition-colors" 
                title="Click, double-click input, or press Ctrl+Space to import"
              >
                System: {toTitleCase(selectedCall.target?.subaddress) || 'None'} 📥
              </span>
            </div>
            <input
              type="text"
              value={verifiedSubaddress}
              onChange={(e) => setVerifiedSubaddress(e.target.value)}
              onKeyDown={(e) => {
                if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { onSubmitReview(e); return; }
                handleInputKeyDown(e, 'subaddress');
              }}
              onDoubleClick={() => onPrefillField('subaddress')}
              className="w-full bg-slate-950 border border-slate-800 hover:border-slate-700 focus:border-sky-500 text-xs text-white rounded-xl px-3 py-2 focus:outline-none"
              placeholder={toTitleCase(selectedCall.target?.subaddress) || "None"}
            />
          </div>

          {/* Talk Group and Map Grid (Side-by-Side) */}
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <div className="flex justify-between items-center">
                <label className="text-[10px] text-slate-400 font-extrabold uppercase font-mono truncate" title="Verified Talk Group">
                  Talk Group
                </label>
                <span 
                  onClick={() => onPrefillField('talkgroup')}
                  className="text-[8px] text-slate-500 hover:text-sky-400 font-bold truncate max-w-[70px] cursor-pointer transition-colors" 
                  title="Click or press Ctrl+Space to import"
                >
                  Sys: {selectedCall.target?.radio_channel || 'None'} 📥
                </span>
              </div>
              <select
                value={verifiedTalkgroup}
                onChange={(e) => setVerifiedTalkgroup(e.target.value)}
                onKeyDown={(e) => {
                  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { onSubmitReview(e); return; }
                  handleInputKeyDown(e, 'talkgroup');
                }}
                className="w-full bg-slate-950 border border-slate-800 hover:border-slate-700 focus:border-sky-500 text-xs text-white rounded-xl px-3 py-2 focus:outline-none cursor-pointer"
              >
                <option value="">-- No Channel --</option>
                {TALK_GROUPS.map(tg => (
                  <option key={tg} value={tg}>{tg}</option>
                ))}
              </select>
            </div>

            <div className="flex flex-col gap-1.5">
              <div className="flex justify-between items-center">
                <label className="text-[10px] text-slate-400 font-extrabold uppercase font-mono truncate" title="Verified Map Grid">
                  Map Grid
                </label>
                <span 
                  onClick={() => onPrefillField('map_grid')}
                  className="text-[8px] text-slate-500 hover:text-sky-400 font-bold truncate max-w-[70px] cursor-pointer transition-colors" 
                  title="Click, double-click input, or press Ctrl+Space to import"
                >
                  Sys: {selectedCall.target?.map_grid || 'Unknown'} 📥
                </span>
              </div>
              <input
                type="text"
                value={verifiedMapGrid}
                onChange={(e) => setVerifiedMapGrid(e.target.value)}
                onKeyDown={(e) => {
                  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { onSubmitReview(e); return; }
                  handleInputKeyDown(e, 'map_grid');
                }}
                onDoubleClick={() => onPrefillField('map_grid')}
                className="w-full bg-slate-950 border border-slate-800 hover:border-slate-700 focus:border-sky-500 text-xs text-white rounded-xl px-3 py-2 focus:outline-none font-mono"
                placeholder={selectedCall.target?.map_grid || "e.g. 92"}
              />
            </div>
          </div>

          {/* HITL Quality Rating Selector */}
          <div className="flex flex-col gap-1.5 bg-slate-950 p-3 border border-slate-850 rounded-xl flex-shrink-0 mt-1">
            <label className="text-[10px] text-slate-400 font-extrabold uppercase font-mono tracking-wider">
              HITL Quality Rating
            </label>
            <div className="grid grid-cols-3 gap-2 mt-1">
              <button
                type="button"
                onClick={() => setQualityRating('PERFECT')}
                className={`py-2 px-1 text-[10px] font-bold rounded-lg border transition-all cursor-pointer text-center font-mono ${
                  qualityRating === 'PERFECT'
                    ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/50 shadow-sm'
                    : 'bg-slate-900 text-slate-400 border-slate-800 hover:border-slate-700'
                }`}
              >
                🟢 Perfect
              </button>
              <button
                type="button"
                onClick={() => setQualityRating('OPERATIONAL')}
                className={`py-2 px-1 text-[10px] font-bold rounded-lg border transition-all cursor-pointer text-center font-mono ${
                  qualityRating === 'OPERATIONAL'
                    ? 'bg-amber-500/20 text-amber-400 border-amber-500/50 shadow-sm'
                    : 'bg-slate-900 text-slate-400 border-slate-800 hover:border-slate-700'
                }`}
              >
                🟡 Operational
              </button>
              <button
                type="button"
                onClick={() => setQualityRating('FAILED')}
                className={`py-2 px-1 text-[10px] font-bold rounded-lg border transition-all cursor-pointer text-center font-mono ${
                  qualityRating === 'FAILED'
                    ? 'bg-rose-500/20 text-rose-400 border-rose-500/50 shadow-sm'
                    : 'bg-slate-900 text-slate-400 border-slate-800 hover:border-slate-700'
                }`}
              >
                🔴 Failed
              </button>
            </div>
          </div>

          {/* Review Notes / Agent Feedback */}
          <div className="flex flex-col gap-1.5 mt-1">
            <label className="text-[10px] text-slate-400 font-extrabold uppercase font-mono tracking-wider">
              📝 Review Notes / Agent Feedback
            </label>
            <textarea
              rows={2}
              value={reviewNotes}
              onChange={(e) => setReviewNotes(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 hover:border-slate-700 focus:border-sky-500 text-xs text-white rounded-xl px-3 py-2 focus:outline-none placeholder:text-slate-600 font-sans"
              placeholder="Enter human review notes, error explanations, or observations for AI agent review..."
            />
          </div>

          {/* Whisper Training Dataset Opt-In */}
          <div className="flex items-center gap-2 bg-slate-950 border border-slate-850 p-3 rounded-xl mt-1">
            <input
              type="checkbox"
              id="include_in_training"
              checked={includeInTraining}
              onChange={(e) => setIncludeInTraining(e.target.checked)}
              className="w-4 h-4 rounded border-slate-800 bg-slate-900 text-sky-500 focus:ring-sky-500 cursor-pointer"
            />
            <label htmlFor="include_in_training" className="text-[10px] text-slate-300 font-extrabold uppercase font-mono cursor-pointer select-none">
              Include in Whisper training dataset?
            </label>
            {selectedCall.audio_duration !== undefined && selectedCall.audio_duration < 35.0 && (
              <span className="text-[8px] text-rose-400 font-bold uppercase tracking-wider ml-auto animate-pulse" title="This call is under 35 seconds and appears to be cut off, so it is automatically excluded from Whisper training by default.">
                ⚠️ Cut-Off Default
              </span>
            )}
          </div>
        </div>

        {/* Submit Verification Button */}
        <div className="pt-3 border-t border-slate-800 mt-auto flex-shrink-0">
          <button
            type="submit"
            disabled={submitting}
            className="bg-emerald-500 hover:bg-emerald-400 text-black font-extrabold py-3 px-6 rounded-xl w-full shadow-lg transition-all duration-150 flex items-center justify-center gap-1.5 cursor-pointer disabled:opacity-50"
          >
            {submitting ? (
              <>
                <span className="animate-spin border-2 border-black border-t-transparent h-4 w-4 rounded-full"></span>
                SUBMITTING...
              </>
            ) : (
              'SUBMIT VERIFICATION'
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
