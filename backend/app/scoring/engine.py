from typing import Dict, Any


def compute_score(ward: Dict[str, Any]) -> Dict[str, Any]:
    keys = [
        "livability_score",
        "hospital_score",
        "school_score",
        "pollution_score",
        "landfill_score",
    ]

    values = [float(ward.get(k, 0)) for k in keys]
    if not values:
        return {"score": 0, "metrics": {}}

    score = sum(values) / len(values)

    return {
        "score": round(score, 2),
        "metrics": {k: ward.get(k, 0) for k in keys},
    }
