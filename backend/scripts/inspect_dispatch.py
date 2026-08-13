import sys
import json
from cfr_dispatch.database import get_db_session
from sqlalchemy import text

def main():
    dispatch_id = sys.argv[1] if len(sys.argv) > 1 else "DISP-2026-2659EC"
    with get_db_session() as session:
        result = session.execute(
            text("SELECT * FROM dispatches WHERE dispatch_id = :id OR incident_number = :id"),
            {"id": dispatch_id}
        ).mappings().first()
        
        if not result:
            print(f"Dispatch '{dispatch_id}' not found in database.")
            return

        call_data = dict(result)
        print(json.dumps(call_data, indent=2, default=str))

if __name__ == "__main__":
    main()
