# Frontend Domain Rules & UX Constraints

Rules and constraints for React, Leaflet, TailwindCSS, and MQTT code in `frontend/`.

---

## 1. Real-Time MQTT WebSockets
* **Persistent WebSocket Handlers**: Store callback handlers (`onInsert`, `onUpdate`, `onDelete`) in a `useRef` inside [`frontend/src/hooks/useMqttListener.js`](src/hooks/useMqttListener.js) to prevent WebSocket teardown and reconnection loops on component re-renders.
* **WSS Protocol**: Under HTTPS/Nginx reverse proxy, target WebSocket path `wss://${hostname}/mqtt` over port 443. For local dev, connect to `ws://${hostname}:9001`.

---

## 2. Leaflet & Turf.js Spatial Performance
* **In-Memory Bbox Filtering**: Hydrants (3,381 points) and emergency zones (134 polygons) must be filtered client-side via Turf.js bounding boxes (`turf.bboxClip` / `turf.booleanPointInPolygon`) on map pan/zoom.
* **Vector Boundary Rules**: Coquitlam Emergency Response Zones must enforce `minZoom={12}` and automatic `zoom 16` cutoff for label density.
* **NFPA 291 Standards**: Render hydrants with color-coded flow ratings: Class AA Blue (>=1500 GPM), Class A Green (1000-1499 GPM), Class B Orange (500-999 GPM), Class C Red (<500 GPM).

---

## 3. Reviewer Ergonomics & Hotkeys
* **Submit Hotkeys**: Maintain `Ctrl+Enter` and `Alt+Enter` hotkeys for instant dispatch verification submission.
* **Auto-Advance & Audio Auto-Play**: Submitting a verification must auto-select the next dispatch row, reset form scroll to top, and automatically start playback of the new call audio.
* **Sequential Dispatch Alignment**: Keep verification input fields ordered by verbal announcement sequence: `Captured Dispatch Tone` -> `Verified Units` -> `Verified Incident Type` -> `Verified Address` -> `Subaddress` -> `Talkgroup & Map Grid` -> `Verified Ground-Truth Transcript`.
