from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import experiments, health, jobs, users
from app.core.config import get_settings
from app.services.auth import SupabaseAuthMiddleware


settings = get_settings()

app = FastAPI(title="Cortex Lab API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SupabaseAuthMiddleware)

app.include_router(health.router, tags=["health"])
app.include_router(experiments.router, prefix="/api/experiments", tags=["experiments"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])
app.include_router(users.router, prefix="/api", tags=["users"])
