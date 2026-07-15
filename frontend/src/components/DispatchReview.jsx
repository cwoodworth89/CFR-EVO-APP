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

export default function DispatchReview({ onClose }) {
  const [calls, setCalls] = useState([]);
  const [evalHistory, setEvalHistory] = useState([]);
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
  const [qualityRating, setQualityRating] = useState('PENDING');
  const [editorTones, setEditorTones] = useState([]);
  const [submitting, setSubmitting] = useState(false);
  const [successMsg, setSuccessMsg] = useState('');
  const [showUploader, setShowUploader] = useState(false);
  const [stage1Open, setStage1Open] = useState(false);
  const [stage2Open, setStage2Open] = useState(false);
  const [stage3Open, setStage3Open] = useState(true);

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
      
      const { data: evalData, error: evalError } = await supabase
        .from('evaluation_history')
        .select('*')
        .order('timestamp', { ascending: true });
      
      if (!evalError) {
        setEvalHistory(evalData || []);
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
  const prevSelectedCallIdRef = React.useRef(null);

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

  // Update form fields & fetch secure signed audio URL when selectedCall changes
  useEffect(() => {
    if (selectedCall) {
      const isDifferentCall = prevSelectedCallIdRef.current !== selectedCall.id;
      prevSelectedCallIdRef.current = selectedCall.id;
      
      if (isDifferentCall) {
        setVerifiedTranscript(selectedCall.verified_transcript || '');
        setVerifiedAddress(selectedCall.verified_address || '');
        setVerifiedIncident(selectedCall.verified_incident || '');
        setQualityRating(selectedCall.quality_rating || 'PENDING');
        
        const initialTones = (selectedCall.target?.tone_name || '')
          .split(',')
          .map(t => t.trim().toLowerCase())
          .filter(Boolean);
        
        // Auto-derive tones from verified units (or responding units)
        const units = selectedCall.verified_units && selectedCall.verified_units.length > 0
          ? selectedCall.verified_units
          : (selectedCall.responding_units || []);
        const derivedTones = deriveTonesFromUnitsList(units);
        const finalTones = Array.from(new Set([...initialTones, ...derivedTones]));
        
        setEditorTones(finalTones);
        
        const displayUnits = selectedCall.verified_units || [];
        setVerifiedUnits(displayUnits.join(', '));
        
        // If we derived new tones that weren't in the database, save them back immediately!
        const tonesChanged = finalTones.length !== initialTones.length || !finalTones.every(t => initialTones.includes(t));
        if (tonesChanged) {
          const toneNamesMapping = {
            chief: 'Chief Tone',
            engine: 'Engine Tone',
            rescue: 'Rescue Tone'
          };
          const mappedTones = finalTones.map(t => toneNamesMapping[t] || t);
          const tonesString = mappedTones.join(', ');
          const updatedTarget = {
            ...(selectedCall.target || {}),
            tone_name: tonesString || null
          };
          
          supabase
            .from('live_calls')
            .update({ target: updatedTarget })
            .eq('id', selectedCall.id)
            .then(({ error }) => {
              if (!error) {
                setCalls(prev => prev.map(c => c.id === selectedCall.id ? { ...c, target: updatedTarget } : c));
              }
            });
        }
        
        setSuccessMsg('');
      } else {
        // Same call update (e.g. from realtime). Only update editorTones if they changed in the database.
        const dbTones = (selectedCall.target?.tone_name || '')
          .split(',')
          .map(t => t.trim().toLowerCase())
          .filter(Boolean);
        const tonesChanged = dbTones.length !== editorTones.length || !dbTones.every(t => editorTones.includes(t));
        if (tonesChanged) {
          setEditorTones(dbTones);
        }
      }
      
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
      prevSelectedCallIdRef.current = null;
    }
  }, [selectedCall]);

  const handleSelectCall = (call) => {
    setSelectedCall(call);
  };

  // handleViewOnMap removed

  const handleQuickRate = (rating) => {
    setQualityRating(rating);
    if (!selectedCall) return;
    if (rating === 'PERFECT' || rating === 'OPERATIONAL') {
      setVerifiedTranscript(prev => prev || selectedCall.raw_transcript || '');
      setVerifiedAddress(prev => prev || selectedCall.target?.address || selectedCall.address || '');
      setVerifiedIncident(prev => prev || selectedCall.incident_type || '');
      const newUnitsStr = (selectedCall.responding_units || []).join(', ');
      setVerifiedUnits(prev => {
        const val = prev || newUnitsStr;
        if (val) {
          setTimeout(() => {
            const typedUnits = val.split(',').map(u => u.trim()).filter(Boolean);
            const derived = deriveTonesFromUnitsList(typedUnits);
            if (derived.length > 0) {
              setEditorTones(prevTones => {
                const uniqueNewTones = Array.from(new Set([...prevTones, ...derived]));
                const tonesChanged = uniqueNewTones.length !== prevTones.length || !uniqueNewTones.every(t => prevTones.includes(t));
                if (tonesChanged && selectedCall) {
                  const toneNamesMapping = {
                    chief: 'Chief Tone',
                    engine: 'Engine Tone',
                    rescue: 'Rescue Tone'
                  };
                  const mappedTones = uniqueNewTones.map(t => toneNamesMapping[t] || t);
                  const tonesString = mappedTones.join(', ');
                  const updatedTarget = {
                    ...(selectedCall.target || {}),
                    tone_name: tonesString || null
                  };
                  supabase
                    .from('live_calls')
                    .update({ target: updatedTarget })
                    .eq('id', selectedCall.id)
                    .then(({ error }) => {
                      if (!error) {
                        setCalls(prevCalls => prevCalls.map(c => c.id === selectedCall.id ? { ...c, target: updatedTarget } : c));
                        setSelectedCall(prevCall => prevCall && prevCall.id === selectedCall.id ? { ...prevCall, target: updatedTarget } : prevCall);
                      }
                    });
                }
                return uniqueNewTones;
              });
            }
          }, 0);
        }
        return val;
      });
    }
  };

  const handleToneToggle = async (tone) => {
    if (!selectedCall) return;
    
    const updatedTones = editorTones.includes(tone)
      ? editorTones.filter(t => t !== tone)
      : [...editorTones, tone];
      
    setEditorTones(updatedTones);
    
    const toneNamesMapping = {
      chief: 'Chief Tone',
      engine: 'Engine Tone',
      rescue: 'Rescue Tone'
    };
    const mappedTones = updatedTones.map(t => toneNamesMapping[t] || t);
    const tonesString = mappedTones.join(', ');
    
    const updatedTarget = {
      ...(selectedCall.target || {}),
      tone_name: tonesString || null
    };
    
    try {
      const { error } = await supabase
        .from('live_calls')
        .update({ target: updatedTarget })
        .eq('id', selectedCall.id);
        
      if (error) throw error;
      setCalls(prevCalls => prevCalls.map(c => c.id === selectedCall.id ? { ...c, target: updatedTarget } : c));
      setSelectedCall(prevCall => prevCall && prevCall.id === selectedCall.id ? { ...prevCall, target: updatedTarget } : prevCall);
    } catch (err) {
      console.error('Error updating tone:', err);
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
      const toneNamesMapping = {
        chief: 'Chief Tone',
        engine: 'Engine Tone',
        rescue: 'Rescue Tone'
      };
      const mappedTones = editorTones.map(t => toneNamesMapping[t] || t);
      const tonesString = mappedTones.join(', ');

      const updatedTarget = {
        ...(selectedCall.target || {}),
        tone_name: tonesString || null
      };

      const { error } = await supabase
        .from('live_calls')
        .update({
          verified_transcript: verifiedTranscript,
          verified_address: verifiedAddress,
          verified_incident: verifiedIncident,
          verified_units: unitsArray,
          feedback_submitted: true,
          verify_location: false,
          quality_rating: qualityRating,
          model_updated: selectedCall.feedback_submitted ? selectedCall.model_updated : false,
          target: updatedTarget
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

  const handleDeleteCall = async (id, dispatchId) => {
    if (!window.confirm(`Are you sure you want to permanently delete dispatch ${dispatchId}?`)) {
      return;
    }
    try {
      const { error } = await supabase
        .from('live_calls')
        .delete()
        .eq('id', id);

      if (error) throw error;
      setCalls((prev) => prev.filter((c) => c.id !== id));
      if (selectedCall?.id === id) {
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
    if (!isOpen) return null;
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
            This dashboard displays sensitive live dispatch data. Please enter your administrator credentials to access.
          </p>

          {loginError && (
            <div className="bg-rose-500/15 text-rose-400 border border-rose-500/20 rounded-xl p-3 text-xs font-mono font-bold animate-in shake duration-150">
              Error: {loginError}
            </div>
          )}

          <form onSubmit={handleLogin} className="flex flex-col gap-4 mt-2">
            <div className="flex flex-col gap-1.5">
              <label className="text-[9px] text-slate-400 font-extrabold uppercase font-mono tracking-wider">
                Admin Email Address
              </label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={loginLoading}
                className="w-full bg-slate-950 border border-slate-800 hover:border-slate-700 focus:border-sky-500 text-xs text-white rounded-xl px-3 py-2.5 focus:outline-none placeholder-slate-500"
                placeholder="admin@cfr-dispatch.com"
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-[9px] text-slate-400 font-extrabold uppercase font-mono tracking-wider">
                Security Password
              </label>
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={loginLoading}
                className="w-full bg-slate-950 border border-slate-800 hover:border-slate-700 focus:border-sky-500 text-xs text-white rounded-xl px-3 py-2.5 focus:outline-none placeholder-slate-500"
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
          </h1>
          <p className="text-xs text-slate-400 mt-1 font-mono">
            Provide ground-truth feedback, edit location anomalies, check audio quality, and review STT performance.
          </p>
        </div>
        <div className="flex gap-3 items-center">
          <button
            type="button"
            onClick={() => setShowUploader(true)}
            className="bg-amber-500 hover:bg-amber-400 text-black px-4 py-2 rounded-lg text-xs font-black transition-all cursor-pointer shadow-md flex items-center gap-1 border border-amber-600"
          >
            📤 UPLOAD DISPATCH
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
                      <th className="py-2.5 px-3 w-[11%] text-center bg-slate-900">STT Synced</th>
                      <th className="py-2.5 px-3 w-[28%] bg-slate-900">System Prefills</th>
                      <th className="py-2.5 px-3 text-right w-[11%] bg-slate-900">Actions</th>
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
                                  call.target?.tone_name?.toLowerCase().includes('chief')
                                    ? 'bg-sky-500/20 border-sky-500/50 text-sky-400 shadow-[0_0_8px_rgba(14,165,233,0.3)] font-black'
                                    : 'bg-slate-900/60 border-slate-850 text-slate-600'
                                }`}
                                title={call.target?.tone_name?.toLowerCase().includes('chief') ? 'Chief Tone Captured' : 'Chief Tone Not Captured'}
                              >
                                C
                              </span>
                              <span
                                className={`w-5 h-5 rounded-full border flex items-center justify-center transition-all ${
                                  call.target?.tone_name?.toLowerCase().includes('engine')
                                    ? 'bg-amber-500/20 border-amber-500/50 text-amber-400 shadow-[0_0_8px_rgba(245,158,11,0.3)] font-black'
                                    : 'bg-slate-900/60 border-slate-850 text-slate-600'
                                }`}
                                title={call.target?.tone_name?.toLowerCase().includes('engine') ? 'Engine Tone Captured' : 'Engine Tone Not Captured'}
                              >
                                E
                              </span>
                              <span
                                className={`w-5 h-5 rounded-full border flex items-center justify-center transition-all ${
                                  call.target?.tone_name?.toLowerCase().includes('rescue')
                                    ? 'bg-rose-500/20 border-rose-500/50 text-rose-400 shadow-[0_0_8px_rgba(244,63,94,0.3)] font-black'
                                    : 'bg-slate-900/60 border-slate-850 text-slate-600'
                                }`}
                                title={call.target?.tone_name?.toLowerCase().includes('rescue') ? 'Rescue Tone Captured' : 'Rescue Tone Not Captured'}
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
                                🟢 YES
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
                              {/* Map button removed */}
                              <button
                                onClick={() => handleSelectCall(call)}
                                className="bg-slate-800 hover:bg-slate-700 text-slate-300 font-bold px-2 py-1 rounded text-[10px] border border-slate-700 transition-all cursor-pointer"
                              >
                                EDIT
                              </button>
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
                {/* View on Map button removed */}
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
                            "{selectedCall.raw_transcript || 'No transcript text captured'}"
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
                            "{selectedCall.sanitized_transcript || selectedCall.raw_transcript || 'No text'}"
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                </div>

                {/* HITL Quality Rating Selector */}
                <div className="flex flex-col gap-1.5 bg-slate-950 p-3 border border-slate-850 rounded-xl flex-shrink-0">
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
                
                {/* Map Location Pin Accuracy field removed */}

                {/* Captured Dispatch Tone (HITL Verification & Backfill) */}
                <div className="flex flex-col gap-1.5">
                  <label className="text-[10px] text-slate-400 font-extrabold uppercase font-mono">
                    Captured Dispatch Tone
                  </label>
                  <div className="grid grid-cols-3 gap-2">
                    <button
                      type="button"
                      onClick={() => handleToneToggle('chief')}
                      className={`py-2 rounded-xl text-[10px] font-extrabold uppercase font-mono border transition-all cursor-pointer flex items-center justify-center ${
                        editorTones.includes('chief')
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
                        editorTones.includes('engine')
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
                        editorTones.includes('rescue')
                          ? 'bg-rose-500/20 border-rose-500/50 text-rose-455 shadow-[0_0_8px_rgba(244,63,94,0.2)] font-black'
                          : 'bg-slate-950 border-slate-800 text-slate-500 hover:border-slate-700'
                      }`}
                    >
                      🔴 Rescue
                    </button>
                  </div>
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
                    onChange={(e) => {
                      const val = e.target.value;
                      setVerifiedUnits(val);
                      
                      const typedUnits = val.split(',').map(u => u.trim()).filter(Boolean);
                      const derived = deriveTonesFromUnitsList(typedUnits);
                      
                      if (derived.length > 0) {
                        const uniqueNewTones = Array.from(new Set([...editorTones, ...derived]));
                        const tonesChanged = uniqueNewTones.length !== editorTones.length || !uniqueNewTones.every(t => editorTones.includes(t));
                        
                        if (tonesChanged) {
                          setEditorTones(uniqueNewTones);
                          
                          if (selectedCall) {
                            const toneNamesMapping = {
                              chief: 'Chief Tone',
                              engine: 'Engine Tone',
                              rescue: 'Rescue Tone'
                            };
                            const mappedTones = uniqueNewTones.map(t => toneNamesMapping[t] || t);
                            const tonesString = mappedTones.join(', ');
                            const updatedTarget = {
                              ...(selectedCall.target || {}),
                              tone_name: tonesString || null
                            };
                            supabase
                              .from('live_calls')
                              .update({ target: updatedTarget })
                              .eq('id', selectedCall.id)
                              .then(({ error }) => {
                                if (!error) {
                                  setCalls(prevCalls => prevCalls.map(c => c.id === selectedCall.id ? { ...c, target: updatedTarget } : c));
                                }
                              });
                          }
                        }
                      }
                    }}
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
      {showUploader && (
        <DispatchAudioUploader 
          onClose={() => setShowUploader(false)}
          onTriggered={(uploadedCall) => {
            setShowUploader(false);
            handleSelectCall(uploadedCall);
          }}
        />
      )}
    </div>
  );
}

function DispatchAudioUploader({ onClose, onTriggered }) {
  const [audioFile, setAudioFile] = useState(null);
  const [verifiedTranscript, setVerifiedTranscript] = useState('');
  const [uploading, setUploading] = useState(false);
  const [statusMsg, setStatusMsg] = useState('');
  const [errorMsg, setErrorMsg] = useState('');
  const [uploadResult, setUploadResult] = useState(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  const pollIntervalRef = React.useRef(null);
  const channelRef = React.useRef(null);

  useEffect(() => {
    let interval = null;
    if (uploading) {
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
  }, [uploading]);

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
    setUploading(false);
    setStatusMsg("");
    setErrorMsg("Upload cancelled by user.");
  };

  const handleClose = () => {
    handleCancel();
    onClose();
  };

  const handleTrigger = async (e) => {
    e.preventDefault();
    if (!audioFile) {
      alert("Please select a .wav or .mp3 audio file to upload.");
      return;
    }

    // Clear previous refs if any exist
    if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    if (channelRef.current) supabase.removeChannel(channelRef.current);

    setUploading(true);
    setErrorMsg('');
    setUploadResult(null);
    setStatusMsg("Uploading audio recording to Supabase storage...");

    try {
      // 1. Upload audio to 'dispatch-audio' bucket
      const fileExt = audioFile.name.split('.').pop();
      const fileName = `upload-${Date.now()}.${fileExt}`;
      
      const { data: uploadData, error: uploadError } = await supabase.storage
        .from('dispatch-audio')
        .upload(fileName, audioFile);
        
      if (uploadError) throw uploadError;

      // Get public URL of the uploaded file
      const { data: publicUrlData } = supabase.storage
        .from('dispatch-audio')
        .getPublicUrl(fileName);
        
      const audioUrl = publicUrlData.publicUrl;

      // 2. Insert request into 'dispatch_uploads'
      setStatusMsg("Queueing dispatch for offline processing...");
      const { data: insertData, error: insertError } = await supabase
        .from('dispatch_uploads')
        .insert([{
          audio_url: audioUrl,
          verified_transcript: verifiedTranscript.trim() || null,
          status: 'pending'
        }])
        .select();

      if (insertError) throw insertError;
      if (!insertData || insertData.length === 0) {
        throw new Error("Failed to create upload entry in database.");
      }

      const requestId = insertData[0].id;
      setStatusMsg("Waiting for dispatch processor to start...");

      // 3. Subscribe to real-time updates for this specific request
      const channel = supabase
        .channel(`upload-${requestId}`)
        .on(
          'postgres_changes',
          {
            event: 'UPDATE',
            schema: 'public',
            table: 'dispatch_uploads',
            filter: `id=eq.${requestId}`
          },
          (payload) => {
            const updated = payload.new;
            if (updated.status === 'processing') {
              setStatusMsg("Transcribing & geocoding in progress...");
            } else if (updated.status === 'completed') {
              setUploadResult(updated.result);
              setUploading(false);
              setStatusMsg("");
              if (pollIntervalRef.current) {
                clearInterval(pollIntervalRef.current);
                pollIntervalRef.current = null;
              }
              supabase.removeChannel(channel);
              channelRef.current = null;
            } else if (updated.status === 'failed') {
              setErrorMsg(updated.error_message || "Processing failed in the backend pipeline.");
              setUploading(false);
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
            .from('dispatch_uploads')
            .select('*')
            .eq('id', requestId)
            .single();

          if (!pollError && pollData) {
            if (pollData.status === 'completed') {
              clearInterval(pollInterval);
              pollIntervalRef.current = null;
              setUploadResult(pollData.result);
              setUploading(false);
              setStatusMsg("");
              if (channelRef.current) {
                supabase.removeChannel(channelRef.current);
                channelRef.current = null;
              }
            } else if (pollData.status === 'failed') {
              clearInterval(pollInterval);
              pollIntervalRef.current = null;
              setErrorMsg(pollData.error_message || "Processing failed in the backend pipeline.");
              setUploading(false);
              setStatusMsg("");
              if (channelRef.current) {
                supabase.removeChannel(channelRef.current);
                channelRef.current = null;
              }
            } else if (pollData.status === 'processing') {
              setStatusMsg("Transcribing & geocoding in progress...");
            }
          }
        } catch (err) {
          console.warn("Polling error:", err);
        }
      }, 3000);
      pollIntervalRef.current = pollInterval;

    } catch (err) {
      console.error("Upload request failed:", err);
      setErrorMsg(err.message || "Failed to initiate upload processing.");
      setUploading(false);
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
          <h3 className="text-sm font-black text-sky-450 uppercase tracking-wider flex items-center gap-1.5">
            📤 UPLOAD DISPATCH AUDIO FOR PROCESSING
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
          {!uploadResult ? (
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
                    disabled={uploading}
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
                  disabled={uploading}
                  placeholder="Paste the expected ground truth text here. The pipeline will compare the Speech-to-Text output against this to verify accuracy..."
                  className="w-full bg-slate-950 border border-slate-800 text-xs text-white rounded-xl p-2.5 focus:outline-none focus:border-sky-500 font-mono resize-none leading-relaxed"
                />
              </div>

              {/* Status & Submit */}
              <div className="border-t border-slate-850 pt-4 mt-2 flex flex-col gap-3">
                {statusMsg && (
                  <div className="flex flex-col items-center justify-center py-4 text-sky-450 gap-2 w-full">
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
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-sky-400 opacity-75"></span>
                      <span className="relative inline-flex rounded-full h-3 w-3 bg-sky-500"></span>
                    </span>
                    <span className="text-[10px] font-bold font-mono tracking-widest uppercase mt-1 animate-pulse">
                      ⚙️ {statusMsg}
                    </span>
                    
                    {/* Time Elapsed & Progress Bar */}
                    <div className="text-[9px] text-slate-500 font-mono mt-1">
                      ⏱️ ELAPSED TIME: <span className="text-sky-400 font-bold">{elapsedSeconds}s</span>
                    </div>
                    
                    <div className="w-full max-w-md bg-slate-950 border border-slate-800/80 rounded-full h-3 overflow-hidden p-0.5 relative mt-1.5 shadow-inner">
                      <div 
                        className="h-full bg-gradient-to-r from-sky-500 via-indigo-500 to-emerald-500 rounded-full transition-all duration-300 relative overflow-hidden"
                        style={{
                          width: `${Math.min(100, (elapsedSeconds / 30) * 100)}%`
                        }}
                      >
                        <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent animate-shimmer" style={{ width: '200%' }} />
                      </div>
                    </div>
                    
                    {elapsedSeconds > 15 && statusMsg.includes("Waiting") && (
                      <p className="text-[9px] text-rose-450 font-bold font-mono mt-2 animate-pulse text-center max-w-sm leading-relaxed bg-rose-500/10 border border-rose-500/20 px-3 py-1.5 rounded-lg">
                        ⚠️ PROCESSOR DELAY: Make sure the Python backend is running ('python main.py' in the agent directory) to process the uploaded call.
                      </p>
                    )}

                    <button
                      type="button"
                      onClick={handleCancel}
                      className="mt-2.5 bg-rose-500/15 hover:bg-rose-500/25 text-rose-400 hover:text-rose-350 border border-rose-500/20 hover:border-rose-500/30 font-black py-2 px-5 rounded-xl text-[10px] transition-all cursor-pointer font-mono uppercase tracking-wider"
                    >
                      ✕ Cancel & Reset Upload
                    </button>
                  </div>
                )}
                
                <button
                  type="submit"
                  disabled={uploading || !audioFile}
                  className="bg-sky-500 hover:bg-sky-400 disabled:opacity-50 text-black font-black py-3 px-6 rounded-xl w-full transition-all duration-150 flex items-center justify-center gap-1.5 cursor-pointer shadow-lg border border-sky-600 uppercase text-xs tracking-wider"
                >
                  {uploading ? (
                    <>
                      <span className="animate-spin border-2 border-black border-t-transparent h-4 w-4 rounded-full"></span>
                      PROCESSING DISPATCH AUDIO...
                    </>
                  ) : (
                    "🚀 PROCESS DISPATCH AUDIO"
                  )}
                </button>
              </div>
            </form>
          ) : (
            // Upload report
            <div className="flex flex-col gap-5 animate-in fade-in duration-200">
              
              {/* Alert Header */}
              <div className="bg-emerald-500/10 border border-emerald-500/20 rounded-xl p-3 flex justify-between items-center">
                <span className="text-xs font-bold text-emerald-400 font-mono flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse"></span>
                  DISPATCH AUDIO PROCESSED SUCCESSFULLY
                </span>
                <span className="text-[10px] text-slate-500 font-mono font-bold uppercase">
                  ID: {uploadResult.dispatch_id}
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
                      <div className="text-sky-400 font-bold mt-0.5">{uploadResult.dispatch_id}</div>
                    </div>
                    <div>
                      <div className="text-[9px] text-slate-500 uppercase font-black">Timestamp</div>
                      <div className="text-slate-300 mt-0.5">{formatTimestampPT(uploadResult.timestamp)}</div>
                    </div>
                    <div>
                      <div className="text-[9px] text-slate-500 uppercase font-black">Call Type</div>
                      <div className="text-slate-200 font-bold mt-0.5">{uploadResult.incident_type}</div>
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
                        {uploadResult.responding_units && uploadResult.responding_units.length > 0 ? (
                          uploadResult.responding_units.map((unit, idx) => (
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
                      <div className="text-slate-200 font-bold mt-0.5 truncate" title={uploadResult.target?.address || uploadResult.address}>
                        {uploadResult.target?.address || uploadResult.address || "N/A"}
                      </div>
                    </div>
                    <div>
                      <div className="text-[9px] text-slate-500 uppercase font-black">Cross Roads</div>
                      <div className="text-slate-200 font-bold mt-0.5 truncate" title={uploadResult.intersection}>
                        {uploadResult.intersection || "N/A"}
                      </div>
                    </div>
                    <div>
                      <div className="text-[9px] text-slate-500 uppercase font-black">Radio Channel</div>
                      <div className="text-sky-400 font-bold mt-0.5 font-bold">Talk Group {uploadResult.radio_channel || "N/A"}</div>
                    </div>
                    <div>
                      <div className="text-[9px] text-slate-500 uppercase font-black">Map Grid</div>
                      <div className="text-sky-400 font-bold mt-0.5 font-bold">Grid {uploadResult.map_grid || "N/A"}</div>
                    </div>
                    <div>
                      <div className="text-[9px] text-slate-500 uppercase font-black">Pipeline Confidence</div>
                      <div className="mt-1 font-bold">
                        <span className={`px-2 py-0.5 rounded text-[10px] border ${getConfidenceColor(uploadResult.confidence_score)}`}>
                          {uploadResult.confidence_score.toFixed(1)}%
                        </span>
                      </div>
                    </div>
                    <div>
                      <div className="text-[9px] text-slate-500 uppercase font-black">Dual-Round Matching</div>
                      <div className="text-slate-300 font-bold mt-0.5">
                        Recorded: {uploadResult.second_round_recorded ? "Yes" : "No"} | Matched: {uploadResult.second_round_matched ? "Yes" : "No"}
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
                        "{uploadResult.raw_transcript || "No transcript output generated."}"
                      </div>
                    </div>

                    {/* Ground-Truth Verification */}
                    {uploadResult.verified_transcript && (
                      <div className="flex flex-col gap-1.5">
                        <div className="flex justify-between items-center font-mono">
                          <span className="text-[9px] text-slate-500 uppercase font-black">Ground-Truth Verification Transcript</span>
                          <span className="text-[10px] font-bold text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-1.5 py-0.5 rounded">
                            Accuracy Match: {uploadResult.transcript_accuracy}%
                          </span>
                        </div>
                        <div className="bg-slate-950 border border-slate-850 p-3 rounded-xl text-xs font-mono text-slate-355 italic max-h-32 overflow-y-auto leading-relaxed select-text">
                          "{uploadResult.verified_transcript}"
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
                  onClick={() => onTriggered(uploadResult)}
                  className="bg-sky-500 hover:bg-sky-400 text-black font-black py-3 px-6 rounded-xl flex-grow transition-all duration-150 flex items-center justify-center gap-1.5 cursor-pointer shadow-lg border border-sky-600 uppercase text-xs tracking-wider"
                >
                  🗺️ WAKE UP KIOSK HUD OVERRIDE
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setUploadResult(null);
                    setAudioFile(null);
                    setVerifiedTranscript('');
                    setErrorMsg('');
                  }}
                  className="bg-slate-850 hover:bg-slate-800 border border-slate-750 text-slate-200 font-bold py-3 px-6 rounded-xl transition-all duration-150 flex items-center justify-center gap-1.5 cursor-pointer text-xs"
                >
                  🔄 UPLOAD ANOTHER RECORDING
                </button>
              </div>

            </div>
          )}
        </div>

      </div>
    </div>
  );
}
