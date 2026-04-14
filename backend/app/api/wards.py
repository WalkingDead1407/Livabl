from fastapi import APIRouter, HTTPException
from typing import List

from app.data.wards import get_all_wards, get_ward_by_id
from app.scoring.engine import compute_score
from app.schemas.ward import WardResponse, WardDetailResponse
import logging

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Wards"])


@router.get("/wards", response_model=List[WardResponse])
def list_wards():
    try:
        data = get_all_wards()
        return [
            {
            "id": w["id"],
            "name": w["name"],
            "city": w["city"],
            "score": w["score"],
            }
            for w in data
        ]
        logger.info(f"Successfully returned {len(response)} wards")
    except EmptyDatasetError:
        raise


@router.get("/wards/{ward_id}", response_model=WardDetailResponse)
def get_ward(ward_id: int):
    try:
        w = get_ward_by_id(ward_id)
        if not w:
            raise HTTPException(status_code=404, detail="Ward not found")
        score_result = compute_score(w)
        return {
        "id": w["id"],
        "name": w["name"],
        "city": w["city"],
        "score": score_result["score"],
        "metrics": score_result["metrics"],
        }
        logger.info(f"Successfully returned details for ward {ward_id}")
    except (WardNotFoundError, InvalidInputError, EmptyDatasetError):
        raise
