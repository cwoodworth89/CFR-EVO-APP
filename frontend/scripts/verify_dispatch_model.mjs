/**
 * Verifies that toActiveCall() reproduces, field for field, what App.jsx's hand-written
 * handleReviewCall translation produced — over every real dispatch in the database.
 *
 * Run before and after the state unification; the diff must be empty.
 *
 *   node frontend/scripts/verify_dispatch_model.mjs http://100.95.146.94:8000
 *
 * Result 2026-08-22, before the unification landed: 421 records, 0 field mismatches.
 *
 * The reference implementation below is a FROZEN COPY of App.jsx's handleReviewCall as it
 * stood before the change. It is deliberately not imported from the app -- once the app
 * uses toActiveCall, importing it would make this compare the function to itself and pass
 * unconditionally. Leave it frozen; it is the record of what the behaviour was.
 */
import { toActiveCall } from '../src/utils/dispatchModel.js';

const API = process.argv[2] || 'http://100.95.146.94:8000';

/** The original hand-written translation from App.jsx, verbatim, as the reference. */
function handleReviewCall_original(call) {
  const units = (call.verified_units && call.verified_units.length > 0)
    ? call.verified_units
    : (call.responding_units && call.responding_units.length > 0 ? call.responding_units : []);

  return {
    ...call,
    id: call.id,
    dispatch_id: call.dispatch_id,
    address: call.verified_address || call.target?.address || call.address || null,
    subaddress: call.target?.subaddress || '',
    intersection: call.target?.intersection || '',
    lat: call.target?.lat ?? call.lat ?? null,
    lng: call.target?.lng ?? call.lng ?? null,
    rings: call.target?.rings || call.rings || [],
    location_type: call.target?.location_type || null,
    segment: call.target?.segment || null,
    endpoints: call.target?.endpoints || null,
    length_m: call.target?.length_m ?? null,
    street: call.target?.street || null,
    resolution_note: call.target?.resolution_note || null,
    incident_type: call.verified_incident || call.incident_type || null,
    responding_units: units,
    priority_code: call.priority_code,
    verify_location: call.verify_location ?? (call.confidence_score ? call.confidence_score >= 90 : true),
    map_grid: call.target?.verified_map_grid || call.target?.map_grid || '',
    radio_channel: call.target?.verified_talkgroup || call.target?.radio_channel || '',
    tone_name: call.target?.tone_name || '',
    isReview: true,
  };
}

const FIELDS = [
  'id', 'dispatch_id', 'address', 'subaddress', 'intersection', 'lat', 'lng', 'rings',
  'location_type', 'segment', 'endpoints', 'length_m', 'street', 'resolution_note',
  'incident_type', 'responding_units', 'priority_code', 'verify_location',
  'map_grid', 'radio_channel', 'tone_name',
];

const res = await fetch(`${API}/api/dispatches?limit=1000`);
if (!res.ok) throw new Error(`API ${res.status}`);
const records = await res.json();
console.log(`fetched ${records.length} dispatch records from ${API}`);

let checked = 0, mismatched = 0;
const examples = [];

for (const record of records) {
  const before = handleReviewCall_original(record);
  const after = toActiveCall(record);
  checked++;
  for (const f of FIELDS) {
    const a = JSON.stringify(before[f] ?? null);
    const b = JSON.stringify(after[f] ?? null);
    if (a !== b) {
      mismatched++;
      if (examples.length < 10) {
        examples.push(`${record.dispatch_id}  ${f}:  ${a}  ->  ${b}`);
      }
    }
  }
}

console.log();
console.log(`records checked : ${checked}`);
console.log(`field mismatches: ${mismatched}`);
if (examples.length) {
  console.log('\nfirst mismatches:');
  for (const e of examples) console.log('  ' + e);
}
console.log(mismatched === 0 ? '\nPASS - identical output on every record' : '\nFAIL');
process.exit(mismatched === 0 ? 0 : 1);
