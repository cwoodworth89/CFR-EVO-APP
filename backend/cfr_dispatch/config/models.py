# NOTE: For parsed data models, segmentation layout, and integration options, see:
#   - docs/call_structure.md
#   - docs/dispatch_integration_options.md
from dataclasses import dataclass
from typing import Optional

@dataclass
class DispatchData:
    raw_text: str
    units: Optional[str] = None
    response_type: Optional[str] = None
    call_type: Optional[str] = None
    address: Optional[str] = None
    intersection: Optional[str] = None
    radio_channel: Optional[str] = None
    map_grid: Optional[str] = None
