# CFR-EVO-APP (Coquitlam Fire Responder - Evolution Application)

A unified monorepo containing the station-side microphone listener agent (backend) and the interactive driver training / dispatch mapping client (frontend) for Coquitlam Fire Rescue.

---

## 📂 Repository Structure

The project is structured as a monorepo separating concerns clearly by directory:

```
CFR-EVO-APP/
│
├── agent/                       # Station Dispatch Microphone Agent (Python)
│   ├── cfr_dispatch/            # Modular DSP, Parser, GIS, & Integration engine
│   ├── audio_files/             # Locution dispatch audio fingerprints and recordings
│   ├── data/                    # Shapefiles for parcel geocoding and emergency zones (git-ignored)
│   ├── main.py                  # Root listener entry point
│   ├── requirements.txt         # Python library dependencies
│   └── .env                     # Local environment credentials (git-ignored)
│
├── client/                      # Interactive Drivers Aid & Training Board (React / Vite)
│   ├── src/                     # React components, map layers, and Supabase client config
│   ├── public/                  # Static assets and training mock datasets
│   ├── package.json             # Node package specifications
│   └── .env.local               # Frontend local environment credentials (git-ignored)
│
└── .github/
    └── workflows/
        └── deploy.yml           # Automated GitHub Pages CI/CD build/deploy pipeline
```

---

## 📡 Database Architecture (Supabase)

Both components interface asynchronously using **Supabase**:
1. The **Python Agent** listens for Locution radio dispatches, transcribes the audio, geocodes coordinates, and inserts a payload into the `live_calls` table using the secure `service_role` key.
2. The **React Client** listens to the `live_calls` table using Realtime WebSockets. When a dispatch occurs, the browser displays visual alarms, suggests driving routes, highlights hydrants, and opens the admin interface for ground-truth review.

---

## 🚀 Getting Started

### 1. Backend Agent (`/agent`)
The backend listener runs on local station hardware (e.g. Raspberry Pi) connected to a radio feed.

```bash
# Navigate to agent directory
cd agent

# Install dependencies
pip install -r requirements.txt

# Setup your local environment credentials in a .env file:
# SUPABASE_URL=https://your-project.supabase.co
# SUPABASE_SERVICE_ROLE_KEY=your-secret-key

# Run the listener
python main.py
```

### 2. Frontend client (`/client`)
The interactive map dashboard is built with React, Tailwind CSS, and Leaflet.

```bash
# Navigate to client directory
cd client

# Install packages
npm install

# Setup your local environment credentials in a .env.local file:
# VITE_SUPABASE_URL=https://your-project.supabase.co
# VITE_SUPABASE_ANON_KEY=your-public-anon-key

# Run development server
npm run dev
```

---

## 🛠️ GitHub Pages Deployment

The React client is automatically built and deployed to GitHub Pages via GitHub Actions.
* **Workflow**: `.github/workflows/deploy.yml` runs on every push to the `main` branch.
* **Secrets Required**: Make sure to set `VITE_SUPABASE_ANON_KEY` in your GitHub Repository settings (**Settings -> Secrets and variables -> Actions**) to allow the runner to bake the key into the production build.
