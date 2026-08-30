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
    cross_street_1 = next((d.cross_street_1 for d in all_candidates if d.cross_street_1), None)
    cross_street_2 = next((d.cross_street_2 for d in all_candidates if d.cross_street_2), None)
            
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
    confidence_score = 0.0
    
    first_candidate = unique_addresses[0] if unique_addresses else "Unknown Location"
    
    if first_candidate == "Contact dispatch for location information":
        local_geocode_result = {
            "address": first_candidate,
            "lat": None,
            "lng": None,
            "rings": []
        }
        confidence_score = 100.0
    elif first_candidate == "Unknown Location":
        local_geocode_result = {
            "address": first_candidate,
            "lat": None,
            "lng": None,
            "rings": []
        }
        confidence_score = 0.0
    else:
        for i, candidate_address in enumerate(unique_addresses):
            logging.debug(f"[{dispatch_id}] Attempting Local Geocode for Candidate #{i+1}: '{candidate_address}'")
            res = validator.local_geocode(
                candidate_address,
                target_map_grid=next((d.map_grid for d in all_candidates if d.map_grid), None),
                cross_street_1=cross_street_1,
                cross_street_2=cross_street_2
            ) if validator else None
            if res:
                conf = res.get("confidence", 85.0)
                logging.info(f"[{dispatch_id}] Local GIS Match SUCCEEDED: '{res['address']}' (Score: {conf}%)")
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
                confidence_score = float(conf)
                break
        
        if not local_geocode_result:
            logging.warning(f"[{dispatch_id}] Geocoding failed for '{first_candidate}'. Storing with null coordinates.")
            local_geocode_result = {
                "address": first_candidate,
                "lat": None,
                "lng": None,
                "rings": []
            }
            confidence_score = 0.0

    best_address = clean_address_string(local_geocode_result["address"])
    lat = local_geocode_result["lat"]
    lng = local_geocode_result["lng"]
    rings = local_geocode_result["rings"]
    target_cross_streets = [s for s in [cross_street_1, cross_street_2] if s]
    
    timestamp = datetime.datetime.now().astimezone().isoformat()
    
    map_grid = next((d.map_grid for d in all_candidates if d.map_grid), None)
    if (not map_grid or str(map_grid).lower() == "none") and lat is not None and lng is not None and validator:
        spatial_grid = validator.get_map_grid_for_point(lat, lng)
        if spatial_grid:
            map_grid = spatial_grid
            logging.info(f"[{dispatch_id}] Spatial fallback: Map grid auto-populated from emergency response zones -> '{map_grid}'")

    radio_channel = next((d.radio_channel for d in all_candidates if d.radio_channel), None)
    
    # Structured Confidence Scoring
    verify_location = False
    if best_address == "Contact dispatch for location information":
        confidence_score = 100.0
        verify_location = False
    else:
        base_confidence = confidence_score if confidence_score is not None else 0.0
        penalties = 0.0
        if lat is None or lng is None:
            penalties += 30.0
        if not responding_units or len(responding_units) == 0 or (len(responding_units) == 1 and responding_units[0] == "Unknown Unit"):
            penalties += 20.0
        if not map_grid or str(map_grid).strip() == "" or str(map_grid).lower() == "none":
            penalties += 15.0
        if not radio_channel or str(radio_channel).strip() == "" or str(radio_channel).lower() == "none":
            penalties += 15.0
        
        confidence_score = max(0.0, base_confidence - penalties)
        if confidence_score < 90.0:
            verify_location = True
            
    if verify_location_override is not None:
        verify_location = verify_location_override
        
    # Calculate per-unit routing metrics from home hall origins (accounting for Emergency vs Routine response)
    routing_metrics = []
    # Parsed once, and NOT defaulted. An unparsed response type is None and stays
    # None all the way to the kiosk, which renders it UNKNOWN on an amber border
    # (operator ruling 2026-08-23, CLAUDE.md 6.1). This previously defaulted to
    # "emergency" here and to "routine" in four other places, so the same unparsed
    # call was routed one way and reconstructed the other. Punch-list #31.
    detected_resp = next((d.response_type for d in all_candidates if d.response_type), None)

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
        "cross_streets": target_cross_streets,
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
                cross_street_1=cross_street_1,
                cross_street_2=cross_street_2,
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
        "confidence_score": confidence_score,
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
