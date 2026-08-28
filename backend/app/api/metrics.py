import logging
from fastapi import APIRouter, Query
from app.scoring.metrics import calculate_environment_score
from app.services.landfill_service import get_landfill_metrics

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/metrics", tags=["Metrics"])

@router.get("/landfill")
def landfill_metrics(
    lat: float = Query(..., description="Latitude of the point to score"),
    lng: float = Query(..., description="Longitude of the point to score"),
    city: str = Query("Delhi", description="City to search for landfill sites in"),
    pollution_score: float | None = Query(
        None,
        ge=0,
        le=1,
        description="Optional 0-1 pollution_score to also return a combined environment_score",
    ),
):
    """live landfill-proximity penalty and score for any lat/lng.
    coomputes distance to the nearest real landfill (fetched from OpenStreetMap, cached ~24h) on the fly -- call this directly no offline pipeline to run first."""
    result = get_landfill_metrics(lat, lng, city)
    if pollution_score is not None:
        result["environment_score"] = calculate_environment_score(
            pollution_score, result["distance_km"]
        )
    return result
