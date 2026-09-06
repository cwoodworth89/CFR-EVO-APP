# Google Maps Platform Terms — the clauses that govern the Street View panel

**Held**: verbatim excerpts, read from the live pages on 2026-09-06 and copied here so they
are available offline (this directory's rule). The full documents are long and change often;
the version read is named on each. Re-read the source before relying on a clause not quoted
below.

| Document | Version read | Source |
|:--|:--|:--|
| Google Maps Platform Terms of Service | *Last modified August 26, 2026* | https://cloud.google.com/maps-platform/terms |
| Google Maps Platform Service Specific Terms | as published 2026-09-06 | https://cloud.google.com/maps-platform/terms/maps-service-terms |
| Street View Static API — Policies | as published 2026-09-06 | https://developers.google.com/maps/documentation/streetview/policies |

The Terms say the Service Specific Terms control over them if they conflict ("URL Terms").

---

## 1. Storing or caching imagery: prohibited

**Terms of Service §3.2.3 Restrictions Against Misusing the Services**

> **(a) No Scraping.** Customer will not export, extract, or otherwise scrape Google Maps
> Content for use outside the Services. For example, Customer will not: (i) pre-fetch, index,
> store, reshare, or rehost Google Maps Content outside the services; (ii) bulk download Google
> Maps tiles, Street View images, geocodes, directions, distance matrix results, roads
> information, places information, elevation values, and time zone details; (iii) copy and save
> business names, addresses, or user reviews; or (iv) use Google Maps Content with
> text-to-speech services.
>
> **(b) No Caching.** Customer will not cache Google Maps Content except as expressly permitted
> under the Maps Service Specific Terms.

**Street View Static API — Policies**

> Content pre-fetching, indexing, storing, or caching is generally prohibited, except for place
> IDs and panorama IDs.

**What this means for CFR EVO**: a Street View image (static or panorama) may not be saved to
disk, to the database, or to the browser beyond the request that displayed it. The saved
"preferred view" must be *parameters*, not a picture.

## 2. What may be stored: the panorama ID, indefinitely

**Service Specific Terms, A. General Service Terms, §3 Google ID Caching**

> Customer may cache the Google ID values from the Services that return such field and allow
> caching, in accordance with its Documentation. For example, Customer may cache (a) place_id
> from Places API, Directions API, Geolocation API and Routes API, (b) pano_ID, from Street
> View Static API, and (c) video_ID from Aerial View API.

**Street View Static API — Policies, "Exceptions from caching restrictions"**

> The panorama ID, used to uniquely identify a Street View panorama, is exempt from the
> caching restriction. Therefore, you can store panorama ID values indefinitely.

Heading, pitch and zoom are the operator's own choices, not Google content. Latitude and
longitude *returned by* a Google service are Google content with 30-day caching limits under
the Service Specific Terms (e.g. §6.3 Geocoding API); the coordinates CFR EVO stores come from
the City's parcel data, not from Google.

## 3. Street View beside a non-Google map: prohibited

**Terms of Service §3.2.3(e) No Use With Non-Google Maps**

> To avoid quality issues and/or brand confusion, Customer will not use the Google Maps Core
> Services with or near a non-Google Map in a Customer Application. For example, Customer will
> not (i) display or use Places content on a non-Google Map, (ii) display Street View imagery
> and non-Google Maps on the same screen, or (iii) link a Google Map to non-Google Maps Content
> or a non-Google Map.

**What this means for CFR EVO**: the kiosk and the workstation draw the Street View panel on
the same screen as the Leaflet map (Carto street tiles, City orthophotos). Clause (ii) names
that arrangement. **Raised with the operator 2026-09-06; not resolved here.** Options are the
operator's: a separate screen or a full-screen modal for Street View with the map hidden,
or dropping Street View.

## 4. Other clauses read and judged not to apply

* §3.2.3(f) *No Use in Embedded Vehicle Systems*: the kiosk is a hall display, not an
  in-vehicle system. The ntfy push carries the department's own text, not Google content.
* §3.2.3(c) *No Creating Content From Google Maps Content*, example (vii): Google Maps Content
  may not be used "to improve machine learning and artificial intelligence models, including
  to train, test, validate or fine-tune the models." Nothing in the STT pipeline touches
  Google content.
* The Service Specific Terms' 30-day caching windows (Directions, Geocoding, Places, Routes)
  concern lat/lng *from those APIs*; CFR EVO geocodes against PostGIS and routes with OSRM.
