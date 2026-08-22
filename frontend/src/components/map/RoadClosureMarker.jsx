import React, { useEffect, useRef } from 'react';
import { Marker, Polyline, Popup } from 'react-leaflet';
import { closureIcon } from './mapIcons';

/**
 * Marker + polyline for one road closure, with popup-on-selection behaviour.
 *
 * Extracted from MapBoard.jsx unchanged apart from its imports. It owns a ref and an
 * effect, so it is a real component rather than a helper, and it was the largest
 * self-contained block in that file.
 */

// 🚧 Sub-component to manage openPopup on selection
function RoadClosureMarker({ closure, isSelected, onSelect }) {
  const markerRef = useRef(null);

  useEffect(() => {
    if (isSelected && markerRef.current) {
      const timer = setTimeout(() => {
        if (markerRef.current) {
          markerRef.current.openPopup();
        }
      }, 300);
      return () => clearTimeout(timer);
    }
  }, [isSelected]);

  let color = "#ef4444"; // NO_ACCESS
  if (closure.emergencyAccess === "ACCESS_ONLY") color = "#f59e0b"; // ACCESS_ONLY
  if (closure.emergencyAccess === "CAUTION") color = "#eab308"; // CAUTION

  const polylinePos = Array.isArray(closure.polyline) && closure.polyline.length > 0
    ? closure.polyline.map(pt => [parseFloat(pt[0]), parseFloat(pt[1])])
    : [];

  // No default coordinate (CLAUDE.md 6.1). A closure with no usable point coordinate
  // previously rendered its marker at COQUITLAM_CENTER, which drew a road closure across
  // City Centre that the municipal feed never reported. Fall back only to the first
  // vertex of the closure's own polyline -- real data from the same record -- and
  // otherwise render no marker at all. The polyline alone still shows the closure.
  const markerPos = Array.isArray(closure.coordinates) && closure.coordinates.length >= 2
    ? [parseFloat(closure.coordinates[0]), parseFloat(closure.coordinates[1])]
    : (polylinePos.length > 0 ? polylinePos[0] : null);

  return (
    <React.Fragment>
      {polylinePos.length > 0 && (
        <Polyline 
          positions={polylinePos} 
          pathOptions={{ 
            color: color, 
            weight: 6, 
            dashArray: "10, 10", 
            opacity: 0.85 
          }} 
        />
      )}
      {markerPos && (
      <Marker 
        ref={markerRef}
        position={markerPos} 
        icon={closureIcon}
        eventHandlers={{
          click: () => {
            onSelect(closure);
          }
        }}
      >
        <Popup className="road-closure-popup" onClose={() => {
          if (isSelected) onSelect(null);
        }}>
          <div className="bg-slate-950 text-white p-2.5 border border-slate-800 rounded-md" style={{ minWidth: '220px', maxWidth: '260px' }}>
            <div className="flex justify-between items-center gap-2">
              <span className={`px-1.5 py-0.5 rounded text-[8px] font-black tracking-wider ${
                closure.emergencyAccess === 'NO_ACCESS' ? 'bg-red-500/20 text-red-400 border border-red-500/30' :
                closure.emergencyAccess === 'ACCESS_ONLY' ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30' :
                'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30'
              }`}>
                {closure.emergencyAccess === 'NO_ACCESS' ? 'FULL CLOSURE' :
                 closure.emergencyAccess === 'ACCESS_ONLY' ? 'EMERGENCY ACCESS ONLY' :
                 'LANE CLOSURE'}
              </span>
              <span className="text-[9px] text-slate-550 font-mono font-medium">{closure.source}</span>
            </div>
            <h3 className="font-bold text-sm text-slate-200 mt-2 leading-tight">{closure.headline}</h3>
            <p className="text-[9px] text-slate-400 font-mono mt-0.5 font-semibold">{closure.street}</p>
            {(closure.affectedZones?.length > 0 || closure.zoneId) && (
              <div className="mt-1.5 pt-1 border-t border-slate-900 flex justify-between items-center text-[9px] font-mono">
                <span className="text-slate-400 font-medium">📍 Impacted Zones</span>
                <span className="bg-sky-950 text-sky-300 border border-sky-800/80 px-1.5 py-0.5 rounded font-black">
                  {closure.affectedZones?.length > 0 
                    ? `Zone ${closure.affectedZones.join(", ")}` 
                    : `Zone ${closure.zoneId}`}
                </span>
              </div>
            )}

            {closure.startDate && (
              <p className="text-[9px] text-sky-400/90 font-mono mt-1 flex items-center gap-1 font-bold">
                📅 {closure.endDate ? (
                  `${new Date(closure.startDate).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })} - ${new Date(closure.endDate).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}`
                ) : (
                  `Started ${new Date(closure.startDate).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })} (Until Further Notice)`
                )}
              </p>
            )}
            <p className="text-xs text-slate-350 mt-2 font-sans leading-relaxed border-t border-slate-900 pt-1.5 whitespace-pre-line overflow-y-auto pr-1 scrollbar-thin scrollbar-thumb-slate-800 scrollbar-track-transparent" style={{ whiteSpace: 'pre-line', maxHeight: '200px' }}>{closure.description}</p>
          </div>
        </Popup>

      </Marker>
      )}
    </React.Fragment>
  );
}


// 🎯 Custom Target Address Icon

export default RoadClosureMarker;
