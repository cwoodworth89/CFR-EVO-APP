# Waze incidents and DriveBC webcams on a call — feasibility, 2026-09-16

**Status: future development. Nothing built, nothing approved, no external call added.**
Written by lead at the operator's request ("a brief report on feasibility, accepting it would be
an external call for bonus information"). Every claim below is from a page read on 2026-09-16
with the operator's permission; the reads are registered in
[`../external_calls.md`](../external_calls.md) Part B. Where something could not be read, it says
so.

## The question

On a motor-vehicle-incident call, pull Waze's live incidents near the address; on a bridge or
highway call, show the nearest DriveBC webcam. Both would be Part A calls of the Street View
kind: on the kiosk, in service, **bonus information that degrades visibly** and never on the
path to the address (CLAUDE.md §1 as ruled 2026-09-16).

## Waze — three routes, only one of them is licensed

| Route | What it is | Cost | Rights |
|:--|:--|:--|:--|
| **Waze for Cities** (Google's partner programme) | A data feed of "real time hazards and incidents such as crashes, construction, emergency vehicles" and "live and upcoming road closures, lane closures and major traffic-impacting events" for the partner's area, plus BigQuery access | "offered free of charge" | Eligible: "authorities that manage traffic or public infrastructure, including transportation departments, **emergency services**, road operators and other public agencies." Application through the Partner Hub with an organisation work email. Format, refresh rate and geography are **not stated on the public page**. |
| openwebninja.com "Waze API" | A third party, not Waze or Google. Alerts (road closures, hazards, police), jams, directions, by bounding box; max 200 alerts / 800 jams per request; API key | Free 100 req/month; $25/month for 10,000; pay-as-you-go $0.005/request | **No statement of how it obtains Waze's data and no terms about the source.** It reads as a scrape of the Waze live map. |
| wazeapi.com | A third party; footer: "Not affiliated with or endorsed by Waze Mobile Ltd. or Google LLC." Area alerts, area jams, route alerts, ETAs; API key | Free 100 one-time; $35/month for 20,000; pay-as-you-go $0.002/request | Terms exist but were not readable; "exactly what millions of Waze drivers see, delivered as clean JSON" is a scrape by its own description. |

**Assessment.** The two third-party APIs would work technically — a bounding box around the
dispatch address on an MVI, one request per call, a handful of alerts back — and either fits the
$0 rule at the free tier for this department's call volume. **But both are unlicensed
redistribution of Waze's data as far as any reachable document says**, and the project's rule
since #47b is that a rights problem is not solved by the call being cheap. Building on one would
put a second 47b on the list on day one.

**The route that fits every rule is Waze for Cities.** It is free, it is the official feed, it
names emergency services as eligible, and it is the data source the scrapers are scraping. The
cost is a partnership application by the department — or a question to the City, which may
already hold a feed for its traffic operations. **Operator, 2026-09-16: "Not sure if they are a
partner, I can ask later in development. Assume yes for now."**

### Where the documentation is (read 2026-09-16, second pass)

Google keeps it in the **Waze Partners Help centre**, `support.google.com/waze/partners/`, under
"Use the Waze for Cities data-sharing tools" (`/waze/partners/topic/10616686`). The two articles
that matter:

- **"Waze Data Feed specifications"** — `support.google.com/waze/partners/answer/13458165`. The
  feed is JSON (`format=1`) or XML with GeoRSS (`format=2`); it carries **alerts**, **jams** and
  **irregularities**. The URL comes from the Partner Hub and has the structure
  `https://www.waze.com/partnerhub-api/partners/<partner-id>/waze-feeds/<unique-token>?format=<format>`.
  Alert `type` ∈ ACCIDENT, JAM, WEATHERHAZARD/HAZARD, MISC, CONSTRUCTION, ROAD_CLOSED, with
  subtypes such as ACCIDENT_MINOR, ACCIDENT_MAJOR, JAM_STAND_STILL_TRAFFIC,
  HAZARD_ON_ROAD_CONSTRUCTION, ROAD_CLOSED_EVENT (twenty-odd). Alert fields: `uuid, type,
  subtype, location (x/y), pubMillis, reliability, confidence, reportRating, street, city,
  roadType, magvar, reportDescription`. Jam fields include `line, speed, speedKPH, length,
  delay, level, blockingAlertUuid`. **The polling interval is not stated on the page.**
- **"How to give Waze attribution"** — `support.google.com/waze/partners/answer/10618825`. Any
  display must carry the Waze logo and one of: "Data provided by Waze App. Learn more at
  Waze.com" (hyperlinked) or "Data by Waze App. https://waze.com". Any other use of Waze data —
  "academic papers, presentations, charts and graphs, marketing materials" — needs Google's
  prior written consent. So an alert on the kiosk carries a logo and a line; a figure in a
  department report does not happen without asking Google first. That goes in
  `docs/standards/data_sources.md` the day a feed exists.

The `reliability`, `confidence` and `reportRating` fields are what §7.6 asked for above: the
measurement of whether a crowd-reported alert is trustworthy enough to sit beside a dispatch
address is a threshold on those, chosen on the corpus, not guessed. `pubMillis` gives the age.

For the ACCIDENT type specifically — the MVI case the operator raised — the feed answers "is
there a Waze-reported crash near this address right now", with a subtype (MINOR / MAJOR), a
street and a reliability score. That is the bonus information in one request, filtered to the
dispatch address's surroundings on the kiosk, never on the path to the address.

Two things the feed would need to be checked for before it reached a crew (§7.6): whether an
alert's coordinates and timestamp are trustworthy enough to place beside a dispatch address
(Waze alerts are crowd-reported, with a reliability score the third-party APIs expose and the
partner feed presumably does too), and how stale an alert can be before it is misleading on a
call. Both are measurements, not guesses, and both need the real feed.

## DriveBC webcams

`github.com/bcgov/drivebc-webcam-api` says MOTI released "images and data from these highway
and traffic cameras on DataBC for commercial use under the Open Government License (OGL) —
British Columbia" and its code is Apache 2.0. **So the rights are clear.**

**The camera list is a published dataset, found through the operator's open.canada.ca link:**
"DriveBC HighwayCams", Government of British Columbia, OGL-BC —
`catalogue.data.gov.bc.ca/dataset/6b39a910-6c77-476f-ac96-7b4f18849b1c`, a CSV of about 335
cameras with `id, highway_number, highway_locationDescription, camName, caption, orientation,
latitude, longitude` and stable image URLs of the form
`https://images.drivebc.ca/bchighwaycam/pub/cameras/<id>.jpg` (thumbnail under `tn/`, a
"replay the day" player). The catalogue warns the image host has changed before. Near the
response area: **292 "Port Mann Bridge - W"** (Highway 1 at the Port Mann, looking westbound,
49.210134, -122.807465), 192 / 193 / 195 on the Lougheed at Kennedy Road, 199 on Mary Hill at
Kingsway. Placing a camera beside a route is a PostGIS nearest-point query on that CSV — no API
needed.

`images.drivebc.ca` itself could not be reached from the dev laptop (one HEAD and one GET
returned nothing, no error; a recollected `/webcam/api/v1/` path reset the connection). Not
diagnosed; the kiosk may reach it. The public camera page `drivebc.ca/cameras/292` is a
JavaScript shell with no readable content.

**Assessment — operator ruling 2026-09-16: "DriveBC cameras are 15 minute intervals. So not
overly useful."** That interval is his knowledge, not stated on any page read (§6.3 tier 4),
and it decides the question: a frame up to fifteen minutes old beside a bridge call is stale
information that reads as current — the §6.1 failure this document warned of — and the crew
will be on scene before the next frame. **Low value; stays on the backlog, not pursued.** If it
is ever revisited, the image must show its capture age or not show at all.

## What would have to be true before either is built

1. Rights settled on paper: Waze for Cities partnership, or OGL-BC for the webcams, cited in
   `docs/standards/data_sources.md`.
2. A Part A row in `docs/external_calls.md` with the crew-visible failure written down.
3. The call is made only while a call of the right type is active (MVI; highway or bridge), one
   request, on the dispatch display, never blocking anything.
4. Freshness is visible on the display, or the item is not shown (§6.1).
5. The operator's permission for the call (ruling 2026-08-31), after the freeze.

## Backlog

One line each in [`../post_freeze_backlog.md`](../post_freeze_backlog.md): Waze (partnership
assumed for now on the operator's word; the spec and attribution terms are above), DriveBC
webcams (fifteen-minute frames; low value, not pursued).
