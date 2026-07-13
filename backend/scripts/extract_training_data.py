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
                
        csv_rows.append({
            "file_name": file_name,
            "verified_transcript": verified_text,
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
