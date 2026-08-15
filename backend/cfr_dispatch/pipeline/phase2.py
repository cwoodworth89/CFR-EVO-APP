import io
import os
import wavio
import logging
import numpy as np
from typing import Any, Tuple

from cfr_dispatch.config.dsp import GOLDEN_FINGERPRINTS
from cfr_dispatch.config.hardware import AUDIO_SAMPLE_RATE
from cfr_dispatch.config.vocab import UNITS_VOCABULARY
from cfr_dispatch.config.cloud import INTEGRATION_PAYLOAD_OPTION, ENABLE_NTFY_PUSH
from cfr_dispatch.config.models import DispatchData
from cfr_dispatch.parser import (
    sanitize_transcript,
    parse_dispatch_announcement,
    split_rounds,
    match_incident_type,
    abbreviate_units,
    merge_units,
    reconstruct_template_transcript,
    CALL_TYPES
)
from cfr_dispatch.stt import transcribe_audio_local
from cfr_dispatch.pipeline.models import Phase2Result, PipelineTimer
from cfr_dispatch.pipeline.payload_builder import build_dispatch_payload, clean_address_string
from audio_service import filter_known_tones
from notification_service import (
    save_dispatch_record,
    update_dispatch_record,
    save_audio_recording,
    publish_mqtt_dispatch,
    post_to_ntfy
)

def save_and_upload_audio(dispatch_id: str, buffer: list, tone_name: str = None, save_to_disk: bool = True) -> Tuple[str | None, float]:
    """Computes duration and conditionally saves audio buffer locally via notification_service."""
    try:
        if not buffer:
            return None, 0.0
            
        full_audio = np.concatenate(buffer)
        duration_seconds = len(full_audio) / AUDIO_SAMPLE_RATE
        
        if not save_to_disk:
            logging.debug(f"[{dispatch_id}] Audio re-recording skipped (save_to_disk=False).")
            return None, duration_seconds

        wav_io = io.BytesIO()
        wavio.write(wav_io, full_audio, AUDIO_SAMPLE_RATE, sampwidth=2)
        audio_bytes = wav_io.getvalue()
        
        # Save to frontend/public/recordings/ if present (atomic write)
        try:
            import tempfile
            frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "..", "frontend", "public", "recordings")
            os.makedirs(frontend_dir, exist_ok=True)
            target_frontend_path = os.path.join(frontend_dir, f"{dispatch_id}.wav")
            with tempfile.NamedTemporaryFile(dir=frontend_dir, delete=False, suffix=".tmp") as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name
            os.replace(tmp_path, target_frontend_path)
        except Exception:
            pass

        # Save locally using notification_service persistence
        local_api_audio_url = save_audio_recording(audio_bytes, f"{dispatch_id}.wav")
        return local_api_audio_url, duration_seconds
    except Exception as e:
        logging.error(f"[{dispatch_id}] Error saving dispatch audio: {e}", exc_info=True)
        return None, 0.0

def process_phase_2_finalize(
    task: dict,
    validator: Any,
    stt_model: Any,
    session_manager: Any
) -> Phase2Result | None:
    """
    Finalizes full audio call, performs Phase 1 vs Phase 2 cross-validation,
    executes corrections if needed, updates the local database, and broadcasts finalized MQTT payload.
    """
    dispatch_id = task["dispatch_id"]
    buffer = task["buffer"]
    tone_name = task["tone_name"]
    units_vocab = task.get("units_vocab", UNITS_VOCABULARY)
    send_mqtt = task.get("send_mqtt", True)
    send_ntfy = task.get("send_ntfy", True)
    is_test = task.get("is_test", False)
    
    metrics = {}
    
    try:
        logging.info(f"[{dispatch_id}] [Phase 2] Finalizing dispatch recording and running full verification...")
        
        # 1. Save and Upload Full Audio
        with PipelineTimer("audio_save") as t_audio:
            audio_url, audio_duration = save_and_upload_audio(dispatch_id, buffer, tone_name)
        metrics["audio_save_ms"] = t_audio.elapsed_ms

        p1_data = session_manager.get_phase_1_data(dispatch_id)
        
        # 2. Filter Full Audio
        with PipelineTimer("dsp_filter") as t_dsp:
            full_dispatch_audio = np.concatenate(buffer)
            filtered_audio = filter_known_tones(full_dispatch_audio, tone_name, AUDIO_SAMPLE_RATE, GOLDEN_FINGERPRINTS)
        metrics["dsp_ms"] = t_dsp.elapsed_ms
        
        # 3. Whisper Transcription (Full Call)
        with PipelineTimer("whisper_stt") as t_stt:
            audio_float = filtered_audio.astype(np.float32) / 32768.0
            if len(audio_float.shape) > 1:
                audio_float = audio_float.squeeze()
            raw_transcript = transcribe_audio_local(audio_float, model=stt_model, validator=validator)
        metrics["stt_ms"] = t_stt.elapsed_ms
            
        if not raw_transcript:
            logging.warning(f"[{dispatch_id}] Phase 2 transcription returned empty. Using fallback placeholder.")
            raw_transcript = "[Transcription Failed]"
            
        transcript = sanitize_transcript(raw_transcript)
        
        # 4. Parse Full Call Announcements
        announcements = split_rounds(transcript, units_vocab)
        all_candidates = []
        for text in announcements:
            if len(text.split()) > 2:
                all_candidates.extend(parse_dispatch_announcement(text, units_vocab))
                
        # 5. Handle Phase 1 Verification vs Correction
        is_match = False
        was_corrected = False
        final_addr = "Unknown Location"
        final_lat = None
        final_lng = None
        final_conf = 0.0

        if not p1_data:
            # Single-phase fallback
            logging.info(f"[{dispatch_id}] [Phase 2] Phase 1 was skipped. Processing as single-phase complete payload...")
            db_payload, responding_units = build_dispatch_payload(
                dispatch_id, raw_transcript, transcript, all_candidates, validator, units_vocab,
                audio_url=audio_url, audio_duration=audio_duration, tone_name=tone_name
            )
            save_dispatch_record(db_payload)
            publish_mqtt_dispatch(db_payload, event_type="INSERT")
            if ENABLE_NTFY_PUSH:
                post_to_ntfy(db_payload)
            
            target = db_payload.get("target", {})
            final_addr = db_payload.get("address") or target.get("address", "Unknown Location")
            final_lat = target.get("lat")
            final_lng = target.get("lng")
            final_conf = db_payload.get("confidence_score", 0.0)
        else:
            p1_candidate = next((d for d in p1_data["candidates"] if d.address or d.intersection), None)
            p2_candidate = next((d for d in all_candidates if d.address or d.intersection), None)
            
            p1_addr = (p1_candidate.address or p1_candidate.intersection or "").lower() if p1_candidate else ""
            p2_addr = (p2_candidate.address or p2_candidate.intersection or "").lower() if p2_candidate else ""
            
            p1_target = p1_data.get("target", {})
            addresses_match = (p1_addr == p2_addr) and (p1_addr != "")

            if addresses_match:
                # MATCH VERIFIED
                is_match = True
                logging.info(f"[{dispatch_id}] [Phase 2] Verification MATCH: Address confirmed ('{p1_addr}'). Updating record to verified.")
                
                p1_units = p1_candidate.units if p1_candidate else None
                p2_units = p2_candidate.units if p2_candidate else None
                p2_units_str = merge_units(p1_units, p2_units) if (p1_units or p2_units) else None
                p2_responding_units = abbreviate_units(p2_units_str) if p2_units_str else []
                
                p2_grid = next((d.map_grid for d in all_candidates if d.map_grid), (p1_candidate.map_grid if p1_candidate else None))
                if (not p2_grid or str(p2_grid).lower() == "none") and p1_target.get("lat") and validator:
                    p2_grid = validator.get_map_grid_for_point(p1_target["lat"], p1_target["lng"])
                p2_channel = next((d.radio_channel for d in all_candidates if d.radio_channel), (p1_candidate.radio_channel if p1_candidate else None))
                p2_incident_type = match_incident_type(transcript, CALL_TYPES)

                reconstructed_transcript = transcript
                best_p2_candidate = p2_candidate or p1_candidate
                if best_p2_candidate:
                    try:
                        candidate_copy = DispatchData(
                            raw_text=best_p2_candidate.raw_text,
                            units=p2_units_str,
                            response_type=best_p2_candidate.response_type or "routine",
                            call_type=p2_incident_type,
                            address=clean_address_string(p1_target.get("address")) or (p1_candidate.address if p1_candidate else best_p2_candidate.address),
                            intersection=best_p2_candidate.intersection,
                            radio_channel=p2_channel,
                            map_grid=p2_grid,
                            subaddress=best_p2_candidate.subaddress or p1_target.get("subaddress")
                        )
                        reconstructed_transcript = reconstruct_template_transcript(candidate_copy)
                    except Exception as r_err:
                        logging.warning(f"[{dispatch_id}] Template reconstruction warning: {r_err}")

                p1_address = p1_target.get("address") or (p1_candidate.address or p1_candidate.intersection if p1_candidate else "")
                target_payload = {
                    "address": p1_address,
                    "lat": p1_target.get("lat"),
                    "lng": p1_target.get("lng"),
                    "rings": p1_target.get("rings", []),
                    "map_grid": p2_grid,
                    "radio_channel": p2_channel
                }
                if p1_target.get("subaddress"):
                    target_payload["subaddress"] = p1_target.get("subaddress")
                if p1_target.get("tone_name"):
                    target_payload["tone_name"] = p1_target.get("tone_name")
                if p1_target.get("intersection"):
                    target_payload["intersection"] = p1_target.get("intersection")

                update_payload = {
                    "verify_location": False,
                    "confidence_score": 100.0,
                    "audio_url": audio_url,
                    "audio_duration": audio_duration,
                    "raw_transcript": raw_transcript,
                    "sanitized_transcript": reconstructed_transcript,
                    "incident_type": p2_incident_type,
                    "responding_units": p2_responding_units
                }
                if INTEGRATION_PAYLOAD_OPTION == 1:
                    update_payload["address"] = p1_address
                else:
                    update_payload["target"] = target_payload

                update_dispatch_record(dispatch_id, update_payload)
                if send_mqtt:
                    publish_mqtt_dispatch(update_payload, event_type="UPDATE", is_test=is_test)
                
                final_addr = p1_address
                final_lat = p1_target.get("lat")
                final_lng = p1_target.get("lng")
                final_conf = 100.0

            else:
                # MISMATCH DETECTED -> ATTEMPT PHASE 2 CORRECTION
                was_corrected = True
                p1_str = p1_candidate.address if p1_candidate else "None"
                p2_str = p2_candidate.address if p2_candidate else "None"
                logging.warning(f"[CORRECTION_AUDIT] ID={dispatch_id} | Mismatch detected: P1='{p1_str}' vs P2='{p2_str}'. Attempting correction...")
                
                if p2_candidate:
                    unique_addresses = [p2_candidate.address or p2_candidate.intersection]
                    res = validator.local_geocode(unique_addresses[0]) if validator else None
                    if res:
                        logging.info(f"[{dispatch_id}] [CORRECTION_AUDIT] Geocoded match SUCCEEDED: '{res['address']}' (Score: {res['confidence']}%)")
                        
                        p1_units = p1_candidate.units if p1_candidate else None
                        p2_units = p2_candidate.units if p2_candidate else None
                        p2_units_str = merge_units(p1_units, p2_units) if (p1_units or p2_units) else None
                        p2_responding_units = abbreviate_units(p2_units_str) if p2_units_str else []
                        
                        p2_grid = next((d.map_grid for d in all_candidates if d.map_grid), (p1_candidate.map_grid if p1_candidate else None))
                        if (not p2_grid or str(p2_grid).lower() == "none") and res.get("lat") and validator:
                            p2_grid = validator.get_map_grid_for_point(res["lat"], res["lng"])
                        p2_channel = next((d.radio_channel for d in all_candidates if d.radio_channel), (p1_candidate.radio_channel if p1_candidate else None))
                        p2_incident_type = match_incident_type(transcript, CALL_TYPES)

                        reconstructed_transcript = transcript
                        best_p2_candidate = p2_candidate or p1_candidate
                        if best_p2_candidate:
                            try:
                                candidate_copy = DispatchData(
                                    raw_text=best_p2_candidate.raw_text,
                                    units=p2_units_str,
                                    response_type=best_p2_candidate.response_type or "routine",
                                    call_type=p2_incident_type,
                                    address=clean_address_string(res["address"]),
                                    intersection=best_p2_candidate.intersection,
                                    radio_channel=p2_channel,
                                    map_grid=p2_grid,
                                    subaddress=best_p2_candidate.subaddress or p1_target.get("subaddress")
                                )
                                reconstructed_transcript = reconstruct_template_transcript(candidate_copy)
                            except Exception as r_err:
                                logging.warning(f"[{dispatch_id}] Template reconstruction warning: {r_err}")

                        target_payload = {
                            "address": res["address"],
                            "lat": res["lat"],
                            "lng": res["lng"],
                            "rings": res.get("rings", []),
                            "map_grid": p2_grid,
                            "radio_channel": p2_channel
                        }
                        if p1_target.get("subaddress") or (best_p2_candidate and best_p2_candidate.subaddress):
                            target_payload["subaddress"] = p1_target.get("subaddress") or best_p2_candidate.subaddress
                        if p1_target.get("tone_name"):
                            target_payload["tone_name"] = p1_target.get("tone_name")
                        if best_p2_candidate and best_p2_candidate.intersection:
                            target_payload["intersection"] = best_p2_candidate.intersection

                        update_payload = {
                            "verify_location": False,
                            "confidence_score": float(res.get("confidence", 80.0)),
                            "audio_url": audio_url,
                            "audio_duration": audio_duration,
                            "raw_transcript": raw_transcript,
                            "sanitized_transcript": reconstructed_transcript,
                            "incident_type": p2_incident_type,
                            "responding_units": p2_responding_units,
                            "is_test": is_test
                        }
                        if INTEGRATION_PAYLOAD_OPTION == 1:
                            update_payload["address"] = res["address"]
                        else:
                            update_payload["target"] = target_payload

                        update_dispatch_record(dispatch_id, update_payload)
                        if send_mqtt:
                            publish_mqtt_dispatch(update_payload, event_type="UPDATE", is_test=is_test)
                        
                        if send_ntfy and ENABLE_NTFY_PUSH:
                            corr_payload = {
                                "dispatch_id": dispatch_id,
                                "incident_type": p2_incident_type,
                                "responding_units": p2_responding_units,
                                "lat": res["lat"],
                                "lng": res["lng"],
                                "target": target_payload,
                                "is_test": is_test
                            }
                            post_to_ntfy(corr_payload, title=f"CORRECTION: Dispatch {dispatch_id}", tags="warning,rotating_light", is_test=is_test)

                        final_addr = res["address"]
                        final_lat = res["lat"]
                        final_lng = res["lng"]
                        final_conf = float(res.get("confidence", 80.0))
                    else:
                        # Geocoding failed for Phase 2, preserve Phase 1 data with verify_location=True
                        logging.warning(f"[{dispatch_id}] Phase 2 geocoding failed. Retaining Phase 1 with verify_location=True.")
                        update_payload = {
                            "verify_location": True,
                            "audio_url": audio_url,
                            "audio_duration": audio_duration,
                            "raw_transcript": raw_transcript,
                            "sanitized_transcript": transcript,
                            "is_test": is_test
                        }
                        update_dispatch_record(dispatch_id, update_payload)
                        if send_mqtt:
                            publish_mqtt_dispatch(update_payload, event_type="UPDATE", is_test=is_test)
                        final_addr = p1_target.get("address", "Unknown Location")
                else:
                    # No Phase 2 candidate found, keep Phase 1 data as verified
                    logging.info(f"[{dispatch_id}] No candidate in Phase 2. Keeping Phase 1 as verified.")
                    update_payload = {
                        "verify_location": False,
                        "audio_url": audio_url,
                        "audio_duration": audio_duration,
                        "raw_transcript": raw_transcript,
                        "sanitized_transcript": transcript,
                        "is_test": is_test
                    }
                    update_dispatch_record(dispatch_id, update_payload)
                    if send_mqtt:
                        publish_mqtt_dispatch(update_payload, event_type="UPDATE", is_test=is_test)
                    final_addr = p1_target.get("address", "Unknown Location")

        logging.info(f"[METRICS] [{dispatch_id}] Phase 2 Finalized | Match={is_match} | Corrected={was_corrected} | Addr='{final_addr}' | Audio={audio_duration:.1f}s")

        return Phase2Result(
            dispatch_id=dispatch_id,
            is_match=is_match,
            was_corrected=was_corrected,
            final_address=final_addr,
            lat=final_lat,
            lng=final_lng,
            confidence_score=final_conf,
            audio_url=audio_url,
            audio_duration=audio_duration,
            metrics=metrics
        )
    except Exception as e:
        logging.error(f"[{dispatch_id}] Error in process_phase_2_finalize: {e}", exc_info=True)
        return None
    finally:
        session_manager.cleanup_session(dispatch_id)

def process_full_dispatch(
    buffer: list,
    validator: Any,
    tone_name: str = None,
    units_vocab: list = None,
    stt_model: Any = None,
    send_mqtt: bool = True,
    send_ntfy: bool = True,
    is_test: bool = False,
    save_db: bool = True,
    save_audio: bool = False,
    dispatch_id: str = None
) -> dict:
    """Processes a full dispatch audio buffer synchronously (single-phase / simulation mode)."""
    import uuid
    import time
    if not dispatch_id:
        dispatch_id = f"DISP-{time.strftime('%Y')}-{uuid.uuid4().hex[:6].upper()}"
    units_vocab = units_vocab or UNITS_VOCABULARY
    logging.info(f"--- STARTING SIMULATED / FULL DISPATCH PROCESSING (ID: {dispatch_id}, is_test={is_test}) ---")
    
    # 1. Save and upload audio (skipped by default for test calls to avoid re-recording)
    audio_url, audio_duration = save_and_upload_audio(dispatch_id, buffer, tone_name, save_to_disk=save_audio)
    
    # 2. Combine & filter audio
    full_audio = np.concatenate(buffer)
    filtered_audio = filter_known_tones(full_audio, tone_name, AUDIO_SAMPLE_RATE, GOLDEN_FINGERPRINTS)
    
    # 3. Transcribe
    audio_float = filtered_audio.astype(np.float32) / 32768.0
    if len(audio_float.shape) > 1:
        audio_float = audio_float.squeeze()
    raw_transcript = transcribe_audio_local(audio_float, model=stt_model, validator=validator)
    
    if not raw_transcript:
        logging.warning(f"[{dispatch_id}] Transcription returned empty.")
        raw_transcript = "[Transcription Failed]"
        
    transcript = sanitize_transcript(raw_transcript)
    logging.info(f"[{dispatch_id}] Sanitized Transcript: '{transcript}'")
    
    # 4. Parse candidates
    announcements = split_rounds(transcript, units_vocab)
    all_candidates = []
    for text in announcements:
        if len(text.split()) > 2:
            all_candidates.extend(parse_dispatch_announcement(text, units_vocab))
            
    # 5. Build payload & Broadcast
    db_payload, responding_units = build_dispatch_payload(
        dispatch_id=dispatch_id,
        raw_transcript=raw_transcript,
        sanitized_transcript=transcript,
        all_candidates=all_candidates,
        validator=validator,
        units_vocabulary=units_vocab,
        audio_url=audio_url,
        audio_duration=audio_duration,
        tone_name=tone_name,
        is_test=is_test
    )
    
    if save_db:
        save_dispatch_record(db_payload)
    else:
        logging.info(f"[{dispatch_id}] Targeted testing mode: Omitted database persistence.")
        
    if send_mqtt:
        publish_mqtt_dispatch(db_payload, event_type="INSERT", is_test=is_test)
    else:
        logging.info(f"[{dispatch_id}] Targeted testing mode: Omitted MQTT broadcast.")
        
    if send_ntfy and ENABLE_NTFY_PUSH:
        post_to_ntfy(db_payload, is_test=is_test)
    elif not send_ntfy:
        logging.info(f"[{dispatch_id}] Targeted testing mode: Omitted Ntfy push.")
        
    best_addr = db_payload.get("address") or db_payload.get("target", {}).get("address")
    logging.info(f"[METRICS] [{dispatch_id}] Full Dispatch Processed | Units: {responding_units} | Addr: '{best_addr}'")
    return db_payload

