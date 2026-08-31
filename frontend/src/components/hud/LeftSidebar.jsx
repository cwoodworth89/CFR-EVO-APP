// NOTE: For the live Coquitlam GIS offline warning status badge details, see docs/gis_endpoints.md
import React from 'react';
import { STATIONS_MAP as STATIONS, KNOWN_BUILDINGS } from '../MapConstants';
import { sanitizeAddress } from '../../utils/addressUtils';
import { API_BASE_URL } from '../../apiClient';
import ActiveDispatchPanel from './ActiveDispatchPanel';

export function LeftSidebar({ 
  leftSidebarOpen, 
  setLeftSidebarOpen, 
  appMode, 
  activeDispatch,
  setActiveDispatch,
  mapStyle,
  setMapStyle,
  // Explore layer toggles
  showZones, 
  setShowZones, 
  showHydrants, 
  setShowHydrants, 
  showRoadClosures, 
  setShowRoadClosures,
  showLabels,
  setShowLabels,
  showRailroadCrossings,
  setShowRailroadCrossings,
  showFireHalls,
  setShowFireHalls,
  homeHall,
  setHomeHall,
  targetAddress,
  setTargetAddress,
  nearestHydrants = [],
  routeMetrics,
  // Road access filter toggles
  // Road access filter toggles
  filterNoAccess,
  setFilterNoAccess,
  filterAccessOnly,
  setFilterAccessOnly,
  filterCaution,
  setFilterCaution,

}) {
  const isExplore = appMode === "EXPLORE";
  const [searchQuery, setSearchQuery] = React.useState("");
  const [showSuggestions, setShowSuggestions] = React.useState(false);
  const [activeIndex, setActiveIndex] = React.useState(-1);
  const [suggestions, setSuggestions] = React.useState([]);
  const [loading, setLoading] = React.useState(false);

  // Reset activeIndex whenever query changes or suggestions show status shifts
  React.useEffect(() => {
    setActiveIndex(-1);
  }, [searchQuery, showSuggestions]);

  // Debounced effect to fetch address suggestions from GIS server
  React.useEffect(() => {
    const query = searchQuery.trim();
    if (query.length < 3) {
      setSuggestions([]);
      return;
    }

    setLoading(true);
    const delayDebounce = setTimeout(() => {
      const url = `${API_BASE_URL}/api/parcels/search?q=${encodeURIComponent(query)}&limit=25`;

      fetch(url)
        .then(r => r.ok ? r.json() : null)
        .then(data => {
          if (data && data.results) {
            const userSearchedUnit = /\b(UNIT|APT|SUITE|STE|BAY|BLDG|#)\s*\w+/i.test(query) ||
              /^\d+[-/]\s*\d+/i.test(query) ||
              /\b(AVE|AVENUE|ST|STREET|RD|ROAD|WAY|DR|DRIVE|CRT|COURT|BLVD|BOULEVARD|CRES|CRESCENT|PL|PLACE|LANE|LN|HWY|HIGHWAY)\s+#?\s*\w+/i.test(query);

            const rawItems = data.results.map(f => {
              const address = f.address;
              const lat = f.lat || 0;
              const lng = f.lng || 0;
              const front_lat = f.front_lat || lat;
              const front_lng = f.front_lng || lng;
              return {
                address,
                lat,
                lng,
                front_lat,
                front_lng,
                zone_id: f.zone_id
              };
            });

            // Check known building matches
            const q = query.toUpperCase();
            const knownMatches = KNOWN_BUILDINGS.filter(b => 
              b.name.toUpperCase().includes(q) || 
              b.address.toUpperCase().includes(q) || 
              b.aliases.some(alias => alias.includes(q))
            ).map(b => ({
              address: b.address,
              buildingName: b.name,
              lat: b.frontEntrance ? b.frontEntrance[0] : b.lat,
              lng: b.frontEntrance ? b.frontEntrance[1] : b.lng,
              frontEntrance: b.frontEntrance,
              note: b.note
            }));

            // Deduplicate multi-unit addresses down to base building address unless user searched a specific unit
            const seen = new Set(knownMatches.map(m => m.address.toUpperCase()));
            const deduplicated = [...knownMatches];

            rawItems.forEach(item => {
              let cleanAddr = item.address;
              if (!userSearchedUnit) {
                cleanAddr = sanitizeAddress(item.address);
              }

              const key = cleanAddr.toUpperCase();
              if (!seen.has(key)) {
                seen.add(key);
                deduplicated.push({
                  ...item,
                  address: cleanAddr
                });
              }
            });

            setSuggestions(deduplicated.slice(0, 6));
          } else {
            setSuggestions([]);
          }
          setLoading(false);
        })
        .catch(err => {
          console.warn("Failed to fetch autocomplete addresses:", err);
          setSuggestions([]);
          setLoading(false);
        });
    }, 300);

    return () => clearTimeout(delayDebounce);
  }, [searchQuery]);

  // Unified select address handler
  const handleSelectAddress = React.useCallback((item) => {
    setTargetAddress(item);
    setSearchQuery("");
    setShowSuggestions(false);
    setActiveIndex(-1);
  }, [setTargetAddress]);

  // Keyboard navigation handler for autocomplete list
  const handleKeyDown = React.useCallback((e) => {
    if (!showSuggestions || suggestions.length === 0) return;
    
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex(prev => (prev + 1) % suggestions.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex(prev => (prev - 1 + suggestions.length) % suggestions.length);
    } else if (e.key === "Enter") {
      e.preventDefault();
      const idx = activeIndex === -1 ? 0 : activeIndex;
      if (idx >= 0 && idx < suggestions.length) {
        handleSelectAddress(suggestions[idx]);
      }
    } else if (e.key === "Escape") {
      e.preventDefault();
      setShowSuggestions(false);
      setActiveIndex(-1);
    }
  }, [showSuggestions, suggestions, activeIndex, handleSelectAddress]);

  const sidebarWidthClass = activeDispatch ? 'w-[400px]' : 'w-80';

  return (
    <div className={`relative h-full flex flex-row transition-all duration-300 ease-in-out z-[1000] min-w-0 flex-shrink-0 ${leftSidebarOpen ? `${sidebarWidthClass} border-r border-slate-800` : 'w-0'}`}>
       {/* Sidebar Body Wrapper (animates width and uses overflow-hidden to prevent contents sticking out when collapsed) */}
       <div className={`h-full bg-slate-900 flex flex-col transition-all duration-300 ease-in-out overflow-hidden ${leftSidebarOpen ? sidebarWidthClass : 'w-0'}`}>
          {activeDispatch ? (
             <ActiveDispatchPanel 
               activeDispatch={activeDispatch} 
               setActiveDispatch={setActiveDispatch} 
               nearestHydrants={nearestHydrants}
               setTargetAddress={setTargetAddress}
             />
          ) : (
             /* Fixed width inner container to prevent squishing during collapse */
             <div className="w-80 h-full flex flex-col overflow-y-auto overflow-x-hidden">
                {/* Header Title */}
                <div className="bg-slate-950 p-4 border-b border-slate-800 text-center flex-shrink-0">
                   <div className="text-slate-500 text-[10px] uppercase font-mono tracking-widest mb-1">CFR EVO SYSTEM</div>
                   <div className="text-lg text-emerald-500 font-extrabold uppercase font-sans tracking-wide">{isExplore ? "MAP CONTROLS" : "ACTIVE SESSION"}</div>
                </div>

             {/* Controls / Information Area */}
             <div className="p-5 flex-grow flex flex-col gap-6 overflow-y-auto">
                     {/* Basemap View Switcher */}
                     <div className="flex flex-col gap-2 bg-slate-950 p-3 border border-slate-800 rounded-xl flex-shrink-0">
                        <div className="text-[10px] text-slate-500 font-black uppercase tracking-wider font-mono border-b border-slate-850 pb-1.5 flex justify-between items-center">
                           <span>BASEMAP VIEW</span>
                           <span className="text-[8px] text-slate-400 font-mono">EXPLORE</span>
                        </div>
                        <div className="grid grid-cols-2 gap-1.5 bg-slate-900/90 p-1 rounded-lg border border-slate-800">
                           <button
                              type="button"
                              onClick={() => setMapStyle && setMapStyle("GREY")}
                              className={`py-1.5 px-2 rounded-md text-xs font-bold transition-all flex items-center justify-center gap-1.5 cursor-pointer ${
                                 mapStyle !== "SATELLITE"
                                    ? "bg-slate-800 text-sky-400 shadow-sm border border-slate-700 font-black"
                                    : "text-slate-400 hover:text-slate-200 hover:bg-slate-850 border border-transparent"
                              }`}
                           >
                              <span>🗺️</span>
                              <span>Street Map</span>
                           </button>
                           <button
                              type="button"
                              onClick={() => setMapStyle && setMapStyle("SATELLITE")}
                              className={`py-1.5 px-2 rounded-md text-xs font-bold transition-all flex items-center justify-center gap-1.5 cursor-pointer ${
                                 mapStyle === "SATELLITE"
                                    ? "bg-emerald-950/80 text-emerald-300 shadow-sm border border-emerald-700/80 font-black"
                                    : "text-slate-400 hover:text-slate-200 hover:bg-slate-850 border border-transparent"
                              }`}
                           >
                              <span>🛰️</span>
                              <span>Aerial 7.5cm</span>
                           </button>
                        </div>
                     </div>

                     {/* Search & Routing Section */}
                     <div className="flex flex-col gap-3 bg-slate-950 p-4 border border-slate-800 rounded-xl flex-shrink-0">
                        <div className="text-[10px] text-slate-500 font-black uppercase tracking-wider font-mono border-b border-slate-850 pb-1.5">NAVIGATION SEARCH</div>
                        
                        {/* 1. Home Hall Selector */}
                        <div className="flex flex-col gap-1.5 mt-1">
                           <label className="text-[9px] text-slate-400 font-extrabold uppercase font-mono">Home Station (Origin)</label>
                           <select 
                              value={homeHall}
                              onChange={(e) => setHomeHall(e.target.value)}
                              className="bg-slate-900 border border-slate-700 hover:border-slate-650 text-white rounded-lg px-2.5 py-1.5 text-xs font-bold focus:outline-none focus:border-sky-500 cursor-pointer shadow-sm w-full"
                           >
                              <option value="1">Town Centre Fire Hall (TCFH)</option>
                              <option value="2">Mariner Fire Hall</option>
                              <option value="3">Austin Heights Fire Hall</option>
                              <option value="4">Burke Mountain Fire Hall</option>
                           </select>
                        </div>

                        {/* 2. Address Search Input */}
                        <div className="flex flex-col gap-1.5 mt-2 relative">
                           <label className="text-[9px] text-slate-400 font-extrabold uppercase font-mono">Target Address / Block</label>
                           <div className="relative">
                              <input 
                                 type="text"
                                 placeholder="Search address (e.g. 4150 Cedar...)"
                                 value={searchQuery}
                                 onChange={(e) => {
                                    setSearchQuery(e.target.value);
                                    setShowSuggestions(true);
                                 }}
                                 onFocus={() => setShowSuggestions(true)}
                                 onKeyDown={handleKeyDown}
                                 className="w-full bg-slate-900 border border-slate-700 hover:border-slate-650 text-white rounded-lg pl-3 pr-8 py-1.5 text-xs focus:outline-none focus:border-sky-500 placeholder-slate-500"
                              />
                              {loading && (
                                 <span className="absolute right-8 top-1/2 -translate-y-1/2 flex h-2 w-2">
                                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-sky-400 opacity-75"></span>
                                    <span className="relative inline-flex rounded-full h-2 w-2 bg-sky-500"></span>
                                 </span>
                              )}
                              {searchQuery && (
                                 <button 
                                    onClick={() => { setSearchQuery(""); setShowSuggestions(false); }}
                                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-500 hover:text-white text-xs font-bold cursor-pointer"
                                 >
                                    ✕
                                 </button>
                              )}
                           </div>

                           {/* Autocomplete Suggestions Dropdown */}
                           {showSuggestions && suggestions.length > 0 && (
                              <>
                                 <div className="fixed inset-0 z-[1010]" onClick={() => setShowSuggestions(false)} />
                                 <div className="absolute left-0 right-0 top-full mt-1.5 bg-slate-900 border border-slate-800 rounded-xl shadow-2xl z-[1020] overflow-hidden select-none max-h-48 overflow-y-auto">
                                    {suggestions.map((item, idx) => (
                                       <div 
                                          key={idx}
                                          onClick={() => handleSelectAddress(item)}
                                          className={`p-2.5 text-xs border-b border-slate-850/50 last:border-0 font-medium transition-all cursor-pointer ${
                                             idx === activeIndex 
                                               ? "bg-slate-800 text-white" 
                                               : "text-slate-350 hover:text-white hover:bg-slate-800"
                                          }`}
                                       >
                                          📍 {item.address}
                                       </div>
                                    ))}
                                 </div>
                              </>
                           )}
                        </div>

                        {/* Active Target Banner / Reset Button & Nearest Hydrant Details */}
                        {targetAddress && (
                           <div className="flex flex-col gap-2.5 bg-slate-950 p-3 border border-slate-800 rounded-lg mt-2 animate-in fade-in duration-200">
                              <div className="flex justify-between items-center">
                                 <span className="text-[8px] text-emerald-400 font-extrabold uppercase tracking-wider font-mono">Routing Active</span>
                                 <button 
                                    onClick={() => setTargetAddress(null)}
                                    className="px-2 py-0.5 bg-slate-800 hover:bg-slate-700 text-rose-400 hover:text-rose-300 rounded text-[8px] font-black tracking-wider transition-all cursor-pointer border border-slate-750"
                                 >
                                    CLEAR
                                 </button>
                              </div>
                              <div className="text-xs text-white font-bold leading-tight truncate">{targetAddress.address}</div>
                              
                              {/* GPS Navigation Button */}
                              {STATIONS[homeHall] && (
                                 <a 
                                    href={`https://www.google.com/maps/dir/?api=1&origin=${STATIONS[homeHall][0]},${STATIONS[homeHall][1]}&destination=${targetAddress.lat},${targetAddress.lng}&travelmode=driving`}
                                    target="_blank" 
                                    rel="noopener noreferrer"
                                    className="bg-indigo-600 hover:bg-indigo-700 text-white font-extrabold py-1.5 px-3 rounded-md text-[10px] flex items-center justify-center gap-1.5 transition-all text-center w-full shadow-md border border-indigo-500"
                                 >
                                    🚙 NAVIGATE (GPS)
                                 </a>
                              )}
                              {/* Multi-Unit Response ETAs & Rail Warning */}
                               <div className="border-t border-slate-900 pt-2.5 flex flex-col gap-2">
                                  <div className="flex justify-between items-center">
                                     <span className="text-[8.5px] text-emerald-400 font-extrabold uppercase tracking-wider font-mono flex items-center gap-1">
                                        🚒 Dispatched Unit ETAs
                                     </span>
                                     <span className="text-[8px] text-slate-400 font-mono">OSRM</span>
                                  </div>

                                  {/* Unit List */}
                                  <div className="flex flex-col gap-1.5">
                                     {routeMetrics?.units?.map((u, idx) => (
                                        <div key={idx} className="flex justify-between items-center bg-slate-900/80 px-2.5 py-1.5 rounded-lg border border-slate-800 font-mono text-xs">
                                           <div className="flex items-center gap-2">
                                              <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: u.color }} />
                                              <span className="text-white font-black">{u.unit}</span>
                                              <span className="text-[7.5px] text-slate-400 uppercase font-bold">{u.tierKey}</span>
                                           </div>
                                           <div className="flex items-center gap-2">
                                              <span className="text-slate-400 text-[10px]">{u.distanceKm != null ? `${u.distanceKm} km` : '-- km'}</span>
                                              <span className="text-emerald-400 font-black">{u.etaMinutes != null ? `${u.etaMinutes} min` : '-- min'}</span>
                                           </div>
                                        </div>
                                     ))}
                                  </div>
                               </div>
                           </div>
                        )}
                     </div>

                    {/* 2. Map Overlays / Layers */}
                    <div className="flex flex-col gap-2">
                       <h3 className="text-[10px] text-slate-500 font-black uppercase tracking-wider font-mono border-b border-slate-850 pb-1.5">MAP LAYERS</h3>
                       <div className="flex flex-col gap-2.5 mt-1.5">
                          {/* 🚒 FIRE HALLS OVERLAY */}
                          <label className="flex items-center gap-2.5 text-xs text-slate-300 cursor-pointer">
                             <input 
                                type="checkbox" 
                                checked={showFireHalls !== false} 
                                onChange={(e) => setShowFireHalls && setShowFireHalls(e.target.checked)} 
                                className="rounded border-slate-800 bg-slate-950 text-red-500 focus:ring-0 focus:ring-offset-0 w-4 h-4 cursor-pointer" 
                             />
                             <span className="flex items-center gap-1.5 font-semibold">🚒 Fire Halls</span>
                          </label>

                          <label className="flex items-center gap-2.5 text-xs text-slate-300 cursor-pointer">
                             <input 
                                type="checkbox" 
                                checked={showRoadClosures} 
                                onChange={(e) => setShowRoadClosures(e.target.checked)} 
                                className="rounded border-slate-800 bg-slate-950 text-rose-500 focus:ring-0 focus:ring-offset-0 w-4 h-4 cursor-pointer" 
                             />
                             <span className="flex items-center gap-1.5 font-semibold">🚧 Road Closures</span>
                          </label>
                          <label className="flex items-center gap-2.5 text-xs text-slate-300 cursor-pointer">
                             <input 
                                type="checkbox" 
                                checked={showHydrants} 
                                onChange={(e) => setShowHydrants(e.target.checked)} 
                                className="rounded border-slate-800 bg-slate-950 text-emerald-500 focus:ring-0 focus:ring-offset-0 w-4 h-4 cursor-pointer" 
                             />
                             <span className="flex items-center gap-1.5 font-semibold">💧 Fire Hydrants</span>
                          </label>
                          <label className="flex items-center gap-2.5 text-xs text-slate-300 cursor-pointer">
                             <input 
                                type="checkbox" 
                                checked={showLabels} 
                                onChange={(e) => setShowLabels(e.target.checked)} 
                                className="rounded border-slate-800 bg-slate-950 text-amber-500 focus:ring-0 focus:ring-offset-0 w-4 h-4 cursor-pointer" 
                             />
                             <span className="flex items-center gap-1.5 font-semibold">🏷️ Road Names & Addresses</span>
                          </label>
                          <label className="flex items-center gap-2.5 text-xs text-slate-300 cursor-pointer">
                             <input 
                                type="checkbox" 
                                checked={showZones} 
                                onChange={(e) => setShowZones(e.target.checked)} 
                                className="rounded border-slate-800 bg-slate-950 text-sky-500 focus:ring-0 focus:ring-offset-0 w-4 h-4 cursor-pointer" 
                             />
                             <span className="flex items-center gap-1.5 font-semibold">📐 Emergency Zones</span>
                          </label>
                          
                          {/* 🛤️ RAILROAD CROSSINGS OVERLAY */}
                          <label className="flex items-center gap-2.5 text-xs text-slate-300 cursor-pointer">
                             <input 
                                type="checkbox" 
                                checked={showRailroadCrossings} 
                                onChange={(e) => setShowRailroadCrossings && setShowRailroadCrossings(e.target.checked)} 
                                className="rounded border-slate-800 bg-slate-950 text-amber-500 focus:ring-0 focus:ring-offset-0 w-4 h-4 cursor-pointer" 
                             />
                             <span className="flex items-center gap-1.5 font-semibold">🛤️ Railroad Crossings</span>
                          </label>
                       </div>
                    </div>

                    {/* 3. Road Hazards, Access Level & Closure Timeframe */}
                    <div className={`flex flex-col gap-2 transition-all duration-300 ${!showRoadClosures && 'opacity-35 pointer-events-none'}`}>
                       <h3 className="text-[10px] text-slate-500 font-black uppercase tracking-wider font-mono border-b border-slate-850 pb-1.5">ROAD HAZARDS & CLOSURES</h3>
                       <div className="flex flex-col gap-2 mt-1.5">
                          <div className="flex flex-col gap-1.5">
                             <span className="text-[9px] text-slate-400 font-mono font-bold uppercase tracking-wider">Access Severity</span>
                             <label className="flex items-center gap-2.5 text-xs text-slate-350 cursor-pointer">
                                <input 
                                   type="checkbox" 
                                   checked={filterNoAccess || filterAccessOnly} 
                                   onChange={(e) => {
                                      setFilterNoAccess(e.target.checked);
                                      setFilterAccessOnly(e.target.checked);
                                   }} 
                                   className="rounded border-slate-850 bg-slate-950 text-red-500 focus:ring-0 focus:ring-offset-0 w-4 h-4 cursor-pointer" 
                                />
                                <span className="flex items-center gap-2 font-medium">
                                   <span className="w-2.5 h-2.5 rounded-full bg-red-500 inline-block shadow-sm"></span>
                                   <span>Full Road Closures</span>
                                </span>
                             </label>
                             <label className="flex items-center gap-2.5 text-xs text-slate-350 cursor-pointer">
                                <input 
                                   type="checkbox" 
                                   checked={filterCaution} 
                                   onChange={(e) => setFilterCaution(e.target.checked)} 
                                   className="rounded border-slate-850 bg-slate-950 text-yellow-500 focus:ring-0 focus:ring-offset-0 w-4 h-4 cursor-pointer" 
                                />
                                <span className="flex items-center gap-2 font-medium">
                                   <span className="w-2.5 h-2.5 rounded-full bg-yellow-500 inline-block shadow-sm"></span>
                                   <span>Lane Restrictions & Construction</span>
                                </span>
                             </label>
                           </div>
                        </div>
                     </div>
                  </div>
               </div>
           )}
        </div>


       {/* Floating Toggle Tab */}
       <button 
         onClick={() => setLeftSidebarOpen(!leftSidebarOpen)}
         className="absolute top-1/2 -translate-y-1/2 -right-6 z-[1010] bg-slate-900 hover:bg-slate-800 text-slate-400 hover:text-white rounded-r-lg w-6 h-16 flex items-center justify-center shadow-2xl border border-l-0 border-slate-800 cursor-pointer select-none transition-all duration-300"
         title={leftSidebarOpen ? "Collapse Control Panel" : "Expand Control Panel"}
       >
         <span className="text-[10px] font-black">{leftSidebarOpen ? "◀" : "▶"}</span>
       </button>
    </div>
  );
}
