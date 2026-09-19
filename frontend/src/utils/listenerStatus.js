/**
 * The console's RF listener pill, from GET /api/listener/status.
 *
 * Since 81f308ac the api serves `listener_state`: `capturing` (alive and recording a broadcast
 * right now -- "a restart now loses the call"), `idle` (alive, waiting for tones) or
 * `unresponsive` (no heartbeat, or a stale one), plus `dispatch_id` while capturing and a
 * `message` that says what a restart would cost. Before it the api sent only `status`
 * ('online' / 'offline'); an api that predates the field still gets the old two states here.
 *
 * This is the signal the operator reads before restarting the agent by hand, so the capturing
 * state has to be visible on the page, not in a tooltip (hover-only content is ruled out on
 * the touch display, and a title is easy to miss on the console too).
 *
 * Nothing is invented for a missing value: the device and the STT engine show "--" when the
 * api does not name them (the badge used to say "Default" and "Whisper"; CLAUDE.md 6.1).
 */

export const LISTENER = Object.freeze({ CHECKING: 'checking', CAPTURING: 'capturing', ONLINE: 'online', OFFLINE: 'offline' });

const text = (v) => (typeof v === 'string' && v.trim() ? v.trim() : '--');

/**
 * `data` is the endpoint's JSON; `error` is set when the request itself failed.
 * Returns { state, dispatchId, device, engine, message }.
 */
export function listenerView(data, error = null) {
  if (error) {
    return { state: LISTENER.OFFLINE, dispatchId: null, device: '--', engine: '--', message: String(error) || 'Listener status unreachable' };
  }
  if (!data) return { state: LISTENER.CHECKING, dispatchId: null, device: '--', engine: '--', message: null };
  let state;
  switch (data.listener_state) {
    case 'capturing': state = LISTENER.CAPTURING; break;
    case 'idle': state = LISTENER.ONLINE; break;
    case 'unresponsive': state = LISTENER.OFFLINE; break;
    default: state = data.status === 'online' ? LISTENER.ONLINE : LISTENER.OFFLINE;   // an api before 81f308ac
  }
  const dispatchId = state === LISTENER.CAPTURING && typeof data.dispatch_id === 'string' && data.dispatch_id.trim()
    ? data.dispatch_id.trim() : null;
  let message = typeof data.message === 'string' && data.message.trim() ? data.message.trim() : null;
  // The capturing wording is the point of this state; if an api ever sends it without, say it.
  if (state === LISTENER.CAPTURING && !(message && /restart/i.test(message))) {
    message = 'A restart now loses the call';
  }
  return { state, dispatchId, device: text(data.device), engine: text(data.stt_engine), message };
}
