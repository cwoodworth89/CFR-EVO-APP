import React, { useState, useEffect } from 'react';
import { supabase } from '../supabaseClient';

// Helper to format timestamps to Pacific Time matching database and local logs
const formatTimestampPT = (ts) => {
  if (!ts) return '';
  try {
    const d = new Date(ts);
    if (isNaN(d.getTime())) return ts;
    // Format to YYYY-MM-DD HH:MM:SS in Pacific Time (America/Los_Angeles)
    const formatter = new Intl.DateTimeFormat('en-US', {
      timeZone: 'America/Los_Angeles',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false
    });
    
    const parts = formatter.formatToParts(d);
    const partMap = {};
    parts.forEach(p => { partMap[p.type] = p.value; });
    
    return `${partMap.year}-${partMap.month}-${partMap.day} ${partMap.hour}:${partMap.minute}:${partMap.second}`;
  } catch (e) {
    try {
      const d = new Date(ts);
      return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}:${String(d.getSeconds()).padStart(2, '0')}`;
    } catch (err) {
      return ts;
    }
  }
};

export default function DispatchReview({ onClose, onLocateAddress }) {
  const [calls, setCalls] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedCall, setSelectedCall] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');

  // Database connection status state
  const [dbStatus, setDbStatus] = useState('checking'); // 'checking' | 'connected' | 'disconnected'
  const [dbError, setDbError] = useState(null);

  // Supabase Auth session states
  const [session, setSession] = useState(null);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loginLoading, setLoginLoading] = useState(false);
  const [loginError, setLoginError] = useState(null);

  // Form states for ground truth corrections
  const [verifiedTranscript, setVerifiedTranscript] = useState('');
  const [verifiedAddress, setVerifiedAddress] = useState('');
  const [verifiedIncident, setVerifiedIncident] = useState('');
  const [verifiedUnits, setVerifiedUnits] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [successMsg, setSuccessMsg] = useState('');
  const [showSimulator, setShowSimulator] = useState(false);

  // Load calls from Supabase
  const fetchCalls = async () => {
    setLoading(true);
    setDbStatus('checking');
    setDbError(null);
    try {
      const { data, error } = await supabase
        .from('live_calls')
        .select('*')
        .order('timestamp', { ascending: false });

      if (error) throw error;
      setCalls(data || []);
      setDbStatus('connected');
    } catch (err) {
      console.error('Error fetching dispatches:', err);
      setDbStatus('disconnected');
      setDbError(err.message || String(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // 1. Get initial session on mount
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session);
    });

    // 2. Listen for auth changes
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, newSession) => {
      setSession(newSession);
    });

    return () => {
      subscription.unsubscribe();
    };
  }, []);

  // Fetch calls & subscribe to realtime updates reactively based on session
  useEffect(() => {
    if (!session) {
      setCalls([]);
      setSelectedCall(null);
      setLoading(false);
      return;
    }

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
  }, [session]);

  const [audioSignedUrl, setAudioSignedUrl] = useState(null);

  // Update form fields & fetch secure signed audio URL when selectedCall changes
  useEffect(() => {
    if (selectedCall) {
      setVerifiedTranscript(selectedCall.verified_transcript || selectedCall.raw_transcript || '');
      setVerifiedAddress(selectedCall.verified_address || selectedCall.target?.address || selectedCall.address || '');
      setVerifiedIncident(selectedCall.verified_incident || selectedCall.incident_type || '');
      
      const units = selectedCall.verified_units || selectedCall.responding_units || [];
      setVerifiedUnits(units.join(', '));
      
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
          verified_alarm: 1,
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

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoginLoading(true);
    setLoginError(null);
    try {
      const { data, error } = await supabase.auth.signInWithPassword({
        email: email.trim(),
        password: password
      });
      if (error) throw error;
      setSession(data.session);
    } catch (err) {
      console.error('Login error:', err);
      setLoginError(err.message || String(err));
    } finally {
      setLoginLoading(false);
    }
  };

  if (!session) {
    return (
      <div className="absolute inset-0 bg-slate-950/95 backdrop-blur-md z-[2000] flex items-center justify-center p-6 text-slate-100 font-sans animate-in fade-in duration-200">
        <div className="w-full max-w-md bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-2xl flex flex-col gap-4 text-left border-sky-500/20">
          <div className="flex justify-between items-center border-b border-slate-800 pb-3">
            <h3 className="text-sm font-black text-sky-455 uppercase tracking-wider flex items-center gap-1.5">
              🛡️ ADMIN DASHBOARD LOGIN
            </h3>
            <button 
              type="button"
              onClick={onClose} 
              className="text-slate-400 hover:text-white text-xs font-bold font-mono cursor-pointer transition-colors"
            >
              ✕ CANCEL
            </button>
          </div>
          
          <p className="text-[11px] text-slate-400 leading-relaxed font-mono">
            This dashboard displays sensitive live dispatch data. Please enter your administrator credentials to access.
          </p>

          {loginError && (
            <div className="bg-rose-500/15 text-rose-400 border border-rose-500/20 rounded-xl p-3 text-xs font-mono font-bold animate-in shake duration-150">
              Error: {loginError}
            </div>
          )}

          <form onSubmit={handleLogin} className="flex flex-col gap-4 mt-2">
            <div className="flex flex-col gap-1.5">
              <label className="text-[9px] text-slate-405 font-extrabold uppercase font-mono tracking-wider">
                Admin Email Address
              </label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={loginLoading}
                className="w-full bg-slate-955 border border-slate-800 hover:border-slate-700 focus:border-sky-500 text-xs text-white rounded-xl px-3 py-2.5 focus:outline-none placeholder-slate-650"
                placeholder="admin@cfr-dispatch.com"
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-[9px] text-slate-405 font-extrabold uppercase font-mono tracking-wider">
                Security Password
              </label>
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={loginLoading}
                className="w-full bg-slate-955 border border-slate-800 hover:border-slate-700 focus:border-sky-500 text-xs text-white rounded-xl px-3 py-2.5 focus:outline-none placeholder-slate-650"
                placeholder="••••••••"
              />
            </div>

            <button
              type="submit"
              disabled={loginLoading}
              className="mt-2 bg-sky-500 hover:bg-sky-400 text-black font-extrabold py-3 px-6 rounded-xl w-full shadow-lg transition-all duration-150 flex items-center justify-center gap-1.5 cursor-pointer disabled:opacity-50"
            >
              {loginLoading ? (
                <>
                  <span className="animate-spin border-2 border-black border-t-transparent h-4 w-4 rounded-full"></span>
                  LOGGING IN...
                </>
              ) : (
                'LOG IN'
              )}
            </button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="absolute inset-0 bg-slate-950/95 backdrop-blur-md z-[2000] flex flex-col p-6 text-slate-100 font-sans animate-in fade-in duration-200">
      {/* Header */}
      <div className="flex justify-between items-center border-b border-slate-800 pb-4 mb-5 flex-shrink-0">
        <div>
          <h1 className="text-xl font-black text-sky-400 tracking-wider flex items-center gap-3 select-none">
            <span>🛡️ ADMIN DISPATCH REVIEW DASHBOARD</span>
            {dbStatus === 'connected' && (
              <span className="text-[10px] text-emerald-400 bg-emerald-500/10 border border-emerald-500/30 px-2 py-0.5 rounded-full font-mono font-bold uppercase tracking-wider flex items-center gap-1.5 animate-in fade-in duration-250">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                DB Connected
              </span>
            )}
            {dbStatus === 'checking' && (
              <span className="text-[10px] text-sky-400 bg-sky-500/10 border border-sky-500/30 px-2 py-0.5 rounded-full font-mono font-bold uppercase tracking-wider flex items-center gap-1.5">
                <span className="h-1.5 w-1.5 rounded-full bg-sky-450 animate-ping"></span>
                Checking DB...
              </span>
            )}
            {dbStatus === 'disconnected' && (
              <span className="text-[10px] text-rose-400 bg-rose-500/10 border border-rose-500/30 px-2 py-0.5 rounded-full font-mono font-bold uppercase tracking-wider flex items-center gap-1.5 animate-in shake duration-300" title={dbError || ''}>
                <span className="h-1.5 w-1.5 rounded-full bg-rose-550"></span>
                DB Error
              </span>
            )}
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
            onClick={async () => {
              await supabase.auth.signOut();
            }}
            className="bg-rose-950/45 border border-rose-900/40 hover:border-rose-500 hover:text-white text-rose-400 px-4 py-2 rounded-lg text-xs font-bold transition-all cursor-pointer shadow-md"
          >
            🚪 LOG OUT
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
            ) : dbStatus === 'disconnected' ? (
              <div className="flex flex-col items-center justify-center py-16 px-4 bg-rose-950/20 border border-rose-900/30 rounded-2xl text-center">
                <span className="text-3xl mb-2">⚠️</span>
                <h3 className="font-extrabold text-rose-455 uppercase text-xs tracking-wider">Database Connection Failed</h3>
                <p className="text-xs text-slate-400 mt-2 max-w-md font-mono leading-relaxed">
                  Could not load dispatches from Supabase. Ensure your client environment variables are correctly set in `client/.env.local` and your Supabase database has matching schema.
                </p>
                {dbError && (
                  <div className="mt-4 p-3 bg-slate-950/80 border border-slate-850 text-[10px] text-rose-400 font-mono rounded-lg max-w-lg overflow-x-auto text-left select-text">
                    Error Details: {dbError}
                  </div>
                )}
                <button
                  type="button"
                  onClick={fetchCalls}
                  className="mt-5 bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 border border-rose-500/35 px-4 py-2 rounded-lg text-xs font-bold transition-all cursor-pointer shadow-md"
                >
                  Retry Connection
                </button>
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
                              {formatTimestampPT(call.timestamp)}
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
                               Units: {call.responding_units?.join(', ') || 'None'}
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

                {/* Responding Units */}
                <div className="flex flex-col gap-1.5">
                  <div className="flex justify-between items-center">
                    <label className="text-[10px] text-slate-400 font-extrabold uppercase font-mono">
                      Verified Units
                    </label>
                    <span className="text-[8px] text-slate-500 font-bold truncate max-w-[150px]" title={selectedCall.responding_units?.join(', ')}>
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
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  const pollIntervalRef = React.useRef(null);
  const channelRef = React.useRef(null);

  useEffect(() => {
    let interval = null;
    if (simulating) {
      setElapsedSeconds(0);
      interval = setInterval(() => {
        setElapsedSeconds((prev) => prev + 1);
      }, 1000);
    } else {
      setElapsedSeconds(0);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [simulating]);

  // Clean up refs on unmount
  useEffect(() => {
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
      if (channelRef.current) {
        supabase.removeChannel(channelRef.current);
      }
    };
  }, []);

  const handleCancel = () => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
    if (channelRef.current) {
      supabase.removeChannel(channelRef.current);
      channelRef.current = null;
    }
    setSimulating(false);
    setStatusMsg("");
    setErrorMsg("Simulation cancelled by user.");
  };

  const handleClose = () => {
    handleCancel();
    onClose();
  };

  const handleTrigger = async (e) => {
    e.preventDefault();
    if (!audioFile) {
      alert("Please upload a .wav or .mp3 audio file to run the simulation.");
      return;
    }

    // Clear previous refs if any exist
    if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    if (channelRef.current) supabase.removeChannel(channelRef.current);

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
              if (pollIntervalRef.current) {
                clearInterval(pollIntervalRef.current);
                pollIntervalRef.current = null;
              }
              supabase.removeChannel(channel);
              channelRef.current = null;
            } else if (updated.status === 'failed') {
              setErrorMsg(updated.error_message || "Simulation failed in the backend pipeline.");
              setSimulating(false);
              setStatusMsg("");
              if (pollIntervalRef.current) {
                clearInterval(pollIntervalRef.current);
                pollIntervalRef.current = null;
              }
              supabase.removeChannel(channel);
              channelRef.current = null;
            }
          }
        )
        .subscribe();
      channelRef.current = channel;

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
              pollIntervalRef.current = null;
              setSimulationResult(pollData.result);
              setSimulating(false);
              setStatusMsg("");
              if (channelRef.current) {
                supabase.removeChannel(channelRef.current);
                channelRef.current = null;
              }
            } else if (pollData.status === 'failed') {
              clearInterval(pollInterval);
              pollIntervalRef.current = null;
              setErrorMsg(pollData.error_message || "Simulation failed in the backend pipeline.");
              setSimulating(false);
              setStatusMsg("");
              if (channelRef.current) {
                supabase.removeChannel(channelRef.current);
                channelRef.current = null;
              }
            } else if (pollData.status === 'processing') {
              setStatusMsg("Speech-to-Text & geocoding in progress...");
            }
          }
        } catch (err) {
          console.warn("Polling error:", err);
        }
      }, 3000);
      pollIntervalRef.current = pollInterval;

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
            onClick={handleClose} 
            className="text-slate-400 hover:text-white text-xs font-bold font-mono cursor-pointer transition-colors"
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
                  <div className="flex flex-col items-center justify-center py-4 text-amber-400 gap-2 w-full">
                    <style>{`
                      @keyframes shimmer {
                        0% { transform: translateX(-100%); }
                        100% { transform: translateX(100%); }
                      }
                      .animate-shimmer {
                        animation: shimmer 1.5s infinite linear;
                      }
                    `}</style>
                    <span className="flex h-3 w-3 relative">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75"></span>
                      <span className="relative inline-flex rounded-full h-3 w-3 bg-amber-500"></span>
                    </span>
                    <span className="text-[10px] font-bold font-mono tracking-widest uppercase mt-1 animate-pulse">
                      ⚙️ {statusMsg}
                    </span>
                    
                    {/* Time Elapsed & Progress Bar */}
                    <div className="text-[9px] text-slate-500 font-mono mt-1">
                      ⏱️ ELAPSED TIME: <span className="text-amber-400 font-bold">{elapsedSeconds}s</span>
                    </div>
                    
                    <div className="w-full max-w-md bg-slate-950 border border-slate-800/80 rounded-full h-3 overflow-hidden p-0.5 relative mt-1.5 shadow-inner">
                      <div 
                        className="h-full bg-gradient-to-r from-amber-500 via-sky-500 to-indigo-500 rounded-full transition-all duration-300 relative overflow-hidden"
                        style={{
                          width: `${Math.min(100, (elapsedSeconds / 30) * 100)}%`
                        }}
                      >
                        <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent animate-shimmer" style={{ width: '200%' }} />
                      </div>
                    </div>
                    
                    {elapsedSeconds > 15 && statusMsg.includes("Waiting") && (
                      <p className="text-[9px] text-rose-450 font-bold font-mono mt-2 animate-pulse text-center max-w-sm leading-relaxed bg-rose-500/10 border border-rose-500/20 px-3 py-1.5 rounded-lg">
                        ⚠️ AGENT DELAY: Make sure the Python agent is running ('python main.py' in agent folder) to process the request.
                      </p>
                    )}

                    <button
                      type="button"
                      onClick={handleCancel}
                      className="mt-2.5 bg-rose-500/15 hover:bg-rose-500/25 text-rose-400 hover:text-rose-350 border border-rose-500/20 hover:border-rose-500/30 font-black py-2 px-5 rounded-xl text-[10px] transition-all cursor-pointer font-mono uppercase tracking-wider"
                    >
                      ✕ Cancel & Reset Simulation
                    </button>
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
                      <div className="text-slate-300 mt-0.5">{formatTimestampPT(simulationResult.timestamp)}</div>
                    </div>
                    <div>
                      <div className="text-[9px] text-slate-500 uppercase font-black">Call Type</div>
                      <div className="text-slate-200 font-bold mt-0.5">{simulationResult.incident_type}</div>
                    </div>
                    <div>
                      <div className="text-[9px] text-slate-500 uppercase font-black">Uploaded File</div>
                      <div className="text-slate-200 font-bold mt-0.5 truncate max-w-[180px]" title={audioFile?.name || 'N/A'}>
                        {audioFile?.name || 'N/A'}
                      </div>
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
