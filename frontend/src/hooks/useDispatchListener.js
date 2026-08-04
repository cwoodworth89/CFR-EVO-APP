import { useMqttListener } from './useMqttListener';

/**
 * DB-Agnostic Dispatch Listener Hook.
 * Listens for INSERT, UPDATE, and DELETE database events broadcast via Mosquitto MQTT WebSockets.
 * 
 * @param {Object} options
 * @param {Function} options.onInsert - Callback when a new call is inserted
 * @param {Function} options.onUpdate - Callback when an existing call is updated
 * @param {Function} options.onDelete - Callback when a call is deleted
 * @param {boolean} options.enabled - Whether real-time listening is active
 */
export function useDispatchListener({ onInsert, onUpdate, onDelete, enabled = true }) {
  return useMqttListener({ onInsert, onUpdate, onDelete, enabled });
}
