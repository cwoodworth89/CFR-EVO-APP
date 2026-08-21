// NOTE: For the live Coquitlam GIS offline warning status badge details, see docs/gis_endpoints.md
import React from 'react';
import { MapContainer, TileLayer, Marker } from 'react-leaflet';
import L from 'leaflet';
import { UNIT_COLORS, STATIONS_MAP as STATIONS, KNOWN_BUILDINGS, STATIONS as STATIONS_LIST } from './MapConstants';
import { sanitizeAddress, calculateParcelFrontagePoint } from '../utils/addressUtils';
import { API_BASE_URL, TILE_BASE_URL } from '../apiClient';


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
  showRoadClosures,
  setShowRoadClosures,
  onOpenRoutingConfig,
  alertsCount,
  gisOffline,
  homeHall
}) {
  const [showLayersMenu, setShowLayersMenu] = React.useState(false);
  const isExplore = appMode === "EXPLORE";

  const handleModeChange = (e) => {
    const selectedValue = e.target.value;
    setAppMode(selectedValue);
  };

  return (
    <div className="bg-slate-950 text-white p-3 shadow-md z-[1100] flex justify-between items-center border-b border-slate-800 h-16 relative select-none">
        {/* Left Side: Brand Logo */}
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-3">
            <h1 className="text-lg font-bold tracking-wider flex items-center gap-1.5 select-none uppercase">
              CFR <span className="text-emerald-500 font-extrabold">DISPATCH</span>
              <span className="text-slate-500 font-normal text-[10px] uppercase tracking-widest ml-1.5 border-l border-slate-800 pl-2 font-mono">
                {(() => {
                  const defaultHallId = import.meta.env.VITE_DEFAULT_HALL || "1";
                  const configStn = STATIONS_LIST.find(s => s.id === defaultHallId) || STATIONS_LIST[0];
                  const configStnName = configStn ? configStn.name.split(" Fire Hall")[0] : `HALL ${defaultHallId}`;
                  return `${configStnName} (Hall ${defaultHallId})`;
                })()}
              </span>
            </h1>
            
            {gisOffline && (
              <span className="bg-rose-500/10 text-rose-400 border border-rose-500/20 text-[9px] font-mono font-bold px-2 py-0.5 rounded flex items-center gap-1.5 select-none animate-pulse">
                <span className="w-1.5 h-1.5 rounded-full bg-rose-500"></span>
                COQUITLAM GIS OFFLINE
              </span>
            )}
          </div>
        </div>

        {/* Center: Mode Select Dropdown */}
        <div className="flex items-center">
          <div className="relative">
            <select 
              value={isExplore ? "EXPLORE" : appMode} 
              onChange={handleModeChange}
              className="bg-slate-900 border border-slate-700 hover:border-slate-650 text-white rounded-lg pl-3 pr-8 py-1.5 text-xs font-bold focus:outline-none focus:border-sky-500 cursor-pointer shadow-sm appearance-none min-w-[220px]"
              style={{ 
                backgroundImage: `url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='24' height='24' fill='none' stroke='%2394a3b8' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><polyline points='6 9 12 15 18 9'></polyline></svg>")`, 
                backgroundPosition: 'right 8px center', 
                backgroundRepeat: 'no-repeat', 
                backgroundSize: '14px' 
              }}
            >
              <option value="EXPLORE">🧭 Notifications / Explore</option>
              <option value="KIOSK_VIEW">🖥️ KIOSK: IN-STATION MODE</option>
              <option value="DRIVER_SETUP">📱 MOBILE: DRIVER PUSH SETUP</option>
              <option value="ADMIN_DISPATCHES">🛡️ ADMIN: DISPATCH REVIEW</option>
            </select>
          </div>
        </div>

        {/* Right Side: Alerts & Mobile Setup Triggers */}
        <div className="flex gap-3 items-center">
          <button
            onClick={() => setAppMode("DRIVER_SETUP")}
            className="px-3 py-1.5 text-xs font-black rounded-lg border bg-amber-500/20 border-amber-500/40 text-amber-300 hover:bg-amber-500/30 hover:border-amber-500/60 transition-all flex items-center gap-1.5 cursor-pointer shadow-md"
            title="Open Driver Mobile Alerts QR Setup"
          >
            📱 DRIVER ALERTS
          </button>

          {/* Right Sidebar Hazards & Alerts Panel Toggle */}
          <button 
            onClick={() => {
              setRightSidebarOpen(!rightSidebarOpen);
              if (setShowRoadClosures) setShowRoadClosures(true);
            }}
            className={`px-3 py-1.5 text-xs font-bold rounded-lg border transition-all flex items-center gap-1.5 cursor-pointer ${
              rightSidebarOpen 
                ? "bg-amber-950/80 border-amber-600/80 text-amber-300 shadow-md animate-pulse" 
                : "bg-slate-900 border-slate-800 text-slate-300 hover:border-slate-700 hover:text-white"
            }`}
            title="Toggle Road Closures Panel"
          >
            🚧 ROAD CLOSURES {alertsCount > 0 && <span className="bg-amber-500 text-slate-950 text-[9px] font-black px-1.5 py-0.2 rounded-full ml-1">{alertsCount}</span>}
          </button>
        </div>
    </div>
  );
}



function SatelliteMiniMap({ lat, lng }) {
  if (!lat || !lng) return null;

  const position = [lat, lng];
  
  // Custom red target icon
  const miniTargetIcon = L.divIcon({
    className: 'custom-mini-target-icon',
    html: `<div style="
      background-color: #ef4444;
      border: 2px solid #ffffff;
      border-radius: 50%;
      width: 12px;
      height: 12px;
      box-shadow: 0 0 10px rgba(239, 68, 68, 0.8);
    "></div>`,
    iconSize: [12, 12],
    iconAnchor: [6, 6]
  });

  return (
    <div className="h-44 w-full rounded-xl overflow-hidden border border-slate-800 relative z-[990]">
      <MapContainer 
        key={`${lat}-${lng}`}
        center={position} 
        zoom={18} 
        zoomControl={false}
        attributionControl={false}
        doubleClickZoom={false}
        scrollWheelZoom={false}
        dragging={false}
        style={{ height: '100%', width: '100%' }}
      >
        <TileLayer
          url={`${TILE_BASE_URL}/services/satellite/tiles/{z}/{x}/{y}.jpg`}
          maxNativeZoom={20}
          maxZoom={22}
        />
        <Marker position={position} icon={miniTargetIcon} />
      </MapContainer>
    </div>
  );
}

function ActiveDispatchPanel({ activeDispatch, setActiveDispatch, nearestHydrants = [], setTargetAddress }) {
  const target = activeDispatch.target || {};
  const lat = target.lat || activeDispatch.latitude;
  const lng = target.lng || activeDispatch.longitude;
  const address = target.address || activeDispatch.address || "Unknown Address";
  const incidentType = activeDispatch.incident_type || "Emergency Call";
  const units = activeDispatch.responding_units || [];

  const handleDismiss = () => {
    setActiveDispatch(null);
    setTargetAddress(null);
  };

  const googleApiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY || '';
  const hasGoogleKey = googleApiKey && googleApiKey !== 'your-google-api-key-here';
  
  const streetViewUrl = hasGoogleKey
    ? `https://maps.googleapis.com/maps/api/streetview?size=400x250&location=${lat},${lng}&key=${googleApiKey}`
    : null;

  return (
    <div className="flex flex-col h-full bg-slate-905 text-slate-100 overflow-y-auto w-full select-none">
      {/* Active Alert Banner */}
      <div className={`p-4 text-center border-b animate-pulse flex flex-col gap-0.5 shadow-md flex-shrink-0 ${
        activeDispatch.is_test 
          ? "bg-gradient-to-r from-amber-600 via-orange-600 to-amber-600 border-amber-500"
          : "bg-gradient-to-r from-red-600 to-orange-600 border-red-700"
      }`}>
        <span className="text-[10px] text-white/95 font-black uppercase tracking-widest font-mono">
          {activeDispatch.is_test ? "⚠️ *TEST* DISPATCH SIMULATION ACTIVE ⚠️" : "🚨 DISPATCH OVERRIDE ACTIVE 🚨"}
        </span>
        <span className="text-xs text-white/80 font-bold tracking-wider font-mono">
          {activeDispatch.is_test ? "SYSTEM QA / TRAINING DRILL" : "STATION KIOSK ALERT"}
        </span>
      </div>

      <div className="p-5 flex-grow flex flex-col gap-6 overflow-y-auto">
        {/* Core Dispatch Details */}
        <div className="bg-slate-950 p-4 border border-slate-800 rounded-2xl flex flex-col gap-1 flex-shrink-0">
          <span className="text-[9px] text-red-400 font-extrabold uppercase font-mono tracking-wider">INCIDENT LOCATION</span>
          <h2 className="text-xl text-white font-black leading-tight tracking-wide uppercase select-text">{address}</h2>
          <div className="border-t border-slate-900 mt-2.5 pt-2 flex flex-col gap-0.5 text-left">
            <span className="text-[8px] text-slate-500 font-extrabold uppercase font-mono">CALL TYPE</span>
            <div className="text-sm text-amber-500 font-black tracking-wide uppercase">
              {activeDispatch.is_test && !incidentType.includes("*TEST*") ? `*TEST* ${incidentType}` : incidentType}
            </div>
          </div>
        </div>

        {/* Responding Units */}
        <div className="flex flex-col gap-2 bg-slate-950 p-4 border border-slate-800 rounded-2xl flex-shrink-0 text-left">
          <span className="text-[9px] text-slate-400 font-extrabold uppercase font-mono tracking-wider">RESPONDING UNITS (ORDER ANNOUNCED)</span>
          {units.length > 0 ? (
            <div className="flex flex-wrap gap-2 mt-1">
              {units.map((unit, idx) => (
                <span 
                  key={idx}
                  className="px-3 py-1.5 rounded-lg text-xs font-black tracking-wider shadow border bg-slate-900 text-sky-400 border-sky-500/30"
                >
                  🚒 {unit}
                </span>
              ))}
            </div>
          ) : (
            <div className="text-xs text-slate-500 italic">No units listed in broadcast.</div>
          )}
        </div>

        {/* Nearest Hydrants */}
        <div className="flex flex-col gap-2 bg-slate-950 p-4 border border-slate-800 rounded-2xl flex-shrink-0 text-left">
          <span className="text-[9px] text-cyan-400 font-extrabold uppercase font-mono tracking-wider">💧 NEAREST CITY HYDRANTS</span>
          <div className="flex flex-col gap-2 mt-1">
            {nearestHydrants.slice(0, 3).map((hyd, idx) => {
              const isPrimary = idx === 0;
              return (
                <div 
                  key={idx}
                  className={`flex justify-between items-center p-2 rounded-xl text-xs border ${
                    isPrimary 
                      ? 'bg-slate-900 border-cyan-500/30' 
                      : 'bg-slate-900/60 border-slate-850'
                  }`}
                >
                  <div className="flex flex-col text-left">
                    <div className="font-black text-white font-mono flex items-center gap-1.5">
                      <span>{hyd.gisId}</span>
                      {isPrimary && (
                        <span className="px-1.5 py-0.2 rounded text-[7px] bg-cyan-500/20 text-cyan-400 font-black tracking-wider uppercase font-sans">
                          Closest
                        </span>
                      )}
                    </div>
                    {hyd.flowClass && (
                      <div className="text-[9px] text-sky-400 font-bold font-mono">Flow: {hyd.flowClass}</div>
                    )}
                  </div>
                  <div className="text-right">
                    <div className="font-extrabold text-emerald-400 font-mono">{hyd.distance}m</div>
                    <div className="text-[8px] text-slate-500 font-extrabold uppercase font-mono">Distance</div>
                  </div>
                </div>
              );
            })}
            {nearestHydrants.length === 0 && (
              <div className="text-xs text-slate-500 italic">Calculating closest hydrants...</div>
            )}
          </div>
        </div>

        {/* TV Kiosk Satellite View */}
        <div className="flex flex-col gap-2 bg-slate-950 p-4 border border-slate-800 rounded-2xl flex-shrink-0 text-left">
          <span className="text-[9px] text-slate-400 font-extrabold uppercase font-mono tracking-wider flex justify-between items-center">
            <span>🛰️ GOOGLE SATELLITE VIEW</span>
            <span className="text-emerald-500 text-[8px] font-black uppercase">ZOOM LEVEL 18</span>
          </span>
          <div className="mt-1">
            {lat && lng ? (
              <SatelliteMiniMap lat={lat} lng={lng} />
            ) : (
              <div className="h-44 w-full bg-slate-900 border border-slate-850 rounded-xl flex items-center justify-center text-xs text-slate-500 italic">
                Coordinates missing
              </div>
            )}
          </div>
        </div>

        {/* TV Kiosk Street View */}
        <div className="flex flex-col gap-2 bg-slate-950 p-4 border border-slate-800 rounded-2xl flex-shrink-0 text-left">
          <span className="text-[9px] text-slate-400 font-extrabold uppercase font-mono tracking-wider flex justify-between items-center">
            <span>📷 STREET VIEW (ALPHA SIDE FRONTAGE)</span>
            <span className="text-indigo-400 text-[8px] font-black uppercase">STREET FRONTAGE</span>
          </span>
          <div className="mt-1">
            {lat && lng ? (
              hasGoogleKey ? (
                <div className="h-44 w-full rounded-xl overflow-hidden border border-slate-800">
                  <img src={streetViewUrl} alt="Google Street View" className="w-full h-full object-cover" />
                </div>
              ) : (
                <div className="bg-slate-900 border border-slate-850 rounded-xl p-3.5 flex flex-col gap-2 relative overflow-hidden text-left">
                  <div className="text-[9px] text-slate-450 font-bold leading-relaxed">
                    Google Maps API Key not configured. Visual mock and coordinates computed:
                  </div>
                  <div className="grid grid-cols-2 gap-2 font-mono text-[9px] bg-slate-950/80 p-2 rounded border border-slate-850 text-center">
                    <div>
                      <div className="text-[7px] text-slate-500 font-black">LATITUDE</div>
                      <div className="text-white font-bold">{lat.toFixed(5)}</div>
                    </div>
                    <div>
                      <div className="text-[7px] text-slate-500 font-black">LONGITUDE</div>
                      <div className="text-white font-bold">{lng.toFixed(5)}</div>
                    </div>
                  </div>
                  <a 
                    href={`https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=${lat},${lng}`}
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="bg-indigo-600 hover:bg-indigo-700 text-white font-extrabold py-2 px-3 rounded-lg text-[10px] flex items-center justify-center gap-1.5 transition-all text-center w-full shadow border border-indigo-500 mt-1"
                  >
                    🌐 OPEN GOOGLE STREET VIEW
                  </a>
                </div>
              )
            ) : (
              <div className="h-44 w-full bg-slate-900 border border-slate-850 rounded-xl flex items-center justify-center text-xs text-slate-500 italic">
                Coordinates missing
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Dismiss Button */}
      <div className="p-4 border-t border-slate-850 bg-slate-950 mt-auto flex-shrink-0">
        <button
          onClick={handleDismiss}
          className="bg-slate-800 hover:bg-slate-700 text-rose-455 hover:text-rose-300 font-extrabold py-3 px-6 rounded-xl w-full transition-all border border-slate-700 hover:border-slate-650 shadow-md flex items-center justify-center gap-1.5 cursor-pointer text-xs"
        >
          ✕ DISMISS DISPATCH OVERRIDE
        </button>
      </div>
    </div>
  );
}

export function LeftSidebar({ 
  leftSidebarOpen, 
  setLeftSidebarOpen, 
  appMode, 
  activeDispatch,
  setActiveDispatch,
  loadingTraining,
  mapStyle,
  setMapStyle,
  onOpenRoutingConfig,
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
  showSchools,
  setShowSchools,
  showFireHalls,
  setShowFireHalls,
  homeHall,
  setHomeHall,
  targetAddress,
  setTargetAddress,
  nearestHydrant,
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
  showActiveNow = true,
  setShowActiveNow,
  showNext24h = false,
  setShowNext24h,
  showNext7d = false,
  setShowNext7d,

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
                              <span>Satellite</span>
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
                                     <span className="text-[8px] text-slate-400 font-mono">EMTRAC Code 3</span>
                                  </div>

                                  {/* Driver Railroad Warning Badge */}
                                  {routeMetrics?.railroadWarning && (
                                     <div className={`p-2 rounded-lg text-[9px] font-mono font-bold leading-snug flex items-center gap-1.5 border ${
                                        routeMetrics.railroadWarning.type === 'AVOIDED'
                                          ? 'bg-emerald-950/80 border-emerald-700/80 text-emerald-300'
                                          : 'bg-amber-950/80 border-amber-700/80 text-amber-300'
                                     }`}>
                                        {routeMetrics.railroadWarning.badge}
                                     </div>
                                  )}

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
                                              <span className="text-slate-400 text-[10px]">{u.distanceKm} km</span>
                                              <span className="text-emerald-400 font-black">{u.etaMinutes} min</span>
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

                          {/* 🏫 SCHOOLS OVERLAY */}
                          <label className="flex items-center gap-2.5 text-xs text-slate-300 cursor-pointer">
                             <input 
                                type="checkbox" 
                                checked={showSchools} 
                                onChange={(e) => setShowSchools && setShowSchools(e.target.checked)} 
                                className="rounded border-slate-800 bg-slate-950 text-blue-500 focus:ring-0 focus:ring-offset-0 w-4 h-4 cursor-pointer" 
                             />
                             <span className="flex items-center gap-1.5 font-semibold">🏫 Schools</span>
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