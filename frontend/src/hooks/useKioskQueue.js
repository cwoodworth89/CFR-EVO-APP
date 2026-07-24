import { useState, useEffect, useRef, useCallback } from 'react';
import { useDispatchListener } from './useDispatchListener';

const DEFAULT_TIMEOUT_SECONDS = 300; // 5 minutes

export function useKioskQueue() {
  const [activeCall, setActiveCall] = useState(null);
  const [queuedCalls, setQueuedCalls] = useState([]);
  const [isSimulationMode, setIsSimulationMode] = useState(false);
  const [isTvMode, setIsTvMode] = useState(false);
  const [isRecentlyUpdated, setIsRecentlyUpdated] = useState(false);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [timeoutSecondsLeft, setTimeoutSecondsLeft] = useState(DEFAULT_TIMEOUT_SECONDS);
  const [isTimerPaused, setIsTimerPaused] = useState(false);

  const timeoutTimerRef = useRef(null);
  const elapsedTimerRef = useRef(null);
  const updateFlashTimeoutRef = useRef(null);

  // Play subtle audio chime on new queued call
  const playQueuedChime = useCallback(() => {
    try {
      const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(587.33, audioCtx.currentTime); // D5
      osc.frequency.exponentialRampToValueAtTime(880, audioCtx.currentTime + 0.3); // A5
      gain.gain.setValueAtTime(0.15, audioCtx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.5);
      osc.connect(gain);
      gain.connect(audioCtx.destination);
      osc.start();
      osc.stop(audioCtx.currentTime + 0.5);
    } catch (e) {
      console.warn('Audio chime playback failed:', e);
    }
  }, []);

  // Trigger brief 4-second "⚡ CALL UPDATED" flash animation
  const triggerUpdateFlash = useCallback(() => {
    setIsRecentlyUpdated(true);
    if (updateFlashTimeoutRef.current) clearTimeout(updateFlashTimeoutRef.current);
    updateFlashTimeoutRef.current = setTimeout(() => {
      setIsRecentlyUpdated(false);
    }, 4000);
  }, []);

  // Reset 5-minute timeout clock on touch or call change
  const resetTimeoutClock = useCallback(() => {
    setTimeoutSecondsLeft(DEFAULT_TIMEOUT_SECONDS);
    setIsTimerPaused(false);
  }, []);

  // Set new active call
  const activateCall = useCallback((call) => {
    setActiveCall(call);
    resetTimeoutClock();
    setElapsedSeconds(0);
  }, [resetTimeoutClock]);

  // Handle incoming INSERT dispatch event
  const handleInsert = useCallback((newCall) => {
    setActiveCall((current) => {
      if (!current) {
        // IDLE -> Activate immediately
        resetTimeoutClock();
        setElapsedSeconds(0);
        return newCall;
      } else {
        // ACTIVE -> Push to queue and chime
        setQueuedCalls((prev) => [...prev, newCall]);
        playQueuedChime();
        return current;
      }
    });
  }, [playQueuedChime, resetTimeoutClock]);

  // Handle incoming UPDATE dispatch event
  const handleUpdate = useCallback((updatedCall) => {
    setActiveCall((current) => {
      if (current && (current.id === updatedCall.id || current.address === updatedCall.address)) {
        triggerUpdateFlash();
        return { ...current, ...updatedCall };
      }
      return current;
    });

    setQueuedCalls((prev) =>
      prev.map((item) =>
        item.id === updatedCall.id || item.address === updatedCall.address
          ? { ...item, ...updatedCall }
          : item
      )
    );
  }, [triggerUpdateFlash]);

  // Real-time Supabase listener
  useDispatchListener({
    onInsert: handleInsert,
    onUpdate: handleUpdate,
    enabled: true,
  });

  // Count-up elapsed timer for active call
  useEffect(() => {
    if (!activeCall) {
      setElapsedSeconds(0);
      return;
    }

    elapsedTimerRef.current = setInterval(() => {
      setElapsedSeconds((prev) => prev + 1);
    }, 1000);

    return () => {
      if (elapsedTimerRef.current) clearInterval(elapsedTimerRef.current);
    };
  }, [activeCall]);

  // 5-Minute Auto-Dismiss Countdown
  useEffect(() => {
    if (!activeCall || isTimerPaused) return;

    timeoutTimerRef.current = setInterval(() => {
      setTimeoutSecondsLeft((prev) => {
        if (prev <= 1) {
          // Timeout reached: dismiss call
          dismissActiveCall();
          return DEFAULT_TIMEOUT_SECONDS;
        }
        return prev - 1;
      });
    }, 1000);

    return () => {
      if (timeoutTimerRef.current) clearInterval(timeoutTimerRef.current);
    };
  }, [activeCall, isTimerPaused]);

  // Advance to next call in queue
  const advanceToNextCall = useCallback(() => {
    setQueuedCalls((prev) => {
      if (prev.length === 0) {
        setActiveCall(null);
        return [];
      }
      const [next, ...rest] = prev;
      activateCall(next);
      return rest;
    });
  }, [activateCall]);

  // Dismiss current active call
  const dismissActiveCall = useCallback(() => {
    setQueuedCalls((prev) => {
      if (prev.length > 0) {
        const [next, ...rest] = prev;
        activateCall(next);
        return rest;
      } else {
        setActiveCall(null);
        return [];
      }
    });
  }, [activateCall]);

  // Admin Simulation Actions
  const triggerSimulationCall = useCallback((mockCall) => {
    setIsSimulationMode(true);
    handleInsert(mockCall);
  }, [handleInsert]);

  const triggerSimulationUpdate = useCallback((updatedMockCall) => {
    handleUpdate(updatedMockCall);
  }, [handleUpdate]);

  const exitSimulation = useCallback(() => {
    setIsSimulationMode(false);
    setActiveCall(null);
    setQueuedCalls([]);
  }, []);

  const toggleTvMode = useCallback(() => {
    setIsTvMode((prev) => !prev);
  }, []);

  // Format seconds to mm:ss or hh:mm:ss
  const formatTime = (secs) => {
    const h = Math.floor(secs / 3600);
    const m = Math.floor((secs % 3600) / 60);
    const s = secs % 60;
    if (h > 0) {
      return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
    }
    return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  };

  return {
    activeCall,
    queuedCalls,
    isSimulationMode,
    isTvMode,
    isRecentlyUpdated,
    elapsedFormatted: formatTime(elapsedSeconds),
    timeoutFormatted: formatTime(timeoutSecondsLeft),
    isTimerPaused,
    resetTimeoutClock,
    advanceToNextCall,
    dismissActiveCall,
    triggerSimulationCall,
    triggerSimulationUpdate,
    exitSimulation,
    toggleTvMode,
  };
}
