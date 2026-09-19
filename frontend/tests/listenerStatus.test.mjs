import test from 'node:test';
import assert from 'node:assert/strict';
import { listenerView, LISTENER } from '../src/utils/listenerStatus.js';

// Shapes as backend/api/routers/audio.py get_listener_status serves them (81f308ac).
const capturing = {
  status: 'online', listener_state: 'capturing', dispatch_id: 'DISP-2026-ABC123',
  message: 'RF Listener capturing DISP-2026-ABC123 for 12s -- a restart now loses the call',
  device: 'USB Audio CODEC', stt_engine: 'faster-whisper', capture_age_seconds: 12,
};

test('capturing: the state, the dispatch id and the restart wording, all as served', () => {
  const v = listenerView(capturing);
  assert.equal(v.state, LISTENER.CAPTURING);
  assert.equal(v.dispatchId, 'DISP-2026-ABC123');
  assert.match(v.message, /a restart now loses the call/);
  assert.equal(v.device, 'USB Audio CODEC');
  assert.equal(v.engine, 'faster-whisper');
});

test('capturing without a message or id still says what a restart costs', () => {
  const v = listenerView({ status: 'online', listener_state: 'capturing' });
  assert.equal(v.state, LISTENER.CAPTURING);
  assert.equal(v.dispatchId, null);
  assert.match(v.message, /restart now loses the call/i);
});

test('idle is ONLINE; unresponsive is OFFLINE with the api message', () => {
  assert.equal(listenerView({ status: 'online', listener_state: 'idle', device: 'hw:1' }).state, LISTENER.ONLINE);
  const off = listenerView({ status: 'offline', listener_state: 'unresponsive', message: 'RF Listener unresponsive (Heartbeat 94s ago)', device: '--' });
  assert.equal(off.state, LISTENER.OFFLINE);
  assert.equal(off.message, 'RF Listener unresponsive (Heartbeat 94s ago)');
  assert.equal(off.dispatchId, null);
});

test('an api before 81f308ac: falls back to status', () => {
  assert.equal(listenerView({ status: 'online', device: 'hw:1' }).state, LISTENER.ONLINE);
  assert.equal(listenerView({ status: 'offline' }).state, LISTENER.OFFLINE);
  assert.equal(listenerView({}).state, LISTENER.OFFLINE);
});

test('no invented device or engine: "--" when the api does not name them', () => {
  const v = listenerView({ status: 'online', listener_state: 'idle' });
  assert.equal(v.device, '--');
  assert.equal(v.engine, '--');
  assert.equal(listenerView({ status: 'online', listener_state: 'idle', device: '--' }).device, '--');
});

test('a failed request is OFFLINE with the error; no answer yet is CHECKING', () => {
  const v = listenerView(null, 'HTTP Error 502');
  assert.equal(v.state, LISTENER.OFFLINE);
  assert.equal(v.message, 'HTTP Error 502');
  assert.equal(listenerView(null).state, LISTENER.CHECKING);
});
