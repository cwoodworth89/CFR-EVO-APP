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
                    
                    # Convert GOOGLE_APPLICATION_CREDENTIALS relative path to absolute
                    if key == "GOOGLE_APPLICATION_CREDENTIALS" and value and not os.path.isabs(value):
                        # Try to resolve relative to agent/ folder (root_dir)
                        abs_path = os.path.abspath(os.path.join(root_dir, value))
                        if os.path.exists(abs_path):
                            value = abs_path
                        else:
                            # Try to resolve relative to workspace root (parent of root_dir)
                            abs_path_parent = os.path.abspath(os.path.join(os.path.dirname(root_dir), value))
                            if os.path.exists(abs_path_parent):
                                value = abs_path_parent
                    
                    os.environ[key] = value

_load_env()
