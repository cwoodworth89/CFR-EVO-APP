import { useSyncExternalStore } from 'react';

/**
 * One line, and only one: Tailwind's `lg` breakpoint (1024 px). Below it the console and the
 * dispatch display are phones or a tablet held upright -- sidebars become sheets over the map, the detail stack
 * becomes tabs, the dispatch grid stacks. At it and above nothing changes, so the hall
 * display and the workstation keep the layout they have (kiosk-responsive-ergonomics).
 *
 * Kept as a hook rather than only as `md:` classes because a few decisions are not CSS:
 * mounting one map instead of three, collapsing the search sheet once an address is picked,
 * and padding a fit by an overlay's height instead of its width. Those read this.
 *
 * `max-width: 1023.98px` is the complement of Tailwind's `min-width: 1024px`, so the two never
 * disagree at the boundary. Measured 2026-09-09 with `md` (768 px) as the line: a landscape
 * phone at 852 px and an iPad upright at 820 px got the desktop columns and were left a 152 px
 * and a 120 px map beside a 320 px sidebar and a 380 px stack. The columns need about 1,000 px
 * to leave a map worth having, which is what `lg` says. Operator ruling 2026-09-09: the crew's phone is the primary
 * surface (docs/briefings/mobile_accessibility_review.md).
 */
export const COMPACT_QUERY = '(max-width: 1023.98px)';

function mediaQueryList() {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return null;
  return window.matchMedia(COMPACT_QUERY);
}

function subscribe(onChange) {
  const mql = mediaQueryList();
  if (!mql) return () => {};
  mql.addEventListener('change', onChange);
  return () => mql.removeEventListener('change', onChange);
}

function getSnapshot() {
  const mql = mediaQueryList();
  return mql ? mql.matches : false;
}

const getServerSnapshot = () => false;

export function useCompactViewport() {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}
