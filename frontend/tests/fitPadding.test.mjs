import test from 'node:test';
import assert from 'node:assert/strict';
import { fitPadding, snapPadding, MAX_PADDED_SHARE } from '../src/components/map/fitPadding.js';

// The dispatch map's own numbers, so the kiosk fit is unchanged by sharing the formula:
// a 1596 x 936 map (the operator's 1916-wide screen minus the sidebar) with the 320 px
// details box 12 px in from the left.
test('wide container reproduces the dispatch map formula', () => {
  const p = fitPadding({ width: 1596, height: 936, panel: { width: 320, height: 300, offsetLeft: 12, offsetTop: 12 }, panelSide: 'left' });
  assert.deepEqual(p.paddingTopLeft, [128 + 320 + 12, 112]);   // 8 % side + panel + its offset, 12 % top
  assert.deepEqual(p.paddingBottomRight, [128, 75]);            // 8 % side, 8 % bottom
});

test('small containers use the floors, not the fractions', () => {
  const p = fitPadding({ width: 300, height: 300 });
  assert.deepEqual(p.paddingTopLeft, [35, 45]);
  assert.deepEqual(p.paddingBottomRight, [35, 35]);
});

// The finding: padding wider than the map gives Leaflet a NaN zoom. The two paddings on
// an axis may never take more than MAX_PADDED_SHARE of it, whatever the panel measures.
test('padding never exceeds the container on a phone-width map', () => {
  for (const width of [73, 262, 393]) {
    const p = fitPadding({ width, height: 788, panel: { width: 320, height: 60, offsetLeft: 12, offsetTop: 12 }, panelSide: 'left' });
    const [l, t] = p.paddingTopLeft; const [r, b] = p.paddingBottomRight;
    assert.ok(l + r <= width * MAX_PADDED_SHARE + 1, `${width}: left ${l} + right ${r}`);
    assert.ok(t + b <= 788 * MAX_PADDED_SHARE + 1);
    assert.ok(l >= 0 && r >= 0 && t >= 0 && b >= 0);
  }
});

// On a phone the details box spans the top, so it pads the top by its height and the left
// by nothing; otherwise a full-width box would eat the whole map from the left.
test('a panel across the top pads the top, not the left', () => {
  const top = fitPadding({ width: 393, height: 460, panel: { width: 377, height: 56, offsetLeft: 8, offsetTop: 56 }, panelSide: 'top' });
  const none = fitPadding({ width: 393, height: 460 });
  assert.equal(top.paddingTopLeft[0], none.paddingTopLeft[0]);
  assert.equal(top.paddingTopLeft[1], none.paddingTopLeft[1] + 56 + 56);
});

test('sheets over the map add to the side they cover', () => {
  const p = fitPadding({ width: 393, height: 700, overlays: { bottom: 150 } });
  const none = fitPadding({ width: 393, height: 700 });
  assert.equal(p.paddingBottomRight[1], none.paddingBottomRight[1] + 150);
});

// A 55 % sheet over a phone-height map asks for more than the budget; the clamp scales
// both paddings down rather than handing Leaflet a negative fit area.
test('a sheet taller than the budget is clamped, not honoured', () => {
  const p = fitPadding({ width: 393, height: 700, overlays: { bottom: 385 } });
  const [, t] = p.paddingTopLeft; const [, b] = p.paddingBottomRight;
  assert.ok(t + b <= 700 * MAX_PADDED_SHARE + 1, `top ${t} + bottom ${b}`);
  assert.ok(b > t, 'the sheet side keeps the larger share');
});

test('a zero-size container falls back rather than dividing by nothing', () => {
  const p = fitPadding({ width: 0, height: 0 });
  assert.ok(p.paddingTopLeft.every(Number.isFinite) && p.paddingBottomRight.every(Number.isFinite));
});

test('snap pads every side equally and clamps the same way', () => {
  const wide = snapPadding({ width: 1596, height: 936 });
  assert.deepEqual(wide.paddingTopLeft, [94, 94]);               // 10 % of the shorter side
  assert.deepEqual(wide.paddingBottomRight, [94, 94]);
  const narrow = snapPadding({ width: 73, height: 788, panel: { width: 320, offsetLeft: 12 }, panelSide: 'left' });
  assert.ok(narrow.paddingTopLeft[0] + narrow.paddingBottomRight[0] <= 73 * MAX_PADDED_SHARE + 1);
});
