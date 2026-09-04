import os
import sys
from sqlalchemy import text

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # tools/, for _repo
from _repo import BACKEND
backend_dir = str(BACKEND)
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

from api.database import engine

def backfill():
    with engine.connect() as conn:
        query = text("""
            UPDATE dispatches 
            SET audio_url = '/api/audio/' || dispatch_id || '.wav' 
            WHERE audio_url IS NULL AND dispatch_id IS NOT NULL;
        """)
        res = conn.execute(query)
        conn.commit()
        print(f"Successfully backfilled audio_url for {res.rowcount} dispatches in local PostgreSQL database.")

if __name__ == "__main__":
    backfill()

