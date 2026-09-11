import test from 'node:test';
import assert from 'node:assert/strict';
import { hydrantCardModel, metresToFeet, hydrantHow, CARD_STATE } from '../src/utils/hydrantCard.js';
import { TIER } from '../src/utils/routeHydrants.js';

const city = (over = {}) => ({ gisId: 'L-144', status: 'ACTIVE', flowClass: 'AA', distance: 45, how: TIER.APPROACH, ...over });
const priv = (over = {}) => ({ gisId: 'P-882', status: 'PRIVATE', flowClass: null, distance: 29, how: TIER.DOORSTEP, ...over });
const found = (picks, over = {}) => ({ tier: picks[0]?.how || TIER.NONE, picks, routeKnown: true, loading: false, failed: false, ...over });

test('feet from metres, exact foot, rounded', () => {
  assert.equal(metresToFeet(45), 148);          // the canvas's own figure for 45 m
  assert.equal(metresToFeet(0.3048), 1);
  assert.equal(metresToFeet(null), null);
  assert.equal(metresToFeet('x'), null);
});

test('no location is awaiting, not a hydrant answer', () => {
  const m = hydrantCardModel({ hasCoords: false, hydrants: found([city()]) });
  assert.equal(m.state, CARD_STATE.AWAITING);
  assert.deepEqual(m.rows, []);
});

test('a failed lookup is reported as failed, never as no hydrant', () => {
  const m = hydrantCardModel({ hasCoords: true, hydrants: found([], { failed: true }) });
  assert.equal(m.state, CARD_STATE.FAILED);
  assert.equal(m.warn, true);
});

test('loading is its own state', () => {
  const m = hydrantCardModel({ hasCoords: true, hydrants: found([], { loading: true }) });
  assert.equal(m.state, CARD_STATE.LOADING);
});

test('nothing within the supply lay is the amber warning', () => {
  const m = hydrantCardModel({ hasCoords: true, hydrants: found([], { tier: TIER.NONE }) });
  assert.equal(m.state, CARD_STATE.NONE);
  assert.equal(m.warn, true);
});

test('one City hydrant on the approach: one row, how it was chosen, in feet', () => {
  const m = hydrantCardModel({ hasCoords: true, hydrants: found([city()]) });
  assert.equal(m.state, CARD_STATE.PICKS);
  assert.equal(m.title, 'FIRST HYDRANT');
  assert.equal(m.warn, false);
  assert.equal(m.rows.length, 1);
  assert.equal(m.rows[0].id, 'L-144');
  assert.equal(m.rows[0].flowClass, 'AA');
  assert.equal(m.rows[0].feet, 148);
  assert.equal(m.rows[0].isPrivate, false);
  assert.equal(m.note, 'City · before arrival, on the route');
});

test('two straight-line picks are a list, so only the first is shown', () => {
  const m = hydrantCardModel({ hasCoords: true, hydrants: found([city({ how: TIER.NEAR, distance: 60 }), city({ gisId: 'L-145', how: TIER.NEAR, distance: 80 })]) });
  assert.equal(m.rows.length, 1);
  assert.match(m.note, /straight-line; none on the approach/);
});

test('route pending is said when the route is not yet drawn', () => {
  const m = hydrantCardModel({ hasCoords: true, hydrants: found([city({ how: TIER.NEAR })], { routeKnown: false }) });
  assert.match(m.note, /route pending/);
});

test('a private hydrant first with a City one second is the PRIVATE IS CLOSER pair', () => {
  const m = hydrantCardModel({ hasCoords: true, hydrants: found([priv(), city()]) });
  assert.equal(m.title, 'PRIVATE IS CLOSER');
  assert.equal(m.warn, true);
  assert.equal(m.rows.length, 2);
  assert.equal(m.rows[0].isPrivate, true);
  assert.equal(m.rows[0].flowClass, null);     // UNRATED is rendered from null, not invented
  assert.equal(m.rows[1].id, 'L-144');
  assert.match(m.note, /Nearest is private and unrated/);
});

test('a long lay with the closer off-route option is the LONG LAY pair', () => {
  const m = hydrantCardModel({ hasCoords: true, hydrants: found([
    city({ distance: 170, longLay: true }),
    city({ gisId: 'L-200', how: TIER.NEAR, distance: 70, closerAlternative: true }),
  ]) });
  assert.equal(m.title, 'LONG LAY');
  assert.equal(m.rows.length, 2);
  assert.equal(m.note, null);
  assert.equal(m.rows[1].how, 'from the address, off route: the closer option');
});

test('a long lay with no closer option is one amber row, and the chip is the whole message', () => {
  const m = hydrantCardModel({ hasCoords: true, hydrants: found([city({ distance: 170, longLay: true })]) });
  assert.equal(m.title, 'LONG LAY');
  assert.equal(m.warn, true);
  assert.equal(m.rows.length, 1);
  // The amber LONG LAY chip and the distance say it; the sentence under them said it again
  // and the operator asked for it gone (2026-09-10).
  assert.equal(m.note, null);
});

test('every tier has a how line and unknown tiers have none', () => {
  assert.equal(hydrantHow({ how: TIER.DOORSTEP }), 'within a 50 ft roll of the address');
  assert.equal(hydrantHow({ how: TIER.SUPPLY }), 'within the 1,000 ft supply lay; none within 300 ft');
  assert.equal(hydrantHow({ how: 'something-else' }), '');
});
