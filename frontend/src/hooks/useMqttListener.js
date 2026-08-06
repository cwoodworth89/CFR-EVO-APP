import { useEffect, useRef } from 'react';
import mqtt from 'mqtt';
import { API_BASE_URL } from '../apiClient';

const getMqttBrokerUrl = () => {
  if (import.meta.env.VITE_MQTT_BROKER_URL) {
    return import.meta.env.VITE_MQTT_BROKER_URL;
  }
  // Extract hostname from API_BASE_URL or window.location
  try {
    const url = new URL(API_BASE_URL);
    const hostname = url.hostname || 'localhost';
    const isSsl = url.protocol === 'https:';
    return isSsl ? `wss://${hostname}/mqtt` : `ws://${hostname}:9001`;
  } catch (e) {
    const hostname = window.location.hostname || 'localhost';
    const isSsl = window.location.protocol === 'https:';
    return isSsl ? `wss://${hostname}/mqtt` : `ws://${hostname}:9001`;
  }
};

/**
 * Real-time MQTT Dispatch Listener Hook.
 * Listens for INSERT, UPDATE, and DELETE dispatch events broadcast by local Mosquitto broker.
 */
export function useMqttListener({ onInsert, onUpdate, onDelete, enabled = true }) {
  const clientRef = useRef(null);
  const callbacksRef = useRef({ onInsert, onUpdate, onDelete });

  // Update callbacks ref on each render without triggering reconnects
  useEffect(() => {
    callbacksRef.current = { onInsert, onUpdate, onDelete };
  });

  useEffect(() => {
    if (!enabled) return;

    const brokerUrl = getMqttBrokerUrl();
    const topic = 'cfr/dispatches';
    
    console.log(`Connecting to local Mosquitto MQTT broker at ${brokerUrl}...`);

    let client;
    try {
      client = mqtt.connect(brokerUrl, {
        clientId: `kiosk_client_${Math.random().toString(16).substring(2, 8)}`,
        keepalive: 30,
        reconnectPeriod: 3000,
        connectTimeout: 5000,
      });

      clientRef.current = client;

      client.on('connect', () => {
        console.log(`MQTT Connected successfully to ${brokerUrl}. Subscribing to '${topic}'...`);
        client.subscribe(topic, { qos: 1 }, (err) => {
          if (err) {
            console.error('MQTT Subscription error:', err);
          } else {
            console.log(`Subscribed to MQTT topic '${topic}'`);
          }
        });
      });

      client.on('message', (receivedTopic, message) => {
        if (receivedTopic !== topic) return;
        try {
          const payload = JSON.parse(message.toString());
          const eventType = payload.eventType || 'INSERT';
          const record = payload.new || payload;

          console.log(`MQTT Received Event [${eventType}]:`, record);
          const { onInsert: handleInsert, onUpdate: handleUpdate, onDelete: handleDelete } = callbacksRef.current;

          if (eventType === 'INSERT' && typeof handleInsert === 'function') {
            handleInsert(formatDispatchPayload(record));
          } else if (eventType === 'UPDATE' && typeof handleUpdate === 'function') {
            handleUpdate(formatDispatchPayload(record));
          } else if (eventType === 'DELETE' && typeof handleDelete === 'function') {
            handleDelete(formatDispatchPayload(record));
          }
        } catch (err) {
          console.error('Failed to parse MQTT message payload:', err);
        }
      });

      client.on('error', (err) => {
        console.warn('MQTT Connection error:', err);
      });
    } catch (err) {
      console.error('Error initializing MQTT client:', err);
    }

    return () => {
      if (client) {
        console.log('Disconnecting MQTT client...');
        client.end(true);
      }
    };
  }, [enabled]);

}

// Standardize raw dispatch payload structure for components
export function formatDispatchPayload(record) {
  if (!record) return null;

  const payloadObj = typeof record.target === 'object' && record.target !== null 
    ? record.target 
    : {};

  let audioUrl = record.audio_url || '';
  if (audioUrl && !audioUrl.startsWith('http')) {
    audioUrl = `${API_BASE_URL}${audioUrl.startsWith('/') ? '' : '/'}${audioUrl}`;
  }

  return {
    id: record.id,
    dispatch_id: record.dispatch_id,
    created_at: record.created_at || record.timestamp || new Date().toISOString(),
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
    audio_url: audioUrl,
    raw_transcript: record.raw_transcript || '',
    sanitized_transcript: record.sanitized_transcript || '',
    rawRecord: record,
  };
}
