import os
import requests
import logging
import time

# --- Minimal Logging Setup for a Test Script ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)-8s - %(message)s')

def launch_navigation_on_phone(location_data: dict, address_label: str, join_api_key: str):
    """
    Builds a simple, multi-part payload that is easy for Tasker to split.
    """
    latitude = location_data['latitude']
    longitude = location_data['longitude']
    label = address_label

    # --- THIS IS THE CORRECTED LINE ---
    # The command is "dispatch:=" with the colon.
    text_payload = f"dispatch=:={latitude}|||{longitude}|||{label}"
    # ------------------------------------
    
    base_url = "https://joinjoaomgcd.appspot.com/_ah/api/messaging/v1/sendPush"
    params = {'apikey': join_api_key, 'deviceId': 'group.phone', 'text': text_payload}
    
    logging.info(f"Preparing to send payload: {text_payload}")
    
    try:
        logging.info("Sending navigation request to Join API...")
        response = requests.get(base_url, params=params, timeout=10)
        response.raise_for_status()
        logging.info("Join message sent successfully.")
    except requests.exceptions.RequestException as e:
        logging.error(f"An error occurred sending Join message: {e}")

# --- Main block for the test script ---
if __name__ == "__main__":
    logging.info("--- Starting Corrected Join/Tasker Test Script ---")
    
    join_api_key = os.environ.get("JOIN_API_KEY")

    # Using the correct Fire Hall coordinates and address label.
    test_location_coords = {
        "latitude": 49.29151263544317,
        "longitude": -122.7908830483919,
    }
    test_address_label = "1300 Pinetree Way, Coquitlam"
    
    if join_api_key:
        launch_navigation_on_phone(test_location_coords, test_address_label, join_api_key)
    else:
        logging.error("JOIN_API_KEY environment variable is not set. Cannot run test.")

    logging.info("--- Test complete. Check your phone. ---")