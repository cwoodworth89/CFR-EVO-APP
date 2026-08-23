import re
import logging
import numpy as np
from typing import List, Any
from collections import Counter

from cfr_dispatch.config.dsp import GOLDEN_FINGERPRINTS
from cfr_dispatch.config.hardware import AUDIO_SAMPLE_RATE
from cfr_dispatch.config.vocab import UNITS_VOCABULARY
from cfr_dispatch.config.cloud import ENABLE_NTFY_PUSH
from cfr_dispatch.config.models import DispatchData
from cfr_dispatch.parser import sanitize_transcript, parse_dispatch_announcement, split_rounds
from cfr_dispatch.stt import transcribe_audio_local
from cfr_dispatch.pipeline.models import Phase1Result, PipelineTimer
from cfr_dispatch.pipeline.payload_builder import build_dispatch_payload
from audio_service import filter_known_tones
from notification_service import save_dispatch_record, publish_mqtt_dispatch, post_to_ntfy

def is_round_1_complete_check(dispatch_list: List[DispatchData], raw_transcript: str) -> bool:
    """Determines if the first round of the dispatch announcement is complete using map grid and unit repetition heuristics."""
    if not dispatch_list:
        return False
    
    candidate = next((d for d in dispatch_list if d.address or d.intersection), None)
    if not candidate:
        return False
        
    has_units = candidate.units is not None and len(candidate.units) > 0
    has_call_type = candidate.call_type is not None and candidate.call_type != "Unknown Incident"
    
    if has_units and has_call_type:
        has_valid_grid = False
        if candidate.map_grid:
            try:
                clean_grid = "".join(filter(str.isdigit, str(candidate.map_grid)))
                if clean_grid:
                    grid_num = int(clean_grid)
                    if 1 <= grid_num <= 134:
                        has_valid_grid = True
            except ValueError:
                pass
        
        if not has_valid_grid:
            grid_matches = re.findall(r'\b(?:grid|grade)\s*(\d{1,3})\b', raw_transcript.lower())
            for gm in grid_matches:
                try:
                    g_val = int(gm)
                    if 1 <= g_val <= 134:
                        has_valid_grid = True
                        break
                except ValueError:
                    pass
                    
        has_unit_repetition = False
        unit_vocab_pattern = '|'.join(u.lower() for u in UNITS_VOCABULARY)
        unit_pairs = re.findall(rf'\b({unit_vocab_pattern})\s+(\d+)\b', raw_transcript.lower())
        if unit_pairs:
            counts = Counter(unit_pairs)
            if any(count >= 2 for count in counts.values()):
                has_unit_repetition = True
                
        if has_valid_grid or has_unit_repetition:
            return True
            
    return False

def process_phase_1_check(
    task: dict,
    validator: Any,
    stt_model: Any,
    session_manager: Any
) -> Phase1Result | None:
    """
    Executes rapid preliminary audio check (<15s) for a dispatch session.
    Combines audio, runs Whisper int8, checks completion heuristic, and broadcasts preliminary alerts.
    """
    dispatch_id = task["dispatch_id"]
    buffer = task["buffer"]
    tone_name = task["tone_name"]
    units_vocab = task.get("units_vocab", UNITS_VOCABULARY)
    send_mqtt = task.get("send_mqtt", True)
    send_ntfy = task.get("send_ntfy", True)
    is_test = task.get("is_test", False)
    
    if session_manager.is_phase_1_triggered(dispatch_id):
        return None
        
    metrics = {}
    try:
        # 1. Combine and Filter Audio
        with PipelineTimer("dsp_filtering") as t_dsp:
            full_dispatch_audio = np.concatenate(buffer)
            filtered_audio = filter_known_tones(full_dispatch_audio, tone_name, AUDIO_SAMPLE_RATE, GOLDEN_FINGERPRINTS)
        metrics["dsp_ms"] = t_dsp.elapsed_ms

        # 2. Whisper In-Memory Transcription
        with PipelineTimer("whisper_stt") as t_stt:
            audio_float = filtered_audio.astype(np.float32) / 32768.0
            if len(audio_float.shape) > 1:
                audio_float = audio_float.squeeze()
            raw_transcript = transcribe_audio_local(audio_float, model=stt_model, validator=validator)
        metrics["stt_ms"] = t_stt.elapsed_ms
            
        if not raw_transcript:
            return None
            
        transcript = sanitize_transcript(raw_transcript)
        
        # 3. Parse Announcements
        announcements = split_rounds(transcript, units_vocab)
        all_candidates = []
        for text in announcements:
            if len(text.split()) > 2:
                all_candidates.extend(parse_dispatch_announcement(text, units_vocab))
                
        # 4. Check Semantic Completion
        if is_round_1_complete_check(all_candidates, transcript):
            logging.info(f"[{dispatch_id}] [Phase 1] Semantic completion trigger met. Processing preliminary payload...")
            
            with PipelineTimer("payload_building") as t_gis:
                db_payload, responding_units = build_dispatch_payload(
                    dispatch_id, raw_transcript, transcript, all_candidates, validator, units_vocab,
                    verify_location_override=False, tone_name=tone_name, is_test=is_test
                )
            metrics["gis_ms"] = t_gis.elapsed_ms

            if db_payload:
                target = db_payload.get("target", {})
                best_addr = db_payload.get("address") or target.get("address", "Unknown Location")

                # 5. Record the session BEFORE broadcasting.
                #
                # These were the other way round. Any exception in the broadcast block left
                # an INSERT published with no phase 1 session stored, and phase 2 then found
                # nothing, took the "Phase 1 was skipped" branch and published a SECOND
                # INSERT -- a duplicate dispatch on the kiosk (punch-list #25, #29).
                #
                # Recording first makes an untracked INSERT impossible: if this fails, the
                # broadcast below still happens and phase 2 still runs, but the failure is
                # logged loudly rather than surfacing later as a mystery duplicate.
                session_manager.record_phase_1_success(
                    dispatch_id=dispatch_id,
                    buffer_len=len(buffer),
                    raw_transcript=raw_transcript,
                    transcript=transcript,
                    candidates=all_candidates,
                    units=responding_units,
                    target=target or {"address": best_addr}
                )

                # 6. Broadcast to local FastAPI & Mosquitto MQTT & Ntfy
                with PipelineTimer("broadcast") as t_bcast:
                    save_dispatch_record(db_payload)
                    if send_mqtt:
                        publish_mqtt_dispatch(db_payload, event_type="INSERT", is_test=is_test)
                    if send_ntfy and ENABLE_NTFY_PUSH:
                        post_to_ntfy(db_payload, is_test=is_test)
                metrics["bcast_ms"] = t_bcast.elapsed_ms

                total_tta_s = (metrics["dsp_ms"] + metrics["stt_ms"] + metrics["gis_ms"] + metrics["bcast_ms"]) / 1000.0
                
                conf = db_payload.get("confidence_score", 0.0)

                logging.info(
                    f"[METRICS] [{dispatch_id}] Phase 1 TTA: {total_tta_s:.2f}s "
                    f"(DSP: {metrics['dsp_ms']:.0f}ms, STT: {metrics['stt_ms']:.0f}ms, GIS: {metrics['gis_ms']:.0f}ms, MQTT: {metrics['bcast_ms']:.0f}ms) | "
                    f"Units: {responding_units} | Addr: '{best_addr}' ({conf:.0f}% conf)"
                )

                return Phase1Result(
                    dispatch_id=dispatch_id,
                    raw_transcript=raw_transcript,
                    sanitized_transcript=transcript,
                    incident_type=db_payload.get("incident_type", "Unknown Incident"),
                    responding_units=responding_units,
                    address=best_addr,
                    lat=target.get("lat"),
                    lng=target.get("lng"),
                    confidence_score=conf,
                    is_triggered=True,
                    db_payload=db_payload,
                    metrics=metrics
                )
    except Exception as e:
        logging.error(f"[{dispatch_id}] Error in process_phase_1_check: {e}", exc_info=True)
        return None
