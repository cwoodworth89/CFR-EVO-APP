import React, { useState, useEffect } from 'react';
import { supabase } from '../supabaseClient';

export default function DispatchReview({ onClose, onLocateAddress }) {
  const [calls, setCalls] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedCall, setSelectedCall] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');

  // Form states for ground truth corrections
  const [verifiedTranscript, setVerifiedTranscript] = useState('');
  const [verifiedAddress, setVerifiedAddress] = useState('');
  const [verifiedIncident, setVerifiedIncident] = useState('');
  const [verifiedUnits, setVerifiedUnits] = useState('');
  const [verifiedAlarm, setVerifiedAlarm] = useState(1);
  const [submitting, setSubmitting] = useState(false);
  const [successMsg, setSuccessMsg] = useState('');

  // Load calls from Supabase
  useEffect(() => {
    const fetchCalls = async () => {
      setLoading(true);
      try {
        const { data, error } = await supabase
          .from('live_calls')
          .select('*')
          .order('timestamp', { ascending: false });

        if (error) throw error;
        setCalls(data || []);
      } catch (err) {
        console.error('Error fetching dispatches:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchCalls();

    // Subscribe to realtime updates
    const channel = supabase
      .channel('live-calls-realtime')
      .on(
        'postgres_changes',
        { event: '*', schema: 'public', table: 'live_calls' },
        (payload) => {
          if (payload.eventType === 'INSERT') {
            setCalls((prev) => [payload.new, ...prev]);
          } else if (payload.eventType === 'UPDATE') {
            setCalls((prev) =>
              prev.map((c) => (c.id === payload.new.id ? payload.new : c))
            );
            // Update selected call state if it's the one being modified
            setSelectedCall((curr) =>
              curr && curr.id === payload.new.id ? payload.new : curr
            );
          } else if (payload.eventType === 'DELETE') {
            setCalls((prev) => prev.filter((c) => c.id !== payload.old.id));
            setSelectedCall((curr) =>
              curr && curr.id === payload.old.id ? null : curr
            );
          }
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, []);

  // Update form fields when selectedCall changes
  useEffect(() => {
    if (selectedCall) {
      setVerifiedTranscript(selectedCall.verified_transcript || selectedCall.raw_transcript || '');
      setVerifiedAddress(selectedCall.verified_address || selectedCall.target?.address || selectedCall.address || '');
      setVerifiedIncident(selectedCall.verified_incident || selectedCall.incident_type || '');
      
      const units = selectedCall.verified_units || selectedCall.responding_units || [];
      setVerifiedUnits(units.join(', '));
      
      setVerifiedAlarm(selectedCall.verified_alarm || selectedCall.alarm_level || 1);
      setSuccessMsg('');
    }
  }, [selectedCall]);

  const handleSelectCall = (call) => {
    setSelectedCall(call);
  };

  const handleViewOnMap = () => {
    if (!selectedCall) return;
    const target = selectedCall.target;
    if (target && target.lat && target.lng) {
      onLocateAddress(target);
      onClose(); // Close the review overlay to show map
    }
  };

  const handleSubmitReview = async (e) => {
    e.preventDefault();
    if (!selectedCall) return;

    setSubmitting(true);
    setSuccessMsg('');

    // Parse units back to array
    const unitsArray = verifiedUnits
      .split(',')
      .map((u) => u.trim())
      .filter((u) => u.length > 0);

    try {
      const { error } = await supabase
        .from('live_calls')
        .update({
          verified_transcript: verifiedTranscript,
          verified_address: verifiedAddress,
          verified_incident: verifiedIncident,
          verified_units: unitsArray,
          verified_alarm: parseInt(verifiedAlarm),
          feedback_submitted: true,
          // Clear verify location warning upon verification
          verify_location: false
        })
        .eq('id', selectedCall.id);

      if (error) throw error;
      setSuccessMsg('Review and corrections submitted successfully!');
    } catch (err) {
      console.error('Error updating call:', err);
      alert('Failed to submit corrections.');
    } finally {
      setSubmitting(false);
    }
  };

  // Filtered calls list based on search query
  const filteredCalls = calls.filter((c) => {
    const query = searchQuery.toLowerCase();
    const address = (c.target?.address || c.address || '').toLowerCase();
    const incident = (c.incident_type || '').toLowerCase();
    const id = (c.dispatch_id || '').toLowerCase();
    const transcript = (c.raw_transcript || '').toLowerCase();
    return address.includes(query) || incident.includes(query) || id.includes(query) || transcript.includes(query);
  });

  const getConfidenceColor = (score) => {
    if (score >= 80) return 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20';
    if (score >= 40) return 'text-amber-400 bg-amber-500/10 border-amber-500/20';
    return 'text-rose-400 bg-rose-500/10 border-rose-500/20';
  };

  return (
    <div className="absolute inset-0 bg-slate-950/90 backdrop-blur-md z-[2000] flex flex-col p-6 text-slate-100 font-sans animate-in fade-in duration-200">
      {/* Header */}
      <div className="flex justify-between items-center border-b border-slate-800 pb-4 mb-6 flex-shrink-0">
        <div>
          <h1 className="text-xl font-black text-sky-400 tracking-wider flex items-center gap-2">
            🛡️ ADMIN DISPATCH REVIEW DASHBOARD
          </h1>
          <p className="text-xs text-slate-400 mt-1 font-mono">
            Provide ground-truth feedback, edit location anomalies, and log transcript corrections.
          </p>
        </div>
        <button
          onClick={onClose}
          className="bg-slate-900 border border-slate-800 hover:border-slate-700 hover:text-white text-slate-400 px-4 py-2 rounded-lg text-xs font-bold transition-all cursor-pointer"
        >
          ✕ CLOSE DASHBOARD
        </button>
      </div>

      {/* Main Grid */}
      <div className="flex-grow flex gap-6 min-h-0 w-full overflow-hidden">
        {/* Left Column: Dispatches Table List */}
        <div className="flex-grow flex flex-col bg-slate-900 border border-slate-800 rounded-2xl p-4 overflow-hidden">
          <div className="flex justify-between items-center gap-4 mb-4 flex-shrink-0">
            <h2 className="text-sm font-extrabold uppercase tracking-wider text-slate-350">
              Captured Dispatches ({filteredCalls.length})
            </h2>
            <input
              type="text"
              placeholder="Search by ID, Address, Incident..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="bg-slate-950 border border-slate-800 hover:border-slate-700 focus:border-sky-500 text-white rounded-lg px-3 py-1.5 text-xs focus:outline-none placeholder-slate-500 w-64"
            />
          </div>

          {/* Table Container */}
          <div className="flex-grow overflow-y-auto pr-1">
            {loading ? (
              <div className="flex flex-col items-center justify-center py-20 text-slate-500 gap-2">
                <span className="flex h-4 w-4 relative">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-sky-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-4 w-4 bg-sky-500"></span>
                </span>
                <span className="text-[10px] font-bold font-mono tracking-widest uppercase">Fetching dispatch logs...</span>
              </div>
            ) : filteredCalls.length === 0 ? (
              <div className="text-center py-20 text-slate-500 text-xs italic">
                No dispatches found in the database.
              </div>
            ) : (
              <div className="flex flex-col gap-2.5">
                {filteredCalls.map((call) => (
                  <div
                    key={call.id}
                    onClick={() => handleSelectCall(call)}
                    className={`p-3.5 border rounded-xl cursor-pointer text-left transition-all flex justify-between items-center gap-4 ${
                      selectedCall?.id === call.id
                        ? 'bg-slate-800 border-sky-500 shadow-md shadow-sky-500/5'
                        : 'bg-slate-950/70 border-slate-850 hover:border-slate-700'
                    }`}
                  >
                    <div className="flex flex-col gap-1.5 min-w-0 flex-grow">
                      {/* Top row metadata */}
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-[10px] font-black text-sky-400 font-mono tracking-wider">
                          {call.dispatch_id}
                        </span>
                        <span className="text-slate-500 text-[10px] font-mono">
                          {new Date(call.timestamp).toLocaleString()}
                        </span>
                        
                        {/* Status badges */}
                        {call.feedback_submitted ? (
                          <span className="text-[8px] font-black px-1.5 py-0.2 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/20 tracking-wider">
                            ✓ REVIEWED
                          </span>
                        ) : call.verify_location ? (
                          <span className="text-[8px] font-black px-1.5 py-0.2 rounded bg-rose-500/20 text-rose-400 border border-rose-500/20 tracking-wider animate-pulse">
                            ⚠️ VERIFY LOCATION
                          </span>
                        ) : (
                          <span className="text-[8px] font-black px-1.5 py-0.2 rounded bg-slate-800 text-slate-400 border border-slate-750 tracking-wider">
                            PENDING
                          </span>
                        )}
                      </div>

                      {/* Incident and Responding Units */}
                      <div className="font-extrabold text-xs text-white leading-tight">
                        {call.verified_incident || call.incident_type} 
                        {call.responding_units && call.responding_units.length > 0 && (
                          <span className="text-slate-400 font-medium ml-2 bg-slate-900 border border-slate-850 px-1.5 py-0.5 rounded text-[10px] font-mono">
                            {(call.verified_units || call.responding_units).join(', ')}
                          </span>
                        )}
                      </div>

                      {/* Location */}
                      <div className="text-[11px] text-slate-350 truncate">
                        📍 {call.verified_address || call.target?.address || call.address || 'Unknown Location'}
                      </div>
                    </div>

                    {/* Confidence score indicator */}
                    <div className="flex flex-col items-end gap-1 flex-shrink-0">
                      <span className="text-[8px] text-slate-500 font-extrabold uppercase font-mono">GIS Match</span>
                      <span className={`px-2 py-0.5 rounded text-xs font-black border font-mono ${getConfidenceColor(call.confidence_score)}`}>
                        {call.confidence_score !== null ? `${Math.round(call.confidence_score)}%` : 'N/A'}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Corrections Form Panel */}
        <div className="w-[30rem] bg-slate-900 border border-slate-800 rounded-2xl p-5 flex flex-col overflow-y-auto flex-shrink-0">
          {!selectedCall ? (
            <div className="flex-grow flex flex-col items-center justify-center text-center text-slate-500 p-6">
              <span className="text-4xl mb-3">🛡️</span>
              <h3 className="font-bold text-slate-350 text-sm uppercase tracking-wider">Select a Dispatch</h3>
              <p className="text-xs text-slate-400 mt-1.5 max-w-[240px]">
                Click any dispatch on the left list to review its details and input verified ground-truth corrections.
              </p>
            </div>
          ) : (
            <form onSubmit={handleSubmitReview} className="flex-grow flex flex-col gap-4 text-left">
              <div className="border-b border-slate-800 pb-3 flex justify-between items-center flex-shrink-0">
                <div>
                  <h3 className="font-black text-white text-sm uppercase tracking-wide">
                    Review: {selectedCall.dispatch_id}
                  </h3>
                  <p className="text-[10px] text-slate-450 font-mono mt-0.5">
                    Original Score: {selectedCall.confidence_score}%
                  </p>
                </div>
                {selectedCall.target?.lat && selectedCall.target?.lng && (
                  <button
                    type="button"
                    onClick={handleViewOnMap}
                    className="bg-indigo-600 hover:bg-indigo-500 text-white font-extrabold px-3 py-1.5 rounded-lg text-[10px] transition-all flex items-center gap-1 shadow border border-indigo-500 cursor-pointer"
                  >
                    🗺️ VIEW ON MAP
                  </button>
                )}
              </div>

              {/* Success Notification */}
              {successMsg && (
                <div className="bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 rounded-xl p-3 text-xs font-semibold animate-in zoom-in duration-150">
                  {successMsg}
                </div>
              )}

              {/* Scrollable Fields */}
              <div className="flex-grow flex flex-col gap-4 overflow-y-auto pr-1">
                {/* Transcript side-by-side */}
                <div className="flex flex-col gap-1">
                  <span className="text-[10px] text-slate-450 font-extrabold uppercase font-mono">
                    Raw Transcript (STT Output)
                  </span>
                  <div className="bg-slate-950 p-2.5 rounded-xl border border-slate-850 text-xs text-slate-400 font-mono italic max-h-24 overflow-y-auto leading-relaxed select-text">
                    "{selectedCall.raw_transcript}"
                  </div>
                </div>

                <div className="flex flex-col gap-1.5">
                  <label className="text-[10px] text-slate-400 font-extrabold uppercase font-mono">
                    Verified Ground-Truth Transcript
                  </label>
                  <textarea
                    rows={3}
                    placeholder="Enter the confirmed dispatch transcript..."
                    value={verifiedTranscript}
                    onChange={(e) => setVerifiedTranscript(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 hover:border-slate-700 focus:border-sky-500 text-xs text-white rounded-xl p-2.5 focus:outline-none font-mono resize-none leading-relaxed"
                  />
                </div>

                {/* Location Input */}
                <div className="flex flex-col gap-1.5">
                  <label className="text-[10px] text-slate-400 font-extrabold uppercase font-mono">
                    Verified Address / Location
                  </label>
                  <input
                    type="text"
                    value={verifiedAddress}
                    onChange={(e) => setVerifiedAddress(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 hover:border-slate-700 focus:border-sky-500 text-xs text-white rounded-xl px-3 py-2 focus:outline-none"
                    placeholder="e.g. 2648 Sandstone Cres"
                  />
                </div>

                {/* Incident Type & Alarm Level Grid */}
                <div className="grid grid-cols-2 gap-4">
                  <div className="flex flex-col gap-1.5">
                    <label className="text-[10px] text-slate-400 font-extrabold uppercase font-mono">
                      Verified Incident Type
                    </label>
                    <input
                      type="text"
                      value={verifiedIncident}
                      onChange={(e) => setVerifiedIncident(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-800 hover:border-slate-700 focus:border-sky-500 text-xs text-white rounded-xl px-3 py-2 focus:outline-none"
                      placeholder="e.g. Structure Fire"
                    />
                  </div>

                  <div className="flex flex-col gap-1.5">
                    <label className="text-[10px] text-slate-400 font-extrabold uppercase font-mono">
                      Verified Alarm Level
                    </label>
                    <select
                      value={verifiedAlarm}
                      onChange={(e) => setVerifiedAlarm(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-800 hover:border-slate-700 focus:border-sky-500 text-xs text-white rounded-xl px-3 py-2 focus:outline-none cursor-pointer"
                    >
                      <option value={1}>1st Alarm</option>
                      <option value={2}>2nd Alarm</option>
                      <option value={3}>3rd Alarm</option>
                    </select>
                  </div>
                </div>

                {/* Responding Units */}
                <div className="flex flex-col gap-1.5">
                  <label className="text-[10px] text-slate-400 font-extrabold uppercase font-mono">
                    Verified Responding Units
                  </label>
                  <input
                    type="text"
                    value={verifiedUnits}
                    onChange={(e) => setVerifiedUnits(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 hover:border-slate-700 focus:border-sky-500 text-xs text-white rounded-xl px-3 py-2 focus:outline-none font-mono"
                    placeholder="e.g. E1, L1, M1 (comma separated)"
                  />
                </div>
              </div>

              {/* Submit Buttons */}
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
          )}
        </div>
      </div>
    </div>
  );
}
