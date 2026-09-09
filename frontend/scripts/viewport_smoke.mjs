/**
 * Renders the built console at phone, tablet, touch-kiosk and workstation sizes and
 * measures what a phone layout has to get right: no horizontal overflow, no control off
 * the screen, the map at least 60 % of the width below the `lg` line, and a real zoom
 * (not NaN) after a route fit. Writes a screenshot per state to --out.
 *
 *   cd frontend && npm run build && npx vite preview --port 4173 &
 *   node scripts/viewport_smoke.mjs http://localhost:4173/ --out /tmp/shots
 *
 * Needs Playwright with a Chromium (`npx playwright install chromium` once, or a global
 * install). It is deliberately NOT a devDependency: the kiosk's `npm install` must not
 * pull a browser. The API, tiles and broker need not be reachable: the address search is
 * answered with no parcel rows, so the one suggestion offered is a building the app itself
 * carries in MapConstants.KNOWN_BUILDINGS, with its real coordinates. Nothing is invented,
 * and the dispatch display is not exercised here at all -- that takes a real call, which is
 * the review replay on the kiosk (CLAUDE.md s6.5).
 *
 * First run 2026-09-09 (docs/briefings/mobile_accessibility_review.md): before the phone
 * layout, 393 px wide gave a 73 px map with the header's controls off screen; after, the
 * map is 393 px and nothing is off screen at any of the five sizes.
 */
import { chromium } from 'playwright';
import { mkdirSync } from 'node:fs';

const URL = process.argv[2] || 'http://localhost:4173/';
const outIdx = process.argv.indexOf('--out');
const OUT = outIdx > 0 ? process.argv[outIdx + 1] : null;
if (OUT) mkdirSync(OUT, { recursive: true });

const VIEWPORTS = [
  { name: 'phone-portrait-393x852',  width: 393,  height: 852,  isMobile: true,  hasTouch: true },
  { name: 'phone-landscape-852x393', width: 852,  height: 393,  isMobile: true,  hasTouch: true },
  { name: 'ipad-portrait-820x1180',  width: 820,  height: 1180, isMobile: true,  hasTouch: true },
  { name: 'kiosk-touch-1280x800',    width: 1280, height: 800,  isMobile: false, hasTouch: true },
  { name: 'workstation-1916x1000',   width: 1916, height: 1000, isMobile: false, hasTouch: false },
];
const COMPACT_BELOW = 1024; // hooks/useCompactViewport.js
const QUERY = 'Grand Central 2';               // MapConstants.KNOWN_BUILDINGS
const SUGGESTION = '📍 2968 Glen Dr';

const browser = await chromium.launch({ headless: true });
let failures = 0;
const check = (ok, msg) => { if (!ok) failures += 1; console.log(`  ${ok ? 'ok  ' : 'FAIL'} ${msg}`); };

for (const vp of VIEWPORTS) {
  const ctx = await browser.newContext({ viewport: { width: vp.width, height: vp.height }, deviceScaleFactor: 1, isMobile: vp.isMobile, hasTouch: vp.hasTouch });
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e.message).slice(0, 160)));
  await page.route('**/api/parcels/search**', (r) => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ results: [] }) }));
  await page.route('**/api/parcels/lookup**', (r) => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ found: false }) }));
  await page.goto(URL, { waitUntil: 'networkidle', timeout: 30000 }).catch(() => {});
  await page.waitForTimeout(1200);

  const measure = () => page.evaluate(() => {
    const mapEl = document.querySelector('.leaflet-container');
    const m = mapEl ? mapEl.getBoundingClientRect() : null;
    const controls = [...document.querySelectorAll('button, a[href], select, input')]
      .map((b) => { const r = b.getBoundingClientRect(); return { t: (b.textContent || b.type || '').trim().slice(0, 20), w: r.width, h: r.height, off: r.right > innerWidth + 1 || r.left < -1 }; })
      .filter((b) => b.w > 0 && b.h > 0);
    return { scrollW: document.documentElement.scrollWidth, innerW: innerWidth, mapW: m ? m.width : 0, offscreen: controls.filter((b) => b.off).map((b) => b.t) };
  });

  console.log(`\n== ${vp.name} ==`);
  const shot = (name) => (OUT ? page.screenshot({ path: `${OUT}/${vp.name}-${name}.png` }) : Promise.resolve());
  await shot('1-explore');
  let m = await measure();
  check(m.scrollW <= m.innerW, `no horizontal overflow (${m.scrollW}/${m.innerW})`);
  check(m.offscreen.length === 0, `no control off screen${m.offscreen.length ? ': ' + m.offscreen.join(', ') : ''}`);
  if (vp.width < COMPACT_BELOW) check(m.mapW >= vp.width * 0.6, `map is at least 60 % of the width (${Math.round(m.mapW)} of ${vp.width})`);

  const search = page.locator('input[placeholder^="Search address"]');
  if (await search.count()) {
    await search.first().fill(QUERY);
    await page.waitForTimeout(700);
    const sugg = page.locator(`text=${SUGGESTION}`);
    check(await sugg.count() > 0, 'the known building is offered');
    if (await sugg.count()) {
      await sugg.first().click();
      await page.waitForTimeout(1500);
      await shot('2-target');
      m = await measure();
      check(m.offscreen.length === 0, 'no control off screen with a target');
      const zoom = await page.locator('text=ZOOM').first().locator('..').textContent().catch(() => '');
      check(/ZOOM\s*\d/.test(zoom || ''), `a real zoom after the fit (${(zoom || '').trim()})`);
      const fold = page.locator('[role="tablist"] button[aria-expanded]');
      if (await fold.count()) { await fold.first().click(); await page.waitForTimeout(500); await shot('2b-folded'); await fold.first().click(); await page.waitForTimeout(400); }
      const tab = page.locator('button[role="tab"]', { hasText: 'Satellite' });
      if (await tab.count()) { await tab.first().click(); await page.waitForTimeout(1000); await shot('3-satellite-tab'); }
    }
  }
  check(errors.length === 0, `no page errors${errors.length ? ': ' + errors.join(' | ') : ''}`);
  await ctx.close();
}
await browser.close();
console.log(failures ? `\n${failures} check(s) failed` : '\nall checks passed');
process.exit(failures ? 1 : 0);
