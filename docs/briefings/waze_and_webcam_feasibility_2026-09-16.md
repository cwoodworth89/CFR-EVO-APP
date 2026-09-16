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
already hold a feed for its traffic operations. **Recommendation: ask the City whether Coquitlam
is a Waze for Cities partner before any code is written.** If it is, the feed is a Part A row
with a "what a crew sees when it drops" line, like Street View. If it is not, the department
applies, or the idea waits.

Two things the feed would need to be checked for before it reached a crew (§7.6): whether an
alert's coordinates and timestamp are trustworthy enough to place beside a dispatch address
(Waze alerts are crowd-reported, with a reliability score the third-party APIs expose and the
partner feed presumably does too), and how stale an alert can be before it is misleading on a
call. Both are measurements, not guesses, and both need the real feed.

## DriveBC webcams

`github.com/bcgov/drivebc-webcam-api` says MOTI released "images and data from these highway
and traffic cameras on DataBC for commercial use under the Open Government License (OGL) —
British Columbia" and its code is Apache 2.0. **So the rights are clear.** The README documents
no endpoint, and the two endpoint reads attempted from here failed (a recollected
`images.drivebc.ca` URL reset the connection; the repository's `code/` path 404'd) — **the API's
shape, refresh interval and camera list are not verified.** Stopped after two attempts (§7.7).

**Assessment.** Licensed, free, and provincial highways are exactly where the cameras are — the
Lougheed, Barnet, the Mary Hill Bypass, the bridges. On a highway or bridge call, the nearest
camera image beside the route is plausible bonus information of the Street View kind: one image
fetch per call, degrades to "no camera image" when the link drops. What has to be measured
first: which cameras fall inside the response area (the camera list, once reachable), how old
an image can be (refresh interval), and whether an image ever reads as *current* when it is
not — a stale camera frame on a bridge call is a §6.1 failure, so the image must carry its
capture time visibly or not show at all.

## What would have to be true before either is built

1. Rights settled on paper: Waze for Cities partnership, or OGL-BC for the webcams, cited in
   `docs/standards/data_sources.md`.
2. A Part A row in `docs/external_calls.md` with the crew-visible failure written down.
3. The call is made only while a call of the right type is active (MVI; highway or bridge), one
   request, on the dispatch display, never blocking anything.
4. Freshness is visible on the display, or the item is not shown (§6.1).
5. The operator's permission for the call (ruling 2026-08-31), after the freeze.

## Backlog

One line each in [`../post_freeze_backlog.md`](../post_freeze_backlog.md): Waze (ask the City
first), DriveBC webcams (find the endpoint, measure freshness).
