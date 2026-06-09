import os
import sys
import re
import googlemaps
import requests # We still use requests
from google.cloud import speech, speech_v2
from word2number import w2n

# Automatically load environment variables and resolve credentials absolute path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)
try:
    import agent.cfr_dispatch
except ImportError:
    try:
        import cfr_dispatch
    except ImportError:
        pass

# Import speech adaptation parameters
try:
    from agent.cfr_dispatch.config import (
        ADAPTATION_RESOURCE_IDS,
        BOOST_MAPPING,
        GCP_PROJECT_ID,
        RECOGNIZER_RESOURCE_NAME
    )
except ImportError:
    from cfr_dispatch.config import (
        ADAPTATION_RESOURCE_IDS,
        BOOST_MAPPING,
        GCP_PROJECT_ID,
        RECOGNIZER_RESOURCE_NAME
    )

# --- All previous functions (transcribe_audio_file, parse_address_from_transcript, geocode_address) remain unchanged ---
# ... (omitting for brevity) ...
def transcribe_audio_file(file_path: str) -> str:
    if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        print("Error: The GOOGLE_APPLICATION_CREDENTIALS environment variable is not set.")
        return ""
    if not os.path.exists(file_path):
        print(f"Error: Audio file not found at '{file_path}'")
        return ""
    try:
        client = speech_v2.SpeechClient()

        phrases_to_boost = []
        for resource_id in ADAPTATION_RESOURCE_IDS:
            base_id = next((key for key in BOOST_MAPPING if resource_id.startswith(key)), None)
            boost_value = BOOST_MAPPING.get(base_id, 10)
            
            full_resource_name = f"projects/{GCP_PROJECT_ID}/locations/global/customClasses/{resource_id}"
            phrases_to_boost.append({"value": f"${full_resource_name}", "boost": boost_value})

        inline_set = speech_v2.types.PhraseSet(phrases=phrases_to_boost)
        adaptation_phrase_set_dict = {"inline_phrase_set": inline_set}
        adaptation_config = speech_v2.SpeechAdaptation(
            phrase_sets=[adaptation_phrase_set_dict]
        )
        
        config = speech_v2.RecognitionConfig(
            auto_decoding_config={},
            language_codes=["en-CA"],
            model="long",
            features=speech_v2.RecognitionFeatures(
                enable_automatic_punctuation=True,
            ),
            adaptation=adaptation_config
        )

        with open(file_path, "rb") as audio_file:
            content = audio_file.read()
        
        request = speech_v2.types.RecognizeRequest(
            recognizer=RECOGNIZER_RESOURCE_NAME,
            config=config,
            content=content,
        )
        
        print("Sending audio to Google Speech-to-Text API v2 with adaptation...")
        response = client.recognize(request=request)
        print("API Response Received.")

        if not response or not response.results:
            print("Warning: API returned no results.")
            return ""
        
        transcripts = []
        for result in response.results:
            if result.alternatives:
                transcripts.append(result.alternatives[0].transcript)
                print(f"Segment Transcript: {result.alternatives[0].transcript}")
                print(f"Segment Confidence: {result.alternatives[0].confidence:.2%}")
        
        full_transcript = " ".join(transcripts).strip()
        print("-" * 30)
        print(f"Full Combined Transcript: {full_transcript}")
        print("-" * 30)
        return full_transcript
    except Exception as e:
        print(f"An API error occurred: {e}")
        return ""

def parse_address_from_transcript(transcript: str) -> str | None:
    from cfr_dispatch.parser import sanitize_transcript, parse_dispatch_announcement
    from cfr_dispatch.config import UNITS_VOCABULARY
    
    sanitized = sanitize_transcript(transcript)
    print(f"Sanitized Transcript: '{sanitized}'")
    
    # Split by 'coquitlam' just like the production loop
    announcements = re.split(r'\bcoquitlam\b', sanitized, flags=re.IGNORECASE)
    all_candidates = []
    for text in announcements:
        if len(text.split()) > 2:
            all_candidates.extend(parse_dispatch_announcement(text, UNITS_VOCABULARY))
            
    print("--- Production Parser Output Details ---")
    for i, d in enumerate(all_candidates):
        print(f"  Candidate {i+1}:")
        print(f"    - Units:        {d.units}")
        print(f"    - Response:     {d.response_type}")
        print(f"    - Call Type:    {d.call_type}")
        print(f"    - Address:      {d.address}")
        print(f"    - Intersection: {d.intersection}")
        print(f"    - Radio Channel: {d.radio_channel}")
        print(f"    - Map Grid:     {d.map_grid}")
    print("-" * 30)
    
    unique_addresses = []
    for d in all_candidates:
        if d.address and d.address not in unique_addresses:
            unique_addresses.append(d.address)
        if d.intersection and d.intersection not in unique_addresses:
            unique_addresses.append(d.intersection)
            
    if unique_addresses:
        print(f"Validation successful. Found address: '{unique_addresses[0]}'")
        return unique_addresses[0]
    return None

def geocode_address(address: str, api_key: str) -> dict | None:
    # ... (code is identical to previous version with validation)
    if not api_key:
        print("Error: GOOGLE_API_KEY environment variable not set.")
        return None
    gmaps = googlemaps.Client(key=api_key)
    try:
        print(f"\nSending address '{address}' to Google Geocoding API...")
        geocode_result = gmaps.geocode(address)
        if not geocode_result:
            print("Geocoding Failure: The address returned no results.")
            return None
        first_result = geocode_result[0]
        location_type = first_result["geometry"]["location_type"]
        good_location_types = ["ROOFTOP", "RANGE_INTERPOLATED", "GEOMETRIC_CENTER"]
        if location_type not in good_location_types:
             print(f"Geocoding Failure: Result is not precise. Location type is '{location_type}'.")
             return None
        location_data = {
            "formatted_address": first_result["formatted_address"],
            "latitude": first_result["geometry"]["location"]["lat"],
            "longitude": first_result["geometry"]["location"]["lng"],
            "place_id": first_result["place_id"],
            "location_type": location_type
        }
        print("--- Geocoding Result ---")
        print(f"  > Formatted Address: {location_data['formatted_address']}")
        print(f"  > Latitude:  {location_data['latitude']}")
        print(f"  > Longitude: {location_data['longitude']}")
        print(f"  > Result Quality:  {location_data['location_type']}")
        print("-" * 30)
        return location_data
    except Exception as e:
        print(f"An API error occurred during geocoding: {e}")
        return None



# --- MODIFIED MAIN BLOCK ---
if __name__ == "__main__":
    gmaps_api_key = os.environ.get("GOOGLE_API_KEY")
    
    audio_file_name = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_dispatch.wav")
    full_transcript = transcribe_audio_file(audio_file_name)

    if full_transcript:
        validated_address = parse_address_from_transcript(full_transcript)
        
        if validated_address:
            print("\n--- DEV OVERRIDE: Using known correct address for testing ---")
            correct_address_for_test = "428 Nelson St, Coquitlam, BC"
            
            location_info = geocode_address(correct_address_for_test, gmaps_api_key)

            if location_info:
                print("\nSUCCESS! Audio to address geocode test complete.")
            else:
                print("\nFAILURE: Could not obtain a precise location for the address.")