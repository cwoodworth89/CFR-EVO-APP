# cfr_dispatch/__init__.py
# Modular Dispatch Mapping Package

import os

def _load_env():
    # Load .env file from the root directory relative to this file
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dotenv_path = os.path.join(root_dir, ".env")
    if os.path.exists(dotenv_path):
        with open(dotenv_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip()
                    # Strip quotes if they surround the value
                    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
                        value = value[1:-1]
                    
                    os.environ[key] = value

_load_env()

# Suppress Hugging Face cache symlink warnings on Windows
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

# Dynamically append sibling services to sys.path
import sys
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
workspace_dir = os.path.dirname(root_dir)
services_dir = os.path.join(workspace_dir, "services")
for service_name in ["gis", "audio_analysis", "dispatch_notifications"]:
    pkg_src = os.path.abspath(os.path.join(services_dir, service_name, "src"))
    if os.path.exists(pkg_src) and pkg_src not in sys.path:
        sys.path.append(pkg_src)

from cfr_dispatch.orchestration import run_dispatch_system, setup_logging
from cfr_dispatch.stt import transcribe_audio_local, transcribe_audio_file_local
from cfr_dispatch.pipeline import Phase1Result, Phase2Result, build_dispatch_payload

__all__ = [
    'run_dispatch_system',
    'setup_logging',
    'transcribe_audio_local',
    'transcribe_audio_file_local',
    'Phase1Result',
    'Phase2Result',
    'build_dispatch_payload'
]

