import React from 'react';
import { UNIT_COLORS } from './MapConstants';

export function Header({ gameMode, score, mapStyle, setMapStyle, startMode, toggleBlocks, showBlocks }) {
  
  return (
    <div className="bg-slate-950 text-white p-3 shadow-md z-20 flex justify-between items-center border-b border-slate-800 h-16">
        <h1 className="text-lg font-bold tracking-wider">
          FIRST DUE <span className="text-sky-500">TRAINER</span>
        </h1>
        {gameMode !== "EXPLORE" && (
          <div className="font-mono text-sm text-slate-400">
            SCORE: <span className="text-white text-lg">{score}</span>
          </div>
        )}
        
        <div className="flex gap-4 items-center">
          {/* Layer Switcher - Simplified */}
          <div className="flex bg-slate-800 rounded p-1 mr-4 border border-slate-700">
            {['GREY', 'DARK'].map(style => (
                <button 
                  key={style} 
                  onClick={() => setMapStyle(style)} 
                  className={`px-2 py-1 text-[10px] font-bold rounded ${
                    mapStyle === style 
                      ? "bg-slate-600 text-white" 
                      : "text-slate-400 hover:text-white"
                  }`}
                >
                  {style}
                </button>
            ))}
          </div>

          {/* Labels Toggle (Now controls Roads + Addresses + Parcels) */}
          <button 
            onClick={() => toggleBlocks(!showBlocks)} 
            className={`mr-4 px-3 py-1 text-xs font-bold rounded border ${
              showBlocks 
                ? "bg-amber-500 text-black border-amber-600" 
                : "bg-slate-800 text-amber-500 border-amber-900 hover:border-amber-500"
            }`}
          >
            {showBlocks ? "HIDE" : "LABELS"}
          </button>

          {/* Game Mode Buttons */}
          <button onClick={() => startMode("EXPLORE")} className="px-3 py-1 text-xs font-bold rounded bg-slate-700 text-white hover:bg-slate-600">EXPLORE</button>
          <button onClick={() => startMode("QUIZ_ZONES")} className="px-3 py-1 text-xs font-bold rounded bg-slate-800 text-sky-500 border border-sky-900 hover:bg-slate-700">ZONES</button>
          <button onClick={() => startMode("QUIZ_INTERSECTIONS")} className="px-3 py-1 text-xs font-bold rounded bg-slate-800 text-emerald-500 border border-emerald-900 hover:bg-slate-700">INTXN</button>
          <button onClick={() => startMode("QUIZ_BLOCKS")} className="px-3 py-1 text-xs font-bold rounded bg-slate-800 text-amber-500 border border-amber-900 hover:bg-slate-700">BLOCKS</button>
          <button onClick={() => startMode("QUIZ_ADDRESSES")} className="px-3 py-1 text-xs font-bold rounded bg-slate-800 text-purple-400 border border-purple-900 hover:bg-slate-700">ADDRESS</button>
        </div>
    </div>
  );
}

export function Sidebar({ gameMode, currentQuestion, feedback, distanceOff, clickedBlockData, onNext, onZoneGuess, map }) {
    if (!currentQuestion) return null;

    return (
        <div className="absolute top-4 right-4 z-[1000] w-72 bg-slate-900/95 backdrop-blur border border-slate-700 shadow-2xl rounded-xl overflow-hidden flex flex-col pointer-events-auto">
            
            {/* HEADER */}
            <div className="bg-slate-800 p-4 border-b border-slate-700 text-center">
                {gameMode === "QUIZ_ZONES" && (
                  <>
                    <h2 className="text-slate-500 text-[10px] uppercase font-bold">FIRST DUE</h2>
                    <div className="text-3xl text-white font-bold">Zone {currentQuestion.zone_id}</div>
                  </>
                )}
                {gameMode === "QUIZ_INTERSECTIONS" && (
                  <>
                    <div className="text-slate-500 text-[10px] uppercase font-bold">LOCATE</div>
                    <div className="text-xl text-white font-bold">{currentQuestion.name}</div>
                  </>
                )}
                {gameMode === "QUIZ_BLOCKS" && (
                  <>
                    <div className="text-slate-500 text-[10px] uppercase font-bold">FIND THE BLOCK</div>
                    <div className="text-3xl text-amber-500 font-bold leading-tight">{currentQuestion.block}</div>
                    <div className="text-lg text-white font-bold">{currentQuestion.street}</div>
                  </>
                )}
                {gameMode === "QUIZ_ADDRESSES" && (
                  <>
                    <div className="text-slate-500 text-[10px] uppercase font-bold tracking-widest mb-1">FIND ADDRESS</div>
                    <div className="text-xl text-white font-bold leading-tight">{currentQuestion.address}</div>
                  </>
                )}
            </div>

            {/* CONTENT AREA */}
            <div className="p-4">
                {/* ZONE BUTTONS */}
                {gameMode === "QUIZ_ZONES" && (
                    <div className="flex flex-col gap-2">
                        {Object.keys(UNIT_COLORS).filter(u => u !== "UNKNOWN").map((unit) => (
                            <button 
                              key={unit} 
                              onClick={() => onZoneGuess(unit)} 
                              disabled={feedback !== null} 
                              className={`w-full py-3 px-4 rounded-lg font-bold text-left flex justify-between items-center transition-all border-l-4 ${
                                feedback === "WRONG" && unit === currentQuestion.unit_id 
                                  ? "bg-green-600 text-white border-green-300 shadow-inner" 
                                  : "bg-slate-800 text-slate-300 border-transparent hover:bg-slate-700 hover:text-white"
                              }`}
                            >
                                <span>{unit}</span>
                                <span 
                                  className="w-3 h-3 rounded-full shadow-sm" 
                                  style={{ backgroundColor: UNIT_COLORS[unit] }}
                                ></span>
                            </button>
                        ))}
                    </div>
                )}

                {/* FEEDBACK & NEXT BUTTON */}
                {feedback ? (
                    <div className="text-center animate-in fade-in">
                        <div className={`text-4xl font-bold mb-2 ${
                          feedback === "PERFECT" || feedback === "CORRECT" 
                            ? "text-green-400" 
                            : "text-slate-300"
                        }`}>
                            {feedback === "PERFECT" || feedback === "CORRECT" 
                              ? "PERFECT!" 
                              : <span className="text-2xl">OFF BY <span className="text-white">{distanceOff}m</span></span>
                            }
                        </div>
                        
                        {/* Show Picked Block if Wrong */}
                        {gameMode === "QUIZ_BLOCKS" && feedback === "WRONG" && clickedBlockData && (
                            <div className="text-red-400 font-bold text-lg mb-4">
                              Picked: {clickedBlockData.block}
                            </div>
                        )}

                        <button 
                          onClick={onNext} 
                          className="bg-sky-600 hover:bg-sky-500 text-white font-bold py-3 px-6 rounded-lg w-full shadow-lg mt-4"
                        >
                          NEXT &rarr;
                        </button>
                    </div>
                ) : (
                    <div className="text-center text-slate-500 text-xs italic">
                        {gameMode === "QUIZ_INTERSECTIONS" && "Tap the intersection..."}
                        {gameMode === "QUIZ_BLOCKS" && "Click the road segment..."}
                        {gameMode === "QUIZ_ADDRESSES" && "Zoom in & find the house..."}
                    </div>
                )}

                {/* ZOOM BUTTON (Address Mode) */}
                {gameMode === "QUIZ_ADDRESSES" && !feedback && (
                    <button 
                      onClick={() => map.setView([currentQuestion.lat, currentQuestion.lng], 20, { animate: true })} 
                      className="mt-4 bg-slate-700 hover:bg-slate-600 text-xs text-white py-2 px-4 rounded w-full border border-slate-500"
                    >
                      🔍 ZOOM TO PARCEL
                    </button>
                )}
            </div>
        </div>
    );
}