# Unified Map Surface — Design Proposal

**Status: proposal, not implemented.** Written 2026-08-22 after the MapBoard decomposition
pass. Nothing in `App.jsx` or the dispatch state model has been changed.

This proposes collapsing the two top-level surfaces — the workstation map and the kiosk
dispatch display — into **one map surface with two modes**, and unifying the two parallel
dispatch state models behind it.

---

## Why this is worth doing

The two surfaces look like different applications and are not. Measured 2026-08-22:

### They already share the layer library

`RouteOverviewPanel` — the kiosk's main map — imports the same components MapBoard does:

```
BaseMap, CoquitlamOverlays, StationsLayer, HydrantsLayer   from ../MapLayers
RoutingOverlay                                             from ../RoutingOverlay
BASE_LAYERS                                                from ../MapConstants
calculateEVORouteMetrics                                   from ../../utils/EVORoutingEngine
```

What differs is which layers mount, not how they are drawn.

| Layer | Workstation | Kiosk |
|:--|:--:|:--:|
| Base map, municipal overlays, stations, hydrants | ✅ | ✅ |
| Dispatch target, routing overlay | ✅ | ✅ |
| Response zones + map-grid labels | ✅ | — |
| Road closures | ✅ | **should be — see below** |
| Railroad crossings | ✅ | — |
| Auto-fit to route, candidate selector | — | ✅ |

### They have the same layout

```
workstation:  Header            + LeftSidebar + map + [address card, satellite, street view]
kiosk:        ActiveAlertBanner +              map + [cadastral,     satellite, street view]
```

Header + main map + right-hand detail stack, both times. The kiosk drops the left sidebar
and swaps one card of the stack.

### The duplication is in the container, not the panels

Both maps independently reimplement:

* the Leaflet map instance handle (`map` vs `mapInstance`),
* `userPanned` pan-tracking and the re-centre behaviour,
* a call to `calculateEVORouteMetrics`.

### And there are two state models for one fact

| | Workstation | Kiosk |
|:--|:--|:--|
| Owner | `MapBoard` | `useKioskQueue` (223 lines) |
| Active incident | `activeDispatch`, `targetAddress`, `targetPolygon` | `activeCall`, `queuedCalls` |
| MQTT listener | its own | its own |

They are bridged by a hand-written field-by-field translation in
`App.jsx:handleReviewCall`. **That translation is the clearest cost**: adding the
street-section fields on 2026-08-22 required editing it, in addition to the geocoder, the
payload builder and the kiosk panels. A field added to a dispatch should not need to be
copied between two representations of the same dispatch.

### Three MQTT subscriptions

`MapBoard:220`, `DispatchReview:136`, `useKioskQueue:104` each subscribe to the same topic
and parse the same message independently. This is the surface where the
`payload.eventType` vs `event` field-name defect produced divergent behaviour between
listeners — one path silently received nulls while another worked.

### Road closures belong in dispatch mode too

Decided 2026-08-22. Closures are currently standby-only, which is backwards: a closure
matters *most* when apparatus is being routed through it.

Two levels, and the cheap one is worth doing first:

1. **Show all active closures in both modes.** Effectively free — the layer already exists
   and `useRoadClosures` already fetches and filters. It is a one-line composition change
   once `MapSurface` exists.
2. **Highlight closures that intersect the route.** The useful version, and the one worth
   treating as a feature rather than a refactor. The data is already there: closures carry
   a `geom` column in PostGIS (added with the road-closure rewrite), and OSRM returns the
   route geometry, so "does this closure touch this route" is a `ST_Intersects` between two
   geometries we already hold. What needs deciding is the *behaviour* — whether an
   intersecting closure is a warning banner, a re-route, or a marker the driver reads — and
   that is an operations decision, not an engineering one.

Level 1 lands with the unification. Level 2 is tracked separately so it does not hold it up.

---

## Proposed shape

```
DispatchProvider                     one MQTT listener, one target model
└── AppShell  mode = STANDBY | DISPATCH
    ├── chrome        Header (standby) | ActiveAlertBanner (dispatch)
    ├── LeftSidebar   standby only
    ├── MapSurface    one <MapContainer>, mode-selected layer set
    │   ├── BaseMap, CoquitlamOverlays, StationsLayer, HydrantsLayer   always
    │   ├── DispatchTargetLayer, RoutingOverlay                        always
    │   ├── ZonesLayer, RoadClosuresLayer, RailroadCrossingsLayer      standby
    │   └── AutoFitBounds, CandidateSelector                           dispatch
    └── detail stack
        ├── TargetAddressCard (standby) | BlockParcelPanel (dispatch)
        ├── PropertySatellitePanel                                     both
        └── StreetViewPanel                                            both
```

### Three rules, applied at different layers

| Layer | Decision | Reasoning |
|:--|:--|:--|
| **State** | **Unify** | One context, one listener, one target model. Deletes `handleReviewCall` and the divergence risk. This is the real win. |
| **Map + layers** | **Share** | Layers already exist as components. Mode selects which mount — no flags inside the layers themselves. |
| **Chrome** | **Keep separate** | `LeftSidebar` (layer controls) and `ActiveAlertBanner` (incident information) display different *kinds* of thing. |

**Flags for degree, components for kind.** Font scale and density for 10-foot versus desk
viewing are flags. Layer controls versus incident information are separate components. A
single 479-line sidebar threaded with `isKiosk` is the failure mode to avoid.

---

## What is already done

The decomposition pass on 2026-08-22 took `MapBoard.jsx` from 1,184 to 662 lines and is
the on-ramp to this, not a separate effort:

* `map/ZonesLayer.jsx`, `map/RoadClosuresLayer.jsx`, `map/DispatchTargetLayer.jsx`,
  `map/MapViewControls.jsx` — inline JSX became layers. A mode-selected layer set cannot be
  composed while the rendering is inline.
* `hooks/useMapLayerPreferences.js`, `hooks/useRoadClosures.js` — view state lifted out of
  the container.
* `map/mapIcons.js`, `map/mapGeometry.js`, `map/layerIcons.js` — shared pure helpers.

## What remains, in dependency order

1. **`useMapInstance`** — map handle, pan tracking, re-centre, fit-bounds. Currently
   written twice. Pure consolidation, no behaviour change, and it is the smallest useful
   step.
2. **`TargetAddressCard`** — the last inline panel in MapBoard's right stack.
3. **`MapSurface`** — one `<MapContainer>` taking a layer set. At this point
   `RouteOverviewPanel` becomes chrome around `MapSurface` rather than its own map.
4. **`DispatchProvider`** — the state unification. **Touches the live dispatch path** and
   should be reviewed on its own, not folded into a refactor.
5. **`App.jsx`** — render one shell with a mode instead of swapping two components.

Steps 1–3 are mechanical and independently shippable. Step 4 is the one with risk.

---

## Risks and open questions

* **Step 4 touches live dispatch.** The MQTT listener, the queue timers and the review
  replay path all move. It should ship behind verification against real historical
  dispatches, the same way the intersection rebuild was diffed against the 24 recorded
  intersection calls.
* **`useKioskQueue` owns more than state** — timers, timeout clocks, queue advancement, TV
  mode. Unifying the *target model* does not require unifying all of that, and it should
  not be attempted in one change.
* **Five Leaflet instances exist today** (MapBoard, RouteOverviewPanel,
  PropertySatellitePanel, BlockParcelPanel, SatelliteMiniMap). This proposal removes one.
  Whether the remaining PIP maps should share a renderer is a separate question and should
  be **measured on kiosk hardware** before being treated as a problem.
* **Giving the kiosk the rest of the layer set is a product decision.** Road closures are
  decided (both modes — see above). Whether a crew wants *zones* and *railroad crossings*
  during a call is still for operations to say, and this document does not assume an
  answer.

## Non-goals

* Changing what any panel displays.
* Changing the 10-foot ergonomics of the kiosk.
* Merging `LeftSidebar` and `ActiveAlertBanner`.
* Touching `DispatchReview`, beyond it eventually consuming the shared listener.
