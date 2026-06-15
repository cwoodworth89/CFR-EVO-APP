# backend/tests/run_test_suite.py
# Local Quality Assurance & Diagnostics test runner for CFR Dispatch
# NOTE: For test procedures, QA metrics, and running diagnostic scripts, see docs/test_procedures.md

import os
import sys
import re
import logging
from typing import List, Dict, Any
from thefuzz import fuzz

# Add parent directory of agent/ to path to allow importing packages
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

try:
    from agent.cfr_dispatch.orchestration import transcribe_audio_file
    from agent.cfr_dispatch.parser import sanitize_transcript, parse_dispatch_announcement, abbreviate_units
    from agent.cfr_dispatch.config import (
        UNITS_VOCABULARY, ADDRESS_SHAPEFILE_PATH, ZONES_SHAPEFILE_PATH,
        ADDRESS_HOUSE_NUM_COLUMN, ADDRESS_STREET_NAME_COLUMN, ADDRESS_STREET_TYPE_COLUMN,
        ADDRESS_FULL_ADDR_COLUMN, STREET_NAME_CONFIDENCE_THRESHOLD, ZONES_MAP_NAME_COLUMN
    )
    from gis_service import CoquitlamDataValidator
except ImportError:
    from cfr_dispatch.orchestration import transcribe_audio_file
    from cfr_dispatch.parser import sanitize_transcript, parse_dispatch_announcement, abbreviate_units
    from cfr_dispatch.config import (
        UNITS_VOCABULARY, ADDRESS_SHAPEFILE_PATH, ZONES_SHAPEFILE_PATH,
        ADDRESS_HOUSE_NUM_COLUMN, ADDRESS_STREET_NAME_COLUMN, ADDRESS_STREET_TYPE_COLUMN,
        ADDRESS_FULL_ADDR_COLUMN, STREET_NAME_CONFIDENCE_THRESHOLD, ZONES_MAP_NAME_COLUMN
    )
    from gis_service import CoquitlamDataValidator

# ANSI Color Codes for Windows terminal output
COLOR_GREEN = "\033[92m"
COLOR_RED = "\033[91m"
COLOR_YELLOW = "\033[93m"
COLOR_BLUE = "\033[94m"
COLOR_CYAN = "\033[96m"
COLOR_BOLD = "\033[1m"
COLOR_RESET = "\033[0m"

def load_test_case(txt_path: str) -> Dict[str, Any]:
    """
    Parses expected values from a .txt test case file.
    Supports both structured key-value (YAML-like) and raw plain text.
    """
    expected = {
        "transcript": "",
        "address": None,
        "units": None,
        "priority": None,
        "grid": None
    }
    
    if not os.path.exists(txt_path):
        return expected
        
    try:
        with open(txt_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
        # Check if file has key-value structure
        is_kv = False
        for line in lines:
            if ":" in line:
                key = line.split(":", 1)[0].strip().lower()
                if key in ["transcript", "address", "units", "priority", "response", "grid", "map_grid"]:
                    is_kv = True
                    break
                    
        if is_kv:
            for line in lines:
                if ":" in line:
                    key, val = line.split(":", 1)
                    key = key.strip().lower()
                    val = val.strip()
                    if key == "transcript":
                        expected["transcript"] = val
                    elif key == "address":
                        expected["address"] = val
                    elif key == "units":
                        expected["units"] = [u.strip().upper() for u in val.split(",") if u.strip()]
                    elif key in ["priority", "response"]:
                        expected["priority"] = val.lower()
                    elif key in ["grid", "map_grid"]:
                        expected["grid"] = val
        else:
            # Fallback to plain text transcript
            expected["transcript"] = " ".join([l.strip() for l in lines if l.strip()])
    except Exception as e:
        print(f"Error loading test case file '{txt_path}': {e}")
        
    return expected

def run_diagnostics():
    print(f"\n{COLOR_CYAN}{COLOR_BOLD}==================================================")
    print("      CFR DISPATCH QA & DIAGNOSTICS DASHBOARD")
    print(f"=================================================={COLOR_RESET}")
    
    test_calls_dir = os.path.join(current_dir, "test_calls")
    if not os.path.exists(test_calls_dir):
        os.makedirs(test_calls_dir)
        print(f"{COLOR_YELLOW}Created empty test directory at: {test_calls_dir}")
        print(f"Please place your private test files (.wav and .txt) in this folder.{COLOR_RESET}\n")
        return
        
    # Scan for wav files
    wav_files = [f for f in os.listdir(test_calls_dir) if f.lower().endswith(".wav")]
    if not wav_files:
        print(f"{COLOR_YELLOW}No test audio (.wav) files found in: {test_calls_dir}")
        print(f"Name them like 'test1.wav' and add matching 'test1.txt' expected files.{COLOR_RESET}\n")
        return
        
    print(f"Found {len(wav_files)} test audio samples. Initializing GIS shapefiles...")
    try:
        validator = CoquitlamDataValidator(
            os.path.join(parent_dir, ADDRESS_SHAPEFILE_PATH),
            os.path.join(parent_dir, ZONES_SHAPEFILE_PATH),
            house_num_col=ADDRESS_HOUSE_NUM_COLUMN,
            street_name_col=ADDRESS_STREET_NAME_COLUMN,
            street_type_col=ADDRESS_STREET_TYPE_COLUMN,
            full_addr_col=ADDRESS_FULL_ADDR_COLUMN,
            zone_map_name_col=ZONES_MAP_NAME_COLUMN,
            street_confidence_threshold=STREET_NAME_CONFIDENCE_THRESHOLD
        )
        print("GIS Database initialized successfully.")
    except Exception as e:
        print(f"{COLOR_RED}Warning: Failed to load GIS shapefiles ({e}). Geocoding checks will be skipped.{COLOR_RESET}")
        validator = None

    print(f"\nRunning test cases...\n")
    
    results = []
    
    for wav_file in sorted(wav_files):
        wav_path = os.path.join(test_calls_dir, wav_file)
        base_name = os.path.splitext(wav_file)[0]
        txt_path = os.path.join(test_calls_dir, f"{base_name}.txt")
        
        expected = load_test_case(txt_path)
        
        print(f"{COLOR_BOLD}Analyzing Sample: {wav_file}...{COLOR_RESET}")
        
        # 1. Transcribe Audio
        actual_raw_transcript = transcribe_audio_file(wav_path)
        if not actual_raw_transcript:
            print(f"  {COLOR_RED}[FAIL] STT FAILURE: Transcription failed to return text.{COLOR_RESET}\n")
            results.append({
                "file": wav_file,
                "score": 0.0,
                "issues": ["STT_FAILURE"]
            })
            continue
            
        actual_sanitized = sanitize_transcript(actual_raw_transcript)
        expected_sanitized = sanitize_transcript(expected["transcript"])
        
        # Calculate Transcription Similarity
        stt_score = fuzz.ratio(expected_sanitized, actual_sanitized)
        
        # 2. Parse Announcements
        # Split by 'coquitlam' just like the production loop
        announcements = re.split(r'\bcoquitlam\b', actual_sanitized, flags=re.IGNORECASE)
        all_candidates = []
        for text in announcements:
            if len(text.split()) > 2:
                all_candidates.extend(parse_dispatch_announcement(text, UNITS_VOCABULARY))
                
        # Aggregate parsed results
        parsed_address = next((d.address for d in all_candidates if d.address), None)
        parsed_intersection = next((d.intersection for d in all_candidates if d.intersection), None)
        parsed_units_str = next((d.units for d in all_candidates if d.units), None)
        parsed_priority = next((d.response_type for d in all_candidates if d.response_type), None)
        parsed_grid = next((d.map_grid for d in all_candidates if d.map_grid), None)
        
        parsed_units_abbr = abbreviate_units(parsed_units_str)
        
        # 3. Geocode check
        geocode_success = False
        coords = None
        if validator and (parsed_address or parsed_intersection):
            loc_candidate = parsed_address or parsed_intersection
            res = validator.local_geocode(loc_candidate)
            if res and res.get("lat") is not None:
                geocode_success = True
                coords = (res["lat"], res["lng"])
                
        # 4. Diagnose Issues & Match Checks
        issues = []
        
        # Audio/STT quality checks
        if stt_score < 75:
            issues.append("LOW_AUDIO_QUALITY")
        elif stt_score < 90:
            issues.append("STT_MINOR_MISHEARINGS")
            
        # Address Match checks
        address_matched = False
        if expected["address"]:
            expected_addr_sanitized = sanitize_transcript(expected["address"])
            actual_addr_sanitized = sanitize_transcript(parsed_address or "")
            if expected_addr_sanitized in actual_addr_sanitized or actual_addr_sanitized in expected_addr_sanitized:
                address_matched = True
            else:
                if expected_addr_sanitized in expected_sanitized:
                    issues.append("PARSER_RULE_ERROR")
                else:
                    issues.append("MISSING_LOCATION")
        
        # Geocode Verification check
        if (parsed_address or parsed_intersection) and not geocode_success:
            issues.append("GIS_DATABASE_MISMATCH")
            
        # Responding units check
        units_matched = True
        if expected["units"]:
            for u in expected["units"]:
                if u not in parsed_units_abbr:
                    units_matched = False
            if not units_matched and parsed_units_str:
                issues.append("PARSER_RULE_ERROR")
                
        # Response priority check
        priority_matched = True
        if expected["priority"] and parsed_priority:
            if expected["priority"].lower() != parsed_priority.lower():
                priority_matched = False
                issues.append("PARSER_RULE_ERROR")
                
        # Grid Match check
        grid_matched = True
        if expected["grid"] and parsed_grid:
            if str(expected["grid"]) != str(parsed_grid):
                grid_matched = False
                issues.append("PARSER_RULE_ERROR")
                
        # Grid Bounds check
        if geocode_success and parsed_grid and validator:
            in_grid = validator.validate_point_in_grid(coords[0], coords[1], parsed_grid)
            if not in_grid:
                issues.append("GRID_BOUNDS_MISMATCH")
                
        # Print Individual Diagnostics Report
        print(f"  {COLOR_BLUE}Expected Transcript:{COLOR_RESET} '{expected['transcript']}'")
        print(f"  {COLOR_BLUE}Actual STT Output:  {COLOR_RESET} '{actual_raw_transcript}'")
        
        color = COLOR_GREEN if stt_score >= 90 else COLOR_YELLOW if stt_score >= 75 else COLOR_RED
        print(f"  {COLOR_BOLD}Transcription Accuracy:{COLOR_RESET} {color}{stt_score}% Match{COLOR_RESET}")
        
        print(f"  {COLOR_BOLD}Parsing Results:{COLOR_RESET}")
        
        # Address Details printing
        if expected["address"] or parsed_address:
            status = f"{COLOR_GREEN}[OK] Match{COLOR_RESET}" if address_matched else f"{COLOR_RED}[FAIL] Mismatch (Expected: '{expected['address']}', Got: '{parsed_address}'){COLOR_RESET}"
            print(f"    - Address:      {parsed_address} ({status})")
            
        # Geocode printing
        if parsed_address:
            geo_status = f"{COLOR_GREEN}[OK] Coordinates Found {coords}{COLOR_RESET}" if geocode_success else f"{COLOR_RED}[FAIL] GIS Shapefile Not Found (Coordinates: None){COLOR_RESET}"
            print(f"    - Geocoding:    {geo_status}")
            
        # Units Details printing
        if expected["units"] or parsed_units_abbr:
            status = f"{COLOR_GREEN}[OK] Match{COLOR_RESET}" if units_matched else f"{COLOR_RED}[FAIL] Mismatch (Expected: {expected['units']}, Got: {parsed_units_abbr}){COLOR_RESET}"
            print(f"    - Responding:   {parsed_units_abbr} ({status})")
            
        # Priority details
        if expected["priority"] or parsed_priority:
            status = f"{COLOR_GREEN}[OK] Match{COLOR_RESET}" if priority_matched else f"{COLOR_RED}[FAIL] Mismatch (Expected: {expected['priority']}, Got: {parsed_priority}){COLOR_RESET}"
            print(f"    - Priority:     {parsed_priority} ({status})")
            
        # Grid Details
        if expected["grid"] or parsed_grid:
            status = f"{COLOR_GREEN}[OK] Match{COLOR_RESET}" if grid_matched else f"{COLOR_RED}[FAIL] Mismatch (Expected: {expected['grid']}, Got: {parsed_grid}){COLOR_RESET}"
            print(f"    - Map Grid:     {parsed_grid} ({status})")
            
        if issues:
            issue_pills = " ".join([f"{COLOR_YELLOW}[{i}]{COLOR_RESET}" for i in issues])
            print(f"  {COLOR_BOLD}Diagnosed Issues:{COLOR_RESET} {issue_pills}")
        else:
            print(f"  {COLOR_GREEN}{COLOR_BOLD}[OK] Clean Parse (No issues detected){COLOR_RESET}")
            
        print("-" * 40 + "\n")
        
        results.append({
            "file": wav_file,
            "score": stt_score,
            "issues": issues,
            "geocode_success": geocode_success
        })
        
    # --- DASHBOARD SUMMARY ---
    total_cases = len(results)
    avg_stt_score = sum(r["score"] for r in results) / total_cases
    geocoded_cases = sum(1 for r in results if r.get("geocode_success", False))
    
    all_issues = []
    for r in results:
        all_issues.extend(r["issues"])
        
    issue_counts = {}
    for i in all_issues:
        issue_counts[i] = issue_counts.get(i, 0) + 1
        
    print(f"{COLOR_CYAN}{COLOR_BOLD}==================================================")
    print("                AGGREGATE STATISTICS")
    print(f"=================================================={COLOR_RESET}")
    print(f"Total Test Cases Run:   {total_cases}")
    
    color = COLOR_GREEN if avg_stt_score >= 90 else COLOR_YELLOW if avg_stt_score >= 75 else COLOR_RED
    print(f"Avg STT Accuracy:       {color}{avg_stt_score:.1f}%{COLOR_RESET}")
    
    geo_pct = (geocoded_cases / total_cases) * 100
    color = COLOR_GREEN if geo_pct >= 90 else COLOR_YELLOW if geo_pct >= 60 else COLOR_RED
    print(f"Geocoding Success Rate: {color}{geo_pct:.1f}% ({geocoded_cases}/{total_cases}){COLOR_RESET}")
    
    if issue_counts:
        print(f"\n{COLOR_BOLD}Identified Issues Grouped by Severity:{COLOR_RESET}")
        for issue_type, count in sorted(issue_counts.items(), key=lambda x: x[1], reverse=True):
            desc = ""
            if issue_type == "LOW_AUDIO_QUALITY":
                desc = "Audio recording is highly distorted/static. Needs line-in correction."
            elif issue_type == "STT_MINOR_MISHEARINGS":
                desc = "Minor phonetic mishearings. Usually ignorable."
            elif issue_type == "PARSER_RULE_ERROR":
                desc = "Address/Priority is transcribed, but parsing regex or state segmenter failed."
            elif issue_type == "MISSING_LOCATION":
                desc = "Location is entirely missing from the transcript."
            elif issue_type == "GIS_DATABASE_MISMATCH":
                desc = "Parsed address does not exist in Coquitlam shapefile (house num or suffix mismatch)."
            elif issue_type == "GRID_BOUNDS_MISMATCH":
                desc = "Resolved coordinates do not match the expected response grid envelope."
                
            print(f"  {COLOR_RED}* {issue_type:<23} ({count} occurrence(s)){COLOR_RESET}")
            print(f"    Description: {desc}")
    else:
        print(f"\n{COLOR_GREEN}{COLOR_BOLD}[SUCCESS] PERFECT RUN! All test cases parsed and geocoded flawlessly.{COLOR_RESET}")
        
    print(f"\n{COLOR_CYAN}{COLOR_BOLD}=================================================={COLOR_RESET}\n")

if __name__ == "__main__":
    run_diagnostics()
