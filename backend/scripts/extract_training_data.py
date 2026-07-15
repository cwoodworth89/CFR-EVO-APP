# backend/scripts/extract_training_data.py
import os
import csv
import sys
import logging
import requests

def load_env():
    # Simple parser for .env
    env = {}
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if "=" in line and not line.strip().startswith("#"):
                    parts = line.strip().split("=", 1)
                    env[parts[0].strip()] = parts[1].strip()
    return env

def learn_new_incident_types(records, base_dir):
    """
    Scans retrieved verified records for 'verified_incident' values.
    If any verified incident type is not in the local call_types.txt,
    it automatically appends it to the file.
    """
    vocab_path = os.path.join(base_dir, "data", "vocabulary", "call_types.txt")
    if not os.path.exists(vocab_path):
        vocab_path = os.path.join(base_dir, "call_types.txt")
        if not os.path.exists(vocab_path):
            logging.warning(f"Could not find call_types.txt at {vocab_path}. Skipping dynamic vocabulary update.")
            return

    # 1. Read existing call types to avoid duplicates
    existing_types = set()
    try:
        with open(vocab_path, "r", encoding="utf-8") as f:
            for line in f:
                line_clean = f.name if hasattr(f, 'name') else '' # dummy line just to read
                line_clean = line.strip()
                if line_clean and not line_clean.startswith("#"):
                    existing_types.add(line_clean.lower())
    except Exception as e:
        logging.error(f"Failed to read call_types.txt for duplicate check: {e}")
        return

    # 2. Extract new types from records
    new_types_to_append = []
    for r in records:
        v_inc = r.get("verified_incident")
        if v_inc:
            v_inc_clean = v_inc.strip()
            if v_inc_clean and v_inc_clean.lower() not in existing_types:
                new_types_to_append.append(v_inc_clean)
                existing_types.add(v_inc_clean.lower())

    # 3. Append new types to the file
    if new_types_to_append:
        logging.info(f"Learned {len(new_types_to_append)} new incident types: {new_types_to_append}")
        try:
            # Check if we need to write a newline first
            prepend_newline = False
            if os.path.exists(vocab_path) and os.path.getsize(vocab_path) > 0:
                with open(vocab_path, "r", encoding="utf-8") as f:
                    f.seek(0, os.SEEK_END)
                    # read last char
                    try:
                        f.seek(f.tell() - 1)
                        if f.read(1) != "\n":
                            prepend_newline = True
                    except Exception:
                        pass
            
            with open(vocab_path, "a", encoding="utf-8") as f:
                if prepend_newline:
                    f.write("\n")
                f.write("\n# --- Dynamically Learned Call Types ---\n")
                for nt in new_types_to_append:
                    f.write(f"{nt}\n")
            logging.info(f"Successfully appended learned call types to {vocab_path}.")
        except Exception as e:
            logging.error(f"Failed to append new call types to call_types.txt: {e}")

def normalize_transcript_raw(verified_text: str) -> str:
    # 1. Convert everything to lowercase
    text = verified_text.lower()
    
    # 2. Remove all standard punctuation marks
    punctuation_to_remove = [".", ",", ";", ":", "?", "!", '"', "'"]
    for char in punctuation_to_remove:
        text = text.replace(char, "")
        
    # 3. Clean up internal spaces
    return " ".join(text.strip().split())

def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    
    # 1. Load config
    env = load_env()
    supabase_url = env.get("SUPABASE_URL")
    supabase_key = env.get("SUPABASE_SERVICE_ROLE_KEY") or env.get("SUPABASE_KEY")
    
    if not supabase_url or not supabase_key:
        logging.error("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY/SUPABASE_KEY in .env")
        sys.exit(1)
        
    # 2. Setup folders
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    training_dir = os.path.join(base_dir, "data", "training")
    audio_dir = os.path.join(training_dir, "audio")
    os.makedirs(audio_dir, exist_ok=True)
    
    # 3. Query verified dispatches
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}"
    }
    
    # We query records where feedback_submitted is true
    endpoint = f"{supabase_url.rstrip('/')}/rest/v1/live_calls?feedback_submitted=eq.true&verified_transcript=not.is.null"
    logging.info(f"Querying verified calls from Supabase: {endpoint}")
    
    try:
        response = requests.get(endpoint, headers=headers, timeout=15)
        response.raise_for_status()
        records = response.json()
    except Exception as e:
        logging.error(f"Failed to fetch records: {e}")
        sys.exit(1)
        
    logging.info(f"Found {len(records)} verified records in database.")
    
    # 3b. Learn and append any new verified incident types
    learn_new_incident_types(records, base_dir)
    
    if not records:
        logging.info("No verified data to extract. Add some human-in-the-loop reviews in the UI first.")
        return
        
    # 4. Process and download audios
    csv_rows = []
    downloaded_count = 0
    
    for r in records:
        dispatch_id = r.get("dispatch_id")
        audio_url = r.get("audio_url")
        verified_text = r.get("verified_transcript", "").strip()
        raw_text = r.get("raw_transcript", "").strip()
        
        if not dispatch_id or not verified_text:
            continue
            
        file_name = f"{dispatch_id}.wav"
        local_path = os.path.join(audio_dir, file_name)
        
        # Download audio if not cached locally
        if audio_url and not os.path.exists(local_path):
            download_url = audio_url
            if "/object/public/" in audio_url:
                download_url = audio_url.replace("/object/public/", "/object/authenticated/")
                
            logging.info(f"Downloading audio for {dispatch_id} from {download_url}...")
            try:
                audio_response = requests.get(download_url, headers=headers, timeout=20)
                audio_response.raise_for_status()
                with open(local_path, "wb") as f:
                    f.write(audio_response.content)
                downloaded_count += 1
            except Exception as e:
                logging.warning(f"Failed to download audio for {dispatch_id}: {e}")
                continue
                
        # Clean and normalize transcript to raw format (lowercase, no punctuation)
        normalized_text = normalize_transcript_raw(verified_text)
        
        # If call is a double-round dispatch (duration > 25s), duplicate the text label
        duration = r.get("audio_duration") or 0.0
        if duration > 25.0 and normalized_text:
            normalized_text = f"{normalized_text} {normalized_text}"
            
        csv_rows.append({
            "file_name": file_name,
            "verified_transcript": normalized_text,
            "raw_transcript": raw_text
        })
        
    # 5. Write metadata.csv
    metadata_csv_path = os.path.join(training_dir, "metadata.csv")
    logging.info(f"Writing metadata entries to {metadata_csv_path}...")
    
    try:
        with open(metadata_csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["file_name", "verified_transcript", "raw_transcript"])
            writer.writeheader()
            writer.writerows(csv_rows)
    except Exception as e:
        logging.error(f"Failed to write metadata.csv: {e}")
        sys.exit(1)
        
    # 6. Update database model_updated flag for successfully synced dispatches
    synced_ids = [r.get("dispatch_id") for r in records if r.get("dispatch_id")]
    if synced_ids:
        logging.info(f"Updating model_updated status for {len(synced_ids)} calls in database...")
        chunk_size = 50
        for i in range(0, len(synced_ids), chunk_size):
            chunk = synced_ids[i:i+chunk_size]
            id_filter = ",".join(f"{id_val}" for id_val in chunk)
            patch_url = f"{supabase_url.rstrip('/')}/rest/v1/live_calls?dispatch_id=in.({id_filter})"
            try:
                patch_response = requests.patch(patch_url, headers=headers, json={"model_updated": True})
                patch_response.raise_for_status()
                logging.info(f"  Successfully marked chunk of {len(chunk)} dispatches as synced.")
            except Exception as e:
                logging.warning(f"  Failed to update model_updated flag for chunk: {e}")

    logging.info(f"SUCCESS: Dataset sync complete. {len(csv_rows)} rows cached. {downloaded_count} new WAV files downloaded.")

if __name__ == "__main__":
    main()
