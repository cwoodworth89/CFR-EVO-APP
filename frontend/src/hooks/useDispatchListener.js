import { useEffect } from 'react';
import { supabase } from '../supabaseClient';

/**
 * DB-Agnostic Dispatch Listener Hook.
 * Listens for INSERT and UPDATE database events on live_calls.
 * 
 * @param {Object} options
 * @param {Function} options.onInsert - Callback when a new call row is inserted
 * @param {Function} options.onUpdate - Callback when an existing call row is updated
 * @param {boolean} options.enabled - Whether real-time listening is active
 */
export function useDispatchListener({ onInsert, onUpdate, enabled = true }) {
  useEffect(() => {
    if (!enabled || !supabase || typeof supabase.channel !== 'function') return;

    let channel = null;

    // Standardize raw payload from Supabase to unified dispatch object structure
    const formatDispatchPayload = (record) => {
      if (!record) return null;
      
      const payloadObj = typeof record.target === 'object' && record.target !== null 
        ? record.target 
        : {};

      return {
        id: record.id,
        created_at: record.created_at || new Date().toISOString(),
        address: record.address || payloadObj.address || 'Unknown Location',
        subaddress: payloadObj.subaddress || record.subaddress || '',
        intersection: payloadObj.intersection || record.intersection || '',
        lat: record.lat ?? payloadObj.lat ?? null,
        lng: record.lng ?? payloadObj.lng ?? null,
        rings: record.rings || payloadObj.rings || [],
        incident_type: record.incident_type || payloadObj.call_type || 'EMERGENCY DISPATCH',
        priority_code: record.priority_code ?? record.response_type ?? 1,
        verify_location: record.verify_location ?? false,
        map_grid: record.map_grid || payloadObj.map_grid || '',
        radio_channel: record.radio_channel || payloadObj.radio_channel || '',
        tone_name: payloadObj.tone_name || record.tone_name || '',
        audio_url: record.audio_url || '',
        raw_transcript: record.raw_transcript || '',
        sanitized_transcript: record.sanitized_transcript || '',
        rawRecord: record,
      };
    };

    try {
      channel = supabase
        .channel('kiosk_live_calls_realtime')
        .on(
          'postgres_changes',
          { event: 'INSERT', schema: 'public', table: 'live_calls' },
          (payload) => {
            const dispatch = formatDispatchPayload(payload.new);
            if (dispatch && onInsert) {
              onInsert(dispatch);
            }
          }
        )
        .on(
          'postgres_changes',
          { event: 'UPDATE', schema: 'public', table: 'live_calls' },
          (payload) => {
            const dispatch = formatDispatchPayload(payload.new);
            if (dispatch && onUpdate) {
              onUpdate(dispatch);
            }
          }
        )
        .subscribe();
    } catch (err) {
      console.warn('Real-time channel subscription error:', err);
    }

    return () => {
      if (channel && typeof supabase.removeChannel === 'function') {
        try {
          supabase.removeChannel(channel);
        } catch (e) {
          // ignore cleanup warning
        }
      }
    };
  }, [onInsert, onUpdate, enabled]);
}
