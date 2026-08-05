import React, { useState, useEffect, useRef } from 'react';
import { apiClient, API_BASE_URL } from '../apiClient';
import { useDispatchListener } from '../hooks/useDispatchListener';

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

const TALK_GROUPS = [
  "5",
  "6",
  "7",
  "8",
  "9",
  "10 Combined Response",
  "Combined Venue Port Mann",
  "Combined Venue Transit System"
];

const toTitleCase = (str) => {
  if (!str) return '';
  return str.replace(/\b\w/g, c => c.toUpperCase());
};

export default function DispatchReview({ onClose, onSimulateCall }) {
  const [calls, setCalls] = useState([]);
  const [evalHistory, setEvalHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedCall, setSelectedCall] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');

  // Database connection status state
  const [dbStatus, setDbStatus] = useState('checking'); // 'checking' | 'connected' | 'disconnected'
  const [dbError, setDbError] = useState(null);

  // RF Listener status state
  const [listenerStatus, setListenerStatus] = useState('checking'); // 'checking' | 'online' | 'offline'
  const [listenerDetails, setListenerDetails] = useState(null);

  // Auth session states
  const [session, setSession] = useState(null);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loginLoading, setLoginLoading] = useState(false);
  const [loginError, setLoginError] = useState(null);

  // Form states for ground truth corrections
  const [verifiedTranscript, setVerifiedTranscript] = useState('');
  const [verifiedAddress, setVerifiedAddress] = useState('');
  const [verifiedIncident, setVerifiedIncident] = useState('');
  const [verifiedUnits, setVerifiedUnits] = useState('');
  const [qualityRating, setQualityRating] = useState('PENDING');
  const [verifiedSubaddress, setVerifiedSubaddress] = useState('');
  const [verifiedTalkgroup, setVerifiedTalkgroup] = useState('');
  const [verifiedMapGrid, setVerifiedMapGrid] = useState('');
  const [includeInTraining, setIncludeInTraining] = useState(true);
  const [reviewNotes, setReviewNotes] = useState('');
  const [verifiedTones, setVerifiedTones] = useState([]);
  const [submitting, setSubmitting] = useState(false);
  const [successMsg, setSuccessMsg] = useState('');
  const [stage1Open, setStage1Open] = useState(false);
  const [stage2Open, setStage2Open] = useState(false);
  const [stage3Open, setStage3Open] = useState(true);

  // Load calls from local FastAPI gateway
  const fetchCalls = async () => {
    setLoading(true);
    setDbStatus('checking');
    setDbError(null);
    try {
      const data = await apiClient.dispatches.fetchAll();
      setCalls(data || []);
      
      try {
        const evalData = await apiClient.evaluations.fetchAll();
        setEvalHistory(evalData || []);
      } catch (e) {
        // non-fatal
      }
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
    apiClient.auth.getSession().then(({ data: { session } }) => {
      setSession(session);
    });

    // 2. Listen for auth changes
    const { data: { subscription } } = apiClient.auth.onAuthStateChange((_event, newSession) => {
      setSession(newSession);
    });

    return () => {
      if (subscription && typeof subscription.unsubscribe === 'function') {
        subscription.unsubscribe();
      }
    };
  }, []);

  const checkListenerStatus = async () => {
    try {
      const data = await apiClient.listener.fetchStatus();
      setListenerStatus(data.status === 'online' ? 'online' : 'offline');
      setListenerDetails(data);
    } catch (e) {
      setListenerStatus('offline');
      setListenerDetails({ message: e.message || 'Listener status unreachable' });
    }
  };

  // Fetch calls & poll listener status on session load
  useEffect(() => {
    if (!session) {
      setCalls([]);
      setSelectedCall(null);
      setLoading(false);
      return;
    }

    fetchCalls();
    checkListenerStatus();

    const interval = setInterval(() => {
      checkListenerStatus();
    }, 10000);

    return () => clearInterval(interval);
  }, [session]);

  // Real-time MQTT listener for dispatches across all 4 station kiosks
  useDispatchListener({
    enabled: !!session,
    onInsert: (dispatch) => {
      setCalls((prev) => [dispatch.rawRecord || dispatch, ...prev]);
    },
    onUpdate: (dispatch) => {
      const updated = dispatch.rawRecord || dispatch;
      setCalls((prev) => prev.map((c) => (c.id === updated.id || c.dispatch_id === updated.dispatch_id ? updated : c)));
      setSelectedCall((curr) => (curr && (curr.id === updated.id || curr.dispatch_id === updated.dispatch_id) ? updated : curr));
    },
    onDelete: (dispatch) => {
      const deleted = dispatch.rawRecord || dispatch;
      setCalls((prev) => prev.filter((c) => c.id !== deleted.id && c.dispatch_id !== deleted.dispatch_id));
      setSelectedCall((curr) => (curr && (curr.id === deleted.id || curr.dispatch_id === deleted.dispatch_id) ? null : curr));
    }
  });

  const [audioSignedUrl, setAudioSignedUrl] = useState(null);
  const prevSelectedCallIdRef = React.useRef(null);
  const prevAudioUrlRef = useRef(null);

  const deriveTonesFromUnitsList = (units) => {
    const derived = [];
    units.forEach(u => {
      const lowerUnit = u.trim().toLowerCase();
      if (lowerUnit.startsWith('e') || lowerUnit.includes('engine')) {
        derived.push('engine');
      }
      if (lowerUnit.startsWith('m') || lowerUnit.startsWith('r') || lowerUnit.includes('medic') || lowerUnit.includes('rescue')) {
        derived.push('rescue');
      }
      if (lowerUnit.startsWith('c') || lowerUnit.includes('car') || lowerUnit.includes('chief')) {
        derived.push('chief');
      }
    });
    return derived;
  };

  const getCallTones = (call) => {
    if (!call) return [];
    const dbTones = (call.target?.tone_name || '')
      .split(',')
      .map(t => {
        const clean = t.trim().toLowerCase();
        if (clean.includes('chief')) return 'chief';
        if (clean.includes('engine')) return 'engine';
        if (clean.includes('rescue')) return 'rescue';
        return clean;
      })
      .filter(Boolean);
    const units = (call.verified_units && call.verified_units.length > 0)
      ? call.verified_units
      : (call.responding_units || []);
    const derived = deriveTonesFromUnitsList(units);
    return Array.from(new Set([...dbTones, ...derived]));
  };

  // Update form fields & fetch secure signed audio URL when selectedCall changes
  useEffect(() => {
    if (selectedCall) {
      const isDifferentCall = prevSelectedCallIdRef.current !== selectedCall.id;
      prevSelectedCallIdRef.current = selectedCall.id;
      
      if (isDifferentCall) {
        setVerifiedTranscript(selectedCall.verified_transcript || '');
        setVerifiedAddress(selectedCall.verified_address || '');
        setVerifiedSubaddress(selectedCall.feedback_submitted ? toTitleCase(selectedCall.target?.subaddress || '') : '');
        setVerifiedMapGrid(selectedCall.target?.verified_map_grid || '');
        setVerifiedTalkgroup(selectedCall.target?.verified_talkgroup || selectedCall.target?.radio_channel || '');
        setVerifiedIncident(selectedCall.verified_incident || '');
        setQualityRating(selectedCall.quality_rating || 'PENDING');
        setReviewNotes(selectedCall.target?.review_notes || selectedCall.review_notes || '');
        
        // Auto-default training checkbox: false for < 35s audio_duration, true otherwise
        const defaultInclude = selectedCall.audio_duration !== undefined && selectedCall.audio_duration !== null 
          ? selectedCall.audio_duration >= 35.0 
          : true;
        const isInclude = selectedCall.target?.include_in_training !== undefined 
          ? selectedCall.target.include_in_training 
          : defaultInclude;
        setIncludeInTraining(isInclude);
        
        const displayUnits = selectedCall.verified_units || [];
        setVerifiedUnits(displayUnits.join(', '));
        
        const rawTonesStr = selectedCall.target?.tone_name;
        let initialTones = [];
        if (rawTonesStr) {
          initialTones = rawTonesStr.split(',')
            .map(t => {
              const clean = t.trim().toLowerCase();
              if (clean.includes('chief')) return 'chief';
              if (clean.includes('engine')) return 'engine';
              if (clean.includes('rescue')) return 'rescue';
              return clean;
            })
            .filter(Boolean);
        } else {
          const checkUnits = selectedCall.responding_units || [];
          initialTones = deriveTonesFromUnitsList(checkUnits);
        }
        setVerifiedTones(initialTones);
        
        setSuccessMsg('');
      }
      
      // Resolve audio URL directly from local FastAPI static server
      const getSignedAudio = async () => {
        if (!selectedCall.audio_url) {
          setAudioSignedUrl(null);
          prevAudioUrlRef.current = null;
          return;
        }
        
        let path = selectedCall.audio_url;
        if (!path.startsWith('http')) {
          path = `${API_BASE_URL}${path.startsWith('/') ? '' : '/'}${path}`;
        }
        setAudioSignedUrl(path);
      };
      
      getSignedAudio();
    } else {
      setAudioSignedUrl(null);
      prevAudioUrlRef.current = null;
      prevSelectedCallIdRef.current = null;
    }
  }, [selectedCall]);

  const handleSelectCall = (call) => {
    setSelectedCall(call);
  };

  const handleQuickRate = (rating) => {
    setQualityRating(rating);
  };

  const handlePrefillDefaults = () => {
    if (!selectedCall) return;
    const systemText = selectedCall.sanitized_transcript || selectedCall.raw_transcript || '';
    setVerifiedTranscript(systemText);
    setVerifiedAddress(selectedCall.target?.address || selectedCall.address || '');
    setVerifiedSubaddress(toTitleCase(selectedCall.target?.subaddress || ''));
    setVerifiedMapGrid(selectedCall.target?.map_grid || '');
    setVerifiedTalkgroup(selectedCall.target?.radio_channel || '');
    setVerifiedIncident(selectedCall.incident_type || '');
    const displayUnits = selectedCall.responding_units || [];
    setVerifiedUnits(displayUnits.join(', '));
  };

  const prefillField = (fieldType) => {
    if (!selectedCall) return;
    switch (fieldType) {
      case 'transcript':
        setVerifiedTranscript(selectedCall.sanitized_transcript || selectedCall.raw_transcript || '');
        break;
      case 'units':
        const displayUnits = selectedCall.responding_units || [];
        setVerifiedUnits(displayUnits.join(', '));
        break;
      case 'incident':
        setVerifiedIncident(selectedCall.incident_type || '');
        break;
      case 'address':
        setVerifiedAddress((selectedCall.target?.address || selectedCall.address || '').replace(/\s*\(\s*Street\s+Centroid\s*\)/gi, '').replace(/\bStreet\s+Centroid\b/gi, '').trim());
        break;
      case 'subaddress':
        setVerifiedSubaddress(toTitleCase(selectedCall.target?.subaddress || ''));
        break;
      case 'talkgroup':
        setVerifiedTalkgroup(selectedCall.target?.radio_channel || '');
        break;
      case 'map_grid':
        setVerifiedMapGrid(selectedCall.target?.map_grid || '');
        break;
      default:
        break;
    }
  };

  const handleInputKeyDown = (e, fieldType) => {
    if ((e.ctrlKey && e.code === 'Space') || (e.altKey && e.key === 'Enter')) {
      e.preventDefault();
      prefillField(fieldType);
    }
  };

  const handleToneToggle = (tone) => {
    setVerifiedTones(prev =>
      prev.includes(tone)
        ? prev.filter(t => t !== tone)
        : [...prev, tone]
    );
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
      const toneNamesMapping = {
        chief: 'Chief Tone',
        engine: 'Engine Tone',
        rescue: 'Rescue Tone'
      };
      const mappedTones = verifiedTones.map(t => toneNamesMapping[t] || t);
      const tonesString = mappedTones.join(', ');

      const updatedTarget = {
        ...(selectedCall.target || {}),
        tone_name: tonesString || null,
        include_in_training: includeInTraining,
        subaddress: verifiedSubaddress || null,
        verified_talkgroup: verifiedTalkgroup || null,
        verified_map_grid: verifiedMapGrid || null,
        review_notes: reviewNotes || null
      };

      const updatedCall = await apiClient.dispatches.update(selectedCall.dispatch_id || selectedCall.id, {
        verified_transcript: verifiedTranscript,
        verified_address: verifiedAddress,
        verified_incident: verifiedIncident,
        verified_units: unitsArray,
        feedback_submitted: true,
        verify_location: false,
        quality_rating: qualityRating,
        model_updated: selectedCall.feedback_submitted ? selectedCall.model_updated : false,
        target: updatedTarget
      });

      setSuccessMsg('Review and corrections submitted successfully!');
      setCalls(prev => prev.map(c => c.id === selectedCall.id || c.dispatch_id === selectedCall.dispatch_id ? updatedCall : c));
      setSelectedCall(updatedCall);
    } catch (err) {
      console.error('Error updating call:', err);
      alert('Failed to submit corrections.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteCall = async (id, dispatchId) => {
    if (!window.confirm(`Are you sure you want to permanently delete dispatch ${dispatchId}?`)) {
      return;
    }
    try {
      await apiClient.dispatches.delete(dispatchId || id);
      setCalls((prev) => prev.filter((c) => c.id !== id && c.dispatch_id !== dispatchId));
      if (selectedCall?.id === id || selectedCall?.dispatch_id === dispatchId) {
        setSelectedCall(null);
      }
    } catch (err) {
      console.error('Error deleting dispatch:', err);
      alert('Failed to delete dispatch.');
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
    if (e && e.preventDefault) e.preventDefault();
    setLoginLoading(true);
    setLoginError(null);
    try {
      const { data, error } = await apiClient.auth.signInWithPassword({
        username: username.trim(),
        password: password
      });
      if (error) throw error;
      setSession(data.session);
    } catch (err) {
      console.error('Login error:', err);
      const errMsg = typeof err === 'string' ? err : (err?.message || (typeof err === 'object' ? JSON.stringify(err) : String(err)));
      setLoginError(errMsg);
    } finally {
      setLoginLoading(false);
    }
  };

  if (!session) {
    return (
      <div className="absolute inset-0 bg-slate-950/95 backdrop-blur-md z-[2000] flex items-center justify-center p-6 text-slate-100 font-sans animate-in fade-in duration-200">
        <div className="w-full max-w-md bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-2xl flex flex-col gap-4 text-left border-sky-500/20">
          <div className="flex justify-between items-center border-b border-slate-800 pb-3">
            <h3 className="text-sm font-black text-sky-400 uppercase tracking-wider flex items-center gap-1.5">
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
            Please enter your administrator username and password to access live dispatch data.
          </p>

          {loginError && (
            <div className="bg-rose-500/15 text-rose-400 border border-rose-500/20 rounded-xl p-3 text-xs font-mono font-bold animate-in shake duration-150">
              Error: {loginError}
            </div>
          )}

          <form onSubmit={handleLogin} className="flex flex-col gap-4 mt-2">
            <div className="flex flex-col gap-1.5">
              <label className="text-[9px] text-slate-400 font-extrabold uppercase font-mono tracking-wider">
                Username
              </label>
              <input
                type="text"
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                disabled={loginLoading}
                className="w-full bg-slate-950 border border-slate-800 hover:border-slate-700 focus:border-sky-500 text-xs text-white rounded-xl px-3 py-2.5 focus:outline-none placeholder-slate-600 font-mono"
                placeholder="cfradmin"
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-[9px] text-slate-400 font-extrabold uppercase font-mono tracking-wider">
                Password
              </label>
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={loginLoading}
                className="w-full bg-slate-950 border border-slate-800 hover:border-slate-700 focus:border-sky-500 text-xs text-white rounded-xl px-3 py-2.5 focus:outline-none placeholder-slate-600 font-mono"
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

  // Render an SVG trend chart for WER and CER
  const renderPerformanceChart = () => {
    if (evalHistory.length === 0) return null;
    
    // Select last 12 entries for cleaner rendering
    const history = evalHistory.slice(-12);
    const height = 65;
    const width = 300;
    const padding = 10;
    
    // Find min and max values for scaling (typically 0% to 50%)
    const maxVal = Math.max(...history.map(h => Math.max(h.wer || 0, 30)), 35);
    
    const scaleX = (index) => padding + (index * (width - 2 * padding) / (history.length - 1 || 1));
    const scaleY = (val) => height - padding - (val * (height - 2 * padding) / maxVal);
    
    // Build path strings
    const newWerPoints = history.map((h, i) => `${scaleX(i)},${scaleY(h.wer)}`).join(' ');
    
    const currentWer = history[history.length - 1]?.wer;
    
    return (
      <div className="bg-slate-950/60 border border-slate-850/60 rounded-xl p-3 mb-4 flex flex-col sm:flex-row gap-4 items-center justify-between shadow-inner">
        <div className="text-left">
          <div className="text-[10px] font-mono font-extrabold uppercase tracking-wider text-slate-400">STT Performance History</div>
          <div className="text-[9px] text-slate-500 mt-0.5 max-w-[17rem] leading-relaxed">
            WER tracking on regression test cases. Local Whisper (green) vs Baseline Cloud (red).
          </div>
          <div className="flex gap-3 mt-1.5 font-mono text-[9px]">
            <span className="flex items-center gap-1.5 text-rose-400 font-bold" title="Cloud STT Baseline">
              <span className="w-1.5 h-1.5 rounded-full bg-rose-500"></span> Old WER: 29%
            </span>
            <span className="flex items-center gap-1.5 text-emerald-400 font-bold">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span> New WER: {Math.round(currentWer)}%
            </span>
          </div>
        </div>
        <div className="relative w-[280px] h-[65px] select-none pointer-events-none">
          <svg className="w-full h-full overflow-visible" viewBox={`0 0 ${width} ${height}`}>
            {/* Grid Lines */}
            <line x1={padding} y1={scaleY(0)} x2={width - padding} y2={scaleY(0)} stroke="#1e293b" strokeWidth={1} />
            <line x1={padding} y1={scaleY(maxVal/2)} x2={width - padding} y2={scaleY(maxVal/2)} stroke="#1e293b" strokeWidth={0.5} strokeDasharray="3 3" />
            
            {/* Baseline Cloud STT (Dashed Red Line) */}
            <line 
              x1={padding} 
              y1={scaleY(29.4)} 
              x2={width - padding} 
              y2={scaleY(29.4)} 
              stroke="#f43f5e" 
              strokeWidth={1.5} 
              strokeDasharray="4 3" 
              opacity={0.6}
            />
            
            {/* New WER Line (Emerald) */}
            {history.length > 1 && (
              <polyline
                fill="none"
                stroke="#10b981"
                strokeWidth={2}
                strokeLinecap="round"
                strokeLinejoin="round"
                points={newWerPoints}
              />
            )}
            
            {/* Dots */}
            {history.map((h, i) => (
              <g key={i}>
                <circle cx={scaleX(i)} cy={scaleY(h.wer)} r={2} fill="#10b981" />
              </g>
            ))}
          </svg>
        </div>
      </div>
    );
  };

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
                <span className="h-1.5 w-1.5 rounded-full bg-sky-400 animate-ping"></span>
                Checking DB...
              </span>
            )}
            {dbStatus === 'disconnected' && (
              <span className="text-[10px] text-rose-400 bg-rose-500/10 border border-rose-500/30 px-2 py-0.5 rounded-full font-mono font-bold uppercase tracking-wider flex items-center gap-1.5 animate-in shake duration-300" title={dbError || ''}>
                <span className="h-1.5 w-1.5 rounded-full bg-rose-500"></span>
                DB Error
              </span>
            )}
            {/* Listener Status Badge */}
            {listenerStatus === 'online' && (
              <span 
                className="text-[10px] text-emerald-400 bg-emerald-500/10 border border-emerald-500/30 px-2 py-0.5 rounded-full font-mono font-bold uppercase tracking-wider flex items-center gap-1.5 animate-in fade-in duration-250 cursor-help"
                title={`RF Listener Online | Device: ${listenerDetails?.device || 'Default'} | Engine: ${listenerDetails?.stt_engine || 'Whisper'}`}
              >
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                📡 LISTENER ONLINE
              </span>
            )}
            {listenerStatus === 'checking' && (
              <span className="text-[10px] text-sky-400 bg-sky-500/10 border border-sky-500/30 px-2 py-0.5 rounded-full font-mono font-bold uppercase tracking-wider flex items-center gap-1.5">
                <span className="h-1.5 w-1.5 rounded-full bg-sky-400 animate-ping"></span>
                📡 CHECKING LISTENER...
              </span>
            )}
            {listenerStatus === 'offline' && (
              <span 
                className="text-[10px] text-rose-400 bg-rose-500/15 border border-rose-500/40 px-2 py-0.5 rounded-full font-mono font-bold uppercase tracking-wider flex items-center gap-1.5 animate-in shake duration-300 shadow-sm cursor-help"
                title={listenerDetails?.message || 'RF Listener offline or process died!'}
              >
                <span className="h-1.5 w-1.5 rounded-full bg-rose-500 animate-ping"></span>
                ⚠️ LISTENER OFFLINE
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
            onClick={async () => {
              await apiClient.auth.signOut();
              setSession(null);
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
          
          {/* Performance Accuracy Chart */}
          {renderPerformanceChart()}

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
                  Could not load dispatches from Supabase. Ensure your client environment variables are correctly set in `frontend/.env.local` and your Supabase database has matching schema.
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
                      const isSelected = selectedCall?.id === call.id;
                      const rowTones = getCallTones(call);
                      return (
                        <tr
                          key={call.id}
                          onClick={() => handleSelectCall(call)}
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
                                <span className="text-rose-455 font-extrabold" title="Map Coordinates Flagged Inaccurate">📍⚠️ </span>
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
                              {typeof onSimulateCall === 'function' && (
                                <button
                                  onClick={() => onSimulateCall(call)}
                                  className="bg-amber-600 hover:bg-amber-500 text-white font-extrabold px-3 py-1 rounded-lg text-[10px] border border-amber-500/40 transition-all flex items-center gap-1 cursor-pointer shadow"
                                  title="Simulate this registered dispatch in Kiosk Mode"
                                >
                                  🚀 SIMULATE
                                </button>
                              )}

                              <button
                                onClick={() => handleDeleteCall(call.id, call.dispatch_id)}
                                className="bg-rose-950/30 hover:bg-rose-900/20 text-rose-400 hover:text-rose-300 font-bold px-2.5 py-1 rounded text-[10px] border border-rose-900/20 transition-all cursor-pointer flex items-center justify-center"
                                title="Delete dispatch entry"
                              >
                                🗑️
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
                  <div className="flex items-center gap-1.5 mt-1">
                    <span className="text-[10px] text-slate-400 font-mono">Confidence:</span>
                    <span className={`text-[10.5px] font-mono font-bold px-1.5 py-0.5 rounded border ${
                      selectedCall.confidence_score >= 80 ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20' :
                      selectedCall.confidence_score >= 40 ? 'text-amber-400 bg-amber-500/10 border-amber-500/20' : 'text-rose-400 bg-rose-500/10 border-rose-500/20'
                    }`}>
                      {selectedCall.confidence_score !== undefined && selectedCall.confidence_score !== null ? `${Math.round(selectedCall.confidence_score)}%` : 'N/A'}
                    </span>
                  </div>
                </div>
                {typeof onSimulateCall === 'function' && (
                  <button
                    type="button"
                    onClick={() => onSimulateCall(selectedCall)}
                    className="bg-amber-600 hover:bg-amber-500 text-white font-extrabold px-3 py-1.5 rounded-lg text-[10px] transition-all flex items-center gap-1 shadow border border-amber-500/40 cursor-pointer"
                    title="Simulate this dispatch call in Kiosk Mode"
                  >
                    🚀 SIMULATE CALL
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

                {/* 3-Stage Pipeline Flow Timeline */}
                <div className="flex flex-col gap-3 mt-2">
                  <span className="text-[10px] text-slate-400 font-extrabold uppercase font-mono tracking-wider">
                    Pipeline Execution Flow
                  </span>

                  <div className="relative border-l border-slate-800 pl-4 ml-2 flex flex-col gap-4">
                    {/* Stage 1: Raw STT Output */}
                    <div className="relative">
                      {/* Timeline Dot */}
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
                      {/* Timeline Dot */}
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
                            {/* Incident Type Badge */}
                            <div className="flex flex-col gap-0.5">
                              <span className="text-[8px] text-slate-500 font-bold uppercase tracking-wider font-mono">Incident</span>
                              <span className="text-[10px] font-bold text-white bg-slate-950 border border-slate-850 px-2 py-0.5 rounded-lg">
                                {selectedCall.incident_type || 'Unknown'}
                              </span>
                            </div>

                            {/* Address Badge */}
                            <div className="flex flex-col gap-0.5">
                              <span className="text-[8px] text-slate-500 font-bold uppercase tracking-wider font-mono">Address</span>
                              <span className="text-[10px] font-bold text-white bg-slate-950 border border-slate-850 px-2 py-0.5 rounded-lg flex items-center gap-1 max-w-[15rem] truncate" title={selectedCall.target?.address || selectedCall.address}>
                                📍 {selectedCall.target?.address || selectedCall.address || 'Unknown'}
                              </span>
                            </div>

                            {/* Units Badge */}
                            <div className="flex flex-col gap-0.5">
                              <span className="text-[8px] text-slate-500 font-bold uppercase tracking-wider font-mono">Units</span>
                              <span className="text-[10px] font-mono text-white bg-slate-950 border border-slate-850 px-2 py-0.5 rounded-lg">
                                {selectedCall.responding_units?.join(', ') || 'None'}
                              </span>
                            </div>

                            {/* Coordinates Badge */}
                            <div className="flex flex-col gap-0.5">
                              <span className="text-[8px] text-slate-500 font-bold uppercase tracking-wider font-mono">Coordinates</span>
                              <span className="text-[10px] font-mono text-white bg-slate-950 border border-slate-850 px-2 py-0.5 rounded-lg">
                                {selectedCall.target?.lat && selectedCall.target?.lng 
                                  ? `${selectedCall.target.lat.toFixed(4)}, ${selectedCall.target.lng.toFixed(4)}`
                                  : 'Null'}
                              </span>
                            </div>

                            {/* Subaddress Badge */}
                            {selectedCall.target?.subaddress && (
                              <div className="flex flex-col gap-0.5">
                                <span className="text-[8px] text-slate-500 font-bold uppercase tracking-wider font-mono">Subaddress</span>
                                <span className="text-[10px] font-bold text-sky-400 bg-slate-950 border border-slate-850 px-2 py-0.5 rounded-lg">
                                  🏢 {toTitleCase(selectedCall.target.subaddress)}
                                </span>
                              </div>
                            )}

                            {/* Cross Roads Badge */}
                            {selectedCall.target?.intersection && (
                              <div className="flex flex-col gap-0.5">
                                <span className="text-[8px] text-slate-500 font-bold uppercase tracking-wider font-mono">Cross Roads</span>
                                <span className="text-[10px] font-bold text-amber-400 bg-slate-950 border border-slate-850 px-2 py-0.5 rounded-lg">
                                  🔀 {selectedCall.target.intersection}
                                </span>
                              </div>
                            )}

                            {/* Talk Group Badge */}
                            <div className="flex flex-col gap-0.5">
                              <span className="text-[8px] text-slate-500 font-bold uppercase tracking-wider font-mono">Talk Group</span>
                              <span className="text-[10px] font-mono text-white bg-slate-950 border border-slate-850 px-2 py-0.5 rounded-lg">
                                📻 {selectedCall.target?.verified_talkgroup || selectedCall.target?.radio_channel || 'None'}
                              </span>
                            </div>

                            {/* Map Grid Badge */}
                            <div className="flex flex-col gap-0.5">
                              <span className="text-[8px] text-slate-500 font-bold uppercase tracking-wider font-mono">Map Grid</span>
                              <span className="text-[10px] font-mono text-white bg-slate-950 border border-slate-850 px-2 py-0.5 rounded-lg">
                                🗺️ {selectedCall.target?.verified_map_grid || selectedCall.target?.map_grid || 'None'}
                              </span>
                            </div>

                          </div>
                        )}
                      </div>
                    </div>

                    {/* Stage 3: Standardized Template Reconstruction */}
                    <div className="relative">
                      {/* Timeline Dot */}
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

                <div className="flex flex-col gap-1.5">
                  <div className="flex justify-between items-center">
                    <label className="text-[10px] text-slate-400 font-extrabold uppercase font-mono">
                      Verified Ground-Truth Transcript
                    </label>
                    <button
                      type="button"
                      onClick={handlePrefillDefaults}
                      className="text-[9px] font-bold text-sky-400 hover:text-sky-300 bg-sky-950/40 border border-sky-900/30 px-2 py-0.5 rounded cursor-pointer transition-all hover:bg-sky-900/30"
                      title="Prefill transcript, address, incident type, and units using system-extracted data"
                    >
                      📋 Prefill Defaults
                    </button>
                  </div>
                  <textarea
                    rows={3}
                    placeholder={selectedCall.sanitized_transcript || selectedCall.raw_transcript || "Enter confirmed transcript... (Ctrl+Space to prefill)"}
                    value={verifiedTranscript}
                    onChange={(e) => setVerifiedTranscript(e.target.value)}
                    onKeyDown={(e) => handleInputKeyDown(e, 'transcript')}
                    onDoubleClick={() => prefillField('transcript')}
                    className="w-full bg-slate-950 border border-slate-800 hover:border-slate-700 focus:border-sky-500 text-xs text-white rounded-xl p-2.5 focus:outline-none font-mono resize-none leading-relaxed"
                  />
                </div>

                {/* 1. Responding Units */}
                <div className="flex flex-col gap-1.5">
                  <div className="flex justify-between items-center">
                    <label className="text-[10px] text-slate-400 font-extrabold uppercase font-mono">
                      Verified Units
                    </label>
                    <span 
                      onClick={() => prefillField('units')}
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
                    onKeyDown={(e) => handleInputKeyDown(e, 'units')}
                    onDoubleClick={() => prefillField('units')}
                    className="w-full bg-slate-950 border border-slate-800 hover:border-slate-700 focus:border-sky-500 text-xs text-white rounded-xl px-3 py-2 focus:outline-none font-mono"
                    placeholder={(selectedCall.responding_units || []).join(', ') || "e.g. E1, L1"}
                  />
                </div>

                {/* 2. Captured Dispatch Tone (HITL Verification & Backfill) */}
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

                {/* 3. Incident Type (Prefilled visual helper) */}
                <div className="flex flex-col gap-1.5">
                  <div className="flex justify-between items-center">
                    <label className="text-[10px] text-slate-400 font-extrabold uppercase font-mono">
                      Verified Incident Type
                    </label>
                    <span 
                      onClick={() => prefillField('incident')}
                      className="text-[8px] text-slate-500 hover:text-sky-400 font-bold cursor-pointer transition-colors" 
                      title="Click, double-click input, or press Ctrl+Space to import"
                    >
                      System: {selectedCall.incident_type || 'Unknown'} 📥
                    </span>
                  </div>
                  <input
                    type="text"
                    value={verifiedIncident}
                    onChange={(e) => setVerifiedIncident(e.target.value)}
                    onKeyDown={(e) => handleInputKeyDown(e, 'incident')}
                    onDoubleClick={() => prefillField('incident')}
                    className="w-full bg-slate-950 border border-slate-800 hover:border-slate-700 focus:border-sky-500 text-xs text-white rounded-xl px-3 py-2 focus:outline-none"
                    placeholder={selectedCall.incident_type || "e.g. Structure Fire"}
                  />
                </div>

                {/* 4. Location Input (Prefilled side-by-side visual reminder) */}
                <div className="flex flex-col gap-1.5">
                  <div className="flex justify-between items-center">
                    <label className="text-[10px] text-slate-400 font-extrabold uppercase font-mono">
                      Verified Address / Location
                    </label>
                    <span 
                      onClick={() => prefillField('address')}
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
                    onKeyDown={(e) => handleInputKeyDown(e, 'address')}
                    onDoubleClick={() => prefillField('address')}
                    className="w-full bg-slate-950 border border-slate-800 hover:border-slate-700 focus:border-sky-500 text-xs text-white rounded-xl px-3 py-2 focus:outline-none"
                    placeholder={selectedCall.target?.address || selectedCall.address || "e.g. 2648 Sandstone Cres"}
                  />
                </div>

                {/* 5. Subaddress Input */}
                <div className="flex flex-col gap-1.5">
                  <div className="flex justify-between items-center">
                    <label className="text-[10px] text-slate-400 font-extrabold uppercase font-mono">
                      Verified Subaddress / Unit / Business
                    </label>
                    <span 
                      onClick={() => prefillField('subaddress')}
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
                    onKeyDown={(e) => handleInputKeyDown(e, 'subaddress')}
                    onDoubleClick={() => prefillField('subaddress')}
                    className="w-full bg-slate-950 border border-slate-800 hover:border-slate-700 focus:border-sky-500 text-xs text-white rounded-xl px-3 py-2 focus:outline-none"
                    placeholder={toTitleCase(selectedCall.target?.subaddress) || "None"}
                  />
                </div>

                {/* 6. Talk Group and Map Grid (Side-by-Side) */}
                <div className="grid grid-cols-2 gap-3">
                  {/* Talk Group / Channel */}
                  <div className="flex flex-col gap-1.5">
                    <div className="flex justify-between items-center">
                      <label className="text-[10px] text-slate-400 font-extrabold uppercase font-mono truncate" title="Verified Talk Group">
                        Verified Talk Group
                      </label>
                      <span 
                        onClick={() => prefillField('talkgroup')}
                        className="text-[8px] text-slate-500 hover:text-sky-400 font-bold truncate max-w-[70px] cursor-pointer transition-colors" 
                        title="Click or press Ctrl+Space to import"
                      >
                        Sys: {selectedCall.target?.radio_channel || 'None'} 📥
                      </span>
                    </div>
                    <select
                      value={verifiedTalkgroup}
                      onChange={(e) => setVerifiedTalkgroup(e.target.value)}
                      onKeyDown={(e) => handleInputKeyDown(e, 'talkgroup')}
                      className="w-full bg-slate-950 border border-slate-800 hover:border-slate-700 focus:border-sky-500 text-xs text-white rounded-xl px-3 py-2 focus:outline-none cursor-pointer"
                    >
                      <option value="">-- No Channel --</option>
                      {TALK_GROUPS.map(tg => (
                        <option key={tg} value={tg}>{tg}</option>
                      ))}
                    </select>
                  </div>

                  {/* Map Grid */}
                  <div className="flex flex-col gap-1.5">
                    <div className="flex justify-between items-center">
                      <label className="text-[10px] text-slate-400 font-extrabold uppercase font-mono truncate" title="Verified Map Grid">
                        Verified Map Grid
                      </label>
                      <span 
                        onClick={() => prefillField('map_grid')}
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
                      onKeyDown={(e) => handleInputKeyDown(e, 'map_grid')}
                      onDoubleClick={() => prefillField('map_grid')}
                      className="w-full bg-slate-950 border border-slate-800 hover:border-slate-700 focus:border-sky-500 text-xs text-white rounded-xl px-3 py-2 focus:outline-none font-mono"
                      placeholder={selectedCall.target?.map_grid || "e.g. 92"}
                    />
                  </div>
                </div>

                {/* 1. HITL Quality Rating Selector */}
                <div className="flex flex-col gap-1.5 bg-slate-950 p-3 border border-slate-850 rounded-xl flex-shrink-0 mt-1.5">
                  <label className="text-[10px] text-slate-400 font-extrabold uppercase font-mono tracking-wider">
                    HITL Quality Rating
                  </label>
                  <div className="grid grid-cols-3 gap-2 mt-1">
                    <button
                      type="button"
                      onClick={() => handleQuickRate('PERFECT')}
                      className={`py-2 px-1 text-[10px] font-bold rounded-lg border transition-all cursor-pointer text-center ${
                        qualityRating === 'PERFECT'
                          ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/50 shadow-sm font-mono'
                          : 'bg-slate-900 text-slate-400 border-slate-800 hover:border-slate-700 font-mono'
                      }`}
                    >
                      🟢 Perfect
                    </button>
                    <button
                      type="button"
                      onClick={() => handleQuickRate('OPERATIONAL')}
                      className={`py-2 px-1 text-[10px] font-bold rounded-lg border transition-all cursor-pointer text-center ${
                        qualityRating === 'OPERATIONAL'
                          ? 'bg-amber-500/20 text-amber-400 border-amber-500/50 shadow-sm font-mono'
                          : 'bg-slate-900 text-slate-400 border-slate-800 hover:border-slate-700 font-mono'
                      }`}
                    >
                      🟡 Operational
                    </button>
                    <button
                      type="button"
                      onClick={() => handleQuickRate('FAILED')}
                      className={`py-2 px-1 text-[10px] font-bold rounded-lg border transition-all cursor-pointer text-center ${
                        qualityRating === 'FAILED'
                          ? 'bg-rose-500/20 text-rose-400 border-rose-500/50 shadow-sm font-mono'
                          : 'bg-slate-900 text-slate-400 border-slate-800 hover:border-slate-700 font-mono'
                      }`}
                    >
                      🔴 Failed
                    </button>
                  </div>
                </div>

                {/* 2. HITL Review Notes / Agent Notes */}
                <div className="flex flex-col gap-1.5 mt-1.5">
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

                {/* 3. Whisper Training Dataset Opt-In */}
                <div className="flex items-center gap-2 bg-slate-950 border border-slate-850 p-3 rounded-xl mt-1.5">
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
                    <span className="text-[8px] text-rose-455 font-bold uppercase tracking-wider ml-auto animate-pulse" title="This call is under 35 seconds and appears to be cut off, so it is automatically excluded from Whisper training by default.">
                      ⚠️ Cut-Off Default
                    </span>
                  )}
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
