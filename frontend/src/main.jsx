import { StrictMode, Component } from 'react'
import { createRoot } from 'react-dom/client'
import L from 'leaflet'
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png'
import markerIcon from 'leaflet/dist/images/marker-icon.png'
import markerShadow from 'leaflet/dist/images/marker-shadow.png'
import './index.css'
import App from './App.jsx'

// Fix Leaflet's default icon asset paths when bundling (Vite/GitHub Pages)
delete L.Icon.Default.prototype._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: markerIcon2x,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
})

// ---------------------------------------------------------------------------
// Stale-chunk failsafe -- punch list #44b.
//
// `npm run build` emits content-hashed chunks and DELETES the previous ones. A
// kiosk tab left open across a deploy still holds the old index.html and asks
// for hashes that are no longer on disk. Because the chunk is only fetched when
// it is first needed, the tab looks perfectly healthy until that moment.
//
// This has now taken two live calls off the display: an alarm activation on
// 2026-08-29 (DISP-2026-AAFDB8) and an overdose on 2026-08-31 (DISP-2026-F7D588).
// Both times the pipeline was flawless and only the display failed. The only
// mitigation was remembering to hard-reload after every deploy, and remembering
// is not a mechanism.
//
// Reloading is a real fix here: nginx serves index.html with no Cache-Control
// (verified in /etc/nginx/sites-enabled 2026-08-31), so a reload revalidates and
// picks up the current hashes.
//
// ONE shot. The marker is cleared once the app has painted, so a later deploy can
// recover again; but if the reload ALSO fails -- server genuinely down rather than
// a stale chunk -- the marker is still set, we stop, and the error boundary shows.
// That is the reload-loop guard.
// ---------------------------------------------------------------------------
const STALE_CHUNK_MARKER = 'cfr-evo:stale-chunk-reload';

// Message text varies by browser: Chrome says "error loading dynamically imported
// module", Firefox "error loading dynamically imported module", Safari "Importing
// a module script failed". Vite's own helper throws "Failed to fetch dynamically
// imported module".
const STALE_CHUNK_PATTERN =
  /(error|failed) loading dynamically imported module|failed to fetch dynamically imported module|importing a module script failed/i;

function isStaleChunkError(error) {
  return STALE_CHUNK_PATTERN.test(String(error?.message ?? error ?? ''));
}

// sessionStorage throws outright in some privacy modes, so every access is guarded
// and absence is treated as "no reload attempted yet".
function readReloadMarker() {
  try { return window.sessionStorage.getItem(STALE_CHUNK_MARKER); } catch { return null; }
}
function writeReloadMarker() {
  try { window.sessionStorage.setItem(STALE_CHUNK_MARKER, new Date().toISOString()); } catch { /* storage unavailable */ }
}
function clearReloadMarker() {
  try { window.sessionStorage.removeItem(STALE_CHUNK_MARKER); } catch { /* storage unavailable */ }
}

/** Returns true if a recovery reload was started, false if we already tried once. */
function recoverFromStaleChunk(source) {
  if (readReloadMarker()) {
    console.error(`[stale-chunk] ${source}: reload already attempted and it did not help -- showing the error card instead of looping.`);
    return false;
  }
  writeReloadMarker();
  console.warn(`[stale-chunk] ${source}: assets are from a previous build; reloading once to pick up the current one.`);
  window.location.reload();
  return true;
}

// Vite raises this on the window when a dynamic import fails to preload. Handling
// it here catches the failure BEFORE React's error boundary sees it, which is why
// the crew gets a flicker rather than a diagnostic card.
window.addEventListener('vite:preloadError', (event) => {
  if (recoverFromStaleChunk('vite:preloadError')) {
    event.preventDefault();
  }
});

class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error("Uncaught application runtime error:", error, errorInfo);
    // Last line of defence. vite:preloadError normally catches a stale chunk before
    // React sees it, but a lazy import that rejects outside the preload helper lands
    // here instead. Same one-shot guard, so this cannot loop.
    if (isStaleChunkError(error)) {
      recoverFromStaleChunk('error boundary');
    }
  }

  render() {
    if (this.state.hasError) {
      const stale = isStaleChunkError(this.state.error);
      return (
        <div className="w-screen h-screen bg-slate-950 text-slate-100 flex flex-col items-center justify-center p-6 text-center select-none font-sans">
          <div className="max-w-2xl bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-2xl flex flex-col items-center gap-4 text-left">
            <div className="flex items-center gap-2 text-rose-400">
              <span className="text-3xl">⚠️</span>
              <h1 className="text-lg font-bold uppercase tracking-wider">
                {stale ? 'Display Out Of Date — Reload Required' : 'Application Diagnostic Error'}
              </h1>
            </div>
            {stale ? (
              <div className="w-full bg-amber-500/10 border border-amber-500/40 rounded-xl p-4">
                <p className="text-sm text-amber-200 font-bold leading-relaxed">
                  This display is running an old version of the software and could not load
                  part of itself. An automatic reload was attempted and did not fix it.
                </p>
                <p className="text-sm text-amber-100 mt-3 leading-relaxed">
                  Press <span className="font-mono font-extrabold bg-slate-950 px-2 py-0.5 rounded border border-amber-500/40">Ctrl</span>
                  {' + '}<span className="font-mono font-extrabold bg-slate-950 px-2 py-0.5 rounded border border-amber-500/40">Shift</span>
                  {' + '}<span className="font-mono font-extrabold bg-slate-950 px-2 py-0.5 rounded border border-amber-500/40">R</span>
                  {' '}on this display, or press the button below.
                </p>
                <p className="text-xs text-amber-200/70 mt-3 leading-relaxed">
                  Dispatches are still being received and recorded — this is a display fault
                  only. Nothing has been lost.
                </p>
              </div>
            ) : (
            <p className="text-xs text-slate-400 font-mono leading-relaxed">
              An unhandled exception occurred during application execution:
            </p>
            )}
            {!stale && this.state.error && (
              <div className="w-full bg-slate-950 border border-slate-800 rounded-xl p-3 text-[11px] font-mono text-rose-300 overflow-x-auto max-h-48 whitespace-pre-wrap">
                {this.state.error.toString()}
                {this.state.error.stack && (
                  <div className="text-[9.5px] text-slate-500 mt-2 border-t border-slate-800 pt-2">
                    {this.state.error.stack}
                  </div>
                )}
              </div>
            )}
            <button
              onClick={() => {
                // Clearing the marker is what makes this button work at all: the
                // one-shot guard would otherwise refuse the operator's own retry.
                clearReloadMarker();
                this.setState({ hasError: false, error: null });
                window.location.reload();
              }}
              className={`font-extrabold px-5 py-2.5 rounded-xl shadow-lg transition cursor-pointer self-center ${
                stale
                  ? 'bg-amber-400 hover:bg-amber-300 text-black text-base px-8 py-3'
                  : 'bg-sky-500 hover:bg-sky-400 text-black text-xs'
              }`}
            >
              🔄 RELOAD DISPLAY
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </StrictMode>,
)

// Hand the one-shot budget back once this boot has proved healthy. Without it the
// FIRST stale chunk would be recovered and every later deploy would land on the
// error card.
//
// NOT requestAnimationFrame, which is what this was first written as. rAF does not
// fire while the document is hidden -- measured in the browser 2026-08-31:
// document.hidden true, no callback within 700 ms. A kiosk whose display has blanked
// or whose tab is backgrounded would never clear the marker, silently degrading this
// failsafe to single-use-for-the-life-of-the-tab. Timers do still fire when hidden.
// Recorded in docs/standards/dependency-behaviour.md.
//
// Ten seconds rather than immediately: the marker has to outlive a reload that lands
// on the SAME failure, because that is the reload-loop guard. A boot that has run ten
// seconds without a chunk error is healthy.
setTimeout(clearReloadMarker, 10_000);
