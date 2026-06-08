import os
import sys
import re
import googlemaps
import requests # We still use requests
from google.cloud import speech
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

# --- All previous functions (transcribe_audio_file, parse_address_from_transcript, geocode_address) remain unchanged ---
# ... (omitting for brevity) ...
def transcribe_audio_file(file_path: str) -> str:
    # ... (code is identical to previous version)
    if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        print("Error: The GOOGLE_APPLICATION_CREDENTIALS environment variable is not set.")
        return ""
    if not os.path.exists(file_path):
        print(f"Error: Audio file not found at '{file_path}'")
        return ""
    try:
        client = speech.SpeechClient()
        with open(file_path, "rb") as audio_file:
            content = audio_file.read()
        audio = speech.RecognitionAudio(content=content)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=44100,
            language_code="en-CA",
            enable_automatic_punctuation=True,
        )
        print("Sending audio to Google Speech-to-Text API...")
        response = client.recognize(config=config, audio=audio)
        print("API Response Received.")
        if not response.results:
            print("Warning: API returned no results.")
            return ""
        first_result = response.results[0]
        transcript = first_result.alternatives[0].transcript
        confidence = first_result.alternatives[0].confidence
        print("-" * 30)
        print(f"Transcript: {transcript}")
        print(f"Confidence: {confidence:.2%}")
        print("-" * 30)
        return transcript
    except Exception as e:
        print(f"An API error occurred: {e}")
        return ""

def parse_address_from_transcript(transcript: str) -> str | None:
    # ... (code is identical to previous version)
    address_pattern = re.compile(
        r"((?:\d+)|(?:[A-Za-z]+\s*)+)\s+([A-Za-z\s]+?)\s+(Street|Avenue|Drive|Way|Road|Crescent|Boulevard|Place|Court)",
        re.IGNORECASE
    )
    matches = address_pattern.findall(transcript)
    if not matches:
        print("Address Parsing: No potential addresses found.")
        return None
    print(f"Address Parsing: Found {len(matches)} potential address(es).")
    parsed_addresses = []
    for match in matches:
        number_part, street_name, street_type = match
        number_part = number_part.strip()
        street_name = street_name.strip()
        try:
            street_number = w2n.word_to_num(number_part)
        except ValueError:
            try:
                digits = [str(w2n.word_to_num(word)) for word in number_part.split()]
                street_number = "".join(digits)
            except ValueError:
                street_number = number_part
        full_address = f"{street_number} {street_name} {street_type}, Coquitlam, BC"
        parsed_addresses.append({"number": str(street_number), "name": street_name, "full": full_address})
    print("--- Parsed Address Details ---")
    for i, addr in enumerate(parsed_addresses):
        print(f"  Match {i+1}: {addr['full']}")
    print("-" * 30)
    if parsed_addresses:
        validated_address = parsed_addresses[0]['full']
        print(f"Validation successful. Using first found address: '{validated_address}'")
        return validated_address
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

# REVISED FUNCTION to use Join and Tasker
def launch_navigation_on_phone(location_data: dict, join_api_key: str):
    """
    Sends a message to an Android phone via Join to trigger a Tasker action.

    Args:
        location_data: A dictionary containing the geocoded location info.
        join_api_key: The personal API key for the Join service.
    """
    if not join_api_key:
        print("Error: JOIN_API_KEY environment variable not set.")
        return

    # The 'text' payload for Join will be our command ("dispatch") followed
    # by the coordinates that Tasker will use.
    coordinates = f"{location_data['latitude']},{location_data['longitude']}"
    text_payload = f"dispatch=:={coordinates}"

    base_url = "https://joinjoaomgcd.appspot.com/_ah/api/messaging/v1/sendPush"
    params = {
        'apikey': join_api_key,
        'deviceId': 'group.phone', # This sends to all your phones
        'text': text_payload
    }

    try:
        print(f"Sending Join message to trigger navigation for: {coordinates}")
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        print("Join message sent successfully.")
    except requests.exceptions.RequestException as e:
        print(f"An error occurred sending Join message: {e}")

# --- MODIFIED MAIN BLOCK ---
if __name__ == "__main__":
    gmaps_api_key = os.environ.get("GOOGLE_API_KEY")
    join_api_key = os.environ.get("JOIN_API_KEY") # Get the Join key
    
    audio_file_name = "test_dispatch.wav"
    full_transcript = transcribe_audio_file(audio_file_name)

    if full_transcript:
        validated_address = parse_address_from_transcript(full_transcript)
        
        if validated_address:
            print("\n--- DEV OVERRIDE: Using known correct address for testing ---")
            correct_address_for_test = "428 Nelson St, Coquitlam, BC"
            
            location_info = geocode_address(correct_address_for_test, gmaps_api_key)

            if location_info:
                # Step 4: Launch navigation on the phone
                launch_navigation_on_phone(location_info, join_api_key)
                
                print("\nSUCCESS! Audio to remote navigation launch test complete.")
            else:
                print("\nFAILURE: Could not obtain a precise location for the address.")