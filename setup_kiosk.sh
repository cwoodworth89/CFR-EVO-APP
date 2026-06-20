#!/bin/bash
# ==============================================================================
# CFR EVO: Lenovo Flex 5 Ubuntu Kiosk Auto-Setup Script
# ==============================================================================

# Exit on error
set -e

PROJECT_DIR=$(pwd)
echo "Starting kiosk auto-setup in directory: ${PROJECT_DIR}"

# 1. Update package list and install system dependencies
echo "Installing system dependencies..."
sudo apt update
sudo apt install -y python3-venv python3-pip nginx chromium-browser unattended-upgrades curl git nodejs npm libportaudio2

# 2. Setup Python virtual environment & backend agent requirements
echo "Setting up Python virtual environment..."
python3 -m venv "${PROJECT_DIR}/.venv"
source "${PROJECT_DIR}/.venv/bin/activate"
echo "Installing agent requirements..."
pip install -r "${PROJECT_DIR}/backend/requirements.txt"
deactivate

# 3. Build the React frontend
echo "Installing frontend node packages and building static files..."
cd "${PROJECT_DIR}/frontend"
npm install
npm run build
cd "${PROJECT_DIR}"

# 4. Configure Nginx to serve the build locally
echo "Configuring Nginx..."
cat <<EOF | sudo tee /etc/nginx/sites-available/cfr-evo
server {
    listen 80 default_server;
    listen [::]:80 default_server;

    root ${PROJECT_DIR}/frontend/dist;
    index index.html;

    server_name _;

    location / {
        try_files \$uri \$uri/ /index.html;
    }
}
EOF

# Enable the configuration and restart Nginx
sudo ln -sf /etc/nginx/sites-available/cfr-evo /etc/nginx/default
sudo ln -sf /etc/nginx/sites-available/cfr-evo /etc/nginx/sites-enabled/default
sudo systemctl restart nginx

# 5. Create backend agent systemd service
echo "Creating cfr-agent systemd service..."
REAL_USER=${SUDO_USER:-$USER}
USER_UID=$(id -u ${REAL_USER})

cat <<EOF | sudo tee /etc/systemd/system/cfr-agent.service
[Unit]
Description=CFR EVO Dispatch Listening Agent
After=network.target sound.target

[Service]
Type=simple
User=${REAL_USER}
Environment=XDG_RUNTIME_DIR=/run/user/${USER_UID}
WorkingDirectory=${PROJECT_DIR}/backend
ExecStart=${PROJECT_DIR}/.venv/bin/python main.py
Restart=always
RestartSec=5
StandardOutput=syslog
StandardError=syslog
SyslogIdentifier=cfr-agent

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable cfr-agent.service
sudo systemctl start cfr-agent.service

# 6. Configure Lid Switch (prevent suspend when folded)
echo "Overriding lid close suspend settings..."
sudo sed -i 's/#HandleLidSwitch=suspend/HandleLidSwitch=ignore/' /etc/systemd/logind.conf
sudo sed -i 's/#HandleLidSwitchExternalPower=suspend/HandleLidSwitchExternalPower=ignore/' /etc/systemd/logind.conf
sudo sed -i 's/#HandleLidSwitchDocked=ignore/HandleLidSwitchDocked=ignore/' /etc/systemd/logind.conf
sudo systemctl restart systemd-logind

# 7. Disable screen blanking & locks in GNOME
echo "Disabling lock screen and display timeout..."
gsettings set org.gnome.desktop.session idle-delay 0
gsettings set org.gnome.desktop.screensaver lock-enabled false

# 8. Configure Chromium autostart kiosk mode
echo "Configuring kiosk browser autostart..."
mkdir -p ~/.config/autostart
cat <<EOF > ~/.config/autostart/kiosk.desktop
[Desktop Entry]
Type=Application
Name=CFR EVO Kiosk
Exec=chromium-browser --kiosk --noerrdialogs --disable-infobars --no-first-run --check-for-update-interval=31536000 http://localhost
X-GNOME-Autostart-enabled=true
EOF

# 9. Configure auto-updates for the kiosk (Git Auto-Pull and rebuild)
echo "Creating self-update script..."
cat <<EOF > "${PROJECT_DIR}/update_kiosk.sh"
#!/bin/bash
PROJECT_DIR="${PROJECT_DIR}"
cd "\${PROJECT_DIR}" || exit 1

# Fetch changes
git fetch origin

LOCAL=\$(git rev-parse @{0})
REMOTE=\$(git rev-parse @{u})

if [ "\${LOCAL}" != "\${REMOTE}" ]; then
    echo "\$(date): Update detected on GitHub! Syncing code..."
    git pull origin main
    
    # Rebuild frontend
    cd frontend || exit 1
    npm install
    npm run build
    
    # Restart services
    sudo systemctl restart cfr-agent.service
    sudo systemctl restart nginx
    echo "\$(date): Kiosk updated successfully."
else
    echo "\$(date): Kiosk is up to date."
fi
EOF

chmod +x "${PROJECT_DIR}/update_kiosk.sh"

# Schedule the update script in crontab (runs at 3:00 AM daily)
echo "Scheduling update cron job..."
(crontab -l 2>/dev/null | grep -F "update_kiosk.sh"; [ $? -ne 0 ] && echo "0 3 * * * ${PROJECT_DIR}/update_kiosk.sh >> ${PROJECT_DIR}/kiosk_update.log 2>&1") | crontab -

# Enable OS automatic security upgrades
echo "Enabling unattended-upgrades..."
sudo systemctl enable unattended-upgrades
sudo systemctl start unattended-upgrades

# 10. Install Tailscale
echo "Installing Tailscale..."
curl -fsSL https://tailscale.com/install.sh | sh

# Copy .env.example if .env does not exist
if [ ! -f "${PROJECT_DIR}/backend/.env" ]; then
    echo "Creating default .env configuration file..."
    cp "${PROJECT_DIR}/backend/.env.example" "${PROJECT_DIR}/backend/.env"
fi

echo "======================================================================"
echo " CFR EVO AUTO-SETUP COMPLETE!"
echo "======================================================================"
echo "To complete setup:"
echo "1. Run Tailscale authentication: 'sudo tailscale up --ssh'"
echo "2. Edit your environment config: 'nano ${PROJECT_DIR}/backend/.env'"
echo "3. Restart the agent after editing .env: 'sudo systemctl restart cfr-agent'"
echo "======================================================================"
