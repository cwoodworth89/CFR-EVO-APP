#!/usr/bin/env bash
# tools/install_dev_packages.sh
# Installs CFR EVO microservices into the active Python environment in editable mode (-e)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=========================================================="
echo " CFR EVO: Installing Sibling Services in Editable Mode   "
echo "=========================================================="

PYTHON_BIN="python3"
if [ -f "$REPO_ROOT/.venv/bin/python" ]; then
    PYTHON_BIN="$REPO_ROOT/.venv/bin/python"
    echo "Using virtualenv Python: $PYTHON_BIN"
fi

$PYTHON_BIN -m pip install --upgrade pip

echo ""
echo "[1/4] Installing services/gis..."
$PYTHON_BIN -m pip install -e "$REPO_ROOT/services/gis"

echo ""
echo "[2/4] Installing services/audio_analysis..."
$PYTHON_BIN -m pip install -e "$REPO_ROOT/services/audio_analysis"

echo ""
echo "[3/4] Installing services/dispatch_notifications..."
$PYTHON_BIN -m pip install -e "$REPO_ROOT/services/dispatch_notifications"

echo ""
echo "[4/4] Installing backend (cfr-dispatch)..."
$PYTHON_BIN -m pip install -e "$REPO_ROOT/backend"

echo ""
echo "Verifying native package imports..."
$PYTHON_BIN -c "import gis_service; import audio_service; import notification_service; import cfr_dispatch; print('>>> SUCCESS: All 4 microservices installed and resolved natively!')"

echo ""
echo "All packages ready for development!"
