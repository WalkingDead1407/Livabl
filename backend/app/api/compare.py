from fastapi import APIRouter, HTTPException
from app.data.wards import get_ward_by_id
from app.scoring.engine import compute_score
from app.schemas.ward import CompareResponse
import logging
from typing import List

router = APIRouter(tags=["Compare"])
logger = logging.getLogger(__name__)

@router.get("/compare", response_model=CompareResponse)
def compare_route(ward1: int, ward2: int):
    try:
        w1 = get_ward_by_id(ward1)
        w2 = get_ward_by_id(ward2)

        if not w1 or not w2:
            raise HTTPException(status_code=404, detail="Invalid Ward IDs")
        score1 = compute_score(w1)
        score2 = compute_score(w2) 
        return {
            "ward1": {
                "id": w1["id"],
                "name": w1["name"],
                "city": w1["city"],
                "score": round(score1["score"], 2),
                "metrics": score1["metrics"]
            },
            "ward2": {
                "id": w2["id"],
                "name": w2["name"],
                "city": w2["city"],
                "score": round(score2["score"], 2),
                "metrics": score2["metrics"]
            }
        }
        logger.info(f"Successfully compared {len(wards_to_compare)} wards")
    except InvalidComparisonError:
        raise
    except EmptyDatasetError:
        raise
