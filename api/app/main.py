from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.logging_setup import configure_logging, get_logger

configure_logging()
log = get_logger(__name__)

app = FastAPI(title="Prime Index API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "version": app.version}


@app.on_event("startup")
def _startup() -> None:
    log.info("starting Prime Index API env=%s", settings.environment)
