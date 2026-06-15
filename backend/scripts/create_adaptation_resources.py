# ==============================================================================
# create_adaptation_resources.py
# DEFINITIVE SCRIPT V1.0
# NOTE: For Google STT speech adaptation resources and vocabulary boost settings, see docs/hardware_specification.md
# ==============================================================================
import os
from google.cloud import speech_v2
from google.api_core.exceptions import AlreadyExists

# --- CONFIGURATION ---
# Make sure this matches the project ID in your main script.
GCP_PROJECT_ID = 'cfr-dispatch-mapping'

# List of all CustomClass resources you want to manage.
# The 'id' is the name it will have in Google Cloud.
# The 'file' is the local .txt file containing the vocabulary.
# NOTE: The main script assumes your street files are in a 'data' subdirectory.
RESOURCES = [
    # Core Location & Dispatch Vocabularies
    {"id": "coquitlam-street-names-1", "file": "data/vocabulary/coquitlam_streets.txt"},
    {"id": "map-grid-numbers", "file": "data/vocabulary/map_grid_numbers.txt"},
    
    # Custom Vocabularies
    {"id": "cfr-units", "file": "data/vocabulary/units_vocabulary.txt"},
    {"id": "cfr-call-types", "file": "data/vocabulary/call_types.txt"},
    {"id": "cfr-radio-channels", "file": "data/vocabulary/radio_channels.txt"},
    {"id": "cfr-keywords", "file": "data/vocabulary/keywords.txt"},
]

def create_resources():
    """Reads local text files and creates or updates CustomClass resources in Google Cloud."""
    print("--- Starting Google Cloud Adaptation Resource Creation ---")
    client = speech_v2.SpeechClient()
    parent = f"projects/{GCP_PROJECT_ID}/locations/global"

    for resource in RESOURCES:
        custom_class_id = resource["id"]
        file_path = resource["file"]
        print(f"\n--- Processing resource: '{custom_class_id}' from file '{file_path}' ---")

        try:
            with open(file_path, 'r') as f:
                # Read all lines, strip whitespace, and filter out empty lines
                items = [line.strip() for line in f if line.strip()]
            if not items:
                print(f"WARNING: File '{file_path}' is empty or contains only whitespace. Skipping.")
                continue
            print(f"Found {len(items)} items in '{file_path}'.")
        except FileNotFoundError:
            print(f"ERROR: File not found at '{file_path}'. Skipping.")
            continue

        # Create the CustomClass object with its items
        custom_class_obj = speech_v2.CustomClass(
            items=[speech_v2.CustomClass.ClassItem(value=item) for item in items]
        )

        # Create the request object to send to the API
        request = speech_v2.CreateCustomClassRequest(
            parent=parent,
            custom_class=custom_class_obj,
            custom_class_id=custom_class_id,
        )

        # Send the request to Google Cloud
        try:
            operation = client.create_custom_class(request=request)
            print(f"Sending request to create '{custom_class_id}'... This may take a moment.")
            response = operation.result() # This waits for the operation to complete
            print(f"SUCCESS: Successfully created CustomClass: {response.name}")
        except AlreadyExists:
            print(f"INFO: Resource '{custom_class_id}' already exists. To force an update, please delete the Custom Class from the Google Cloud Console and re-run this script.")
        except Exception as e:
            print(f"ERROR: An unexpected error occurred while creating '{custom_class_id}': {e}")

if __name__ == "__main__":
    # Best practice is to set this environment variable, but we also check for gcloud login as a fallback.
    if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        print("INFO: GOOGLE_APPLICATION_CREDENTIALS environment variable is not set.")
        print("Please ensure you have authenticated with 'gcloud auth application-default login' in your terminal.")
    
    create_resources()
    print("\n--- Resource processing complete. ---")