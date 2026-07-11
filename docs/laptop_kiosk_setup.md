# CFR EVO: Laptop Kiosk Deployment & Setup Guide
## Repurposed Lenovo Flex 5 + Behringer UCA202

This guide outlines the step-by-step setup to turn a repurposed **Lenovo Flex 5** touchscreen laptop and a **Behringer UCA202/UCA222 USB Audio Interface** into a dedicated, self-maintaining, and fully remote-manageable station dispatch kiosk.

---

## 📋 System Architecture

```mermaid
flowchart TD
    subgraph Station Audio Rack
        A[ART 341 Graphic EQ] -->|Unused 1/4" OUT| B[Line-Level Signal]
    end

    subgraph Lenovo Flex 5 Kiosk
        B -->|1/4" TS to RCA Cable| C[Behringer UCA202 USB Card]
        C -->|USB Port| D[Python Listening Agent]
        D -->|Local WebSockets / Supabase| E[Chromium Kiosk Screen]
        F[GitHub Remote Repo] -->|Auto-Updates Cron| E
    end
```

---

## 💿 Step 1: OS Selection & Installation

For repurposed laptops, we recommend **Lubuntu 24.04 LTS** (which uses the extremely lightweight LXQt desktop environment) or standard **Ubuntu 24.04 LTS**. Lubuntu runs on minimal memory and CPU resources, ensuring the maximum computing power is allocated to local Whisper transcription.

1.  Download the **Lubuntu 24.04 LTS** ISO.
2.  Flash the ISO onto a USB drive using **Rufus** (Windows) or **BalenaEtcher**.
3.  Boot the Lenovo Flex 5 into the BIOS (press `F2` repeatedly on startup).
    *   *BIOS Setting*: Enable **Power On on AC Attach** (or similar) if available, so the laptop boots automatically if it ever drains its battery completely and power is restored.
4.  Boot from the USB drive and run the installer.
5.  **Crucial Setup Choice**: In the installer screen, under the user account creation section, ensure you tick the box for **"Log in automatically without asking for a password"**.

---

## 🔧 Step 2: OS Optimization (Lid Switch & Sleeping)

Since the laptop will be folded into tablet mode or mounted, you must configure the OS to ignore lid-close actions and completely disable display sleeping.

### 1. Ignore Lid Close (Prevents Sleep when Folded)
Open a terminal and edit the system login configuration file:
```bash
sudo nano /etc/systemd/logind.conf
```
Uncomment and edit the following lines under the `[Login]` section:
```ini
[Login]
HandleLidSwitch=ignore
HandleLidSwitchExternalPower=ignore
HandleLidSwitchDocked=ignore
```
Save the file (`Ctrl+O`, `Enter`, `Ctrl+X`) and restart the login service to apply:
```bash
sudo systemctl restart systemd-logind
```

### 2. Disable Screen Blanking & Sleep
Run the following commands to tell the desktop manager never to lock the screen or put the display to sleep:
```bash
# Disable idle screen dimming and blanking
gsettings set org.gnome.desktop.session idle-delay 0
gsettings set org.gnome.desktop.screensaver lock-enabled false

# If using Lubuntu (LXQt), disable screen saving via settings:
# Settings -> LXQt settings -> Session Settings -> Basic Settings -> Disable Screen Saver.
```

## 🚀 Recommended: Automated Kiosk Installation

We have included a fully automated installation script `setup_kiosk.sh` in the root of the repository. Rather than performing all system configurations, folder permissions, cron jobs, and service creations manually, you can run this script to do everything for you.

### How to Run the Automated Setup
1.  Open a terminal on your Lenovo Flex 5 laptop.
2.  Clone the repository and enter the directory:
    ```bash
    git clone https://github.com/cwoodworth89/CFR-EVO-APP.git ~/CFR-EVO-APP
    cd ~/CFR-EVO-APP
    ```
3.  Make the setup script executable and run it:
    ```bash
    chmod +x setup_kiosk.sh
    ./setup_kiosk.sh
    ```
4.  Follow the post-setup checklist outputted by the script:
    *   Initialize Tailscale: `sudo tailscale up --ssh`
    *   Configure your environment variables: `nano backend/.env`
    *   Restart the agent: `sudo systemctl restart cfr-agent`

---

## 📦 Step 3: Application Installation & Setup (Manual Reference)

If you prefer to perform the configuration manually or want to understand what each systemd daemon, Nginx configuration, and cron scheduler is doing behind the scenes, you can follow these reference steps:

Clone the repository and install the dependencies:
```bash
git clone https://github.com/cwoodworth89/CFR-EVO-APP.git ~/CFR-EVO-APP
cd ~/CFR-EVO-APP

# Install system prerequisites
sudo apt update
sudo apt install -y python3-venv libportaudio2

# Set up virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

### 1. Host the React Frontend via Nginx
Compile the production build:
```bash
cd frontend
npm install
npm run build
```
This generates static files in `frontend/dist`.

Install Nginx:
```bash
sudo apt update
sudo apt install nginx -y
```
Configure Nginx to serve the build on port 80. Edit `/etc/nginx/sites-available/default`:
```nginx
server {
    listen 80 default_server;
    root /home/YOUR_USERNAME/CFR-EVO-APP/frontend/dist;
    index index.html;
    server_name _;

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```
*(Replace `YOUR_USERNAME` with your actual Ubuntu/Lubuntu username).*

Restart Nginx:
```bash
sudo systemctl restart nginx
```

### 2. Configure the Python Agent Service
Create a systemd service to run the listening backend. Create the file `/etc/systemd/system/cfr-agent.service`:
```ini
[Unit]
Description=CFR EVO Dispatch Listening Agent
After=network.target sound.target

[Service]
Type=simple
User=YOUR_USERNAME
Environment=XDG_RUNTIME_DIR=/run/user/YOUR_USER_ID
WorkingDirectory=/home/YOUR_USERNAME/CFR-EVO-APP/backend
ExecStart=/home/YOUR_USERNAME/CFR-EVO-APP/.venv/bin/python main.py
Restart=always
RestartSec=5
StandardOutput=syslog
StandardError=syslog
SyslogIdentifier=cfr-agent

[Install]
WantedBy=multi-user.target
```
*(Replace `YOUR_USERNAME` with your actual username, and `YOUR_USER_ID` with your Linux user ID. You can find your user ID by running `id -u YOUR_USERNAME` in the terminal. The first user created on Ubuntu is almost always `1000`).*

Enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable cfr-agent.service
sudo systemctl start cfr-agent.service
```

---

## 🔄 Step 4: Kiosk Mode & Auto-Updating (Self-Maintenance)

To make the kiosk maintenance-free, configure it to automatically update its operating system and automatically pull down code updates from GitHub.

### 1. Automatic OS Security Updates
Ensure Ubuntu handles system security updates automatically in the background:
```bash
sudo apt install unattended-upgrades -y
sudo dpkg-reconfigure --priority=low unattended-upgrades
```

### 2. Automatic Kiosk Code Updates (Git Auto-Pull)
We want the laptop to periodically check your GitHub repository. If you push a code change (e.g., frontend styling or parser updates), the laptop should pull the update, rebuild the client files, and restart the backend agent.

Create an update script `~/CFR-EVO-APP/update_kiosk.sh`:
```bash
#!/bin/bash

# Configuration
USER_DIR="/home/YOUR_USERNAME"
PROJECT_DIR="${USER_DIR}/CFR-EVO-APP"

cd "$PROJECT_DIR" || exit 1

# Fetch remote changes
git fetch origin

LOCAL=$(git rev-parse @{0})
REMOTE=$(git rev-parse @{u})

if [ "$LOCAL" != "$REMOTE" ]; then
    echo "$(date): New update detected on GitHub! Updating..."
    
    # Pull changes
    git pull origin main
    
    # Rebuild frontend
    cd frontend || exit 1
    npm install
    npm run build
    
    # Restart services
    sudo systemctl restart cfr-agent.service
    sudo systemctl restart nginx
    
    echo "$(date): Kiosk updated and services restarted successfully."
else
    echo "$(date): Kiosk is up to date."
fi
```
*(Make sure to change `YOUR_USERNAME` inside the script).*

Make the script executable:
```bash
chmod +x ~/CFR-EVO-APP/update_kiosk.sh
```

Add a cron job to run this update check every night at 3:00 AM:
```bash
# Open user crontab
crontab -e
```
Add the following line at the bottom:
```cron
0 3 * * * /home/YOUR_USERNAME/CFR-EVO-APP/update_kiosk.sh >> /home/YOUR_USERNAME/kiosk_update.log 2>&1
```

### 3. Auto-Start Chromium in Kiosk Mode
Create a desktop autostart entry so Chromium launches in full-screen mode at startup.
Create the directory and file:
```bash
mkdir -p ~/.config/autostart
nano ~/.config/autostart/kiosk.desktop
```
Add the following configuration:
```ini
[Desktop Entry]
Type=Application
Name=CFR EVO Kiosk
Exec=chromium-browser --kiosk --noerrdialogs --disable-infobars --no-first-run --check-for-update-interval=31536000 http://localhost
X-GNOME-Autostart-enabled=true
```

---

## 🔒 Step 5: Tailscale & Remote Access

Tailscale allows you to SSH into the laptop or inspect the web dashboard remotely from your phone or secondary computer, even though the laptop is behind the fire station's secure firewall.

1.  Install Tailscale:
    ```bash
    curl -fsSL https://tailscale.com/install.sh | sh
    ```
2.  Authenticate and enable Tailscale SSH:
    ```bash
    sudo tailscale up --ssh
    ```
3.  Click the link generated in the terminal, log in, and authorize the device.
4.  Once connected, copy the laptop's Tailscale IP (e.g. `100.115.120.30`). You can now securely manage the kiosk remotely:
    *   **Remote Console**: `ssh YOUR_USERNAME@100.115.120.30`
    *   **Remote Dashboard**: Open your browser and go to `http://100.115.120.30`

---

## 📂 Step 6: Transferring Shapefiles & Credentials (SCP over Tailscale)

Because shapefiles (geocoding boundaries) and credential files (like `.env` and Google Service Account key JSON files) contain sensitive information and large datasets, they are gitignored and not pushed to GitHub. 

Now that both your development machine and the laptop are on the same Tailscale network, you can copy these files securely in seconds using `scp` (Secure Copy Protocol) directly from your development machine.

### 1. Transfer the Shapefiles
Open a terminal (PowerShell or Command Prompt) on your **development machine** and run the following:
```powershell
# Navigate to the local repository directory on Windows
cd \path\to\CFR-EVO-APP\backend

# Copy the entire data/ folder to the laptop (replace <laptop-tailscale-ip> and YOUR_USERNAME)
scp -r data YOUR_USERNAME@<laptop-tailscale-ip>:/home/YOUR_USERNAME/CFR-EVO-APP/backend/
```

### 2. Transfer Credentials (Optional)
You can also copy your locally configured `.env` file and Google JSON key directly:
```powershell
# Copy your local .env configuration file
scp .env YOUR_USERNAME@<laptop-tailscale-ip>:/home/YOUR_USERNAME/CFR-EVO-APP/backend/

# Copy your Google Application Credentials key file
scp gcp-service-account-key.json YOUR_USERNAME@<laptop-tailscale-ip>:/home/YOUR_USERNAME/CFR-EVO-APP/backend/
```

> [!CAUTION]
> **Git Discipline & Security**
> Ensure that you **never** commit or push your `.env` or `.json` credential files to public/private Git repositories. Keep them gitignored on all development workspaces.

---

## 🎤 Step 7: Audio Setup (UCA202 Integration)

1.  Plug the Behringer UCA202 into a USB port on the Lenovo Flex 5.
2.  Connect your station graphic equalizer or amp utility feed to the UCA202 **INPUT L/R** RCA ports.
3.  Verify the card is detected by ALSA:
    ```bash
    arecord -l
    ```
    Note the card index (e.g., `card 1`).
4.  Open `~/CFR-EVO-APP/backend/.env` and update the audio configuration:
    ```env
    AUDIO_DEVICE_ID=1  # Change to match card index from arecord -l
    STT_ENGINE=whisper # Recommend local whisper since the laptop has the CPU power for it
    WHISPER_MODEL=base # base is fast and accurate on x86 laptops
    ```
5.  Calibrate and test the audio levels:
    ```bash
    python backend/scripts/calibrate_audio_interactive.py
    ```
