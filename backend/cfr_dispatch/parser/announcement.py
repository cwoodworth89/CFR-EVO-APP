# cfr_dispatch/parser/announcement.py
# Dispatch announcement segmentation and the template parser that turns a
# sanitised transcript into DispatchData records.

import logging
import regex as re
from typing import List
from word2number import w2n
from thefuzz import fuzz

from cfr_dispatch.config import (
    DispatchData,
    UNIT_PARSING_IGNORE_LIST,
    INVALID_NEXT_WORDS,
    RESPONSE_TYPES,
    RADIO_CHANNELS,
    MAP_GRIDS,
)

from .sanitize import sanitize_transcript
from .call_types import CALL_TYPES, match_incident_type
from .channels import match_radio_channel, clean_channel_name_for_output
from .location import (
    normalize_street_suffix,
    clean_location_text,
    extract_subaddress_info,
    fuzzy_correct_cross_roads,
)

def parse_dispatch_announcement(announcement_text: str, units_vocab: List[str]) -> List[DispatchData]:
    """
    Parses sanitized text for dispatch fields, including addresses, intersections, units,
    response priority types, and map response grids. Attempts template-aligned anchor
    segmentation first, and falls back to standard regex parsing if necessary.
    """
    text = sanitize_transcript(announcement_text)
    
    street_types = r"street|avenue|drive|way|road|crescent|boulevard|place|court|highway|lane"
    
    # --- 1. Try Template-Aligned Anchor Segmentation ---
    # Template: [Units] respond [priority] [incident_type] [address] near/cross roads [cross_roads] use talk group [channel] map grid [grid]
    response_pattern_str = '|'.join(re.escape(rt.strip().lower()) for rt in RESPONSE_TYPES)
    respond_match = re.search(r'\brespond\s+(' + response_pattern_str + r')\b', text, re.IGNORECASE)
    if respond_match:
        try:
            respond_idx = respond_match.start()
            respond_len = len(respond_match.group(0))
            
            # Units segment: text preceding 'respond'
            units_segment = text[:respond_idx].strip()
            # Clean up trailing and leading "and" from units segment
            units_segment = re.sub(r'^(?:and\s+)+|(?:and\s*)+$', '', units_segment, flags=re.IGNORECASE).strip()
            
            # Remainder of the announcement after 'respond [priority]'
            remainder = text[respond_idx + respond_len:].strip()
            
            # Find boundary anchors
            cross_roads_match = re.search(r'\b(cross\s+roads|near|cross\s+street|cross\s+of)\b', remainder, re.IGNORECASE)
            talk_group_match = re.search(r'\b(use\s+talk\s+group|talk\s+group)\b', remainder, re.IGNORECASE)
            map_grid_match = re.search(r'\bmap\s+grid\b', remainder, re.IGNORECASE)
            
            # Determine end of Call Type + Address segment
            address_end_idx = len(remainder)
            if cross_roads_match:
                address_end_idx = min(address_end_idx, cross_roads_match.start())
            elif talk_group_match:
                address_end_idx = min(address_end_idx, talk_group_match.start())
            elif map_grid_match:
                address_end_idx = min(address_end_idx, map_grid_match.start())
                
            call_type_and_address_segment = remainder[:address_end_idx].strip()
            
            # Match Call Type within the segment to isolate the Address
            matched_call_type = None
            address_part = call_type_and_address_segment
            
            # Sort call types by length descending to match longest phrases first
            for ct in CALL_TYPES:
                ct_clean = sanitize_transcript(ct)
                if ct_clean in call_type_and_address_segment:
                    matched_call_type = ct
                    address_part = call_type_and_address_segment.replace(ct_clean, "").strip()
                    break
            else:
                # If call type didn't match exactly, isolate address by finding the first digits (house number)
                digit_match = re.search(r'\b\d+\b', call_type_and_address_segment)
                if digit_match:
                    address_part = call_type_and_address_segment[digit_match.start():].strip()
                    call_type_part = call_type_and_address_segment[:digit_match.start()].strip()
                    matched_call_type = match_incident_type(call_type_part, CALL_TYPES)
                else:
                    matched_call_type = "Unknown Incident"
            
            # If the isolated address still has text before the first digit (house number), strip it
            if address_part:
                digit_match = re.search(r'\b\d+\b', address_part)
                if digit_match:
                    pre_digit_text = address_part[:digit_match.start()].strip()
                    if pre_digit_text:
                        logging.info(f"Stripping pre-digit noise '{pre_digit_text}' from address '{address_part}'")
                        address_part = address_part[digit_match.start():].strip()
            
            # Clean and normalize isolated address
            address_part, extracted_subaddr = extract_subaddress_info(address_part)
            address_part = clean_location_text(address_part, CALL_TYPES, units_vocab)
            normalized_address = normalize_street_suffix(address_part)
            
            # Extract Cross Roads segment
            cross_roads_str = None
            if cross_roads_match:
                cross_roads_start = cross_roads_match.start() + len(cross_roads_match.group(0))
                cross_roads_end = len(remainder)
                if talk_group_match:
                    cross_roads_end = min(cross_roads_end, talk_group_match.start())
                elif map_grid_match:
                    cross_roads_end = min(cross_roads_end, map_grid_match.start())
                cross_roads_raw = remainder[cross_roads_start:cross_roads_end].strip()
                cross_roads_clean = clean_location_text(cross_roads_raw, CALL_TYPES, units_vocab)
                cross_roads_str = normalize_street_suffix(cross_roads_clean)
                try:
                    from cfr_dispatch.config.vocab import COQUITLAM_STREETS
                    if COQUITLAM_STREETS:
                        cross_roads_str = fuzzy_correct_cross_roads(cross_roads_str, COQUITLAM_STREETS)
                except Exception as ex:
                    logging.warning(f"Failed to fuzzy correct cross roads: {ex}")
                
            # Extract Talk Group (Radio channel)
            talk_group_str = None
            if talk_group_match:
                talk_group_start = talk_group_match.start() + len(talk_group_match.group(0))
                talk_group_end = len(remainder)
                if map_grid_match:
                    talk_group_end = min(talk_group_end, map_grid_match.start())
                talk_group_raw = remainder[talk_group_start:talk_group_end].strip()
                matched_chan = match_radio_channel(talk_group_raw, RADIO_CHANNELS)
                if matched_chan:
                    talk_group_str = clean_channel_name_for_output(matched_chan)
                    
            # Extract Map Grid
            map_grid_str = None
            if map_grid_match:
                map_grid_start = map_grid_match.start() + len(map_grid_match.group(0))
                map_grid_raw = remainder[map_grid_start:].strip()
                grid_digits = re.search(r'\d+', map_grid_raw)
                if grid_digits:
                    grid_val = grid_digits.group(0)
                    if grid_val in MAP_GRIDS:
                        map_grid_str = grid_val
                    else:
                        logging.warning(f"Parsed map grid '{grid_val}' is not in ground-truth MAP_GRIDS. Rejecting.")
                    
            is_intersection = bool(normalized_address and re.search(r'\band\b', normalized_address, re.IGNORECASE))

            # Split cross streets into individual columns
            cross_1 = None
            cross_2 = None
            if cross_roads_str:
                cross_parts = re.split(r'\s+and\s+|\s*&\s*', cross_roads_str, flags=re.IGNORECASE)
                cross_1 = cross_parts[0].strip() if len(cross_parts) >= 1 else None
                cross_2 = cross_parts[1].strip() if len(cross_parts) >= 2 else None

            # If the address itself is an intersection, also extract its parts as cross streets
            if is_intersection and normalized_address:
                int_parts = re.split(r'\s+and\s+|\s*&\s*', normalized_address, flags=re.IGNORECASE)
                cross_1 = int_parts[0].strip() if len(int_parts) >= 1 else cross_1
                cross_2 = int_parts[1].strip() if len(int_parts) >= 2 else cross_2

            dispatch = DispatchData(
                raw_text=text,
                units=units_segment if units_segment else None,
                response_type=respond_match.group(1).strip(),
                call_type=matched_call_type,
                address=normalized_address if normalized_address and not is_intersection else None,
                intersection=normalized_address if is_intersection else None,  # ONLY true intersections
                cross_street_1=cross_1,
                cross_street_2=cross_2,
                radio_channel=talk_group_str,
                map_grid=map_grid_str,
                subaddress=extracted_subaddr
            )
            
            if dispatch.address or dispatch.intersection:
                return [dispatch]
        except Exception as e:
            logging.warning(f"Template parsing failed: {e}. Falling back to regex parser.")

    # --- 2. Fallback to Standard Regex Parsing ---
    unit_lookbehind = '|'.join(UNIT_PARSING_IGNORE_LIST)
    
    address_pattern = re.compile(
        fr"(?<!\b(?:{unit_lookbehind})s?\s\d+\s)" 
        fr"(?P<number_phrase>(?:\d+[\s-]*)+)\s+" 
        fr"(?P<street_name>(?:[a-zA-Z'-]+\s+){{0,4}}?)"
        fr"(?P<street_type>{street_types})"
        fr"(?! \s* (?:{INVALID_NEXT_WORDS}))",
        re.IGNORECASE | re.VERBOSE
    )
    
    address_matches = list(address_pattern.finditer(text))
    intersection_pattern = re.compile(
        fr"((?:[\w'-]+\s+){{0,4}}?(?:{street_types}))\s+and\s+((?:[\w'-]+\s+){{0,4}}?(?:{street_types}))",
        re.IGNORECASE
    )
    intersection_match = intersection_pattern.search(text)
    
    found_dispatches = []
    if address_matches:
        for match in address_matches:
            number_phrase = match.group('number_phrase').strip()
            cleaned_number = None
            
            try:
                cleaned_number = str(w2n.word_to_num(number_phrase))
                logging.debug(f"Successfully parsed number phrase '{number_phrase}' with word2number -> {cleaned_number}")
            except (ValueError, AttributeError, TypeError, KeyError):
                digits_only = "".join(filter(str.isdigit, number_phrase))

                if digits_only:
                    cleaned_number = digits_only
                    logging.debug(f"word2number failed for '{number_phrase}', fell back to digit joining -> {cleaned_number}")

            if not cleaned_number:
                logging.warning(f"Could not parse a valid number from phrase: '{number_phrase}'. Skipping candidate.")
                continue

            raw_street = f"{match.group('street_name').strip()} {match.group('street_type')}"
            cleaned_street = clean_location_text(raw_street, CALL_TYPES, units_vocab)
            normalized_street = normalize_street_suffix(cleaned_street)
            
            if normalized_street:
                address_str = f"{cleaned_number} {normalized_street}"
                # Check for trailing subaddress right after the street type
                post_address_text = text[match.end():].strip()
                # Strip out any subsequent anchors (cross roads, talk group, map grid) to isolate the subaddress
                sub_clean = re.sub(r'\b(?:near|cross\s+roads|cross\s+street|cross\s+of|use\s+talk\s+group|talk\s+group|map\s+grid|math\s+grade|math\s+grid)\b.*', '', post_address_text, flags=re.IGNORECASE).strip()
                sub_clean = sub_clean.rstrip(',- ').lstrip(',- ')
                
                extracted_subaddr = sub_clean if sub_clean else None
                if extracted_subaddr and re.match(r'^#?\s*\d+$', extracted_subaddr):
                    extracted_subaddr = f"Unit {extracted_subaddr.replace('#', '').strip()}"
                
                found_dispatches.append(DispatchData(raw_text=text, address=address_str, subaddress=extracted_subaddr))
                
    if not found_dispatches and intersection_match:
        leg1 = clean_location_text(intersection_match.group(1), CALL_TYPES, units_vocab)
        leg2 = clean_location_text(intersection_match.group(2), CALL_TYPES, units_vocab)
        normalized_leg1 = normalize_street_suffix(leg1)
        normalized_leg2 = normalize_street_suffix(leg2)
        if normalized_leg1 and normalized_leg2:
            intersection_str = f"{normalized_leg1} and {normalized_leg2}"
            found_dispatches.append(DispatchData(
                raw_text=text,
                intersection=intersection_str,
                cross_street_1=normalized_leg1,
                cross_street_2=normalized_leg2
            ))
            
    if not found_dispatches:
        return []

    # Sort units_vocab descending by length to support multi-word units correctly in the regex
    sorted_vocab = sorted(units_vocab, key=len, reverse=True)
    units_pattern = re.compile(r'^(?:coquitlam\s+)?(?P<units>(?:(?:' + '|'.join(re.escape(u) for u in sorted_vocab) + r')\s+[\w\d-]+[,\s]*)+)', re.IGNORECASE)
    response_pattern = re.compile(r'\brespond\s*(?P<type>' + response_pattern_str + r')\b', re.IGNORECASE)
    map_grid_pattern = re.compile(r'\b(?:map grid|math grade|math grid)\s*(\d{1,3})\b', re.IGNORECASE)
    final_grid_pattern = re.compile(r'coquitlam\s*(\d{1,3})\b', re.IGNORECASE)
    
    units_str = (units_pattern.search(text).group('units').strip() if units_pattern.search(text) else None)
    response_str = (response_pattern.search(text).group('type').strip() if response_pattern.search(text) else None)
    
    parsed_grids = map_grid_pattern.findall(text)
    final_grid_matches = final_grid_pattern.findall(text)
    if final_grid_matches:
        parsed_grids.extend(final_grid_matches)
    valid_grids = [g for g in parsed_grids if g in MAP_GRIDS]
    grid_str = valid_grids[0] if valid_grids else None
    
    # Look for talk group match in fallback text
    talk_group_pattern = re.compile(r'\b(?:use talk group|talk group)\s+(.+?)(?:\s+map grid|\s+math grade|\s+math grid|$)', re.IGNORECASE)
    tg_match = talk_group_pattern.search(text)
    fallback_tg_str = None
    if tg_match:
        matched_chan = match_radio_channel(tg_match.group(1), RADIO_CHANNELS)
        if matched_chan:
            fallback_tg_str = clean_channel_name_for_output(matched_chan)
            
    for dispatch in found_dispatches:
        dispatch.units = units_str
        dispatch.response_type = response_str
        dispatch.map_grid = grid_str
        dispatch.radio_channel = fallback_tg_str
        
    return found_dispatches


def split_rounds(text: str, units_vocab: List[str]) -> List[str]:
    """
    Splits a continuous transcript containing multiple announcement rounds into separate segments.
    Aligns with Coquitlam dispatch structures where the wake-word is not repeated.
    Splits by:
      1. Right after the first "map grid [digits]" or "grid [digits]" phrase.
      2. Before the second occurrence of the station wake-word "coquitlam".
      3. Before the second occurrence of a responding unit followed by "respond" or "response".
    """
    # Normalize spaces
    text = ' '.join(text.strip().split())
    
    # 1. Split right after the first "(map) grid [digits/words]" (standard end of Round 1)
    grid_split = re.split(r'(?<=\b(?:map\s+)?grid\s+\w+\b)', text, maxsplit=1, flags=re.IGNORECASE)
    if len(grid_split) >= 2 and len(grid_split[0].strip()) > 15:
        return [grid_split[0].strip(), grid_split[1].strip()]
        
    # 2. Split before the second occurrence of "coquitlam" (station wake-word)
    cq_matches = list(re.finditer(r'\bcoquitlam\b', text, flags=re.IGNORECASE))
    if len(cq_matches) >= 2 and cq_matches[1].start() > 15:
        split_idx = cq_matches[1].start()
        return [text[:split_idx].strip(), text[split_idx:].strip()]

    # 3. Fallback: Split before the second occurrence of a unit followed by "respond" / "response"
    unit_pattern = '|'.join(re.escape(u.lower()) for u in units_vocab)
    matches = list(re.finditer(rf'\b({unit_pattern})\s+\d+\s+respon(?:d|se)\b', text, flags=re.IGNORECASE))
    if len(matches) >= 2 and matches[1].start() > 15:
        split_idx = matches[1].start()
        return [text[:split_idx].strip(), text[split_idx:].strip()]
        
    return [text]


def reconstruct_template_transcript(dispatch: DispatchData) -> str:
    """
    Reconstructs a clean, standard, template-compliant transcript from parsed entities,
    expanding abbreviations to align verbally with the dispatcher's voice.
    """
    # 1. Expand Unit Names (e.g. E1 -> Engine 1, R2 -> Rescue 2)
    def expand_unit(u: str) -> str:
        u_clean = str(u).strip().upper()
        match = re.match(r'^([A-Z]+)(\d+)$', u_clean)
        if match:
            abbr, num = match.groups()
            name_map = {
                'E': 'Engine', 'R': 'Rescue', 'L': 'Ladder',
                'Q': 'Quint', 'M': 'Medic', 'S': 'Squad', 'B': 'Battalion'
            }
            full_name = name_map.get(abbr, abbr)
            return f"{full_name} {num}"
        return str(u).title()

    if dispatch.units:
        unit_list = dispatch.units if isinstance(dispatch.units, list) else [dispatch.units]
        units_part = ", ".join(expand_unit(u) for u in unit_list)
        # Strip any leading 'coquitlam' from units_part to avoid doubled-up "Coquitlam Coquitlam"
        units_part = re.sub(r'^(?:coquitlam\s+)+', '', units_part, flags=re.IGNORECASE).strip()
    else:
        units_part = "units"
        
    # 2. Priority
    resp = (dispatch.response_type or "routine").lower()
    priority_part = f"respond {resp}"
    
    # 3. Call Type
    call_type_part = (dispatch.call_type or "incident").lower()
        
    # 4. Address (Expand suffix abbreviations: e.g. pl -> place, cres -> crescent)
    def expand_address_suffix(addr: str) -> str:
        if not addr:
            return "address"
        suffix_map = {
            r'\bpl\b': 'place',
            r'\bcres\b': 'crescent',
            r'\bave\b': 'avenue',
            r'\bst\b': 'street',
            r'\brd\b': 'road',
            r'\bdr\b': 'drive',
            r'\bln\b': 'lane',
            r'\bct\b': 'court',
            r'\bblvd\b': 'boulevard',
            r'\bhwy\b': 'highway',
            r'\bwy\b': 'way'
        }
        addr_lower = addr.lower()
        for pattern, replacement in suffix_map.items():
            addr_lower = re.sub(pattern, replacement, addr_lower)
        return addr_lower

    if dispatch.address:
        address_part = expand_address_suffix(dispatch.address)
        if dispatch.subaddress:
            address_part = f"{address_part} {dispatch.subaddress}"
        cross_desc = None
        if dispatch.cross_street_1 and dispatch.cross_street_2:
            cross_desc = f"{dispatch.cross_street_1} and {dispatch.cross_street_2}"
        elif dispatch.cross_street_1:
            cross_desc = dispatch.cross_street_1
        elif dispatch.intersection:
            cross_desc = dispatch.intersection
        elif " and " in dispatch.address.lower() or " & " in dispatch.address:
            cross_desc = dispatch.address
        intersection_part = f", near {expand_address_suffix(cross_desc)}" if cross_desc else ""
    elif dispatch.intersection:
        address_part = expand_address_suffix(dispatch.intersection)
        if dispatch.subaddress:
            address_part = f"{address_part} {dispatch.subaddress}"
        intersection_part = f", near {expand_address_suffix(dispatch.intersection)}"
    else:
        address_part = "address"
        intersection_part = ""
        
    # 6. Radio Channel (Map digital channels back to the full verbal name)
    channel_part = None
    if dispatch.radio_channel:
        chan = dispatch.radio_channel.strip()
        if chan == "10" or "combined" in chan.lower():
            channel_part = "use talk group 10 combined response coquitlam"
        else:
            chan_lower = chan.lower()
            if "talk group" in chan_lower:
                channel_part = chan_lower
            else:
                channel_part = f"use talk group {chan_lower}"
            if not channel_part.endswith("coquitlam"):
                channel_part = f"{channel_part} coquitlam"
            
    # 7. Map Grid
    grid_part = f"map grid {dispatch.map_grid}" if dispatch.map_grid else None
        
    # Reconstruct transcript matching template punctuation/commas
    # Format: "Coquitlam [Units], respond [Priority], [Incident], [Address], [near Intersection], [Talk Group], [Map Grid]"
    parts = [
        f"Coquitlam {units_part}",
        priority_part,
        call_type_part,
        f"{address_part}{intersection_part}"
    ]
    if channel_part:
        parts.append(channel_part)
    if grid_part:
        parts.append(grid_part)
        
    reconstructed = ", ".join(parts)
    return reconstructed
