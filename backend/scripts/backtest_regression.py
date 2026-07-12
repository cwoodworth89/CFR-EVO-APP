# backend/scripts/backtest_regression.py
import os
import sys
import csv
import json
import time
import logging
import datetime
import numpy as np
import requests

# Set up paths so we can import cfr_dispatch package
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

import cfr_dispatch
from cfr_dispatch.orchestration import transcribe_audio_file, get_shared_validator
from cfr_dispatch.config import STT_ENGINE, UNITS_VOCABULARY, DispatchData, CALL_TYPES
from cfr_dispatch.parser import (
    sanitize_transcript, 
    split_rounds, 
    reconstruct_template_transcript, 
    parse_dispatch_announcement,
    abbreviate_units,
    match_incident_type
)

def levenshtein_distance(s1, s2):
    """Calculates Levenshtein distance between two lists or strings."""
    if len(s1) > len(s2):
        s1, s2 = s2, s1
    distances = range(len(s1) + 1)
    for i2, c2 in enumerate(s2):
        distances_ = [i2+1]
        for i1, c1 in enumerate(s1):
            if c1 == c2:
                distances_.append(distances[i1])
            else:
                distances_.append(1 + min((distances[i1], distances[i1 + 1], distances_[-1])))
        distances = distances_
    return distances[-1]

def calculate_wer(reference: str, hypothesis: str) -> float:
    """Calculates Word Error Rate (WER)."""
    ref_words = reference.lower().split()
    hyp_words = hypothesis.lower().split()
    if not ref_words:
        return 0.0 if not hyp_words else 1.0
    dist = levenshtein_distance(ref_words, hyp_words)
    return float(dist) / len(ref_words)

def calculate_cer(reference: str, hypothesis: str) -> float:
    """Calculates Character Error Rate (CER)."""
    ref_chars = list(reference.lower().strip())
    hyp_chars = list(hypothesis.lower().strip())
    if not ref_chars:
        return 0.0 if not hyp_chars else 1.0
    dist = levenshtein_distance(ref_chars, hyp_chars)
    return float(dist) / len(ref_chars)

def get_quality_rating(wer: float) -> str:
    if wer == 0.0:
        return "100% Perfect"
    elif wer < 0.20:
        return "Operational"
    else:
        return "Failed"

def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    
    # 1. Paths setup
    training_dir = os.path.join(backend_dir, "data", "training")
    audio_dir = os.path.join(training_dir, "audio")
    metadata_csv_path = os.path.join(training_dir, "metadata.csv")
    history_json_path = os.path.join(training_dir, "evaluation_history.json")
    
    if not os.path.exists(metadata_csv_path):
        logging.error(f"Metadata file not found: {metadata_csv_path}")
        logging.error("Please run scripts/extract_training_data.py first to sync verified dataset.")
        sys.exit(1)
        
    # 2. Load dataset
    records = []
    try:
        with open(metadata_csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                records.append(row)
    except Exception as e:
        logging.error(f"Failed to read metadata.csv: {e}")
        sys.exit(1)
        
    logging.info(f"Loaded {len(records)} test samples from metadata.csv.")
    
    if not records:
        logging.error("Metadata is empty. No evaluations can be run.")
        sys.exit(1)
        
    # Initialize shapefile validator for template reconstruction geocoding
    validator = get_shared_validator()
    
    # 3. Execution loop
    print("==================================================")
    print("        REGRESSION BACKTESTING & EVALUATION       ")
    print("==================================================")
    print(f"STT Engine: {STT_ENGINE.upper()}")
    print("Transcribing and evaluating test cases...")
    print("--------------------------------------------------")
    
    comparisons = []
    old_wers, new_wers = [], []
    old_cers, new_cers = [], []
    quality_counts = {"100% Perfect": 0, "Operational": 0, "Failed": 0}
    regressions_found = 0
    improvements_found = 0
    
    for idx, r in enumerate(records):
        file_name = r.get("file_name")
        ref_text = r.get("verified_transcript", "").strip()
        old_hyp = r.get("raw_transcript", "").strip()
        
        local_path = os.path.join(audio_dir, file_name)
        if not os.path.exists(local_path):
            logging.warning(f"Audio file missing, skipping: {local_path}")
            continue
            
        print(f"Processing ({idx+1}/{len(records)}): {file_name}...")
        
        # Run active STT model
        try:
            new_hyp = transcribe_audio_file(local_path)
            if new_hyp is None:
                new_hyp = ""
            new_hyp = new_hyp.strip()
        except Exception as e:
            logging.error(f"Transcription failed for {file_name}: {e}")
            new_hyp = ""
            
        # Sanitize for structured evaluation (mapping words to digits, normalizing names)
        sanitized_ref = sanitize_transcript(ref_text)
        sanitized_old_raw = sanitize_transcript(old_hyp)
        sanitized_new_raw = sanitize_transcript(new_hyp)
        
        # Split rounds on the sanitized text to keep only the first round
        old_rounds = split_rounds(sanitized_old_raw, UNITS_VOCABULARY)
        sanitized_old = old_rounds[0] if old_rounds else sanitized_old_raw
        
        new_rounds = split_rounds(sanitized_new_raw, UNITS_VOCABULARY)
        round_1_text = new_rounds[0] if new_rounds else sanitized_new_raw
        sanitized_new = round_1_text
        
        # Apply Post-Transcription Template Reconstruction to evaluate true parser performance
        if not ("contact dispatch" in round_1_text or "location information" in round_1_text) and "unknown location" not in round_1_text:
            try:
                candidates = parse_dispatch_announcement(round_1_text, UNITS_VOCABULARY)
                if candidates:
                    cand = candidates[0]
                    resolved_addr = cand.address
                    if cand.address and validator:
                        score, matched_addr = validator.validate_address_exists(cand.address)
                        if matched_addr:
                            resolved_addr = matched_addr
                            
                    # Extract channel digit fallback
                    channel_val = cand.radio_channel
                    if not channel_val and "use talk group" in round_1_text:
                        parts = round_1_text.split("use talk group")
                        if len(parts) > 1:
                            words = parts[1].strip().split()
                            if words and words[0].isdigit():
                                channel_val = words[0]
                                
                    reconstructed = reconstruct_template_transcript(DispatchData(
                        raw_text=cand.raw_text,
                        units=abbreviate_units(cand.units) if cand.units else None,
                        response_type=cand.response_type,
                        call_type=match_incident_type(round_1_text, CALL_TYPES),
                        address=resolved_addr,
                        intersection=cand.intersection,
                        radio_channel=channel_val,
                        map_grid=cand.map_grid
                    ))
                    sanitized_new = sanitize_transcript(reconstructed)
            except Exception as eval_err:
                logging.warning(f"Failed to reconstruct hypothesis in evaluation loop: {eval_err}")
            
        # Calculate statistics based on sanitized outputs (what the parser actually sees)
        old_wer = calculate_wer(sanitized_ref, sanitized_old)
        new_wer = calculate_wer(sanitized_ref, sanitized_new)
        old_cer = calculate_cer(sanitized_ref, sanitized_old)
        new_cer = calculate_cer(sanitized_ref, sanitized_new)
        
        old_wers.append(old_wer)
        new_wers.append(new_wer)
        old_cers.append(old_cer)
        new_cers.append(new_cer)
        
        rating = get_quality_rating(new_wer)
        quality_counts[rating] += 1
        
        status = "Unchanged"
        if new_wer < old_wer:
            status = "Improved"
            improvements_found += 1
        elif new_wer > old_wer:
            status = "Regression"
            regressions_found += 1
            
        comparisons.append({
            "id": file_name.replace(".wav", ""),
            "reference": ref_text,
            "sanitized_reference": sanitized_ref,
            "old_hypothesis": old_hyp,
            "sanitized_old": sanitized_old,
            "new_hypothesis": new_hyp,
            "sanitized_new": sanitized_new,
            "old_wer": old_wer,
            "new_wer": new_wer,
            "status": status
        })
        
    if not new_wers:
        logging.error("No samples successfully evaluated.")
        sys.exit(1)
        
    # 4. Display Results Table
    print("\n--------------------------------------------------")
    print("Evaluation Results Summary:")
    print("--------------------------------------------------")
    for c in comparisons:
        color = "⚪"
        if c["status"] == "Improved":
            color = "🟢"
        elif c["status"] == "Regression":
            color = "🔴"
            
        print(f"{color} Call {c['id']}: {c['status']}")
        print(f"  - Human Ref (Raw):  \"{c['reference']}\"")
        print(f"  - Sanitized Ref:    \"{c['sanitized_reference']}\"")
        print(f"  - Old Hypoth (San): \"{c['sanitized_old']}\" (WER: {c['old_wer']:.1%})")
        print(f"  - New Hypoth (San): \"{c['sanitized_new']}\" (WER: {c['new_wer']:.1%})")
        print(f"  - New Hypoth (Raw): \"{c['new_hypothesis']}\"")
        print()
        
    # Calculate global metrics
    old_avg_wer = np.mean(old_wers)
    new_avg_wer = np.mean(new_wers)
    old_avg_cer = np.mean(old_cers)
    new_avg_cer = np.mean(new_cers)
    
    total = len(new_wers)
    perfect_p = (quality_counts["100% Perfect"] / total) * 100
    operational_p = (quality_counts["Operational"] / total) * 100
    failed_p = (quality_counts["Failed"] / total) * 100
    
    print("==================================================")
    print("               FINAL MODEL SUMMARY                ")
    print("==================================================")
    print(f"  - Total Test Samples:    {total}")
    print(f"  - Baseline (Old) WER:    {old_avg_wer:.1%}")
    print(f"  - New Evaluation WER:    {new_avg_wer:.1%}")
    print(f"  - Baseline (Old) CER:    {old_avg_cer:.1%}")
    print(f"  - New Evaluation CER:    {new_avg_cer:.1%}")
    print("--------------------------------------------------")
    print(f"  - Improvements Found:    {improvements_found}")
    print(f"  - Regressions Found:     {regressions_found}")
    print("--------------------------------------------------")
    print("Quality Rating Distribution:")
    print(f"  - 100% Perfect:          {perfect_p:.1f}% ({quality_counts['100% Perfect']})")
    print(f"  - Operational:           {operational_p:.1f}% ({quality_counts['Operational']})")
    print(f"  - Failed:                {failed_p:.1f}% ({quality_counts['Failed']})")
    print("==================================================")
    
    # 5. Log history
    evaluation_run = {
        "timestamp": datetime.datetime.now().isoformat(),
        "model_version": f"{STT_ENGINE}-boost-classes",
        "total_evaluation_samples": total,
        "old_average_wer": float(old_avg_wer),
        "new_average_wer": float(new_avg_wer),
        "old_average_cer": float(old_avg_cer),
        "new_average_cer": float(new_avg_cer),
        "quality_metrics": {
            "perfect_percent": float(perfect_p),
            "operational_percent": float(operational_p),
            "failed_percent": float(failed_p)
        }
    }
    
    history_list = []
    if os.path.exists(history_json_path):
        try:
            with open(history_json_path, "r", encoding="utf-8") as f:
                history_list = json.load(f)
                if not isinstance(history_list, list):
                    history_list = []
        except Exception:
            history_list = []
            
    history_list.append(evaluation_run)
    
    try:
        with open(history_json_path, "w", encoding="utf-8") as f:
            json.dump(history_list, f, indent=2)
        logging.info(f"Evaluation metrics logged to: {history_json_path}")
    except Exception as e:
        logging.warning(f"Failed to log evaluation history: {e}")

    # 6. Post history to Supabase evaluation_history
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
    if supabase_url and supabase_key:
        headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
        }
        db_payload = {
            "model_version": f"{STT_ENGINE}-boost-classes",
            "total_samples": int(total),
            "wer": float(round(new_avg_wer * 100, 2)),
            "cer": float(round(new_avg_cer * 100, 2)),
            "perfect_percent": float(round(perfect_p, 2)),
            "operational_percent": float(round(operational_p, 2)),
            "failed_percent": float(round(failed_p, 2))
        }
        endpoint = f"{supabase_url.rstrip('/')}/rest/v1/evaluation_history"
        logging.info(f"Posting evaluation metrics to Supabase: {endpoint}")
        try:
            db_response = requests.post(endpoint, headers=headers, json=db_payload, timeout=10)
            db_response.raise_for_status()
            logging.info("Successfully posted metrics to Supabase evaluation_history.")
        except Exception as e:
            logging.warning(f"Failed to post evaluation metrics to Supabase: {e}")
    else:
        logging.warning("Missing SUPABASE_URL or SUPABASE_KEY. Skipping Supabase metrics upload.")



if __name__ == "__main__":
    main()
