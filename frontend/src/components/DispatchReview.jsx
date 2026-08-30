import React, { useState, useEffect, useRef } from 'react';
import { apiClient, API_BASE_URL } from '../apiClient';
import { useDispatchListener } from '../hooks/useDispatchListener';
import SystemMetricsPanel from './admin/SystemMetricsPanel';
import ReviewTable from './review/ReviewTable';
import { getCallTones } from './review/reviewFormat';
import VerificationSidebar from './review/VerificationSidebar';
import { toTitleCase } from './review/verificationConstants';

export default function DispatchReview({ onClose, onReviewCall }) {
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
  const [activeTab, setActiveTab] = useState('review'); // 'review' | 'metrics'

  // Auth session states
  const [session, setSession] = useState(null);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loginLoading, setLoginLoading] = useState(false);
  const [loginError, setLoginError] = useState(null);

  // Filter states
  const [statusFilter, setStatusFilter] = useState('all');
  const [unitFilter, setUnitFilter] = useState('all');
  const [toneFilter, setToneFilter] = useState('all');

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
  // 'routine' | 'emergency' | null. Null is a real answer, not 'unset':
  // the reviewer confirming the dispatch never announced one is exactly the
  // ground truth RESPONSE_TYPE_UNKNOWN needs (punch-list #31, #45).
  const [verifiedResponseType, setVerifiedResponseType] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [successMsg, setSuccessMsg] = useState('');
  const [stage1Open, setStage1Open] = useState(false);
  const [stage2Open, setStage2Open] = useState(false);
  const [stage3Open, setStage3Open] = useState(false);

  const [audioSignedUrl, setAudioSignedUrl] = useState(null);
  const prevSelectedCallIdRef = useRef(null);
  const prevAudioUrlRef = useRef(null);
  const audioRef = useRef(null);
  const formContainerRef = useRef(null);

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
      } catch {
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

  // Update form fields & fetch secure signed audio URL when selectedCall changes
  useEffect(() => {
    if (selectedCall) {
      const isDifferentCall = prevSelectedCallIdRef.current !== selectedCall.id;
      prevSelectedCallIdRef.current = selectedCall.id;
      
      if (isDifferentCall) {
        setVerifiedTranscript(selectedCall.verified_transcript || selectedCall.sanitized_transcript || selectedCall.raw_transcript || '');
        setVerifiedAddress(selectedCall.verified_address || '');
        setVerifiedSubaddress(selectedCall.feedback_submitted ? toTitleCase(selectedCall.target?.subaddress || '') : '');
        setVerifiedMapGrid(selectedCall.target?.verified_map_grid || '');
        setVerifiedTalkgroup(selectedCall.target?.verified_talkgroup || selectedCall.target?.radio_channel || '');
        setVerifiedIncident(selectedCall.verified_incident || '');
        // Prefer the reviewer's own correction, then what the parser heard, then
        // null. Null is a real state here — "the dispatch did not announce one".
        setVerifiedResponseType(
          selectedCall.target?.verified_response_type
          ?? selectedCall.target?.response_type
          ?? null);
        setVerifiedResponseType(
          selectedCall.target?.verified_response_type
          ?? selectedCall.target?.response_type
          ?? null);
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
        
        const initialTones = getCallTones(selectedCall);
        setVerifiedTones(initialTones);
        
        setSuccessMsg('');
      }
      
      // Resolve audio URL directly from local FastAPI static server
      const getSignedAudio = () => {
        if (!selectedCall.audio_url) {
          setAudioSignedUrl(null);
          prevAudioUrlRef.current = null;
          return;
        }
        
        let path = selectedCall.audio_url;
        if (!path.startsWith('http')) {
          path = `${API_BASE_URL}${path.startsWith('/') ? '' : '/'}${path}`;
        }
        if (prevAudioUrlRef.current !== path) {
          prevAudioUrlRef.current = path;
          setAudioSignedUrl(path);
        }
      };
      
      getSignedAudio();
    } else {
      setAudioSignedUrl(null);
      prevAudioUrlRef.current = null;
      prevSelectedCallIdRef.current = null;
    }
  }, [selectedCall?.id, selectedCall?.audio_url]);

  const handleSelectCall = (call) => {
    setSelectedCall(call);
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

  const handlePrefillField = (fieldType) => {
    if (!selectedCall) return;
    switch (fieldType) {
      case 'transcript':
        setVerifiedTranscript(selectedCall.sanitized_transcript || selectedCall.raw_transcript || '');
        break;
      case 'units': {
        const displayUnits = selectedCall.responding_units || [];
        setVerifiedUnits(displayUnits.join(', '));
        break;
      }
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

  // Filtered calls list based on search query and status/unit/tone filters
  const filteredCalls = calls.filter((c) => {
    const query = searchQuery.toLowerCase();
    const address = (c.target?.address || c.address || '').toLowerCase();
    const incident = (c.incident_type || '').toLowerCase();
    const id = (c.dispatch_id || '').toLowerCase();
    const transcript = (c.raw_transcript || '').toLowerCase();
    const matchesQuery = !query || address.includes(query) || incident.includes(query) || id.includes(query) || transcript.includes(query);
    if (!matchesQuery) return false;

    // Status Filter
    if (statusFilter === 'needs_review' && c.feedback_submitted) return false;
    if (statusFilter === 'fine_tuned' && !c.feedback_submitted) return false;
    // 'flagged' = the system named at least one reason to look. Replaces the
    // low_confidence filter, which keyed off a score that no longer exists (#45).
    if (statusFilter === 'flagged'
        && (c.review_flags ?? c.target?.review_flags ?? []).length === 0) return false;

    // Tone Filter
    if (toneFilter !== 'all') {
      const callTones = getCallTones(c);
      // 'none' finds calls the TONE SPOTTER recorded nothing for. Added 2026-08-29
      // for punch-list #14: while clearing Chief tags off PA pages it is easy to
      // strip one from a real dispatch, and this is how you check. It also surfaces
      // recordings whose tones were genuinely lost rather than mistagged -- e.g.
      // DISP-2026-DD939E, whose audio was clipped at both ends so the tones never
      // reached the detector.
      //
      // Tests target.tone_name directly, NOT getCallTones(): that helper also
      // DERIVES tones from the responding units, so a real dispatch with units but
      // no stored tone would come back as "has tones" and never appear here --
      // hiding exactly the case this filter exists to find.
      if (toneFilter === 'none') {
        if ((c.target?.tone_name || '').trim() !== '') return false;
      } else if (!callTones.includes(toneFilter)) {
        return false;
      }
    }

    // Unit Filter
    if (unitFilter !== 'all') {
      const units = (c.verified_units && c.verified_units.length > 0) ? c.verified_units : (c.responding_units || []);
      const matchesUnit = units.some(u => u.toLowerCase().includes(unitFilter.toLowerCase()));
      if (!matchesUnit) return false;
    }

    return true;
  });

  const handleSubmitReview = async (e) => {
    if (e && e.preventDefault) e.preventDefault();
    if (!selectedCall) return;

    setSubmitting(true);
    setSuccessMsg('');

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
        verified_response_type: verifiedResponseType,
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

      // Auto-advance to next dispatch row in filtered list
      const currentIndex = filteredCalls.findIndex(c => c.id === selectedCall.id || c.dispatch_id === selectedCall.dispatch_id);
      const nextCall = (currentIndex >= 0 && currentIndex + 1 < filteredCalls.length) ? filteredCalls[currentIndex + 1] : null;

      if (nextCall) {
        setSelectedCall(nextCall);
        if (formContainerRef.current) {
          formContainerRef.current.scrollTo({ top: 0, behavior: 'smooth' });
        }
      } else {
        setSelectedCall(updatedCall);
      }
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

  // Login Modal
  if (!session) {
    return (
      <div className="absolute inset-0 bg-slate-950/95 backdrop-blur-md z-[2000] flex items-center justify-center p-6 text-slate-100 font-sans animate-in fade-in duration-200">
        <div className="w-full max-w-md bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-2xl flex flex-col gap-4 text-left border-sky-500/20">
          <div className="flex justify-between items-center border-b border-slate-800 pb-3">
            <h3 className="text-sm font-black text-sky-400 uppercase tracking-wider flex items-center gap-1.5 font-mono">
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
            Please enter your administrator credentials to access station dispatch review and telemetry data.
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
              className="mt-2 bg-sky-500 hover:bg-sky-400 text-black font-extrabold py-3 px-6 rounded-xl w-full shadow-lg transition-all duration-150 flex items-center justify-center gap-1.5 cursor-pointer disabled:opacity-50 font-mono"
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
            Provide ground-truth feedback, verify locations and tones, check audio quality, and review STT performance.
          </p>
        </div>
        <div className="flex gap-3 items-center">
          <button
            type="button"
            onClick={async () => {
              await apiClient.auth.signOut();
              setSession(null);
            }}
            className="bg-rose-950/45 border border-rose-900/40 hover:border-rose-500 hover:text-white text-rose-400 px-4 py-2 rounded-lg text-xs font-bold transition-all cursor-pointer shadow-md font-mono"
          >
            🚪 LOG OUT
          </button>
          <button
            type="button"
            onClick={onClose}
            className="bg-slate-900 border border-slate-800 hover:border-slate-700 hover:text-white text-slate-400 px-4 py-2 rounded-lg text-xs font-bold transition-all cursor-pointer shadow-md font-mono"
          >
            ✕ CLOSE DASHBOARD
          </button>
        </div>
      </div>

      {/* Sub-Navigation Tab Bar */}
      <div className="flex gap-2 mb-4 flex-shrink-0">
        <button
          type="button"
          onClick={() => setActiveTab('review')}
          className={`px-4 py-2.5 text-xs font-mono font-extrabold rounded-xl transition-all duration-150 cursor-pointer flex items-center gap-2 ${
            activeTab === 'review'
              ? 'bg-sky-500 text-black shadow-lg shadow-sky-500/20'
              : 'bg-slate-900 border border-slate-800 text-slate-400 hover:text-white hover:bg-slate-850'
          }`}
        >
          📋 CALL REVIEW PANEL ({filteredCalls.length})
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('metrics')}
          className={`px-4 py-2.5 text-xs font-mono font-extrabold rounded-xl transition-all duration-150 cursor-pointer flex items-center gap-2 ${
            activeTab === 'metrics'
              ? 'bg-sky-500 text-black shadow-lg shadow-sky-500/20'
              : 'bg-slate-900 border border-slate-800 text-slate-400 hover:text-white hover:bg-slate-850'
          }`}
        >
          📊 SYSTEM & STT METRICS
        </button>
      </div>

      {activeTab === 'metrics' ? (
        <div className="flex-grow overflow-y-auto w-full">
          <SystemMetricsPanel dispatches={calls} evaluations={evalHistory} />
        </div>
      ) : (
        /* Main Grid: Modular ReviewTable + VerificationSidebar */
        <div className="flex-grow flex gap-5 min-h-0 w-full overflow-hidden">
          <ReviewTable
            calls={calls}
            filteredCalls={filteredCalls}
            selectedCall={selectedCall}
            onSelectCall={handleSelectCall}
            searchQuery={searchQuery}
            setSearchQuery={setSearchQuery}
            statusFilter={statusFilter}
            setStatusFilter={setStatusFilter}
            toneFilter={toneFilter}
            setToneFilter={setToneFilter}
            unitFilter={unitFilter}
            setUnitFilter={setUnitFilter}
            loading={loading}
            dbStatus={dbStatus}
            dbError={dbError}
            onRetryFetch={fetchCalls}
            onReviewCall={onReviewCall}
            onDeleteCall={handleDeleteCall}
          />

          <VerificationSidebar
            selectedCall={selectedCall}
            audioSignedUrl={audioSignedUrl}
            audioRef={audioRef}
            verifiedTranscript={verifiedTranscript}
            setVerifiedTranscript={setVerifiedTranscript}
            verifiedAddress={verifiedAddress}
            setVerifiedAddress={setVerifiedAddress}
            verifiedIncident={verifiedIncident}
            setVerifiedIncident={setVerifiedIncident}
            verifiedUnits={verifiedUnits}
            setVerifiedUnits={setVerifiedUnits}
            verifiedSubaddress={verifiedSubaddress}
            setVerifiedSubaddress={setVerifiedSubaddress}
            verifiedTalkgroup={verifiedTalkgroup}
            setVerifiedTalkgroup={setVerifiedTalkgroup}
            verifiedMapGrid={verifiedMapGrid}
            setVerifiedMapGrid={setVerifiedMapGrid}
            verifiedTones={verifiedTones}
            verifiedResponseType={verifiedResponseType}
            setVerifiedResponseType={setVerifiedResponseType}
            setVerifiedTones={setVerifiedTones}
            qualityRating={qualityRating}
            setQualityRating={setQualityRating}
            reviewNotes={reviewNotes}
            setReviewNotes={setReviewNotes}
            includeInTraining={includeInTraining}
            setIncludeInTraining={setIncludeInTraining}
            stage1Open={stage1Open}
            setStage1Open={setStage1Open}
            stage2Open={stage2Open}
            setStage2Open={setStage2Open}
            stage3Open={stage3Open}
            setStage3Open={setStage3Open}
            submitting={submitting}
            successMsg={successMsg}
            onSubmitReview={handleSubmitReview}
            onPrefillDefaults={handlePrefillDefaults}
            onPrefillField={handlePrefillField}
            onReviewCall={onReviewCall}
            formContainerRef={formContainerRef}
          />
        </div>
      )}
    </div>
  );
}
