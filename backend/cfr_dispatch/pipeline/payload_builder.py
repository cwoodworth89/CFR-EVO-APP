import re
import datetime
import logging
from typing import List, Tuple, Any

from cfr_dispatch.config.cloud import INTEGRATION_PAYLOAD_OPTION
from cfr_dispatch.config.models import DispatchData
from cfr_dispatch.parser import (
    match_incident_type,
    abbreviate_units,
    reconstruct_template_transcript,
    CALL_TYPES
)

from cfr_dispatch.pipeline.review_flags import (
    compute_review_flags, LOCATION_UNRESOLVED, LOCATION_SUBSTITUTED,
)

def clean_address_string(addr: str) -> str:
    """Strips postal codes and regional/provincial suffix boilerplate from address strings."""
    if not addr:
        return addr
    addr = re.sub(r',\s*[A-Z]\d[A-Z]\s*\d[A-Z]\d', '', addr, flags=re.IGNORECASE)
    addr = re.sub(r',\s*(BC|British Columbia)\b.*', '', addr, flags=re.IGNORECASE)
    addr = re.sub(r',\s*Canada\b.*', '', addr, flags=re.IGNORECASE)
    addr = re.sub(r',\s*Coquitlam\b.*', '', addr, flags=re.IGNORECASE)
    addr = re.sub(r',\s*Port Coquitlam\b.*', '', addr, flags=re.IGNORECASE)
    addr = re.sub(r',\s*Port Moody\b.*', '', addr, flags=re.IGNORECASE)
    return addr.strip()

def build_dispatch_payload(
    dispatch_id: str,
    raw_transcript: str,
    sanitized_transcript: str,
    all_candidates: List[DispatchData],
    validator: Any,
    units_vocabulary: List[str] = None,
    verify_location_override: bool = None,
    audio_url: str = None,
    audio_duration: float = None,
    verified_transcript: str = None,
    tone_name: str | list = None,
    is_test: bool = False
) -> Tuple[dict, list]:
    """
    Unified constructor for dispatch payloads conforming to local database and MQTT contracts.
    Handles offline local GIS validation, fallback scoring, subaddress isolation, and template reconstruction.
    """
    unique_addresses = []
    for d in all_candidates:
        if d.address and d.address not in unique_addresses:
            unique_addresses.append(d.address)
        if d.intersection and d.intersection not in unique_addresses:
            unique_addresses.append(d.intersection)
            
    # Extract cross streets for geocoder narrowing
    x_street_1 = next((d.x_street_1 for d in all_candidates if d.x_street_1), None)
    x_street_2 = next((d.x_street_2 for d in all_candidates if d.x_street_2), None)
            
    incident_type = match_incident_type(sanitized_transcript, CALL_TYPES)
    if incident_type == "Unknown Incident" and all_candidates:
        for cand in all_candidates:
            if getattr(cand, "call_type", None) and cand.call_type != "Unknown Incident":
                incident_type = cand.call_type
                break
    units_str = next((d.units for d in all_candidates if d.units), None)
    responding_units = abbreviate_units(units_str)

    is_specific_placeholder = "contact dispatch" in sanitized_transcript.lower() or "location information" in sanitized_transcript.lower()
    
    if is_specific_placeholder:
        unique_addresses = ["Contact dispatch for location information"]
    
    if not unique_addresses:
        if responding_units or incident_type != "Unknown Incident":
            logging.warning(f"[{dispatch_id}] No address parsed, but incident details found. Using 'Unknown Location' fallback.")
            unique_addresses = ["Unknown Location"]
        else:
            logging.warning(f"[{dispatch_id}] No address or details found. Storing fallback for manual review.")
            unique_addresses = ["Unknown Location"]
            verify_location_override = True
        
    local_geocode_result = None
    
    first_candidate = unique_addresses[0] if unique_addresses else "Unknown Location"
    
    if first_candidate == "Contact dispatch for location information":
        local_geocode_result = {
            "address": first_candidate,
            "lat": None,
            "lng": None,
            "rings": []
        }
    elif first_candidate == "Unknown Location":
        local_geocode_result = {
            "address": first_candidate,
            "lat": None,
            "lng": None,
            "rings": []
        }
    else:
        for i, candidate_address in enumerate(unique_addresses):
            logging.debug(f"[{dispatch_id}] Attempting Local Geocode for Candidate #{i+1}: '{candidate_address}'")
            res = validator.local_geocode(
                candidate_address,
                target_map_grid=next((d.map_grid for d in all_candidates if d.map_grid), None),
                x_street_1=x_street_1,
                x_street_2=x_street_2
            ) if validator else None
            if res:
                logging.info(f"[{dispatch_id}] Local GIS Match SUCCEEDED: '{res['address']}'")
                local_geocode_result = {
                    "address": res["address"],
                    "lat": res["lat"],
                    "lng": res["lng"],
                    "rings": res.get("rings", [])
                }
                # A "<street> and <street>" dispatch resolves to a street SECTION rather
                # than a point. These fields are what let the kiosk highlight the stretch
                # and warn that it is not a located incident; dropping them here would
                # leave the representative midpoint looking like an exact match.
                for k in ("location_type", "segment", "endpoints", "length_m",
                          "resolution_note", "requested_address"):
                    if res.get(k) is not None:
                        local_geocode_result[k] = res[k]
                break
        
        if not local_geocode_result:
            logging.warning(f"[{dispatch_id}] Geocoding failed for '{first_candidate}'. Storing with null coordinates.")
            local_geocode_result = {
                "address": first_candidate,
                "lat": None,
                "lng": None,
                "rings": []
            }

    best_address = clean_address_string(local_geocode_result["address"])
    lat = local_geocode_result["lat"]
    lng = local_geocode_result["lng"]
    rings = local_geocode_result["rings"]
    # TWO VARIABLES, never a list. Locution announces
    #   [address] NEAR [x_street_1] AND [x_street_2]
    # and either may be omitted. This was `[s for s in [c1, c2] if s]`, and that
    # filter destroyed position: an announcement carrying only the SECOND street
    # landed it at index 0, where every reader took it for the first.
    # Absent stays None -- an omitted XStreet is a real answer (CLAUDE.md 6.1).
    
    timestamp = datetime.datetime.now().astimezone().isoformat()
    
    map_grid = next((d.map_grid for d in all_candidates if d.map_grid), None)
    if (not map_grid or str(map_grid).lower() == "none") and lat is not None and lng is not None and validator:
        spatial_grid = validator.get_map_grid_for_point(lat, lng)
        if spatial_grid:
            map_grid = spatial_grid
            logging.info(f"[{dispatch_id}] Spatial fallback: Map grid auto-populated from emergency response zones -> '{map_grid}'")

    radio_channel = next((d.radio_channel for d in all_candidates if d.radio_channel), None)
    
    # Parsed once, and NOT defaulted. An unparsed response type is None and stays
    # None all the way to the kiosk, which renders it UNKNOWN on an amber border
    # (operator ruling 2026-08-23, CLAUDE.md 6.1). This previously defaulted to
    # "emergency" here and to "routine" in four other places, so the same unparsed
    # call was routed one way and reconstructed the other. Punch-list #31.
    detected_resp = next((d.response_type for d in all_candidates if d.response_type), None)

    # Named review flags replace the old confidence score (punch-list #45).
    #
    # What was here: the geocoder's score minus 30 for no coordinates, 20 for no
    # units, 15 for no map grid, 15 for no talk group, with anything under 90
    # setting verify_location. A correct address with an untranscribed talk group
    # scored 85; a confidently WRONG address scored 100. The penalties had no
    # provenance, were not commensurable, and destroyed the very information they
    # consumed -- by the time the operator saw "85" the missing field was gone.
    review_flags = compute_review_flags(
        lat=lat,
        lng=lng,
        responding_units=responding_units,
        incident_type=incident_type,
        map_grid=map_grid,
        radio_channel=radio_channel,
        response_type=detected_resp,
        resolution_note=local_geocode_result.get("resolution_note"),
        location_type=local_geocode_result.get("location_type"),
    )

    # verify_location survives as the operator-facing "check this location" marker,
    # but is now driven by a NAMED condition rather than an arithmetic threshold.
    verify_location = LOCATION_UNRESOLVED in review_flags or LOCATION_SUBSTITUTED in review_flags

    if verify_location_override is not None:
        verify_location = verify_location_override
        
    # Calculate per-unit routing metrics from home hall origins (accounting for Emergency vs Routine response)
    routing_metrics = []
    if lat is not None and lng is not None and responding_units:
        try:
            from gis_service.routing_engine import EVORoutingEngine
            router = EVORoutingEngine()
            routing_metrics = router.calculate_units_routing(
                responding_units, lat, lng, response_type=detected_resp,
                destination_options=local_geocode_result.get("endpoints"))
            logging.info(f"[{dispatch_id}] Computed {detected_resp or 'unknown (routing at emergency speed)'} routing metrics for {len(routing_metrics)} responding units.")
        except Exception as route_err:
            logging.warning(f"[{dispatch_id}] Could not compute routing metrics: {route_err}")

    subaddress = next((d.subaddress for d in all_candidates if d.subaddress), None)
    target_payload = {
        "address": best_address,
        "lat": lat,
        "lng": lng,
        "rings": rings,
        "map_grid": map_grid,
        "radio_channel": radio_channel,
        "routing_metrics": routing_metrics,
        "x_street_1": x_street_1,
        "x_street_2": x_street_2,
        # Named reasons this dispatch may need a human look, and their count
        # (punch-list #45). These live in TARGET, not at the top level: there is no
        # review_flags column, and the API applies updates with
        # `setattr(call, key, val)` over a Pydantic model_dump, so a top-level key
        # with no schema field is silently DROPPED. Putting them here also means
        # phase 2 replacing `target` wholesale replaces the flags with it, which is
        # exactly the lifecycle wanted -- a stale phase 1 flag cannot outlive the
        # correction that fixed it.
        "review_flags": review_flags,
        "review_flag_count": len(review_flags),
        # 'routine' | 'emergency' | None. None means the dispatch did not announce it
        # or it did not transcribe -- never a guess. Punch-list #31.
        "response_type": detected_resp,
    }
    for k in ("location_type", "segment", "endpoints", "length_m",
              "resolution_note", "requested_address"):
        if local_geocode_result.get(k) is not None:
            target_payload[k] = local_geocode_result[k]
    if subaddress:
        target_payload["subaddress"] = subaddress
    if tone_name:
        if isinstance(tone_name, list):
            target_payload["captured_tones"] = tone_name
            target_payload["tone_name"] = ", ".join(tone_name)
        else:
            target_payload["tone_name"] = str(tone_name)
            target_payload["captured_tones"] = [t.strip() for t in str(tone_name).split(",") if t.strip()]
    if all_candidates and all_candidates[0].intersection:
        target_payload["intersection"] = all_candidates[0].intersection
    
    # Template Reconstruction
    reconstructed_transcript = sanitized_transcript
    if all_candidates and not is_specific_placeholder and best_address != "Unknown Location":
        try:
            candidate_copy = DispatchData(
                raw_text=all_candidates[0].raw_text,
                units=units_str,
                response_type=all_candidates[0].response_type,
                call_type=incident_type,
                address=best_address,
                intersection=all_candidates[0].intersection,
                x_street_1=x_street_1,
                x_street_2=x_street_2,
                radio_channel=radio_channel,
                map_grid=map_grid,
                subaddress=subaddress
            )
            reconstructed_transcript = reconstruct_template_transcript(candidate_copy)
            logging.debug(f"[{dispatch_id}] Reconstructed template transcript: '{reconstructed_transcript}'")
        except Exception as r_err:
            logging.warning(f"[{dispatch_id}] Failed to reconstruct template transcript: {r_err}")

    db_payload = {
        "dispatch_id": dispatch_id,
        "incident_type": incident_type,
        "responding_units": responding_units,
        "routing_metrics": routing_metrics,
        "timestamp": timestamp,
        "raw_transcript": raw_transcript,
        "sanitized_transcript": reconstructed_transcript,
        "verify_location": verify_location,
        "is_test": is_test
    }
    
    if audio_url is not None:
        db_payload["audio_url"] = audio_url
    if audio_duration is not None:
        db_payload["audio_duration"] = audio_duration
    if verified_transcript is not None:
        db_payload["verified_transcript"] = verified_transcript
    
    if INTEGRATION_PAYLOAD_OPTION == 1:
        db_payload["address"] = best_address
    else:
        db_payload["target"] = target_payload

    return db_payload, responding_units
