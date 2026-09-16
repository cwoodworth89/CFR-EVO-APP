import React from 'react';
import { accessStyle, passesAccessFilter, closureKey } from '../../utils/closureAccess';

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

export function RightSidebar({ 
  // A phone: a drawer over the right of the map rather than a column beside it.
  compact = false,
  rightSidebarOpen, 
  setRightSidebarOpen, 
  appMode, 
  roadClosures, 
  showRoadClosures, 
  filterNoAccess,
  filterAccessOnly,
  filterCaution,
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

  const groupedClosures = React.useMemo(() => {
    const now = new Date();

    const filtered = roadClosures
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
        // An N/A closure (no severity from the feed, #91) passes every access toggle.
        if (!passesAccessFilter(closure, { filterNoAccess, filterAccessOnly, filterCaution })) return false;

        const isCurrentlyActive = closure.isActive;
        const is24hFuture = closure.isFuture && closure.start && ((closure.start.getTime() - now.getTime()) <= 24 * 3600 * 1000);
        const is7dFuture = closure.isFuture && closure.start && ((closure.start.getTime() - now.getTime()) <= 7 * 86400 * 1000);

        const matchesTimeframe = 
          (showActiveNow && isCurrentlyActive) ||
          (showNext24h && is24hFuture) ||
          (showNext7d && is7dFuture);

        return matchesTimeframe;
      });

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

    Object.keys(groups).forEach(key => {
      groups[key].sort((a, b) => {
        const aTime = a.start ? a.start.getTime() : 0;
        const bTime = b.start ? b.start.getTime() : 0;
        return bTime - aTime; // Newest first
      });
    });

    let order = ["1", "2", "3", "4", "OTHER"];
    if (homeHall === "1") order = ["1", "2", "3", "4", "OTHER"];
    else if (homeHall === "2") order = ["2", "1", "3", "4", "OTHER"];
    else if (homeHall === "3") order = ["3", "1", "2", "4", "OTHER"];
    else if (homeHall === "4") order = ["4", "1", "2", "3", "OTHER"];

    return order
      .map(hallKey => ({
        unit: hallKey,
        closures: groups[hallKey],
        ...GROUP_DEFS[hallKey]
      }))
      .filter(g => g.closures.length > 0);
    // showActiveNow / showNext24h / showNext7d were read by the filter above and missing
    // from this list. Nothing has ever called their setters -- useMapLayerPreferences
    // returns them but no control is wired -- so the values never changed and the stale
    // grouping never showed. Latent, not live, and listed now so that wiring a timeframe
    // toggle is a UI change rather than a UI change plus a silent bug.
  }, [roadClosures, zones, homeHall, filterNoAccess, filterAccessOnly, filterCaution,
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
                                        <span className="opacity-75 font-mono">{group.closures.length}</span>
                                    </div>
                                    
                                    {/* Group Closures */}
                                    {!collapsedGroups[group.unit] && (
                                      <div className="flex flex-col gap-2 pl-1 border-l border-slate-800/40">
                                        {group.closures.map((closure, idx) => {
                                          const mapPoint = closureMapPoint(closure);
                                          const access = accessStyle(closure);
                                          return (
                                            <div 
                                              // rowId, not the feed's id, which is null when the feed sent none (#91)
                                              // and would collide.
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
                                                        {closure.street}
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
                                                 {/* Operator ruling 2026-09-16 (#91): a record with no feed id is kept and the
                                                     card says so. rowId is never shown in its place. */}
                                                 {closure.idMissing && (
                                                   <div className="text-[9px] font-mono font-bold text-amber-400 bg-amber-500/10 border border-amber-500/30 rounded px-1.5 py-1">
                                                     ⚠️ NO ID IN FEED RECORD
                                                   </div>
                                                 )}
                                                 
                                                 {/* Headline & Warning Type Pill */}
                                                 <div className="flex justify-between items-center text-[9px] font-mono font-bold text-slate-400">
                                                    <span className="truncate pr-1">{closure.headline}</span>
                                                    <span className={`text-[7px] px-1 py-0.2 rounded font-black tracking-wider flex-shrink-0 ${access.pill}`}>
                                                      {access.label}
                                                    </span>
                                                 </div>

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
                                    )}
                                </div>
                            ))
                        ) : (
                            <div className="text-center py-12 text-slate-650 text-xs italic">
                               No matching alerts found.
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
