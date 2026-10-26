from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.models import DashboardState, QuestionStatus, SimulationRequest
from app.state import SCENARIOS, store

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
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
    }


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

