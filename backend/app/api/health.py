from fastapi import APIRouter
from app.cache import data_cache
import logging

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Health"])

@router.get("/health")
def health_check():
    return {
        "status": "healthy" if data_cache.is_loaded() else "degraded",
        "api": "running",
        "cache": {
            "loaded": data_cache.is_loaded(),
            "size": data_cache.size(),
            "status": "ready" if data_cache.is_loaded() else "loading"
        }
    }

@router.get("/cache/stats")
def cache_stats():
    return {
        "cache_loaded": data_cache.is_loaded(),
        "num_wards": data_cache.size(),
        "thread_safe": True
    }
