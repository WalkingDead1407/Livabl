from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import health, wards, compare
import logging
from app.config import setup_logging

logger = logging.getLogger(__name__)
setup_logging()
app = FastAPI(title="Livebl API"
              decription="Quality of Life Index"
              version="1.0.0")


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

app.include_router(health.router)
app.include_router(wards.router)
app.include_router(compare.router)


