# CFR EVO: Operational Background, System Purpose & Design Rationale

---

## Part 1: Operational Pitch & Core Rationale
*(A structured summary of the operational problem, field observations, and technical solution for discussion with station members and management.)*

### 1. The Origin Story: From Driver Training Game to Emergency Response HUD
* **The Starting Point**: The project originally began as an interactive map study tool and quiz game. Senior firefighters often talked about the rigorous map drills of the past—spending hours memorizing street names, grid boundaries, and arterial intersections.
* **The Practice App**: Using basic web development and the City of Coquitlam's open GIS data, a training tool was built to test street knowledge and zone familiarity from the driver's perspective.
* **The Evolution**: As the mapping engine grew more accurate, it became obvious that the same geospatial engine could do far more than static study drills. By connecting the local mapping database to line-in radio dispatch audio using local speech-to-text processing, the study tool evolved into a real-time, sub-second apparatus bay dispatch system.

### 2. The Core Problem: Systemic Friction in Turnout Times
* **The Pressure**: Department leadership and performance standards emphasize reducing chute and turnout times.
* **The Reality on the Floor**: Turnout delays are not caused by crew members moving slowly. They are caused by a disjointed, analog workflow that places an unequal logistical burden on the apparatus driver before the vehicle can move.
* **The Chokepoint**: While jump-seat firefighters only need to don turnout gear and board, the driver must simultaneously listen to the radio, wait for a sleeping printer, search a physical map rack, orient a laminated grid sheet, search for addresses (which may be missing on older maps due to new development), plan a route from memory, and start the apparatus.

### 3. "Designed in Coquitlam for Coquitlam": The Municipal Data Advantage
* **Single Source of Official Truth**: Rather than relying on generic commercial maps, CFR EVO ingests the official geospatial datasets that the City of Coquitlam already publishes open-source (the same foundation behind the city's *QtheMap* portal).
* **Parcels & Building Outlines**: Boundary polygons and frontage points for all 69,000+ addressed properties in Coquitlam are cached locally. When the City updates a subdivision or parcel, the data synchronizes into the fire department's database automatically.
* **Hydrant Flow & Operational Status**: Ingests rated hydrant layers with NFPA 291 color coding and active operational status—providing immediate flow capability that legacy CAD/PIPS screens often lack.
* **Morning Shift Road Closure Awareness**: Integrates municipal construction and road closure notices. Crews can review active and upcoming closures on station screens at the start of shift.
* **Offline Apparatus-Aware Routing**: A custom, 100% offline routing engine tailored for heavy fire engines and ladder trucks. It applies operational corridor biasing (preferring primary emergency corridors even if a secondary residential shortcut is a few seconds shorter) and dynamically routes around or flags active city road closures.

### 4. The Legacy Workflow vs. The EVO System

| Step | Legacy Station Workflow | CFR EVO System |
| :--- | :--- | :--- |
| **Driver Training & Knowledge** | Static paper map memorization and flash cards. | Interactive street-name and zone quiz engine with real municipal data. |
| **Alerting** | Listen to radio broadcast; decipher non-unique tones over station ambient noise. | Automated line-in radio capture; sub-second tone detection. |
| **Address Identification** | Wait for thermal printer to wake from sleep and print "rip & run" slip. | Immediate address display on high-visibility bay monitors before voice broadcast finishes. |
| **Map Lookup** | Walk to wall rack, pull laminated map sheet, flip to back, locate grid coordinates. | Automatic parcel boundary, building footprint, and frontage point loaded from municipal GIS. |
| **Data Currency** | Static paper maps that do not reflect recent subdivisions, redevelopments, or street changes. | Real-time vector shapefiles with 69,000+ indexed Coquitlam addresses and emergency zones. |
| **Water Supply & Hydrants** | Officer or driver manually checks paper maps for hydrants while driving. | Pre-calculated NFPA 291 color-coded hydrants with flow ratings and distance rings. |
| **Road Hazards & Closures** | Relies on memory of paper bulletins or radio updates. | Active municipal road closures highlighted on the map; daily morning dashboard view. |
| **Routing & Pathfinding** | Driver recalls memory routes; no allowance for heavy apparatus turn restrictions. | Offline emergency routing with arterial corridor biasing and closure avoidance. |
| **Crew Role Alignment** | Driver handles all mapping and paper logistics while trying to get the truck running. | Driver focuses 100% on vehicle startup and road safety. Officer/junior member grabs paper as backup for the doghouse. |

### 5. Key Operational Outcomes
1. **Shaves Critical Seconds off Chute Times**: Information is visible on the apparatus bay screen the moment the tones drop.
2. **Reduces Driver Cognitive Overload**: Eliminates the paper hunt during high-stress callouts.
3. **Improves Spatial Pre-Planning for Officers**: Officers can see building layouts, aerial views, street view frontage, and hydrant locations while walking to the rig and en route.
4. **100% Offline Station Reliability**: Runs entirely on local fire hall hardware (PostgreSQL, local APIs, and MQTT). Operates with zero cloud subscriptions, zero monthly software fees, and zero dependency on external internet connections.

---

## Part 2: Verbatim Driver Commentary (Voice Journal)
*(Recorded by Apparatus Driver during workflow observation, operational testing, and system design.)*

### Entry 1: Turnout Friction & The Driver's Chokepoint
> *"When I first started driving, I found that there were some things lacking in our system. With pressure from management to have faster response times, I started looking at the system as a whole, breaking it down into parts and pieces, and really observing where we have the biggest slowdowns.*
> 
> *One of them is with the driver, not necessarily because anyone is slow-rolling a call, but the system is: listen for non-unique truck tones, wait to hear an address, stand by a printer that has to come out of standby and actually print a rip and run. Then you have to look at the address, find the zone map on there, walk over to the zone map holders, find your zone, and pull out a plastic-sized piece of paper that you immediately flip to the back because the front is garbage and nobody uses it.*
> 
> *Then you grab your rip and run, confirm your address, look at your plastic-sized piece of paper, orient it to the north, figure out where you're standing, and find the address you're going to, which sometimes isn't actually even on the map because places get developed or subdivided. So you find where you're going, write it down, take a quick look to make sure you get it right, and go off of historical best practices for routing.*
> 
> *Then you grab all that gear, and if you are going to a call requiring your turnout gear, you put on your bare minimum turnout gear and get the truck started, when in reality the rest of the crew just had to get their gear on. So the driving role had a lot of optimizations that could be made.*
> 
> *One of the big things is how do we display relevant, high-impact information to drivers that can cut our response times. Part of this system redesign is maybe we grab the laminated placemap as a backup, because all systems do fail, but maybe now that's something that the officer grabs or the junior guy grabs. Just grab the rip and run, get it to the officer, grab the placemap, put it on the doghouse, and then if we need it, we need it. Otherwise, both of those could go to the officer and now they can actually look at the zone map and do some pre-planning on the way to an incident with the placemap."*

### Entry 2: "Designed in Coquitlam for Coquitlam" & The Municipal GIS Advantage
> *"This system is designed in Coquitlam for Coquitlam. First of all, all of the data and processing happens completely offline, so we're not relying on external servers for any of the core processes. There are a few APIs that we're leveraging, such as the Google Street View and some of the open-source ArcGIS ESRI satellite imagery. But for the most part, the idea of this project was to use the official mapping, geospatial information, and notifications that the city already produces and publishes open-source for the public.*
> 
> *For example, we use the map tiles that the Q the Map system displays. We pull the emergency zone layers, the hydrant information layers, which now includes status and classification, which are pips are missing, and we also pull all of the parcel data which shows the boundary boxes of every individual addressed property in Coquitlam.*
> 
> *By pulling that information and caching it with periodic re-updates, the fire department's official information is coming from Coquitlam itself, so updates that are made on one end should be propagated across naturally anyways. But what's really cool is this lets us tie in the system to get road closure information that's updated by the city, and we can display that and alert our drivers that, hey, you know, if they wanted to check in the morning, be like, oh, hey, there's all these new road closures they should be aware of.*
> 
> *We also have it so that when a route is formed by the system, which again is completely offline and custom-made for emergency vehicles with allowances for weighting, say, always bias taking Johnson Street versus Pine Tree Street if it only adds a few seconds. So, by having the road closure information in a database, we can then route around it if we wanted to or even just flag the route and be like, hey, heads up, there's some construction here, and a new route can be picked."*

### Entry 3: The Genesis — From Map Memorization Drills to Live Audio Dispatch
> *"Where this entire project really started was as a game I developed using the Coquitlam data sources to develop a little project to help me as a driver just get better at road names and stuff because I remember the old guys used to say we did all this map practice and training and memorizing. So I kind of wanted to build a test my own knowledge using the skills I have with coding and information systems to come up with something I could practice with as a new driver and it slowly evolved with more advanced tools like Google ANT Gravity IDE. So I started building on this project that started off as a training program and it slowly evolved into a more comprehensive mapping project and then I thought about tying in dispatch data through audio software."*

---

## Part 3: Engineering Principles & Infrastructure

1. **Pragmatic Utility Over Complexity**  
   The interface is built around the "10-foot rule": high-contrast UI, large typography, and mission-critical metrics (Address, Map Grid, Assigned Units, Radio Channel, Hydrants, Road Hazards) readable from anywhere in the apparatus bay.

2. **Local Data Sovereignty & Offline Resilience**  
   All core systems—radio tone capture, local Whisper transcription, Coquitlam GIS validation, apparatus routing, and MQTT dispatch broadcasts—operate 100% locally on fire hall hardware. Internet connectivity is only used for auxiliary visual imagery (Street View / Satellite).

3. **Municipal Data Alignment**  
   By caching Coquitlam's official open GIS shapefiles directly, the department avoids paying commercial mapping vendors for data the City already owns and updates.

4. **Complementary Redundancy, Not Replacement**  
   Physical map books and printed rip-and-run slips remain in the station as an essential fail-safe on the engine's doghouse. CFR EVO eliminates the paper dependency during the turnout scramble without eliminating the physical backup.
