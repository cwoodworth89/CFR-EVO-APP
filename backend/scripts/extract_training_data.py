# backend/scripts/extract_training_data.py
import os
import csv
import sys
import logging
import requests

# Set up paths so we can import cfr_dispatch package
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

from cfr_dispatch.parser import split_rounds
from cfr_dispatch.config import UNITS_VOCABULARY

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

def learn_new_incident_types(records, base_dir=None):
    """Adds HITL-verified incident types not yet in public.vocabulary.

    Previously this appended to data/vocabulary/call_types.txt. The parser reads
    vocabulary from public.vocabulary, and nothing synced the file back into the
    database, so every learned call type was stranded in a file the parser never read.
    Writes now go to the database directly, where the parser and the Whisper bias
    prompt both pick them up on next start.
    """
    import os
    from sqlalchemy import create_engine, text

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        logging.error("DATABASE_URL is not set. Cannot record learned incident types.")
        return

    try:
        engine = create_engine(db_url)
        with engine.begin() as conn:
            existing = {
                r[0].strip().lower()
                for r in conn.execute(text(
                    "SELECT term FROM public.vocabulary WHERE category = 'call_type'"
                )).fetchall() if r[0]
            }

            learned = []
            for r in records:
                v_inc = (r.get("verified_incident") or "").strip()
                if v_inc and v_inc.lower() not in existing:
                    learned.append(v_inc)
                    existing.add(v_inc.lower())

            if not learned:
                logging.info("No new incident types to learn.")
                return

            for term in learned:
                conn.execute(text("""
                    INSERT INTO public.vocabulary
                        (category, term, term_normalized, sort_order, source, is_active)
                    VALUES ('call_type', :term, lower(:term), 999, 'hitl_learned', TRUE)
                    ON CONFLICT DO NOTHING
                """), {"term": term})

            logging.info(
                f"Learned {len(learned)} new incident types into public.vocabulary "
                f"(source='hitl_learned'): {learned}"
            )
    except Exception as e:
        logging.error(f"Failed to record learned incident types in public.vocabulary: {e}")


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
    local_api_url = env.get("LOCAL_API_URL", "http://localhost:8000").rstrip("/")
    
    # 2. Setup folders
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    training_dir = os.path.join(base_dir, "data", "training")
    audio_dir = os.path.join(training_dir, "audio")
    os.makedirs(audio_dir, exist_ok=True)
    
    # 3. Query verified dispatches from local database API
    endpoint = f"{local_api_url}/api/dispatches?limit=500"
    logging.info(f"Querying verified calls from local API gateway: {endpoint}")
    
    try:
        response = requests.get(endpoint, timeout=15)
        response.raise_for_status()
        all_records = response.json()
        records = [r for r in all_records if r.get("feedback_submitted") and r.get("verified_transcript")]
    except Exception as e:
        logging.error(f"Failed to fetch records: {e}")
        sys.exit(1)
        
    logging.info(f"Found {len(records)} verified records in local database.")

    
    # 3b. Learn and append any new verified incident types
    learn_new_incident_types(records)
    
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
        
        # Respect dataset opt-in/opt-out flag inside target JSONB
        target = r.get("target") or {}
        if isinstance(target, str):
            try:
                import json
                target = json.loads(target)
            except Exception:
                target = {}
        
        include_in_training = target.get("include_in_training", True)
        if not include_in_training:
            logging.info(f"Skipping call {dispatch_id} (explicitly excluded from training dataset).")
            continue
            
        if not dispatch_id or not verified_text:
            continue
            
        file_name = f"{dispatch_id}.wav"
        local_path = os.path.join(audio_dir, file_name)
        
        # Download audio if not cached locally
        if audio_url and not os.path.exists(local_path):
            download_url = audio_url
            # If URL is a relative path, prepends the local API url
            if download_url.startswith("/"):
                download_url = f"{local_api_url}{download_url}"
                
            logging.info(f"Downloading audio for {dispatch_id} from {download_url}...")
            try:
                audio_response = requests.get(download_url, timeout=20)
                audio_response.raise_for_status()
                with open(local_path, "wb") as f:
                    f.write(audio_response.content)
                downloaded_count += 1
            except Exception as e:
                logging.warning(f"Failed to download audio for {dispatch_id}: {e}")
                continue
                
        # Clean and normalize transcript to raw format (lowercase, no punctuation)
        normalized_text = normalize_transcript_raw(verified_text)
        
        # If call is a double-round dispatch (duration > 25s), duplicate the text label ONLY if it doesn't already contain multiple rounds
        duration = r.get("audio_duration") or 0.0
        if duration > 25.0 and normalized_text:
            rounds = split_rounds(normalized_text, UNITS_VOCABULARY)
            if len(rounds) < 2:
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
        for id_val in synced_ids:
            patch_url = f"{local_api_url}/api/dispatches/{id_val}"
            try:
                patch_response = requests.patch(patch_url, json={"model_updated": True}, timeout=10)
                patch_response.raise_for_status()
            except Exception as e:
                logging.warning(f"  Failed to update model_updated flag for dispatch {id_val}: {e}")

    logging.info(f"SUCCESS: Dataset sync complete. {len(csv_rows)} rows cached. {downloaded_count} new WAV files downloaded.")

if __name__ == "__main__":
    main()
