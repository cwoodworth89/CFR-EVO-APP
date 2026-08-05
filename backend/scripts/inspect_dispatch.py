import sys
import json
from backend.api.database import SessionLocal
from backend.api.models import LiveCallModel

def main():
    dispatch_id = sys.argv[1] if len(sys.argv) > 1 else "DISP-2026-16D5FA"
    db = SessionLocal()
    call = db.query(LiveCallModel).filter(LiveCallModel.dispatch_id == dispatch_id).first()
    if not call:
        print(f"Call {dispatch_id} not found.")
        return
    print("========================================")
    print(f"DISPATCH ID: {call.dispatch_id}")
    print(f"RAW TRANSCRIPT:\n{call.raw_transcript}")
    print("----------------------------------------")
    print(f"SANITIZED TRANSCRIPT:\n{call.sanitized_transcript}")
    print("----------------------------------------")
    print(f"VERIFIED TRANSCRIPT:\n{call.verified_transcript}")
    print("========================================")

if __name__ == "__main__":
    main()
