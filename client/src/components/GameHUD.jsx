import React from 'react';
import { UNIT_COLORS, STATIONS_MAP as STATIONS } from './MapConstants';


export function Header({ 
  appMode, 
  setAppMode, 
  mapStyle, 
  setMapStyle, 
  showLabels, 
  setShowLabels,
  leftSidebarOpen,
  setLeftSidebarOpen,
  rightSidebarOpen,
  setRightSidebarOpen,
  alertsCount
}) {
  const [showLayersMenu, setShowLayersMenu] = React.useState(false);
  const isExplore = appMode === "EXPLORE";

  return (
    <div className="bg-slate-950 text-white p-3 shadow-md z-[1100] flex justify-between items-center border-b border-slate-800 h-16 relative select-none">
        {/* Left Side: Brand Logo and Sidebar Toggles */}
        <div className="flex items-center gap-4">
          <button 
            onClick={() => setLeftSidebarOpen(!leftSidebarOpen)}
            className={`p-2 rounded-lg border text-xs font-bold transition-all ${
              leftSidebarOpen 
                ? "bg-slate-800 border-slate-700 text-sky-400" 
                : "bg-slate-900 border-slate-800 text-slate-400 hover:text-white"
            }`}
            title="Toggle Left Control Panel"
          >
            📋 CONTROL PANEL
          </button>
          
          <h1 className="text-lg font-bold tracking-wider flex items-center gap-1.5 select-none">
            CFR <span className="text-emerald-500 font-extrabold">EVO</span>
            <span className="text-slate-500 font-normal text-[10px] uppercase tracking-widest ml-1.5 border-l border-slate-800 pl-2">APP</span>
          </h1>
        </div>

        {/* Center: Mode Select Dropdown */}
        <div className="flex items-center">
          <div className="relative">
            <select 
              value={isExplore ? "EXPLORE" : appMode} 
              onChange={(e) => setAppMode(e.target.value)}
              className="bg-slate-900 border border-slate-700 hover:border-slate-650 text-white rounded-lg pl-3 pr-8 py-1.5 text-xs font-bold focus:outline-none focus:border-sky-500 cursor-pointer shadow-sm appearance-none min-w-[220px]"
              style={{ 
                backgroundImage: `url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='24' height='24' fill='none' stroke='%2394a3b8' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><polyline points='6 9 12 15 18 9'></polyline></svg>")`, 
                backgroundPosition: 'right 8px center', 
                backgroundRepeat: 'no-repeat', 
                backgroundSize: '14px' 
              }}
            >
              <option value="EXPLORE">🧭 EXPLORE / DRIVERS AID</option>
              <option value="TRAINING_ZONES">🎓 TRAINING: EMERGENCY ZONES</option>
              <option value="TRAINING_INTERSECTIONS">🎓 TRAINING: STREET INTERSECTIONS</option>
              <option value="TRAINING_BLOCKS">🎓 TRAINING: BLOCK RANGES</option>
              <option value="TRAINING_ADDRESSES">🎓 TRAINING: PARCEL ADDRESSES</option>
              <option value="ADMIN_DISPATCHES">🛡️ ADMIN: DISPATCH REVIEW</option>
            </select>
          </div>
        </div>

        {/* Right Side: Options & Alerts Panel Trigger */}
        <div className="flex gap-3 items-center">
          {/* Map Options Button */}
          <div className="relative">
             <button 
                onClick={() => setShowLayersMenu(!showLayersMenu)}
                className={`px-3 py-1.5 text-xs font-bold rounded-lg border transition-all flex items-center gap-1.5 ${
                  showLayersMenu 
                    ? "bg-slate-800 text-white border-slate-600 shadow-md animate-pulse" 
                    : "bg-slate-900 text-slate-300 border-slate-800 hover:border-slate-700 hover:text-white"
                }`}
             >
                ⚙️ MAP OPTIONS
             </button>
             
             {showLayersMenu && (
                <>
                  <div className="fixed inset-0 z-[1050]" onClick={() => setShowLayersMenu(false)} />
                  <div className="absolute right-0 mt-2 w-48 bg-slate-900 border border-slate-800 rounded-xl p-3 shadow-2xl z-[1200] flex flex-col gap-3 animate-in fade-in slide-in-from-top-2 duration-155 select-none">
                     <div>
                       <div className="text-[8px] text-slate-500 font-extrabold uppercase tracking-wider mb-1 font-mono">Basemap Style</div>
                       <div className="flex bg-slate-950 rounded-lg p-0.5 border border-slate-855">
                         {['GREY', 'DARK'].map(style => (
                             <button 
                               key={style} 
                               onClick={() => { setMapStyle(style); setShowLayersMenu(false); }} 
                               className={`flex-1 py-1 text-[9px] font-black rounded transition-all ${
                                 mapStyle === style 
                                   ? "bg-slate-800 text-white shadow" 
                                   : "text-slate-500 hover:text-slate-300"
                               }`}
                             >
                               {style}
                             </button>
                         ))}
                       </div>
                     </div>
                     
                     <div className="border-t border-slate-850 pt-2">
                       <div className="flex justify-between items-center">
                          <span className="text-[9px] text-slate-400 font-extrabold uppercase tracking-wider font-mono">Street Labels</span>
                          <button 
                             onClick={() => { setShowLabels(!showLabels); setShowLayersMenu(false); }}
                             className={`px-2 py-0.5 rounded text-[8px] font-black border transition-all ${
                               showLabels 
                                 ? "bg-amber-500 text-black border-amber-600 shadow-sm" 
                                 : "bg-slate-950 text-slate-500 border-slate-850 hover:border-slate-700 hover:text-slate-400"
                             }`}
                          >
                             {showLabels ? "ON" : "OFF"}
                          </button>
                       </div>
                     </div>
                  </div>
                </>
             )}
          </div>

          {/* Right Sidebar Alerts Panel Toggle */}
          <button 
            onClick={() => setRightSidebarOpen(!rightSidebarOpen)}
            className={`px-3 py-1.5 text-xs font-bold rounded-lg border transition-all flex items-center gap-1.5 ${
              rightSidebarOpen 
                ? "bg-slate-800 border-slate-700 text-rose-400" 
                : "bg-slate-900 border-slate-800 text-slate-400 hover:text-white"
            }`}
            title="Toggle Alerts List"
          >
            🔔 ALERTS {alertsCount > 0 && <span className="bg-rose-500 text-white text-[9px] font-black px-1.5 py-0.2 rounded-full ml-1">{alertsCount}</span>}
          </button>
        </div>
    </div>
  );
}



export function LeftSidebar({ 
  leftSidebarOpen, 
  setLeftSidebarOpen, 
  appMode, 
  loadingTraining,
  // Explore layer toggles
  showZones, 
  setShowZones, 
  showHydrants, 
  setShowHydrants, 
  showRoadClosures, 
  setShowRoadClosures,
  showLabels,
  setShowLabels,
  homeHall,
  setHomeHall,
  targetAddress,
  setTargetAddress,
  nearestHydrant,
  // Road access filter toggles
  filterNoAccess,
  setFilterNoAccess,
  filterAccessOnly,
  setFilterAccessOnly,
  filterCaution,
  setFilterCaution,
  // Training HUD
  score,
  currentQuestion,
  feedback,
  distanceOff,
  clickedBlockData,
  onNext,
  onZoneGuess,
  map
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
      const upperQuery = query.toUpperCase().replace(/'/g, "''");
      const encodedWhere = encodeURIComponent(`UPPER(ADDRESS) LIKE '%${upperQuery}%'`);
      const url = `https://geodata.coquitlam.ca/arcgis/rest/services/DynamicServices/Cadastral/MapServer/15/query?where=${encodedWhere}&outFields=ADDRESS&returnGeometry=true&outSR=4326&resultRecordCount=5&f=json`;

      fetch(url)
        .then(r => r.ok ? r.json() : null)
        .then(data => {
          if (data && data.features) {
            const items = data.features.map(f => {
              const address = f.attributes.ADDRESS;
              const geom = f.geometry;
              let lat = 0;
              let lng = 0;
              let rings = null;
              if (geom && geom.rings && geom.rings.length > 0) {
                rings = geom.rings;
                // Calculate center (centroid) of the first ring
                const ring = geom.rings[0];
                let latSum = 0;
                let lngSum = 0;
                ring.forEach(pt => {
                  lngSum += pt[0];
                  latSum += pt[1];
                });
                lat = latSum / ring.length;
                lng = lngSum / ring.length;
              }
              return {
                address,
                lat,
                lng,
                rings
              };
            });
            setSuggestions(items);
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

  return (
    <div className={`relative h-full flex flex-row transition-all duration-300 ease-in-out z-[1000] min-w-0 flex-shrink-0 ${leftSidebarOpen ? 'w-80 border-r border-slate-800' : 'w-0'}`}>
       {/* Sidebar Body Wrapper (animates width and uses overflow-hidden to prevent contents sticking out when collapsed) */}
       <div className={`h-full bg-slate-900 flex flex-col transition-all duration-300 ease-in-out overflow-hidden ${leftSidebarOpen ? 'w-80' : 'w-0'}`}>
          {/* Fixed width inner container to prevent squishing during collapse */}
          <div className="w-80 h-full flex flex-col overflow-y-auto overflow-x-hidden">
             {/* Header Title */}
             <div className="bg-slate-950 p-4 border-b border-slate-800 text-center flex-shrink-0">
                {isExplore ? (
                   <>
                     <div className="text-slate-500 text-[10px] uppercase font-mono tracking-widest mb-1">CFR EVO SYSTEM</div>
                     <div className="text-lg text-emerald-500 font-extrabold uppercase font-sans tracking-wide">MAP CONTROLS</div>
                   </>
                ) : (
                   <>
                     <div className="text-slate-500 text-[10px] uppercase font-mono tracking-widest mb-1">CFR EVO TRAINING</div>
                     <div className="text-lg text-sky-400 font-extrabold uppercase font-sans tracking-wide">ACTIVE SESSION</div>
                   </>
                )}
             </div>

             {/* Controls / Information Area */}
             <div className="p-5 flex-grow flex flex-col gap-6 overflow-y-auto">
                {isExplore ? (
                  <>
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
                                    className="bg-indigo-650 hover:bg-indigo-600 text-white font-extrabold py-1.5 px-3 rounded-md text-[10px] flex items-center justify-center gap-1.5 transition-all text-center w-full shadow-md border border-indigo-500"
                                 >
                                    🚙 NAVIGATE (GPS)
                                 </a>
                              )}
                              
                              {/* Nearest Hydrant Info */}
                              {nearestHydrant && (
                                 <div className="border-t border-slate-900 pt-2 flex flex-col gap-1.5">
                                    <div className="text-[8px] text-sky-400 font-extrabold uppercase tracking-wider font-mono flex items-center gap-1">
                                       <span>💧 Nearest Hydrant</span>
                                    </div>
                                    <div className="grid grid-cols-3 gap-1 bg-slate-900/60 p-1.5 rounded border border-slate-850 text-center">
                                       <div>
                                          <div className="text-[7px] text-slate-500 font-extrabold uppercase tracking-wider">ID</div>
                                          <div className="text-[10px] text-white font-bold font-mono">{nearestHydrant.gisId}</div>
                                       </div>
                                       <div>
                                          <div className="text-[7px] text-slate-500 font-extrabold uppercase tracking-wider">Distance</div>
                                          <div className="text-[10px] text-emerald-400 font-bold font-mono">{nearestHydrant.distance}m</div>
                                       </div>
                                       <div>
                                          <div className="text-[7px] text-slate-500 font-extrabold uppercase tracking-wider">Class</div>
                                          <div className="text-[10px] text-sky-400 font-bold font-mono">{nearestHydrant.flowClass || "N/A"}</div>
                                       </div>
                                    </div>
                                 </div>
                              )}
                           </div>
                        )}
                     </div>
                    {/* 1. Time Filters */}
                    <div className="flex flex-col gap-2">
                       <h3 className="text-[10px] text-slate-500 font-black uppercase tracking-wider font-mono border-b border-slate-850 pb-1.5">TIME FILTERS</h3>
                       <div className="flex flex-col gap-2.5 mt-1.5">
                          <label className="flex items-center gap-2.5 text-xs text-slate-350 cursor-pointer">
                             <input type="checkbox" checked readOnly className="rounded border-slate-800 bg-slate-950 text-emerald-500 focus:ring-0 focus:ring-offset-0 w-4 h-4 cursor-pointer" />
                             <span>Now / Active Alerts</span>
                          </label>
                          <label className="flex items-center gap-2.5 text-xs text-slate-500 cursor-not-allowed">
                             <input type="checkbox" disabled className="rounded border-slate-900 bg-slate-950 text-slate-700 w-4 h-4" />
                             <span>Next 7 Days (Planned)</span>
                          </label>
                          <label className="flex items-center gap-2.5 text-xs text-slate-500 cursor-not-allowed">
                             <input type="checkbox" disabled className="rounded border-slate-900 bg-slate-950 text-slate-700 w-4 h-4" />
                             <span>Next 30 Days (Future)</span>
                          </label>
                       </div>
                    </div>

                    {/* 2. Map Overlays / Layers */}
                    <div className="flex flex-col gap-2">
                       <h3 className="text-[10px] text-slate-500 font-black uppercase tracking-wider font-mono border-b border-slate-850 pb-1.5">MAP LAYERS</h3>
                       <div className="flex flex-col gap-2.5 mt-1.5">
                          <label className="flex items-center gap-2.5 text-xs text-slate-300 cursor-pointer">
                             <input 
                                type="checkbox" 
                                checked={showRoadClosures} 
                                onChange={(e) => setShowRoadClosures(e.target.checked)} 
                                className="rounded border-slate-800 bg-slate-950 text-rose-500 focus:ring-0 focus:ring-offset-0 w-4 h-4 cursor-pointer" 
                             />
                             <span className="flex items-center gap-1.5">🚧 Road Closures</span>
                          </label>
                          <label className="flex items-center gap-2.5 text-xs text-slate-300 cursor-pointer">
                             <input 
                                type="checkbox" 
                                checked={showHydrants} 
                                onChange={(e) => setShowHydrants(e.target.checked)} 
                                className="rounded border-slate-800 bg-slate-950 text-emerald-500 focus:ring-0 focus:ring-offset-0 w-4 h-4 cursor-pointer" 
                             />
                             <span className="flex items-center gap-1.5">💧 Fire Hydrants</span>
                          </label>
                          <label className="flex items-center gap-2.5 text-xs text-slate-300 cursor-pointer">
                             <input 
                                type="checkbox" 
                                checked={showLabels} 
                                onChange={(e) => setShowLabels(e.target.checked)} 
                                className="rounded border-slate-800 bg-slate-950 text-amber-500 focus:ring-0 focus:ring-offset-0 w-4 h-4 cursor-pointer" 
                             />
                             <span className="flex items-center gap-1.5">🏷️ Road Names & Addresses</span>
                          </label>
                          <label className="flex items-center gap-2.5 text-xs text-slate-300 cursor-pointer">
                             <input 
                                type="checkbox" 
                                checked={showZones} 
                                onChange={(e) => setShowZones(e.target.checked)} 
                                className="rounded border-slate-800 bg-slate-950 text-sky-500 focus:ring-0 focus:ring-offset-0 w-4 h-4 cursor-pointer" 
                             />
                             <span className="flex items-center gap-1.5">📐 Emergency Zones</span>
                          </label>
                       </div>
                    </div>

                    {/* 3. Access Level Filter (Enabled only when Road Closures are toggled) */}
                    <div className={`flex flex-col gap-2 transition-all duration-300 ${!showRoadClosures && 'opacity-35 pointer-events-none'}`}>
                       <h3 className="text-[10px] text-slate-500 font-black uppercase tracking-wider font-mono border-b border-slate-850 pb-1.5">ROAD EMERGENCY ACCESS</h3>
                       <div className="flex flex-col gap-2.5 mt-1.5">
                          <label className="flex items-center gap-2.5 text-xs text-slate-350 cursor-pointer">
                             <input 
                                type="checkbox" 
                                checked={filterNoAccess} 
                                onChange={(e) => setFilterNoAccess(e.target.checked)} 
                                className="rounded border-slate-850 bg-slate-950 text-red-500 focus:ring-0 focus:ring-offset-0 w-4 h-4 cursor-pointer" 
                             />
                             <span className="flex items-center gap-2"><span className="w-2.5 h-2.5 rounded-full bg-red-500 inline-block"></span>No Emergency Access</span>
                          </label>
                          <label className="flex items-center gap-2.5 text-xs text-slate-350 cursor-pointer">
                             <input 
                                type="checkbox" 
                                checked={filterAccessOnly} 
                                onChange={(e) => setFilterAccessOnly(e.target.checked)} 
                                className="rounded border-slate-850 bg-slate-950 text-amber-500 focus:ring-0 focus:ring-offset-0 w-4 h-4 cursor-pointer" 
                          />
                             <span className="flex items-center gap-2"><span className="w-2.5 h-2.5 rounded-full bg-amber-500 inline-block"></span>Emergency Access Only</span>
                          </label>
                          <label className="flex items-center gap-2.5 text-xs text-slate-350 cursor-pointer">
                             <input 
                                type="checkbox" 
                                checked={filterCaution} 
                                onChange={(e) => setFilterCaution(e.target.checked)} 
                                className="rounded border-slate-850 bg-slate-950 text-yellow-500 focus:ring-0 focus:ring-offset-0 w-4 h-4 cursor-pointer" 
                             />
                             <span className="flex items-center gap-2"><span className="w-2.5 h-2.5 rounded-full bg-yellow-500 inline-block"></span>Passable with Caution</span>
                          </label>
                       </div>
                    </div>

                    {/* 4. Legend Section */}
                    <div className="flex flex-col gap-2 mt-auto border-t border-slate-855 pt-4">
                       <h3 className="text-[10px] text-slate-500 font-black uppercase tracking-wider font-mono mb-2">MAP LEGEND</h3>
                       <div className="flex flex-col gap-3 font-mono text-[9px] text-slate-400">
                          <div className="flex items-center gap-2.5">
                             <div className="w-6 border-b-2 border-dashed border-red-500"></div>
                             <span>No Emergency Access Road</span>
                          </div>
                          <div className="flex items-center gap-2.5">
                             <div className="w-6 border-b-2 border-dashed border-amber-500"></div>
                             <span>Emergency Access Only Road</span>
                          </div>
                          <div className="flex items-center gap-2.5">
                             <div className="w-6 border-b-2 border-dashed border-yellow-500"></div>
                             <span>Passable with Caution Road</span>
                          </div>
                          <div className="flex items-center gap-2.5">
                             <div className="w-4 h-4 rounded-full bg-slate-900 border border-slate-750 flex items-center justify-center text-[8px] font-bold text-sky-400">💧</div>
                             <span>City Fire Hydrant Overlay</span>
                          </div>
                          <div className="flex items-center gap-2.5">
                             <div className="w-4 h-4 rounded-full bg-white border-2 border-red-500 flex items-center justify-center text-[8px]">🚒</div>
                             <span>Coquitlam Fire Hall</span>
                          </div>
                       </div>
                    </div>
                  </>
                 ) : loadingTraining ? (
                   <div className="flex flex-col items-center justify-center py-16 gap-3 text-slate-400">
                      <span className="flex h-5 w-5 relative">
                         <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-sky-400 opacity-75"></span>
                         <span className="relative inline-flex rounded-full h-5 w-5 bg-sky-500"></span>
                      </span>
                      <span className="text-[10px] font-bold font-mono tracking-widest animate-pulse">LOADING TRAINING DATA...</span>
                   </div>
                 ) : (
                  <>
                    {/* Training Details Panel */}
                    <div className="flex flex-col gap-4 text-center">
                       {appMode === "TRAINING_ZONES" && currentQuestion && (
                         <div className="bg-slate-950 p-4 border border-slate-850 rounded-xl animate-in fade-in">
                           <div className="text-slate-500 text-[10px] uppercase font-mono tracking-widest">Target Zone</div>
                           <div className="text-3xl text-sky-400 font-extrabold mt-1">Zone {currentQuestion.zone_id}</div>
                         </div>
                       )}
                       {appMode === "TRAINING_INTERSECTIONS" && currentQuestion && (
                         <div className="bg-slate-950 p-4 border border-slate-850 rounded-xl text-left animate-in fade-in">
                           <div className="text-slate-500 text-[10px] uppercase font-mono tracking-widest mb-1 text-center">Locate Intersection</div>
                           <div className="text-sm text-white font-black text-center mt-1 leading-snug">{currentQuestion.name}</div>
                         </div>
                       )}
                       {appMode === "TRAINING_BLOCKS" && currentQuestion && (
                         <div className="bg-slate-950 p-4 border border-slate-850 rounded-xl animate-in fade-in">
                           <div className="text-slate-500 text-[10px] uppercase font-mono tracking-widest">Target Block Range</div>
                           <div className="text-3xl text-amber-500 font-black mt-1">{currentQuestion.block}</div>
                           <div className="text-sm text-white font-bold mt-1 font-mono">{currentQuestion.street}</div>
                         </div>
                       )}
                       {appMode === "TRAINING_ADDRESSES" && currentQuestion && (
                         <div className="bg-slate-950 p-4 border border-slate-850 rounded-xl text-left animate-in fade-in">
                           <div className="text-slate-500 text-[10px] uppercase font-mono tracking-widest mb-1 text-center">Find Target Address</div>
                           <div className="text-base text-white font-black text-center mt-1 leading-snug">{currentQuestion.address}</div>
                         </div>
                       )}
                    </div>

                    {/* Active Option Inputs / Buttons */}
                    <div className="flex-grow flex flex-col justify-center gap-3">
                       {appMode === "TRAINING_ZONES" && (
                           <div className="flex flex-col gap-2">
                               {Object.keys(UNIT_COLORS).filter(u => u !== "UNKNOWN").map((unit) => (
                                   <button 
                                     key={unit} 
                                     onClick={() => onZoneGuess(unit)} 
                                     disabled={feedback !== null} 
                                     className={`w-full py-3 px-4 rounded-xl font-bold text-left flex justify-between items-center transition-all border-l-4 shadow-sm ${
                                       feedback === "WRONG" && unit === currentQuestion.unit_id 
                                         ? "bg-green-600 text-white border-green-300 animate-pulse" 
                                         : "bg-slate-950 border-slate-850 text-slate-300 hover:bg-slate-800 hover:text-white"
                                     }`}
                                   >
                                       <span>{unit} Response</span>
                                       <span 
                                         className="w-3 h-3 rounded-full" 
                                         style={{ backgroundColor: UNIT_COLORS[unit] }}
                                       ></span>
                                   </button>
                               ))}
                           </div>
                       )}

                       {/* Score HUD */}
                       <div className="mt-4 text-center">
                          <span className="text-slate-500 text-[10px] font-mono uppercase tracking-wider">Session Score</span>
                          <div className="text-2xl font-black text-white font-mono mt-0.5">{score} pts</div>
                       </div>
                    </div>

                    {/* Response Feedback Details */}
                    {feedback ? (
                        <div className="text-center bg-slate-950 p-4 border border-slate-850 rounded-xl animate-in fade-in">
                            <div className={`text-3xl font-extrabold mb-1.5 ${
                              feedback === "PERFECT" || feedback === "CORRECT" 
                                ? "text-emerald-400" 
                                : "text-rose-400"
                            }`}>
                                {feedback === "PERFECT" || feedback === "CORRECT" ? "PERFECT!" : "WRONG"}
                            </div>
                            
                            {feedback !== "PERFECT" && feedback !== "CORRECT" && (
                               <div className="text-xs text-slate-400 font-mono mt-1">
                                  Error Distance: <span className="text-white font-bold">{distanceOff}m</span>
                               </div>
                            )}

                            {appMode === "TRAINING_BLOCKS" && feedback === "WRONG" && clickedBlockData && (
                                <div className="text-rose-400 font-semibold text-xs mt-1 border-t border-slate-900 pt-1.5">
                                  Selected: {clickedBlockData.block} {clickedBlockData.street}
                                </div>
                            )}

                            <button 
                              onClick={onNext} 
                              className="bg-emerald-500 hover:bg-emerald-400 text-black font-extrabold py-3 px-6 rounded-xl w-full shadow-lg mt-4 transition-all duration-150"
                            >
                              NEXT &rarr;
                            </button>
                        </div>
                    ) : (
                        <div className="text-center text-slate-500 text-[10px] italic border-t border-slate-850/50 pt-4">
                            {appMode === "TRAINING_INTERSECTIONS" && "Tap matching intersection point on the map..."}
                            {appMode === "TRAINING_BLOCKS" && "Click correct highlighted road segment..."}
                            {appMode === "TRAINING_ADDRESSES" && "Zoom in and tap correct parcel boundary..."}
                        </div>
                    )}

                    {/* ZOOM UTILITIES */}
                    {appMode === "TRAINING_ADDRESSES" && !feedback && currentQuestion && (
                        <button 
                          onClick={() => map.setView([currentQuestion.lat, currentQuestion.lng], 20, { animate: true })} 
                          className="bg-slate-950 hover:bg-slate-850 text-[10px] text-white font-bold py-2.5 px-4 rounded-lg w-full border border-slate-800 flex items-center justify-center gap-1.5 transition-all mt-auto"
                        >
                          🔍 ZOOM TO PARCEL
                        </button>
                    )}
                  </>
                )}
             </div>
          </div>
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

export function RightSidebar({ 
  rightSidebarOpen, 
  setRightSidebarOpen, 
  appMode, 
  roadClosures, 
  showRoadClosures, 
  filterNoAccess,
  filterAccessOnly,
  filterCaution,
  map,
  onSelectClosure
}) {
  const isExplore = appMode === "EXPLORE";
  if (!isExplore) return null; // Only render right sidebar alerts in Explore/Information Mode

  // Process and sort closures:
  // 1. Parse start and end dates.
  // 2. Identify if ACTIVE, FUTURE or EXPIRED (based on new Date()).
  // 3. Exclude expired closures to keep map and list clean.
  // 4. Sort: ACTIVE closures first (ordered by duration ascending, i.e., shortest duration first),
  //    then FUTURE closures (ordered by start date ascending, i.e., starting soonest first).
  const processedClosures = React.useMemo(() => {
    const now = new Date();

    return roadClosures
      .map(closure => {
        const start = closure.startDate ? new Date(closure.startDate) : null;
        const end = closure.endDate ? new Date(closure.endDate) : null;

        let isActive = false;
        let isFuture = false;
        let isExpired = false;
        let durationMs = Infinity;

        if (!start) {
          // Fallback: closures with no start date are treated as active
          isActive = true;
        } else if (now < start) {
          isFuture = true;
        } else if (end && now > end) {
          // Live Municipal 511 feeds can have tentative database end dates in the past
          // but are still active and should be displayed. Only expire DriveBC events.
          if (closure.source === "DriveBC Open511") {
            isExpired = true;
          } else {
            isActive = true;
          }
        } else {
          isActive = true;
        }

        if (start && end) {
          durationMs = end.getTime() - start.getTime();
        }

        return {
          ...closure,
          start,
          end,
          isActive,
          isFuture,
          isExpired,
          durationMs
        };
      })
      .filter(closure => {
        // Hide expired closures
        if (closure.isExpired) return false;

        // Apply emergencyAccess filters
        if (closure.emergencyAccess === "NO_ACCESS" && !filterNoAccess) return false;
        if (closure.emergencyAccess === "ACCESS_ONLY" && !filterAccessOnly) return false;
        if (closure.emergencyAccess === "CAUTION" && !filterCaution) return false;
        return true;
      })
      .sort((a, b) => {
        // Active closures first, then future
        if (a.isActive && !b.isActive) return -1;
        if (!a.isActive && b.isActive) return 1;

        if (a.isActive && b.isActive) {
          // Sort active closures by duration ascending (shortest first)
          if (a.durationMs !== b.durationMs) {
            return a.durationMs - b.durationMs;
          }
          // Fallback: sort by start date ascending
          const aTime = a.start ? a.start.getTime() : 0;
          const bTime = b.start ? b.start.getTime() : 0;
          return aTime - bTime;
        }

        if (a.isFuture && b.isFuture) {
          // Sort future closures by start date ascending (soonest first)
          const aTime = a.start ? a.start.getTime() : 0;
          const bTime = b.start ? b.start.getTime() : 0;
          return aTime - bTime;
        }

        return 0;
      });
  }, [roadClosures, filterNoAccess, filterAccessOnly, filterCaution]);

  const formatDateRange = (start, end) => {
    if (!start) return "Ongoing";
    
    const options = { month: 'short', day: 'numeric', year: 'numeric' };
    const startStr = start.toLocaleDateString('en-US', options);
    
    if (!end) {
      return `Started ${startStr}`;
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
                <div className="text-slate-500 text-[10px] uppercase font-mono tracking-widest mb-1">CFR EVO ALERTS</div>
                <div className="text-lg text-rose-500 font-extrabold uppercase font-sans tracking-wide">ACTIVE HAZARDS</div>
             </div>

             {/* Alerts Card List */}
             <div className="p-4 flex-grow overflow-y-auto min-h-0 scrollbar-thin scrollbar-thumb-slate-800 scrollbar-track-transparent">
                {showRoadClosures ? (
                    <div className="flex flex-col gap-2.5 pr-1">
                        <div className="text-slate-400 text-[10px] font-semibold mb-1 uppercase font-mono tracking-wider">Filtered Alerts ({processedClosures.length})</div>
                        {processedClosures.length > 0 ? (
                            processedClosures.map((closure) => (
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
                                          {closure.emergencyAccess === 'NO_ACCESS' ? 'NO ACCESS' :
                                           closure.emergencyAccess === 'ACCESS_ONLY' ? 'LTD ACCESS' :
                                           'CAUTION'}
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