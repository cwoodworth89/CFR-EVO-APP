/* global __BUILD_DATE__ */
import React, { useEffect, useState, useRef, useCallback } from 'react'; // Added useRef and useCallback
import { MapContainer, Polygon, CircleMarker, Polyline, Tooltip, Pane, Marker, Popup } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import * as turf from '@turf/turf';
import L from 'leaflet';

// Import from your other components
import { BaseMap, CoquitlamOverlays, StationsLayer, FireZonesLayer, HydrantsLayer } from './MapLayers';
import { MapClickEvents, SmartZoom, ZoomToFeedback } from './MapActions';
import { Header, Sidebar } from './GameHUD';
import { MODE_DEFAULTS, UNIT_COLORS } from './MapConstants';

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
  const [showLabels, setShowLabels] = useState(false); 
  const [showHydrants, setShowHydrants] = useState(false); 
  const [showZones, setShowZones] = useState(false); 
  const [showRoadClosures, setShowRoadClosures] = useState(false); 
  
  const [currentQuestion, setCurrentQuestion] = useState(null);
  const [score, setScore] = useState(0);
  const [feedback, setFeedback] = useState(null);
  
  const [userGuess, setUserGuess] = useState(null);
  const [distanceOff, setDistanceOff] = useState(0); 
  const [clickedBlockData, setClickedBlockData] = useState(null);

  // ⏱️ TIMER REF (Prevents double-skipping if you hit Enter while waiting)
  const autoAdvanceTimer = useRef(null);

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
            
            return {
              id: evt.id || Math.random().toString(),
              headline: evt.headline || "TRAFFIC ALERT",
              street: evt.road_name || "Regional Road",
              severity: (evt.severity || "MINOR").toUpperCase(),
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
    // We use import.meta.env.BASE_URL to automatically add '/coquitlam-fire-trainer/' 
    // when deployed, but keep it as '/' when on localhost.
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
      setMapStyle(MODE_DEFAULTS[mode]); 
      
      // Only show labels automatically for Address Mode
      setShowLabels(mode === "QUIZ_ADDRESSES");
      
      if (mode === "EXPLORE") {
          setShowZones(false);
          setShowHydrants(false);
          setShowRoadClosures(false);
          setCurrentQuestion(null);
      } else {
          // Quiz Modes: Hydrants ON by default, road closures icons ON by default, zones OFF
          setShowHydrants(true);
          setShowRoadClosures(true);
          setShowZones(false);
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

  return (
    <div className="h-screen w-screen flex flex-col bg-slate-900 overflow-hidden">
      
      <Header 
        gameMode={gameMode} score={score} mapStyle={mapStyle} setMapStyle={setMapStyle} 
        startMode={startMode} 
        showLabels={showLabels} setShowLabels={setShowLabels} 
        showHydrants={showHydrants} setShowHydrants={setShowHydrants}
        showZones={showZones} setShowZones={setShowZones}
        showRoadClosures={showRoadClosures} setShowRoadClosures={setShowRoadClosures}
      />

      <div className="flex-grow relative">
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
          {showRoadClosures && roadClosures.map((closure, i) => (
            <Marker 
              key={closure.id || i} 
              position={closure.coordinates} 
              icon={closureIcon}
            >
              <Popup className="road-closure-popup">
                <div className="bg-slate-950 text-white p-2.5 border border-slate-800 rounded-md" style={{ minWidth: '220px', maxWidth: '260px' }}>
                  <div className="flex justify-between items-center gap-2">
                    <span className={`px-1.5 py-0.5 rounded text-[8px] font-bold tracking-wider ${
                      closure.severity === 'MAJOR' ? 'bg-red-500/20 text-red-400 border border-red-500/30' :
                      closure.severity === 'MODERATE' ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30' :
                      'bg-slate-800/60 text-slate-300 border border-slate-700/30'
                    }`}>{closure.severity}</span>
                    <span className="text-[9px] text-slate-400 font-mono font-medium">{closure.source}</span>
                  </div>
                  <h3 className="font-bold text-sm text-amber-500 mt-2 leading-tight">{closure.headline}</h3>
                  <p className="text-[9px] text-slate-400 font-mono mt-0.5 font-semibold">{closure.street}</p>
                  <p className="text-xs text-slate-300 mt-2 font-sans leading-relaxed border-t border-slate-850 pt-1.5">{closure.description}</p>
                </div>
              </Popup>
            </Marker>
          ))}
        </MapContainer>

        {/* APPLICATION VERSION & COMPILE TIMESTAMP WATERMARK */}
        <div className="absolute bottom-3 left-3 z-[1000] pointer-events-none font-mono text-[9px] text-slate-400/85 drop-shadow-sm select-none">
          CFR EVO APP | BUILD: {buildTime}
        </div>

        {/* SIDEBAR */}
        <Sidebar 
            gameMode={gameMode} currentQuestion={currentQuestion} feedback={feedback} 
            distanceOff={distanceOff} clickedBlockData={clickedBlockData} map={map}
            onNext={goToNext} 
            onZoneGuess={handleZoneGuess}
            roadClosures={roadClosures}
            showRoadClosures={showRoadClosures}
        />

      </div>
    </div>
  );
}