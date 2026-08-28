from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.api import health, wards, compare
from app.cache import data_cache
from app.data.ingestion import load_geojson
from app.config import setup_logging
import logging
from app.api import health, wards, compare, metrics

logger = logging.getLogger(__name__)
setup_logging()
app = FastAPI(title="Livebl API",
              decription="Quality of Life Index",
              version="1.0.1")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(
        f"Unhandled exception: {exc}",
        extra={
            "path": request.url.path,
            "method": request.method,
            "client": request.client
        },
        exc_info=True
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An unexpected error occurred. Please try again later.",
            "path": request.url.path
        }
    )
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"message": "Livebl API running"}

@app.on_event("startup")
async def startup_event():
    try:
        logger.info("Starting Livebl API...")
        # Load data into cache
        data_cache.load(load_geojson, "wards_score.geojson")
        logger.info(
            f"Cache loaded successfully with {data_cache.size()} wards"
        )
    except Exception as e:
        logger.error(
            f"Failed to load cache on startup: {e}. "
            f"API will return 503 until data is available.",
            exc_info=True
        )

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Livebl API shutting down...")
    data_cache.clear()
    logger.info("✓ Cache cleared")


app.include_router(health.router)
app.include_router(wards.router)
app.include_router(compare.router)
app.include_router(metrics.router)

