import React from 'react';

export function RightSidebar({ 
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
  homeHall = "1"
}) {
  const [collapsedGroups, setCollapsedGroups] = React.useState({});

  const toggleGroup = (groupId) => {
    setCollapsedGroups(prev => ({
      ...prev,
      [groupId]: !prev[groupId]
    }));
  };

  const groupDefs = {
    "1": { label: "Town Centre (Hall 1)", color: "border-rose-500/80 text-rose-400 bg-rose-950/40" },
    "2": { label: "Mariner (Hall 2)", color: "border-blue-500/80 text-blue-400 bg-blue-950/40" },
    "3": { label: "Austin Heights (Hall 3)", color: "border-emerald-500/80 text-emerald-400 bg-emerald-950/40" },
    "4": { label: "Burke Mountain (Hall 4)", color: "border-purple-500/80 text-purple-400 bg-purple-950/40" },
    "OTHER": { label: "Regional Corridors / Other", color: "border-slate-600 text-slate-400 bg-slate-800/30" }
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
        if (closure.emergencyAccess === "NO_ACCESS" && !filterNoAccess) return false;
        if (closure.emergencyAccess === "ACCESS_ONLY" && !filterAccessOnly) return false;
        if (closure.emergencyAccess === "CAUTION" && !filterCaution) return false;

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
        ...groupDefs[hallKey]
      }))
      .filter(g => g.closures.length > 0);
  }, [roadClosures, zones, homeHall, filterNoAccess, filterAccessOnly, filterCaution]);

  const isExplore = appMode === "EXPLORE";
  if (!isExplore) return null; // Only render right sidebar alerts in Explore/Information Mode

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

  return (
    <div className={`relative h-full flex flex-row-reverse transition-all duration-300 ease-in-out z-[1000] min-w-0 flex-shrink-0 ${rightSidebarOpen ? 'w-80 border-l border-slate-800' : 'w-0'}`}>
       {/* Sidebar Body Wrapper (animates width and uses overflow-hidden to prevent contents sticking out when collapsed) */}
       <div className={`h-full bg-slate-900 flex flex-col transition-all duration-300 ease-in-out overflow-hidden ${rightSidebarOpen ? 'w-80' : 'w-0'}`}>
          <div className="w-80 h-full flex flex-col overflow-hidden">
             {/* Header Title */}
             <div className="bg-slate-950 p-4 border-b border-slate-800 text-center flex-shrink-0">
                <div className="text-slate-500 text-[10px] uppercase font-mono tracking-widest mb-1">CFR DISPATCH</div>
                <div className="text-lg text-rose-500 font-extrabold uppercase font-sans tracking-wide">ROAD CLOSURES</div>
             </div>

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
                                        {group.closures.map((closure) => (
                                            <div 
                                              key={closure.id} 
                                              onClick={() => {
                                                if (map) {
                                                  map.flyTo(closure.coordinates, 16, { animate: true });
                                                }
                                                if (onSelectClosure) {
                                                  onSelectClosure(closure);
                                                }
                                              }}
                                              className="bg-slate-950 hover:bg-slate-900 border border-slate-850 hover:border-slate-750 text-left p-2.5 rounded-xl shadow-sm cursor-pointer transition-all flex flex-col gap-1.5 group relative overflow-hidden flex-shrink-0"
                                            >
                                                 {/* Street Name (Prominent & Color-coded) & Source */}
                                                 <div className="flex justify-between items-center gap-1.5">
                                                     <span className={`text-xs font-black uppercase tracking-wide truncate ${
                                                       closure.emergencyAccess === 'NO_ACCESS' ? 'text-red-500' :
                                                       closure.emergencyAccess === 'ACCESS_ONLY' ? 'text-amber-500' :
                                                       'text-yellow-500'
                                                     }`}>
                                                        {closure.street}
                                                     </span>
                                                     <span className="text-[8px] text-slate-500 font-mono font-medium flex-shrink-0">{closure.source}</span>
                                                 </div>
                                                 
                                                 {/* Headline & Warning Type Pill */}
                                                 <div className="flex justify-between items-center text-[9px] font-mono font-bold text-slate-400">
                                                    <span className="truncate pr-1">{closure.headline}</span>
                                                    <span className={`text-[7px] px-1 py-0.2 rounded font-black tracking-wider flex-shrink-0 ${
                                                      closure.emergencyAccess === 'NO_ACCESS' ? 'bg-red-500/10 text-red-400 border border-red-500/20' :
                                                      closure.emergencyAccess === 'ACCESS_ONLY' ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20' :
                                                      'bg-yellow-500/10 text-yellow-400 border border-yellow-500/20'
                                                    }`}>
                                                      {closure.emergencyAccess === 'NO_ACCESS' ? 'FULL CLOSURE' :
                                                       closure.emergencyAccess === 'ACCESS_ONLY' ? 'EMERGENCY ACCESS ONLY' :
                                                       'LANE CLOSURE'}
                                                    </span>
                                                 </div>

                                                 {/* Date Range & Status Pill */}
                                                 <div className="flex justify-between items-center text-[9px] font-mono border-t border-slate-900/50 pt-1.5 mt-0.5">
                                                    <span className="text-slate-400 flex items-center gap-1">
                                                      📅 {formatDateRange(closure.start, closure.end)}
                                                    </span>
                                                    {closure.isActive ? (
                                                      <span className="bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-1.5 py-0.2 rounded text-[7px] font-black tracking-wider flex items-center gap-1">
                                                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse inline-block"></span>
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
                                        ))}
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
         className="absolute top-1/2 -translate-y-1/2 -left-6 z-[1010] bg-slate-900 hover:bg-slate-800 text-slate-400 hover:text-white rounded-l-lg w-6 h-16 flex items-center justify-center shadow-2xl border border-r-0 border-slate-800 cursor-pointer select-none transition-all duration-300"
         title={rightSidebarOpen ? "Collapse Alerts" : "Expand Alerts"}
       >
         <span className="text-[10px] font-black">{rightSidebarOpen ? "▶" : "◀"}</span>
       </button>
    </div>
  );
}
