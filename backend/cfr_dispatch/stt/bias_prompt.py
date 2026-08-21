import os
import re
import time
import logging
import requests

_cached_hitl_streets = []
_last_hitl_fetch_time = 0.0

def get_hitl_verified_streets() -> list[str]:
    """
    Fetches the most frequently misheard street names that required HITL correction.
    Cached in memory for 10 minutes to prevent blocking network requests during transcription.
    """
    global _cached_hitl_streets, _last_hitl_fetch_time
    now = time.time()
    if _cached_hitl_streets and (now - _last_hitl_fetch_time < 600.0):
        return _cached_hitl_streets

    try:
        local_api_url = os.environ.get("LOCAL_API_URL", "http://localhost:8000").rstrip("/")
        endpoint = f"{local_api_url}/api/dispatches?limit=200"
        response = requests.get(endpoint, timeout=3)
        response.raise_for_status()
        records = response.json()
        
        from collections import defaultdict
        tally = defaultdict(int)
        
        for r in records:
            if not r.get("feedback_submitted"):
                continue
            verified_addr = r.get("verified_address")
            system_addr = r.get("address") or (r.get("target", {}).get("address") if r.get("target") else None)
                
            if not verified_addr:
                continue
                
            def clean_street(addr_str):
                if not addr_str:
                    return ""
                match = re.search(r'^\d+\s+(?P<street>.*)', addr_str.split(',')[0].strip())
                if match:
                    return match.group('street').strip().title()
                return addr_str.strip().title()
                
            v_street = clean_street(verified_addr)
            sys_street = clean_street(system_addr)
            
            if v_street and sys_street and v_street != sys_street:
                tally[v_street] += 1
                
        sorted_streets = sorted(tally.keys(), key=lambda s: tally[s], reverse=True)
        _cached_hitl_streets = sorted_streets
        _last_hitl_fetch_time = now
        return sorted_streets
    except Exception as e:
        logging.warning(f"Failed to fetch HITL verified streets for STT hotwords: {e}")
        return _cached_hitl_streets

def build_stt_bias_words(validator=None, units_vocabulary: list[str] = None) -> tuple[str, str]:
    core_dispatch_terms = [
        'Coquitlam', 'respond', 'routine', 'emergency', 'Combined Response Coquitlam',
        'use talk group', 'map grid', 'medical aid', 'overdose', 'lift assist',
        'structure fire', 'alarm activated', 'rescue', 'hazard'
    ]
    
    # ALL unit names
    unit_terms = []
    if units_vocabulary and isinstance(units_vocabulary, (list, set)):
        unit_terms = [str(u).title() for u in units_vocabulary if len(str(u).strip()) > 1]
    
    # HITL corrections (unchanged)
    hitl_streets = get_hitl_verified_streets()
    
    # ALL road names from database (replaces top-25 GeoDataFrame hack)
    all_streets = []
    if validator and hasattr(validator, 'get_all_road_names'):
        try:
            all_streets = [str(s).title() for s in validator.get_all_road_names()]
        except Exception as e:
            logging.warning(f'Failed to load road names for STT hotwords: {e}')
    
    # ALL call types from vocabulary
    all_call_types = []
    try:
        from cfr_dispatch.config.vocab import CALL_TYPES
        all_call_types = [str(ct).title() for ct in CALL_TYPES if len(str(ct).strip()) > 1]
    except Exception:
        pass
    
    # Build complete hotword list — NO artificial truncation
    all_hotwords = list(dict.fromkeys(
        core_dispatch_terms + unit_terms + hitl_streets + all_streets + all_call_types
    ))
    hotwords_str = ', '.join(all_hotwords)
    
    initial_prompt_str = (
        'Coquitlam Fire Dispatch. Engine 1, Ladder 1, Quint 5, Rescue 1. '
        'Structure Fire, Medical Aid, Alarm Activated, Commercial Alarm. '
        'Respond on talk group Tac 1, map grid.'
    )
    return initial_prompt_str, hotwords_str
