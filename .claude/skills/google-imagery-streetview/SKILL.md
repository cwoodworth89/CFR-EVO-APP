---
name: google-imagery-streetview
description: Procedures and integration workflows for fetching, caching, orienting, persisting, and rendering Google Street View panoramas and high-resolution satellite aerial imagery in CFR EVO.
---

# Satellite Imagery & Street View Enrichment Runbook

> [!IMPORTANT]
> **The aerial basemap is not Google and not Esri.** Since 2026-08-31 the map's aerial layer
> is `ortho.mbtiles` — City of Coquitlam 2025 7.5cm orthophotography crawled from the City's
> own `Imagery_2025` service, under the Open Government Licence, served offline from
> `/services/ortho`. The Esri `satellite` layer was retired; see `gis-pipeline-sync` §4.1.
>
> This skill covers **Street View** enrichment and the historical Google static-imagery
> integration only. Do not use it as the reference for the aerial basemap.


This skill outlines how to fetch, orient, cache, persist, and display high-resolution **Google Satellite aerial imagery** and **Street View 360° building facade views** for emergency dispatches in **CFR EVO**.

---

## 1. Tactical Purpose on Station Displays

When arriving at an incident, crew situational awareness is dramatically improved by seeing:
1. **Satellite Aerial Imagery**: Roof structure, commercial access gates, alleyway egress, nearby exposure hazards, and hazardous material storage.
2. **Street View Facade**: Front door location, driveway orientation, building height/stories, and visible security gates.

```mermaid
flowchart TD
    A[Geocoded Incident Coordinates] --> B[Calculate Frontage Heading θ]
    B --> C[Fetch Google Street View API]
    A --> D[Fetch High-Res Satellite Static Map]
    
    C --> E[Local Image Cache & PostgreSQL Database]
    D --> E
    
    E --> F[Kiosk UI Split-Screen Display]
    F --> F1[Live Tactical Vector Map (CartoDB Voyager)]
    F --> F2[Satellite Aerial with Parcel Polygon]
    F --> F3[Street View 360° Building Entrance]
```

---

## 2. Dynamic Heading ($\theta$) & Facade Orientation

To ensure Street View points directly at the building entrance (rather than down the road), calculate the bearing from the street access point to the parcel centroid:

```python
import math

def calculate_streetview_heading(street_lat: float, street_lng: float, parcel_lat: float, parcel_lng: float) -> int:
    """
    Calculates compass heading (0-360 degrees) from street point toward building centroid.
    """
    d_lng = math.radians(parcel_lng - street_lng)
    lat1 = math.radians(street_lat)
    lat2 = math.radians(parcel_lat)

    y = math.sin(d_lng) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(d_lng)
    
    bearing = math.degrees(math.atan2(y, x))
    return int((bearing + 360) % 360)
```

---

## 3. Real-Time POV Drag Synchronization Pattern (React + Google JS SDK)

In interactive 360° mode, cross-origin Security (`same-origin` policy) prevents `<iframe>` elements from leaking user touch/mouse camera rotation angles back to React. To capture the exact angle a user drags to when tapping **"Save Preferred View"**, use `window.google.maps.StreetViewPanorama` with a real-time `pov_changed` listener:

```javascript
// frontend/src/components/kiosk/StreetViewPanel.jsx
const currentPovRef = useRef({ heading: 0, pitch: 5, zoom: 1 });

const pano = new window.google.maps.StreetViewPanorama(targetContainer, {
  pov: { heading: parseFloat(initialHeading), pitch: parseFloat(initialPitch) },
  zoom: 1,
  fullscreenControl: false, // Hides Google's native button underneath custom Expand button
  addressControl: false,
  panControl: false,
  linksControl: true,
  visible: true
});

// Resolve nearest street panorama within 300m outdoor radius (prevents rooftop centroid ZERO_RESULTS gray screens!)
const svService = new window.google.maps.StreetViewService();
svService.getPanorama({
  location: { lat: parseFloat(frontLat), lng: parseFloat(frontLng) },
  radius: 300,
  source: window.google.maps.StreetViewSource.OUTDOOR,
  preference: window.google.maps.StreetViewPreference.NEAREST
}, (data, status) => {
  if (status === window.google.maps.StreetViewStatus.OK && data && data.location) {
    pano.setPano(data.location.pano);
    pano.setPov({ heading: parseFloat(initialHeading), pitch: parseFloat(initialPitch) });
    pano.setVisible(true);
  } else {
    pano.setPosition({ lat: parseFloat(frontLat), lng: parseFloat(frontLng) });
  }
});

// Real-time POV drag listener (captures exact touch & mouse camera angles!)
pano.addListener('pov_changed', () => {
  const pov = pano.getPov();
  if (pov && !isNaN(pov.heading)) {
    currentPovRef.current = {
      heading: Math.round(pov.heading || 0),
      pitch: Math.round(pov.pitch || 0),
      zoom: Math.round(pano.getZoom() || 1)
    };
  }
});
```

---

## 4. PostgreSQL Parcel Schema & Override Persistence

Camera vectors (`streetview_heading`, `streetview_pitch`, `streetview_fov`), Lock Box notes, and Pre-Incident Construction Plan PDF URLs are consolidated directly into the `parcels` table in PostgreSQL:

```sql
-- PostgreSQL Parcel Schema Extension
ALTER TABLE parcels 
ADD COLUMN IF NOT EXISTS streetview_heading DOUBLE PRECISION DEFAULT 0.0,
ADD COLUMN IF NOT EXISTS streetview_pitch DOUBLE PRECISION DEFAULT 5.0,
ADD COLUMN IF NOT EXISTS streetview_fov DOUBLE PRECISION DEFAULT 80.0,
ADD COLUMN IF NOT EXISTS lock_box_notes TEXT,
ADD COLUMN IF NOT EXISTS pre_plan_pdf_url TEXT;
```

When a user taps **"Save Preferred View"**:
1. Post payload `{ clean_address, front_lat, front_lng, heading, pitch, fov }` to `/api/parcels/streetview`.
2. Cache payload in `localStorage` under `cfr_sv_override_${cleanAddress}` for zero-latency client retrieval.

---

## 5. Google Cloud Console API Requirements

To ensure zero gray error boxes on station kiosks, the Google Maps API Key (`VITE_GOOGLE_MAPS_API_KEY`) must have the following APIs enabled in Google Cloud Console:
1. **Maps JavaScript API** (Required for `StreetViewPanorama` WebGL canvas & `pov_changed` drag events)
2. **Maps Embed API** (Required for reliable `<iframe>` embed fallback)
3. **Geocoding API** (Required for address centroid lookups)
