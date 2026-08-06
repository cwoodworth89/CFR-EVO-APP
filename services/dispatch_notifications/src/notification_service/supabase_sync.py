# NOTE: Legacy forwarder module - use notification_service.dispatch_persistence instead
from notification_service.dispatch_persistence import (
    save_dispatch_record as post_to_local_api,
    save_dispatch_record as post_to_supabase,
    update_dispatch_record as update_supabase_record,
    save_audio_recording as upload_to_supabase_storage,
    LOCAL_API_URL
)

