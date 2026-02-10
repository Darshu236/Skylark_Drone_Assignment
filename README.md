# Skylark Drone Assignment

# Drone Operations Coordinator AI Agent (Skylark Assignment)

This is a lightweight, deployable prototype of an AI agent that coordinates pilots, drones, and missions. It provides:
- Conversational API (`/chat`)
- Roster management with status updates
- Assignment matching
- Drone inventory queries
- Conflict detection
- Optional 2-way Google Sheets sync (pilot and drone status updates)

## Quick Start (Local)

```bash
python -m venv .venv
./.venv/Scripts/activate
pip install -r requirements.txt
python app.py
```

Then open `http://localhost:8000`.

## Streamlit Demo (Required Prototype)

Run the Streamlit UI:

```bash
streamlit run streamlit_app.py
```

This provides the hosted-demo friendly interface. Deploy using Streamlit Community Cloud or any platform that supports Streamlit.

## Google Sheets Setup (2-way sync)

This app can read/write to Google Sheets using a service account.

1. Create a Google Cloud project and enable Google Sheets API.
2. Create a service account and download JSON credentials.
3. Share your Pilot and Drone sheets with the service account email.
4. Set environment variables:

```bash
set GOOGLE_SERVICE_ACCOUNT_JSON=C:\path\to\service-account.json
set PILOT_SHEET_ID=your_google_sheet_id
set PILOT_SHEET_TAB=PilotRoster
set DRONE_SHEET_ID=your_google_sheet_id
set DRONE_SHEET_TAB=DroneFleet
```

If env vars are missing, the app falls back to CSV files in the repo.

## Data Files

- `pilot_roster.csv`
- `drone_fleet.csv`
- `missions.csv`

## API

`POST /chat` with JSON:

```json
{ "message": "find available mapping pilots in Bangalore" }
```

## Deployment

This app is compatible with Render, Railway, HuggingFace Spaces, or Vercel (via container or Python runtime).

Recommended: Render Web Service
- Build command: `pip install -r requirements.txt`
- Start command: `python app.py`
