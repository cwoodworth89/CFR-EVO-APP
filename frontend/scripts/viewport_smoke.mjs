/**
 * Renders the built frontend at phone, tablet, touch-kiosk and workstation sizes and
 * measures what a layout has to get right: no horizontal overflow, no control off the
 * screen, the map at least 60 % of the width below the `lg` line, and a real zoom (not
 * NaN) after a route fit. Writes a screenshot per state to --out.
 *
 *   cd frontend && npm run build && npx vite preview --port 4173 &
 *   node scripts/viewport_smoke.mjs http://localhost:4173/ --out /tmp/shots
 *
 * Two passes:
 *
 *   The console (always): the address search is answered with no parcel rows, so the one
 *   suggestion offered is a building the app itself carries in MapConstants.KNOWN_BUILDINGS,
 *   with its real coordinates. Needs no API, tiles or broker.
 *
 *   The dispatch display (with --dispatch DISP-... and --api http://<kiosk>:8000): the named
 *   REAL dispatch record is fetched from the kiosk's API and handed to the app through its own
 *   reload-restore path (useKioskQueue reads /api/dispatches?limit=5 on boot), marked
 *   `isReview` and re-stamped to now so the five-minute restore window accepts it -- which is
 *   what the review replay does on the kiosk (elapsed from zero, auto-dismiss paused, REVIEW
 *   REPLAY on the header). Every other request to the API and to the tile server (--tiles) is
 *   proxied to the kiosk, so the route, the hydrants, the parcel and the basemap are the real
 *   answers. Nothing is synthesised (CLAUDE.md s6.5). Google Street View is whatever the built
 *   bundle's key allows; without one the tile shows its labelled fallback.
 *
 * Needs Playwright with a browser. It is deliberately NOT a devDependency: the kiosk's
 * `npm install` must not pull a browser. `npm i --no-save playwright` in frontend/ and either
 * `npx playwright install chromium` or, with Chrome installed, `--channel chrome`.
 *
 * First run 2026-09-09 (docs/briefings/mobile_accessibility_review.md): before the phone
 * layout, 393 px wide gave a 73 px map with the header's controls off screen; after, the
 * map is 393 px and nothing is off screen at any of the five sizes. The dispatch pass was
 * added 2026-09-09 for artboard 3A (docs/design/) and first run against DISP-2026-CE3851
 * (602 Como Lake Ave, five units) and DISP-2026-D65FD1 (3030 Gordon Ave, the canvas's own
 * example address).
 */
import { chromium } from 'playwright';
import { mkdirSync } from 'node:fs';

const argv = process.argv.slice(2);
// The one positional argument is the page URL; everything else is `--flag value`.
const positional = argv.filter((a, i) => !a.startsWith('--') && !(argv[i - 1] || '').startsWith('--'));
const PAGE_URL = positional[0] || 'http://localhost:4173/';
const opt = (name) => { const i = argv.indexOf(name); return i >= 0 ? argv[i + 1] : null; };
const opts = (name) => argv.map((a, i) => (a === name ? argv[i + 1] : null)).filter(Boolean);
const OUT = opt('--out');
const CHANNEL = opt('--channel') || undefined;   // e.g. 'chrome' to use an installed Chrome
const API = (opt('--api') || '').replace(/\/$/, '');
const TILES = (opt('--tiles') || '').replace(/\/$/, '');
const DISPATCHES = opts('--dispatch');
if (OUT) mkdirSync(OUT, { recursive: true });
if (DISPATCHES.length && !API) { console.error('--dispatch needs --api http://<kiosk>:8000'); process.exit(2); }

const VIEWPORTS = [
  { name: 'phone-portrait-393x852',  width: 393,  height: 852,  isMobile: true,  hasTouch: true },
  { name: 'phone-landscape-852x393', width: 852,  height: 393,  isMobile: true,  hasTouch: true },
  { name: 'ipad-portrait-820x1180',  width: 820,  height: 1180, isMobile: true,  hasTouch: true },
  { name: 'kiosk-touch-1280x800',    width: 1280, height: 800,  isMobile: false, hasTouch: true },
  { name: 'workstation-1916x1000',   width: 1916, height: 1000, isMobile: false, hasTouch: false },
];
const COMPACT_BELOW = 1024; // hooks/useCompactViewport.js
// The zoom readout is found by an EXACT text match: Playwright's bare `text=ZOOM` is a
// case-insensitive substring, and it started matching the hydrant card's "Tap to zoom"
// when that card moved into the header (2026-09-10).
const QUERY = 'Grand Central 2';               // MapConstants.KNOWN_BUILDINGS
const SUGGESTION = '📍 2968 Glen Dr';

// The page is served from localhost, so apiClient.js resolves the API and the tiles to these.
const PAGE_API = 'http://localhost:8000';
const PAGE_TILES = 'http://localhost:8081';

const browser = await chromium.launch({ headless: true, channel: CHANNEL });
let failures = 0;
const check = (ok, msg) => { if (!ok) failures += 1; console.log(`  ${ok ? 'ok  ' : 'FAIL'} ${msg}`); };

/** The real record, from the kiosk, as the API serves it. */
async function fetchDispatch(id) {
  const res = await fetch(`${API}/api/dispatches?limit=500`);
  if (!res.ok) throw new Error(`API ${res.status}`);
  const records = await res.json();
  const rec = records.find((r) => r.dispatch_id === id);
  if (!rec) throw new Error(`${id} not among the last 500 dispatches`);
  return rec;
}

async function proxy(route, base) {
  const u = new globalThis.URL(route.request().url());
  try {
    const resp = await route.fetch({ url: `${base}${u.pathname}${u.search}` });
    await route.fulfill({ response: resp });
  } catch {
    await route.abort().catch(() => {});
  }
}

// `vertical`: also count a control below the fold as off screen. False for a column that
// scrolls (the dispatch display on a phone), where below the fold is reachable.
const measure = (page, { vertical = true } = {}) => page.evaluate((vertical) => {
  const mapEl = document.querySelector('.leaflet-container');
  const m = mapEl ? mapEl.getBoundingClientRect() : null;
  const controls = [...document.querySelectorAll('button, a[href], select, input')]
    .map((b) => { const r = b.getBoundingClientRect(); return { t: (b.textContent || b.getAttribute('aria-label') || b.type || '').trim().slice(0, 20), w: r.width, h: r.height, off: r.right > innerWidth + 1 || r.left < -1 || (vertical && r.bottom > innerHeight + 1) }; })
    .filter((b) => b.w > 0 && b.h > 0);
  return { scrollW: document.documentElement.scrollWidth, innerW: innerWidth, mapW: m ? m.width : 0, offscreen: controls.filter((b) => b.off).map((b) => b.t) };
}, vertical);

for (const vp of VIEWPORTS) {
  // ---- the console --------------------------------------------------------------------
  {
    const ctx = await browser.newContext({ viewport: { width: vp.width, height: vp.height }, deviceScaleFactor: 1, isMobile: vp.isMobile, hasTouch: vp.hasTouch });
    const page = await ctx.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e.message).slice(0, 160)));
    await page.route('**/api/parcels/search**', (r) => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ results: [] }) }));
    await page.route('**/api/parcels/lookup**', (r) => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ found: false }) }));
    await page.goto(PAGE_URL, { waitUntil: 'networkidle', timeout: 30000 }).catch(() => {});
    await page.waitForTimeout(1200);

    console.log(`\n== ${vp.name} :: console ==`);
    const shot = (name) => (OUT ? page.screenshot({ path: `${OUT}/${vp.name}-${name}.png` }) : Promise.resolve());
    await shot('1-explore');
    // Horizontal only: the console's sheets scroll, so a control below the fold is reachable.
    let m = await measure(page, { vertical: false });
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
        m = await measure(page, { vertical: false });
        check(m.offscreen.length === 0, 'no control off screen with a target');
        const zoom = await page.locator('text="ZOOM"').first().locator('..').textContent().catch(() => '');
        check(/ZOOM\s*\d/.test(zoom || ''), `a real zoom after the fit (${(zoom || '').trim()})`);
        const fold = page.locator('[role="tablist"] button[aria-expanded]');
        if (await fold.count()) { await fold.first().click(); await page.waitForTimeout(500); await shot('2b-folded'); await fold.first().click(); await page.waitForTimeout(400); }
        const tab = page.locator('button[role="tab"]', { hasText: 'Aerial' });
        if (await tab.count()) { await tab.first().click(); await page.waitForTimeout(1000); await shot('3-satellite-tab'); }
      }
    }
    check(errors.length === 0, `no page errors${errors.length ? ': ' + errors.join(' | ') : ''}`);
    await ctx.close();
  }

  // ---- the dispatch display, one real record at a time ---------------------------------
  for (const id of DISPATCHES) {
    const record = await fetchDispatch(id);
    const now = new Date().toISOString();
    const replay = { ...record, timestamp: now, created_at: now, isReview: true };

    const ctx = await browser.newContext({ viewport: { width: vp.width, height: vp.height }, deviceScaleFactor: 1, isMobile: vp.isMobile, hasTouch: vp.hasTouch });
    const page = await ctx.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e.message).slice(0, 160)));
    // Later registrations win, so the proxies go first and the replay record overrides them.
    await page.route((u) => u.origin === PAGE_API, (r) => proxy(r, API));
    if (TILES) await page.route((u) => u.origin === PAGE_TILES, (r) => proxy(r, TILES));
    await page.route((u) => u.origin === PAGE_API && u.pathname === '/api/dispatches' && u.searchParams.get('limit') === '5',
      (r) => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([replay]) }));
    await page.goto(PAGE_URL, { waitUntil: 'networkidle', timeout: 45000 }).catch(() => {});
    await page.waitForTimeout(3000);

    const tag = id.replace(/^DISP-\d+-/, '');
    console.log(`\n== ${vp.name} :: dispatch ${id} (${(record.verified_address || record.target?.address || '').trim()}) ==`);
    const shot = (name) => (OUT ? page.screenshot({ path: `${OUT}/${vp.name}-D-${tag}-${name}.png` }) : Promise.resolve());
    await shot('1-route');
    const compact = vp.width < COMPACT_BELOW;
    let m = await measure(page, { vertical: !compact });
    check(m.scrollW <= m.innerW, `no horizontal overflow (${m.scrollW}/${m.innerW})`);
    check(m.offscreen.length === 0, `no control off screen${m.offscreen.length ? ': ' + m.offscreen.join(', ') : ''}`);
    if (compact) {
      // The phone column scrolls: the bottom of it is the tile tabs, and it has to be reachable.
      const scrolled = await page.evaluate(() => { const r = document.querySelector('.kiosk-root'); if (!r) return null; r.scrollTo(0, r.scrollHeight); return r.scrollTop; });
      await page.waitForTimeout(400);
      await shot('1b-bottom');
      check(scrolled != null && scrolled > 0, `the phone column scrolls (${scrolled} px)`);
      await page.evaluate(() => document.querySelector('.kiosk-root')?.scrollTo(0, 0));
    }
    check(await page.locator('h1').count() > 0, 'the address heading is on screen');
    check(await page.locator('text=/REVIEW REPLAY/i').count() > 0, 'the header says REVIEW REPLAY');
    const pill = await page.locator('text=/^(ROUTE|STRAIGHT-LINE) ·/').first().textContent().catch(() => '');
    check(/(ROUTE|STRAIGHT-LINE) · [\d.]+ KM · \d+ MIN/.test(pill || ''), `the route pill carries OSRM's figures (${(pill || '').trim()})`);
    check(await page.locator('text=/HYDRANT|TAP TO ZOOM/i').count() > 0, 'the hydrant card is on the map');
    if (vp.width >= COMPACT_BELOW) {
      check(m.mapW >= vp.width * 0.5, `the route map is at least half the width (${Math.round(m.mapW)} of ${vp.width})`);
      const zoom = await page.locator('text="ZOOM"').first().locator('..').textContent().catch(() => '');
      check(/ZOOM\s*\d/.test(zoom || ''), `a real zoom after the route fit (${(zoom || '').trim()})`);
    } else {
      check(m.mapW >= vp.width * 0.9, `the route map spans the phone (${Math.round(m.mapW)} of ${vp.width})`);
    }

    // A control that cannot be tapped is a finding, not a crash: the click is given five
    // seconds and a failure is recorded against the run.
    const tap = async (locator, what) => {
      try { await locator.first().click({ timeout: 5000 }); return true; }
      catch { check(false, `${what} can be tapped`); return false; }
    };
    const snap = page.locator('button', { hasText: /snap to call/i });
    if (await snap.count() && await tap(snap, 'SNAP TO CALL')) {
      await page.waitForTimeout(2000);
      await shot('2-snap');
      const recentre = page.locator('button', { hasText: /re-centre/i });
      check(await recentre.count() > 0 && !(await recentre.first().isDisabled()), 'RE-CENTRE is live after a snap');
    }
    const tab = page.locator('button[role="tab"]', { hasText: /street view/i });
    if (await tab.count() && await tap(tab, 'the Street View tab')) { await page.waitForTimeout(1500); await shot('3-streetview-tab'); }
    check(errors.length === 0, `no page errors${errors.length ? ': ' + errors.join(' | ') : ''}`);
    await ctx.close();
  }
}
await browser.close();
console.log(failures ? `\n${failures} check(s) failed` : '\nall checks passed');
process.exit(failures ? 1 : 0);
