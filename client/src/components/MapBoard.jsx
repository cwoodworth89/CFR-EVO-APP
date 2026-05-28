import React, { useEffect, useState, useRef, useCallback } from 'react'; // Added useRef and useCallback
import { MapContainer, Polygon, CircleMarker, Polyline, Tooltip, Pane } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import * as turf from '@turf/turf';
import L from 'leaflet';

// Import from your other components
import { BaseMap, CoquitlamOverlays, StationsLayer, FireZonesLayer } from './MapLayers';
import { MapClickEvents, SmartZoom, ZoomToFeedback } from './MapActions';
import { Header, Sidebar } from './GameHUD';
import { MODE_DEFAULTS, UNIT_COLORS } from './MapConstants';

// 🎲 Pure utility function to pick a random element, satisfying React 19 render purity rules
const getRandomElement = (arr) => {
  if (!arr || arr.length === 0) return null;
  return arr[Math.floor(Math.random() * arr.length)];
};

export default function MapBoard() {
  const [map, setMap] = useState(null);

  // DATA STATE
  const [zones, setZones] = useState([]);
  const [intersections, setIntersections] = useState([]);
  const [blocks, setBlocks] = useState([]);
  const [addresses, setAddresses] = useState([]);
  
  // GAME STATE
  const [gameMode, setGameMode] = useState("EXPLORE"); 
  const [mapStyle, setMapStyle] = useState("GREY"); 
  const [showLabels, setShowLabels] = useState(false); 
  
  const [currentQuestion, setCurrentQuestion] = useState(null);
  const [score, setScore] = useState(0);
  const [feedback, setFeedback] = useState(null);
  
  const [userGuess, setUserGuess] = useState(null);
  const [distanceOff, setDistanceOff] = useState(0); 
  const [clickedBlockData, setClickedBlockData] = useState(null);

  // ⏱️ TIMER REF (Prevents double-skipping if you hit Enter while waiting)
  const autoAdvanceTimer = useRef(null);

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
    const diff = Math.abs(currentQuestion.block - blockData.block);
    
    if (diff === 0) { 
        setFeedback("PERFECT"); 
        setScore(s => s + 1); 
        // Auto-advance
        autoAdvanceTimer.current = setTimeout(nextBlockQuestion, 1500); 
    }
    else { setFeedback("WRONG"); setDistanceOff(diff); }
  }, [currentQuestion, gameMode, feedback, nextBlockQuestion]);

  // --- RENDER HELPERS ---
  const getBlockStyle = (block) => {
    if (!feedback) return { color: mapStyle === "ORTHO" ? "#38bdf8" : "#64748b", weight: 8, opacity: 0.9 }; 
    const isTarget = block.block === currentQuestion.block;
    const isClicked = clickedBlockData && block.block === clickedBlockData.block;
    if (isTarget) return { color: "#22c55e", weight: 14, opacity: 1 }; 
    if (isClicked) return { color: "#ef4444", weight: 14, opacity: 1 }; 
    return { color: "#94a3b8", weight: 4, opacity: 0.2 }; 
  };

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
        startMode={startMode} toggleBlocks={setShowLabels} showBlocks={showLabels} 
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
          
          {/* 2. DEFINE CUSTOM PANES */}
          <Pane name="underlayPane" style={{ zIndex: 390 }} />
          <Pane name="labelsPane" style={{ zIndex: 410 }} />
          
          {/* 3. LAYERS ASSIGNED TO PANES */}
          
          {/* "Top Bun" - The Text Labels */}
          <FireZonesLayer 
              visible={gameMode === "EXPLORE" || gameMode === "QUIZ_ZONES"} 
              pane="labelsPane" 
          />
          
          {/* "Bottom Bun" - The Highlight */}
          {gameMode === "QUIZ_ZONES" && zones.map((zone) => (
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
            blocks.filter(b => b.street === currentQuestion.street).map((block, i) => (
                <Polyline 
                    key={`${block.street}-${block.block}-${i}`} 
                    positions={block.coordinates} 
                    eventHandlers={{ click: (e) => { L.DomEvent.stopPropagation(e); handleBlockClick(block); } }} 
                    pathOptions={getBlockStyle(block)}
                >
                    <Tooltip sticky direction="top" className="font-bold text-xs bg-slate-900 text-white border-0">{feedback ? `Block ${block.block}` : "Block ???"}</Tooltip>
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
        </MapContainer>

        {/* SIDEBAR */}
        <Sidebar 
            gameMode={gameMode} currentQuestion={currentQuestion} feedback={feedback} 
            distanceOff={distanceOff} clickedBlockData={clickedBlockData} map={map}
            onNext={goToNext} 
            onZoneGuess={handleZoneGuess}
        />

      </div>
    </div>
  );
}