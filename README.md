# ChatPulse

AI-powered Twitch audience engagement copilot for the Codex × TwitchCon Hackathon 2026.

## Prerequisites

- Node.js 24 or newer
- npm 11 or newer
- CPython 3.13 (project-local runtime managed with `uv`)
- uv
- Git

## Project structure

```text
ChatPulse/
├── backend/       FastAPI API
├── frontend/      React + TypeScript + Vite
└── docs/          PRD and development plan
```

## First-time setup

### Backend

```powershell
cd backend
uv python install 3.13 --install-dir .python --no-bin --no-registry --cache-dir .uv-cache
uv venv --python .\.python\cpython-3.13-windows-x86_64-none\python.exe .venv --cache-dir .uv-cache
uv pip install --python .\.venv\Scripts\python.exe -r requirements.txt --cache-dir .uv-cache
Copy-Item ..\.env.example .env
```

### Frontend

```powershell
cd frontend
npm install
```

## Run locally

Open two PowerShell terminals.

Backend:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

Frontend:

```powershell
cd frontend
npm run dev
```

- Dashboard: http://localhost:5173
- API health check: http://localhost:8000/api/health
- Interactive API docs: http://localhost:8000/docs

## Verify

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest

cd ..\frontend
npm run build
```

Copy `.env.example` to `.env` before adding local credentials. Never commit `.env`.

## Connect Twitch

Register the exact callback URL from `TWITCH_REDIRECT_URI` in the Twitch Developer Console, then set:

```env
TWITCH_CLIENT_ID=your-client-id
TWITCH_CLIENT_SECRET=your-client-secret
TWITCH_REDIRECT_URI=http://localhost:8000/api/auth/twitch/callback
TWITCH_SCOPES=user:read:chat
```

Restart the backend after changing environment variables. Open the Dashboard and select **Connect Twitch**. When the authorized channel goes live, select **Track streaming** beside the connect control. ChatPulse verifies the live stream, subscribes to `channel.chat.message` over EventSub WebSocket, and reconnects automatically. A blocking warning dialog appears if chat tracking drops while the stream is still live.

The right-hand Dashboard panel embeds the authorized channel's current broadcast with the official Twitch player. It is a streamer-side live preview only; the previous OBS/Spotlight output is not part of the current MVP.

For production, replace the callback and origins with their deployed HTTPS URLs in both the hosting environment and Twitch Developer Console. OAuth tokens are currently held in backend memory, so a backend restart requires reconnecting Twitch.

