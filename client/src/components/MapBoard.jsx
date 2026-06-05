/* global __BUILD_DATE__ */
import React, { useEffect, useState, useRef, useCallback } from 'react'; // Added useRef and useCallback
import { MapContainer, Polygon, CircleMarker, Polyline, Tooltip, Pane, Marker, Popup } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import * as turf from '@turf/turf';
import L from 'leaflet';

// Import from your other components
import { BaseMap, CoquitlamOverlays, StationsLayer, FireZonesLayer, HydrantsLayer } from './MapLayers';
import { MapClickEvents, SmartZoom, ZoomToFeedback } from './MapActions';
import { Header, LeftSidebar, RightSidebar } from './GameHUD';
import { MODE_DEFAULTS, UNIT_COLORS } from './MapConstants';
import { RoutingOverlay } from './RoutingOverlay';

// 🎲 Pure utility function to pick a random element, satisfying React 19 render purity rules
const getRandomElement = (arr) => {
  if (!arr || arr.length === 0) return null;
  return arr[Math.floor(Math.random() * arr.length)];
};

// 🚧 Barricade Icon for Road Closures
const closureIcon = L.divIcon({
  className: 'custom-closure-icon',
  html: `<div style="
    background-color: #f59e0b;
    border: 2px solid #000000;
    border-radius: 6px;
    width: 28px;
    height: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 2px 5px rgba(0,0,0,0.4);
    font-size: 15px;
    box-sizing: border-box;
  ">🚧</div>`,
  iconSize: [28, 28],
  iconAnchor: [14, 14],
  popupAnchor: [0, -14]
});

// 🚒 Fire Hall coordinate mapping
const STATIONS = {
  "1": [49.291329039026046, -122.79161362016414], // Town Centre Fire Hall (TCFH)
  "2": [49.26223510671969, -122.81725512755891],  // Mariner Fire Hall
  "3": [49.24804277980424, -122.86566519365569],  // Austin Heights Fire Hall
  "4": [49.2952132946437, -122.7425391041921]     // Burke Mountain Fire Hall
};

// 🎯 Custom Target Address Icon
const targetIcon = L.divIcon({
  className: 'custom-target-icon',
  html: `<div style="
    background-color: #4f46e5;
    border: 2px solid #ffffff;
    border-radius: 50%;
    width: 24px;
    height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 2px 6px rgba(0,0,0,0.4);
    font-size: 13px;
    box-sizing: border-box;
    color: white;
  ">🎯</div>`,
  iconSize: [24, 24],
  iconAnchor: [12, 12],
  popupAnchor: [0, -12]
});

export default function MapBoard() {
  const [map, setMap] = useState(null);

  // Safe dynamic compile-time stamp
  const buildTime = typeof __BUILD_DATE__ !== 'undefined' ? __BUILD_DATE__ : 'LOCAL_DEV';

  // DATA STATE
  const [zones, setZones] = useState([]);
  const [intersections, setIntersections] = useState([]);
  const [blocks, setBlocks] = useState([]);
  const [addresses, setAddresses] = useState([]);
  const [roadClosures, setRoadClosures] = useState([]);
  
  // GAME STATE
  const [gameMode, setGameMode] = useState("EXPLORE"); 
  const [mapStyle, setMapStyle] = useState("GREY"); 
  const [showLabels, setShowLabels] = useState(true); 
  const [showHydrants, setShowHydrants] = useState(true); 
  const [showZones, setShowZones] = useState(false); 
  const [showRoadClosures, setShowRoadClosures] = useState(true); 
  
  // COLLAPSIBLE SIDEBAR STATES
  const [leftSidebarOpen, setLeftSidebarOpen] = useState(true);
  const [rightSidebarOpen, setRightSidebarOpen] = useState(false);

  // NAVIGATION & ROUTING STATES
  const [homeHall, setHomeHall] = useState(() => {
    return localStorage.getItem('home_hall') || "1";
  });
  const [targetAddress, setTargetAddress] = useState(null);
  const [targetPolygon, setTargetPolygon] = useState(null);
  const [nearestHydrant, setNearestHydrant] = useState(null);

  const updateTargetAddress = useCallback((addr) => {
    setTargetAddress(addr);
    setTargetPolygon(null);
    setNearestHydrant(null);
  }, []);

  useEffect(() => {
    localStorage.setItem('home_hall', homeHall);
  }, [homeHall]);

  // Query Property Polygon and Nearest Hydrant on targetAddress change
  useEffect(() => {
    if (!targetAddress) return;

    const addressStr = targetAddress.address;
    const lat = targetAddress.lat;
    const lng = targetAddress.lng;

    // 1. Fetch Property Polygon from Layer 15 (Property Information)
    const upperAddress = addressStr.toUpperCase().replace(/'/g, "''");
    const propUrl = `https://geodata.coquitlam.ca/arcgis/rest/services/DynamicServices/Cadastral/MapServer/15/query?where=UPPER(ADDRESS)='${encodeURIComponent(upperAddress)}'&outFields=ADDRESS,GIS_ID&returnGeometry=true&outSR=4326&f=json`;

    fetch(propUrl)
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data && data.features && data.features.length > 0) {
          const geom = data.features[0].geometry;
          if (geom && geom.rings) {
            // Convert ESRI rings [lng, lat] to Leaflet coordinates [lat, lng]
            const leafletPolygon = geom.rings.map(ring => 
              ring.map(coord => [coord[1], coord[0]])
            );
            setTargetPolygon(leafletPolygon);
          } else {
            setTargetPolygon(null);
          }
        } else {
          setTargetPolygon(null);
        }
      })
      .catch(err => {
        console.warn("Failed to fetch property boundary polygon:", err);
        setTargetPolygon(null);
      });

    // 2. Fetch Nearby Hydrants from Layer 2 (within 150m)
    const hydUrl = `https://geodata.coquitlam.ca/arcgis/rest/services/DynamicServices/Water/MapServer/2/query?geometry=${lng},${lat}&geometryType=esriGeometryPoint&inSR=4326&distance=150&units=esriSRUnit_Meter&outFields=OBJECTID,gis_id,status,flow_class&returnGeometry=true&outSR=4326&f=json`;

    fetch(hydUrl)
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data && data.features && data.features.length > 0) {
          // Calculate distance using Turf
          const fromPoint = turf.point([lng, lat]);
          
          const sortedHydrants = data.features.map(f => {
            const hLng = f.geometry.x;
            const hLat = f.geometry.y;
            const toPoint = turf.point([hLng, hLat]);
            const distMeters = Math.round(turf.distance(fromPoint, toPoint, { units: 'kilometers' }) * 1000);
            
            return {
              gisId: f.attributes.gis_id || "Unknown",
              lat: hLat,
              lng: hLng,
              distance: distMeters,
              flowClass: f.attributes.flow_class || "",
              status: f.attributes.status || ""
            };
          }).sort((a, b) => a.distance - b.distance);

          if (sortedHydrants.length > 0) {
            setNearestHydrant(sortedHydrants[0]);
          } else {
            setNearestHydrant(null);
          }
        } else {
          setNearestHydrant(null);
        }
      })
      .catch(err => {
        console.warn("Failed to fetch nearby hydrants:", err);
        setNearestHydrant(null);
      });
  }, [targetAddress]);

  // Adaptive Zooming: fit bounds to show both the selected Fire Hall (origin) and searched address (destination)
  useEffect(() => {
    if (map && targetAddress && STATIONS[homeHall] && gameMode === "EXPLORE") {
      const origin = STATIONS[homeHall];
      const dest = [targetAddress.lat, targetAddress.lng];
      map.fitBounds([origin, dest], { padding: [50, 50], animate: true });
    }
  }, [map, targetAddress, homeHall, gameMode]);

  // ROAD ACCESS FILTER STATES
  const [filterNoAccess, setFilterNoAccess] = useState(true);
  const [filterAccessOnly, setFilterAccessOnly] = useState(true);
  const [filterCaution, setFilterCaution] = useState(true);

  const [currentQuestion, setCurrentQuestion] = useState(null);
  const [score, setScore] = useState(0);
  const [feedback, setFeedback] = useState(null);
  
  const [userGuess, setUserGuess] = useState(null);
  const [distanceOff, setDistanceOff] = useState(0); 
  const [clickedBlockData, setClickedBlockData] = useState(null);

  // ⏱️ TIMER REF (Prevents double-skipping if you hit Enter while waiting)
  const autoAdvanceTimer = useRef(null);

  // Auto-resize Leaflet map container to prevent gray areas when sidebars open/close
  useEffect(() => {
    if (map) {
      const timer = setTimeout(() => {
        map.invalidateSize();
      }, 350); // wait for transitions to settle
      return () => clearTimeout(timer);
    }
  }, [map, leftSidebarOpen, rightSidebarOpen]);

  // LOAD ROAD CLOSURES
  useEffect(() => {
    const baseUrl = import.meta.env.BASE_URL;

    // Fetch municipal local feed
    const fetchMuni = fetch(`${baseUrl}data/road_closures.json?v=1`)
      .then(r => r.ok ? r.json() : [])
      .catch(() => []);

    // Fetch DriveBC live API
    const fetchDriveBC = fetch("https://api.open511.gov.bc.ca/events?format=json&limit=100")
      .then(r => r.ok ? r.json() : { events: [] })
      .then(data => {
        if (!data || !data.events) return [];
        // Filter to Coquitlam bounding box
        return data.events
          .filter(evt => {
            if (!evt.geography || !evt.geography.coordinates) return false;
            let coords = [];
            if (evt.geography.type === "Point") {
              coords = [evt.geography.coordinates];
            } else if (evt.geography.type === "LineString") {
              coords = evt.geography.coordinates;
            } else {
              return false;
            }
            return coords.some(([lng, lat]) => 
              lat >= 49.20 && lat <= 49.38 && lng >= -122.92 && lng <= -122.68
            );
          })
          .map(evt => {
            let lat = 49.28;
            let lng = -122.80;
            if (evt.geography.type === "Point") {
              lng = evt.geography.coordinates[0];
              lat = evt.geography.coordinates[1];
            } else if (evt.geography.type === "LineString") {
              const middleIndex = Math.floor(evt.geography.coordinates.length / 2);
              lng = evt.geography.coordinates[middleIndex][0];
              lat = evt.geography.coordinates[middleIndex][1];
            }

            const severityVal = (evt.severity || "MINOR").toUpperCase();
            let emergencyAccess = "CAUTION";
            if (severityVal === "MAJOR") {
              emergencyAccess = "NO_ACCESS";
            } else if (severityVal === "MODERATE") {
              emergencyAccess = "ACCESS_ONLY";
            }
            
            return {
              id: evt.id || Math.random().toString(),
              headline: evt.headline || "TRAFFIC ALERT",
              street: evt.road_name || "Regional Road",
              severity: severityVal,
              emergencyAccess: emergencyAccess,
              description: evt.description || "Active traffic event.",
              coordinates: [lat, lng],
              source: "DriveBC Open511"
            };
          });
      })
      .catch(() => []);

    Promise.all([fetchMuni, fetchDriveBC]).then(([muniEvents, bcEvents]) => {
      setRoadClosures([...muniEvents, ...bcEvents]);
    });
  }, []);

  // LOAD DATA
  useEffect(() => {
    const baseUrl = import.meta.env.BASE_URL;

    fetch(`${baseUrl}data/zones.json?v=2`)
      .then(r => {
        if (!r.ok) throw new Error("HTTP 404");
        return r.json();
      })
      .then(setZones)
      .catch(e => console.error("Missing zones.json", e));

    fetch(`${baseUrl}data/intersections.json?v=1`)
      .then(r => {
        if (!r.ok) throw new Error("HTTP 404");
        return r.json();
      })
      .then(setIntersections)
      .catch(e => console.error("Missing intersections.json", e));

    fetch(`${baseUrl}data/blocks.json?v=2`)
      .then(r => {
        if (!r.ok) throw new Error("HTTP 404");
        return r.json();
      })
      .then(setBlocks)
      .catch(e => console.error("Missing blocks.json", e));

    fetch(`${baseUrl}data/addresses.json?v=2`)
      .then(r => {
        if (!r.ok) throw new Error("HTTP 404");
        return r.json();
      })
      .then(setAddresses)
      .catch(e => console.error("Missing addresses.json", e));
  }, []);

  // --- CONTROLLER LOGIC (Callbacks wrapped in useCallback to prevent unnecessary re-renders) ---
  const nextQuestion = useCallback((dataset) => {
      clearTimeout(autoAdvanceTimer.current); // Stop timer if manual click happened
      if (!dataset || dataset.length === 0) return;
      setCurrentQuestion(getRandomElement(dataset));
      setFeedback(null);
      setUserGuess(null);
  }, []);

  const nextBlockQuestion = useCallback(() => {
    clearTimeout(autoAdvanceTimer.current);
    if (!blocks || blocks.length === 0) return;
    const valid = blocks.filter(b => b.block > 0);
    setCurrentQuestion(getRandomElement(valid));
    setFeedback(null);
    setClickedBlockData(null);
  }, [blocks]);

  const goToNext = useCallback(() => {
      if(gameMode === "QUIZ_ZONES") nextQuestion(zones);
      if(gameMode === "QUIZ_INTERSECTIONS") nextQuestion(intersections);
      if(gameMode === "QUIZ_BLOCKS") nextBlockQuestion();
      if(gameMode === "QUIZ_ADDRESSES") nextQuestion(addresses);
  }, [gameMode, zones, intersections, addresses, nextQuestion, nextBlockQuestion]);

  const startMode = useCallback((mode) => {
      clearTimeout(autoAdvanceTimer.current); // Clear any pending jumps
      setGameMode(mode);
      setScore(0);
      setFeedback(null);
      setUserGuess(null);
      setTargetAddress(null);
      setMapStyle(MODE_DEFAULTS[mode]); 
      
      // Only show labels automatically for Address Mode and Explore
      setShowLabels(mode === "QUIZ_ADDRESSES" || mode === "EXPLORE");
      
      if (mode === "EXPLORE") {
          setShowZones(false);
          setShowHydrants(true);
          setShowRoadClosures(true);
          setCurrentQuestion(null);
          setLeftSidebarOpen(true);
          setRightSidebarOpen(false);
      } else {
          // Quiz Modes: Hydrants ON by default, road closures icons ON by default, zones OFF
          setShowHydrants(true);
          setShowRoadClosures(true);
          setShowZones(false);
          setLeftSidebarOpen(true);
          setRightSidebarOpen(false); // Close alerts list panel for training focus
      }
      
      if (mode === "QUIZ_ZONES") nextQuestion(zones);
      if (mode === "QUIZ_INTERSECTIONS") nextQuestion(intersections);
      if (mode === "QUIZ_BLOCKS") nextBlockQuestion();
      if (mode === "QUIZ_ADDRESSES") nextQuestion(addresses);
  }, [zones, intersections, addresses, nextQuestion, nextBlockQuestion]);

  // ⌨️ KEYBOARD LISTENER (Enter = Next) - Declared below goToNext to resolve TDZ hoisting bug
  useEffect(() => {
    const handleKeyDown = (e) => {
        // If Enter is pressed AND we are showing feedback (waiting for next)
        if (e.key === "Enter" && feedback && gameMode !== "EXPLORE") {
            goToNext();
        }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [feedback, gameMode, goToNext]);

  // --- HANDLERS ---
  const handleZoneGuess = useCallback((unitId) => {
    if (!currentQuestion) return;
    if (unitId === currentQuestion.unit_id) { 
        setFeedback("CORRECT"); 
        setScore(s => s + 1); 
        // Auto-advance
        autoAdvanceTimer.current = setTimeout(() => nextQuestion(zones), 1000); 
    } 
    else { setFeedback("WRONG"); }
  }, [currentQuestion, zones, nextQuestion]);

  const handleMapClick = useCallback((latlng) => {
    if (!currentQuestion || (gameMode !== "QUIZ_INTERSECTIONS" && gameMode !== "QUIZ_ADDRESSES") || feedback) return;
    setUserGuess(latlng);
    
    const from = turf.point([latlng.lng, latlng.lat]);
    const to = turf.point([currentQuestion.lng, currentQuestion.lat]);
    let distMeters = Math.round(turf.distance(from, to, { units: 'kilometers' }) * 1000);
    
    const tolerance = gameMode === "QUIZ_ADDRESSES" ? 15 : 50;
    if (distMeters <= tolerance) distMeters = 0;
    
    setDistanceOff(distMeters);
    const points = Math.max(0, 500 - distMeters);
    setScore(s => s + points);
    
    const result = distMeters === 0 ? "PERFECT" : points > 0 ? "OKAY" : "MISS";
    setFeedback(result);

    // 🔽 Auto-advance for Intersection/Address modes too
    if (result === "PERFECT") {
        autoAdvanceTimer.current = setTimeout(() => {
            if (gameMode === "QUIZ_INTERSECTIONS") nextQuestion(intersections);
            if (gameMode === "QUIZ_ADDRESSES") nextQuestion(addresses);
        }, 1500);
    }
  }, [currentQuestion, gameMode, feedback, intersections, addresses, nextQuestion]);

  const handleBlockClick = useCallback((blockData) => {
    if (!currentQuestion || gameMode !== "QUIZ_BLOCKS" || feedback) return;
    setClickedBlockData(blockData);
    
    const isCorrectStreet = currentQuestion.street === blockData.street;
    const diff = Math.abs(currentQuestion.block - blockData.block);
    
    if (isCorrectStreet && diff === 0) { 
        setFeedback("PERFECT"); 
        setScore(s => s + 1); 
        // Auto-advance
        autoAdvanceTimer.current = setTimeout(nextBlockQuestion, 1500); 
    }
    else { setFeedback("WRONG"); setDistanceOff(diff); }
  }, [currentQuestion, gameMode, feedback, nextBlockQuestion]);

  // --- RENDER HELPERS ---
  const getBlockStyle = useCallback((block) => {
    if (!feedback) return { color: "#64748b", weight: 6, opacity: 0.8 }; 
    const isTarget = block.block === currentQuestion.block && block.street === currentQuestion.street;
    const isClicked = clickedBlockData && block.block === clickedBlockData.block && block.street === clickedBlockData.street;
    if (isTarget) return { color: "#22c55e", weight: 12, opacity: 1 }; 
    if (isClicked) return { color: "#ef4444", weight: 12, opacity: 1 }; 
    return { color: "#475569", weight: 4, opacity: 0.15 }; 
  }, [feedback, currentQuestion, clickedBlockData]);

  const getZoneStyle = (zone) => {
    if (gameMode === "QUIZ_ZONES") {
        if (currentQuestion && zone.zone_id === currentQuestion.zone_id) {
            return { color: "#06b6d4", fillOpacity: 0.5, weight: 0 }; 
        }
        return { color: "transparent", fillOpacity: 0, weight: 0 }; 
    }
    return { color: "#475569", fillOpacity: 0.05, weight: 1 };
  };

  // Filter closures for map and alerts rendering
  const activeClosures = roadClosures.filter(closure => {
    if (closure.emergencyAccess === "NO_ACCESS" && !filterNoAccess) return false;
    if (closure.emergencyAccess === "ACCESS_ONLY" && !filterAccessOnly) return false;
    if (closure.emergencyAccess === "CAUTION" && !filterCaution) return false;
    return true;
  });

  return (
    <div className="h-screen w-screen flex flex-col bg-slate-950 overflow-hidden text-slate-100 font-sans">
      
      <Header 
        gameMode={gameMode} 
        startMode={startMode} 
        mapStyle={mapStyle} 
        setMapStyle={setMapStyle} 
        showLabels={showLabels} 
        setShowLabels={setShowLabels} 
        leftSidebarOpen={leftSidebarOpen}
        setLeftSidebarOpen={setLeftSidebarOpen}
        rightSidebarOpen={rightSidebarOpen}
        setRightSidebarOpen={setRightSidebarOpen}
        alertsCount={showRoadClosures ? activeClosures.length : 0}
      />

      <div className="flex flex-row flex-grow w-full h-[calc(100vh-4rem)] relative overflow-hidden z-10">
        {/* Left Control Panel & Option Toggles */}
        <LeftSidebar 
          leftSidebarOpen={leftSidebarOpen}
          setLeftSidebarOpen={setLeftSidebarOpen}
          gameMode={gameMode}
          showZones={showZones}
          setShowZones={setShowZones}
          showHydrants={showHydrants}
          setShowHydrants={setShowHydrants}
          showRoadClosures={showRoadClosures}
          setShowRoadClosures={setShowRoadClosures}
          showLabels={showLabels}
          setShowLabels={setShowLabels}
          addresses={addresses}
          homeHall={homeHall}
          setHomeHall={setHomeHall}
          targetAddress={targetAddress}
          setTargetAddress={updateTargetAddress}
          nearestHydrant={nearestHydrant}
          filterNoAccess={filterNoAccess}
          setFilterNoAccess={setFilterNoAccess}
          filterAccessOnly={filterAccessOnly}
          setFilterAccessOnly={setFilterAccessOnly}
          filterCaution={filterCaution}
          setFilterCaution={setFilterCaution}
          score={score}
          currentQuestion={currentQuestion}
          feedback={feedback}
          distanceOff={distanceOff}
          clickedBlockData={clickedBlockData}
          onNext={goToNext}
          onZoneGuess={handleZoneGuess}
          map={map}
        />

        {/* Map Container Wrapper */}
        <div className="flex-grow h-full relative flex flex-col bg-slate-900 min-w-0">
          <MapContainer 
              center={[49.28, -122.80]} 
              zoom={12} 
              style={{ height: "100%", width: "100%" }} 
              className="bg-slate-900" zoomControl={false} maxZoom={22} ref={setMap}
          >
            {/* 1. BASE MAP (z-index 200) */}
            <BaseMap style={mapStyle} />
            
            <CoquitlamOverlays visible={showLabels} />
            
            {/* Hydrants Visual GIS Overlay */}
            <HydrantsLayer visible={showHydrants} />
            
            {/* 2. DEFINE CUSTOM PANES */}
            <Pane name="underlayPane" style={{ zIndex: 390 }} />
            <Pane name="labelsPane" style={{ zIndex: 410 }} />
            
            {/* 3. LAYERS ASSIGNED TO PANES */}
            
            {/* "Top Bun" - The Text Labels */}
            <FireZonesLayer 
                visible={gameMode === "QUIZ_ZONES" || (gameMode === "EXPLORE" && showZones)} 
                pane="labelsPane" 
            />
            
            {/* "Bottom Bun" - The Highlight */}
            {(gameMode === "QUIZ_ZONES" || (gameMode === "EXPLORE" && showZones)) && zones.map((zone) => (
              <Polygon 
                  key={zone.zone_id} 
                  positions={zone.geometry.coordinates[0].map(c => [c[1], c[0]])} 
                  pathOptions={getZoneStyle(zone)} 
                  pane="underlayPane" 
              />
            ))}

            {/* HIDE STATIONS IN QUIZ MODE */}
            {gameMode !== "QUIZ_ZONES" && <StationsLayer />}
            
            <MapClickEvents onMapClick={handleMapClick} />
            
            {!feedback && currentQuestion && (
               <SmartZoom target={currentQuestion} mode={gameMode} allBlocks={blocks} allZones={zones} />
            )}
            {feedback === "WRONG" && gameMode === "QUIZ_BLOCKS" && clickedBlockData && (
               <ZoomToFeedback guessBlock={clickedBlockData} targetBlock={blocks.find(b => b.block === currentQuestion.block && b.street === currentQuestion.street)} mode={gameMode} />
            )}

            {/* GAME VISUALS: BLOCKS */}
            {gameMode === "QUIZ_BLOCKS" && currentQuestion && blocks && blocks.length > 0 && 
              blocks.map((block, i) => (
                  <Polyline 
                      key={`${block.street}-${block.block}-${i}`} 
                      positions={block.coordinates} 
                      eventHandlers={{ 
                          click: (e) => { L.DomEvent.stopPropagation(e); handleBlockClick(block); },
                          mouseover: (e) => { 
                              if (!feedback) {
                                  e.target.setStyle({ color: "#f59e0b", weight: 10, opacity: 1 });
                                  e.target.bringToFront();
                              }
                          },
                          mouseout: (e) => { 
                              e.target.setStyle(getBlockStyle(block)); 
                          }
                      }} 
                      pathOptions={getBlockStyle(block)}
                  >
                      <Tooltip sticky direction="top" className="font-bold text-xs bg-slate-900 text-white border-0">
                          {feedback ? `${block.block} ${block.street}` : "Block ???"}
                      </Tooltip>
                  </Polyline>
            ))}

            {/* GAME VISUALS: PINS */}
            {(gameMode === "QUIZ_INTERSECTIONS" || gameMode === "QUIZ_ADDRESSES") && userGuess && (
               <>
                  <CircleMarker center={userGuess} radius={6} pathOptions={{ color: "white", fillColor: feedback === "PERFECT" ? "#22c55e" : "#ef4444", fillOpacity: 1, weight: 2 }} />
                  {feedback !== "PERFECT" && (
                      <>
                          <CircleMarker center={[currentQuestion.lat, currentQuestion.lng]} radius={6} pathOptions={{ color: "white", fillColor: "#22c55e", fillOpacity: 1, weight: 2 }} />
                          <Polyline positions={[userGuess, [currentQuestion.lat, currentQuestion.lng]]} pathOptions={{ color: "#ef4444", dashArray: '10, 10', weight: 2, opacity: 0.8 }} />
                      </>
                  )}
               </>
            )}

            {/* ROAD CLOSURES LAYER */}
            {showRoadClosures && activeClosures.map((closure, i) => {
              let color = "#ef4444"; // NO_ACCESS
              if (closure.emergencyAccess === "ACCESS_ONLY") color = "#f59e0b"; // ACCESS_ONLY
              if (closure.emergencyAccess === "CAUTION") color = "#eab308"; // CAUTION
              
              return (
                <React.Fragment key={closure.id || i}>
                  {closure.polyline && closure.polyline.length > 0 && (
                    <Polyline 
                      positions={closure.polyline} 
                      pathOptions={{ 
                        color: color, 
                        weight: 6, 
                        dashArray: "10, 10", 
                        opacity: 0.85 
                      }} 
                    />
                  )}
                  <Marker 
                    position={closure.coordinates} 
                    icon={closureIcon}
                  >
                    <Popup className="road-closure-popup">
                      <div className="bg-slate-950 text-white p-2.5 border border-slate-800 rounded-md" style={{ minWidth: '220px', maxWidth: '260px' }}>
                        <div className="flex justify-between items-center gap-2">
                          <span className={`px-1.5 py-0.5 rounded text-[8px] font-black tracking-wider ${
                            closure.emergencyAccess === 'NO_ACCESS' ? 'bg-red-500/20 text-red-400 border border-red-500/30' :
                            closure.emergencyAccess === 'ACCESS_ONLY' ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30' :
                            'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30'
                          }`}>
                            {closure.emergencyAccess === 'NO_ACCESS' ? 'NO EMERGENCY ACCESS' :
                             closure.emergencyAccess === 'ACCESS_ONLY' ? 'EMERGENCY ACCESS ONLY' :
                             'PASSABLE WITH CAUTION'}
                          </span>
                          <span className="text-[9px] text-slate-550 font-mono font-medium">{closure.source}</span>
                        </div>
                        <h3 className="font-bold text-sm text-slate-200 mt-2 leading-tight">{closure.headline}</h3>
                        <p className="text-[9px] text-slate-400 font-mono mt-0.5 font-semibold">{closure.street}</p>
                        <p className="text-xs text-slate-350 mt-2 font-sans leading-relaxed border-t border-slate-900 pt-1.5">{closure.description}</p>
                      </div>
                    </Popup>
                  </Marker>
                </React.Fragment>
              );
            })}

            {/* Active Target Address Marker & Suggested Route Overlay */}
            {gameMode === "EXPLORE" && targetAddress && (
              <>
                {targetPolygon ? (
                  <Polygon 
                    positions={targetPolygon} 
                    pathOptions={{ 
                      color: '#4f46e5', 
                      fillColor: '#818cf8', 
                      fillOpacity: 0.35, 
                      weight: 3 
                    }}
                  >
                    <Popup className="target-address-popup">
                      <div className="bg-slate-950 text-white p-3 border border-slate-800 rounded-md" style={{ minWidth: '220px', maxWidth: '260px' }}>
                        <div className="flex justify-between items-center gap-2">
                          <span className="text-[9px] text-slate-400 font-mono font-medium">SEARCH TARGET</span>
                          <span className="text-emerald-400 text-[9px] font-bold tracking-wider">ACTIVE ROUTE</span>
                        </div>
                        <h3 className="font-bold text-sm text-sky-400 mt-2 leading-tight">{targetAddress.address}</h3>
                        <p className="text-[9px] text-slate-450 font-mono mt-0.5 font-semibold">Coquitlam, BC</p>
                        
                        {nearestHydrant && (
                          <div className="mt-2.5 pt-2 border-t border-slate-900 flex flex-col gap-1">
                            <span className="text-[8px] text-sky-400 font-extrabold uppercase tracking-wider font-mono">💧 Nearest Hydrant</span>
                            <div className="flex justify-between text-xs mt-0.5">
                              <span className="text-slate-400">ID / Distance</span>
                              <span className="text-white font-mono font-bold">{nearestHydrant.gisId} ({nearestHydrant.distance}m)</span>
                            </div>
                            {nearestHydrant.flowClass && (
                              <div className="flex justify-between text-xs">
                                <span className="text-slate-400">Flow Rating</span>
                                <span className="text-sky-400 font-mono font-bold">{nearestHydrant.flowClass}</span>
                              </div>
                            )}
                          </div>
                        )}

                        <div className="mt-3 pt-2 border-t border-slate-900">
                          <a 
                            href={`https://www.google.com/maps/dir/?api=1&origin=${STATIONS[homeHall][0]},${STATIONS[homeHall][1]}&destination=${targetAddress.lat},${targetAddress.lng}&travelmode=driving`}
                            target="_blank" 
                            rel="noopener noreferrer"
                            className="bg-indigo-650 hover:bg-indigo-600 text-white font-extrabold py-2 px-4 rounded-lg text-xs flex items-center justify-center gap-1.5 transition-all text-center w-full shadow-md border border-indigo-500"
                          >
                            🚙 NAVIGATE (GPS)
                          </a>
                        </div>
                      </div>
                    </Popup>
                  </Polygon>
                ) : (
                  <Marker 
                    position={[targetAddress.lat, targetAddress.lng]} 
                    icon={targetIcon}
                  >
                    <Popup className="target-address-popup">
                      <div className="bg-slate-950 text-white p-3 border border-slate-800 rounded-md" style={{ minWidth: '220px', maxWidth: '260px' }}>
                        <div className="flex justify-between items-center gap-2">
                          <span className="text-[9px] text-slate-400 font-mono font-medium">SEARCH TARGET</span>
                          <span className="text-emerald-400 text-[9px] font-bold tracking-wider">ACTIVE ROUTE</span>
                        </div>
                        <h3 className="font-bold text-sm text-sky-400 mt-2 leading-tight">{targetAddress.address}</h3>
                        <p className="text-[9px] text-slate-450 font-mono mt-0.5 font-semibold">Coquitlam, BC</p>
                        
                        {nearestHydrant && (
                          <div className="mt-2.5 pt-2 border-t border-slate-900 flex flex-col gap-1">
                            <span className="text-[8px] text-sky-400 font-extrabold uppercase tracking-wider font-mono">💧 Nearest Hydrant</span>
                            <div className="flex justify-between text-xs mt-0.5">
                              <span className="text-slate-400">ID / Distance</span>
                              <span className="text-white font-mono font-bold">{nearestHydrant.gisId} ({nearestHydrant.distance}m)</span>
                            </div>
                            {nearestHydrant.flowClass && (
                              <div className="flex justify-between text-xs">
                                <span className="text-slate-400">Flow Rating</span>
                                <span className="text-sky-400 font-mono font-bold">{nearestHydrant.flowClass}</span>
                              </div>
                            )}
                          </div>
                        )}

                        <div className="mt-3 pt-2 border-t border-slate-900">
                          <a 
                            href={`https://www.google.com/maps/dir/?api=1&origin=${STATIONS[homeHall][0]},${STATIONS[homeHall][1]}&destination=${targetAddress.lat},${targetAddress.lng}&travelmode=driving`}
                            target="_blank" 
                            rel="noopener noreferrer"
                            className="bg-indigo-650 hover:bg-indigo-600 text-white font-extrabold py-2 px-4 rounded-lg text-xs flex items-center justify-center gap-1.5 transition-all text-center w-full shadow-md border border-indigo-500"
                          >
                            🚙 NAVIGATE (GPS)
                          </a>
                        </div>
                      </div>
                    </Popup>
                  </Marker>
                )}

                {nearestHydrant && (
                  <>
                    {/* Dashed Tracer Line from Target Address to Closest Hydrant */}
                    <Polyline 
                      positions={[
                        [targetAddress.lat, targetAddress.lng],
                        [nearestHydrant.lat, nearestHydrant.lng]
                      ]} 
                      pathOptions={{ 
                        color: '#06b6d4', 
                        weight: 3, 
                        dashArray: '5, 10', 
                        opacity: 0.8 
                      }} 
                    />
                    
                    {/* Glowing outline around the closest hydrant */}
                    <CircleMarker 
                      center={[nearestHydrant.lat, nearestHydrant.lng]} 
                      radius={16} 
                      pathOptions={{ 
                        color: '#06b6d4', 
                        fillColor: '#22d3ee', 
                        fillOpacity: 0.15, 
                        weight: 2,
                        className: 'animate-pulse' 
                      }} 
                    >
                      <Tooltip direction="top" className="font-bold text-xs bg-slate-950 text-white border border-slate-800 p-2 shadow-xl">
                        <div className="flex flex-col gap-0.5" style={{ minWidth: '120px' }}>
                          <span className="text-[9px] text-cyan-400 uppercase font-mono tracking-wider">NEAREST HYDRANT</span>
                          <span className="text-white text-sm font-bold">{nearestHydrant.gisId}</span>
                          <span className="text-slate-400 text-[10px] mt-1 font-mono">Distance: {nearestHydrant.distance}m</span>
                          {nearestHydrant.flowClass && (
                            <span className="text-sky-400 text-xs font-semibold">Flow Class: {nearestHydrant.flowClass}</span>
                          )}
                        </div>
                      </Tooltip>
                    </CircleMarker>
                  </>
                )}

                {STATIONS[homeHall] && (
                  <RoutingOverlay 
                    from={STATIONS[homeHall]} 
                    to={[targetAddress.lat, targetAddress.lng]} 
                  />
                )}
              </>
            )}
          </MapContainer>

          {/* APPLICATION VERSION & COMPILE TIMESTAMP WATERMARK */}
          <div className="absolute bottom-3 left-3 z-[1000] pointer-events-none font-mono text-[9px] text-slate-400/85 drop-shadow-sm select-none">
            CFR EVO APP | BUILD: {buildTime}
          </div>
        </div>

        {/* Right Sidebar Alerts Panel */}
        <RightSidebar 
          rightSidebarOpen={rightSidebarOpen}
          setRightSidebarOpen={setRightSidebarOpen}
          gameMode={gameMode}
          roadClosures={roadClosures}
          showRoadClosures={showRoadClosures}
          filterNoAccess={filterNoAccess}
          filterAccessOnly={filterAccessOnly}
          filterCaution={filterCaution}
          map={map}
        />
      </div>
    </div>
  );
}