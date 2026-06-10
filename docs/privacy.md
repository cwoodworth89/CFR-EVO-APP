# Privacy Policy & Audio Processing Design

This document details the privacy-preserving design of the CFR-EVO system, outlining how audio is processed locally and explaining the public nature of all stored datasets.

---

## 1. Passive Audio Monitoring & Privacy

The system uses a microphone or line-in feed to pick up dispatch audio from the hall's radio receivers. However, **it does not capture or record background conversations.**

### How it Works (Alexa/Siri/Gemini Model)
The audio listening agent operates similarly to standard offline wake-word engines (like Siri or Alexa):
1. **Passive Local Monitoring**: The system runs a continuous, temporary audio buffer entirely in local volatile memory (RAM). This buffer is never saved to disk or transmitted over the network.
2. **Wake-Tone Activation**: The local code analyzes this temporary buffer strictly looking for the station's specific **dispatch alert tones** (the 2-tone sequential paging frequencies).
3. **No Conversational Recording**: Ambient room noise, conversations, and unrelated radio chatter are ignored and immediately overwritten in memory.
4. **Targeted Transcription**: Only when a valid alert tone sequence is matched does the system record the ensuing radio dispatch announcement. 
5. **Metadata Extraction**: Once transcribed, only the structured call details (incident type, address, dispatched units, response priority, and talk group channel) are extracted. The raw audio and transcript are used only to populate the dispatch dashboard.

---

## 2. Public Nature of Collected Data

All information collected, geocoded, and displayed by this application consists of **publicly available datasets**. No private personal data, PII (Personally Identifiable Information), or confidential city records are stored.

*   **Dispatch Announcements**: Dispatch calls are broadcast over public, unencrypted VHF/UHF radio bands and public safety trunked channels, which are accessible via standard radio scanners.
*   **Property Addresses**: The parcel cadastral datasets are public records provided freely by the City of Coquitlam Open Data Portal.
*   **Fire Hydrants**: The hydrant locations, status, and flow classes are public infrastructure assets provided by the city's public water utilities services.
*   **Response Zones**: Emergency response grid maps are standard public zoning boundaries.

---

## 3. Data Storage & Transmission

All parsed call details are transmitted securely to a dedicated database instance (Supabase) and are used solely to populate the incident mapping screens at the stations. The database holds no records of who is in the room, ambient audio, or off-duty personnel conversations.
