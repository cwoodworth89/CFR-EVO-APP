import { useState, useEffect, useRef, useCallback } from 'react';
import { useDispatchListener } from './useDispatchListener';
import { isSameDispatch, getVisibleChanges, toActiveCall } from '../utils/dispatchModel';
import { API_BASE_URL } from '../apiClient';

const DEFAULT_TIMEOUT_SECONDS = 300; // 5 minutes

// ---------------------------------------------------------------------------
// Rehydration after a reload -- punch list #44b follow-up.
//
// The kiosk learned about calls from MQTT and nothing else, and MQTT publishes
// WITHOUT the retain flag (mqtt_broker.py / api/mqtt.py both publish qos=1, no
// retain), so a freshly loaded page has no way to hear about a call that has
// already been announced. Any reload during an incident -- the stale-chunk
// failsafe, a browser restart, a power cycle -- left the crew looking at a
// working map with no call on it.
//
// The dispatch was never lost: public.dispatches is the system of record
// (CLAUDE.md 6.2). So on boot we ask the database what is live rather than
// waiting for a broadcast that has already been and gone.
// ---------------------------------------------------------------------------

const DISMISSED_STORAGE_KEY = 'cfr-evo:dismissed-dispatches';

// localStorage throws outright in some privacy modes; absence must degrade to
// "nothing dismissed" rather than taking the kiosk down.
function readDismissedIds() {
  try {
    const raw = window.localStorage.getItem(DISMISSED_STORAGE_KEY);
    if (!raw) return new Map();
    const cutoff = Date.now() - DEFAULT_TIMEOUT_SECONDS * 1000;
    // Entries older than the window can never suppress anything, so drop them.
    return new Map(
      Object.entries(JSON.parse(raw)).filter(([, at]) => Number(at) >= cutoff)
    );
  } catch {
    return new Map();
  }
}

function rememberDismissedId(dispatchId) {
  if (!dispatchId) return;
  try {
    const entries = readDismissedIds();
    entries.set(dispatchId, Date.now());
    window.localStorage.setItem(
      DISMISSED_STORAGE_KEY,
      JSON.stringify(Object.fromEntries(entries))
    );
  } catch { /* storage unavailable -- rehydration may re-show it once, which is
                the safe direction to fail: a call shown twice beats one lost. */ }
}

export function useKioskQueue() {
  const [activeCall, setActiveCall] = useState(null);
  const [queuedCalls, setQueuedCalls] = useState([]);
  const [isReviewMode, setIsReviewMode] = useState(false);
  const [isTvMode, setIsTvMode] = useState(false);
  const [isRecentlyUpdated, setIsRecentlyUpdated] = useState(false);
  // Which operator-visible fields changed, for the badge tooltip. Empty when idle.
  const [updatedFields, setUpdatedFields] = useState([]);
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
  // Announce an update ONLY when something the operator can see actually changed.
  //
  // Callers pass the changed field names from getVisibleChanges(); an empty list is
  // a no-op. MQTT QoS 1 is at-least-once, so a duplicate delivery of an unchanged
  // call is the contract rather than an anomaly, and the two-phase pipeline
  // re-broadcasts after correcting the address and grid. This used to fire on ANY
  // re-delivery, so the kiosk told the operator data had changed when frequently
  // nothing had. Punch-list #34.
  const triggerUpdateFlash = useCallback((changedFields) => {
    if (!changedFields || changedFields.length === 0) return;
    setUpdatedFields(changedFields);
    setIsRecentlyUpdated(true);
    if (updateFlashTimeoutRef.current) clearTimeout(updateFlashTimeoutRef.current);
    updateFlashTimeoutRef.current = setTimeout(() => {
      setIsRecentlyUpdated(false);
      setUpdatedFields([]);
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
    // If this is a real live dispatch, exit review-replay mode immediately
    if (!newCall?.isReview) {
      setIsReviewMode(false);
    }

    setActiveCall((current) => {
      // If idle or currently replaying a historical review call, a real call takes over immediately!
      if (!current || (current.isReview && !newCall?.isReview)) {
        resetTimeoutClock();
        setElapsedSeconds(0);
        return newCall;
      }

      // SAME DISPATCH, BROADCAST AGAIN -- merge, do not queue.
      //
      // The two-phase pipeline can emit more than one INSERT for one dispatch_id: phase 1
      // broadcasts a preliminary payload, and phase 2 re-broadcasts after correcting the
      // address and map grid. Without this check the kiosk queued the corrected copy as
      // though it were a second incident, so the operator saw an amber "call queued"
      // banner for a call already on screen, and tapping it appeared to do nothing --
      // it activated a near-identical copy of the same call.
      //
      // Observed 2026-08-22 on DISP-2026-282647: the screen showed map grid 61 while the
      // stored record had grid 68, so the two payloads genuinely differed. Merging keeps
      // the corrected values, which is what an operator needs, and is what an UPDATE
      // event would have done.
      if (isSameDispatch(current, newCall)) {
        // Merge regardless -- the corrected values are what the operator needs --
        // but only ANNOUNCE it if the merge actually changes something visible.
        triggerUpdateFlash(getVisibleChanges(current, newCall));
        return { ...current, ...newCall };
      }

      // A genuinely different incident: queue it and chime.
      setQueuedCalls((prev) => {
        // Guard the queue too -- a re-broadcast of something already waiting should
        // replace it rather than stack up.
        const existing = prev.findIndex((q) => isSameDispatch(q, newCall));
        if (existing !== -1) {
          const merged = [...prev];
          merged[existing] = { ...merged[existing], ...newCall };
          return merged;
        }
        playQueuedChime();
        return [...prev, newCall];
      });
      return current;
    });
  }, [playQueuedChime, resetTimeoutClock, triggerUpdateFlash]);

  // Handle incoming UPDATE dispatch event
  const handleUpdate = useCallback((updatedCall) => {
    // Identity is dispatch_id, never address. Matching on address merged distinct
    // incidents that happen to share a location -- the recorded corpus has three
    // separate overdose dispatches at 3030 Gordon Ave, so two of them active at once
    // would have overwritten each other's units, transcript and coordinates.
    setActiveCall((current) => {
      if (isSameDispatch(current, updatedCall)) {
        triggerUpdateFlash(getVisibleChanges(current, updatedCall));
        return { ...current, ...updatedCall };
      }
      return current;
    });

    setQueuedCalls((prev) =>
      prev.map((item) => (isSameDispatch(item, updatedCall)
        ? { ...item, ...updatedCall }
        : item))
    );
  }, [triggerUpdateFlash]);

  // Real-time MQTT dispatch listener
  useDispatchListener({
    onInsert: handleInsert,
    onUpdate: handleUpdate,
    enabled: true,
  });

  // Mirrors activeCall so the dismiss handlers can record which call was dismissed
  // without reading state inside a setState updater.
  const activeCallRef = useRef(null);
  useEffect(() => { activeCallRef.current = activeCall; }, [activeCall]);

  // Restore an in-progress call after a reload. Runs once, on mount.
  useEffect(() => {
    const controller = new AbortController();
    let cancelled = false;

    (async () => {
      try {
        // limit=5 rather than 1: two calls inside one five-minute window is
        // uncommon at ~11 dispatches a day but entirely real, and restoring only
        // the newest would silently drop the one the crew is actually on.
        const res = await fetch(`${API_BASE_URL}/api/dispatches?limit=5`, { signal: controller.signal });
        if (!res.ok || cancelled) return;
        const records = await res.json();
        if (cancelled || !Array.isArray(records)) return;

        const dismissed = readDismissedIds();
        const now = Date.now();

        const stillLive = records
          .map((record) => ({ record, ageSeconds: (now - Date.parse(record.timestamp)) / 1000 }))
          // Date.parse is safe here: the API emits an offset-bearing ISO string
          // ("...+00:00", verified against the running API 2026-08-31). A naive
          // timestamp would be read as local time and be hours out.
          .filter(({ record, ageSeconds }) =>
            Number.isFinite(ageSeconds) &&
            ageSeconds >= 0 &&
            ageSeconds < DEFAULT_TIMEOUT_SECONDS &&
            !dismissed.has(record.dispatch_id))
          // Oldest first, reproducing what the screen held before the reload: the
          // earlier call is the active one and later arrivals were queued behind it.
          .sort((a, b) => b.ageSeconds - a.ageSeconds);

        if (cancelled || stillLive.length === 0) return;

        const [oldest, ...rest] = stillLive;
        const restored = toActiveCall(oldest.record, { apiBaseUrl: API_BASE_URL });
        const age = Math.round(oldest.ageSeconds);

        setActiveCall((current) => {
          // MQTT may have beaten the fetch, and a live broadcast is fresher than
          // anything we just read. Never overwrite it.
          if (current) return current;

          // Seed the clocks from the dispatch's real age rather than restarting
          // them. A fresh 5:00 would silently extend the display window, and an
          // elapsed clock reset to 00:00 would misreport how long the crew has
          // been on the call -- a number that reads as real and is not
          // (CLAUDE.md 6.1).
          setElapsedSeconds(age);
          setTimeoutSecondsLeft(Math.max(1, DEFAULT_TIMEOUT_SECONDS - age));
          setIsTimerPaused(false);
          return restored;
        });

        if (rest.length > 0) {
          setQueuedCalls((prev) => (prev.length > 0
            ? prev
            : rest.map(({ record }) => toActiveCall(record, { apiBaseUrl: API_BASE_URL }))));
        }
      } catch {
        // Offline or the API is down: MQTT remains the primary path and a later
        // broadcast still populates the screen. Nothing is invented here.
      }
    })();

    return () => { cancelled = true; controller.abort(); };
  }, []);

  // Reset the elapsed counter the moment the active call clears, during render.
  // Doing it inside the effect below left the previous call's elapsed time on
  // screen for one frame after dismissal.
  const [hadActiveCall, setHadActiveCall] = useState(false);
  if (!!activeCall !== hadActiveCall) {
    setHadActiveCall(!!activeCall);
    if (!activeCall) setElapsedSeconds(0);
  }

  // Count-up elapsed timer for active call
  useEffect(() => {
    if (!activeCall) return;

    elapsedTimerRef.current = setInterval(() => {
      setElapsedSeconds((prev) => prev + 1);
    }, 1000);

    return () => {
      if (elapsedTimerRef.current) clearInterval(elapsedTimerRef.current);
    };
  }, [activeCall]);

  // Advance to next call in queue
  const advanceToNextCall = useCallback(() => {
    // Moving on is a dismissal of the call being left behind -- same reasoning.
    const leaving = activeCallRef.current;
    if (leaving && !leaving.isReview) rememberDismissedId(leaving.dispatch_id);

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
    // Record it, or the rehydration on the next reload would put a call the
    // operator has deliberately cleared straight back on the screen. Review
    // replays are excluded -- they are not live incidents.
    const dismissing = activeCallRef.current;
    if (dismissing && !dismissing.isReview) rememberDismissedId(dismissing.dispatch_id);

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

  // 5-Minute Auto-Dismiss Countdown (Disabled during historical Review replay).
  // Declared after dismissActiveCall: referencing it earlier hit the temporal dead
  // zone and threw when the countdown actually reached zero.
  useEffect(() => {
    if (!activeCall || isTimerPaused || isReviewMode || activeCall?.isReview) return;

    timeoutTimerRef.current = setInterval(() => {
      setTimeoutSecondsLeft((prev) => {
        if (prev <= 1) {
          dismissActiveCall();
          return DEFAULT_TIMEOUT_SECONDS;
        }
        return prev - 1;
      });
    }, 1000);

    return () => {
      if (timeoutTimerRef.current) clearInterval(timeoutTimerRef.current);
    };
  }, [activeCall, isTimerPaused, isReviewMode, dismissActiveCall]);

  // Historical Dispatch Review Replay (Admin Dispatch Review panel)
  const triggerReviewCall = useCallback((reviewCall) => {
    setIsReviewMode(true);
    handleInsert(reviewCall);
  }, [handleInsert]);

  const exitReview = useCallback(() => {
    setIsReviewMode(false);
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
    isReviewMode,
    isTvMode,
    isRecentlyUpdated,
    updatedFields,
    elapsedFormatted: formatTime(elapsedSeconds),
    timeoutFormatted: formatTime(timeoutSecondsLeft),
    isTimerPaused,
    resetTimeoutClock,
    advanceToNextCall,
    dismissActiveCall,
    triggerReviewCall,
    exitReview,
    toggleTvMode,
  };
}
