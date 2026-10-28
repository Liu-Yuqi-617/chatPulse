import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.config import get_settings
from app.analysis import AnalysisService
from app.models import DashboardState, QuestionStatus, SimulationRequest
from app.state import SCENARIOS, store
from app.twitch import TwitchService

settings = get_settings()
twitch = TwitchService(settings, store)
analysis = AnalysisService(settings, store)


@asynccontextmanager
async def lifespan(_: FastAPI):
    analysis.start()
    yield
    await analysis.stop()
    await twitch.disconnect()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", tags=["system"])
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "ai": "configured" if analysis.configured else "not_configured",
    }


@app.post("/api/analysis/run", tags=["analysis"])
async def run_analysis() -> dict[str, bool | str | None]:
    if not analysis.configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Qwen API configuration is missing",
        )
    try:
        updated = await analysis.analyze_latest(force=True)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Qwen analysis failed",
        ) from exc
    return {"updated": updated, "model": settings.soclaas_model, "error": analysis.error}


@app.get("/api/auth/twitch/login", tags=["authentication"])
async def twitch_login() -> RedirectResponse:
    try:
        return RedirectResponse(twitch.login_url())
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


@app.get("/api/auth/twitch/callback", tags=["authentication"])
async def twitch_callback(code: str, state: str) -> RedirectResponse:
    try:
        await twitch.authorize(code, state)
    except (ValueError, RuntimeError, KeyError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Twitch authorization failed. Verify the callback URL and credentials.",
        ) from exc
    return RedirectResponse(f"{settings.frontend_origin}?twitch=connected")


@app.get("/api/auth/status", tags=["authentication"])
async def auth_status() -> dict:
    return twitch.status()


@app.post("/api/auth/twitch/disconnect", tags=["authentication"])
async def twitch_disconnect() -> dict:
    await twitch.disconnect()
    return twitch.status()


@app.post("/api/twitch/track", tags=["twitch"])
async def track_twitch_stream() -> dict:
    try:
        return await twitch.track_live_stream()
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@app.get("/api/state", response_model=DashboardState, tags=["dashboard"])
async def get_state() -> DashboardState:
    return store.snapshot()


@app.get("/api/dev/scenarios", tags=["development"])
async def get_scenarios() -> dict[str, list[str]]:
    return {"scenarios": list(SCENARIOS)}


@app.post("/api/dev/simulate", response_model=DashboardState, tags=["development"])
async def simulate_chat(request: SimulationRequest) -> DashboardState:
    try:
        return store.simulate(request.scenario)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@app.post(
    "/api/questions/{question_id}/{action}",
    response_model=DashboardState,
    tags=["questions"],
)
async def update_question(question_id: str, action: QuestionStatus) -> DashboardState:
    try:
        return store.update_question(question_id, action)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found",
        ) from exc


@app.delete("/api/spotlight", response_model=DashboardState, tags=["spotlight"])
async def clear_spotlight() -> DashboardState:
    return store.clear_spotlight()


async def stream_state(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            await websocket.send_json(store.snapshot().model_dump(mode="json"))
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass


@app.websocket("/ws/dashboard")
async def dashboard_websocket(websocket: WebSocket) -> None:
    await stream_state(websocket)


@app.websocket("/ws/overlay")
async def overlay_websocket(websocket: WebSocket) -> None:
    await stream_state(websocket)

