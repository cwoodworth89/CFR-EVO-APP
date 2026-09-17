import React from 'react';
import { accessStyle, passesAccessFilter, closureKey, closureText, roadRestriction, feedSeverityLine, BUCKETS, BUCKET_LABELS, DEFAULT_BUCKET_FILTER, countByBucket, groupByBucket } from '../../utils/closureAccess';

/** Hall labels and their badge classes. Static, so it lives at module scope: as a literal
 *  inside the component it was rebuilt every render and read by the useMemo below without
 *  being in its dependency list, which is what react-hooks/preserve-manual-memoization was
 *  reporting -- the compiler could not preserve a memo whose inputs it could not see. */
const GROUP_DEFS = {
  "1": { label: "Town Centre (Hall 1)", color: "border-rose-500/80 text-rose-400 bg-rose-950/40" },
  "2": { label: "Mariner (Hall 2)", color: "border-blue-500/80 text-blue-400 bg-blue-950/40" },
  "3": { label: "Austin Heights (Hall 3)", color: "border-emerald-500/80 text-emerald-400 bg-emerald-950/40" },
  "4": { label: "Burke Mountain (Hall 4)", color: "border-purple-500/80 text-purple-400 bg-purple-950/40" },
  "OTHER": { label: "Regional Corridors / Other", color: "border-slate-600 text-slate-400 bg-slate-800/30" }
};

/** Where tapping a closure card flies the map, or null when the record carries no usable
 *  location. Same order as RoadClosureMarker.jsx: the closure's own point, then the first
 *  vertex of its own polyline -- both real data from the same record -- and otherwise
 *  nothing. No default coordinate (CLAUDE.md 5, 6.1): since e3009d6a the API sends
 *  `coordinates: null` rather than a fake point, and Leaflet's flyTo throws on null, which
 *  left the tap silently dead. Stricter than the marker only in rejecting NaN. Punch list #90. */
function closureMapPoint(closure) {
  const toPoint = pt => {
    if (!Array.isArray(pt) || pt.length < 2) return null;
    const lat = parseFloat(pt[0]);
    const lng = parseFloat(pt[1]);
    return Number.isFinite(lat) && Number.isFinite(lng) ? [lat, lng] : null;
  };
  return toPoint(closure.coordinates)
    ?? (Array.isArray(closure.polyline) && closure.polyline.length > 0 ? toPoint(closure.polyline[0]) : null);
}

/** Bucket colours, the same families as the closure lines on the map (closureAccess.js). */
const BUCKET_ON_CLASS = {
  WARNING: 'border-red-500/60 text-red-300',
  CAUTION: 'border-yellow-500/60 text-yellow-300',
  INFO: 'border-cyan-500/60 text-cyan-300',
  UNSPECIFIED: 'border-slate-500/60 text-slate-200',
};
const BUCKET_DOT_CLASS = {
  WARNING: 'bg-red-500', CAUTION: 'bg-yellow-500', INFO: 'bg-cyan-400', UNSPECIFIED: 'bg-slate-400',
};

export function RightSidebar({ 
  // A phone: a drawer over the right of the map rather than a column beside it.
  compact = false,
  rightSidebarOpen, 
  setRightSidebarOpen, 
  appMode, 
  roadClosures, 
  showRoadClosures, 
  // Warning / Caution / Info / Unspecified: shown by the toggles at the top of this sidebar, and
  // the same state filters the map (useRoadClosures). Owned by useMapLayerPreferences.
  closureBuckets = DEFAULT_BUCKET_FILTER,
  setClosureBuckets = null,
  showActiveNow = true,
  showNext24h = false,
  showNext7d = false,
  map,
  onSelectClosure,
  zones = [],
  homeHall = "1",
  // { outcome, lastAttemptAt, error, sources } from useRoadClosures, or null when the API
  // did not send one (an api container older than 2026-09-16). Punch list #89.
  syncStatus = null
}) {
  const [collapsedGroups, setCollapsedGroups] = React.useState({});

  const toggleGroup = (groupId) => {
    setCollapsedGroups(prev => ({
      ...prev,
      [groupId]: !prev[groupId]
    }));
  };

  const { groupedClosures, bucketCounts } = React.useMemo(() => {
    const now = new Date();

    const inTimeframe = roadClosures
      .map(closure => {
        const start = closure.startDate ? new Date(closure.startDate) : null;
        const end = closure.endDate ? new Date(closure.endDate) : null;

        let isActive = false;
        let isFuture = false;
        let isExpired = false;

        if (start && now < start) {
          isFuture = true;
        } else if (end && now > end) {
          isExpired = true;
        } else {
          isActive = true;
        }

        return {
          ...closure,
          start,
          end,
          isActive,
          isFuture,
          isExpired
        };
      })
      .filter(closure => {
        if (closure.isExpired) return false;

        const isCurrentlyActive = closure.isActive;
        const is24hFuture = closure.isFuture && closure.start && ((closure.start.getTime() - now.getTime()) <= 24 * 3600 * 1000);
        const is7dFuture = closure.isFuture && closure.start && ((closure.start.getTime() - now.getTime()) <= 7 * 86400 * 1000);

        const matchesTimeframe = 
          (showActiveNow && isCurrentlyActive) ||
          (showNext24h && is24hFuture) ||
          (showNext7d && is7dFuture);

        return matchesTimeframe;
      });

    // The count on each toggle is every closure in its bucket for the current timeframe, shown
    // or not, so a bucket that is switched off never vanishes silently (CLAUDE.md 6.1).
    const counts = countByBucket(inTimeframe);
    const filtered = inTimeframe.filter(closure => passesAccessFilter(closure, closureBuckets));

    const groups = { "1": [], "2": [], "3": [], "4": [], OTHER: [] };
    filtered.forEach(closure => {
      const zoneMatch = zones.find(z => String(z.zone_id) === String(closure.zoneId));
      let hall = "OTHER";
      if (zoneMatch) {
        const u = zoneMatch.unit_id;
        if (u === "E1") hall = "1";
        else if (u === "E2") hall = "2";
        else if (u === "E3" || u === "Q5") hall = "3";
        else if (u === "E4") hall = "4";
      }
      if (groups[hall]) {
        groups[hall].push(closure);
      } else {
        groups["OTHER"].push(closure);
      }
    });

    let order = ["1", "2", "3", "4", "OTHER"];
    if (homeHall === "1") order = ["1", "2", "3", "4", "OTHER"];
    else if (homeHall === "2") order = ["2", "1", "3", "4", "OTHER"];
    else if (homeHall === "3") order = ["3", "1", "2", "4", "OTHER"];
    else if (homeHall === "4") order = ["4", "1", "2", "3", "OTHER"];

    // Hall, then impact (operator 2026-09-17: "group by hall, but maybe we change to display a
    // subgroup by impact, then dates inside those groups"): Warning, Caution, Info, Unspecified,
    // empty ones left out, newest start first inside each (groupByBucket).
    const halls = order
      .map(hallKey => ({
        unit: hallKey,
        count: groups[hallKey].length,
        buckets: groupByBucket(groups[hallKey]),
        ...GROUP_DEFS[hallKey]
      }))
      .filter(g => g.count > 0);
    return { groupedClosures: halls, bucketCounts: counts };
    // showActiveNow / showNext24h / showNext7d were read by the filter above and missing
    // from this list. Nothing has ever called their setters -- useMapLayerPreferences
    // returns them but no control is wired -- so the values never changed and the stale
    // grouping never showed. Latent, not live, and listed now so that wiring a timeframe
    // toggle is a UI change rather than a UI change plus a silent bug.
  }, [roadClosures, zones, homeHall, closureBuckets,
      showActiveNow, showNext24h, showNext7d]);

  const isExplore = appMode === "EXPLORE";
  if (!isExplore) return null; // Only render right sidebar alerts in Explore/Information Mode

  // 320 px beside the map; over it, most of a phone's width but never more than 24 rem.
  const openWidth = compact ? 'w-[min(85vw,24rem)]' : 'w-80';

  const formatDateRange = (start, end) => {
    if (!start) return "Ongoing (Until Further Notice)";
    
    const options = { month: 'short', day: 'numeric', year: 'numeric' };
    const startStr = start.toLocaleDateString('en-US', options);
    
    if (!end) {
      return `Started ${startStr} (Until Further Notice)`;
    }
    
    const endStr = end.toLocaleDateString('en-US', options);
    if (start.toDateString() === end.toDateString()) {
      return startStr;
    }
    
    return `${startStr} - ${endStr}`;
  };

  // Punch list #89, operator ruling 2026-09-16: warn only while the last attempt to sync
  // the closure feeds FAILED, and say nothing otherwise. NOT_ATTEMPTED is not a failure --
  // it is what a database never synced by a build that records the outcome reports, and it
  // is the live value on the kiosk today -- and a null status is an older api container,
  // which is equally not a failure. Both render no banner (CLAUDE.md 6.1).
  const syncFailed = syncStatus?.outcome === "FAILED";

  // Only shown when the backend gave a parseable timestamp; never a placeholder that could
  // be read as the time of an attempt that did not happen. A plain value, not a useMemo:
  // this runs after the `!isExplore` early return above, and a hook there changes the hook
  // count when appMode changes with the sidebar mounted (react-hooks/rules-of-hooks).
  const lastAttemptAt = syncStatus?.lastAttemptAt ? new Date(syncStatus.lastAttemptAt) : null;
  const lastAttemptLabel = lastAttemptAt && !Number.isNaN(lastAttemptAt.getTime())
    ? lastAttemptAt.toLocaleString('en-US', {
        month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit'
      })
    : null;

  return (
    <div className={`${compact ? 'absolute inset-y-0 right-0' : 'relative'} h-full flex flex-row-reverse transition-all duration-300 ease-in-out z-[1000] min-w-0 flex-shrink-0 ${rightSidebarOpen ? `${openWidth} border-l border-slate-800` : 'w-0'}`}>
       {/* Sidebar Body Wrapper (animates width and uses overflow-hidden to prevent contents sticking out when collapsed) */}
       <div className={`h-full bg-slate-900 flex flex-col transition-all duration-300 ease-in-out overflow-hidden ${rightSidebarOpen ? openWidth : 'w-0'}`}>
          <div className={`${openWidth} h-full flex flex-col overflow-hidden`}>
             {/* Header Title */}
             <div className="bg-slate-950 p-4 border-b border-slate-800 text-center flex-shrink-0">
                <div className="text-slate-500 text-[10px] uppercase font-mono tracking-widest mb-1">CFR DISPATCH</div>
                <div className="text-lg text-rose-500 font-extrabold uppercase font-sans tracking-wide">ROAD CLOSURES</div>
             </div>

             {/* Sync failure banner -- outside the scroll area on purpose: a warning that
                 can be scrolled out of sight is a warning the crew does not get. The list
                 keeps drawing beneath it, since a stale list with a warning beats an empty
                 one (punch list #89). */}
             {syncFailed && (
               <div
                 role="status"
                 className="flex-shrink-0 mx-4 mt-4 p-2.5 rounded-lg bg-amber-950/40 border border-amber-500/60 flex flex-col gap-1"
               >
                  <div className="text-[11px] font-black uppercase font-mono tracking-wide text-amber-400">
                     ⚠️ CLOSURE FEED SYNC FAILED
                  </div>
                  <div className="text-[10px] font-mono text-amber-200/90 leading-snug">
                     Showing the last list received. It may be out of date.
                  </div>
                  {syncStatus.error && (
                    <div className="text-[10px] font-mono text-amber-300/80 leading-snug break-words">
                       {syncStatus.error}
                    </div>
                  )}
                  {lastAttemptLabel && (
                    <div className="text-[9px] font-mono text-amber-500/70">
                       Last attempt {lastAttemptLabel}
                    </div>
                  )}
               </div>
             )}

             {/* Bucket toggles, at the top of the sidebar (operator 2026-09-17: "move and rename the
                 filtering toggles to inside the road closures side bar, at the top, and let them
                 filter the list and map"). Buttons with the state in words and the count on each,
                 sized for a finger; nothing in a tooltip. Hidden with the layer off, like the list. */}
             {showRoadClosures && (
               <div className="flex-shrink-0 px-4 pt-3 grid grid-cols-2 gap-2">
                 {BUCKETS.map((bucket) => {
                   const on = Boolean(closureBuckets?.[bucket]);
                   return (
                     <button
                       key={bucket}
                       type="button"
                       aria-pressed={on}
                       onClick={() => setClosureBuckets && setClosureBuckets((prev) => ({ ...(prev || DEFAULT_BUCKET_FILTER), [bucket]: !prev?.[bucket] }))}
                       className={`flex items-center justify-between gap-2 rounded-lg border px-2.5 py-2 touch:py-3 font-mono text-[11px] font-bold uppercase tracking-wide cursor-pointer transition ${
                         on ? `${BUCKET_ON_CLASS[bucket]} bg-slate-950` : 'border-slate-800 bg-slate-900 text-slate-500'
                       }`}
                     >
                       <span className="flex items-center gap-1.5 min-w-0">
                         <span className={`w-2 h-2 rounded-full flex-shrink-0 ${on ? BUCKET_DOT_CLASS[bucket] : 'bg-slate-700'}`}></span>
                         <span className="truncate">{BUCKET_LABELS[bucket]}</span>
                       </span>
                       <span className={on ? '' : 'text-slate-600'}>({bucketCounts[bucket]})</span>
                     </button>
                   );
                 })}
               </div>
             )}

             {/* Alerts Card List */}
             <div className="p-4 flex-grow overflow-y-auto min-h-0 scrollbar-thin scrollbar-thumb-slate-800 scrollbar-track-transparent">
                {showRoadClosures ? (
                    <div className="flex flex-col gap-4 pr-1">
                        {groupedClosures.length > 0 ? (
                            groupedClosures.map((group) => (
                                <div key={group.unit} className="flex flex-col gap-2">
                                    {/* Group Title Header */}
                                    <div 
                                      onClick={() => toggleGroup(group.unit)}
                                      className={`text-[10px] font-black uppercase font-mono px-2 py-1.5 border-l-2 rounded-r-md flex justify-between items-center shadow-sm cursor-pointer select-none hover:brightness-110 transition-all ${group.color}`}
                                    >
                                        <span className="flex items-center gap-1.5">
                                          <span>{collapsedGroups[group.unit] ? "▶" : "▼"}</span>
                                          <span>📍 {group.label}</span>
                                        </span>
                                        <span className="opacity-75 font-mono">{group.count}</span>
                                    </div>
                                    
                                    {/* Group Closures */}
                                    {!collapsedGroups[group.unit] && (
                                      <div className="flex flex-col gap-2 pl-1 border-l border-slate-800/40">
                                        {group.buckets.map((sub) => (
                                        <div key={sub.bucket} className="flex flex-col gap-2">
                                          <div className="flex items-center justify-between px-1 pt-0.5 font-mono text-[10px] font-bold uppercase tracking-[0.12em] text-slate-400">
                                            <span className="flex items-center gap-1.5">
                                              <span className={`w-1.5 h-1.5 rounded-full ${BUCKET_DOT_CLASS[sub.bucket]}`}></span>
                                              {BUCKET_LABELS[sub.bucket]}
                                            </span>
                                            <span className="text-slate-500">{sub.closures.length}</span>
                                          </div>
                                        {sub.closures.map((closure, idx) => {
                                          const mapPoint = closureMapPoint(closure);
                                          const access = accessStyle(closure);
                                          const restriction = roadRestriction(closure);
                                          const severityLine = feedSeverityLine(closure);
                                          return (
                                            <div 
                                              // rowId, the database row: stable across syncs and always sent (#91).
                                              key={closureKey(closure) ?? `${group.unit}-${idx}`}
                                              onClick={() => {
                                                // No location, no fly and no selection: there is
                                                // no marker to open, and the card says why below.
                                                if (!mapPoint) return;
                                                if (map) {
                                                  map.flyTo(mapPoint, 16, { animate: true });
                                                }
                                                if (onSelectClosure) {
                                                  onSelectClosure(closure);
                                                }
                                              }}
                                              className={`bg-slate-950 border border-slate-850 text-left p-2.5 rounded-xl shadow-sm transition-all flex flex-col gap-1.5 group relative overflow-hidden flex-shrink-0 ${
                                                mapPoint ? 'hover:bg-slate-900 hover:border-slate-750 cursor-pointer' : 'cursor-default'
                                              }`}
                                            >
                                                 {/* Street Name (Prominent & Color-coded) & Source */}
                                                 <div className="flex justify-between items-center gap-1.5">
                                                     <span className={`text-xs font-black uppercase tracking-wide truncate ${access.text}`}>
                                                        {closureText(closure.street)}
                                                     </span>
                                                     <span className="text-[8px] text-slate-500 font-mono font-medium flex-shrink-0">{closure.source}</span>
                                                 </div>

                                                 {/* Operator ruling 2026-09-16 (#90): no coordinates shows an
                                                     error under the location, and the card still displays.
                                                     Said on the card, not in a tooltip: the hall display is touch. */}
                                                 {!mapPoint && (
                                                   <div className="text-[9px] font-mono font-bold text-amber-400 bg-amber-500/10 border border-amber-500/30 rounded px-1.5 py-1">
                                                     ⚠️ NO MAP LOCATION IN FEED RECORD
                                                   </div>
                                                 )}
                                                 
                                                 {/* Headline & Warning Type Pill */}
                                                 <div className="flex justify-between items-center text-[9px] font-mono font-bold text-slate-400">
                                                    <span className="truncate pr-1">{closureText(closure.headline)}</span>
                                                    <span className={`text-[7px] px-1 py-0.2 rounded font-black tracking-wider flex-shrink-0 ${access.pill}`}>
                                                      {access.label}
                                                    </span>
                                                 </div>

                                                 {/* #91 ruling 5: the restriction DriveBC states, beside the tier (a
                                                     one-direction closure names its direction: crews may go counterflow
                                                     with flaggers), and DriveBC's own severity as information, never as
                                                     the tier. Both absent for Municipal 511 and for an older api. */}
                                                 {(restriction || severityLine) && (
                                                   <div className="flex justify-between items-center gap-2 text-[9px] font-mono">
                                                     <span className={`font-bold truncate ${access.text}`}>{restriction || ''}</span>
                                                     {severityLine && (
                                                       <span className="text-slate-500 flex-shrink-0">{severityLine}</span>
                                                     )}
                                                   </div>
                                                 )}

                                                 {/* Date Range & Status Pill */}
                                                 <div className="flex justify-between items-center text-[9px] font-mono border-t border-slate-900/50 pt-1.5 mt-0.5">
                                                    <span className="text-slate-400 flex items-center gap-1">
                                                      📅 {formatDateRange(closure.start, closure.end)}
                                                    </span>
                                                    {closure.isActive ? (
                                                      <span className="bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-1.5 py-0.2 rounded text-[7px] font-black tracking-wider flex items-center gap-1">
                                                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 motion-safe:animate-pulse inline-block"></span>
                                                        ACTIVE
                                                      </span>
                                                    ) : (
                                                      <span className="bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 px-1.5 py-0.2 rounded text-[7px] font-black tracking-wider flex items-center gap-1">
                                                        <span className="w-1.5 h-1.5 rounded-full bg-indigo-500 inline-block"></span>
                                                        FUTURE
                                                      </span>
                                                    )}
                                                 </div>

                                            </div>
                                          );
                                        })}
                                        </div>
                                        ))}
                                      </div>
                                    )}
                                </div>
                            ))
                        ) : (
                            <div className="text-center py-12 text-slate-650 text-xs italic">
                               No closures in the buckets switched on.
                            </div>
                        )}
                    </div>
                ) : (
                    <div className="text-center py-16 text-slate-600 text-xs italic border border-dashed border-slate-850 rounded-xl p-4 mt-4">
                       Road Closures layer is disabled. Turn it on in the Control Panel to view active alerts.
                    </div>
                )}
             </div>
          </div>
       </div>

       {/* Floating Toggle Tab */}
       <button 
         onClick={() => setRightSidebarOpen(!rightSidebarOpen)}
         className={`absolute ${compact ? 'top-24' : 'top-1/2 -translate-y-1/2'} -left-6 touch:-left-9 z-[1010] bg-slate-900 hover:bg-slate-800 text-slate-400 hover:text-white rounded-l-lg w-6 touch:w-9 h-16 flex items-center justify-center shadow-2xl border border-r-0 border-slate-800 cursor-pointer select-none transition-all duration-300`}
         title={rightSidebarOpen ? "Collapse Alerts" : "Expand Alerts"}
         aria-label={rightSidebarOpen ? "Collapse road closures" : "Expand road closures"}
       >
         <span className="text-[10px] font-black">{rightSidebarOpen ? "▶" : "◀"}</span>
       </button>
    </div>
  );
}
