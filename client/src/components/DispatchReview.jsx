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
  const [showSimulator, setShowSimulator] = useState(false);

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

  const [audioSignedUrl, setAudioSignedUrl] = useState(null);

  // Update form fields & fetch secure signed audio URL when selectedCall changes
  useEffect(() => {
    if (selectedCall) {
      setVerifiedTranscript(selectedCall.verified_transcript || selectedCall.raw_transcript || '');
      setVerifiedAddress(selectedCall.verified_address || selectedCall.target?.address || selectedCall.address || '');
      setVerifiedIncident(selectedCall.verified_incident || selectedCall.incident_type || '');
      
      const units = selectedCall.verified_units || selectedCall.responding_units || [];
      setVerifiedUnits(units.join(', '));
      
      setVerifiedAlarm(selectedCall.verified_alarm || selectedCall.alarm_level || 1);
      setSuccessMsg('');
      
      // Securely fetch signed URL for private audio bucket
      const getSignedAudio = async () => {
        if (!selectedCall.audio_url) {
          setAudioSignedUrl(null);
          return;
        }
        
        const path = selectedCall.audio_url;
        
        if (path.includes('/storage/v1/object/')) {
          try {
            const parts = path.split('/');
            const filename = parts[parts.length - 1];
            
            const { data, error } = await supabase.storage
              .from('dispatch-audio')
              .createSignedUrl(filename, 300); // 5 minutes validity
              
            if (error) throw error;
            setAudioSignedUrl(data.signedUrl);
          } catch (err) {
            console.error('Error generating signed URL:', err);
            setAudioSignedUrl(path);
          }
        } else {
          setAudioSignedUrl(path);
        }
      };
      
      getSignedAudio();
    } else {
      setAudioSignedUrl(null);
    }
  }, [selectedCall]);

  const handleSelectCall = (call) => {
    setSelectedCall(call);
  };

  const handleViewOnMap = () => {
    if (!selectedCall) return;
    onLocateAddress(selectedCall);
    onClose(); // Close the review overlay to show map
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

  const getAudioUrl = (url) => {
    if (!url) return null;
    return url;
  };

  return (
    <div className="absolute inset-0 bg-slate-950/95 backdrop-blur-md z-[2000] flex flex-col p-6 text-slate-100 font-sans animate-in fade-in duration-200">
      {/* Header */}
      <div className="flex justify-between items-center border-b border-slate-800 pb-4 mb-5 flex-shrink-0">
        <div>
          <h1 className="text-xl font-black text-sky-400 tracking-wider flex items-center gap-2">
            🛡️ ADMIN DISPATCH REVIEW DASHBOARD
          </h1>
          <p className="text-xs text-slate-400 mt-1 font-mono">
            Provide ground-truth feedback, edit location anomalies, check audio quality, and review STT performance.
          </p>
        </div>
        <div className="flex gap-3 items-center">
          <button
            type="button"
            onClick={() => setShowSimulator(true)}
            className="bg-amber-500 hover:bg-amber-400 text-black px-4 py-2 rounded-lg text-xs font-black transition-all cursor-pointer shadow-md flex items-center gap-1 border border-amber-600"
          >
            ⚡ SIMULATE DISPATCH
          </button>
          <button
            type="button"
            onClick={onClose}
            className="bg-slate-900 border border-slate-800 hover:border-slate-700 hover:text-white text-slate-400 px-4 py-2 rounded-lg text-xs font-bold transition-all cursor-pointer shadow-md"
          >
            ✕ CLOSE DASHBOARD
          </button>
        </div>
      </div>

      {/* Main Grid */}
      <div className="flex-grow flex gap-5 min-h-0 w-full overflow-hidden">
        {/* Left Column: Dispatches Table List */}
        <div className="flex-grow flex flex-col bg-slate-900 border border-slate-800 rounded-2xl p-4 overflow-hidden">
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
            ) : filteredCalls.length === 0 ? (
              <div className="text-center py-20 text-slate-500 text-xs italic">
                No dispatches found in the database.
              </div>
            ) : (
              <div className="min-w-[800px]">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="border-b border-slate-800 text-[10px] text-slate-400 font-extrabold uppercase tracking-wider font-mono bg-slate-950/40 sticky top-0 backdrop-blur-sm">
                      <th className="py-2.5 px-3">Dispatch ID</th>
                      <th className="py-2.5 px-3">Recorded</th>
                      <th className="py-2.5 px-3">Audio</th>
                      <th className="py-2.5 px-3">System Prefills</th>
                      <th className="py-2.5 px-3">Raw Transcript</th>
                      <th className="py-2.5 px-3">Status</th>
                      <th className="py-2.5 px-3 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredCalls.map((call) => {
                      const isSelected = selectedCall?.id === call.id;
                      return (
                        <tr
                          key={call.id}
                          onClick={() => handleSelectCall(call)}
                          className={`border-b border-slate-850 hover:bg-slate-800/40 transition-all cursor-pointer text-xs ${
                            isSelected ? 'bg-slate-800/70 border-sky-500/40 shadow-sm' : ''
                          }`}
                        >
                          <td className="py-3 px-3 font-mono font-bold">
                            <div className="text-sky-400">{call.dispatch_id}</div>
                            <div className="text-[9px] text-slate-500 font-normal mt-0.5">
                              {new Date(call.timestamp).toLocaleString()}
                            </div>
                          </td>
                          <td className="py-3 px-3 font-mono font-bold text-slate-300">
                            {call.audio_duration ? `${call.audio_duration}s` : 'N/A'}
                          </td>
                          <td className="py-3 px-3">
                            {call.audio_url ? (
                              <span className="text-[10px] text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-1.5 py-0.5 rounded font-bold uppercase tracking-wider">
                                🎙️ Available
                              </span>
                            ) : (
                              <span className="text-[10px] text-slate-500 italic">—</span>
                            )}
                          </td>
                          <td className="py-3 px-3 max-w-[15rem] truncate text-slate-350">
                            <div className="font-extrabold text-white text-[11px] truncate">
                              {call.incident_type}
                            </div>
                            <div className="text-[10px] truncate mt-0.5">
                              📍 {call.target?.address || call.address || 'Unknown Address'}
                            </div>
                            <div className="text-[9px] text-slate-500 font-mono mt-0.5">
                              Alarm: {call.alarm_level} | Units: {call.responding_units?.join(', ') || 'None'}
                            </div>
                          </td>
                          <td className="py-3 px-3 max-w-[12rem] truncate text-slate-400 italic" title={call.raw_transcript}>
                            "{call.raw_transcript || 'No transcript text'}"
                          </td>
                          <td className="py-3 px-3">
                            {call.feedback_submitted ? (
                              <span className="text-[8px] font-black px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/20 tracking-wider">
                                ✓ REVIEWED
                              </span>
                            ) : call.verify_location ? (
                              <span className="text-[8px] font-black px-1.5 py-0.5 rounded bg-rose-500/20 text-rose-400 border border-rose-500/20 tracking-wider animate-pulse">
                                ⚠️ VERIFY
                              </span>
                            ) : (
                              <span className="text-[8px] font-black px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-750 tracking-wider">
                                PENDING
                              </span>
                            )}
                          </td>
                          <td className="py-3 px-3 text-right" onClick={(e) => e.stopPropagation()}>
                            <div className="flex gap-1.5 justify-end">
                              {call.target?.lat && call.target?.lng && (
                                <button
                                  onClick={() => {
                                    onLocateAddress(call);
                                    onClose();
                                  }}
                                  className="bg-indigo-650 hover:bg-indigo-600 text-white font-extrabold px-2 py-1 rounded text-[10px] border border-indigo-500/50 transition-all flex items-center gap-0.5 cursor-pointer shadow"
                                  title="Display Route & Hydrants on Map"
                                >
                                  🗺️ MAP
                                </button>
                              )}
                              <button
                                onClick={() => handleSelectCall(call)}
                                className="bg-slate-800 hover:bg-slate-750 text-slate-300 font-bold px-2 py-1 rounded text-[10px] border border-slate-700 transition-all cursor-pointer"
                              >
                                EDIT
                              </button>
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

        {/* Right Column: Corrections Form Panel */}
        <div className="w-[28rem] bg-slate-900 border border-slate-800 rounded-2xl p-5 flex flex-col overflow-y-auto flex-shrink-0">
          {!selectedCall ? (
            <div className="flex-grow flex flex-col items-center justify-center text-center text-slate-500 p-6">
              <span className="text-4xl mb-3">🛡️</span>
              <h3 className="font-bold text-slate-305 text-xs uppercase tracking-wider">Select a Dispatch</h3>
              <p className="text-xs text-slate-400 mt-2 max-w-[240px] leading-relaxed">
                Click any dispatch on the table to review its details, listen to audio, and input verified ground-truth corrections.
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
                {/* Audio Player in Details Form */}
                {selectedCall.audio_url && (
                  <div className="flex flex-col gap-1 bg-slate-950 p-3 border border-slate-850 rounded-xl">
                    <span className="text-[10px] text-slate-455 font-extrabold uppercase font-mono flex justify-between items-center">
                      <span>🎙️ Dispatch Recording</span>
                      <span className="text-sky-400">{selectedCall.audio_duration ? `${selectedCall.audio_duration}s` : ''}</span>
                    </span>
                    {audioSignedUrl ? (
                      <audio
                        src={audioSignedUrl}
                        controls
                        className="w-full mt-2 focus:outline-none animate-in fade-in duration-200"
                      />
                    ) : (
                      <div className="text-[10px] text-slate-500 font-mono mt-2 py-1.5 italic animate-pulse text-center">
                        Retrieving secure audio link...
                      </div>
                    )}
                  </div>
                )}

                {/* Transcript side-by-side */}
                <div className="flex flex-col gap-1">
                  <span className="text-[10px] text-slate-450 font-extrabold uppercase font-mono">
                    Raw Transcript (STT Output)
                  </span>
                  <div className="bg-slate-950 p-2.5 rounded-xl border border-slate-850 text-xs text-slate-400 font-mono italic max-h-24 overflow-y-auto leading-relaxed select-text">
                    "{selectedCall.raw_transcript || 'No transcript text captured'}"
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

                {/* Location Input (Prefilled side-by-side visual reminder) */}
                <div className="flex flex-col gap-1.5">
                  <div className="flex justify-between items-center">
                    <label className="text-[10px] text-slate-400 font-extrabold uppercase font-mono">
                      Verified Address / Location
                    </label>
                    <span className="text-[8px] text-slate-500 font-bold max-w-[180px] truncate" title={selectedCall.target?.address || selectedCall.address}>
                      System: {selectedCall.target?.address || selectedCall.address || 'Unknown'}
                    </span>
                  </div>
                  <input
                    type="text"
                    value={verifiedAddress}
                    onChange={(e) => setVerifiedAddress(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 hover:border-slate-700 focus:border-sky-500 text-xs text-white rounded-xl px-3 py-2 focus:outline-none"
                    placeholder="e.g. 2648 Sandstone Cres"
                  />
                </div>

                {/* Incident Type (Prefilled visual helper) */}
                <div className="flex flex-col gap-1.5">
                  <div className="flex justify-between items-center">
                    <label className="text-[10px] text-slate-400 font-extrabold uppercase font-mono">
                      Verified Incident Type
                    </label>
                    <span className="text-[8px] text-slate-500 font-bold">
                      System: {selectedCall.incident_type || 'Unknown'}
                    </span>
                  </div>
                  <input
                    type="text"
                    value={verifiedIncident}
                    onChange={(e) => setVerifiedIncident(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 hover:border-slate-700 focus:border-sky-500 text-xs text-white rounded-xl px-3 py-2 focus:outline-none"
                    placeholder="e.g. Structure Fire"
                  />
                </div>

                {/* Alarm Level & Responding Units */}
                <div className="grid grid-cols-2 gap-4">
                  <div className="flex flex-col gap-1.5">
                    <div className="flex justify-between items-center">
                      <label className="text-[10px] text-slate-400 font-extrabold uppercase font-mono">
                        Verified Alarm
                      </label>
                      <span className="text-[8px] text-slate-500 font-bold">
                        Sys: {selectedCall.alarm_level || 1}
                      </span>
                    </div>
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

                  <div className="flex flex-col gap-1.5">
                    <div className="flex justify-between items-center">
                      <label className="text-[10px] text-slate-400 font-extrabold uppercase font-mono">
                        Verified Units
                      </label>
                      <span className="text-[8px] text-slate-500 font-bold truncate max-w-[80px]" title={selectedCall.responding_units?.join(', ')}>
                        Sys: {selectedCall.responding_units?.join(', ') || 'None'}
                      </span>
                    </div>
                    <input
                      type="text"
                      value={verifiedUnits}
                      onChange={(e) => setVerifiedUnits(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-800 hover:border-slate-700 focus:border-sky-500 text-xs text-white rounded-xl px-3 py-2 focus:outline-none font-mono"
                      placeholder="e.g. E1, L1"
                    />
                  </div>
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
      {showSimulator && (
        <LiveDispatchSimulator 
          onClose={() => setShowSimulator(false)}
          onTriggered={(simCall) => {
            setShowSimulator(false);
            onLocateAddress(simCall);
          }}
        />
      )}
    </div>
  );
}

function LiveDispatchSimulator({ onClose, onTriggered }) {
  const [audioFile, setAudioFile] = useState(null);
  const [verifiedTranscript, setVerifiedTranscript] = useState('');
  const [simulating, setSimulating] = useState(false);
  const [statusMsg, setStatusMsg] = useState('');
  const [errorMsg, setErrorMsg] = useState('');
  const [simulationResult, setSimulationResult] = useState(null);

  const handleTrigger = async (e) => {
    e.preventDefault();
    if (!audioFile) {
      alert("Please upload a .wav or .mp3 audio file to run the simulation.");
      return;
    }

    setSimulating(true);
    setErrorMsg('');
    setSimulationResult(null);
    setStatusMsg("Uploading audio recording to Supabase storage...");

    try {
      // 1. Upload audio to 'dispatch-audio' bucket
      const fileExt = audioFile.name.split('.').pop();
      const fileName = `sim-${Date.now()}.${fileExt}`;
      
      const { data: uploadData, error: uploadError } = await supabase.storage
        .from('dispatch-audio')
        .upload(fileName, audioFile);
        
      if (uploadError) throw uploadError;

      // Get public URL of the uploaded file
      const { data: publicUrlData } = supabase.storage
        .from('dispatch-audio')
        .getPublicUrl(fileName);
        
      const audioUrl = publicUrlData.publicUrl;

      // 2. Insert simulation request into 'simulation_requests'
      setStatusMsg("Queueing request for Python pipeline...");
      const { data: insertData, error: insertError } = await supabase
        .from('simulation_requests')
        .insert([{
          audio_url: audioUrl,
          verified_transcript: verifiedTranscript.trim() || null,
          status: 'pending'
        }])
        .select();

      if (insertError) throw insertError;
      if (!insertData || insertData.length === 0) {
        throw new Error("Failed to create simulation request in database.");
      }

      const requestId = insertData[0].id;
      setStatusMsg("Waiting for Python agent to pickup request...");

      // 3. Subscribe to real-time updates for this specific request
      const channel = supabase
        .channel(`sim-${requestId}`)
        .on(
          'postgres_changes',
          {
            event: 'UPDATE',
            schema: 'public',
            table: 'simulation_requests',
            filter: `id=eq.${requestId}`
          },
          (payload) => {
            const updated = payload.new;
            if (updated.status === 'processing') {
              setStatusMsg("Speech-to-Text & geocoding in progress...");
            } else if (updated.status === 'completed') {
              setSimulationResult(updated.result);
              setSimulating(false);
              setStatusMsg("");
              supabase.removeChannel(channel);
            } else if (updated.status === 'failed') {
              setErrorMsg(updated.error_message || "Simulation failed in the backend pipeline.");
              setSimulating(false);
              setStatusMsg("");
              supabase.removeChannel(channel);
            }
          }
        )
        .subscribe();

      // Fallback polling in case realtime websocket fails or has delay
      const pollInterval = setInterval(async () => {
        try {
          const { data: pollData, error: pollError } = await supabase
            .from('simulation_requests')
            .select('*')
            .eq('id', requestId)
            .single();

          if (!pollError && pollData) {
            if (pollData.status === 'completed') {
              clearInterval(pollInterval);
              setSimulationResult(pollData.result);
              setSimulating(false);
              setStatusMsg("");
              supabase.removeChannel(channel);
            } else if (pollData.status === 'failed') {
              clearInterval(pollInterval);
              setErrorMsg(pollData.error_message || "Simulation failed in the backend pipeline.");
              setSimulating(false);
              setStatusMsg("");
              supabase.removeChannel(channel);
            } else if (pollData.status === 'processing') {
              setStatusMsg("Speech-to-Text & geocoding in progress...");
            }
          }
        } catch (err) {
          console.warn("Polling error:", err);
        }
      }, 3000);

      // Clean up interval on component unmount
      return () => {
        clearInterval(pollInterval);
        supabase.removeChannel(channel);
      };

    } catch (err) {
      console.error("Simulation request failed:", err);
      setErrorMsg(err.message || "Failed to trigger simulation.");
      setSimulating(false);
      setStatusMsg("");
    }
  };

  const getConfidenceColor = (score) => {
    if (score >= 80) return 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20';
    if (score >= 40) return 'text-amber-400 bg-amber-500/10 border-amber-500/20';
    return 'text-rose-400 bg-rose-500/10 border-rose-500/20';
  };

  return (
    <div className="fixed inset-0 bg-slate-950/90 backdrop-blur-sm z-[2500] flex items-center justify-center p-4">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-2xl w-full max-w-4xl text-left animate-in zoom-in-95 duration-150 flex flex-col max-h-[90vh] text-slate-100">
        
        {/* Header */}
        <div className="flex justify-between items-center border-b border-slate-800 pb-3 mb-4 flex-shrink-0">
          <h3 className="text-sm font-black text-amber-400 uppercase tracking-wider flex items-center gap-1.5">
            ⚡ LIVE PIPELINE DISPATCH SIMULATION
          </h3>
          <button 
            type="button"
            onClick={onClose} 
            disabled={simulating}
            className="text-slate-400 hover:text-white text-xs font-bold font-mono cursor-pointer"
          >
            ✕ CLOSE
          </button>
        </div>

        {/* Content Area */}
        <div className="flex-grow overflow-y-auto pr-1 flex flex-col gap-5">
          {!simulationResult ? (
            <form onSubmit={handleTrigger} className="flex flex-col gap-4">
              <p className="text-xs text-slate-400 leading-relaxed font-mono">
                Upload a raw audio recording file (.wav or .mp3) of a dispatch announcement to process it through the actual Speech-to-Text, parsing, geocoding, and dual-round alert matching backend.
              </p>

              {/* Error Message */}
              {errorMsg && (
                <div className="bg-rose-500/20 text-rose-400 border border-rose-500/30 rounded-xl p-3 text-xs font-mono font-bold animate-in shake duration-150">
                  ❌ Error: {errorMsg}
                </div>
              )}

              {/* Audio File Input */}
              <div className="flex flex-col gap-1.5">
                <label className="text-[9px] text-slate-400 font-extrabold uppercase font-mono tracking-wider">
                  Select Call Audio Recording (.wav / .mp3)
                </label>
                <div className="bg-slate-950 border border-slate-800 hover:border-slate-700 rounded-xl p-4 transition-all flex flex-col items-center justify-center border-dashed relative">
                  <input
                    type="file"
                    accept="audio/wav, audio/mpeg, audio/mp3"
                    onChange={(e) => setAudioFile(e.target.files[0])}
                    disabled={simulating}
                    className="absolute inset-0 opacity-0 cursor-pointer w-full h-full"
                  />
                  <span className="text-2xl mb-1">🎙️</span>
                  <span className="text-xs font-bold text-slate-300">
                    {audioFile ? audioFile.name : "Drag & drop or click to choose audio file"}
                  </span>
                  {audioFile && (
                    <span className="text-[10px] text-slate-500 font-mono mt-1">
                      Size: {(audioFile.size / (1024 * 1024)).toFixed(2)} MB
                    </span>
                  )}
                </div>
              </div>

              {/* Verified Transcript Input */}
              <div className="flex flex-col gap-1.5">
                <label className="text-[9px] text-slate-400 font-extrabold uppercase font-mono tracking-wider">
                  Verification Transcript (Optional Ground Truth)
                </label>
                <textarea
                  rows={4}
                  value={verifiedTranscript}
                  onChange={(e) => setVerifiedTranscript(e.target.value)}
                  disabled={simulating}
                  placeholder="Paste the expected ground truth text here. The pipeline will compare the Speech-to-Text output against this to verify accuracy..."
                  className="w-full bg-slate-950 border border-slate-800 text-xs text-white rounded-xl p-2.5 focus:outline-none focus:border-amber-500 font-mono resize-none leading-relaxed"
                />
              </div>

              {/* Status & Submit */}
              <div className="border-t border-slate-850 pt-4 mt-2 flex flex-col gap-3">
                {statusMsg && (
                  <div className="flex flex-col items-center justify-center py-4 text-amber-400 gap-2">
                    <span className="flex h-3 w-3 relative">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75"></span>
                      <span className="relative inline-flex rounded-full h-3 w-3 bg-amber-500"></span>
                    </span>
                    <span className="text-[10px] font-bold font-mono tracking-widest uppercase mt-1 animate-pulse">
                      ⚙️ {statusMsg}
                    </span>
                  </div>
                )}
                
                <button
                  type="submit"
                  disabled={simulating || !audioFile}
                  className="bg-amber-500 hover:bg-amber-400 disabled:opacity-50 text-black font-black py-3 px-6 rounded-xl w-full transition-all duration-150 flex items-center justify-center gap-1.5 cursor-pointer shadow-lg border border-amber-600 uppercase text-xs tracking-wider"
                >
                  {simulating ? (
                    <>
                      <span className="animate-spin border-2 border-black border-t-transparent h-4 w-4 rounded-full"></span>
                      RUNNING SIMULATION PIPELINE...
                    </>
                  ) : (
                    "🚀 RUN PIPELINE SIMULATION"
                  )}
                </button>
              </div>
            </form>
          ) : (
            // Simulation Report Screen
            <div className="flex flex-col gap-5 animate-in fade-in duration-200">
              
              {/* Alert Header */}
              <div className="bg-emerald-500/10 border border-emerald-500/20 rounded-xl p-3 flex justify-between items-center">
                <span className="text-xs font-bold text-emerald-400 font-mono flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse"></span>
                  SIMULATION PROCESSING PIPELINE COMPLETED SUCCESSFULLY
                </span>
                <span className="text-[10px] text-slate-500 font-mono font-bold uppercase">
                  ID: {simulationResult.dispatch_id}
                </span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                
                {/* Left Column: Extracted Metadata */}
                <div className="flex flex-col gap-4 bg-slate-950/50 border border-slate-850 p-4 rounded-xl">
                  <h4 className="text-[10px] text-sky-400 font-extrabold uppercase tracking-widest border-b border-slate-850 pb-1.5 font-mono">
                    📊 EXTRACTED METADATA
                  </h4>
                  
                  <div className="grid grid-cols-2 gap-x-4 gap-y-3.5 text-xs font-mono">
                    <div>
                      <div className="text-[9px] text-slate-500 uppercase font-black">Call ID</div>
                      <div className="text-sky-400 font-bold mt-0.5">{simulationResult.dispatch_id}</div>
                    </div>
                    <div>
                      <div className="text-[9px] text-slate-500 uppercase font-black">Timestamp</div>
                      <div className="text-slate-300 mt-0.5">{new Date(simulationResult.timestamp).toLocaleString()}</div>
                    </div>
                    <div>
                      <div className="text-[9px] text-slate-500 uppercase font-black">Call Type</div>
                      <div className="text-slate-200 font-bold mt-0.5">{simulationResult.incident_type}</div>
                    </div>
                    <div>
                      <div className="text-[9px] text-slate-500 uppercase font-black">Alarm Level</div>
                      <div className="text-slate-200 font-bold mt-0.5">{simulationResult.alarm_level} Alarm</div>
                    </div>
                    <div className="col-span-2">
                      <div className="text-[9px] text-slate-500 uppercase font-black">Responding Units</div>
                      <div className="flex gap-1.5 flex-wrap mt-1">
                        {simulationResult.responding_units && simulationResult.responding_units.length > 0 ? (
                          simulationResult.responding_units.map((unit, idx) => (
                            <span key={idx} className="bg-slate-800 border border-slate-700 text-sky-400 font-black px-2 py-0.5 rounded text-[10px]">
                              {unit}
                            </span>
                          ))
                        ) : (
                          <span className="text-slate-500 italic">None Extracted</span>
                        )}
                      </div>
                    </div>
                    <div>
                      <div className="text-[9px] text-slate-500 uppercase font-black">Parsed Address</div>
                      <div className="text-slate-200 font-bold mt-0.5 truncate" title={simulationResult.target?.address || simulationResult.address}>
                        {simulationResult.target?.address || simulationResult.address || "N/A"}
                      </div>
                    </div>
                    <div>
                      <div className="text-[9px] text-slate-500 uppercase font-black">Cross Roads</div>
                      <div className="text-slate-200 font-bold mt-0.5 truncate" title={simulationResult.intersection}>
                        {simulationResult.intersection || "N/A"}
                      </div>
                    </div>
                    <div>
                      <div className="text-[9px] text-slate-500 uppercase font-black">Radio Channel</div>
                      <div className="text-amber-400 font-bold mt-0.5">Talk Group {simulationResult.radio_channel || "N/A"}</div>
                    </div>
                    <div>
                      <div className="text-[9px] text-slate-500 uppercase font-black">Map Grid</div>
                      <div className="text-amber-400 font-bold mt-0.5">Grid {simulationResult.map_grid || "N/A"}</div>
                    </div>
                    <div>
                      <div className="text-[9px] text-slate-500 uppercase font-black">Pipeline Confidence</div>
                      <div className="mt-1 font-bold">
                        <span className={`px-2 py-0.5 rounded text-[10px] border ${getConfidenceColor(simulationResult.confidence_score)}`}>
                          {simulationResult.confidence_score.toFixed(1)}%
                        </span>
                      </div>
                    </div>
                    <div>
                      <div className="text-[9px] text-slate-500 uppercase font-black">Dual-Round Matching</div>
                      <div className="text-slate-300 font-bold mt-0.5">
                        Recorded: {simulationResult.second_round_recorded ? "Yes" : "No"} | Matched: {simulationResult.second_round_matched ? "Yes" : "No"}
                      </div>
                    </div>
                  </div>
                </div>

                {/* Right Column: Transcription & Verification */}
                <div className="flex flex-col gap-4 bg-slate-950/50 border border-slate-850 p-4 rounded-xl">
                  <h4 className="text-[10px] text-sky-400 font-extrabold uppercase tracking-widest border-b border-slate-850 pb-1.5 font-mono">
                    🎙️ PIPELINE TRANSCRIPTION & VERIFICATION
                  </h4>

                  <div className="flex flex-col gap-3.5">
                    {/* Pipeline STT Output */}
                    <div className="flex flex-col gap-1">
                      <span className="text-[9px] text-slate-500 uppercase font-black font-mono">Sanitized Speech-To-Text Output</span>
                      <div className="bg-slate-950 border border-slate-850 p-3 rounded-xl text-xs font-mono text-slate-350 italic max-h-32 overflow-y-auto leading-relaxed select-text">
                        "{simulationResult.raw_transcript || "No transcript output generated."}"
                      </div>
                    </div>

                    {/* Ground-Truth Verification */}
                    {simulationResult.verified_transcript && (
                      <div className="flex flex-col gap-1.5">
                        <div className="flex justify-between items-center font-mono">
                          <span className="text-[9px] text-slate-500 uppercase font-black">Ground-Truth Verification Transcript</span>
                          <span className="text-[10px] font-bold text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-1.5 py-0.5 rounded">
                            Accuracy Match: {simulationResult.transcript_accuracy}%
                          </span>
                        </div>
                        <div className="bg-slate-950 border border-slate-850 p-3 rounded-xl text-xs font-mono text-slate-355 italic max-h-32 overflow-y-auto leading-relaxed select-text">
                          "{simulationResult.verified_transcript}"
                        </div>
                      </div>
                    )}
                  </div>
                </div>

              </div>

              {/* Action Buttons */}
              <div className="border-t border-slate-800 pt-4 mt-2 flex gap-4">
                <button
                  type="button"
                  onClick={() => onTriggered(simulationResult)}
                  className="bg-sky-500 hover:bg-sky-400 text-black font-black py-3 px-6 rounded-xl flex-grow transition-all duration-150 flex items-center justify-center gap-1.5 cursor-pointer shadow-lg border border-sky-600 uppercase text-xs tracking-wider"
                >
                  🗺️ WAKE UP KIOSK HUD OVERRIDE
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setSimulationResult(null);
                    setAudioFile(null);
                    setVerifiedTranscript('');
                    setErrorMsg('');
                  }}
                  className="bg-slate-850 hover:bg-slate-800 border border-slate-750 text-slate-200 font-bold py-3 px-6 rounded-xl transition-all duration-150 flex items-center justify-center gap-1.5 cursor-pointer text-xs"
                >
                  🔄 TEST ANOTHER RECORDING
                </button>
              </div>

            </div>
          )}
        </div>

      </div>
    </div>
  );
}
