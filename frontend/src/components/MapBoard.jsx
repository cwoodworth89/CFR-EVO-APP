/* global __BUILD_DATE__ */
import React, { useEffect, useState, useRef, useCallback, useMemo } from 'react'; // Added useRef, useCallback, useMemo
import { MapContainer, Polygon, CircleMarker, Polyline, Tooltip, Pane, Marker, Popup } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import * as turf from '@turf/turf';
import L from 'leaflet';

// Import from your other components
import { BaseMap, CoquitlamOverlays, StationsLayer, FireZonesLayer, HydrantsLayer, CranesLayer } from './MapLayers';
import { MapClickEvents, SmartZoom, ZoomToFeedback } from './MapActions';
import { Header, LeftSidebar, RightSidebar } from './DashboardHUD';
import { MODE_DEFAULTS, UNIT_COLORS, STATIONS_MAP as STATIONS } from './MapConstants';

import { RoutingOverlay } from './RoutingOverlay';
import DispatchReview from './DispatchReview';
import { supabase } from '../supabaseClient';

// 🎲 Pure utility function to pick a random element, satisfying React 19 render purity rules
const getRandomElement = (arr) => {
  if (!arr || arr.length === 0) return null;
  return arr[Math.floor(Math.random() * arr.length)];
};

// 🗺️ GeometryDecoder decodes Municipal 511 encoded coordinates sequentially
class GeometryDecoder {
  constructor(encoded) {
    this.points = [];
    this.index = 0;
    if (!encoded) return;
    let u = 0;
    const c = encoded.length;
    let f = 0;
    let e = 0;
    while (u < c) {
      let r = 0;
      let t = 0;
      let i;
      do {
        i = encoded.charCodeAt(u++) - 63;
        t |= (i & 31) << r;
        r += 5;
      } while (i >= 32);
      const o = (t & 1) !== 0 ? ~(t >> 1) : t >> 1;
      f += o;

      r = 0;
      t = 0;
      do {
        i = encoded.charCodeAt(u++) - 63;
        t |= (i & 31) << r;
        r += 5;
      } while (i >= 32);
      const s = (t & 1) !== 0 ? ~(t >> 1) : t >> 1;
      e += s;

      this.points.push([f / 1e5, e / 1e5]);
    }
  }

  getNPoints(n) {
    const pts = this.points.slice(this.index, this.index + n);
    this.index += n;
    return pts;
  }
}

// helper for road closure type names from Municipal 511
const getClosureTypeName = (bit) => {
  switch (bit) {
    case 1: return "Detour";
    case 8: return "Sidewalk Closed";
    case 16: return "Bike Lane Closed";
    case 32:
    case 256:
    case 512: return "Lane(s) Closed";
    case 2048: return "Alternating Traffic";
    case 8192: return "One Direction Closed";
    case 16384: return "Road Closed - Local Traffic Only";
    case 32768:
    case 65536: return "Road Closed - Emergency Access Only";
    case 131072: return "Intermittent Blockage";
    case 262144: return "Road Closed - No Emergency Access";
    default: return "";
  }
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

  return (
    <React.Fragment>
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
        ref={markerRef}
        position={closure.coordinates} 
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
            {closure.startDate && (
              <p className="text-[9px] text-sky-400/90 font-mono mt-1 flex items-center gap-1 font-bold">
                📅 {closure.endDate ? (
                  `${new Date(closure.startDate).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })} - ${new Date(closure.endDate).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}`
                ) : (
                  `Started ${new Date(closure.startDate).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}`
                )}
              </p>
            )}
            <p className="text-xs text-slate-350 mt-2 font-sans leading-relaxed border-t border-slate-900 pt-1.5 whitespace-pre-line overflow-y-auto pr-1 scrollbar-thin scrollbar-thumb-slate-800 scrollbar-track-transparent" style={{ whiteSpace: 'pre-line', maxHeight: '200px' }}>{closure.description}</p>
          </div>
        </Popup>
      </Marker>
    </React.Fragment>
  );
}


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

// 🏠 Find the Alpha side segment of a parcel boundary (clockwise ordering)
// rings: targetAddress.rings[0], referencePt: [lng, lat] (from route end or fallback)
function getAlphaSegment(rings, referencePt) {
  if (!rings || rings.length < 2) return null;
  
  const refPt = turf.point(referencePt);
  let minDistance = Infinity;
  let alphaSeg = null;
  
  for (let i = 0; i < rings.length - 1; i++) {
    const p1 = rings[i];
    const p2 = rings[i+1];
    const segment = turf.lineString([p1, p2]);
    const dist = turf.pointToLineDistance(refPt, segment, { units: 'meters' });
    if (dist < minDistance) {
      minDistance = dist;
      alphaSeg = segment;
    }
  }
  return alphaSeg;
}

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
  const [selectedClosure, setSelectedClosure] = useState(null);
  
  // APP/TERMINAL STATE
  const [appMode, setAppMode] = useState("EXPLORE"); 
  const [activeDispatch, setActiveDispatch] = useState(null);
  const [trainingDataLoaded, setTrainingDataLoaded] = useState(false);
  const [loadingTraining, setLoadingTraining] = useState(false);
  const [mapStyle, setMapStyle] = useState("GREY"); 
  const [showLabels, setShowLabels] = useState(true); 
  const [showHydrants, setShowHydrants] = useState(true); 
  const [showZones, setShowZones] = useState(false); 
  const [showRoadClosures, setShowRoadClosures] = useState(true); 
  const [showCranes, setShowCranes] = useState(false); 
  const [cadastralError, setCadastralError] = useState(false); 
  
  // COLLAPSIBLE SIDEBAR STATES
  const [leftSidebarOpen, setLeftSidebarOpen] = useState(true);
  const [rightSidebarOpen, setRightSidebarOpen] = useState(false);

  // NAVIGATION & ROUTING STATES
  const [homeHall, setHomeHall] = useState(() => {
    return localStorage.getItem('home_hall') || "1";
  });
  const [targetAddress, setTargetAddress] = useState(null);
  const [targetPolygon, setTargetPolygon] = useState(null);
  const [allNearbyHydrants, setAllNearbyHydrants] = useState([]);
  const [routeCoordinates, setRouteCoordinates] = useState([]);
  const [allHydrantsData, setAllHydrantsData] = useState([]);

  // Load all hydrants data and fire zones once on mount
  useEffect(() => {
    fetch('/data/hydrants.json')
      .then(r => r.ok ? r.json() : [])
      .then(data => {
        setAllHydrantsData(data);
      })
      .catch(err => {
        console.error("Failed to load local cached hydrants database:", err);
      });

    // Fetch zones on startup for offline map overlay
    const baseUrl = import.meta.env.BASE_URL;
    fetch(`${baseUrl}data/zones.json?v=2`)
      .then(r => r.ok ? r.json() : [])
      .then(data => {
        setZones(data);
      })
      .catch(err => {
        console.error("Failed to load zones at startup:", err);
      });
  }, []);

  const updateTargetAddress = useCallback((addr) => {
    setTargetAddress(addr);
    if (addr && addr.rings) {
      const leafletPolygon = addr.rings.map(ring => 
        ring.map(coord => [coord[1], coord[0]])
      );
      setTargetPolygon(leafletPolygon);
    } else {
      setTargetPolygon(null);
    }
    setAllNearbyHydrants([]);
    setRouteCoordinates([]);
  }, []);

  useEffect(() => {
    localStorage.setItem('home_hall', homeHall);
  }, [homeHall]);

  // Subscribe to live dispatches from Supabase
  useEffect(() => {
    const channel = supabase
      .channel('live-calls-realtime-map')
      .on(
        'postgres_changes',
        { event: '*', schema: 'public', table: 'live_calls' },
        (payload) => {
          console.log("Realtime Dispatch Event:", payload);
          if (payload.eventType === 'INSERT') {
            const newCall = payload.new;
            if (newCall) {
              setActiveDispatch(newCall);
              const target = newCall.target || (newCall.address ? { address: newCall.address, lat: newCall.latitude || 49.28, lng: newCall.longitude || -122.80 } : null);
              if (target) {
                updateTargetAddress(target);
                if (map && target.lat && target.lng) {
                  map.flyTo([target.lat, target.lng], 17, { animate: true });
                }
              }
              setLeftSidebarOpen(true);
              setRightSidebarOpen(false);
            }
          } else if (payload.eventType === 'UPDATE') {
            const updatedCall = payload.new;
            setActiveDispatch(curr => {
              if (curr && curr.id === updatedCall.id) {
                const oldTarget = curr.target;
                const newTarget = updatedCall.target;
                if (newTarget && (!oldTarget || oldTarget.lat !== newTarget.lat || oldTarget.lng !== newTarget.lng)) {
                  updateTargetAddress(newTarget);
                  if (map && newTarget.lat && newTarget.lng) {
                    map.flyTo([newTarget.lat, newTarget.lng], 17, { animate: true });
                  }
                }
                return updatedCall;
              }
              return curr;
            });
          } else if (payload.eventType === 'DELETE') {
            const deletedCall = payload.old;
            setActiveDispatch(curr => {
              if (curr && curr.id === deletedCall.id) {
                updateTargetAddress(null);
                return null;
              }
              return curr;
            });
          }
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, [map, updateTargetAddress]);

  // Query Nearby Hydrants on targetAddress change (using local in-memory dataset)
  useEffect(() => {
    if (!targetAddress || allHydrantsData.length === 0) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setAllNearbyHydrants(prev => prev.length > 0 ? [] : prev);
      return;
    }

    const lat = targetAddress.lat;
    const lng = targetAddress.lng;
    const centerPoint = turf.point([lng, lat]);

    try {
      // Filter hydrants within 300m (0.3 km)
      const nearby = allHydrantsData
        .map(h => {
          const hydPoint = turf.point([h.lng, h.lat]);
          const distKm = turf.distance(centerPoint, hydPoint, { units: 'kilometers' });
          const distM = Math.round(distKm * 1000);
          return { ...h, distM };
        })
        .filter(h => h.distM <= 300)
        .map(h => ({
          gisId: h.gisId,
          lat: h.lat,
          lng: h.lng,
          flowClass: h.flowClass,
          status: h.status
        }));

      setAllNearbyHydrants(nearby);
    } catch (e) {
      console.warn("Failed to filter nearby hydrants locally:", e);
      setAllNearbyHydrants(prev => prev.length > 0 ? [] : prev);
    }
  }, [targetAddress, allHydrantsData]);

  // Filter and sort nearby hydrants dynamically with Alpha-segment logic
  const nearestHydrants = useMemo(() => {
    if (allNearbyHydrants.length === 0 || !targetAddress) return [];

    const fromPoint = turf.point([targetAddress.lng, targetAddress.lat]);

    // Try to construct parcel boundary components
    let parcelLine = null;
    let ringCoords = null;
    if (targetAddress.rings && targetAddress.rings.length > 0) {
      try {
        ringCoords = targetAddress.rings[0];
        if (ringCoords.length >= 2) {
          parcelLine = turf.lineString(ringCoords);
        }
      } catch (e) {
        console.warn("Could not construct parcel boundary line for hydrant calculations:", e);
      }
    }

    // Determine target frontage reference point if route is loaded
    let commonFrontagePt = null;
    if (routeCoordinates && routeCoordinates.length > 0) {
      const lastRouteCoord = routeCoordinates[routeCoordinates.length - 1];
      commonFrontagePt = [lastRouteCoord.lng, lastRouteCoord.lat];
    }

    // Process each hydrant to compute distances to Alpha line
    const hydrantsWithDistances = allNearbyHydrants.map(hyd => {
      const toPoint = turf.point([hyd.lng, hyd.lat]);
      let distance;

      if (ringCoords && ringCoords.length >= 2) {
        // Find Alpha segment closest to either the common frontage (route end) or this hydrant itself
        const refPt = commonFrontagePt || [hyd.lng, hyd.lat];
        const alphaSeg = getAlphaSegment(ringCoords, refPt);
        
        if (alphaSeg) {
          distance = Math.round(turf.pointToLineDistance(toPoint, alphaSeg, { units: 'meters' }));
        } else if (parcelLine) {
          distance = Math.round(turf.pointToLineDistance(toPoint, parcelLine, { units: 'meters' }));
        } else {
          distance = Math.round(turf.distance(fromPoint, toPoint, { units: 'kilometers' }) * 1000);
        }
      } else {
        distance = Math.round(turf.distance(fromPoint, toPoint, { units: 'kilometers' }) * 1000);
      }

      return {
        ...hyd,
        distance
      };
    });

    // Sort by Alpha distance
    hydrantsWithDistances.sort((a, b) => a.distance - b.distance);

    // Filter by route line if available
    if (routeCoordinates && routeCoordinates.length > 1) {
      try {
        const routeLine = turf.lineString(routeCoordinates.map(c => [c.lng, c.lat]));
        const onRouteHydrants = hydrantsWithDistances.map(hyd => {
          const pt = turf.point([hyd.lng, hyd.lat]);
          const distanceToRoute = turf.pointToLineDistance(pt, routeLine, { units: 'meters' });
          return { ...hyd, distanceToRoute };
        }).filter(hyd => hyd.distanceToRoute <= 25); // 25m threshold along route

        if (onRouteHydrants.length > 0) {
          onRouteHydrants.sort((a, b) => a.distance - b.distance);
          return onRouteHydrants.slice(0, 3); // Return up to 3 hydrants on route
        }
      } catch (e) {
        console.error("Error filtering hydrants by route line:", e);
      }
    }

    return hydrantsWithDistances.slice(0, 3); // Return up to 3 closest hydrants
  }, [allNearbyHydrants, targetAddress, routeCoordinates]);

  const targetCoords = useMemo(() => {
    return targetAddress ? [targetAddress.lat, targetAddress.lng] : null;
  }, [targetAddress]);

  // Adaptive Zooming: fit bounds to show both the selected Fire Hall (origin) and searched address (destination)
  useEffect(() => {
    if (map && targetAddress && STATIONS[homeHall] && appMode === "EXPLORE") {
      const origin = STATIONS[homeHall];
      const dest = [targetAddress.lat, targetAddress.lng];
      map.fitBounds([origin, dest], { padding: [50, 50], animate: true });
    }
  }, [map, targetAddress, homeHall, appMode]);

  // ROAD ACCESS FILTER STATES
  const [filterNoAccess, setFilterNoAccess] = useState(true);
  const [filterAccessOnly, setFilterAccessOnly] = useState(false);
  const [filterCaution, setFilterCaution] = useState(false);

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
    // 1. Fetch DriveBC live API
    const fetchDriveBC = fetch("https://api.open511.gov.bc.ca/events?format=json&limit=100")
      .then(r => r.ok ? r.json() : { events: [] })
      .catch(err => {
        console.warn("Failed to fetch DriveBC Open511 events:", err);
        return { events: [] };
      });

    // 2. Fetch Municipal 511 API via proxy (Dynamic versioned filename parser to bypass caching)
    const fetchMuni511 = fetch("https://api.codetabs.com/v1/proxy?quest=https://bc.municipal511.ca/")
      .then(r => r.ok ? r.text() : Promise.reject("Primary HTML proxy failed"))
      .then(html => {
        const match = html.match(/"jsonData0\.txt"\s*:\s*"([^"]+)"/);
        const hashedFilename = match ? match[1] : "jsonData0.txt";
        return fetch(`https://api.codetabs.com/v1/proxy?quest=https://bc.municipal511.ca/Dynamic/${hashedFilename}`)
          .then(r => r.ok ? r.json() : Promise.reject("Primary Data proxy failed"));
      })
      .catch(err => {
        console.warn("Primary CORS proxy failed, trying fallback...", err);
        return fetch("https://api.allorigins.win/raw?url=https://bc.municipal511.ca/")
          .then(r => r.ok ? r.text() : Promise.reject("Fallback HTML proxy failed"))
          .then(html => {
            const match = html.match(/"jsonData0\.txt"\s*:\s*"([^"]+)"/);
            const hashedFilename = match ? match[1] : "jsonData0.txt";
            return fetch(`https://api.allorigins.win/raw?url=https://bc.municipal511.ca/Dynamic/${hashedFilename}`)
              .then(r => r.ok ? r.json() : Promise.reject("Fallback Data proxy failed"));
          });
      })
      .catch(err => {
        console.warn("All CORS proxies failed to fetch Municipal 511:", err);
        return { Issues: [], CoordsEncoded: "" };
      });

    Promise.all([fetchDriveBC, fetchMuni511])
      .then(([dbData, muniData]) => {
        const combinedEvents = [];
        const now = new Date();

        // --- Process DriveBC Events ---
        const dbEvents = (dbData.events || [])
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
            let polyline = [];
            if (evt.geography.type === "Point") {
              lng = evt.geography.coordinates[0];
              lat = evt.geography.coordinates[1];
            } else if (evt.geography.type === "LineString") {
              polyline = evt.geography.coordinates.map(pt => [pt[1], pt[0]]);
              const middleIndex = Math.floor(evt.geography.coordinates.length / 2);
              lng = evt.geography.coordinates[middleIndex][0];
              lat = evt.geography.coordinates[middleIndex][1];
            }

            const severityVal = (evt.severity || "MINOR").toUpperCase();
            let emergencyAccess = "CAUTION";
            if (severityVal === "MAJOR") {
              emergencyAccess = "NO_ACCESS";
            }

            let startDate = null;
            let endDate = null;
            if (evt.schedule && Array.isArray(evt.schedule.intervals) && evt.schedule.intervals.length > 0) {
              const parts = evt.schedule.intervals[0].split('/');
              if (parts.length === 2) {
                const s = new Date(parts[0]);
                const e = new Date(parts[1]);
                if (!isNaN(s.getTime())) startDate = s.toISOString();
                if (!isNaN(e.getTime())) endDate = e.toISOString();
              }
            }
            if (!startDate && evt.created) {
              const c = new Date(evt.created);
              if (!isNaN(c.getTime())) startDate = c.toISOString();
            }

            return {
              id: evt.id || Math.random().toString(),
              headline: evt.headline || "TRAFFIC ALERT",
              street: evt.road_name || "Regional Road",
              severity: severityVal,
              emergencyAccess: emergencyAccess,
              description: evt.description || "Active traffic event.",
              coordinates: [lat, lng],
              polyline: polyline,
              source: "DriveBC Open511",
              startDate: startDate,
              endDate: endDate
            };
          });

        combinedEvents.push(...dbEvents);

        // --- Process Municipal 511 Events ---
        const muniIssues = muniData.Issues || [];
        const coordsEncoded = muniData.CoordsEncoded || "";
        const decoder = new GeometryDecoder(coordsEncoded);

        muniIssues.forEach(issue => {
          const geoms = issue.Geometry || [];
          geoms.forEach((geom, geomIdx) => {
            const numPoints = geom.NumPoints || 0;
            const pathPoints = decoder.getNPoints(numPoints); // Array of [lat, lng]

            // Check if any point falls inside Coquitlam bounding box
            const inCoquitlam = pathPoints.some(([lat, lng]) => 
              lat >= 49.20 && lat <= 49.38 && lng >= -122.92 && lng <= -122.68
            );

            if (!inCoquitlam) return;

            // Determine midpoint coordinates for pin placement
            let lat = 49.28;
            let lng = -122.80;
            let polyline = [];

            if (pathPoints.length === 1) {
              lat = pathPoints[0][0];
              lng = pathPoints[0][1];
            } else if (pathPoints.length > 1) {
              polyline = pathPoints;
              const middleIndex = Math.floor(pathPoints.length / 2);
              lat = pathPoints[middleIndex][0];
              lng = pathPoints[middleIndex][1];
            } else {
              return; // Empty geometry, skip
            }

            // Map RoadClosureType flags to emergencyAccess level
            const rct = geom.MarkerInfo?.RoadClosureType || 0;
            let highestBit = 0;
            if (rct > 0) {
              highestBit = 1 << Math.floor(Math.log2(rct));
            }

            const desc = issue.Description || {};
            const descLower = (desc.BaseDescription || "").toLowerCase();
            const headlineLower = (desc.Headline || "").toLowerCase();
            const isRoadClosedText = descLower.includes("road closed") || 
                                     descLower.includes("full closure") || 
                                     headlineLower.includes("road closed") || 
                                     headlineLower.includes("full closure");

            let emergencyAccess = "CAUTION";
            let severity = "MINOR";

            if (highestBit === 262144) {
              emergencyAccess = "NO_ACCESS";
              severity = "MAJOR";
            } else if (highestBit === 65536 || highestBit === 32768 || highestBit === 16384) {
              emergencyAccess = "ACCESS_ONLY";
              severity = "MODERATE";
            } else if (isRoadClosedText) {
              emergencyAccess = "ACCESS_ONLY";
              severity = "MODERATE";
            } else if (issue.Priority >= 4) {
              severity = "MAJOR";
            } else if (issue.Priority === 3) {
              severity = "MODERATE";
            }

            // Dates conversion
            let startDate = null;
            let endDate = null;
            if (desc.ProposedStartTimeUtcEpochMillis) {
              startDate = new Date(desc.ProposedStartTimeUtcEpochMillis).toISOString();
            }
            if (desc.ProposedEndTimeUtcEpochMillis) {
              endDate = new Date(desc.ProposedEndTimeUtcEpochMillis).toISOString();
            }
            if (!startDate && desc.UpdateTimeUtcEpochMillis) {
              startDate = new Date(desc.UpdateTimeUtcEpochMillis).toISOString();
            }

            // Headline, street and description
            const locationName = geom.MarkerInfo?.LocationName || "";
            const streetName = locationName || issue.TableViewInfo?.Location || desc.BaseLocationDescription || "Local Road";
            
            let categoryName = "Traffic Alert";
            const iconClass = geom.MarkerInfo?.IconClass || issue.TableViewInfo?.IconClass || "";
            if (iconClass.toLowerCase().includes("construction")) {
              categoryName = "Construction";
            } else if (iconClass.toLowerCase().includes("event")) {
              categoryName = "Special Event";
            } else if (iconClass.toLowerCase().includes("debris")) {
              categoryName = "Caution";
            } else if (iconClass.toLowerCase().includes("slippery")) {
              categoryName = "Weather Alert";
            }

            const closureTypeName = getClosureTypeName(highestBit);
            let headlineText = desc.Headline || "";
            if (!headlineText) {
              headlineText = closureTypeName ? `${categoryName}: ${closureTypeName}` : categoryName;
            }

            let descriptionText = desc.BaseDescription ? desc.BaseDescription.trim() : "";
            if (!descriptionText) {
              descriptionText = closureTypeName ? `Local activity/road work. Status: ${closureTypeName}.` : "Local construction or road activity.";
            }

            const item = {
              id: `${issue.IssueId}_${geomIdx}`,
              headline: headlineText,
              street: streetName,
              severity: severity,
              emergencyAccess: emergencyAccess,
              description: descriptionText,
              coordinates: [lat, lng],
              polyline: polyline,
              source: issue.Source || "City of Coquitlam",
              startDate: startDate,
              endDate: endDate
            };

            combinedEvents.push(item);
          });
        });

        // --- Post-process: Expiry, deduplication and sorting preparation ---
        const processed = combinedEvents.map(evt => {
          const start = evt.startDate ? new Date(evt.startDate) : null;
          const end = evt.endDate ? new Date(evt.endDate) : null;

          let isActive = false;
          let isFuture = false;
          let isExpired = false;
          let durationMs = Infinity;

          if (start && now < start) {
            isFuture = true;
          } else if (end && now > end) {
            isExpired = true;
          } else {
            isActive = true;
          }

          if (start && end) {
            durationMs = end.getTime() - start.getTime();
          }

          return {
            ...evt,
            start,
            end,
            isActive,
            isFuture,
            isExpired,
            durationMs
          };
        });

        // Filter out expired ones
        const unexpired = processed.filter(evt => !evt.isExpired);

        // Group & merge events at the same location (rounded to 4 decimal places)
        const groups = {};
        unexpired.forEach(evt => {
          const latKey = evt.coordinates[0].toFixed(4);
          const lngKey = evt.coordinates[1].toFixed(4);
          const key = `${latKey}_${lngKey}`;

          if (!groups[key]) {
            groups[key] = [];
          }
          groups[key].push(evt);
        });

        const deduplicated = Object.values(groups).map(group => {
          if (group.length === 1) return group[0];

          const first = group[0];

          // Merge severity and emergencyAccess
          const severityOrder = { "MAJOR": 3, "MODERATE": 2, "MINOR": 1 };
          let highestSeverity = "MINOR";
          let maxSeverityVal = 0;

          const accessOrder = { "NO_ACCESS": 3, "ACCESS_ONLY": 2, "CAUTION": 1 };
          let mostRestrictiveAccess = "CAUTION";
          let maxAccessVal = 0;

          group.forEach(evt => {
            const sVal = severityOrder[evt.severity] || 0;
            if (sVal > maxSeverityVal) {
              maxSeverityVal = sVal;
              highestSeverity = evt.severity;
            }

            const aVal = accessOrder[evt.emergencyAccess] || 0;
            if (aVal > maxAccessVal) {
              maxAccessVal = aVal;
              mostRestrictiveAccess = evt.emergencyAccess;
            }
          });

          const uniqueDescriptions = [...new Set(group.map(evt => evt.description.trim()))];
          const combinedDescription = uniqueDescriptions.length > 1
            ? uniqueDescriptions.map(desc => `• ${desc}`).join('\n')
            : uniqueDescriptions[0];

          let earliestStart = null;
          let latestEnd = null;
          group.forEach(evt => {
            if (evt.start) {
              if (!earliestStart || evt.start < earliestStart) earliestStart = evt.start;
            }
            if (evt.end) {
              if (!latestEnd || evt.end > latestEnd) latestEnd = evt.end;
            }
          });

          const anyActive = group.some(evt => evt.isActive);

          return {
            ...first,
            severity: highestSeverity,
            emergencyAccess: mostRestrictiveAccess,
            description: combinedDescription,
            startDate: earliestStart ? earliestStart.toISOString() : null,
            endDate: latestEnd ? latestEnd.toISOString() : null,
            start: earliestStart,
            end: latestEnd,
            isActive: anyActive,
            isFuture: !anyActive && group.some(evt => evt.isFuture),
            durationMs: earliestStart && latestEnd ? latestEnd.getTime() - earliestStart.getTime() : Infinity
          };
        });

        setRoadClosures(deduplicated);
      })
      .catch((err) => {
        console.error("Critical error in road closures loading workflow:", err);
      });
  }, []);

  // LAZY LOAD TRAINING DATA
  const loadTrainingData = useCallback(() => {
    if (trainingDataLoaded || loadingTraining) return;
    setLoadingTraining(true);
    const baseUrl = import.meta.env.BASE_URL;

    const fetchZones = fetch(`${baseUrl}data/zones.json?v=2`).then(r => r.ok ? r.json() : []);
    const fetchIntersections = fetch(`${baseUrl}data/intersections.json?v=1`).then(r => r.ok ? r.json() : []);
    const fetchBlocks = fetch(`${baseUrl}data/blocks.json?v=2`).then(r => r.ok ? r.json() : []);
    const fetchAddresses = fetch(`${baseUrl}data/addresses.json?v=2`).then(r => r.ok ? r.json() : []);

    Promise.all([fetchZones, fetchIntersections, fetchBlocks, fetchAddresses])
      .then(([zonesData, intersectionsData, blocksData, addressesData]) => {
        setZones(zonesData);
        setIntersections(intersectionsData);
        setBlocks(blocksData);
        setAddresses(addressesData);
        setTrainingDataLoaded(true);
        setLoadingTraining(false);
      })
      .catch(err => {
        console.error("Failed to load training data:", err);
        setLoadingTraining(false);
      });
  }, [trainingDataLoaded, loadingTraining]);

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
      if(appMode === "TRAINING_ZONES") nextQuestion(zones);
      if(appMode === "TRAINING_INTERSECTIONS") nextQuestion(intersections);
      if(appMode === "TRAINING_BLOCKS") nextBlockQuestion();
      if(appMode === "TRAINING_ADDRESSES") nextQuestion(addresses);
  }, [appMode, zones, intersections, addresses, nextQuestion, nextBlockQuestion]);

  const startMode = useCallback((mode) => {
      clearTimeout(autoAdvanceTimer.current); // Clear any pending jumps
      setAppMode(mode);
      setActiveDispatch(null);
      setScore(0);
      setFeedback(null);
      setUserGuess(null);
      setTargetAddress(null);
      setCurrentQuestion(null);
      setClickedBlockData(null);
      setMapStyle(MODE_DEFAULTS[mode] || "GREY"); 
      
      // Only show labels automatically for Address Mode and Explore
      setShowLabels(mode === "TRAINING_ADDRESSES" || mode === "EXPLORE");
      
      if (mode === "EXPLORE") {
          setShowZones(false);
          setShowHydrants(true);
          setShowRoadClosures(true);
          setLeftSidebarOpen(true);
          setRightSidebarOpen(false);
      } else {
          // Training Modes: Hydrants ON by default, road closures icons ON by default, zones OFF
          setShowHydrants(true);
          setShowRoadClosures(true);
          setShowZones(false);
          setLeftSidebarOpen(true);
          setRightSidebarOpen(false); // Close alerts list panel for training focus
          
          if (!trainingDataLoaded) {
            loadTrainingData();
          }
      }
  }, [trainingDataLoaded, loadTrainingData]);

  // Reactive effect to set active question once training data downloads
  useEffect(() => {
    if (!trainingDataLoaded || appMode === "EXPLORE") return;
    if (!currentQuestion) {
      const timer = setTimeout(() => {
        if (appMode === "TRAINING_ZONES") nextQuestion(zones);
        if (appMode === "TRAINING_INTERSECTIONS") nextQuestion(intersections);
        if (appMode === "TRAINING_BLOCKS") nextBlockQuestion();
        if (appMode === "TRAINING_ADDRESSES") nextQuestion(addresses);
      }, 0);
      return () => clearTimeout(timer);
    }
  }, [trainingDataLoaded, appMode, zones, intersections, blocks, addresses, nextQuestion, nextBlockQuestion, currentQuestion]);

  // ⌨️ KEYBOARD LISTENER (Enter = Next) - Declared below goToNext to resolve TDZ hoisting bug
  useEffect(() => {
    const handleKeyDown = (e) => {
        // If Enter is pressed AND we are showing feedback (waiting for next)
        if (e.key === "Enter" && feedback && appMode !== "EXPLORE") {
            goToNext();
        }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [feedback, appMode, goToNext]);

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
    if (!currentQuestion || (appMode !== "TRAINING_INTERSECTIONS" && appMode !== "TRAINING_ADDRESSES") || feedback) return;
    setUserGuess(latlng);
    
    const from = turf.point([latlng.lng, latlng.lat]);
    const to = turf.point([currentQuestion.lng, currentQuestion.lat]);
    let distMeters = Math.round(turf.distance(from, to, { units: 'kilometers' }) * 1000);
    
    const tolerance = appMode === "TRAINING_ADDRESSES" ? 15 : 50;
    if (distMeters <= tolerance) distMeters = 0;
    
    setDistanceOff(distMeters);
    const points = Math.max(0, 500 - distMeters);
    setScore(s => s + points);
    
    const result = distMeters === 0 ? "PERFECT" : points > 0 ? "OKAY" : "MISS";
    setFeedback(result);
 
    // 🔽 Auto-advance for Intersection/Address modes too
    if (result === "PERFECT") {
        autoAdvanceTimer.current = setTimeout(() => {
            if (appMode === "TRAINING_INTERSECTIONS") nextQuestion(intersections);
            if (appMode === "TRAINING_ADDRESSES") nextQuestion(addresses);
        }, 1500);
    }
  }, [currentQuestion, appMode, feedback, intersections, addresses, nextQuestion]);
 
  const handleBlockClick = useCallback((blockData) => {
    if (!currentQuestion || appMode !== "TRAINING_BLOCKS" || feedback) return;
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
  }, [currentQuestion, appMode, feedback, nextBlockQuestion]);
 
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
    if (appMode === "TRAINING_ZONES") {
        if (currentQuestion && zone.zone_id === currentQuestion.zone_id) {
            return { color: "#06b6d4", fillOpacity: 0.5, weight: 0 }; 
        }
        return { color: "transparent", fillOpacity: 0, weight: 0 }; 
    }
    
    // Color-code by fire hall for explore/live modes
    const stationName = zone.station || "";
    let color = "#475569"; // default slate gray
    
    if (stationName.includes("Hall 1") || zone.unit_id === "E1") color = "#f87171";      // Red for Hall 1
    else if (stationName.includes("Hall 2") || zone.unit_id === "E2") color = "#60a5fa"; // Blue for Hall 2
    else if (stationName.includes("Hall 3") || zone.unit_id === "E3" || zone.unit_id === "Q5") color = "#34d399"; // Green for Hall 3
    else if (stationName.includes("Hall 4") || zone.unit_id === "E4") color = "#c084fc"; // Purple for Hall 4
    
    return {
      color: color,
      fillColor: color,
      fillOpacity: 0.08,
      weight: 1.5,
      dashArray: "3 3"
    };
  };
 
  // Filter closures for map and alerts rendering (only show currently active ones on map)
  const activeClosures = roadClosures.filter(closure => {
    if (!closure.isActive) return false;
    if (closure.emergencyAccess === "NO_ACCESS" && !filterNoAccess) return false;
    if (closure.emergencyAccess === "ACCESS_ONLY" && !filterAccessOnly) return false;
    if (closure.emergencyAccess === "CAUTION" && !filterCaution) return false;
    return true;
  });
 
  return (
    <div className="h-screen w-screen flex flex-col bg-slate-950 overflow-hidden text-slate-100 font-sans">
      
      <Header 
        appMode={appMode} 
        setAppMode={startMode} 
        mapStyle={mapStyle} 
        setMapStyle={setMapStyle} 
        showLabels={showLabels} 
        setShowLabels={setShowLabels} 
        leftSidebarOpen={leftSidebarOpen}
        setLeftSidebarOpen={setLeftSidebarOpen}
        rightSidebarOpen={rightSidebarOpen}
        setRightSidebarOpen={setRightSidebarOpen}
        alertsCount={showRoadClosures ? activeClosures.length : 0}
        gisOffline={cadastralError}
      />

      <div className="flex flex-row flex-grow w-full h-[calc(100vh-4rem)] relative overflow-hidden z-10">
        {/* Left Control Panel & Option Toggles */}
        <LeftSidebar 
          leftSidebarOpen={leftSidebarOpen}
          setLeftSidebarOpen={setLeftSidebarOpen}
          appMode={appMode}
          activeDispatch={activeDispatch}
          setActiveDispatch={setActiveDispatch}
          loadingTraining={loadingTraining}
          showZones={showZones}
          setShowZones={setShowZones}
          showHydrants={showHydrants}
          setShowHydrants={setShowHydrants}
          showRoadClosures={showRoadClosures}
          setShowRoadClosures={setShowRoadClosures}
          showLabels={showLabels}
          setShowLabels={setShowLabels}
          showCranes={showCranes}
          setShowCranes={setShowCranes}
          addresses={addresses}
          homeHall={homeHall}
          setHomeHall={setHomeHall}
          targetAddress={targetAddress}
          setTargetAddress={updateTargetAddress}
          nearestHydrant={nearestHydrants[0] || null}
          nearestHydrants={nearestHydrants}
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
            <BaseMap style={mapStyle} useLabelsFallback={cadastralError} />
            
            <CoquitlamOverlays 
                visible={showLabels && !cadastralError} 
                onLoadError={() => setCadastralError(true)} 
            />
            
            {/* Hydrants Visual GIS Overlay */}
            <HydrantsLayer visible={showHydrants} />
            
            {/* Tower Cranes Map Overlay */}
            <CranesLayer visible={showCranes} />
            
            {/* 2. DEFINE CUSTOM PANES */}
            <Pane name="underlayPane" style={{ zIndex: 390 }} />
            <Pane name="labelsPane" style={{ zIndex: 410 }} />
            
            {/* 3. LAYERS ASSIGNED TO PANES */}
            
            {/* "Top Bun" - The Text Labels */}
            <FireZonesLayer 
                visible={(appMode === "TRAINING_ZONES" || (appMode === "EXPLORE" && showZones)) && !cadastralError} 
                pane="labelsPane" 
            />
            
            {/* "Bottom Bun" - The Highlight */}
            {(appMode === "TRAINING_ZONES" || (appMode === "EXPLORE" && showZones)) && zones.map((zone) => (
              <Polygon 
                  key={zone.zone_id} 
                  positions={zone.geometry.coordinates[0].map(c => [c[1], c[0]])} 
                  pathOptions={getZoneStyle(zone)} 
                  pane="underlayPane" 
              >
                {appMode === "EXPLORE" && (
                  <Tooltip sticky direction="center" permanent={false}>
                    <div className="font-mono text-[10px] font-bold text-slate-200">
                      <span className="text-amber-400 font-extrabold">ZONE {zone.zone_id}</span>
                      <span className="mx-1 text-slate-500">|</span>
                      <span className="text-slate-300 font-semibold">{zone.unit_id}</span>
                    </div>
                  </Tooltip>
                )}
              </Polygon>
            ))}

            {/* HIDE STATIONS IN TRAINING MODE */}
            {appMode !== "TRAINING_ZONES" && <StationsLayer />}
            
            <MapClickEvents onMapClick={handleMapClick} />
            
            {!feedback && currentQuestion && (
               <SmartZoom target={currentQuestion} mode={appMode} allBlocks={blocks} allZones={zones} />
            )}
            {feedback === "WRONG" && appMode === "TRAINING_BLOCKS" && clickedBlockData && (
               <ZoomToFeedback guessBlock={clickedBlockData} targetBlock={blocks.find(b => b.block === currentQuestion.block && b.street === currentQuestion.street)} mode={appMode} />
            )}

            {/* TRAINING VISUALS: BLOCKS */}
            {appMode === "TRAINING_BLOCKS" && currentQuestion && blocks && blocks.length > 0 && 
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

            {/* TRAINING VISUALS: PINS */}
            {(appMode === "TRAINING_INTERSECTIONS" || appMode === "TRAINING_ADDRESSES") && userGuess && (
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
            {showRoadClosures && activeClosures.map((closure, i) => (
              <RoadClosureMarker 
                key={closure.id || i}
                closure={closure}
                isSelected={selectedClosure !== null && selectedClosure.id === closure.id}
                onSelect={setSelectedClosure}
              />
            ))}

            {/* Active Target Address Marker & Suggested Route Overlay */}
            {appMode === "EXPLORE" && targetAddress && (
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
                        
                        {nearestHydrants.length > 0 && (
                          <div className="mt-2.5 pt-2 border-t border-slate-900 flex flex-col gap-1">
                            <span className="text-[8px] text-sky-400 font-extrabold uppercase tracking-wider font-mono">💧 Nearest Hydrant</span>
                            <div className="flex justify-between text-xs mt-0.5">
                              <span className="text-slate-400">ID / Distance</span>
                              <span className="text-white font-mono font-bold">{nearestHydrants[0].gisId} ({nearestHydrants[0].distance}m)</span>
                            </div>
                            {nearestHydrants[0].flowClass && (
                              <div className="flex justify-between text-xs">
                                <span className="text-slate-400">Flow Rating</span>
                                <span className="text-sky-400 font-mono font-bold">{nearestHydrants[0].flowClass}</span>
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
                        
                        {nearestHydrants.length > 0 && (
                          <div className="mt-2.5 pt-2 border-t border-slate-900 flex flex-col gap-1">
                            <span className="text-[8px] text-sky-400 font-extrabold uppercase tracking-wider font-mono">💧 Nearest Hydrant</span>
                            <div className="flex justify-between text-xs mt-0.5">
                              <span className="text-slate-400">ID / Distance</span>
                              <span className="text-white font-mono font-bold">{nearestHydrants[0].gisId} ({nearestHydrants[0].distance}m)</span>
                            </div>
                            {nearestHydrants[0].flowClass && (
                              <div className="flex justify-between text-xs">
                                <span className="text-slate-400">Flow Rating</span>
                                <span className="text-sky-400 font-mono font-bold">{nearestHydrants[0].flowClass}</span>
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

                {/* Highlight Top 3 closest hydrants (No tracer line) */}
                {nearestHydrants.map((hyd, idx) => {
                  const isPrimary = idx === 0;
                  return (
                    <CircleMarker 
                      key={`${hyd.gisId}-${idx}`}
                      center={[hyd.lat, hyd.lng]} 
                      radius={isPrimary ? 16 : 12} 
                      pathOptions={{ 
                        color: isPrimary ? '#06b6d4' : '#c084fc', // Cyan for closest, Lavender for others
                        fillColor: isPrimary ? '#22d3ee' : '#e9d5ff', 
                        fillOpacity: isPrimary ? 0.15 : 0.1, 
                        weight: isPrimary ? 2 : 1.5,
                        className: isPrimary ? 'animate-pulse' : '' 
                      }} 
                    >
                      <Tooltip direction="top" className="font-bold text-xs bg-slate-950 text-white border border-slate-800 p-2 shadow-xl">
                        <div className="flex flex-col gap-0.5" style={{ minWidth: '120px' }}>
                          <span className={`text-[9px] uppercase font-mono tracking-wider ${isPrimary ? 'text-cyan-400' : 'text-purple-400'}`}>
                            {isPrimary ? 'NEAREST HYDRANT' : `HYDRANT OPTION #${idx + 1}`}
                          </span>
                          <span className="text-white text-sm font-bold">{hyd.gisId}</span>
                          <span className="text-slate-400 text-[10px] mt-1 font-mono">Distance: {hyd.distance}m</span>
                          {hyd.flowClass && (
                            <span className="text-sky-400 text-xs font-semibold">Flow Class: {hyd.flowClass}</span>
                          )}
                        </div>
                      </Tooltip>
                    </CircleMarker>
                  );
                })}

                {STATIONS[homeHall] && (
                  <RoutingOverlay 
                    from={STATIONS[homeHall]} 
                    to={targetCoords} 
                    onRouteCalculated={setRouteCoordinates}
                  />
                )}
              </>
            )}
          </MapContainer>

          {/* APPLICATION VERSION & COMPILE TIMESTAMP WATERMARK */}
          <div className="absolute bottom-3 left-3 z-[1000] pointer-events-none font-mono text-[9px] text-slate-400/85 drop-shadow-sm select-none">
            CFR EVO APP | BUILD: {buildTime} | LICENSE: POLYFORM NONCOMMERCIAL 1.0.0
          </div>
        </div>

        {/* Right Sidebar Alerts Panel */}
        <RightSidebar 
          rightSidebarOpen={rightSidebarOpen}
          setRightSidebarOpen={setRightSidebarOpen}
          appMode={appMode}
          roadClosures={roadClosures}
          showRoadClosures={showRoadClosures}
          filterNoAccess={filterNoAccess}
          filterAccessOnly={filterAccessOnly}
          filterCaution={filterCaution}
          map={map}
          onSelectClosure={setSelectedClosure}
        />
      </div>

      {appMode === "ADMIN_DISPATCHES" && (
        <DispatchReview 
          onClose={() => startMode("EXPLORE")} 
          onLocateAddress={(call) => {
            startMode("EXPLORE");
            setActiveDispatch(call);
            const target = call?.target || call;
            if (target) {
              updateTargetAddress(target);
              if (map && target.lat && target.lng) {
                map.flyTo([target.lat, target.lng], 17, { animate: true });
              }
            }
            setLeftSidebarOpen(true);
            setRightSidebarOpen(false);
          }}
        />
      )}
    </div>
  );
}