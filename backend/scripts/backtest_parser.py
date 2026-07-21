# backend/scripts/backtest_parser.py
# Compares production parser against the new sequential destructive parser using Supabase ground-truth reviews

import sys
import os
import requests
from typing import List, Dict, Any

# Ensure backend directory is in the path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

from cfr_dispatch.parser import parse_dispatch_announcement, split_rounds, abbreviate_units
from cfr_dispatch.destructive_parser import parse_destructive
from cfr_dispatch.config import UNITS_VOCABULARY

def load_credentials() -> tuple[str, str]:
    url, key = None, None
    env_path = os.path.join(backend_dir, ".env")
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    if k.strip() == "SUPABASE_URL":
                        url = v.strip()
                    elif k.strip() == "SUPABASE_SERVICE_ROLE_KEY":
                        key = v.strip()
    return url, key

def fetch_verified_calls(url: str, key: str) -> List[Dict[str, Any]]:
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json"
    }
    # Query all verified calls
    endpoint = f"{url.rstrip('/')}/rest/v1/live_calls?feedback_submitted=eq.true&order=timestamp.desc"
    res = requests.get(endpoint, headers=headers)
    if res.status_code == 200:
        return res.json()
    else:
        print(f"Error fetching calls: {res.status_code} {res.text}")
        return []

def normalize_street_suffixes(s: str) -> str:
    s = s.lower()
    suffix_map = {
        r'\blane\b': 'ln',
        r'\bstreet\b': 'st',
        r'\bavenue\b': 'ave',
        r'\broad\b': 'rd',
        r'\bdrive\b': 'dr',
        r'\bcrescent\b': 'cres',
        r'\bboulevard\b': 'blvd',
        r'\bplace\b': 'pl',
        r'\bcourt\b': 'ct',
        r'\bhighway\b': 'hwy'
    }
    for k, v in suffix_map.items():
        s = re.sub(k, v, s)
    return s

def clean_comparable_string(s: Any) -> str:
    if not s:
        return ""
    s_str = str(s).lower()
    s_str = normalize_street_suffixes(s_str)
    return "".join(filter(str.isalnum, s_str))

def check_address_match(gt: str, parsed: str) -> bool:
    gt_clean = clean_comparable_string(gt)
    parsed_clean = clean_comparable_string(parsed)
    if not gt_clean or not parsed_clean:
        return False
        
    # Check direct substring matching first
    if gt_clean in parsed_clean or parsed_clean in gt_clean:
        return True
        
    # If intersection, check set overlap of words (handles reverse street ordering)
    if "and" in gt.lower() or "and" in parsed.lower() or "&" in gt or "&" in parsed:
        gt_parts = {clean_comparable_string(p) for p in re.split(r'\s+and\s+|\s*&\s*', gt.lower()) if p.strip()}
        parsed_parts = {clean_comparable_string(p) for p in re.split(r'\s+and\s+|\s*&\s*', parsed.lower()) if p.strip()}
        if gt_parts and parsed_parts and gt_parts == parsed_parts:
            return True
            
    return False

def parse_units_to_set(units_val: Any) -> set:
    if not units_val:
        return set()
    if isinstance(units_val, list):
        return {u.lower().strip() for u in units_val if u}
    if isinstance(units_val, str):
        # Use production unit abbreviation logic
        abbr = abbreviate_units(units_val)
        return {u.lower().strip() for u in abbr if u}
    return set()

def main():
    url, key = load_credentials()
    if not url or not key:
        print("Error: Supabase URL or Service Role Key missing from backend/.env")
        sys.exit(1)

    calls = fetch_verified_calls(url, key)
    if not calls:
        print("No human-verified calls found in database to evaluate.")
        return

    print(f"Loaded {len(calls)} human-verified dispatches for comparative backtesting.\n")

    # Metrics trackers
    stats = {
        "prod": {"address": 0, "incident": 0, "units": 0, "grid": 0, "channel": 0},
        "destruct": {"address": 0, "incident": 0, "units": 0, "grid": 0, "channel": 0},
        "total": 0
    }

    discrepancies = []

    for call in calls:
        dispatch_id = call.get("dispatch_id")
        raw_transcript = call.get("raw_transcript") or ""
        if not raw_transcript:
            continue

        # Split double-rounds and grab the first round for basic parsing comparison
        rounds = split_rounds(raw_transcript, UNITS_VOCABULARY)
        first_round_text = rounds[0] if rounds else raw_transcript

        # Ground Truth Values
        gt_address = call.get("verified_address") or ""
        gt_incident = call.get("verified_incident") or call.get("incident_type") or ""
        gt_units = parse_units_to_set(call.get("verified_units") or call.get("responding_units"))
        
        target = call.get("target") or {}
        gt_grid = target.get("verified_map_grid") or target.get("map_grid") or ""
        gt_channel = target.get("verified_talkgroup") or target.get("radio_channel") or ""

        # 1. Run Production Parser
        prod_candidates = parse_dispatch_announcement(first_round_text, UNITS_VOCABULARY)
        prod_candidate = prod_candidates[0] if prod_candidates else None
        
        # 2. Run Test Destructive Parser
        destruct_candidate = parse_destructive(first_round_text, UNITS_VOCABULARY)

        stats["total"] += 1

        # Evaluate Address
        prod_addr_text = (prod_candidate.address or prod_candidate.intersection or "") if prod_candidate else ""
        destruct_addr_text = (destruct_candidate.address or destruct_candidate.intersection or "") if destruct_candidate else ""
        
        prod_addr_ok = check_address_match(gt_address, prod_addr_text)
        destruct_addr_ok = check_address_match(gt_address, destruct_addr_text)

        if prod_addr_ok: stats["prod"]["address"] += 1
        if destruct_addr_ok: stats["destruct"]["address"] += 1

        # Evaluate Incident Type
        prod_incident = prod_candidate.call_type if prod_candidate else ""
        destruct_incident = destruct_candidate.call_type

        prod_incident_ok = clean_comparable_string(gt_incident) == clean_comparable_string(prod_incident)
        destruct_incident_ok = clean_comparable_string(gt_incident) == clean_comparable_string(destruct_incident)

        if prod_incident_ok: stats["prod"]["incident"] += 1
        if destruct_incident_ok: stats["destruct"]["incident"] += 1

        # Evaluate Responding Units
        prod_units = parse_units_to_set(prod_candidate.units if prod_candidate else None)
        destruct_units = parse_units_to_set(destruct_candidate.units)

        prod_units_ok = prod_units == gt_units
        destruct_units_ok = destruct_units == gt_units

        if prod_units_ok: stats["prod"]["units"] += 1
        if destruct_units_ok: stats["destruct"]["units"] += 1

        # Evaluate Map Grid
        prod_grid = prod_candidate.map_grid if prod_candidate else ""
        destruct_grid = destruct_candidate.map_grid

        prod_grid_ok = clean_comparable_string(gt_grid) == clean_comparable_string(prod_grid)
        destruct_grid_ok = clean_comparable_string(gt_grid) == clean_comparable_string(destruct_grid)

        if prod_grid_ok: stats["prod"]["grid"] += 1
        if destruct_grid_ok: stats["destruct"]["grid"] += 1

        # Evaluate Radio Channel / Talk Group
        prod_chan = prod_candidate.radio_channel if prod_candidate else ""
        destruct_chan = destruct_candidate.radio_channel

        prod_chan_ok = clean_comparable_string(gt_channel) == clean_comparable_string(prod_chan)
        destruct_chan_ok = clean_comparable_string(gt_channel) == clean_comparable_string(destruct_chan)

        if prod_chan_ok: stats["prod"]["channel"] += 1
        if destruct_chan_ok: stats["destruct"]["channel"] += 1

        # Track Divergences/Discrepancies
        if (prod_addr_ok != destruct_addr_ok) or (prod_units_ok != destruct_units_ok) or (prod_grid_ok != destruct_grid_ok):
            discrepancies.append({
                "id": dispatch_id,
                "raw": raw_transcript,
                "gt": {
                    "address": gt_address,
                    "incident": gt_incident,
                    "units": list(gt_units),
                    "grid": gt_grid,
                    "channel": gt_channel
                },
                "prod": {
                    "address": prod_addr_text,
                    "incident": prod_incident,
                    "units": list(prod_units),
                    "grid": prod_grid,
                    "channel": prod_chan
                },
                "destruct": {
                    "address": destruct_addr_text,
                    "incident": destruct_incident,
                    "units": list(destruct_units),
                    "grid": destruct_grid,
                    "channel": destruct_chan
                }
            })

    total = stats["total"]
    if total == 0:
        print("No calls evaluated.")
        return

    # Print Comparative Accuracy Report
    print("=" * 80)
    print("                 PARSER ACCURACY COMPARISON REPORT")
    print(f"                 Total Verified Calls Tested: {total}")
    print("=" * 80)
    print("Variable          Production Parser Accuracy      Test Destructive Parser Accuracy")
    print("-" * 80)
    print(f"Address/Location  {stats['prod']['address']}/{total} ({stats['prod']['address']/total*100:.1f}%)"
          f"                {stats['destruct']['address']}/{total} ({stats['destruct']['address']/total*100:.1f}%)")
    print(f"Incident Type     {stats['prod']['incident']}/{total} ({stats['prod']['incident']/total*100:.1f}%)"
          f"                {stats['destruct']['incident']}/{total} ({stats['destruct']['incident']/total*100:.1f}%)")
    print(f"Responding Units  {stats['prod']['units']}/{total} ({stats['prod']['units']/total*100:.1f}%)"
          f"                {stats['destruct']['units']}/{total} ({stats['destruct']['units']/total*100:.1f}%)")
    print(f"Map Grid          {stats['prod']['grid']}/{total} ({stats['prod']['grid']/total*100:.1f}%)"
          f"                {stats['destruct']['grid']}/{total} ({stats['destruct']['grid']/total*100:.1f}%)")
    print(f"Talk Group        {stats['prod']['channel']}/{total} ({stats['prod']['channel']/total*100:.1f}%)"
          f"                {stats['destruct']['channel']}/{total} ({stats['destruct']['channel']/total*100:.1f}%)")
    print("=" * 80)

    # Print Discrepancy Breakdown
    if discrepancies:
        print(f"\nDiscrepancy Log ({len(discrepancies)} cases where parsers diverged):")
        print("-" * 80)
        for idx, d in enumerate(discrepancies[:10]):
            print(f"\n[{idx+1}] Dispatch ID: {d['id']}")
            print(f"  Raw Text: '{d['raw'][:140]}...'")
            print(f"  Ground Truth: Address='{d['gt']['address']}', Incident='{d['gt']['incident']}', Units={d['gt']['units']}, Grid='{d['gt']['grid']}', TalkGroup='{d['gt']['channel']}'")
            print(f"  Prod Parser:  Address='{d['prod']['address']}', Incident='{d['prod']['incident']}', Units={d['prod']['units']}, Grid='{d['prod']['grid']}', TalkGroup='{d['prod']['channel']}'")
            print(f"  Test Parser:  Address='{d['destruct']['address']}', Incident='{d['destruct']['incident']}', Units={d['destruct']['units']}, Grid='{d['destruct']['grid']}', TalkGroup='{d['destruct']['channel']}'")
        if len(discrepancies) > 10:
            print(f"\n... and {len(discrepancies) - 10} more discrepancies.")
    else:
        print("\nAll parsed outputs match identically across all reviewed dispatches!")

import regex as re
if __name__ == "__main__":
    main()
