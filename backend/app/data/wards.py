import json
from pathlib import Path
import logging
from typing import List, Optional, Dict, Any
from app.exceptions import WardNotFoundError, EmptyDatasetError, InvalidInputError, InvalidComparisonError

APP_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = APP_DIR.parent
DATA_PATH = BACKEND_DIR / "data" / "processed" / "wards_score.geojson"


logger = logging.getLogger(__name__)

def _ward_name(properties: dict, index: int) -> str:
    name = properties.get("Ward_Name")
    if isinstance(name, str) and name.strip():
        return name.strip()
    return f"Ward {index}"

def get_all_wards() -> List[Dict[str, Any]]:
    try:
        from app.data.ingestion import load_geojson
        data = load_geojson("wards_score.geojson")
        features = data.get("features", [])
        if not features:
            logger.error("Dataset is empty or missing features")
            raise EmptyDatasetError()

        wards = [{
                "id": i,
                "name": _ward_name(w["properties"], i),
                "city": "Delhi",
                "score": round(float(w["properties"].get("livability_score", 0)) * 100, 2),
                **w["properties"],}
            for i, w in enumerate(features)
        ]
        logger.info(f"Successfully retrieved {len(wards)} wards")
        return wards
    except EmptyDatasetError:
        raise
    except FileNotFoundError as e:
        logger.error(f"GeoJSON file not found: {e}")
        raise EmptyDatasetError()
    except Exception as e:
        logger.error(f"Error retrieving wards: {e}", exc_info=True)
        raise EmptyDatasetError()

def get_ward_by_id(ward_id) -> Optional[Dict[str, Any]]:
    if ward_id is None or ward_id == "":
        logger.warning("Empty ward_id provided")
        raise InvalidInputError("ward_id", "Ward ID cannot be empty")
    try:
        ward_id_int = int(ward_id)
    except (TypeError, ValueError):
        raise InvalidInputError("ward_id", "Ward ID must be an integer")
    wards = get_all_wards()
    if ward_id_int < 0 or ward_id_int >= len(wards):
        logger.warning(f"Ward with ID {ward_id} not found")
        raise WardNotFoundError(ward_id)

    logger.info(f"Successfully retrieved ward {ward_id}")
    return wards[ward_id_int]

def validate_ward_ids(ward_ids: List[str]) -> None:
    if not ward_ids:
        raise InvalidComparisonError("Ward IDs list cannot be empty")

    elif len(ward_ids) < 2:
        raise InvalidComparisonError("At least 2 wards are required for comparison")

    elif len(ward_ids) > 10:  # Optional: limit comparisons to 10 wards
        raise InvalidComparisonError("Cannot compare more than 10 wards at once")

    # Validate each ward exists
    wards = get_all_wards()
    available_ids = {str(w["id"]) for w in wards}

    for ward_id in ward_ids:
        if str(ward_id) not in available_ids:
            logger.warning(f"Ward ID {ward_id} does not exist during validation")
            raise InvalidComparisonError(f"Ward '{ward_id}' does not exist")
